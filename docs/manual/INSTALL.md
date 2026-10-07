# 安装、构建与运行

> **本文只回答一个问题：怎么构建、怎么运行，安装包做到什么程度了。**
>
> 与同层其它文档的分工：
> - [README.md](README.md) —— 为谁做、能做什么、**不能做什么**（用户第一眼该看的那份）；
> - [FEATURES.md](FEATURES.md) —— 功能全表（14 学科视图 / 6 类绘图 / 工具 / AI / 学习 / 系统）；
> - [WORKFLOWS.md](WORKFLOWS.md) —— **装起来之后**怎么用：算题、画图、工作区、导出；
> - [TROUBLESHOOTING.md](TROUBLESHOOTING.md) —— 起不来、白屏、卡死、日志与诊断包在哪；
> - [FAQ.md](FAQ.md) —— 为什么算不出来、离线承诺、许可证这类零散问题；
> - 跨层权威源：宿主验收步骤 [ACCEPTANCE.md](../../MFMath.Host.Rust/docs/ACCEPTANCE.md)、
>   出包与**未验证部分** [PACKAGING.md](../../MFMath.Host.Rust/docs/PACKAGING.md)、
>   "尚未验证"的完整清单 [DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) §5。

**核对时间**：2026-10-07 11:07（本机，`master`）。
**纪律**：本文每个数字都带**出处**（`文件:行`、可复跑命令、或另一份文档的小节），
并写成"**2026-10-07 在 <产物> 上实测**"。没有出处的数字一律不写 —— 见 [AGENTS.md](../../AGENTS.md) §5。

---

## 0. 先接受三个前提

| # | 前提 | 依据 |
| --- | --- | --- |
| 1 | **git 里没有任何编译产物** —— 克隆下来是一棵纯源码树，没有 `build/`、没有 `dist/`、没有 exe | `git ls-files` 里没有 `(build\|dist\|target\|bin\|obj)/` 下的任何路径；`git check-ignore -q` 对 `MF_Mathematics/build`、`MF_UI/MFMath.UI.Vue/dist`、`MFMath.Host.Rust/target`、`MFMath.Host/bin` 全部退出码 0（本机 2026-10-07 11:0x 实测） |
| 2 | **三步构建（引擎 → 前端 → 宿主）是目前唯一被实测跑通的路径** | `README.md:233-234`；本文 §3 |
| 3 | **"装完安装包能不能跑"没有被任何人验过** —— 能出包，但安装后的布局、安装/卸载、从安装目录启动都缺实测 | `PACKAGING.md` §3（表里 5 行 ❌/⚠️）；`DESIGN-BOUNDARIES.md` §5 第 1 行 |

> ⚠ **本文不是"照着做就能跑起来"的保证。** 本文能保证的只有一件事：
> **§3 那三步在本机被跑通过，产物可复现**。§4 的"从构建产物直接起宿主"也被跑通过；
> **§6 的"从安装包安装后启动"没有任何人跑通过**。这两件事的差别就是本文的主线。

本机当前**存在**这些编译产物（是本机自己构建出来的，不是从 git 来的）：
`MF_Mathematics/build/`、`MF_UI/MFMath.UI.Vue/dist/`、`MF_UI/MFMath.UI.React/dist/`、
`MFMath.Host.Rust/target/`、`MFMath.Host/bin|obj/`
（`Test-Path` 逐个实测，2026-10-07 11:0x）。它们全部被 `.gitignore` 收容（见 §9）。

---

## 1. 前置依赖

