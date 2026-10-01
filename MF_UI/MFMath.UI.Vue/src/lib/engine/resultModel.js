/**
 * resultModel.js — 引擎返回值 → 可渲染节点（决定"哪一段是数学、哪一段是文字"）
 *
 * 为什么需要它：结果里混着两种东西。
 *   · 数学：`(x + 2)*(x - 2)`、`-a^2/4`、`x = -sqrt(a)` —— 要用 KaTeX 排版
 *   · 元信息：`solveMethod = "symbolic"`、`kind = "maximum"`、`note = "…"`
 * 把 `"symbolic"` 丢给 KaTeX 会排成 s·y·m·b·o·l·i·c 的斜体乘积 —— 看起来像数学，
 * 其实是错的。所以判定必须"宁可退回纯文本"，共四道闸门：
 *
 *   ① 字段名在 PLAIN_KEYS（引擎明确的元信息字段）→ 文字
 *   ② 含中日韩文字或全角标点 → 文字
 *   ③ 没有任何"只可能出现在数学里"的字符（数字、运算符、括号、√ π …）→ 文字
 *   ④ 引擎的 sym_latex 必须真的解析出 LaTeX → 才当数学
 *
 * 第 ② 道闸门是实测逼出来的：sym_latex("该分支内结论不唯一：极大值") 会
 * **原样返回中文**并报 ok:true —— "引擎接受了"不等于"这是数学"。
 * 第 ④ 道闸门说明：引擎的解析器不认 `=`（"Unknown token: '='"），
 * 所以等式走 equationLatex()：把 `a = b` 两边分别转 LaTeX 再拼回去。
 */
"use strict";
import { fmtNum } from "./resultFormat.js";
import { symLatex } from "../plot/prepare.js";

/** 引擎结果里的元信息字段：即使含数字/等号也按原文显示 */
export const PLAIN_KEYS = new Set([
  "solveMethod", "solveNote", "valueFieldNote",  // 求解方式与取值域说明
  // generalSolution：Engine 的周期通解写成集合族记法
  // （`{2*n*pi + pi | n in (-oo, oo)} U {2*n*pi | …}`），引擎自己的解析器不认 `|`
  // 与 `{}`，送去排版只会失败退回文字；直接定性为文字，省一次无用的解析尝试。
  "generalSolution",
  "kind", "nature", "deltaSign", "signDefinite", // 极值/判别式结论
  "realness", "realnessReason",                  // 实根性判定
  "method", "reason", "note", "error", "steps",  // 方法、原因、步骤说明
  "vars", "exists", "uniform",                   // 变量表与存在性
]);

/**
 * 引擎字段名 → 中文标签。
 *
 * 为什么需要：结果对象是**直接按引擎返回的键渲染**的，于是用户会看到
 * `deltaSign = positive`、`realnessReason = …`、`solutions = …` 这种英文键名。
 * 原版会把结果排成一段公式（`a = b` 形式），不会把内部键名摆到脸上。
 *
 * 这里只做**显示层**的翻译，不改任何计算结果；没收录的键原样显示（宁可见到英文，
 * 也不要猜错含义）。
 */
export const FIELD_LABELS = {
  delta: "判别式 Δ",
  deltaSign: "判别式符号",
  realness: "实根性",
  realnessReason: "实根性依据",
  signDefinite: "正定性",
  solutions: "解集",
  solution: "解",
  // 三角方程的周期通解走这个字段（解集 solutions 为空是**正常**的：
  // 无有限根可列，全部解在通解里）。
  generalSolution: "通解",
  roots: "根",
  exact: "精确形式",
  params: "参数",
  vars: "变量",
  values: "取值",
  kind: "类型",
  nature: "结论",
  sign: "符号",
  method: "方法",
  solveMethod: "求解方式",
  solveNote: "求解说明",
  valueFieldNote: "取值范围说明",
  reason: "原因",
  note: "说明",
  error: "错误",
  steps: "步骤",
  exists: "是否存在",
  uniform: "是否一致",
  count: "个数",
  sum: "和",
  product: "积",
  mean: "均值",
  variance: "方差",
  stddev: "标准差",
  min: "最小值",
  max: "最大值",
  argmin: "最小值点",
  argmax: "最大值点",
  extrema: "极值",
  barcodes: "条形码",
  pairs: "配对",
  persistence: "持续值",
  birth: "出生",
  death: "消失",
  residue: "留数",
  order: "阶",
  poles: "极点",
  singularities: "奇点",
  residueSum: "留数和",
  convergence: "收敛性",
  radius: "半径",
  interval: "区间",
  domain: "定义域",
  range: "值域",
  rank: "秩",
  det: "行列式",
  trace: "迹",
  eigenvalues: "特征值",
  eigenvectors: "特征向量",
  nullspace: "零空间",
  basis: "基",
  dimension: "维数",
  matrix: "矩阵",
  vector: "向量",
  norm: "范数",
  angle: "夹角",
  dot: "点积",
  pValue: "p 值",
  statistic: "统计量",
  df: "自由度",
  confidence: "置信度",
  ci: "置信区间",
  alternative: "备择假设",
  reject: "是否拒绝原假设",
  n: "n",
  k: "k",
  t: "t",
  x: "x",
  y: "y",
  z: "z",
};

