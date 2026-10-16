# 功能补齐计划（实现只用 C++ / C# / JS·TS）

> 目标：把产品应有的功能集里、v2.0 目前尚未具备的部分补齐，同时把实现代码里的 Python **清零**。
> 本文只做方案，不含实现。所有结论均基于对现有代码的清点，关键处附证据。
>
> **清点状态：三路清点已全部完成** —— AI / 搜索 / 用户系统（§2、§4）、教程 / 键盘 / 工作区 / 分步（§3）、`.pyd` 覆盖审计（§5.1）。
>
> **实现状态（本仓库已完成的部分）**
> - ✅ **教程系统**（§3.1–§3.2）：18 篇 YAML 构建期转 JSON（含数量自检）、目录页、正文页、示例库、欢迎窗、引导遮罩与状态机。
>   已修：34/66 步静默失效 → 缺目标显式提示；补上上一步/暂停/继续/步骤进度条/接着上次走；只有真走完才标记已学；遮罩不再吞点击。
> - ✅ **数学键盘**（§3.3）：126 键 / 6 分类；插入值全部 LaTeX 化；占位符 `#0/#?` 保留；矩阵模板补齐 `\end`；新增搜索 / 最近使用 / 收藏 / 页签记忆。
> - ⏸ **分步显示**（§3.5）：按指示本轮不做（依赖"步骤来源"决策，见 §0.4 第 4 条）。
> - ⏸ 工作区保存（§3.4）、用户系统与搜索（§4）、AI（§2）：尚未开始。
> - 验证：`npm run check:ui`（构建期自检）、`npm run build`、`tests/cdp-tutorials-keypad.mjs`（真实宿主内 30 项断言全通过，已登记进 `tests/run-all.ps1`）。
>
> **两处与计划的偏差（后续处理）**
> 1. 教程进度暂存 **localStorage**（WebView2 用户数据目录在 `%LOCALAPPDATA%\MFMath\WebView2`，卸载不误删），而非计划里的 `%APPDATA%\MFMath\tutorial_progress.json`；读取该遗留进度文件需要宿主文件访问（§4.3 的 `store` 桥，属 P1）。
> 2. 11 个依赖 AI / 搜索 / 设置界面的引导步骤列为"待实现"（`src/lib/tutorial/targets.js` 的 `PENDING`）；构建期自检会拦住既未实现、又没写理由的目标。

---

## 0. 约束、现状与判定标准

### 0.1 三条硬约束

1. **实现代码只用 C++、C#、JS/TS** → 现有 Python 必须整体清零。
2. **计算仍由 C++ 引擎完成** → 引入 AI 也不能破坏（注意既有的 Python 版分步提示词**违反**这条，见 §2.9）。
3. **不破坏已验证成果** → 引擎 424 action、准确性 2180 用例、前端 43 个 CDP 测试的能力不能因改造而丢失。

### 0.2 现状核对（已实测）

| 项 | 事实 |
| --- | --- |
| 桥接协议 | JS → C# 走 `window.chrome.webview.hostObjects.sync.<对象>.<方法>()`；现有三个宿主对象：`mf`(引擎)、`win`(窗口)、`con`(控制台) |
| 引擎桥 | `mf.Dispatch(name, argsJson)` 通用透传 + 8 个类型化符号方法；`mf.FunctionExists(name)` 可做能力探测 |
| 长任务模式 | 控制台用「开始 + 轮询」：`con.Start(...)` 返回 `runId`，再 `con.Poll(runId)` 取状态（同步调用会阻塞页面） |
| **推送通道** | **目前没有**。宿主未见 `PostWebMessageAsJson` / `WebMessageReceived` 的使用，C#→JS 只能靠同步返回值。AI 流式输出与更新进度都需要它 → 列为 P0（动工前再复核一次，一行 grep 即可） |
| 宿主代码量 | 约 1150 行 C#（ConsoleBridge 684 / ComponentDownload 174 / WindowBridge 89 / MainWindow 75 / MathBridge 63 / NativeEngine 41 / App 21），风格是"一个 Bridge 一个 host object" |
| 前端代码量 | `MF_UI/MFMath.UI.Vue/src` 共 9927 行；已用 Vue 3.5 + Vite + **KaTeX** + **MathLive** + vue-router |
| 前端已有基础 | 数学键盘**已部分实现**（`ExpressionList.vue` 符号面板、`BasicCalcView.vue` 30 键）；教程、工作区保存、分步显示**三块都还没做**（`CalcView.vue:147-152` 明确写"步骤推导未接入"） |
| 现有可复用能力 | **组件下载**（`ComponentDownload.cs`）已实现断点续传（`RangeHeaderValue`）+ SHA-256 校验 + zip 解包 + 进度回调；基址 `https://mf-vis-science.cn/download/component/`，可用 `__MF_COMPONENT_BASE` 覆盖 |
| 站点后端 | 已提供桌面端所需全部端点（§4），其中 `/api/version` 与 `/api/components` 现成 |
| 站点依赖 | 站点**不依赖** `math_http_service.py`（站点源码零引用）→ 该服务可整体弃用 |
| 引擎调用方式 | v2.0 走 **P/Invoke 进程内调用**（`NativeEngine.cs`）；仓库里那套"Python HTTP 服务 + `{code,data.result,msg}` 生成客户端"是**已废弃的 HTTP 层**，不复用（§4.4 第 11 条） |
| 引擎注册方式 | `register_function`（`registry.hpp:23` / `registry.cpp:18`），不是宏 |

### 0.3 Python 清零清单

| 位置 | 性质 | 处置 |
| --- | --- | --- |
| `MF_Mathematics/**/*.py`（12 域后端 + `core/registry.py` + `utils/` + `ai_accelerator`/`ai_cache`） | 派发层 + 部分算法 + 守卫判据 | 派发层已由 C#/TS 直调 C ABI 取代；守卫判据下沉引擎（§5.3） |
| `numerical/*.pyd`（6 个）+ `linear_algebra/inner_product.dll` | CPython 扩展 | **可安全弃用** —— 覆盖审计已完成（§5.1）：15 项完全覆盖 / 4 项部分覆盖 / **0 未覆盖**，只需 1 项前置修改 |
| `MF_UI/**/*.py`（Qt 应用 2101 文件） | 既有 Qt UI | 已被 Vue 取代 |
| `math_http_service.py` + `.spec` | Python HTTP 服务 | **整体弃用**（站点零引用） |
| `MF_AI` / `MF_Online` / `MF_Tutorial` / `MF_User` | 四个功能模块 | C#/TS 重写（§2–§4） |
| `scripts/*.py` + 3 个 PyInstaller `.spec` | 打包、手册、图标、截图 | Node(.mjs) 或 C# 重写（§8） |
| `tests/accuracy/*.py`（2180 用例） | 验证 | **冻结成语言中立 JSON + C++ runner**（§5.2） |

### 0.4 开工前需要你拍板（六项）

1. **控制台的 Python 语言支持是否保留？** 那是给用户写程序的**可选运行时组件**（CPython 组件），不是我们的实现代码。建议保留，但需确认不算违反约束。
2. **是否允许 Node 作为构建工具？** 打包 / 手册 / 截图都需要一个脚本层；用 Node(.mjs) 最省事，若要构建层也是 C#，改写为控制台工具同样可行。
3. **Inno Setup 的 `.iss` 与 CMake 的 `CMakeLists.txt`** 属第三方工具的**声明式配置**（不是实现代码），建议视为例外；严格模式可改 WiX/MSIX（用 C# 生成）。
4. **AI 分步提示词要"改行为"，且"本地步骤"会随 Python 清零而消失（两件事一起定）**：
   - 既有的分步提示词明确要求模型**自己算**（原文见 §2.9），与"计算仍用 C++"**直接冲突** → v2.0 按"引擎先算、AI 只解释"改写；
   - 既有的本地步骤（`MathObject.steps`）由 **84 个 Python 文件、约 600 处**产出，而引擎的 C ABI 信封**没有 steps 字段**（已核对，见 §3.5）→ **Python 清零后本地步骤会整体消失**。请选择：① 引擎侧为高频 action 新增步骤输出；② 纯 AI；③ **混合**（推荐，本方案默认）。
5. **是否给 AI / 云功能加登录门禁？** 既有实现**完全没有门禁**（§4.1 末尾）：`balance`/`is_active` 只做显示，唯一配额是本地 `usage.json` 且配了 API Key 就绕过。若要"登录才解锁"，需站点侧配套按 `balance` 扣减，目前后端没有这个语义。
6. **配额制（免费 5 次步骤 / 3 次加速）保留否？** 保留的话云服务要能对账（现状是纯本地计数 + 绕过规则，服务端不参与）。

---

## 1. 目标架构

