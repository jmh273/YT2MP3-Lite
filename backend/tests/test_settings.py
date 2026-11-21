"""Settings 端點與工具函式測試"""
import json
import pathlib

import pytest
import main


# ── load_settings ─────────────────────────────────────────────────────────────
def test_load_settings_defaults():
    """無設定檔時回傳預設值"""
    assert not main.SETTINGS_FILE.exists()
    s = main.load_settings()
    assert s["download_retries"] == 3
    assert "YT-MP3" in s["output_path"]
    assert s["download_concurrency"] == 2


def test_load_settings_merges_file(tmp_path):
    """設定檔存在時合併覆蓋預設值"""
    main.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    main.SETTINGS_FILE.write_text(json.dumps({"download_retries": 5}))
    s = main.load_settings()
    assert s["download_retries"] == 5
    assert "YT-MP3" in s["output_path"]  # 預設值保留


# ── GET /settings ─────────────────────────────────────────────────────────────
async def test_get_settings_defaults(client):
    """GET /settings 回傳預設設定"""
    async with client as c:
        r = await c.get("/settings")
    assert r.status_code == 200
    data = r.json()
    assert "output_path" in data
    assert data["download_concurrency"] == 2


# ── PUT /settings ─────────────────────────────────────────────────────────────
async def test_put_settings_download_concurrency(client):
    """PUT /settings 更新 download_concurrency"""
    async with client as c:
        r = await c.put("/settings", json={"download_concurrency": 4})
    assert r.status_code == 200
    assert r.json()["download_concurrency"] == 4


async def test_put_settings_output_path_creates_dir(client, tmp_path):
    """PUT /settings 指定新路徑時自動建立資料夾"""
    new_path = str(tmp_path / "new_music" / "yt")
    async with client as c:
        r = await c.put("/settings", json={"output_path": new_path})
    assert r.status_code == 200
    assert pathlib.Path(new_path).exists()
    assert r.json()["output_path"] == new_path


async def test_put_settings_partial_update(client):
    """PUT /settings 只傳一個欄位，另一個欄位維持不變"""
    # 先設定初始值
    async with client as c:
        await c.put("/settings", json={"download_concurrency": 5})
        r = await c.put("/settings", json={"download_concurrency": None})
    # download_concurrency 沒傳，應維持先前的值
    assert r.json()["download_concurrency"] == 5


async def test_put_settings_persisted(client):
    """PUT /settings 儲存後，GET /settings 應看到新值"""
    async with client as c:
        await c.put("/settings", json={"download_concurrency": 1})
        r = await c.get("/settings")
    assert r.json()["download_concurrency"] == 1



async def test_put_settings_download_concurrency_valid(client):
    async with client as c:
        r = await c.put("/settings", json={"download_concurrency": 4})
        r2 = await c.get("/settings")
    assert r.status_code == 200
    assert r.json()["download_concurrency"] == 4
    assert r2.json()["download_concurrency"] == 4


async def test_put_settings_download_concurrency_too_low(client):
    async with client as c:
        r = await c.put("/settings", json={"download_concurrency": 0})
    assert r.status_code == 422


async def test_put_settings_download_concurrency_too_high(client):
    async with client as c:
        r = await c.put("/settings", json={"download_concurrency": 99})
    assert r.status_code == 422











# ── normalize_target_db ───────────────────────────────────────────────────────
async def test_get_settings_normalize_target_db_default(client):
    """GET /settings 預設 normalize_target_db=89.0 (mp3gain ReplayGain reference)"""
    async with client as c:
        r = await c.get("/settings")
    assert r.json()["normalize_target_db"] == 89.0


async def test_put_settings_normalize_target_db_valid(client):
    """PUT /settings normalize_target_db=92.0 應更新並持久化"""
    async with client as c:
        r1 = await c.put("/settings", json={"normalize_target_db": 92.0})
        r2 = await c.get("/settings")
    assert r1.status_code == 200
    assert r1.json()["normalize_target_db"] == 92.0
    assert r2.json()["normalize_target_db"] == 92.0


async def test_put_settings_normalize_target_db_min_boundary(client):
    """PUT /settings normalize_target_db=80.0 為下限，應接受"""
    async with client as c:
        r = await c.put("/settings", json={"normalize_target_db": 80.0})
    assert r.status_code == 200
    assert r.json()["normalize_target_db"] == 80.0


