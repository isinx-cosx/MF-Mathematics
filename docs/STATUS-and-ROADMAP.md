# MF-Mathematics v2.0 现状与规划报告

> 生成时间：本轮工作结束时。所有数字均为**实测**（命令见 §6），非估算。
> 配套文档：`docs/PLAN-feature-completion.md`（功能补全方案，含逐项证据与行号）。

---

## 一、一句话结论

**现在是一个"引擎 + 前端 + 宿主同处一棵树、可直接构建运行"的干净版本**（407 个源文件 / 约 3 MB），
引擎 424 个数学函数与 2180 条准确性用例全部通过；22 个计算/绘图模式、外观系统、控制台、组件下载、
**教程系统、数学键盘、设置面板**均已可用，并经真实宿主窗口端到端验证。

**缺的是四块功能**（AI 助手、在线搜索、用户系统、分步显示）与**一条工程主线的收尾**（交付链与 Python 清零）。
其中"分步显示"卡在一个必须你拍板的语义决策上（见 §3.5 第 4 条），因此按指示未做。

### 本轮之后的状态变化（相对于本报告初稿）

| 项 | 变化 |
| --- | --- |
| 设置面板 | 由"没有（顶栏弹 alert）"变为**容器式面板**：7 个分组、搜索可跳到具体项；外观/引擎/组件/存储四组已可用，AI/搜索/更新三组为占位并写明依赖 |
| 引导目标 | 已实现 22 个、待实现 9 个（此前 20 / 11）；设置分组登记为目标后，教程里 `settings_dialog.*` 两步不再是"目标不存在" |
| 引导提示 | 新增"目标在别的页面 / 需先满足前置条件"的提示与"前往该界面"按钮，避免把"不在当前页"误报成"界面未实现" |
| 修掉的 bug | `lib/bridge.js` 的 `functionExists()` 此前**恒为 false**（把 C ABI 导出 `function_exists` 当成已注册动作去 Dispatch）；`/settings` 路由漏注册（点设置后内容区空白） |
| 回归用例 | 新增 `cdp-settings.mjs`（25 项）与 `cdp-tutorials-keypad.mjs`（30 项），均已登记进 `run-all.ps1` |

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
| `MF_UI/MFMath.UI.Vue/` | Vue 3 + TS 前端源码 | `src` 56 文件 / **13,248 行** |
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

### 2.3 前端（Vue 3 + TS）

- **22 个模式视图全部已迁移**：`REAL_VIEWS` 9 项 + `CalcView` 13 项 = 导航全部 22 项，**没有路由还在用占位页**。
- 外观系统：10 套配色 + 形状/疏密/字体四维 + 跟随系统 + 实时预览卡（**超出 v1**：v1 只有 4 套且靠按钮循环）。
- 控制台：CodeMirror 6、语法包按语言惰性加载、可选组件（CPython / MinGW）安装。
- **教程系统（本轮新增）**：18 篇 / 66 步 / 52 示例 / 42 FAQ；目录页、正文页（概述/步骤/示例表/FAQ/标记已学）、示例库、首次启动欢迎窗、引导遮罩与状态机。
- **数学键盘（本轮新增）**：126 键 / 6 分类，键面文字与分类顺序与 v1 一致；插入值全部 LaTeX 化；符号搜索、最近使用、收藏、页签与显隐记忆。

### 2.4 宿主（C#）

`mf`(引擎桥) · `win`(窗口) · `con`(控制台) · ComponentDownload（组件下载，含断点续传 + SHA-256 校验 + zip 解包）。
构建 **0 警告 0 错误**；引擎 DLL 与 5 个依赖经 csproj 相对路径自动带入输出，前端 `dist` 自动填入 `wwwroot`。

### 2.5 版本管理现状

| 仓库 | 提交数 | 跟踪文件 | 工作区 |
| --- | --- | --- | --- |
| `Multifunctional-Mathematics-v2.0`（新） | 2 | 396 | 干净 |
| `cppcshap` | 1（本轮首次纳入） | 725 | 干净 |
| `Multifunctional-Mathematics`（v1） | 有历史 | 324+ | 干净 |
| `MVS官网` | 13 | 231 | **1 处未提交**（见 §3.4 第 6 条） |

### 2.6 已通过的验证（均可复现）

