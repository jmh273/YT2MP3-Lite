# no-google-auth Specification

## Purpose
YT2MP3-Lite 是從 YT → MP3 Tool 拆出、給不想設定 Google Cloud 的朋友用的版本。整個產品 MUST 在沒有任何 Google 帳號、OAuth 憑證或 API 金鑰的情況下完整可用。本 spec 定義這個承諾，以及守住它的檢查。

## Requirements

### Requirement: 不依賴 Google API 套件
後端程式碼 MUST NOT import 任何 Google API 或 OAuth 套件（`google.*`、`googleapiclient`、`google_auth_oauthlib`、`oauthlib`），`requirements.txt` MUST NOT 列出這些套件，也 MUST NOT 存在 `require_credentials` / `load_credentials` 這類憑證關卡。

#### Scenario: 程式碼與相依套件
- **WHEN** 掃描 `backend/main.py`、`__main__.py`、`ytdlp_loader.py`（去掉註解後）與 `requirements.txt`
- **THEN** 不出現上述任何套件或憑證關卡
- **AND** 測試環境照 requirements 安裝後，這些套件 MUST 無法 import

### Requirement: 沒有需要授權的路由
後端 MUST NOT 註冊需要 Google 授權的路由（`/auth`、`/subscriptions`、`/channels`、`/drive`、`/quota`、`/latest-videos`、`/trending-videos`、`/discovery`、`/search-channels`）。任何 GET 路由 MUST NOT 回 401 或 403。

#### Scenario: 原本被擋的路由不登入就能用
- **WHEN** 未登入（本來就沒有登入）呼叫 `/url-preview`、`/search-videos`、`/download/next-seq`
- **THEN** 回 200

#### Scenario: 授權路由不存在
- **WHEN** 呼叫 `/auth/status`
- **THEN** 回 404

### Requirement: 前端不呼叫授權路由
前端原始碼（測試以外）MUST NOT 呼叫上述授權路由，MUST NOT 引用登入、配額、觀察名單、Drive 上傳相關的 store 或元件，也 MUST NOT 有導向登入頁的路由守衛。

#### Scenario: 首頁直接可用
- **WHEN** 使用者開啟首頁
- **THEN** 直接看到「貼網址」「搜尋」來源分頁與「下載」「音量正規化」工作分頁，不經過登入頁
- **AND** 掛載時不呼叫任何授權路由

### Requirement: 發行包不含 Google 憑證或套件
`scripts/build.bat` SHALL 在壓縮前以 `scripts/check_bundle.py` 檢查 PyInstaller 輸出；bundle 內出現 `client_secret.json`、`token.json`，或 `_internal/` 下出現 Google API 套件時 MUST 讓 build 失敗。檢查對象不是有效 bundle（缺 `yt2mp3-lite.exe` 或 `_internal/`）時 MUST 失敗，不得當成通過。

#### Scenario: 乾淨的 bundle
- **WHEN** bundle 只有程式本體與 yt-dlp 等允許的套件
- **THEN** 檢查回 0，build 繼續壓縮

#### Scenario: 混入憑證或 Google 套件
- **WHEN** bundle 內有 `client_secret.json` 或 `_internal/googleapiclient/`
- **THEN** 檢查回 1 並列出違規項目，build 失敗

#### Scenario: 掃到空資料夾
- **WHEN** 檢查對象不是有效 bundle
- **THEN** 檢查回 2，build 失敗
