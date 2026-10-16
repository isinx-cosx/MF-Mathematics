# 前端与引擎的接线

> 本文回答：前端如何把界面接到引擎上、三张映射表各管什么、模式可达性如何校验、异步分流阈值是多少。
>
> 与同层文档的分工：
> - [README.md](README.md) —— 两个工程、共享机制、构建链；
> - [ARCHITECTURE.md](ARCHITECTURE.md) —— 目录分层、路由、i18n、样式；
> - [CHECKS.md](CHECKS.md) —— 构建期检查与守卫（本文只引用可达性守卫的行为）；
> - [PLOT.md](PLOT.md) —— 绘图页的采样与视口（本文只讲其中的同步/异步分流）。
>
> 引擎侧契约见 [`../engine/CONTRACT.md`](../engine/CONTRACT.md)。

## 1. 前端职责边界

前端不承担计算，只做参数构造、传输、展示三件事：

| 前端负责 | 载体 | 定位命令 |
| --- | --- | --- |
| 参数构造 | `src/lib/engine/calcArgs.js` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/engine/calcArgs.js -Pattern "buildEngineArgs"` |
| 传输 | `src/lib/bridge.js` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/bridge.js -Pattern "engineCall"` |
| 展示 | `src/lib/engine/resultModel.js`、`resultFormat.js` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/engine/resultModel.js -Pattern "toResultNodes"` |

引擎桥对象是 `window.chrome.webview.hostObjects.sync.mf`，取值在 `bridge.js` 的 `bridgeObj()`。成员名是 PascalCase 且大小写敏感：`Dispatch` 写成 `dispatch` 会抛 `0x80070057`。同步调用会占住渲染进程主线程，这是 §5 异步分流的全部理由。

## 2. 一条计算的完整链路

以计算页为例：

| 步 | 环节 | 定位命令 |
| --- | --- | --- |
| 1 | 用户输入进入 `block.expr` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/views/calc/CalcView.vue -Pattern "block.expr"` |
| 2 | 点「计算」触发 `calc()` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/views/calc/CalcView.vue -Pattern "calc\("` |
| 3 | 查表 `ENGINE_MAP[mode]` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/views/calc/CalcView.vue -Pattern "ENGINE_MAP"` |
| 4 | 需要弹窗时进入 `MultiVarDialog` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/engine/calcArgs.js -Pattern "needsVarDialog"` |
| 5 | 构造 args | `buildEngineArgs` / `buildEngineArgsFromValues` |
| 6 | 必填缺失时拒绝计算 | `Select-String -Path MF_UI/MFMath.UI.Vue/src/views/calc/CalcView.vue -Pattern "defaulted"` |
| 7 | 分流 `shouldRunAsync` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/engine/asyncPolicy.js -Pattern "shouldRunAsync"` |
| 8 | 过桥 `engineCall` / `engineCallAsync` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/bridge.js -Pattern "engineCall"` |
| 9 | 宿主 `mf.Dispatch` → 引擎 | `Select-String -Path MFMath.Host.Rust/src/handlers.rs -Pattern "Dispatch"` |
| 10 | 展示与历史摘要 | `Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/engine/resultModel.js -Pattern "briefValue"` |

无宿主时 `engineCall` 返回 `null`，界面显示「未检测到引擎桥」，这是环境状态而非错误。桥抛异常时包成 `{isError:true, value:"桥调用失败: …"}`，不向外抛。args 以 JSON 字符串传输，`engineCall` 负责 `JSON.stringify`。

## 3. 参数构造

`buildEngineArgs(mode, expr, report)` 按固定次序处理输入框文本。输入框支持用深度 0 的 `;` 分段一次给多个参数（`splitSegments`）。

| 步 | 规则 | 定位命令 |
| --- | --- | --- |
| 1 | 第一段喂给 `pickTextArg` 选出的参数（先找必填 `string`，自动映射路径排除 `string_array`/`complex_obj`） | `Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/engine/calcArgs.js -Pattern "pickTextArg"` |
| 2 | `string_array` 参数把剩余段整组 `join(";")` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/engine/calcArgs.js -Pattern "string_array"` |
| 3 | 其余必填参数按声明顺序逐段消费 | 同上 |
| 4 | 剩余段补给可选参数 | 同上 |
| 5 | 仍缺的必填参数取 `ENGINE_VAR_SPECS` 字段，再无则兜底并记账 | `Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/engine/calcArgs.js -Pattern "noteDefaulted"` |
| 6 | 其余可选参数取弹窗字段，没有则整键省略 | 同上 |

兜底值（`0`/`[0,0]`/`[]`/`""`）在引擎眼里是合法值，因此每次兜底都经 `noteDefaulted` 记账，调用点在 `report.defaulted` 非空时拒绝调引擎并说明缺什么。

类型转换集中在 `convertArg`。解析失败时原样返回文本，让引擎抛它自己的中文错误。

## 4. 三张映射表

