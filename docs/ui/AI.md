# AI 助手

> 本文回答 AI 面板的实现：页面直连端点的流式请求、SSE 分帧、密钥存储位置、端点地址校验，以及 AI 不作为计算源的原则。
>
> 与同层文档的分工：[ARCHITECTURE.md](ARCHITECTURE.md) 讲 Vue 壳的分层与路由；[ENGINE-BINDING.md](ENGINE-BINDING.md) 讲 `ENGINE_MAP` 与 `engineCall` 的绑定；[SETTINGS-WORKSPACE.md](SETTINGS-WORKSPACE.md) 讲设置读写与导入导出的通用机制，本文只写 `ai.json` 与凭据剥离；[CHECKS.md](CHECKS.md) 讲构建闸门；凭据边界总账见 [../link/CREDENTIALS.md](../link/CREDENTIALS.md)。

## 1. 文件与规模

`src/lib/ai/` 共 9 个文件，其中 8 个是代码，`engine-signatures.json` 是数据：

| 文件 | 行数 | 职责 |
| --- | --- | --- |
| `bridge.js` | 1,036 | 配置读写、脱敏视图、消息组装、会话落盘、工具循环编排 |
| `client.ts` | 369 | OpenAI 兼容端点的分片语义 |
| `collect.ts` | 121 | 阻塞式消费者、工具参数碎片拼接收尾 |
| `engine-signatures.json` | 5,905 | 424 个 action 的参数表，AI 工具目录的权威源 |
| `markdown.ts` | 236 | 受限 markdown 转 token 树 |
| `relay.ts` | 252 | 运输层：页面 fetch、地址闸门、取消与超时分类 |
| `sse.ts` | 92 | 唯一一份 SSE 分帧实现 |
| `tools.ts` | 387 | 两个工具的 schema、参数校验、执行 |
| `types.ts` | 129 | 模型层契约 |

8 个代码文件合计 2,372 非空行。验证命令：

```powershell
Get-ChildItem MF_UI\MFMath.UI.Vue\src\lib\ai -File | Where-Object { $_.Extension -ne ".json" } |
  ForEach-Object { (Get-Content $_.FullName | Where-Object { $_.Trim() -ne "" }).Count } | Measure-Object -Sum
```

## 2. AI 不是宿主对象

| 事实 | 证据 |
| --- | --- |
| 宿主只注册 9 个对象，没有 `ai` | `MFMath.Host.Rust/src/main.rs` 的对象注册表 |
| 宿主不存在 `ai.*` 推送话题 | 命令 `Select-String -Path MFMath.Host.Rust\src\*.rs -Pattern '"ai\.'` 返回 0 匹配 |
| DPAPI 调用点只在 `account.rs`、`search.rs`、`selftest.rs` | 命令 `Select-String -Path MFMath.Host.Rust\src\*.rs -Pattern 'dpapi::(protect|unprotect)'` |
| 请求由页面发出 | `relay.ts` 的 `relayPost` 内 `fetch` |
| 页面读原始字节，不做分帧 | `relay.ts` 的 `bodyStream` |
| 分帧只在 `sse.ts` 一份，被 `client.ts` 消费 | `parseSSE` |

「就绪」的语义是配置齐备：读到设置文件、开关打开、有明文密钥、端点合法。`isRelayHosted()` 只检查 `creds.apiKey` 与 `isUsableBaseUrl(creds.baseUrl)`。

## 3. 一次发送的路径

| 步 | 行为 | 位置 |
| --- | --- | --- |
| ① | 面板取草稿、清空输入框、调 `sendTurn` | `AiPanel.vue` |
| ② | 前置校验：启用、有密钥、未在跑、端点合法、运输层就绪，早退写 `aiState.error` | `bridge.js` 的 `sendTurn` / `failTurn` |
| ③ | 组装 messages（系统提示 + 现场上下文 + 历史 + 本轮问题） | `buildMessages` |
| ④ | 用户消息先入会话，再重置 `aiState` | `sendTurn` |
| ⑤ | 每轮新建 `AbortController`，推送 `{baseUrl, apiKey, timeoutSec}` | `sendTurn` |
| ⑥ | `client.stream()` → `relayPost` → `fetch`；字节 → `parseSSE` → 分片 → `ModelEvent` | `client.ts` |
| ⑦ | 增量经 `collect({onEvent})` 写入状态 | `collect.ts` |
| ⑧ | 收尾先核对当前轮次，再并入会话、落盘 | `sendTurn` 尾部 |

