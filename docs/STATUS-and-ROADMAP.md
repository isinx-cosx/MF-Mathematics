# MF-Mathematics v2.0 现状与规划报告

> 生成时间：本轮工作结束时。所有数字均为**实测**（命令见 §6），非估算。
> 配套文档：`docs/PLAN-feature-completion.md`（功能补全方案，含逐项证据与行号）。

---

## 一、结论

**现在是一个"引擎 + 前端 + 宿主同处一棵树、可直接构建运行"的干净版本**（407 个源文件 / 约 3 MB），
引擎 424 个数学函数与 2180 条准确性用例全部通过；22 个计算/绘图模式、外观系统、控制台、组件下载、
**教程系统、数学键盘、设置面板**均已可用，并经真实宿主窗口端到端验证。

**功能面只剩一个入口没做**（计算块上的「AI 加速」按钮）；剩下的是**一条工程主线的收尾**
（交付链与 Python 清零）。设置面板里**已经没有「待实现」项**，教程引导目标 31 项里 **30 已实现 / 1 待实现**。
AI 助手（含**工具调用**）、联网搜索、用户系统都已完成，见 `docs/AI-ASSISTANT.md`、
`docs/ONLINE-SEARCH.md`、`docs/ACCOUNT.md`。

**分步显示的语义已按你的决定定下**：给 AI 一个能直接调用 DLL（引擎）的工具 ——
于是每一步计算都是**一次引擎调用**，"步骤里的公式要不要验算"这个问题自然消失。
该地基（工具调用）**已落地**：`engine_find` + `engine_call`，370 个引擎函数，
越权调用被拒，轮次有上限；剩下的只是把这套记录渲染成"步骤"而不是"工具块"。

### 本轮已定的四项决策（2026）

| # | 决策 | 落地情况 |
| --- | --- | --- |
| 1 | **给 AI 加一个能直接调用 DLL 的工具** | 已落地（本文件与 `AI-ASSISTANT.md` §4.1） |
| 2 | **改密码即全端下线**（会话版本号 `token_version`） | 站点侧已落地并验证（`docs/ACCOUNT.md`；站点 `scripts/verify-client-api.mjs` 25/0） |
| 3 | **AI 额度：保持现状**（用户自带密钥，站点只记账） | 不动；账号页只显示站点侧状态 |
| 4 | **更新链：只提示 + 打开下载页 + 显示 sha256**（不自动执行安装包） | **已完成**（站点补 sha256 + 宿主 UpdateBridge + 设置→更新 + 顶栏提示）；端到端 `cdp-update.mjs` **37 / 0**；见 `docs/UPDATE-CHAIN.md` |

### 本轮之后的状态变化（相对于本报告初稿）

| 项 | 变化 |
| --- | --- |
| 设置面板 | 由"没有（顶栏弹 alert）"变为**容器式面板**：**8 个分组**（本轮新增「计算与绘图」「AI」为真实分组）、搜索可跳到具体项；外观/计算与绘图/引擎/组件/AI/存储六组已可用，搜索/更新两组为占位并写明依赖 |
| 工作区保存 / 载入（本轮） | 之前"没有"（早先的实现在安装目录里且字段残缺）。现在把**计算块 / 绘图表达式与视野 / 控制台代码**存进 `%LOCALAPPDATA%\MFMath\settings\workspace.json`，支持另存为文件、从文件打开、清空；载入后跳回保存时的页面；坏输入（版本更新、不是 JSON、缺字段）都给可读原因，不静默 |
| 导出图片（本轮） | 之前"没有"（早先菜单里有）。六个绘图页都有入口，按 `max(2, devicePixelRatio)` 重绘并铺不透明底色后交宿主写 PNG；状态行写明路径与像素尺寸 |
| 快捷键（本轮） | 之前只有局部快捷键。现在全局 F1 → 教程页、Ctrl+Z/Ctrl+Y → 计算页撤销/重做（50 步、换页清空、输入框内不抢键）；**全程不弹任何窗口**，可发现性靠页面上的「↶ 撤销 / ↷ 重做」按钮与 title |
| 两个设置项（本轮） | 之前两项都没有：**数值精度**（小数位数 0–15，默认 12）与**绘图默认范围**（四项都填才生效，留空按画布自动）；改了就生效、非法值行内说明，都不弹窗 |
| 引导目标 | 已实现 22 个、待实现 9 个（此前 20 / 11）；设置分组登记为目标后，教程里 `settings_dialog.*` 两步不再是"目标不存在" |
| 引导提示 | 新增"目标在别的页面 / 需先满足前置条件"的提示与"前往该界面"按钮，避免把"不在当前页"误报成"界面未实现" |
| 修掉的 bug | `lib/bridge.js` 的 `functionExists()` 此前**恒为 false**（把 C ABI 导出 `function_exists` 当成已注册动作去 Dispatch）；`/settings` 路由漏注册（点设置后内容区空白） |
| 回归用例 | 新增 `cdp-settings.mjs`（25 项）与 `cdp-tutorials-keypad.mjs`（37 项），均已登记进 `run-all.ps1` |
| 引擎超越方程拦截 | 由"表达式里出现 sin/cos/exp/log 就一律拒绝、且文案恒称『方程』"改为**按结构判定 + 分流**：三角方程交给专用求解器给出周期通解，根式/分段/指数含未知量给出**准确原因**再拒绝（详见下节） |

### 本轮引擎修复：超越方程拦截的误伤（`symbolic_util.h` / `symbolic_api.cpp`）

