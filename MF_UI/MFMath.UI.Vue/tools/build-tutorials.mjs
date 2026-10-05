/**
 * build-tutorials.mjs — 把 v1 的教程 YAML 转成前端可直接 import 的 JSON，并做严格自检。
 *
 * 为什么要自己写 YAML 子集解析器：本项目依赖里没有 js-yaml / yaml（已核对
 * node_modules），而教程 YAML 只用到极小的语法子集（顶层标量、`>` 折叠块、
 * 以及 steps/examples/faq 三个「映射列表」）。为避免引入新依赖，这里实现
 * 恰好够用的解析器——**但必须自证正确**，所以脚本内置了一张"权威数量表"：
 * 每篇教程的 step/example/faq 条数取自对 v1 的独立清点结果，任一对不上就
 * 以非零码退出。这样解析器一旦出错（例如把折叠块或列表缩进解析错），
 * 立刻暴露，而不是悄悄产出残缺教程。
 *
 * 用法：
 *   node tools/build-tutorials.mjs            # 转换 + 自检
 *   MF_TUTORIAL_SRC=<dir> node tools/build-tutorials.mjs
 *
 * 产出：
 *   src/tutorials/tutorials.json   前端 import 的数据源
 *   <v2.0>/docs/tutorials-src/*.yaml   YAML 原件留档（供比对；不参与运行）
 */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const VUE = path.resolve(HERE, "..");                       // MFMath.UI.Vue
const V2 = path.resolve(VUE, "..", "..");                   // Multifunctional-Mathematics-v2.0
const SRC = process.env.MF_TUTORIAL_SRC
  || "C:\\Users\\fsafsafsa\\Desktop\\MVS知识库\\Multifunctional系列\\Multifunctional-Mathematics\\MF_Tutorial\\tutorials";
const OUT_JSON = path.join(VUE, "src", "tutorials", "tutorials.json");
const ARCHIVE = path.join(V2, "docs", "tutorials-src");

/* ── 权威数量表（来自对 v1 的独立清点，不是从本解析器推导出来的）────────── */
const EXPECTED = [
  { order: 1, id: "quick-start", steps: 4, examples: 2, faq: 2 },
  { order: 2, id: "basic-calculation", steps: 6, examples: 5, faq: 3 },
  { order: 3, id: "plot-2d", steps: 6, examples: 4, faq: 3 },
  { order: 4, id: "ai-assistant", steps: 5, examples: 2, faq: 3 },
  { order: 5, id: "ai-steps-accelerate", steps: 5, examples: 2, faq: 2 },
  { order: 6, id: "linear-algebra", steps: 3, examples: 4, faq: 2 },
  { order: 7, id: "probability-statistics", steps: 3, examples: 3, faq: 2 },
  { order: 8, id: "numerical-analysis", steps: 3, examples: 4, faq: 2 },
  { order: 9, id: "plot-3d-complex", steps: 4, examples: 4, faq: 2 },
  { order: 10, id: "vector-field-geometry", steps: 3, examples: 4, faq: 2 },
  { order: 11, id: "math-keyboard", steps: 3, examples: 2, faq: 2 },
  { order: 12, id: "search-settings", steps: 6, examples: 2, faq: 2 },
  { order: 13, id: "themes-appearance", steps: 2, examples: 0, faq: 2 },
  { order: 14, id: "tips-and-tricks", steps: 1, examples: 2, faq: 4 },
  { order: 15, id: "complex-analysis", steps: 3, examples: 3, faq: 2 },
  { order: 16, id: "functional-analysis", steps: 3, examples: 3, faq: 2 },
  { order: 17, id: "measure-theory", steps: 3, examples: 3, faq: 2 },
  { order: 18, id: "algebraic-topology", steps: 3, examples: 3, faq: 3 },
];

