# MFMath.Host.Rust —— Rust/Tauri 宿主

> 状态：**可用**（不是 spike 了）。链接层 10 个宿主对象已落地 **7 个**，前端与 49 个 CDP 用例
> **一行未改**；引擎、前端都不动。
>
> 逐项的现状、踩过的坑与验收方式在 **[`docs/LINK-LAYER.md`](docs/LINK-LAYER.md)**——
> 那份文档是这件事的唯一依据，本 README 只讲"这是什么、怎么构建、怎么测"。

---

## 一、这是什么

同一套产品的第二个宿主：把 C# WPF + WebView2 换成 **Rust + Tauri v2**。
引擎（C++ `mf_mathematics.dll`）与前端（`MF_UI/MFMath.UI.Vue`）都不动。

| 层 | 位置 | 说明 |
| --- | --- | --- |
| 引擎 | `MF_Mathematics/` | 两个 C ABI：`math_call` / `function_exists`，424 个 action |
| 宿主 | **`MFMath.Host.Rust/`（本目录，现役）** · `MFMath.Host/`（C#，**2026-10-07 已废弃**，只作迁移参考） | 窗口 + WebView + **9 个宿主对象**（`ai` 归 TS） |
| 前端 | `MF_UI/MFMath.UI.Vue/` | Vue 外壳 + React 绘图页，共用 `src/lib/**` |

### 链接层：同步宿主对象，不是 `invoke`

前端的调用形状是 WebView2 的**同步** COM 宿主对象，而且用在采样热循环里：

```js
window.chrome.webview.hostObjects.sync.mf.Dispatch("expr_eval_vars_batch", "{…}")
```

Tauri 没有 `AddHostObjectToScript` 的官方对应物，但有 `with_webview()` ——
它把底层的 `ICoreWebView2Controller` 交出来，于是这条路**保住了**：

```
WebviewWindow::with_webview() → PlatformWebview::controller() → ICoreWebView2
   ├─ AddHostObjectToScript("mf"/"win"/"sys"/"diag"/"push"/"update"/"account"/…)
   ├─ SetVirtualHostNameToFolderMapping("mfmath.local", <exe>/wwwroot)
   └─ PostWebMessageAsJson（宿主 → 页面 的推送通道）
```

COM 那一层只有一份通用实现（`src/hostobject.rs`：手写 7 个 vtable 槽位 + 由
`CreateDispTypeInfo` 造出的 `ITypeInfo`）；**加一个桥 = `src/handlers.rs` 加一个分支
+ `src/main.rs` 的方法表加一段**，COM 代码一行不用动。

页面 URL 因此与 C# 宿主逐字相同：`https://mfmath.local/index.html`。

### 已实现（10 个宿主对象**全部落地**）

> 逐项现状、验收数字与踩过的坑见 [`docs/LINK-LAYER.md`](docs/LINK-LAYER.md) 的 §0.1/§0.2。
> 编译**零警告**；`--selftest-jobs` 5/5、`--selftest-common` 10/0 两条无头自检。


| 宿主对象 | 状态 | 验收用例 |
| --- | --- | --- |
| `mf`（引擎，16 方法，含异步 job 通道） | ✅ | `cdp-basic-calc` 41/0、`cdp-bridge-verify` 7/0、绘图各组 |
| `win`（窗口 + 文件对话框，10 方法） | ✅ | `cdp-window-shell` 25/0 |
| `sys`（设置/存储，8 方法） | ✅ | `cdp-settings` **43/0**（另两项由 `con` 落地转绿） |
| `diag`（前端异常入 app.log） | ✅ | 前端异常确实落进 `app.log` |
| `push`（宿主 → 页面 推送，3 方法） | ✅ | `cdp-push` **20/0**（另六项由 `con` 落地转绿） |
| `update`（更新链，6 方法） | ✅ | `cdp-update` **37/0** |
| `account`（用户系统，19 方法） | ✅ | `cdp-account` **52/0** |
| `search`（联网搜索，12 方法） | ✅ | `cdp-search` **55/0**、`cdp-history-search` **21/0** |
| `con`（控制台 + 组件下载，10 方法） | ✅ | `cdp-console` **66/0**、`cdp-console-sci` **8/0** |
| `ai`（AI 助手 + SSE 中继，11 方法） | ✅ | `cdp-ai` **127/0** |

**跑全套**（仓库自带的跑批脚本，把宿主换成 Rust 那份即可 —— 它本来就认 `MF_HOST_EXE`）：

```powershell
$env:MF_HOST_EXE = "$env:TEMP\mfhost-run\mfmath-host-rust.exe"   # 见上面"宿主 exe 要放到工作区外"
powershell -ExecutionPolicy Bypass -File <仓库>\MF_UI\MFMath.UI.Vue\tests\run-all.ps1
```

⚠ 必须用 **`pwsh`(7)** 或给脚本补上 UTF-8 BOM 后再用 `powershell`(5.1)：该脚本满是中文注释却
原本没有 BOM，5.1 会按 ANSI 读、直接解析失败（`Missing expression after ','` 那一串，一行用例都跑不了）。
本目录已一并给它加了 BOM（见提交 `3ba3447`）。

---

## 二、构建

```powershell
$repo = "<仓库根>\Multifunctional-Mathematics-v2.0"
$H    = "$repo\MFMath.Host.Rust"

# 本机（受沙箱限制）需要两条：
$env:TEMP = "$repo\.tmp-build"; $env:TMP = $env:TEMP   # ① 见下面"坑一"
$env:CARGO_HOME = "$repo\.cargo-home"                  # ② 见下面"坑二"
node "$H\tools\crates-proxy.mjs"                       # ③ 取包代理，见下面"坑三"

cd $H; cargo build
```

