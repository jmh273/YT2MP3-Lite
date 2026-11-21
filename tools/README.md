# tools/

只有本機打包或開發時才需要。CI 會自己下載。

要讓 `scripts/build.bat` 或開發模式能下載、正規化，把下面三個檔放進來：

- **`ffmpeg.exe`**：Windows 靜態版，例如
  https://github.com/BtbN/FFmpeg-Builds/releases 的 `ffmpeg-master-latest-win64-gpl.zip`，只取 `bin/ffmpeg.exe`。
- **`mp3gain.exe`**：https://mp3gain.sourceforge.net/ 或 `winget install GlenSawyer.MP3Gain`
  （再從 `C:\Program Files (x86)\MP3Gain\mp3gain.exe` 複製過來）。
- **`deno.exe`**：yt-dlp 解 YouTube nsig challenge 用的 JS runtime。版本以
  `.github/workflows/release.yml` 的 `DENO_VERSION` 為準，從
  https://github.com/denoland/deno/releases 下載 `deno-x86_64-pc-windows-msvc.zip`。

整個 `tools/` 除了這份 README 都在 `.gitignore` 裡。
