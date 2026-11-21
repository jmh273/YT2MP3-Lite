import asyncio
import json
import os
import pathlib
import re
import shutil
import sys
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# 受管 yt-dlp 必須在 import yt_dlp 之前掛上 finder，否則會先載到內建版本而無法覆蓋。
# 受管版本不存在或損毀時，activate 會自動退回內建版本。
from ytdlp_loader import activate_managed_ytdlp

activate_managed_ytdlp()

import yt_dlp
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


# ── Bundle / dev path resolution ──────────────────────────────────────────────
def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _resource_path(name: str) -> pathlib.Path:
    """Locate a resource by name.

    Frozen (PyInstaller onedir/onefile): try the bundle's data dir first
    (sys._MEIPASS = `_internal/` in onedir; a temp dir in onefile), then fall
    back to the exe's directory (where build.bat drops external assets like
    ffmpeg.exe / mp3gain.exe / deno.exe).
    Dev: next to backend/main.py.
    """
    if _is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidate = pathlib.Path(meipass) / name
            if candidate.exists():
                return candidate
        return pathlib.Path(sys.executable).parent / name
    return pathlib.Path(__file__).parent / name


def _setup_bundled_path() -> None:
    """In a frozen bundle, prepend the exe's directory to PATH so that bundled
    ffmpeg.exe / mp3gain.exe are picked up by shutil.which() and subprocess calls."""
    if _is_frozen():
        bundle_dir = str(pathlib.Path(sys.executable).parent)
        os.environ["PATH"] = bundle_dir + os.pathsep + os.environ.get("PATH", "")


_setup_bundled_path()


# ── JavaScript runtime（yt-dlp 解 YouTube nsig challenge 用） ──────────────────
# yt-dlp 需要真正的 JS runtime 才能解開 YouTube 的 n challenge；缺了它產出的媒體
# URL 會被 YouTube 拒絕（HTTP 403），下載全面失敗。runtime 隨發行版散布，路徑明確
# 指定而不依賴使用者 PATH——否則機器上剛好有的其他版本會被誤用。
_JS_RUNTIME_NAME = "deno.exe" if os.name == "nt" else "deno"


def _js_runtime_path() -> pathlib.Path | None:
    """回傳隨程式散布的 JS runtime 路徑；找不到回 None。

    Frozen：與 exe 同目錄（build.bat 把 deno.exe 複製到 bundle 根目錄）。
    Dev：repo 的 tools/（與 ffmpeg.exe / mp3gain.exe 同一個位置）。
    """
    if _is_frozen():
        candidate = pathlib.Path(sys.executable).parent / _JS_RUNTIME_NAME
    else:
        candidate = pathlib.Path(__file__).parent.parent / "tools" / _JS_RUNTIME_NAME
    return candidate if candidate.is_file() else None


def _check_js_runtime() -> None:
    """啟動時檢查 runtime 是否可用。不可用時明確告警，不要無聲降級——
    否則使用者只會在下載階段看到難以理解的 403。"""
    path = _js_runtime_path()
    if path is None:
        print(
            f"[JS] 警告：找不到 {_JS_RUNTIME_NAME}。yt-dlp 將無法解開 YouTube 的 "
            f"nsig challenge，下載很可能全面失敗（HTTP 403）。",
            flush=True,
        )
        return
    if not os.access(path, os.X_OK):
        print(f"[JS] 警告：{path} 存在但無法執行。下載很可能失敗。", flush=True)
        return
    print(f"[JS] JavaScript runtime: {path}", flush=True)


_check_js_runtime()


# ── 路徑設定 ──────────────────────────────────────────────────────────────────
# 與完整版 YT_to_MP3(~/.yt-mp3-tool/)分開,兩者可裝在同一台電腦互不干擾。
CONFIG_DIR = pathlib.Path.home() / ".yt2mp3-lite"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "output_path": str(pathlib.Path.home() / "Music" / "YT-MP3"),
    "normalize_target_db": 89.0,
    # 給朋友用:同一個 IP 短時間大量下載容易被 YouTube 限速,預設比完整版(3)保守。
    "download_concurrency": 2,
    # YouTube player client 優先序。yt-dlp 的預設選擇會落到 android_vr 並回 403,
    # 必須明確指定。可經設定覆寫,讓 YouTube 換封鎖對象時不必重新發版。
    "youtube_player_clients": ["tv", "android", "mweb", "tv_simply"],
    # GVS PO Token。缺少時 YouTube 不提供 audio-only 格式,只能退而下載
    # progressive 影片再抽音軌(音質較低、流量較大)。格式為 yt-dlp 的
    # "<client>.gvs+<token>",例如 "mweb.gvs+XXXX"。目前無法自動取得,需手動填入。
    "youtube_po_tokens": [],
    "download_retries": 3,
    "download_retry_backoff": 2.0,
}

MP3GAIN_TOLERANCE_DB = 0.75
MP3GAIN_REFERENCE_DB = 89.0  # mp3gain default target = ReplayGain reference

CONFIG_DIR.mkdir(exist_ok=True)


# ── 下載診斷 log ──────────────────────────────────────────────────────────────
# yt-dlp 的警告是判斷失敗根因的主要依據，但 console 視窗一關就沒了。寫進檔案，
# 讓故障在事後仍可追查，並讓每一次重試嘗試都留下紀錄而非只有最後一次。
LOG_DIR = CONFIG_DIR / "logs"
DOWNLOAD_LOG_FILE = LOG_DIR / "download.log"

