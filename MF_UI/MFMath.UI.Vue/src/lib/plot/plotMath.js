/**
 * 表达式解析 / 类型识别 / 参数提取（对齐 Desmos 的输入约定）
 *
 * Desmos 行为：
 *   y = x^2          显式函数（向左到右扫描 x）
 *   x = y^2          垂直关系（按 y 扫描）
 *   r = 1 + cos(θ)   极坐标
 *   (cos t, sin t)   参数方程（也接受 (cos(t), sin(t))）
 *   (1, 2)           点
 *   y > x^2          （不等式区域，暂记为 inequality）
 *   x^2              无等号 → 自动视作 y = x^2（Desmos 会自动补 y=）
 */
"use strict";

/** 已知常量与函数名（不视作参数） */
const KNOWN = new Set([
  "pi", "e", "tau", "inf", "nan", "true", "false",
  "sin", "cos", "tan", "csc", "sec", "cot",
  "asin", "acos", "atan", "acsc", "asec", "acot",
  "sinh", "cosh", "tanh", "asinh", "acosh", "atanh",
  "sqrt", "cbrt", "abs", "exp", "log", "ln", "log2", "log10",
  "floor", "ceil", "round", "sign", "max", "min", "mod", "pow",
  "factorial", "gamma", "erf",
  // Desmos 常用简写
  "arcsin", "arccos", "arctan",
]);

/**
 * 归一化为引擎可解析的表达式：**只做纯字面的字符替换**（全角 → 半角、×÷− → * / -）。
 *
 * ⚠ 这里刻意不做任何"算符/常量改写"，因为那些改写会改数学语义。两笔历史教训：
 *   ① 插隐式乘号（`2x` → `2*x`、`)x` → `)*x`）：引擎把隐式乘法绑得比除号更紧，
 *      `1/2x` = 1/(2x) = 0.125、`1/2(x+1)` = 1/(2(x+1)) = 0.125、`1/(x+1)(x-1)` 同理；
 *      本地插了 `*` 就变成 `1/2*x` = 2（x=4 时差 16 倍）。三个页面（2D/3D/向量场）
 *      都走这条本地路径，于是"同一个输入在不同页面画出不同函数"。
 *   ② 替换希腊字母（`π` → `pi`）：`πx` 会被粘成标识符 `pix` 而解析失败。
 * 实测引擎自己就认这些课本写法：`π`=3.14159、`πx`=2π（x=2）、`2π`、`x²`、`1/2π`、
 * `θ` → 变量 theta。所以**算符与常量的语义只在引擎一处定义**，界面不参与。
 */
export function toEngineExpr(text) {
  let s = String(text || "").trim();
  // 全角 → 半角
  s = s.replace(/[\uFF01-\uFF5E]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xfee0));
  s = s.replace(/×/g, "*").replace(/÷/g, "/").replace(/−/g, "-");
  return s;
}

/** 供测试/排障：把本地归一化的结果拿出来看（CDP 里够不到模块作用域） */
export function initPlotMathHook() {
  try { window.__mfToEngineExpr = toEngineExpr; } catch { /* 忽略 */ }
}

/** 提取标识符（区分"函数名"与"变量"） */
function identifiers(text) {
  const out = [];
  const re = /[a-zA-Z_][a-zA-Z0-9_]*/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    const name = m[0];
    const after = text.slice(m.index + name.length);
    const isCall = /^\s*\(/.test(after);
    out.push({ name, isCall, index: m.index });
  }
  return out;
}

/**
 * 提取自由参数（除自变量外的变量），对齐 Desmos「自动生成滑块」的行为。
 * @param {string} text 用户输入（原始写法）
 * @param {string[]} freeVars 自变量候选（如 explicit → ["x"]）
 */
export function extractParams(text, freeVars = ["x"]) {
  const seen = new Set();
  const out = [];
  for (const { name, isCall } of identifiers(text)) {
    if (isCall) continue;                    // 函数名
    if (KNOWN.has(name)) continue;           // 常量/函数
    if (freeVars.includes(name)) continue;   // 自变量
    if (seen.has(name)) continue;
    seen.add(name);
    out.push(name);
  }
  return out;
}

/**
 * 识别表达式类型并给出引擎求值所需信息。
 * @returns {{type:string, valid:boolean, error:string|null, var:string, body:string,
 *            radius:string|null, xsExpr:string|null, ysExpr:string|null,
 *            params:string[], display:string}}
 */
