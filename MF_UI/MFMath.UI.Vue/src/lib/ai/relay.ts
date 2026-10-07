/**
 * ai/relay.ts — 运输层：**页面自己发请求**（协议语义仍然只在 TS 侧一份实现）
 *
 * 这一层只有一个职责：拿"用户在设置里填的端点 + 明文密钥 + 超时"，发一次 POST，
 * 把响应体的**原始字节成块**交出去。它**不理解** SSE，也不理解 OpenAI 的分片语义
 * —— `event:` / `data:` 的分帧在 sse.ts，分片语义在 client.ts。
 *
 * 凭据从哪来：bridge.js 读 `%LOCALAPPDATA%\MFMath\settings\ai.json`（`apiKey` 明文），
 * 刷新配置后调用 `setRelayCredentials()` 推进来。方向是
 * relay.ts ← client.ts ← bridge.js，反过来 import 会形成循环 —— 而且
 * "配置从哪来、怎么脱敏"本来就是 bridge.js 的职责，运输层只该知道
 * "用哪个地址、带哪个密钥、超时多久"。
 *
 * ⚠ **绝不"地址不认识就退回默认站点"**：baseUrl 是用户自己填的。如果它不合法
 * （不是 http/https 绝对地址）而这里悄悄换成内置站点，就等于把用户的密钥发到
 * 我们的服务器上 —— 那是隐私事故，不是一次降级。所以 `joinBasePath()` 只做
 * `baseUrl.trimEnd('/') + path`，非法一律抛 RelayError('config')。
 *
 * 取消的语义是**"停止等待"**：abort 会掐断这条流、让调用方立刻收尾；
 * 但**它撤不回已经发出的请求**（服务商那边可能已经收到、已经在计费）。
 */

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

/* ── 凭据 ────────────────────────────────────────────────────────────── */

export interface RelayCredentials {
  baseUrl?: string
  apiKey?: string
  timeoutSec?: number
}

const DEFAULT_TIMEOUT_SEC = 120

let creds = { baseUrl: '', apiKey: '', timeoutSec: DEFAULT_TIMEOUT_SEC }

/** 更新凭据。字段传 `undefined` 表示"这一项不改" */
export function setRelayCredentials(next: RelayCredentials): void {
  if (next.baseUrl !== undefined) creds.baseUrl = String(next.baseUrl ?? '')
  if (next.apiKey !== undefined) creds.apiKey = String(next.apiKey ?? '')
  if (next.timeoutSec !== undefined) {
    const n = Number(next.timeoutSec)
    creds.timeoutSec = Number.isFinite(n) && n > 0 ? n : DEFAULT_TIMEOUT_SEC
  }
}

/**
 * baseUrl 是不是一个**可用的** http/https 绝对地址。
 * 只做格式校验：不认识就报 false，**绝不换成默认站点**。
 */
export function isUsableBaseUrl(baseUrl: unknown): boolean {
  const text = String(baseUrl ?? '').trim()
  if (!text) return false
  let url: URL
  try {
    url = new URL(text)
  } catch {
    return false
  }
  return (url.protocol === 'http:' || url.protocol === 'https:') && url.hostname !== ''
}

/**
 * 组请求地址：`baseUrl.trimEnd('/') + path`。
 *
 * 三条都不许放宽：
 *   · 端点必须是 http/https 绝对地址 —— 不合法就抛错，**不退回内置站点**；
 *   · 路径必须以单个 `/` 开头（相对路径），否则一段注入的绝对地址就变成了端点；
 *   · 拼接结果必须与 baseUrl **同源** —— 路径里塞 `//host` 一类的东西不能改写到别的站点。
 */
export function joinBasePath(baseUrl: unknown, path: unknown): string {
  const base = String(baseUrl ?? '').trim().replace(/\/+$/, '')
  if (!isUsableBaseUrl(base)) {
    throw new RelayError('config',
      `端点地址不是合法的 http/https 地址：${base || '（空）'}。不会退回内置站点 —— 请到「设置 → AI」改对。`)
  }
  const p = String(path ?? '')
  if (!p.startsWith('/')) throw new RelayError('config', `只接受以 / 开头的相对路径：${p || '（空）'}`)
  if (/[\s\u0000-\u001f]/.test(p)) throw new RelayError('config', '路径里不允许空白或控制字符')

  const joined = base + p
  let url: URL
  try {
    url = new URL(joined)
  } catch {
    throw new RelayError('config', `拼接后的地址不合法：${joined}`)
  }
  if (url.origin !== new URL(base).origin) {
    throw new RelayError('config', '路径不能把请求改写到别的站点')
  }
  return joined
}

