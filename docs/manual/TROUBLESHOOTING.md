# 排障手册：出了问题怎么排查

> **本文只回答一个问题：出了问题怎么排查。**
>
> 与同层其它文档的分工：
> - [README.md](README.md) —— 为谁做、能做什么、**不能做什么**（总入口）；
> - [FEATURES.md](FEATURES.md) —— 功能全表（14 学科视图、6 类绘图、工具、AI、学习、系统）；
> - [WORKFLOWS.md](WORKFLOWS.md) —— 典型用法（算题、画图、AI 步骤、控制台、导出与工作区）；
> - [INSTALL.md](INSTALL.md) —— 安装与构建（⚠ 受 Rust 宿主"安装 → 启动"真机验证阻塞）；
> - [FAQ.md](FAQ.md) —— 常见问题（为什么算不出来、离线承诺、为什么不上报崩溃、许可证）。

**核对时间**：2026-10-07 11:11（读源码 + 在本机现存产物上实跑命令；命令与输出原文都在下面）。
**本文不回答**：现在还缺什么功能、有哪些已确证的缺陷 —— 那是状态类文档，见 [docs/OPEN-ITEMS.md](../OPEN-ITEMS.md)、[MF_UI/BUGS.md](../../MF_UI/BUGS.md)、[docs/PROJECT-BOARD.md](../PROJECT-BOARD.md)。

---

## 0. 先做这四件事（任何症状都适用）

| # | 做什么 | 为什么 / 判据 |
| --- | --- | --- |
| 1 | **确认日志目录里有没有东西** | 日志与崩溃**只写本地**（[DECISIONS.md](../DECISIONS.md) D-008）。`%LOCALAPPDATA%\MFMath\logs`（`logging.rs:35-46`）。目录是空的，说明宿主根本没走到写日志那一步，或 exe 跑在工作区内的受限位置（`ACCEPTANCE.md` §0.2） |
| 2 | **确认页面 URL 是 `https://mfmath.local/index.html`** | 用例取页的正则靠它（`ACCEPTANCE.md` §0.3 原话是"47 个用例"）；宿主自己声明的常量在 `main.rs:309-310` |
| 3 | **确认引擎在不在** | `app.log` 里搜 `引擎自检`：期望 `引擎已加载，list_functions.count = 424`（`main.rs:388` → `handlers.rs:386-400`） |
| 4 | **确认宿主对象是不是 9 个** | `app.log` 里应有 9 行 `宿主对象 <name> 已注册（<n> 个方法）`（`main.rs:533`），清单与期望方法数见 `ACCEPTANCE.md` §2；`ai` **故意不在其中** |

一条命令把 1、3、4 一起看：

```powershell
$logs = Join-Path $env:LOCALAPPDATA 'MFMath\logs'; Get-ChildItem $logs | Sort-Object LastWriteTime -Descending | Select-Object -First 8 Name,Length,LastWriteTime
Select-String -Path "$logs\app.log" -Pattern '宿主对象|引擎自检|WebView2 用户数据目录|UI 目录'
```

> ⚠ **失败必须先分类**：**产品缺陷** / **用例判据错** / **环境没准备好**（[AGENTS.md](../../AGENTS.md) §5）。
> ① `MF_UI/BUGS.md` §0.2 曾把 88+37+27 条失败归给"宿主缺桥"，随后被并行提交推翻（`BUGS.md:71-87`）；
> ② 全量跑的 fail 数**不能直接当回归数**：成套 6/12 的用例单跑是 18/0（`ACCEPTANCE.md` §3.3）。
> 任何"某处失败 ⇒ 归因给环境/宿主"的结论**必须带时间戳**（[AGENTS.md](../../AGENTS.md) §5 第 1 条）。

---

## 1. 点了没反应，或界面卡住

### 1.1 先分四种形态（判据不同，别混成一件事）

| 形态 | 现场判据 | 归类 |
| --- | --- | --- |
| 按钮/菜单**点了完全没动静**，界面其余部分能动 | `app.log` 里有 `[前端] 未捕获异常 @#/…`（`logging.rs:218-226`） | 前端异常（见 §1.2） |
| 弹窗/提示写了"**未检测到引擎桥（请在 MFMath.exe 中运行）**" | `CalcView.vue:371-376`（`result === null`） | 不在宿主里跑，或桥名不对（见 §1.3） |
| **白屏 + 系统标"未响应"**，几秒到几分钟 | 同步桥占住渲染进程主线程（`bridge.js:140-144`、`jobs.rs:3-7`） | 重活走了同步通道，或引擎在算（见 §1.4） |
| 宿主窗口**根本出不来** | stderr 有 `[rust-host] … 失败`，且写了 `crash-*.log` | 见 §1.5（`0x800700AA`） |

