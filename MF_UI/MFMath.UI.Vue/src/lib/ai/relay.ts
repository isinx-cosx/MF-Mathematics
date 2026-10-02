/**
 * ai/relay.ts — 宿主中继的页面侧（凭据与网络在宿主，协议语义在 TS）
 *
 * 为什么不是页面直接 fetch：
 *   · **密钥**。页面直连就必须自己持有 API Key，落点只能是 localStorage / 内存 ——
 *     而本项目已经有渲染进程注入面的现实案例（教程富文本清洗那个绕过，
 *     见 docs/FRONTEND-FIXES.md）。密钥留在宿主，页面里根本不存在这个字符串。
 *   · **端点可配**。baseUrl 允许用户填自建 / 中转端点，这类不少不发 CORS 头
 *     （本项目自己的假端点就是），宿主侧则对任何端点都成立。
 *
 * 宿主只做两件事：**用自己的密钥发这个请求**、**把响应原始字节转回来**。
 * 它**不理解** SSE，也不理解 OpenAI 的分片语义 —— 那些全在 sse.ts / client.ts 里
 * （移植自 MVS Agent），宿主侧没有第二份实现。
 *
 * 安全边界（宿主侧强制，见 MFMath.Host/AiRelay.cs）：
 *   · 只接受**相对路径**（如 `/chat/completions`），绝对 URL 一律拒绝 ——
 *     否则这就是一个"把密钥发到任意地址"的原语；
 *   · Authorization 由宿主自己加，页面传的任何头都不能覆盖它。
 *
 * 事件话题：ai.http（状态行）· ai.raw（base64 字节块）· ai.rawEnd · ai.rawError
 */

import { onPush } from '../push.js'

export interface RelayResponse {
  status: number
  statusText: string
  /** 响应体原始字节流（未解码），交给 parseSSE */
  body: AsyncIterable<Uint8Array>
}

export class RelayError extends Error {
  kind: string
  status: number
  constructor(kind: string, message: string, status = 0) {
    super(message)
    this.name = 'RelayError'
    this.kind = kind
    this.status = status
  }
}

interface Queue {
  chunks: Uint8Array[]
  status: number
  statusText: string
  done: boolean
  error: RelayError | null
  wake: (() => void) | null
  headersReady: Promise<void>
  resolveHeaders: () => void
}

function newQueue(): Queue {
  let resolveHeaders: () => void = () => {}
  const headersReady = new Promise<void>((resolve) => { resolveHeaders = resolve })
  return {
    chunks: [], status: 0, statusText: '', done: false, error: null, wake: null,
    headersReady, resolveHeaders,
  }
}

const queues = new Map<string, Queue>()
/** 请求头可能比 Begin 的返回值先到（极端时序），先按 id 存这里，绑定时认领 */
const orphans = new Map<string, Queue>()
let subscribed = false

function hostObj() {
  try {
    return window.chrome?.webview?.hostObjects?.sync?.ai ?? null
  } catch {
    return null
  }
}

export function isRelayHosted(): boolean {
  return hostObj() !== null
}

function b64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i)
  return out
}

function wake(q: Queue) {
  const fn = q.wake
  q.wake = null
  if (fn) fn()
}

function ensureSubscribed() {
  if (subscribed) return
  subscribed = true
  onPush((env: { topic?: string; payload?: Record<string, unknown> }) => {
    const topic = String(env?.topic || '')
    if (topic !== 'ai.http' && !topic.startsWith('ai.raw')) return
    const p = env.payload || {}
    const id = String(p.requestId || '')
    const q = queues.get(id) ?? orphans.get(id) ?? newQueue()
    if (!queues.has(id) && !orphans.has(id)) orphans.set(id, q)

    switch (topic) {
      case 'ai.http':
        q.status = Number(p.status || 0)
        q.statusText = String(p.statusText || '')
        q.resolveHeaders()
        break
      case 'ai.raw':
        q.chunks.push(b64ToBytes(String(p.b64 || '')))
        break
      case 'ai.rawEnd':
        q.done = true
        break
      case 'ai.rawError':
        q.error = new RelayError(String(p.kind || 'unknown'), String(p.message || ''), Number(p.status || 0))
        q.done = true
        q.resolveHeaders()   // 连接都没起来时不会有 ai.http，别让调用方干等
        break
      default:
        break
    }
    wake(q)
  })
}

/**
 * 让宿主带密钥请求一次（path 必须是相对路径），把响应体当字节流交回来。
 */
export async function relayPost(path: string, body: unknown): Promise<RelayResponse> {
  const ai = hostObj()
  if (!ai) throw new RelayError('config', '无宿主：AI 只在 MFMath.exe 里可用')

  ensureSubscribed()

  const res = JSON.parse(String(ai.Begin(JSON.stringify({ path, body }))) || '{}')
  if (!res || res.ok !== true) {
    throw new RelayError(String(res?.kind || 'config'), String(res?.error || '中继启动失败'), Number(res?.status || 0))
  }

  const id = String(res.requestId || '')
  const q = orphans.get(id) ?? newQueue()
  queues.set(id, q)
  orphans.delete(id)

  // 等状态行：宿主在收到响应头时立刻推 ai.http（早于任何字节）。
  // 没有它就没法判断 2xx/4xx，所以这里必须等，而不是拿一个恒为 0 的 status 去猜。
  await q.headersReady

  const cancel = () => {
    try { ai.Cancel(id) } catch { /* 忽略 */ }
  }

  async function* bodyStream(): AsyncGenerator<Uint8Array> {
    try {
      for (;;) {
        if (q.chunks.length) {
          yield q.chunks.shift() as Uint8Array
          continue
        }
        if (q.error) throw q.error
        if (q.done) return
        await new Promise<void>((resolve) => { q.wake = resolve })
      }
    } finally {
      queues.delete(id)
      cancel()
    }
  }

  return { status: q.status, statusText: q.statusText, body: bodyStream() }
}

/** 停止当前这一轮（页面点"停止"、或页面卸载时） */
export function relayCancelAll(): void {
  try { hostObj()?.CancelAll() } catch { /* 忽略 */ }
}

export function relayBusy(): boolean {
  try { return hostObj()?.Busy() === true } catch { return false }
}

/**
 * 一次性读干响应体（非 2xx 的错误体很短，不需要流式渲染）。
 * 带上限，避免坏端点把内存打爆。
 */
export async function readAll(body: AsyncIterable<Uint8Array>, limit = 64 * 1024): Promise<string> {
  const decoder = new TextDecoder('utf-8')
  let out = ''
  for await (const chunk of body) {
    out += decoder.decode(chunk, { stream: true })
    if (out.length >= limit) break
  }
  out += decoder.decode()
  return out
}
