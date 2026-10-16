# 文档地图

> 本文回答一个问题：要了解某件事，应当读哪一份文档。
> 本文给出六层结构、按问题查的索引、每份文档的用途、数字的复跑命令。
> 仓库根 [`../README.md`](../README.md) 面向使用者：这是什么、有哪些功能、架构如何、怎么构建与验证。
> [`manual/README.md`](manual/README.md) 是用户向入口：给谁用、能做什么、不能做什么。

## 文档分布

`docs/` 下共 48 份 `.md`，其中 34 份属于本文的六层地图；加上仓库根 [`../README.md`](../README.md)，地图共 35 份。其余 14 份属于记录类，见「地图外」一节。

| 位置 | `.md` 数 | 地图内 | 内容 |
| --- | ---: | ---: | --- |
| `docs/`（根） | 18 | 4 | 地图、设计理念、决策记录、功能边界；其余 14 份不在图内 |
| `docs/engine/` | 9 | 9 | C++ 计算引擎 |
| `docs/link/` | 6 | 6 | 前端与宿主之间的契约 |
| `docs/ui/` | 9 | 9 | Vue 壳与内嵌 React 绘图组 |
| `docs/manual/` | 6 | 6 | 用户向 |
| **合计** | **48** | **34** | 地图另含仓库根 README，计 35 |

```powershell
Get-ChildItem docs -Recurse -Filter *.md -File | Group-Object DirectoryName | Select-Object Name, Count
```

`docs/` 下的非 `.md` 文件共 19 个：`docs/tutorials-src/*.yaml` 18 份（教程原件，构建期转为 JSON），以及 `docs/stress-scan.json` 1 份（算法扫描数据）。

```powershell
Get-ChildItem docs -Recurse -File | Where-Object Extension -ne '.md'
```

地图只收手册。手册的判据是：只有架构或契约确实改变时才需要修改。进度、风险、审查结论、迁移报告这类内容随每次改动变化，属于记录类，不进地图。

## 六层结构

```text
第 1 层  入口        这是什么 + 三步构建 + 本地图
第 2 层  设计理念     为什么这么做（读代码前先读它）
第 3 层  链接层       前端与宿主之间的契约（第 4、5 层都引用它）
第 4 层  引擎         C++ 计算层
第 5 层  前端         Vue 壳 + 内嵌 React 绘图组
第 6 层  用户向       能做什么、不能做什么、怎么排障
```

| 层 | 回答什么 | 份数 | 读者 |
| --- | --- | ---: | --- |
| 1 入口 | 这是什么、怎么构建起来、文档从哪进 | 2 | 全部读者 |
| 2 设计理念 | 为什么是这个样子：哪些选择是刻意的、代价落在哪里 | 3 | 评估者、改代码的人 |
| 3 链接层 | 前端与宿主之间那条缝由什么构成、契约是什么 | 6 | 改前端或改宿主的人 |
| 4 引擎 | C++ 计算层怎么组织、怎么调用、边界在哪 | 9 | 改引擎的人、需要核对数值的人 |
| 5 前端 | 两个工程怎么分工、界面怎么接到引擎 | 9 | 改界面的人 |
| 6 用户向 | 能做什么、不能做什么、出问题怎么办 | 6 | 使用者、评估者 |

阅读顺序即写作顺序：第 2 层定口径，第 3 层定契约，第 4、5 层是契约两侧的实现，第 6 层引用前面全部内容。

## 按问题查

