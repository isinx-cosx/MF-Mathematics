/**
 * keyFace.js — 数学键盘"键面该怎么显示"的**纯逻辑**（无 Vue 依赖，构建期自检可以直接跑）。
 *
 * 背景（这是一个真实缺陷）：模板类键的键面本身就是 LaTeX
 * （`\frac{▢}{▢}`、`\sqrt[▢]{▢}`、`∫_{▢}^{▢}`、`lim_{▢→▢}`）。
 * 这些键以前把 LaTeX 源码当普通文字画在键上，用户看到的就是一串反斜杠和花括号 ——
 * 一排看不懂的键。修法：**键面按数学排版**（KaTeX），排不了的退成可读文本。
 *
 * 三条规则：
 *   1. 只有"含 LaTeX 命令 / 上下标 / 占位符"的键面才排版；其余 100 多个键面是 Unicode 或函数名
 *      （`∫` `sin` `α` `≤` `A⁻¹`），保持纯文本：省开销，也和 v1 的字面观感一致。
 *   2. 排版前先**试渲染**。KaTeX 在 `throwOnError: false` 时会把解析失败的源码用红字画出来，
 *      比原来更糟，所以失败要在这里拦住、换成可读文本。
 *      例：v1 遗留的 `\begin{pmatrix}` 只有开头没有 `\end`，本来就渲染不出来。
 *   3. `▢` 是 v1 的占位符（"光标会停在这里的空位"），键面上换成 KaTeX 的空方框 `\square`。
 *
 * 不变量（由 tools/check-ui.mjs 守着）：**任何键面都不允许显示裸 LaTeX 语法**
 * —— 要么排版成数学，要么是反斜杠/花括号都已清理掉的文本。
 */
import katex from "katex";

/** 含 LaTeX 命令、上下标或占位符 → 需要排版 */
export const NEEDS_MATH = /[\\^_{}]|▢/;

/**
 * 少数键面在 30px 高的键格里放不下（矩阵环境），或本身就是残缺 LaTeX。
 * 这里换成**一眼能懂**的紧凑键面；完整 LaTeX 仍在 title 提示里可见。
 */
export const FACE_OVERRIDE = {
  "\\begin{pmatrix}": "(2×2)",
  "\\begin{bmatrix}": "[2×2]",
  "\\begin{vmatrix}": "|2×2|",
};

/** 键盘里出现的 Unicode 数学符号 → LaTeX 命令（KaTeX 对裸 Unicode 运算符支持不一致） */
export const UNICODE_TO_TEX = [
  ["▢", "\\square "],
  ["∫", "\\int "],
  ["∬", "\\iint "],
  ["∑", "\\sum "],
  ["∏", "\\prod "],
  ["√", "\\sqrt "],
  ["∞", "\\infty "],
  ["∂", "\\partial "],
  ["∇", "\\nabla "],
  ["→", "\\to "],
  ["×", "\\times "],
  ["·", "\\cdot "],
  ["≤", "\\le "],
  ["≥", "\\ge "],
  ["≠", "\\ne "],
  ["≈", "\\approx "],
  ["±", "\\pm "],
];

export function toTex(label) {
  let tex = label;
  for (const [ch, cmd] of UNICODE_TO_TEX) tex = tex.split(ch).join(cmd);
  return tex;
}

/** 渲染不了时的可读回退：去掉环境名与反斜杠花括号，而不是把源码原样丢给用户 */
export function toPlain(label) {
  return (
    label
      .replace(/\\(begin|end)\{[^}]*\}/g, "")
      .replace(/\\/g, "")
      .replace(/[{}]/g, "")
      .trim() || label
  );
}

/** KaTeX 能否真的排出这段源码（`throwOnError: true` 时才如实抛错） */
export function isRenderable(tex) {
  try {
    katex.renderToString(tex, { throwOnError: true, strict: false, output: "html", displayMode: false });
    return true;
  } catch {
    return false;
  }
}

/**
 * 键面信息。
 * @returns {{tex: string, text: string, reason: "plain"|"override"|"math"|"fallback"}}
 *   `tex` 非空表示"按数学排版"；为空则显示 `text`（此时 text 保证不含裸 LaTeX 语法）。
 */
export function keyFaceInfo(label) {
  const raw = String(label ?? "");
  if (!NEEDS_MATH.test(raw)) return { tex: "", text: raw, reason: "plain" };

  const override = FACE_OVERRIDE[raw];
  if (override) return { tex: "", text: override, reason: "override" };

  const tex = toTex(raw);
  if (isRenderable(tex)) return { tex, text: raw, reason: "math" };

  return { tex: "", text: toPlain(raw), reason: "fallback" };
}

/**
 * 这个键面是不是还在把 **LaTeX 语法**当文字显示（自检用的判定）。
 *
 * 注意别把"字符本身就是花括号"的键误判成缺陷：`{` `}` 这两个键显示花括号是**正确的**
 * （它们插入的就是花括号）。所以这里只看语法特征：反斜杠命令、上下标分组、花括号分组。
 * —— 第一版写成 `/[\\{}]/` 就误报了这两个键，是自检自己抓出来的。
 */
export function showsRawLatex(face) {
  if (face.tex) return false;
  const t = face.text;
  if (t.includes("\\")) return true;     // 还留着 LaTeX 命令，如 \frac
  if (/[_^]\{/.test(t)) return true;     // 还留着上下标分组，如 0_{m\times n}
  if (/\{[^}]*\}/.test(t)) return true;  // 还留着花括号分组，如 e^{▢}
  return false;
}
