# 构建期检查与守卫

> 本文回答：构建期有哪些检查、各检查的范围是什么、守卫清单有哪些、加一条守卫必须遵守什么原则。
>
> 与同层文档的分工：
> - [README.md](README.md) —— 构建链与测试资产；
> - [ENGINE-BINDING.md](ENGINE-BINDING.md) —— 映射表与可达性校验的语义；
> - [ARCHITECTURE.md](ARCHITECTURE.md) —— i18n 与导航的组织；
> - [TUTORIAL-KEYPAD.md](TUTORIAL-KEYPAD.md) —— 教程与键盘的内容（本文只讲对应的守卫判据）。

## 1. 检查入口

`npm run check` 是 Vue 侧聚合入口，展开为四段（`MF_UI/MFMath.UI.Vue/package.json`）：

```powershell
Select-String -Path MF_UI/MFMath.UI.Vue/package.json -Pattern '"check"'
```

| 段 | 命令 | 范围 |
| --- | --- | --- |
| `check:types` | `tsc --noEmit -p tsconfig.json` | TypeScript 类型错误 |
| `check:signatures` | `node tools/engine-signatures.mjs --check` | 引擎源码 ↔ 签名表 |
| `check:args` | `node tools/check-arg-contract.mjs` | UI 声明的参数键 ↔ 引擎实际读的键 |
| `check:ui` | `build-tutorials.mjs && check-ui.mjs && check-examples.mjs` | 教程、键盘、映射、i18n、用例登记 |

React 侧只有 `npm run check:types`，无聚合脚本。`npm run check` 不是纯只读：`check:ui` 的第一步 `build-tutorials.mjs` 会重写 `src/tutorials/tutorials.json`。

不在闸门内的命令：`npm run build`（产出 `dist/`，是构建而非判据）、`tests/run-all.ps1`（端到端，需真宿主）。

## 2. 引擎侧的两道检查

`check:signatures` 与 `check:args` 都读引擎源码（`MF_Mathematics/`）。

### 2.1 `check:signatures`

判据是单向的，只有三种情况进硬失败：

| 失败方向 | 判定 |
| --- | --- |
| 函数集合不一致 | 源码 `register_function` 与表键两侧不一致 |
| 源码读取的参数表里没有 | 工具箱/AI 无法提供该参数 |
| 源码按必填读、表里写成可选 | 用户会漏填 |

反向（表里有、源码没刮到）只提示，因为引擎大量参数经 `args["k"]` 或域内辅助函数读取，刮取器看不到，严格判定会产出成片假差异。

本次实测输出：

```
引擎签名对账：源码 register_function 424 条 / 表 424 条
提示（不判定失败）124 处
```

重建入口是 `npm run signatures:write`。

### 2.2 `check:args`

判据：UI 为某模式声明的每个键 K，要么刮取器看到 `get_xxx(args,"K")`，要么在 `HELPER_READ` 白名单里且带判据字符串。反向（引擎必填、UI 未声明）只警告，已核为多分支互斥的假阳性。

本次实测输出：

```
参数契约对账：415 个模式 / 检查 935 个声明键
  引擎 register_function 424 个；白名单 74 条
```

白名单经差分探针（删键或改值，用 `probe_call.exe` 真调引擎）逐个验证。白名单按 `fn → { key: 判据 }` 逐条写，而非全局键名白名单。

## 3. `check-ui.mjs` 的守卫

任一 `problems` 非空即 `exit 1`；`warnings` 只打印不失败。守卫清单：

