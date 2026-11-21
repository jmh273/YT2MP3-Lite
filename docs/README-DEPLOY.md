# YT → MP3 Lite 使用小抄

## 啟動
雙擊 `yt2mp3-lite.exe`。黑色視窗是程式本體，使用時不要關；瀏覽器會自動開到 http://localhost:8010/

第一次執行若出現「Windows 已保護您的電腦」：點「其他資訊」→「仍要執行」。

## 更新
執行這個資料夾裡的 `update.bat`。不需要 GitHub 帳號。

## 下載失敗
1. 設定 →「下載元件」→「查詢最新版」→「更新下載元件」，然後關掉程式再開。
2. 還是不行就跑 `update.bat`。

## 你的資料在哪裡
- 設定：`%USERPROFILE%\.yt2mp3-lite\settings.json`
- 下載紀錄（除錯用）：`%USERPROFILE%\.yt2mp3-lite\logs\download.log`
- 下載的檔案：設定頁的「輸出資料夾」（預設 `%USERPROFILE%\Music\YT-MP3\`）

更新時以上資料**不會被動到**。

## 授權條款
本工具原始碼為 MIT；隨附的 ffmpeg / mp3gain 為 GPL，詳見 `THIRD-PARTY-NOTICES.txt`。
僅供個人使用，下載 YouTube 內容可能違反其服務條款，風險自負。