| 用途 | 需要什么 | 本机实测版本 | 出处 / 判据 |
| --- | --- | --- | --- |
| 引擎构建 | **CMake ≥ 3.16** | `cmake 4.4.0` | `MF_Mathematics/CMakeLists.txt:1`（`cmake_minimum_required(VERSION 3.16)`）；版本由 `cmake --version` 实测 |
| 引擎构建 | **Visual Studio（C++ 工具链）** | `Visual Studio Community 2026`，安装版本 `18.10.12224.181` | README 的三步构建用的生成器是 `Visual Studio 18 2026`（`README.md:117`）；本机 `vswhere -latest -products * -property displayName` / `-property installationVersion` 实测；生成器可用性由 `cmake --help` 列出 `* Visual Studio 18 2026` 证实 |
| 引擎依赖 | **[vcpkg](https://github.com/microsoft/vcpkg) 安装 `symengine` `flint` `gmp` `mpfr` `eigen3`** | 本机根目录 `C:\Users\fsafsafsa\vcpkg`，`installed/x64-windows` 下 `include/symengine`、`include/eigen3`、`lib/flint.lib`、`lib/gmp.lib`、`lib/mpfr.lib` 均存在 | 包清单 `README.md:105`；本机路径由 `CMakeCache.txt` 的 `MF_SYMENGINE_ROOT` / `MF_EIGEN_INCLUDE_DIR` 与 `Test-Path` 实测 |
| 前端构建 | **Node.js ≥ 18（`npm`）** | `node v26.3.1`、`npm 11.16.0` | 门槛出自 `README.md:106`。⚠ 这条**不是**被强制的：`MF_UI/MFMath.UI.Vue/package.json` 里**没有 `engines` 字段**（全文读过），所以"低于 18 会怎样"**未证实** |
| 宿主构建 | **Rust 工具链（`cargo`）** | `cargo 1.96.0 (30a34c682 2026-05-25)`、`rustc 1.96.0 (acfdaa20 2026-05-25)` | `README.md:107`；`Cargo.toml:4` 是 `edition = "2024"`（需要较新的工具链 —— 具体最低版本**未证实**，仓库里**没有** `rust-toolchain.toml`） |
| 宿主构建 | Windows 上还需要 **MSVC 的 C/C++ 编译器**（构建期要 `cl.exe`） | 同上那个 VS 2026 | `Cargo.toml:23` 记着一次实测：`aws-lc-sys` 的现场编译在 `cl.exe` 上报 `D8050`「命令行太长」，因此改用 ring 后端（`Cargo.toml:22-26`） |
| 运行（宿主） | **WebView2 Runtime**（Win11 自带；Win10 需装 Evergreen Runtime） | `pv=149.0.4022.80`，`name=Microsoft Edge WebView2 Runtime` | 说明见 `README.md:107`、`PACKAGING.md:138`；本机由 `HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` 实测 |
| 宿主构建 | **共享库**（Tauri 侧的运行时依赖） | `MFMath.Host.Rust/README.md` 里列了它们 | `README.md:107` 指向 `MFMath.Host.Rust/README.md`。⚠ 那份 README 的**状态头是过时的**，见 §10 债 4 |
| ~~.NET~~ | **.NET SDK 10 已不再需要** | 本机 `dotnet 10.0.401`（仅为残留） | `README.md:107`："~~.NET SDK 10~~ 仅对已废弃的 .NET 宿主还需要"；废弃决定见 §7 |

### 1.1 一个会咬人的默认值

`MF_Mathematics/CMakeLists.txt:13-20` 的两个 `CACHE PATH` 默认值**写死了作者的绝对路径**：

```cmake
set(MF_EIGEN_INCLUDE_DIR "C:/Users/fsafsafsa/vcpkg/installed/x64-windows/include/eigen3" ...)
set(MF_SYMENGINE_ROOT    "C:/Users/fsafsafsa/vcpkg/installed/x64-windows" ...)
```

所以**别的机器上必须显式用 `-D` 覆盖这两个变量**（README 的第三步命令就是这么写的，
`README.md:118-119`）。本机 `CMakeCache.txt` 实测的正是这两条路径 —— 也就是说本机的"默认值恰好对"。

---

## 2. 目录与产物对照（后面每一步都落在这里）

| 步骤 | 产出 | 本机实测大小 / 数量 |
| --- | --- | --- |
| 1 引擎 | `MF_Mathematics/build/bin/Release/` 下 `mf_mathematics.dll` + 5 个依赖 DLL | 6 个 DLL，合计 **21.78 MB**（`Get-ChildItem *.dll \| Measure-Object Length -Sum`，2026-10-07） |
| 2 前端 | `MF_UI/MFMath.UI.Vue/dist/` | **73 个文件 / 3.90 MB**（同步进 `target/release/wwwroot` 后实测） |
| 3 宿主 | `MFMath.Host.Rust/target/release/mfmath-host-rust.exe` | **13.90 MiB** |
| 3 宿主（顺带） | `target/release/wwwroot/`、`python/`、`cpp/` | 由 `build.rs` 自动同步，见 §3.3 |
| 4 出包（未验证安装） | `target/release/bundle/nsis/MF-Mathematics_2.0.0_x64-setup.exe` | **11.11 MiB**（文件时间 2026-10-07 10:00:22） |

> 引擎的 6 个 DLL 逐个来自 `MF_Mathematics/CMakeLists.txt:156-159` 这段 `foreach`：
> `symengine-0.14.dll` `flint-24.dll` `gmp-10.dll` `mpfr-6.dll` `pthreadVC3.dll`
> 从 `${MF_SYMENGINE_ROOT}/bin/` 拷到产物目录 —— 也就是说 **vcpkg 的 `bin/` 必须齐全**。
> ⚠ `README.md:105` 的 vcpkg 清单只有 5 个包（不含 pthreads），而运行需要 `pthreadVC3.dll`。
> 本机该文件在 `C:\Users\fsafsafsa\vcpkg\installed\x64-windows\bin\pthreadVC3.dll`，
> vcpkg 的 `share/` 下有 `pthread` / `pthreads` / `PThreads_windows` / `PThreads4W` 四个登记项
> —— 但它**是不是**由 `symengine`/`flint` 传递安装的、还是需要显式 `vcpkg install pthreads`，
> **未证实**。复核方法：干净 vcpkg 里只装那 5 个包，看 `installed/x64-windows/bin/` 有没有 `pthreadVC3.dll`。

---

## 3. 三步构建（顺序不可颠倒）

三步的完整命令出自 `README.md:109-128`；**顺序理由**也在那里（`README.md:130-131`）：
宿主的 `build.rs` 用相对路径取引擎产物与前端 `dist`，**所以必须先有 1 和 2**。

### 3.1 第一步 · 引擎

```powershell
# 生成器 -G 按你本机的 VS 版本改（下面这行是当前使用的版本）
cmake -S MF_Mathematics -B MF_Mathematics/build -G "Visual Studio 18 2026" -A x64 `
      -DMF_SYMENGINE_ROOT="$env:VCPKG_ROOT\installed\x64-windows" `
      -DMF_EIGEN_INCLUDE_DIR="$env:VCPKG_ROOT\installed\x64-windows\include\eigen3"
cmake --build MF_Mathematics/build --config Release --target mf_mathematics
```

出处：`README.md:117-120`。本机实测：生成器 = `Visual Studio 18 2026`、平台 = `x64`
（`CMakeCache.txt` 的 `CMAKE_GENERATOR` / `CMAKE_GENERATOR_PLATFORM`）。

- 目标名 `mf_mathematics` 出自 `MF_Mathematics/CMakeLists.txt:167`（`add_library(mf_mathematics SHARED api.cpp)`）。
- 它的静态内核是 `mf_mathematics_core`（`CMakeLists.txt:28`），导出面**恰好两个** C ABI 函数。
- ⚠ **`/WHOLEARCHIVE` 不能省**（`CMakeLists.txt:182-183` 已经加好）：自己另建导出 DLL 时漏掉它，
  注册表会**静默**变空。守门断言见 §8。
- ⚠ **`$env:VCPKG_ROOT` 在本机未设置**（实测：未设置）。README 的命令里用了它，
  所以要么先设这个变量，要么把 `-D` 的值写成你自己的 vcpkg 绝对路径。

### 3.2 第二步 · 前端

```powershell
npm --prefix MF_UI/MFMath.UI.Vue install
npm --prefix MF_UI/MFMath.UI.Vue run build
```

出处：`README.md:123-124`。`build` 脚本 = `vite build && node scripts/prune-fonts.mjs`
（`MF_UI/MFMath.UI.Vue/package.json` 的 `scripts.build`）。

另外两个**不是构建**但属于这一面的闸门（`package.json` 的 `check`）：
`npm run check` = `check:types` + `check:signatures` + `check:args` + `check:ui`，
期望 exit 0（判据：`AGENTS.md` §2 的 B 面行）。
React 绘图组的独立类型检查是 `npm run check:types --prefix MF_UI/MFMath.UI.React`。

### 3.3 第三步 · 宿主

```powershell
$repo = "<仓库根>"
$env:TEMP = "$repo\.tmp-build"; $env:TMP = $env:TEMP     # 沙箱下 %TEMP% 不可写会让 cl.exe 报 D8050
$env:CARGO_HOME = "$repo\.cargo-home"                    # 不要写用户级 CARGO_HOME
cd "$repo\MFMath.Host.Rust"
cargo build --message-format short                       # 期望：Finished，且 warning 数 = 0
```

出处：`ACCEPTANCE.md` §0.1（`:14-20`），判据 `AGENTS.md` §2 的 A 面行（`Finished`，warning = 0）。
上面两个环境变量出自 `AGENTS.md` §4 的并发互斥表。

`build.rs` 会自动把三样东西同步到 exe 同目录，**这一步不需要你手工做**：

| 来源 | 目标 | 出处 |
| --- | --- | --- |
| `MF_Mathematics/build/bin/Release/` 的 6 个 DLL（可用 `MF_ENGINE_BIN` 覆盖） | exe 同目录 | `build.rs:27-33`、`:90-92` |
| `MF_UI/MFMath.UI.Vue/dist` | `wwwroot/` | `build.rs:114-117` |
| `MFMath.Host/python`、`MFMath.Host/cpp` | `python/`、`cpp/` | `build.rs:137` |

**这三件事的缺失都是"只打 warning、不报错"**，所以很容易在"构建成功"的假象下跑出一个白屏或算不了数的宿主：

- 找不到引擎产物 → `build.rs:104-108` 打 warning，文案里明说"宿主能起来但算不了数"；
- 找不到 `/dist/index.html` → `build.rs:120-124` 打 warning，页面会**退回内嵌资产、URL 变成 `tauri.localhost`**；
- 找不到控制台门面 → `build.rs:143-147` 打 warning，"控制台能起，但组件安装会失败"。

> ⚠ **已废弃的 `MFMath.Host/` 目录仍是这一步的构建输入**：`build.rs:137` 读的是
> `MFMath.Host/python`（实测 1 个文件 `mfmath.py`）与 `MFMath.Host/cpp`
> （实测 2 个文件 `mfmath.hpp`、`mfmath_autorun.hpp`）。`build.rs:134-135` 的注释解释了原因
> （"这三个文件在仓库里只有那一份，两个宿主共用"）—— **注释与代码一致**，
> 但含义是：**删掉废弃目录会让控制台组件安装失败**。登记在 §10 债 5。

---

## 4. 运行（构建产物直起，**这条被跑通过**）

Rust 宿主的运行方式**不在 README 的「运行」小节里** —— 那里写的是已废弃的 .NET 宿主
（`README.md:133-137`，README 自己在 `:97-99` 声明了这一点）。**以 `ACCEPTANCE.md` 为准。**

### 4.1 必须跑到工作区外（这是最容易被跳过的一步）

```powershell
$repo = "<仓库根>"
$run = "$env:TEMP\mfhost-run"
node "$repo\MFMath.Host.Rust\tools\sync-wwwroot.mjs" --exe "$run\mfmath-host-rust.exe"
Start-Process "$run\mfmath-host-rust.exe"
```

出处：`ACCEPTANCE.md` §0.2（`:35-38`）与 §0.3（`:45-46`）。
**为什么必须**：工作区内的进程写不了 `%LOCALAPPDATA%`，日志/设置会**静默失败**（`ACCEPTANCE.md:33-34`）。
反向证据也在：在 `target\release\…` 里直接跑 `--selftest-common` 会得 **9/1**，
失败项是 zip 往返的 `拒绝访问 (os error 5)`（`PACKAGING.md:85-89`，指向 `selftest.rs:75`）——
这属于**环境没准备好**，不是产品缺陷。

⚠ `sync-wwwroot.mjs` 会**清空目标 `wwwroot`**，因此它**拒绝**把 exe 目录当目标
（`ACCEPTANCE.md:40-41`）—— 别绕过这道闸门。

### 4.2 起来之后，三条可判定的现象

| 现象 | 期望值 | 怎么读 | 出处 |
| --- | --- | --- | --- |
| 页面 URL | **`https://mfmath.local/index.html`** | `curl.exe -s http://127.0.0.1:9222/json/list \| Select-String mfmath` | `ACCEPTANCE.md:52-56`；URL 是契约（48 个用例按它找页面），理由见 [HOSTS.md](../link/HOSTS.md) §1 |
| 宿主对象 | **9 个**（`mf`16 `win`9 `sys`8 `diag`1 `push`3 `update`6 `account`19 `search`12 `con`10），**没有 `ai`** | 启动日志逐个打印对象与方法数 | `ACCEPTANCE.md` §2（`:70-87`）；`[HOSTS.md](../link/HOSTS.md):17` |
| 无头自检 | `--selftest-jobs` **5/5**、`--selftest-common` **10/0** | 直接跑 exe，不起窗口 | `ACCEPTANCE.md` §1（`:64-66`）；release 构建在工作区外也实测同一组数字（`PACKAGING.md:82`） |

`ai` **刻意不在**这 9 个里 —— 这是 [DECISIONS.md](../DECISIONS.md) D-004 的直接后果，
判据是"`cdp-ai` 必须在一个**没有 `ai` 宿主对象**的宿主上全绿"（`ACCEPTANCE.md:86-87`）。

### 4.3 端到端用例（可选，但它是"跑通了"的最强证据）

```powershell
$env:MF_HOST_EXE = "$env:TEMP\mfhost-run\mfmath-host-rust.exe"
cd "$repo\MF_UI\MFMath.UI.Vue\tests"
pwsh -NoProfile -ExecutionPolicy Bypass -File .\run-all.ps1
```

出处：`ACCEPTANCE.md` §3（`:93-97`）。登记在册 **26 组**（`ACCEPTANCE.md:99-106`），
`tests/` 下共 **48** 个 `cdp-*.mjs`（本机 `Get-ChildItem -Filter 'cdp-*.mjs'` 实测 = 48；
与 `PROJECT-BOARD.md:318` 的"48 / 48"一致）—— 差额就是"未登记进 run-all、需要时单独跑"的那些。

⚠ **跑全量前先确认没有别人在驱动同一个页面**：`AGENTS.md` §4 的并发规矩；
违反它一次会得到"整套看起来像产品回归的假失败"（`PROJECT-BOARD.md` §3 R1 结案、R4）。
⚠ **全量的 fail 数不能直接当回归数**，只有"单独跑也红"的才算真失败（`ACCEPTANCE.md:132-133`）。

### 4.4 一个**未证实**的点：Rust 宿主没有"Debug 指向 Vite dev server"

`README.md:139-140` 说"Debug 构建的宿主指向 Vite dev server（5173）"—— 那是**已废弃 .NET 宿主**的行为。
Rust 侧实测：`tauri.conf.json`（全文 38 行）里**没有 `devUrl`**；
`main.rs` 里与 UI 目录有关的只有 `MF_WWWROOT`（`main.rs:301`）与 `MF_WEBVIEW2_DIR`（`main.rs:226-229`）；
`mfmath.local` 的虚拟主机映射是硬契约（`main.rs:309-310`）。
**结论**：Rust 宿主没有已证实的 dev-server 路径，前端改动要走"`npm run build` → 重新同步 wwwroot"。
是否存在别的 dev 机制**未证实** —— 验证方法：`cargo run` 起 debug 宿主，看它加载的是 exe 同目录的
`wwwroot` 还是某个 http origin（读 `%LOCALAPPDATA%\MFMath\logs\app.log` 的启动行）。

---

## 5. 三个可选的环境开关

| 变量 | 作用 | 默认 | 出处 |
| --- | --- | --- | --- |
| `MF_WWWROOT` | 指到别处的 `wwwroot` | exe 同目录的 `wwwroot` | `main.rs:301`；`HOSTS.md` §1.1 |
| `MF_WEBVIEW2_DIR` | WebView2 用户数据目录（**与 C# 宿主同名开关**） | `%LOCALAPPDATA%\MFMath\webview2` | `main.rs:226-229`；`HOSTS.md` §1.1 |
| `MF_ENGINE_BIN` | 覆盖 `build.rs` 取引擎 DLL 的源目录 | `<根>/MF_Mathematics/build/bin/Release` | `build.rs:90-92` |

`MF_WEBVIEW2_DIR` 存在的理由是"多个宿主实例不能共用同一数据目录"：
撞上会得到 `0x800700AA`，宿主的提示文案在 `main.rs:321`（`HOSTS.md:46-49`）。

---

## 6. 安装包：到哪一步了（**这一节的"没验过"是真的没验过**）

### 6.1 验过的部分

| 事项 | 结果 | 出处 |
| --- | --- | --- |
| 能出 NSIS 安装包 | ✅ `target/release/bundle/nsis/MF-Mathematics_2.0.0_x64-setup.exe`，**11.11 MiB** | `PACKAGING.md:10-11`；本机 2026-10-07 实测同一文件名与体积（时间 10:00:22） |
| 出包耗时 | 首次 release 编译 **2 分 01 秒**；之后改配置重打包 **38.7 秒** | `PACKAGING.md:70` |
| NSIS 工具链来源 | 首次打包从 GitHub 下 NSIS 3.11 与 `nsis_tauri_utils.dll`，校验哈希后解压（日志有 `validating hash`） | `PACKAGING.md:71` |
| 安装器元数据 | 文件版本 2.0.0、产品名 `MF-Mathematics`、manifest 是 **`asInvoker`** | `PACKAGING.md:97` |
| 出包命令可复现 | 见 `PACKAGING.md` §2（`:39-68`），含**必须**配的 `resources` 覆盖 | `PACKAGING.md` §2 |

**`resources` 覆盖为什么是必须的**（`PACKAGING.md:18-33`）：打包器**不认识** `build.rs` 同步的那三样
（引擎 6 个 DLL 21.78 MB、`wwwroot/` 3.90 MB / 73 个文件、`python/` + `cpp/`），
Tauri 只把 exe 和 `bundle.resources` 列出的东西放进安装包。**漏了就装出一个只有 exe 的包** ——
页面白屏（没有 `wwwroot`）、算不了数（没有 DLL）、控制台装不上组件（没有 `python/mfmath.py`）。

### 6.2 **没验过**的部分（照抄 `PACKAGING.md` §3 的口径，不要美化）

| 想验的 | 结果 | 失败分类 |
| --- | --- | --- |
| 静默安装到指定目录 | ❌ 两次都失败：`Start-Process … /S /D=<dir>` 报 `ERROR_CANCELLED`；改 `& <setup> /S /D=<dir>` 则静默不生效、`$LASTEXITCODE` 为空、目标目录没被创建 | **环境没准备好**（需要审批的动作被自动拒绝），**不是打包做错了** |
| 安装目录布局（exe + 6 DLL + `wwwroot/` + `python/` + `cpp/`） | ❌ 未能实测（依赖上一条） | 环境 |
| 包内是否真收了那 25.7 MB 资产 | ⚠️ **无法证实也无法证伪**：NSIS 文件表整体压缩，扫描明文必然扫不到；体积也不决定性 | — |
| 卸载后程序目录清空、`%LOCALAPPDATA%\MFMath` 保留 | ❌ 未实测 | 环境 |
| `installMode` 是否真的生效 | ⚠️ 两次构建（默认 / `currentUser`）安装表现完全相同 | — |

> 🚩 `PACKAGING.md:97` 明确要求：**"默认需要管理员"这个结论我没有证据，不要写进任何文档**。
> 本文遵守这一条 —— 本文只说"已证实的是 manifest 是 `asInvoker`"。

### 6.3 真机上要走的五步（**交付前必做，本文不替你背书**）

逐字照 `PACKAGING.md` §4（`:104-116`）：① 双击安装器按提示装（每用户）；② 打开安装目录逐项确认
`MF-Mathematics.exe`、6 个引擎 DLL、`wwwroot\index.html`、`python\mfmath.py`、`cpp\`；
③ 启动后核 `curl.exe -s http://127.0.0.1:9222/json/list` 的 URL 必须是 `https://mfmath.local/index.html`、
`%LOCALAPPDATA%\MFMath\logs\app.log` 里必须有 **9 个宿主对象**的注册行**且没有 `ai`**、随手算一条要能出数；
④ 附着跑 `pwsh -File tests\run-all.ps1 -NoLaunch`（**不要另起宿主**）；⑤ 卸载后程序目录应清空、
`%LOCALAPPDATA%\MFMath`（设置/日志/组件/工作区）**必须保留**。

**门槛也写在那里**（`PACKAGING.md:116`）：做完第 2、3 步才可以把 §2 的内联覆盖**固化进
`tauri.conf.json`**；做完第 5 步才算"发布形态可用"。当前 `tauri.conf.json:29` 仍是 `"active": false`
（本机实测），**和这条门槛一致** —— 不是遗漏。

### 6.4 兜底路线：zip + 手工布局（不依赖任何工具链）

`PACKAGING.md` §5（`:120-139`）给了一条随时可用的路：把 `target/release` 下
`mfmath-host-rust.exe`、`*.dll`、`wwwroot/`、`python/`、`cpp/` 拷出来打成 zip。
两个与 NSIS 的**差异**：① exe 名字（NSIS 用 `productName` → `MF-Mathematics.exe`，
cargo 产物叫 `mfmath-host-rust.exe`；程序不依赖自己的文件名）；② **没有安装/卸载与开始菜单项**。
⚠ 另外 **WebView2 运行时是系统依赖**，宿主不负责安装它，缺了会得到一条可读的启动失败提示
（`PACKAGING.md:138`）。

---

## 7. C# / .NET 宿主：已废弃（2026-10-07）

| 项 | 内容 | 出处 |
| --- | --- | --- |
| 决定 | **`MFMath.Host/`（C#/.NET 宿主）已废弃**，项目所有者原话 **".NET 是废弃的东西"**（2026-10-07） | `DECISIONS.md` D-006（`:102-116`）；`AGENTS.md` §2；`HOSTS.md:18` |
| 现役宿主 | 只有 **`MFMath.Host.Rust/`**（Rust/Tauri + WebView2，9 个宿主对象 / 84 个方法） | `HOSTS.md:17` |
| 废弃资产的地位 | **只读作迁移参考**，不属于任何工作面，不接受功能改动 | `AGENTS.md` §2；`PROJECT-BOARD.md:48` |
| 目录本身 | 仍在磁盘上（本机实测 `MFMath.Host/bin`、`MFMath.Host/obj` 都存在），`MFMath.Host.csproj:5` 是 `net10.0-windows` | 实测；且它**仍是 Rust 宿主构建的输入**（§3.3） |

**对本文的直接后果**（这是本文最实用的一条）：

- `README.md:127` 的第三步命令 `dotnet build MFMath.Host/MFMath.Host.csproj -c Release --no-incremental`
  与 `README.md:136` 的运行命令 `& MFMath.Host\bin\Release\net10.0-windows\MFMath.exe`
  **都指向已废弃的宿主**。README 自己在 `:97-99` 与 `:11-13` 声明了"尚未重写、不要照着它判断当前该怎么跑"。
- `MF_UI/MFMath.UI.Vue/tests/run-all.ps1:26` 的**默认宿主候选**也仍指向
  `MFMath.Host\bin\Release\net10.0-windows\MFMath.exe`（本机实测该行原文）。
  所以跑批时**必须**用 `MF_HOST_EXE` 覆盖成 Rust 宿主（`ACCEPTANCE.md:94` 就是这么写的）。
  这条是 B 面的文件，已登记在 `PROJECT-BOARD.md` §3 R7 第 2 条。
- 想在别处看到"C# 宿主也是现役"这类说法，**见到就改**：它已经不成立（`AGENTS.md` §2 的原话）。

---

## 8. 构建完必须过的三道闸门

| 闸门 | 命令 | 期望 | 出处 |
| --- | --- | --- | --- |
| 注册表守门 | `& MF_Mathematics\build\bin\Release\probe_call.exe list_functions '{}'` | `"count":424` | `README.md:154`；本机 2026-10-07 实测输出 `{"isError":false,...,"count":424,...}` |
| 引擎用例 | `ctest --test-dir MF_Mathematics/build -C Release --output-on-failure` | **16/16** 套件 | `README.md:151`；`CMakeLists.txt` 里 `add_test(` 实测 16 条（`grep`/`Select-String` 计数），`MF_Mathematics/tests` 下实测 15 个 `test_*.cpp` + 4 个 `probe_*.cpp` |
| 前端类型与自检 | `npm run check --prefix MF_UI/MFMath.UI.Vue` | exit 0 | `AGENTS.md` §2 的 B 面行；脚本组成见 §3.2 |

**为什么 `count == 424` 是构建闸门而不是功能测试**：不加 `/WHOLEARCHIVE` 时，
链接器会丢弃那些"没有外部引用的全局注册器"目标文件，失效是**静默的** ——
DLL 照常加载、`function_exists` 照常能调，只是每个 action 都返回"未找到函数"
（`README.md:196-199`）。所以这个数字掉了，比报错更值得警惕。

四个 `probe_*.cpp` 里 `probe_call` 可以**不起宿主直调引擎**（`README.md:181`），
是"引擎单独可用"的最短验证路径（本文上面的 `count` 就是这么跑的）。

---

## 9. 什么不入库

`AGENTS.md` §6 与 `PACKAGING.md` §6（`:143-146`）是权威口径。与本文件直接相关的：

| 路径 | 谁忽略它 | 本机实测 |
| --- | --- | --- |
| `MF_Mathematics/build/` | 根 `.gitignore` | `git check-ignore -q` 退出码 0 |
| `dist/`（前端产物） | 根 `.gitignore` | 同上 |
| `MFMath.Host.Rust/target/` | **由该目录自己的 `.gitignore` 管** | 同上 |
| `MFMath.Host/bin`、`MFMath.Host/obj` | 根 `.gitignore` | 同上 |
| `.tmp-build/`（本机 `TEMP`/`TMP` 的落点） | 根 `.gitignore` 的 `.tmp-*` | 同上 |
| `.cargo-home/`（仓库根那份 cargo 缓存） | 根 `.gitignore` | 本机实测存在 |

**不要**把安装包或 DLL 提交进仓库（`README.md` 的理由：可重建，且会让历史迅速膨胀）。
⚠ `MF_UI/MFMath.UI.Vue/.tmp-*.mjs` 这类排查脚本里有**本机绝对路径与本机端点**，尤其不该进历史
（`.gitignore:49`）。

---

## 10. 已知的文档债

> 规矩（[AGENTS.md](../../AGENTS.md) §5）：**修完就删**，留着不删就会变成没人信的摆设。
> 本节只记**与"构建 / 运行 / 安装"直接相关**的；全量清单在
> [PROJECT-BOARD.md](../PROJECT-BOARD.md) §3 R7/R8。

| # | 位置 | 文档说 | 实际是 | 归属 |
| --- | --- | --- | --- | --- |
| 1 | `README.md:261-263` | "唯一有意保留的是 `MF_Mathematics/tests/accuracy/`（28 个 `.py`，2180 条准确性用例）" | **该目录在磁盘与 git 里都不存在**。本机 `Test-Path MF_Mathematics/tests/accuracy` = False；`git ls-files \| Select-String accuracy` 只匹配到 `MF_UI/MFMath.UI.Vue/tests/cdp-plot-accuracy.mjs` | C 面 |
| 2 | `README.md:127`、`:136` | 三步构建的第 3 步与运行命令 | 都指向**已废弃**的 .NET 宿主。README 自己在 `:97-99` 声明未重写，但命令仍是可直接复制的正文 | C 面（README 管理人） |
| 3 | `MF_UI/MFMath.UI.Vue/tests/run-all.ps1:26` | 默认宿主 = `MFMath.Host\...\MFMath.exe` | 与 D-006 冲突；且 `PROJECT-BOARD.md:200` 记着实测那份 `wwwroot` 停在 03:45 | **B 面**（管理者已登记，未代改） |
| 4 | `MFMath.Host.Rust/README.md:3`、`:46`、`:19` | `:3` "10 个宿主对象已落地 **7 个**"、`:46` "10 个宿主对象**全部落地**"、表格里 `win` 是 **10 方法** | 权威面是 **9 个**对象（`ACCEPTANCE.md` §2、`HOSTS.md:17`），且 `win` 是 **9 方法**（`Restore` 已删，`ACCEPTANCE.md:76`）。同文件 `:3-4` 还写着"47 个 CDP 用例"，而当前实测 **48** 个 | **A 面**（`HOSTS.md:21-22` 已把这份 README 列进 R7 债） |
| 5 | `AGENTS.md` §2 与 `build.rs:134-137` | §2：`MFMath.Host/` "不是任何面的管辖范围……只保留作迁移参考" | **代码层面它仍是 Rust 宿主构建的输入**：`build.rs:137` 读 `MFMath.Host/python` 与 `MFMath.Host/cpp`，缺了只打 warning（`build.rs:143-147`），后果是"控制台能起、组件装不上"。注释与代码一致，但两份口径合起来容易被读成"这个目录可以删" | C 面 / A 面协商：要么改 `build.rs` 把门面挪出废弃目录，要么在这两处各加一句"不可删" |
| 6 | `README.md:139-140` | "Debug 构建的宿主指向 Vite dev server（5173）" | 那是已废弃 .NET 宿主的行为。Rust 侧 `tauri.conf.json` 无 `devUrl`（全文已读），`main.rs` 只有 `MF_WWWROOT`（`main.rs:301`） | C 面（README）/ A 面核对 |

---

## 11. 未证实清单（照 §6.2 与 §1 汇总，**不要当成"没有"**）

| 事项 | 为什么没证实 | 怎么才能证实 |
| --- | --- | --- |
| 安装 → 启动全链路 | 本机起不了安装器（`ERROR_CANCELLED`，环境限制） | 真机按 `PACKAGING.md` §4 走五步 |
| 包内是否真收了 25.7 MB 资产 | NSIS 文件表整体压缩，明文扫描必然扫不到 | 装完后逐项列目录（§6.3 第 2 步） |
| `installMode` 是否生效、"是否需要管理员" | 两次构建表现相同，**没有证据** | 真机安装时观察是否弹 UAC |
| 卸载是否保留 `%LOCALAPPDATA%\MFMath` | 未实测 | §6.3 第 5 步 |
| Node.js < 18 是否真的不能构建 | `package.json` **没有 `engines` 字段**，门槛只是 README 的说明 | 低版本 Node 上跑一次 `npm run build` |
| Rust 的最低工具链版本 | 无 `rust-toolchain.toml`，`Cargo.toml:4` 只写 `edition = "2024"` | 逐版本试 `cargo build`，或补一个 `rust-toolchain.toml` |
| `pthreadVC3.dll` 是否需要显式 `vcpkg install pthreads` | 本机有它，但不知是显式装的还是传递装的 | 干净 vcpkg 只装 README 那 5 个包后看 `bin/` |
| Rust 宿主是否有 dev-server 路径 | `tauri.conf.json` 无 `devUrl`，但"没有已知机制"≠"不存在机制" | §4.4 末尾给的读日志法 |
| Win10 + 旧 WebView2 上的表现 | 本机 WebView2 是 `149.0.4022.80`，且系统是当前这台 | 找一台 Win10 老机器按 §4 跑一遍 |

> 最后一条纪律（[DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) §6）：**"尚未验证"只要验一次就转正** ——
> 这条最容易，也最常被跳过。验完请把对应行**从本文删掉**，不是改成"已完成"。
