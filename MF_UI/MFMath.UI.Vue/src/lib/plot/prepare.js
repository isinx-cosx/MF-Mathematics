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
  /* ⚠ 只归一化**第一段**。
   *
   * `;` 分段的约定是"第一段 = 那条表达式，后面是附带参数"，而参数可能是**关键词**：
   *   `central` / `normal` / `t` / `chi2` / `lebesgue` / `circle(0+0i,1)` / `square` …
   * 引擎的 to_engine_expr 是给**数学表达式**补隐式乘号的，它会把未知的多字母标识符
   * 拆成字母乘积：
   *   "x^2; 1; 1e-6; central"  →  "x^2; 1; 1e-6; c*e*n*t*r*a*l"
   * 于是引擎拿到 c*e*n*t*r*a*l，报「未知方法: c*e*n*t*r*a*l」。实测受影响的模式：
   *   数值求导、最优步长、p值、围道积分、Cauchy积分（样本/默认值里带关键词的那些）。
   * 后面的段一律原样透传：它们由 calcArgs 的 convertArg 按各自类型转换，
   * 而且引擎自己的解析器本来就认得 2x / (x+1)(x-1) 这类隐式乘法。
   */
  const parts = key.split(";");
  /* 纯字母的词**不归一化**：它要么是关键词（lebesgue / central / normal / parity …），
   * 要么是隐式乘法的写法（xy）。前者归一化会被拆成字母乘积、彻底失效：
   *   to_engine_expr("lebesgue") → "l*e*b*e*s*g*u*e"
   *   （实测：乘积测度那一格标签就写着"数字或 lebesgue"，用户在这儿打 lebesgue 必然踩到）
   * 后者**有引擎兜底**：符号那条路径是"先原样解析，只有拿到可疑结果才改用归一化串"，
   *   diff(xy) 直接得 y ✓，所以跳过归一化不会让它退化。
   * 含数字/运算符/括号的串（2x、(x+1)(x-1)、x^2）照旧归一化。 */
  const isBareWord = (s) => /^[A-Za-z]+$/.test(s.trim());
  const normOne = (s) => {
    if (isBareWord(s)) return s;
    const r = engineCall("to_engine_expr", { expr: s });
    return (r && !r.isError && r.value && typeof r.value.expr === "string") ? r.value.expr : s;
  };
  const out = parts.length === 1 ? normOne(key) : [normOne(parts[0]), ...parts.slice(1)].join(";");
  if (engCache.size >= MAX_CACHE) engCache.clear();
  engCache.set(key, out);
  return out;
}