# 安装器设计

> 本文说明安装器的形态、安装与卸载流程、目录布局与命名规则，以及签名要求。
> 载荷的构成与体积见 [PACKAGING.md](PACKAGING.md)，宿主的验收步骤见 [ACCEPTANCE.md](ACCEPTANCE.md)。
> 本文是设计定稿；安装器代码尚未实现，实现进度以本文第 10 节为准。

## 1. 形态与目标

| 项 | 取值 |
| --- | --- |
| 交付形态 | 单个 exe，尾部内嵌压缩后的载荷 |
| 安装模式 | 每用户安装，不请求管理员权限 |
| 安装目录 | `%LOCALAPPDATA%\Programs\Multifunctional-Mathematics\` |
| 主程序文件名 | `Multifunctional-Mathematics.exe` |
| 目标平台 | Windows 10 / 11 x64 |
| 载荷未压缩体积 | 43.09 MB（实测） |
| 产物体积 | **11.03 MB**（xz / LZMA2 实测）；zip / deflate 为 15.71 MB |
| 实现语言 | Rust（与宿主共用工具链） |

选择自解压单 exe 而非 MSI 或 NSIS：安装逻辑、目录结构、WebView2 处理全部由本仓库掌握，不依赖第三方安装框架。NSIS 方案的三个具体问题记录在第 9 节。

安装器**离线可用**：默认不联网。只有在检测到系统缺少 WebView2 时才运行内嵌的引导程序，见第 5 节。

## 2. 载荷清单

体积为 release 构建实测值。

| 内容 | 文件 | 体积 |
| --- | --- | ---: |
| 宿主主程序 | `mfmath-host-rust.exe`（安装为 `Multifunctional-Mathematics.exe`） | 13.91 MB |
| 引擎 | `mf_mathematics.dll` | 3.22 MB |
| 依赖 | `symengine-0.14.dll` | 8.00 MB |
| 依赖 | `flint-24.dll` | 9.68 MB |
| 依赖 | `gmp-10.dll` | 0.42 MB |
| 依赖 | `mpfr-6.dll` | 0.40 MB |
| 依赖 | `pthreadVC3.dll` | 0.06 MB |
| 前端 | `wwwroot/`（103 个文件） | 7.38 MB |
| 控制台 Python 门面 | `python/mfmath.py` | 24 KB |
| 控制台 C++ 门面 | `cpp/mfmath.hpp`、`cpp/mfmath_autorun.hpp` | 含上 |
| 快捷方式图标 | `icons/icon.ico` | 0.12 MB |

6 个引擎相关 DLL 合计 21.78 MB。

控制台的可选组件（CPython 11 MB、MinGW 54 MB）**不进入安装包**，由用户在控制台内按需下载，见 [../src/console.rs](../src/console.rs) 的组件清单。

## 3. 安装流程

```
解析自身尾部内嵌的 payload + manifest
  │
  ├─ 1. 参数解析（GUI 或 /S 静默；/D 指定目录）
  │
  ├─ 2. WebView2 检测（第 5 节）
  │      已安装或系统自带 → 跳过
  │      缺失 → 运行内嵌引导程序（静默）
  │
  ├─ 3. 释放载荷到安装目录
  │      写入临时文件后原子替换，避免半写状态
  │
  ├─ 4. 主程序改名
  │      mfmath-host-rust.exe → Multifunctional-Mathematics.exe
  │
  ├─ 5. 写卸载信息（第 6 节）
  │
  ├─ 6. 建开始菜单快捷方式（桌面可选）
  │
  ├─ 7. 写 manifest.json（版本、逐文件 sha256、安装时间）
  │
  └─ 完成
