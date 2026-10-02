# AI 助手（阶段 1：对话 + 解释 + 上下文 + 流式）

> 落地于本轮。范围按"第一版只做对话与解释"执行：**工具调用只留契约位置，不执行**；
> 分步显示（§2.2）不在本阶段。密钥、传输、错误分类全在宿主侧，页面只组装消息与渲染。

## 1. 一句话设计

**宿主只做"凭据 + 网络"，协议在 TS，一切计算仍然由 C++ 引擎完成，AI 只解释。**

这次改动（第二轮）把一个关键边界挪了位置：原先宿主里有一套 C# 的 SSE 分帧与
OpenAI 分片解析，TS 只做 UI。现在那套 C# 实现**删掉了**，协议层整体搬到 TS
（移植自 MVS Agent 的 `src/model/`，语言相同所以是逐个文件搬），宿主缩成"带密钥发请求、
把响应原始字节转回来"。理由：**SSE 分帧/分片语义/错误分类只该有一份实现**——
两边各写一套的后果正是 MVS Agent README 里那句「两份实现不一致 = 一直在线的界面和
刚刷新的界面显示不同的东西」。顺带收益：分帧这类纯逻辑第一次能**脱离宿主做离线单测**。

| 层 | 职责 | 位置 |
| --- | --- | --- |
| 凭据 | DPAPI 加密落盘、只写不读、脱敏视图 | `MFMath.Host/AiDpapi.cs`、`AiConfig.cs` |
| 网络 | 带密钥发请求、响应字节 base64 转发、取消、超时、失败分类 | `MFMath.Host/AiRelay.cs` |
| 桥面 | `hostObjects.sync.ai`：Info / Configure / SetKey / ClearKey / Test / **Begin** / Cancel / CancelAll / Busy / SelfCheck | `MFMath.Host/AiBridge.cs` |
| **协议** | **SSE 分帧、OpenAI 分片语义、降级通知、事件契约** | `src/lib/ai/sse.ts`、`client.ts`、`collect.ts`、`types.ts`（**移植自 MVS Agent**） |
| 页面 | 消息组装（隐私开关）、token 估算、公式切分渲染、会话落盘 | `src/lib/ai/bridge.js`、`relay.ts` |
| 界面 | 右侧**非模态抽屉**面板 + 设置 → AI 分组 | `src/components/ai/AiPanel.vue`、`src/components/settings/AiGroup.vue` |

数据流：

```
面板点发送 → bridge.js 组装 messages（隐私开关在此生效）
          → client.ts 拼 OpenAI 请求体
          → relay.ts 调 ai.Begin({path:"/chat/completions", body})
          → 宿主 AiRelay：用自己的密钥 + Authorization 发 POST，读字节
          → PushHub: ai.http{status} / ai.raw{b64}* / ai.rawEnd | ai.rawError
          → relay.ts 还原成字节流 → sse.ts 分帧 → client.ts 映射成 ModelEvent
          → collect({onEvent}) 一边推增量给面板、一边收干成最终文本落盘
```

## 2. 安全边界：中继的闸门（关键）

中继天然是一个"替我发一次请求"的原语。如果允许页面传**绝对 URL**，它就变成
"把密钥发到任意地址"——渲染进程里一段注入脚本就能把 key 骗走。所以
`AiRelay.ValidatePath` 只接受以单个 `/` 开头的相对路径，并且：

- 拒绝绝对地址（`https://…`）；
- 拒绝协议相对地址（`//host`）；
- 拒绝 `..` 穿越与换行；
- 端点来自宿主自己的配置，页面无从指定；
- `Authorization` 由宿主自己加，页面传的任何头都不会被转发。

端到端用例里有三条断言专门打这个闸门（绝对地址 / `//host` / `..` 都必须被拒），
设置里的自检也把这条列为一项。

## 3. 三条纪律（照搬 MVS Agent 的模型层，现在是同一份 TS 代码）

1. **流式是原语**：`ModelClient.stream(req): AsyncIterable<ModelEvent>`；阻塞式结果是它的
   派生（`collect()`）。事件里从第一天就有 `tool_call_delta`（本版不执行，但契约留位——
   以后加"AI 调度引擎"不用重写模型层）。
2. **能力缺失是可观测的降级**：缺 `usage`、流里出现坏 JSON、没有 `[DONE]` —— 都不是崩溃，
   而是 `notice`（`missing_usage` / `bad_sse_data` / `truncated_stream`）。
3. **错误是一等事件**：分类为 `config | network | http | protocol | timeout | aborted`。
   被掐断（`IOException` → `network`）与"端点回了看不懂的东西"（`protocol`）分开，
   因为前者重试可能成功、后者不会；手动停止（`aborted`）与超时（`timeout`）也分开。

另外两个实测易踩点（都在注释里）：`usage` 尾包的 `choices` 是**空数组**，必须在取
`choices[0]` 之前处理；`tool_calls` 的参数是**按 index 分组的 JSON 碎片**，拼完才可能合法。