_download_logger: "logging.Logger | None" = None


def _get_download_logger() -> "logging.Logger":
    global _download_logger
    if _download_logger is not None:
        return _download_logger

    import logging
    from logging.handlers import RotatingFileHandler

    logger = logging.getLogger("yt2mp3_lite.download")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                DOWNLOAD_LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
            )
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)-7s %(message)s")
            )
            logger.addHandler(handler)
        except OSError:
            # 無法寫 log 不該讓下載失敗
            logger.addHandler(logging.NullHandler())
    _download_logger = logger
    return logger


class _YdlLogger:
    """把 yt-dlp 的輸出導向下載 log，並標註是哪支影片的第幾次嘗試。

    yt-dlp 會把 info 級訊息也送到 debug()，因此 debug 只在訊息看起來像警告時才記，
    避免把逐秒的進度輸出灌進檔案。"""

    def __init__(self, video_id: str, attempt: int):
        self._prefix = f"[{video_id} 第{attempt}次] "
        self._log = _get_download_logger()

    def debug(self, msg):
        text = str(msg)
        if text.startswith("[debug] "):
            return
        if "WARNING" in text or "ERROR" in text:
            self._log.warning(self._prefix + text)

    def info(self, msg):
        pass  # 逐項進度不入檔，避免淹沒真正的診斷訊息

    def warning(self, msg):
        self._log.warning(self._prefix + str(msg))

    def error(self, msg):
        self._log.error(self._prefix + str(msg))


def log_download_failure(video_id: str, attempt: int, message: str) -> None:
    _get_download_logger().error(f"[{video_id} 第{attempt}次] 失敗：{message}")


def _read_version() -> str:
    vfile = _resource_path("_version.txt")
    if vfile.exists():
        try:
            return vfile.read_text(encoding="utf-8").strip() or "0.0.0-dev"
        except OSError:
            return "0.0.0-dev"
    return "0.0.0-dev"


__version__ = _read_version()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if shutil.which("ffmpeg") is None:
        print(
            "\033[91m[警告] 找不到 ffmpeg!MP3 轉換功能將無法使用。"
            "請安裝 ffmpeg 並將其加入 PATH,然後重新啟動。\033[0m"
        )
    else:
        import subprocess
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        version_line = result.stdout.splitlines()[0] if result.stdout else "unknown"
        print(f"[OK] ffmpeg 已就緒:{version_line}")
    print(f"[OK] yt2mp3-lite v{__version__}")
    yield


app = FastAPI(title="YT → MP3 Lite", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 下載進度佇列（全域） ────────────────────────────────────────────────────────
download_progress: dict[str, dict] = {}

# ── 音量正規化進度與目錄鎖（全域） ────────────────────────────────────────────────
normalize_progress: dict[str, dict] = {}
_active_normalize_dirs: set[str] = set()



# ── 工具函式 ───────────────────────────────────────────────────────────────────
import locale as _locale
_FS_ANSI_ENCODING = _locale.getpreferredencoding(False)


def _sanitize_filename(name: str) -> str:
    """Strip characters that mp3gain (Windows ANSI argv) cannot handle from a YouTube title.

    Step 1: keep ASCII alphanumerics, spaces, `.-_()`, CJK Unified Ideographs (BMP + Extension A);
            replace everything else (full-width punctuation, emoji, symbols) with `_`.
    Step 2: drop any remaining character that the active system codepage cannot encode (e.g. CJK
            ideographs like U+7287 that are in the Unicode block but NOT in CP950 / CP936 / etc.).
            Without this, Windows argv Wide→ANSI conversion would corrupt the subprocess call
            and mp3gain.exe would fail to open the file.
    """
    import re
    if not name:
        return "untitled"
    safe = re.sub(r"[^\w\s一-鿿㐀-䶿().\-]", "_", name)
    out_chars = []
    for c in safe:
        try:
            c.encode(_FS_ANSI_ENCODING)
        except UnicodeEncodeError:
            out_chars.append("_")
        else:
            out_chars.append(c)
    safe = "".join(out_chars)
    safe = re.sub(r"\s+", " ", safe)
    safe = re.sub(r"_+", "_", safe)
    safe = safe.strip(" ._")
    if not safe:
        return "untitled"
    return safe[:120]


_HIGHLIGHT_PREFIX_RE = re.compile(r"^精華[ _]?")


def _strip_highlight_prefix(stem: str) -> str:
    """Normalize away a leading `【精華】` highlight marker on a sanitized stem.

    `_sanitize_filename("【精華】My Talk")` yields `精華_My Talk` (full-width 【】 → `_`,
    leading `_` stripped, `】` → `_`). For "is this already downloaded?" comparisons we
    want `【精華】xxx` to match a plain `xxx` re-upload, so we drop a single leading `精華`
    token plus any immediately following separator. Only the start of the stem is touched;
    an interior `精華` (e.g. `年度精華回顧`) is left intact.
    """
    return _HIGHLIGHT_PREFIX_RE.sub("", stem, count=1)


_SETTINGS_RANGES = {
    "normalize_target_db": ((int, float), 80.0, 100.0),
    "output_path": (str, None, None),
    "youtube_player_clients": (list, None, None),
    "youtube_po_tokens": (list, None, None),
    "download_retries": (int, 0, 10),
    "download_retry_backoff": ((int, float), 0.5, 60.0),
}


def load_settings() -> dict:
    """Tolerant load: legacy / out-of-range / wrong-type values for known keys are
    silently reset to defaults; unknown keys are preserved untouched."""
    raw: dict = {}
    if SETTINGS_FILE.exists():
        try:
            raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raw = {}
        except (json.JSONDecodeError, OSError):
            raw = {}
    merged = {**DEFAULT_SETTINGS, **raw}
    for key, (expected_type, lo, hi) in _SETTINGS_RANGES.items():
        value = merged.get(key)
        if not isinstance(value, expected_type):
            merged[key] = DEFAULT_SETTINGS[key]
            continue
        if lo is not None and hi is not None and not (lo <= value <= hi):
            merged[key] = DEFAULT_SETTINGS[key]
    return merged


def save_settings(data: dict):
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 設定路由 ───────────────────────────────────────────────────────────────────
@app.get("/settings")
def get_settings():
    return load_settings()


class SettingsUpdate(BaseModel):
    output_path: str | None = None
    normalize_target_db: float | None = None
    download_concurrency: int | None = Field(default=None, ge=1, le=8)


@app.put("/settings")
def update_settings(body: SettingsUpdate):
    settings = load_settings()
    if body.output_path is not None:
        p = pathlib.Path(body.output_path)
        p.mkdir(parents=True, exist_ok=True)
        settings["output_path"] = str(p)
    if body.normalize_target_db is not None:
        if not (80.0 <= body.normalize_target_db <= 100.0):
            raise HTTPException(status_code=422, detail="normalize_target_db 必須介於 80.0 到 100.0 之間(dB SPL)")
        settings["normalize_target_db"] = body.normalize_target_db
    if body.download_concurrency is not None:
        settings["download_concurrency"] = body.download_concurrency
    save_settings(settings)
    return settings


# ── 搜尋影片路由 ───────────────────────────────────────────────────────────────
def _sync_search_videos_yt_dlp(keyword: str) -> list[dict]:
    import yt_dlp
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "default_search": "ytsearch50",
    }
    
    videos = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch50:{keyword}", download=False)
            if "entries" in info:
                for entry in info["entries"]:
                    if not entry:
                        continue
                    
                    video_id = entry.get("id")
                    if not video_id:
                        continue
                        
                    duration = entry.get("duration")
                            
                    thumbnails = entry.get("thumbnails", [])
                    thumbnail_url = thumbnails[0].get("url") if thumbnails else f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"
                            
                    videos.append({
                        "video_id": video_id,
                        "title": entry.get("title", ""),
                        "published": "",
                        "thumbnail": thumbnail_url,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "channel_id": entry.get("channel_id", ""),
                        "channel_title": entry.get("uploader", ""),
                        "duration_seconds": duration,
                    })
        except Exception as e:
            print(f"[yt-dlp Search Error] {e}")
            
    return videos