/** 取字段的中文标签；没有收录就原样返回键名。 */
export function labelOf(key) {
  return FIELD_LABELS[key] || String(key ?? "");
}

/**
 * 只可能出现在数学里的字符（纯字母一律不算）。
 * 注意这里**不包含单独一个减号**：`two-sided`、`two-way` 这类英文取值含减号，
 * 送进引擎会被解析成 `two - sided`（引擎确实接受），排出来是 t·w·o − s·i·d·e·d 的假数学。
 * 带数字的 `x-1` 由数字这一项兜住，`-sqrt(a)` 由括号兜住，都不受影响。
 */
const MATH_CHARS = /[0-9+*/^()=<>√π|]/;

/** 中日韩文字与全角标点：出现即说明这是说明文字，不是公式 */
const CJK = /[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]/;

/** 这段文本该按数学显示吗（第 ①②③ 道闸门；④ 由 symLatex 决定） */
export function isMathText(text, key = "") {
  if (PLAIN_KEYS.has(key)) return false;
  const t = String(text ?? "").trim();
  if (!t) return false;
  if (CJK.test(t)) return false;
  return MATH_CHARS.test(t);
}

/**
 * 等式 `a = b` → LaTeX。引擎解析器不认 `=`，所以把两边分开转再拼。
 * 两边都必须能解析：一边解析不了就整串退回纯文本，
 * 不做"一半数学一半文字"的混排（那比纯文本更难看懂）。
 */
function equationLatex(src) {
  const m = /^([^=<>!]+)=([^=<]*)$/.exec(src);
  if (!m) return "";
  const l = symLatex(m[1].trim());
  const r = symLatex(m[2].trim());
  return l && r ? `${l} = ${r}` : "";
}

function latexFor(src) {
  const t = src.trim();
  return symLatex(t) || equationLatex(t);
}

function stringNodes(text, key) {
  const src = String(text);
  if (!isMathText(src, key)) return [{ k: "text", text: src }];
  const latex = latexFor(src);
  // 引擎解析不了 → 说明它不是数学表达式，退回原文
  return latex ? [{ k: "math", latex, text: src }] : [{ k: "text", text: src }];
}

/**
 * 引擎返回值 → 节点数组（统一是数组：矩阵单元、数组项、对象字段都能直接渲染）
 *   {k:'num',    text}          数字（已按 fmtNum 格式化）
 *   {k:'bool',   text}          真 / 假
 *   {k:'math',   latex, text}   KaTeX 渲染，解析失败时用 text 兜底
 *   {k:'text',   text}          原样文字
 *   {k:'table',  rows:[[节点…],…]}   矩阵
 *   {k:'list',   items:[节点…]}      一维数组
 *   {k:'obj',    rows:[{key,value}]} 对象
 */
export function toResultNodes(value, key = "") {
  if (value === null || value === undefined) return [{ k: "text", text: "（空）" }];
  if (typeof value === "number") return [{ k: "num", text: fmtNum(value) }];
  if (typeof value === "boolean") return [{ k: "bool", text: value ? "真" : "假" }];
  if (typeof value === "string") return stringNodes(value, key);

  if (Array.isArray(value)) {
    if (value.length === 0) return [{ k: "text", text: "（空）" }];
    // 数组的数组 → 矩阵（表格）
    if (value.every((r) => Array.isArray(r))) {
      return [{ k: "table", rows: value.map((r) => r.map((c) => toResultNodes(c, key))) }];
    }
    return [{ k: "list", items: value.map((v) => toResultNodes(v, key)) }];
  }

  if (typeof value === "object") {
    const entries = Object.entries(value);
    // 空对象必须**显示**成"（空）"：渲染成空节点时对话框里什么都没有，
    // 看起来像"算了但没结果"，实测就是靠这一点把几个模式判成失败的。
    if (entries.length === 0) return [{ k: "text", text: "（空对象）" }];
    return [{
      k: "obj",
      rows: entries.map(([k, v]) => ({ key: k, value: toResultNodes(v, k) })),
    }];
  }

  return [{ k: "text", text: String(value) }];
}

/** 一段文本的 LaTeX（给调用方自己排版用；拿不到就返回空串） */
export function textLatex(text, key = "") {
  return isMathText(text, key) ? latexFor(String(text)) : "";
}