| 守卫 | 判据 | 定位命令 |
| --- | --- | --- |
| 教程 target 覆盖 | 每个教程步骤的 target 在源码 `data-tour` 里存在，或在 `PENDING` 里登记理由；双向校验 | `Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern "PENDING"` |
| 键盘键数与键面 | 键数等于基准值、`▢` 无残留、`\begin{}` 有配对 `\end{}`、分类名与顺序固定 | `Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern "KEY_COUNT"` |
| 键面可读性 | 键面要么排版成数学，要么是清理过的可读文本 | `Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern "showsRawLatex"` |
| 教程字段合法性 | `actionType`、`highlight`、`placement` 取值合法 | `Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern "ACTIONS"` |
| 映射重复键 | `engineMap.js` 与 `engineMapExtra.js` 各跑一次重复键检查 | `Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern "checkDuplicateKeys"` |
| 模式可达性 | 正向校验未登记不可达，反向校验登记后已可达 | `Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern "NOT_EXPOSED"` |
| 区间参数契约 | 固定列出的 10 个 handler 对应模式的 args 必须有 `interval` 键 | `Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern "INTERVAL_FNS"` |
| 概率表契约 | 用真实构造器加自带默认值跑 `buildEngineArgsFromValues`，`prob_table` 参数必须非空 | `Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern "prob_table"` |
| 重名模式登记 | 名字选不到但 fn 被页面覆盖的必须登记进 `DUPLICATE_NAME_GROUPS` | `Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern "DUPLICATE_NAME_GROUPS"` |
| 冻结的 Vue 绘图组 | 6 个白名单文件在位、目录无新增、无人 import | `Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern "FROZEN_VUE_PLOT_FILES"` |
| i18n 文案 | 键含中文的 `t("…")` 调用必须有译文 | `Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern "i18n 文案"` |
| i18n 模式名 | `ENGINE_MAP` 的每个键在 `en-modes.js` 有译文 | 同上 |
| i18n 弹窗字段 | `ENGINE_VAR_SPECS` 的每条唯一标签在 `en-vars.js` 有译文 | 同上 |
| i18n 结果标签 | `FIELD_LABELS` 的每个值在 `en-results.js` 有译文 | 同上 |
| i18n 键盘分类 | 6 个分类名有译文 | 同上 |
| 端到端用例登记 | `tests/cdp-*.mjs` 必须登记进 `run-all.ps1`，登记了却不存在也失败 | `Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern "NOT_IN_SUITE"` |
| 样本 fixture 重复键 | 只警告 | `Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern "样本 fixture"` |

本次实测守卫输出（`node tools/check-ui.mjs`，exit 0）：

```
引擎模式可达性      ：映射 415 个 / 页面并集 391 个 / 取不到 0 个
区间参数契约        ：10 个 handler / 命中模式 10 个 / 缺 interval 0 个
概率表契约          ：4 个模式 / 空表 0 个
冻结的 Vue 绘图组    ：6/6 个文件在位，被 import 0 处
重名模式登记        ：已登记 24 个，未登记 0 个
跨视图重名          ：2 处（已登记 2，未登记 0）
i18n 文案            ：已用 t() 包裹 50 条，缺译文 0 条
i18n 模式名          ：415 个模式，缺译文 0 个
i18n 弹窗字段        ：186 条唯一标签，缺译文 0 条
i18n 结果标签        ：78 个字段，缺译文 0 个
i18n 键盘分类        ：6 个分类，缺译文 0 个
样本 fixture        ：287 个键 / 重复键 0 个
数学键盘            ：6 分类 / 126 键（基准 126）
端到端用例          ：cdp-* 49 个，已登记 49 个
```

## 4. 守卫必须可被证伪

一条永远为真的断言等于没有断言。加守卫的标准动作是三步：临时制造违反 → 确认自检报错并 `exit 1` → 还原。

每条守卫都对应一个真实缺陷，例如区间参数契约对应「引擎读 `interval`、UI 发 `a`/`b`，用户填的区间被静默忽略」，概率表契约对应「用户不改弹窗默认值直接计算就失败」。

## 5. 设计取舍：`check-ui.mjs` 不读引擎源码

`check-ui.mjs` 的 import 全部指向 Vue 包内部，不接触引擎树：

```powershell
Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern "MF_Mathematics|scrape\("
```

原因：引擎源码是树外路径，自检若读它，换机器或只检出前端时 `npm run check` 无法运行。代价是它检查的是登记表而非真源码，例如「区间参数契约」把 10 个 handler 名写死在 `INTERVAL_FNS`，引擎新增同类 handler 时须把名字加进来。

这一取舍只覆盖 `check-ui.mjs`。`engine-signatures.mjs` 与 `check-arg-contract.mjs` 都读引擎树。

## 6. 加一条守卫的步骤

| 步 | 做法 |
| --- | --- |
| 1 | 先有真实缺陷，再写守卫，并记录该守卫拦的是哪一类缺陷 |
| 2 | 判断进 `problems`（硬失败）还是 `warnings`（只提示）；只有确定的错才硬失败 |
| 3 | 登记表类守卫必须双向校验，登记了却已不需要时报过时条目 |
| 4 | 白名单每一条带判据字符串，拿不出判据不加 |
| 5 | 制造一次违反，确认失败，再还原 |
| 6 | 若守卫的输入是登记表而非真源码，把不读源码的原因写进注释 |
| 7 | 更新相关文档的清单与计数 |
| 8 | 复跑 `npm run check` 与 `npm run check:types --prefix MF_UI/MFMath.UI.React` |

## 7. 复跑命令

| 目标 | 命令 |
| --- | --- |
| 全部闸门 | `npm run check --prefix MF_UI/MFMath.UI.Vue` |
| 守卫清单 | `node MF_UI/MFMath.UI.Vue/tools/check-ui.mjs` |
| React 类型检查 | `npm run check:types --prefix MF_UI/MFMath.UI.React` |