| 我想知道 | 读 |
| --- | --- |
| 这是什么软件、能做什么、不能做什么 | [`manual/README.md`](manual/README.md) |
| 全部功能一览（学科视图 / 绘图 / 工具 / AI / 学习 / 系统） | [`manual/FEATURES.md`](manual/FEATURES.md) |
| 某个功能怎么按顺序走一遍 | [`manual/WORKFLOWS.md`](manual/WORKFLOWS.md) |
| 怎么构建、怎么运行、安装包做到什么程度 | [`manual/INSTALL.md`](manual/INSTALL.md) |
| 出问题了（卡死 / 算不出来 / 字体 / 组件 / 登录更新 / 日志） | [`manual/TROUBLESHOOTING.md`](manual/TROUBLESHOOTING.md)、[`manual/FAQ.md`](manual/FAQ.md) |
| 为什么前端一行数学都不算 | [`DESIGN.md`](DESIGN.md)、[`ui/ENGINE-BINDING.md`](ui/ENGINE-BINDING.md) |
| 为什么「算不出来」是真实的算不出来 | [`engine/BOUNDARIES.md`](engine/BOUNDARIES.md)、[`manual/FAQ.md`](manual/FAQ.md) |
| 哪些事明确不做、哪些推迟、哪些尚未验证 | [`DESIGN-BOUNDARIES.md`](DESIGN-BOUNDARIES.md) |
| 某个设计为什么是这个样子、当时的代价是什么 | [`DESIGN.md`](DESIGN.md)、[`DECISIONS.md`](DECISIONS.md) |
| 引擎怎么构建、C ABI 有几个导出、怎么跑测试 | [`engine/README.md`](engine/README.md) |
| 某个 action 的参数键名是什么、缺参数会怎样 | [`engine/CONTRACT.md`](engine/CONTRACT.md)；action 与键名的权威源是 [`engine-signatures.json`](../MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json) |
| 各学科模块各有多少 action、边界在哪 | [`engine/MODULES.md`](engine/MODULES.md) |
| 符号层、数值层、输入层分别怎么做 | [`engine/SYMBOLIC.md`](engine/SYMBOLIC.md)、[`engine/NUMERIC.md`](engine/NUMERIC.md)、[`engine/INPUT.md`](engine/INPUT.md) |
| 绘图与分形在引擎侧的契约 | [`engine/PLOT.md`](engine/PLOT.md) |
| 引擎的测试资产与守门断言 | [`engine/TESTS.md`](engine/TESTS.md) |
| 前端怎么组织（目录、路由、i18n、样式） | [`ui/README.md`](ui/README.md)、[`ui/ARCHITECTURE.md`](ui/ARCHITECTURE.md) |
| 前端怎么把界面接到引擎 | [`ui/ENGINE-BINDING.md`](ui/ENGINE-BINDING.md) |
| 绘图页怎么组织 | [`ui/PLOT.md`](ui/PLOT.md) |
| AI 面板怎么实现、密钥放在哪 | [`ui/AI.md`](ui/AI.md)、[`link/CREDENTIALS.md`](link/CREDENTIALS.md) |
| 控制台、函数工具箱、历史、搜索页 | [`ui/TOOLS.md`](ui/TOOLS.md) |
| 设置与工作区怎么存 | [`ui/SETTINGS-WORKSPACE.md`](ui/SETTINGS-WORKSPACE.md) |
| 教程系统与数学键盘 | [`ui/TUTORIAL-KEYPAD.md`](ui/TUTORIAL-KEYPAD.md) |
| 构建期有哪些闸门、各拦什么 | [`ui/CHECKS.md`](ui/CHECKS.md) |
| 前端与宿主之间那条缝是什么 | [`link/README.md`](link/README.md) |
| 宿主对象有哪些方法、什么参数 | [`link/OBJECTS.md`](link/OBJECTS.md) |
| 为什么某个操作会卡住、取消到底取消了什么 | [`link/JOBS-PUSH.md`](link/JOBS-PUSH.md) |
| 凭据存在哪、什么形式、谁能读到 | [`link/CREDENTIALS.md`](link/CREDENTIALS.md) |
| 搜索、账号、更新、备份、控制台怎么落地 | [`link/FEATURES.md`](link/FEATURES.md) |
| 有几个宿主、谁是现役、换宿主时什么跟着走 | [`link/HOSTS.md`](link/HOSTS.md) |
| 怎么复现宿主验收 | [`ACCEPTANCE.md`](../MFMath.Host.Rust/docs/ACCEPTANCE.md) |
| 怎么打包 | [`PACKAGING.md`](../MFMath.Host.Rust/docs/PACKAGING.md) |
| 某份文档是否属于本图、是否仍然现行 | 「地图外」一节 |

## 六层清单

### 第 1 层 · 入口（2 份）

| 文件 | 用途 |
| --- | --- |
| [`../README.md`](../README.md) | 这是什么、功能、架构、三步构建、验证命令、边界、许可证、工作室官网 |
| 本文（`docs/README.md`） | 文档地图：六层结构、按问题查、清单、数字复跑命令、地图外的文档 |