每轮由 `currentTurn = {id, ctrl}` 标识，所有收尾先核对 `currentTurn?.id !== myTurn`，防止旧轮改写新轮的流式正文。

## 4. 直连与流式实现

`relay.ts` 用页面内 `fetch` 直连端点，把响应体作为字节流交给 `sse.ts`。`sse.ts` 的 `parseSSE` 维护缓冲区并跨 chunk 切块：

| 规则 | 实现 |
| --- | --- |
| 跨 chunk 保留余量 | 缓冲区 + `indexOf('\n\n')` 循环 |
| 三种行尾 | 末尾孤立 `\r` 保留，等下一个 chunk |
| 冒号开头注释 | 跳过 |
| 冒号后最多去一个空格，多行 `data` 用 `\n` 连接 | `sse.ts` |
| 末尾无空行仍发最后事件 | `parseSSE` |
| 分帧层不接收 `AbortSignal` | 底层 body 被 abort 时抛错 |

OpenAI 分片语义在 `client.ts`：

| 线上形状 | 处理 |
| --- | --- |
| `data: [DONE]` | 终止标记 |
| 单条 `data` 非 JSON | 降级 `bad_sse_data` notice，不算失败 |
| `chunk.usage` 尾包 | 在取 `choice` 前处理 |
| `delta.reasoning_content ?? delta.reasoning` | 思维链增量 |
| `delta.content` | 正文增量 |
| `delta.tool_calls` 碎片 | 原样吐 `argsJsonDelta`，不在此解析 |
| `choice.finish_reason` | 归一为 `stop` / `tool_calls` / `length` / `unknown` |
| HTTP 非 2xx | 读干错误体，`kind:'http'` |
| HTTP 200 + JSON 错误体 | `protocol` 错误，附原文开头 4096 字节 |
| 200 下的错误分片 | 作为 `kind:'http'` 抛出 |
| 流结束缺 usage 或无 `[DONE]` | `missing_usage` / `truncated_stream` notice |

失败分类：`classify()` 产出 `timeout` / `aborted` / `network` 三种；取消与超时在 `client.ts` 当正常终止（`done`），其余才是 `error`。

取消的语义是停止等待，不是撤回请求——请求已到服务商侧，计费不变。

## 5. 密钥存储

| 事实 | 位置 |
| --- | --- |
| 存储于 `%LOCALAPPDATA%\MFMath\settings\ai.json` 的 `apiKey`，明文 | `bridge.js` 的 `readAiFile` |
| 读写走 `sys.StoreRead` / `sys.StoreWrite` | `bridge.js` |
| 保存时删除旧版 `apiKeyProtected` | `aiSetKey` |
| 明文密钥只活在模块作用域 `aiKey`，不进 `aiConfig` | `bridge.js` |
| 脱敏视图 `aiConfig` 删掉 `apiKey` 与 `apiKeyProtected` | `bridge.js` |
| 旧版 DPAPI 密文页面侧解不开，只剩密文时 `hasKey=false` | `bridge.js` |
| 界面文案如实说明明文、无加密 | `AiGroup.vue` |

跨宿主可移植性：`ai.json` 的明文密钥不随用户走。C# 旧宿主写的是 DPAPI 密文 `apiKeyProtected`，Rust/TS 读的是明文 `apiKey`，两种形式互不通用。

## 6. 端点地址校验

核心约束是不做「地址不认识就退回内置站点」的规范化，理由写在 `relay.ts`：baseUrl 由用户填写，悄悄替换等于把用户密钥发往内置服务器。

| 规则 | 实现 |
| --- | --- |
| 只接受 http/https 绝对地址且 hostname 非空 | `isUsableBaseUrl` |
| 路径以单个 `/` 开头 | `joinBasePath` |
| 路径不允许空白或控制字符 | `joinBasePath` |
| 拼接结果与 baseUrl 同源 | `joinBasePath` 内 origin 比较 |
| 违反即抛 `RelayError('config')`，不退回 | `joinBasePath` |
| 规范化只在 baseUrl 为空时套默认值 | `normalizeConfig` |
| 发送前本地拦截，一个请求都不出去 | `sendTurn` |
| 自检项「端点不退回内置站点」 | `aiSelfCheck` |
| 纯函数暴露给断言 | `window.__mfAi.relay` |

