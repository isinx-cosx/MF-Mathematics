# MF-Mathematics

**多功能可视化科学计算 —— Windows 桌面应用。**

微积分、代数、线性代数、概率统计、复分析、实分析、泛函分析、测度论、代数拓扑、数论、数值分析、
调和分析……**14 个学科视图**，外加 2D / 3D / 极坐标 / 复平面 / 向量场 / 几何 / 分形七种绘图、
控制台、联网搜索、AI 助手与 18 篇交互式教程。

**离线优先**：断网后本地计算、绘图、教程、控制台全部照常；只有联网搜索、账号与 AI 需要网络。

> 平台 Windows 10/11 (x64) · 引擎 C++17 · 界面 Vue 3 + Vite · 宿主 Rust + Tauri + WebView2

---

## 目录

- [这是什么](#这是什么)
- [功能](#功能)
- [架构](#架构)
- [快速开始](#快速开始)
- [验证与测试](#验证与测试)
- [项目结构](#项目结构)
- [文档](#文档)
- [已知边界](#已知边界)
- [许可证](#许可证)

---

## 这是什么

一个**单目录树、自包含**的数学工作台。它最不一样的地方是三条**写在代码里**的纪律：

**① 不编造结果。** 算不出来就说算不出来。不定积分 `∫xˣ dx`、`∫sin(x)/x dx`、`∫e^{−x²}dx`
返回**"未实现"**而不是硬给一个式子 —— 它们确实不是初等函数；未识别的拓扑空间名会**报错**，
而不是返回 `π₁(输入)` 这种看着像答案的占位串。

**② AI 不承担计算。** AI 助手能调用**全部 424 个引擎函数**（工具表由引擎签名表生成，逐字一致），
但不允许自己估算数值 —— 端到端用例里有一条专门守这个约束：假端点故意回 `1+1=3`，
断言界面不得把它当计算结果。

**③ 每个修复都要留下"为什么"和"怎么证明"。** 例如 18 条积分规则每条都配一条**求导自证**测试
（对结果求导、再与原式数值比对，容差 `1e-9`）。写 `∫cos³x` 时把 `−sin³x/3` 写成了 `+`，
就是这条自证以 `maxrel=0.635` 当场抓出来的 —— **一个错误的原函数比"未实现"危险得多**。

这些不是口号：**每一条在代码里都有对应机制，并且有可复跑的判据**。

---

## 功能

| 分区 | 内容 |
| --- | --- |
| **学科计算**（14 视图） | 代数、微积分、线性代数、概率论与数理统计、数值分析、数论、实分析、泛函分析、复分析、代数拓扑、测度论、调和分析、数列、解析几何 |
| **绘图** | 2D 函数（含隐函数 / 参数方程）、极坐标、3D 曲面、复平面、向量场、自由几何、分形 |
| **工具** | 联网搜索、控制台（Python / C++ 跑同一个引擎）、**函数工具箱**（424 个引擎函数可直接调用） |
| **AI** | 助手抽屉、步骤推导、可调引擎的数学问答（流式输出、可中断） |
| **学习** | 18 篇交互式教程（带高亮引导）、示例任务库、126 键数学键盘（键位与分类与 v1 对齐） |
| **系统** | 9 组设置、工作区保存 / 还原、结果导出为图片、账号、更新检查（只提示，安装包交给浏览器）、深浅色主题 |

---

## 架构

```
┌─ 前端 ────────────────────────────────────────────────────────────
│  MF_UI/MFMath.UI.Vue/        Vue 3 + Vite  →  构建成 wwwroot/
│  MF_UI/MFMath.UI.React/      React 绘图组（被 Vue 壳内嵌）
└─ 调用：window.chrome.webview.hostObjects.sync.mf.Dispatch(name, json)
                     │
                     ▼
┌─ 宿主 ────────────────────────────────────────────────────────────
│  MFMath.Host.Rust/           Rust + Tauri + WebView2
│  9 个宿主对象 / 84 个方法（窗口、存储、搜索、账号、更新、控制台…）
└─ 调用：C ABI，恰好两个导出
                     │
                     ▼
┌─ 引擎 ────────────────────────────────────────────────────────────
│  MF_Mathematics/             C++17，110 个 .cpp（不含 build/、tests/）
│  424 个已注册 action；SymEngine + flint + gmp + mpfr + Eigen
└─ DLL 边界不暴露 std::string / std::vector / SymEngine::RCP
```

**为什么前端一行数学都不算**：所有数值与符号结果都来自引擎，前端只做参数构造、展示与编排。
这样"结论"只有一个来源，也才谈得上可复现。

---

## 快速开始

> ⚠ **仓库不含编译产物**（`MF_Mathematics/build/`、`dist/`、`target/`、`bin/`、`obj/` 都在 `.gitignore` 里）。
> 克隆后必须走完下面三步 —— **顺序不可颠倒**。

### 前置依赖

| 用途 | 需要 |
| --- | --- |
| 引擎 | CMake ≥ 3.16、Visual Studio（C++ 工具链）、[vcpkg](https://github.com/microsoft/vcpkg) 安装 `symengine` `flint` `gmp` `mpfr` `eigen3` |
| 前端 | Node.js ≥ 18 |
| 宿主 | Rust 工具链（`cargo`）、WebView2 Runtime（Win11 自带，Win10 需安装） |

### 三步构建

```powershell
git clone https://github.com/isinx-cosx/MF-Mathematics.git
cd MF-Mathematics

# 1) 引擎 —— 依赖默认取 vcpkg 安装位置，可用 -D 覆盖
#    生成器 -G 按你本机的 VS 版本改（下面这行是当前使用的版本）
cmake -S MF_Mathematics -B MF_Mathematics/build -G "Visual Studio 18 2026" -A x64 `
      -DMF_SYMENGINE_ROOT="$env:VCPKG_ROOT\installed\x64-windows" `
      -DMF_EIGEN_INCLUDE_DIR="$env:VCPKG_ROOT\installed\x64-windows\include\eigen3"
cmake --build MF_Mathematics/build --config Release --target mf_mathematics

# 2) 前端
npm --prefix MF_UI/MFMath.UI.Vue install
npm --prefix MF_UI/MFMath.UI.Vue run build

# 3) 宿主（Rust）—— build.rs 会把引擎 DLL 与前端 dist 同步到 exe 同目录
cargo build --release --manifest-path MFMath.Host.Rust/Cargo.toml
```

### 运行

```powershell
& MFMath.Host.Rust\target\release\mfmath-host-rust.exe
```

> **受限环境（沙箱 / 受限令牌）里另有两个开关**：把 `TEMP`/`TMP` 指到仓库内可写目录、
> 并把 `CARGO_HOME` 指到仓库内（本机 Schannel 在受限令牌下不可用）。
> 完整注意事项与逐条验收步骤见 [`MFMath.Host.Rust/docs/ACCEPTANCE.md`](MFMath.Host.Rust/docs/ACCEPTANCE.md)。

**改了前端之后**：重跑 `npm run build`，再 `cargo build` 让 `build.rs` 把新的 `dist` 同步到
exe 同目录的 `wwwroot/`；也可以用环境变量 `MF_WWWROOT` 把宿主指到别处的 UI 目录
（`MFMath.Host.Rust/src/main.rs` 的 `wwwroot_dir()`）。宿主**不内置 Vite dev server 集成**。

---

## 验证与测试

四层，全部可在本机跑：

```powershell
# ① 引擎：CTest（19 个可执行目标 = 15 个 test_*.cpp + 4 个 probe_*.cpp；其中 16 个注册进 CTest）
cmake --build MF_Mathematics/build --config Release
ctest --test-dir MF_Mathematics/build -C Release --output-on-failure

# ② 注册表守门：/WHOLEARCHIVE 一旦失效，这个数会掉下来（而导出数依然漂亮）
& MF_Mathematics\build\bin\Release\probe_call.exe list_functions '{}'   # count 应为 424

# ③ 前端：类型检查 + 引擎签名 + 构建期自检
npm --prefix MF_UI/MFMath.UI.Vue run check

# ④ 端到端：48 个 CDP 用例，跑在一个真实的宿主会话里
powershell -NoProfile -File MF_UI/MFMath.UI.Vue/tests/run-all.ps1
```

**构建期自检**（`npm run check` 里的 `tools/check-ui.mjs`）拦的是"运行时几乎不可察觉"的问题。
下面是它实跑输出（2026-10-07，exit 0）的**摘录** —— 原输出 17 行，这里去掉分隔线并按列对齐重排，
**数字未经改动**：

```text
引擎模式可达性 ：映射 415 个 / 页面并集 391 个 / 取不到 0 个
区间参数契约   ：10 个 handler / 命中模式 10 个 / 缺 interval 0 个
概率表契约     ：4 个模式 / 空表 0 个
冻结的 Vue 绘图组：6/6 个文件在位，被 import 0 处
i18n 模式名    ：415 个模式，缺译文 0 个
i18n 弹窗字段  ：186 条唯一标签，缺译文 0 条
教程引用的 target：30 个（已实现 30，待实现 0）
数学键盘       ：6 分类 / 126 键（v1 也是 126）
端到端用例     ：cdp-* 48 个，已登记 48 个
```

它拦下过的真实缺陷里有两个例子：**64 个"引擎有映射、页面根本选不到"的模式**（现已清零）；
v1 曾有 **34/66 个教程目标控件根本不存在**却被标记"已完成"。

---

## 项目结构

| 路径 | 内容 |
| --- | --- |
| `MF_Mathematics/` | 引擎源码（C++17，110 个 `.cpp`，不含 `build/` 与 `tests/`）+ `CMakeLists.txt`；`tests/` 下 19 个可执行目标 |
| `MFMath.Host.Rust/` | **宿主**：Rust + Tauri + WebView2，9 个宿主对象。`docs/ACCEPTANCE.md` 是验收步骤，`docs/PACKAGING.md` 是打包 |
| `MF_UI/MFMath.UI.Vue/` | Vue 3 界面：`src/`、`tests/`（48 个 CDP 用例 + fixtures）、`tools/`（构建期自检） |
| `MF_UI/MFMath.UI.React/` | React 绘图组：被 Vue 壳内嵌，6 个绘图页；独立跑 `npm run check:types` |
| `MFMath.Host/` | 早期 C#/.NET 宿主，**已停止演进**，保留作迁移参考（其 `python/`、`cpp/` 仍是控制台组件的来源） |
| `docs/` | 文档 —— 入口是 [`docs/README.md`](docs/README.md) 这份**文档地图** |
| `tools/` | 仓库级小工具（如行数统计） |

### 引擎的两个构建目标

| 目标 / 别名 | 类型 | 内容 |
| --- | --- | --- |
| `mf_mathematics_core`（`MFMath::engine`） | STATIC | 全部数学实现 |
| `mf_mathematics`（`MFMath::cabi`） | SHARED | 只有 `api.cpp`，导出**恰好两个** C ABI 函数 |

> ⚠ 若自己另建导出 DLL 并链 `MFMath::engine`，**必须**加 `/WHOLEARCHIVE`。
> 每个 `*_api.cpp` 靠一个**没有外部引用的全局注册器**注册；不加，链接器会把这些目标文件整个丢弃
> → 注册表为空。这种失效是**静默的**：DLL 照常加载、`function_exists` 照常能调，
> 只是每个 action 都返回"未找到函数"。守门断言就是上面的 `count == 424`。

---

## 文档

全部文档的入口是 **[`docs/README.md`](docs/README.md)** —— 它是一份文档地图，
按"我想知道 X 该读哪份"编排，并区分**手册**（只在架构真的改了才动）与**状态类**（每天在变，
引用时必须看时间戳）。

按角色挑几份：

| 你是 | 先读 |
| --- | --- |
| **使用者 / 评估者** | [`docs/manual/README.md`](docs/manual/README.md)（能做什么、**不能做什么**）、[`docs/manual/WORKFLOWS.md`](docs/manual/WORKFLOWS.md)、[`docs/manual/FAQ.md`](docs/manual/FAQ.md) |
| **想读懂代码** | [`docs/DESIGN.md`](docs/DESIGN.md)（为什么是这个样子）、[`docs/engine/README.md`](docs/engine/README.md)、[`docs/ui/ENGINE-BINDING.md`](docs/ui/ENGINE-BINDING.md)、[`docs/link/README.md`](docs/link/README.md) |
| **想知道还缺什么** | [`docs/DESIGN-BOUNDARIES.md`](docs/DESIGN-BOUNDARIES.md)（明确不做 / 推迟 / 尚未验证）、[`docs/OPEN-ITEMS.md`](docs/OPEN-ITEMS.md) |
| **参与开发** | [`AGENTS.md`](AGENTS.md)（文件所有权与提交规约）、[`docs/DECISIONS.md`](docs/DECISIONS.md)（每条决定都写了代价） |
| **调宿主 / 打包** | [`MFMath.Host.Rust/docs/ACCEPTANCE.md`](MFMath.Host.Rust/docs/ACCEPTANCE.md)、[`PACKAGING.md`](MFMath.Host.Rust/docs/PACKAGING.md) |

---

## 已知边界

完整清单见 [`docs/DESIGN-BOUNDARIES.md`](docs/DESIGN-BOUNDARIES.md)，它区分四种性质不同的"没做"。
这里只列最容易被误解的几条：

- **数学能力边界**：不定积分对非初等函数如实返回"未实现"，部分不定式极限与复变不定积分同理。
  这是**设计选择**，不是缺陷。
- **多语言只覆盖了一部分**：导航、顶栏、全部 14 个学科视图（含 415 个模式名与 186 条参数弹窗标签）
  已中英双语，可在「设置 → 外观 → 界面语言」切换并记忆；**页面正文与教程正文仍是中文**。
  迁移路径明确：把要翻的那处包一层 `t()`，再补 `src/lib/i18n/en-*.js` —— `npm run check` 会拦住漏译。
- **安装包尚未真机验证**：宿主可以出 NSIS 安装包，但"安装 → 启动"这条路径**还没有人在真机上走过**。
  因此上面的「三步构建 + 直接运行」是目前唯一被实测跑通的路径。
- **崩溃只本地记录，不联网上报**：写进 `%LOCALAPPDATA%\MFMath\logs\`，可由用户在
  「设置 → 存储与数据 → 导出诊断包」主动交出。数学工具的用户不该因为一次崩溃被上传任何东西。

---

## 许可证

**暂未提供许可证（保留所有权利）。** 因此依默认版权规则，**未经作者许可不得复制、修改或分发**。
这是作者有意保留的选择权 —— 若你需要以其它方式使用，请联系作者。

---

## 与 v1 的关系

v2.0 从 v1 中只取走了 **Vue 前端与引擎 C++ 源码**，重写为单目录树、单一计算来源的结构。
（v1 树混合了旧 Python/Qt 后端、旧 JS UI 与多份构建缓存，迁移时约 1.4 GB，现在更大。）

v1 作为应用已不可运行、也不再维护：它的计算全靠那套 Python 后端，而 v2 把计算全部搬进了
`mf_mathematics.dll`。因此 v1 的 Python 后端（277 个 `.py`）与 8 个无法重建的二进制已删除，
删前已归档。

**唯一有意保留的是 v1 树里的那套准确性用例**（28 个 `.py`，2180 条）：

```text
../Multifunctional-Mathematics/MF_Mathematics/tests/accuracy/    ← 在 v1 树，不在本仓库
```

它是**测试资产**而不是运行时代码：可以对**任意**引擎 DLL 运行（用环境变量 `MF_ACC_DLL` 指定），
v2 的引擎也能拿它验一遍。本仓库的 `MF_Mathematics/tests/` 下只有 `test_*.cpp` 与 `probe_*.cpp`。
