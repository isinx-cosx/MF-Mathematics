/**
 * prepare.js — 输入预处理（引擎侧规范化 + LaTeX）
 *
 * 引擎的 `prepare_expr` 做三件事：
 *   ① 把课本/LaTeX 写法规范化成引擎语法（cosx、2x、x²、π、√x、\frac…）
 *   ② 校验并给出**解析后的 LaTeX**
 *   ③ 说明自动改写了什么
 *
 * 界面拿它做实时预览：把"这段输入被理解成了什么"直接渲染出来。
 * 这一步的价值不只是好看——`cosx` 这类误读（旧解析器会当成变量 cosx）
 * 会在预览里立刻现形，而不用等画不出图才发现。
 *
 * 结果按文本缓存：每次按键都会调用，但不重复请求同样的字符串。
 */
import { engineCall } from "../bridge.js";

const cache = new Map();
const MAX_CACHE = 400;

/** @returns {{ok:boolean, latex:string, normalized:string, changed:boolean, notes:string[], error:string}} */
export function prepareExpr(text) {
  const key = String(text ?? "");
  const hit = cache.get(key);
  if (hit) return hit;

  const out = { ok: false, latex: "", normalized: key, changed: false, notes: [], error: "" };
  const r = engineCall("prepare_expr", { expr: key });
  if (r && !r.isError && r.value) {
    out.ok = !!r.value.ok;
    out.latex = r.value.latex || "";
    out.normalized = r.value.normalized ?? key;
    out.changed = !!r.value.changed;
    out.notes = Array.isArray(r.value.notes) ? r.value.notes : [];
    out.error = r.value.error || "";
  } else if (r && r.isError) {
    out.error = String(r.value);
  }

  if (cache.size >= MAX_CACHE) cache.clear();
  cache.set(key, out);
  return out;
}

/**
 * 把引擎返回的表达式字符串转成 LaTeX（用于渲染驻点/解/交点等结果）。
 * 解析不了时返回空串，调用方退回纯文本。
 */
const latexCache = new Map();
export function symLatex(expr) {
  const key = String(expr ?? "");
  if (latexCache.has(key)) return latexCache.get(key);
  let out = "";
  const r = engineCall("sym_latex", { expr: key });
  if (r && !r.isError && r.value && r.value.ok && r.value.latex) out = r.value.latex;
  if (latexCache.size >= MAX_CACHE) latexCache.clear();
  latexCache.set(key, out);
  return out;
}

/**
 * LaTeX → 引擎语法（MathLive 的 <math-field> 给的是 LaTeX）。
 * 只做规范化，不解析、不生成 LaTeX —— 每次按键都会调用，要尽量轻。
 */
const engCache = new Map();
export function toEngineExpr(latex) {
  const key = String(latex ?? "");
  if (engCache.has(key)) return engCache.get(key);
  let out = key;
  const r = engineCall("to_engine_expr", { expr: key });
  if (r && !r.isError && r.value && typeof r.value.expr === "string") out = r.value.expr;
  if (engCache.size >= MAX_CACHE) engCache.clear();
  engCache.set(key, out);
  return out;
}