| 验证 | 命令 | 结果 |
| --- | --- | --- |
| 引擎构建 | `cmake -S MF_Mathematics -B MF_Mathematics/build -G "Visual Studio 18 2026" -A x64` + `cmake --build ... --target mf_mathematics` | 成功 |
| 引擎准确性 | 施 `MF_ACC_DLL=<v2.0 的 dll>` 后跑准确性套件 | **2180 / 0 / 覆盖 424** |
| 教程与键盘自检 | `npm run check:ui` | 通过（引导目标无静默失效、126 键对齐） |
| 前端构建 | `npm run build` | 通过（prune-fonts 另删 38 个冗余字体省 0.767 MB） |
| 宿主构建 | `dotnet build MFMath.Host -c Release --no-incremental` | 0 警告 0 错误 |
| **端到端** | 启动宿主（CDP 9222）→ `node tests/cdp-tutorials-keypad.mjs` | **30 项断言全通过** |

---

## 三、缺什么

### 3.1 用户可感知的功能缺口

| 功能 | v1 有吗 | v2.0 现状 | 影响 |
| --- | --- | --- | --- |
| **AI 助手** | 有（`MF_AI` + 对话窗） | 无 | 大：直接决定"查看步骤"能否接通 |
| **分步显示** | 名义上有（实际是一整块只读富文本） | 无（本轮按指示未做） | 大：依赖 §3.5 第 4 条的决策 |
| **用户系统** | 有（登录/注册/邮箱验证） | 无 | 中：站点后端已现成，只缺客户端 |
| **在线搜索** | 有（DDG / Wolfram / 自定义） | 无 | 中：顶栏"搜索"是死按钮 |
| **设置面板** | 有 | 无（顶栏"设置"弹 alert） | 中：外观已可用，但 AI/搜索/更新等配置无处可去 |
| **历史记录** | 有（计算历史对话框） | 无（顶栏"历史"是死按钮） | 中 |
| **工作区保存** | 有（但残缺：写在安装目录、3 个字段、恢复时谎报成功） | 无 | 中 |
| **自动更新** | 有（后台检测新版本） | 无 | 中：站点 `/api/version` 缺 `sha256`，需先补字段 |
| **教程引导** | 有（但 34/66 步失效） | **已完成** | — |
| **数学键盘** | 有（但 115/126 键插 Unicode） | **已完成** | — |
| 教程进度跨设备/跨重装 | 无 | 存 localStorage（重装 Win 后 WebView2 数据目录可能丢） | 小 |

### 3.2 交付与工程缺口

| 缺口 | 说明 |
| --- | --- |
| **安装包流水线** | `scripts/installer.iss`、`build-installer.ps1`、`verify-installer.ps1`、`gen_installer_assets.py`、`dist-installer/`（216 MB）全在 v1，v2.0 无法产出安装包 |
| **独立下载器** | `MFMath.Downloader` 未纳入（按你的决定） |
| **分发脚本** | `sync-engine.ps1`（把 DLL 同步到各消费方）未纳入 v2.0 |
| **桥接回归与示例** | `MFMath.Test`（152 行 C#）、`demo_cs_mf` 未纳入 |
| **打包脚本的 Python 化** | 手册/版权/图标/截图脚本是 Python，需改 Node 或 C# |
| **推送通道** | 宿主目前只有同步 host object + 轮询，**没有 C#→JS 推送**；AI 流式输出与更新进度都依赖它 |

### 3.3 Python 清零进度

**目标：实现代码只用 C++ / C# / JS·TS。当前进度约 15%。**

| 项 | 数量 | 状态 |
| --- | --- | --- |
| v1 遗留 Python 文件 | **305 个 / 61,534 行** | 未处理（其中派发层已事实上被 C#/TS 直调 C ABI 取代） |
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
7. **AI 提示词的硬约束冲突**（详见 §3.5 第 4 条）：v1 的分步提示词明确要求模型"自己完成计算，而不是解释已有的结果"。

### 3.5 待你拍板的六项（方案已写入 `PLAN-feature-completion.md` §0.4）

