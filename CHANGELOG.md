# Changelog

## 0.1.1 — 2026-11-21

### 修正
- 設定頁改「MP3 輸出資料夾」後回到首頁，「下載到」仍顯示舊的根目錄（檔案其實已存到新位置），
  音量正規化的預設目錄也跟著指錯。現在根目錄一律跟著設定，保留自訂的資料夾名。
- `update.bat` 下載與解壓時關掉 PowerShell 進度列：131 MB 的 zip 從約 10 分鐘降到 18 秒。
  （從 0.1.0 更新到 0.1.1 這一次仍是舊的 `update.bat`，之後的更新才會變快。）

### 新增
- MP4 實際畫質低於選擇時，下載列顯示「⚠ 實際畫質 Np，低於選擇的畫質」。
  沒有 PO Token 時 YouTube 常只提供 360p，以前會悄悄降級。

## 0.1.0 — 2026-11-21

從 [YT → MP3 Tool](https://github.com/jmh273/yt-mp3-tool)（`e4de0b1`）拆出的免登入版本。

### 保留（照搬）
- 貼網址預覽與下載（單支、播放清單、頻道），分頁、跨頁勾選
- 關鍵字搜尋影片（yt-dlp `ytsearch50:`）
- MP3 / MP4 下載、格式音質、同時下載、重試退避、失敗紀錄、續下
- 每日資料夾、序號前綴、目標資料夾、已下載標記與「允許再次下載」
- 音量正規化（mp3gain）、下載完自動接正規化
- 影片預覽播放、yt-dlp 版本顯示 / 更新 / 退回、deno JS runtime、PO Token、player client 優先序

### 移除（需要 Google 授權）
- 登入、多帳號、訂閱清單與對帳、健康檢查、頻道影片、最新影片、觀察名單、熱門影片、
  同類新頻道、搜尋頻道、Google Drive 上傳、API 配額
- 相依套件 `google-auth`、`google-auth-oauthlib`、`google-api-python-client`、`aiohttp`
- 設定欄位 `videos_per_channel`、`latest_hours`、`discovery_keyword_top_n`、
  `min_duration_minutes`、`max_duration_minutes`、`drive_root_folder`、
  `drive_upload_concurrency`、`quota_used`、`quota_date`

### 變更
- 預設同時下載數 3 → 2
- 連接埠 8000 → 8010（環境變數 `YT2MP3_LITE_PORT`、`YT2MP3_LITE_HOST`、`YT2MP3_LITE_NO_BROWSER`）
- 設定與受管 yt-dlp 目錄 `~/.yt-mp3-tool/` → `~/.yt2mp3-lite/`
- 執行檔 `yt2mp3-lite.exe`，分頁標題「YT → MP3 Lite」
- 畫面：左欄訂閱 / 觀察名單拿掉；來源只剩「貼網址」「搜尋」，工作區只剩「下載」「音量正規化」
- `/url-preview`、`/search-videos`、`/download/next-seq` 不再要求登入

### 新增守門
- 後端 `tests/test_no_google_auth.py`：程式碼與 requirements 不含 Google 套件、
  沒有授權路由、任何 GET 路由不回 401
- 前端 `src/tests/noGoogleAuth.test.ts`：不呼叫授權路由、不引用已移除的 store
- `scripts/check_bundle.py`：發行包裡出現 `client_secret.json` 或 Google API 套件就讓 build 失敗