- **旧行为（代码原文）**：`has_transcendental(expr_str)` 在**打印出来的整串表达式**里做子串匹配，命中 `asin(`…`exp(`…`sqrt(`…`cbrt(`…`abs(`…`gamma(`…`erf(` 中任意一个就抛错。于是三类误伤同时发生：`sin(x)=0`（教科书三角方程）、`x^2-sin(1)`（`sin(1)` 只是常数，未知量其实在多项式里）、`sqrt(x)-2`／`abs(x)-3`／`x*sin(x)=0`（代数或乘积形式，x=4、±3、0 都是精确解）全被拦。文案主体恒为"含超越函数（整串表达式）"，既不区分根式/分段/指数，也不给替代做法；上下文前缀由各调用方自己传（`solve_sym` 传"方程"、求驻点传"驻点方程"、绘图交点传"交点方程"）——所以同一句"含超越函数"会同时出现在解方程、求驻点、求交点里，用户看不出到底哪一类、下一步能做什么。
- **新行为**：改判**结构**——未知量是否真的落在超越函数/根式/分段函数的参数里，或落在指数上——然后分流：
  - 三角方程 → 专用 `solve_trig`，返回周期通解集合（新字段 `generalSolution`）与 `note`；`solutions` 保持空数组，避免下游把它当成有限根。
  - 采纳解集前先过 `is_usable_solution`：非空 `FiniteSet` 一律可用，`ImageSet` / `Union` 只在允许无穷时可用，`ConditionSet` / `EmptySet` 一律丢弃——防止把"原式复述"当成解（此项是本轮自己发现的回归，已写进电池用例）。
  - 根式 / 分段（`abs`、`sign`、`floor`、`ceil`…）/ 指数含未知量 → 仍然拒绝，但文案点明原因，且带上原始表达式与替代做法（实测原文："方程含未知量的根式（-2 + sqrt(x)）；…请先平方（或换元）去根号后求解，再代回原方程验根" / "方程含分段函数 abs()（-3 + abs(x)），需要分区间讨论…" / "方程的未知量出现在指数上（-2 + exp(x)），属超越方程…"）。
  - `solve_sym` 对外走 `SolvePolicy::Decompose`（整式与三角因子可分解时给出**部分根 + note** 说明哪些因子未解）；`monotonicity`、`local_extrema`、`global_extrema` 等内部调用仍是 `Strict`，宁缺勿错。
- **验证**：424 个动作全量扫描 + 针对性电池无崩溃、无挂死（含此前会栈溢出的 `sin(20*x)` 写法）；准确性套件 2180 用例中 3 处失败逐条复核为**预期改进**，已就地更新用例（`cases_core.py` 两条由"期望报错"改为校验周期通解，`cases_calculus.py` 一条放宽为子串"超越"），现为 **2180 通过 / 0 失败 / 0 跳过，覆盖 424/424**。
- **界面侧同步做掉的三件事**（否则引擎算对了、用户看到的仍是"没解出来"）：结果窗把 `generalSolution` 翻成中文标签「通解」并定性为文字（集合族记法 `{2*n*pi + pi | …}` 引擎解析器不认，送去排版只会失败）；`solutions` 为空而通解存在时**收掉"解集（空）"**（两者并排显示看着像自相矛盾，原始 JSON 不变）；新增端到端回归 `tests/cdp-engine-solve.mjs`（13 项断言，已登记进 `run-all.ps1`），在真实宿主里从输入框走到结果窗，覆盖通解 / 部分解 / 拒绝文案 / 二次方程显示四类结局。
- **界面的问题（本轮遇到并记录）**：宿主读的是 `MFMath.Host\bin\Release\net10.0-windows\wwwroot`，那是 `dist` 的**拷贝**（csproj 的 `Content Include="..\MF_UI\MFMath.UI.Vue\dist\**"`）。改了前端只跑 `npm run build` 不够，必须再 `dotnet build -c Release`，否则端到端测试对着旧界面跑——本轮第二遍里"通解标签没出现、'解集（空）'还在"这 2 项失败就是这个原因。（第一遍那 8 项失败是测试脚本自己的 bug：MathLive 的 `value` setter 异步生效，紧接着派发 `input` 事件时界面读到的还是空串，于是报"请输入表达式"；两者叠加过，别把账只记在一处。）
- **仍未解决**：`exp(x)-2`、`log(x)-1` 仍被拒（通用求解器有风险、`solve_rational` 对该形式没给出非空有限解集），文案准确；要彻底修需先对 exp/log 形式做经验探测。

### 设置面板的分批状态（按依赖）

| 批次 | 分组 | 状态 |
| --- | --- | --- |
| 第一批 | 外观、引擎、组件、存储与数据 | 已完成并验证 |
| 第二批 | 搜索、历史与工作区管理 | 依赖 P1；分组已存在，项已列入并标"待实现" |
| 第三批 | AI、更新 | 依赖 P3 / P5；同上 |

---

## 二、现在有什么

### 2.1 目录结构与规模（v2.0）

| 路径 | 内容 | 规模 |
| --- | --- | --- |
| `MF_Mathematics/` | 数学库源码，**仅 C++**（`.cpp/.h/.hpp` + `CMakeLists.txt` + C++ 测试） | 251 个源文件 / 1.68 MB |
| `MF_Mathematics/build/bin/Release/` | **编译结果**：`mf_mathematics.dll` 3.23 MB + 5 个运行时依赖 DLL | 6 个文件 / 21.8 MB |
| `MFMath.Host/` | C# 桌面宿主（WPF + WebView2） | 源码 10 文件 / 1,193 行 |
| `MF_UI/MFMath.UI.Vue/` | Vue 3（**无 TS**：`src` 里 `.ts` 文件 0 个） | `src` **73 文件 / ≈16,141 行**（39 `.vue` + 32 `.js` + 1 `.css` + 1 `.json`） |
| `docs/` | 方案与留档（含 18 篇教程 YAML 原件 `tutorials-src/`） | 19 文件 |
| `tools/`（前端内） | 教程转换、构建期自检 | 2 个脚本 |
| **合计（源码，git 跟踪）** | | **396 文件 / 2.9 MB** |

