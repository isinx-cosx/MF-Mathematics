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
import { isKnownName } from "./knownNames.js";

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
  /* 缓存键就用原文：修复规则不再依赖"当前登记了哪些用户函数"，
   * 只看 `name(` 长得像不像自变量/内置名（见下面的 callNames）。 */
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
  /* 引擎对"未知标识符"的处理**两种都有害**（实测，见 BUGS.md B16）：
   *   · 单字母 `f(x)`      → `f*(x)`        —— 变成 f 乘 (x)
   *   · 多字母 `zzz(2)`    → `z*z*z*(2)`    —— 被拆成字母乘积（`central` 也是这个下场）
   * 所以**不能靠"归一化之后再修回来"**：那时候串里已经没有 `f(` / `zzz(` 了（我踩过这个坑）。
   * 必须**归一化之前**先把这些调用名保护起来。
   *
   * 做法：把"长得像函数调用、但既不是内置名也不是自变量"的 `name(` 临时换成**归一化不动的
   * 内置函数名**（arcsin 这一类），送引擎归一化，再换回来。
   *   · 内置名：引擎本来就不插号、不拆分（实测 `sin(x)` 原样返回），所以换成它们最安全；
   *   · 自变量（x/y/t/r/θ…）：`x(x+1)`、`2x(x+1)` 这类合法隐式乘法**必须保持**，不保护；
   *   · 其余归一化（`\frac`、`π`、`x²`）照旧生效 —— 这正是"整段跳过归一化"方案的缺陷
   *     （那份 PLAN §4.1 的写法会把 LaTeX 转换一起跳过）。 */
  const VARISH = new Set(["x", "y", "t", "r", "u", "v", "w", "s", "n", "theta", "θ", "φ", "phi"]);
  /** 输入里"像函数调用"的名字（按原串扫，不能在归一化之后扫） */
  const callNames = (s) => {
    const out = [];
    const re = /([A-Za-z_][A-Za-z0-9_]*)\s*\(/g;
    let m;
    while ((m = re.exec(s)) !== null) {
      const n = m[1];
      if (!isKnownName(n) && !VARISH.has(n) && !out.includes(n)) out.push(n);
    }
    return out;
  };
  /* 占位用：这些名字归一化前后都不变，且相互不前缀冲突 */
  const POOL = ["arcsin", "arccos", "arctan", "asinh", "acosh", "atanh", "cbrt", "sign"];
  const normOne = (s) => {
    if (isBareWord(s)) return s;
    const names = callNames(s);
    const map = new Map();               // 占位名 → 原调用名
    let send = s;
    if (names.length) {
      const free = POOL.filter((n) => !s.includes(n));
      names.forEach((n, k) => {
        const pool = free[k];
        if (!pool) return;               // 池子用完就放弃保护（宁可退化，也不要乱替换）
        map.set(pool, n);
        send = send.replace(new RegExp(`\\b${n}(\\s*\\()`, "g"), `${pool}$1`);
      });
    }
    const r = engineCall("to_engine_expr", { expr: send });
    let got = (r && !r.isError && r.value && typeof r.value.expr === "string") ? r.value.expr : send;
    for (const [pool, n] of map) got = got.replace(new RegExp(`\\b${pool}(\\s*\\()`, "g"), `${n}$1`);
    return got;
  };
  const out = parts.length === 1 ? normOne(key) : [normOne(parts[0]), ...parts.slice(1)].join(";");
  if (engCache.size >= MAX_CACHE) engCache.clear();
  engCache.set(key, out);
  return out;
}