```
┌─────────────────────────── Vue 3 + TS（前端，9927 行）───────────────────────────┐
│  现有 22 个模式视图（已全部迁移完成：REAL_VIEWS 9 + CalcView 13）                │
│  新增：AiPanel / StepPanel、SettingsPanel、SearchPanel、HistoryPanel、           │
│        LoginDialog / RegisterDialog / AccountPanel、TourOverlay + 教程引擎、     │
│        SymbolPad（统一符号键盘）、工作区保存                                      │
└──────────────┬───────────────────────────────────────────┬──────────────────────┘
      ①同步 host object（请求/响应、短操作）        ②新增推送通道（流式、进度）
      window.chrome.webview.hostObjects.sync.*      postMessage ↔ PostWebMessageAsJson
┌──────────────┴───────────────────────────────────────────┴──────────────────────┐
│  C# 宿主 MFMath.Host（现 1150 行）                                              │
│  现有：mf (MathBridge) · win (WindowBridge) · con (ConsoleBridge) ·             │
│        ComponentDownload（组件下载，含断点续传+sha256）                          │
│  新增：PushChannel · ai (AiBridge) · acc (AccountBridge) · net (SearchBridge) · │
│        store (StoreBridge) · upd (UpdateBridge) + MFMath.Updater.exe            │
└──────────────────────────────┬──────────────────────────────────────────────────┘
                               │ P/Invoke
┌──────────────────────────────┴──────────────────────────────────────────────────┐
│  C++ 引擎 mf_mathematics.dll（424 action）+ 5 个依赖 DLL                          │
│  对外仅两个 C ABI：math_call(name, args_json, out, size) / function_exists(name)  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**新增推送通道（P0，一切流式功能的地基）**

- C#：`CoreWebView2.WebMessageReceived`（JS→C#）与 `CoreWebView2.PostWebMessageAsJson`（C#→JS）
- JS：`window.chrome.webview.postMessage(obj)` / `window.chrome.webview.addEventListener("message", handler)`
- 统一事件信封：
  ```json
  { "v":1, "ch":"ai|update|component|search", "id":"<requestId>",
    "seq":12, "done":false, "payload":{ } }
  ```
- 规则：`seq` 单调递增；单通道缓冲上限（超出置 `overflow:true`）；`done:true` 后停止；同一 `id` 只认一次 `done`
- **合并投递**：AI 逐字回包按 ~40ms 或 ~64 字符合并成一批再 postMessage，避免每字符一次跨进程调用
- 无宿主时（浏览器 `npm run dev` 预览）全部降级为空实现，与现有 `console/bridge.js` 的 `if (!c) return null` 风格一致
- 兜底：保留轮询式接口（`Poll(id)`），供不支持推送的环境与回归测试用

---

## 2. AI 助手（同时补齐"查看步骤"）

### 2.1 现状与缺口

- `CalcView.vue:147-152` 的 `onSteps()` 提示「步骤推导未接入」——"查看步骤"是唯一已接线却无能力的入口。
- 既有 Python 桌面版的 AI 是真实功能：`main_window.py:603` `from MF_AI.config import Config`，另有 `MF_UI/dialogs/ai_dialog.py`、`ai_config_prompt.py`、`MF_UI/calc/step_viewer.py`。
- 新前端 grep 无任何 AI 代码。

### 2.2 组件划分

**C# `AiBridge.cs`（宿主对象 `ai`，约 450 行）**

| 方法 | 语义 |
| --- | --- |
| `Configured()` | 是否已配置（密钥或本地模型可用） |
| `GetConfig()` | 返回非敏感配置 + `apiKeySet` 布尔；**绝不回明文密钥** |
| `SetConfig(json)` | 写入配置；密钥经 DPAPI 加密后单独存 |
| `TestConfig(json)` | 连通性自检（既有 Python 版设置页有"测试连接"） |
| `Ask(requestId, json)` | **立即返回**；回复经推送通道 `ch:"ai"` 分片回传 |
| `Cancel(requestId)` / `CancelAll()` | 中断流式请求 |
| `History(limit, offset)` / `ClearHistory()` | 会话历史（JSONL） |
| `Models()` | 从 `provider_models` 返回可选模型（修正既有实现的硬编码，见 §2.10） |

**TS**：`src/lib/ai/bridge.js`（协议 + 无宿主降级）、`src/components/ai/AiPanel.vue`（对话 / 流式 / 停止 / 复制最后回复 / 清空 / 上下文提示条 / 未配置 banner）、`src/components/ai/StepPanel.vue`（分步推导，见 §3.5）
**接入点**：`CalcView.vue` 的 `onSteps()`、`ResultDialog.vue` 的"查看步骤"按钮、`App.vue` 顶栏 AI 入口

### 2.3 关键设计：AI 不计算（守住硬约束）

固定流程「**引擎先算，AI 只解释**」：

1. 用户提问或点"查看步骤" → **先**调引擎（`mf.Dispatch`）拿到精确结果与可用中间量；
2. 把 `{题目, 引擎结论, 中间量}` 作为**事实**写进提示词，并声明"不得改变这些结论"；
3. AI 产出步骤，**每一步里的数学式子回引擎核验**：
   - 等式/化简 → `compare_expr`（恒等判定）
   - 数值点 → `expr_eval`
   - 求导/化简步骤 → `diff` / `simplify_sym`
   - 核验失败的步骤在 UI 标黄并注明"未通过引擎核验"，**绝不静默采纳**
4. 结果区**永远**显示引擎值；AI 文本只能进入"解释"区。
5. 可选优化：引擎新增 `steps_verify`（批量核验一组等式），减少往返。

**验收判据**：一条 CDP 测试断言"无论 AI 说什么，结果区文本恒等于引擎返回值"。

### 2.4 配置、密钥与隐私

- 配置：`%LOCALAPPDATA%\MFMath\ai-config.json`，**字段名与既有的 `MF_AI/config.yaml` 对齐**（§2.8）；启动时若发现遗留的 `config.yaml`，做一次性迁移并提示
- 密钥：**DPAPI**（`ProtectedData.Protect`，`CurrentUser`）加密存 `ai.secret`；**同时继续读 `AI_API_KEY` 环境变量 / `.env`**（兼容既有部署，优先级见 §2.8）
- 不落明文、不进日志、错误信息过滤；设置面板提供**"禁用 AI"**硬开关
- 隐私：明确告知"提问内容会发送到所配模型服务"

### 2.5 上下文、成本与健壮性

- 上下文只带 `{当前模式, 表达式, 引擎结果, 最近 N 轮}`（N 默认 6，可配）
- 缓存沿用既有语义（§2.8）：命中不计费；v2.0 增加缓存面板可清空
- 超时沿用既有约定（非流式 60s / 流式 120s）；**既有实现没有重试，v2.0 增加指数退避重试**（仅网络错误与 5xx，4xx 不重试）
- 会话历史默认保留 200 条，超出滚动删除

### 2.6 提示词

版本化资源 `prompts/stepwise.md`、`prompts/tutor.md`、`prompts/explain-error.md`，随宿主发布。
**系统提示词必须写明**：不得自行计算、结论以引擎值为准、不得编造未核验的等式。
既有三段提示词的原文已取到（§2.9），改写时保留其教学语气与 `\boxed{...}` 约定。

### 2.7 异常矩阵（全部要过）

断网 / 无密钥 / 密钥错误 / 超时 / 用户取消 / 服务端 5xx / 流式半途断开 —— 七种情况都不崩、都有明确提示、都保持引擎结果可用。

### 2.8 既有配置面清点（逐条对齐，不得丢字段）

| 项 | 内容 |
| --- | --- |
| 配置结构 | `MF_AI/config.yaml` 两层嵌套：`api_base`、`default_model`、`context_length`、`model_map`（角色名→模型名）、`model_params`（按模型覆盖 max_tokens/temperature）、`provider`、`provider_endpoints`、`provider_models`、`local_model{enabled,path,auto_detect}` |
| **角色名** | `Chat`/`Fable`/`Haiku`/`Mythos`/`Opus`/`Reasoner`/`Sonnet` —— **不能只存实际模型名**：`ai_accelerator` 以 `role="Sonnet"` 调用，删掉映射会全链路报错 |
| 环境变量 | `AI_API_KEY`、`AI_BASE_URL`、`AI_MODEL`、`AI_MAX_TOKENS`、`AI_TEMPERATURE`、`AI_SYSTEM_PROMPT`；优先级：运行时设置 > `config.yaml` > 环境变量 > 默认值。**`api_key` 只从环境变量/`.env` 读**（既有约定：不写进 yaml） |
| 请求协议 | `{baseUrl}` 下的 OpenAI 兼容对话端点 `POST /v1/chat/completions`（`v1` 是该协议的版本段，与服务商接口一致，与本产品版本无关）；请求体为 OpenAI 兼容格式；SSE 流式识别 `data: ` 前缀与 `[DONE]` 终止 |
| 默认值 | base `https://api.deepseek.com`、model `deepseek-v4-pro`、max_tokens 8192、temperature 0.7 |
| 缓存 | `ai_cache.json`：键 `md5("{mode}|{expr}|{model}")`，条目 `{mode,expr,model,response,timestamp}`，上限 128，LRU。**键算法必须一致**，否则既有缓存全失效 |
| 配额 | `usage.json`：`{"YYYY-MM-DD":{"steps":n,"accelerations":n}}`，免费 5 / 3，**配了 API Key 则完全不限**（是否保留见 §0.4 第 6 条） |
| 输出约定 | `\boxed{...}` 标最终答案；`$...$` 行内、`$$...$$` 独立行 |
| 附加配置面 | 根 `config.json` 的 `ai` 段（`daily_free_steps`、`daily_free_accelerations`、`providers.*`、`default_provider`）目前无人消费，但已是公开配置面，建议一并读取 |
| 三级步骤来源 | 内存缓存 → 磁盘 `ai_cache.json` → AI；另有一条"本地 `MathObject.steps` 直出，跳过 AI"（因构造/赋值竞态从未生效，见 §3.5） |