磁盘占用 127 MB = 源码 2.9 MB + `node_modules` 75.5 MB（已 gitignore）+ 编译结果 21.8 MB + 宿主 `bin/obj` 26.6 MB。

### 2.2 引擎（C++）

- **已注册函数 424 个**（`signatures.json` 顶层键 424，源码 `register_function` 调用 425 处）。
- 对外仅两个 C ABI：`math_call(name, args_json, out, size)` 与 `function_exists(name)`；信封 `{isError, value}`。
- 在 v2.0 这棵树里**重新编译成功**（MSVC 19.51 / VS 18 2026），只有 1 个既有 `C4244` 警告。
- 编译产物经**准确性套件复验：2180 通过 / 0 失败 / 0 跳过，action 覆盖 424/424**（35.4 秒）。
- 依赖 Eigen 与 SymEngine（vcpkg），运行时依赖 flint/symengine/gmp/mpfr/pthread 五个 DLL。

### 2.3 前端（Vue 3，无 TS）

- **22 个模式视图全部已迁移**：`REAL_VIEWS` 9 项 + `CalcView` 13 项 = 导航全部 22 项，**没有路由还在用占位页**。
- 外观系统：10 套配色 + 形状/疏密/字体四维 + 跟随系统 + 实时预览卡（早先只有 4 套且靠按钮循环）。
- 控制台：CodeMirror 6、语法包按语言惰性加载、可选组件（CPython / MinGW）安装。
- **教程系统（本轮新增）**：18 篇 / 66 步 / 52 示例 / 42 FAQ；目录页、正文页（概述/步骤/示例表/FAQ/标记已学）、示例库、首次启动欢迎窗、引导遮罩与状态机。
- **数学键盘（本轮新增）**：126 键 / 6 分类作为基准值，键面文字与分类顺序沿用该基准；插入值全部 LaTeX 化；符号搜索、最近使用、收藏、页签与显隐记忆。

### 2.4 宿主（C#）

`mf`(引擎桥) · `win`(窗口) · `con`(控制台) · ComponentDownload（组件下载，含断点续传 + SHA-256 校验 + zip 解包）。
构建 **0 警告 0 错误**；引擎 DLL 与 5 个依赖经 csproj 相对路径自动带入输出，前端 `dist` 自动填入 `wwwroot`。

### 2.5 版本管理现状

| 仓库 | 提交数 | 跟踪文件 | 工作区 |
| --- | --- | --- | --- |
| `Multifunctional-Mathematics-v2.0`（新） | 2 | 396 | 干净 |
| `cppcshap` | 1（本轮首次纳入） | 725 | 干净 |
| `Multifunctional-Mathematics` | 有历史 | 324+ | 干净 |
| `MVS官网` | 13 | 231 | **1 处未提交**（见 §3.4 第 6 条） |

### 2.6 已通过的验证（均可复现）

