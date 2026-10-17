/**
 * userFn.js — 用户自定义函数（`f(x)=e^x`）的定义收集与调用展开。
 *
 * 为什么必须在前端做（证据见 docs/PLAN-plot-user-functions.md §1）：
 * 引擎把"未知标识符紧跟 `(`"一律当隐式乘法 —— `to_engine_expr("f(x)")` → `"f*(x)"`。
 * 这条规则**不能改**：`x(x+1)`、`2x`、`x²` 全靠它，宽松化会打断合法输入。
 * 所以送引擎前必须让 `f(` 消失：本模块把它展开成定义体。
 *
 * 展开是**纯文本替换**，不做数学化简 —— 引擎那边会再规范化一次。
 * 展开的正确性靠三条：
 *   ① 实参非原子时整体加括号（`f(a+1)` 代入 `x^2` 必须是 `(a+1)^2`，不是 `a+1^2`）；
 *   ② 括号必须**扫描配平**（`f(g(x))` 用正则 `[^)]*` 会被截断）；
 *   ③ 标识符按**整词**匹配（`af(x)` 里的 `a` 不能被当成 `a` 变量）。
 */
"use strict";
import { isKnownName } from "./knownNames.js";

const IDENT_START = /[A-Za-z_]/;
const IDENT_CHAR = /[A-Za-z0-9_]/;

/**
 * 解析定义行 `name(arg)=body`。不是定义返回 null。
 * ⚠ 只认**单形参**：`f(x,y)=…` 需要引擎级语言能力（见 PLAN §8），不做。
 */
export function parseDefinition(text) {
  const t = String(text || "").trim();
  const m = t.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*=\s*([^=<>≤≥]+)$/);
  if (!m) return null;
  const name = m[1];
  const arg = m[2];
  const body = m[3].trim();
  if (!body) return null;
  if (name === arg) return { name, arg, body, error: `形参与函数名不能相同：${name}` };
  if (isKnownName(name)) return { name, arg, body, error: `${name} 是内置函数/常量，不能重定义` };
  return { name, arg, body, error: null };
}

/** 从行文本收集定义（后定义覆盖前定义，与 Desmos 一致；与行顺序无关） */
export function collectDefs(texts) {
  const defs = new Map();
  for (const t of texts) {
    const d = parseDefinition(t);
    if (d && !d.error) defs.set(d.name, d);
  }
  return defs;
}

const isAtomic = (s) => /^[A-Za-z_][A-Za-z0-9_]*$/.test(s) || /^\d+(\.\d+)?$/.test(s);

/** s[open] === '('，返回配对 ')' 的下标；不配对返回 -1 */
function matchParen(s, open) {
  let depth = 0;
  for (let i = open; i < s.length; i++) {
    if (s[i] === "(") depth++;
    else if (s[i] === ")" && --depth === 0) return i;
  }
  return -1;
}

/** 只替换**完整标识符**等于 name 的出现（不碰 `af` 里的 `a`） */
function replaceIdent(body, name, replacement) {
  let out = "";
  let i = 0;
  while (i < body.length) {
    if (IDENT_START.test(body[i]) && (i === 0 || !IDENT_CHAR.test(body[i - 1]))) {
      let j = i + 1;
      while (j < body.length && IDENT_CHAR.test(body[j])) j++;
      const w = body.slice(i, j);
      out += w === name ? replacement : w;
      i = j;
      continue;
    }
    out += body[i++];
  }
  return out;
}

/** 单遍展开（实参里还有调用时，交给外层的不动点迭代） */
function expandOnce(src, defs) {
  let out = "";
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    if (IDENT_START.test(c) && (i === 0 || !IDENT_CHAR.test(src[i - 1]))) {
      let j = i + 1;
      while (j < src.length && IDENT_CHAR.test(src[j])) j++;
      const name = src.slice(i, j);
      let k = j;
      while (k < src.length && /\s/.test(src[k])) k++;
      const d = defs.get(name);
      if (d && src[k] === "(") {
        const close = matchParen(src, k);
        if (close < 0) return { text: src, error: `括号不匹配：${name}(…)` };
        const arg = expandOnce(src.slice(k + 1, close), defs);
        if (arg.error) return { text: src, error: arg.error };
        // ⚠ 实参整体加括号：f(a+1) 代入 x^2 必须是 (a+1)^2，不是 a+1^2
        const wrapped = isAtomic(arg.text.trim()) ? arg.text.trim() : `(${arg.text})`;
        out += `(${replaceIdent(d.body, d.arg, wrapped)})`;
        i = close + 1;
        continue;
      }
      out += name;
      i = j;
      continue;
    }
    out += c;
    i++;
  }
  return { text: out, error: null };
}

/**
 * 展开全部用户函数调用。不动点迭代 + 层数上限：
 * 既能处理"定义套定义"，又能在 `f(x)=f(x-1)` 这种循环定义上停下来报错，
 * 而不是把渲染进程卡死。
 */
export function expandCalls(input, defs, opts = {}) {
  const maxDepth = opts.maxDepth ?? 8;
  const src = String(input ?? "");
  if (!defs || defs.size === 0) return { text: src, error: null };
  let cur = src;
  for (let depth = 0; depth < maxDepth; depth++) {
    const r = expandOnce(cur, defs);
    if (r.error) return { text: src, error: r.error };
    if (r.text === cur) return { text: cur, error: null };   // 到不动点
    cur = r.text;
  }
  return { text: src, error: `函数展开层数过深（>${maxDepth}），疑似循环定义` };
}

/** 展开后仍存在的"未知但被当函数调用"的标识符（用于报错，而不是静默画空白） */
export function findUndefinedCalls(text, defs) {
  const bad = [];
  const s = String(text ?? "");
  const re = /([A-Za-z_][A-Za-z0-9_]*)\s*\(/g;
  let m;
  while ((m = re.exec(s)) !== null) {
    const n = m[1];
    if (!isKnownName(n) && !(defs && defs.has(n)) && !bad.includes(n)) bad.push(n);
  }
  return bad;
}

/* ── 页面级"当前定义表" ──────────────────────────────────────────────────
 *
 * 为什么需要它：`parseExpr` 是纯函数、被 4 个组件共 12 处调用（PlotCanvas×3、
 * usePlotSampling×1、PlotPage×8）。把 defs 一层层透传要改 4 个组件的签名，
 * 而它们拿到的都只是"行文本"；改成**页面在渲染时登记一次**，调用点只把
 * `parseExpr` 换成 `resolveExpr` 即可。
 *
 * 代价是模块级状态。为此约束两点：① 只有绘图页会设它，而且每次 rows 变化都重设；
 * ② 组件卸载时清空（`setActiveDefs(null)`），避免跨页残留。
 * 若以后要把 defs 显式透传，`resolveExpr(raw, defs)` 已经支持传参，逐个替换即可。
 */
let activeDefs = null;

/** 设置当前页的用户函数定义表（传 null/空 Map 即清空） */
export function setActiveDefs(defs) {
  activeDefs = defs instanceof Map && defs.size ? defs : null;
}

/** 取当前页的定义表（可能为 null） */
export function getActiveDefs() {
  return activeDefs;
}

/** 登记单个用户函数名（输入过程中的第一帧就要生效，见 prepare.js 的修复逻辑） */
export function registerUserFn(name) {
  const n = String(name || "");
  if (!n || isKnownName(n)) return;
  const next = new Map(activeDefs || []);
  if (!next.has(n)) next.set(n, { name: n });   // 只登记"名字"，定义体由下次 rows 渲染补全
  activeDefs = next;
}
