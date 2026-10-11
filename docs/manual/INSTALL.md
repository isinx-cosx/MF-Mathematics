# 构建与运行

> 本文回答：怎么从源码构建、怎么运行、安装包做到什么程度。
> 产品说明见 [README.md](README.md)，宿主验收见 [ACCEPTANCE.md](../../MFMath.Host.Rust/docs/ACCEPTANCE.md)，
> 打包细节见 [PACKAGING.md](../../MFMath.Host.Rust/docs/PACKAGING.md)。

## 1. 前提

| 项 | 内容 |
| --- | --- |
| 仓库内容 | 只有源码，不含编译产物与安装包 |
| 从源码跑 | 三步构建 + 直接运行 exe，见第 3、4 节 |
| 安装包 | 自写安装器，可一条命令出包；安装、卸载、快捷方式、卸载项均已实测 |
| 签名 | **未签名**。首次运行会出现 Windows SmartScreen 提示，处理方式见第 6 节 |

## 2. 前置依赖

| 用途 | 需要 |
| --- | --- |
| 引擎 | CMake ≥ 3.16、Visual Studio C++ 工具链、vcpkg 安装 `symengine` `flint` `gmp` `mpfr` `eigen3` |
| 前端 | Node.js ≥ 18 |
| 宿主 | Rust 工具链、MSVC 的 C/C++ 编译器 |
| 运行 | WebView2 Runtime（Win11 自带，Win10 需安装） |

引擎依赖路径是两个 CMake 缓存变量：`MF_SYMENGINE_ROOT` 与 `MF_EIGEN_INCLUDE_DIR`，默认指向作者
机器的 vcpkg 路径，别的机器必须用 `-D` 覆盖。

## 3. 三步构建

顺序不可颠倒：宿主的 `build.rs` 用相对路径取引擎产物与前端 `dist`，所以必须先有前两步。

### 第一步 · 引擎

```powershell
cmake -S MF_Mathematics -B MF_Mathematics/build -G "Visual Studio 18 2026" -A x64 `
      -DMF_SYMENGINE_ROOT="$env:VCPKG_ROOT\installed\x64-windows" `
      -DMF_EIGEN_INCLUDE_DIR="$env:VCPKG_ROOT\installed\x64-windows\include\eigen3"
cmake --build MF_Mathematics/build --config Release --target mf_mathematics
```

生成器 `-G` 按本机 Visual Studio 版本改。目标 `mf_mathematics` 是导出 C ABI 的动态库。

### 第二步 · 前端

```powershell
npm --prefix MF_UI/MFMath.UI.Vue install
npm --prefix MF_UI/MFMath.UI.Vue run build
```

`build` 脚本由 `vite build` 与字体裁剪组成。构建期检查用 `npm run check --prefix MF_UI/MFMath.UI.Vue`。

### 第三步 · 宿主

```powershell
$repo = "<仓库根>"
$env:TEMP = "$repo\.tmp-build"; $env:TMP = $env:TEMP
$env:CARGO_HOME = "$repo\.cargo-home"
cd "$repo\MFMath.Host.Rust"
cargo build --message-format short
```

`build.rs` 自动把引擎 DLL、前端 `dist` 与控制台门面文件同步到 exe 同目录。这三样缺失时只打
警告不报错，所以「构建成功」不保证能跑出正确结果。

## 4. 运行

宿主必须跑到工作区外，否则写不了 `%LOCALAPPDATA%`，日志与设置会静默失败：

```powershell
$repo = "<仓库根>"
$run = "$env:TEMP\mfhost-run"
node "$repo\MFMath.Host.Rust\tools\sync-wwwroot.mjs" --exe "$run\mfmath-host-rust.exe"
Start-Process "$run\mfmath-host-rust.exe"
```

起来后的判定：

| 现象 | 期望值 |
| --- | --- |
| 页面 URL | `https://mfmath.local/index.html` |
| 宿主对象 | 9 个，没有 `ai` |
| 无头自检 | `--selftest-jobs` 5/5，`--selftest-common` 10/0 |

无头自检不需窗口：

```powershell
& MFMath.Host.Rust\target\release\mfmath-host-rust.exe --selftest-jobs
& MFMath.Host.Rust\target\release\mfmath-host-rust.exe --selftest-common
```

## 5. 可选环境开关

| 变量 | 作用 |
| --- | --- |
| `MF_WWWROOT` | 指定 UI 目录，默认 exe 同目录的 `wwwroot` |
| `MF_WEBVIEW2_DIR` | 指定 WebView2 用户数据目录 |
| `MF_ENGINE_BIN` | 覆盖引擎 DLL 的源目录 |

## 6. 安装包

安装器是自写程序（`MFMath.Installer/`），一条命令出包：

```powershell
.\MFMath.Installer\tools\build-setup.ps1
```

产出 `MFMath.Installer\target\release\Multifunctional-Mathematics_<版本>_x64-setup.exe`（约 18 MB）。
安装器本身的说明、命令行参数与验收记录见
[INSTALLER.md](../../MFMath.Host.Rust/docs/INSTALLER.md)。

安装行为：

| 项 | 取值 |
| --- | --- |
| 安装位置 | `%LOCALAPPDATA%\Programs\Multifunctional-Mathematics\`（每用户，不需要管理员） |
| 主程序 | `Multifunctional-Mathematics.exe` |
| 快捷方式 | 开始菜单与桌面各一份 |
| 卸载入口 | 「设置 → 应用 → 已安装的应用」，或安装目录里的 `uninstall.exe` |
| 用户数据 | `%LOCALAPPDATA%\MFMath`，卸载默认保留 |

安装包自带 WebView2 引导程序：系统缺少 Runtime 时会静默安装它，Windows 11 通常不需要。

### 首次运行的安全提示

安装包**没有数字签名**，因此首次运行时 Windows 可能显示「Windows 已保护你的电脑」（SmartScreen）。

继续运行的方法：

1. 点击提示框里的「**更多信息**」；
2. 出现「仍要运行」按钮后点击它。

如果提示来自浏览器下载，则是「**保留**」→「显示更多」→「仍然保留」。

**为什么没有签名**：代码签名证书需要按年付费并通过身份核验，本项目暂未采购。签名解决的是
"发布者可识别"，不改变软件本身的行为。**校验文件有没有被改过，用发布页面公布的 SHA-256 比对**
（出包脚本会打印该值）：

```powershell
Get-FileHash .\Multifunctional-Mathematics_2.0.0_x64-setup.exe -Algorithm SHA256
```

哈希与发布页公布的一致，就说明文件在传输途中没有被替换。

## 7. 构建后的闸门

| 闸门 | 命令 | 期望 |
| --- | --- | --- |
| 引擎注册表 | `probe_call.exe list_functions '{}'` | `count` 为 424 |
| 引擎用例 | `ctest --test-dir MF_Mathematics/build -C Release --output-on-failure` | 全绿 |
| 前端检查 | `npm run check --prefix MF_UI/MFMath.UI.Vue` | 退出码 0 |

`count` 为 424 是构建闸门。漏掉 `/WHOLEARCHIVE` 链接选项时，链接器会丢弃注册器目标文件，
注册表变空但 DLL 照常加载，每个函数都返回「未找到函数」，失效是静默的。

## 8. 不入库

`MF_Mathematics/build/`、`dist/`、`target/`、`bin/`、`obj/` 都在 `.gitignore` 中。安装包与 DLL
不提交进仓库。构建前把 `TEMP`、`TMP` 指到仓库内的 `.tmp-build`，把 `CARGO_HOME` 指到仓库内的
`.cargo-home`。
