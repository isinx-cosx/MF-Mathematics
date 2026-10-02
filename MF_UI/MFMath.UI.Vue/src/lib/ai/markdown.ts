/**
 * ai/markdown.ts — 受限 markdown 解析（产出 token 树，**不产出 HTML 字符串**）
 *
 * 为什么不引 marked / markdown-it + DOMPurify：
 *   那条路的形状是"库吐 HTML 字符串 → 净化 → v-html"，而 v-html 正是本项目踩过的坑
 *   （教程富文本清洗那个绕过，见 docs/FRONTEND-FIXES.md）。这里的形状是
 *   **解析成 token 树 → Vue 模板渲染**：插值天然转义，结构上不存在注入面，
 *   也就不用赌净化器写得对不对。代价是自己维护一个子集解析器，所以支持范围要写清楚。
 *
 * 支持（够模型回答用，其余一律当纯文本，不猜）：
 *   块级：段落 · 标题 1–6 · 无序/有序列表（缩进按 depth 渲染） · 围栏代码块 ·
 *         引用 · 分隔线 · 管道表格（含对齐）
 *   行内：**粗** __粗__ · *斜* _斜_ · `代码` · ~~删除~~ · [文字](链接) · 行内/独立公式
 *   **不**支持：嵌套列表的语义嵌套（只按缩进）、图片（渲染成文字，避免模型输出触发网络请求）、
 *             HTML（原样当文本）、脚注、定义列表、表格内换行
 *
 * 公式沿用同一套克制：`$...$` 里若没有字母/数字/反斜杠/运算符，就当**占位符文本**
 * （"行内 $...$"这种情况照字面显示，不能渲染成空公式）。
 */

/* ── 行内 ───────────────────────────────────────────────────────────── */

export type Inline =
  | { type: 'text'; text: string }
  | { type: 'strong'; content: Inline[] }
  | { type: 'em'; content: Inline[] }
  | { type: 'code'; text: string }
  | { type: 'strike'; content: Inline[] }
  | { type: 'math'; tex: string; display: boolean }
  | { type: 'link'; href: string; safe: boolean; content: Inline[] }

const MATHISH = /[A-Za-z0-9\\^_=+\-*/<>()[\]]/

/** 链接只放行 http/https/mailto；`javascript:`、`data:`、`file:` 一律标 unsafe */
function safeHref(href: string): boolean {
  return /^(https?:\/\/|mailto:)/i.test(String(href || "").trim())
}

/**
 * 一个正则按优先级匹配所有行内记号；没命中的部分就是文本。
 *
 * ⚠ 这里存的是**源码字符串**，不是正则对象：`parseInline` 是递归的，
 * 而带 `g` 标志的正则对象**自带 lastIndex 状态** —— 内外层共用同一个对象时，
 * 内层调用会把外层的 lastIndex 冲掉，外层 `exec` 于是可能停在原地死循环
 * （实测把渲染进程卡到 CDP 30 秒超时）。每次调用各建一个。
 */
const INLINE_SOURCE = [
  '(`[^`\\n]+`)',                       // 1 代码
  '(\\$\\$[\\s\\S]+?\\$\\$|\\$[^$\\n]+?\\$)', // 2 公式
  '(!?\\[([^\\]]*)\\]\\(([^)\\s]+)\\))', // 3/4/5 链接（含图片，图片另处理）
  '(\\*\\*[^*]+\\*\\*)',                // 6 粗体
  '(__[^_]+__)',                        // 7 粗体（下划线）
  '(~~[^~]+~~)',                        // 8 删除线
  '(\\*[^*\\n]+\\*)',                   // 9 斜体
  '(_[^_\\n]+_)',                       // 10 斜体（下划线）
].join('|')

export function parseInline(src: string): Inline[] {
  const text = String(src ?? "")
  const out: Inline[] = []
  const re = new RegExp(INLINE_SOURCE, 'g')   // ← 每次调用一个新对象（见上）
  let last = 0
  let m: RegExpExecArray | null

  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push({ type: 'text', text: text.slice(last, m.index) })
    const push = (t: Inline) => out.push(t)

    if (m[1] !== undefined) {
      push({ type: 'code', text: m[1].slice(1, -1) })
    } else if (m[2] !== undefined) {
      const raw = m[2]
      const display = raw.startsWith('$$')
      const tex = raw.slice(display ? 2 : 1, display ? -2 : -1).trim()
      // 占位符不当公式：内容里没有"像公式"的字符就原样当文本
      if (tex && MATHISH.test(tex)) push({ type: 'math', tex, display })
      else push({ type: 'text', text: raw })
    } else if (m[3] !== undefined) {
      const isImage = m[3].startsWith('!')
      const label = m[4] ?? ''
      const href = m[5] ?? ''
      if (isImage) {
        // 图片不渲染成 <img>：模型输出不该触发对任意远端地址的请求
        push({ type: 'text', text: label ? `[图片：${label}] ` : '[图片] ' })
        push({ type: 'code', text: href })
      } else {
        push({ type: 'link', href, safe: safeHref(href), content: parseInline(label) })
      }
    } else if (m[6] !== undefined || m[7] !== undefined) {
      const raw = m[6] ?? m[7] ?? ''
      push({ type: 'strong', content: parseInline(raw.slice(2, -2)) })
    } else if (m[8] !== undefined) {
      push({ type: 'strike', content: parseInline(m[8].slice(2, -2)) })
    } else if (m[9] !== undefined || m[10] !== undefined) {
      const raw = m[9] ?? m[10] ?? ''
      push({ type: 'em', content: parseInline(raw.slice(1, -1)) })
    }
    last = m.index + m[0].length
  }

  if (last < text.length) out.push({ type: 'text', text: text.slice(last) })
  return out.length ? out : [{ type: 'text', text }]
}