### 1.2 "点了没反应" = 多半是事件处理器抛了异常

**React 的错误边界不捕获事件处理器抛出的异常**，所以不会渲染失败页，表现就是"按钮没反应"
（`BUGS.md:459`，B3 就是这么被发现的：`zoomFit` 必抛 `ReferenceError`）。但异常**不会丢**：
未捕获异常 / 未处理 Promise / Vue 组件异常三类都由 `installErrorReporting`（`main.js:22`）经 `diag`
写进**同一个** `app.log`，前缀 `[前端]`（`errors.js:54-72` → `handlers.rs:287` → `logging.rs:218-226`）。

```powershell
Select-String -Path (Join-Path $env:LOCALAPPDATA 'MFMath\logs\app.log') -Pattern '\[前端\]' | Select-Object -Last 20
```

复现一次卡住的点击再跑它：有 `@#/plot/2d` 这类路由与异常名就定位到文件了；
**日志里一条都没有**，才考虑"没抛异常但也没做事"（那要读代码，不是猜）。

### 1.3 "宿主没有那个桥"——**这是一个已经作废的结论**，先验证再下结论

跑端到端失败时，最容易得出的错结论是"宿主缺 `ai`/`search`/`account`/`update` 桥"。
`BUGS.md:71-87` 记录了这次误判：当时 Rust 宿主确实只有 `mf/sys/diag/win/push`，但并行提交很快补齐，
用**最新提交**重新构建后同样的套件逐条转绿（`cdp-ai` 39/88 → **160/0**）。现场三问，任何一条不符就先别写"缺桥"：

| 问 | 命令 / 位置 | 期望 |
| --- | --- | --- |
| 页面 URL 对不对？ | `curl.exe -s http://127.0.0.1:9222/json/list \| Select-String mfmath` | `https://mfmath.local/index.html` |
| 页面看得到桥吗？ | 页面里 `!!window.chrome?.webview?.hostObjects?.sync?.mf`（`cdp-bridge-verify.mjs:43`） | `true` |
| 桥能调通吗？ | `window.chrome.webview.hostObjects.sync.mf.FunctionExists('solve_sym')`（`cdp-bridge-verify.mjs:44`） | `true` |
| 宿主注册了几个对象？ | `app.log` 里 `宿主对象 X 已注册（N 个方法）` | 9 行，方法数见 `ACCEPTANCE.md` §2 |

> ⚠ 成员名 **PascalCase 且大小写敏感**：写 `mf.dispatch` 会抛 `0x80070057`（不是返回 `undefined`），
> 所以"用 `typeof` 试探"这条路不通（`bridge.js:4`、`errors.js:62-67`）。

**要看到桥"实际被问了什么"**：用 `MF_TRACE_DISPATCH=1` 起宿主，会把每次 `QI` 与 IDispatch 调用
追加到 `<exe 目录>\dispatch-trace.log`（`hostobject.rs:68-87`）。这是"点了没反应，但桥调用到底有没有发生"的唯一直接证据。

### 1.4 卡住：先看是不是"引擎在算"，以及取消是**假的**

| 事实 | 出处 |
| --- | --- |
| 同步 `mf.Dispatch` 会占住 WebView2 的 UI 线程；重活走 `DispatchJob` + `PollJob` 轮询 | `bridge.js:140-158`、`jobs.rs:1-18` |
| `CancelJob` 只能**停止等待 + 丢弃结果**：引擎没有取消钩子，工作线程会把它算完 —— 所以界面文案只能是"**已取消等待**"，不能写"已停止" | `jobs.rs:15-17`、`bridge.js:154-158` |
| 分界线由 `lib/engine/asyncPolicy.js` 决定；轻活仍同步（毫秒级），重的才走后台 | `CalcView.vue:316-323` |

**已知会慢的地方**（不是缺陷，是设计上还没优化）：持续同调 O(n³)、12×12 以上符号矩阵、
`roots_in_disc`、`expand((x+1)^10000000)` —— 完整清单见 [docs/HANG-OPTIMIZATION.md](../HANG-OPTIMIZATION.md) §4，别重复在这里写。

**大型病态输入现在会"快速明确拒绝"**：82 处取参收口到带上限的 `get_int_bounded`（`HANG-OPTIMIZATION.md:83-90`），
验证结果 40 REJECTED / 4 OK、**0 HANG 0 CRASH**（[hang-fix-verification.md](../hang-fix-verification.md):55-62）。
看到"…超出可计算范围 [lo, hi]：收到 N…"就是这一层，**不是坏了**。

