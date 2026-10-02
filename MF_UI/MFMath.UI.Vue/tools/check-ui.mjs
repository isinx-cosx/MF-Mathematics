/**
 * check-ui.mjs — 教程与键盘的构建期自检（无需浏览器）
 *
 * 这是在还 v1 的一笔债：v1 的 66 个引导步骤里有 34 个目标控件**根本不存在**，
 * 而 walkthrough 找不到控件时只是 `_current_step += 1; 递归`（静默跳过），
 * 于是教程 05 与 11 每一步都失效、点一下遮罩就消失，**却仍被标记成"已完成"**。
 * 这类错误在运行时几乎不可察觉，必须在构建期拦下来。
 *
 * 五项断言：
 *   1. 每个教程步骤的 target 要么在源码里真有 data-tour，要么在 PENDING 里写明理由；
 *   2. PENDING 里不留过时条目（教程已不引用它了，说明该删）；
 *   3. 键盘键数 = 126（与 v1 一致），且插入的 LaTeX 里没有残留的 ▢ 占位符、
 *      `\begin{...}` 环境都配了 `\end{...}`（v1 的 `\begin{pmatrix}` 就是缺后半截）；
 *   4. 教程数据的字段合法性（actionType 取值、步骤/示例/FAQ 完整性）；
 *   5. 引擎映射表里没有重复键（JS 后者胜，前面的会变成"改了没反应"的死条目）。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { PENDING, REGISTERED } from "../src/lib/tutorial/targets.js";
import { ALL_KEYS, KEY_COUNT, V1_KEY_COUNT, CATEGORIES } from "../src/lib/math/keypadSymbols.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(HERE, "..", "src");

const problems = [];
const warnings = [];

/* ── 1. 收集源码里真实存在的 data-tour ─────────────────────────────────── */
function collectSourceTargets() {
  const found = new Map(); // name -> 文件
  const walk = (dir) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) { walk(p); continue; }
      if (!/\.(vue|js)$/.test(e.name)) continue;
      if (p.includes(`${path.sep}tutorials${path.sep}`)) continue;
      const text = fs.readFileSync(p, "utf8");
      // 静态：data-tour="name"；动态：:data-tour="cond ? 'name' : undefined"
      // 名字可能不含点号（plot_canvas、geometry_canvas），所以不能靠点号筛；
      // 同时只认引号里的字面量，避免把动态表达式里的 g.id / undefined 当成目标名。
      for (const m of text.matchAll(/\s:?data-tour="([^"]*)"/g)) {
        const value = m[1];
        const literals = [...value.matchAll(/'([^']+)'|"([^"]+)"/g)];
        const names = literals.length ? literals.map((q) => q[1] ?? q[2]) : [value.trim()];
        for (const s of names) {
          if (!s || s === "undefined") continue;
          if (!found.has(s)) found.set(s, path.relative(SRC, p));
        }
      }
    }
  };
  walk(SRC);
  return found;
}

const sourceTargets = collectSourceTargets();
const tutorials = JSON.parse(fs.readFileSync(path.join(SRC, "tutorials", "tutorials.json"), "utf8")).tutorials;

/* ── 2. 教程 target 覆盖 ───────────────────────────────────────────────── */
const usedTargets = new Map();
for (const t of tutorials) {
  for (const s of t.steps) usedTargets.set(s.target, (usedTargets.get(s.target) || 0) + 1);
}

for (const [name, count] of usedTargets) {
  const inSource = sourceTargets.has(name);
  const pending = Object.prototype.hasOwnProperty.call(PENDING, name);
  if (!inSource && !pending) {
    problems.push(`教程 target 「${name}」（${count} 处）既不在源码的 data-tour 里，也没写进 PENDING 说明理由`);
  }
  if (inSource && pending) {
    // 两边都占：说明界面已经做出来了，PENDING 该删了
    warnings.push(`「${name}」源码里已注册 data-tour，但 PENDING 里还有它 —— 请从 PENDING 删除`);
  }
}
for (const name of Object.keys(PENDING)) {
  if (!usedTargets.has(name)) {
    problems.push(`PENDING 里的「${name}」已没有任何教程步骤引用 —— 属于过时条目，请删除`);
  }
}
for (const name of REGISTERED) {
  if (!sourceTargets.has(name)) {
    problems.push(`REGISTERED 里声明了「${name}」，但源码里找不到对应的 data-tour`);
  }
}

