# Planwise 组员3修复与交接核查汇总报告

日期：2026年11月14日

本报告汇总组员3的输入校验与异常处理修复、逐文件修改、备份和测试结果，以及前一组员 HTTPS 与 OOP 分支交接说明的补充核查。主要输入边界问题已在本地修复；本地 Python 127 项与 Node 14 项回归通过。但前端畸形计划快照仍有一项已复现缺口，6 项 Gunicorn 集成及当前修改版部署验收尚未完成。

**2026年11月16日交付更新：用户已要求上传修改后的完整项目。源代码修复、测试用例、项目内测试记录及报告已纳入本地提交；原始 ZIP 备份保留在项目外。当前 GitHub 登录账号 xyc-1999 对 Z3ych1k/Planwise 无写权限，推送返回 403，远端上传尚未完成。**

## 一 项目基线和工作范围

- 本地项目目录：`Planwise`；备份保存在项目同级目录。
- 分支：`feature/nas-cloudflare-oop`
- 原始提交：`9779ee705dbb432ef721b8f6b63f44feedd95455`
- 交付范围：修复代码、测试用例、项目内测试记录和报告。已建立本地提交，远端推送因权限不足尚未完成；未部署。
- 修复前工作区无已有未提交修改；未操作其他目录中的旧版本项目。
- 截图中的组员分工用作职责参考。本报告不将截图中的“Usability 10%”视为已经核实的完整课程评分标准。

本次没有修改排程优先级、时间分配算法、账号权限设计、数据库表结构或页面布局。已有的半小时规则、事务回滚、请求幂等、CSRF 和多设备版本冲突机制继续沿用。

## 二 修复前备份

在修改源文件前，将原项目中全部 86 个 Git 管理文件打包，保留相对路径：

```text
Planwise-backup-20261114-093131/original-files.zip
Planwise-backup-20261114-093131/manifest.json
```

`manifest.json` 记录来源目录、原提交及各文件的 SHA-256。创建后，已读取 ZIP 内全部文件并与原文件摘要逐项比对，全部一致。备份目录名称中的时间来自执行主机；本文日期使用用户的 Asia/Shanghai 日期，目录名不作为用户本地精确时间声明。

备份覆盖本次修改的全部原文件，不包含 `.git` 历史，也不包含忽略或未跟踪的用户数据。本次测试使用临时账号、临时 SQLite 和临时 JSON，没有接触真实 NAS 数据库。

如需回退，先另外保存后续工作，再从 ZIP 中按相对路径恢复所需原文件。本次新增的 `validation.py` 和 `test_validation.py` 在原备份中不存在；完全回退代码时应同时移除这两个新增文件。报告和测试记录可另行保留。不要在有其他未保存修改时直接覆盖整个目录。

## 三 修复前发现的问题

### 1 空列表能穿过 API 校验

原 `nas/domain.py` 接受空列表字段，之后 `planner.py` 等位置使用 `data.get(key, [''])[0]`。字段存在但值为 `[]` 时，默认值不会生效，读取 `[0]` 引发 `IndexError`。

已复现的关键输入是 `save` 操作中的 `title: []`，以及 `save_settings` 中的 `language: []`。原测试模式抛出未处理异常；常规服务模式会成为服务端错误，而不是正确的输入错误响应。复现时原计划和版本号未改变。

### 2 日期错误直接暴露 Python 提示

输入 `2026-02-30` 时原系统虽返回 400，但错误文字为 Python 的英文日期范围异常。它没有清楚告诉使用者应如何修正，也无法稳定提供项目已有的三种界面语言。

### 3 导入流程提前访问未经验证的数据

NAS 在统一备份验证前自行解析 JSON，并直接对 `tasks` 等原始字段调用 `len()`。字段为 `null` 等错误结构时会走通用类型异常路径；语法错误也可能直接暴露解析细节。应当复用已有的 `import_state()`，先验证和迁移，再检查 NAS 的条目数量限制。

### 4 前端默认所有响应均为 JSON

原 NAS 前端直接执行 `response.json()`。代理或服务器返回 HTML 错误页时，解析异常可能丢失原 HTTP 状态并显示底层异常；不可读的成功响应也不能作为保存已成功的证据。