**实现提醒**：既有的 `config.py:_parse_yaml_manual` 是只支持两层的**手写 YAML 解析器**。C# 侧用正式 YAML 库读同一文件即可，但要保证 `model_map`/`model_params` 往返不丢字段。

### 2.9 既有三段提示词里，有一处直接违反硬约束（必读）

既有实现里存在**三套**独立的分步提示词：

1. `MF_UI/calc/step_viewer.py` 的 `_STEP_SYSTEM_PROMPT`：
   > 「你是一位经验丰富的数学教师……请你从头开始完成这个操作，生成完整的、逐步的推导过程——注意：**你需要自己完成计算，而不是解释已有的结果**。」
   > 并要求「每步标注【步骤 N】」「最终答案用 `\boxed{...}` 标注」「步骤数量 3~8 步」。
2. `MF_Mathematics/utils/ai_accelerator.py` 的 `generate_steps`：system 为「你是一位数学助教……请给出清晰的分步推导过程。每步以【步骤 N】开头，最后给出最终答案。」
3. 同文件 `accelerate`：system 为「你是一位数学计算引擎。请直接对表达式进行计算，返回计算结果……**仅返回结果，不要解释**。」并以 `MathObject` 返回。

**冲突**：第 1、3 套都让模型**自己算**。第 3 套的 `accelerate` 更是直接拿模型输出当计算结果的替代品——它被真实接线在 `base_calc_block.py:180-196`（守卫判定 BLOCK 时让用户选"AI 加速"）。

**v2.0 的处理**：
- 三段全部改写为"引擎先算、AI 只解释"；删除"你需要自己完成计算"这类指令；增加"每一步等式必须可被引擎核验"。
- `accelerate` 这个能力应当由**引擎直接提供**（引擎已有对应 action），而不是问模型；若引擎确实算不了，UI 应如实说明"引擎不支持"，而不是让模型给个近似值冒充结果。
- **这是行为变更，需你确认**（§0.4 第 4 条）。

### 2.10 前端渲染与"不移植"清单

**渲染**：既有 Python 实现用 matplotlib `agg` + `mathtext` 把公式渲染成 base64 PNG（并会降级 `\boxed`/矩阵/cases）。v2.0 改用**已有的 KaTeX**，保留既有的预处理语义：剥离 `\boxed{}`（配对括号算法）、`pmatrix/bmatrix/vmatrix` → 括号、`cases` 展开、`$$...$$` 块级居中 / `$...$` 行内。流式期间先追加纯文本、结束后整体替换为渲染结果（沿用既有行为，避免逐字重排版闪烁）。

**不移植（死代码与缺陷）**：
- `MF_AI/agent.py` 全体（`MathAgent`、`TOOLS`、工具调用循环）：全项目无引用；其 `_tool_eval` 用 Python `eval()` + numpy 白名单 —— **绝不可照搬到 JS 的 `eval`**（注入风险）。将来若做"模型调工具"，只允许模型请求**引擎 action 名**，由 C# 白名单校验后再调引擎。
- `MF_AI/strategy.recommend()`、`models.ChatRequest/ChatResponse`、`Config.get_model_for_role()`：均无生产调用者。
- `ai_dialog` 硬编码 5 个模型的下拉（含 `gpt-4o` 配 DeepSeek 端点必然失败）→ 改为读 `provider_models`。
- `_AIStreamWorker` **全局改 `Config` 单例的 model**（`ai_dialog.py:136-149`）→ v2.0 一律按请求传参，禁止进程级副作用。
- `about_dialog.py` 三处声称"密钥存 keyring"——**与实现不符**（实际只读环境变量/`.env`），不要照抄该说法。

---

## 3. 教程系统 / 数学键盘 / 工作区保存 / 分步显示

### 3.1 既有教程系统的清点结论（数据层尚可，**引导层基本不可用**）

**数据层质量不错**：`models.py` 5 个 dataclass、`engine.py` 16 个 public 方法、18 课 YAML 驱动、`tutorial_progress.json` 单文件进度持久化。

**但引导层严重缺损**：

| 缺陷 | 事实 | 后果 |
| --- | --- | --- |
| 目标控件不存在 | **66 个步骤中 34 个**目标控件不存在（`calc_block.input`、`settings_dialog.ai_tab`、`math_keyboard.panel` 等 **22 个名字全库无 `setObjectName`**），在 `walkthrough.py:118-123` 被**静默跳过** | 教程 **05 与 11 每一步都失效**；点"引导"遮罩一闪即消失，**而教程仍被标记为"已完成"** |
| 遮罩吞点击 | `overlay.py:91` 设 `WA_TransparentForMouseEvents=False` | 所谓"用户点击"其实是 `_execute_action` 反射式模拟；多数 `click` 步骤因缺 `action_value` 根本不执行 |
| 缺基本控制 | `_advance` 只前进；`stop`/skip 把 `_current_step` 归零 | **没有"上一步"、没有"暂停"** |
| 定位机制 | 「注册名 → QWidget 对象引用」字典 + `objectName` 兜底（`walkthrough.py:104-123,177-191`），**YAML 里没有任何坐标** | 好消息：迁到 Vue 可 1:1 平移（`data-tour` + `querySelector` + `getBoundingClientRect()`） |

**结论：引导层必须重做，不沿用既有实现。** 重做时必须：
- **禁止静默跳过**：目标不存在时要么在 JSON 里标注该步不可用并**从课程中移除**，要么在 Vue 组件上补 `data-tour`；绝不能"跳过但算完成"。
- 重新逐个核对那 22 个失效名字，决定"补 `data-tour`"还是"删除该步"。
- 补齐既有实现缺失的**上一步 / 暂停 / 跳过 / 步骤进度条**。
- 遮罩改为**不拦截点击**（`pointer-events: none`）+ 显式"下一步"按钮；若某步要求用户真实操作，才局部开启 `pointer-events: auto` 并提示"点击此处继续"。
- **完成判定**：只有真正走完全部步骤才写 `done:true`（消除既有的假完成判定）。

#### 3.1.1 精确事实（清点结论，实现时照此对齐）

**数据模型**（`models.py`，5 个 dataclass）：
- `Step`：`target, text, highlight(rect|circle), placement(top|bottom|left|right), action(click|type|select|wait), action_value, image`
- `Example`：`label, expr, mode, action, description`
- `FAQ`：`q, a`
- `Tutorial`：`id, title, difficulty, category, duration, order(默认 99), summary, steps[], examples[], faq[], prerequisites[]`
- `TutorialProgress`：`completed[], last_tutorial, first_launch_done, launch_count`

⚠️ **`action` 字段两层语义重载**：`Step.action` = 动作类型（click/type/select/wait），`Example.action` = 计算操作名（如"化简"）。YAML 里两者都写 `action:`，靠缩进区分 → **Vue 侧必须改名**（`step.actionType` / `example.operation`），否则必然出错。

⚠️ **两个死字段**：`Step.image` 在 18 个 YAML 中**出现 0 次**；`Tutorial.prerequisites` 只有 4 篇写、**无任何消费点**，且 `16-functional-analysis.yaml` 引用的 `"real-analysis"` **教程并不存在**。

**规模**：18 课 / **66 步 / 52 示例 / 42 条 FAQ**。（`welcome_dialog.py:110` 文案写"30+ 示例任务"，实际 52 条——顺带修）
**步骤文本含 HTML**（`<br>`/`<b>`），是唯一被两处消费的富文本约定：引导 tooltip 直接渲染，帮助浏览器只做 `<br>→" → "`、删 `<b>` 的降级，**其余标签原样泄漏**。

**进度文件**：`<仓库根>/tutorial_progress.json`，仅 4 键、无版本号、无 per-step 粒度。实况：`{"completed":["quick-start"],"last_tutorial":"quick-start","first_launch_done":true,"launch_count":445}`。
- **读容错不全**：只捕 `FileNotFoundError`/`JSONDecodeError`（退化为全新进度，**不提示用户**）；`PermissionError` 等会**向上抛**
- **写静默失败**：`except OSError` 只 `logger.debug`（`engine.py:289-290`）→ **装在 Program Files 时进度丢失且用户无感**
- "标记完成"只有两个触发点：引导 `_finish()`（**包括全部步骤被跳过的空转**）与帮助文档的 `✓ 标记为已学` 链接
- 引擎级 API 中 `get_next_uncompleted` / `mark_incomplete` / `get_launch_count` **UI 零调用**（死代码）
- **引擎没有任何步骤导航 API**（无 start/next/prev/pause/resume）；`start()` 永远从第 0 步开始且**不检查 `is_completed`**；`stop()`/skip 会把 `_current_step` **归零**（丢进度）

