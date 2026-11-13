# Cloudflare Tunnel 試作：先測試，再批准公開

此文件適用 `feature/nas-cloudflare-oop`。直接以組員 `Sukiyin516/Planwise` 的 `oop-modularization`（`d6c1990`）為基線開發代理相容功能，保留共用時間模組、NAS 流程拆分及 Database 封裝；沒有 merge 舊 Cloudflare 分支的提交歷史，也不合回 main。這個分支不會自行更新已運作的 NAS。[開發說明](../docs/cloudflare-oop-integration.md)。

目前已準備程式、獨立 Compose 及隔離測試。**尚未建立 Cloudflare 帳號、購買域名、設定 DNS、啟動 Tunnel 或更換 NAS 容器。** 沒有域名／Tunnel Token 時，不能宣稱已有可長期使用的 HTTPS 網址。Quick Tunnel 只適合臨時驗證，本次也沒有啟動。

## 連線及資料

```text
瀏覽器 / NAS APK
    → HTTPS → Cloudflare → 加密 Tunnel → NAS 的 cloudflared
    → 專用 Docker 內部網路的 HTTP → Planwise / SQLite
```

前端、API、帳號及行程資料庫都在 NAS；沒有 Vercel、共享表或離線寫入。Cloudflare 終止 HTTPS 並代理請求，這不屬於端對端加密；啟用前需同意由 Cloudflare 處理這些流量。

每帳號仍各自一張表，同帳號跨裝置共用。邀請碼註冊、版本衝突檢查、自己的密碼設定和備份功能不變。管理員仍在容器互動終端用 `python -m nas.manage create-user admin --admin` 建立，沒有預設密碼。

## 與現有內網部署分開

| 配置 | 專案／資料卷 | 入口 |
| --- | --- | --- |
| 原 `compose.yaml`／`nas/compose.yaml` | 保持原樣 | 原內網埠，模板為 9473；自訂埠也保留 |
| 新 `compose.cloudflare.yaml` | `planwise-cloudflare-preview`／`cloudflare-data` | 不發佈 NAS 主機埠；只接受指定 Tunnel connector |

**不要用 `-f compose.yaml -f compose.cloudflare.yaml` 合併。** 使用新檔案、獨立專案及資料卷測試，不把生產 `/data` 掛到試作容器。兩個資料卷不會自動同步；新試作帳號也不是原有帳號的鏡像。

未來若批准正式切換，需先停止各裝置編輯、用原版 `backup-db` 做一致備份、另存容器外，再將備份還原到另一個卷並核對全部帳號／行程。切換時只保留一個可寫的正式服務，避免舊 HTTP 與新 HTTPS 各自寫出不同資料。這一步沒有自動執行。

## 已實作的代理邊界

- 只有同時設定 `PLANWISE_PUBLIC_ORIGIN`、`PLANWISE_TRUSTED_PROXY_IPS` 和 `PLANWISE_COOKIE_SECURE=1` 才啟用；半套設定會拒絕啟動。
- `PUBLIC_ORIGIN` 必須是單一 HTTPS origin，不含帳密、路徑、查詢參數；主機名必須吻合。只信任設定內的**確切 connector IP**，不接受 `*` 或整段子網路。
- connector 必須提供 `X-Forwarded-Proto: https` 和單一合法 `CF-Connecting-IP`。後者作為限流訪客 IP；忽略 `X-Forwarded-For`／Host／Port 的偽造鏈。
- Gunicorn 自動轉發標頭信任停用，由上述邊界統一處理。CSRF／Origin／Referer／帳號權限檢查保留；壞掉的 Origin 也明確拒絕，不產生 500。
- Gunicorn 在 fork 前初始化 SQLite，避免兩個 worker 首次啟動時同時切換 WAL；資料庫連線仍按請求開關，格式不變。
- cookie 在此模式為 Secure／HttpOnly／SameSite=Strict。帳號 API、備份、錯誤回應均禁止快取；Cloudflare 端另設 `/api/*` Cache Rule 為 Bypass，不加 Cache Everything 規則。
- 只有容器本機的 `GET /healthz` 例外允許無代理標頭，供健康檢查；不提供帳號資料。

新配置的 Planwise 只在內部 Docker 網路；cloudflared 同時接內部網路和出站網路。沒有 privileged、Docker socket 或 Planwise 資料卷權限。預設固定 IP 為 `.2`／`.3`，子網為 `172.30.77.0/29`；若與既有 Docker／VPN 衝突，需一起修改三個地址，不能隨意放寬信任範圍。

## A. 現在可以做的隔離驗證

完整原始碼切換到此分支，使用 Python 3.12+、OpenSSL 命令及 Node；macOS／Linux 可執行：

```sh
python -m pip install -r nas/requirements.txt
python -m unittest discover -v
node --test nas/test_client.cjs
```

測試僅綁定 `127.0.0.1`，產生臨時憑證與資料庫。HTTPS client 明確信任該臨時 CA，沒有關閉憑證驗證；不是公開 Cloudflare 連線。每個模擬裝置使用獨立 Cookie jar，實際經 TLS relay → Gunicorn → SQLite 發送請求。

Linux Docker 的實際容器邊界檢查：

```sh
docker build --platform linux/amd64 -f nas/Dockerfile -t planwise-nas:test .
python nas/check_proxy_container.py
docker run --rm --network none cloudflare/cloudflared:2026.11.0 --version
```

第二條使用隨機名稱的專用容器／卷／網路，測完清理；從可信 `.3` 和不可信 `.4` 實際連接同一 origin。沒有發佈主機埠、沒有 Token、不啟動 cloudflared Tunnel。[驗證紀錄](CLOUDFLARE_TESTING.md)。

## B. 建立實際公網入口前，先確認