| 验证 | 命令 | 结果 |
| --- | --- | --- |
| 引擎构建 | `cmake -S MF_Mathematics -B MF_Mathematics/build -G "Visual Studio 18 2026" -A x64` + `cmake --build ... --target mf_mathematics` | 成功 |
| 引擎准确性 | 施 `MF_ACC_DLL=<v2.0 的 dll>` 后跑准确性套件 | **2180 / 0 / 覆盖 424** |
| 教程与键盘自检 | `npm run check:ui` | 通过（引导目标无静默失效、126 键对齐） |
| 前端构建 | `npm run build` | 通过（prune-fonts 另删 38 个冗余字体省 0.767 MB） |
| 宿主构建 | `dotnet build MFMath.Host -c Release --no-incremental` | 0 警告 0 错误 |
| **端到端** | 启动宿主（CDP 9222）→ `node tests/cdp-tutorials-keypad.mjs` | **37 项断言全通过** |
| **端到端（解方程）** | 同上 → `node tests/cdp-engine-solve.mjs` | **13 项断言全通过**（通解 / 部分解 / 拒绝文案 / 二次方程无回归） |
| **端到端（历史 + 搜索）** | 同上 → `node tests/cdp-history-search.mjs` | **20 项断言全通过**（算一次进历史、能搜、能点回填、清空要确认、真的落盘） |
| **端到端（控制台科学包）** | 同上 → `node tests/cdp-console-sci.mjs` | **8 项断言全通过**（sympy/numpy/scipy 能 import 且能算，门面仍能调引擎；组件未装时 SKIP） |
| **端到端（推送通道）** | 同上 → `node tests/cdp-push.mjs` | **20 项断言全通过**（信封形状、控制台运行结束、组件安装进度、设置里的通道自检行） |
| **端到端（工作区）** | 同上 → `node tests/cdp-workspace.mjs` | **25 项断言全通过**（三页采集 / 落盘 / 刷新后还原 / 另存为与从文件打开 / 四类坏输入） |
| **端到端（导出图片）** | 同上 → `node tests/cdp-export-image.mjs` | **45 项断言全通过**（六个绘图页逐页导出：真 PNG、2 倍分辨率、背景不透明、失败有原因） |
| **端到端（快捷键 + 两个设置项）** | 同上 → `node tests/cdp-shortcuts-prefs.mjs` | **23 项断言全通过**（F1 跳转、Ctrl+Z/Y 真撤销重做、输入框内不抢键、精度 12→4→**0** 影响真实结果、绘图范围影响新开页面；**全程零弹窗**） |
| **端到端（表达式归一化语义）** | 同上 → `node tests/cdp-expr-normalize.mjs` | **26 项断言全通过**（界面归一化不许改字面；归一化前后交给引擎必须同值；`1/2x`@4=0.125、`πx`@2=2π） |
| **端到端（教程富文本清洗）** | 同上 → `cdp-tutorials-keypad.mjs` 的注入防护段 | **6 类注入载荷全部被清掉**（`onerror`/`onclick`/`script`/`img`/`javascript:`/`iframe`），白名单标签与属性剥离正常 |
| **端到端（联网搜索）** | 宿主需带 `--remote-debugging-port=9222` **且带 `MF_SEARCH_ENDPOINTS`** 启动 → `node tests/cdp-search.mjs`（用例自带 `tests/fake-search-server.mjs`，**不联网**） | **53 项断言全通过**：三条后端（DDG 结果页+IA 摘要 / Wolfram 需 App ID / SearXNG JSON）、缓存命中不出网 + 忽略缓存 + **换引擎不误命中**、六类异常分类（含"空结果不是错误"）、**App ID 不外泄**、`OpenUrl` 协议闸门、表达式「算这个」送去计算页、`?q=` 深链、自检五项 |
| **端到端（设置备份）** | 宿主需带 `--remote-debugging-port=9222` 启动 → `node tests/cdp-settings-io.mjs`（走宿主的自动化路径钩子，不弹原生对话框） | **32 项断言全通过**：包格式 · **凭据文件整份排除** · **像凭据的字段被剥掉并按字段名递归验证** · 导出到磁盘且磁盘上也没有凭据 · round-trip 恢复设置与外观 · 坏包一律拒绝且不部分写入 · **导入含凭据文件的包会跳过、`ai.json` 不变** · 界面两个按钮在且不再有「待实现」标签 |`r`n| **端到端（更新链）** | 宿主需带 `--remote-debugging-port=9222` 启动 → `node tests/cdp-update.mjs`（复用 `tests/fake-account-server.mjs`，`/api/version` 夹具可用 `/__setversion` 调） | **37 项断言全通过**：自检五项（含 `1.10.0 > 1.9.9`）· 自动检查默认关 · **站点更旧 → 判定 older 且顶栏不出现徽标** · 有新版 → 徽标 + 差异 + sha256/大小 + 下载入口 · **缺校验值 → 显示原因而非"已校验"** · 协议闸门与相对路径闸门（`javascript:`/`file:`/`//host`/`..` 全拒）· 点前显示"将打开：" · 检查失败只报错且**本地计算照常** |
| **更新** | 有（更新检查） | **已完成**：查版本 + **关系判定**（站点版本比本机旧时**不**提示更新，避免把用户引去下载旧安装包）+ 显示 sha256/大小 + 把下载交给浏览器（**不自动下载或执行安装包**）；端到端 `cdp-update.mjs` **37 / 0**；见 `docs/UPDATE-CHAIN.md` | — |
| **端到端（AI 助手 + 分步显示）** | 宿主需带 `--remote-debugging-port=9222` 启动 → `node tests/cdp-ai.mjs`（用例自带 `tests/fake-ai-server.mjs`，**不联网、不要真 key**） | **127 项断言全通过**：配置/密钥不外泄、**中继闸门**（绝对地址 / `//host` / `..` 全拒）、流式逐字增长、停止、**七类异常**不崩且有原因、隐私开关真的改变请求体、**AI 不得当计算源**、markdown 渲染且**注入面为零**、**工具调用**（只暴露两个工具、只走引擎、表外函数与越权调用被拒、参数校验给出签名、轮次上限、隐私闸门、界面上工具块显示的是引擎的值而非模型的措辞）、自检、非模态抽屉 |
| **离线单测（SSE 分帧）** | `node tests/unit-sse.mjs`（**不需要宿主**） | **13 项全通过**：四份录制样本在 1/2/3/5/17/64/333 字节切分下结果一致 + 规范细节（CRLF 切散/多行 data/注释/只去一个空格/末尾无空行/多字节跨 chunk） |
| **前端审查结论核实** | 见 `docs/FRONTEND-FIXES.md` | 八条**全部复核成立**，修 6 条、留 2 条（接线类）；另修 4 处同类问题；新暴露的 20 处既有缺陷登记为带原因的已知失败基线 |
| **端到端（绘图，9 个套件）** | `cdp-plot-verify` … `cdp-canvas-theme` | 全部通过（9/7/9/11/10/7/15/23/9/5 项）；**`cdp-plot-p5` 例外，见风险台账** |
| 结果模型单测 | `node tests/unit-result-model.mjs` | 30 / 0 |

---

## 三、缺什么

### 3.1 用户可感知的功能缺口

