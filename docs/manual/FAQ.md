# 常见问题（FAQ）

> **本文只回答一个问题：常见问题。**
>
> 与同层其它文档的分工：
> - [README.md](README.md) —— 为谁做、能做什么、**不能做什么**（本份只回答"为什么"与"东西在哪"）；
> - [FEATURES.md](FEATURES.md) —— 功能全表（14 学科视图、绘图、工具、AI、学习、系统）；
> - [WORKFLOWS.md](WORKFLOWS.md) —— 典型用法（算题、画图、AI 步骤、控制台、导出与工作区）；
> - [INSTALL.md](INSTALL.md) —— 安装与构建（⚠ 受"安装 → 启动"真机验证未走完的阻塞）；
> - [TROUBLESHOOTING.md](TROUBLESHOOTING.md) —— 已经坏了怎么查（卡死、字体、组件下载、账号/更新、日志）。

**本文口径**：写于 **2026-10-07 11:05（+08:00）**。文中数字只有两类——**本次用命令跑出来的**（命令抄在节内）
与**引自既有文档的**（标了 `文件:行` 或小节）。**本份文档没有运行宿主**，所以"界面上会怎样"这类结论
一律来自源码或既有文档，不来自我自己的端到端实测。

复跑本文所用命令的前置条件：引擎产物已存在（`MF_Mathematics/build/bin/Release/probe_call.exe`；
它是 `README.md`「三步构建」第 1 步的产物，仓库不含编译产物）。本文所有 `probe_call` 命令的工作目录是仓库根。

## 1. 为什么有些积分算不出来（`∫xˣ dx`、`∫sin(x)/x dx`、`∫e^{−x²}dx`）？

**因为这三个原函数确实不是初等函数，软件如实返回"未实现"，而不是硬凑一个式子。**
这是刻意的设计选择，不是缺陷：一个错误的原函数比"未实现"危险得多 —— 用户看到"未实现"会换条路，
看到一个错的闭式解就会拿它去算别的东西（[../DESIGN.md](../DESIGN.md) §2 ②，`:52-53`）。

本次实测（三个都返回同一个形状）：

```powershell
& MF_Mathematics\build\bin\Release\probe_call.exe integrate '{"expr":"x^x","var":"x"}'
# {"isError":false,"value":"未实现"}
& MF_Mathematics\build\bin\Release\probe_call.exe integrate '{"expr":"sin(x)/x","var":"x"}'   # 同上
& MF_Mathematics\build\bin\Release\probe_call.exe integrate '{"expr":"e^(-x^2)","var":"x"}'   # 同上
& MF_Mathematics\build\bin\Release\probe_call.exe integrate '{"expr":"cos(x)^3","var":"x"}'
# {"isError":false,"value":"(-1/3)*sin(x)**3 + sin(x) + C"}   ← 初等函数照样算得出来
```

能力边界的完整清单（含"推翻它的门槛"）在 [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) §3（`:63-73`）；
纪律本身在 [../../README.md](../../README.md)「三条纪律」①（`:29-31`）。**这是设计选择，改它等于改设计**，
不是"补个功能"（`DESIGN-BOUNDARIES.md:115`）。

## 2. "未实现"和"报错"有什么区别？我看到一条报错，是坏了吗？

**"未实现"不是错误，是答案**：它走的信封是 `isError:false`（见上一节实测），展示层把它当结果渲染；
而引擎遇到**非法输入**才用 `isError:true`。同一台引擎上两条对照（本次实测）：

```powershell
& MF_Mathematics\build\bin\Release\probe_call.exe fundamental_group '{"space":"NoSuchSpace"}'
# {"isError":true,"value":"不认识的拓扑空间「NoSuchSpace」。可用写法：S1/S2/S3…（球面）、T2（环面）…"}
& MF_Mathematics\build\bin\Release\probe_call.exe fundamental_group '{"space":"circle"}'
# {"isError":false,"value":"Z"}
```

**报错要分类**，三类不能混着看（[../ui/ENGINE-BINDING.md](../ui/ENGINE-BINDING.md) §2.1，`:86-95`）：

| 你看到的 | 分类 | 该找谁 |
| --- | --- | --- |
| `{isError:true,value:"未实现…"}` | **不是缺陷**，能力边界 | 不用找，换条路（§1） |
| 界面显示"未检测到引擎桥"（`engineCall` 返回 `null`） | **环境没准备好**（没跑在宿主里） | 用宿主启动，别用浏览器预览（`bridge.js:128-129`） |
| `"mf 没有这个方法：X"` | 版本不匹配（宿主比前端旧） | 重装/重编宿主（`handlers.rs:349`） |
| `"对象缺少键: z"` / `"参数 n 类型错误"` | **产品缺陷**：前端声明的 args 与引擎实际读的键不符 | 登记进 [../../MF_UI/BUGS.md](../../MF_UI/BUGS.md)（同类历史见 B1） |