/* ── 3. 键盘 ───────────────────────────────────────────────────────────── */
if (KEY_COUNT !== V1_KEY_COUNT) {
  problems.push(`键盘键数 ${KEY_COUNT} ≠ v1 的 ${V1_KEY_COUNT}`);
}
for (const c of CATEGORIES) {
  if (!c.name || !c.rows.length) problems.push(`分类 ${c.id} 缺少名称或键区`);
}
for (const k of ALL_KEYS) {
  if (!k.label) problems.push(`有键缺少键面文字（cat=${k.cat}）`);
  if (!k.latex) problems.push(`键「${k.label}」缺少插入值`);
  if (k.latex.includes("▢")) problems.push(`键「${k.label}」的插入值里还残留 ▢ 占位符：${k.latex}`);
  if (k.latex.includes("\\begin{")) {
    const env = k.latex.match(/\\begin\{(\w+)\}/)[1];
    if (!k.latex.includes(`\\end{${env}}`)) {
      problems.push(`键「${k.label}」的 \\begin{${env}} 没有配对的 \\end（v1 就是这个毛病）`);
    }
  }
}
const cats = CATEGORIES.map((c) => c.name).join(",");
if (cats !== "基础运算,微积分,线性代数,希腊字母,概率统计,常用模板") {
  problems.push(`键盘分类的名称或顺序与 v1 不一致：${cats}`);
}

/* ── 4. 教程数据字段合法性 ─────────────────────────────────────────────── */
const ACTIONS = new Set([null, "click", "type", "select", "wait"]);
for (const t of tutorials) {
  if (!t.version) problems.push(`${t.id}: 缺少内容指纹 version`);
  for (const s of t.steps) {
    if (!ACTIONS.has(s.actionType)) problems.push(`${t.id} 步骤 ${s.index}: actionType 非法（${s.actionType}）`);
    if (!["rect", "circle"].includes(s.highlight)) problems.push(`${t.id} 步骤 ${s.index}: highlight 非法`);
    if (!["top", "bottom", "left", "right"].includes(s.placement)) problems.push(`${t.id} 步骤 ${s.index}: placement 非法`);
  }
}

/* ── 5. 引擎映射表：不许有重复键（JS 后者胜，前面的会变成"改了没反应"的死条目）──
 * 实测教训：`engineMapExtra.js` 里 `Laurent级数` 的 VAR_SPECS 重复了一次，
 * 后面那条丢了 `展开中心 z0` 字段且**生效**，于是"展开项数"的值被当成展开中心
 * 喂给引擎（z0=[4]），用户改字段也看不出问题。这类重复必须在构建期拦下来。 */
function checkDuplicateKeys(file) {
  const text = fs.readFileSync(file, "utf8");
  for (const name of ["RAW_MAP", "RAW_VAR_SPECS", "EXTRA_MAP", "EXTRA_VAR_SPECS"]) {
    const at = text.indexOf(`const ${name} = `);
    if (at < 0) continue;
    const brace = text.indexOf("{", at);
    let i = brace, depth = 0, end = -1;
    for (; i < text.length; i++) {
      const c = text[i];
      if (c === '"') {
        i++;
        while (i < text.length && text[i] !== '"') { if (text[i] === "\\") i++; i++; }
        continue;
      }
      if (c === "{" || c === "[") depth++;
      else if (c === "}" || c === "]") { depth--; if (depth === 0) { end = i; break; } }
    }
    const body = text.slice(brace + 1, end);
    const keys = [];
    let d = 0;
    for (let k = 0; k < body.length; k++) {
      const c = body[k];
      if (c === '"') {
        let j = k + 1, name2 = "";
        while (j < body.length && body[j] !== '"') {
          if (body[j] === "\\") { name2 += body[j + 1]; j += 2; continue; }
          name2 += body[j]; j++;
        }
        if (d === 0 && /^\s*:/.test(body.slice(j + 1))) keys.push(name2);
        k = j;
        continue;
      }
      if (c === "{" || c === "[") d++;
      else if (c === "}" || c === "]") d--;
    }
    const seen = new Map();
    for (const k of keys) seen.set(k, (seen.get(k) || 0) + 1);
    for (const [k, n] of seen) {
      if (n > 1) problems.push(`${path.basename(file)} 的 ${name} 里「${k}」重复 ${n} 次（后者胜，前面的是死条目）`);
    }
  }
}
checkDuplicateKeys(path.join(SRC, "lib", "engine", "engineMap.js"));
checkDuplicateKeys(path.join(SRC, "lib", "engine", "engineMapExtra.js"));

/* ── 输出 ──────────────────────────────────────────────────────────────── */
console.log("=".repeat(78));
console.log(`源码里注册的 data-tour：${sourceTargets.size} 个`);
console.log(`教程引用的 target    ：${usedTargets.size} 个（已实现 ${[...usedTargets.keys()].filter((n) => sourceTargets.has(n)).length}，待实现 ${Object.keys(PENDING).length}）`);
console.log(`数学键盘            ：${CATEGORIES.length} 分类 / ${KEY_COUNT} 键（v1 也是 ${V1_KEY_COUNT}）`);
console.log("=".repeat(78));

if (warnings.length) {
  console.log("\n提示：");
  for (const w of warnings) console.log("  ⚠ " + w);
}
if (problems.length) {
  console.error("\n自检失败：");
  for (const p of problems) console.error("  ✗ " + p);
  process.exit(1);
}
console.log("\n自检通过 ✔  引导目标无静默失效、键盘键位与 v1 对齐");
