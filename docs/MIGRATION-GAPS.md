# v1 → v2.0 功能迁移缺口报告

> 目的：把"v1 有的功能，v2.0 有没有、缺的怎么补、先补哪个"一次写清，作为后续排期的唯一依据。
> 判定基准：**v1 的实际产品形态**是 Python + PySide6 桌面应用（`Multifunctional-Mathematics.spec` 打包的就是它），
> 不是中间产物 `MF_UI/MFMath.UI`（原生 JS 网页壳）或 `MF_UI/MFMath.UI.Vue`（更早的 Vue 版本）。
> v2.0 形态：C++ 引擎（`mf_mathematics.dll`）+ C# WebView2 宿主 + Vue 3 前端。
> 方法：源码清点（读代码判定，未实跑 v1，见 §7）。所有结论都附文件与行号。

---

## 0. 结论摘要

- **算得对这件事已经过关**：引擎 424 个 action、准确性套件 2180 用例全过、覆盖 424/424；
- **v2.0 已经具备一个可用计算器的全部主功能**：14 个学科域的计算、7 种绘图、控制台、教程/引导/示例库、数学键盘、设置面板、外观主题；
- **但 v1 作为一个"应用"还差 12 类用户可感知的功能**（AI 助手、分步显示、在线搜索、用户系统、历史记录、工作区保存、中英双语、导出图片、数学边界守卫、无理数逼近、自动更新、关于对话框）；
- **另有 4 处"迁了但降级"**（控制台运行时、快捷键、两个设置项、历史持久化），这类比"没有"更容易被漏掉；
- **最不该有的现状**：顶栏「搜索」「历史」两个按钮点了**没有任何反应**（死按钮）。→ 本轮已修，见 §0.1

### 0.1 本轮已完成的修正（2026-10-02）

| 项 | 状态 | 证据 |
| --- | --- | --- |
| 顶栏「历史」死按钮 → **真实历史功能** | 已完成 | `src/lib/history/store.js` + `src/components/history/HistoryDialog.vue`；落 `%LOCALAPPDATA%\MFMath\settings\history.json`（走宿主原子写）；端到端 `cdp-history-search.mjs` **20 / 0** |
| 顶栏「搜索」死按钮 → **占位说明面板** | 已完成（真实搜索仍未做） | `src/components/tools/SearchPlaceholder.vue`：明说"尚未接入 + 将来是什么 + 依赖什么"，可直接跳到设置里的搜索分组；详见 §2.3 |
| 控制台缺 sympy / numpy / scipy | **本地已解决**，站点尚未换包 | `MFMath.Host/tools/build-python-component.ps1` 重建组件包（10.5 MB → 64 MB 下载 / 191 MB 安装）；实测控制台里 import 与真实计算全部通过；详见 §3.1 |
| 基础运算页"最近计算"不落盘 | 已完成（与全局历史统一） | `BasicCalcView.vue` 的列表改为读全局历史（不再刷新即失）；设置 → 存储与数据里可看条数与清空 |
| **C#→JS 推送通道**（AI 与更新进度的共同前置） | 已完成 | 宿主 `PushHub.cs`（`PostWebMessageAsJson` + UI 线程编组 + 信封 `{topic,seq,ts,payload}`）+ JS `src/lib/push.js`；真实生产者：组件安装进度 `component.install`、控制台运行 `console.run`；设置 → 引擎里有自检行；端到端 `cdp-push.mjs` **19 / 0** |

---

## 1. 已经做完的

