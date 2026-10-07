# AI 面板：页面直连、SSE 分帧、步骤视图、密钥放哪

> **本文只回答一个问题：AI 面板是怎么做的 —— 页面直连、SSE 分帧、步骤视图、密钥放哪。**
>
> 与同层其它文档的分工：
> - [`ARCHITECTURE.md`](ARCHITECTURE.md) —— Vue 壳的分层、路由与导航（本文不重复）；
> - [`ENGINE-BINDING.md`](ENGINE-BINDING.md) —— `ENGINE_MAP` / `engineCall` 的绑定与可达性守门（AI 工具只用到它的一小层）；
> - [`SETTINGS-WORKSPACE.md`](SETTINGS-WORKSPACE.md) —— 设置读写与导入导出的通用机制（本文只写 `ai.json` 与凭据剥离）；
> - [`CHECKS.md`](CHECKS.md) —— 四道构建闸门与"守卫必须验证过会失败"的规矩；
> - [`../link/CREDENTIALS.md`](../link/CREDENTIALS.md) —— 凭据边界总账（本文只写 AI 这一条，代价对照 §2.1）。

**本文口径**：以代码为准。所有数字都由本文 §11 的命令跑出来，未复跑的一律标注"未证实"。文档债集中写在 §12。

---

## 1. 这一层的规模与文件角色

`src/lib/ai/` 下共 **9 个文件**，其中 **8 个是代码**（`engine-signatures.json` 是数据）：

| 文件 | 行数（非空 / 含空行） | 职责 | 权威行 |
| --- | --- | --- | --- |
| [`bridge.js`](../../MF_UI/MFMath.UI.Vue/src/lib/ai/bridge.js) | 944 / 1036 | 配置读写、脱敏视图、消息组装、会话落盘、工具循环编排 | `DEFAULT_CFG` bridge.js:57-82；`sendTurn` bridge.js:709-940 |
| [`client.ts`](../../MF_UI/MFMath.UI.Vue/src/lib/ai/client.ts) | 336 / 369 | OpenAI 兼容端点的**分片语义**（chrome 形状 → 事件） | `stream` client.ts:54-255 |
| [`collect.ts`](../../MF_UI/MFMath.UI.Vue/src/lib/ai/collect.ts) | 111 / 121 | 阻塞式消费者 + 工具参数碎片拼接收尾 | `collect` collect.ts:42-103 |
| [`engine-signatures.json`](../../MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json) | 5905 / 5905 | 424 个 action 的参数表（AI 工具目录的权威源，94.5 KB） | 见 §11 ② |
| [`markdown.ts`](../../MF_UI/MFMath.UI.Vue/src/lib/ai/markdown.ts) | 207 / 236 | 受限 markdown → **token 树**（不产 HTML 字符串） | `parseInline` markdown.ts:58；`parseMarkdown` markdown.ts:150 |
| [`relay.ts`](../../MF_UI/MFMath.UI.Vue/src/lib/ai/relay.ts) | 226 / 252 | 运输层：页面自己 `fetch`、地址闸门、取消与超时分类 | `joinBasePath` relay.ts:87-108；`relayPost` relay.ts:135-220 |
| [`sse.ts`](../../MF_UI/MFMath.UI.Vue/src/lib/ai/sse.ts) | 80 / 92 | **唯一一份 SSE 分帧实现** | `parseSSE` sse.ts:65-92 |
| [`tools.ts`](../../MF_UI/MFMath.UI.Vue/src/lib/ai/tools.ts) | 351 / 387 | 两个工具的 schema、参数校验、执行（只走引擎桥） | `AI_TOOLS` tools.ts:183-214；`executeTool` tools.ts:233-333 |
| [`types.ts`](../../MF_UI/MFMath.UI.Vue/src/lib/ai/types.ts) | 117 / 129 | 模型层契约：请求进、事件流出 | `ModelEvent` types.ts:105-125 |

8 个代码文件合计 **2,372 非空行 / 2,622 含空行**（命令见 §11 ①）。这与 [`../DECISIONS.md`](../DECISIONS.md) D-004 记的"8 个文件 / 2,372 行"**一致**（D-004 用的是非空行口径）。

---

## 2. AI 不是宿主对象

这一条是 D-004 的核心，也是读这一层时最容易按旧印象理解错的地方。