### 5 本地读取和异常兜底仍有缺口

本地文件读取没有统一处理过深 JSON 触发的 `RecursionError`。NAS 原有处理器覆盖业务异常和数据库异常，但其他未预料异常仍可能产生 HTML 错误页。需要在保留日志和错误状态码的前提下提供稳定响应，而不是假装保存成功。

## 四 逐文件修改说明

| 文件 | 修改位置或职责 | 修改内容与原因 |
| --- | --- | --- |
| `validation.py` 新增 | `normalize_fields()`、`parse_date()` | 统一外部表单字段结构校验及友好日期解析，供 NAS 和本地 Android 共用 |
| `nas/domain.py` | `apply()` | 用共用校验代替原循环；导入先执行 `import_state()` 再检查 NAS 上限；工作日转换失败提供明确提示 |
| `planner.py` | `mutate()` | 任务开始日和截止日改用友好日期解析；保留已有日期先后和工时规则 |
| `events.py` | `save_event()`、`move_occurrence()`、`cancel_occurrence()` | 事项日期、重复结束日期、单次原日期和移动目标日期使用友好日期解析 |
| `nas/application.py` | 新增最终异常处理器 | 未预料异常记录堆栈并返回 500 JSON；API 的 HTTP 错误保持状态码并返回 JSON；原业务、413 和 SQLite 专用处理器继续保留 |
| `nas/static/ui.js` | `api()`、`change()`、翻译条目 | 捕获 JSON 解析失败和非对象结果；保留失败响应的 HTTP 状态；不可读成功响应进入结果未确认流程；请求 ID 生成移入 `try`，保证异常时执行释放状态逻辑 |
| `android/runtime/main.py` | `Handler.do_POST()` | URL 表单解析后统一校验，拒绝重复单值字段，复用原 400 错误反馈和先保存后更新内存的流程 |
| `storage.py` | `load_state()` | 将结构访问、溢出和递归异常纳入读取失败提示；原文件保留，本地运行时可进入只读恢复状态 |
| `translations.json` | 新错误提示 | 新增 7 条服务端提示的简体和英文翻译；繁体使用原消息；原有工作日及备份翻译继续复用 |
| `.dockerignore` | Docker 构建白名单 | 允许 `validation.py` 进入构建上下文 |
| `nas/Dockerfile` | 共用模块 COPY | 将 `validation.py` 放入 NAS 镜像，避免部署后导入失败 |
| `android/build-apk.sh` | Python 文件复制清单 | 将 `validation.py` 复制至 Android Python 运行目录 |
| `nas/test_api.py` | 新增 8 个测试方法 | 覆盖空列表、多值、错误类型、日期翻译、损坏备份、工时和名称边界、异常回滚及 HTTP JSON 响应 |
| `test_validation.py` 新增 | 7 个测试方法 | 覆盖共用校验、闰日、结构限制、打包清单、过深本地文件保护，以及本地 Android HTTP 保存与重新加载 |
| `nas/test_client.cjs` | 测试传输模拟及新增 4 个用例 | 模拟无效 JSON 和实际的 `null`；覆盖 HTML 错误页、错误响应结构、失败保留输入和后续重试、保存结果未确认 |

### 字段校验的具体约定

`normalize_fields()` 在业务函数读取字段之前运行。最多接受 100 个字段，字段名必须是字符串且最多 100 字符，每个列表最多 20 项。沿用原 NAS 可接受文字及数值的约定，转换为内部使用的字符串列表；拒绝布尔值、`null`、嵌套对象、嵌套列表、`NaN` 和无穷值。

普通单值字段必须恰好提供一个值，既拒绝空列表，也拒绝重复值。`workdays` 和 `weekdays` 属于多选字段，可提供多个值，也可为空；随后由既有业务规则检查星期范围及默认行为。缺失字段仍交给原业务层判定是否必填，避免把所有字段都错误地设为必填。

这里的“恰好一个值”不等于“非空文字”。例如空任务名仍由任务层拒绝，而可选的空开始日期仍然合法。没有将所有空列表简单替换为空字符串，因为那会掩盖结构错误。

