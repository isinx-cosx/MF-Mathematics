# 功能边界

> 本文回答一个问题：哪些事是「想过、并且决定不做」的，哪些是推迟的，哪些是设计导致的能力上限，哪些尚未验证。
> 与兄弟文档的分工：[`DESIGN.md`](DESIGN.md) 讲这些选择背后的理念；[`DECISIONS.md`](DECISIONS.md) 记录逐条决定的代价；产品门面在 [`../README.md`](../README.md)。
> 权威源是 [`../README.md`](../README.md) 的「边界」一节与 [`../MFMath.Host.Rust/docs/PACKAGING.md`](../MFMath.Host.Rust/docs/PACKAGING.md)。

## 四类的性质

四类「没做」性质不同，混在一起会退化成免责声明。下表先立总纲：

| 类别 | 含义 | 谁能改 | 推翻门槛 |
| --- | --- | --- | --- |
| 不实现 | 想过，决定不做，有理由 | 需要新证据 | 一个具体场景 + 证据，证明缺它就不能用 |
| 推迟 | 想做，现在不做，有前置条件 | 前置条件满足就做 | 证明前置条件已满足 |
| 能力上限 | 设计选择的直接后果，不是「没做」 | 改设计，不是补功能 | 不动门槛；要改先改 [`DESIGN.md`](DESIGN.md) 与 [`DECISIONS.md`](DECISIONS.md) |
| 未验证 | 可能能用，但无人验过 | 验一次转正 | 验一次 |

四类的判据：

- 「不实现」与「推迟」的区别：推迟的每一条写得出回来的条件；写不出的是不实现。
- 「推迟」与「能力上限」的区别：推迟是「被前置条件挡住」，能力上限是「设计就要求这样，没有前置条件可满足」。
- 「能力上限」与「未验证」的区别：能力上限是「验过、确实如此」，未验证是「没验过、不能下结论」。
- 「未验证」最容易出错，也最该先看。把「没验过」当成「没有」，会白做一遍工作；把「没验过」当成「有」，会对外承诺一个不存在的能力。两类误读后果不同，但都源于同一件事：不写现状、只写结论。

## 怎么把新请求归类

一个新请求到来时，按顺序回答四个问题：

1. 是否有前置条件（服务端配合、外部 payload、另一项设计先落地）？有，且条件写得出 → 推迟；写不出条件 → 不实现。
2. 是否已有明确的「不做」结论，且理由仍然成立？是 → 不实现；理由是「设计本身要求这样」 → 能力上限。
3. 是不是改一行代码就能补，但没人验证过它能用？是 → 未验证，验一次转正。
4. 是不是「删掉更干净、但失去回退」这类取舍的产物？是 → 能力上限，配套可见断言（如冻结白名单）。

归类后照「怎么推翻一条」的对应行决定要不要动手。

## 不实现

性质：这类事项已经讨论过，结论是不做，理由在当时成立。推翻它们需要新证据，不是「想起来了就做」。