| 事实 | 证据 |
| --- | --- |
| 宿主只注册 **9 个**对象：`mf` `sys` `diag` `win` `push` `update` `account` `search` `con`，**没有 `ai`** | `MFMath.Host.Rust/src/main.rs:207-215` |
| 宿主里不存在任何 `ai.*` 推送话题 | 命令 §11 ④ 返回 0 匹配 |
| DPAPI 调用点只剩三处，`ai` 不在其中（出现 `ai.rs` 即回退） | 命令 §11 ⑤；[`../link/CREDENTIALS.md`](../link/CREDENTIALS.md) §5 的判据 |
| 请求由**页面**发：`relayPost` 里是 `fetch(url, {method:'POST', headers:{Authorization:'Bearer '+creds.apiKey}})` | relay.ts:177-190 |
| 页面自己读原始字节：`resp.body.getReader()`，**不做任何分帧**，原样 yield | relay.ts:196-217 |
| 分帧只在 TS 里做一份：`parseSSE` 被 `client.ts` 直接消费 | sse.ts:65-92；client.ts:108 |
| 密钥与配置走的是**另一个**桥 `sys`（`StoreRead` / `StoreWrite`），与 AI 无关 | bridge.js:39-45、bridge.js:99-139 |

**"就绪"的语义已经变了**：不再是"宿主提供了 `ai` 桥"，而是"**配置齐备**"——
能读到设置文件 + 开关打开 + 有明文密钥 + 端点合法（bridge.js:230-234；
relay.ts:116-118 的 `isRelayHosted()` 同样只看 `creds.apiKey` 与 `isUsableBaseUrl(creds.baseUrl)`）。

用例在三处反向钉住这件事：无密钥时不得自称就绪（`tests/cdp-ai.mjs:167`）、
push log 里不得出现任何 `ai.*` 话题（`tests/cdp-ai.mjs:280-284`）、
请求必须带 `Origin` 头且等于页面 origin（`tests/cdp-ai.mjs:677-681`——
旧架构里那个宿主侧 HttpClient 不会带这个头）。

副作用（是收益，不是代价）：请求只活在页面里，刷新页面 = 连接一起消失，
不会再出现"界面停在正在输出、其实宿主早跑完了"（bridge.js:186-189）。

---

## 3. 一次发送的完整路径

| 步 | 做什么 | 位置 |
| --- | --- | --- |
| ① | 面板取草稿、清空输入框、调 `sendTurn` | AiPanel.vue:100-110 |
| ② | 前置校验：启用 / 有密钥 / 没有在跑 / 端点合法 / 运输层就绪。**每条早退都写 `aiState.error`** | bridge.js:709-722、`failTurn` bridge.js:704-707 |
| ③ | 组装 messages（系统提示 + 现场上下文 + 历史 + 本轮问题） | `buildMessages` bridge.js:564-590 |
| ④ | 用户那条**先入会话**（失败也能看到自己说过什么），再重置 `aiState` | bridge.js:729-735 |
| ⑤ | 每轮新建 `AbortController`，并把 `{baseUrl, apiKey, timeoutSec}` 推给运输层 | bridge.js:737-746 |
| ⑥ | `client.stream()` → `relayPost` → `fetch`；响应字节 → `parseSSE` → 分片解析 → `ModelEvent` | client.ts:54-255 |
| ⑦ | 增量经 `collect({onEvent})` 写进 `aiState.stream/reasoning/usage/notices` | bridge.js:762-808；collect.ts:42-103 |
| ⑧ | 收尾（**先验归属**）：并入会话、清空实时缓冲、落盘 | bridge.js:891-937 |

两处容易读漏的设计：

- **`onEvent` 是"旁观"而不是第二套累积**：`collect` 既给出完整结果（落会话），
  又在每个事件上回调（推界面），所以界面与记录不会算出两个不同的答案（collect.ts:31-40）。
- **轮次有归属**：`currentTurn = {id, ctrl}`，所有收尾都先验 `currentTurn?.id !== myTurn`
  （bridge.js:671-673、bridge.js:900、bridge.js:921、bridge.js:936）。
  这是为修掉"旧轮把新轮正在流式的正文清空、把半截回答当新消息插进历史"那个竞态
  （bridge.js:658-670 的注释记着三种症状；`stopTurn` 也因此**不**同步把 `running` 置 false，
  bridge.js:942-952）。

---

## 4. SSE 分帧：一个 chunk 不等于一个事件

