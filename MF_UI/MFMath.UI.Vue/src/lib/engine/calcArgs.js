/**
 * 引擎参数构造（移植自旧版 MFMath.UI/js/calcblock.js，并按类型补全）
 *
 * 两条路径：
 *  ① 自动映射：用 ENGINE_MAP[mode].args 的签名 + ENGINE_VAR_SPECS 的默认值
 *  ② 多参数弹窗：用户逐项填写 VAR_SPECS 字段后
 *
 * ⚠ 2026-09 修正（原实现把结构化参数当字符串/数字塞，导致一类静默失败）：
 *   旧代码对非 string 参数一律 `a.type === 'double' ? 0 : 1`，于是
 *     · point        → 1     （引擎 get_point 要求 [x,y]）
 *     · matrix       → 1     （get_matrix 要求 [[…]]）
 *     · double_array → 1     （方差/插值/检验这类模式全部打不开）
 *     · 可选参数缺省时被塞成 1，而不是"省略、让引擎用自己的默认"
 *   现在按声明的类型真解析，并且输入框支持用 `;` 分段一次给多个参数：
 *     "(1,2);(3,4)"     → p1=[1,2], p2=[3,4]
 *     "1,2,3"           → data=[1,2,3]
 *     "[[1,2],[3,4]]"   → matrix
 *     "x^2-4; -2; 2"    → expr="x^2-4"，再补 a=-2, b=2
 *     "x>1; x<3"        → string_array ["x>1","x<3"]
 *   不分号的老写法行为不变（只有一个表达式时走 VAR_SPECS/引擎默认）。
 */
"use strict";

import { ENGINE_MAP, ENGINE_VAR_SPECS } from "./engineMap.js";

/**
 * 表达式语法归一化。
 *
 * 曾经这里是"旧版 UI 的 ^ 幂写法 → 引擎的 **"的替换。2026-09 统一为 **使用 `^`**：
 * 引擎（math_input.h 的归一化）现在把 `**` 也归一到 `^`，界面不再做任何算符替换，
 * 语法归一化只发生在引擎里一处（避免"界面换一种、引擎换一种"的两套写法）。
 */
export function toEngineExpr(s) {
  return String(s == null ? "" : s);
}

/**
 * 跳过不映射到引擎参数的字段（变量/表达式类，用输入框或默认值提供）。
 * 「（输入框）」是显式约定：该字段就是输入框的占位，值已经在弹窗第一个格子里预填。
 */
export function isSkippedField(label) {
  const s = String(label ?? "");
  return s.includes("（输入框）") || s.includes("(输入框)")
      || s === "变量" || s.includes("表达式") || s.includes("被积")
      || s.includes("通项") || s.includes("函数");
}

/** 结构化参数类型：必须真解析成数组/点，不能当字符串 */
export const STRUCTURED = new Set([
  "point", "vec", "vector", "matrix", "matrix_list", "point_cloud", "prob_table",
  "double_array", "int_array", "string_array", "double_list", "int_list", "pair_list", "complex_obj",
  "ll_matrix", "ll_array", "ll_list",
]);

/** 按深度 0 的分号/换行切段：括号里的分号不算分隔；只去掉末尾空段，位置保持稳定 */
export function splitSegments(text) {
  const s = String(text ?? "");
  const parts = [];
  let depth = 0, cur = "";
  for (const c of s) {
    if ("([{".includes(c)) depth++;
    else if (")]}".includes(c)) depth = Math.max(0, depth - 1);
    if ((c === ";" || c === "\n") && depth === 0) { parts.push(cur); cur = ""; continue; }
    cur += c;
  }
  parts.push(cur);
  const out = parts.map((x) => x.trim());
  if (out.length > 1 && out[out.length - 1] === "") out.pop();
  return out;
}

/** 文本 → 数字数组（容忍 [] () 逗号 空格 与中文逗号） */
function numberList(text) {
  const t = String(text ?? "").replace(/[\[\](){}]/g, " ").replace(/[，、]/g, " ");
  const out = [];
  for (const p of t.split(/[\s,]+/)) {
    if (p === "") continue;
    const v = Number(p);
    if (Number.isFinite(v)) out.push(v);
  }
  return out;
}