| # | 能力 | 证据 |
| --- | --- | --- |
| 1 | **引擎（C++）**：424 个 action，C ABI `math_call` / `function_exists` | 准确性套件 2180 通过 / 0 失败 / 覆盖 424/424；`MF_Mathematics/registry.cpp` 注册 |
| 2 | **宿主桥**：`mf`（引擎）、`win`（窗口）、`con`（控制台/组件）、`sys`（设置/存储）、`push`（推送诊断）五个 host object + C#→JS 推送通道 | `MFMath.Host/{MathBridge,WindowBridge,ConsoleBridge,SettingsBridge,PushBridge,PushHub}.cs`；`src/lib/push.js` |
| 3 | **计算页**：14 个学科域 + 基础运算页，模式下拉 → 引擎 action 映射 | `src/lib/engine/engineMap.js`(54 KB) + `engineMapExtra.js`(44 KB) + `viewConfigs.js` |
| 4 | **绘图 7 模式**：2D / 极坐标 / 3D 曲面 / 复平面 / 向量场 / 自由几何 / 分形 | `src/router/registry.js` 的 `NAV_GROUPS.plot`；对应 `src/views/plot/*.vue` 6 个 + PlotCanvas |
| 5 | **参数滑块 + 几何撤销重做** | `components/plot/ParamSlider.vue`；`views/plot/PlotGeometryView.vue:31-32` |
| 6 | **控制台**：CodeMirror 6（高亮/补全/搜索，按需加载）+ CPython/MinGW 组件按需下载 | `views/tools/ConsoleView.vue`、`lib/console/editor.js`、`MFMath.Host/ConsoleBridge.cs`（`Start/Poll/Stop/Install/Uninstall`） |
| 7 | **教程系统**：18 篇 / 66 步 / 52 示例 / 42 FAQ + 交互式引导 + 示例库 | `docs/tutorials-src/*.yaml`（18 个原件）→ `src/tutorials/tutorials.json`；`lib/tutorial/*`、`components/tutorial/*` |
| 8 | **数学键盘**：126 键 / 6 分类 / 搜索 / 最近使用 / LaTeX 占位符 | `lib/math/keypadSymbols.js`、`components/math/MathKeypad.vue` |
| 9 | **设置面板**：容器式 7 分组 + 搜索跳转 + 引擎自检 + 组件状态 + 诊断包导出 | `lib/settings/catalog.js`、`views/settings/SettingsView.vue`、`components/settings/*` |
| 10 | **外观**：10 套配色 + 亮/暗/跟随系统 + 圆角/疏密/字体四维 | `components/settings/AppearanceGroup.vue`、`App.vue` |
| 11 | **结果呈现**：KaTeX 排版 + 字段中文标签 + 复制结果 / 复制 JSON | `components/calc/ResultDialog.vue`、`lib/engine/resultModel.js` |
| 12 | **工程化**：git 版本管理、构建期自检、端到端测试 | `tools/check-ui.mjs`、`tests/run-all.ps1`、`tests/cdp-*.mjs`（教程+键盘 37 项、设置 25 项、解方程 13 项） |

---

## 2. 没做完的（完全缺失，12 项）

每项格式：**v1 有什么 → v2.0 现在什么状态 → 怎么补 → 依赖 → 粗估工作量**。

### 2.1 AI 助手

- **v1**：`MF_AI/`（8 文件：`agent.py`/`client.py`/`config.py`(17 KB)/`models.py`/`strategy.py`）+ `MF_UI/dialogs/ai_dialog.py`(14.8 KB) + `dialogs/ai_config_prompt.py` + 缓存 `ai_cache.json`。
- **v2.0**：完全没有，连顶栏按钮都不存在。`lib/settings/catalog.js` 里 AI 组 12 个设置项全是 `pending`（字段名已按 v1 的 `config.yaml` 对齐）。
- **怎么补**：
  1. 宿主新增 `AiBridge.cs`：`HttpClient` 打 SSE 流式接口；密钥用 DPAPI 加密后存 `%LOCALAPPDATA%\MFMath\settings\ai.json`（复用 `sys.StoreWrite`）。
  2. ~~先补推送通道~~ —— **本轮已完成**：宿主 `PushHub.Send(topic, payload)` + JS `lib/push.js` 的 `onPush(topic, handler)`，信封 `{topic,seq,ts,payload}`，跨线程安全、失败只记计数不抛。AI 剩下要做的只是在 `AiBridge` 里边收边 `PushHub.Send("ai.delta", …)`。
  3. 前端 `views/ai/AiDialog.vue`（对话 + 上下文 + 流式渲染，订阅 `ai.delta`/`ai.done`；数学片段交给现有 `MathLatex.vue`）。
  4. 把 `catalog.js` 的 AI 组从 `pending` 改成 `ready` 并接上真实读写。