| 功能 | 参考实现 | v2.0 现状 | 影响 |
| --- | --- | --- | --- |
| **AI 助手** | 有（`MF_AI` + 对话窗） | **阶段 1 + 工具调用 + 分步显示已完成**：顶栏「AI」打开**非模态抽屉**，流式输出走推送通道；密钥只存宿主（DPAPI 密文）；默认只发表达式与结果；**AI 可以用 `engine_find`/`engine_call` 直接调引擎真算**（370 个函数、越权调用被拒、参数按动作表校验、轮次上限 4）；**「查看步骤」把引擎调用按步骤排开**（见 `docs/STEP-VIEW.md`）；端到端 `cdp-ai.mjs` **127 / 0** | — |
| **分步显示** | 名义上有（实际是一整块只读富文本） | **已完成（渲染层）**：步骤 = 这一轮 AI 调引擎的记录，每条写着函数名、参数、**引擎返回的完整值**与耗时，失败标红保留；入口两处（AI 回答上的「查看步骤」+ 计算页结果对话框）；教程目标 `step_viewer.content` 已从待实现清单删除；见 `docs/STEP-VIEW.md` | — |
| **用户系统** | 有（登录/注册/邮箱验证） | **已完成**：站点契约（Bearer + `{detail}`）早已存在，本轮补上续期端点与「记住我」，软件侧落地 `/account` 页面 + 顶栏登录态 + 宿主 `AccountBridge`（DPAPI）；**未登录/断网不影响任何计算**；端到端 `cdp-account.mjs` **52 / 0** | — |
| **在线搜索** | 有（DDG / Wolfram / 自定义） | **已完成**：抓取与解析在宿主（C#，三个后端 + 四个解析器 + 缓存），页面是路由 `/tools/search`；App ID 只存宿主（DPAPI 密文）；缓存键**含引擎**（修掉旧实现缓存键不含引擎的缺陷）；失败分类到"下一步怎么办"；端到端 `cdp-search.mjs` **53 / 0** | — |
| **设置面板** | 有 | 无（顶栏"设置"弹 alert）→ **已完成**：容器式 9 分组，**全部是真实设置、没有任何「待实现」项**（外观 / 计算与绘图 / 引擎 / 组件 / AI / 搜索 / 账号 / 更新 / 存储与数据）；最近落地的是「更新」（`UPDATE-CHAIN.md`）与「导入·导出设置」（`SETTINGS-BACKUP.md`） | — |
| **历史记录** | 有（计算历史对话框） | **已完成**（跨会话落 `%LOCALAPPDATA%\MFMath\settings\history.json`，可搜 / 可点回填 / 可清空；基础运算页的"最近计算"也统一到它） | — |
| **工作区保存** | 有（但残缺：写在安装目录、3 个字段、恢复时谎报成功） | **已完成**：计算块 / 绘图表达式与视野 / 控制台代码可存可还原，落 `%LOCALAPPDATA%\MFMath\settings\workspace.json`，支持另存为文件（宿主文件对话框）与版本校验 | — |
| **自动更新** | 有（后台检测新版本） | 无 | 中：站点 `/api/version` 缺 `sha256`，需先补字段 |
| **教程引导** | 有（但 34/66 步失效） | **已完成** | — |
| **数学键盘** | 有（但 115/126 键插 Unicode） | **已完成** | — |
| 教程进度跨设备/跨重装 | 无 | 存 localStorage（重装 Win 后 WebView2 数据目录可能丢） | 小 |

### 3.2 交付与工程缺口

| 缺口 | 说明 |
| --- | --- |
| **安装包流水线** | `scripts/installer.iss`、`build-installer.ps1`、`verify-installer.ps1`、`gen_installer_assets.py`、`dist-installer/`（216 MB）全在相邻仓库 `../Multifunctional-Mathematics/`，v2.0 无法产出安装包 |
| **独立下载器** | `MFMath.Downloader` 未纳入（按你的决定） |
| **分发脚本** | `sync-engine.ps1`（把 DLL 同步到各消费方）未纳入 v2.0 |
| **桥接回归与示例** | `MFMath.Test`（152 行 C#）、`demo_cs_mf` 未纳入 |
| **打包脚本的 Python 化** | 手册/版权/图标/截图脚本是 Python，需改 Node 或 C# |
| ~~**推送通道**~~ | **已完成**：宿主 `PushHub`（`PostWebMessageAsJson`，任意线程可调）+ JS `lib/push.js`（`onPush(topic, fn)`）；组件安装进度、控制台运行结束已在用，AI 流式输出与更新进度可以直接接 |
| ~~**文件对话框**~~ | **已完成**：`win.SaveTextFile / OpenTextFile`（工作区另存为/打开）与 `win.SaveBinaryFile`（导出图片，base64→文件） |

### 3.3 Python 清零进度

**目标：实现代码只用 C++ / C# / JS·TS。当前进度约 15%。**

| 项 | 数量 | 状态 |
| --- | --- | --- |
| 遗留 Python 文件 | **305 个 / 61,534 行** | 未处理（其中派发层已事实上被 C#/TS 直调 C ABI 取代） |
| `.pyd` 扩展 | 7 个（+ `inner_product.dll`） | 覆盖审计已完成：**15 完全覆盖 / 4 部分覆盖 / 0 未覆盖**，可弃用，但需 1 项前置修改 |
| `math_http_service.py` | 1 项 | 可整体弃用（站点零引用，已核实） |
| 准确性套件 | 28 个 `.py` / 2180 用例 | 未冻结成语言中立 JSON |
| 打包/文档脚本 | `scripts/*.py` | 未改写 |
| PyInstaller `.spec` | 3 个 | 待删除（v2.0 已不需要） |

### 3.4 技术债与已发现的隐患

1. **7 个 `.pyd` 已无法重建**：两棵树里都没有构建它们的脚本，`CMakeLists.txt` 只构建 `mf_mathematics`。其中 `interpolation_core.pyd`（2026-07-28）早于 `cubic_spline` 越界写修复（头文件 2026-10-01），**很可能仍带该 bug**。
2. **`linear_algebra/liner_product.cpp` 谎报 ABI**：其声明（按值 `std::vector<double>`、无 `extern "C"`）与 `inner_product.dll` 的实际签名 `dot_c(double*, double*, int32)` 不符，且 DLL 比它更早。删 DLL 时必须一并处理，否则后人照它重建会静默破坏 ctypes 快路径。
3. **引擎信封没有 `steps` 字段**（已核对 `api.cpp` 与全部 `*_api.cpp`）→ 见 §3.5 第 4 条。
4. **宿主与引擎版本错配风险**：历史上出现过"Release 宿主是新的、Debug 仍跑几个月前引擎"的静默降级（`sync-engine.ps1` 就是为它写的）。更新机制必须把二者当**同一原子单元**。
5. **推送通道缺失**：见 §3.2。
6. **`MVS官网` 有 1 处未提交改动**：`docs/MVS-Studio-图标设计说明.md` 被改写（168 增 / 243 删，**不是换行符差异**）。这不是本轮改动，需要你确认是否保留。
7. **AI 提示词的硬约束冲突**（详见 §3.5 第 4 条）：早先的分步提示词明确要求模型"自己完成计算，而不是解释已有的结果"。

### 3.5 待你拍板的六项（方案已写入 `PLAN-feature-completion.md` §0.4）