**目标名注册**：`main_window.py:858-882` 只注册 **9 个**名字，且 `theme_toggle`/`ai_button`/`search_button`/`settings_button` 在缺控件时**回退成整个主窗口** → 高亮框住整窗（"看似生效实则错位"的隐藏缺陷）。
**失效的 22 个 target 名**（全库无对应 `setObjectName`，附出现次数）：`calc_block.input`(5)、`calc_block.action_dropdown`(4)、`plot_workspace.add_function`(3)、`plot_canvas`(2)、`calc_block.calc_button`(2)、`calc_block.ai_accel_button`(2)、`math_keyboard.titlebar`、`math_keyboard.panel`、`geometry_canvas`、`main_window.keyboard_button`、`settings_dialog.ai_tab`、`settings_dialog.appearance_tab`、`search_panel.input`、`search_panel.results`、`ai_dialog.input`、`ai_dialog.send_button`、`ai_dialog.context_label`、`plot_workspace.function_input`、`plot_workspace.sliders`、`result_dialog.steps_button`、`step_viewer.content`、`main_window.ai_settings`。
命名风格也确实对不上（例：YAML `calc_block.calc_button` vs 代码 `setObjectName("calc_btn")`；`result_dialog.steps_button` vs `"resultStepBtn"`；`math_keyboard.panel` vs `"KeyboardPanel"`）。

**遮罩的精确参数**（Vue 版要 1:1 还原才算"等效"）：padding **8px**；挖洞圆角 **8px**，`circle` 为椭圆；遮罩色 `#00000073`(亮) / `#0000008C`(暗)；边框 `2.5px solid #3b82f6` + 外发光 `12px rgba(59,130,246,.24)`；脉冲 **1200ms InOutSine 无限**；tooltip 宽 220–340px，四方位定位后 `clamp(10, …)`；**最后一步按钮文字变"完成"**。

**三处点击/入口缺陷**：
- 遮罩**吞掉所有鼠标事件**（`WA_TransparentForMouseEvents=False`），点高亮区=前进而非真实点击；真实动作由 `_execute_action` 反射模拟，且 **15 处 `action: click` 里绝大多数没有 `action_value` → 根本不执行**
- `_open_guided_walkthrough` **硬编码 `start("quick-start")`** → 帮助文档/示例库里**没有"开始这篇教程的引导"入口**
- `example_library` 的筛选筛的是 `tutorial.category`（非示例自身字段）；示例的 `mode` 只映射了 14 个子模式里的 **4 个**，`"2D 绘图"` 匹配不到 → **静默不切换**（示例的绘图语义完全丢失）

**帮助文档 / Welcome / 示例库的来源**：
- 帮助文档 **100% 由教程 YAML 渲染**（没有独立 markdown 源）；`last_tutorial` 的**唯一写入点**在帮助浏览器
- Welcome 窗的 4 张卡片是**硬编码常量**（不读 YAML）；`mark_launched()` 在 `if` 块外**无条件执行** → 所以 `launch_count` 才会累积到 445；**唯一重置方式是删除进度文件**
- `MF_Tutorial` 全库**只被 `main_window.py` 引用**，纯 Python 自包含 → **移植成本低**

### 3.2 教程数据的迁移

- 18 课 YAML → 一次性 Node 脚本转 `ui/src/tutorials/*.json`（含上面的"失效步骤"处置结果）；YAML 原件留档 `docs/tutorials-src/` 供比对
- 动作受控指令集：`{action:"navigate"|"setField"|"click"|"wait", target, value}`
- `TourEngine.ts`：`start / next / prev / pause / skip / finish / resume`
- 进度：`localStorage["mf_tut_progress"] = { [id]: {version, step, done, updatedAt} }`；**教程版本变更即重置**
- 首次启动 `localStorage["mf_tut_welcome_seen"]` 不存在 → 欢迎窗一次；设置里可重置
- 帮助浏览器：打包 Markdown 用 `markdown-it`；示例库 → `ui/src/tutorials/examples.json`，走 `engineMap` 同一套参数构造

**验收**：18 课逐个走通；每步高亮框与目标元素矩形误差 ≤1px（CDP 断言）；中断后重进可续；**目标元素缺失时必须显式报错，不得静默跳过**；版本变更后进度重置。

### 3.3 数学键盘（126 键，但绝大多数按键插入的是 Unicode 而非 LaTeX）

**既有实现的事实**：126 键 / 6 分类，但**只有"常用模板"11 键插真 LaTeX，其余 115 键插 Unicode**；`▢` 占位符被 `replace` 直接剥掉（`math_keyboard.py:110`）；靠 `QApplication.focusWidget()` + `QLineEdit.insert()`，**对 AI 输入框和控制台完全无效**；无搜索、无最近使用、无收藏。

**v2.0 设计**：前端已有基础（`ExpressionList.vue` 符号面板、`BasicCalcView.vue` 30 键）→ 统一为一个 `SymbolPad.vue`：
1. 按键**一律插 LaTeX**（不再一半 Unicode 一半 LaTeX），由 MathLive 的 MathField 消费；
2. `▢` 占位符改为 **MathLive 的可跳转占位**（Tab 切换），不再被剥掉；
3. 作用对象 = **当前聚焦的 MathField / CodeEditor**；无焦点时给出明确提示（消除既有的静默失败）；
4. 补齐**搜索（按符号名/LaTeX）、最近使用、收藏**（localStorage）。

### 3.4 工作区保存（既有实现残缺）

**既有实现的事实**：全库唯一实现在 `main_window.py:667-697`，**只存 3 个字段**；`mode`/`calc_mode` **写了但恢复时从不读取**（只读 `expression`）；文件写在**安装目录**（Program Files 下必然失败）；无版本号、无自动保存、无关闭保存；恢复靠"第一个可见 `QLineEdit`"，找不到就**谎报"工作区已加载"**。

**v2.0 设计**：
- 存 `%LOCALAPPDATA%\MFMath\workspace.json`，带 `version` 字段（便于迁移）
- 字段 = 每个模式的输入/表达式列表/视图参数（缩放、范围、选中项等）
- **自动保存**（输入防抖 2s）+ 关闭时保存 + 手动"保存 / 另存为 / 恢复"
- 恢复失败必须**如实报错**，不得谎报成功
- 与 §4.3 的历史记录共用 `StoreBridge`（同一处落盘、同一套版本迁移）

### 3.5 分步显示（名为"分步"，实际是单块富文本；且存在一个真实缺陷）

**既有实现的事实**：
- 界面是**一整块只读 `QTextEdit` 富文本**：无列表、无折叠、**无逐步播放**；LaTeX 走 matplotlib→PNG→base64，`_fix_latex` 会把 `\boxed`/矩阵/cases 全降级
- **真 bug**：`StepViewer` 在**构造函数里就调 `_start()`**，而 `set_local_steps()` 在构造返回后才被调用 → **本地 `MathObject.steps`（由 84 个 Python 文件真实产出）永远不渲染**，用户看到的永远是 AI 现编的版本
- 三级来源与状态文案：内存缓存 / 磁盘 `ai_cache.json` / AI，对应 `（缓存）就绪` / `（磁盘缓存）就绪` / `就绪`

**v2.0 设计**（`StepPanel.vue`）：
- **可折叠的步骤列表 + 逐步播放**（上一步/下一步/全部展开），不再是单块富文本
- LaTeX 走 KaTeX（与全站一致）
- **优先显示引擎/本地产出的步骤**（消除既有的时序缺陷）：进入面板时先查本地步骤 → 再查缓存 → 最后才请求 AI，且顺序在 UI 上可见（"来源：引擎本地 / 缓存 / AI"）
- 与 §2.3 的核验回环联动：AI 产出的每一步都标注"已通过引擎核验 / 未核验"

**⚠️ 一条被清点揭出的重大后果（必须与 §0.4 第 4 条一起决策）**

既有的"本地步骤"（`MathObject.steps`，`list[str]`）是由 **84 个 Python 文件、约 600 处**产出的 —— 也就是说，**它属于要被清零的 Python 层**。而引擎当前的 C ABI 信封只有 `{isError, value}`，**没有任何 steps 字段**（已核对：`api.cpp` 与全部 `*_api.cpp` 中唯一命中 `"steps"` 的是 `multiplication_principle(get_int_array(args,"steps"))` 这个无关参数名）。

**结论：Python 清零后，这套本地步骤会整体消失。** 于是"查看步骤"只有三条路：
1. **引擎侧为高频 action 新增步骤输出**（推荐，但不可能覆盖 424 个；建议只做常用几十个：求导/积分/化简/解方程/极限/因式分解）；
2. **纯 AI**（等同于既有那套违反硬约束的做法）；
3. **混合**（本方案默认）：引擎能给的优先给，给不了的才问 AI，且 AI 步骤**必须回引擎核验**。

无论选哪条，P3 都要在 UI 上明确标注**步骤来源**（引擎本地 / 缓存 / AI）—— 用户需要知道哪几步是引擎保证的、哪几步只是解释。

### 3.6 既有实现中明确**不存在**的功能（清点结论，避免照想象实现）

