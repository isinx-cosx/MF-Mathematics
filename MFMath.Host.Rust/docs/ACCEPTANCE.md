# 验收清单（Rust 宿主）

> 这份清单是**照着跑就能复现**的验收步骤。每一项都写"期望值"与"判据从哪来"，
> 不写"应该没问题"这类话。**数字会随代码变化** —— 变了就更新这里，别让它变成装饰。
>
> 当前基线见 `docs/LINK-LAYER.md` §0.1；架构决策（AI 归 TS）见 §8。

---

## 0. 前提：三段构建 + 一个工作区外的运行目录

### 0.1 构建（本机沙箱必需的两个环境变量）

```powershell
$repo = "<仓库根>"
$env:TEMP = "$repo\.tmp-build"; $env:TMP = $env:TEMP     # 沙箱下 %TEMP% 不可写会让 cl.exe 报 D8050
$env:CARGO_HOME = "$repo\.cargo-home"                    # 不要写用户级 CARGO_HOME
cd "$repo\MFMath.Host.Rust"
cargo build --message-format short                       # 期望：Finished，且 warning 数 = 0
```

前端（改了 `src/**` 才需要）：

```powershell
cd "$repo\MF_UI\MFMath.UI.Vue"
npm run build            # 期望：✓ built in …（chunk>500kB 的警告属正常）
npm run check:types      # 期望：0 错误
node tools/check-ui.mjs  # 期望：自检通过 ✔，且"端到端用例 N 个已登记 N 个"
```

### 0.2 部署到工作区外（**必须**）

工作区内的进程写不了 `%LOCALAPPDATA%`（日志/设置会静默失败），所以验收要跑在工作区外：

```powershell
$run = "$env:TEMP\mfhost-run"
node "$repo\MFMath.Host.Rust\tools\sync-wwwroot.mjs" --exe "$run\mfmath-host-rust.exe"
```

> ⚠ `sync-wwwroot.mjs` 会**清空目标 `wwwroot`**，所以它拒绝把 exe 目录（含
> `mfmath-host-runtime.exe` / `MFMath.exe`）当作目标 —— 别绕过这道闸门。

### 0.3 起宿主

```powershell
Start-Process "$run\mfmath-host-rust.exe"
# 带搜索假端点时（跑 cdp-search 用）：
$eps = '{"ddgHtml":"http://127.0.0.1:8792/ddg/html","ddgIa":"http://127.0.0.1:8792/ddg/ia","wolfram":"http://127.0.0.1:8792/wolfram/result"}'
Start-Process "$run\mfmath-host-rust.exe" -Environment @{MF_SEARCH_ENDPOINTS=$eps}
```

页面 URL 必须是 **`https://mfmath.local/index.html`**（47 个用例的取页正则靠它）：

```powershell
curl.exe -s http://127.0.0.1:9222/json/list | Select-String mfmath
```

---

## 1. 无头自检（不起窗口，最先跑）

| 命令 | 期望 | 判据 |
| --- | --- | --- |
| `mfmath-host-rust.exe --selftest-jobs` | **5/5** | job 通道（`DispatchJob`/`PollJob`/`CancelJob`）的并发与取消 |
| `mfmath-host-rust.exe --selftest-common` | **10/0** | 共享件：DPAPI 往返、HTTP 客户端、SHA-256/zip |
| `mfmath-host-rust.exe --selftest-con` | 视实现 | `con` 的下载/解压/校验（**若尚未实现，跳过并记一笔**） |

---

## 2. 宿主对象注册面 = **9 个**（AI 刻意不在其中）

启动日志会逐个打印对象与方法数。期望（2026-10-07 基线）：

| 对象 | 方法数 | 说明 |
| --- | --- | --- |
| `mf` | 16 | 含 job 通道三件套 |
| `win` | 9 | `Restore` **已删**（C# 有、两侧前端都没人调） |
| `sys` | 8 | 含 `ExportDiagnostics` |
| `diag` | 1 | `Front`（Tauri 命令 `front_log` 那条路已删） |
| `push` | 3 | 信封 `{topic,seq,ts,payload}` |
| `update` | 6 | |
| `account` | 19 | |
| `search` | 12 | |
| `con` | 10 | |

