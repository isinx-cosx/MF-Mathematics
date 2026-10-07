# MF-Mathematics v2.0

**多功能可视化科学计算 —— Windows 桌面应用。**
C++ 数学引擎 + Vue 3 界面 + Rust/Tauri 宿主，三层在同一目录树内，自包含、可离线运行。

> 🚩 **宿主正在迁移（2026-10-07，项目所有者决定）**：**C#/.NET 宿主 `MFMath.Host/` 已废弃** ——
> 不再接受功能改动，只保留作迁移参考。接替者是 **`MFMath.Host.Rust/`**（Rust/Tauri + WebView2）。
>
> - 它的可复现验收步骤：[`MFMath.Host.Rust/docs/ACCEPTANCE.md`](MFMath.Host.Rust/docs/ACCEPTANCE.md)；
> - 打包（实测能出 NSIS 安装包 **11.11 MiB**）与**尚未真机验证的部分**：[`PACKAGING.md`](MFMath.Host.Rust/docs/PACKAGING.md)；
> - ⚠ **本文的架构图、快速开始第 3 步、运行命令与部分文档仍写的是那个废弃宿主，尚未重写** ——
>   在 Rust 宿主"安装 → 启动"的真机验证走完之前，不改成"用 Rust 跑起来"（那等于替没验过的路径背书）。
>   前端与引擎的构建方式（第 1、2 步）不受影响。
>
> 进度与文档债清单见 [`docs/PROJECT-BOARD.md`](docs/PROJECT-BOARD.md)。

微积分、代数、线性代数、概率统计、复分析、实分析、泛函分析、测度论、代数拓扑、数论、数值分析、
调和分析……**14 个学科视图**，外加 2D/3D/极坐标/复平面/向量场/几何/分形绘图、控制台、联网搜索、
AI 助手与交互式教程。

> 平台：Windows 10/11（x64） · 宿主：Rust/Tauri + WebView2（`MFMath.Host.Rust/`）· 前端：Vue 3 + Vite · 引擎：C++17

---

## 这个项目的三条纪律

不是口号，是代码里有对应机制与测试的：

**① 不编造结果。** 算不出来就说算不出来。例：不定积分 `∫xˣ dx`、`∫sin(x)/x dx`、`∫e^{−x²}dx`
返回"未实现"而不是硬给一个式子 —— 它们确实不是初等函数；未识别的拓扑空间名会**报错**，
而不是返回 `π₁(输入)` 这种看着像答案的占位串。

**② AI 不承担计算。** AI 助手能调**全部 424 个引擎函数**（工具表由引擎签名表生成，逐字一致），
但不允许自己估算数值 —— 端到端用例里有一条专门守这个约束
（`tests/cdp-ai.mjs`：「AI 不得当计算源」）。

**③ 每个修复都要留下"为什么"和"怎么证明"。** 例如本轮补的 18 条积分规则，每条都配一条
**求导自证**测试：对结果求导、再与原式数值比对（容差 1e-9）。写 `∫cos³x` 时把 `−sin³x/3`
写成了 `+`，就是这条自证以 `maxrel=0.635` 当场抓出来的 —— 一个错误的原函数比"未实现"危险得多。

> 这三条不是口号：**每一条在代码里都有对应机制、并且有可复跑的判据**。
> 完整展开（含"违反它会发生什么"与已知代价）见 [`docs/DESIGN.md`](docs/DESIGN.md)；
> 具体的架构决定与代价见 [`docs/DECISIONS.md`](docs/DECISIONS.md)。

---

## 功能一览