| 事项 | 为什么 | 机制落点 | 推翻门槛 |
| --- | --- | --- | --- |
| 不重建后端（用户系统 / 组件清单 / 版本检测） | 站点已有这些能力，重建等于维护两份真相 | 复用既有站点端点，默认基址 `https://mf-vis-science.cn`（`Select-String -Path MFMath.Host.Rust/src/site.rs -Pattern "DEFAULT_BASE_URL"`） | 站点侧长期不可用，且有实测证明挡住发布 |
| 更新不自动下载、不自动安装 | 只提示有新版，下载交给浏览器 | `update` 宿主对象只有 `Check` / `OpenDownloadPage` / `PreviewDownloadUrl`，无下载与执行入口（`Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "UPDATE_SPEC"`） | 出现需要客户端自动落盘与执行的场景 |
| 崩溃与前端异常不上报 | 数学工具的使用内容可反推用户在研究什么，隐私优先 | 只写 `%LOCALAPPDATA%\MFMath\logs\`，由用户主动导出诊断包（`sys.ExportDiagnostics`） | 需要线上崩溃分布才能定位的问题反复出现 |
| AI 密钥不走 DPAPI 密文 | 密钥由页面直连使用，宿主侧没有 `ai` 桥 | 明文存 `%LOCALAPPDATA%\MFMath\settings\ai.json` 的 `apiKey` 字段，界面标 `keySource: "file"`（`Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/ai/bridge.js -Pattern "keySource"`） | 有明确的安全需求变更 |
| 数学能力不硬凑 | 非初等函数的不定积分返回「未实现」，不返回错误原函数 | `MF_Mathematics/calculus/integrals.cpp` 的 `"未实现"`、`1e12` 安全阀与瑕点检测 | 出现必须给出原函数才能使用的场景 |
| 不提供许可证 | 作者保留后续授权方式的选择权 | 仓库根无 `LICENSE` / `COPYING` 文件（`Get-ChildItem -File | Where-Object { $_.Name -match 'LICENSE|COPYING' }`） | 作者本人改主意 |

「数学能力不硬凑」与「能力上限」一节里的「符号层如实拒绝」是同一件事的两个侧面：前者写「为什么不做」，后者写「为什么这是设计而不是缺陷」。

## 离线范围的准确口径

「离线优先」的边界由 [`../README.md`](../README.md) 的「边界」一节给出：断网后本地计算、绘图、教程、控制台照常；联网搜索、账号与 AI 助手需要网络。这条口径的机制在 [`DESIGN.md`](DESIGN.md) 的「离线范围与隐私默认」一条：涉及网络的用例一律跑在自带的假端点上，因此判据本身不需要真网络。

需要网络的三个功能各自的落点：

| 功能 | 宿主对象 / 前端落点 | 依赖的服务 |
| --- | --- | --- |
| 联网搜索 | `search` 宿主对象（App ID 走 DPAPI 密文，只在宿主） | 搜索服务 |
| 账号 | `account` 宿主对象（token 只在宿主，页面只见脱敏字段） | `https://mf-vis-science.cn` 的 `/api/*` 端点 |
| AI 助手 | 页面直连模型端点（`src/lib/ai/`，密钥明文存 `ai.json`） | 模型服务 |

这三项之外的能力离线可用。离线边界可验收：断网后本地计算、绘图、教程、控制台照常。

## 推迟

性质：这类事项想做，但被一个前置条件挡住，不是被否定。每一条都必须写得出「回来的条件」，写不出的就归入不实现。

| 事项 | 前置条件 | 回来的条件 |
| --- | --- | --- |
| 更新回滚 | 需要服务端配合（版本清单 + 旧包留存策略） | 站点侧先有回滚清单 |
| 控制台可选组件（CPython 嵌入包 / MinGW 工具链） | 组件清单端点返回 `payloadAvailable: true`；payload 常量是 `PYTHON_PAYLOAD_NAME`、`CPP_PAYLOAD_NAME`（`Select-String -Path MFMath.Host.Rust/src/console.rs -Pattern "PAYLOAD_NAME"`） | 两个 payload 在下载源可用后，`con.Components` 的清单不再标不可用 |
| AI 多模态 | 输入通道、成本模型、UI 都要改 | 有明确的使用场景 |
| 多语言覆盖页面正文与教程正文 | 目前只覆盖导航、模式名、参数弹窗标签、结果字段、键盘分类 | 逐步迁移，`npm run check` 拦漏译；迁移方法见 [`../README.md`](../README.md)「边界」一节 |
| 安装包 `tauri.conf.json` 固化 | 现在用 `--config` 内联覆盖出包，仓库里的 `bundle.active` 仍是 `false` | 真机确认安装没问题后，把覆盖固化进 `tauri.conf.json`（见 [`PACKAGING.md`](../MFMath.Host.Rust/docs/PACKAGING.md)） |

「控制台可选组件」这一条的性质要分清：实现代码在 `MFMath.Host.Rust/src/console.rs` 已存在，缺的是下载源上的两个 payload，而不是代码。它因此是「推迟」，不是「不实现」。

## 能力上限

性质：这一节的每一条是设计选择的直接后果，改它等于改设计，不是补一个功能。它们的根在 [`DESIGN.md`](DESIGN.md) 的「结果不臆造」与「计算来源唯一」两条。

