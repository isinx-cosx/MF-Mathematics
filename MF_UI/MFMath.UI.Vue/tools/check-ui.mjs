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
import { keyFaceInfo, showsRawLatex } from "../src/lib/math/keyFace.js";
import { VIEW_CONFIGS } from "../src/lib/engine/viewConfigs.js";
import { ENGINE_MAP, ENGINE_VAR_SPECS } from "../src/lib/engine/engineMap.js";
import { EXTRA_MAP } from "../src/lib/engine/engineMapExtra.js";
import { EN } from "../src/lib/i18n/en-US.js";
import { EN_MODES } from "../src/lib/i18n/en-modes.js";
import { EN_VARS } from "../src/lib/i18n/en-vars.js";
import { EN_RESULTS } from "../src/lib/i18n/en-results.js";
import { FIELD_LABELS } from "../src/lib/engine/resultModel.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(HERE, "..", "src");

/* 与 src/lib/i18n/index.js 保持同款的合并顺序（en-US 优先） */
const DICT = { ...EN_MODES, ...EN_VARS, ...EN_RESULTS, ...EN };

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

/* ── 3b. 键面必须"看得懂"：不允许把 LaTeX 源码当文字显示 ──────────────────
 * 这是一次真实缺陷的自检：模板类键的键面本身就是 LaTeX（`\frac{▢}{▢}`、
 * `\begin{pmatrix}`），以前直接把源码画在键上，用户看到的是一串反斜杠和花括号。
 * 现在键面要么排版成数学，要么是清理过语法的可读文本 —— 两者必居其一。 */
