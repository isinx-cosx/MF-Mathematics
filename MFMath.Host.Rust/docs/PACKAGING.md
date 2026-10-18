# 发布形态（Rust 宿主）

> 这份文档回答一个问题：**怎么把 Rust 宿主打包成能发给用户的东西，以及哪些部分我验过、哪些没验。**
> 验收的其它步骤见 [`ACCEPTANCE.md`](ACCEPTANCE.md)。
>
> ⚠ **本文记录的 NSIS 打包方案已被替代**：Tauri 的 `tauri build --bundles nsis` 路径不再采用，
> 改为自写安装器。安装器的形态、安装卸载流程、目录布局与签名要求见 [`INSTALLER.md`](INSTALLER.md)；
> 第 9 节「NSIS 方案被替换的原因」列出替代的三个技术理由。
> 本文其余内容（载荷构成、体积实测、`resources` 覆盖的必要性）在自写安装器下**仍然成立并继续使用**。

---

## 0. 结论先说

> **以下这一段是 NSIS 时期的记录**（11.11 MiB、安装 → 跑起来在这台机器上验不了）。
> 现在出包走自写安装器，成品 18.29 MB，且「安装 → 启动 → 卸载」已在 Windows 11 本机验证，
> 见 [`INSTALLER.md`](INSTALLER.md)。本节保留作为当时的实测留档。

- **能出包**：`tauri build --bundles nsis` 在带上 `resources` 覆盖后成功产出
  `target/release/bundle/nsis/MF-Mathematics_2.0.0_x64-setup.exe`（**实测 11.11 MiB**）。
- **但"安装 → 跑起来"这条路我在这台机器上验不了**（原因见 §3），
  所以**装完的布局、安装/卸载、从安装目录启动**都还没被实测过 —— 交付前必须在真机上按 §4 走一遍。
- 兜底路线（§5，zip + 手工布局）随时可用，不依赖任何工具链。

---

## 1. 为什么需要 `resources` 覆盖（**这是最容易漏的一步**）

`build.rs` 把三样东西同步到 **exe 同目录**（`target/<profile>/`）：

| 来源 | 目标 | 大小（release 实测） |
| --- | --- | --- |
| 引擎 6 个 DLL（`mf_mathematics.dll` + symengine/flint/gmp/mpfr/pthreadVC3） | exe 同目录 | **21.78 MB** |
| `MF_UI/MFMath.UI.Vue/dist` | `wwwroot/` | **3.90 MB**（73 个文件） |
| `MFMath.Host.Rust/console/python`、`MFMath.Host.Rust/console/cpp` | `python/`、`cpp/` | 1 + 2 个文件 |

**打包器不认识这三样**：Tauri 只把 exe（和 `bundle.resources` 列出的东西）放进安装包。
不配 `resources` 的话，装出来的包**只有 exe** —— 页面白屏（没有 `wwwroot`）、算不了数（没有 DLL）、
控制台装不上组件（没有 `python/mfmath.py`）。

`resources` 我指向 **`target/release/` 下 build.rs 已经同步好的产物**（而不是重新罗列引擎源目录），
这样"哪份资产进包"只有**一个来源**：build.rs 同步什么，包里就是什么。

---

## 2. 出包命令（实测可复现）

```powershell
$repo = "<仓库根>"
$env:TEMP = "$repo\.tmp-build"; $env:TMP = $env:TEMP      # 沙箱下必需
$env:CARGO_HOME = "$repo\.cargo-home"
cd "$repo\MFMath.Host.Rust"

# 一次性：把 Tauri CLI 装到**临时目录**（不要改进 MF_UI 的 package.json，那是前端面的文件）
$cli = "$env:TEMP\tauri-cli"
npm i --prefix $cli @tauri-apps/cli@^2

$res = [ordered]@{
  "target/release/wwwroot" = "wwwroot"
  "target/release/python" = "python"
  "target/release/cpp" = "cpp"
  "target/release/mf_mathematics.dll" = "mf_mathematics.dll"
  "target/release/symengine-0.14.dll" = "symengine-0.14.dll"
  "target/release/flint-24.dll" = "flint-24.dll"
  "target/release/gmp-10.dll" = "gmp-10.dll"
  "target/release/mpfr-6.dll" = "mpfr-6.dll"
  "target/release/pthreadVC3.dll" = "pthreadVC3.dll"
}
$cfg = @{ bundle = @{
  active = $true
  targets = @("nsis")
  resources = $res
  windows = @{ nsis = @{ installMode = "currentUser" } }   # 每用户安装，不要管理员
} } | ConvertTo-Json -Depth 8 -Compress

node "$cli\node_modules\@tauri-apps\cli\tauri.js" build --bundles nsis --config $cfg
```

实测耗时：**首次 release 编译 2 分 01 秒**（之后改配置重打包 **38.7 秒**，release 二进制复用）。
首次打包会从 GitHub 下 NSIS 3.11 与 `nsis_tauri_utils.dll`（校验哈希后解压，日志里有 `validating hash`）。

> ⚠ 我用 `--config` **内联覆盖**，没有改仓库里的 `tauri.conf.json`（那里的 `bundle.active` 仍是 `false`）。
> 等你确认过真机安装没问题，再把这份覆盖**固化进 `tauri.conf.json`** —— 顺序反了会把没验过的东西
> 变成默认行为。

---

## 3. 我**没能**验证的部分（如实写明）