| # | 决策 | 为什么卡住 |
| --- | --- | --- |
| 1 | 控制台的 **Python 语言支持**是否保留 | 那是给用户写程序的可选运行时组件，不是我们的实现代码。保留与否影响"只用 C++/C#/JS·TS"的边界认定 |
| 2 | 是否允许 **Node 作为构建工具** | 打包/手册/截图需要一个脚本层。用 Node 最省事，要求纯 C# 也可行但更慢 |
| 3 | Inno Setup 的 `.iss` / CMake 的 `CMakeLists.txt` 是否算例外 | 它们是第三方工具的声明式配置。若要求严格，安装包可改 WiX/MSIX |
| 4 | **AI 分步的语义 + 步骤来源**（最要紧） | ① v1 提示词让模型自己算，与"计算用 C++"直接冲突；② v1 的"本地步骤"由 **84 个 Python 文件 / 约 600 处**产出，**属于要被清零的那一层**，而引擎信封没有 `steps` 字段 → Python 清零后本地步骤会整体消失。三条路：引擎为高频 action 补步骤输出 / 纯 AI / 混合（推荐） |
| 5 | 是否给 AI / 云功能加**登录门禁** | v1 完全没有门禁（`balance`/`is_active` 只做显示）；若加，需站点侧按 `balance` 扣减，目前后端没有这个语义 |
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

- `StoreBridge.cs`：历史与工作区落 `%LOCALAPPDATA%\MFMath\*.json`（带 `version` 字段；解析失败**报错并保留原文件**，不覆盖）；顺带接管教程进度，使它能读 v1 的 `tutorial_progress.json`（**当前缺口**，§3.1 末行）。
- `SearchBridge.cs`：三种后端（DDG / Wolfram / 自定义），放 C# 是因为 UI 跑在 `https://mfmath.local` 虚拟主机下、直连会撞 CORS 且 `appid` 不该进渲染进程；修正 v1 缺陷：缓存键加入 engine、加 TTL。
- `SettingsPanel.vue` + `HistoryPanel.vue` + `SearchPanel.vue`，把顶栏两个死按钮接上。

**验收**：三个入口全部可用；工作区跨重启保留且恢复失败会报错。

### P2 — 用户系统（纯客户端，约 3 天）

复用站点现成端点（**不需要写后端**）：`/api/login`（form-urlencoded）、`/api/register`、`/api/send-code`、`/api/verify-code`、`/api/me`、`/api/logout`、`/api/login-history`。
`AccountBridge.cs` + 令牌 DPAPI 加密持久化 + 启动静默校验 + 401 自动登出。
**注意同一批 POST 里编码不统一**：`/login`、`/verify-code` 是 form，其余是 JSON。

**验收**：与站点联调通过；离线不崩。

### P3 — AI 助手 + 分步显示（6–8 天，**依赖 §3.5 第 4 条决策**）

- `AiBridge.cs`：配置对齐 v1 的 `MF_AI/config.yaml`（含 `model_map` 角色名，删了会全链路报错）；密钥 DPAPI；流式经推送通道。
- **硬约束设计**：引擎先算 → AI 只解释 → **每一步的式子回引擎核验**（`compare_expr` / `expr_eval`），核验不过的标黄；结果区**永远**显示引擎值。
- 提示词改写：删掉"你需要自己完成计算"，改为"结论以引擎值为准"。
- 分步面板：可折叠步骤列表 + 逐步播放（v1 是一整块只读富文本，无列表无折叠无播放）。

**验收**：20 题抽检步骤式子全部经引擎核验；七种异常（断网/无密钥/密钥错/超时/取消/5xx/流中断）不崩。

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
2. 删除 A 档 `.pyd`，把 v1 的 Python 后端明确标记为"仅历史参考"。
3. 把 v2.0 的回归套件（现有 43 个 CDP + 新增教程键盘用例）跑成一条命令，作为后续所有改动的守门。

### 中期（1 个月）：把用户可感知的缺口补齐

4. P1（设置/历史/搜索/工作区）+ P2（用户系统）→ 顶栏两个死按钮消失，桌面端具备账号能力。
5. P3（AI + 分步）→ 接通"查看步骤"，并把"引擎先算、AI 只解释"落成机制而不是约定。
6. **关键里程碑：Python 清零完成**（打包脚本改写 + 准确性套件迁移 + `.pyd` 全删 + `math_http_service.py` 弃用）。

### 长期（季度）