## 3. 密钥与隐私

**密钥不进渲染进程**，这是与其它设置最不同的一点：

- 其它设置走"页面写 JSON → `sys.StoreWrite`"，因为页面本来就知道内容；
  AI 配置**不能**这样——它包含 API Key，一这么走密钥就必须先出现在页面里。
- 所以 AI 配置由宿主自己读写 `%LOCALAPPDATA%\MFMath\settings\ai.json`，
  页面对外只有 `hasKey / keySource / keyPersisted` 三个布尔/枚举，**看不到密钥本身**。
- 加密用 Windows DPAPI（`CryptProtectData`，当前用户范围，禁止弹 UI），
  **P/Invoke 而不是拉 NuGet 包**（宿主依赖清单刻意短）。
- **DPAPI 不可用时不降级成明文**：密钥只留内存，界面明说"重启后要重填"。
- 页面就算用 `sys.StoreRead("ai")` 读到整个文件，拿到的也只是密文。

**会发送什么**（设置 → AI → 「会发送什么」逐项可关，默认值就是隐私承诺）：

| 内容 | 默认 | 理由 |
| --- | --- | --- |
| 问题文本 | 必需 | 没有它就没有对话 |
| 当前表达式 | **开** | 不开的话 AI 看不到你在算什么，讲解质量会很差 |
| 引擎结果 | **开** | 且明确告诉模型"以此为准" |
| 会话历史 | 关 | 私人对话内容；打开后按"保留 N 轮"截断（成本闸门） |
| 控制台代码 | 关 | 那是用户的私人代码 |

面板底部实时显示**这一轮将发送约多少 token**与包含哪些部分（与 `buildMessages` 用同一份
逻辑算，不另算一遍），上下文窗口的来源也如实标注（"你声明的值" / "保守默认"）。

## 4. 硬约束：AI 不得成为计算源

系统提示词里写明"所有计算由 C++ 引擎完成，你只做解释"，但**提示词不是机制**。本轮的机制与
断言是：

- AI 的输出**只进面板**，不写任何计算页的结果区（结果区永远显示引擎值）；
- CDP 用例 `cdp-ai.mjs` 里有一条把这条钉住的断言：假端点故意回 `1+1=3`，
  断言计算页 LCD **仍然是 2**（引擎算出来的值）。这条断言存在的意义是：以后谁把 AI 的输出
  接到结果区，它立刻变红。
- 命令/输出**永不执行**：不 `eval`、不拼 HTML。面板里模型正文走插值，公式片段交给
  `MathLatex.vue`（KaTeX 内部安全渲染），切分只认 `$...$` / `$$...$$`。

阶段 2（分步）与阶段 3（工具调用）要在这条红线内做：分步的每一条式子回引擎核验
（`compare_expr`）、核验不过标黄并保留原文；工具调用只允许映射到已注册的引擎 action。

## 5. 验收与证据

| 用例 | 断言 | 结果 |
| --- | --- | --- |
| `unit-sse.mjs`（新，**离线**：不需要宿主/网络） | 四份 MVS Agent 录制样本（text-basic / reasoning-deepseek / tool-calls / no-usage）在 **1/2/3/5/17/64/333 字节切分下结果一致**；CRLF 被切散、多行 data、注释行、只去一个空格、末尾无空行、多字节 UTF-8 跨 chunk、纯空行 | **13 / 0** |
| `cdp-ai.mjs`（自带假端点） | 配置读写、**密钥不外泄**（脱敏视图无明文、落盘是密文、password 输入框）、**中继闸门**（绝对地址 / `//host` / `..` 全被拒）、流式增量、停止、**七类异常**（401 / 500 / 坏 SSE / 无 usage / 无 [DONE] / 连接失败 / 超时）、异常后仍可继续、隐私开关真的改变请求体（历史 2 条 vs 14 条）、**AI 不得当计算源**、自检、面板非模态、不可用时诚实提示、**架构断言**（走的是 `ai.http`/`ai.raw*`，宿主不再推 `ai.delta`） | **58 / 0** |
| `cdp-settings.mjs`（更新） | AI 组从占位变真实设置（有可用开关、无待实现标记、逐项隐私开关、密钥状态说明）；「占位必须说清依赖」这条覆盖挪到仍占位的搜索组 | 30 / 0 |
| 全套回归（16 个用例一轮跑完，含离线单测） | — | **464 / 0** |

自检（设置 → AI → 自检，不联网）四项：DPAPI 可用性、**中继路径闸门（拒绝绝对地址）**、
**响应字节 base64 转手无损**、配置目录可写。

## 6. 本地假端点（不联网、不要真 key）

`tests/fake-ai-server.mjs` 跑在真实 TCP + 真实 SSE 上，场景由最后一条 user 消息触发：