`cargo build` 会一并做三件事（`build.rs`，**只在新的时候拷、缺了只警告**）：

1. 引擎产物（`mf_mathematics.dll` + 5 个依赖）→ exe 同目录；
2. `MF_UI/MFMath.UI.Vue/dist` → `<exe 同目录>/wwwroot`；
3. 图标检查。

**缺了第 1 条**：界面照常打开，但启动自检会写「引擎未加载：找不到数学引擎…」，一次都算不了。
**缺了第 2 条**：页面退回 Tauri 内嵌资产，URL 变成 `http://tauri.localhost` —— 49 个 CDP 用例
会当场找不到页面。

手工同步（要放到别的目录时用）—— ⚠ **两个脚本的 `--dest` 不是一回事，别传同一个目录**：

```powershell
# 引擎：--dest 是「exe 所在的目录」
node tools/sync-engine.mjs  --dest "<exe 目录>"

# 界面：--exe 指到 exe，wwwroot 自动落到它同目录（推荐这么写）
node tools/sync-wwwroot.mjs --exe "<exe 目录>\mfmath-host-rust.exe"
# 或明确写全：--dest "<exe 目录>\wwwroot"
```

`sync-wwwroot` 的 `--dest` 是"**wwwroot 目录本身**"，而且它**会先清空目标**再拷 ——
把 exe 目录传给它，引擎 DLL 与宿主 exe 会一起被删掉。脚本现在会检测目标里有没有宿主 exe
并**直接拒绝**（这条护栏是踩过一次之后加的：我自己就在冒烟测试里把整份部署目录清空了一遍）。

### 本机开发的三条特殊处理

1. **`TEMP` 必须指到仓库内**（经自动化沙箱构建时）：受限令牌下 `%TEMP%` 不可写，
   编任何 C 依赖（`ring` / `aws-lc-sys`）都会报
   `cl.exe D8050 未能将命令行放入调试记录中` —— 看起来像编译器坏了，其实是临时目录写不了。
   **用户自己的终端里不需要这条。**
2. **`CARGO_HOME` 放在仓库内**（`<repo>\.cargo-home`）：同理，写 `~/.cargo` 会被拒。
3. **crates 走本地明文代理**（`.cargo/config.toml` + `tools/crates-proxy.mjs`）：
   本机取不到包时用它 —— Node 走 HTTPS 取、cargo 只走 127.0.0.1 明文。
   CI / 干净机器不需要这三条（删掉 `.cargo/config.toml` 即回直连）。

---

## 三、跑与测

```powershell
# 起宿主（会自己开 CDP 9222）
& "$H\target\debug\mfmath-host-rust.exe"

# 无头自检（不需要 WebView2，受限环境里也能跑）
& "$H\target\debug\mfmath-host-rust.exe" --selftest-jobs     # 异步任务通道，5 项
& "$H\target\debug\mfmath-host-rust.exe" --selftest-common   # DPAPI/sha256/zip/HTTP 环境

# 端到端（与 C# 宿主共用同一批用例）
node "$repo\MF_UI\MFMath.UI.Vue\tests\cdp-basic-calc.mjs"
```

### ⚠ 经自动化沙箱跑用例时：宿主 exe 要放到工作区**外面**

沙箱会限制"**镜像位于工作区内**的进程写工作区外"：宿主在 `target/debug` 下跑时写不了
`%LOCALAPPDATA%\MFMath`（日志、设置、WebView2 数据目录全部静默失败），用例会莫名其妙地红。
把 exe + DLL + wwwroot 拷到工作区外再跑即可：

```powershell
$run = "$env:TEMP\mfhost-run"
Copy-Item "$H\target\debug\mfmath-host-rust.exe" $run -Force
Copy-Item "$H\target\debug\*.dll" $run -Force
Copy-Item "$H\target\debug\wwwroot" $run -Recurse -Force
& "$run\mfmath-host-rust.exe"
```

（`MF_WEBVIEW2_DIR` 可指定 WebView2 用户数据目录 —— 想同时跑两份实例（例如拿一份干净的做对照）
就用它指到不同目录。**同一目录只允许一个实例**：宿主在建窗口之前会独占打开数据目录里的
`.mf-instance` 锁文件，第二个实例会被明确拦下并报出持有者的 pid（而不是撞进 WebView2 拿到一个
看不出原因的 `0x800700AA`）。这个开关名是从已废弃的 C# 宿主沿用下来的。）

---

## 四、与 C# 宿主共存

两者可以并存、互不干扰，切换成本为零：

- **前端共用**：`wwwroot` 都是 `MF_UI/MFMath.UI.Vue/dist` 的拷贝，两边读同一份；
- **数据目录共用**：`%LOCALAPPDATA%\MFMath\`（settings / logs / components / WebView2），
  设置 JSON 的字段名两边**逐字一致**；凭据是 DPAPI 密文（base64 blob，**不传 entropy**），
  Rust 侧已实测能解开 C# 侧写的密文、反之亦然；
- **端到端用例共用**：49 个 `cdp-*.mjs` 走 CDP，与宿主用什么语言无关；
- **行为对齐**：窗口尺寸/最小尺寸/数据目录/CDP 端口/页面 URL 都按 C# 宿主抄。

---

## 五、已知缺口

看 `docs/LINK-LAYER.md` 的 §0.1 与 §7（那里是清单，修完就删）。
当前主要是：`search` / `con` / `ai` 三个桥，以及一批 edition-2024 的
`unsafe_op_in_unsafe_fn` 警告（`hostobject.rs`，纯噪音不影响功能）。
