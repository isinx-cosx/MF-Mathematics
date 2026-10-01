/**
 * 结果格式化：数值与摘要文本
 *
 * 注意：**结果里的数学不再由这里拼 HTML**。
 * 旧实现有个 mathHtml()，把 `**`→`^`、`^2`→`<sup>2</sup>` 做 ASCII 近似 ——
 * 那套已经废弃，改由 resultModel.js 判定数学/文字、MathLatex.vue（KaTeX）排版。
 * 这里只留与排版无关的部分：数字格式化与单行摘要。
 */
"use strict";

export function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/**
 * 数值显示。
 *
 * 与原版（calculator.py 的 _fmt_result）对齐的三点：
 *   ① 默认保留 **12** 位小数并去掉尾随零（原版是 f"{v:.12f}"；这里曾是 10 位，
 *      于是 1/3 显示 0.3333333333 而原版是 0.333333333333）。
 *   ② 阈值与原版一致：|v| ≥ 1e12 或 0 < |v| < 1e-10 才走科学计数法（都是 .6e）。
 *   ③ **整数原样输出**。原版对 int 直接 str()，所以 20! 显示完整的
 *      2432902008176640000；这里若按 1e12 阈值转成 2.432902e+18，
 *      用户会以为"数字没算准"（阶乘、组合数场景下尤其明显）。
 *      所以：数值本身是整数（或 ≥1e12 但在 double 精度内能精确表示的整数）时给完整十进制。
 */
export function fmtNum(v) {
  if (typeof v !== "number" || !isFinite(v)) return "错误";
  // 整数原样输出（含超过 1e12 的大整数，如阶乘结果）
  if (Number.isInteger(v)) return String(v);
  if (Math.abs(v) >= 1e12 || (Math.abs(v) < 1e-10 && v !== 0)) return v.toExponential(6);
  const s = v.toFixed(12).replace(/\.?0+$/, "");
  return s === "" ? "0" : s;
}

/** 结果摘要（用于列表/状态栏的单行文本） */
export function resultSummary(value, limit = 80) {
  let text;
  if (value === null || value === undefined) text = "（空）";
  else if (typeof value === "number") text = fmtNum(value);
  else if (typeof value === "string") text = value;
  else if (Array.isArray(value)) text = `[${value.length} 项]`;
  else if (typeof value === "object") text = `{${Object.keys(value).length} 个字段}`;
  else text = String(value);
  return text.length > limit ? text.slice(0, limit) + "…" : text;
}
