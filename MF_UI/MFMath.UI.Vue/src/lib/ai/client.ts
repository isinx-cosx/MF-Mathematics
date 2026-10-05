/**
 * ai/client.ts — OpenAI 兼容端点客户端（移植自 MVS Agent 的
 * `src/model/openai-compatible.ts`，**只换掉运输层**：fetch → 宿主中继）
 *
 * 一份适配器覆盖 DeepSeek / OpenAI / Moonshot / 硅基流动 / Ollama / vLLM ——
 * 它们共用 chat completions 的形状。**刻意不做 provider 注册表**：
 * 等真接了第二家"形状不同"的（比如 Anthropic 的 messages），抽象会自己浮出来。
 *
 * 与原文的三处差异，都是"桌面应用"这个环境决定的：
 *   1. 运输层换成 `relayPost`（宿主带密钥发请求并把原始字节转回来）——
 *      页面里没有密钥，也不受 CORS 影响；
 *   2. `baseUrl` 不再由这里拼接：宿主持有端点，页面只给**相对路径**；
 *   3. 取消/超时的判定来自宿主的中继错误（kind: aborted / timeout），
 *      它们与"真的出错"分开 —— 上层要能区分"没开始"和"吐了一半"。
 *
 * 已知的行为差异不在这里抹平，而是降级成 Notice 让上层看见：
 *   - 有没有 reasoning_content
 *   - 有没有 usage 尾包
 *   - 有没有 [DONE]
 */

import type {
  FinishReason,
  Message,
  ModelClient,
  ModelError,
  ModelEvent,
  ModelRequest,
  ToolSchema,
} from './types.ts'
import { parseSSE } from './sse.ts'
import { relayPost, readAll, RelayError } from './relay.ts'

export interface HostClientConfig {
  /**
   * 是否请求 usage 尾包（stream_options.include_usage）。
   * OpenAI / DeepSeek 支持；部分兼容网关会拒绝这个字段，置 false 即可。
   * 缺失不是错误，会降级为 missing_usage 通知。
   */
  includeUsage?: boolean
}

const DEFAULT_INCLUDE_USAGE = true
const CHAT_PATH = '/chat/completions'

export class HostRelayClient implements ModelClient {
  #config: HostClientConfig

  constructor(config: HostClientConfig = {}) {
    this.#config = config
  }