const faceStats = { math: 0, plain: 0, override: 0, fallback: 0 };
for (const k of ALL_KEYS) {
  const face = keyFaceInfo(k.label);
  faceStats[face.reason] = (faceStats[face.reason] || 0) + 1;
  if (showsRawLatex(face)) {
    problems.push(`键面「${k.label}」仍在显示裸 LaTeX —— 用户看不懂（cat=${k.cat}）`);
  }
}
if (faceStats.math === 0) {
  problems.push("没有任何键面按数学排版：模板类键的键面很可能又退回成 LaTeX 源码了");
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

/* ── 6. 引擎模式可达性：ENGINE_MAP 里有映射的模式，必须能在某个页面上选到 ──
 *
 * 这是一次真实缺陷的自检。实测发现：**64 个**模式在 ENGINE_MAP/EXTRA_MAP 里有完整映射、
 * 引擎也实现并有测试，但 viewConfigs 的 13 个页面模式表**一个都没挂** —— 用户在页面上
 * 根本选不到（`解一元二次`/`判别式`/`韦达定理`/`化简分式` …）。代数页那 10 个已补齐。
 *
 * 它为什么藏得住：用例里 setBlock 找不到模式时只 `return 'no-mode'`，调用方不看返回值，
 * 于是"模式没切成功 → 用上一个模式算 → 结果里没有键值行"被静默吞掉，最后表现成一条
 * 完全看不懂的断言失败（cdp-calc-workspace 的 .res-key 就是这么藏了很久的）。
 *
 * 判据：每个模式要么在某页面的 modes 里，要么它映射的 fn 已由**页面上的**某个模式覆盖
 * （同一个 action 换个名字挂在页面上，不算缺口）。其余必须显式登记进 NOT_EXPOSED 并写明原因。
 */
const NOT_EXPOSED_GROUPS = [
  // ★ 现已为空：ENGINE_MAP 里**每一个**模式都能在某个页面上选到（本项自检第一次跑时是 64 个）。
  //
  // 最后离开这里的三条，修法都不是"补个入口"那么简单：
  //  · 「柯西定理 / 辐角原理 / Rouche 定理」：围道参数走输入框时会被引擎 to_engine_expr
  //    补隐式乘号拆坏（circle(0,1) → c*i*r*c*l*e*(0+0*i,1)）。改为走**参数弹窗**
  //    （普通 <input>，转换走 calcArgs 自带的透传版 toEngineExpr），并把 args 里的
  //    func/f **重排到 contour 前面**（声明顺序决定谁吃输入框第一段），再挂回复分析页。
  //  · 「空间完备性」：引擎要的是二维数组（vector<vector<double>>），而参数类型声明成了 `?`
  //    → 前端把它转成字符串 → 引擎报"值不是数组或对象"。已声明为 matrix。
  //
  // 保留这个空数组是为了机制：将来若确有模式不该暴露，按 ["原因", ["模式名", …]] 登记；
  // 自检会**双向校验** —— 没登记的必须能在某页面上选到，登记了的必须真的选不到（否则报"过时条目"）。
];
const NOT_EXPOSED = new Map(
  NOT_EXPOSED_GROUPS.flatMap(([why, names]) => names.map((n) => [n, why])));

{
  const ALL_MODES = { ...ENGINE_MAP, ...EXTRA_MAP };
  const pageModes = new Set();
  for (const cfg of Object.values(VIEW_CONFIGS)) for (const m of cfg.modes || []) pageModes.add(m);
  const pageFns = new Set([...pageModes].map((m) => ALL_MODES[m]?.fn).filter(Boolean));

  for (const [mode, spec] of Object.entries(ALL_MODES)) {
    if (pageModes.has(mode)) continue;
    if (pageFns.has(spec.fn)) continue;          // 同 action 在页面另有名字 → 不算缺口
    if (NOT_EXPOSED.has(mode)) continue;         // 已显式登记
    problems.push(`模式「${mode}」（${spec.fn}）没有任何页面能选到，也没登记进 NOT_EXPOSED`);
  }
  // 反向：登记了却已经可达 → 过时条目（和 PENDING 的规矩一致）
  for (const [mode, why] of NOT_EXPOSED) {
    if (!ALL_MODES[mode]) {
      problems.push(`NOT_EXPOSED 里的「${mode}」在 ENGINE_MAP 里不存在（${why}）`);
      continue;
    }
    if (pageModes.has(mode) || pageFns.has(ALL_MODES[mode].fn)) {
      problems.push(`NOT_EXPOSED 里的「${mode}」现在已经能在页面上选到了 —— 过时条目，请删除`);
    }
  }
  const missing = [...new Set(Object.keys(ALL_MODES))].filter(
    (m) => !pageModes.has(m) && !pageFns.has(ALL_MODES[m]?.fn));
  console.log(`引擎模式可达性      ：映射 ${Object.keys(ALL_MODES).length} 个 / 页面并集 ${pageModes.size} 个 / ` +
    `取不到 ${missing.length} 个（已登记 ${NOT_EXPOSED.size} 个待补或无处安放）`);
}

/* ── 7. i18n：t("…") 用到的键，必须在 en-US 里有译文 ─────────────────────────
 *
 * 译文表以**中文原文为键**（见 src/lib/i18n/index.js 的说明），好处是数据层一行都不用改、
 * 可以逐条迁移；代价是"改了中文原文就等于改了 key"。那种情况下英文界面会**回退显示中文**
 * —— 不空白、不乱码，但等于漏译，而且很难被人发现。这条自检专门盯它。
 *
 * 反向（译文表里多出来的条目）**不算问题**：那可能只是别处还没包 t()，属于迁移中间态。
 * 只认"键里含中文"的调用：`t` 是个极短的名字，其它地方的普通变量 t 会误报，
 * 而本项目的翻译键就是中文原文，这个过滤足够精准。
 */
{
  const walk = (dir) => fs.readdirSync(dir, { withFileTypes: true }).flatMap((d) => {
    if (d.name === "node_modules" || d.name === "dist") return [];
    const p = path.join(dir, d.name);
    return d.isDirectory() ? walk(p) : [p];
  });

  const used = new Map();   // 键 → 首次出现的文件（用于定位）
  const files = walk(SRC).filter(
    (p) => /\.(vue|js)$/.test(p) && !p.endsWith(path.join("i18n", "en-US.js")));
  for (const f of files) {
    const text = fs.readFileSync(f, "utf8");
    for (const m of text.matchAll(/\bt\(\s*(["'])([^"'\\]*[\u4e00-\u9fff][^"'\\]*)\1/g)) {
      if (!used.has(m[2])) used.set(m[2], path.relative(SRC, f));
    }
  }

  const missing = [...used.keys()].filter((k) => !(k in EN) && !(k in EN_MODES));
  for (const k of missing) {
    problems.push(`i18n：t("${k}") 在 lib/i18n/en-US.js 里没有译文（${used.get(k)}）`);
  }
  console.log(`i18n 文案            ：已用 t() 包裹 ${used.size} 条，缺译文 ${missing.length} 条`);

  /* 8. 模式名必须全部有译文 —— t(m) 传的是**变量**，上面那条字面量自检盯不到它。
   *    模式名只在一个地方渲染（CalcView 的下拉框与结果标题），改一处即覆盖 14 个视图；
   *    但也正因为是变量，漏译会**静默回退成中文**。所以这里按 ENGINE_MAP 直接对账。 */
  const ALL = { ...ENGINE_MAP, ...EXTRA_MAP };
  const noTr = Object.keys(ALL).filter((m) => !(m in EN_MODES));
  for (const m of noTr) {
    problems.push(`i18n：模式「${m}」在 lib/i18n/en-modes.js 里没有译文（计算页下拉框会显示中文）`);
  }
  console.log(`i18n 模式名          ：${Object.keys(ALL).length} 个模式，缺译文 ${noTr.length} 个`);

  /* 9. 参数弹窗的字段标签同样要全部有译文 —— 同理，t(f[0]) 传的也是变量。 */
  const labelSet = new Set();
  for (const fields of Object.values(ENGINE_VAR_SPECS)) {
    for (const f of fields) labelSet.add(f[0]);
  }
  const labelNoTr = [...labelSet].filter((l) => !(l in EN_VARS));
  for (const l of labelNoTr) {
    problems.push(`i18n：参数弹窗字段「${l}」在 lib/i18n/en-vars.js 里没有译文`);
  }
  console.log(`i18n 弹窗字段        ：${labelSet.size} 条唯一标签，缺译文 ${labelNoTr.length} 条`);

  /* 10. 结果面板的字段标签（resultModel.js 的 FIELD_LABELS）。
   *     渲染出口只有 labelOf() 一处，但那里传的也是**变量**，字面量自检看不见 → 同样按表对账。 */
  const resNoTr = Object.values(FIELD_LABELS).filter((l) => !(l in EN_RESULTS));
  for (const l of resNoTr) {
    problems.push(`i18n：结果字段标签「${l}」在 lib/i18n/en-results.js 里没有译文`);
  }
  console.log(`i18n 结果标签        ：${Object.keys(FIELD_LABELS).length} 个字段，缺译文 ${resNoTr.length} 个`);

  /* 11. 数学键盘的分类名（6 个，渲染在 kp-tab 上）。分类名不翻译键面 —— 键面必须保持
   *     v1 的字样（keyFace.js 还要按数学排版它，改了会同时弄坏显示与肌肉记忆）。 */
  const catNoTr = CATEGORIES.map((c) => c.name).filter((n) => !(n in DICT));
  for (const n of catNoTr) problems.push(`i18n：键盘分类名「${n}」没有译文`);
  console.log(`i18n 键盘分类        ：${CATEGORIES.length} 个分类，缺译文 ${catNoTr.length} 个`);
}

/* ── 输出 ──────────────────────────────────────────────────────────────── */
console.log("=".repeat(78));
console.log(`源码里注册的 data-tour：${sourceTargets.size} 个`);
console.log(`教程引用的 target    ：${usedTargets.size} 个（已实现 ${[...usedTargets.keys()].filter((n) => sourceTargets.has(n)).length}，待实现 ${Object.keys(PENDING).length}）`);
console.log(`数学键盘            ：${CATEGORIES.length} 分类 / ${KEY_COUNT} 键（v1 也是 ${V1_KEY_COUNT}）`);
console.log(`键面可读性          ：排版 ${faceStats.math} 键 / 文字 ${faceStats.plain} 键 / 紧凑替代 ${faceStats.override} 键 / 清理后文字 ${faceStats.fallback} 键（裸 LaTeX 0 键）`);
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
console.log("\n自检通过 ✔  引导目标无静默失效、键盘键位与 v1 对齐、每个键面都看得懂");