### 日期与数据安全的处理方式

`parse_date()` 仍调用 Python 原有日期解析，成功时返回日期对象；只转换预期的类型和日期格式错误，提示有效日期示例，并去掉底层异常链的外部展示。导入备份继续使用统一的备份格式错误提示，不将其逐个改写为交互日期错误。

NAS 数据写入继续由现有 SQLite 事务管理，异常离开事务后回滚，再生成失败响应。新增兜底不返回成功、不吞掉服务器日志，也不自动重试写操作。对于未知错误，提示用户刷新并核对最新数据，不笼统承诺所有请求都必然未发生任何副作用。

前端拿到 HTTP 错误页时保留状态码；HTTP 200 但响应不可读时，不能证明保存失败或成功，沿用现有“结果未确认、重新连接后核对”的只读机制，避免直接重复记录投入。

## 五 测试方法与结果

本次环境为 Windows，Python 3.14.6，Node.js v24.21.0。没有为了完成测试而修改全局依赖或安装 Gunicorn。

| 验证项 | 结果 | 说明 |
| --- | --- | --- |
| Python 可运行回归集 | 127 项通过，0 失败，0 错误 | 包含原有排程、事项、偏好、计划变化、API、账号邀请、管理命令、代理规则和新增校验测试；结果对应本地修复工作区，不是远端原提交 |
| Node 前端回归集 | 14 项通过，0 失败 | 原有 10 项及本次新增 4 项 |
| NAS 前端语法 | 通过 | `node --check nas/static/ui.js` |
| Android 前端语法 | 通过 | `node --check android/runtime/app.js` |
| Python 编译检查 | 通过 | 共用模块、NAS 和本地 Android runtime |
| Git 差异空白检查 | 通过 | `git diff --check` |
| Gunicorn TCP/TLS 集成 | 6 项未执行 | `nas.test_proxy_live` 依赖未安装的 Gunicorn；当前 Windows 环境不作为其部署运行环境 |

新增 Python 测试方法共 15 个，许多方法通过子测试覆盖多种非法输入，不能将方法数等同于全部输入组合数量。

重点验收证据：

1. `title: []`、`language: []` 和普通字段多值均返回 400，状态及版本号不变。
2. 空工作日、多选星期依然可以成功保存，避免修复引入兼容性退化。
3. 不存在的日期返回可理解提示，并验证繁体、简体和英文三种语言。
4. 工时为非数字、负数、四分之一小时、非有限数值，以及空白或超长名称时，保存被拒绝且原计划不变。
5. 无效 JSON、空备份、错误包装结构和缺少事项字段等导入均被拒绝，并保留原数据。
6. 模拟未预料业务异常时返回 500 JSON，响应不含内部错误细节，原计划和版本号不变。
7. 继续通过原有数据库写失败回滚、重复请求幂等、多设备冲突、账号隔离和权限测试。
8. 本地 Android 实际启动回环 HTTP 服务，验证重复字段和非法日期返回 400；随后正常任务可保存为 200，并从 JSON 文件重新读取。
9. 本地过深 JSON 文件不被覆盖，服务进入只读状态。
10. 前端模拟错误页和不可读响应；验证旧计划、输入内容保留，普通校验失败后按钮恢复且下一次合法修改可成功。

自动化前端测试使用 Node VM 中的 DOM 模拟；本地 Android 测试运行 Python 回环服务。两者都不是实体手机或完整浏览器点击测试，报告不将其表述为设备实测。

### 复跑命令

在项目根目录执行以下 PowerShell 命令，可复跑本次 127 项 Python 测试和 14 项前端测试：

```powershell
python -m unittest test_events test_planner test_preferences test_schedule_changes test_timetable test_validation nas.test_api nas.test_invitations nas.test_manage nas.test_proxy -v
node --test nas/test_client.cjs
node --check nas/static/ui.js
node --check android/runtime/app.js
python -m compileall -q validation.py planner.py events.py storage.py nas android/runtime
git diff --check
```

以下测试记录已随项目纳入本地 Git 提交；远端推送成功后可按这些相对路径查看：

