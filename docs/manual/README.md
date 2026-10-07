# MF-Mathematics v2.0：这是什么、给谁用、能做什么、不能做什么

> **本文只回答一个问题：这是什么软件、给谁用、能做什么、不能做什么。**
>
> 与同层其它文档的分工：
> - [FEATURES.md](FEATURES.md) —— 功能全表（14 个学科视图 / 415 个界面模式 / 绘图 / 工具 / AI / 学习 / 系统），逐项落到模式名与页面；
> - [WORKFLOWS.md](WORKFLOWS.md) —— 典型用法：算一道题、画一张图、让 AI 出步骤、用控制台、导出与工作区；
> - [INSTALL.md](INSTALL.md) —— 构建与安装现状（含「Rust 宿主的『安装 → 启动』尚未真机验证」这条硬边界）；
> - [TROUBLESHOOTING.md](TROUBLESHOOTING.md) —— 卡死、字体、组件下载、账号/更新、日志与诊断包；
> - [FAQ.md](FAQ.md) —— 常见误解（为什么算不出来、离线承诺、为什么不上报崩溃、许可证）。

**核对时间**：2026-10-07 11:05–11:09（+08:00），本机 HEAD `6353eef`。
凡写「本机实测」的，都是这次真跑过的命令（命令抄在 §13）；其余一律给 `文件:行` 或另一份文档的小节。
**没验过的一律写「未证实」并给验法**，不替它背书。

---

## 1. 一句话

**MF-Mathematics v2.0 是一个 Windows 桌面数学工作台**：14 个学科的计算视图 + 6 类绘图 + 控制台 + 联网搜索 + AI 助手 + 交互式教程，计算全部由同一个本地 C++ 引擎给出。

| 项 | 值 | 出处 |
| --- | --- | --- |
| 名称 / 版本 | `MF-Mathematics` / `2.0.0` | `MFMath.Host.Rust/tauri.conf.json:3-4`、`Cargo.toml`（`version = "2.0.0"`） |
| 平台 | Windows 10/11（x64）；宿主用 WebView2（Win11 自带，Win10 需安装） | [README.md](../../README.md):21、`:107` |
| 形态 | 单目录树三层：C++ 引擎 + Rust/Tauri 宿主 + Vue 前端（内嵌 React 绘图组） | [README.md](../../README.md):4、`:64-82` |
| 是否联网 | 本地自包含、可离线运行 | [README.md](../../README.md):4；准确口径见本文 §10 |
| 仓库里有什么 | **版本控制里只有源码，不含编译产物/安装包**（`build/`、`dist/`、`bin/`、`obj/` 都在 `.gitignore`） | [README.md](../../README.md):94；本机实测（`Get-ChildItem -Force` 根目录）除 `docs/`、`MF_Mathematics/`、`MF_UI/`、`MFMath.Host/`、`MFMath.Host.Rust/`、`tools/` 外只有 3 个文件（`.gitignore`、`AGENTS.md`、`README.md`）。⚠ 本机磁盘上 `MF_Mathematics/build/` 是存在的——那是本地构建产物，不是仓库内容（§13 的 `probe_call.exe` 就在里面） |
| 引擎函数 | **424 个已注册 action** | 本机实测：`& MF_Mathematics\build\bin\Release\probe_call.exe list_functions` → `"count":424`；[README.md](../../README.md):154 |

**它不是一个"替你做作业"的东西**，而是一个"结果只有一个来源、算不出来就如实说算不出来"的计算工具。
这句话不是口号：三条纪律在代码里有对应机制与可复跑的判据（[README.md](../../README.md):25-43、[../DESIGN.md](../DESIGN.md) §2）。

| 纪律 | 在软件里的可见表现 | 出处 |
| --- | --- | --- |
| ① 不编造结果 | 非初等不定积分返回字面量 `未实现`；不认识的拓扑空间名报错，不给占位串 | [../engine/BOUNDARIES.md](../engine/BOUNDARIES.md) §1.1、§1.5 |
| ② AI 不承担计算 | AI 只能经 `engine_call` 取引擎结果，端到端有一条专门守它的用例 | `tests/cdp-ai.mjs:8`、`:696` |
| ③ 每个修复留下"为什么"和"怎么证明" | 每条积分规则配**求导自证**（对结果求导再与原式数值比对） | [../engine/BOUNDARIES.md](../engine/BOUNDARIES.md):56 |

---

## 2. 给谁用

