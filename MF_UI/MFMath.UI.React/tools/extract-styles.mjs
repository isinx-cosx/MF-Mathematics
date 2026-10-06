// 把 Vue SFC 的 <style> 块原样抽成 CSS 文件，供 React 版直接 import。
// 目的：界面不许走样 —— 样式只能复用，不能重写。
// 用法: node tools/extract-styles.mjs
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const vueSrc = path.resolve(here, "../../MFMath.UI.Vue/src");
const outRoot = path.resolve(here, "../src/styles");

const JOBS = [
  { from: "App.vue",                    to: "app.css" },
  { from: "views/plot/PlotView.vue",    to: "plot-view.css" },
  { from: "components/plot/PlotCanvas.vue", to: "plot-canvas.css" },
  { from: "components/plot/ExpressionList.vue", to: "expr-list.css" },
  { from: "components/plot/ParamSlider.vue", to: "param-slider.css" },
  { from: "components/math/MathField.vue", to: "math-field.css" },
  { from: "components/math/MathLatex.vue", to: "math-latex.css" },
  { from: "components/plot/VectorFieldCanvas.vue", to: "plot-vector.css" },
  { from: "views/plot/Plot3DView.vue",  to: "plot-3d.css" },
  { from: "views/plot/PlotComplexView.vue", to: "plot-complex.css" },
  // 其余绘图页（逐页迁 React 时逐个打开）
  { from: "views/plot/PlotVectorView.vue", to: "plot-vector-view.css" },
  { from: "views/plot/PlotFractalView.vue", to: "plot-fractal.css" },
  { from: "views/plot/PlotGeometryView.vue", to: "plot-geometry.css" },
  { from: "components/plot/SurfaceCanvas.vue", to: "surface-canvas.css" },
  { from: "components/plot/GeometryCanvas.vue", to: "geometry-canvas.css" },
];

fs.mkdirSync(outRoot, { recursive: true });

let n = 0;
for (const job of JOBS) {
  const src = path.join(vueSrc, job.from);
  if (!fs.existsSync(src)) { console.log("  跳过（不存在）: " + job.from); continue; }
  const text = fs.readFileSync(src, "utf8");
  const blocks = [...text.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1]);
  if (!blocks.length) { console.log("  无 style 块: " + job.from); continue; }
  const header =
    `/* 自动抽取自 ${job.from} 的 <style>，请勿手改。\n` +
    ` * 重新生成: node tools/extract-styles.mjs\n` +
    ` * 目的：React 版沿用 Vue 版同一份样式，保证界面不走样。 */\n`;
  fs.writeFileSync(path.join(outRoot, job.to), header + blocks.join("\n\n"), "utf8");
  const kb = Math.round(fs.statSync(path.join(outRoot, job.to)).size / 1024);
  console.log(`  ${job.from}  →  src/styles/${job.to}   ${kb} KB`);
  n++;
}
console.log(`完成：${n} 个文件`);
