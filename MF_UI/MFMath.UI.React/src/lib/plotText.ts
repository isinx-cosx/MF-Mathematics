import { symLatex } from "@shared/plot/prepare.js";

/**
 * textLatex — 判断一段引擎返回值该不该按数学排版，并给出 LaTeX。
 *
 * ⚠ 与 Vue 版 `lib/engine/resultModel.js` 的 `textLatex/isMathText/latexFor` 是同一套规则。
 * 之所以在 React 侧再写一份：resultModel.js 顶部 import 了 i18n（i18n 又 import vue），
 * 直接复用会把 Vue 拉进 React 打包结果，与"绘图页面不用 Vue"相冲突。
 * `symLatex` 本身在 `lib/plot/prepare.js` 里，是零依赖的，这里直接复用。
 *
 * 后续应收口：把 isMathText/latexFor/textLatex + PLAIN_KEYS 从 resultModel.js
 * 挪到 `lib/plot/plotText.js`（零依赖），两边都从那里 import。
 */
const PLAIN_KEYS = new Set([
  "kind", "nature", "sign", "method", "solveMethod", "solveNote", "valueFieldNote",
  "reason", "note", "error", "exists", "uniform", "realness", "realnessReason",
  "deltaSign", "signDefinite", "generalSolution",
]);

/** 只可能出现在数学里的字符（纯字母一律不算；也不含单独一个减号） */
const MATH_CHARS = /[0-9+*/^()=<>√π|]/;
/** 中日韩文字与全角标点：出现即说明这是说明文字，不是公式 */
const CJK = /[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]/;

export function isMathText(text: unknown, key = ""): boolean {
  if (PLAIN_KEYS.has(key)) return false;
  const t = String(text ?? "").trim();
  if (!t) return false;
  if (CJK.test(t)) return false;
  return MATH_CHARS.test(t);
}

function equationLatex(src: string): string {
  const m = /^([^=<>!]+)=([^=<]*)$/.exec(src);
  if (!m) return "";
  const l = symLatex(m[1].trim());
  const r = symLatex(m[2].trim());
  return l && r ? `${l} = ${r}` : "";
}

function latexFor(src: string): string {
  const t = src.trim();
  return symLatex(t) || equationLatex(t);
}

export function textLatex(text: unknown, key = ""): string {
  return isMathText(text, key) ? latexFor(String(text)) : "";
}

/** 数字的显示格式（与 Vue 版 prettyNum 一致：极小/极大走科学计数） */
export function prettyNum(v: unknown): string {
  const n = Number(v);
  if (!isFinite(n)) return "—";
  const a = Math.abs(n);
  if (a !== 0 && (a < 1e-4 || a >= 1e5)) return n.toExponential(3);
  return String(Math.round(n * 1e4) / 1e4);
}