/* ── v2 覆盖表：v1 教程文本里在 v2 不成立的内容 ──────────────────────────────
 *
 * 为什么不直接改 YAML 原件：原件是 v1 的留档、也是本脚本的输入，
 * 既定方针是"沿用 v1 的语义与文本，教程与 YAML 原件都不用改"。
 * 改这里的好处是**每次重新生成都生效**（`npm run check:ui` 的第一步就是本脚本，
 * 直接改 tutorials.json 会被覆盖掉），而且只换文字/指向、**不动条数** ——
 * 所以上面那张 EXPECTED 权威数量表依然成立。
 *
 * 目前只有一类需要覆盖：**「AI 加速」**。
 *   v1 在每个计算块上有那个按钮；v2 **决定不做**（见 docs/OPEN-ITEMS.md 的讨论）：
 *   · 引擎现在跑 1113 个病态用例只需 4.9 秒、最慢一例 199.6 ms、0 超时
 *     （docs/stress-scan.json）—— "本地引擎算不动"这个前提基本消失了；
 *   · 而"让模型直接计算"正是本产品唯一那条硬约束所禁止的：
 *     **AI 不得成为计算源** —— AI 的所有数值都必须来自 `engine_call`
 *     （src/lib/ai/tools.ts:310），且有端到端断言（tests/cdp-ai.mjs ⑥）。
 *   所以原文会让用户去点一个不存在的按钮，还承诺了没有任何实现的配额。
 *
 * ⚠ 索引是**数组下标（0 基）**；写错不会静默 —— 下面的"自检 3"会以非零码退出。
 * ⚠ 已实现但仍指向 ai_accel_button 的步骤必须同时**改指向**，否则
 *   check-ui.mjs 会因为"目标既无 data-tour 又不在 PENDING 里"而报错。
 */
const V2_OVERRIDES = {
  "basic-calculation": {
    steps: {
      5: {
        target: "toolbar.ai_button",
        text:
          "如果表达式特别复杂，可以让 AI 助手帮你选对引擎函数。<br>" +
          "点顶栏的「AI」打开助手 —— 它通过 engine_call 调本地引擎来算，数值始终由引擎产出。",
      },
    },
  },
  "ai-steps-accelerate": {
    title: "步骤推导与 AI 讲解",
    summary: "学习用 AI 生成详细推导步骤（每一步都由本地引擎算出），以及用 AI 提问、选对引擎函数。",
    steps: {
      4: {
        target: "ai_dialog.input",
        text:
          "拿不准一条式子该怎么算时，直接在助手里问它。<br>" +
          "它会先用 engine_find 找函数、再用 engine_call 让引擎算 —— 数值一律由引擎产出。",
      },
    },
    faq: {
      0: {
        q: "「查看步骤」里的数字是 AI 算的吗？",
        a:
          "不是。AI 只负责组织与讲解，每一步的数值都由它调用本地引擎（engine_call）算出。" +
          "这也是本产品的硬约束：AI 不得成为计算源。",
      },
      1: {
        q: "AI 功能有次数限制吗？",
        a: "按本地计数，配置 API Key 后不受限。注意所有数值计算都在本地引擎完成，不消耗 AI 额度。",
      },
    },
  },
  "tips-and-tricks": {
    faq: {
      2: {
        q: "计算太慢怎么办？",
        a:
          "先确认输入是不是过于极端（例如 (x+1)^80 这种展开量会爆炸的式子）。" +
          "引擎通常都在毫秒级完成，真正慢的是这类人为极端的输入；数值分析模块里也可以用近似方法。",
      },
    },
  },
};

/** 记录覆盖表的命中情况，供"自检 3"确认没有写错的索引 */
const overrideHits = new Set();

/** 把 v2 覆盖表应用到一篇教程上（**就地**改，保持数组引用不变） */
function applyOverrides(id, doc) {
  const spec = V2_OVERRIDES[id];
  if (!spec) return;
  if (spec.title) { doc.title = spec.title; overrideHits.add(`${id}/title`); }
  if (spec.summary) { doc.summary = spec.summary; overrideHits.add(`${id}/summary`); }
  for (const [i, ov] of Object.entries(spec.steps || {})) {
    const s = doc.steps[Number(i)];
    if (!s) continue;
    if (ov.target) s.target = ov.target;
    if (ov.text) s.text = ov.text;
    overrideHits.add(`${id}/steps/${i}`);
  }
  for (const [i, ov] of Object.entries(spec.faq || {})) {
    const f = doc.faq[Number(i)];
    if (!f) continue;
    if (ov.q) f.q = ov.q;
    if (ov.a) f.a = ov.a;
    overrideHits.add(`${id}/faq/${i}`);
  }
}

/* ── YAML 子集解析 ──────────────────────────────────────────────────────── */

const indentOf = (l) => l.length - l.trimStart().length;
const isBlank = (l) => l.trim() === "";
const isComment = (l) => l.trimStart().startsWith("#");