| 常见误解 | 实际 |
| --- | --- |
| 引导有"上一步" | ❌ 不存在 |
| 引导有"暂停/继续" | ❌ 不存在；`stop()`/skip 还把步数归零 |
| 引导可跨会话续学（记住第几步） | ❌ 只记录整篇 completed |
| 引导可启动任意教程 | ❌ 硬编码 `quick-start` |
| 教程进度有 per-step 粒度 / 多用户隔离 | ❌ 只有整篇布尔标记，单文件无隔离 |
| `prerequisites` 有依赖门禁 | ❌ 死字段；且引用了不存在的教程 |
| `Step.image` 有截图 | ❌ 0 次出现 |
| 引导能真的点到真实按钮 | ❌ 遮罩吞点击，动作是反射模拟且多数不执行 |
| 帮助文档有独立 markdown 源 | ❌ 100% 由教程 YAML 渲染 |
| 帮助树显示难度标签 | ❌ 算了 `diff_tag` 却没拼进标签 |
| 数学键盘是浮动的 | ❌ 是底部固定面板（教程 11 的文案与实现不符） |
| 键盘支持搜索 / 最近使用 / 收藏 / 快捷键 | ❌ 全部未实现 |
| 键盘在 AI 输入框 / 控制台可用 | ❌ 只支持 `QLineEdit` |
| 键盘插入的是 LaTeX | ⚠️ 只有"常用模板"11 键是 LaTeX，其余 115 键是 Unicode；且 `▢` 占位符被**剥掉**（`\frac{▢}{▢}` → `\frac{}{}`，无法定位光标） |
| `QLineEdit` 有 LaTeX 高亮 | ❌ `LatexLineEdit` 是空壳子类 |
| 工作区有自动保存 / 关闭保存 / 启动恢复 / 快捷键 | ❌ 全部没有（只有手动菜单） |
| 工作区恢复模式 | ❌ `mode`/`calc_mode` 写了从不读 |
| 工作区有版本号 / 迁移 / 备份 | ❌ 全无；且直接覆盖写，写一半崩溃即损坏 |
| 步骤显示是"分步列表" | ❌ 是一整块只读 `QTextEdit`；无列表、无折叠、无逐步播放 |
| 步骤来自本地引擎 | ⚠️ 有本地 steps，但因构造/赋值竞态**实际永不显示**（§3.5） |
| 步骤用 KaTeX 渲染 | ❌ matplotlib mathtext → base64 PNG，且 `\boxed`/矩阵/cases 被降级剥离 |
| 步骤跟随暗色主题 | ❌ 颜色硬编码，暗色下仍是白底浅字图片 |
| 步骤渲染失败会重试 / AI 步骤是流式 | ❌ 都没有；`QThread` 也无法中断 |
| 教程的"续学"数据被消费 | ❌ `get_next_uncompleted` 是死代码 |

**修复优先级（按用户可感知的严重度）**

1. 教程 **34/66 步骤目标失效**（05 与 11 全废，且空转即标记完成）
2. 工作区 `mode`/`calc_mode` 不恢复 + 安装目录写入失败
3. **本地步骤因竞态永不显示**，却去调 AI（既慢又违反硬约束）
4. 引导"假交互"（遮罩吞点击 + 模拟点击不可靠）
5. 教程进度静默写失败（用户丢进度无感）
6. 键盘插入后 **Ctrl+Z 无法逐字符撤销**（窗口级"表达式历史"抢占了快捷键）
7. 暗色主题下步骤正文仍是白底

---

## 4. 用户系统 / 在线搜索 / 历史与设置

### 4.1 用户系统：**只做客户端**（后端现成，已核实）

站点已有端点（`MVS官网/src/app/api/`）：

| 端点 | 方法与编码 | 请求 | 成功响应 |
| --- | --- | --- | --- |
| `POST /api/login` | **form-urlencoded** | `username`, `password` | `{access_token, token_type:"bearer"}` |
| `POST /api/send-code` | JSON | `email` | `{msg}` |
| `POST /api/register` | JSON | `username`, `email`, `password`, `code` | `{msg}` |
| `POST /api/verify-code` | **form-urlencoded** | `username`, `code` | `{msg}` |
| `GET /api/me` | — | 头 `Authorization: Bearer <token>` | `{username, email, balance, is_active}` |
| `POST /api/logout` | JSON（空对象 `{}`） | 同上头 | `{msg}` |
| `GET /api/version` | — | 无鉴权头 | `{code:0, data:{latest, date, download_url, changelog}}` |

- 信封：公开 API 用 `{code:0, data, msg}`；错误统一 `{detail:"..."}` + HTTP 状态码（**既有 FastAPI 兼容格式，桌面端依赖 `detail`**）
- 限流：登录失败过多返回 429，文案含剩余时间

**C# `AccountBridge.cs`（宿主对象 `acc`，约 250 行）**：`Login` / `Logout` / `Current` / `Refresh` / `Register` / `SendCode` / `VerifyCode` / `ChangePassword` / `LoginHistory`

**接口约定（逐条必须保）**
- 7 个端点的**方法与编码逐字不变**，且注意**同批 POST 里编码不统一**：`/login`、`/verify-code` 是 **form**；`/send-code`、`/register`、`/logout` 是 **JSON**（`/logout` 体为空对象）
- 错误体字段名 `detail`；鉴权头 `Authorization: Bearer <token>`；token 字段名 `access_token`；`/me` 字段 `username/email/balance/is_active`
- 默认基址 `https://mf-vis-science.cn` **必须保持默认值**（既有实现硬编码且无配置入口 → v2.0 补配置能力，默认不变）
- 注册校验 6 条逐条复刻：用户名 ≥3 且仅 `[a-zA-Z0-9_]`；邮箱 `^[^\s@]+@[^\s@]+\.[^\s@]+$`；验证码 6 位纯数字；密码 ≥6；两次输入一致
- 交互细节：发送验证码 **60 秒冷却**（按钮显示 `Ns`）；注册成功 → 自动登录（成功 800ms 关窗；失败则提示并预填登录页 + 1200ms 切页）；验证成功 → 持有用户名密码则自动登录，否则 1000ms 关窗；提交期间禁用表单、主按钮变 `处理中…`
- 文案与提示语（含 `登  录` 的全角空格）若文档/截图依赖，不要改

**关键结论：既有实现的登录前后没有任何功能门禁。**
`balance` 与 `is_active` 只用于**显示**（状态栏"欢迎，{username}！(余额: N)"），从未参与权限或配额判断；菜单项不随登录状态变化；唯一的配额是本地 `usage.json`（5/3），且**配了 API Key 就完全绕过**——与服务端 `balance` 毫无关系。
因此 v2.0 默认也**不做 gating**；若你希望改成"登录才解锁 AI/云功能"，属产品决策且需站点侧配套（§0.4 第 5 条）。

**既有实现的两处缺陷建议一并修**：token **不持久化**（纯内存，重启即丢登录）+ **无过期校验**（token 过期后 UI 仍显示已登录；`/me` 失败只记 warning 不清会话）→ v2.0 用 DPAPI 持久化 + 启动静默校验 + 401 自动登出。

### 4.2 在线搜索（`MF_Online` → C# 代理）

**三种后端（清点结果）**

| 引擎 id | 端点与解析 |
| --- | --- |
| `duckduckgo`（默认） | `GET https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1`，UA `MF-Mathematics/1.0`；解析 `Abstract`（1 条，`title=AbstractSource or "定义"`）+ `RelatedTopics[].Text/FirstURL` |
| `wolfram` | `GET https://api.wolframalpha.com/v2/query?input={q}&appid={app_id}&format=plaintext&output=json`；解析 `pods[].title` + `subpods[].plaintext`；`url` 统一构造为 `https://www.wolframalpha.com/input?i={q}`；缺 key 抛「Wolfram Alpha App ID 未配置。请在设置中配置。」 |
| `custom`（SearXNG 等） | `GET {endpoint}/search?q={q}&format=json`，UA 同上；解析 `results[].title/content/url` |

统一返回 `[{title, snippet, url, latex}]`，上限 **8 条**；`latex` 由文本里的 `$...$`（优先）或 `\[...\]` 提取。

**为什么放 C# 而不是前端 fetch**：UI 跑在 `https://mfmath.local` 虚拟主机下，直连第三方会撞 CORS（DDG 与 Wolfram 均无 CORS 头），且 `appid` 不应进入渲染进程；C# 侧统一出网并复用现有 `HttpClient` 策略。

- `SearchBridge.cs`（约 200 行）：`Search(query, requestId)`（结果经推送通道回传）、`Cancel(id)`、`ClearCache()`
- TS：`SearchPanel.vue`（搜索框占位"搜索数学概念、公式、定理…"、引擎下拉、结果列表 `"{title}\n{snippet[:200]}"` + tooltip 全文、状态栏、**"插入到当前块"**按钮、回车搜索、双击插入、空结果提示项）
- 插入语义：取 `snippet`（回退 `title`），有 `latex` 时前缀 `"$" + latex + "$ "`，插到**当前聚焦输入框**，找不到则提示"请先激活一个计算块输入框。"
- **对齐点**：结果字段名 `title/snippet/url/latex`；引擎 id 字符串 `duckduckgo`/`wolfram`/`custom`；env 名 `SEARCH_ENGINE`/`SEARCH_TIMEOUT`/`WOLFRAM_APP_ID`/`SEARCH_CUSTOM_URL`；8 条上限；DDG 参数与 UA；用户可见错误文案
- **要修正的既有缺陷**：缓存键**只有 query、engine 不入键**（换引擎会命中别家结果）、**无 TTL**、容量恒为 50 且不读环境变量 → v2.0 键改为 `sha256(engine + query)` 并加 TTL（属行为变更，需知会）
- 既有实现**完全没有搜索配置 UI**（Wolfram / 自定义在不手写 env 时必然失败）→ v2.0 在设置面板补齐