- **依赖**：§0.4 第 4 条决策（AI 步骤语义）；`PLAN-feature-completion.md` P3。
- **粗估**：4-6 人日（推送通道已完成，不再计入）。

### 2.2 分步显示

- **v1**：`MF_UI/calc/step_viewer.py`(10.2 KB，"AI 驱动的步骤查看器，LaTeX 渲染，像人类教师书写")；入口在结果窗的"查看步骤"。
- **v2.0**：**入口已在、内容为空**：`CalcView.vue:178` 的 `onSteps()` 只给出"当前给出明确提示，不伪造内容"。引擎信封没有 `steps` 字段（已核对全部 `*_api.cpp`）。
- **怎么补（三条路线，需先决策）**：
  | 路线 | 做法 | 优点 | 代价 |
  | --- | --- | --- | --- |
  | A 引擎出步骤 | 在 `symbolic_api.cpp` 等 handler 里逐步记录（求导链、换元、分部积分） | 与硬约束"计算在 C++"完全一致、可回核验 | 工作量大，很多 action 没有天然步骤 |
  | B AI 出步骤 | AI 生成讲解，引擎结果作为事实底稿 | 出稿快、像人讲 | 需 AI（推送通道**已就绪**）；必须加"结果区恒等于引擎值"的断言防越权计算 |
  | C 规则拼步骤 | 前端按 action 类型套模板（如"求导：和差→积→链式"） | 无依赖、可离线 | 覆盖面窄，易写成"复述公式" |
- **注意**：v1 的步骤文本来自 84 个 Python 文件约 600 处，随"Python 清零"一起消失——**不能靠移植 v1 代码拿回来**。
- **依赖**：§0.4 第 4 条决策（三选一）。
- **粗估**：A 10+ 人日 / B 3 人日（含 AI）/ C 4 人日。

### 2.3 在线搜索

- **v1**：`MF_Online/`（`search.py` 5.7 KB、`cache.py`、`config.py`）+ `dialogs/search_panel.py`(7.4 KB)，支持 DuckDuckGo / Wolfram Alpha / 自定义端点。
- **v2.0（本轮后）**：顶栏「搜索」不再是死按钮 —— 点开 `components/tools/SearchPlaceholder.vue`，写明"尚未接入 + 将来支持什么 + 依赖什么"，并可一键跳到设置里的搜索分组（`/settings?group=search`）。**真实的搜索面板仍未实现。**
- **怎么补（真实面板）**：宿主新增 `SearchBridge.cs`（`HttpClient` + 超时 + 结果解析 + 本地缓存到 `%LOCALAPPDATA%\MFMath\search_cache.json`）；前端把占位面板换成 `components/tools/SearchPanel.vue`（非模态、结果里的表达式可一键送进计算页，复用 `lib/workspace/pendingInput.js`）；`catalog.js` 的 search 组 6 项落地。
- **注意**：占位面板里**故意不放搜索框** —— 摆一个搜不出东西的输入框比明说"还没接入"更糟。这条约束在 `cdp-history-search.mjs` 里有断言守着。
- **依赖**：Wolfram 需要 App ID（用户自带）。
- **粗估**：真实面板 2-3 人日（占位已完成）。

### 2.4 用户系统

- **v1**：`MF_User/`（`login_dialog.py` **34 KB**、`auth_service.py`、`auth_worker.py`、`api_client.py` 10.9 KB）+ `users.json`；站点侧接口现成。
- **v2.0**：无，顶栏也没有登录入口。
- **怎么补**：宿主 `AccountBridge.cs`（登录/注册/邮箱验证码 + token 存 DPAPI）；前端 `views/account/AccountDialog.vue` + 顶栏登录态（登录后显示用户名）；离线可用性必须保住——**未登录不得影响任何计算功能**。
- **依赖**：站点后端接口（已存在）。
- **粗估**：3-4 人日。