| 规矩 | 实现 | 位置 |
| --- | --- | --- |
| 必须自己维护缓冲、跨 chunk 保住余量；直接对每个 chunk 做 `JSON.parse` 是最常见的崩法 | 缓冲区 + `indexOf('\n\n')` 循环切块 | sse.ts:71-83 |
| 行尾三种都要收，且要处理"\r 在 chunk 末尾、\n 在下一个 chunk 开头" | 末尾孤立 `\r` 原样保留，等下个 chunk | sse.ts:26-32 |
| 以冒号开头的是注释（心跳），跳过 | sse.ts:42 |
| 冒号后**最多去掉一个空格**；多行 `data` 用 `\n` 连接 | sse.ts:47-56 |
| 末尾没有空行收尾时，最后一个事件仍要发出去 | sse.ts:86-91 |
| 分帧层**不接收 AbortSignal**：底层 body 被 abort 时会自己抛错 | sse.ts:59-64 |

**OpenAI 分片语义在 `client.ts`，也只有一份**（client.ts:1-21 声明；逐条实现如下）：

| 线上形状 | 处理 | 位置 |
| --- | --- | --- |
| `data: [DONE]` | 终止标记，不是 JSON | client.ts:116-119 |
| 单条 `data` 不是 JSON | 降级为 `bad_sse_data` notice，**不算失败**，继续读 | client.ts:121-130 |
| `chunk.usage` 尾包（`choices` 是空数组） | 必须在取 `choice` **之前**处理 | client.ts:151-161 |
| `delta.reasoning_content ?? delta.reasoning` | 思维链，两种端点写法都收 | client.ts:168-172 |
| `delta.content` | 正文增量 | client.ts:174-176 |
| `delta.tool_calls` 碎片（按 `index`） | 原样吐出 `argsJsonDelta`，**不在这里解析** | client.ts:178-189 |
| `choice.finish_reason` | 归一成 `stop` / `tool_calls` / `length` / `unknown` | client.ts:191-194、client.ts:329-341 |
| HTTP 非 2xx | 读干错误体，作为 `kind:'http'` + 状态码 | client.ts:77-90 |
| **HTTP 200 + JSON 错误体** | 零事件 + 无 `[DONE]` ⇒ 报 `protocol` 错误并附原文开头 4096 字节 | client.ts:96-106、client.ts:219-233 |
| 200 下的 `data: {"error":{…}}` 分片 | 作为 `kind:'http'` 错误抛出，**不再被 `if (!choice) continue` 吞掉** | client.ts:134-149 |
| 流正常结束但没 usage / 没 `[DONE]` 也没 `finish_reason` | 各发一条 notice（`missing_usage` / `truncated_stream`），**是可观测的降级** | client.ts:236-253 |

**失败分类**（风格规矩 ⑤：不许含糊）：运输层先把"谁取消的"分好类，
`classify()` 只产出 `timeout` / `aborted` / `network` 三种（relay.ts:168-173），
`client.ts` 再把取消与超时当**正常终止**（`done`，reason 分别是 `aborted` / `timeout`），
其余才是 `error`（client.ts:196-213）。用例按这个分类逐条断言：
401/500 → `kind:"http"`；坏 SSE → notice；无 usage → notice；无 `[DONE]` → notice；
断流 → `kind:"network"`；连不上 → `kind:"network"`；挂起 → `doneReason:"timeout"`
（`tests/cdp-ai.mjs:616-642`）。

**取消的语义要如实说**：`relayCancelAll()` / `abort` 是"**停止等待**"，
不是"撤回请求"——请求早已到服务商那边，该计费的照旧计费（relay.ts:222-232、bridge.js:942-946）。

---

## 5. 密钥放哪：`ai.json` 的 `apiKey`，明文

| 事实 | 位置 |
| --- | --- |
| 存储：`%LOCALAPPDATA%\MFMath\settings\ai.json` 的 `apiKey` 字段，**没有加密** | bridge.js:8-11；路径由 `sys.Info().settingsDir` 拼出 bridge.js:143-153 |
| 读写走 `sys.StoreRead` / `sys.StoreWrite`；无宿主时明确报"读不到设置文件" | bridge.js:99-139、bridge.js:102 |
| 保存：明文写入，并**顺手删掉旧版 `apiKeyProtected`**（免得两把钥匙打架） | `aiSetKey` bridge.js:278-294 |
| 明文密钥**只活在模块作用域**（`let aiKey`），绝不进 `aiConfig` | bridge.js:89-90、bridge.js:211-215 |
| 脱敏视图 `aiConfig` 删掉 `apiKey` 与 `apiKeyProtected` 两个字段 | bridge.js:211-215；断言 `tests/cdp-ai.mjs:194-196` |
| 旧版 DPAPI 密文**页面侧解不开**：只剩密文时 `hasKey=false` + 提示"重填一次" | bridge.js:197-206；用例 `tests/cdp-ai.mjs:832-847` |
| 界面文案必须如实说明"明文、没有加密"，不许暗示受保护 | AiGroup.vue:180-201；用例 `tests/cdp-ai.mjs:766-772` |