口径的第三条纪律要求"失败要分类"（[../../AGENTS.md](../../AGENTS.md) §5 第 3 条）。

## 3. 为什么前端不自己算？界面里明明有数字。

**因为"结论"只能有一个来源。** 前端只做三件事 —— 参数构造、传输、展示；一切数值/符号结果都来自
`mf_mathematics.dll`（[../DESIGN.md](../DESIGN.md) §2 ①，`:26-39`；
[../ui/ENGINE-BINDING.md](../ui/ENGINE-BINDING.md) §1，`:20-27`）。
如果前端也能算，同一个问题就会有两个来源，两者不一致时**用户没有办法判断哪个对** —— v1 的失败正是
这个形状（Python 后端 + 旧 JS UI 两处实现，[../../README.md](../../README.md)「与 v1 的关系」）。

这条不是自觉，是有用例顶着的：端到端里有一条硬约束 —— 假端点故意回 `1+1=3`，
断言结果区**不得**被它改写（[../ui/AI.md](../ui/AI.md) §8「红线用例」，`:224-237`）。
边界也要说清：前端确实会决定"在哪些点问引擎"（采样横坐标）、把数值格式化成显示文本，
但它**不改数值、不产生新数值**（`ENGINE-BINDING.md` §1.2，`:40-51`）。

## 4. AI 会不会算错？它到底算不算数？

**AI 不承担计算：它只能调引擎。** 系统提示里写死"所有计算由 C++ 引擎完成，你只做解释"，
它手上**只有两个工具**（`engine_find` 找函数、`engine_call` 调函数），且只能走引擎桥，
碰不到 `win`/`sys`/`con`（[../ui/AI.md](../ui/AI.md) §8，`:212-215`）；
"查看步骤"里显示的**不是模型编的步骤**，而是这一轮 `engine_call` 的调用记录（`AI.md` §9，`:243-245`）。

**要如实说的部分**：界面保证的是"结果区仍是引擎的值"，**不保证模型正文里的每一句话都对** ——
红线用例只断言那条错的等式出现在 AI 回复里、而结果区没有被改写（[../ui/AI.md](../ui/AI.md) §8，`:230-233`）。
所以：**要数值就看计算块与步骤视图里的引擎结果，别抄对话正文里的数字。**

## 5. 为什么有的模式下拉里写着"（未接入引擎）"？

**那个模式不在 `ENGINE_MAP` 里**，也就是前端没有它的函数映射，所以算不了
（[../ui/ENGINE-BINDING.md](../ui/ENGINE-BINDING.md) §2.1，`:95`）。
这种"引擎里有、页面选不到"的中间态**不许静默**：构建期自检要求每个模式要么能在某个页面选到、
要么显式登记进 `NOT_EXPOSED` 并写明原因，**反向**还要报"过时条目"（[../DECISIONS.md](../DECISIONS.md) D-012，`:176-188`）。

现状：`NOT_EXPOSED` **已为空**、取不到的模式为 0（[../ui/ENGINE-BINDING.md](../ui/ENGINE-BINDING.md) §5.1，`:190-197`）；
另有 24 个**旧名字**重复登记，它们的功能由同一 `fn` 的页面模式提供（同节 `:199-204`）。
所以看到"（未接入引擎）"多半是旧版本的下拉快照，请以本机 `npm run check:ui --prefix MF_UI/MFMath.UI.Vue` 的输出为准。

## 6. 断网还能用吗？

**能，但有边界**：断网后**本地计算、绘图、教程、控制台全部照常**；只有**联网搜索 / 账号 / AI** 需要网络
（[../../README.md](../../README.md)「离线承诺」，`:58`；[../DESIGN.md](../DESIGN.md) §2 ⑤，`:88-92`）。
这条是可验收的：端到端用例对着**假端点**跑，不依赖真网络（`DESIGN.md:91-92`）。
**准确说法**：离线不影响"算"，只影响"取外部东西"。

## 7. 哪些功能必须联网？还有哪些地方是"半成品"？

