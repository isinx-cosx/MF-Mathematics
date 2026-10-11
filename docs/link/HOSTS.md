# 宿主谱系与运行形态

> 本文说明宿主当前的运行形态：现役宿主、页面地址约定、数据目录布局，以及更换宿主时哪些配置可以沿用。
> 宿主对象与方法清单见 [OBJECTS.md](OBJECTS.md)，接缝机制见 [README.md](README.md)，凭据边界见 [CREDENTIALS.md](CREDENTIALS.md)，可复现验收见 [ACCEPTANCE.md](../../MFMath.Host.Rust/docs/ACCEPTANCE.md)。

## 1. 运行形态

产品只有一个宿主：`MFMath.Host.Rust/`（Rust + Tauri v2 + WebView2）。早期的 C# / WPF + WebView2 宿主已从仓库移除。

| 宿主 | 路径 | 状态 |
| --- | --- | --- |
| Rust / Tauri v2 + WebView2 | `MFMath.Host.Rust/` | 现役 |

窗口与进程形态：

| 项 | 取值 | 定位命令 |
| --- | --- | --- |
| 窗口 | 无边框，标题栏由页面自绘 | `Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "decorations\(false\)"` |
| 初始尺寸 | 1240×820 | `Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "inner_size"` |
| 最小尺寸 | 980×640 | `Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "min_inner_size"` |
| 调试端口 | 9222 | `Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "remote-debugging-port"` |
| 进程子系统 | GUI，无控制台窗口 | `Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "windows_subsystem"` |

宿主是 GUI 子系统，双击运行时 stdout 不连终端。启动与失败信息经 `note()` 同时写 stderr 与 `app.log`（`Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "fn note"`）。WebView2 初始化失败时经 `fail_with_reason()` 写崩溃文件、弹提示框并退出，提示框等待上限是 20 秒（`Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "fn fail_with_reason"`）。

启动参数（`main.rs` 在 `main()` 入口处按参数分支，均为无头自检）：

| 参数 | 作用 | 依赖 |
| --- | --- | --- |
| `--selftest-jobs` | 验后台任务通道的派发、串行、轮询与两种取消 | 不需要 WebView2 |
| `--selftest-common` | 验 DPAPI / sha256 / zip / HTTP 环境 | 不需要 WebView2 |
| `--selftest-common --unprotect <base64>` | 解开外部（C#/PowerShell）产出的 DPAPI 密文并比对 | 不需要 WebView2 |

```powershell
Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "selftest-jobs|selftest-common|unprotect"
```

单实例闸门在 `lock_webview_dir()` 内实现：以 `share_mode(1)` 共享读模式打开数据目录里的 `.mf-instance` 锁文件并写入持有者 pid，句柄存入 `INSTANCE_GUARD` 活到进程结束。第二个实例的 open 得到 `ERROR_SHARING_VIOLATION`，在建窗口之前就被 `fail_with_reason` 拦下并报出持有者 pid；目录不可写（`ERROR_ACCESS_DENIED` 等）只跳过检查，不阻止启动。

## 2. 页面地址约定

页面地址由两个常量给出：`UI_HOST` 的取值是 `mfmath.local`，`UI_URL` 的取值是 `https://mfmath.local/index.html`（`Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "const UI_HOST|const UI_URL"`）。

宿主不把前端直接嵌进 exe。存在 exe 同目录 `wwwroot` 时，宿主用 `SetVirtualHostNameToFolderMapping` 把该目录映射到 `mfmath.local`，再在注册完宿主对象后 `Navigate` 到 `UI_URL`（`Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "SetVirtualHostNameToFolderMapping"`）。Tauri 的内嵌资产（`frontendDist`）只作兜底：`wwwroot` 里没有 `index.html` 时页面退回内嵌资产，地址变为 `http://tauri.localhost`。

48 个 `cdp-*.mjs` 用例按正则 `mfmath.local|index.html` 从 `http://127.0.0.1:9222/json/list` 取页，地址改变会使这批用例取不到页面。

| 环境变量 | 作用 | 默认值 | 定位命令 |
| --- | --- | --- | --- |
| `MF_WWWROOT` | 指定 UI 目录 | exe 同目录的 `wwwroot` | `Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "fn wwwroot_dir"` |
| `MF_WEBVIEW2_DIR` | 指定 WebView2 用户数据目录 | `%LOCALAPPDATA%\MFMath\webview2` | `Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "fn webview_data_dir"` |
| `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` | 追加浏览器参数 | 宿主未设置时设为 `--remote-debugging-port=9222` | `Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"` |
| `MF_HOST_EXE` | `run-all.ps1` 指定被测宿主 exe | 无 | `Select-String -Path MF_UI/MFMath.UI.Vue/tests/run-all.ps1 -Pattern "MF_HOST_EXE"` |