### 代价（照 [`../link/CREDENTIALS.md`](../link/CREDENTIALS.md) §2.1，逐条给代码出处）

| 代价 | 具体含义 | 出处 |
| --- | --- | --- |
| ① 明文落盘 | 换用户、拷贝文件、看备份都能直接读到 | bridge.js:278-294 |
| ② 密钥常驻页面内存 | 每次请求都要拼 `Authorization`，所以**会话期间一直在渲染进程里**，不只是录入那一瞬 | bridge.js:90、relay.ts:182 |
| ③ 旧密文解不开 | 老用户的 `apiKeyProtected` 页面侧没有 DPAPI 可调 ⇒ 如实要求重填，且**不假装有密钥** | bridge.js:197-206 |
| ④ `baseUrl` 成了新的安全边界 | 旧架构"宿主只接受相对路径"那条属性随中继一起消失；闸门挪到 §6 | relay.ts:14-21；[`../DECISIONS.md`](../DECISIONS.md) D-004 |
| ⑤ 兼容面未证实 | 只实测过 DeepSeek 与 GitHub，**不能**说"所有服务商都能直连"（企业代理、按域白名单的服务商仍可能不行） | [`../link/CREDENTIALS.md`](../link/CREDENTIALS.md) §2.1 第 5 条 |
| ⑥ `.bak` 残留 | `StoreWrite` 覆盖前会复制 `<name>.json.bak`，而 `StoreDelete` **只删 `.json`** ⇒ `ai.json.bak` 里可能留着明文密钥，且界面上看不到（`StoreList` 只列 `.json`） | `MFMath.Host.Rust/src/sys.rs:210`、`sys.rs:222-232`；[`../link/CREDENTIALS.md`](../link/CREDENTIALS.md) §2.3（待修） |

跨宿主可移植性：`ai.json` 的密钥**不跟着用户走**——C# 写的是 `apiKeyProtected`（DPAPI 密文），
Rust/TS 读的是 `apiKey`（明文），两种形式互不通用（[`../link/CREDENTIALS.md`](../link/CREDENTIALS.md) §3）。
这是架构变更的直接后果，不是 bug。

---

## 6. 闸门一：端点合法性（`relay.ts`）

**核心禁令：绝不做"地址不认识就退回内置站点"的规范化。**
理由写在 relay.ts:14-17：baseUrl 是用户自己填的，悄悄换成内置站点等于**把用户的密钥发到我们的服务器上**，
那是隐私事故，不是一次降级。

| 规则 | 实现 | 位置 |
| --- | --- | --- |
| 只接受 **http/https 绝对地址**，且 hostname 非空；空地址返回 false | `isUsableBaseUrl` | relay.ts:67-77 |
| 路径必须以**单个 `/`** 开头（相对路径），否则一段注入的绝对地址就成了端点 | `joinBasePath` | relay.ts:93-94 |
| 路径里不允许空白或控制字符 | 同上 | relay.ts:95 |
| 拼接结果必须与 `baseUrl` **同源**（`//host` 一类不能改写站点） | `new URL(joined).origin !== new URL(base).origin` 即抛错 | relay.ts:97-107 |
| 违反以上任一条 ⇒ 抛 `RelayError('config', …)`，**不退回内置站点** | | relay.ts:89-107 |
| 配置规范化**只在 baseUrl 为空时**套内置默认值；"填了但不认识"的**原样保留**去报错 | `normalizeConfig` | bridge.js:161-170 |
| 发送前先本地拦：不合法直接 `failTurn`，**一个请求都不出去** | `sendTurn` | bridge.js:717-720；用例 `tests/cdp-ai.mjs:245-249` |
| 自检 4 项之一"端点不退回内置站点"：验拼接相等 + 非 http/https 报错 + 不认识的地址报错 | `aiSelfCheck` | bridge.js:347-364 |
| 纯函数暴露给断言（这两条不能只看行为，行为要联网才看得见） | `window.__mfAi.relay` | bridge.js:1023-1025；用例 `tests/cdp-ai.mjs:211-231` |

