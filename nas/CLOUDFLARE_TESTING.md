# Cloudflare 分支驗證紀錄

日期：2026-11-13。所有測試使用臨時帳號、資料庫、憑證和專用網路；沒有連使用者 NAS、Cloudflare 帳號或公網 Tunnel。

## 本機已完成

`python -m unittest discover -v`：**116 項通過**，包含原有 104 項，加上 6 項代理邊界及 6 項真實運行服務的整合測試。`node --test nas/test_client.cjs`：原有 **10 項通過**。

整合測試路徑為 HTTPS client（驗證臨時 CA）→ 僅迴環地址的 TLS relay → 真實 Gunicorn → 臨時 SQLite；不是 Flask test client。relay 模擬 Cloudflare 覆寫協定／IP 的合約，沒有代替 Cloudflare 實網測試。

| 情境 | 已觀察結果 |
| --- | --- |
| 管理員及兩個邀請註冊的一般帳號，各用獨立 Cookie jar | 各自登入；註冊傳入 `is_admin` 仍為一般帳號 |
| A／B 同時建立各自行程 | 兩者成功；A、B 及管理員的任務各自獨立 |
| B 傳入 A 的 task ID／user_id，或指定 A 的匯出參數 | 修改拒絕；匯出／讀取仍只得到 B 的表 |
| 一般帳號呼叫邀請碼 GET／POST | 403 |
| 同帳號另一個 session 讀取；舊版本提交 | 讀到同一任務；舊提交 409，不覆蓋 |
| 登出其中一個 session | 該 session 401，另一個仍登入 |
| 改密碼 | 該帳號所有 session 失效；其他帳號仍可用；新密碼可登入 |
| HTTPS cookie 與 HTTP | Secure／HttpOnly；Cookie jar 不把 Secure cookie 發到 HTTP |
| state、匯出、離線快照與未登入錯誤 | private/no-store；Cloudflare CDN cache 指令 no-store |
| 假 Origin、損壞 Origin、缺 CSRF | 403；損壞 Origin 已由原本 500 修成明確拒絕 |
| 錯 Host／HTTP 協定／非法或串接 CF IP | 400／403 |
| 訪客偽造 X-Forwarded-*、CF IP | 模擬 edge 先覆寫可信欄位；假鏈不改身分 |
| 不同訪客經同一 connector | 註冊限流按訪客 IP 分開，改 XFF 不能繞過 |

代理單元測試另驗證：不可信 peer 即使帶完整偽造 Cloudflare 標頭仍被拒；未啟用時不信任標頭；半套設定拒絕啟動且不建立 DB；健康檢查例外僅限本機 GET。

## Docker CI

分支 [Actions](https://github.com/Z3ych1k/Planwise/actions?query=branch%3Afeature%2Fnas-cloudflare) 執行：

- 以上 Python／Node、原內網兩份 Compose、獨立 Cloudflare Compose 檢查。
- Linux amd64 生產 Gunicorn 映像建置、原持久資料卷／重啟與 0.2.0 同卷升級回歸。
- `nas/check_proxy_container.py`：確認 Compose 來源為新分支、沒有主機埠、獨立卷、確切 connector IP、秘密只掛到 cloudflared；實際從 `.3`／`.4` 兩個容器 IP 測試信任／拒絕。
- 官方固定版本 cloudflared 在 `--network none` 下執行 version，不建立 Tunnel。

是否通過以對應提交的 Actions 結果為準。本機沒有 Docker engine，因此不把本機 TLS 測試稱為 fnOS／Cloudflare 完整驗收。

## 保持不變與未測項目

沒有改資料庫格式、排程演算法、前端流程或 Android 原始碼；沒有重建 APK。`main`、`feature/nas-server` 和組員 fork 分支不推送。

尚未驗證：使用者 fnOS 的實際 Docker 網段／權限、真實域名與 Cloudflare edge、Tunnel Token、外網手機連線、Android 真機 HTTPS 登入。沒有啟用 Cloudflare Access、Quick Tunnel、Vercel、域名購買或正式資料遷移。