@app.get("/search-videos")
async def search_videos(q: str):
    if not q or not q.strip():
        return {"videos": []}
    
    videos = await asyncio.to_thread(_sync_search_videos_yt_dlp, q.strip())
    return {"videos": videos}



# ── 網址預覽路由 ───────────────────────────────────────────────────────────────
def _sync_url_preview_yt_dlp(url: str) -> list[dict]:
    import yt_dlp
    ydl_opts = {
        "quiet": True,
        "extract_flat": "in_playlist",
    }

    videos = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            if not info:
                return []
                
            entries = info.get("entries")
            if entries is None:
                entries = [info]  # 單一影片
                
            for entry in entries:
                if not entry:
                    continue
                
                video_id = entry.get("id")
                if not video_id:
                    continue
                    
                duration = entry.get("duration")
                        
                thumbnails = entry.get("thumbnails", [])
                thumbnail_url = thumbnails[0].get("url") if thumbnails else f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"
                        
                videos.append({
                    "video_id": video_id,
                    "title": entry.get("title", ""),
                    "published": "",
                    "thumbnail": thumbnail_url,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "channel_id": entry.get("channel_id", ""),
                    "channel_title": entry.get("uploader", ""),
                    "duration_seconds": duration,
                })
        except Exception as e:
            print(f"[yt-dlp URL Preview Error] {e}")
            raise HTTPException(status_code=400, detail=f"網址解析失敗: {e}")
            
    return videos

@app.get("/url-preview")
async def url_preview(url: str):
    if not url or not url.strip():
        raise HTTPException(status_code=400, detail="網址不能為空")
    
    videos = await asyncio.to_thread(_sync_url_preview_yt_dlp, url.strip())
    return {"videos": videos}


# ── 下載路由 ───────────────────────────────────────────────────────────────────
class DownloadRequest(BaseModel):
    videos: list[dict]  # [{video_id, title, url}]
    format: str = "mp3"   # "mp3" | "mp4"
    quality: int = 192    # mp3: kbps; mp4: p
    seq_enabled: bool = True
    start_seq: str | None = Field(default=None, pattern=r"^\d{1,10}$")
    target_dir: str | None = None


_MP3_QUALITIES = (128, 192, 256, 320)
_MP4_QUALITIES = (360, 480, 720, 1080)
_FORMAT_DEFAULT_QUALITY = {"mp3": 192, "mp4": 720}


def _normalize_format_quality(fmt: str | None, quality: int | None) -> tuple[str, int]:
    """白名單外的值無聲修正為該格式預設；未知格式回退 mp3 / 192。"""
    f = fmt if fmt in _FORMAT_DEFAULT_QUALITY else "mp3"
    allowed = _MP3_QUALITIES if f == "mp3" else _MP4_QUALITIES
    q = quality if isinstance(quality, int) and quality in allowed else _FORMAT_DEFAULT_QUALITY[f]
    return f, q