行为层的两条硬断言：`ftp://…` 与空地址都必须在**本地**报错，且错误信息里不得出现内置站点域名
（`tests/cdp-ai.mjs:227-231`）；非法端点下发送被拒且假端点**收到 0 个新请求**
（`tests/cdp-ai.mjs:242-249`）。

> 一条如实说明：`isUsableBaseUrl` 只做**格式**校验，不做可达性/白名单校验
> ——"用户把端点填成攻击者地址"这件事在这一层是**被允许的**，因为端点本来就是用户自己的配置项。

---

## 7. 闸门二：导出与诊断剥掉密钥

**双保险，且是可见的**（剥了什么会写进包里）：

| 位置 | 做法 | 出处 |
| --- | --- | --- |
| 前端导出：**整份排除** `ai` / `account` / `search`，并把名字写进 `excluded` | `CREDENTIAL_FILES` | `src/lib/settings/io.js:31`、`io.js:90`、`io.js:114` |
| 前端导出：其余文件里再按字段名剥一遍（`protected` / `password` / `passwd` / `secret` / `token` / `api[-_]?key`），并记录 `stripped` | `SECRET_FIELD` + `stripSecrets` | `io.js:34`、`io.js:122-131` |
| 导入侧同样**不写**这三类文件（否则会静默覆盖用户现在的密钥） | `applyBundle` | `io.js:152-160` |
| 宿主诊断包：`CREDENTIAL_STEMS = ["ai","account","search"]`，**外加**"文件名含 `secret`"的兜底 | | `MFMath.Host.Rust/src/sys.rs:282`、`sys.rs:291-297` |

`SECRET_FIELD` 确实命中了 `apiKey`：`api[-_]?key` 在忽略大小写下匹配它（io.js:9-12 说明了这一点）。

> 这里记着那个真实的坑（`sys.rs:278-281` 的注释）：宿主原先**只按"文件名含 secret"跳**，
> 而 `ai.json` / `account.json` / `search.json` **一个都不含 `secret`** —— 等于没跳。
> **"过滤规则写对了"与"过滤规则真的命中"是两件事。**

复查命令与判据见 [`../link/CREDENTIALS.md`](../link/CREDENTIALS.md) §5 ③。

---

## 8. 硬约束：AI 不得成为计算源

这是整条功能线的红线（[`../DECISIONS.md`](../DECISIONS.md) D-002 的落地）。

| 机制 | 实现 | 位置 |
| --- | --- | --- |
| 系统提示里写死"所有计算由 C++ 引擎完成，你只做解释"、"不要自行给一个可能出错的数值" | `SYSTEM_PROMPT` | bridge.js:529-536 |
| 工具**只暴露两个**（不是 424 个）：`engine_find` 找函数、`engine_call` 调函数 | `AI_TOOLS` | tools.ts:183-214；用例 `tests/cdp-ai.mjs:410-411` |
| 目录以**引擎签名表**为权威（424 条），不再从 `ENGINE_MAP` 反推（反推只有 371/424 可达，且漏掉全部 `expr_eval` 家族） | `CATALOG`、`ENGINE_FN_COUNT` | tools.ts:45-117 |
| 工具**只能走 `engineCall`**（`mf.Dispatch`），绝不碰 `win`/`sys`/`con` 那些桥 | tools.ts:11-12、tools.ts:310；`src/lib/bridge.js:127-131` | 越权用例：`SaveTextFile` 被拒 `tests/cdp-ai.mjs:405-418` |
| 表外的函数名一律拒绝，并回最接近的候选 | tools.ts:269-280 | 用例 `tests/cdp-ai.mjs:414` |
| 参数按动作表校验：缺必填 / 写错参数名 ⇒ 回"缺什么、多了什么 + 正确签名" | `validateArgs` tools.ts:155-172 | 用例 `tests/cdp-ai.mjs:415-417` |
| 隐私闸门：`sendResult` 关着时**拒绝**工具调用（结果要回传给模型 = 把引擎结果发出去） | tools.ts:300-308 | 用例 `tests/cdp-ai.mjs:420-421`、`tests/cdp-ai.mjs:485-493` |
| 结果回给模型前截断到 3000 字符（界面仍显示完整值） | `MAX_CONTENT` tools.ts:220-225 | StepViewer.vue:37-42 |
| 轮次上限 **4**（`MAX_TOOL_ROUNDS`），到顶如实说明而不是继续烧 | bridge.js:685、bridge.js:818-828 | 用例 `tests/cdp-ai.mjs:480-483` |
| 单轮工具调用上限 **8**（`MAX_TOOL_CALLS_PER_ROUND`）：超限的不执行，但**每个都要回一条结果**，否则下一轮请求会被端点拒 | bridge.js:686-694、bridge.js:838-883 | — |
| 漂移检测：把静态表与**运行中的引擎**核对，返回缺失/多余两组名字 | `verifyEngineTable` tools.ts:342-365 | — |