### 2.5 历史记录 —— 本轮已完成

- **v1**：`dialogs/history_dialog.py`("点击回退到该表达式") + 编辑菜单"清空历史"，跨会话保留。
- **v2.0 实现（已完成）**：
  1. `src/lib/history/store.js` —— 唯一记录入口（`record/removeEntry/clearAll/clearRoute/listByRoute/searchEntries`），落 `%LOCALAPPDATA%\MFMath\settings\history.json`，走宿主的**原子写**（`SettingsBridge.StoreWrite`：先校验 JSON → 备份旧文件 → 临时文件替换）；
  2. `src/components/history/HistoryDialog.vue` —— 顶栏「历史」打开：时间 / 模式 / 表达式 / 结果摘要，支持搜索、逐条删除、点一条**回到原页面并回填**（走 `pendingInput` 这条已验证通路）、清空带二次确认；
  3. 记录点：`CalcView`（成功与失败都记）与 `BasicCalcView`（失败也记）；摘要由 `resultModel.briefValue()` 生成，**优先取"答案类"字段**（解集/根/取值…）而不是 `delta/exact/params` 那串元信息；
  4. 基础运算页的"最近计算"改为读全局历史（不再刷新即失），清空只清本页那部分；
  5. `catalog.js` 的 `storage.history` 由 `pending` 改 `ready`，设置 → 存储与数据里可看条数、可清空。
- **验证**：`tests/cdp-history-search.mjs` **20 / 0**（含"真的落盘：`sys.StoreList()` 里能看到 history 文件"）。
- **未做**：导出历史为文件（需要宿主文件对话框，见 §3.5）；绘图页的操作没记入历史（v1 也只记计算）。

### 2.6 工作区保存 / 加载

- **v1**：文件菜单"保存工作区 / 加载工作区" → `workspace_save.json` + `calc/base_workspace.py`(4.9 KB)。
- **v2.0**：无；`catalog.js` 里 `storage.workspace`、`storage.io`（导入/导出设置）仍是 pending。**历史的落盘通路（`sys.Store*`）已经跑通，工作区可以直接复用它**。
- **怎么补**：定义工作区 schema（`{version, appearance, calc: {blocks}, plot: {expressions, ranges, view}, console: {tabs}}`）→ 用 `sys.StoreWrite("workspace", json)` 存"最近工作区"，另用文件对话框支持"另存为 .mfws.json"（**需要新宿主方法**，见 §7.3）；加载时校验 `version` 并给出迁移提示。
- **注意**：v1 的坑是"写在安装目录 + 恢复时谎报成功"，v2.0 必须写到 `%LOCALAPPDATA%` 并在失败时明确报错。
- **粗估**：2-3 人日（含文件对话框）。

### 2.7 中英双语（i18n）

- **v1**：`MF_UI/i18n.py`（中/英两套完整字典，第 70-138 行）+ `utils/translator.py`(7 KB) + 设置里"语言 / Language"下拉。
- **v2.0**：只有中文，没有 i18n 机制。
- **怎么补**：建 `src/i18n/`（`zh-CN.js` / `en-US.js` + `t()` + 语言状态存 localStorage/`sys.StoreWrite`）；**分两步**——先做壳层（顶栏、导航、对话框标题与按钮、设置面板），再逐页替换正文；页面内的长文案（教程、占位说明）可后置。
- **工作量依据**：v2 前端源码里**非注释的中文行约 1695 行**，这就是需要抽键的文案量级。
- **粗估**：壳层 2 人日；全量 6-8 人日。

### 2.8 导出图片

- **v1**：i18n 键 `menu.export = "导出图片"`；`plot/*/workspace.py:289` 导出 PNG（dpi=200）；`calc/math_display.py:288` 也有 `fig.savefig`。
- **v2.0**：没有（全仓 `toDataURL` / `saveImage` 零命中）。绘图结果只能看，不能存。
- **怎么补**：`PlotCanvas` 等本来就是 `<canvas>` → `canvas.toDataURL("image/png")`（按 `devicePixelRatio` 出 2x 图）+ 宿主新增 `SaveFileDialog` 方法落盘；同时提供"复制到剪贴板"。
- **粗估**：1 人日。