**`ai` 不在这里，这是正确的**（AI 归 TS，页面直连；见 `LINK-LAYER.md` §8）。
判据：`cdp-ai` 必须在一个**没有 `ai` 宿主对象**的宿主上全绿 —— 那才是"AI 不再依赖宿主"的证据。

---

## 3. CDP 端到端用例

```powershell
$env:MF_HOST_EXE = "$env:TEMP\mfhost-run\mfmath-host-rust.exe"
cd "$repo\MF_UI\MFMath.UI.Vue\tests"
pwsh -NoProfile -ExecutionPolicy Bypass -File .\run-all.ps1
```

### 3.1 `run-all.ps1` 登记在册的 26 组

`unit-result-model`、`unit-sse`、`unit-markdown`、`cdp-plot-accuracy`、`cdp-bridge-verify`、
`cdp-plot-region`、`cdp-plot-extrema`、`cdp-complex-modes`、`cdp-diff-at-param`、`cdp-console`、
`cdp-tutorials-keypad`、`cdp-settings`、`cdp-settings-io`、`cdp-engine-solve`、
`cdp-history-search`、`cdp-console-sci`、`cdp-push`、`cdp-workspace`、`cdp-export-image`、
`cdp-shortcuts-prefs`、`cdp-expr-normalize`、`cdp-ai`、`cdp-search`、`cdp-account`、`cdp-update`、
`audit-modes`

`tests/` 下另有若干**未登记进 run-all** 的组（如 `cdp-plot-p3/p4/p5`、`cdp-appearance`、
`cdp-font-load`、`cdp-window-shell`、`cdp-input-notation`、`cdp-plot-final/fractal/asymptote/3d/vector`、
`cdp-modes-render`、`cdp-engine-coverage` 等），需要时单独跑。
**它们也是验收的一部分**，只是当前没进一键脚本。

### 3.2 期望：每组 **0 fail**

唯一的例外是"已知易抖"那几条（见 §3.3），且必须能被单独复现为通过。

### 3.3 已知会互相影响 / 易抖的组（附证据，别当成回归）

| 现象 | 证据 | 处置 |
| --- | --- | --- |
| `cdp-export-image` 紧跟 `cdp-plot-verify` 在同一宿主会话里跑 → **20/13**（单独跑 43/2） | 本会话实测 | 成套跑时尽量让**每组独占一个宿主进程** |
| `cdp-modes-render` 成套 **189/2**、单独 **191/0** | 本会话实测 | 同上 |
| `cdp-engine-coverage` 成套跑会**大量超时**（296/7，全是超时） | 仓库提交 `b6a77c0` | 单独跑；超时要与"真失败"分开看 |
| 首屏冷缓存时页面加载慢 → 早期用固定 `sleep` 会假失败 | 本会话实测（同一构建有时 52/0、有时满屏 Uncaught） | 用例已改成 `waitTrue` 轮询，新用例照此写 |
| **2026-10-07 10:20 实测的成套 vs 单跑对照**（同一份 wwwroot、同一宿主构建，`run-all.ps1` 全量 **2142/20**） | | |
| `cdp-font-load` 成套 **6/12** → 单独 **18/0** | 上面那次全量的产物 | 成套数字不可信，**单跑为准** |
| `cdp-appearance` 成套 **32/1** → 单独 **33/0** | 同上 | 同上 |
| `cdp-plot-p5` 成套 **11/1** → 单独 **12/0** | 同上 | 同上 |
| `cdp-plot-asymptote` 成套 **6/1** → 单独 **7/0** | 同上 | 同上 |
| `cdp-plot-fractal` 成套 **9/5** → 单独 **12/2**（那条 `提高迭代后重新渲染` / `滚轮缩放改变窗口并重算` **稳定复现**，连跑三次都在） | 同上 | ⚠ **这一条不是干扰，是真失败**；属于前端绘图面（B），不在宿主面（A）的处理范围 |

