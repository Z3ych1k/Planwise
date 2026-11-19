# Planwise 组员交接补充核查

日期：2026年11月14日。核查对象为用户补充截图中的上个组员说明、当前代码和组员3修复记录。本轮只检查和补测，未修改业务代码；新增本说明及两份审计结果文件。

## 核查结论

当前代码保留前一组员的 OOP 整理与 HTTPS 可信代理实现。组员3上轮的主要输入校验修复已经完成，但存在一项已复现的前端响应结构校验遗漏。交付闭环还缺少修复后版本的 Linux 全量集成、容器构建与升级验收，以及将本地修改交给实际部署源的步骤。真实公网及手机验收仍不能视为已完成。

## 交接内容逐项核对

| 上个组员说明 | 当前证据 | 本轮结论 |
| --- | --- | --- |
| 基于 OOP 分支，保留时间模块解耦 | `time_slots.py` 继续存在，时间解析仍共用 | 保留；上轮未重写该模块 |
| 保留 NAS 保存流程拆分 | `prepare_plan_snapshot()` 与 `commit_plan_action()` 继续存在 | 保留；上轮未重新合并流程 |
| 保留 Database 封装 | `nas/database.py` 中 `Database` 及事务管理继续存在 | 保留 |
| HTTPS 来源和可信代理校验 | `nas/proxy.py`、`same_origin()`、代理单元测试 | 保留；本轮另对 HTTPS 可信代理模式做针对性补测 |
| Secure Cookie 和 API 禁缓存 | 登录 Cookie 属性、响应头及现有测试 | 本轮验证 Secure、HttpOnly 和错误响应的 CDN no-store |
| 多账号隔离和版本冲突 | 原 API 测试仍在 127 项通过记录中 | 本机 API 回归通过；不等同真实多 worker 部署验证 |
| Python 118 项、Node 10 项 | 仓库交接文档说明 Python 含 112 项普通测试及 6 项 Gunicorn HTTPS 集成 | 原数字属于旧基线；不能直接代表本地修复后版本 |
| Docker 构建、数据保留升级和代理测试 | `.github/workflows/nas-check.yml` 包含对应步骤和脚本 | 流程已存在；本轮未验证远端历史 CI 运行结果，也未运行当前修改版 Docker 验收 |
| 补齐 time_slots.py 打包遗漏 | 原 Docker 白名单、COPY 和 Android 清单包含该模块 | 已保留；上轮也已为新增 validation.py 补齐三处清单 |
| 固定 Cloudflare Tunnel Compose | `compose.cloudflare.yaml` 和部署文档存在 | 配置已交付；未启动真实 Tunnel |
| Quick Tunnel 支持 | 仓库搜索仅查到未启动说明，未查到专用 Quick Tunnel 脚本或操作教程 | 无法仅凭当前仓库确认该项完整交付；应与前一组员澄清“支持”的具体含义，不自动启动公网服务 |
| 没有合回 main | 当前分支仍为 feature/nas-cloudflare-oop | 本次没有执行 main 合并或推送；不据此独立证明完整远端合并历史 |

## 已复现的遗漏 前端计划响应结构校验

位置：`nas/static/ui.js` 的 `api()` 和 `adopt()`。

上轮已处理 JSON 语法错误、HTML 错误页、null、数组和标量。但一个“可以解析的 JSON 对象”仍可能缺少计划必要结构。例如：

```json
{"api_version":1,"user":{"id":1},"state":null,"view":{}}
```

模拟前端已加载正常计划后，服务器以 HTTP 200 返回该对象，观察到：保存函数返回 false，进入离线状态，但是 `adopt()` 已经执行 `snap=data`，之后读取 `data.state.language` 才发生错误。此时内存中的 `snap.state` 已为 null，原计划不再保留于当前内存对象。

这不是已证实的数据库损坏：本轮使用模拟响应，没有写真实服务器；先前持久缓存也不能据此断言已被覆盖。问题是前端失败时未能保证原有效内存状态仍可显示。

建议作为组员3下一项代码补修：在任何快照赋值、缓存清理或界面更新之前，验证计划响应必要结构，包括 api_version、user、state、view 及页面使用的关键数组；结构错误走统一无效响应路径。不同端点返回不同类型的对象，不应把所有登录、注销和邀请 API 都强制要求返回计划快照。

应新增回归断言：畸形对象不能替换旧 snap、不能覆盖缓存、不能报保存成功；提示保存结果未确认；恢复连接取得合法计划后可以继续操作。还应覆盖 state 为 null、缺失 user、tasks 非数组等情况。

证据：`docs/member3-test-results/handoff-client-audit.json`。

## 本轮补测 HTTPS 模式兼容性

使用 Flask test client、临时数据库、临时账号，启用 PUBLIC_ORIGIN、确切 TRUSTED_PROXY_IPS 和 COOKIE_SECURE。补测不涉及真实 Cloudflare 网络或真实 NAS。

- 登录成功，Cookie 保留 Secure 和 HttpOnly。
- title 空列表、language 空列表、非法日期均返回 400 JSON。
- 上述错误请求前后计划和版本一致，响应保留 Cloudflare-CDN-Cache-Control no-store。
- 不可信代理 peer 返回 403。
- 转发协议为 http 返回 403。

证据：`docs/member3-test-results/handoff-proxy-audit.json`。这是针对性补测，不计入原 127 项 unittest 数量，也不能替代 Gunicorn TLS 集成测试。

## 测试数字说明及尚未闭环事项

原基线 118 项 Python = 112 项普通测试 + 6 项 Gunicorn 集成。上轮新增 15 个 Python 测试方法后，当前发现的 Python 集合对应 133 项，其中本机运行 127 项全部通过，6 项未运行。Node 从原 10 项增加至 14 项，均通过。

Linux CI 已配置 unittest discover、Node、Compose 校验、Docker 构建、数据持久化、旧版升级和容器可信代理检查，不需要另起一套 CI。需要让**包含本地修改的提交**运行这套现有流程，并保留对应 SHA 的结果；旧提交通过不能作为当前修改版通过的证据。

当前主机没有找到 Docker 命令，Gunicorn 不可用；尝试查询 WSL 分发版时得到访问拒绝，未通过提权或安装软件绕过。故本轮未运行上述 Linux 和容器验收。

部署源还需要明确：根目录 compose.yaml 固定从远端 nas-v0.3.0-preview 标签构建；compose.cloudflare.yaml 默认从远端 feature/nas-cloudflare-oop 构建。两者都不会读取工作目录里尚未提交和推送的文件。后续应先完成补修，再提交交付并针对该提交运行 CI，部署时选择已验证的提交或明确改用本地构建上下文。这个步骤尚未执行，本轮不擅自推送或更换生产部署配置。

真实域名、Tunnel Token、Cloudflare edge、NAS 网段和权限、外网手机及 Android HTTPS 登录仍属于部署验收，不应标记为本地代码测试完成。前组员仓库文档也明确区分了这些范围。

完成建议优先级：先补前端快照结构校验及回归测试，再完成包含修改的提交与 Linux CI，随后构建并验收容器及 APK，最后在实际部署环境进行网络和手机验证。Quick Tunnel 交付含义单独澄清，不作为输入校验任务的默认前置条件。