### 2.9 数学边界守卫

- **v1**：`MF_UI/utils/math_guard.py`(12.7 KB) + `math_guard_ui.py`(5.5 KB)：三级拦截——黄=预计 >10s 慢速预警、红=超高次幂积分/大矩阵/大范围求和等爆炸风险、黑=除以零/未定义符号等硬错误；阈值从 `config.json` 的 `math_guard` 段读取。
- **v2.0**：无对应的**提交前预判**。引擎内部有局部守卫（`safe_solve`、定义域约束），但"这次计算会不会卡死"没人拦。
- **怎么补**：两条路——① 引擎加一个 `estimate_cost(expr, action)` action（可复用 `symbolic_util.h` 的 `node_count()`）；② 前端用规则表先做一版（幂次、矩阵阶数、求和范围、嵌套层数）。命中即弹确认框（可"仍然计算"），阈值进设置；黑名单类错误直接拦。
- **粗估**：引擎路线 2 人日 / 前端规则路线 1 人日。

### 2.10 无理数逼近模块

- **v1**：`MF_UI/calc/numerical_estimation.py`(14.9 KB)：Ramanujan 级数求 π、Leibniz 级数求 π、Monte Carlo 求 π、Taylor 求 e、Newton 求 √2。
- **v2.0**：无（引擎里的 `leibniz_test` 是级数判敛，不是这个）。
- **怎么补**：引擎加 5 个 action（`ramanujan_pi` / `leibniz_pi` / `monte_carlo_pi` / `taylor_e` / `newton_sqrt`），数值分析页挂成模式，结果页展示"迭代次数—误差"表。
- **粗估**：1.5 人日（引擎 5 个小函数 + 映射）。

### 2.11 自动更新

- **v1**：`main_window.py:1147-1158` 启动时请求 `https://mf-vis-science.cn/api/version`，发现新版弹窗；设置里有"启动时自动检查更新"；另有独立下载器 `dist-downloader/`(249 文件)。
- **v2.0**：无；`catalog.js` 的 update 组 6 项 pending。
- **怎么补**：① 站点 `/api/version` 先补 `sha256` 字段（当前缺）；② 宿主 `UpdateBridge.cs`：检查 → 下载到临时目录 → 校验 sha256 → 原子替换 → 提示重启；③ 前端设置组落地 + 启动时静默检查（可关）。
- **依赖**：站点改动（不在本仓库）。
- **粗估**：宿主 3 人日 + 站点 0.5 人日。

### 2.12 关于对话框

- **v1**：`dialogs/about_dialog.py`(14.5 KB，"完整功能介绍与技术栈"，可滚动)。
- **v2.0**：`App.vue:183` → `alert("MF-Mathematics\nMF-Vis-Science · Open Studio")`。等于没有。
- **怎么补**：`components/shell/AboutDialog.vue`，文案从 v1 搬，版本号/引擎信息/依赖状态**运行时读**（`mf.Version()`、`sys.EngineReport()` 已有）；加"打开数据目录""导出诊断包"两个现成入口。
- **粗估**：0.5 人日。

---

## 3. 迁了但降级 / 残缺的（4 项）

### 3.1 控制台的运行时与可用包 —— 本轮已解决（本机生效）

| | v1 | v2.0（本轮后） |
| --- | --- | --- |
| 执行方式 | 进程内 Python，**numpy / sympy / scipy + MF_Mathematics 包**直接可用（`console/console_engine.py` 顶部即 import） | 跑**下载来的** CPython 组件，经 `mfmath.py` 门面调引擎（`ConsoleBridge.cs:34-37, 504-537`） |
| 第三方包 | 开箱即用 | **组件包已重建，三个包都在**（sympy 1.14.0 / numpy 2.5.3 / scipy 1.18.1 / mpmath 1.3.0） |
| 下载体积 | — | 10.5 MB → **64 MB**；安装后 191 MB |