```

安装器把自身复制一份到安装目录，命名为 `uninstall.exe`。卸载复用同一份代码，带 `/uninstall` 参数运行，不需要单独编译卸载器。

## 4. 目录布局

安装后：

```
%LOCALAPPDATA%\Programs\Multifunctional-Mathematics\
├── Multifunctional-Mathematics.exe    主程序
├── mf_mathematics.dll                 引擎
├── symengine-0.14.dll
├── flint-24.dll
├── gmp-10.dll
├── mpfr-6.dll
├── pthreadVC3.dll
├── wwwroot\                           前端（103 个文件）
├── python\mfmath.py                   控制台 Python 门面
├── cpp\mfmath.hpp
├── cpp\mfmath_autorun.hpp
├── uninstall.exe                      卸载器
└── manifest.json                      版本与逐文件 sha256
```

用户数据不在安装目录内，位于 `%LOCALAPPDATA%\MFMath\`（`settings/`、`logs/`、`components/`、`console/`）。卸载默认不触碰该目录。

宿主按**自身所在目录**定位 `wwwroot` 与引擎 DLL（`../src/main.rs` 的 `wwwroot_dir()`、`../src/handlers.rs` 的 `exe_dir()`），与 exe 文件名无关。因此重命名主程序不影响资源查找。

## 5. WebView2 处理

策略：**内嵌 Evergreen 引导程序**（Tauri 的 `embedBootstrapper` 模式），约 1.8 MB。

流程：

1. 读注册表检测已安装的 Evergreen Runtime 版本。检测位置：
   `HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` 的 `pv` 值，
   以及 `HKCU\Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` 的 `pv` 值。
2. 键存在且 `pv` 非空非 `0.0.0.0` → 视为已安装，跳过。
3. 否则运行内嵌的 `MicrosoftEdgeWebview2Setup.exe /silent /install`。
4. 引导程序自身需要联网下载 Runtime；失败时**不阻断安装**，改为在完成页提示用户手动安装 WebView2，并给出微软下载页地址。

Windows 11 自带 WebView2 Runtime，此分支通常不触发。

## 6. 卸载与用户数据

| 项 | 行为 |
| --- | --- |
| 触发方式 | 设置 → 应用 → 已安装的应用；或开始菜单的卸载项；或 `uninstall.exe` |
| 结束进程 | 先结束正在运行的 `Multifunctional-Mathematics.exe` |
| 删除范围 | 安装目录、开始菜单项、桌面快捷方式（若创建过）、卸载注册表键 |
| 用户数据 | **默认保留** `%LOCALAPPDATA%\MFMath\` |
| 删除用户数据 | 卸载界面提供一个勾选项「同时删除我的数据（设置、日志、组件缓存）」，**默认不勾选** |
| 自我删除 | 卸载器进程退出前用 `MoveFileEx(..., MOVEFILE_DELAY_UNTIL_REBOOT)` 排入自身删除 |

卸载注册表键位置：

```
HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\Multifunctional-Mathematics
```

写入的字段：

| 字段 | 取值 |
| --- | --- |
| `DisplayName` | `Multifunctional-Mathematics` |
| `DisplayVersion` | `manifest.json` 中的版本号（当前 `2.0.0`） |
| `Publisher` | 待定 |
| `InstallLocation` | 安装目录绝对路径 |
| `UninstallString` | `<安装目录>\uninstall.exe /uninstall` |
| `DisplayIcon` | `<安装目录>\Multifunctional-Mathematics.exe` |
| `EstimatedSize` | 载荷解压后的 KB 数 |
| `NoModify` / `NoRepair` | `1` |

## 7. 命名规则

| 位置 | 名称 |
| --- | --- |
| 主程序文件 | `Multifunctional-Mathematics.exe` |
| 开始菜单快捷方式 | `Multifunctional-Mathematics` |
| 卸载项显示名 | `Multifunctional-Mathematics` |
| 安装目录 | `Multifunctional-Mathematics` |
| 用户数据目录 | `%LOCALAPPDATA%\MFMath` |
| 卸载注册表键 | `...\Uninstall\Multifunctional-Mathematics` |

所有面向用户与面向系统的名字一律用全名 `Multifunctional-Mathematics`，只有用户数据目录沿用 `MFMath`（宿主与既有的设置/日志路径都按它定位）。

v1 的安装目录是 `%LOCALAPPDATA%\Programs\MF-Mathematics\`，与本产品的目录不同，两者可以并存。

Cargo 包名保持 `mfmath-host-rust`（`../Cargo.toml`），构建产物与开发脚本沿用该名（`../docs/ACCEPTANCE.md`、`../../MF_UI/MFMath.UI.Vue/tests/run-all.ps1` 都按它定位）。改名由安装器在释放阶段完成，避免波及开发流程。

## 8. 命令行

| 参数 | 作用 |
| --- | --- |
| （无） | 常规安装，控制台输出进度 |
| `/S` | 静默安装，不显示任何输出 |
| `/D=<路径>` | 指定安装目录，必须是最后一个参数且不加引号 |
| `--dir <路径>` | 同上，写法更宽松 |
| `/force` | 目标目录已有本产品以外的文件时，仍就地覆盖 |
| `/uninstall` | 卸载（保留用户数据） |
| `/uninstall /S` | 静默卸载 |
| `/uninstall /S /purge` | 静默卸载并删除用户数据 |

## 9. 签名要求

安装包与主程序都需要 Authenticode 签名，否则 Windows SmartScreen 会拦下并显示「Windows 已保护你的电脑」。

| 项 | 做法 |
| --- | --- |
| 签名对象 | 安装器 exe、`Multifunctional-Mathematics.exe` |
| 摘要算法 | SHA-256 |
| 时间戳 | 必须。缺少时间戳的签名在证书过期后失效 |
| 工具 | `signtool sign /fd sha256 /tr <时间戳服务器> /td sha256` |

证书就位前，安装包功能不受影响，SmartScreen 提示无法消除。

### NSIS 方案被替换的原因

先前用 Tauri 的 NSIS 打包器产出过 11.12 MB 的安装包，遇到三个问题：

1. **安装时联网下载 WebView2**。NSIS 的 `downloadBootstrapper` 模式在安装阶段从微软下载引导程序，网络不可用时安装直接失败。
2. **临时目录依赖**。NSIS 安装器先把自身解压到 `%TEMP%`，该目录不可写时弹出 `Error writing temporary file`，安装无法继续。
3. **SmartScreen 判定更严**。NSIS 自解压外壳是被恶意软件广泛使用的形态，启发式判据对它更敏感。

自写安装器后，第 1 点改为内嵌引导程序，第 2 点由安装器自行管理释放路径，第 3 点只剩签名问题。

## 10. 实现分期

| 阶段 | 内容 | 完成标准 | 状态 |
| --- | --- | --- | --- |
| 1 | 载荷收集与压缩：把第 2 节清单打成 payload | 产出 payload 归档，记录压缩比 | **已验证**，见第 12 节 |
| 2 | 释放核心：解压到安装目录、主程序改名、写 `manifest.json` | 装完能直接运行主程序 | **已验证** |
| 3 | 系统集成：开始菜单快捷方式、卸载注册表键、`uninstall.exe` | 安装与卸载闭环，卸载后无残留 | **已验证** |
| 4 | 静默参数：`/S`、`/D=`、`/uninstall`、`/purge` | 静默装与静默卸可用 | **已验证** |
| 5 | WebView2 检测与内嵌引导程序 | 删除 WebView2 后仍能安装 | 未开始 |
| 6 | 打包流水线：一条命令产出成品 exe | 单命令可重复出包 | **已验证**（`tools/build-setup.ps1`） |
| 7 | 签名接入 | 证书就位后签名，SmartScreen 不再拦截 | 未开始 |

## 11. 未验证项

以下内容尚未在本机验证，实现时以实测为准：

- 内嵌引导程序的实际体积（估算 1.8 MB，取决于微软当前发布的 bootstrapper）；
- WebView2 注册表检测在只装了 Edge 浏览器但未装 Runtime 的机器上的判定结果；
- `Publisher` 字段的取值（取决于证书主体）；
- 自解压 exe 的自身体积开销（压缩载荷 11.03 MB 之外，安装器逻辑本身占多少）。

## 12. 验证记录

### 载荷收集与压缩（第 1 期）

载荷按第 4 节布局收集完成，113 个文件，未压缩 43.09 MB。压缩与完整性验证结果：

| 格式 | 体积 | 压缩耗时 |
| --- | ---: | ---: |
| 未压缩 | 43.09 MB | — |
| zip / deflate | 15.71 MB | 1.6 s |
| xz / LZMA2 | **11.03 MB** | 15.8 s |

完整性验证：解压后逐文件 SHA-256 比对，**113 个文件全部一致，差异 0 个**。

功能验证：对布局后的载荷运行宿主无头自检，两项均通过。

| 自检 | 结果 |
| --- | --- |
| `Multifunctional-Mathematics.exe --selftest-jobs` | **5 / 5 通过**，退出码 0 |
| `Multifunctional-Mathematics.exe --selftest-common` | **10 / 0 通过**，退出码 0 |

复现命令（在载荷目录下执行）：

```powershell
# 收集载荷后压缩
tar.exe -cJf payload.tar.xz -C .tmp-build\payload MF-Mathematics

