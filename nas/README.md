# Planwise NAS 0.3.0 Preview

**[完整 fnOS 安裝與管理員密碼教程](INSTALL.md)** · **[保留資料更新](UPGRADE.md)** · **[單檔 Compose](../compose.yaml)**

`feature/nas-cloudflare` 額外提供 [獨立 HTTPS／Tunnel 試作](CLOUDFLARE.md)，需批准域名和公網權限後才部署。原 LAN Compose 及 NAS 0.3.0 APK 保留。[此分支多帳號整合測試](CLOUDFLARE_TESTING.md)。

Python／Flask JSON API + 獨立 HTML/CSS/JavaScript，fnOS x86-64 Docker 部署。局域網 HTTP，外出經 ZeroTier；預設 NAS 埠 9473。

- 每帳號獨立一張表，同帳號跨網頁及 NAS APK 共用。沒有共享表。
- **0.3.0**：登入頁以管理員邀請碼建立一般帳號；每碼限用一次、7 天有效、可撤銷。管理員沿用終端建立／重設密碼的方法；一般帳號第三頁不顯示邀請碼管理。
- 版本檢查阻止舊畫面覆蓋；15 秒輪詢／回到頁面檢查，編輯中的輸入保留。
- **0.2.0**：手機預設七日，七欄適應螢幕；點日期看單日，點任務看完整詳情，不以橫向捲動代替總覽。
- **0.2.0**：NAS APK 立即載入內置介面與唯讀快取，API 逾時 8 秒；不等待遠端網頁失敗，可在頁面重新整理重連。
- 原有半小時排程、重複事項、固定事項鎖定與單次取消、私人時間、拖動、可選前移、目標填色、三語及 JSON 匯入匯出保留。

## 離線、帳號與儲存

離線只查看，不修改、不排隊提交。最近快照存於當前網站 localStorage，不含密碼、session cookie、CSRF token 或邀請碼管理資料；重連取得最新資料才允許修改。線上登出／登入失效會清除快取，已匯出的 HTML 須自行保管。

LAN HTTP 瀏覽器關閉後重新離線開啟，請用下載的唯讀 HTML 或 NAS APK。HTTPS／localhost 可用 Service Worker 快取介面，帳號 API 不經此快取。本 Compose 沒有 HTTPS 反向代理。

SQLite 僅由 NAS 本地服務存取，不透過 SMB 給裝置開檔。`/data/planwise.sqlite3` 儲存帳號、session、每帳號 JSON 狀態。交易內檢查版本與儲存；匯入保留最近 10 份原資料，完整備份用 `nas.manage backup-db`。

scrypt 雜湊、HttpOnly／SameSite=Strict cookie、CSRF、同來源檢查與登入／註冊限流；session 7 天。邀請碼隨機產生，資料庫只存 SHA-256，原碼只在產生時回傳，不寫入快取。註冊與消耗邀請碼在同一交易執行，即使傳入管理員欄位也只會建立一般帳號。LAN HTTP cookie 不加 Secure，只用於可信 LAN／ZeroTier；NAS 主機管理者可讀資料庫，並非端對端加密。

## Android 與模組

NAS APK 在 `nas/android/`，`hk.planwise.nas`，`0.3.0-nas-preview`／versionCode 3，Android 8+／現代 WebView。設定 JDK 17／21 的 `JAVA_HOME`、SDK 36 的 `ANDROID_HOME`，執行 `bash nas/android/build-apk.sh`。預覽版需保留相同 debug 簽章升級，私鑰不提交 GitHub。

本次需更新 Docker 和 NAS APK。NAS APK 內置 HTML／JS 以支援立即離線顯示，**介面不會隨 Docker 自動更新**；0.2.0 APK 仍可用原帳號登入，但沒有新註冊入口／邀請碼介面。瀏覽器則在 Docker 更新後重新整理即可。本地 Android 不使用 NAS 帳號，沿用 0.5.2。

本地 APK 在 `android/`，`hk.planwise.app`；內置 Python／WebView 在 `android/runtime/`，不再提供桌面本地網頁啟動入口。共用規則在根目錄；NAS API `application.py`、儲存 `database.py`、介接 `domain.py`、帳號 CLI `manage.py`、前端 `static/`。

## 驗證

```sh
python -m unittest discover -v
node --test nas/test_client.cjs
node --check nas/static/ui.js
node --check android/runtime/app.js
```

[驗證紀錄](TESTING.md)。每帳號 500 任務／500 事項／5000 投入；請求 8 MB、狀態 4 MB。未實作離線寫入、自動合併衝突、無邀請註冊、郵件找回或大型公開服務。