_SEQ_PREFIX_RE = None


def _today_download_dir() -> pathlib.Path:
    """Return today's date subdirectory under the configured output_path (local time)."""
    from datetime import datetime
    settings = load_settings()
    return pathlib.Path(settings.get("output_path", "")) / datetime.now().strftime("%Y%m%d")


def _resolve_output_child(output_path: str, child: str | None) -> pathlib.Path:
    from datetime import datetime
    base = pathlib.Path(output_path).resolve()
    name = child if child is not None and child.strip() else datetime.now().strftime("%Y%m%d")
    if "/" in name or "\\" in name or name in ("", ".", ".."):
        raise HTTPException(status_code=400, detail="target_dir must be a child folder name")
    target = (base / _sanitize_filename(name)).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=400, detail="target_dir escapes output_path")
    return target


def _format_seq(n: int) -> str:
    """Zero-pad to 2 digits, auto-widen past 99 (07 / 99 / 100 / 121)."""
    width = max(2, len(str(n)))
    return f"{n:0{width}d}"


def _scan_next_seq(directory: pathlib.Path) -> int:
    """Return the next sequence number for filenames matching `^(\\d+)_` in *directory*.

    Scans all entries regardless of extension (mp3 / mp4 / .part) so mixed-format
    batches share the same counter. Missing directory or no matches → 1.
    """
    import re
    global _SEQ_PREFIX_RE
    if _SEQ_PREFIX_RE is None:
        _SEQ_PREFIX_RE = re.compile(r"^(\d+)_")
    try:
        entries = list(directory.iterdir())
    except (FileNotFoundError, NotADirectoryError):
        return 1
    max_seq = 0
    for entry in entries:
        if not entry.is_file():
            continue
        m = _SEQ_PREFIX_RE.match(entry.name)
        if m:
            n = int(m.group(1))
            if n > max_seq:
                max_seq = n
    return max_seq + 1


def _scan_existing_seqs(directory: pathlib.Path) -> list[int]:
    """Return ascending list of every numeric prefix found in *directory*."""
    import re
    global _SEQ_PREFIX_RE
    if _SEQ_PREFIX_RE is None:
        _SEQ_PREFIX_RE = re.compile(r"^(\d+)_")
    try:
        entries = list(directory.iterdir())
    except (FileNotFoundError, NotADirectoryError):
        return []
    seqs: list[int] = []
    for entry in entries:
        if not entry.is_file():
            continue
        m = _SEQ_PREFIX_RE.match(entry.name)
        if m:
            seqs.append(int(m.group(1)))
    seqs.sort()
    return seqs


def _compute_seq_prefix(start_seq: str | None, default_next: int, idx: int) -> str:
    """Build the `nn_` prefix for the *idx*-th video in a batch.

    - `start_seq=None`: continue from scanned `default_next`, width = max(2, len(str(n))).
    - `start_seq` set: width follows the input string length, expanding when n outgrows it.
    """
    if start_seq is None:
        return f"{_format_seq(default_next + idx)}_"
    n = int(start_seq) + idx
    width = max(len(start_seq), len(str(n)))
    return f"{n:0{width}d}_"


def _build_ydl_opts(
    output_path: str,
    safe_title: str,
    hook,
    fmt: str,
    quality: int,
    seq_prefix: str = "",
    player_clients: list[str] | None = None,
    po_tokens: list[str] | None = None,
) -> dict:
    base = {
        "outtmpl": os.path.join(output_path, f"{seq_prefix}{safe_title}.%(ext)s"),
        "progress_hooks": [hook],
        "quiet": True,
        # 刻意「不」設 no_warnings：yt-dlp 的警告是判斷失敗根因的主要依據
        # （缺 JS runtime、n challenge 解算失敗都只出現在警告裡）。壓掉它會讓
        # 下一次同類故障重新變成數小時的盲猜。
        # 分塊下載：googlevideo 對長連線的節流是已知問題，分塊可降低中途被斷的機率。
        "http_chunk_size": 10 * 1024 * 1024,
        "retries": 10,
        "fragment_retries": 10,
    }

    # JS runtime：yt-dlp 解 nsig challenge 必要。明確指定路徑，不依賴 PATH。
    # 結構為 {runtime: {config}}——Python API 與 CLI 的 "deno:PATH" 字串形式不同。
    runtime = _js_runtime_path()
    if runtime is not None:
        base["js_runtimes"] = {"deno": {"path": str(runtime)}}

    # player client：預設選擇會落到 android_vr 並回 403，必須明確指定。
    clients = player_clients or list(DEFAULT_SETTINGS["youtube_player_clients"])
    yt_args: dict[str, list[str]] = {"player_client": clients}
    # PO Token 有提供才帶。沒有的話 yt-dlp 會自動跳過需要它的格式並退回
    # progressive——可下載但音質較低，這是刻意的降級而非失敗。
    if po_tokens:
        yt_args["po_token"] = list(po_tokens)
    base["extractor_args"] = {"youtube": yt_args}
    if fmt == "mp4":
        return {
            **base,
            "format": (
                f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/"
                f"best[height<={quality}][ext=mp4]/best"
            ),
            "merge_output_format": "mp4",
        }
    # mp3 預設
    return {
        **base,
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": str(quality),
        }],
    }