function scalar(raw) {
  let s = raw.trim();
  // 去掉行尾注释：只在 '#' 前有空白、且不在引号内时才当注释
  if (!/^["']/.test(s)) {
    const m = s.match(/^(.*?)\s+#\s.*$/);
    if (m) s = m[1].trim();
  }
  if (s.length >= 2 && ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'")))) {
    const inner = s.slice(1, -1);
    // 双引号里的 \" \\ \n 等转义（YAML 里教程文本用到的不多，够用即可）
    return s.startsWith('"') ? inner.replace(/\\"/g, '"').replace(/\\n/g, "\n").replace(/\\\\/g, "\\") : inner.replace(/''/g, "'");
  }
  if (/^-?\d+$/.test(s)) return Number(s);
  if (s === "true") return true;
  if (s === "false") return false;
  return s;
}

function parseBlockScalar(lines, i, parentIndent, style) {
  const collected = [];
  let contentIndent = null;
  while (i < lines.length) {
    const ln = lines[i];
    if (isBlank(ln)) { collected.push(""); i++; continue; }
    const ind = indentOf(ln);
    if (ind <= parentIndent) break;
    if (contentIndent === null) contentIndent = ind;
    collected.push(ln.slice(Math.min(contentIndent, ln.length)));
    i++;
  }
  while (collected.length && collected[collected.length - 1] === "") collected.pop();
  if (style === ">") {
    // 折叠：块内单换行 → 空格；空行 → 真换行
    let out = "";
    let prevBlank = true;
    for (const l of collected) {
      if (l === "") { out += "\n"; prevBlank = true; }
      else { out += (prevBlank ? "" : " ") + l.trim(); prevBlank = false; }
    }
    return [out.trim(), i];
  }
  return [collected.join("\n").trim(), i];
}

function parseNode(lines, i, minIndent) {
  while (i < lines.length && (isBlank(lines[i]) || isComment(lines[i]))) i++;
  if (i >= lines.length) return [null, i];
  const ind = indentOf(lines[i]);
  if (ind < minIndent) return [null, i];
  return lines[i].trimStart().startsWith("-")
    ? parseList(lines, i, ind)
    : parseMap(lines, i, ind);
}

function parseMap(lines, i, indent) {
  const out = {};
  while (i < lines.length) {
    const ln = lines[i];
    if (isBlank(ln) || isComment(ln)) { i++; continue; }
    const ind = indentOf(ln);
    if (ind < indent) break;
    if (ind > indent) throw new Error(`第 ${i + 1} 行缩进异常（期望 ${indent}，实际 ${ind}）：${ln.trim()}`);
    const content = ln.trim();
    if (content.startsWith("-")) break;
    const ci = content.indexOf(":");
    if (ci < 0) throw new Error(`第 ${i + 1} 行缺少冒号：${content}`);
    const key = content.slice(0, ci).trim();
    const rest = content.slice(ci + 1).trim();
    if (rest === "") {
      const [child, ni] = parseNode(lines, i + 1, indent + 1);
      out[key] = child;
      i = ni;
    } else if (/^[>|][-+]?$/.test(rest)) {
      const [s, ni] = parseBlockScalar(lines, i + 1, indent, rest[0]);
      out[key] = s;
      i = ni;
    } else {
      out[key] = scalar(rest);
      i++;
    }
  }
  return [out, i];
}

function parseList(lines, i, indent) {
  const arr = [];
  while (i < lines.length) {
    const ln = lines[i];
    if (isBlank(ln) || isComment(ln)) { i++; continue; }
    const ind = indentOf(ln);
    if (ind < indent) break;
    if (ind > indent) throw new Error(`第 ${i + 1} 行列表缩进异常（期望 ${indent}，实际 ${ind}）：${ln.trim()}`);
    const content = ln.trim();
    if (!content.startsWith("-")) break;
    const after = content.slice(1).trim();
    if (after === "") {
      const [child, ni] = parseNode(lines, i + 1, indent + 1);
      arr.push(child);
      i = ni;
      continue;
    }
    if (/^[^:]+:(\s|$)/.test(after)) {
      // 「- key: value」：把该行改写成 key 位于 indent+2 的普通映射行再解析
      const saved = lines[i];
      lines[i] = " ".repeat(indent + 2) + after;
      const [child, ni] = parseMap(lines, i, indent + 2);
      lines[i] = saved;
      arr.push(child);
      i = ni;
      continue;
    }
    arr.push(scalar(after));
    i++;
  }
  return [arr, i];
}

function parseYaml(text) {
  const lines = text.split(/\r?\n/);
  const [doc] = parseNode(lines, 0, 0);
  return doc;
}

/* ── 规范化 + 版本指纹 ──────────────────────────────────────────────────── */

const CATEGORY_LABEL = {
  general: { icon: "📖", label: "入门指南" },
  calculation: { icon: "🧮", label: "计算模块" },
  plot: { icon: "📊", label: "绘图系统" },
  ai: { icon: "🤖", label: "AI 功能" },
  tools: { icon: "🔧", label: "工具" },
  settings: { icon: "⚙️", label: "设置" },
};
const DIFFICULTY_LABEL = {
  beginner: { icon: "🔵", label: "入门" },
  intermediate: { icon: "🟡", label: "进阶" },
  advanced: { icon: "🟣", label: "高级" },
};

function normalize(t, file) {
  const steps = (t.steps || []).map((s, idx) => ({
    index: idx + 1,
    // ⚠️ 字段改名：v1 的 Step.action 与 Example.action 同名不同义（前者是动作类型、
    //    后者是计算操作名），YAML 里靠缩进区分。这里拆成 actionType / operation，
    //    否则前端必然把两者搞混。
    target: s.target || "",
    text: s.text || "",
    highlight: s.highlight === "circle" ? "circle" : "rect",
    placement: ["top", "bottom", "left", "right"].includes(s.placement) ? s.placement : "bottom",
    actionType: s.action || null,
    actionValue: s.action_value || "",
  }));
  const examples = (t.examples || []).map((e, idx) => ({
    index: idx + 1,
    label: e.label || "",
    expr: e.expr || "",
    mode: e.mode || "",
    operation: e.action || "",
    description: e.description || "",
  }));
  const faq = (t.faq || []).map((f) => ({ q: f.q || "", a: f.a || "" }));
  // v2 覆盖（见 V2_OVERRIDES）：必须在算内容指纹**之前**应用，
  // 否则 version 对应的不是真正发出去的那份内容（store.js 靠它判断"教程变了"）。
  const v2 = { title: t.title, summary: t.summary || "", steps, faq };
  applyOverrides(t.id, v2);
  const fingerprint = crypto
    .createHash("sha1")
    .update(JSON.stringify({ steps: v2.steps, examples, faq: v2.faq }))
    .digest("hex")
    .slice(0, 8);
  return {
    id: t.id,
    title: v2.title,
    difficulty: t.difficulty || "beginner",
    difficultyIcon: (DIFFICULTY_LABEL[t.difficulty] || DIFFICULTY_LABEL.beginner).icon,
    difficultyLabel: (DIFFICULTY_LABEL[t.difficulty] || DIFFICULTY_LABEL.beginner).label,
    category: t.category || "general",
    categoryIcon: (CATEGORY_LABEL[t.category] || CATEGORY_LABEL.general).icon,
    categoryLabel: (CATEGORY_LABEL[t.category] || CATEGORY_LABEL.general).label,
    duration: t.duration || "",
    order: typeof t.order === "number" ? t.order : 99,
    summary: v2.summary,
    // 内容指纹：教程内容一变，进行中的引导进度与"已学"标记就该失效（见 store.js）
    version: fingerprint,
    // prerequisites 在 v1 是死字段且引用了不存在的教程，这里保留原文仅供比对，不参与逻辑
    prerequisites: t.prerequisites || [],
    steps,
    examples,
    faq,
    source: file,
  };
}

/* ── 主流程 ────────────────────────────────────────────────────────────── */

if (!fs.existsSync(SRC)) {
  console.error(`找不到教程源目录：${SRC}`);
  console.error("可用 MF_TUTORIAL_SRC=<dir> 覆盖。");
  process.exit(1);
}
const files = fs.readdirSync(SRC).filter((f) => f.endsWith(".yaml")).sort();
if (files.length === 0) {
  console.error(`教程源目录里没有 .yaml：${SRC}`);
  process.exit(1);
}

const tutorials = [];
const problems = [];
for (const f of files) {
  const raw = fs.readFileSync(path.join(SRC, f), "utf8");
  let doc;
  try {
    doc = parseYaml(raw);
  } catch (e) {
    problems.push(`${f}: YAML 子集解析失败 — ${e.message}`);
    continue;
  }
  if (!doc || typeof doc !== "object" || !doc.id) {
    problems.push(`${f}: 解析结果缺少 id`);
    continue;
  }
  tutorials.push(normalize(doc, f));
}
tutorials.sort((a, b) => a.order - b.order);

/* 自检 1：数量必须与权威表逐项一致 */
if (tutorials.length !== EXPECTED.length) {
  problems.push(`教程篇数 ${tutorials.length} ≠ 期望 ${EXPECTED.length}`);
}
for (const exp of EXPECTED) {
  const got = tutorials.find((t) => t.id === exp.id);
  if (!got) { problems.push(`缺少教程 ${exp.id}`); continue; }
  const cmp = [
    ["steps", got.steps.length, exp.steps],
    ["examples", got.examples.length, exp.examples],
    ["faq", got.faq.length, exp.faq],
  ];
  for (const [what, actual, want] of cmp) {
    if (actual !== want) problems.push(`${exp.id} 的 ${what} = ${actual}，期望 ${want}`);
  }
  if (got.order !== exp.order) problems.push(`${exp.id} 的 order = ${got.order}，期望 ${exp.order}`);
}

/* 自检 1b：v2 覆盖表必须**全部命中** —— 索引写错时绝不能静默失效
 * （这个项目反复踩的就是"看起来在跑、其实没生效"这一类）。 */
for (const [tid, spec] of Object.entries(V2_OVERRIDES)) {
  if (spec.title && !overrideHits.has(`${tid}/title`)) problems.push(`v2 覆盖表未命中：${tid} 的 title`);
  if (spec.summary && !overrideHits.has(`${tid}/summary`)) problems.push(`v2 覆盖表未命中：${tid} 的 summary`);
  for (const i of Object.keys(spec.steps || {})) {
    if (!overrideHits.has(`${tid}/steps/${i}`)) problems.push(`v2 覆盖表未命中：${tid} 步骤下标 ${i}`);
  }
  for (const i of Object.keys(spec.faq || {})) {
    if (!overrideHits.has(`${tid}/faq/${i}`)) problems.push(`v2 覆盖表未命中：${tid} FAQ 下标 ${i}`);
  }
}

/* 自检 2：字段完整性（防止折叠块被解析成空串这类静默损坏） */
for (const t of tutorials) {
  if (!t.title) problems.push(`${t.id}: 缺 title`);
  if (!t.summary) problems.push(`${t.id}: summary 为空`);
  for (const s of t.steps) {
    if (!s.target) problems.push(`${t.id} 步骤 ${s.index}: 缺 target`);
    if (!s.text) problems.push(`${t.id} 步骤 ${s.index}: text 为空`);
  }
  for (const e of t.examples) {
    if (!e.label) problems.push(`${t.id} 示例 ${e.index}: 缺 label`);
    // expr 允许为空：绘图/设置/AI 类示例本来就没有表达式（v1 里就是 expr:""，
    // 已抽查 10-vector-field-geometry / 12-search-settings / 14-tips-and-tricks 确认）。
    // 但那时必须有 mode 或 description，否则这条示例在界面上没有任何可读内容。
    if (!e.expr && !e.mode && !e.description) {
      problems.push(`${t.id} 示例 ${e.index}: expr/mode/description 全为空`);
    }
  }
  for (const [i, f] of t.faq.entries()) {
    if (!f.q || !f.a) problems.push(`${t.id} FAQ ${i + 1}: q/a 为空`);
  }
}

const counts = {
  tutorials: tutorials.length,
  steps: tutorials.reduce((n, t) => n + t.steps.length, 0),
  examples: tutorials.reduce((n, t) => n + t.examples.length, 0),
  faq: tutorials.reduce((n, t) => n + t.faq.length, 0),
};

function printTable() {
  console.log("order  id                              steps ex  faq  dur");
  for (const t of tutorials) {
    console.log(
      String(t.order).padStart(4),
      " ", t.id.padEnd(30),
      String(t.steps.length).padStart(4),
      String(t.examples.length).padStart(3),
      String(t.faq.length).padStart(4),
      "  " + t.duration
    );
  }
}

console.log("=".repeat(78));
console.log(`源目录：${SRC}`);
console.log(`解析到 ${counts.tutorials} 篇 / ${counts.steps} 步 / ${counts.examples} 示例 / ${counts.faq} FAQ`);
console.log("=".repeat(78));
printTable();

if (problems.length) {
  console.error("\n自检失败：");
  for (const p of problems) console.error("  ✗ " + p);
  process.exit(1);
}

fs.mkdirSync(path.dirname(OUT_JSON), { recursive: true });
fs.writeFileSync(
  OUT_JSON,
  JSON.stringify(
    { generatedFrom: "MF_Tutorial/tutorials/*.yaml", categories: CATEGORY_LABEL, tutorials },
    null,
    2
  ) + "\n",
  "utf8"
);
fs.mkdirSync(ARCHIVE, { recursive: true });
for (const f of files) fs.copyFileSync(path.join(SRC, f), path.join(ARCHIVE, f));

console.log("\n自检通过 ✔");
console.log(`  写出 ${path.relative(V2, OUT_JSON)} （${(fs.statSync(OUT_JSON).size / 1024).toFixed(1)} KB）`);
console.log(`  留档 ${path.relative(V2, ARCHIVE)} （${files.length} 个 YAML 原件）`);