### 红线用例：假端点故意回 `1+1=3`

假端点对默认请求回的就是错的等式（`tests/fake-ai-server.mjs:350`）。
用例先在计算页按键算出引擎值当基准，再让 AI 回答，最后断言**结果区没有被改写**：

| 断言行 | 断言 |
| --- | --- |
| `tests/cdp-ai.mjs:717` | "引擎算出 1+1=2（作为对照基准）" —— `engineVal === "2"` |
| `tests/cdp-ai.mjs:725` | "AI 回复里确实出现了那个错的等式（否则这条断言没有意义）" —— `aiText.includes("1+1=3")` |
| `tests/cdp-ai.mjs:727-728` | "AI 回复**没有**改写结果区（结果仍是引擎的值 2）" —— `afterVal === engineVal && afterVal === "2"` |

同一族还有一条：工具块显示的必须是引擎的值，而模型那句错的数字只是文本
（`tests/cdp-ai.mjs:456-457`），以及步骤视图里的值不得出现模型那句 99
（`tests/cdp-ai.mjs:525-526`）。

---

## 9. 步骤视图的语义：步骤 = AI 调引擎的记录

**这是本文最要紧的一句**：StepViewer 渲染的**不是"模型写的步骤"**，而是这一轮里
`engine_call` 的调用记录 —— 模型提出要算什么，数值由引擎给出，所以每一步天然可核对
（StepViewer.vue:5-10）。

为什么必须这样：引擎信封里**没有 `steps` 字段**（CalcView.vue:405 记着"已核对 `api.cpp` 与全部 `*_api.cpp`"），
"从引擎直接拿步骤"做不到；让模型自己编步骤就是**伪造推导**，直接违反硬约束。

| 呈现 | 内容 | 位置 |
| --- | --- | --- |
| AI 面板里的工具块 | 引擎徽标 + 函数名 + 参数 + 结果 + 耗时 | AiPanel.vue:214-234 |
| 「查看步骤」→ StepViewer | 编号步骤（第 N 步 · 函数 · 参数 · **完整结果** · 状态） | StepViewer.vue:45-94 |

两条显示纪律：**完整结果**（给人看的 value 不截断，工具块里给模型的才是截断版，
StepViewer.vue:37-42）与**失败保留**（`!s.ok` 标红并留在列表里，不隐藏、不假装成功，
StepViewer.vue:66-79；用例 `tests/cdp-ai.mjs:472-473`）。

两条入口：

| 入口 | 通路 |
| --- | --- |
| ① 面板里任何带引擎步骤的回答 → 「查看步骤（N）」按钮 | AiPanel.vue:229-233 → `openSteps` AiPanel.vue:64-67 |
| ② 计算页结果对话框的「查看步骤」 | CalcView.vue:412-429 `requestAiTurn(prompt, {autoSteps:true})` → `bridge.js:978-983` → App 打开面板（`src/App.vue:258`）→ 面板取走请求并自动发送（AiPanel.vue:75-81）→ 收尾后若这一轮带步骤则自动弹层（bridge.js:913-916 → AiPanel.vue:83-88） |

**为什么 ② 不直接从引擎拿步骤**：见上；它的 prompt 明确要求"每一步都要用 `engine_call`
让本地引擎算出数值（不要自己心算）"（CalcView.vue:418）。
用例覆盖了这条通路确实接上（不是死按钮）：`tests/cdp-ai.mjs:546-574`。

---

## 10. 面板与渲染（与 5 个兄弟文档的边界之外，这里只列与 AI 有关的点）