  async *stream(req: ModelRequest): AsyncGenerator<ModelEvent> {
    const model = req.model
    if (!model) {
      yield {
        type: 'error',
        error: { kind: 'protocol', message: '未指定模型：请求和配置里都没有 model' },
      }
      return
    }

    let finishReason: FinishReason = 'unknown'
    let sawUsage = false
    let sawDone = false
    let sawFinishReason = false
    // 这两个要在 try 之前声明：循环后的"零事件"判断要用（见下面那段）
    let rawHead = ''
    let parsedChunks = 0

    try {
      // signal 必须一路传到中继 —— 否则"停止"只是改了页面状态，
      // 宿主连接照旧、这条流照旧读完，工具循环还会继续开新请求（真实 token 花费）。
      const response = await relayPost(CHAT_PATH, this.#body(req, model), req.signal)

      if (response.status < 200 || response.status >= 300) {
        // 非 2xx：错误体很短，读干后作为 http 错误交出去（同原文语义）
        const detail = (await readAll(response.body)).trim()
        yield {
          type: 'error',
          error: {
            kind: 'http',
            status: response.status,
            message: `HTTP ${response.status}${response.statusText ? ` ${response.statusText}` : ''}` +
                     `${detail ? ` — ${truncate(detail, 400)}` : ''}`,
          },
        }
        return
      }

      // 一边喂 SSE 解析、一边留一份原始文本的开头。
      // 为什么要留：端点在 **HTTP 200** 下返回普通 JSON 错误体（额度/鉴权/模型名）时，
      // parseSSE 一个事件都发不出来（它只认 event: / data: 两种字段），
      // 于是界面上只剩"空白回答 + 一句灰色小字"，真实原因永远看不到、只能抓包。
      const RAW_HEAD = 4096
      const tapDecoder = new TextDecoder('utf-8')
      async function* tappingBody(): AsyncGenerator<Uint8Array> {
        for await (const chunk of response.body) {
          if (rawHead.length < RAW_HEAD) {
            rawHead += tapDecoder.decode(chunk, { stream: true })
            if (rawHead.length > RAW_HEAD) rawHead = rawHead.slice(0, RAW_HEAD)
          }
          yield chunk
        }
      }

      for await (const sse of parseSSE(tappingBody())) {
        // 取消要在**每一片**上生效。中继那条流被 abort 时会抛 RelayError('aborted')，
        // 但这里再主动看一眼，避免"已经取消却还把剩余分片读完/继续解析"。
        if (req.signal?.aborted) {
          yield { type: 'done', reason: 'aborted' }
          return
        }
        // 终止标记，不是 JSON
        if (sse.data === '[DONE]') {
          sawDone = true
          break
        }

        let chunk: OpenAIChunk
        try {
          chunk = JSON.parse(sse.data) as OpenAIChunk
        } catch {
          yield {
            type: 'notice',
            notice: { code: 'bad_sse_data', message: `无法解析的 SSE data：${truncate(sse.data)}` },
          }
          continue
        }

        parsedChunks += 1

        // ⚠ 200 下的错误分片：`data: {"error":{...}}`。
        // 原先这段被下面的 `if (!choice) continue` 直接吞掉 ——
        // 用户看到半截/空白回答，却不知道上游到底说了什么（限流？密钥？模型名？）。
        const chunkErr = (chunk as unknown as { error?: unknown }).error
        if (chunkErr) {
          const msg = (chunkErr as { message?: unknown })?.message
          yield {
            type: 'error',
            error: {
              kind: 'http',
              status: response.status,
              message: msg ? String(msg) : truncate(JSON.stringify(chunkErr), 400),
            },
          }
          return
        }

        // usage 尾包的 choices 是空数组，必须在取 choice 之前处理
        if (chunk.usage) {
          sawUsage = true
          yield {
            type: 'usage',
            usage: {
              inputTokens: chunk.usage.prompt_tokens ?? 0,
              outputTokens: chunk.usage.completion_tokens ?? 0,
            },
          }
        }

        const choice = chunk.choices?.[0]
        if (!choice) continue

        const delta = choice.delta ?? {}

        // DeepSeek 用 reasoning_content，部分端点用 reasoning
        const reasoning = delta.reasoning_content ?? delta.reasoning
        if (typeof reasoning === 'string' && reasoning !== '') {
          yield { type: 'reasoning_delta', text: reasoning }
        }

        if (typeof delta.content === 'string' && delta.content !== '') {
          yield { type: 'text_delta', text: delta.content }
        }

        if (Array.isArray(delta.tool_calls)) {
          for (const call of delta.tool_calls) {
            if (typeof call?.index !== 'number') continue
            yield {
              type: 'tool_call_delta',
              index: call.index,
              id: call.id,
              name: call.function?.name,
              argsJsonDelta: call.function?.arguments,
            }
          }
        }

        if (choice.finish_reason) {
          sawFinishReason = true
          finishReason = mapFinishReason(choice.finish_reason)
        }
      }
    } catch (err) {
      // 宿主侧已把"谁取消的"分好类：取消是正常终止，不是错误
      const relay = err instanceof RelayError ? err : null
      if (relay && relay.kind === 'aborted') {
        yield { type: 'done', reason: 'aborted' }
        return
      }
      if (relay && relay.kind === 'timeout') {
        yield { type: 'done', reason: 'timeout' }
        return
      }
      if (relay) {
        yield { type: 'error', error: { kind: toErrorKind(relay.kind), status: relay.status, message: relay.message } }
        return
      }
      // 流中途失败也是一等事件：上层要能区分「没开始」和「吐了一半」
      yield { type: 'error', error: toModelError(err) }
      return
    }

    // 一个事件都没解析出来 —— 这个响应体根本不是 SSE 流。
    // 最常见的就是"HTTP 200 + JSON 错误体"（限流 / 密钥 / 模型名 / baseUrl 写错）。
    // 原先这里只发两条灰色 notice 就结束了，用户看到的是空白回答，真实原因永远不可见。
    if (parsedChunks === 0 && !sawDone) {
      const detail = rawHead.trim()
      yield {
        type: 'error',
        error: {
          kind: 'protocol',
          status: 0,
          message:
            'HTTP 200，但响应体不是 SSE 流（零个事件，也没有 [DONE]）。' +
            '常见原因：端点返回了 JSON 错误体、baseUrl 或路径不对、模型名不被支持。' +
            (detail ? ` 原文开头：${truncate(detail, 400)}` : ''),
        },
      }
      return
    }

    // 只有「流正常结束」这一条路径会走到这里
    if (!sawUsage) {
      yield {
        type: 'notice',
        notice: {
          code: 'missing_usage',
          message: '服务端未返回 usage，token 统计不可用（正常的兼容性降级）',
        },
      }
    }
    if (!sawDone && !sawFinishReason) {
      yield {
        type: 'notice',
        notice: {
          code: 'truncated_stream',
          message: '流既没有 [DONE] 也没有 finish_reason 就结束了',
        },
      }
    }
    yield { type: 'done', reason: finishReason }
  }

  #body(req: ModelRequest, model: string): Record<string, unknown> {
    const body: Record<string, unknown> = {
      model,
      messages: req.messages.map(toWireMessage),
      stream: true,
    }

    if (this.#config.includeUsage ?? DEFAULT_INCLUDE_USAGE) {
      body.stream_options = { include_usage: true }
    }
    if (req.tools && req.tools.length > 0) {
      body.tools = req.tools.map(toWireTool)
    }
    if (req.temperature !== undefined) body.temperature = req.temperature
    if (req.maxTokens !== undefined) body.max_tokens = req.maxTokens
    return body
  }
}