> 🚩 **最贵的操作坑：套件跑到一半 Ctrl-C。**
> 中途杀掉会留下一支没跑完的后台任务占住引擎，此后页面上**任何同步 engine 调用都会永久阻塞** ——
> 渲染进程卡死，连 `location.hash` 这种纯 DOM 读取都超时（实测卡死 30+ 分钟）。
> **要中断就先停宿主**（杀 `mfmath-host-rust` 再起，恢复几秒）。见 `BUGS.md:116-121`、`BUGS.md:1096-1099`。

### 1.5 `0x800700AA`：WebView2 数据目录被占用

宿主**在建窗口之前**就会自己查一次：用独占共享模式打开数据目录里的 `.mf-instance` 锁文件
（`share_mode(1)`），锁文件里写着持有者的 pid（`main.rs:239-283`）。所以：

| 你看到的 | 含义 | 怎么确认 / 怎么办 |
| --- | --- | --- |
| 启动直接报"WebView2 数据目录正被另一个实例占用：`<dir>`（pid=…）" | 真的有两个实例 | 读 `%LOCALAPPDATA%\MFMath\webview2\.mf-instance` 里的 pid；结束那个进程 |
| 走到建窗口才报 `HRESULT(0x800700AA)` + 提示"结束掉 `msedgewebview2.exe`，或 `MF_WEBVIEW2_DIR` 指到别的目录" | 启动前的租约检查**没**命中，多半是上次异常退出残留的 WebView2 子进程 | `Get-Process msedgewebview2`。⚠ 区分：CBS/SearchHost 的实例不属我们（`BUGS.md:250-251`） |
| 换了**全新目录**仍报同一个码 | **不是**"另一个实例" | 见下 |

> ⚠ **这条提示文案本身会误导排查方向。** `BUGS.md:239-253` 记着实测：`MF_WEBVIEW2_DIR` 指到全新目录
> 同样报错、不带 `--remote-debugging-port=9222` 同样起不来、系统里**没有任何** `mfmath-host-rust.exe`
> 且 6 个 `msedgewebview2.exe` 全属 `SearchHost.exe`。结论是**宿主侧（A 面）的问题**，属产品缺陷而非环境。
> **未证实**：截至本文核对，没看到该问题被修好的证据 —— 要验证只能在真机上重跑一次建窗口，
> 并把 `crash-*.log` 与 `app.log` 一并留档。

其它旋钮：数据目录默认 `%LOCALAPPDATA%\MFMath\webview2`，优先读 `MF_WEBVIEW2_DIR`（`main.rs:225-234`）；
UI 目录优先读 `MF_WWWROOT`，否则 `<exe 目录>\wwwroot`（`main.rs:293-306`）；`wwwroot` 缺失时退回 Tauri 内嵌资产、
页面 URL 变成 `tauri.localhost`（`main.rs:296-299`）—— **URL 一变，一串用例会假失败**，先按 §0 第 2 条确认。

---

## 2. 算不出来：先分清"如实未实现"和"真失败"

**纪律①"不编造结果"的落地形态就是**：算不出来返回"未实现"，而不是硬给一个式子（[README.md](../../README.md):229-230）。
所以"算不出来"本身**可能就是正确答案**。四种封套必须分清：

| 引擎返回（原文形态） | 含义 | 归类 |
| --- | --- | --- |
| `{"isError":false,"value":"未实现"}` | 如实拒绝（非初等函数等） | **设计选择，不是缺陷** |
| `{"isError":true,"value":"未找到函数: <fn>"}` | action 名不存在：拼错，或注册表是空的 | 产品缺陷（见 §2.1） |
| `{"isError":true,"value":"…超出可计算范围 [lo, hi]：收到 N…"}` | 上限拒绝，防卡死 | 设计选择；改用更小规模或分批 |
| `{"isError":true,"value":"缺少必填参数 point（应为数字）。本次调用传入的参数键：expr"}` | 参数没给全 | 用例判据错 / 输入不全 |
| 界面上写着"缺少必填参数：…。请在…补上" | UI 侧**拒绝计算**，根本没调引擎 | 输入不全（`CalcView.vue:360-368`，B4 的修法） |