/**
 * 名字保留（调用方只认这个名字），但**语义已经变了**：
 *   以前 = "宿主提供了 `ai` 桥"；
 *   现在 = "配置就绪" —— 有明文密钥，且 baseUrl 是合法的 http/https 地址。
 * 网络由页面自己发，所以缺的只剩配置；`hosted` 里的 "host" 不再指宿主。
 */
export function isRelayHosted(): boolean {
  return creds.apiKey !== '' && isUsableBaseUrl(creds.baseUrl)
}

/* ── 在飞的请求（取消 / 忙碌判定）────────────────────────────────────── */

const active = new Set<AbortController>()

function message(e: unknown): string {
  if (e instanceof Error) return e.message || e.name
  return String(e)
}

/**
 * 让页面带密钥请求一次（path 必须是相对路径），把响应体当字节流交回来。
 *
 * `signal` 必须真的能打断这条流 —— 否则"停止"只把页面状态改成空闲，
 * 连接照旧读完，工具循环还会继续开新请求（真实 token 花费）。
 */
export async function relayPost(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<RelayResponse> {
  if (!creds.apiKey) throw new RelayError('config', '还没有配置 API Key：去「设置 → AI」填一个')
  // 已经取消过就先按取消收尾（别把"用户停了"报成"配置错了"）
  if (signal?.aborted) throw new RelayError('aborted', '已取消')
  // 非法地址在这里就是 config 错误（**不会退回内置站点**）
  const url = joinBasePath(creds.baseUrl, path)

  // 超时与"用户取消"是两个来源：收尾时才能说清是谁取消的（kind: timeout / aborted）。
  // 超时是**整轮**的墙钟上限（和原来宿主侧一致），不是"每个分片的间隔"。
  const ctrl = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    ctrl.abort()
  }, creds.timeoutSec * 1000)

  const onOuterAbort = () => ctrl.abort()
  if (signal) signal.addEventListener('abort', onOuterAbort, { once: true })

  active.add(ctrl)
  let released = false
  const release = () => {
    if (released) return
    released = true
    clearTimeout(timer)
    try { signal?.removeEventListener('abort', onOuterAbort) } catch { /* 忽略 */ }
    active.delete(ctrl)
  }

  const classify = (e: unknown): RelayError => {
    if (timedOut) return new RelayError('timeout', '本轮超过设定的超时时间（可在设置 → AI 里调整）')
    if (ctrl.signal.aborted || signal?.aborted) return new RelayError('aborted', '已取消')
    // 连接失败 / 被静默拦截（CORS、证书、代理）都归这一类：重试**可能**有意义
    return new RelayError('network', `请求没能建立或中途断了：${message(e)}`)
  }

  let resp: Response
  try {
    resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        Authorization: 'Bearer ' + creds.apiKey,
      },
      // body 已经是 JSON 字符串时原样送（调用方负责形状）
      body: typeof body === 'string' ? body : JSON.stringify(body ?? {}),
      signal: ctrl.signal,
      // 不传 credentials：跨源请求默认不带 cookie。
      // 重定向也不额外处理：浏览器在**跨源重定向**时会自己删掉 Authorization，
      // 所以 baseUrl 里的开放重定向不会把密钥转到别的站点。
    })
  } catch (e) {
    release()
    throw classify(e)
  }

  const reader = resp.body ? resp.body.getReader() : null

  async function* bodyStream(): AsyncGenerator<Uint8Array> {
    try {
      if (!reader) return
      for (;;) {
        let step: ReadableStreamReadResult<Uint8Array>
        try {
          step = await reader.read()
        } catch (e) {
          throw classify(e)
        }
        if (step.done) return
        // 字节按原样交出去，**不做任何分帧**：分帧是 sse.ts 的事
        if (step.value && step.value.byteLength > 0) yield step.value
      }
    } finally {
      release()
      // 调用方提前收工（解析到 [DONE] 就 break）时也要把这条连接关掉
      try { await reader?.cancel() } catch { /* 忽略 */ }
    }
  }

  return { status: resp.status, statusText: resp.statusText, body: bodyStream() }
}

/**
 * 停止当前这一轮（页面点"停止"、或页面卸载时）。
 *
 * ⚠ 这是"**停止等待**"，不是"撤回请求"：请求早已发到服务商那边，
 * 该计费的照旧计费。这里能保证的只是不再继续读、不再继续开新请求。
 */
export function relayCancelAll(): void {
  for (const c of [...active]) {
    try { c.abort() } catch { /* 忽略 */ }
  }
}

/** 页面里还有没有在飞的请求 */
export function relayBusy(): boolean {
  return active.size > 0
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