/* ── 块级 ───────────────────────────────────────────────────────────── */

export type Align = 'left' | 'center' | 'right'

export type Block =
  | { type: 'p'; content: Inline[] }
  | { type: 'h'; level: number; content: Inline[] }
  | { type: 'ul'; items: { depth: number; content: Inline[] }[] }
  | { type: 'ol'; items: { depth: number; n: string; content: Inline[] }[] }
  | { type: 'code'; lang: string; text: string }
  | { type: 'quote'; content: Inline[] }
  | { type: 'hr' }
  | { type: 'table'; head: Inline[][]; align: Align[]; rows: Inline[][][] }

const RE_FENCE = /^\s*(```|~~~)\s*([A-Za-z0-9_+-]*)\s*$/
const RE_HEADING = /^(#{1,6})\s+(.*)$/
const RE_HR = /^\s*(-{3,}|\*{3,}|_{3,})\s*$/
const RE_UL = /^(\s*)([-*+])\s+(.*)$/
const RE_OL = /^(\s*)(\d{1,3})[.)]\s+(.*)$/
const RE_SEP_CELL = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$/

function splitRow(line: string): string[] {
  let s = line.trim()
  if (s.startsWith('|')) s = s.slice(1)
  if (s.endsWith('|')) s = s.slice(0, -1)
  // 不处理转义的 \|：模型回答里极少见，宁可显示得笨一点也不要解析出幻觉结构
  return s.split('|').map((c) => c.trim())
}

function alignOf(sep: string): Align[] {
  return splitRow(sep).map((c) => {
    const left = c.startsWith(':')
    const right = c.endsWith(':')
    if (left && right) return 'center'
    if (right) return 'right'
    return 'left'
  })
}

/** 缩进深度（2 空格或 1 个 tab 记一层，最多 3 层） */
function depthOf(indent: string): number {
  const n = indent.replace(/\t/g, '  ').length
  return Math.min(3, Math.floor(n / 2))
}

export function parseMarkdown(src: string): Block[] {
  const lines = String(src ?? "").replace(/\r\n?/g, '\n').split('\n')
  const blocks: Block[] = []
  let i = 0

  const isBlockStart = (line: string): boolean =>
    RE_FENCE.test(line) || RE_HEADING.test(line) || RE_HR.test(line) ||
    RE_UL.test(line) || RE_OL.test(line) || /^\s*>\s?/.test(line) || /^\s*\|/.test(line)

  while (i < lines.length) {
    const line = lines[i]

    if (line.trim() === '') { i += 1; continue }

    // 围栏代码块
    const fence = line.match(RE_FENCE)
    if (fence) {
      const marker = fence[1]
      const lang = fence[2] || ''
      const buf: string[] = []
      i += 1
      while (i < lines.length && !lines[i].trim().startsWith(marker)) { buf.push(lines[i]); i += 1 }
      if (i < lines.length) i += 1   // 吃掉收尾围栏
      blocks.push({ type: 'code', lang, text: buf.join('\n') })
      continue
    }

    // 表格：本行含 | 且下一行是分隔行
    if (line.includes('|') && i + 1 < lines.length && RE_SEP_CELL.test(lines[i + 1])) {
      const head = splitRow(line).map(parseInline)
      const align = alignOf(lines[i + 1])
      const rows: Inline[][][] = []
      i += 2
      while (i < lines.length && lines[i].includes('|') && lines[i].trim() !== '') {
        rows.push(splitRow(lines[i]).map(parseInline))
        i += 1
      }
      blocks.push({ type: 'table', head, align, rows })
      continue
    }

    const h = line.match(RE_HEADING)
    if (h) { blocks.push({ type: 'h', level: h[1].length, content: parseInline(h[2]) }); i += 1; continue }

    if (RE_HR.test(line)) { blocks.push({ type: 'hr' }); i += 1; continue }

    // 引用：连续的 > 行合成一段
    if (/^\s*>\s?/.test(line)) {
      const buf: string[] = []
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) { buf.push(lines[i].replace(/^\s*>\s?/, '')); i += 1 }
      blocks.push({ type: 'quote', content: parseInline(buf.join('\n')) })
      continue
    }

    // 无序列表
    if (RE_UL.test(line)) {
      const items: { depth: number; content: Inline[] }[] = []
      while (i < lines.length && RE_UL.test(lines[i])) {
        const mm = lines[i].match(RE_UL)!
        items.push({ depth: depthOf(mm[1]), content: parseInline(mm[3]) })
        i += 1
      }
      blocks.push({ type: 'ul', items })
      continue
    }

    // 有序列表
    if (RE_OL.test(line)) {
      const items: { depth: number; n: string; content: Inline[] }[] = []
      while (i < lines.length && RE_OL.test(lines[i])) {
        const mm = lines[i].match(RE_OL)!
        items.push({ depth: depthOf(mm[1]), n: mm[2], content: parseInline(mm[3]) })
        i += 1
      }
      blocks.push({ type: 'ol', items })
      continue
    }

    // 段落：吃到空行或下一个块级开头为止
    const buf: string[] = [line]
    i += 1
    while (i < lines.length && lines[i].trim() !== '' && !isBlockStart(lines[i])) { buf.push(lines[i]); i += 1 }
    blocks.push({ type: 'p', content: parseInline(buf.join('\n')) })
  }

  return blocks
}