| 决定 | 做法 | 位置 |
| --- | --- | --- |
| 右侧**非模态抽屉**（`position: fixed`，自占 420px，不放全屏遮罩） | | AiPanel.vue:322-335；用例 `tests/cdp-ai.mjs:801-802` |
| 未就绪时**把原因和去处说出来**，而不是给一个点不动的输入框 | | AiPanel.vue:186-197 |
| 模型输出是不可信输入：**全程没有 `v-html`、没有拼 HTML 字符串** | markdown token 树 + 模板插值 | markdown.ts:4-8、AiInline.vue:5-8；用例 `tests/cdp-ai.mjs:379-381` |
| 不引 marked + DOMPurify 的理由：结构上不存在注入面，就不用赌净化器写对了 | | markdown.ts:4-8 |
| 链接只放行 `http/https/mailto`，其余标 unsafe**不生成 `<a>`**；点击是复制而不是导航 | | markdown.ts:34-37、AiInline.vue:26-33；用例 `tests/cdp-ai.mjs:377-378` |
| 不渲染 `<img>`：模型输出不该触发对任意远端地址的请求 | 图片降级成 `[图片：label]` + 代码 | markdown.ts:82-85；用例 `tests/cdp-ai.mjs:379-380` |
| `$...$` 里不像公式就当**占位符文本**（"行内 `$...$`"照字面显示） | `MATHISH` | markdown.ts:17-18、markdown.ts:75-77；用例 `tests/cdp-ai.mjs:331-332` |
| 流式正文节流 ~80ms：直接渲染会每增量重解析全文 + 重渲 KaTeX，长回答是 O(n²) | `streamShown` | AiPanel.vue:38-55 |
| 会话落盘只落**最终消息**，不落增量；思考过程跟消息走且有上限 8000 字 | `MAX_MESSAGES=40` / `MAX_REASONING` | bridge.js:464-499 |
| 自检、连通性测试都**不联网**（测试连接才发一条 `stream:false` + `max_tokens:1` 的 ping） | | `aiSelfCheck` bridge.js:308-367、`aiTest` bridge.js:373-439；用例 `tests/cdp-ai.mjs:735-743`、`tests/cdp-ai.mjs:749-759` |

设置分组 `设置 → AI` 共 **11 个 `data-setting="ai.*"` 小节**（命令 §11 ⑥）：
`enabled` / `baseUrl` / `model` / `modelParams` / `apiKey` / `context` / `tools` / `privacy` / `test` / `selftest` / `chat`
（AiGroup.vue:106-323）。provider 不做注册表，就是三个预设按钮
（DeepSeek / OpenAI / Ollama，AiGroup.vue:60-69）。

---

## 11. 复跑命令

在仓库根目录执行：

```powershell
# ① ai/ 代码规模（8 个代码文件，排除 engine-signatures.json）—— 期望 2372（非空行口径）
Get-ChildItem MF_UI\MFMath.UI.Vue\src\lib\ai -File | Where-Object { $_.Extension -ne ".json" } |
  ForEach-Object { (Get-Content $_.FullName | Measure-Object -Line).Lines } | Measure-Object -Sum

# ② 引擎签名表键数（AI 工具目录的权威源）—— 期望 424
((Get-Content MF_UI\MFMath.UI.Vue\src\lib\ai\engine-signatures.json -Raw | ConvertFrom-Json).PSObject.Properties |
  Measure-Object).Count

# ③ 用例的静态断言点 —— 期望 151（展开后 160，见下）
(Select-String -Path MF_UI\MFMath.UI.Vue\tests\cdp-ai.mjs -Pattern '^\s*check\(' -AllMatches).Count

# ④ 宿主里不该有 ai.* 推送话题 —— 期望 0
(Select-String -Path MFMath.Host.Rust\src\*.rs -Pattern '"ai\.' -AllMatches).Count

# ⑤ DPAPI 调用点只该有三处文件（出现 ai.rs 即回退）
Select-String -Path MFMath.Host.Rust\src\*.rs -Pattern 'dpapi::(protect|unprotect)' |
  ForEach-Object { $_.Filename } | Sort-Object -Unique

# ⑥ 设置页 AI 分组的小节 id —— 期望 11 个不同值
Select-String -Path MF_UI\MFMath.UI.Vue\src\components\settings\AiGroup.vue `
  -Pattern 'data-setting="(ai\.[a-zA-Z.]+)"' -AllMatches |
  ForEach-Object { $_.Matches } | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