# 實測（乾淨網路、官方 yt-dlp + deno）：tv / android / mweb / tv_simply 可下載；
# android_vr 拿得到 URL 但一律 403；web / ios / web_safari 只回圖片（需 PO Token）。
_BLOCKED_PLAYER_CLIENTS = frozenset({"android_vr", "web", "ios", "web_safari"})


def _resolve_player_clients(settings: dict, has_po_token: bool = False) -> list[str]:
    """讀取 player client 優先序；結果為空時退回預設。

    _BLOCKED_PLAYER_CLIENTS 之所以失效，是因為它們需要 GVS PO Token。使用者若已
    供給 token，就不該再擋——否則填了 token 也永遠用不到，PO Token 功能等於白做。
    """
    raw = settings.get("youtube_player_clients")
    if not isinstance(raw, list):
        raw = DEFAULT_SETTINGS["youtube_player_clients"]
    clients = [c.strip() for c in raw if isinstance(c, str) and c.strip()]
    if not has_po_token:
        clients = [c for c in clients if c not in _BLOCKED_PLAYER_CLIENTS]
    return clients or list(DEFAULT_SETTINGS["youtube_player_clients"])


def _resolve_po_tokens(settings: dict) -> list[str]:
    """讀取使用者提供的 GVS PO Token。格式不合的項目直接忽略，不讓設定錯誤中斷下載。"""
    raw = settings.get("youtube_po_tokens")
    if not isinstance(raw, list):
        return []
    return [t.strip() for t in raw if isinstance(t, str) and "+" in t and t.strip()]


def _resolve_retry_config(settings: dict) -> tuple[int, float]:
    """回傳 (最大重試次數, 退避基數秒)。沿用既有的容錯：值不合法即退回預設。"""
    try:
        retries = max(0, min(10, int(settings.get("download_retries", 3))))
    except (TypeError, ValueError):
        retries = 3
    try:
        backoff = max(0.5, min(60.0, float(settings.get("download_retry_backoff", 2.0))))
    except (TypeError, ValueError):
        backoff = 2.0
    return retries, backoff


def _resolve_concurrency(settings: dict) -> int:
    """Read download_concurrency from settings, clamp to 1..8, fallback 2 on missing/invalid."""
    raw = settings.get("download_concurrency", 2)
    try:
        return max(1, min(8, int(raw)))
    except (TypeError, ValueError):
        return 2


def run_download(
    videos: list[dict],
    output_path: str,
    task_id: str,
    fmt: str = "mp3",
    quality: int = 192,
    seq_enabled: bool = True,
    start_seq: str | None = None,
    concurrency: int = 1,
    player_clients: list[str] | None = None,
    po_tokens: list[str] | None = None,
    max_retries: int = 3,
    retry_backoff: float = 2.0,
):
    download_progress[task_id] = {"status": "running", "items": {}}

    for v in videos:
        vid = v["video_id"]
        download_progress[task_id]["items"][vid] = {"title": v["title"], "percent": 0, "speed": "", "status": "pending"}

    def make_hook(vid: str):
        def hook(d):
            if d["status"] == "downloading":
                pct_str = d.get("_percent_str", "0%").strip().replace("%", "")
                speed_str = d.get("_speed_str", "").strip()
                try:
                    pct = float(pct_str)
                except ValueError:
                    pct = 0
                download_progress[task_id]["items"][vid]["percent"] = pct
                download_progress[task_id]["items"][vid]["speed"] = speed_str
                download_progress[task_id]["items"][vid]["status"] = "downloading"
            elif d["status"] == "finished":
                download_progress[task_id]["items"][vid]["percent"] = 100
                download_progress[task_id]["items"][vid]["speed"] = ""
                download_progress[task_id]["items"][vid]["status"] = "converting"
        return hook

    default_next = _scan_next_seq(pathlib.Path(output_path))

    def download_one(idx: int, v: dict):
        """Download + convert a single video. Errors are caught per-video so a
        failure never aborts sibling downloads when running concurrently."""
        vid = v["video_id"]
        safe_title = _sanitize_filename(v.get("title", ""))
        # 序號前綴依批次內 idx 計算，與完成順序解耦 → 並行下檔名編號仍正確
        seq_prefix = _compute_seq_prefix(start_seq, default_next, idx) if seq_enabled else ""
        item = download_progress[task_id]["items"][vid]

        # 每次嘗試都重新建立 YoutubeDL 並重跑 download()，因而重新解析取得新的串流
        # URL。403 通常綁在特定一次解析的 URL 上，重用舊 URL 重試沒有意義。
        #
        # 退避等待發生在 semaphore 名額之內（並行模式下）。評估後接受此代價：
        # 預設最壞情況約 14 秒，換取序列與並行兩條路徑共用同一份重試邏輯。
        # 其他影片不會因此被中斷或誤標為失敗，僅是開始時間可能後延。
        last_error = "未知錯誤"
        for attempt in range(1, max_retries + 2):
            ydl_opts = _build_ydl_opts(
                output_path, safe_title, make_hook(vid), fmt, quality, seq_prefix,
                player_clients, po_tokens,
            )
            ydl_opts["logger"] = _YdlLogger(vid, attempt)
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([v["url"]])
                item["status"] = "done"
                item.pop("error", None)
                item.pop("attempt", None)
                return
            except Exception as e:
                last_error = str(e)
                log_download_failure(vid, attempt, last_error)
                if attempt > max_retries:
                    break
                item["status"] = "retrying"
                item["attempt"] = attempt
                item["error"] = last_error
                time.sleep(retry_backoff * (2 ** (attempt - 1)))

        item["status"] = "error"
        item["error"] = last_error
        item["attempt"] = max_retries + 1

    if concurrency <= 1 or len(videos) <= 1:
        for idx, v in enumerate(videos):
            download_one(idx, v)
    else:
        async def _coordinate():
            sem = asyncio.Semaphore(concurrency)

            async def _one(idx: int, v: dict):
                async with sem:
                    await asyncio.to_thread(download_one, idx, v)

            await asyncio.gather(*(_one(idx, v) for idx, v in enumerate(videos)))

        # run_download executes in a worker thread (run_in_executor), so it owns
        # no running loop here — asyncio.run is safe and keeps the sync interface.
        asyncio.run(_coordinate())

    download_progress[task_id]["status"] = "done"