- `docs/member3-test-results/python-regression.log`：127 项结果，开头列出 6 项未执行集成测试。
- `docs/member3-test-results/node-regression.log`：14 项前端测试结果。
- `docs/member3-test-results/verification.json`：备份核验及辅助检查结果。

完整发现命令 `python -m unittest discover -v` 还会加载 `nas.test_proxy_live`。在具备项目依赖和 Gunicorn 的适当 Linux 或 NAS 环境中，应补跑该模块的 6 项用例。本机缺少该依赖不应通过删除测试或假装通过来处理。

## 六 与前一组员交接说明的核对

| 上个组员说明 | 当前证据 | 交接核查阶段结论 |
| --- | --- | --- |
| 基于 OOP 分支，保留时间模块解耦 | `time_slots.py` 继续存在，时间解析仍共用 | 保留；首次修复阶段未重写该模块 |
| 保留 NAS 保存流程拆分 | `prepare_plan_snapshot()` 与 `commit_plan_action()` 继续存在 | 保留；首次修复阶段未重新合并流程 |
| 保留 Database 封装 | `nas/database.py` 中 `Database` 及事务管理继续存在 | 保留 |
| HTTPS 来源和可信代理校验 | `nas/proxy.py`、`same_origin()`、代理单元测试 | 保留；交接核查阶段另对 HTTPS 可信代理模式做针对性补测 |
| Secure Cookie 和 API 禁缓存 | 登录 Cookie 属性、响应头及现有测试 | 交接核查阶段验证 Secure、HttpOnly 和错误响应的 CDN no-store |
| 多账号隔离和版本冲突 | 原 API 测试仍在 127 项通过记录中 | 本机 API 回归通过；不等同真实多 worker 部署验证 |
| Python 118 项、Node 10 项 | 仓库交接文档说明 Python 含 112 项普通测试及 6 项 Gunicorn HTTPS 集成 | 原数字属于旧基线；不能直接代表本地修复后版本 |
| Docker 构建、数据保留升级和代理测试 | `.github/workflows/nas-check.yml` 包含对应步骤和脚本 | 流程已存在；交接核查阶段未验证远端历史 CI 运行结果，也未运行当前修改版 Docker 验收 |
| 补齐 time_slots.py 打包遗漏 | 原 Docker 白名单、COPY 和 Android 清单包含该模块 | 已保留；首次修复阶段也已为新增 validation.py 补齐三处清单 |
| 固定 Cloudflare Tunnel Compose | `compose.cloudflare.yaml` 和部署文档存在 | 配置已交付；未启动真实 Tunnel |
| Quick Tunnel 支持 | 仓库搜索仅查到未启动说明，未查到专用 Quick Tunnel 脚本或操作教程 | 无法仅凭当前仓库确认该项完整交付；应与前一组员澄清“支持”的具体含义，不自动启动公网服务 |
| 没有合回 main | 当前分支仍为 feature/nas-cloudflare-oop | 本次没有执行 main 合并或推送；不据此独立证明完整远端合并历史 |

## 七 已复现但尚未修复的前端遗漏

位置：`nas/static/ui.js` 的 `api()` 和 `adopt()`。

首次修复阶段已处理 JSON 语法错误、HTML 错误页、null、数组和标量。但一个“可以解析的 JSON 对象”仍可能缺少计划必要结构。例如：

```json
{"api_version":1,"user":{"id":1},"state":null,"view":{}}
```

模拟前端已加载正常计划后，服务器以 HTTP 200 返回该对象，观察到：保存函数返回 false，进入离线状态，但是 `adopt()` 已经执行 `snap=data`，之后读取 `data.state.language` 才发生错误。此时内存中的 `snap.state` 已为 null，原计划不再保留于当前内存对象。

这不是已证实的数据库损坏：交接核查阶段使用模拟响应，没有写真实服务器；先前持久缓存也不能据此断言已被覆盖。问题是前端失败时未能保证原有效内存状态仍可显示。

建议作为组员3下一项代码补修：在任何快照赋值、缓存清理或界面更新之前，验证计划响应必要结构，包括 api_version、user、state、view 及页面使用的关键数组；结构错误走统一无效响应路径。不同端点返回不同类型的对象，不应把所有登录、注销和邀请 API 都强制要求返回计划快照。