| 功能 | 联网 | 现状与出处 |
| --- | --- | --- |
| 本地计算 / 绘图 / 教程 / 控制台 | 不需要 | `README.md:58` |
| 联网搜索（Wolfram 等） | 需要 | 抓取与解析在宿主（[../link/FEATURES.md](../link/FEATURES.md)） |
| AI 助手 | 需要 | 页面直连用户自己配的端点（[../DECISIONS.md](../DECISIONS.md) D-004，`:71-84`） |
| 账号（登录 / 记住我 / 静默续期） | 需要 | ⚠ **线上未部署**：`POST /api/token/refresh → 404`，「记住我」在线上不生效（[../OPEN-ITEMS.md](../OPEN-ITEMS.md) §1，`:34-42`） |
| 更新检查 | 需要 | 只提示 + 显示 sha256 + 把下载交给浏览器（`README.md:56`） |
| 控制台的 sympy / numpy / scipy 组件 | 需要下载 | ⚠ 两个 zip **尚未上传**，清单如实标 `available:false`（[../OPEN-ITEMS.md](../OPEN-ITEMS.md) §4，`:119`） |

另外一条环境发现（2026-10，**不是本项目代码的问题**）：本机 .NET 侧到生产站点的 TLS 建立失败
（`The SSL connection could not be established`），Node 侧正常；它影响的是账号/更新对着线上
（[../OPEN-ITEMS.md](../OPEN-ITEMS.md) §1，`:54-58`）。**注意它描述的是已废弃的 .NET 宿主**
（[../DECISIONS.md](../DECISIONS.md) D-006），但在 Rust 侧对着线上验过一次之前不许划掉
（[../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) §5 尾注，`:101-103`）。

## 8. 为什么崩溃不上报？出了问题你们怎么知道？

