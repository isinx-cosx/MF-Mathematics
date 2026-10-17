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

/* 已知常量/函数名在 knownNames.js（`userFn.js` 也要用，见那里的说明）。
 * 依赖方向：knownNames ← userFn ← plotMath，单向，没有循环。 */
import { KNOWN, isKnownName } from "./knownNames.js";
import {
  parseDefinition, expandCalls, findUndefinedCalls, getActiveDefs,
} from "./userFn.js";

/** 这个名字是不是内置常量/函数（`prepare.js` 也要判，所以从这里再导出一次） */
export { isKnownName };

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

  /* ⓪ 用户函数定义 `f(x)=body` —— 必须**先于**所有等式分支。
   * 否则它会被当成隐式方程 `(f(x))-(body)`，而引擎会把 `f(` 拆成 `f*(`，
   * 于是方程里多出一个永不取值的符号 f，采样全 null、曲线静默消失（PLAN §1.4）。
   * 定义行本身**不绘制**（见 PlotPage/PlotCanvas 对 type==="definition" 的处理）。 */
  const def = parseDefinition(text);
  if (def) {
    if (def.error) return { ...base, type: "definition", valid: false, error: def.error };
    return {
      ...base,
      type: "definition",
      valid: true,
      var: def.arg,
      fnName: def.name,        // 供页面跳过绘制 / 图例显示
      argName: def.arg,
      body: toEngineExpr(def.body),
      // 参数从定义体取并排除形参：`f(x)=ax^2` → ["a"]；`f(x)=e^x` → []
      params: extractParams(def.body, [def.arg]).filter((n) => n !== def.name),
    };
  }

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

/**
 * `parseExpr` + 用户函数展开 —— **页面应当用它，而不是 parseExpr**。
 *
 * 展开发生在送引擎**之前**，所以引擎永远收不到裸 `f(`（引擎会把它拆成 `f*(`）。
 * 展开后若仍有"未定义但被当函数调用"的名字，**明确报错**而不是让引擎静默返回全 null
 * （静默空白是这个 bug 今天唯一能被用户看见的入口，不能继续留着）。
 *
 * @param raw 行文本（引擎语法；undefined/空串按空表达式处理，与 parseExpr 一致）
 * @param {Map<string,{name:string,arg:string,body:string}>} [defs] 本页收集的定义；
 *        省略时用页面登记的"当前定义表"（见 userFn.js 的 setActiveDefs）
 */
export function resolveExpr(raw, defs) {
  const p = parseExpr(raw);
  if (!p.valid || p.type === "definition") return p;
  const table = defs === undefined ? getActiveDefs() : defs;
  // 只认"有定义体"的条目：输入过程中的第一帧可能只登记了名字（见 registerUserFn）
  const ready = new Map([...(table || [])].filter(([, d]) => d && typeof d.body === "string"));

  const out = { ...p };
  if (ready.size) {
    for (const f of ["body", "radius", "xsExpr", "ysExpr", "boundary"]) {
      if (typeof out[f] === "string" && out[f]) {
        const r = expandCalls(out[f], ready);
        if (r.error) return { ...out, valid: false, error: r.error };
        out[f] = r.text;
      }
    }
  }

  /* 未定义函数检查**无条件执行**（哪怕本页一个定义都没有）。
   * 为什么不能只在"有定义表"时才查：把定义行删掉之后，引用行就变成"没有定义的 f"，
   * 若此时跳过检查，引擎会拿 `f` 当未绑定符号 → 全 null → 曲线**静默消失**
   * （docs/PLAN-plot-user-functions.md §1.4：这正是这个 bug 今天唯一能被用户看见的入口）。
   * 排除自变量与自由参数：`x(x+1)` 里的 `x` 是变量乘括号，不是函数调用。 */
  const probe = out.body || out.radius || out.xsExpr || out.ysExpr || out.boundary || "";
  const bad = findUndefinedCalls(probe, ready)
    .filter((n) => n !== p.var && !(p.params || []).includes(n));
  if (bad.length) {
    return { ...out, valid: false, error: `未定义的函数 ${bad[0]}（可用 ${bad[0]}(x)=… 定义）` };
  }
  // 已定义的函数名不是参数（否则会凭空多一个滑块）
  out.params = (p.params || []).filter((n) => !ready.has(n));
  return out;
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