# 往返验证
tar.exe -xf payload.tar.xz -C <解压目录>
<解压目录>\MF-Mathematics\Multifunctional-Mathematics.exe --selftest-jobs
<解压目录>\MF-Mathematics\Multifunctional-Mathematics.exe --selftest-common
```

### 一条实现约束

自检在**工作区内**运行时，`--selftest-common` 的「打包到解包往返」一项会以 `拒绝访问 (os error 5)` 失败；把同一份载荷放到用户可写的目录（如 `%LOCALAPPDATA%\Temp`）后该项通过。

结论：**主程序运行所在的目录必须对当前用户可写**。安装目标 `%LOCALAPPDATA%\Programs\Multifunctional-Mathematics\` 满足该条件。

## 13. 实现与第 2–4 期验证记录

### 代码位置与构建

安装器是独立 crate，位于 [`../../MFMath.Installer/`](../../MFMath.Installer/)：

| 文件 | 职责 |
| --- | --- |
| `src/main.rs` | 命令行解析与三种模式的分发 |
| `src/payload.rs` | 尾部内嵌载荷的读写、zip 解压、清单生成 |
| `src/install.rs` | 安装流程 |
| `src/uninstall.rs` | 卸载流程与自删除 |
| `src/shortcut.rs` | 快捷方式（COM `IShellLink`） |
| `src/registry.rs` | 卸载注册表项（`winreg`） |
| `src/pack.rs` | 把载荷目录封成单文件安装器 |
| `src/util.rs` | 路径、输出、哈希、静默开关 |
| `tools/build-setup.ps1` | 收集载荷并一条命令出包 |

构建（宿主所在目录提供 cargo 源替换配置）：

```powershell
cd MFMath.Host.Rust
cargo build --release --offline --manifest-path ..\MFMath.Installer\Cargo.toml
```

产物 `MFMath.Installer\target\release\mfmath-installer.exe`，**685 KB**，编译零警告。依赖只用宿主已缓存的 crate（`zip`、`serde_json`、`sha2`、`winreg`、`walkdir`、`windows`），可离线构建。

### 打包

一条命令出包（收集载荷 + 压缩 + 内嵌）：

```powershell
.\MFMath.Installer\tools\build-setup.ps1
```

产物 `MFMath.Installer\target\release\Multifunctional-Mathematics_<版本>_x64-setup.exe`。

脚本也可单独调用安装器的打包模式：

```powershell
.\MFMath.Installer\target\release\mfmath-installer.exe --pack <载荷目录> <输出 exe> --version 2.0.0
```

实测：载荷 43.21 MB（114 个文件）→ 压缩 **15.75 MB** → 成品安装包 **16.46 MB**（含 685 KB 安装器逻辑）。

只有 `--pack` 产出的安装包能直接安装。安装器的编译产物本身不含载荷，直接运行会提示改用打包脚本。

### 第 2 期：释放核心

| 检查 | 结果 |
| --- | --- |
| 释放文件数 | 114 |
| 主程序改名 `mfmath-host-rust.exe` → `Multifunctional-Mathematics.exe` | 成功，旧名不再存在 |
| 卸载器 `uninstall.exe` | 写入成功 |
| `manifest.json` | `product` / `version` / 115 条逐文件 sha256（114 载荷 + 卸载器）均正确 |
| 装好的主程序无头自检 | `--selftest-jobs` **5 / 5 通过**、`--selftest-common` **10 / 0 通过**，退出码 0 |

### 第 3 期：系统集成

快捷方式（用 COM 读回 `.lnk` 实际内容）：

| 项 | 取值 |
| --- | --- |
| 目标 | `<安装目录>\Multifunctional-Mathematics.exe` |
| 工作目录 | 安装目录 |
| 图标 | `<安装目录>\icon.ico,0` |
| 位置 | 开始菜单 `Programs\` 与桌面各一份 |

卸载注册表项（`HKCU\...\Uninstall\Multifunctional-Mathematics`）：

| 字段 | 值 |
| --- | --- |
| `DisplayName` | `Multifunctional-Mathematics` |
| `DisplayVersion` | 版本号，随升级更新 |
| `InstallLocation` | 安装目录 |
| `UninstallString` | `"<安装目录>\uninstall.exe" /uninstall` |
| `QuietUninstallString` | `"<安装目录>\uninstall.exe" /uninstall /S` |
| `DisplayIcon` | `<安装目录>\Multifunctional-Mathematics.exe` |
| `EstimatedSize` | 61074（KB） |
| `NoModify` / `NoRepair` | 1 / 1 |

卸载闭环：

| 检查 | 结果 |
| --- | --- |
| 卸载后安装目录 | 完整删除 |
| 卸载后快捷方式 | 开始菜单与桌面两份都消失 |
| 卸载后注册表项 | 消失 |
| 卸载后用户数据 | 保留 `%LOCALAPPDATA%\MFMath`，输出中明确说明 |
| 卸载器自身与临时副本 | 由收尾脚本删除，`%TEMP%` 无残留 |
| 退出码 | 0 |

### 第 4 期：静默参数

| 参数 | 结果 |
| --- | --- |
| `/S` | 静默安装零输出、退出码 0、文件正确落盘 |
| `/D=<路径>` | 生效，与 `--dir` 等价 |
| `/uninstall` | 生效，退出码 0 |
| `/uninstall /S` | 零输出、退出码 0 |
| `/uninstall /S /purge` | 零输出；安装目录与用户数据都被删除 |
| `/force` | 见下一节 |

### 安装目录里可能有别的东西

默认安装目录定为 `%LOCALAPPDATA%\Programs\Multifunctional-Mathematics\`，而不是 v1 用的 `%LOCALAPPDATA%\Programs\MF-Mathematics\`。原因是实测发现后者**已经装着 v1**：

```
%LOCALAPPDATA%\Programs\MF-Mathematics\
Multifunctional-Mathematics-v1.0.exe   132.20 MB
unins000.exe                             4.30 MB
unins000.dat
```

若 v2 沿用该目录并按覆盖升级先清空，就会把 v1 整个删掉。改用独立目录后两者互不干扰，用户升级到 v2 时 v1 仍然可用。

`--dir` 仍可指向任意位置，所以安装器与卸载器都保留了下面的保护规则：

| 情况 | 行为 |
| --- | --- |
| 目录不存在或为空 | 直接安装 |
| 目录里有本产品的 `manifest.json` | 视为覆盖升级：按旧清单只删登记过的文件 |
| 目录里有其它文件 | **默认拒绝**，列出看到的内容，退出码 1 |
| 同上且带 `/force` | 就地覆盖：只覆盖同名文件，其它文件不动 |

清单只登记本产品释放的文件（归档条目 + `uninstall.exe`），不扫描整个目录。卸载同样只删清单里的文件；若目录里还剩别的东西，**保留目录**并列出剩余项。

实测结果（隔离的 `LOCALAPPDATA` 下造的模拟 v1 环境）：

| 检查 | 结果 |
| --- | --- |
| `--dir` 指向含 v1 的目录 | 拒绝，列出 v1 的 3 个文件，退出码 1，v1 完好 |
| 同上加 `/force` | 成功；v1 的 3 个文件仍在 |
| 与 v1 共存时的清单条目数 | 115（114 载荷 + `uninstall.exe`），**不含 v1 的文件** |
| 卸载后 | 本产品 115 个文件全删；v1 的 3 个文件与目录本身都保留 |
| 重复安装同版本 | 识别为既有安装并覆盖，退出码 0 |
| 安装更高版本 | 识别旧版本、按清单清理、版本号与注册表同步更新 |

### 关于开发机沙箱

本会话中，**位于工作区内的**二进制只能写工作区内的路径，所以最初运行安装器时，快捷方式、注册表、`%TEMP%` 写入全部被拒绝。

把安装包复制到工作区外（`C:\MF-Setup\`）再运行后，上述操作全部成功 —— 因此第 3 期已在真机完整验证，不受该限制影响。同一会话里 PowerShell 对这些位置的写入也一直正常，说明是沙箱对二进制所在位置的限制，与文件权限无关。

安装器仍保留了对受限环境的容错：快捷方式与卸载注册表项写入失败按**非致命**处理并逐条报告；临时目录不可写时卸载降级为原地卸载；退出后清理失败也不影响卸载结果。