| # | 决策 | 为什么卡住 |
| --- | --- | --- |
| 1 | 控制台的 **Python 语言支持**是否保留 | 那是给用户写程序的可选运行时组件，不是我们的实现代码。保留与否影响"只用 C++/C#/JS·TS"的边界认定 |
| 2 | 是否允许 **Node 作为构建工具** | 打包/手册/截图需要一个脚本层。用 Node 最省事，要求纯 C# 也可行但更慢 |
| 3 | Inno Setup 的 `.iss` / CMake 的 `CMakeLists.txt` 是否算例外 | 它们是第三方工具的声明式配置。若要求严格，安装包可改 WiX/MSIX |
| 4 | **AI 分步的语义 + 步骤来源**（最要紧） | ① 早先的提示词让模型自己算，与"计算用 C++"直接冲突；② 早先的"本地步骤"由 **84 个 Python 文件 / 约 600 处**产出，**属于要被清零的那一层**，而引擎信封没有 `steps` 字段 → Python 清零后本地步骤会整体消失。三条路：引擎为高频 action 补步骤输出 / 纯 AI / 混合（推荐） |
| 5 | 是否给 AI / 云功能加**登录门禁** | 既有实现完全没有门禁（`balance`/`is_active` 只做显示）；若加，需站点侧按 `balance` 扣减，目前后端没有这个语义 |
| 6 | **配额制**（免费 5 次步骤 / 3 次加速）是否保留 | 保留的话云服务要能对账（现状是纯本地计数 + 有 API Key 就绕过） |

---

## 四、怎么补

按依赖关系排序。**P0 是一切地基**（AI 流式、更新进度、组件进度都吃推送通道）。

### P0 — 地基（3–4 天）

1. **推送通道** `PushChannel.cs`：`CoreWebView2.WebMessageReceived`（JS→C#）+ `PostWebMessageAsJson`（C#→JS）；统一事件信封 `{v,ch,id,seq,done,payload}`；AI 回包按 ~40ms 或 ~64 字符合并投递；无宿主时降级为空实现（与既有 `console/bridge.js` 风格一致）。
2. **引擎补 `iterations`**：把 `numerical_api.cpp:288-291 / 298-301 / 308-311` 里已算出却被丢弃的 `it` 写进返回对象，输出改为 `{x, iterations}` —— 这是弃用 `.pyd` 的**唯一前置修改**。
3. **准确性套件语言中立化**：趁 Python 还在，把期望值与容差冻结成 `tests/fixtures/accuracy_cases.json`，runner 改写为 C++（ctest 目标）。
4. **按 A/B/C 档删除 `.pyd`**（A 档 6 个可立即删；C 档必须同时处理 `liner_product.cpp`）。

**验收**：2180 用例在 C++ runner 下全绿；A 档删除后 v2.0 仍正常构建。

### P1 — 设置 / 历史 / 搜索 / 工作区（约 4 天）

- `StoreBridge.cs`：历史与工作区落 `%LOCALAPPDATA%\MFMath\*.json`（带 `version` 字段；解析失败**报错并保留原文件**，不覆盖）；顺带接管教程进度，使它能读此前的 `tutorial_progress.json`（**当前缺口**，§3.1 末行）。
- `SearchBridge.cs`：三种后端（DDG / Wolfram / 自定义），放 C# 是因为 UI 跑在 `https://mfmath.local` 虚拟主机下、直连会撞 CORS 且 `appid` 不该进渲染进程；修正旧实现缺陷：缓存键加入 engine、加 TTL。
- `SettingsPanel.vue` + `HistoryPanel.vue` + `SearchPanel.vue`，把顶栏两个死按钮接上。

**验收**：三个入口全部可用；工作区跨重启保留且恢复失败会报错。

### P2 — 用户系统（**已完成**；站点侧只加了续期端点，约 2.5 天）

复用站点现成端点（**不需要写后端**）：`/api/login`（form-urlencoded）、`/api/register`、`/api/send-code`、`/api/verify-code`、`/api/me`、`/api/logout`、`/api/login-history`。
`AccountBridge.cs` + 令牌 DPAPI 加密持久化 + 启动静默校验 + 401 自动登出。
**注意同一批 POST 里编码不统一**：`/login`、`/verify-code` 是 form，其余是 JSON。

**验收**：与站点联调通过；离线不崩。

### P3 — AI 助手 + 分步显示（AI 阶段 1 **已完成**；分步 2–3 天，**依赖 §3.5 第 4 条决策**）

- ~~`AiBridge.cs`：配置对齐 `MF_AI/config.yaml`；密钥 DPAPI；流式经推送通道。~~
  **已完成**，但有三处**有意偏离**该计划：① 不复用 `sys.StoreWrite` 写密钥——那样密钥必须先
  出现在渲染进程里，与"密钥不进渲染进程"冲突，改成宿主自己读写 `ai.json`；
  ② 不做 `model_map` 角色名与 provider 注册表（12 项收敛成 10 项）；
  ③ **协议层改用 TS**（`src/lib/ai/{types,sse,client,collect}.ts`，移植自 `MVS Agent` 的
  `src/model/`），宿主缩成"带密钥发请求 + 转发原始字节"（`AiRelay.cs`）。
  理由：SSE 分帧与分片语义只该有一份实现 —— 两边各写一套的后果正是"界面和刷新后显示不同的东西"；
  顺带让分帧这类纯逻辑能脱离宿主做离线单测（`tests/unit-sse.mjs`）。
  中继只接受相对路径（绝对地址 / `//host` / `..` 一律拒绝），否则它就是"把密钥发到任意地址"的原语。
- **硬约束设计**：引擎先算 → AI 只解释 → **每一步的式子回引擎核验**（`compare_expr` / `expr_eval`），
  核验不过的标黄；结果区**永远**显示引擎值。阶段 1 已把"结果区不被 AI 改写"写成断言；
  核验机制随阶段 2 的分步一起做。