| 边界 | 现状 | 为什么是有意的 | 机制落点 |
| --- | --- | --- | --- |
| 前端不计算 | 没有宿主进程就没有数学，浏览器预览里 `engineCall()` 返回 `null` | 单一计算来源，数值与符号结果只来自引擎 | `MF_UI/MFMath.UI.Vue/src/lib/bridge.js` 的 `if (!mf) return null` |
| 取消不真停 | `CancelJob` 只做到「停止等待 + 丢弃结果」，工作线程会把这一步算完 | 引擎没有取消钩子；真停只能靠进程边界 | `MFMath.Host.Rust/src/jobs.rs` 的 `cancel_job()`，界面文案「已停止等待」 |
| 引擎调用串行 | 一次只跑一个重活 | 引擎除一个 `thread_local` 外无同步原语，并发会踩 FLINT / SymEngine 全局缓存 | `MFMath.Host.Rust/src/jobs.rs` 的 `worker_loop()` |
| 同步与异步的分界是规模阈值 | `mandelbrot` 1.5e8、`complex_grid` 2.5e5、`expr_eval_grid` 2.5e5、`matrix_multiply` 2e6 以上走异步 job 通道 | 判据是数出来的工作量，不是「重不重」；绘图页每条曲线一次的采样保持同步 | `MF_UI/MFMath.UI.Vue/src/lib/engine/asyncPolicy.js` 的阈值 |
| C ABI 只暴露两个函数 | 跨进程边界只有 `math_call` 与 `function_exists`，只收发 `const char*` 与调用方缓冲区 | DLL 边界不暴露 `std::string` / `std::vector` / `SymEngine::RCP`，内部签名可自由重构 | `MF_Mathematics/api.h` 与 `api.cpp` |
| 符号层如实拒绝 | 求不出初等原函数、部分不定式极限、复变不定积分时返回「未实现」或错误信封 | 一个错误的原函数比「未实现」危害大 | `MF_Mathematics/calculus/integrals.cpp` |
| 多语言只覆盖界面层 | 导航、模式名、参数弹窗标签、结果字段、键盘分类已中英双语；页面正文与教程正文仍是中文 | 覆盖面逐步扩大，不是没做 | `MF_UI/MFMath.UI.Vue/tools/check-ui.mjs` 输出各 i18n 行的缺口计数 |
| Vue 绘图组冻结 | 7 条 `/plot/*` 路由指向 React，Vue 版 6 个文件保留为回退资产，不参与构建、不在类型检查范围 | 删除更干净但失去回退；冻结 + 断言不许悄悄接回 | `MF_UI/MFMath.UI.Vue/tools/check-ui.mjs` 的 `FROZEN_VUE_PLOT_FILES` |
| C# 宿主已停止演进 | `MFMath.Host/` 保留作迁移参考，不是现役实现 | 现役宿主只有 `MFMath.Host.Rust/` | 涉及宿主行为的说明以 Rust 侧为准（[`link/HOSTS.md`](link/HOSTS.md)） |

「多语言只覆盖界面层」同时出现在「能力上限」与「推迟」两节没有冲突：其界面层覆盖是设计现状（能力上限），其页面正文与教程正文的迁移是推迟。两节各写各的那一半。

## 未验证

性质：这类事项可能已经能用，只是无人验过，因此不能对外承诺。它们与「能力上限」的区别是：能力上限是「验过、确实如此」，未验证是「没验过、不能下结论」。权威源是 [`PACKAGING.md`](../MFMath.Host.Rust/docs/PACKAGING.md) 的「未能验证的部分」一节。

| 事项 | 现状 | 验证方法 |
| --- | --- | --- |
| 安装包「安装 → 启动」整体路径 | 可出 NSIS 安装包（实测 11.11 MiB），但装完的布局、安装 / 卸载、从安装目录启动均未验过 | 真机上按 [`PACKAGING.md`](../MFMath.Host.Rust/docs/PACKAGING.md) 的「真机上要走的验证」走五步 |
| 静默安装到指定目录 | 本机 `Start-Process` 起安装器报 `ERROR_CANCELLED`，改用 `& <setup> /S /D=<dir>` 则静默不生效、目标目录未创建；归因是「环境没准备好」，不是「打包做错」 | 真机上执行静默安装并确认目标目录 |
| 安装目录布局 | exe + 6 引擎 DLL + `wwwroot/` + `python/` + `cpp/` 是否齐备未实测，依赖上一条 | 打开安装目录逐项核对 |
| 包内是否收到运行资产 | 无法证实也无法证伪：NSIS 文件表整体压缩，扫安装器里的明文必然扫不到；体积不决定性（exe 单独 13.9 MB，安装器 11.11 MB） | 真机安装后核对安装目录内容 |
| 卸载行为 | 卸载后程序目录是否清空、`%LOCALAPPDATA%\MFMath` 是否保留未实测 | 真机卸载后核对两个目录 |
| `installMode` 是否生效 | 默认 / `currentUser` 两次构建在本机表现相同，结论「默认需要管理员」无证据；已证实安装器 manifest 是 `asInvoker` | 真机分别安装观察是否请求管理员 |
| 站点端点部署状态 | 账号 / 版本检测走 `https://mf-vis-science.cn`，线上是否部署了各 `/api/*` 路由未核对 | 对已部署的 `POST` 端点发请求，期望返回不是 404（`Invoke-WebRequest -Method Post -Uri https://mf-vis-science.cn/api/token/refresh -SkipHttpErrorCheck`） |
| 控制台可选组件 payload 可用性 | 组件清单端点是否已提供两个 payload 未核对，代码里 `payloadAvailable` 字段如实反映 | 从宿主调用 `con.Components`，读返回 JSON 里各组件条目的 `payloadAvailable` |

