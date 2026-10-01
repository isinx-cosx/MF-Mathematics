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
  const fingerprint = crypto
    .createHash("sha1")
    .update(JSON.stringify({ steps, examples, faq }))
    .digest("hex")
    .slice(0, 8);
  return {
    id: t.id,
    title: t.title,
    difficulty: t.difficulty || "beginner",
    difficultyIcon: (DIFFICULTY_LABEL[t.difficulty] || DIFFICULTY_LABEL.beginner).icon,
    difficultyLabel: (DIFFICULTY_LABEL[t.difficulty] || DIFFICULTY_LABEL.beginner).label,
    category: t.category || "general",
    categoryIcon: (CATEGORY_LABEL[t.category] || CATEGORY_LABEL.general).icon,
    categoryLabel: (CATEGORY_LABEL[t.category] || CATEGORY_LABEL.general).label,
    duration: t.duration || "",
    order: typeof t.order === "number" ? t.order : 99,
    summary: t.summary || "",
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