/** 文本 → 矩阵（"[[1,2],[3,4]]" / "1,2; 3,4" / "1,2,3,4" 都接受） */
function matrixOf(text) {
  const s = String(text ?? "").trim();
  if (s.startsWith("[[")) {
    try {
      const v = JSON.parse(s.replace(/，/g, ","));
      if (Array.isArray(v) && v.length && v.every(Array.isArray)) return v.map((r) => r.map(Number));
    } catch { /* 落到下面的宽松解析 */ }
  }
  const rows = s.split(/[;\n]/).map((r) => numberList(r)).filter((r) => r.length);
  if (rows.length > 1) return rows;
  const flat = numberList(s);
  return flat.length ? [flat] : [];
}

/** 文本 → 矩阵数组（[[[…]],…]；只给一个矩阵时包成单元素数组） */
function matrixListOf(text) {
  const s = String(text ?? "").trim();
  if (s.startsWith("[[[")) {
    try {
      const v = JSON.parse(s.replace(/，/g, ","));
      if (Array.isArray(v) && v.every((m) => Array.isArray(m) && m.every(Array.isArray)))
        return v.map((m) => m.map((r) => r.map(Number)));
    } catch { /* 落到单矩阵处理 */ }
  }
  const m = matrixOf(s);
  return m.length ? [m] : [];
}

/**
 * 文本 → 概率表对象：`"A_and_B=0.2; B=0.5"` → `{A_and_B:0.2, B:0.5}`。
 * 条件概率/全概率/贝叶斯要的是"带具体键名的对象"，前端没法从纯数值输入拼出来，
 * 所以给一个最直白的 `键=值; 键=值` 写法。
 */
function complexObjOf(text) {
  const s = String(text ?? "").trim();
  if (s.startsWith("{")) { try { return JSON.parse(s); } catch { return {}; } }
  const out = {};
  for (const seg of s.split(/[|;]\s*/)) {
    const i = seg.indexOf(":");
    if (i <= 0) continue;
    const dim = seg.slice(0, i).trim();
    const sims = seg.slice(i + 1).split(/,\s*/).filter((x) => x !== "");
    if (sims.length) out[dim] = [sims.map((v) => Math.trunc(Number(v) || 0))];
  }
  return out;
}

function probTableOf(text) {
  const out = {};
  for (const seg of String(text ?? "").split(/[;,]\s*/)) {
    const i = seg.indexOf("=");
    if (i <= 0) continue;
    const k = seg.slice(0, i).trim();
    const v = Number(seg.slice(i + 1).trim());
    if (k) out[k] = Number.isFinite(v) ? v : 0;
  }
  return out;
}

/** 文本 → 点 [x,y]（写成分组的 (1,2) 时取第一组） */
function pointOf(text) {
  const g = String(text ?? "").match(/[(（[][^)）\]]*[)）\]]/);
  const flat = numberList(g ? g[0] : text);
  return flat.slice(0, 2);
}

/**
 * 按类型把文本转成引擎要的 JSON 值。
 * 解析不出来时**原样返回文本**：让引擎抛出它自己的参数错误（对话框里能看到中文原因）。
 * 在这里静默塞 0/1 才是真正难查的失败。
 */
export function convertArg(type, raw) {
  const s = String(raw == null ? "" : raw).trim();
  switch (type) {
    case "double": return Number.isFinite(Number(s)) ? Number(s) : s;
    case "int": return Number.isFinite(Number(s)) ? Math.trunc(Number(s)) : s;
    case "bool": return s === "true" || s === "1" || s === "是";
    case "string_or_number": return /^-?\d+(\.\d+)?$/.test(s) ? Number(s) : toEngineExpr(s);
    case "point": return pointOf(s);
    case "vec": case "vector": return numberList(s);
    case "matrix": return matrixOf(s);
    case "matrix_list": return matrixListOf(s);
    case "point_cloud": return matrixOf(s);   // 点云就是 [[x,y],…]
    case "prob_table": return probTableOf(s);
    case "complex_obj": return complexObjOf(s);
    case "ll_matrix": return matrixOf(s);
    case "ll_array": case "ll_list": return numberList(s);
    case "double_array": case "double_list": return numberList(s);
    case "int_array": case "int_list": return numberList(s).map((v) => Math.trunc(v));
    case "string_array": return splitSegments(s);
    default: return toEngineExpr(s);
  }
}