```

端到端用例（**需要宿主带 `--remote-debugging-port=9222` 启动**，本套件自己拉起假端点，
不需要网络也不需要真 key）：

```powershell
node MF_UI\MFMath.UI.Vue\tests\cdp-ai.mjs     # 用法见该文件第 19 行
```

| 数字 | 值 | 状态 |
| --- | --- | --- |
| 静态 `check(` 调用点 | **151** | 本次实测（命令 ③） |
| 展开后的断言条数 | **160** | 推导：151 − 3（两处循环体里的静态点）+ 6×1 + 3×2 = 160；与 D-004 记的"曾实测 **160/0**"吻合。**本次未复跑用例**（需要宿主与 CDP 端口独占，见 [`../../AGENTS.md`](../../AGENTS.md) §4） |
| `probe_call.exe list_functions` 的 `count` | 424 | 未在本文复跑；判据见 [`../DECISIONS.md`](../DECISIONS.md) D-003 与 [`../README.md`](../README.md) |

---

## 12. 已知的文档债

以代码为准；下表都是"注释/旧文档说 X，代码做 Y"的实例，未修改任何源文件。

| # | 位置 | 说 | 实际做 |
| --- | --- | --- | --- |
| 1 | `src/lib/ai/types.ts:41`、`types.ts:109-113` | `ToolSchema` 注释"形状先定死，本版不实现工具循环"；`tool_call_delta` 注释"本版（对话 + 解释）不执行工具循环" | 工具循环已实现：`AI_TOOLS` tools.ts:183-214、`toolLoop` bridge.js:758-888、轮次上限 bridge.js:685，并用例守着（`tests/cdp-ai.mjs:423-483`） |
| 2 | `src/lib/ai/types.ts:74-82` | `config` / `busy` 的注释写成"**宿主侧**配置问题""宿主侧已有一轮在跑（页面刷新后旧请求还没结束）" | 两者现在都在页面侧：`busy` 由 `sendTurn` 的守卫产生（bridge.js:716），`config` 由 `relay.ts` 的地址/密钥检查与 `failTurn` 产生（relay.ts:90-95、relay.ts:140） |
| 3 | `src/components/settings/AiGroup.vue:5` | "相比于 v1 的 12 项…这里**收敛成 10 项**" | 实际 **11** 个 `data-setting="ai.*"` 小节（命令 §11 ⑥）；且注释里的序号有两个"⑧"（AiGroup.vue:247 隐私、AiGroup.vue:278 测试连接），后续 ⑨ ⑩ 跟着错位 |
| 4 | [`../link/CREDENTIALS.md`](../link/CREDENTIALS.md) §2.2 | "`ai.SelfCheck()` 里有一项专门验它（**含"错误信息里不出现内置站点域名"**）" | 自检项确实存在（"端点不退回内置站点"，bridge.js:347-364），但那一项只验"拼接相等 + 非 http/https 抛错 + 不认识的地址抛错"，**没有**断错误信息里不含内置站点域名；域名那条断言在用例里（`tests/cdp-ai.mjs:228`、`tests/cdp-ai.mjs:230`） |
| 5 | [`../AI-ASSISTANT.md`](../AI-ASSISTANT.md):1-30 | 把 C# 宿主的 `hostObjects.sync.ai`（`AiDpapi.cs` / `AiRelay.cs` / `AiBridge.cs`）写成**现役**："密钥、传输、错误分类全在宿主侧"；同页还写"分步显示（§2.2）不在本阶段" | `ai` 宿主对象不存在（`main.rs:207-215` 只有 9 个对象）、宿主里没有任何 `ai.*` 话题（命令 ④）；传输在 `relay.ts:177`、分步显示已落地（StepViewer.vue）。这正是 [`../../AGENTS.md`](../../AGENTS.md) §2 登记的 R7 债；现状说明以本文与 [`../link/CREDENTIALS.md`](../link/CREDENTIALS.md) 为准 |

**未证实项**（不替它背书，写明怎么验）：

1. **"所有 OpenAI 兼容端点都能直连"** —— 未证实。只实测过 DeepSeek 与 GitHub
   （[`../link/CREDENTIALS.md`](../link/CREDENTIALS.md) §2.1 第 5 条）。
   验法：对目标端点跑一次 `设置 → AI` 的「测试连接」，再看 `tests/cdp-ai.mjs` 的
   Origin/CORS 断言是否需要为它加一条场景。
2. **端到端 160/0 的当前复现** —— 本次未复跑（需独占宿主与 9222 端口，见
   [`../../AGENTS.md`](../../AGENTS.md) §4）。验法：命令 §11 的 `node …cdp-ai.mjs`，
   判据是末行 `RESULT|cdp-ai|<pass>|<fail>` 且 fail 为 0。
3. **`.bak` 明文残留在真机上的实际存在性** —— 代码路径已核实（`sys.rs:210` 复制、
   `sys.rs:222-232` 不删 `.bak`），但本文未在真机上翻过 `ai.json.bak` 的内容。
   验法：改一次 AI 设置后检查 `%LOCALAPPDATA%\MFMath\settings\ai.json.bak` 是否含 `apiKey`。
