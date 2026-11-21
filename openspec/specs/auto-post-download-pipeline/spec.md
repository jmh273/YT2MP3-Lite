# auto-post-download-pipeline Specification

## Purpose
定義下載面板的選用「下載後自動正規化」流程：一個預設關閉、狀態持久化的勾選框，勾選後於 mp3 下載完成時自動對該批實際下載到的資料夾執行音量正規化。由前端協調（重用既有 `/normalize/start` 端點與進度面板），並以 `POST /download` 回傳的 resolved directory 作為依據。

> Lite 版：完整版在正規化之後還會自動上傳 Google Drive；Lite 不需要 Google 授權，沒有上傳階段。

## Requirements

### Requirement: 下載後自動正規化的選用開關
下載面板 SHALL 提供「下載完成後自動正規化」勾選框，預設 MUST 為**不勾選**。其狀態 SHALL 持久化（localStorage），跨會話保留。未勾選時，下載完不自動做任何後續動作。

#### Scenario: 預設不勾選
- **WHEN** 使用者第一次開啟下載面板
- **THEN** 該勾選框為未勾選狀態，下載完成後不自動正規化

#### Scenario: 狀態跨會話保留
- **WHEN** 使用者勾選後重新整理頁面
- **THEN** 勾選框維持勾選

### Requirement: 依格式決定是否正規化
勾選時，下載完成後系統 SHALL 依該批格式決定後續動作。

#### Scenario: mp3 自動正規化
- **WHEN** 勾選開關且下載格式為 mp3，該批下載完成
- **THEN** 系統 SHALL 切到「音量正規化」分頁、載入該批下載資料夾並自動開始正規化

#### Scenario: mp4 不做任何後續動作
- **WHEN** 勾選開關且下載格式為 mp4，該批下載完成
- **THEN** 系統 SHALL NOT 自動正規化（mp3gain 僅支援 mp3），也 SHALL NOT 切換分頁

#### Scenario: 未勾選或沒有目錄
- **WHEN** 開關未勾選，或下載回應沒有 directory
- **THEN** 系統 SHALL NOT 自動正規化

### Requirement: 無檔可正規化時不卡住
當 mp3 批次載入後沒有可正規化的檔，系統 SHALL 直接結束串接（回到 idle），MUST NOT 呼叫正規化批次、也 MUST NOT 停滯於正規化階段。正規化批次啟動失敗時同樣回到 idle。

#### Scenario: 無檔可正規化
- **WHEN** mp3 批次下載完成但資料夾內沒有可正規化的檔
- **THEN** 系統 SHALL NOT 呼叫正規化批次，串接狀態回到 idle

### Requirement: 下載回應提供 resolved 目錄
`POST /download` 回應 SHALL 除 `task_id` 外，提供該批 resolved 的下載目錄路徑（`directory`），作為前端串接正規化的依據。

#### Scenario: 回應含 directory
- **WHEN** 前端送出 `POST /download`
- **THEN** 回應 body 同時包含 `task_id` 與該批實際寫入的 `directory`（含日期子目錄 / target_dir 解析結果）
