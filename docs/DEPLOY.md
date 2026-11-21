# 發版指南（維護者）

## 版本來源

版本號只有一個來源：git tag（`vX.Y.Z`）。`scripts/build.bat` 讀 tag 寫進 `backend/_version.txt`，
打包後的 exe 從那裡讀。程式碼裡不寫死版號。

## 發版前（本機）

```bash
cd backend && .venv/Scripts/python.exe -m pytest        # 全綠
cd frontend && npm run test && npm run build             # 全綠、型別檢查通過
```

有 `tools/ffmpeg.exe`、`mp3gain.exe`、`deno.exe` 的話，可以先在本機跑一次 `scripts\build.bat`，
它會在最後用 `scripts/check_bundle.py` 檢查 bundle 裡沒有 Google 憑證或 Google API 套件。

## 發版

```bash
git tag v0.X.Y
git push origin v0.X.Y
```

GitHub Actions（`.github/workflows/release.yml`）會：

1. 下載 ffmpeg（BtbN latest）、deno（釘選版本）、mp3gain（winget）
2. 跑後端 pytest（含不依賴 Google 授權的守門）
3. `scripts\build.bat`：前端建置（含型別檢查）→ PyInstaller onedir → 附檔 → bundle 守門 → zip
4. 冒煙：`yt2mp3-lite.exe --health-check` 回報的版本要等於 tag
5. 建立 Release，附上 `yt2mp3-lite-vX.Y.Z-windows-x64.zip`

## 發版後

- 到 Releases 頁確認 zip 存在、大小合理（約 100 MB 上下）。
- 在一台乾淨的電腦（或另一個資料夾）解壓、雙擊 exe，貼一支影片網址實際下載一次。
- 已安裝的電腦跑 `update.bat`，確認會更新到新版。

## update.bat 的預設值

- `REPO=jmh273/YT2MP3-Lite`
- `INSTALL_DIR=C:\Tools\YT2MP3-Lite`（和完整版的 `C:\Tools\YT-MP3` 分開）

兩者都可以用環境變數覆寫。repo 為公開，`update.bat` 匿名下載即可，不需要 token。

## 退回舊版

到 Releases 頁下載舊版 zip，關掉 `yt2mp3-lite.exe` 後解壓覆蓋安裝資料夾即可。
設定在 `%USERPROFILE%\.yt2mp3-lite\`，不受影響。