| 表 | 位置 | 职责 | 键数 |
| --- | --- | --- | --- |
| `RAW_MAP` | `engineMap.js` | 由早期映射自动转换得到的快照 | 324 |
| `EXTRA_MAP` | `engineMapExtra.js` | 增量与修正，同名覆盖前者 | 165 |
| `ENGINE_MAP` | `engineMap.js` | `{...RAW_MAP, ...EXTRA_MAP}`，中文模式名 → `{fn, module, args}` | 415 |
| `RAW_VAR_SPECS` | `engineMap.js` | 早期弹窗字段快照 | 19 |
| `EXTRA_VAR_SPECS` | `engineMapExtra.js` | 弹窗字段增量 | 130 |
| `ENGINE_VAR_SPECS` | `engineMap.js` | 模式名 → 字段数组，有它才弹窗 | 139 |
| `VIEW_CONFIGS` | `viewConfigs.js` | 学科页 → `{title, desc, modes, single}` | 14 页 |

键数由命令核对：

```powershell
node --input-type=module -e 'const m=await import("./src/lib/engine/engineMap.js");const x=await import("./src/lib/engine/engineMapExtra.js");console.log(Object.keys(m.ENGINE_MAP).length,Object.keys(m.ENGINE_VAR_SPECS).length,Object.keys(x.EXTRA_MAP).length,Object.keys(x.EXTRA_VAR_SPECS).length)'
```

`RAW_MAP` 与 `RAW_VAR_SPECS` 未导出，数量从源码对象字面量解析得到（324 / 19）。新增模式或改参数只改 `engineMapExtra.js`，`engineMap.js` 是自动生成内容。

签名表 `src/lib/ai/engine-signatures.json` 是引擎全部 action 的副本，共 424 条，是函数工具箱与 AI 工具表的唯一数据源。模式表只覆盖其中 371 个 action，另 53 个仅由工具箱暴露：

```powershell
node --input-type=module -e 'import fs from "node:fs";const m=await import("./src/lib/engine/engineMap.js");const sig=JSON.parse(fs.readFileSync("src/lib/ai/engine-signatures.json","utf8"));const fns=new Set(Object.values(m.ENGINE_MAP).map(s=>s.fn));console.log(Object.keys(sig).length,fns.size,Object.keys(sig).filter(k=>!fns.has(k)).length)'
```

## 5. 模式可达性校验

判据在 `tools/check-ui.mjs`，双向校验：

| 机制 | 行为 | 定位命令 |
| --- | --- | --- |
| `NOT_EXPOSED_GROUPS` | 无法在页面选到、且 fn 未被覆盖的模式必须登记；当前为空数组 | `Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern "NOT_EXPOSED_GROUPS"` |
| 正向校验 | 模式不在任何页面 `modes`、fn 未被覆盖、未登记 → 硬失败 | 同上 |
| 反向校验 | 登记了却已可达 → 报过时条目 | 同上 |
| `DUPLICATE_NAME_GROUPS` | 名字选不到但 fn 已被页面覆盖的重复命名必须登记 | `Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern "DUPLICATE_NAME_GROUPS"` |

判定顺序：先 `pageModes`，再 `pageFns`，再 `NOT_EXPOSED`。当前状态（复跑 `node tools/check-ui.mjs`）：

```
引擎模式可达性      ：映射 415 个 / 页面并集 391 个 / 取不到 0 个
重名模式登记        ：已登记 24 个，未登记 0 个
```

映射 415 与页面并集 391 的差额是 24 个已被取代的名字，其功能由同 fn 的页面模式提供。

## 6. 异步分流阈值

`shouldRunAsync(name, args, opt)` 依次判三条：

| 判据 | 条件 | 数量 | 定位命令 |
| --- | --- | --- | --- |
| 强制 | `opt.force === true` | — | `Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/engine/asyncPolicy.js -Pattern "opt.force"` |
| 无上界 | `ALWAYS_ASYNC.has(name)` | 28 | `Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/engine/asyncPolicy.js -Pattern "ALWAYS_ASYNC"` |
| 按规模 | 工作量超过 `LIMIT[name]` | 4 | `Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/engine/asyncPolicy.js -Pattern "BY_SIZE"` |

按规模判定的 action 与阈值：

| action | 工作量公式 | 阈值 |
| --- | --- | --- |
| `mandelbrot` | `width × height × max_iter`（缺省 256） | `1.5e8` |
| `complex_grid` | `nx × ny` | `2.5e5` |
| `expr_eval_grid` | `xs.length × ys.length`（缺省退回 nx/ny） | `2.5e5` |
| `matrix_multiply` | `n³` | `2e6` |

判据是严格大于，工作量等于阈值时不走异步。`num(v, d)` 把非正数与非有限值折成默认值，避免脏参数算成 0 工作量。

异步通道语义（`bridge.js` 的 `engineCallAsync`）：

| 行为 | 事实 |
| --- | --- |
| 无宿主 | 返回 `null`，与同步版一致 |
| 宿主无 `DispatchJob` | 自动退回同步调用 |
| 轮询间隔 | `POLL_MS = 120` 毫秒 |
| 取消 | 引擎没有取消钩子，宿主只能停止等待并丢弃结果，文案写「已取消等待」 |

绘图页「每条曲线一次」的采样刻意保持同步，只给用户明确发起的重活走异步通道。

## 7. 复跑命令

| 目标 | 命令（工作目录 `MF_UI/MFMath.UI.Vue`） |
| --- | --- |
| 可达性、区间契约、概率表契约、重名登记 | `node tools/check-ui.mjs` |
| 参数契约 | `npm run check:args` |
| 引擎签名对账 | `npm run check:signatures` |