`run-all.ps1` 未设 `MF_HOST_EXE` 时的默认候选是 `MFMath.Host.Rust\target\release\mfmath-host-rust.exe`（`Select-String -Path MF_UI/MFMath.UI.Vue/tests/run-all.ps1 -Pattern 'mfmath-host-rust'`）。

## 3. 数据目录

数据根目录是 `%LOCALAPPDATA%\MFMath`（`Select-String -Path MFMath.Host.Rust/src/logging.rs -Pattern "fn data_dir"`）。

| 子目录 | 内容 | 定位命令 |
| --- | --- | --- |
| `settings` | 设置 JSON 文件 | `Select-String -Path MFMath.Host.Rust/src/sys.rs -Pattern "fn settings_dir"` |
| `logs` | `app.log`、`crash-*.log` | `Select-String -Path MFMath.Host.Rust/src/logging.rs -Pattern "fn dir"` |
| `components` | 控制台可选组件 | `Select-String -Path MFMath.Host.Rust/src/console.rs -Pattern "fn components_root"` |
| `webview2` | WebView2 用户数据 | `Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "fn webview_data_dir"` |

设置文件的写入由 `store_write()` 完成（`Select-String -Path MFMath.Host.Rust/src/sys.rs -Pattern "fn store_write"`）：文件名为 `<name>.json`，名称只允许小写字母、数字、下划线与连字符（`Select-String -Path MFMath.Host.Rust/src/sys.rs -Pattern "fn valid_name"`）；覆盖前把旧文件复制为 `<name>.json.bak`，写入走临时文件加 `rename` 的原子替换。

宿主从工作区内的 `target\debug` 启动时写不了 `%LOCALAPPDATA%`，日志与设置会静默失败。验收前把 exe 与 `wwwroot` 部署到工作区外，步骤见 [ACCEPTANCE.md](../../MFMath.Host.Rust/docs/ACCEPTANCE.md)。

## 4. 配置可移植性

设置文件由页面与宿主经 `sys.StoreWrite` 共同写入，字段名按 camelCase 序列化（`Select-String -Path MFMath.Host.Rust/src/account.rs -Pattern 'rename_all = "camelCase"'`），与 C# 宿主的 `PropertyNameCaseInsensitive` 反序列化对齐。两类凭据用 DPAPI 加密且不传 optional entropy，同一 Windows 用户下由任一宿主写出的密文可被另一个解开（`Select-String -Path MFMath.Host.Rust/src/dpapi.rs -Pattern "CryptProtectData"`）。

| 配置 | 文件与字段 | 可否跨宿主沿用 | 说明 |
| --- | --- | --- | --- |
| 登录 token | `settings/account.json` 的 `token_protected` | 是 | DPAPI 密文（base64） |
| Wolfram App ID | `settings/search.json` 的 `wolfram_key_protected` | 是 | DPAPI 密文（base64） |
| 更新 / 工作区 / 历史 | `settings/update.json`、`workspace.json`、`history.json` | 是 | camelCase 字段一致 |
| AI 密钥 | `settings/ai.json` | 否 | 字段形式不同，见下 |

AI 密钥是唯一不可跨宿主沿用的配置。旧版 C# 宿主写 `apiKeyProtected`（DPAPI 密文）；现役 AI 由页面直连，密钥以明文存于 `apiKey`（`Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/ai/bridge.js -Pattern "next.apiKey = k"`）。页面侧无 DPAPI 可调，读到旧版密文时 `hasKey` 为 `false`，界面提示重填一次，其余配置不受影响。

## 5. 核对

```powershell
# 宿主对象数与方法总数（期望 9 / 84）
(Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern '^\s+\("(\w+)", \w+_SPEC\),').Count
(Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern 'MethodSpec \{ name:').Count
# 依赖页面地址的 CDP 用例数（期望 48）
(Get-ChildItem MF_UI/MFMath.UI.Vue/tests -Filter cdp-*.mjs | Select-String -Pattern 'mfmath' | Select-Object Path -Unique).Count
# 窗口尺寸、最小尺寸与页面地址
Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern 'inner_size|min_inner_size|UI_URL|remote-debugging-port'
```