**这是隐私上的默认，不是没做。** 崩溃与前端未捕获异常**只写本地**（`%LOCALAPPDATA%\MFMath\logs\`），
只有用户主动「设置 → 存储与数据 → 导出诊断包」才会交出去；理由写在决定里 ——"数学工具的用户不该因为
一次崩溃被上传任何东西"（[../DECISIONS.md](../DECISIONS.md) D-008，`:131-140`；
[../DESIGN.md](../DESIGN.md) §2 ⑤，`:94-97`）。

**代价是写明的**：作者**看不见**线上崩溃分布，只能等你报；每次排障都要引导你导日志
（`DECISIONS.md:137`）。所以：遇到崩溃，请导一次诊断包（[TROUBLESHOOTING.md](TROUBLESHOOTING.md)）。

## 9. 崩溃日志和诊断包在哪？里面有什么？

| 项 | 事实 | 出处 |
| --- | --- | --- |
| 目录 | `%LOCALAPPDATA%\MFMath\logs`（一定可写） | [../link/CREDENTIALS.md](../link/CREDENTIALS.md) §4（`:148-154`） |
| 常规日志 | `app.log`，单文件上限 **2 MB**，轮转成 `app.1.log` | 同上 |
| 崩溃日志 | `crash-*.log`：环境 + 异常 + **`app.log` 尾部 200 行**；只留最近 **20** 个 | 同上 |
| 诊断包 | `ExportDiagnostics` 写到 `dataDir\diagnostics-<stamp>.txt` | [../ui/SETTINGS-WORKSPACE.md](../ui/SETTINGS-WORKSPACE.md) §3.1（`:93`） |
| ⚠ 会带出去的东西 | **三份凭据文件被跳过**，另有"文件名含 `secret`"的兜底；但 **`ai-chat.json` 不在跳过名单里** —— 它会连同会话原文整份进诊断包 | `SETTINGS-WORKSPACE.md` §4.5（`:195-196`） |

**发给别人之前先看一眼**：诊断包里有你自己的聊天原文（上表最后一行）。
导出/诊断剥密钥的两道闸门见 [../link/CREDENTIALS.md](../link/CREDENTIALS.md) §2.2（`:89-102`）。

## 10. 我的 API Key、登录 token 存在哪？安不安全？

**同一份设置目录里，两种截然不同的待遇**（[../link/CREDENTIALS.md](../link/CREDENTIALS.md) §0，`:17-21`）：

| 数据 | 形式 | 页面能看到什么 |
| --- | --- | --- |
| 账号 token | **DPAPI 密文**（base64 blob） | 只有 `hasToken` 这类布尔 |
| 搜索 Wolfram App ID | **DPAPI 密文** | 只有 `hasWolframKey` 布尔 |
| **AI 的 API Key** | **明文** | **明文本身** |

DPAPI 那两条有三条纪律：**只在当前用户下可解**、**禁止弹 UI**、**失败绝不降级成明文落盘**
（失败时只留在内存并如实告诉你"本次会话有效、重启后需重填"）
（`CREDENTIALS.md` §1，`:31-36`；复核命令在 §5，`:162-173`）。
**准确的说法**：一般凭据受 Windows 用户级加密保护，**AI 那把钥匙是刻意的例外**，见下一问。

## 11. AI 的 Key 为什么是明文？安全吗？

**因为 2026-10-07 决定"AI 归 TS"：页面直连、SSE 流式，密钥明文存 `ai.json`**（[../DECISIONS.md](../DECISIONS.md) D-004，`:71-84`）。
代价**如实写在案**（[../link/CREDENTIALS.md](../link/CREDENTIALS.md) §2.1，`:65-74`）：
密钥明文落盘（换用户、拷贝文件、看备份都能读到）、**密钥常驻渲染进程内存**（不只是录入那一瞬）、
旧版 DPAPI 密文在页面侧**解不开**（现在如实提示"请在设置里重填一次"，且 `hasKey=false`，不假装还有密钥）。

还有一条**待修的残留**：`StoreWrite` 覆盖前会把旧文件复制成 `<name>.json.bak`，
而 `StoreDelete` **只删 `.json`、不删 `.bak`** —— 于是 `ai.json.bak` 里可能留着明文密钥，
界面上看不到（`StoreList` 只列 `.json`）、诊断包也不会带它
（`CREDENTIALS.md` §2.3，`:104-125`）。**`StoreDelete` ≠ 抹除**：要真正抹掉得手工删 `<name>.json.bak`。
导出 / 导入 / 诊断三道剥离的实现与判据见 `CREDENTIALS.md` §2.2 与 §5。

## 12. 换了宿主（.NET ↔ Rust）我的密钥要重填吗？

**只有 AI 这一项要重填，其余配置不用动。** `search.json` / `account.json` / `update.json` / 窗口 / 工作区 / 历史
**能跟着走**（字段同名、格式相同，Rust 侧还给每个字段加了 PascalCase `alias`）；
`ai.json` 的密钥**不能**：C# 写的是 `apiKeyProtected`（DPAPI 密文），Rust/TS 读的是 `apiKey`（明文），
两种形式互不通用（[../link/CREDENTIALS.md](../link/CREDENTIALS.md) §3，`:136-141`）。
这是架构变更的直接后果，**不是 bug**。另外现役宿主只有 Rust 那份，C# 宿主已废弃
（[../DECISIONS.md](../DECISIONS.md) D-006，`:102-116`）。

## 13. 能不能商用？代码能拿去改吗？

**不能 —— 仓库没有 LICENSE，依默认版权规则"保留所有权利"。** 未经作者许可**不得复制、修改或分发**，
这条**包括公司内评估**（[../DECISIONS.md](../DECISIONS.md) D-011，`:167-174`；
[../../README.md](../../README.md)「已知边界」最后一条，`:239-241`）。
**这是有意的，不是忘了加**：作者保留后续授权方式的选择权（`DECISIONS.md:171`）。
需要以其它方式使用，请联系作者（`README.md:241`）。注意它在公开平台上，**但公开 ≠ 开源**。

## 14. 支持哪些系统？

| 项 | 事实 | 出处 |
| --- | --- | --- |
| 操作系统 | **Windows 10 / 11（x64）** | [../../README.md](../../README.md) `:21` |
| 运行时 | WebView2 Runtime（Win11 自带；Win10 需安装） | `README.md:107` |
| 宿主 | Rust/Tauri + WebView2（`MFMath.Host.Rust/`，9 个宿主对象） | `README.md:21`、[../../MFMath.Host.Rust/README.md](../../MFMath.Host.Rust/README.md) `:19` |
| 构建需要 | CMake ≥ 3.16 + VS C++ 工具链 + vcpkg（引擎）；Node ≥ 18（前端）；Rust（宿主） | `README.md:103-107` |

**未证实**：非 Windows 平台。Tauri 本身是跨平台框架，但本仓库**没有任何非 Windows 的构建或验证记录**。
怎么验：在目标平台上跑通 `README.md` 的三步构建并执行
[../../MFMath.Host.Rust/docs/ACCEPTANCE.md](../../MFMath.Host.Rust/docs/ACCEPTANCE.md) 的自检 —— 没跑过之前不对外承诺。

## 15. 能装吗？安装包验证到哪一步了？

**能出安装包，但"装完能不能跑"还没验过 —— 所以不能照着说"装完就能用"。**
Rust 宿主用 `tauri build --bundles nsis` 可以产出 NSIS 安装包（实测 **11.11 MiB**，
引自 [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) §5 `:95` 与
[../../MFMath.Host.Rust/docs/PACKAGING.md](../../MFMath.Host.Rust/docs/PACKAGING.md) §3，**本份文档未复核**），
但安装后的布局、安装/卸载、从安装目录启动**都尚未在真机上验证**；原因是本机 `Start-Process`
起不了安装器（`ERROR_CANCELLED`，manifest 是 `asInvoker` 所以不是 UAC）（`DESIGN-BOUNDARIES.md:95`）。
另外仓库当前 `tauri.conf.json:29` 的 `bundle.active` 是 `false` —— 与"`--bundles nsis` 能出包"之间
是否互相影响，**本次未核实**（怎么验：真机跑一次打包）。
**目前唯一被实测跑通的路径仍是源码构建三步**（`README.md:233-234`），展开见 [INSTALL.md](INSTALL.md)。

## 16. 我的数据（设置、历史、工作区、日志）到底存在哪？

**根是 `%LOCALAPPDATA%\MFMath`**，设置文件在它下面的 `settings\`：
`settingsDir = dataDir/settings`、`dataDir = %LOCALAPPDATA%\MFMath`
（[../ui/SETTINGS-WORKSPACE.md](../ui/SETTINGS-WORKSPACE.md) §3.1，`:95`；`sys.rs:31-36`、`logging.rs:29-36`）。
同目录还有 `logs/`、`components/`、WebView2 用户数据目录，并且**与已废弃的 C# 宿主共用这一份**
（[../../MFMath.Host.Rust/README.md](../../MFMath.Host.Rust/README.md) `:170`）。

| 内容 | 落在哪 | 出处 |
| --- | --- | --- |
| 外观 / 界面语言 | **`localStorage`**（`mf_theme` / `mf.lang` 等），不是设置文件 | `SETTINGS-WORKSPACE.md` §3.2（`:105`） |
| 计算与绘图偏好 | `settings\prefs.json` | 同上（`:107`） |
| AI 配置 / 会话 | `settings\ai.json`（明文 Key）+ `settings\ai-chat.json` | 同上（`:110`） |
| 搜索 / 账号 / 更新 | `settings\search.json` / `account.json` / `update.json` | 同上（`:111-113`） |
| 历史 / 工作区 | `settings\history.json`（上限 200 条）、`settings\workspace.json` | 同上（`:116`、§5.5 `:283`） |
| 日志 / 崩溃 / 诊断包 | `logs\`、`logs\crash-*.log`、`diagnostics-<stamp>.txt` | [../link/CREDENTIALS.md](../link/CREDENTIALS.md) §4 |

## 17. 怎么把配置迁到另一台机器？

**走「设置 → 存储与数据 → 导入 / 导出设置」**（实现在 `lib/settings/io.js`，
契约见 [../ui/SETTINGS-WORKSPACE.md](../ui/SETTINGS-WORKSPACE.md) §4，`:125-182`）：

| 你要知道的 | 事实 | 出处 |
| --- | --- | --- |
| 凭据**不进**导出包 | `ai` / `account` / `search` **整份排除**，名字写进包里的 `excluded`；其余文件再按字段名剥一遍并记进 `stripped` | `SETTINGS-WORKSPACE.md` §4.1（`:152-157`） |
| 导入**不会清掉**你现有的凭据 | `applyBundle` 永远不写这三份文件，并再查一遍 | §4.2（`:168`） |
| 坏包**整包拒绝** | `app`/`kind`/`version` 任一不对，在写第一个文件之前就返回 | §4.2（`:169`） |
| **AI 密钥要重填** | 凭据不进包（本表第 1 行）+ 两个宿主格式不通用（见 §11、§12） | [../link/CREDENTIALS.md](../link/CREDENTIALS.md) §3 |
| 工作区是**另一个**文件 | 「工作区 → 另存为文件」产出 `workspace.mfws.json` | `SETTINGS-WORKSPACE.md` §5.5（`:285`） |

⚠ **工作区的「载入」不是自动发生的**：`loadFromApp()` 全仓库只有一个调用点 —— 设置面板那一行的「载入」按钮，
所以刷新或重启之后要**显式点一次**（`SETTINGS-WORKSPACE.md` §5.5，`:289-292`）。

### 17.1 导入设置后为什么必须重启？

**因为设置文件与外观偏好都是启动时读取的，界面如实说要重启，而不是假装即时生效。**
`applyBundle()` 的返回值里 `needsRestart: true` 是**写死的**，理由记在同处
（[../ui/SETTINGS-WORKSPACE.md](../ui/SETTINGS-WORKSPACE.md) §4.3，`:178-182`）；界面也明说，
用例还断言了这条文案（同节 `:182`）。**未证实**：不重启是否"完全不生效" —— 怎么验：导入一个含
`mf_theme` 的包 → 不刷新页面看 `document.documentElement.dataset.theme`，再刷新对比
（`SETTINGS-WORKSPACE.md` §8 第 3 条，`:370`）。

## 18. 为什么有时候算得很慢？

**慢有两类，先分清**：一类是**算法本身没优化完**，另一类是**输入规模本来就大**。
第二类里最坏的一种（"用户给的一个整数直接当循环上界/分配尺寸"）已经改成**按上限明确拒绝并解释原因**，
所以现在多数病态输入是"快速报错"而不是"卡住界面"（[../HANG-OPTIMIZATION.md](../HANG-OPTIMIZATION.md) §1.3，`:83-90`）。

**仍会慢的清单以那份文档为准 —— 本文不复制它的数字**（复制就会有两份真相）：
[../HANG-OPTIMIZATION.md](../HANG-OPTIMIZATION.md) §4（`:163-170`），逐条验证记录在
[../hang-fix-verification.md](../hang-fix-verification.md)；能力边界一栏只给指针
（[../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) §4，`:77-85`）。
重活会走后台通道并把进度写进状态栏（[../ui/ENGINE-BINDING.md](../ui/ENGINE-BINDING.md) §6，`:226-247`）。

## 19. 算太久能取消吗？取消了是真停了吗？

**能"停止等待"，但引擎不会被叫停 —— 那一步会算完。**
引擎**没有取消钩子**，宿主只能"停止等待并丢弃结果"，所以文案必须是"**已取消等待**"，不能写"已停止"
（[../ui/ENGINE-BINDING.md](../ui/ENGINE-BINDING.md) §6.2，`:283`；
[../link/JOBS-PUSH.md](../link/JOBS-PUSH.md)）。
异步通道还有两条如实设计：宿主**没有** `DispatchJob` 时会自动退回同步调用（前端不因宿主版本旧就不好用），
轮询间隔 `POLL_MS = 120`（同节 `:278-282`）。

## 20. 同一个功能为什么有时弹参数窗口、有时不弹？

**判据只有一条：这个模式在 `ENGINE_VAR_SPECS` 里有没有登记参数表** ——
`needsVarDialog(mode)` 就是一次 `hasOwnProperty` 检查
（`calcArgs.js:450-452`，见 [../ui/ENGINE-BINDING.md](../ui/ENGINE-BINDING.md) §2 ③' `:78`）。

本次实测（工作目录 `MF_UI/MFMath.UI.Vue`）：

```powershell
node --input-type=module -e "const m=await import('./src/lib/engine/engineMap.js');const vs=m.ENGINE_VAR_SPECS;console.log('VAR_SPECS',Object.keys(vs).length);const b={};for(const [k,s] of Object.entries(m.ENGINE_MAP))(b[s.fn]??=[]).push(k);const x=Object.entries(b).filter(([f,ms])=>ms.length>1&&ms.some(k=>vs[k])&&ms.some(k=>!vs[k]));console.log('混合',x.length);for(const [f,ms] of x.slice(0,8))console.log(' ',f,ms.map(k=>k+(vs[k]?'[弹]':'[不弹]')).join(' / '));"
# VAR_SPECS 139 / 混合 21
#   global_extrema 全局最值[不弹] / 最值[弹]        （输出节选；命令会列 8 组）
#   series_sum     级数求和[不弹] / 数列求和[弹] / 无穷级数求和[弹]
```

**所以"同一个功能"其实常常是同一个 `fn` 下的两个不同模式**：一个有参数表（先弹窗收参数）、
一个没有（直接在输入框里算）。另外两条相关规矩：字段标签里带「（输入框）」的表示该参数由输入框提供，
弹窗不重复收（`calcArgs.js:45-50`、`:314-334`）；输入框里已经用 `;` 填过的参数，弹窗字段会**同步跳过**
（[../ui/ENGINE-BINDING.md](../ui/ENGINE-BINDING.md) §3，`:121`）。

## 21. 输入框里的分号 `;` 是干什么的？

**它是"参数分段符"：深度 0 的 `;` 把输入切成多段，一次把多个参数喂进去**
（`splitSegments`，[../ui/ENGINE-BINDING.md](../ui/ENGINE-BINDING.md) §3 `:101-103`）。
分段的分配顺序是写死的六步（第一段给"必填的 `string`"、`string_array` 类整串吃掉剩余段、
其余必填按声明顺序逐段吃……），见同节 `:105-112`；例：`x^2-4; -2; 2`。

**一个已知的坑**：`;` 在**概率表**里是表项分隔符 —— 两种语义会撞车，所以 `prob_table`
必须整串 `join` 回去（`calcArgs.js:279-291`；[../../MF_UI/BUGS.md](../../MF_UI/BUGS.md) B2①）。
**缺必填参数时不会兜底**：界面直接拒绝调引擎并说清缺什么，而不是静默填 `0`/`[0,0]`/`[]`
（`ENGINE-BINDING.md` §3.1，`:126-136`）。

## 22. 界面语言为什么只翻了一部分？

**因为多语言是"逐步扩大"的，不是"没做"**：导航、顶栏与**全部 14 个学科视图**
（含 415 个模式名与 184 个参数弹窗字段）已中英双语，可在「设置 → 外观 → 界面语言」切换并记忆；
**页面正文**（设置面板各行、工具/绘图/帮助页、`lib/` 里的提示文案、教程正文）仍是中文
（[../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) §3，`:72`；[../../README.md](../../README.md) `:235-238`）。

**迁移路径是明确的**：把要翻的那处包一层 `t()` → 往 `src/lib/i18n/en-*.js` 补译文 →
`npm run check` 会拦住漏译（`DESIGN-BOUNDARIES.md:72`）。
顺带一条同族事实：**UI 语言与"AI 用什么语言回答"是两件事**，AI 的回答语言由它自己决定（同节 `:73`）。

## 23. v1 的 Python 后端去哪了？还能跑 v1 吗？

**v1 作为应用已经不可运行、也不再维护**：它的计算全靠那套 Python 后端，而 v2 把计算全部搬进
`mf_mathematics.dll`（[../../README.md](../../README.md)「与 v1 的关系」，`:251-259`）。
因此 v1 的 Python 后端 **277 个 `.py` + 8 个二进制**（`.pyd` / `inner_product.dll`）**已删除**，
删前归档在 `Multifunctional系列/_archive/v1-python-backend-*.zip`（[../OPEN-ITEMS.md](../OPEN-ITEMS.md) §4，`:120`）。

**唯一有意保留的是测试资产**：`MF_Mathematics/tests/accuracy/` 的 28 个 `.py`（2180 条准确性用例），
它可对**任意**引擎 DLL 运行（环境变量 `MF_ACC_DLL`），所以没跟着清掉（`README.md:261-263`）。
不移植 v1 死代码的理由（`MF_AI/agent.py` 含 Python `eval()`）见
[../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) §1 第 4 条（`:36`）。

## 附：本文用到的复跑命令（一次抄全）

工作目录：仓库根（`integrate` / `list_functions` 等），或 `MF_UI/MFMath.UI.Vue`（前端那几条）。

```powershell
# ① 引擎注册表守门：期望 count = 424（本次实测）
& MF_Mathematics\build\bin\Release\probe_call.exe list_functions '{}'

