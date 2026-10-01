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

/** 引擎不认识的自然写法 → 引擎语法 */
const CONST_MAP = {
  "π": "pi",
  "θ": "theta",
  "∞": "inf",
};

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
 * 归一化为引擎可解析的表达式：全角符号 → 半角，π/θ → 名称。
 *
 * 幂**不再**做 `^` → `**` 的替换：2026-09 起统一使用 `^`，`**` 由引擎的归一化
 * （math_input.h）自己合并成 `^`。算符改写只发生在引擎一处，界面不参与。
 */
export function toEngineExpr(text) {
  let s = String(text || "").trim();
  // 全角 → 半角
  s = s.replace(/[\uFF01-\uFF5E]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xfee0));
  s = s.replace(/×/g, "*").replace(/÷/g, "/").replace(/−/g, "-");
  for (const [k, v] of Object.entries(CONST_MAP)) s = s.split(k).join(v);
  // 隐式乘法的常见写法（2x → 2*x, 3sin(x) → 3*sin(x), x y → x*y）
  s = s.replace(/(\d)\s*([a-zA-Z(])/g, "$1*$2");
  s = s.replace(/\)\s*([a-zA-Z(])/g, ")*$1");
  s = s.replace(/([a-zA-Z_])\s*\(/g, (m, p1) =>
    KNOWN.has(p1) || p1.length > 1 ? m : m); // 函数调用不动
  return s;
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