- **怎么做的**：`MFMath.Host/tools/build-python-component.ps1` —— 取官方 embeddable 包，把 cp313/win_amd64 的轮子解到 `Lib\site-packages`，改写 `python313._pth`（加 `Lib\site-packages` 与 `import site`），打包成**同名** zip；用宿主既有的"同名 `.sha256` 旁文件优先"机制（`ConsoleBridge.cs:227-243`）放进组件缓存，安装流程即可接受，**不用改宿主代码**。
- **验证**：`tests/cdp-console-sci.mjs` **8 / 0** —— 真实宿主控制台里 `import sympy, numpy, scipy, mpmath`、`sp.diff`、`np.linalg.det`、`scipy.integrate.quad` 全部算对，且门面 `mfmath.call` 仍能调 C++ 引擎。
- **还差一步（站点）**：把新包上传到 `https://mf-vis-science.cn/download/component/python`，然后更新 `ConsoleBridge.cs` 的 `PythonPayloadSha256` 与 `PythonPayloadBytes`（脚本会把两个值打印出来）。**换包之前不要改这两个常量**，否则新用户下到旧包会校验失败。当前本机靠 `.sha256` 旁文件生效，别人拿不到。

### 3.2 快捷键

- **v1**：F1 帮助（`main_window.py:398`）、Ctrl+Z 撤销、Ctrl+Y 重做（编辑菜单）。
- **v2.0**：只有局部快捷键——对话框 Esc/Enter、编辑器 Ctrl+Enter 运行、引导 ←/→（全仓无全局 F1、无 Ctrl+Z/Y）。
- **怎么补**：`App.vue` 挂全局 `keydown`：F1 → `/tutorial`，Ctrl+Z/Y → 计算页撤销栈（需要给 `CalcView` 加 blocks 历史栈）。顺手把"快捷键一览"放进帮助文档。

### 3.3 两个设置项缺失

| v1 设置项 | v2.0 |
| --- | --- |
| **数值精度**（"位有效数字"，`settings_dialog.py:162-167`） | 无此项；数字格式化固定 12 位（`lib/engine/resultFormat.js:34` 的 `toFixed(12)`） |
| **绘图默认值**（X/Y 轴范围，`settings_dialog.py:112-136`） | 无此项 |

- **怎么补**：`catalog.js` 加 `precision.digits`、`plot.defaultRange` 两项（外观/引擎组旁边新开"计算与绘图"分组更合适）；写入设置文件后由 `resultFormat.js` / `PlotView` 默认区间读取。

### 3.4 历史不跨会话 —— 已并入 §2.5 并完成

---

## 4. 怎么补：排序与批次

排序原则：**先修"点了没反应"和"半小时能做完的"，再补依赖少的，最后做需要新通道/后端/决策的。**

### 第一批（P0，合计约 2 人日）——先让界面不说假话

| 项 | 动作 | 状态 |
| --- | --- | --- |
| 顶栏死按钮 | 「历史」做成真实功能；「搜索」先给占位说明面板 | **已完成**（`cdp-history-search` 20/0） |
| 关于对话框 | 新建 `AboutDialog.vue`，替换 `App.vue` 的 alert | 未开始 |
| 控制台包核实 | 跑 `import sympy/numpy/scipy` 各一行 | **已完成**：三个包都在，并已重建组件包（`cdp-console-sci` 8/0）；**只差站点换包** |

### 第二批（P1，合计约 4-6 人日）——不依赖任何未决事项

| 项 | 动作 | 前置 | 状态 |
| --- | --- | --- | --- |
| **历史记录**（§2.5） | `sys.Store*` 落盘 + 统一记录入口 + 历史面板 + 接顶栏 | 无 | **已完成** |
| **导出图片**（§2.8） | canvas → PNG + 新增宿主 `SaveFileDialog` | 需新增宿主方法 | 未开始 |
| **工作区保存/加载**（§2.6） | schema + `sys.StoreWrite` + 另存为 | 同上 | 未开始（落盘通路已由历史验证） |
| **快捷键**（§3.2） | 全局 F1 / Ctrl+Z / Ctrl+Y | 无 | 未开始 |
| **两个设置项**（§3.3） | 精度 + 绘图默认范围 | 无 | 未开始 |
| **数学守卫**（§2.9） | 前端规则版先上，阈值进设置 | 无 | 未开始 |
| **无理数逼近**（§2.10） | 引擎 5 个 action + 数值分析页模式 | 无 | 未开始 |
| **站点换组件包**（§3.1） | 上传新 zip + 改 `PythonPayloadSha256` / `PythonPayloadBytes` | 站点写入权限 | 未开始（本机已生效） |

