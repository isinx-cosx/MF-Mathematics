/**
 * ai/types.ts — 模型层的唯一契约：请求进，事件流出。
 *
 * 移植自 MVS Agent 的 `src/model/types.ts`（同一份契约，语言相同所以这次是逐字搬），
 * 目的只有一个：**桌面应用与 agent 用同一套事件语义**，而不是各写一份流式实现。
 * 你自己 README 里那条教训正是这么来的：「两份实现不一致 = 一直在线的界面和刚刷新的
 * 界面显示不同的东西」。
 *
 * 两条不可动摇的设计约束（原文照抄）：
 *
 * 1. **流式是原语，不是可选功能。**
 *    字符串随时能从流里塌缩出来（见 collect.ts），反过来不行。
 *    一旦这里暴露的是 `Promise<string>`，以后想加流式就要改穿每一层。
 *
 * 2. **能力缺失必须是可观测的降级，不是崩溃。**
 *    不同兼容端点的能力不一致（有的不给 usage，有的不给 reasoning）。
 *    所以 Notice 是一等事件，上层永远不许假设某个字段一定存在。
 */

export type Role = 'system' | 'user' | 'assistant' | 'tool'

export interface ToolCall {
  id: string
  name: string
  /**
   * 原始 JSON 字符串，**故意不在这里解析**。
   * 参数校验是工具层的职责：模型层只负责把碎片拼回来。
   */
  argsJson: string
}

export type Message =
  | { role: 'system'; content: string }
  | { role: 'user'; content: string }
  | { role: 'assistant'; content: string; toolCalls?: ToolCall[] }
  | { role: 'tool'; content: string; toolCallId: string }

export interface ToolSchema {
  name: string
  description?: string
  /** JSON Schema 对象。形状先定死，本版不实现工具循环。 */
  parameters: Record<string, unknown>
}

export interface ModelRequest {
  model: string
  messages: Message[]
  tools?: ToolSchema[]
  temperature?: number
  maxTokens?: number
  /** 一路穿到底，中间不许吞掉 */
  signal?: AbortSignal
}

export type FinishReason =
  | 'stop'
  | 'tool_calls'
  | 'length'
  | 'aborted'
  | 'timeout'
  | 'error'
  | 'unknown'

export interface Usage {
  inputTokens: number
  outputTokens: number
}

export type ModelErrorKind =
  /** 连接失败、TCP 中断、DNS 等 */
  | 'network'
  /** 拿到了 HTTP 响应但状态码非 2xx */
  | 'http'
  /** 响应形状不符合预期（缺 body、SSE 无法解析等） */
  | 'protocol'
  /** 宿主侧配置问题：没端点、没密钥、未启用 */
  | 'config'
  /** 整轮墙钟超时 */
  | 'timeout'
  | 'aborted'
  /** 宿主侧已有一轮在跑（页面刷新后旧请求还没结束时点发送会撞上） */
  | 'busy'
  | 'unknown'

export interface ModelError {
  kind: ModelErrorKind
  message: string
  status?: number
  cause?: unknown
}

/** 能力缺失 / 降级的可观测记录 */
export interface Notice {
  code:
    /** 服务端没有返回 usage —— 常见于兼容网关与本地推理，属正常降级 */
    | 'missing_usage'
    /** 流在没有 [DONE]、也没有 finish_reason 的情况下结束了 */
    | 'truncated_stream'
    /** 单条 SSE data 无法解析 */
    | 'bad_sse_data'
    | (string & {})
  message: string
}

export type ModelEvent =
  | { type: 'text_delta'; text: string }
  /** 思维链。DeepSeek 用 reasoning_content，部分端点用 reasoning */
  | { type: 'reasoning_delta'; text: string }
  /**
   * 工具调用参数是**按 index 分组的 JSON 碎片**，必须累积后才能解析。
   * 本版（对话 + 解释）不执行工具循环，但这个位置先留着 ——
   * 否则以后要重写模型层（事件形状是契约，驱动可以后加）。
   */
  | {
      type: 'tool_call_delta'
      index: number
      id?: string
      name?: string
      argsJsonDelta?: string
    }
  | { type: 'usage'; usage: Usage }
  | { type: 'notice'; notice: Notice }
  | { type: 'done'; reason: FinishReason }
  /** 流中途失败也是事件，不是异常 —— 上层要能区分「没开始」和「吐了一半」 */
  | { type: 'error'; error: ModelError }

export interface ModelClient {
  stream(req: ModelRequest): AsyncIterable<ModelEvent>
}