# ② 未实现 vs 算得出来（本文 §1）
& MF_Mathematics\build\bin\Release\probe_call.exe integrate '{"expr":"x^x","var":"x"}'
& MF_Mathematics\build\bin\Release\probe_call.exe integrate '{"expr":"cos(x)^3","var":"x"}'

# ③ 未识别空间名报错（本文 §2）
& MF_Mathematics\build\bin\Release\probe_call.exe fundamental_group '{"space":"NoSuchSpace"}'
& MF_Mathematics\build\bin\Release\probe_call.exe fundamental_group '{"space":"circle"}'

# ④ 参数弹窗表规模与"同一 fn 混合"（本文 §20）—— 在 MF_UI/MFMath.UI.Vue 下
node --input-type=module -e "const m=await import('./src/lib/engine/engineMap.js'); console.log('VAR_SPECS', Object.keys(m.ENGINE_VAR_SPECS).length);"

# ⑤ 凭据边界复查（判据：DPAPI 调用点只应出现在 account.rs / search.rs / selftest.rs；出现 ai.rs 即回退）
Select-String -Path MFMath.Host.Rust\src\*.rs -Pattern 'dpapi::(protect|unprotect)'
Select-String -Path MF_UI\MFMath.UI.Vue\src\lib\settings\io.js -Pattern 'CREDENTIAL_FILES|SECRET_FIELD'