### 第三批（P2，合计约 8-10 人日）——需要新通道或外部改动

| 项 | 动作 | 前置 | 状态 |
| --- | --- | --- | --- |
| **C#→JS 推送通道** | `PushHub` + `PostWebMessageAsJson` + `lib/push.js` 的 `onPush` | 无 | **已完成**（`cdp-push` 19/0；组件安装进度与控制台运行结束已在用） |
| **AI 助手**（§2.1） | `AiBridge.cs` + AI 对话窗 + 设置组落地 | §0.4 第 4 条决策（推送通道已就绪） | 未开始 |
| **分步显示**（§2.2） | 按选定路线实现，接 `CalcView.vue:178` 已有的 `onSteps` | 同上的决策 | 未开始 |
| **自动更新**（§2.11） | 站点补 sha256 + `UpdateBridge.cs` + 设置组（进度条可直接用推送） | 站点改动 | 未开始 |

### 第四批（P3）——需要后端或性价比低

| 项 | 前置 |
| --- | --- |
| 用户系统（§2.4） | 站点接口（已存在） |
| 在线搜索（§2.3） | Wolfram App ID（用户自带） |
| 中英双语（§2.7） | 无前置，但文案量大（约 1695 行中文），建议壳层先做、正文后做 |

---

## 5. 有意不迁移的（决策，不算缺口）

| 项 | 说明 |
| --- | --- |
| 安装包流水线 | `dist-installer/`(472 文件)、`scripts/installer.iss`、`build-installer.ps1` —— v2.0 目前产不出安装包（`STATUS-and-ROADMAP.md` §3.2） |
| 独立下载器 | `dist-downloader/`(249 文件)，未纳入 |
| HTTP 计算服务 | `math_http_service.py`，站点零引用（已核实），可整体弃用 |
| 分发脚本 | `MF_Mathematics/tools/sync-engine.ps1`（消费方清单仍是旧布局，未纳入 v2.0） |
| 派生工程 | `MFMath.Test`、`demo_cs_mf`、`MF_Scheduling` |
| PyInstaller spec | 3 个 `.spec`，v2.0 已不需要 |

---

## 6. 复现验证命令