- 提示词改写：已删掉"你需要自己完成计算"，改为"结论以引擎值为准"（`lib/ai/bridge.js` 的 SYSTEM_PROMPT）。
- 分步面板（待做）：可折叠步骤列表 + 逐步播放（早先是一整块只读富文本，无列表无折叠无播放）。

**验收（阶段 1）**：`cdp-ai.mjs` 52 / 0；七种异常（断网/无密钥/密钥错/超时/取消/5xx/流中断）
不崩且有明确原因 —— 已达成（另加"坏 SSE"与"无 usage"两种降级）。

### P4 — 教程补完（约 2 天）

教程主体已完成。剩余：
- 把 11 个"待实现"步骤（`src/lib/tutorial/targets.js` 的 `PENDING`）在对应界面做出来后逐个删掉 —— P1/P3 完成后大部分会自动变为可用。
- 教程正文里的相对定位文案（"主工具栏"等）与新 UI 布局对齐（本轮只把 `data-tour` 目标接对，文案未逐句重写）。

### P5 — 自动更新（约 4 天）

1. 站点侧给 `/api/version` 补 `size` / `sha256` / `min_supported` / `mandatory`（**现在没有 `sha256`，无法安全更新**）。
2. `UpdateBridge.cs` + `MFMath.Updater.exe`：后台检查（延迟 10s、不阻塞启动）、断点续传（复用 `ComponentDownload.cs` 的 Range + SHA-256 逻辑）、**宿主与引擎 DLL 作为同一原子单元**替换。

**验收**：篡改 `sha256` 必须拒绝安装。

### P6 — 交付链去 Python（约 4 天）

`tools/build.mjs`（编排 cmake → vite → dotnet → ISCC）替代三个 `.ps1`；`capture_all/take_screenshots/reshoot/snap_all` 用已有的 43 个 CDP 脚本统一为 `tools/shots.mjs`；手册与版权页用 Node 或 C# 重写；删除 3 个 PyInstaller `.spec`。
**验收**：空机器一条命令产出安装包。

**合计约 5–6 周**（一人含自测）。风险集中在 P0（`.pyd` 删除）与 P3（核验回环+提示词改写）。

---

## 五、未来规划

### 近期（1–2 周）：把"能自证"的地基打牢

1. P0 推送通道 + 引擎 `iterations` + 准确性套件 C++ 化 → **拿到一条不依赖 Python 的验证链**。
2. 删除 A 档 `.pyd`，把外部 Python 后端明确标记为"仅历史参考"。
3. 把 v2.0 的回归套件（现有 43 个 CDP + 新增教程键盘用例）跑成一条命令，作为后续所有改动的守门。

### 中期（1 个月）：把用户可感知的缺口补齐

4. P1（设置/历史/搜索/工作区）+ P2（用户系统）→ 顶栏两个死按钮消失，桌面端具备账号能力。
5. P3（AI + 分步）→ 接通"查看步骤"，并把"引擎先算、AI 只解释"落成机制而不是约定。
6. **关键里程碑：Python 清零完成**（打包脚本改写 + 准确性套件迁移 + `.pyd` 全删 + `math_http_service.py` 弃用）。

### 长期（季度）

7. **P5 自动更新 + P6 安装包**：形成"改代码 → 一条命令出安装包 → 站点发布 → 客户端自更新"的闭环；更新把宿主与引擎绑成一个版本单元，消除"新旧引擎混用"这类静默降级。
8. 跨平台：引擎是 CMake + 标准 C++（Eigen/SymEngine/flint 均有 Linux 版本），具备迁到 Linux/CI 的条件；届时准确性套件可以在 CI 上自动跑（现在是手工跑）。
9. 语法/交互深化：把既有的 `math_guard` 复杂度守卫从**字符串启发式**下沉到引擎的 **AST** 判定（正则对 `\frac`、隐式乘法、多行输入会误判），并补 `complexity_report` / `suggest_actions` 这类以引擎解析器为基础的能力。
10. 产品化：教程内容与 UI 的关系反转（现在教程的 `target` 是硬编码的界面名，将来可考虑由 UI 声明"可引导点"，让教程只写业务语言）。

### 明确不做 / 推迟

- **不重建后端**：用户系统、组件清单、版本检测全部复用站点端点。
- **不重写下载能力**：直接复用 `ComponentDownload.cs`。
- **不复用已废弃的 HTTP 层**：`math_http_service.py` 与那套 `{code,data.result,msg}` 生成客户端（契约冲突，且 v2.0 走 P/Invoke）。
- **不移植死代码**：`MF_AI/agent.py`（含 Python `eval()`，绝不可照搬到 JS 的 `eval`）、`strategy.recommend` 等。
- **不照抄既有实现的引导层与外层壳**：教程遮罩、步骤展示、工作区保存均已重做；旧 JS UI（`MFMath.UI`）仅作历史回退目标。
- 推迟：更新回滚、AI 多模态、教程录制回放、离线文档全文搜索。

---

## 六、风险台账