> **先说验到的**：release 构建的**无头自检**跑通了 —— 把 `mfmath-host-rust.exe` 与 6 个 DLL 放到
> **工作区外**（`%TEMP%\mfhost-release`）后：`--selftest-common` **10/0**、`--selftest-jobs` **5/5**。
> 也就是说 release profile 下引擎 DLL 能加载、job 通道能用、DPAPI/sha256/zip/HTTP 都正常。
>
> ⚠ 反过来，**在工作区内跑**（如 `target\release\…`）会看到 `--selftest-common` **9/1**，
> 失败项是 zip 往返的 `拒绝访问 (os error 5)` —— 因为那段自检写的是
> `logging::data_dir()/selftest-tmp`（即 `%LOCALAPPDATA%\MFMath\`，见 `selftest.rs:75`），
> 而**从工作区内起的进程写不了工作区外**。这是环境限制，不是 release 缺陷；
> 验收时按 `ACCEPTANCE.md` §0.2 把它们拷到工作区外再跑。

| 想验的 | 结果 |
| --- | --- |
| 静默安装到指定目录 | ❌ **两次都失败**：`Start-Process … /S /D=<dir>` 报 `ERROR_CANCELLED`（"操作已被用户取消"）；改用 `& <setup> /S /D=<dir>` 则静默不生效、`$LASTEXITCODE` 为空、目标目录没被创建 |
| 安装目录布局（exe + 6 DLL + `wwwroot/` + `python/` + `cpp/`） | ❌ 未能实测（依赖上一条） |
| 包内是否真的收了那 25.7 MB 资产 | ⚠️ **无法证实也无法证伪**：NSIS 的文件表是整体压缩的，扫描安装器里有没有 `wwwroot` / `gmp-10.dll` 这类明文**必然扫不到**（我扫过，没有 —— 但这不是证据）；体积也不决定性（exe 单独 13.9 MB，安装器 11.11 MB） |
| 卸载后程序目录清空、`%LOCALAPPDATA%\MFMath` 保留 | ❌ 未实测 |
| `installMode` 是否真的生效 | ⚠️ 两次构建（默认 / `currentUser`）安装表现完全相同（都启动不了），所以**"默认需要管理员"这个结论我没有证据，不要写进任何文档**。已证实的是：安装器 manifest 是 **`asInvoker`**（扫描二进制得到），文件版本 2.0.0、产品名 `MF-Mathematics` |

失败原因判断：本会话**需要审批的动作会被自动拒绝**，而运行一个会写注册表/写程序目录的安装器大概率落在这一类
（不是 UAC —— manifest 是 `asInvoker`）。这一条**属于"环境没准备好"，不是"打包做错了"**。

---

## 4. 真机上要走的验证（交付前必做）

1. 双击 `MF-Mathematics_2.0.0_x64-setup.exe` → 按提示安装（每用户，不需要管理员）。
2. 打开安装目录，逐项确认：`MF-Mathematics.exe`、6 个引擎 DLL、`wwwroot\index.html`、
   `python\mfmath.py`、`cpp\`。
3. 启动它，然后：
   - `curl.exe -s http://127.0.0.1:9222/json/list` → URL 必须是 **`https://mfmath.local/index.html`**；
   - `%LOCALAPPDATA%\MFMath\logs\app.log` 里必须有 **9 个宿主对象**的注册行，**并且没有 `ai`**；
   - 随手算一条：能在引擎里算出结果（证明 6 个 DLL 都在）。
4. 附着跑一遍用例：`pwsh -File tests\run-all.ps1 -NoLaunch`（不要另起宿主）。
5. 卸载：程序目录应被清空，`%LOCALAPPDATA%\MFMath`（用户数据：设置/日志/组件/工作区）**必须保留**。

> 做完第 2、3 步，才可以把 §2 的覆盖固化进 `tauri.conf.json`；做完第 5 步，才算"发布形态可用"。

---

## 5. 兜底路线：zip + 手工布局（不依赖任何工具链）

如果 NSIS 那条路在真机上也有问题，或者你暂时不想引入打包器：

```powershell
# 产物目录（就是 build.rs 同步好的那份，天然等同"安装后布局"）
$stage = "$repo\MFMath.Host.Rust\target\release"
# 只挑运行需要的东西，避免把 build/ 之类的中间物也带上
Copy-Item "$stage\mfmath-host-rust.exe" "$out\MF-Mathematics.exe"
Copy-Item "$stage\*.dll" $out
Copy-Item "$stage\wwwroot" $out -Recurse
Copy-Item "$stage\python"  $out -Recurse
Copy-Item "$stage\cpp"     $out -Recurse
Compress-Archive -Path "$out\*" -DestinationPath "MF-Mathematics-2.0.0-win-x64.zip"
```

注意与 NSIS 的**两个差异**：① exe 名字（NSIS 用 `productName` → `MF-Mathematics.exe`，cargo 产物叫
`mfmath-host-rust.exe`，这里改名只是为了观感，程序不依赖自己的文件名）；② 没有安装/卸载与开始菜单项。
另外要一并说明 **WebView2 运行时**是系统依赖（Win11 自带；Win10 老机器需装 Evergreen Runtime）——
宿主不负责安装它，缺了会得到一条可读的启动失败提示。

---

## 6. 与 `.gitignore` 的关系

产物都在 `target/`（已忽略）与 `.tmp-build/`（已忽略，`.gitignore` 的 `.tmp-*` 覆盖）下，
**不要**把安装包或 DLL 提交进仓库（`README.md` 已说明理由：可重建，且会让历史迅速膨胀）。