```powershell
$V2 = "C:\Users\fsafsafsa\Desktop\MVS知识库\Multifunctional系列\Multifunctional-Mathematics-v2.0"

# 1) 引擎：构建 + 准确性（2180 用例 / 覆盖 424）
cmake -S "$V2\MF_Mathematics" -B "$V2\MF_Mathematics\build" -G "Visual Studio 18 2026" -A x64
cmake --build "$V2\MF_Mathematics\build" --config Release --target mf_mathematics
python "$V2\..\Multifunctional-Mathematics\MF_Mathematics\tests\accuracy\run_accuracy.py"
#    准确性套件仍在 v1 树，但默认 DLL 已是 v2.0 的绝对路径（harness.py 的 ENGINE_DLL），
#    不需要再设 MF_ACC_DLL；要测别的构建产物才用该环境变量覆盖。

# 2) 前端：自检 + 构建
npm run check:ui --prefix "$V2\MF_UI\MFMath.UI.Vue"
npm run build    --prefix "$V2\MF_UI\MFMath.UI.Vue"

# 3) 宿主 + 端到端（改过前端必须重跑 build：宿主读的是 dist 的**拷贝**）
dotnet build "$V2\MFMath.Host\MFMath.Host.csproj" -c Release --no-incremental
$env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = "--remote-debugging-port=9222"
Start-Process "$V2\MFMath.Host\bin\Release\net10.0-windows\MFMath.exe"
node "$V2\MF_UI\MFMath.UI.Vue\tests\cdp-tutorials-keypad.mjs"   # 37 项
node "$V2\MF_UI\MFMath.UI.Vue\tests\cdp-settings.mjs"           # 26 项
node "$V2\MF_UI\MFMath.UI.Vue\tests\cdp-engine-solve.mjs"       # 13 项
node "$V2\MF_UI\MFMath.UI.Vue\tests\cdp-history-search.mjs"     # 20 项（历史 + 搜索占位）
node "$V2\MF_UI\MFMath.UI.Vue\tests\cdp-console-sci.mjs"        #  8 项（组件未装时 SKIP）
node "$V2\MF_UI\MFMath.UI.Vue\tests\cdp-push.mjs"               # 19 项（推送通道：往返/运行/安装/自检）
node "$V2\MF_UI\MFMath.UI.Vue\tests\cdp-basic-calc.mjs"         # 41 项
# 或一次跑完：powershell -ExecutionPolicy Bypass -File "$V2\MF_UI\MFMath.UI.Vue\tests\run-all.ps1"

# 4) 控制台组件包（带 sympy / numpy / scipy）
powershell -ExecutionPolicy Bypass -File "$V2\MFMath.Host\tools\build-python-component.ps1" -Install
#    -Install 会把自建包放进组件缓存并写同名 .sha256 旁文件；
#    随后在应用里「设置 → 组件 → CPython」先卸载再安装即可生效。
#    换官方发布包时：上传新 zip 到站点，再按脚本打印的值更新 ConsoleBridge.cs 的两个常量。
```

---

## 7. 方法局限与待核实项

1. **v1 未实跑**：本报告"v1 有"全部按源码判定（`MF_UI/main_window.py`、`MF_UI/dialogs/*`、`MF_UI/calc/*`、`MF_UI/console/*`、`MF_AI/*`、`MF_Online/*`、`MF_User/*`、`MF_UI/i18n.py`、`MF_UI/utils/math_guard.py` 等）。个别功能的实际行为可能与此不同，若要逐项确认需先把 v1 的 PySide6 环境跑通。
2. **仍待核实**：
   - ~~控制台组件的 CPython 里有没有 numpy / sympy / scipy~~ —— **已核实并解决**（见 §3.1）；
   - v1"数值精度"设置对结果格式化的实际作用范围（我只看到设置项与固定 12 位两个端点，没逐处核对）；
   - 站点 `/api/version` 现有字段与自动更新的接口约定（§2.11）。
3. **宿主能力清单（写补法时的前提，已核对）**：
   - 已有：`mf.Dispatch/Version/FunctionExists/*Symbolic`、`win.{Minimize,ToggleMaximize,Restore,IsMaximized,Close,StartDrag,SetChromeBackground}`、`con.{Start,Poll,Stop,Install,Uninstall,Components,SetDownloadBase,InstallStatus,CancelInstall}`、`sys.{Info,EngineReport,StoreList,StoreRead,StoreWrite,StoreDelete,OpenPath,ExportDiagnostics}`、`push.{Info,Emit,Ready}`；
   - **推送通道（已完成）**：宿主侧 `PushHub.Send(topic, payloadJson)`（任意线程可调，内部编组回 UI 线程；失败只记 `Failed`/`LastError`，不抛）。已用的主题：`component.install`（安装进度）、`console.run`（阶段/结束）、`settings.test`（自检）。新增主题只需在宿主处 `Send`，页面 `onPush("主题", fn)` 订阅。
   - 缺：**文件对话框**（导出图片/工作区另存为需要新增）；
   - 存储位置：`%LOCALAPPDATA%\MFMath`（设置与键值文件在 `settings\` 子目录，原子写 + 损坏备份已实现）。
4. **组件包的两个只在宿主编译时才校准的常量**：`PythonPayloadSha256` / `PythonPayloadBytes` 是给"从站点下载"用的；自建包靠同名 `.sha256` 旁文件生效。**站点换包前不要改这两个常量**。