| 分区 | 内容 |
| --- | --- |
| **学科计算**（14 视图） | 代数、微积分、线性代数、概率论与数理统计、数值分析、数论、实分析、泛函分析、复分析、代数拓扑、测度论、调和分析、数列、解析几何 |
| **绘图** | 2D 函数（含隐函数/参数方程/极坐标）、3D 曲面、复平面、向量场、自由几何、分形 |
| **工具** | 联网搜索、控制台（Python / C++ 跑同一个引擎）、**函数工具箱**（全部 424 个引擎函数可直接调用） |
| **AI** | 助手抽屉、步骤推导、可调引擎的数学问答（流式输出、可中断） |
| **学习** | 18 篇交互式教程（带高亮引导）、示例任务库、126 键数学键盘（与 v1 对齐） |
| **系统** | 9 组设置、工作区保存/还原、结果导出为图片、账号（与站点对接）、更新检查（只提示，安装包交给浏览器）、深浅色主题 |

**离线承诺**：断网后本地计算、绘图、教程、控制台全部照常。只有联网搜索 / 账号 / AI 需要网络。

---

## 架构

```
┌──────────────────────────────────────────────────────────────┐
│  MF_UI/MFMath.UI.Vue         Vue 3 + Vite（构建成 wwwroot）    │
│  界面、路由、工作区、教程、AI 面板、函数工具箱                    │
└───────────────┬──────────────────────────────────────────────┘
                │  window.chrome.webview.hostObjects.sync.mf.Dispatch(name, json)
┌───────────────▼──────────────────────────────────────────────┐
│  MFMath.Host (已废弃)        C# / WPF + WebView2              │
│  MFMath.Host.Rust  现役      Rust/Tauri + WebView2            │
│  窗口、桥（9 个宿主对象，清单见 ACCEPTANCE.md §2）、             │
│  凭据只存宿主、HTTP 抓取、组件下载                                │
└───────────────┬──────────────────────────────────────────────┘
                │  C ABI：function_exists / math_call（**恰好两个导出**）
┌───────────────▼──────────────────────────────────────────────┐
│  MF_Mathematics              C++17（110 个 .cpp）              │
│  424 个已注册 action；SymEngine + flint + gmp + mpfr + Eigen    │
│  DLL 边界不暴露 std::string / std::vector / SymEngine::RCP      │
└──────────────────────────────────────────────────────────────┘
```

**为什么前端一行数学都不算**：所有数值/符号结果都来自引擎。前端只做参数构造、展示与编排。
这样"结论"只有一个来源，也才谈得上可复现。

> ⚠ **上图里 `MFMath.Host.Rust` 那一层是后加的，整张图还没有重画**（例如宿主对象的清单、
> 组件下载与推送通道的落点都变了）。属登记在案的文档债，见 `docs/PROJECT-BOARD.md` §3 R7。

---

## 快速开始

> ⚠ **仓库不含编译产物**（`MF_Mathematics/build/`、`dist/`、`bin/`、`obj/` 都在 `.gitignore` 里）。
> 克隆后必须走完下面三步，才能运行 `MFMath.exe`。
>
> 🚩 **下面第 3 步与运行命令写的是已废弃的 .NET 宿主**（见文首的迁移说明）。
> 前端（第 2 步）与引擎（第 1 步）照旧；宿主那一段**待 Rust 侧真机验证走完后重写**，
> 在此之前不要照着它判断"当前该怎么跑起来" —— 以 `MFMath.Host.Rust/docs/ACCEPTANCE.md` 为准。

### 前置依赖