| 风险 | 现状 | 对策 |
| --- | --- | --- |
| **AI 越权计算**（唯一能直接违反硬约束的点） | 早先的实现就是这么做的 | 引擎先算 + 步骤回核验 + 一条 CDP 断言"结果区恒等于引擎值" |
| **静默失效**（34/66 步失效、`.pyd` 陈旧、引擎版本错配都是这一类） | 已发现 3 类 | 构建期自检（`check-ui.mjs`）+ 更新按原子单元校验 + `.pyd` 删除前先补返回值 |
| `.pyd` 删除后 Python 层失效 | `numerical_integration.py` 的 5 个算法**无纯 Python 回退** | 必须与"整体退役外部 Python 层"同步进行，不能单独删 |
| 准确性套件冻结后无法自主扩展 | 未开始 | 保留预言机源码与原始输出，新用例离线重生成 |
| 教程进度存在本地 | 已实现 localStorage | P1 的 `store` 桥迁到 `%APPDATA%`，届时可读旧进度 |
| 站点仓库有未提交的内容改写 | 见 §3.4 第 6 条 | 需要你确认是否保留 |
| **`cdp-plot-p5` 会把页面挂住** | 跑到"极坐标网格切换 / 网格显示开关"时页面不再响应（`Runtime.evaluate` 20s 超时），此后同一宿主会话里**后面的用例全部"无 RESULT 行"**。已确认与本轮改动无关：改用 HEAD 版 `PlotView.vue` 重建后复现同样的 2 通过 / 10 失败 | 修它之前，成套跑先排除这一项，或让每个用例独占一个宿主进程 |
| **编译结果不入 git 是刻意的** | `.gitignore` 第 7–10 行写明理由：DLL 可由源码完整重建，每版 21.8 MB 二进制会让历史膨胀；DLL 留在磁盘上，所以直接拷这份文件夹仍能运行 | 换机器/新克隆要"开箱即用"时，需先 `cmake --build`，或另建发布目录只跟踪发行版 DLL |

---

## 附录 A：本轮新增/修改的关键文件

| 文件 | 作用 |
| --- | --- |
| `MF_UI/MFMath.UI.Vue/tools/build-tutorials.mjs` | 18 篇 YAML → JSON，内置权威数量表（18/66/52/42）逐项自检 |
| `MF_UI/MFMath.UI.Vue/tools/check-ui.mjs` | 构建期自检：引导目标无静默失效、键盘 126 键与分类对齐 |
| `src/lib/tutorial/{store,targets,tour}.js` | 进度存储 / 目标定位与待实现清单 / 引导状态机 |
| `src/components/tutorial/{TourOverlay,WelcomeDialog,ExampleLibrary}.vue` | 引导遮罩 / 欢迎窗 / 示例库 |
| `src/views/tutorial/{TutorialCatalogView,HelpArticleView}.vue` | 教程目录 / 正文 |
| `src/lib/math/{keypadSymbols,activeField}.js` | 126 键定义（LaTeX 化）/ 插入目标判定 |
| `src/components/math/{MathKeypad,MathField}.vue` | 键盘面板 / 输入框（登记为可插入目标） |
| `src/lib/workspace/pendingInput.js` | 跨路由把示例表达式送进目标界面（含完整 mode→路由映射） |
| `tests/cdp-tutorials-keypad.mjs` | 真实宿主内 37 项端到端断言，已登记进 `tests/run-all.ps1` |
| `tests/cdp-engine-solve.mjs` | 真实宿主内 13 项解方程端到端断言（通解带中文标签、部分解带说明、根式拒绝文案准确、二次方程无回归），同样登记进 `run-all.ps1` |
| `src/lib/engine/resultModel.js` | 新增 `generalSolution` 的中文标签「通解」，并把它归入"按文字显示"的元信息字段（引擎解析器不认集合族记法） |
| `src/components/calc/ResultDialog.vue` | 显示层删减：`solutions` 为空且存在 `generalSolution` 时不显示"解集（空）"（原始 JSON 不变） |
| `MF_Mathematics/symbolic_util.h` | 超越判定由"字符串包含"改为**结构判定**；新增 `SolvePolicy::{Strict,Decompose}`、`is_usable_solution`、`decompose_factors`、`transcendental_heads` 等，并为每类拒绝配准确文案 |
| `MF_Mathematics/symbolic_api.cpp` | `solve_sym` 走 `Decompose` 策略并输出 `generalSolution` / `note`；`exact_roots` 允许回传非有限解集 |
| `../Multifunctional-Mathematics/MF_Mathematics/tests/accuracy/cases_core.py`、`cases_calculus.py` | 3 条用例随行为改进同步更新；准确性套件位于相邻仓库 `../Multifunctional-Mathematics/MF_Mathematics/tests/accuracy/`（28 个 `.py` + `report.json`，2180 条用例 / 覆盖 424 个 action），跑法 `python run_accuracy.py`，所用 DLL 可由环境变量 `MF_ACC_DLL` 覆盖 |

## 附录 B：复现验证的三条命令

```powershell
$V2 = "C:\Users\fsafsafsa\Desktop\MVS知识库\Multifunctional系列\Multifunctional-Mathematics-v2.0"

# 1) 引擎：构建 + 准确性（2180 / 覆盖 424）
cmake -S "$V2\MF_Mathematics" -B "$V2\MF_Mathematics\build" -G "Visual Studio 18 2026" -A x64
cmake --build "$V2\MF_Mathematics\build" --config Release --target mf_mathematics

# 2) 前端：自检 + 构建
npm run check:ui --prefix "$V2\MF_UI\MFMath.UI.Vue"
npm run build    --prefix "$V2\MF_UI\MFMath.UI.Vue"

# 3) 宿主 + 端到端（教程系统与数学键盘 37 项、解方程 13 项断言）
dotnet build "$V2\MFMath.Host\MFMath.Host.csproj" -c Release --no-incremental
$env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = "--remote-debugging-port=9222"
Start-Process "$V2\MFMath.Host\bin\Release\net10.0-windows\MFMath.exe"
node "$V2\MF_UI\MFMath.UI.Vue\tests\cdp-tutorials-keypad.mjs"
node "$V2\MF_UI\MFMath.UI.Vue\tests\cdp-engine-solve.mjs"
```

> **改了前端就必须重跑 `dotnet build -c Release`**：宿主把界面固定映射到
> `MFMath.Host\bin\Release\net10.0-windows\wwwroot`，那是个**拷贝**（csproj 的
> `Content Include=..\MF_UI\MFMath.UI.Vue\dist\**`）。只跑 `npm run build` 的话，
> 界面改动不会进宿主，端到端测试会对着旧界面跑——本轮就在这里白跑了一轮。