### 第 2 层 · 设计理念（3 份）

| 文件 | 用途 |
| --- | --- |
| [`DESIGN.md`](DESIGN.md) | 六条设计理念：每条对应代码中的机制，以及违反之后的后果 |
| [`DECISIONS.md`](DECISIONS.md) | 架构决策记录：背景、决定、代价、现状、出处 |
| [`DESIGN-BOUNDARIES.md`](DESIGN-BOUNDARIES.md) | 明确不做、推迟、能力边界、未验证，并写明推翻每一条的门槛 |

### 第 3 层 · 链接层（6 份）

| 文件 | 用途 |
| --- | --- |
| [`link/README.md`](link/README.md) | 接缝由 `AddHostObjectToScript` 构成，三条契约，同步调用的必要性，怎么增加一个宿主对象 |
| [`link/OBJECTS.md`](link/OBJECTS.md) | 宿主对象与方法表；对象名与方法名以 `main.rs` 的 `HOST_OBJECTS` 与 `MethodSpec` 为准 |
| [`link/JOBS-PUSH.md`](link/JOBS-PUSH.md) | 异步任务通道（`DispatchJob` / `PollJob` / `CancelJob` / `JobStats`）与下行推送信封 |
| [`link/CREDENTIALS.md`](link/CREDENTIALS.md) | 哪些内容走 DPAPI 密文、哪些落明文 `ai.json`、各自的理由 |
| [`link/FEATURES.md`](link/FEATURES.md) | 搜索、账号、更新、备份、控制台各自怎么落在这条缝上 |
| [`link/HOSTS.md`](link/HOSTS.md) | 宿主谱系：.NET 宿主已退役、Rust 宿主现役，迁移时哪些内容跟着走 |

### 第 4 层 · 引擎（9 份）

| 文件 | 用途 |
| --- | --- |
| [`engine/README.md`](engine/README.md) | 两个构建目标（`mf_mathematics_core` 与 `mf_mathematics`）、C ABI 的两个导出、`/WHOLEARCHIVE` 守门、构建与测试入口 |
| [`engine/CONTRACT.md`](engine/CONTRACT.md) | args JSON 的形状、键名契约、必填参数拒绝计算、「未实现」的返回形状 |
| [`engine/MODULES.md`](engine/MODULES.md) | 各学科模块的 action 清单与边界 |
| [`engine/SYMBOLIC.md`](engine/SYMBOLIC.md) | 符号层：SymEngine 与 `RCP` 边界、化简、求导、积分、极限、pretty 与 LaTeX |
| [`engine/NUMERIC.md`](engine/NUMERIC.md) | 数值层：特殊函数与复数、精度与容差策略 |
| [`engine/INPUT.md`](engine/INPUT.md) | 输入层：归一化与解析 |
| [`engine/PLOT.md`](engine/PLOT.md) | 采样与视口契约、分形迭代上限、必须同步的调用 |
| [`engine/BOUNDARIES.md`](engine/BOUNDARIES.md) | 引擎如实承认的能力边界与 `NOT_EXPOSED` 口径 |
| [`engine/TESTS.md`](engine/TESTS.md) | 可执行目标与 CTest 用例的划分、怎么增加一条、`count` 守门 |

### 第 5 层 · 前端（9 份）

| 文件 | 用途 |
| --- | --- |
| [`ui/README.md`](ui/README.md) | 两个工程（Vue 壳与 React 绘图组）、`@shared` 共享面、构建链、测试资产 |
| [`ui/ARCHITECTURE.md`](ui/ARCHITECTURE.md) | 分层（`views` / `components` / `lib`）、路由与导航表、i18n、样式 |
| [`ui/ENGINE-BINDING.md`](ui/ENGINE-BINDING.md) | 一条计算从界面到引擎的链路、`ENGINE_MAP` 可达性守门、`asyncPolicy` 分流 |
| [`ui/PLOT.md`](ui/PLOT.md) | React 绘图页、共享绘图库、工作区载荷，以及被冻结的 Vue 绘图组 |
| [`ui/AI.md`](ui/AI.md) | 页面直连模型端点、SSE 分帧、步骤视图、`ai.json` 明文密钥的代价 |
| [`ui/TOOLS.md`](ui/TOOLS.md) | 控制台、函数工具箱、历史、搜索页 |
| [`ui/SETTINGS-WORKSPACE.md`](ui/SETTINGS-WORKSPACE.md) | 设置分组与目录、导入导出、工作区按路由分页保存的载荷形状 |
| [`ui/TUTORIAL-KEYPAD.md`](ui/TUTORIAL-KEYPAD.md) | 教程系统与数学键盘 |
| [`ui/CHECKS.md`](ui/CHECKS.md) | 构建期闸门与逐条守卫，以及守卫必须先被验证过会失败这条规矩 |