### 4.3 历史与设置（当前是死按钮与 `alert("待实现")`）

- `StoreBridge.cs`（约 200 行）：`GetHistory()` / `AppendHistory(entry)` / `ClearHistory()` / `ExportHistory(path)`，并兼管工作区（§3.4）
- 存储 `%LOCALAPPDATA%\MFMath\history.json`（**不用 localStorage**：WebView2 数据目录重建不丢，且控制台/CLI 可读）
- 条目：`{at, mode, route, input, engineResult, verified, aiUsed}`，默认上限 2000
- `SettingsPanel.vue`：外观（复用现有 10 套配色 + 形状/疏密/字体，**已有实现不动**）、引擎路径与版本、AI 配置、账户、搜索配置、更新通道、组件目录、缓存清理、重置教程进度
  - 外观继续用 localStorage；其余落 C# JSON
- 顶栏搜索框：本地历史模糊搜索 + 可选在线搜索两种模式

### 4.4 既有缺陷清单：修或保留（逐条需拍板）

| # | 缺陷（均已核实） | 建议 |
| --- | --- | --- |
| 1 | 分步提示词要求模型**自己算**（违反硬约束，§2.9） | **必改** |
| 2 | `.env` **未进 `.gitignore`**（密钥误入库风险） | **必改**（v2.0 的 `.gitignore` 已含 `.env`） |
| 3 | 教程 34/66 步目标控件不存在，**静默跳过且仍标记完成**（§3.1） | **必改** |
| 4 | `StepViewer` 构造即启动，本地步骤永远不渲染（§3.5） | **必改** |
| 5 | 工作区保存写在**安装目录**、字段残缺、恢复时谎报成功（§3.4） | **必改** |
| 6 | token 不持久化 + 无过期校验（过期仍显示已登录） | 改 |
| 7 | 版本比较用**字符串 `>`**（`1.10.0 > 1.9.0` 判 false） | 改（语义化比较） |
| 8 | 搜索缓存键不含 engine、无 TTL、容量写死 | 改 |
| 9 | 搜索/账户基址无配置入口 | 改（默认值不变） |
| 10 | AI 模型下拉硬编码、与 `provider_models` 不一致 | 改 |
| 11 | 全局篡改 `Config` 单例的 model | 改 |
| 12 | 数学键盘 115/126 键插 Unicode 而非 LaTeX、对 AI/控制台无效（§3.3） | 改 |
| 13 | 配额 5/3 与"配 key 即无限" | **需你定**（§0.4 第 6 条） |
| 14 | `about` 文案声称 keyring 实际不是 | 改文案；v2.0 真用 DPAPI |
| 15 | 生成的 C# 客户端期望 `{code,data.result,msg}`，而 HTTP 服务实际返回 `{isError,value}` —— **二者不兼容** | **不复用该 HTTP 层**：v2.0 走 P/Invoke，这套生成客户端与 Python HTTP 服务一并弃用 |

---

## 5. 引擎侧（C++）

### 5.1 弃用 6 个 `.pyd`：覆盖审计结果（**已完成**）

**结论：7 个模块（6 个 `.pyd` + `inner_product.dll`）可以全部弃用**，只有 1 项前置修改。

**为什么安全**：引擎已经**通过共享头文件**复用了这些 `.pyd` 的计算内核——`numerical_integration.cpp:9`、`interpolation.cpp:10` 直接 `#include` 同一份 `numerical_core.h` / `interpolation_core.h` 等；`CMakeLists.txt:56-62` 的源清单里**没有**任何 `*_core.cpp`，全库也**无 pybind11 依赖**。也就是说：算法本体早已编入 `mf_mathematics.dll`，`.pyd` 只是同一份内核的 CPython 包装层。

**覆盖统计：完全覆盖 15 项 / 部分覆盖 4 项 / 未覆盖 0 项。**

**部分覆盖的 4 项都是"返回值/参数层面"，不是算法缺失**：

| 项 | 缺口 | 处置 |
| --- | --- | --- |
| `jacobi_iteration` | 引擎丢弃了迭代次数（`numerical_api.cpp:288` 声明了 `int it`，`:289` 只返回向量），而 Python 侧 `matrix_numerical.py:129` 靠它判收敛 | **前置修改**（见下） |
| `gauss_seidel` | 同上（`:298-301`、`matrix_numerical.py:198`） | 同上 |
| `conjugate_gradient` | 同上（`:308-311`、`matrix_numerical.py:268`） | 同上 |
| `dot_c` / `norm_c` | 精度面：DLL 快路径为 double 专用；Python 侧的精确/有理输入原本走 sympy 回退，引擎只给 double | 记录为已知差异；若确有高精度需求，另开 action |

**唯一的前置修改**（1 处、3 个函数）：把 `numerical_api.cpp:288-291 / 298-301 / 308-311` 里**已经算出来却被丢弃的 `it`** 写进返回对象，输出改为 `{x: number[], iterations: int}` —— 与同文件 `power_method:319-323` 的风格一致，**无需新增 action 名**。次选方案是新增 `linear_iteration_report`。

**顺带确认的两件"死模块"**：
- `ode_core.pyd`：**零调用点**（`ode_solver.py` 全文不 import 它，用纯 numpy 重实现）→ 直接删。
- `trap.pyd`：**零调用点**，无源码；二进制分析确认只暴露 `trapezoidal(py::function,double,double,int)`。唯一提及是 `numerical_integration.py:68` 一条**过时报错文案**（真正的 import 在 `:17` 加载 `numerical_core`）→ 删，并顺手改掉那条误导文案。

**精度语义确认**（否定了此前的担心）：
- **不存在**"新引擎走高精度/有理数、`.pyd` 走 double"的整体对立；
- **也不存在** tanh-sinh 替换自适应 Simpson 这类算法替换——三个积分 action 直接调用原 `numerical_core.h` 内核；
- 唯一显著差异是 `optimal_step` **换了公式**：`.pyd` 用旧的 `eps^(1/3)·|f(x)|`（`numerical_core.cpp:65-74`），引擎用高阶导数探针（`numerical_core.h:135-157`）。`f=e^x, x=10` 时两者相差约 **1.1e4 倍**，**方向是引擎更优**。

**一个必须一并处理的留雷点**：`linear_algebra/liner_product.cpp`（注意拼写错误的 `liner_`）的声明与 `inner_product.dll` 的实际 ABI **不兼容**——反汇编 `dot_c`（RVA 0x13F9）确认实际签名是 `(double*, double*, int32)`，而该 `.cpp` 写的是按值 `std::vector<double>`、且没有 `extern "C"`；且 DLL（08-20）早于该 `.cpp`（08-21）。**删除 DLL 时必须同时删掉或修正这份源码**，否则后人照它重建会静默破坏 ctypes 快路径。

#### 5.1.1 删除分批（A 档不必等前置项）

| 档 | 文件 | 前置条件 |
| --- | --- | --- |
| **A 档（可立即删）** | `ode_core.pyd`、`trap.pyd` | 无。两者**全树零调用点**：`ode_solver.py` 完全绕过 `ode_core`（改用纯 numpy），`trap.pyd` 唯一提及是 `numerical_integration.py:68` 一条**过时文案**（真正加载的是 `numerical_core`，顺手改掉该文案） |
| **A 档（可立即删）** | `interpolation_core.pyd`、`matrix_core.pyd`、`numerical_core.pyd`、`optimization_core.pyd` | 无。内核已通过 `*_core.h` 编入 DLL（`interpolation.cpp:10`、`numerical_integration.cpp:9`；`CMakeLists.txt:56-62` 不含任何 `*_core.cpp`），删除不影响 v2.0 构建 |
| **B 档（先补再删）** | `matrix_core.pyd` 的三个迭代解法 | 先补 `iterations`（§5.1 前置修改） |
| **C 档（可删但必须同时改源码）** | `inner_product.dll` | 必须同时删除或改正 `linear_algebra/liner_product.cpp`；另需确认"精确点积"用例归属（§5.1.3） |

⚠️ **A 档有一个牵连**：既有 `numerical_integration.py` 的 5 个算法**没有纯 Python 回退**（缺 `.pyd` 时直接 `return MathObject(error=...)`）。所以删 `numerical_core.pyd` 会让 Python 层的 `trapezoidal_rule` / `simpson_rule` / `gauss_quadrature` / `numerical_derivative` / `optimal_step` 直接失效 —— **必须与"整体退役 Python 层"同步进行，不能单独删**。

#### 5.1.2 迁移必读：调用约定与参数差异