**不起宿主直接问引擎**（本机实测，2026-10-07；`probe_call.exe` 在 `MF_Mathematics\build\bin\Release\`，
该目录不在 git 里：`README.md:94`，换机器要先构建）：

```powershell
$p = "MF_Mathematics\build\bin\Release\probe_call.exe"
& $p list_functions '{}'                                  # {"isError":false,"value":{"count":424,…}}
& $p integrate       '{"expr":"x**x","var":"x"}'          # {"isError":false,"value":"未实现"}
& $p diff_at         '{"expr":"x^2"}'                     # {"isError":true,"value":"缺少必填参数 point（应为数字）。…"}
& $p bernoulli_number '{"n":100000}'                       # {"isError":true,"value":"…超出可计算范围 [0, 500]：收到 100000。…"}
& $p not_a_real_action '{}'                               # {"isError":true,"value":"未找到函数: not_a_real_action"}
```

### 2.1 如果**所有** action 都返回"未找到函数"

那是**注册表整个为空**，不是参数问题。成因在链接期：每个 `*_api.cpp` 靠一个**没有外部引用的全局注册器**注册，
自建导出 DLL 时不加 `/WHOLEARCHIVE`，链接器会把这些目标文件整个丢弃 —— 而这种失效是**静默的**
（DLL 照常加载、`function_exists` 照常能调）。守门断言就是 `count == 424`（`README.md:154`、`README.md:196-199`）。

### 2.2 结果"看着像答案但不对"

按 B1/B2/B4 那一类**参数契约失配**查：UI 声明的键名与引擎实际读的键名不一致时，用户填了也不生效。
现役闸门是 `npm run check:args`（`tools/check-arg-contract.mjs`，已进 `npm run check`），判据见 [MF_UI/BUGS.md](../../MF_UI/BUGS.md) §0.4。

### 2.3 `[超时]` / 没有 `RESULT` 行

**不要**当成"算法错了"：先按 §1.4 排查，并确认没有被别的会话并发驱动同一个页面 ——
`cdp-engine-coverage` 的 7 条失败**全部**是 `[超时]`，真因是并发驱动，且单独跑那 4 个可疑模式全程 0–3 ms
（`BUGS.md:160-198`）。并发**只会造成假失败，不会造成假通过**（`BUGS.md:196-197`）。

---

## 3. 字体与公式显示不对

**先分三种现象**，它们的修法完全不同：

| 现象 | 真因 | 怎么确认 |
| --- | --- | --- |
| 公式/变量渲染成**方框、豆腐块**，间距怪 | 字体文件没加载到（woff2 不在产物里，或 `wwwroot` 是旧的） | 打开 DevTools 看 Network 里 `KaTeX_*.woff2` 的状态码；`dist` 里应有 `KaTeX_*.woff2` |
| 公式位置显示成 `\frac{a}{b}` 这样的**纯文本源码** | **不是字体问题**：KaTeX 渲染失败后**主动退回纯文本**（`MathLatex.vue:20-40`），键面同理（`keyFace.js:73-98`） | 看该元素的 `data-tex` 在不在；`MathLatex.vue:38` 渲染成功才挂 `data-tex` |
| 整个界面像旧版 | `wwwroot` 没同步：`npm run build` 之后**必须**重新 `sync-wwwroot.mjs` | `AGENTS.md` §4；`sync-wwwroot.mjs` 会**清空目标 `wwwroot`**，见 `ACCEPTANCE.md` §0.2 |

**为什么会"字体被删掉"**：`npm run build` = `vite build && node scripts/prune-fonts.mjs`
（`MFMath.UI.Vue/package.json` 的 `scripts.build`），最后一步只保留 `.woff2`（WebView2/Chromium 一定命中它），
把 `.woff/.ttf/.otf/.eot` 删掉（`prune-fonts.mjs:2-14`、`:80-91`）。规则保守：**只有该「字体族+字重」确实存在 woff2 时才删**，
否则整组保留并打警告（`prune-fonts.mjs:16-19`、`:91-95`）。已知留下来的 2 个文件是 `KaTeX_Size3` 的 `.woff`/`.ttf`
（它的 woff2 被 Vite 内联成 `data:font/woff2`），**不是漏删**（`prune-fonts.mjs:21-25`）。

**唯一权威的字体判据**（真宿主里跑，已进 `run-all.ps1` 总回归；期望 **18 通过 / 0 失败**，`BUGS.md` §0.2 有实测）：

```powershell
node MF_UI\MFMath.UI.Vue\tests\cdp-font-load.mjs
```

它断言四件事（`cdp-font-load.mjs:133-184`）：① 只请求 `.woff2`、全部 200、没有 woff/ttf 回退请求；
② `document.fonts` 里 `KaTeX_Main`/`KaTeX_Math`/`KaTeX_Size1`/`KaTeX_Size2`/`KaTeX_AMS`/`KaTeX_Caligraphic`/`KaTeX_Fraktur` 都 `loaded`；
③ 真字体**确实参与排版**（canvas 量宽与回退字体不同）；④ 字形族**逐族**落点正确（`\mathbb→AMS`、`\mathcal→Caligraphic`、
`\mathfrak→Fraktur`、`√→Size1`、`∫→Size2`）—— 某一族文件被误删时它会**点名**。
注意它用 `.cb-input`/`.cb-mode` 定位（`:78-89`），即**只覆盖 Vue 壳的计算页**。

---

## 4. 控制台的可选组件装不上

### 4.1 先看是哪一类

| 界面文案 | 字段 | 含义 |
| --- | --- | --- |
| "未安装（组件包已在本地，约 N MB，点安装即可）" | `payloadAvailable:true` | 包已在 `cache/` 或 `<exe>/components/`，安装不会再联网 |
| "未安装（上次只下到 N MB，点安装会接着下）" | `payloadPartial:true` | 存在 `<包名>.part`，会带 `Range` 续传 |
| 有"安装"但点了报"组件不完整" | `cpp.ready:false` | 见 §4.4 |
| 作业 `state="error"` | `con.InstallStatus` 的 `message` | 读原文：里面带下载地址、断点文件名与手工兜底办法 |

文案出处 `ConsoleView.vue:81-83`；字段由宿主算出（`console.rs:194-211`、`:231-287`）。
**关键：`payloadAvailable` 是纯本地判据**（只查 `cache_dir()` 与 `<exe>/components/`，`console.rs:207-211`），
它**不能**说明站点上有没有这个包。

### 4.2 断点续传与校验（"下载失败"要看清是哪种失败）

| 机制 | 细节 | 出处 |
| --- | --- | --- |
| 下载地址 | `{base}/download/component/{python\|mingw}`（⚠ 组件的**下载名**是 `mingw`，安装名是 `cpp`） | `console.rs:553`、`:800`、`:849` |
| 默认基址 | `https://mf-vis-science.cn`；可被 `__MF_COMPONENT_BASE` → `MF_COMPONENT_BASE` → `SetDownloadBase` 覆盖（会话级、不落盘） | `console.rs:80`、`:150-159`、`:181-189` |
| 续传 | 进度存 `<包名>.part`，请求带 `Range: bytes=<have>-`；服务端返回 `200`（忽略 Range）→ **丢弃已下字节从头写**；`416` → 删 `.part` 重来；最多 **3 轮** | `console.rs:511-532`、`:559-587` |
| 校验 | 整包 SHA-256：内置常量，或被校验文件旁边的同名 `<包名>.sha256` 旁文件**优先**（换自建包不必改代码）；对不上就当失败 | `console.rs:61-62`、`:736-741`、`:755-770` |
| 校验失败 | **保留 `.part`**，绝不进解压（否则报错会指到"解压后没有 python.exe"这种误导性地方） | `console.rs:518-520` |
| 失败原文 | 路径里就写着断点文件位置与"手工把 zip 放到哪"；取消同样用 `state="error"` 承载，且**解压/dlltool/替换目录完全不响应取消** | `console.rs:589-594`；[link/FEATURES.md](../link/FEATURES.md) §5.2 |