@app.post("/download")
async def start_download(body: DownloadRequest):
    settings = load_settings()
    output_path = settings["output_path"]
    
    # 建立日期子目錄 YYYYMMDD
    final_output_path = _resolve_output_child(output_path, body.target_dir)
    
    final_output_path.mkdir(parents=True, exist_ok=True)

    import uuid
    task_id = str(uuid.uuid4())

    fmt, quality = _normalize_format_quality(body.format, body.quality)
    concurrency = _resolve_concurrency(settings)
    po_tokens = _resolve_po_tokens(settings)
    player_clients = _resolve_player_clients(settings, has_po_token=bool(po_tokens))
    max_retries, retry_backoff = _resolve_retry_config(settings)

    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        None,
        run_download,
        body.videos,
        str(final_output_path),
        task_id,
        fmt,
        quality,
        body.seq_enabled,
        body.start_seq,
        concurrency,
        player_clients,
        po_tokens,
        max_retries,
        retry_backoff,
    )

    return {"task_id": task_id, "directory": str(final_output_path.resolve())}


@app.get("/download/next-seq")
async def download_next_seq(target_dir: str | None = Query(default=None, alias="dir")):
    if target_dir is not None and target_dir.strip():
        settings = load_settings()
        scan_dir = _resolve_output_child(settings["output_path"], target_dir)
    else:
        scan_dir = _today_download_dir()
    existing = _scan_existing_seqs(scan_dir)
    next_n = (existing[-1] + 1) if existing else 1
    return {"next_seq": _format_seq(next_n), "existing": existing}


@app.get("/download/progress/{task_id}")
async def download_progress_sse(task_id: str):
    async def event_stream() -> AsyncGenerator[str, None]:
        while True:
            state = download_progress.get(task_id)
            if state is None:
                yield f"data: {json.dumps({'error': 'task not found'})}\n\n"
                break
            yield f"data: {json.dumps(state)}\n\n"
            if state.get("status") == "done":
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── 音量正規化（mp3gain 引擎） ────────────────────────────────────────────────
def _suggest_safe_filenames(filenames: list[str]) -> dict[str, str]:
    """Apply _sanitize_filename to each file's stem; disambiguate collisions with -2/-3 suffix."""
    out: dict[str, str] = {}
    seen: set[str] = set()
    for fn in filenames:
        stem, suffix = os.path.splitext(fn)
        sanitized_stem = _sanitize_filename(stem) or "untitled"
        candidate = f"{sanitized_stem}{suffix}"
        if candidate == fn:
            out[fn] = candidate
            seen.add(candidate)
            continue
        n = 2
        unique = candidate
        while unique in seen or unique in filenames:
            unique = f"{sanitized_stem}-{n}{suffix}"
            n += 1
        out[fn] = unique
        seen.add(unique)
    return out


def _list_mp3s(directory: pathlib.Path) -> list[dict]:
    raw_names = [
        e.name for e in directory.iterdir()
        if e.is_file() and e.suffix.lower() == ".mp3"
    ]
    raw_names.sort()
    suggestions = _suggest_safe_filenames(raw_names)
    files: list[dict] = []
    for name in raw_names:
        path = directory / name
        suggested = suggestions[name]
        files.append({
            "filename": name,
            "size_bytes": path.stat().st_size,
            "needs_rename": suggested != name,
            "suggested_name": suggested,
        })
    return files