/** 必填参数拿不到值时的兜底（仍交给引擎校验并报错） */
function fallbackOf(type) {
  switch (type) {
    case "double": case "int": return 0;
    case "bool": return false;
    case "point": return [0, 0];
    default: return STRUCTURED.has(type) ? [] : "";
  }
}

/**
 * 自动映射构造参数
 * @param {string} mode 中文模式名
 * @param {string} expr 用户输入的表达式（可用 `;` 分段附带结构化参数）
 * @returns {object|null} 引擎参数对象；模式未映射时返回 null
 */
export function buildEngineArgs(mode, expr) {
  const spec = ENGINE_MAP[mode];
  if (!spec) return null;
  const fields = ENGINE_VAR_SPECS[mode] || [];
  const segments = splitSegments(expr);
  const args = {};
  const missingRequired = [];
  const eat = (a, text) => (a.type === "string" ? toEngineExpr(text) : convertArg(a.type, text));
  let seg = 0;

  // ① 第一段永远是"那条表达式"：给第一个必填的字符串参数
  //    （不能按声明顺序给 —— 傅里叶系数这类模式的必填项是 n:int 在前、f:string 在后，
  //      那样会把用户写的表达式当项号。）
  // 第一段给"必填"参数：优先必填字符串（表达式），其次第一个必填参数，
  // 全可选时才用第一个声明的。旧写法会落到**可选**字符串上（z 检验的 alternative
  // 是个可选字符串，结果输入框第一段被它吃掉，sample_mean 反而错位）。
  const textArg = spec.args.find((a) => !a.opt && a.type === "string")
               || spec.args.find((a) => !a.opt && a.type !== "string_array")
               || spec.args.find((a) => a.type !== "string_array" && a.type !== "complex_obj")
               || spec.args[0];
  // 必须按类型转换：textArg 现在可能是数字/矩阵/点等（旧写法一律 toEngineExpr，
  // 结果把 "5" 当字符串塞给 int 参数 → "参数 n 类型错误"。string_array 交给下面的分支整组处理）
  if (textArg && segments.length) { args[textArg.key] = eat(textArg, segments[seg++]); }

  // ② 不等式组这类：剩下的段整组当字符串数组
  for (const a of spec.args) {
    if (a.type !== "string_array" || a.key in args) continue;
    args[a.key] = convertArg("string_array", segments.slice(seg).join(";"));
    seg = segments.length;
  }

  // ③ 其余必填参数按声明顺序吃段
  for (const a of spec.args) {
    if (a.opt || a.key in args) continue;
    if (seg < segments.length) { args[a.key] = eat(a, segments[seg++]); continue; }
    missingRequired.push(a);
  }

  // ④ 还有剩余的段 → 补给可选参数（"x^2-4; -2; 2"）
  for (const a of spec.args) {
    if (!a.opt || a.key in args) continue;
    if (seg >= segments.length) break;
    args[a.key] = eat(a, segments[seg++]);
  }

  // ⑤ 仍缺的必填参数 → VAR_SPECS 字段（跳掉表达式类字段），再不行按类型兜底
  let fi = 0;
  const skipField = () => { while (fi < fields.length && isSkippedField(fields[fi][0])) fi++; };
  const takeField = () => { skipField(); return fi < fields.length ? fields[fi++][1] : null; };
  for (const a of missingRequired) {
    const v = takeField();
    args[a.key] = v === null ? fallbackOf(a.type) : eat(a, v);
  }

  // ⑥ 其余可选参数 → VAR_SPECS 字段；没有就**整个键省略**，让引擎用自己的默认值
  for (const a of spec.args) {
    if (a.key in args) continue;
    const v = takeField();
    if (v !== null) args[a.key] = eat(a, v);
  }
  return args;
}