| 触发词 | 行为 |
| --- | --- |
| `断开` | 吐两个字后粗暴掐断连接（验证 network / "吐了一半"） |
| `慢速` | 每 300ms 一个字（验证流式渲染与停止） |
| `挂起` | 吐一个字后永不结束（验证超时） |
| `500` / `401` | 对应状态码 + JSON 错误体 |
| `坏JSON` | 中间塞一条不是 JSON 的 data |
| `无usage` / `无DONE` | 触发两种降级通知 |
| `思考` | 先 `reasoning_content` 再正文（DeepSeek 式思维链） |
| `公式` | 正文带回 `$...$` 与 `$$...$$` |

外加给测试用的 `GET /__requests`（**记录请求原文**，隐私断言靠它）、`POST /__reset`、
`GET /__health`。密钥只记"有没有 + 末四位"，假端点也不持有全文。

## 7. 与 v1 / 与 MVS Agent 的关系

**从 MVS Agent 抄的是协议与教训，现在是同一份代码**（第二版改动之后）：

| 抄来的 | 位置 | 为什么值得抄 |
| --- | --- | --- |
| `sse.ts`（逐字） | `src/lib/ai/sse.ts` | 「一个 TCP chunk ≠ 一个 SSE 事件」这一整类坑：缓冲跨 chunk、末尾孤立 `\r` 要留到下一 chunk、`data:` 后只去一个空格、注释行、多行 data、末尾无空行 |
| `types.ts`（逐字） | `src/lib/ai/types.ts` | 事件契约 + `Notice`（能力缺失是一等事件）+ 错误分类 + `tool_call_delta` 留位 |
| `openai-compatible.ts`（只换运输层） | `src/lib/ai/client.ts` | 一份适配器覆盖 DeepSeek/OpenAI/Ollama/vLLM；`include_usage` 可关；`reasoning_content` 两种字段名 |
| `collect.ts`（逐字） | `src/lib/ai/collect.ts` | 阻塞式是流的派生；`onEvent` 旁观回调让"推 UI"和"拿完整结果"共用一条路径 |
| 录制样本 + 任意切分测试法 | `tests/fixtures/*.sse`、`tests/unit-sse.mjs` | 端到端里几乎不可能稳定复现"字节被切散"，纯函数测才行 |
| 假端点按消息内容触发场景 | `tests/fake-ai-server.mjs` | 不联网、不要真 key、异常路径可按需触发 |
| 「日志里允许有冗余，不允许有歧义」 | 会话落盘只落最终消息 | 增量不落盘，否则日志被 token 撑爆 |

**没抄的**：`agent.py` 那套"正则从正文抠 JSON 当工具调用 + Python `eval()`"（原生
`tool_calls` 按 index 累积才是正解）；provider 注册表与 `model_map` 角色名（12 项设置
收敛成 10 项）；登录门禁与配额（BYO Key）。

**与 v1 的差异（有意为之）**：

| v1 | 现在 | 为什么 |
| --- | --- | --- |
| 12 项设置（provider / model_map / localModel / cache…） | **10 项** | provider 不做注册表 → 三个预设按钮；`model_map` 是内部间接层，用户不需要知道；localModel 由 Ollama 预设覆盖；cache → 会话记录（对话缓存会让回答过期） |
| 模态对话框 | **非模态右侧抽屉** | 用户要一边看结果一边问；也符合"不弹窗口"的一贯要求 |
| 有 key 就绕过配额、`balance` 只做显示 | **BYO Key：不登录、不配额** | v1 的本地计数是假的，站点也没有对账语义 |
| 分步是一整块只读富文本 | 阶段 2 再做（引擎出结构 + AI 出措辞 + 每步核验） | 见 `MIGRATION-GAPS.md` §2.2 与 §0.4 第 4 条 |

## 8. 已知边界

- **上下文窗口多数探不到**：OpenAI / DeepSeek 的兼容层不返回上下文长度，所以默认按 32k
  保守估计并**如实标注来源**；`usage.prompt_tokens` 只用来显示本轮消耗，尚未做估算自校准。
- **会话落盘只落最终消息**（`ai-chat.json`，最多 40 条），不落增量。
- **工具调用未实现**：`tool_call_delta` 事件已经产生但没人消费，界面里也没有"AI 执行了什么"。
- **没有 markdown 渲染**：正文按纯文本 + 公式片段渲染（模型输出是不可信输入）。
- **超时是整轮墙钟上限**（默认 120s），没有"首字节超时"与重试退避。
- **字节经推送转手**：`ai.raw` 每条一个读取块（base64）。刻意不做合并——合并会让最后一个
  事件卡在缓冲里，界面看起来"卡住不动"。代价是消息条数多一些（SSE 每块几百字节，量级无妨）。
- **中继只支持 POST + JSON body**：目前只有 `/chat/completions` 用得到；要支持别的形状
  （比如上传、GET）得先扩 `Begin` 的入参，而不是放宽路径闸门。