# ⑥ 模式可达性 / 参数弹窗契约（本文 §5、§20）—— 在 MF_UI/MFMath.UI.Vue 下
npm run check:ui
npm run check:signatures
```

## 已知的文档债

> 规矩照 [../../AGENTS.md](../../AGENTS.md) §5 与 [../DESIGN.md](../DESIGN.md) §2 ③：**以代码为准**。
> 以下都是本次（2026-10-07）读代码 / 读文档时发现的**不一致**，我只登记，**没有改任何文件**。

| # | 位置 | 它说 | 代码/实测是 | 怎么核 |
| --- | --- | --- | --- | --- |
| 1 | `src/lib/ai/engine-signatures.json` 的 `integrate` 项 | `required: ["expr","a","b"]`（`integrate_complex` / `integrate_double` / `integrate_triple` 的边界键同理） | 源码里 `a`/`b` 是**"给不给"决定定积分还是不定积分**的开关，不是必填：`calculus_api.cpp:94-99`（只给 `expr` 就走不定积分，本次实测返回 `未实现`）；`engineMap.js` 的「定积分」模式也把 `a`/`b` 标成 `opt:true` | `node tools/engine-signatures.mjs --check --verbose`（本次 exit 0，把这两条归入"提示：表里的「a」未能在源码里刮到"）；再对照 `& probe_call.exe integrate '{"expr":"x^x","var":"x"}'` |
| 1b | 上一条的**下游后果**（同一处债，未在运行时验证） | — | `tools.ts:81-90` 用签名表的 `optional` 决定 `opt`，合并 `ENGINE_MAP` 时**只补"表里没有的键"**（`:105-111`），所以 AI 工具表与工具箱里 `a`/`b` 仍显示为必填；`validateArgs`（`:155-172`）会因此判"缺少必填参数" | 起宿主后让 AI 调 `engine_call` 传 `integrate {"expr":"x^x"}`，看是否被 `validateArgs` 拒（**未验证**） |
| 2 | [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) `:34` 与 [../OPEN-ITEMS.md](../OPEN-ITEMS.md) `:137` | "复用既有的组件下载实现"、"不重写下载能力（复用 `ComponentDownload.cs`）" | `MFMath.Host/ComponentDownload.cs` **确实存在**，但那是**已废弃**的 .NET 宿主（[../../AGENTS.md](../../AGENTS.md) §2）；现役实现在 `MFMath.Host.Rust/src/console.rs`（见 [../ui/SETTINGS-WORKSPACE.md](../ui/SETTINGS-WORKSPACE.md) §3.2 `:109`） | `Get-ChildItem MFMath.Host -Recurse -Filter ComponentDownload.cs`；`Get-ChildItem MFMath.Host.Rust/src -Filter console.rs` |
| 3 | [../../MFMath.Host.Rust/README.md](../../MFMath.Host.Rust/README.md) `:3` 与 `:46`、`:63` | 文首写"链接层 10 个宿主对象已落地 **7 个**"；下文又写"已实现（10 个宿主对象**全部落地**）"，表格里 `ai` 仍是 ✅ | 同一文件 `:19` 自己写的是"**9 个宿主对象**（`ai` 归 TS）"；[../DECISIONS.md](../DECISIONS.md) D-004（`:74-75`）记着宿主对象 **10 → 9**、`ai` 桥被拆除 | 同文件三处行号对照 + D-004；宿主侧登记表是 `MFMath.Host.Rust/src/main.rs` 的 `MF_SPEC`/`SYS_SPEC` |
| 4 | [../README.md](../README.md) `:8`（文档地图台账） | "计划档位：标准（35 份）· 已落地 **11 份**"，层 2 / 层 3 多份仍标 🚧 | 2026-10-07 11:05 本机实测：`docs/engine/*.md`（9 份）、`docs/ui/*.md`（9 份）、`docs/link/*.md`（6 份）**都已在树中** | `Get-ChildItem docs -Recurse -Filter *.md \| Select-Object -ExpandProperty FullName` |

**本文只核对了与它自己结论相关的部分**：`docs/` 里指向已废弃 .NET 实现的那批（`ACCOUNT.md`、`ONLINE-SEARCH.md`、
`AI-ASSISTANT.md`、`UPDATE-CHAIN.md`、`SETTINGS-BACKUP.md`、`MIGRATION-GAPS.md`、`STATUS-and-ROADMAP.md`）
是**已登记的**文档债（[../PROJECT-BOARD.md](../PROJECT-BOARD.md) §3 **R7**），本文不重复登记 ——
重复就是两份真相（[../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) §4 `:85` 用的是同一条规矩）。