**手工兜底**：把 `<包名>.zip` 直接放进 `%LOCALAPPDATA%\MFMath\components\cache\`（或 `<exe>\components\`）后再点安装，
宿主会跳过下载直接校验（`console.rs:548-551`、`:207-211`）。

### 4.3 "组件包未上传 ⇒ available 为 false"要小心这里的同名不同物

有两件东西都叫"可用/available"，**不是一个字段**：

| 说法 | 谁算的 | 判据 |
| --- | --- | --- |
| `payloadAvailable` | **宿主** | 只看**本地**缓存/应用目录里有没有这个 zip（`console.rs:194-211`） |
| 站点清单里的 `available:false` | **站点** | 见 [DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md):98、[OPEN-ITEMS.md](../OPEN-ITEMS.md):119：两个 zip（python 11 MB / mingw 54 MB）**尚未上传** |

Rust 宿主的组件清单是**编译进代码的常量，没有远程清单**（[link/FEATURES.md](../link/FEATURES.md) §5.1；
常量在 `console.rs:44-66`）。**所以站点没上传包时桌面端不会"提前知道"**，只有 `Install` 真去下载才报错，
而 `payloadAvailable` 仍是 `false`。**怎么确认属于这一类**：`con.Install` 的 `message` 里会出现
`组件下载失败：…` 与那条 `{base}/download/component/…` 地址，把它贴到浏览器/`curl.exe -I` 上看服务端返回码。
**未证实**：仓库里**没有任何代码**读 `/api/components`（全仓 grep 只命中两份 md）—— 那句"清单如实标 `available:false`"
描述的是**站点侧**的事。

### 4.4 "下拉里有 C++，一跑就报缺件"

`cpp.ready`（决定 C++ 是否出现在语言下拉）**只检查两件文件**：`lib\libmf_mathematics.a` + `include\mfmath.hpp`；
而实际运行还要求第三件 `include\mfmath_autorun.hpp`。**只缺第三件时就是"能选、一点就报组件不完整"**
（`console.rs:258-287`；`link/FEATURES.md` §5.5 已登记为代码行为问题）。

---

## 5. 登录与更新失败

### 5.1 什么时候会清掉登录态（**修正一条流传的说法**）

`site.rs:178` 把 **401 与 403 都映射为 `unauthorized`**，而 `clear_token()` 在 `RefreshProfile` 与
`RefreshToken` 收到 `unauthorized` 时清登录态。所以准确表述是：

> **401 或 403 才清登录态**；404 / 429 / 5xx / 网络 / 超时**都不清**。

（`docs/OPEN-ITEMS.md:44` 写的"只有 401 才清登录态"与代码不符 —— 403 同样会把用户登出。
还有两条容易误判：**登录失败不会清掉已有登录态**；**`Logout` 不会清 `username`/`email`/`balance`**，
要真正抹掉得调 `ClearLocal`。出处：[link/FEATURES.md](../link/FEATURES.md) §2.3。）

失败词表**不是全局统一**的（两处实现有意不同）：`account` 8 类、`search` 6 类（把 401/403 与 429 都并进 `http`）、
`update` 走 `site` 层词表 —— 写"链接层统一的失败词表"是**错的**（[link/FEATURES.md](../link/FEATURES.md) §1.2、§6.4）。

### 5.2 "登录后过一会就掉线 / 静默续期从不触发"

按顺序查这三条，它们都**不是报错**，只是静默不发生：

1. **站点改动未部署**：`POST /api/token/refresh` 线上仍是 `404`（新增端点没上线），
   `/api/version` 也没带 `sha256`/`size`。复跑探针见 [docs/OPEN-ITEMS.md](../OPEN-ITEMS.md) §1（含部署步骤：
   `git archive` → `scp` → **必须重跑 `npm run build`** → `systemctl restart`）。
2. **站点既不给 `expires_in` 也不是 JWT** ⇒ 到期时间取不到，静默续期**永不触发**。
3. **"未登录"与"续期失败"都返回 `false`**，调用方无法区分 —— 这是已知的接口缺陷，不是你的环境问题。

（以上三条出处：[link/FEATURES.md](../link/FEATURES.md) §2.4。）

### 5.3 更新："站点版本比本机旧"是**正确判定**，不是失败

版本比较的是**关系**而不是"不同"：只有 `relation:"newer"` 才叫"有更新"；
`older` 会显示"站点上的版本（1.2.0）比本机旧"并**不提示下载**（避免把 v2 用户引去下 v1 安装包）。
站点现在报的是 1.2.0，本机声明 2.0.0（[link/FEATURES.md](../link/FEATURES.md) §3.3）。

- **发布 v2.0 前必做**：把站点 `src/lib/constants.ts` 的 `VERSION` 改成 `2.0.0`，否则本机永远显示"站点上的版本比本机旧"。
  这是**站点数据不是代码缺陷**，但忘了它用户就收不到任何更新提示（同上）。
- `sha256` **只显示、不校验**：全仓库 `pack::sha256_eq` 的调用点只有组件安装包与两处自检，更新链**一处都没有**
  （没有下载物就没有可比对的对象）。站点没给就返回 `null` **并附原因**，绝不给空串让界面显示成"已校验"（§3.2）。
- 更新链**永远不**自动下载/执行安装包，只把下载页交给系统浏览器（§3.1、§3.6）。

### 5.4 本机 .NET 侧 TLS 失败（环境问题，且很可能已经过期）

现象：`The SSL connection could not be established`，而 Node 侧（`fetch`）正常；影响是账号/更新
**对着线上会失败**，错误分类为 `network`，本地功能不受影响
（[docs/OPEN-ITEMS.md](../OPEN-ITEMS.md):54-58、[DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md):99）。

**归因改过一次，别再抄旧理由**：一度写成"本机 Schannel 不可用所以用 rustls"，后来服务器抓包定案 ——
**RST 是本机发的**，真凶是开发机的**出站阻止规则**（只对部分进程生效）；rustls 仍用，但理由改成
"不依赖系统 TLS 配置、与 Chromium 那条链一致"，并明确**不要**因为"某台机器连不上"去关系统代理
（[LINK-LAYER.md](../../MFMath.Host.Rust/docs/LINK-LAYER.md):122）。Rust 宿主走 `reqwest` + rustls（同文 `:498`），
所以这条"很可能已经不再重要"，**但在 Rust 侧对着线上验过一次之前不要划掉**
（[DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md):101-103）。**未证实**：没有该问题在 Rust 侧的线上验证记录。

### 5.5 症状："账号/更新/搜索**全都**报 `aborted`"

那是**取消闩锁**，不是网络问题：`site::cancel_all()` 置一个**全局**标记（`site.rs:25-29`），
而只有两处会复位它 —— `account.Configure`（`account.rs:300`）与 `search.Start`（`search.rs:1780`）；
其它任何成功调用都**不会**解锁。后果是点过一次取消之后，`account`/`update`/`search` 的后续网络调用
**一路返回 `{"ok":false,"kind":"aborted"}`**，直到改一次账号设置（[link/FEATURES.md](../link/FEATURES.md) §6.3）。
前端**从不调** `account.CancelAll`，所以这条路径一般由用例或外部脚本触发。

另外两处"取消"语义**完全不同**，别混：`CancelJob` 是"停止等待 + 丢弃结果"（`jobs.rs:15-17`），
`con.Stop` 是**真杀进程树**（`taskkill /PID <pid> /T /F`）（[link/FEATURES.md](../link/FEATURES.md) §6.3）。

---

## 6. 怎么拿日志与诊断包（以及：**不上报**）

### 6.1 路径与内容

| 项 | 事实 | 出处 |
| --- | --- | --- |
| 日志目录 | `%LOCALAPPDATA%\MFMath\logs` | `logging.rs:35-46` |
| 常规日志 | `app.log`，单文件上限 **2 MB**，轮转成 `app.1.log`（只留一代）；前端异常也写这里，前缀 `[前端]`；两个宿主**共用同一个文件**，所以时间线对得上 | `logging.rs:19`、`:238-248`、`:218-226`、`:4-5` |
| 崩溃日志 | `crash-<yyyyMMddHHmmss>.log`：环境 + 异常/backtrace + **`app.log` 尾部 200 行**；**只留最近 20 个** | `logging.rs:20-21`、`:253-291` |
| 诊断包 | `%LOCALAPPDATA%\MFMath\diagnostics-<yyyyMMddHHmmss>.txt`，含宿主与环境、引擎产物清单、设置文件列表、**除凭据外的设置文件原文**、`app.log` 尾部 200 行、**最新一份崩溃记录全文** | `sys.rs:258-319`、`:321-336` |
| 怎么导出 | 「设置 → 存储与数据 → 导出诊断包」（成功后给出路径，可一键"打开"） | `StorageGroup.vue:125-130`、`main.rs:95` |

### 6.2 三条命令

```powershell
$d    = Join-Path $env:LOCALAPPDATA 'MFMath'
$logs = Join-Path $d 'logs'
Start-Process explorer.exe $logs                                   # 直接打开日志目录
Select-String -Path "$logs\app.log" -Pattern '\[前端\]|宿主对象|引擎自检|panic' | Select-Object -Last 40
Get-Content "$logs\app.log" -Tail 200                              # 与崩溃日志里附的那 200 行同一口径
```

`logs` 目录在数据目录之下，所以设置里的「打开数据目录」也能到它附近（`OpenPath` 的白名单含数据目录根，见 [link/FEATURES.md](../link/FEATURES.md) §4.5）。

### 6.3 **不上报**，且诊断包不带凭据

- **崩溃与前端异常只写本地，不联网上报**（[DECISIONS.md](../DECISIONS.md) D-008）。只有**用户主动**导出诊断包并交出去，
  才会有任何东西离开这台机器（[link/CREDENTIALS.md](../link/CREDENTIALS.md) §4）。
- 诊断包**跳过凭据**：名单是 `["ai","account","search"]`，**外加**"文件名含 `secret`"的兜底（`sys.rs:278-297`）。
  这条兜底是踩过坑才有的：原先**只**按"文件名含 `secret`"跳，而这三个文件**一个都不含 `secret`** —— 等于没跳，
  会把 API Key、登录态、Wolfram App ID 整份打进去（`sys.rs:278-281`、[link/CREDENTIALS.md](../link/CREDENTIALS.md) §2.2）。
- ⚠ **`StoreDelete` ≠ 抹除**：删除只删 `<name>.json`，**不删 `.bak`**，而 `ai.json.bak` 里是**明文 `apiKey`**；
  它不出现在 `StoreList` 也不进诊断包，所以是"删了以后磁盘上还留着"（[link/CREDENTIALS.md](../link/CREDENTIALS.md) §2.3）——
  共享机器上要真正抹掉，得手工删 `%LOCALAPPDATA%\MFMath\settings\<name>.json.bak`。

### 6.4 日志是空的？

按这个顺序查：① exe 是不是跑在**工作区内的受限位置**（工作区内的进程写不了 `%LOCALAPPDATA%`，
日志/设置会**静默失败** —— 所以验收必须部署到工作区外，`ACCEPTANCE.md` §0.2）；
② `LOCALAPPDATA` 被重定向了（`logging.rs:28-32` 读它）—— 但 Tauri 建窗口走 known-folder API、
**不读** `LOCALAPPDATA`，所以重定向它对 WebView2 数据目录无效（`main.rs:394-400`）；③ 宿主根本没启动（§1.5）。
另两条只在**跑验证**时出现的坑：`npm run build` 报 `esbuild-…: Access is denied` 时把 `TEMP`/`TMP` 指到工程内
（`$env:TEMP="$repo\.buildtmp"; $env:TMP=$env:TEMP`，`BUGS.md:50-57`）；`tests/run-all.ps1` **必须保留 UTF-8 BOM**，
否则 PowerShell 5.1 按 ANSI 解码会把中文注释后面那行代码吞掉（`run-all.ps1:7-10`）。
成套 vs 单跑的假失败、以及"0 通过 0 失败"其实是 SKIP，见 `ACCEPTANCE.md` §3.3 与 `run-all.ps1:195-201`。

---

## 已知的文档债

> 规矩：以**代码为准**。下面每一条都是"注释/文档说 X，代码做 Y"，并给到 `文件:行`。

| # | 位置 | 问题 |
| --- | --- | --- |
| 1 | `MF_UI/MFMath.UI.Vue/src/lib/diagnostics/errors.js:1-9`、`:62-67` | 通篇按**已废弃的 C# 宿主**描述（`MFMath.Host/Log.cs`、`App.xaml.cs`、`LogBridge.cs`）。现役实现是 Rust 宿主对象 `diag.Front`（`handlers.rs:287` → `logging.rs:218-226`）。`main.rs:566-574` 已明确三条 Tauri 命令（含 `front_log`）已删。 |
| 2 | `docs/DESIGN-BOUNDARIES.md:98`、`docs/OPEN-ITEMS.md:119` | 写"清单里如实标着 `available:false`"。**全仓库没有任何代码**读 `/api/components`（`grep api/components` 只命中这两份 md），Rust 宿主的组件清单是编译进代码的常量（`console.rs:44-66`）且字段叫 `payloadAvailable`、只查**本地**文件（`console.rs:194-211`）。同一段文字里的 `available` 与 `payloadAvailable` 不是同一个东西，容易读成桌面端行为。 |
| 3 | `MFMath.Host.Rust/docs/ACCEPTANCE.md:99-111` | 写"`run-all.ps1` 登记在册的 **26 组**"。实测（2026-10-07，对 `run-all.ps1` 做正则去重）：**53 组**（`cdp-*` 48 + `unit-*` 4 + `audit-modes` 1），与磁盘上 48 个 `cdp-*.mjs`/4 个 `unit-*.mjs` 一一对应。该文档自己写了"数字会随代码变化，变了就更新"。 |
| 4 | `MF_UI/BUGS.md:71-93` | §0.2 里"宿主缺桥 ⇒ 88+37+27 条失败"那一行**已作废**（文档自己用红字划掉了，但表格里的旧数字仍在），引用时只准引二次实测列。 |
| 5 | `docs/OPEN-ITEMS.md:44` | "只有 401 才清登录态"与 `site.rs:178` 不符（403 同样清）。同一行下面的"`token_version` 同样未生效"还有一层：`token_version` 在宿主侧**零实现**（`link/FEATURES.md` §2.6）。 |
| 6 | `MFMath.Host.Rust/src/dpapi.rs:1,18` | 仍把 AI 的 API Key 列为 DPAPI 用户（AI 已改明文；`link/CREDENTIALS.md` §1 登记）。 |

## 附：怎么复查本文的数字

```powershell
# ① 引擎注册表 + 四种封套（不起宿主；产物不在 git 里，先按 README 构建）
$p = "MF_Mathematics\build\bin\Release\probe_call.exe"
& $p list_functions '{}'                        # count 应为 424
& $p integrate '{"expr":"x**x","var":"x"}'      # 未实现
& $p bernoulli_number '{"n":100000}'            # 上限拒绝原文

# ② 用例登记数与磁盘数对账（本文引用的 53 / 48 / 4）
$raw = Get-Content MF_UI\MFMath.UI.Vue\tests\run-all.ps1 -Raw
([regex]::Matches($raw,'"([a-z0-9\-]+)"') | % { $_.Groups[1].Value } | ? { $_ -match '^(unit|cdp|audit)-' } | Select-Object -Unique).Count
(Get-ChildItem MF_UI\MFMath.UI.Vue\tests\cdp-*.mjs).Count

# ③ 日志/诊断包常量（§6）、401/403 与取消闩锁（§5.1、§5.5）
Select-String -Path MFMath.Host.Rust\src\logging.rs -Pattern 'MAX_BYTES|KEEP_CRASH_FILES|CRASH_TAIL_LINES|app\.1\.log'
Select-String -Path MFMath.Host.Rust\src\sys.rs -Pattern 'CREDENTIAL_STEMS|diagnostics-'
Select-String -Path MFMath.Host.Rust\src\site.rs -Pattern '401 \| 403|cancel_all|pub fn arm'
Select-String -Path MFMath.Host.Rust\src\*.rs -Pattern 'site::arm\(\)'
```