| 你是 | 从哪开始 | 别拿它干什么 |
| --- | --- | --- |
| **使用者**（拿它算题、画图、看步骤） | 本文 → [WORKFLOWS.md](WORKFLOWS.md) → [FEATURES.md](FEATURES.md)；出问题 [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | 别把「未实现」当成软件坏了 —— 见 §11 |
| **评估者**（判断它到底能干多少） | 本文 §4–§11 → [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md)（能做什么/不能做什么，并写明推翻门槛）→ [../HANG-OPTIMIZATION.md](../HANG-OPTIMIZATION.md) §4（已知慢的地方） | 别把「尚未验证」当成「没有」，也别当成「有」—— 见 §12 |
| **要装/要构建的人** | [INSTALL.md](INSTALL.md)；宿主侧判据 [ACCEPTANCE.md](../../MFMath.Host.Rust/docs/ACCEPTANCE.md)、打包 [PACKAGING.md](../../MFMath.Host.Rust/docs/PACKAGING.md) | ⚠ 别照 [README.md](../../README.md):109-137 那三步直接跑：那一节写的宿主是**已废弃的 .NET 宿主**（[README.md](../../README.md):11-13 自己声明了） |
| **改代码的人** | [AGENTS.md](../../AGENTS.md)（谁能改哪些文件）→ [../DESIGN.md](../DESIGN.md) → [../PROJECT-BOARD.md](../PROJECT-BOARD.md) | 本文件是用户向入口，不含改代码的规矩 |
| **想知道还缺什么** | [../OPEN-ITEMS.md](../OPEN-ITEMS.md)（功能缺口）、[BUGS.md](../../MF_UI/BUGS.md)（确有证据的缺陷） | 状态类文档每天在变，引用必须看时间戳（[../README.md](../README.md) §0） |

> 📌 本文是**手册**（只在架构真改了才动），不是状态类文档。版本、函数个数、用例个数都会变；
> 每次引用请用 §13 的命令复跑一遍。

---

## 3. 三层结构，以及每层的边界

```
Vue 3 壳（MF_UI/MFMath.UI.Vue）── 内嵌 ──▶ React 绘图组（MF_UI/MFMath.UI.React）
        │ hostObjects.sync.mf.Dispatch(name, json)      ← 唯一的上行入口
        ▼
Rust/Tauri 宿主（MFMath.Host.Rust）  窗口 / 桥 / 凭据 / HTTP / 组件下载
        │ C ABI：function_exists、math_call（**恰好两个导出**）
        ▼
C++17 引擎（MF_Mathematics）  424 个 action；SymEngine + flint + gmp + mpfr + Eigen
```

| 层 | 路径 | 职责 | 出处 |
| --- | --- | --- | --- |
| 引擎 | `MF_Mathematics/` | 全部数学实现；110 个 `.cpp`（本机实测：`Get-ChildItem MF_Mathematics -Recurse -Filter *.cpp` 排除 `build/`、`tests/` 得 110；[README.md](../../README.md):180 同值） | [README.md](../../README.md):76-81 |
| 宿主 | `MFMath.Host.Rust/` | 窗口、桥、凭据、HTTP 抓取、组件下载；**9 个宿主对象 / 84 个方法** | [../link/OBJECTS.md](../link/OBJECTS.md):15-28（权威源 `src/main.rs:67-216`） |
| 前端 | `MF_UI/MFMath.UI.Vue/`（Vue 壳） + `MF_UI/MFMath.UI.React/`（绘图组，被 Vue 内嵌） | 界面、路由、工作区、教程、AI 面板、函数工具箱 | [../ui/README.md](../ui/README.md):24-36、`:63-76` |
| 桥 | `window.chrome.webview.hostObjects.sync.mf.Dispatch(name, json)` | 页面 → 宿主 → 引擎的唯一通路 | [README.md](../../README.md):69；接缝契约 [../link/README.md](../link/README.md) §2 |

**两条必须知道的边界**：

1. **前端一行数学都不算**（[README.md](../../README.md):84、[../DECISIONS.md](../DECISIONS.md):49 D-002）。
   所以"结果"只有一个来源，也才谈得上可复现；界面只做参数构造、展示与编排。
2. **C#/.NET 宿主 `MFMath.Host/` 已废弃**（[README.md](../../README.md):6、[../DECISIONS.md](../DECISIONS.md):102 D-006、[AGENTS.md](../../AGENTS.md) §2）。
   磁盘上还在，但只作迁移参考；`docs/` 里少数老文档仍把它写成现役实现，那是**已登记的文档债**（[../PROJECT-BOARD.md](../PROJECT-BOARD.md) §3 R7）。见到「C# 宿主也是现役」的说法就是过时。

---

## 4. 能做什么：14 个学科视图

本机实测：「计算模式」组共 **15** 个导航项 = `基础运算` + **14 个学科视图**（`nav.js:21-39`；计数命令见 §13）。
14 个学科与 [README.md](../../README.md):51 的列举一致：

| # | 视图 | 路由 | # | 视图 | 路由 |
| --- | --- | --- | --- | --- | --- |
| 1 | 代数计算 | `/calc/algebra` | 8 | 数论 | `/calc/number-theory` |
| 2 | 微积分 | `/calc/calculus` | 9 | 实分析 | `/calc/real-analysis` |
| 3 | 解析几何 | `/calc/analytic-geometry` | 10 | 泛函分析 | `/calc/functional-analysis` |
| 4 | 数列 | `/calc/sequences` | 11 | 复分析 | `/calc/complex-analysis` |
| 5 | 线性代数 | `/calc/linear-algebra` | 12 | 代数拓扑 | `/calc/algebraic-topology` |
| 6 | 概率论与数理统计 | `/calc/probability` | 13 | 测度论 | `/calc/measure-theory` |
| 7 | 数值分析 | `/calc/numerical` | 14 | 调和分析 | `/calc/harmonic-analysis` |

> 上表按 `nav.js:21-39` 的顺序抄写（顺序与 v1 对齐，`nav.js:17-20` 记了理由），
> 编号是本文为方便引用加的；第 15 个导航项 `基础运算`（`/calc/basic`）是通用计算器，不计入 14 个学科。

**三个数字，别混**：

| 数字 | 含义 | 出处 |
| --- | --- | --- |
| **424** | 引擎注册表里的 action 总数（构建守门值） | 本机实测 `probe_call.exe list_functions` → `count: 424` |
| **415** | 界面模式表 `ENGINE_MAP ∪ EXTRA_MAP` 的模式名数 | 本机实测 `node tools/check-ui.mjs` → `映射 415 个 / 页面并集 391 个 / 取不到 0 个` |
| **53** | 有引擎实现、但**不在**任何 `ENGINE_MAP` 条目里的 action 数 | [../engine/BOUNDARIES.md](../engine/BOUNDARIES.md) §2.4（含复跑脚本） |

那 53 个里大部分是内部/绘图通路，但也夹着看着像用户能力的（`integrate_complex`、`taylor_series`、`is_harmonic`、`matrix_multiply` …）——
**它们不是没入口**：函数工具箱以 `engine-signatures.json` 为唯一数据源，把全部 424 个 action 列出来并能直接调用
（`src/views/tools/ToolboxView.vue:3,10-11,22,46`；[../engine/BOUNDARIES.md](../engine/BOUNDARIES.md):199）。

---

## 5. 能做什么：绘图

**界面有 7 个绘图入口**（本机实测：`nav.js` 里 `/plot/*` 共 7 条，`:48-56`）；
**React 侧只有 6 个绘图页组件**（`PlotPage`、`Plot3DPage`、`PlotComplexPage`、`PlotVectorPage`、`PlotGeometryPage`、`PlotFractalPage`），
因为 `/plot/2d` 与 `/plot/polar` **共用 `PlotPage`**，靠 `gridMode` 区分（[../ui/README.md](../ui/README.md):63-76）。

| 入口 | 路由 | 组件 | 出处 |
| --- | --- | --- | --- |
| 2D 函数绘图（含隐函数/参数方程） | `/plot/2d` | `PlotPage` | `nav.js:49`；[../ui/README.md](../ui/README.md):65 |
| 极坐标 | `/plot/polar` | `PlotPage`（`gridMode`） | `nav.js:50`；[../ui/README.md](../ui/README.md):66 |
| 3D 曲面 | `/plot/3d` | `Plot3DPage` | `nav.js:51` |
| 复平面 | `/plot/complex` | `PlotComplexPage` | `nav.js:52` |
| 向量场 | `/plot/vector` | `PlotVectorPage` | `nav.js:53` |
| 自由几何 | `/plot/geometry` | `PlotGeometryPage` | `nav.js:54` |
| 分形 | `/plot/fractal` | `PlotFractalPage` | `nav.js:55` |

- [README.md](../../README.md):52 说的「**6 类**绘图」是把极坐标算在 2D 函数那一类里，与上表 7 个入口**不矛盾**，只是数法不同（本文把两种数法都写出来，免得读者以为有一个是错的）。
- **导出**：绘图页可以把画布导出成 PNG（`src/lib/plot/exportImage.js:96`；6 个 React 绘图页各自调用，如 `PlotPage.tsx:415`）。
- **工作区**：绘图页的操作可以按路由存进工作区（[../ui/README.md](../ui/README.md):91）。
  ⚠ 其中 5 个绘图页（3D/复平面/向量场/几何/分形）的工作区往返**尚未跑出数字**（[../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md):96）。
- Vue 侧旧绘图页（`src/views/plot/` 6 个文件）**被有意冻结成回退资产**，不在构建图与路由里；守卫会拦下任何 import（本机实测 `check-ui.mjs` → `冻结的 Vue 绘图组：6/6 个文件在位，被 import 0 处`；[../DECISIONS.md](../DECISIONS.md):86 D-005）。

---

## 6. 能做什么：工具（搜索 / 控制台 / 函数工具箱）

| 工具 | 能做什么 | 需要什么 | 出处 |
| --- | --- | --- | --- |
| **联网搜索** | 三个后端：`duckduckgo`（默认，免密钥）、`wolfram`（需 App ID）、`custom`（SearXNG 形状）；结果可复制、可送进计算页 | **要网络**；Wolfram 要密钥 | `nav.js:64`；`src/views/tools/SearchView.vue:5,95`；[../link/FEATURES.md](../link/FEATURES.md) §1.1、`:18-24` |
| **控制台** | 写 Python 或 C++ 跑一段程序，并调用**同一个引擎** | **要网络装可选组件**（CPython / MinGW），装好后可离线用 | `nav.js:65`；[../link/FEATURES.md](../link/FEATURES.md) §5.1、§5.4 |
| **函数工具箱** | 列出并直接调用**全部 424 个**引擎 action | 无（本地） | `nav.js:66-73`；`ToolboxView.vue:3,10-11,22,46` |

- 搜索**只解析引擎给的摘要**：不做翻页、不抓网页正文、不做请求去重/限流 —— 这是**明确的边界**，不是待办（[../link/FEATURES.md](../link/FEATURES.md):79-81、[../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md):38）。
- 控制台的语言只有 `python` 与 `cpp` 两种，且**非 `cpp` 一律当 Python**（含拼错的名字，这是照旧保留的行为：[../link/FEATURES.md](../link/FEATURES.md):358）。
- ⚠ 控制台的组件包**目前下载不到**：站点侧两个 zip（python / mingw）尚未上传，清单里如实标 `available:false`（[../OPEN-ITEMS.md](../OPEN-ITEMS.md):119）；
  宿主侧的组件清单是**编译进代码的常量**、期望 SHA-256 也是内置常量（[../link/FEATURES.md](../link/FEATURES.md):359-361）。
  本机**是否已有缓存好的包，未证实**（缓存优先的查找顺序见 [../link/FEATURES.md](../link/FEATURES.md):367）。

---

## 7. 能做什么：AI 助手

| 项 | 事实 | 出处 |
| --- | --- | --- |
| 形态 | 助手抽屉（右侧一条，主界面仍可操作）+ 步骤推导视图 | [README.md](../../README.md):54；[../STEP-VIEW.md](../STEP-VIEW.md) |
| 走哪条路 | **页面直连**模型端点，不经过宿主；宿主里**没有** `ai` 对象 | [../DECISIONS.md](../DECISIONS.md):71 D-004；[../link/OBJECTS.md](../link/OBJECTS.md):30-32 |
| 能不能自己算 | **不能**。它的工具只有 `engine_find` 与 `engine_call`；数值/符号结果一律取自引擎 | `tests/cdp-ai.mjs:411`、`:409`；[README.md](../../README.md):33 |
| 可调范围 | 引擎注册表的全部 424 个 action（工具目录由签名表生成） | [README.md](../../README.md):33；`tests/cdp-ai.mjs:409` |
| 接口设置 | 可配 API Base / 模型 / `max_tokens`、`temperature`、超时等 | `src/lib/settings/catalog.js:66-76` |
| 默认发什么 | 默认只发**表达式与结果**；隐私说明是设置里的一行 | `catalog.js:72` |
| 密钥怎么存 | **明文**写在 `ai.json`（唯一"降级"过的凭据；账号 token 与搜索 App ID 是 DPAPI 密文） | [../link/CREDENTIALS.md](../link/CREDENTIALS.md):17-23 |
| 需要网络吗 | **需要**（这是三个联网功能之一） | [README.md](../../README.md):58 |
| UI 语言 vs 回答语言 | 是两件事：AI 用什么语言回答由它自己决定 | [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md):73 |

---

## 8. 能做什么：学习（教程 / 示例 / 键盘）

本机实测（读生成的运行期数据 `src/tutorials/tutorials.json`，命令见 §13）：

| 项 | 数字 | 怎么来的 |
| --- | --- | --- |
| 交互式教程 | **18 篇** | `tutorials.json` 的 `tutorials` 数组；YAML 原件留档 `docs/tutorials-src/*.yaml` 也是 18 个；权威数量表在 `tools/build-tutorials.mjs:41-60` |
| 教程步骤 | **66 步** | 同上（各篇 `steps` 求和） |
| 教程分类 | **6 类**（入门/计算/绘图/AI/工具/设置） | `tutorials.json` 的 `categories` |
| 示例任务库 | **52 条**（来自教程的 `examples` 字段，**没有独立数据源**） | 同上；`ExampleLibrary.vue:5,38-40` |
| 教程 FAQ | **42 条** | `tutorials.json` 的 `faq` |
| 教程高亮目标控件 | 引用 **30 个**（已实现 30、待实现 0） | 本机实测 `node tools/check-ui.mjs` →「教程引用的 target：30 个（已实现 30，待实现 0）」 |
| 数学键盘 | **6 分类 / 126 键** | 本机实测 `node --input-type=module -e "…keypadSymbols.js"` → `KEY_COUNT 126`、`CATEGORIES 6`；`V1_KEY_COUNT = 126`（`keypadSymbols.js:146`）与 v1 对齐 |

**为什么"教程目标控件"要专门守**：v1 曾有 **34/66** 个引导目标控件根本不存在，却被标记"已完成"（`tools/check-ui.mjs:4-7`）。
现在这是构建期硬断言：目标要么在源码里真有 `data-tour`，要么写进 `PENDING` 并说明理由（`check-ui.mjs:10-11`；[README.md](../../README.md):167）。

> ⚠ 上面出现了两个「66」，**别当成一件事**：`check-ui.mjs:4` 的「34/66」是 **v1 的记录**（v1 的 66 个引导步骤里有 34 个目标控件不存在）；
> 本文的「66 步」是本机实测的 18 篇教程步骤总数。两者**是否指同一批步骤，本文没有逐条核对** ——
> 教程文本沿用 v1（`tools/build-tutorials.mjs:64-65`），所以有可能就是同一批；未核实前不写成结论。

---

## 9. 能做什么：系统与设置

**9 组设置**（本机实测：`catalog.js` 的 `GROUPS` 长度 9；各组的设置项合计 **57** 项）：

| 组 | 设置项数 | 这一组管什么 | 出处 |
| --- | --- | --- | --- |
| 外观 | 6 | 主题模式 / 配色方案 / 圆角与阴影 / 疏密 / 字体 / 恢复默认；**界面语言入口也在这里** | `catalog.js:18`、`:35-40` |
| 计算与绘图 | 2 | 数值精度、绘图默认范围 | `catalog.js:19`、`:43-44` |
| 引擎 | 6 | 版本、目录、依赖 DLL 状态、已注册函数数、推送通道、引擎自检 | `catalog.js:20`、`:47-52` |
| 组件 | 5 | CPython / MinGW 组件、组件目录、下载源、清理未使用组件 | `catalog.js:21`、`:55-59` |
| AI | 11 | 开关、Base URL、模型、模型参数、密钥、上下文、隐私、测试连接、自检、工具调用、会话记录 | `catalog.js:22`、`:66-76` |
| 搜索 | 8 | 引擎、Wolfram App ID、自定义端点、超时、结果条数、缓存、隐私、自检 | `catalog.js:23`、`:79-86` |
| 账号 | 5 | 站点地址、登录会话、本机凭据、离线承诺、连接自检 | `catalog.js:24`、`:89-93` |
| 更新 | 7 | 当前版本、通道、自动检查、检查间隔、手动检查、更新源、自检 | `catalog.js:25`、`:96-102` |
| 存储与数据 | 7 | 数据目录、教程进度、设置文件、导出诊断包、历史记录、工作区、导入/导出设置 | `catalog.js:26`、`:105-111` |

| 系统能力 | 事实 | 出处 |
| --- | --- | --- |
| 工作区保存/还原 | 按路由分页存（`src/lib/workspace/store.js`、`pendingInput.js`）；绘图页载荷见 [../ui/README.md](../ui/README.md):91 | [../ui/README.md](../ui/README.md):91；[../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md):96（5 页往返未跑数字） |
| 导出图片 | **绘图页**导出 PNG（2 倍像素）；设置里另有**导出设置备份**与**导出诊断包** | `src/lib/plot/exportImage.js:96`；`StorageGroup.vue:28-37`、`:127` |
| 账号 | 登录/注册/续期/改密/登录历史；**未登录、断网都不影响任何计算功能** | [../link/FEATURES.md](../link/FEATURES.md) §2；`:187` |
| 更新检查 | 只提示 + 显示 `sha256` + 把下载页交给系统浏览器；**不自动下载、不执行安装包** | [../link/FEATURES.md](../link/FEATURES.md) §3.1（`:213-222`） |
| 深浅色主题 | 主题模式含"跟随系统"；配色方案可换 | `catalog.js:35-37` |
| 崩溃记录 | **只本地记录、不上报**，在 `%LOCALAPPDATA%\MFMath\logs\`；可导出诊断包 | [README.md](../../README.md):244；[../DECISIONS.md](../DECISIONS.md):131 D-008 |

---

## 10. 离线承诺（准确版）

> **断网后本地计算、绘图、教程、控制台全部照常。只有联网搜索 / 账号 / AI 需要网络。**（[README.md](../../README.md):58）

这条承诺成立，但要把「更新检查」这一项单独说清楚：

| 功能 | 默认要不要网络 | 出处 |
| --- | --- | --- |
| 计算（14 视图）、绘图、教程、键盘、函数工具箱、工作区、设置 | **不要** | 全部结果来自本地引擎（[README.md](../../README.md):84） |
| 控制台 | **不要**（但**装组件**时要） | [../link/FEATURES.md](../link/FEATURES.md) §5.1 |
| 联网搜索 | 要（也可只用本地缓存命中） | [../link/FEATURES.md](../link/FEATURES.md) §1.3 |
| 账号 | 登录/续期/取资料要；`Info`/`ClearLocal`/`Busy` 不要 | [../link/FEATURES.md](../link/FEATURES.md):185-186 |
| AI | 要 | [README.md](../../README.md):58 |
| **更新检查** | **默认不要**：`autoCheck` 默认 `false`，不点「检查」就不会联网；打开「自动检查」后才按间隔（默认 7 天）在启动后 1.5 s 查一次 | `src/lib/update/bridge.js:45`、`:149-161`；设置项 `catalog.js:98-99` |

> ⚠ [README.md](../../README.md):58 那句没列「更新检查」。按代码读，它的默认值让它不违反离线承诺，
> **但一旦用户打开「自动检查」，就多了一个联网功能** —— 引用那句话时请带上这个前提（已记入文末文档债）。

---

## 11. 不能做什么

分类口径照 [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) §0（**四类性质完全不同，混着看就退化成免责声明**）。

### 11.1 能力边界（设计选择的直接后果，不是缺陷）

| 不能做 | 现状（真跑过） | 为什么是有意的 | 出处 |
| --- | --- | --- | --- |
| 非初等函数的不定积分 | `∫xˣ dx`、`∫sin(x)/x dx`、`∫e^{−x²}dx`、`∫1/log(x) dx`、`∫x²e^{−x²}dx` → 返回 `{"isError":false,"value":"未实现"}` | 它们**确实不是初等函数**；一个错误的原函数比「未实现」危险得多 | [../engine/BOUNDARIES.md](../engine/BOUNDARIES.md) §1.1（判定点 `MF_Mathematics/calculus/integrals.cpp:1051-1052`） |
| 部分不定重积分 / 三重积分 | 内层对某个变量不成就**整条**返回「未实现」 | 同上 | [../engine/BOUNDARIES.md](../engine/BOUNDARIES.md) §1.2 |
| 部分不定式极限 | `limit x·sin(1/x) @0` → 报「不定式『三角函数在 ∞（振荡）』暂未实现该形式的求解（不猜结果）」 | 极限**存在**（夹逼），但引擎"知道该拒绝"而不是"知道答案是 0"：宁可不给，也不给没有证明支撑的数 | [../engine/BOUNDARIES.md](../engine/BOUNDARIES.md) §1.4（`calculus/limits.cpp:1084`） |
| 未识别的拓扑空间名 | 直接**报错**，不返回 `π₁(输入)` 这类占位串 | 占位串是本项目最想避免的形状 | [../engine/BOUNDARIES.md](../engine/BOUNDARIES.md) §1.5 |
| 多语言覆盖 | 导航、顶栏、**14 个学科视图**（415 个模式名 + 参数弹窗字段，本机实测缺译文 0）已中英双语；**页面正文**（设置面板各行、工具/绘图/帮助页、`lib/` 提示文案、教程正文）仍是中文 | 覆盖面逐步扩大，不是"没做"；迁移路径明确 | [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md):72；本机实测 `check-ui.mjs` → `i18n 模式名：415 个模式，缺译文 0 条` |

> 引擎「算不出来」时**外部形状不统一**（`isError:false` + 字面量 `未实现` / `isError:true` + 中文文案 / `isError:true` + 第三方英文 `Not Implemented`）——
> 这是做错误处理与写文档的人都必须知道的一张表：[../engine/BOUNDARIES.md](../engine/BOUNDARIES.md) §1.6。

### 11.2 明确不做（想过、决定不做）

| 不做 | 出处 |
| --- | --- |
| 搜索：翻页 / 抓网页正文 / 请求去重限流 | [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md):38 |
| 绘图：复制到剪贴板、导出 SVG/PDF | [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md):39 |
| 更新：自动下载、自动执行安装包（`sha256` **只显示、不校验**） | [../link/FEATURES.md](../link/FEATURES.md) §3.1、§3.2（`:226-232`） |
| AI：token 估算自校准、首字节超时与重试退避 | [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md):40 |
| 崩溃上报（隐私默认；只本地记录） | [../DECISIONS.md](../DECISIONS.md):131 D-008 |
| 不提供 LICENSE（保留所有权利） | [../DECISIONS.md](../DECISIONS.md):167 D-011；本机实测 `Test-Path LICENSE` / `LICENSE.md` / `COPYING` **全为 False** |

### 11.3 推迟（有回来的条件）

更新回滚、AI 多模态、教程录制回放、离线文档全文搜索、历史导出为文件、绘图操作入历史、外观偏好进工作区文件、
控制台的可选组件（sympy / numpy / scipy）—— 每条的**回来的条件**都写在 [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) §2（`:52-59`）。

### 11.4 已知未优化（能用，但慢）

持续同调 `O(n³)`、符号矩阵 > 12×12、`roots_in_disc` 密集求值、`expand((x+1)^10000000)` 等 ——
**清单与判据只在** [../HANG-OPTIMIZATION.md](../HANG-OPTIMIZATION.md) §4（`:163`），本文**不复制它的数字**（复制就会有两份真相）。

### 11.5 部署与安装的现状（最容易被误读的一条）

| 事实 | 说明 | 出处 |
| --- | --- | --- |
| **能出 NSIS 安装包** | `tauri build --bundles nsis` 实测产出 `MF-Mathematics_2.0.0_x64-setup.exe`，**11.11 MiB** | [PACKAGING.md](../../MFMath.Host.Rust/docs/PACKAGING.md):10-11 |
| **但"装完能不能跑"没验过** | 安装后的布局、安装/卸载、从安装目录启动**都尚未真机验证**；原因是本机 `Start-Process` 起不了安装器（`ERROR_CANCELLED`） | [PACKAGING.md](../../MFMath.Host.Rust/docs/PACKAGING.md):12-13、§3 |
| **裸 `tauri build` 不出包** | 仓库里 `bundle.active` 仍是 `false`；要出包必须像 PACKAGING §2 那样**用 `--config` 内联覆盖** `resources`（不配的话装出来只有 exe：白屏 + 算不了数） | `MFMath.Host.Rust/tauri.conf.json:29`；[PACKAGING.md](../../MFMath.Host.Rust/docs/PACKAGING.md):28-30、`:73-75` |
| **仓库不含任何产物/安装包** | 克隆后必须自己构建 | [README.md](../../README.md):94、`:233` |

---

## 12. 尚未验证（别当成有，也别当成没有）

[../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) §5（`:89-103`）说得最清楚，这里只列用户能感知到的几条：

| 事项 | 现状 | 怎么验 |
| --- | --- | --- |
| Rust 宿主「安装 → 启动」 | 能出包，但装完的布局/安装/卸载/启动**都没验过** | 真机上按 [PACKAGING.md](../../MFMath.Host.Rust/docs/PACKAGING.md) §4 走五步 |
| 5 个绘图页的工作区往返（B14） | 用例已写、已登记，**尚未跑出数字** | 在**独占**窗口里跑一次 `cdp-plot-workspace`（[../DECISIONS.md](../DECISIONS.md):153 D-010） |
| 站点侧改动 | `git` 已提交但**线上未部署**，账号"记住我"与静默续期对着线上是半成品 | 部署后跑探针，期望 `401 未认证`（[../OPEN-ITEMS.md](../OPEN-ITEMS.md) §1） |
| 控制台两个组件包 | 清单端点已修，但两个 zip 未上传，标着 `available:false` | 上传后 `available` 应变 `true`（[../OPEN-ITEMS.md](../OPEN-ITEMS.md):119） |
| 那 53 个未映射 action 是否**逐个**能在工具箱里调成功 | [../engine/BOUNDARIES.md](../engine/BOUNDARIES.md):201 逐字写「未证实」——本文同样不替它背书 | 在真宿主里逐个点，或对 `probe_call.exe <fn>` 逐个喂合法参数 |
| 48 个 CDP 端到端用例此刻是否全绿 | **本文没跑**（需要真宿主且要独占，[AGENTS.md](../../AGENTS.md) §4） | `powershell -File MF_UI/MFMath.UI.Vue/tests/run-all.ps1 -NoLaunch` |

---

## 13. 想自己复核：命令清单

```powershell
$V2 = "<本仓库根>"      # 例：C:\...\Multifunctional-Mathematics-v2.0
cd $V2

# ① 引擎注册表：count 应为 424
& MF_Mathematics\build\bin\Release\probe_call.exe list_functions

# ② 引擎边界的真跑样例（非初等积分 → 未实现）
& MF_Mathematics\build\bin\Release\probe_call.exe integrate '{"expr":"x**x","var":"x"}'

# ③ 前端构建期自检（不写盘、不需宿主）：415 模式 / 126 键 / 30 target / 48 用例登记
cd MF_UI\MFMath.UI.Vue
node tools/check-ui.mjs

# ④ 本文 §4/§8/§9 的几个计数
Select-String -Path src\lib\router\nav.js -Pattern 'route: "/calc/' | Measure-Object   # 15（基础运算 + 14 学科）
Select-String -Path src\lib\router\nav.js -Pattern 'route: "/plot/' | Measure-Object   # 7 个绘图入口
node --input-type=module -e "const m=await import('./src/lib/math/keypadSymbols.js'); console.log(m.KEY_COUNT, m.CATEGORIES.length)"
node --input-type=module -e "const m=await import('./src/lib/settings/catalog.js'); console.log(m.GROUPS.length)"
node --input-type=module -e "const j=(await import('node:fs')).readFileSync('src/tutorials/tutorials.json','utf8'); const o=JSON.parse(j); const s=a=>a.reduce((x,t)=>x+t,0); console.log('教程',o.tutorials.length,'步骤',s(o.tutorials.map(t=>t.steps.length)),'示例',s(o.tutorials.map(t=>t.examples.length)))"

# ⑤ 许可证：三个都应为 False
Test-Path LICENSE; Test-Path LICENSE.md; Test-Path COPYING
```

⚠ **跑端到端（`tests/run-all.ps1`）之前先读 [AGENTS.md](../../AGENTS.md) §4**：宿主、`dist/`/`wwwroot`、CDP 端口 9222 都是**全仓库只有一份**的独占资源，并行会话会互相踩出假失败。

---

## 已知的文档债

> 规矩同 [AGENTS.md](../../AGENTS.md) §5：注释/旧文档与**代码**不符时以代码为准，并记 `文件:行`。下表每条都给了复跑方式。
> 其中**第 4、5 两条**是本文写作时新发现的（其余已由别处登记，这里给出复跑方式）。

| # | 位置 | 文档/注释说 | 代码/实测做 | 复跑方式 |
| --- | --- | --- | --- | --- |
| 1 | [README.md](../../README.md):56 | 系统分区含「**结果**导出为图片」 | 导出图片只存在于**绘图页**（`src/lib/plot/exportImage.js`；6 个 React 绘图页各自调用）；计算结果的对话框只有「复制结果 / 复制 JSON」（`src/components/calc/ResultDialog.vue:138-139`），没有导出图片 | `Select-String -Path MF_UI -Pattern exportCanvas -Recurse`（命中全部在 `plot/` 下） |
| 2 | [README.md](../../README.md):58 | 「只有联网搜索 / 账号 / AI 需要网络」 | 还有**更新检查**：设置里有「自动检查 + 检查间隔」（`catalog.js:98-99`），打开后会在启动后 1.5 s 联网查一次（`lib/update/bridge.js:149-161`）。默认 `autoCheck:false`（`:45`），所以默认不违反离线承诺 | 读 `MF_UI/MFMath.UI.Vue/src/lib/update/bridge.js:45` 与 `:149-161` |
| 3 | `MF_UI/MFMath.UI.Vue/src/lib/settings/catalog.js:23` | 搜索组注：「抓取与解析在宿主（**C#**）」 | 现役宿主是 Rust（`MFMath.Host.Rust/src/search.rs`）；C# 宿主已废弃（[../DECISIONS.md](../DECISIONS.md):102 D-006） | 读 `catalog.js:23` 对比 `MFMath.Host.Rust/src/search.rs` 是否存在 |
| 4 | `MF_UI/MFMath.UI.Vue/src/lib/settings/catalog.js:22` | AI 组注：「密钥只存宿主（**DPAPI**）」 | AI 的 API Key 已是**明文** `ai.json`（[../link/CREDENTIALS.md](../link/CREDENTIALS.md):17-23）；**同一个文件** `:70` 的 keywords 自己写着"明文 … 不受保护" —— 同一文件内自相矛盾 | 读 `catalog.js:22` 与 `:70`；`docs/link/CREDENTIALS.md` §0 |
| 5 | `MF_UI/MFMath.UI.Vue/tests/run-all.ps1:63` | 注释「设置面板（入口、**7 个分组**…）」 | `catalog.js:17-26` 的 `GROUPS` 是 **9** 组（本机实测） | `node --input-type=module -e "console.log((await import('./MF_UI/MFMath.UI.Vue/src/lib/settings/catalog.js')).GROUPS.length)"` |
| 6 | [../ui/README.md](../ui/README.md):229、`:256` | `unit-*.mjs` **3** 个 / 登记表 **52** 项（该文件自称核对时间 2026-10-07 10:52） | 本机实测：磁盘 `unit-*.mjs` **4** 个，`run-all.ps1` 登记 **53** 项（48 `cdp-*` + 4 `unit-*` + `audit-modes`） | §13 的计数脚本（`$tests` 数组解析）；`(Get-ChildItem MF_UI/MFMath.UI.Vue/tests/unit-*.mjs).Count` |
| 7 | [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md):72 | 「**184 个**参数弹窗字段」 | 本机实测 `check-ui.mjs` 打印 `i18n 弹窗字段：186 条唯一标签`（口径是否同一未证实）——已由 [../engine/BOUNDARIES.md](../engine/BOUNDARIES.md) 文档债 §#3 登记 | `cd MF_UI/MFMath.UI.Vue; node tools/check-ui.mjs` |
| 8 | `MF_UI/MFMath.UI.Vue/tools/build-tutorials.mjs:476` | 生成数据里的 `generatedFrom` 字段写 `MF_Tutorial/tutorials/*.yaml` | 运行期数据来自该脚本的输入（v1 树，`MF_TUTORIAL_SRC`），**留档副本**在 `docs/tutorials-src/`（`build-tutorials.mjs:36`）。那个字符串是**写死的旧路径**，不是本次生成的来源路径 | 读 `build-tutorials.mjs:36` 与 `:476`；`Get-ChildItem docs/tutorials-src/*.yaml` 得 18 |

> 另有 3 条**不是本文的范围但引用前必须知道**（已在别处登记，这里只给指针）：
> [README.md](../../README.md):11-13 声明「快速开始第 3 步与运行命令仍写的是已废弃宿主」；
> [../ui/README.md](../ui/README.md):369-377 的 D1–D7（含 `package.json` 的 C# 描述、`run-all.ps1` 默认宿主人选等）；
> [../PROJECT-BOARD.md](../PROJECT-BOARD.md) §3 R7（`docs/` 里把 C# 宿主写成现役的那批文档）。