def _run_mp3gain_analyze(input_path: pathlib.Path, target_db: float) -> dict:
    """Run mp3gain analysis (no modify). Returns measured + recommended dB change."""
    import subprocess
    import re

    delta = target_db - MP3GAIN_REFERENCE_DB
    # mp3gain (no -r/-a) only analyzes; -d shifts the target reference.
    cmd = ["mp3gain", "-q", "-d", f"{delta:.2f}", str(input_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"mp3gain analyze failed: {(proc.stderr or proc.stdout).strip()[-400:]}")

    m = re.search(r'Recommended\s+"?Track"?\s+dB\s+change[:=]\s*(-?\d+(?:\.\d+)?)', proc.stdout)
    if not m:
        raise RuntimeError(f"could not parse mp3gain output: {proc.stdout.strip()[-400:]}")
    recommended = float(m.group(1))
    # mp3gain doesn't directly report the file's current dB SPL; derive it:
    # recommended = target - measured, so measured = target - recommended
    measured = target_db - recommended
    return {"measured_db": measured, "recommended_db_change": recommended}


def _run_mp3gain_apply(input_path: pathlib.Path, target_db: float) -> None:
    """Apply mp3gain track gain in place (modifies frame headers, no audio re-encoding)."""
    import subprocess

    delta = target_db - MP3GAIN_REFERENCE_DB
    cmd = ["mp3gain", "-r", "-k", "-q", "-d", f"{delta:.2f}", str(input_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"mp3gain apply failed: {(proc.stderr or proc.stdout).strip()[-400:]}")


def run_normalize_batch(
    task_id: str,
    directory: str,
    filenames: list[str],
    target_db: float,
    concurrency: int = 1,
) -> None:
    state = normalize_progress[task_id]
    dir_path = pathlib.Path(directory)

    def normalize_one(filename: str) -> None:
        item = state["items"][filename]
        file_path = dir_path / filename
        try:
            item["status"] = "measuring"
            analyzed = _run_mp3gain_analyze(file_path, target_db)
            item["measured_db"] = analyzed["measured_db"]
            item["recommended_db_change"] = analyzed["recommended_db_change"]

            if abs(analyzed["recommended_db_change"]) < MP3GAIN_TOLERANCE_DB:
                item["status"] = "skipped"
                return

            item["status"] = "normalizing"
            _run_mp3gain_apply(file_path, target_db)
            item["status"] = "done"
        except Exception as e:
            item["status"] = "error"
            item["error"] = str(e)

    try:
        if concurrency <= 1 or len(filenames) <= 1:
            for filename in filenames:
                normalize_one(filename)
        else:
            async def _coordinate() -> None:
                sem = asyncio.Semaphore(concurrency)

                async def _one(filename: str) -> None:
                    async with sem:
                        await asyncio.to_thread(normalize_one, filename)

                await asyncio.gather(*(_one(filename) for filename in filenames))

            asyncio.run(_coordinate())
    finally:
        state["status"] = "done"
        _active_normalize_dirs.discard(directory)


@app.get("/normalize/list")
def normalize_list(dir: str):
    p = pathlib.Path(dir)
    if not p.is_dir():
        raise HTTPException(status_code=400, detail=f"目錄不存在或不是資料夾：{dir}")
    return {"directory": str(p), "files": _list_mp3s(p)}


class NormalizeStartRequest(BaseModel):
    directory: str
    filenames: list[str]
    target_db: float | None = None


@app.post("/normalize/start")
async def normalize_start(body: NormalizeStartRequest):
    if shutil.which("mp3gain") is None:
        raise HTTPException(
            status_code=503,
            detail="找不到 mp3gain，請安裝 mp3gain 並加入 PATH 後重新啟動後端",
        )

    if body.target_db is not None:
        if not (80.0 <= body.target_db <= 100.0):
            raise HTTPException(status_code=422, detail="target_db 必須介於 80.0 到 100.0 之間（dB SPL）")

    dir_path = pathlib.Path(body.directory)
    if not dir_path.is_dir():
        raise HTTPException(status_code=400, detail=f"目錄不存在或不是資料夾：{body.directory}")

    dir_resolved = dir_path.resolve()
    for fn in body.filenames:
        if "/" in fn or "\\" in fn or fn in ("", ".", ".."):
            raise HTTPException(status_code=400, detail=f"檔名不可含路徑分隔：{fn}")
        target = (dir_path / fn).resolve()
        try:
            target.relative_to(dir_resolved)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"檔案不在目錄內：{fn}")
        if not target.is_file():
            raise HTTPException(status_code=400, detail=f"檔案不存在：{fn}")

    dir_key = str(dir_resolved)
    if dir_key in _active_normalize_dirs:
        raise HTTPException(status_code=409, detail="該目錄已有正在執行的正規化任務")

    settings = load_settings()
    target_db = float(body.target_db if body.target_db is not None else settings.get("normalize_target_db", 89.0))
    concurrency = _resolve_concurrency(settings)

    import uuid
    task_id = str(uuid.uuid4())
    normalize_progress[task_id] = {
        "status": "running",
        "items": {
            fn: {
                "filename": fn,
                "status": "pending",
                "measured_db": None,
                "target_db": target_db,
                "recommended_db_change": None,
                "error": None,
            }
            for fn in body.filenames
        },
    }
    _active_normalize_dirs.add(dir_key)

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_normalize_batch, task_id, dir_key, body.filenames, target_db, concurrency)

    return {"task_id": task_id}


class NormalizeRenameRequest(BaseModel):
    directory: str
    renames: list[dict]  # [{"from": str, "to": str}]