// ---------------------------------------------------------------------------
// 线上格式（wire format）
// ---------------------------------------------------------------------------

interface OpenAIChunk {
  choices?: Array<{
    index?: number
    delta?: {
      content?: string | null
      reasoning_content?: string | null
      reasoning?: string | null
      tool_calls?: Array<{
        index?: number
        id?: string
        function?: { name?: string; arguments?: string }
      }>
    }
    finish_reason?: string | null
  }>
  usage?: { prompt_tokens?: number; completion_tokens?: number } | null
}

function toWireMessage(message: Message): Record<string, unknown> {
  switch (message.role) {
    case 'assistant': {
      const out: Record<string, unknown> = { role: 'assistant', content: message.content }
      if (message.toolCalls && message.toolCalls.length > 0) {
        out.tool_calls = message.toolCalls.map((call) => ({
          id: call.id,
          type: 'function',
          function: { name: call.name, arguments: call.argsJson },
        }))
      }
      return out
    }
    case 'tool':
      return { role: 'tool', tool_call_id: message.toolCallId, content: message.content }
    default:
      return { role: message.role, content: message.content }
  }
}

function toWireTool(tool: ToolSchema): Record<string, unknown> {
  return {
    type: 'function',
    function: {
      name: tool.name,
      description: tool.description,
      parameters: tool.parameters,
    },
  }
}

function mapFinishReason(raw: string): FinishReason {
  switch (raw) {
    case 'stop':
      return 'stop'
    case 'tool_calls':
    case 'function_call':
      return 'tool_calls'
    case 'length':
      return 'length'
    default:
      return 'unknown'
  }
}

function toErrorKind(kind: string): ModelError['kind'] {
  switch (kind) {
    case 'network':
    case 'http':
    case 'protocol':
    case 'config':
    case 'timeout':
    case 'aborted':
    // 宿主以 kind:"busy" 拒绝（已有一轮在跑）。原先落到 default → 面板显示
    // "类别：unknown"，看不出是"上一轮还没结束"，用户只能干等最长 900s。
    case 'busy':
      return kind
    default:
      return 'unknown'
  }
}

function toModelError(err: unknown): ModelError {
  if (err instanceof Error) {
    return { kind: 'network', message: err.message, cause: err }
  }
  return { kind: 'unknown', message: String(err), cause: err }
}

function truncate(text: string, max = 200): string {
  return text.length <= max ? text : `${text.slice(0, max)}…`
}
