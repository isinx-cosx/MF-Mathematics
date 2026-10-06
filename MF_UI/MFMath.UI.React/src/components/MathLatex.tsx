import katex from "katex";
import "../styles/math-latex.css";

/**
 * MathLatex — 用 KaTeX 渲染引擎给出的 LaTeX（照抄 Vue 版 MathLatex.vue）。
 * 渲染失败或没有 LaTeX 时**退回纯文本**，绝不显示空白。
 */
export default function MathLatex({
  latex = "", fallback = "", display = false,
}: { latex?: string; fallback?: string; display?: boolean }) {
  const src = (latex || "").trim();
  let html = "";
  if (src) {
    try {
      html = katex.renderToString(src, {
        throwOnError: false, // 语法可疑也尽量渲染，而不是整块消失
        displayMode: display,
        output: "html",
        strict: false,
      });
    } catch {
      html = "";
    }
  }
  // data-tex 保留原始 LaTeX：KaTeX 把公式拆成一堆 span，文字内容读不回原式，
  // 调试与测试都需要这个出口。
  return html ? (
    <span className="math-latex" data-tex={src} dangerouslySetInnerHTML={{ __html: html }} />
  ) : (
    <span className="math-plain">{fallback}</span>
  );
}