### 第 6 层 · 用户向（6 份）

| 文件 | 用途 |
| --- | --- |
| [`manual/README.md`](manual/README.md) | 给谁用、能做什么、不能做什么、离线承诺的准确口径 |
| [`manual/FEATURES.md`](manual/FEATURES.md) | 功能全表：逐项落到模式名与页面 |
| [`manual/WORKFLOWS.md`](manual/WORKFLOWS.md) | 典型用法，每一步对应真实存在的控件 |
| [`manual/INSTALL.md`](manual/INSTALL.md) | 构建与运行、安装包的现状、安装到启动这条路径的验证方法 |
| [`manual/TROUBLESHOOTING.md`](manual/TROUBLESHOOTING.md) | 按症状排查：卡死、算不出来、字体、组件、登录更新、日志与诊断包 |
| [`manual/FAQ.md`](manual/FAQ.md) | 常见问题：为什么算不出来、离线边界、为什么不上报崩溃、许可证 |

### 宿主工程自己的文档（不计入 35）

| 文件 | 用途 |
| --- | --- |
| [`ACCEPTANCE.md`](../MFMath.Host.Rust/docs/ACCEPTANCE.md) | Rust 宿主的可复现验收步骤 |
| [`PACKAGING.md`](../MFMath.Host.Rust/docs/PACKAGING.md) | 出包流程与其中尚未验证的部分 |
| [`LINK-LAYER.md`](../MFMath.Host.Rust/docs/LINK-LAYER.md) | 链接层迁移的工作日志，属于记录类，不作为手册引用 |

## 每个数字怎么自己算

下表每个数字都随代码变化。引用之前先跑同一行的命令。

| 数字 | 含义 | 复跑 |
| --- | --- | --- |
| 48 / 34 / 14 | `docs/` 下 `.md` 数 / 地图内 docs 文档数 / 地图外文档数 | `Get-ChildItem docs -Recurse -Filter *.md -File \| Group-Object DirectoryName \| Select-Object Name, Count` |
| 19 | `docs/` 下非 `.md` 文件数（18 份教程 YAML + 1 份数据 JSON） | `Get-ChildItem docs -Recurse -File \| Where-Object Extension -ne '.md'` |
| 424 | 引擎注册的 action 数，同时是构建守门值 | `& MF_Mathematics\build\bin\Release\probe_call.exe list_functions '{}'`，读 `value.count`；产物不存在时先按 [`engine/README.md`](engine/README.md) 构建 Release |
| 2 | C ABI 导出数（`math_call` 与 `function_exists`） | `Select-String -Path MF_Mathematics\api.h -Pattern 'MF_API'` |
| 19 / 16 | 引擎可执行目标数 / 注册进 CTest 的用例数 | `(Select-String -Path MF_Mathematics\CMakeLists.txt -Pattern 'add_executable\(').Count`；`ctest --test-dir MF_Mathematics/build -C Release -N` |
| 9 / 84 | 宿主对象数 / 宿主方法数 | `(Select-String -Path MFMath.Host.Rust\src\main.rs -Pattern 'MethodSpec \{').Count`；对象数由同一文件的 `HOST_OBJECTS` 表读出 |
| 415 / 391 | 映射到页面的界面模式数 / 页面并集数 | 在 `MF_UI\MFMath.UI.Vue` 下执行 `node tools/check-ui.mjs`，读输出的「引擎模式可达性」一行 |
| 48 | 端到端用例数 | `(Get-ChildItem MF_UI\MFMath.UI.Vue\tests\cdp-*.mjs).Count`；登记数由同一次自检输出「端到端用例」一行 |
| 18 / 30 / 126 | 教程篇数 / 教程引导目标数 / 数学键盘键数 | `(Get-ChildItem docs\tutorials-src\*.yaml).Count`；后两项读 `node tools/check-ui.mjs` 输出的「教程引用的 target」与「数学键盘」两行 |

