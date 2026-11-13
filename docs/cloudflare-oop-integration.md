# 基於 OOP 分支繼續 Cloudflare 開發

本次直接從組員 `Sukiyin516/Planwise` 的 `oop-modularization`（`d6c19907d8cc2b27d7e893137d1e75f670bae9db`）建立自己的 `feature/nas-cloudflare-oop`，在此基礎上接入 Cloudflare 相容功能。舊 `feature/nas-cloudflare`（`4eeca0c`）只作已驗證代理實作的參考，**不 merge 舊分支的提交歷史，不合回 main，也不覆寫組員分支**。

## 組員這次更新了甚麼

| 改動 | 實際作用 |
| --- | --- |
| 新增 `time_slots.py` | 集中半小時時間解析；`events.py` 不再反向導入 `timetable.py`，解除循環依賴，保留原有錯誤提示。 |
| `prepare_plan_snapshot()` | 統一讀取、初始化及必要時保存行程；快照回應仍由路由組裝。 |
| `commit_plan_action()` | 組織請求去重、版本檢查、業務動作、導入備份及保存順序。 |
| 現有 `Database` 類增加方法 | 把行程、備份及請求紀錄 SQL 收回資料庫類；沿用呼叫方同一連線／交易，不自行提交。 |
| 寫入失敗回滾測試 | 模擬部分 SQL 已寫入後出錯，確認行程、備份和請求紀錄一起回滾。 |

這是模組與責任分工的整理；OOP 改善集中於現有 Database 封裝，其餘流程使用普通函式。用戶功能、JSON／資料庫格式及排程規則保持原樣。組員基線在本機重新驗證為 Python 105／Node 10 通過。

## 本輪怎樣接上 Cloudflare

- 保留組員的 `events.py`、`timetable.py`、`time_slots.py`、`nas/database.py` 和 Android 打包修改，不還原成舊版 SQL／流程。
- 接入獨立 `nas/proxy.py`，在 Flask 接收請求前處理可信 connector、HTTPS、Host 和訪客 IP；API 路由只保留少量代理設定接入與禁止快取標頭。
- 保留 Cloudflare 的 Secure cookie、CSRF／來源檢查、分 IP 限流及 Gunicorn fork 前初始化設定。
- 補上 `.dockerignore` 的 `!time_slots.py`：組員 Dockerfile 已加入 COPY，但原白名單仍排除此檔案；只跑 Python 測試看不出這個打包問題。
- 新 Compose、環境範本及容器測試改為指向 `feature/nas-cloudflare-oop`，避免實際建置時又抓回未包含 OOP 重構的舊 Cloudflare 分支。
- CI 加入新分支及根目錄 Python 檔案路徑，執行完整測試、Docker 建置／升級和可信／不可信 peer 測試。

## 後續協作流程

```text
組員 oop-modularization ──→ feature/nas-cloudflare-oop ──→ 繼續開發／測試
```

目前只在自己的新分支繼續開發及驗證。未來是否合回哪個團隊分支，待團隊另行決定；本輪不建立合併請求、不合回 main。若組員的 OOP 分支繼續更新，再先比較改動和衝突，不把整個 `application.py` 複製覆蓋來「同步」。

整合後應為 Python **118 項**（105 + 13）、Node **10 項**；[CI 結果](https://github.com/Z3ych1k/Planwise/actions?query=branch%3Afeature%2Fnas-cloudflare-oop) 為對應提交的驗證依據。詳細代理測試及未驗證邊界見 [驗證紀錄](../nas/CLOUDFLARE_TESTING.md)。

本輪只推送新分支。不替換 NAS 容器、不搬正式資料、不啟用公網 Tunnel、不重建 APK；實網與 Android 真機驗收仍待後續授權。