以下需使用者提供具體選擇及批准後才操作：

1. 域名及主機名，例如 `planner.你的域名`，以及域名費用、DNS 管理權；範例 `planner.example.com` 不是可用服務。
2. 使用哪個 Cloudflare 帳號／zone、建立哪一個**專用 Tunnel**，只發佈這個 Planwise 測試服務。
3. 同意 Cloudflare 代理流量；本階段**不啟用 Cloudflare Access**。如要加 Access，需另驗證 APK 外站登入跳轉，不能假設原 APK 支援。
4. 先用測試帳號及獨立資料卷；正式資料切換另做備份、核對與批准。
5. 撤回方式：停止此 `cloudflared` connector，停用該 hostname route／撤銷專用 Token；保留試作資料卷和原內網部署。

不要把 Cloudflare 密碼、Token 或驗證碼貼到聊天／GitHub。

## C. 批准後的 NAS 準備方法（尚未執行）

取得此分支的 [compose.cloudflare.yaml](../compose.cloudflare.yaml) 和 [.env.cloudflare.example](../.env.cloudflare.example)。把後者複製為 `.env.cloudflare`，設定**批准的** `PLANWISE_PUBLIC_ORIGIN=https://實際主機名`。預設從 `feature/nas-cloudflare-oop` 建置重構與代理整合後的程式；驗收後可把 `PLANWISE_BUILD_REF` 固定為此分支已測提交的完整 SHA。舊 `feature/nas-cloudflare` 及 0.3.0 標籤不包含這次 OOP 整合。

Token 只保存於 NAS 本地 `.secrets/cloudflare-tunnel-token`，不放環境變數值或命令列。以 NAS 檔案編輯器建立檔案，貼入 Dashboard 給該專用 Tunnel 的 Token；只放 Token 本身，不放整條 Docker 命令。Linux NAS 調整檔案擁有者／權限：

```sh
mkdir -p .secrets
chmod 700 .secrets
sudo chown 65532:65532 .secrets/cloudflare-tunnel-token
sudo chmod 400 .secrets/cloudflare-tunnel-token
```

cloudflared 明確以 UID/GID `65532:65532` 執行，只有它掛載這個 secret。Compose 的本地檔案型 secret 使用檔案來源權限，不能只依賴 YAML 的 `uid`／`mode` 自動改權限。NAS 管理員仍可讀取檔案。這些本地設定與 secret 已被 Git 忽略。

先只建置、啟動內部 origin；此時沒有公網 connector：

```sh
docker compose --env-file .env.cloudflare -f compose.cloudflare.yaml config --quiet
docker compose --env-file .env.cloudflare -f compose.cloudflare.yaml up -d --build planwise
docker compose --env-file .env.cloudflare -f compose.cloudflare.yaml exec planwise python -m nas.manage create-user admin --admin
```

在 Cloudflare 的公開應用／hostname route 設定：

- Hostname：與 `PLANWISE_PUBLIC_ORIGIN` 相同的實際主機名。
- Service：**HTTP** `http://planwise:8080`，不是舊 NAS 的 9473／自訂內網埠。
- HTTP Host Header：設為該公開主機名，不能填 `planwise:8080`。
- 啟用該主機名的 Always Use HTTPS；`/api/*` 設為 Bypass cache，保留標準 `CF-Connecting-IP` 和協定標頭。不要啟用會移除訪客 IP 的 Managed Transform，也不要設定 Pseudo IPv4 的 Overwrite Headers。

只有在上述公網權限已批准後，才啟動公開 profile：

```sh
docker compose --env-file .env.cloudflare -f compose.cloudflare.yaml --profile public up -d cloudflared
```

固定為經核對的官方 `cloudflare/cloudflared:2026.11.0`；`TUNNEL_TOKEN_FILE` 是官方支援的 Token 檔案方式。若連線失敗先查 Token 可讀性、Dashboard route、Host Header 和出站連線，不關閉來源／憑證驗證。

## D. HTTPS、舊 HTTP 與 APK

日常統一使用批准的 HTTPS 地址。新配置不會同時接受舊 HTTP 直接登入；Secure cookie 也不會發給 HTTP。原內網容器仍可按原模式運行，但那是另一個獨立服務／資料卷，不能當成兩個網址自動同步。

**0.3.0 NAS APK 的 Java 程式已接受 HTTPS 地址，本次沒有修改前端或 APK。** 若不用 Access，預期只需第三頁「更改 NAS 地址」填入新 HTTPS origin。更改地址會清掉 APK 原快取及 cookie，需在線登入一次再建立該地址的新離線快取；NAS 上的資料不會因此刪除。真實 Cloudflare 網址及 Android 真機登入仍待公開測試驗收，不以本機 TLS 測試代替。

## E. 停用／回退

最先停 connector，即可撤回這個連線入口，不刪除行程：

```sh
docker compose --env-file .env.cloudflare -f compose.cloudflare.yaml --profile public stop cloudflared
```

再於 Dashboard 停用專用 hostname route，按需要輪換／撤銷 Token。舊內網專案不受此命令影響。不要執行 `down -v` 或刪除任何資料卷。

若將來已遷移正式資料，回退前先備份 HTTPS 版的**最新**資料；不能直接啟用落後的舊卷而忽略切換後的修改。實際切換方案需在批准時依 NAS 的現有專案／掛載確認。

官方參考：[Tunnel 設定](https://developers.cloudflare.com/tunnel/get-started/)、[訪客 IP 與協定標頭](https://developers.cloudflare.com/fundamentals/reference/http-headers/)、[Token 檔案參數](https://developers.cloudflare.com/tunnel/reference/run-parameters/)、[Docker 檔案型 secrets](https://docs.docker.com/compose/how-tos/use-secrets/)。