7. **P5 自动更新 + P6 安装包**：形成"改代码 → 一条命令出安装包 → 站点发布 → 客户端自更新"的闭环；更新把宿主与引擎绑成一个版本单元，消除"新旧引擎混用"这类静默降级。
8. 跨平台：引擎是 CMake + 标准 C++（Eigen/SymEngine/flint 均有 Linux 版本），具备迁到 Linux/CI 的条件；届时准确性套件可以在 CI 上自动跑（现在是手工跑）。
9. 语法/交互深化：把 v1 的 `math_guard` 复杂度守卫从**字符串启发式**下沉到引擎的 **AST** 判定（正则对 `\frac`、隐式乘法、多行输入会误判），并补 `complexity_report` / `suggest_actions` 这类以引擎解析器为基础的能力。
10. 产品化：教程内容与 UI 的关系反转（现在教程的 `target` 是硬编码的界面名，将来可考虑由 UI 声明"可引导点"，让教程只写业务语言）。

### 明确不做 / 推迟

- **不重建后端**：用户系统、组件清单、版本检测全部复用站点端点。
- **不重写下载能力**：直接复用 `ComponentDownload.cs`。
- **不复用已废弃的 HTTP 层**：`math_http_service.py` 与那套 `{code,data.result,msg}` 生成客户端（契约冲突，且 v2.0 走 P/Invoke）。
- **不移植死代码**：`MF_AI/agent.py`（含 Python `eval()`，绝不可照搬到 JS 的 `eval`）、`strategy.recommend` 等。
- **不照抄 v1 的引导层与外层壳**：教程遮罩、步骤展示、工作区保存均已重做；旧 JS UI（`MFMath.UI`）仅作历史回退目标。
- 推迟：更新回滚、AI 多模态、教程录制回放、离线文档全文搜索。

---

## 六、风险台账

| 风险 | 现状 | 对策 |
| --- | --- | --- |
| **AI 越权计算**（唯一能直接违反硬约束的点） | v1 就是这么做的 | 引擎先算 + 步骤回核验 + 一条 CDP 断言"结果区恒等于引擎值" |
| **静默失效**（v1 的 34/66 步、`.pyd` 陈旧、引擎版本错配都是这一类） | 已发现 3 类 | 构建期自检（`check-ui.mjs`）+ 更新按原子单元校验 + `.pyd` 删除前先补返回值 |
| `.pyd` 删除后 Python 层失效 | `numerical_integration.py` 的 5 个算法**无纯 Python 回退** | 必须与"整体退役 v1 Python 层"同步进行，不能单独删 |
| 准确性套件冻结后无法自主扩展 | 未开始 | 保留预言机源码与原始输出，新用例离线重生成 |
| 教程进度存在本地 | 已实现 localStorage | P1 的 `store` 桥迁到 `%APPDATA%`，届时可读 v1 旧进度 |
| 站点仓库有未提交的内容改写 | 见 §3.4 第 6 条 | 需要你确认是否保留 |

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
| `tests/cdp-tutorials-keypad.mjs` | 真实宿主内 30 项端到端断言，已登记进 `tests/run-all.ps1` |

## 附录 B：复现验证的三条命令

```powershell
$V2 = "C:\Users\fsafsafsa\Desktop\MVS知识库\Multifunctional系列\Multifunctional-Mathematics-v2.0"

# 1) 引擎：构建 + 准确性（2180 / 覆盖 424）
cmake -S "$V2\MF_Mathematics" -B "$V2\MF_Mathematics\build" -G "Visual Studio 18 2026" -A x64
cmake --build "$V2\MF_Mathematics\build" --config Release --target mf_mathematics

# 2) 前端：自检 + 构建
npm run check:ui --prefix "$V2\MF_UI\MFMath.UI.Vue"
npm run build    --prefix "$V2\MF_UI\MFMath.UI.Vue"

# 3) 宿主 + 端到端（教程系统与数学键盘 30 项断言）
dotnet build "$V2\MFMath.Host\MFMath.Host.csproj" -c Release --no-incremental
$env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = "--remote-debugging-port=9222"
Start-Process "$V2\MFMath.Host\bin\Release\net10.0-windows\MFMath.exe"
node "$V2\MF_UI\MFMath.UI.Vue\tests\cdp-tutorials-keypad.mjs"
```
