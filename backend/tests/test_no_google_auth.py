"""守門:YT2MP3-Lite 不依賴任何 Google 授權。

規格(來源:拆分計畫 §5.5):
- 程式碼與 requirements 裡沒有 Google API / OAuth 套件,也沒有 require_credentials。
- 需要授權的路由(auth、訂閱、Drive、配額…)不存在。
- 任何路由都不會回 401。
- 發行包裡沒有 client_secret.json 或 Google API 套件(scripts/check_bundle.py)。

每道掃描式守門都先確認掃到已知錨點,再判斷禁止的東西;並在測試裡用好、壞兩份輸入
當對照組,證明判準會給出不同答案。
"""
import importlib.util
import io
import pathlib
import re
import tokenize
from unittest.mock import patch

import pytest
from fastapi.routing import APIRoute

import main

BACKEND = pathlib.Path(__file__).resolve().parent.parent
REPO = BACKEND.parent

FORBIDDEN_CODE = re.compile(
    r"^\s*(from|import)\s+(google|googleapiclient|google_auth_oauthlib|oauthlib)\b"
    r"|\brequire_credentials\b|\bload_credentials\b|\bclient_secret\.json\b",
    re.M,
)
FORBIDDEN_REQUIREMENT = re.compile(
    r"^\s*(google-auth|google-auth-oauthlib|google-api-python-client|google-auth-httplib2|oauthlib)\b",
    re.I | re.M,
)
# 原本需要授權、在 Lite 拿掉的路由前綴
REMOVED_ROUTE_PREFIXES = (
    "/auth", "/subscriptions", "/channels", "/drive", "/quota",
    "/latest-videos", "/trending-videos", "/discovery", "/search-channels",
)


def strip_python_comments(source: str) -> str:
    """去掉 # 註解(保留字串),避免註解裡提到套件名造成誤報。"""
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type != tokenize.COMMENT:
            out.append(tok)
    return tokenize.untokenize(out)