| 差异 | `.pyd` 侧 | 引擎侧 | 影响 |
| --- | --- | --- | --- |
| **被积/右端函数 `f`** | `pybind11::function`（传 **Python 可调用对象 / lambda**） | **表达式字符串**（`signatures.json: f: string`，由 `expr_util.h` 求值） | **任何传 lambda 的调用方都必须改写**。`ode_solver.py:16-22` 的 `_parse_ode_func` 正说明旧层本来就在做"字符串 → lambda"的转换 |
| 插值参数名 | `x_points` / `y_points` | `x` / `y` | 旧调用方需改；可选加别名兼容 |
| `cubic_spline` 的 `bc_type` | 有 `bc_type="natural"`（原实现本就忽略） | 无 | 无算法损失；可选加 `bc_type?` 只接受 natural |
| `gradient_descent` 的 `df` | 可传用户导数，`None` 时中心差分 | **无 `df`，改为符号微分** | 导数来源不同；对不可导函数行为待实测（§5.1.5） |
| `gauss_quad` 的 n 越界 | 返回 `0.0`（静默错误值） | 抛错 | 引擎更严格，是改进 |
| `conjugate_gradient` 的 `pᵀAp<1e-15` | 静默 `break` 返回近似解 | 抛错 | **错误语义不同**：若上游依赖"不抛错"，需在调用侧捕获 |
| `power_method` 初值 | `std::rand()/RAND_MAX`（跨进程不稳定） | Eigen `Random`（确定性） | 对等模最大特征值时收敛结果可能不同 |
| ODE 步数取整 | `(int)((t_end-t0)/h)` **截断** | `ceil(...)` | 例：区间 1、h=0.3 → 旧取 3 步、新取 4 步；引擎是**修正** |
| 迭代次数 | 三个迭代解法返回 `iterations`（Python 用它判收敛） | 当前**被丢弃** | B 档前置项 |

#### 5.1.3 精度与语义差异（含唯一的精度回归点）

**没有**出现"新引擎走高精度/有理数、`.pyd` 走 double"的整体对立 —— 这 6 个 `.pyd` 与引擎对应域**都是 double**；GMP/MPFR/flint 只服务符号与数论侧。**也不存在** tanh-sinh 替换自适应 Simpson：三个积分 action 直接调用 `numerical_core.h` 的复合梯形 / 复合辛普森 / 2–4 点 Gauss-Legendre。

| 项 | 结论 |
| --- | --- |
| `optimal_step` | **唯一实质性精度差异，方向是引擎更优**。旧式 `eps^(1/3)·\|f(x)\|` 被 `f(x)` 放大：`f=e^x, x=10` 时给 0.1，而真值 `h*≈8.73e-6`，**差约 1.1e4 倍** |
| `lagrange` / `newton` / `cubic_spline` / `least_squares` | 引擎调用**同一份内核**（头文件 SHA256 相同）；`least_squares` 引擎还多返回 `r_squared` |
| `trapezoidal` / `simpson` / `gauss_quad` / `derivative` | 同一内核、同一公式；引擎额外校验 `h!=0` 与 method 名（更严格） |
| `ode_core` | 引擎与 **Python 版**对齐（20 次牛顿迭代），`.pyd` 版是预估-校正 → 弃用是改进 |
| **`inner_product`（唯一精度回归点）** | `dot_c`/`norm_c` 是 double 专用；既有实现里**精确/有理/符号向量本来走 sympy 回退**，弃用后引擎只给 double ⇒ 超出 2^53 的整数向量点积不再精确。**需确认上游是否有"精确点积/精确范数"用例**；若有，要么接受 double 化，要么在引擎侧新增精确点积 action |
| `cubic_spline` 的越界写 bug | 源码**已修**（`interpolation_core.h:58-65,81`），但 `.pyd` 二进制（2026-07-28）早于修复（头文件 2026-10-01）→ **该 `.pyd` 很可能仍带 bug**；`tests/accuracy/cases_numerical.py:1073-1080` 记载过这起"越界写 1 个 double + 读未初始化内存"。这只强化弃用结论 |

#### 5.1.4 建议的 action 修改 / 新增（与现有风格一致）

| 类型 | action | 参数 | 返回 | 原因 |
| --- | --- | --- | --- | --- |
| **修改（推荐）** | `jacobi_iteration` | 不变 | 向量 → `{x: number[], iterations: int}` | 补 `.pyd` 的 `iterations` |
| **修改（推荐）** | `gauss_seidel` | 不变 | 同上 | 同上 |
| **修改（推荐）** | `conjugate_gradient` | 不变 | 同上 | 同上 |
| 可选（次选） | `linear_iteration_report` | `{A,b,x0,method,tol?,max_iter?}` | `{x, iterations, residual, converged}` | 若不愿改现有返回形状 |
| 可选（兼容旧调用方） | `cubic_spline` | 加 `bc_type?: "natural"` | 不变 | 旧参数兼容 |
| 可选（兼容旧调用方） | `lagrange_interpolation` / `newton_interpolation` / `least_squares_fit` | 加 `x_points`/`y_points` 别名 | 不变 | 旧 Python 用这两个名 |

#### 5.1.5 三处待实测 / 待确认（审计明确标注"不确定"）

1. **`inner_product.dll` 的真实源码不在树内** —— 已证明现存 `liner_product.cpp` 不可能是它的来源（ABI 不符 + 时间戳），但无法回溯原始实现。
2. **`interpolation_core.pyd` 二进制是否含已修复的 `cubic_spline`** —— 源码已修、二进制更早，无法从二进制确证。
3. **`gradient_descent` 对不可导目标函数（如 `|x|`）的行为** —— 引擎改符号微分后与数值差分必然分歧，**未实测**；P0 期间应补一条实测用例。

### 5.2 准确性套件语言中立化（保住 2180 用例）

- 现在：Python harness + mpmath/sympy/scipy 预言机
- 迁移：**趁 Python 还在**，把每条用例的期望值与容差**冻结成 JSON**（`tests/fixtures/accuracy_cases.json`：`action` / `args` / `expected` / `tolerance` / `note`），预言机脚本与原始输出留档 `docs/oracle-src/`、`fixtures/oracle_raw/`
- 新 runner：`tests/accuracy_runner.cpp`（ctest 目标），只依赖引擎 + 仓库已有 `json.hpp` + 固定容差比较
- 效果：产品树零 Python，仍能一条命令跑完 424 action 覆盖与 2180 用例
- 风险：冻结后期望值不能自动重算 → 新用例需离线重生成（流程写进文档），不进入产品构建

### 5.3 引擎新增能力汇总

- **前置修改（P0，弃用 `.pyd` 所必需）**：3 个迭代解法返回对象补 `iterations`（§5.1）；同时按 §5.1.4 决定是否补 `bc_type?` 与 `x_points/y_points` 兼容别名（旧调用方兼容，可不做）
- **按 §5.1.1 分批删除 `.pyd`**：A 档 6 个文件可立即删，C 档必须与 `liner_product.cpp` 的处置同步
- **确认精确点积归属**：`inner_product` 是唯一精度回归点（§5.1.3），若上游有"精确点积/精确范数"用例，需新增对应的精确 action 或明确接受 double 化
- **把复杂度守卫判据下沉到引擎**：既有的 `math_guard`（运算符计数、嵌套深度、多项式次数、矩阵维度、级数范围、极限振荡检测）用**字符串启发式**实现，阈值在根 `config.json` 的 `math_guard` 段。这类判据必须在 **AST** 上统计才可靠（正则会误判 `\frac`、隐式乘法、多行输入），而解析器已在引擎里。建议新增 action（如 `complexity_report(expr)` 返回各维度指标与是否超阈，阈值仍从配置读，**键名保留**）
- **表达式分类下沉引擎**：既有的 `MF_AI/strategy.recommend()` 用正则猜"等式/导数/积分/极限/矩阵/概率/级数"，脆弱且无人调用；如需"智能推荐操作"，应基于引擎 AST 判断（可作为 `suggest_actions(expr)`）
- 可选 `steps_verify`：批量核验一组等式（给 AI 步骤把关，减少往返）
- 可选 `engine_info`：返回引擎版本、构建时间、依赖版本（供更新器与支持排查复用；现有 `list_functions` 只给 424 的计数）
- 所有新增 action 必须同步进 `tests/fixtures/accuracy_cases.json` 与文档

---

## 6. 宿主侧基础设施（C#）

| 文件 | 作用 | 预估行数 |
| --- | --- | --- |
| `PushChannel.cs`（新） | 推送通道：分片、合并、反压、无宿主降级 | ~150 |
| `AiBridge.cs`（新） | AI 请求/流式/取消/配置/DPAPI 密钥 | ~450 |
| `AccountBridge.cs`（新） | 账户与令牌 | ~250 |
| `SearchBridge.cs`（新） | 在线搜索 + 缓存 | ~200 |
| `StoreBridge.cs`（新） | 历史与工作区 JSON 存储 | ~220 |
| `UpdateBridge.cs`（新） | 版本检查、校验、下载、替换、重启 | ~350 |
| `MFMath.Updater.exe`（新） | 独立更新器（避免自己替换自己） | ~200 |
| `MainWindow.xaml.cs`（改） | 注册新 host object、接入推送通道 | +40 |
| `MFMath.Host.csproj`（改） | 打包 `prompts/`、`tutorials/`、`help/` 资源 | +10 |

**复用而非重写**：`ComponentDownload.cs` 的断点续传（`RangeHeaderValue`）+ SHA-256 校验 + zip 解包 + 进度回调，几乎就是更新器需要的全部下载逻辑。