同一个数字在全文只保留一个权威源，其余文档引用该权威源。action 与键名的权威源是 [`engine-signatures.json`](../MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json)。

## 写文档的规矩

1. 一份文档回答一个问题。标题即该问题，正文开头用引用块写明本文回答什么、与哪些兄弟文档分工。同一件事不写两遍。
2. 数字必须能由命令复跑。命令写进文档，或注明它出自哪份文档的哪条命令。action 数、方法数、用例数属于命令产出物，不属于叙述。
3. 手册与记录类分开。明确不做、能力边界、契约进手册；进度、风险、审查结论属于记录类，不进手册。
4. 引用代码给符号名。写函数名、常量名、键名、目标名，并在括号内给一条定位命令。行号会随改动漂移，不作为依据。
5. 失败先分类。产品缺陷、用例自身判据错误、环境未准备好是三种不同的结论，各自写明是哪一种。
6. 未验证的内容写现状与验证方法，不写成已验证。安装到启动这条路径即属此类，[`manual/INSTALL.md`](manual/INSTALL.md) 只写现状与验法。
7. 不留死链。只链接确实存在的文件；相对路径按写它的那个文件自身位置计算，本文位于 `docs/` 根，到仓库根写作 `../README.md`，`docs/manual/README.md` 到仓库根写作 `../../README.md`。
8. 改一处就改它的全部引用。改标题、改文件名、改口径时，在同一次改动中修掉引用它的位置。

## 地图外

`docs/` 根目录下另有 14 份 `.md` 不属于六层地图。其中 12 份列于下表；其余 2 份分别记录当前进度与风险、以及未实现的功能，随每次改动变化，用 `Get-ChildItem docs -Filter *.md -File` 列举。

| 文件 | 内容 | 与现役实现的关系 |
| --- | --- | --- |
| [`ACCOUNT.md`](ACCOUNT.md) | 用户系统的实现表 | 描述已退役的 .NET 宿主；现役落点见 [`link/FEATURES.md`](link/FEATURES.md) |
| [`ONLINE-SEARCH.md`](ONLINE-SEARCH.md) | 联网搜索的宿主侧实现 | 同上 |
| [`UPDATE-CHAIN.md`](UPDATE-CHAIN.md) | 更新链：只提示、显示校验值、交给浏览器 | 同上 |
| [`SETTINGS-BACKUP.md`](SETTINGS-BACKUP.md) | 设置备份的导出与导入 | 同上 |
| [`AI-ASSISTANT.md`](AI-ASSISTANT.md) | AI 助手：对话、上下文、流式、工具调用 | .NET 宿主时期的实现记录；现役面板见 [`ui/AI.md`](ui/AI.md) |
| [`STEP-VIEW.md`](STEP-VIEW.md) | 分步显示的渲染层 | 现役渲染约定，被 [`manual/README.md`](manual/README.md) 引用 |
| [`HANG-OPTIMIZATION.md`](HANG-OPTIMIZATION.md) | 会卡住的算法：实测、定位与优化 | 现役手册，被 [`manual/README.md`](manual/README.md) 引用 |
| [`hang-fix-verification.md`](hang-fix-verification.md) | 上述优化的修复前后对照 | 由脚本生成，不手工编辑 |
| [`MIGRATION-GAPS.md`](MIGRATION-GAPS.md) | 迁移期功能缺口报告 | 迁移期报告，判定基准是迁移前产品的实际形态 |
| [`PLAN-feature-completion.md`](PLAN-feature-completion.md) | 功能补全方案 | 规划期文档，含逐项清点结论 |
| [`STATUS-and-ROADMAP.md`](STATUS-and-ROADMAP.md) | 现状与规划报告 | 记录类，数字均为实测 |
| [`FRONTEND-FIXES.md`](FRONTEND-FIXES.md) | 前端审查结论的核实与修复记录 | 审查记录，含逐条可复跑断言 |

上表中描述 .NET 宿主的四份文档只保留作迁移参考，其数字与结论以 [`link/FEATURES.md`](link/FEATURES.md) 为准。
