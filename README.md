# 留白 Planwise

安排大學生的 DDL，保留課程、私人時間與長期目標。以半小時為單位，不使用 AI。

## 第一次使用｜Windows／macOS

下載本分支的完整 ZIP（GitHub **Code → Download ZIP**），先全部解壓，再打開含 `main.py` 和 `nas/` 的資料夾。需要 Python 3.11 或以上。本機試用只需要 Python 和瀏覽器。

**Windows（PowerShell）**：在解壓後的資料夾內開啟 PowerShell，輸入：

```powershell
py -3 --version
py -3 -m pip install -r nas/requirements.txt
py -3 main.py
```

如果找不到 `py`，但 `python --version` 有顯示 Python 3.11 或更新版本，就把每行的 `py -3` 改成 `python`。如果兩個命令都找不到，先安裝 Python，再重新開啟 PowerShell。

**macOS（終端機）**：進入解壓後含 `main.py` 的資料夾，執行：

```sh
python3 --version
python3 -m pip install -r nas/requirements.txt
python3 main.py
```

1. 保持終端機開著，在 Edge、Chrome 或其他瀏覽器開啟 <http://127.0.0.1:8765/>。第一次會顯示「建立本機帳號」。帳號須為 3–40 個英文字母、數字、點、底線或連字號，密碼須為 12–200 字元。確認密碼後，程式會登入並打開你的行程。
2. 按「新增任務」，填一個有期限的作業和預計工時，再切到「時間行程」查看安排。可在「事項與設定」加入固定課程或私人時間。
3. 用 Ctrl+C 停止。之後在**同一份解壓資料夾**執行 `main.py`，以原有帳號登入。帳號與資料存於 `data/planwise-demo.sqlite3`，請勿刪除或把它放進要分享的 ZIP。

如果瀏覽器打不開，確認終端機仍在執行，並使用正確的網址。若 8765 已被使用，可執行 `py -3 main.py --port 8766`（macOS 用 `python3`），再開啟 <http://127.0.0.1:8766/>。如果之前用終端機建過帳號，登入頁會直接讓你用該帳號登入。

**使用組員部署好的 NAS 網址時**，先向管理員索取邀請碼，再從登入頁選「以邀請碼建立帳號」。本機帳號只保存在這份解壓資料夾。用同一個 NAS 網址及帳號登入，才會在不同裝置看到同一份行程。

整合及測試說明見 [提交版審查紀錄](docs/submission-review.md)。

| 使用方式 | 資料與連線 | 安裝 |
| --- | --- | --- |
| NAS 網頁＋NAS APK 0.3.0 Preview | NAS 上每帳號一張表，同帳號跨裝置同步；離線唯讀 | [詳細教程與管理員密碼設定](nas/INSTALL.md) |
| 本地 Android 0.5.2 Preview | 手機內獨立 JSON，不需要 NAS 或網絡 | [本地 Android 說明](android/README.md) |

本地 Android 的內置介面在 `android/runtime/`。課程入口、NAS 網頁和 NAS APK 共用 Flask 服務及網頁介面。

## NAS 入口

- 此分支另提供 **[Cloudflare HTTPS 試作與批准步驟](nas/CLOUDFLARE.md)**、[獨立 Compose](compose.cloudflare.yaml) 和 [多帳號實測紀錄](nas/CLOUDFLARE_TESTING.md)。尚未啟用公網入口，原內網部署檔保留原樣。
- **[直接查看／複製 Compose](compose.yaml)**：只取這一個檔案即可在 fnOS 建置；預設網址 `http://NAS的IP:9473/`。
- **[安裝教程](nas/INSTALL.md)**：fnOS 圖形介面、終端部署、管理員帳號與密碼、重設密碼、升級與備份。
- **[版本下載](https://github.com/Z3ych1k/Planwise/releases/tag/nas-v0.3.0-preview)**：部署包、NAS APK、Compose 及教程；本地 Android 仍用 0.5.2。
- **[已有 NAS 的保留資料更新步驟](nas/UPGRADE.md)**：先備份，再更新原 Compose 專案；網頁重新整理，NAS APK 覆蓋升級。
- [NAS 說明與驗證](nas/README.md)。

已啟動容器但未設帳號：在**容器互動終端**執行：

```sh
python -m nas.manage create-user admin --admin
```

按提示輸入兩次**自己設定、至少 12 字元**的密碼。不顯示字元或星號是正常的。沒有預設密碼，也不是 fnOS 密碼。已存在帳號請看教程中的 `reset-password`。

管理員在第三頁「邀請碼管理」產生邀請碼；新使用者在登入頁按「以邀請碼建立帳號」，自行設定帳號和密碼。每碼限用一次、7 天有效，可由管理員撤銷。一般帳號只有自己的行程、偏好、備份及密碼設定，沒有邀請碼管理權限。

## 介面與開發

期限優先，同期限再看重要性；課程、固定事項及私人時間先扣除。長期目標只提醒，圓點隨投入填滿。提前完成後先保留原安排，前移僅作建議。

重複事項、香港 2026–2027 假日、固定事項單次取消、任務拖動、繁／簡／英文及 JSON 匯入匯出均保留。手機預設一次看全七天；點日期看單日，點任務看氣泡詳情。

```sh
python -m pip install -r nas/requirements.txt
python -m unittest discover -v
node --check nas/static/ui.js
node --test nas/test_client.cjs
node --check android/runtime/app.js
```

根目錄 Python 模組為共用規則；NAS API 與前端在 `nas/`，本地 Android 在 `android/`，NAS Android 在 `nas/android/`。歷史規格及審查紀錄作課程開發記錄保留，當前安裝方法以本頁和安裝教程為準。

## Code Structure & Refactoring

| 文件 | 主要職責 |
| --- | --- |
| `timetable.py` | 計算時間表與可用時段。 |
| `events.py` | 處理日程與固定事項的規則，例如移動單次事項。 |
| `time_slots.py` | 提供兩個時間模組共用的時間解析功能。 |
| `nas/application.py` | 接收 NAS 網頁 API 請求，組織計劃快照與保存流程。 |
| `nas/domain.py` | 執行 NAS 計劃操作並產生供頁面使用的資料，沿用共用業務規則。 |
| `nas/database.py` | 以 `Database` 類管理資料庫連線、交易及計劃資料讀寫。 |

第一階段把共用時間解析移至 `time_slots.py`，解除 `timetable.py` 與 `events.py` 的循環依賴。第三階段把 NAS 計劃快照和提交步驟整理為普通函數，並將相關 SQL 集中到已有的 `Database` 類；這些調整不改變原有功能。第二階段比較 NAS 與本地 Android 的操作後，決定暫不提取新的共用動作模組。

詳細記錄：[第一階段：時間模組](docs/refactoring-01-time-dependency.md) · [第二階段：共用動作審查](docs/refactoring-02-review.md) · [第三階段：NAS 計劃流程](docs/refactoring-03-nas-application.md)。
