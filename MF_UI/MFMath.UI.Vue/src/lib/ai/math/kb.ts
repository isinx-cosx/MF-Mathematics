/**
 * ai/math/kb.ts — 本地知识库（`search_knowledge` 的实现）
 *
 * math-assistant 的 README 给了三条接法：Rust 宿主调 `math_rag.dll`、打包 JSON 走前端、
 * 或起 HTTP sidecar。这里选**打包走前端**那条 —— 理由是它零宿主改动、离线可用、
 * 而且本软件本来就有一份成型的教材型内容：`src/tutorials/tutorials.json`
 * （18 篇教程 + 每篇的步骤与 FAQ，构建期由 `tools/build-tutorials.mjs` 生成）。
 *
 * 索引方式刻意保持"可解释"：不引第三方检索库，只做
 *
 *   · 词项切分：拉丁词（`diff` / `matrix`）+ 中文二元组（"导数""矩阵"这类）；
 *   · 打分：命中标题 ×3、命中正文 ×1，整串命中再 +5；按词项数归一化到 0~1；
 *   · 排序：分数降序、同分按标题字典序（**确定性**，便于用例断言）。
 *
 * 局限（写明，不假装是语义检索）：同义词未扩展、长句问法召回弱。
 * 真要上向量检索，把 `searchKb` 换成宿主侧的 `mrag_search` 即可 —— 工具层不关心谁实现。
 */
import data from "../../../tutorials/tutorials.json";
import type { KnowledgeHit } from "./mfmath.ts";

interface Entry {
  id: string;
  title: string;
  topic: string;
  text: string;
  /** 预拼接的小写检索串（标题 + 正文），避免每次查询重复拼 */
  hay: string;
  /** 标题单独的小写串，命中权重更高 */
  hayTitle: string;
}

/** 一条教程/FAQ 的正文上限（KB 里存全文会让单条命中就把上下文塞满） */
const MAX_ENTRY_TEXT = 900;

/** 教程步骤里带 `<br>` / `<b>` 这类标记（v1 YAML 里就是 HTML 片段），进 KB 前先剥掉 */
function stripTags(s: unknown): string {
  return String(s ?? "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

function clip(s: string, max = MAX_ENTRY_TEXT): string {
  const text = String(s ?? "").replace(/\s+/gu, " ").trim();
  const points = Array.from(text);
  return points.length <= max ? text : `${points.slice(0, max).join("")}…`;
}

function buildEntries(): Entry[] {
  const out: Entry[] = [];
  const tutorials = Array.isArray((data as any)?.tutorials) ? (data as any).tutorials : [];

  for (const t of tutorials) {
    const steps = Array.isArray(t?.steps) ? t.steps : [];
    const faqs = Array.isArray(t?.faq) ? t.faq : [];
    const stepText = steps
      .map((s: any) => {
        // 步骤里只有 text（含 HTML 片段）；title/detail 是别的数据源的写法，留着兼容
        const title = stripTags(s?.title ?? "").trim();
        const body = stripTags(s?.detail ?? s?.body ?? s?.text ?? "").trim();
        return [title, body].filter(Boolean).join("：");
      })
      .filter(Boolean)
      .join("\n");
    const faqText = faqs
      .map((f: any) => [stripTags(f?.q).trim(), stripTags(f?.a).trim()].filter(Boolean).join("："))
      .filter(Boolean)
      .join("\n");

    const text = clip([stripTags(t?.summary), stepText, faqText].filter(Boolean).join("\n"));
    if (!text) continue;
    const title = String(t?.title ?? t?.id ?? "").trim();
    out.push({
      id: `tut:${t?.id ?? out.length}`,
      title,
      topic: String(t?.categoryLabel ?? t?.category ?? "教程"),
      text,
      hay: `${title}\n${text}`.toLowerCase(),
      hayTitle: title.toLowerCase(),
    });

    // FAQ 单独成条：问法往往比教程标题更接近学生的原话
    for (let i = 0; i < faqs.length; i += 1) {
      const q = stripTags(faqs[i]?.q).trim();
      const a = stripTags(faqs[i]?.a).trim();
      if (!q || !a) continue;
      out.push({
        id: `faq:${t?.id ?? out.length}#${i}`,
        title: q,
        topic: String(t?.categoryLabel ?? t?.category ?? "常见问题"),
        text: clip(a),
        hay: `${q}\n${a}`.toLowerCase(),
        hayTitle: q.toLowerCase(),
      });
    }
  }
  return out;
}

const ENTRIES = buildEntries();

/** 中文二元组 + 拉丁词；中文单字不作为词项（噪音太大） */
export function tokenize(query: string): string[] {
  const q = String(query ?? "").toLowerCase();
  const terms = new Set<string>();
  for (const m of q.matchAll(/[a-z][a-z0-9_]{1,}/g)) terms.add(m[0]);
  const cjk = q.replace(/[^\u4e00-\u9fff]+/g, " ");
  for (const run of cjk.split(/\s+/)) {
    if (run.length === 1) continue; // 单字太泛
    for (let i = 0; i + 2 <= run.length; i += 1) terms.add(run.slice(i, i + 2));
  }
  return [...terms];
}

function scoreOf(entry: Entry, terms: string[], whole: string): number {
  if (terms.length === 0) return 0;
  let hit = 0;
  for (const term of terms) {
    if (entry.hayTitle.includes(term)) hit += 3;
    else if (entry.hay.includes(term)) hit += 1;
  }
  if (whole && entry.hay.includes(whole)) hit += 5;
  // 归一化：单个词项最多拿 3 分（标题全命中），保证分数落在 0~1
  const max = terms.length * 3 + 5;
  return Math.min(1, hit / max);
}

/**
 * 检索本地知识库。返回按分数降序的命中（同分按标题字典序，保证结果确定）。
 * 没有任何命中时返回空数组 —— 由工具层回一句「没命中，换术语」。
 */
export function searchKb(query: string, topK = 3): KnowledgeHit[] {
  const q = String(query ?? "").trim();
  if (!q) return [];
  const whole = q.toLowerCase().replace(/\s+/g, "");
  const terms = tokenize(q);
  if (terms.length === 0) return [];

  const scored = ENTRIES.map((e) => ({ e, score: scoreOf(e, terms, whole) }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score || a.e.title.localeCompare(b.e.title));

  return scored.slice(0, Math.max(1, Math.min(10, topK))).map(({ e, score }) => ({
    id: e.id,
    title: e.title,
    topic: e.topic,
    text: e.text,
    score: Math.round(score * 1000) / 1000,
  }));
}

/** 给用例/排障用：条目数与几条样例标题 */
export function kbStats(): { count: number; sample: string[] } {
  return { count: ENTRIES.length, sample: ENTRIES.slice(0, 5).map((e) => e.title) };
}