应新增回归断言：畸形对象不能替换旧 snap、不能覆盖缓存、不能报保存成功；提示保存结果未确认；恢复连接取得合法计划后可以继续操作。还应覆盖 state 为 null、缺失 user、tasks 非数组等情况。

本地证据：`docs/member3-test-results/handoff-client-audit.json`；已纳入完整项目的本地提交，等待推送。

## 八 HTTPS 可信代理模式补测

使用 Flask test client、临时数据库、临时账号，启用 PUBLIC_ORIGIN、确切 TRUSTED_PROXY_IPS 和 COOKIE_SECURE。补测不涉及真实 Cloudflare 网络或真实 NAS。

- 登录成功，Cookie 保留 Secure 和 HttpOnly。
- title 空列表、language 空列表、非法日期均返回 400 JSON。
- 上述错误请求前后计划和版本一致，响应保留 Cloudflare-CDN-Cache-Control no-store。
- 不可信代理 peer 返回 403。
- 转发协议为 http 返回 403。

本地证据：`docs/member3-test-results/handoff-proxy-audit.json`；已纳入完整项目的本地提交，等待推送。这是针对性补测，不计入原 127 项 unittest 数量，也不能替代 Gunicorn TLS 集成测试。

## 九 尚未完成事项和下一步

| 优先级 | 事项 | 当前状态 | 完成标准 |
| --- | --- | --- | --- |
| P1 | 前端计划快照结构验证 | 已复现，尚未补修 | 先验证后赋值；畸形响应不替换旧计划、不清除或覆盖缓存，恢复连接后仍可继续操作 |
| P1 | 修复代码交付 | 已建立本地提交，远端推送因 403 失败 | 取得目标仓库写权限或明确个人 fork 目的地后推送 |
| P1 | 当前修改版 Linux 回归 | 6 项 Gunicorn 集成未运行 | 使用包含修复的提交，运行现有 Linux CI；不得复用旧提交通过结果 |
| P2 | 容器构建与数据保留升级 | 未运行当前修改版 | 通过现有 Docker 构建、持久化、旧版升级及容器代理测试 |
| P2 | 本地 Android APK 构建和手机验收 | 仅静态核对复制清单及回环服务测试 | 成功构建 APK，验证安装、非法输入、保存和重启读取 |
| P2 | 真实 HTTPS 部署验收 | 未启动真实服务 | 在测试账号与独立数据上核对域名、Tunnel、NAS 权限和外网手机登录 |
| 待澄清 | Quick Tunnel 交接范围 | 缺少专用教程或脚本证据 | 由前组员说明其“支持”的含义；不默认要求组员3启动公网服务 |

原基线 118 项 Python = 112 项普通测试 + 6 项 Gunicorn 集成。首次修复新增 15 个 Python 测试方法后，当前代码对应 133 项，其中本机已运行 127 项且全部通过，6 项未执行；Node 从 10 项增加至 14 项，全部通过。补充 HTTPS 审计是额外探测，不重复计入 127 项 unittest。

当前 Windows 主机没有找到 Docker 命令，Gunicorn 不可用；查询 WSL 分发版时得到访问拒绝，未通过提权或安装软件绕过。现有 `.github/workflows/nas-check.yml` 已包含全量 Python、Node、Compose、Docker、数据持久化、升级和代理检查，无需另起一套流程。

2026年11月14日交接核查时，远端 feature/nas-cloudflare-oop 分支仍指向原始提交 `9779ee705dbb432ef721b8f6b63f44feedd95455`。2026年11月16日已将修复、测试及报告纳入本地提交，但推送返回 403；源代码修复尚未进入目标远端。

部署时还需注意：根目录 `compose.yaml` 从远端 `nas-v0.3.0-preview` 标签构建；`compose.cloudflare.yaml` 默认从远端 `feature/nas-cloudflare-oop` 构建。两者都不会读取本地未提交和未推送的修改。代码交付后应让构建明确使用已经验证的提交，或明确采用本地构建上下文。