/**
 * 用多参数弹窗收集的值构造参数
 *
 * 规则（与弹窗交互对齐）：
 *   ① 输入框内容（values[0]，也就是弹窗第一个格子预填的值）喂给
 *      **第一个必填参数**；若没有必填参数，则喂给第一个声明的参数。
 *      旧实现只认"第一个必填字符串"，于是首参是数字/矩阵的模式（等差数列、Lp范数、
 *      拉格朗日插值…）拿不到输入框里的值。
 *   ② 其余字段按顺序填剩下的参数：先必填，后可选；跳过「（输入框）」占位字段。
 * @param {object} spec ENGINE_MAP[mode]
 * @param {Array<[string,string]>} fields VAR_SPECS 的字段定义
 * @param {string[]} values 用户填写的值（与 fields 一一对应）
 */
export function buildEngineArgsFromValues(spec, fields, values) {
  const args = {};
  // 弹窗第一个格子就是输入框的内容，里面同样可以用 `;` 分段带参数：
  //   "x^3; x; 2" + 弹窗默认 → 不必逐个手填
  const segments = splitSegments(String((values && values[0]) ?? ""));
  const boxEmpty = segments.length === 1 && segments[0] === "";
  // 输入框为空时（例如"只靠弹窗填参数"的模式）跳过它，直接吃弹窗字段
  const rest = fields
    .map((f, i) => ({ label: f[0], value: values[i] }))
    .filter((f, i) => i > 0 && !isSkippedField(f.label));
  let ui = 0, seg = 0;
  const conv = (a, v) => (a.type === "string" ? toEngineExpr(String(v)) : convertArg(a.type, v));

  if (!boxEmpty) {
    // ① 第一段给第一个必填字符串参数（"那条表达式"），其次给第一个必填参数
    const textArg = spec.args.find((a) => !a.opt && a.type === "string")
                 || spec.args.find((a) => !a.opt) || spec.args[0];
    if (textArg) args[textArg.key] = conv(textArg, segments[seg++]);
    // ② 剩下的段：**先必填、后可选**，按声明顺序（与 buildEngineArgs 同一规则）。
    //    旧写法按声明顺序一把梭，遇到"可选参数声明在前"的模式（RK4 的 h）会把
    //    第一段参数喂给可选参数，必填参数反而落空。
    for (const pass of [false, true]) {
      for (const a of spec.args) {
        if (!!a.opt !== pass || a.key in args) continue;
        if (seg >= segments.length) break;
        args[a.key] = conv(a, segments[seg++]);
      }
    }
  }

  // 段已经填过若干参数 → 对应的弹窗字段也要跳过，否则同一参数被"段"和"字段"各填一次
  // （交换律验证就是这样把运算符填成了 b 的值）
  ui = Math.max(0, seg - 1);
  // ③ 其余必填参数（弹窗字段优先，其次兜底）
  for (const a of spec.args) {
    if (a.opt || a.key in args) continue;
    args[a.key] = ui < rest.length ? conv(a, rest[ui++].value) : fallbackOf(a.type);
  }
  // ④ 可选参数（剩余字段；没有就省略 → 用引擎默认）
  for (const a of spec.args) {
    if (!a.opt || a.key in args) continue;
    if (ui < rest.length) args[a.key] = conv(a, rest[ui++].value);
  }
  return args;
}

/** 模式是否有引擎映射 */
export function hasEngineMode(mode) {
  return Object.prototype.hasOwnProperty.call(ENGINE_MAP, mode);
}

/** 模式是否需要多参数弹窗 */
export function needsVarDialog(mode) {
  return Object.prototype.hasOwnProperty.call(ENGINE_VAR_SPECS, mode);
}

export { ENGINE_MAP, ENGINE_VAR_SPECS };