async def test_put_settings_normalize_target_db_max_boundary(client):
    """PUT /settings normalize_target_db=100.0 為上限，應接受"""
    async with client as c:
        r = await c.put("/settings", json={"normalize_target_db": 100.0})
    assert r.status_code == 200
    assert r.json()["normalize_target_db"] == 100.0


async def test_put_settings_normalize_target_db_too_high(client):
    """PUT /settings normalize_target_db=105.0 超出上限，應回傳 422"""
    async with client as c:
        r = await c.put("/settings", json={"normalize_target_db": 105.0})
    assert r.status_code == 422


async def test_put_settings_normalize_target_db_too_low(client):
    """PUT /settings normalize_target_db=75.0 超出下限，應回傳 422"""
    async with client as c:
        r = await c.put("/settings", json={"normalize_target_db": 75.0})
    assert r.status_code == 422


# ── Tolerant load_settings ───────────────────────────────────────────────────
def test_load_settings_resets_legacy_lufs_value():
    """舊版 LUFS = -14（在新版 dB SPL 80–100 範圍外）→ 載入時 reset 成預設 89.0"""
    main.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    main.SETTINGS_FILE.write_text(json.dumps({"normalize_target_db": -14.0}))
    s = main.load_settings()
    assert s["normalize_target_db"] == 89.0


def test_load_settings_resets_wrong_type():
    """download_retries 是字串 → reset 成預設"""
    main.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    main.SETTINGS_FILE.write_text(json.dumps({"download_retries": "three"}))
    s = main.load_settings()
    assert s["download_retries"] == 3


def test_load_settings_preserves_unknown_legacy_key():
    """未知 key（早期版本留下的）應保留在 dict 中、不報錯"""
    main.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    main.SETTINGS_FILE.write_text(json.dumps({"removed_old_setting": "something"}))
    s = main.load_settings()
    assert s["removed_old_setting"] == "something"


def test_load_settings_passes_through_in_range_value():
    """合法值原樣回傳，不亂改"""
    main.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    main.SETTINGS_FILE.write_text(json.dumps({"normalize_target_db": 92.0}))
    s = main.load_settings()
    assert s["normalize_target_db"] == 92.0


def test_load_settings_does_not_reset_out_of_range_concurrency():
    """download_concurrency 不在 _SETTINGS_RANGES：load_settings 須原樣保留越界值，
    交由 _resolve_concurrency 夾限（0→1、99→8），而非 reset 成預設 2。"""
    main.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    main.SETTINGS_FILE.write_text(json.dumps({"download_concurrency": 99}))
    s = main.load_settings()
    assert s["download_concurrency"] == 99
    assert main._resolve_concurrency(s) == 8




def test_load_settings_handles_corrupt_json():
    """設定檔內容不是合法 JSON → 全部 reset 成預設、不報錯"""
    main.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    main.SETTINGS_FILE.write_text("{ broken json")
    s = main.load_settings()
    assert s["normalize_target_db"] == 89.0
    assert s["download_retries"] == 3


# ── 拿掉的設定欄位(需要 Google 授權的功能才用得到) ──────────────────────────
REMOVED_KEYS = (
    "videos_per_channel", "latest_hours", "discovery_keyword_top_n",
    "min_duration_minutes", "max_duration_minutes",
    "drive_root_folder", "drive_upload_concurrency", "quota_used", "quota_date",
)


async def test_get_settings_has_no_removed_keys(client):
    async with client as c:
        r = await c.get("/settings")
    for key in REMOVED_KEYS:
        assert key not in r.json(), key


async def test_put_settings_ignores_removed_keys(client):
    """舊前端或手動呼叫送來已移除的欄位,不會被寫進設定檔。"""
    async with client as c:
        r = await c.put("/settings", json={"drive_root_folder": "x", "latest_hours": 48})
    assert r.status_code == 200
    assert "drive_root_folder" not in r.json()
    assert "latest_hours" not in r.json()


# ── /version endpoint ────────────────────────────────────────────────────────
async def test_version_endpoint(client):
    """GET /version 回傳 {version: __version__}"""
    async with client as c:
        r = await c.get("/version")
    assert r.status_code == 200
    body = r.json()
    assert "version" in body
    # 在 dev 環境（沒有 _version.txt）應該是 0.0.0-dev；CI build 會是真實版號
    assert body["version"] == main.__version__