| 用途 | 需要 |
| --- | --- |
| 引擎 | CMake ≥ 3.16、Visual Studio（C++ 工具链）、[vcpkg](https://github.com/microsoft/vcpkg) 安装 `symengine` `flint` `gmp` `mpfr` `eigen3` |
| 前端 | Node.js ≥ 18（`npm`） |
| 宿主 | **Rust** 工具链（`cargo`）+ WebView2 Runtime（Win11 自带，Win10 需安装）。共享库见 `MFMath.Host.Rust/README.md`；~~.NET SDK 10~~ 仅对已废弃的 .NET 宿主还需要 |

### 三步构建（顺序不可颠倒）

```powershell
git clone https://github.com/isinx-cosx/MF-Mathematics.git
cd MF-Mathematics

# 1) 引擎：依赖默认取 vcpkg 安装位置，可用 -D 覆盖
#    生成器 -G 按你本机的 VS 版本改（下面这行是当前使用的版本）
cmake -S MF_Mathematics -B MF_Mathematics/build -G "Visual Studio 18 2026" -A x64 `
      -DMF_SYMENGINE_ROOT="$env:VCPKG_ROOT\installed\x64-windows" `
      -DMF_EIGEN_INCLUDE_DIR="$env:VCPKG_ROOT\installed\x64-windows\include\eigen3"
cmake --build MF_Mathematics/build --config Release --target mf_mathematics

# 2) 前端
npm --prefix MF_UI/MFMath.UI.Vue install
npm --prefix MF_UI/MFMath.UI.Vue run build

# 3) 宿主（--no-incremental 必加：增量构建会掩盖 SDK 不兼容等编译错误）
dotnet build MFMath.Host/MFMath.Host.csproj -c Release --no-incremental
```

宿主 csproj 用**相对路径**引用引擎产物与前端 `dist`，`CopyToOutputDirectory=PreserveNewest`
自动跟随，所以**不会出现"跑的是旧引擎"**；但也因此顺序必须是「引擎 → 前端 → 宿主」。

### 运行

```powershell
& MFMath.Host\bin\Release\net10.0-windows\MFMath.exe
```

开发时热更新：先在 `MF_UI/MFMath.UI.Vue` 下 `npm run dev`（Vite，5173），
再运行 **Debug** 构建的宿主 —— Debug 指向 Vite dev server，不依赖 `wwwroot`。

---

## 验证与测试

四层，全部可在本机跑：

```powershell
# ① 引擎：16 个 CTest 套件
cmake --build MF_Mathematics/build --config Release
ctest --test-dir MF_Mathematics/build -C Release --output-on-failure

# ② 注册表守门：WHOLEARCHIVE 一旦失效，这个数会掉下来（而导出数依然漂亮）
& MF_Mathematics\build\bin\Release\probe_call.exe list_functions '{}'      # count 应为 424

# ③ 前端：类型检查（strict）+ 构建期自检
npm --prefix MF_UI/MFMath.UI.Vue run check

# ④ 端到端：48 个 CDP 用例，跑在一个真实的宿主会话里（`check-ui` 会校验"用例数 = 登记数"）
powershell -NoProfile -File MF_UI/MFMath.UI.Vue/tests/run-all.ps1
```

最近一次全量结果：**引擎 16/16 套件；端到端 2118 项检查全通过**；无宿主单元测试 3 组（30/18/13）。

**构建期自检**（`npm run check` 里的 `tools/check-ui.mjs`）会拦下这几类"运行时几乎不可察觉"的问题：

- 教程步骤的目标控件是否真的存在（v1 曾有 34/66 个目标控件根本不存在，却被标记"已完成"）
- 键盘键数与分类顺序是否与 v1 一致；键面是否把 LaTeX 源码当文字显示
- 引擎映射表是否有重复键（JS 后者胜，前面会变成"改了没反应"的死条目）
- **引擎模式可达性**：每个已注册模式要么能在某个页面上选到、要么显式登记进 `NOT_EXPOSED`
  并写明原因 —— 双向校验（登记了却能选到的报"过时条目"）。这项自检第一次跑就抓出
  **64 个"引擎有映射、页面根本选不到"的模式**，现已清零。

---

## 目录结构

| 路径 | 内容 |
| --- | --- |
| `MF_Mathematics/` | 引擎源码（仅 C++，110 个 `.cpp`）、`CMakeLists.txt` |
| `MF_Mathematics/tests/` | **19 个可执行目标** = 15 个 `test_*.cpp` + 4 个 `probe_*.cpp`；其中 **16 个注册进了 CTest**（15 个 `test_*` + `probe_bugs`）。`probe_call` 可不起宿主直调引擎 |
| **`MFMath.Host.Rust/`** | **现役宿主**：Rust/Tauri + WebView2，9 个宿主对象；`docs/ACCEPTANCE.md` 是验收步骤，`docs/PACKAGING.md` 是打包 |
| `MFMath.Host/` | 🚩 **已废弃**（C#/WPF 宿主）。不再接受功能改动，只留作迁移参考 —— 下面几份设计文档里凡是指向它的实现说明都已过时，见 `docs/PROJECT-BOARD.md` §3 R7 |
| `MF_UI/MFMath.UI.Vue/` | Vue 3 前端：`src/`、`tests/`（48 个 CDP 用例 + fixtures）、`tools/`（构建期自检） |
| `MF_UI/MFMath.UI.React/` | React 绘图组：被 Vue 壳内嵌（`ReactPlotView.vue`），6 个绘图页；独立跑 `npm run check:types` |
| `docs/` | 设计文档与状态记录 —— **入口是 [`docs/README.md`](docs/README.md) 这份文档地图**（六层结构与"我想知道 X 该读哪份"的查表） |
| `AGENTS.md` · `docs/PROJECT-BOARD.md` | 并行协作规约 · 工作面进度与风险台账 |

### 引擎的两个目标

| 目标 / 别名 | 类型 | 内容 |
| --- | --- | --- |
| `mf_mathematics_core`（`MFMath::engine`） | STATIC | 全部数学实现 |
| `mf_mathematics`（`MFMath::cabi`） | SHARED | 只有 `api.cpp`，导出恰好两个 C ABI 函数 |

> ⚠ 若自己另建导出 DLL 并链 `MFMath::engine`，**必须**加 `/WHOLEARCHIVE`。
> 每个 `*_api.cpp` 靠一个**没有外部引用的全局注册器**注册；不加，链接器会把这些目标文件
> 整个丢弃 → 注册表为空。这种失效是**静默的**：DLL 照常加载、`function_exists` 照常能调，
> 只是每个 action 都返回"未找到函数"。守门断言就是上面的 `count == 424`。

---

## 文档

**全部文档的入口是 [`docs/README.md`](docs/README.md)** —— 它是文档地图，也是建设进度的台账：
六层结构（README / 设计理念 / 链接层 / 引擎 / 前端 / 全面介绍软件）、"我想知道 X 该读哪份"的查表，
以及哪些已经写好、哪些还没动笔。

只需要按角色挑三份的话：

| 你是 | 先读 |
| --- | --- |
| **使用者 / 评估者** | [`docs/DESIGN-BOUNDARIES.md`](docs/DESIGN-BOUNDARIES.md)（能做什么、**不能做什么**）、[`docs/HANG-OPTIMIZATION.md`](docs/HANG-OPTIMIZATION.md)（已知慢的地方） |
| **改代码的人** | [`AGENTS.md`](AGENTS.md)（谁能改哪些文件、怎么提交）、[`docs/DESIGN.md`](docs/DESIGN.md)（为什么是这个样子）、[`docs/PROJECT-BOARD.md`](docs/PROJECT-BOARD.md)（现在到哪一步了） |
| **想知道还缺什么** | [`docs/OPEN-ITEMS.md`](docs/OPEN-ITEMS.md)（功能缺口）、[`MF_UI/BUGS.md`](MF_UI/BUGS.md)（确有证据的缺陷） |
| **调宿主 / 打包** | [`MFMath.Host.Rust/docs/ACCEPTANCE.md`](MFMath.Host.Rust/docs/ACCEPTANCE.md)、[`PACKAGING.md`](MFMath.Host.Rust/docs/PACKAGING.md) |

> 📌 这个项目里的文档分两种寿命：**手册**（只在架构真的改了才动）与**状态类**（每天在变）。
> 两者的区分与读法写在 [`docs/README.md`](docs/README.md) §0 —— 引用状态类结论时**必须看时间戳**。

---

## 已知边界（如实列出）

**完整清单在 [`docs/DESIGN-BOUNDARIES.md`](docs/DESIGN-BOUNDARIES.md)** —— 它区分四种性质不同的"没做"
（**明确不做** / **推迟** / **能力边界** / **尚未验证**），并写明每一条的推翻门槛。
本节只留三条最容易被误解的，与一条法律声明：

- **数学能力边界**：不定积分对非初等函数如实返回"未实现"（`∫xˣ dx`、`∫sin(x)/x dx`、`∫e^{−x²}dx`…），
  部分不定式极限与复变不定积分同理。**这是设计选择，不是缺陷** —— 见上文"三条纪律 ②"。
- **安装包：能出，但"装完能不能跑"还没验过**。Rust 宿主用 `tauri build --bundles nsis` **可以**产出
  NSIS 安装包（实测 **11.11 MiB**），但安装后的布局、安装/卸载、从安装目录启动**都尚未在真机上验证**
  （见 [`PACKAGING.md`](MFMath.Host.Rust/docs/PACKAGING.md) §3）。仓库本身仍不含任何编译产物/安装包。
  ⚠ 因此本文上面的「三步构建」仍是**唯一被实测跑通**的路径。
- **多语言只覆盖了一部分**：导航、顶栏、**全部 14 个学科视图**（含 415 个模式名与 184 个参数弹窗字段）
  已中英双语，可在「设置 → 外观 → 界面语言」切换并记忆；**页面正文（设置面板各行、工具/绘图/帮助页、
  lib 里的提示文案、教程正文）仍是中文**。迁移路径：把要翻的那处包一层 `t()`，再往
  `src/lib/i18n/en-*.js` 补译文 —— `npm run check` 会拦住漏译。
- **无 LICENSE（保留所有权利）**：仓库暂未提供许可证，因此依默认版权规则
  **未经作者许可不得复制、修改或分发**。这是**有意的** —— 作者保留后续授权方式的选择权。
  若你需要以其它方式使用，请联系作者。

> 另外两条已经独立的文档接管，本文不再重复（**重复就是两份真相**）：
> 崩溃**只本地记录、不上报**（`%LOCALAPPDATA%\MFMath\logs\`，可导出诊断包）见
> [`docs/DECISIONS.md`](docs/DECISIONS.md) D-008；
> 已知**慢**的地方（持续同调 O(n³)、符号矩阵 > 12×12、`roots_in_disc`…）见
> [`docs/HANG-OPTIMIZATION.md`](docs/HANG-OPTIMIZATION.md) §4。

---

## 与 v1 的关系

v2.0 从 `Multifunctional系列/Multifunctional-Mathematics/`（v1，约 1.46 GB，混合了旧 Python/Qt 后端、
旧 JS UI 与多份构建缓存）中只取走了 **Vue 前端与引擎 C++ 源码**，重写为单目录树、单一计算来源的结构。

**v1 作为应用已经不可运行、也不再维护**：它的计算全靠那套 Python 后端，而 v2 把计算全部搬进
`mf_mathematics.dll`（覆盖同样的功能）。因此 v1 的 Python 后端（277 个 `.py`）与 8 个无法重建的
二进制（`.pyd` / `inner_product.dll`）**已删除**，删前归档在
`Multifunctional系列/_archive/v1-python-backend-*.zip`（v1 自己的 git 历史里也还在）。

**唯一有意保留的是 `MF_Mathematics/tests/accuracy/`（28 个 `.py`，2180 条准确性用例）** ——
它是**测试资产**而不是运行时代码：可以对**任意**引擎 DLL 运行（用环境变量 `MF_ACC_DLL` 指定），
v2 的引擎也能拿它验一遍，所以没跟着一起清掉。其余旧 JS/Python UI、旧 Python/Qt 应用未纳入。