@app.post("/normalize/rename")
def normalize_rename(body: NormalizeRenameRequest):
    dir_path = pathlib.Path(body.directory)
    if not dir_path.is_dir():
        raise HTTPException(status_code=400, detail=f"目錄不存在或不是資料夾：{body.directory}")
    dir_resolved = dir_path.resolve()

    # Validate every entry first
    pairs: list[tuple[str, str]] = []
    for entry in body.renames:
        src = entry.get("from", "")
        dst = entry.get("to", "")
        for label, val in (("from", src), ("to", dst)):
            if "/" in val or "\\" in val or val in ("", ".", ".."):
                raise HTTPException(status_code=400, detail=f"{label} 不可含路徑分隔：{val}")
            try:
                (dir_path / val).resolve().relative_to(dir_resolved)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"{label} 不在目錄內：{val}")
        pairs.append((src, dst))

    renamed: list[dict] = []
    skipped: list[dict] = []
    for src, dst in pairs:
        src_p = dir_path / src
        dst_p = dir_path / dst
        if not src_p.is_file():
            skipped.append({"from": src, "to": dst, "reason": "source missing"})
            continue
        if src == dst:
            skipped.append({"from": src, "to": dst, "reason": "no-op"})
            continue
        if dst_p.exists():
            skipped.append({"from": src, "to": dst, "reason": "target exists"})
            continue
        os.replace(str(src_p), str(dst_p))
        renamed.append({"from": src, "to": dst})

    if renamed:
        from datetime import datetime as _dt
        log_path = dir_path / "_rename_log.json"
        existing: list = []
        if log_path.exists():
            try:
                existing = json.loads(log_path.read_text(encoding="utf-8"))
                if not isinstance(existing, list):
                    existing = []
            except (json.JSONDecodeError, OSError):
                existing = []
        existing.append({"ts": _dt.now().isoformat(timespec="seconds"), "mappings": renamed})
        log_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"renamed": renamed, "skipped": skipped}


@app.get("/normalize/progress/{task_id}")
async def normalize_progress_sse(task_id: str):
    async def event_stream() -> AsyncGenerator[str, None]:
        while True:
            state = normalize_progress.get(task_id)
            if state is None:
                yield f"data: {json.dumps({'error': 'task not found'})}\n\n"
                break
            yield f"data: {json.dumps(state)}\n\n"
            if state.get("status") == "done":
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── 工作資料夾與版本 ──────────────────────────────────────────────────────────
def _list_work_folders(settings: dict) -> list[pathlib.Path]:
    """列 output_path 下的日期子資料夾，依名稱倒序。純 filesystem。"""
    output = pathlib.Path(settings["output_path"]).resolve()
    if not output.is_dir():
        return []
    return sorted((p for p in output.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True)


@app.get("/folders")
def list_folders():
    """列 output_path 下的工作資料夾（日期子資料夾）。純 filesystem。"""
    settings = load_settings()
    folders = [{"name": p.name, "directory": str(p)} for p in _list_work_folders(settings)]
    return {"folders": folders}


@app.get("/version")
def version():
    return {"version": __version__}


# ── yt-dlp 版本管理 ───────────────────────────────────────────────────────────
def _ejs_solver_status() -> tuple[str | None, bool]:
    """回傳 (版本, 是否真的可用)。

    打包後沒有 dist-info，只讀 importlib.metadata 會永遠是 None——那無法區分
    「沒裝」與「裝了但讀不到版本」。這裡直接 import yt-dlp 實際使用的模組來探測。
    """
    version = None
    try:
        import importlib.metadata as _md

        version = _md.version("yt-dlp-ejs")
    except Exception:
        pass
    try:
        import yt_dlp_ejs.yt.solver as _solver

        usable = bool(_solver.core()) and bool(_solver.lib())
        version = version or getattr(
            __import__("yt_dlp_ejs"), "version", None
        )
    except Exception:
        usable = False
    return version, usable


@app.get("/ytdlp/version")
def ytdlp_version():
    """目前生效的 yt-dlp / EJS solver 版本與來源（受管或內建）。"""
    import ytdlp_loader

    ejs_version, ejs_usable = _ejs_solver_status()
    return {
        "yt_dlp": yt_dlp.version.__version__,
        "yt_dlp_ejs": ejs_version,
        "yt_dlp_ejs_usable": ejs_usable,
        "source": ytdlp_loader.active_source(),
        "js_runtime": str(_js_runtime_path()) if _js_runtime_path() else None,
    }


@app.get("/ytdlp/latest")
def ytdlp_latest():
    """查詢上游最新版。離線時降級為「無法查詢」，不得讓既有安裝進入不可用狀態。"""
    import ytdlp_loader

    try:
        return {"available": True, "versions": ytdlp_loader.latest_versions()}
    except Exception as e:
        return {"available": False, "error": f"無法查詢上游版本：{e}"}


@app.post("/ytdlp/update")
def ytdlp_update():
    """下載並安裝最新的 yt-dlp + EJS solver（成組更新）。需重新啟動才會生效。"""
    import ytdlp_loader

    try:
        installed = ytdlp_loader.install_managed()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"更新失敗，維持目前版本：{e}")
    return {
        "installed": installed,
        "restart_required": True,
        "message": "更新完成，重新啟動程式後生效。",
    }


@app.post("/ytdlp/revert")
def ytdlp_revert():
    """移除受管版本，回退到發行版內建版本。需重新啟動才會生效。"""
    import ytdlp_loader

    ytdlp_loader.revert_to_bundled()
    return {"restart_required": True, "message": "已回退為內建版本，重新啟動後生效。"}


# ── SPA static mount (LAST: matches when no API route did) ───────────────────
class _SPAStaticFiles(StaticFiles):
    """StaticFiles 子類別：對 index.html 加上 no-cache header。

    SPA 的 index.html 永遠引用 content-hashed assets（如 LoginView-<hash>.js）。
    若瀏覽器快取舊版 index.html，升版後會請求已不存在的 chunk 檔名 → 404。
    對 index.html 強制 revalidate；hashed assets 仍可長期快取。
    """

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        # path == "" 是 mount root (回傳 index.html)；明確指定 index.html 也算
        if path in ("", "index.html"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


_static_dir = _resource_path("static")
if _static_dir.is_dir():
    app.mount("/", _SPAStaticFiles(directory=str(_static_dir), html=True), name="spa")