def strip_requirement_comments(text: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def forbidden_code_hits(source: str) -> list[str]:
    return [m.group(0).strip() for m in FORBIDDEN_CODE.finditer(strip_python_comments(source))]


def forbidden_requirement_hits(text: str) -> list[str]:
    return [m.group(0).strip() for m in FORBIDDEN_REQUIREMENT.finditer(strip_requirement_comments(text))]


def backend_sources() -> dict[str, str]:
    files = [BACKEND / "main.py", BACKEND / "__main__.py", BACKEND / "ytdlp_loader.py"]
    return {f.name: f.read_text(encoding="utf-8") for f in files}


# ── 對照組:判準本身對好、壞輸入給不同答案 ──────────────────────────────────────
def test_code_scanner_control_group():
    bad = "import os\nfrom googleapiclient.discovery import build\n"
    bad2 = "def f():\n    creds = require_credentials()\n"
    good = "import os\n# 以前用 from googleapiclient.discovery import build\nx = 'google'\n"
    assert forbidden_code_hits(bad)
    assert forbidden_code_hits(bad2)
    assert forbidden_code_hits(good) == []


def test_requirement_scanner_control_group():
    bad = "fastapi==1\ngoogle-auth==2.49.0\n"
    good = "fastapi==1\n# 刻意不依賴 google-auth、google-api-python-client\nyt-dlp==1\n"
    assert forbidden_requirement_hits(bad) == ["google-auth"]
    assert forbidden_requirement_hits(good) == []


# ── 真實檔案 ────────────────────────────────────────────────────────────────
def test_backend_code_has_no_google_auth():
    sources = backend_sources()
    # 錨點:確認讀到的是真正的後端,而不是空檔
    assert "def run_download(" in sources["main.py"]
    assert "import yt_dlp" in sources["main.py"]
    for name, src in sources.items():
        assert forbidden_code_hits(src) == [], name


def test_requirements_have_no_google_packages():
    text = (BACKEND / "requirements.txt").read_text(encoding="utf-8")
    assert re.search(r"^yt-dlp==", text, re.M), "錨點:requirements.txt 應該釘選 yt-dlp"
    assert forbidden_requirement_hits(text) == []


def test_google_packages_not_importable_in_test_env():
    """測試環境照 requirements 裝,Google 套件不該在;若在,上面的測試就無法證明程式不需要它。"""
    for mod in ("googleapiclient", "google_auth_oauthlib"):
        assert importlib.util.find_spec(mod) is None, mod


def test_no_auth_routes_registered():
    paths = {r.path for r in main.app.routes if isinstance(r, APIRoute)}
    # 錨點
    assert {"/download", "/url-preview", "/search-videos", "/download/next-seq"} <= paths
    leaked = sorted(p for p in paths if p.startswith(REMOVED_ROUTE_PREFIXES))
    assert leaked == []


# ── 任何路由都不回 401 ───────────────────────────────────────────────────────
def _fake_entries(*_args, **_kwargs):
    return [{"video_id": "abc", "title": "t", "url": "https://www.youtube.com/watch?v=abc"}]


async def test_no_get_route_returns_401(client, tmp_path):
    get_routes = [
        r for r in main.app.routes
        if isinstance(r, APIRoute) and "GET" in r.methods and "{" not in r.path
    ]
    assert len(get_routes) >= 8, "錨點:GET 路由數量異常,可能沒掃到"
    params = {"q": "lofi", "url": "https://www.youtube.com/watch?v=abc", "dir": str(tmp_path)}
    with patch("main._sync_search_videos_yt_dlp", side_effect=_fake_entries), \
         patch("main._sync_url_preview_yt_dlp", side_effect=_fake_entries), \
         patch("ytdlp_loader.latest_versions", return_value={}), \
         patch("main.load_settings", return_value={**main.DEFAULT_SETTINGS, "output_path": str(tmp_path)}):
        async with client as c:
            for route in get_routes:
                r = await c.get(route.path, params=params)
                assert r.status_code not in (401, 403), (route.path, r.status_code)


@pytest.mark.parametrize("path,params", [
    ("/search-videos", {"q": "lofi"}),
    ("/url-preview", {"url": "https://www.youtube.com/watch?v=abc"}),
    ("/download/next-seq", {}),
])
async def test_previously_gated_routes_work_without_login(client, tmp_path, path, params):
    """完整版這三個路由先呼叫 require_credentials();Lite 不登入也要回 200。"""
    with patch("main._sync_search_videos_yt_dlp", side_effect=_fake_entries), \
         patch("main._sync_url_preview_yt_dlp", side_effect=_fake_entries), \
         patch("main._today_download_dir", return_value=tmp_path):
        async with client as c:
            r = await c.get(path, params=params)
    assert r.status_code == 200, r.text


# ── 打包守門(scripts/check_bundle.py)的對照組 ─────────────────────────────
def _load_check_bundle():
    spec = importlib.util.spec_from_file_location("check_bundle", REPO / "scripts" / "check_bundle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_bundle(root: pathlib.Path) -> pathlib.Path:
    bundle = root / "yt2mp3-lite"
    (bundle / "_internal" / "yt_dlp").mkdir(parents=True)
    (bundle / "yt2mp3-lite.exe").write_bytes(b"MZ")
    return bundle


def test_check_bundle_passes_clean_bundle(tmp_path):
    cb = _load_check_bundle()
    assert cb.check_bundle(_make_bundle(tmp_path)) == (0, [])


@pytest.mark.parametrize("inject", [
    "_internal/googleapiclient/discovery.py",
    "_internal/google/auth/__init__.py",
    "_internal/google_auth_oauthlib-1.3.1.dist-info/METADATA",
    "client_secret.json",
    "_internal/client_secret.json",
])
def test_check_bundle_rejects_google_artifacts(tmp_path, inject):
    cb = _load_check_bundle()
    bundle = _make_bundle(tmp_path)
    target = bundle / inject
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x")
    code, messages = cb.check_bundle(bundle)
    assert code == 1
    assert messages


def test_check_bundle_rejects_empty_dir(tmp_path):
    """掃一個空資料夾不能算通過(錨點不存在)。"""
    cb = _load_check_bundle()
    assert cb.check_bundle(tmp_path)[0] == 2