---

## 7. 自动更新

### 7.1 现状问题

站点 `GET /api/version` 只返回 `{latest, date, download_url, changelog}`（信封 `{code,data,msg}`）——**没有 `sha256`，无法安全更新**。
既有实现的启动检查在 `main_window.py:1146-1169`（硬编码 URL + **字符串比较版本**），且 `APIClient.check_version()` 是重复实现、从未被调用。

### 7.2 站点侧补字段（Next.js，字段级改动）

```json
{ "code": 0, "msg": "success", "data": {
    "latest": "2.0.0",
    "date": "2026-10-01",
    "download_url": "https://mf-vis-science.cn/download/MFMath-Setup.exe",
    "size": 53248000,
    "sha256": "<hex>",
    "changelog": "/changelog",
    "min_supported": "1.5.0",
    "mandatory": false,
    "channel": "stable"
} }
```

### 7.3 桌面端 `UpdateBridge.cs` + `MFMath.Updater.exe`

- 启动后延迟 10s **后台检查**（不阻塞启动；既有实现也是"非阻塞，尊重用户自动更新设置"——`main_window.py:217`）
- 三态设置：只检查 / 自动下载 / 自动安装
- **语义化版本比较**（修正既有的字符串比较缺陷）
- 下载到 `%LOCALAPPDATA%\MFMath\update\`，**断点续传 + `sha256` 必须匹配**才允许安装；校验失败一律丢弃并提示
- 安装：调 Inno Setup 安装包 `/SILENT`，或替换法（**宿主 + 引擎 DLL 作为同一原子单元**一起换）
- 更新器与被更新进程分离（`MFMath.Updater.exe`）
- 二期可选：保留上一版目录，启动失败自动回退

**特别注意**：宿主与引擎 DLL 必须当作**同一个版本单元**发布与校验。历史上出现过"Release 宿主是新的、Debug 仍跑几个月前引擎"的静默降级（这正是 `sync-engine.ps1` 当初要解决的问题）。

---

## 8. 构建与打包（去掉 Python）

| 现有脚本 | 替代方案 |
| --- | --- |
| `scripts/gen_installer_assets.py`、`make_ico.py`、`svg2ico.py` | Node(.mjs)（sharp/svg 库）或 C#（ImageSharp） |
| `scripts/gen_user_manual_docx.py`、`gen_user_manual_html.py`、`gen_copyright_*.py` | 手册走 Markdown → HTML → docx（Node 或 C# Open XML SDK）；版权页同管线 |
| `scripts/capture_all.py`、`take_screenshots.py`、`reshoot.py`、`snap_all.py` | **已有替代**：前端 43 个 CDP 测试脚本（`.mjs`）本就能驱动页面并截图，统一为 `tools/shots.mjs` |
| `scripts/build-installer.ps1`、`verify-installer.ps1`、`make-downloader.ps1` | `tools/build.mjs`（编排 cmake → vite → dotnet → ISCC）或 C# 控制台工具；保留原有退出码与"体检"语义 |
| `MF-Mathematics.spec`、`Multifunctional-Mathematics.spec`、`math_http_service.spec` | **删除**（PyInstaller 不再需要） |
| `scripts/installer.iss` | **保留**（Inno Setup 声明式配置；严格模式可改 WiX/MSIX） |
| `MF_Mathematics/tools/sync-engine.ps1` | 改写为 `tools/sync-engine.mjs`（逻辑不变：纯消费方覆盖、派生副本只报告，退出码供 CI 用） |

---

## 9. 分阶段实施与验收

| 阶段 | 内容 | 产出 | 验收 |
| --- | --- | --- | --- |
| **P0** | 推送通道；引擎补 `iterations`；准确性套件冻结；按 §5.1.1 分批删除 `.pyd` | `PushChannel.cs`；`numerical_api.cpp` 3 处修改；`accuracy_cases.json` + `accuracy_runner.cpp` | 2180 用例在 C++ runner 下全绿；A 档 6 个 `.pyd` 删除后 v2.0 仍正常构建；`gradient_descent` 不可导用例（`\|x\|`）行为已实测记录 |
| **P1** | 设置 / 历史 / 搜索（三个死按钮）+ 工作区保存 | `StoreBridge`、`SearchBridge`、`SettingsPanel.vue`、`SearchPanel.vue`、`HistoryPanel.vue`、工作区读写 | 顶栏三入口全部可用；工作区跨重启保留且恢复失败会报错；历史可导出 |
| **P2** | 用户系统（纯客户端） | `AccountBridge` + 登录/注册/账户面板 | 与站点 7 个端点联调通过（**注意 form/JSON 两种编码**）；令牌 DPAPI 加密；离线不崩 |
| **P3** | AI 助手 + 查看步骤（含核验回环与提示词改写） | `AiBridge` + `AiPanel`/`StepPanel` + `prompts/` | 20 题抽检：步骤式子全部经引擎核验；七种异常不崩；结果区恒等于引擎值；本地步骤优先显示 |
| **P4** | 教程 18 课（重做引导层）+ 欢迎窗 + 帮助 + 示例库 + 符号键盘 | `TourEngine`/`TourOverlay` + tutorials JSON + `SymbolPad.vue` | 18 课全通且**无静默跳过**；CDP 断言高亮精度；键盘全部插 LaTeX 且对 MathField 生效 |
| **P5** | 自动更新（站点补字段 + 更新器） | `/api/version` 扩展；`UpdateBridge` + `MFMath.Updater` | 篡改 sha256 必须拒绝安装；断点续传生效 |
| **P6** | 打包链去 Python + 其余引擎补齐（`complexity_report` 等） | `tools/build.mjs`；安装包 | 空机器一条命令出安装包；装后首启跑通教程与 AI 配置向导 |

**依赖**：P0 是一切地基（AI / 更新 / 组件都吃推送通道）；P1 与 P2 可并行；P5 需站点侧配合一个字段级改动。
**工作量粗估**（一人含自测）：P0 ≈ 3–4 天（覆盖审计已完成，只剩实现）、P1 ≈ 4（多了工作区）、P2 ≈ 3、P3 ≈ 6–8、P4 ≈ 6（引导层要重做）、P5 ≈ 4、P6 ≈ 4 → **合计约 5–6 周**，风险集中在 P0 与 P3。

---

## 10. 风险与对策

| 风险 | 对策 |
| --- | --- |
| **AI 越权计算**（最大风险，直接违反硬约束；既有实现就是这么做的） | "引擎先算 + 步骤回核验"硬流程；改写三段提示词；AI 文本不得写入结果区；CDP 断言"结果区恒等于引擎值" |
| 照抄既有教程引导层 → 把"静默跳过"一起搬过来 | 明确禁止静默跳过；先核对 22 个失效目标名，逐个决定"补 `data-tour`"或"删该步"；完成判定必须走完全程 |
| 弃用 `.pyd` 时漏掉返回值语义 | 补 `iterations` 是**唯一**前置项（已定位到行号）；`dot_c/norm_c` 精度差异记录在案；删 DLL 时同步处理 `liner_product.cpp` 的 ABI 谎报 |
| 准确性套件冻结后无法自主扩展 | 保留预言机源码与原始输出；新用例离线重生成，流程入文档 |
| 更新后宿主与引擎版本错配（历史上真发生过） | 两者绑成同一版本号，更新器按原子单元校验与替换 |
| 推送通道打满 / 丢事件 | `seq` + 缓冲上限 + `overflow` 标记 + `done` 只认一次；AI 分片 40ms 合并 |
| 工作区/历史文件损坏或跨版本不兼容 | 都带 `version` 字段；解析失败时**报错并保留原文件**（不覆盖），提供"导出诊断包" |
| 密钥与令牌泄露 | 一律 DPAPI；日志与错误信息过滤；提供"禁用 AI"开关；明确告知传输内容；`.env` 保持被 git 忽略 |
| 兼容点写错（用户系统 form/JSON 混用、`detail` 字段） | 按 §4.1 表格逐条实现并写集成测试对着真实站点跑 |
| 约束边界争议 | 见 §0.4（控制台 Python、Node 构建、Inno Setup、AI 语义、gating、配额） |

---

## 11. 明确不做 / 推迟

- **不重建后端**：用户系统、组件清单、版本检测全部复用站点端点
- **不重写下载能力**：直接复用 `ComponentDownload.cs`（断点续传 + sha256 + 解包）
- **不复用已废弃的 HTTP 层**：`math_http_service.py` 与那套 `{code,data.result,msg}` 生成客户端（契约冲突，且 v2.0 走 P/Invoke）
- **不移植死代码**：`MF_AI/agent.py`、`strategy.recommend`、`models.ChatRequest/ChatResponse` 等（§2.10）
- **不照抄既有的引导层与外层壳**：教程引导、遮罩交互、步骤展示、工作区保存全部重做（§3）
- **不动已完成的迁移**：22 个模式视图、10 套配色外观系统、控制台、组件安装均已就绪
- **不迁移旧 JS UI（`MFMath.UI`）**：仅作历史回退目标，确认不再需要可删除
- **推迟**：更新回滚（二期）、AI 多模态、教程录制回放、离线文档全文搜索
