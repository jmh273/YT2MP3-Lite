# YT → MP3 Lite

貼上 YouTube 網址或輸入關鍵字，把影片下載成 MP3（或 MP4）的 Windows 小工具。
**不需要 Google 帳號、不需要登入、不需要任何 API 金鑰**：下載解壓、雙擊就能用。

> ⚠️ **僅供個人使用，風險自負。** 從 YouTube 下載內容可能違反
> [YouTube 服務條款](https://www.youtube.com/t/terms)。請只下載你有權保存的內容，
> 勿用於侵犯著作權或商業散布。使用本工具的任何後果由使用者自行承擔，
> 作者不提供任何擔保（見 [LICENSE](LICENSE)）。

## 功能

- 貼網址：單支影片、播放清單、頻道網址都可以；大型清單分頁顯示，可跨頁勾選
- 關鍵字搜尋影片
- 下載 MP3（128 / 192 / 256 / 320 kbps）或 MP4（360p–1080p）
- 每日資料夾、檔名流水號、失敗自動重試、關掉再開可以接著下載
- 音量正規化（讓每首歌音量一致），可設定下載完自動接著做
- 點縮圖可先預覽播放
- 設定頁可以一鍵更新下載元件（yt-dlp），YouTube 改版導致下載失敗時通常按這個就好

## 安裝

1. 到 [Releases 頁](https://github.com/jmh273/YT2MP3-Lite/releases/latest)下載最新的
   `yt2mp3-lite-vX.Y.Z-windows-x64.zip`。
2. 解壓到一個資料夾，例如 `C:\Tools\YT2MP3-Lite\`。
3. 雙擊 `yt2mp3-lite.exe`。會先跳出一個黑色視窗（程式本體，用的時候不要關），
   接著瀏覽器自動開啟 <http://localhost:8010/>。

> 第一次執行時 Windows 可能跳出「Windows 已保護您的電腦」（SmartScreen）：
> 點「其他資訊」→「仍要執行」。這是因為本工具沒有付費的程式碼簽章，不是病毒。

不需要另外安裝 Python、Node.js 或 ffmpeg，zip 裡都附好了。

### 更新

執行安裝資料夾裡的 `update.bat`。有新版才會下載、覆蓋、重新啟動；
你的設定（`%USERPROFILE%\.yt2mp3-lite\`）和下載好的檔案不會被動到。

## 使用

1. 左邊選「🔗 貼網址」或「🔍 搜尋」，勾選想下載的影片。
2. 右邊「下載」分頁選格式與音質，按下載。
3. 檔案存在設定頁的「輸出資料夾」（預設 `音樂\YT-MP3\`），每天一個日期資料夾。

### 下載失敗怎麼辦

1. 到「設定」→「下載元件」→「查詢最新版」→「更新下載元件」，關掉程式再開。
2. 還是不行，跑 `update.bat` 更新整個程式。
3. 同一時間下載太多支容易被 YouTube 暫時限速；預設同時下載 2 支，可以在設定頁調低。

### 想自動備份到雲端

把設定頁的「輸出資料夾」設在雲端硬碟同步資料夾裡（例如 Google 雲端硬碟電腦版的「我的雲端硬碟」）就會自動同步。

## 和完整版的差別

這是 [YT → MP3 Tool](https://github.com/jmh273/yt-mp3-tool) 拿掉所有需要 Google 授權功能後的簡化版。

| | 完整版 | Lite |
| --- | --- | --- |
| 貼網址下載、關鍵字搜尋 | ✅ | ✅ |
| MP3 / MP4、流水號、每日資料夾、重試、續下 | ✅ | ✅ |
| 音量正規化、影片預覽、yt-dlp 更新 / 退回、PO Token | ✅ | ✅ |
| 登入 Google、訂閱清單、最新影片、熱門、同類新頻道、搜尋頻道 | ✅ | — |
| 觀察名單 | ✅ | 規劃中（本機清單，可匯入 Google Takeout 的訂閱匯出檔） |
| 上傳 Google 雲端硬碟 | ✅ | —（改用雲端硬碟同步資料夾） |
| 預設同時下載數 | 3 | 2 |

兩者可以裝在同一台電腦：Lite 用 `localhost:8010` 與 `~/.yt2mp3-lite/`，完整版用 `8000` 與 `~/.yt-mp3-tool/`，互不干擾。

> 🔧 **維護者注意**：兩個 repo 的下載核心（`backend/main.py` 的 yt-dlp 參數、player client、
> PO Token、`ytdlp_loader.py`、deno 版本）是各自一份。YouTube 改版需要修下載時，**兩邊都要改**。

## 授權

原始碼為 MIT（見 [LICENSE](LICENSE)）。隨附的 ffmpeg、mp3gain 為 GPL，deno 為 MIT，
詳見 [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt)。

---

## 從原始碼開發

需求：Python 3.12、Node.js 20+、[uv](https://docs.astral.sh/uv/)（或 pip）。
`tools/` 放 `ffmpeg.exe`、`mp3gain.exe`、`deno.exe`（見 [tools/README.md](tools/README.md)）。

```bash
# 後端
cd backend
uv venv -p 3.12 .venv
uv pip install -p .venv/Scripts/python.exe -r requirements.txt -r requirements-dev.txt
.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8010 --reload

# 前端（另一個終端機）
cd frontend
npm ci
npm run dev     # http://localhost:5173，/api 代理到 8010
```

或直接雙擊 `start.bat`。

### 測試

```bash
cd backend && .venv/Scripts/python.exe -m pytest     # 後端
cd frontend && npm run test                          # 前端（vitest）
cd frontend && npm run build                         # 型別檢查 + 建置
```

`backend/tests/test_no_google_auth.py` 與 `frontend/src/tests/noGoogleAuth.test.ts` 守住
「不依賴任何 Google 授權」：程式碼、相依套件、路由、發行包都會檢查。

### 發版

見 [docs/DEPLOY.md](docs/DEPLOY.md)。
