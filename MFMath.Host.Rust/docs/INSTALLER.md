# 安装器设计

> 本文说明安装器的形态、安装与卸载流程、目录布局与命名规则，以及签名要求。
> 载荷的构成与体积见 [PACKAGING.md](PACKAGING.md)，宿主的验收步骤见 [ACCEPTANCE.md](ACCEPTANCE.md)。
> 本文是设计定稿；安装器代码尚未实现，实现进度以本文第 10 节为准。

## 1. 形态与目标

| 项 | 取值 |
| --- | --- |
| 交付形态 | 单个 exe，尾部内嵌压缩后的载荷 |
| 安装模式 | 每用户安装，不请求管理员权限 |
| 安装目录 | `%LOCALAPPDATA%\Programs\MF-Mathematics\` |
| 主程序文件名 | `Multifunctional-Mathematics.exe` |
| 目标平台 | Windows 10 / 11 x64 |
| 载荷未压缩体积 | 约 43.2 MB |
| 预计产物体积 | 11–14 MB（LZMA 压缩后） |
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
%LOCALAPPDATA%\Programs\MF-Mathematics\
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
HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\MF-Mathematics
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
| 安装目录 | `MF-Mathematics` |
| 用户数据目录 | `%LOCALAPPDATA%\MFMath` |
| 卸载注册表键 | `...\Uninstall\MF-Mathematics` |

主程序名与安装目录名不一致是有意为之：安装目录沿用仓库与既有产物的短名 `MF-Mathematics`，主程序与所有面向用户的显示名使用全名 `Multifunctional-Mathematics`。

Cargo 包名保持 `mfmath-host-rust`（`../Cargo.toml`），构建产物与开发脚本沿用该名（`../docs/ACCEPTANCE.md`、`../../MF_UI/MFMath.UI.Vue/tests/run-all.ps1` 都按它定位）。改名由安装器在释放阶段完成，避免波及开发流程。

## 8. 命令行

| 参数 | 作用 |
| --- | --- |
| （无） | 图形界面安装 |
| `/S` | 静默安装，不显示界面 |
| `/D=<路径>` | 指定安装目录，必须是最后一个参数且不加引号 |
| `/uninstall` | 卸载 |
| `/uninstall /S` | 静默卸载（保留用户数据） |
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

| 阶段 | 内容 | 完成标准 |
| --- | --- | --- |
| 1 | 载荷收集与压缩：把第 2 节清单打成 payload | 产出 payload 归档，记录压缩比 |
| 2 | 释放核心：解压到安装目录、主程序改名、写 `manifest.json` | 装完能直接运行主程序 |
| 3 | 系统集成：开始菜单快捷方式、卸载注册表键、`uninstall.exe` | 安装与卸载闭环，卸载后无残留 |
| 4 | 静默参数：`/S`、`/D=`、`/uninstall`、`/purge` | 静默装与静默卸可用 |
| 5 | WebView2 检测与内嵌引导程序 | 删除 WebView2 后仍能安装 |
| 6 | 打包流水线：一条命令产出成品 exe | 单命令可重复出包 |
| 7 | 签名接入 | 证书就位后签名，SmartScreen 不再拦截 |

## 11. 未验证项

以下内容尚未在本机验证，实现时以实测为准：

- 内嵌引导程序的实际体积（估算 1.8 MB，取决于微软当前发布的 bootstrapper）；
- 压缩后的成品体积（预计 11–14 MB，依据是 NSIS 同载荷实测 11.12 MB）；
- WebView2 注册表检测在只装了 Edge 浏览器但未装 Runtime 的机器上的判定结果；
- `Publisher` 字段的取值（取决于证书主体）。