> 结论口径：**全量的 fail 数不能直接当回归数**。要先把每一组单独跑一遍，
> 只有"单独跑也红"的才算真失败（上表最后一行就是这种）。

---

## 4. 与 AI 架构相关的专项（这次变更的重点）

| 检查 | 期望 | 判据 |
| --- | --- | --- |
| 宿主里没有 `ai` 对象 | 注册面只有 §2 那 9 个 | 启动日志 |
| `cdp-ai` 全绿 | **160/0** | 用例输出 |
| 请求**确由页面发出** | 假端点收到 `Origin = https://mfmath.local` | `cdp-ai` §⑤ |
| 不再依赖宿主推送 | push 日志里没有任何 `ai.*` 话题 | `cdp-ai` §⑦ |
| 密钥来源如实 | `keySource: "file"`、`keyPersisted: true`、脱敏视图里没有 `apiKey`/`apiKeyProtected` | `cdp-ai` §① |
| **绝不退回内置站点** | 非法/空 `baseUrl` 一律报 `config` 错，错误文本里不出现内置域名 | `cdp-ai` 纯函数 + 行为断言 |
| 旧版密文不假装可用 | `hasKey:false` + 设置页提示"请重填一次" | `cdp-ai` §⑨ |
| 跑完不留残留 | `ai.json` 无 `apiKey`、无 `apiKeyProtected`、`enabled:false`、`baseUrl` 回生产域名 | `cdp-ai` 收尾断言 |

---

## 5. 只有真机能验的（本机做不了，交付前请在带代理的机器上跑）

1. **AI 直连**：企业认证代理下、以及非 DeepSeek 的服务商（本机只实测过 DeepSeek 与 GitHub）。
2. **搜索**：真实 DDG HTML/IA 的 markup（解析器是手写扫描器）、自建 SearXNG 带 `?format=json` 的网关。
3. **组件下载**：真实 CDN 的 Range/断点续传；`taskkill` 不可用的受限环境（应看到 `app.log` 里那条 WARN）。
4. **账号**：真实站点契约（登录/刷新/401 自动登出）。
5. **更新**：站点 `/api/version` 比本机旧的场景（必须判定为"不需更新"，不能把用户引去下载站点上的旧安装包）。

---

## 6. 一键跑法（把上面的都串起来）

```powershell
# 1) 构建（0 警告）
# 2) 部署到工作区外 + 起宿主
# 3) 无头自检 5/5、10/0
# 4) 确认页面 URL = https://mfmath.local/index.html
# 5) 确认宿主对象 = 9 个（没有 ai）
# 6) run-all.ps1（26 组）+ 未登记的组
# 7) 记下每组的 pass/fail —— 任何 fail 都要能单独复现，否则先按 §3.3 排查顺序影响
```

> ⚠ 跑全量前先确认 `dist` 的构建时间戳，并**记进结论**：如果工作区里还有别人正在改的前端代码，
> 数字反映的是"那份未提交的代码"，不是被测提交。

---

## 7. 发布形态（单独一份，见 `PACKAGING.md`）

打包/分发不在上面的用例里。`PACKAGING.md` 里写了：出包命令（含**必须**配的 `resources` 覆盖 ——
漏了它，装出来的包就只有 exe，页面白屏且算不了数）、实测产物与体积、
**我在这台机器上没能验证的部分**（安装器在本会话无法启动：`Start-Process` 报 `ERROR_CANCELLED`，
直接调用静默不生效；manifest 是 `asInvoker` 所以不是 UAC），以及真机上要走的五步验证。

> AGENTS.md §4 的并发规矩在这里同样适用：**起宿主前先看有没有别人在跑**，优先用
> `run-all.ps1 -NoLaunch` 附着到已有宿主，不要另起一个。