「安装 → 启动」未验证与「能出安装包」不矛盾：前者是运行时结论，后者是构建期结论。构建期已经实测能出包（11.11 MiB），且 release 构建的无头自检跑通（`--selftest-common` 与 `--selftest-jobs` 均通过，见 [`PACKAGING.md`](../MFMath.Host.Rust/docs/PACKAGING.md)）；运行时的安装与启动尚未在真机走通。

真机上验证安装到启动的五步（原文见 [`PACKAGING.md`](../MFMath.Host.Rust/docs/PACKAGING.md) 的「真机上要走的验证」）：

1. 双击 `MF-Mathematics_2.0.0_x64-setup.exe`，按提示安装（每用户，不需要管理员）。
2. 打开安装目录，逐项确认：`MF-Mathematics.exe`、6 个引擎 DLL、`wwwroot\index.html`、`python\mfmath.py`、`cpp\`。
3. 启动，然后核对：`curl.exe -s http://127.0.0.1:9222/json/list` 的 URL 是 `https://mfmath.local/index.html`；`%LOCALAPPDATA%\MFMath\logs\app.log` 里有 9 个宿主对象注册行且没有 `ai`；随手算一条能出结果（证明 6 个 DLL 都在）。
4. 附着跑一遍用例：`pwsh -File tests\run-all.ps1 -NoLaunch`。
5. 卸载：程序目录清空，`%LOCALAPPDATA%\MFMath`（设置 / 日志 / 组件 / 工作区）保留。

## 兜底分发路线

NSIS 之外有一条不依赖任何工具链的 zip + 手工布局路线（见 [`PACKAGING.md`](../MFMath.Host.Rust/docs/PACKAGING.md) 的「兜底路线」）。产物目录是 `build.rs` 同步好的 `MFMath.Host.Rust\target\release`，天然等同「安装后布局」：挑出 `mfmath-host-rust.exe`（改名 `MF-Mathematics.exe`）、`*.dll`、`wwwroot/`、`python/`、`cpp/` 打成 zip。与 NSIS 的两个差异：exe 名字不同（程序不依赖自己的文件名）、没有安装 / 卸载与开始菜单项。

WebView2 Runtime 是系统依赖，不是包里带的东西：Win11 自带；Win10 老机器需装 Evergreen Runtime。宿主不负责安装它，缺失时给出可读的启动失败提示。

## 怎么推翻一条

推翻的门槛只有一条：给出证据说明它现在会害人。

| 类别 | 推翻需要什么 |
| --- | --- |
| 不实现 | 一个具体场景 + 证据（用户报障、可复现的失败），证明缺它就不能用 |
| 推迟 | 证明前置条件已满足（例如组件 payload 已上传） |
| 能力上限 | 不动门槛，这是设计选择；要改先改 [`DESIGN.md`](DESIGN.md) 与 [`DECISIONS.md`](DECISIONS.md) |
| 未验证 | 验一次就转正 |

推翻后要做两件事：把条目从本文删掉，而不是改成「已完成」；如果是「推迟 → 已做」，在对应的实现文档里记一笔。

本文的条目随代码变化时同步更新：机制落点列的符号名（函数、常量、键名、目标名）用括号内的 `Select-String` / `Get-ChildItem` 命令定位，行号不作为依据；数字（如 11.11 MiB）就近给复跑命令。数字变了就更新，不留下装饰性条目。