`isUsableBaseUrl` 只做格式校验，不做可达性或白名单校验——端点本就是用户自己的配置项。

## 7. 导出与诊断剥掉密钥

| 位置 | 做法 |
| --- | --- |
| 前端导出 | `CREDENTIAL_FILES = ["ai","account","search"]` 整份排除，名字写进 `excluded` |
| 字段级剥离 | `SECRET_FIELD` 正则剥 `protected`/`password`/`passwd`/`secret`/`token`/`api[-_]?key`，记进 `stripped` |
| 导入侧 | 三类文件不写 |
| 宿主诊断包 | `CREDENTIAL_STEMS = ["ai","account","search"]`，加文件名含 `secret` 的兜底 |

## 8. 不作为计算源

| 机制 | 实现 |
| --- | --- |
| 系统提示写死计算由 C++ 引擎完成 | `SYSTEM_PROMPT` |
| 工具只暴露 `engine_find` 与 `engine_call` 两个 | `AI_TOOLS` |
| 目录以引擎签名表为权威（424 条） | `CATALOG` / `ENGINE_FN_COUNT` |
| 工具只走 `engineCall` | `executeTool` |
| 表外函数名拒绝并回最接近候选 | `executeTool` |
| 参数按动作表校验 | `validateArgs` |
| 隐私闸门：`sendResult` 关着时拒绝工具调用 | `executeTool` |
| 结果回模型前截断到 3000 字符 | `MAX_CONTENT` |
| 轮次上限 4 | `MAX_TOOL_ROUNDS` |
| 单轮工具调用上限 8 | `MAX_TOOL_CALLS_PER_ROUND` |
| 漂移检测 | `verifyEngineTable` |

签名表 424 条是 AI 工具目录的权威源，由引擎源码重建，验证命令：

```powershell
cd MF_UI\MFMath.UI.Vue; node tools/engine-signatures.mjs --check
```

## 9. 步骤视图

StepViewer 渲染的是本轮 `engine_call` 的调用记录，不是模型编写的步骤。引擎信封没有 `steps` 字段，让模型自编步骤即伪造推导，违反硬约束。

| 呈现 | 内容 |
| --- | --- |
| AI 面板工具块 | 引擎徽标 + 函数名 + 参数 + 结果 + 耗时 |
| 「查看步骤」→ StepViewer | 编号步骤、函数、参数、完整结果、状态 |

显示纪律：给人看的完整结果不截断；失败保留并标红，不隐藏。

## 10. 面板与渲染

| 决定 | 做法 |
| --- | --- |
| 右侧非模态抽屉 | `position: fixed`，自占 420px |
| 未就绪说明原因 | `AiPanel.vue` |
| 模型输出不可信输入 | 无 `v-html`，无拼接 HTML |
| 链接只放行 http/https/mailto | `markdown.ts` |
| 不渲染 `<img>` | 图片降级为文本 |
| 流式正文节流约 80 ms | `streamShown` |
| 会话只落最终消息 | `MAX_MESSAGES = 40` |
| 思考过程随消息，上限 8000 字 | `MAX_REASONING` |
| 自检与连通性测试不联网 | `aiSelfCheck` / `aiTest` |

设置分组 `设置 → AI` 共 11 个 `data-setting="ai.*"` 小节：`enabled`、`baseUrl`、`model`、`modelParams`、`apiKey`、`context`、`tools`、`privacy`、`test`、`selftest`、`chat`。provider 不设注册表，是三个预设按钮（DeepSeek / OpenAI / Ollama）。

验证命令：

```powershell
Select-String -Path MF_UI\MFMath.UI.Vue\src\components\settings\AiGroup.vue -Pattern 'data-setting="(ai\.[a-zA-Z.]+)"' -AllMatches |
  ForEach-Object { $_.Matches } | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
```

## 11. 验证命令

```powershell
# 引擎签名表键数（期望 424）
((Get-Content MF_UI\MFMath.UI.Vue\src\lib\ai\engine-signatures.json -Raw | ConvertFrom-Json).PSObject.Properties | Measure-Object).Count

# 宿主里不该有 ai.* 推送话题（期望 0）
(Select-String -Path MFMath.Host.Rust\src\*.rs -Pattern '"ai\.' -AllMatches).Count
```

端到端用例 `tests/cdp-ai.mjs` 共 151 个 `check(` 调用点，自行拉起假端点，需要宿主带 `--remote-debugging-port=9222` 启动，不需要网络与真实密钥。