export function parseExpr(raw) {
  const text = String(raw || "").trim();
  const base = {
    type: "explicit",
    valid: false,
    error: null,
    var: "x",
    body: "",
    radius: null,
    xsExpr: null,
    ysExpr: null,
    params: [],
    display: text,
  };
  if (!text) return { ...base, error: null };

  // ① 参数方程 / 点：(expr, expr)
  const parenPair = text.match(/^\(\s*([^,]+?)\s*,\s*([^,]+?)\s*\)$/);
  if (parenPair) {
    const [, a, b] = parenPair;
    const aHasT = /(^|[^a-zA-Z_])t([^a-zA-Z_]|$)/.test(a);
    const bHasT = /(^|[^a-zA-Z_])t([^a-zA-Z_]|$)/.test(b);
    const aConst = !/[a-zA-Z_]/.test(a.replace(/[a-zA-Z_]+/g, (w) => (KNOWN.has(w) ? "" : w)));
    const bConst = !/[a-zA-Z_]/.test(b.replace(/[a-zA-Z_]+/g, (w) => (KNOWN.has(w) ? "" : w)));
    if (aHasT || bHasT) {
      return {
        ...base,
        type: "parametric",
        valid: true,
        var: "t",
        xsExpr: toEngineExpr(a),
        ysExpr: toEngineExpr(b),
        params: extractParams(text, ["t"]),
      };
    }
    if (aConst && bConst) {
      return { ...base, type: "point", valid: true, var: "", body: text, params: [] };
    }
  }

  // ② 带等号/不等号
  const m = text.match(/^([^=<>≤≥]+)(=|>|<|≥|≤|>=|<=)(.+)$/);
  if (m) {
    const lhs = m[1].trim();
    let op = m[2];
    const rhs = m[3].trim();
    if (op === ">=") op = "≥";
    if (op === "<=") op = "≤";
    if (op !== "=") {
      // 不等式：区分「以 y 为界」(y > f(x)) 与「以 x 为界」(x < g(y))，以及二元区域
      const flip = { ">": "<", "<": ">", "≥": "≤", "≤": "≥" };
      if (/^y$/i.test(lhs)) {
        return {
          ...base, type: "inequality", valid: true, axis: "y", op,
          boundary: toEngineExpr(rhs), var: "x",
          params: extractParams(rhs, ["x"]),
        };
      }
      if (/^x$/i.test(lhs)) {
        return {
          ...base, type: "inequality", valid: true, axis: "x", op,
          boundary: toEngineExpr(rhs), var: "y",
          params: extractParams(rhs, ["y"]),
        };
      }
      // 反向写法 f(x) > y 等价于 y < f(x)
      if (/^y$/i.test(rhs)) {
        return {
          ...base, type: "inequality", valid: true, axis: "y", op: flip[op] || "<",
          boundary: toEngineExpr(lhs), var: "x",
          params: extractParams(lhs, ["x"]),
        };
      }
      if (/^x$/i.test(rhs)) {
        return {
          ...base, type: "inequality", valid: true, axis: "x", op: flip[op] || "<",
          boundary: toEngineExpr(lhs), var: "y",
          params: extractParams(lhs, ["y"]),
        };
      }
      // 二元区域（如 x^2+y^2 < 4）：由二维网格扫描判定
      return {
        ...base, type: "region", valid: true, axis: "xy", op,
        body: toEngineExpr(`(${lhs})-(${rhs})`), var: "x",
        params: extractParams(text, ["x", "y"]),
      };
    }
    // 极坐标 r = f(θ)：参数从右值提取（避免把 r 本身当作参数）
    if (/^r$/i.test(lhs)) {
      return {
        ...base,
        type: "polar",
        valid: true,
        var: "theta",
        radius: toEngineExpr(rhs),
        params: extractParams(rhs, ["theta"]),
      };
    }
    // 垂直关系 x = f(y)：参数从右值提取
    if (/^x$/i.test(lhs)) {
      return {
        ...base,
        type: "vertical",
        valid: true,
        var: "y",
        body: toEngineExpr(rhs),
        params: extractParams(rhs, ["y"]),
      };
    }
    // 显式 y = f(x)：参数从右值提取（左侧的 y 不是参数）
    if (/^y$/i.test(lhs)) {
      return {
        ...base,
        type: "explicit",
        valid: true,
        var: "x",
        body: toEngineExpr(rhs),
        params: extractParams(rhs, ["x"]),
      };
    }
    // 其它等式（隐式方程）→ 记作 implicit，暂按 y= 处理不了则标记
    return {
      ...base,
      type: "implicit",
      valid: true,
      var: "x",
      body: toEngineExpr(`(${lhs})-(${rhs})`),
      params: extractParams(text, ["x", "y"]),
    };
  }

  // ③ 无等号 → Desmos 自动视作 y = expr
  return {
    ...base,
    type: "explicit",
    valid: true,
    var: "x",
    body: toEngineExpr(text),
    params: extractParams(text, ["x"]),
  };
}

/** 简易合法性检查：括号配对 + 空表达式 */
export function validate(text) {
  const t = String(text || "").trim();
  if (!t) return null;
  let depth = 0;
  for (const c of t) {
    if (c === "(") depth++;
    else if (c === ")") depth--;
    if (depth < 0) return "括号不匹配";
  }
  if (depth !== 0) return "括号不匹配";
  return null;
}
