/**
 * prune-fonts.mjs — 构建后清理字体冗余格式（把 wwwroot 从 2.44 MB 降到 1.66 MB）
 *
 * 背景（实测）：
 *   KaTeX 与 MathLive 都随 CSS 提供同一套字体的三种格式：
 *     .woff2  0.24 MB / 19 个   ← Chromium（WebView2）只认这个，优先命中
 *     .woff   0.29 MB / 20 个   ← 只有老浏览器才需要
 *     .ttf    0.49 MB / 20 个   ← 同上
 *   也就是说 1.02 MB 的字体里，有 0.78 MB 是**这个桌面程序永远不会读**的。
 *   压缩后差别更大：三种格式全留时 xz 734 KB，只留 woff2 时 xz 257 KB（字形数据几乎不可压缩）。
 *
 * 为什么删文件是安全的：
 *   @font-face 的 src 是**按顺序**取第一个浏览器支持的格式，Chromium 一定命中 woff2，
 *   后面的 woff/ttf 永远不会被请求（CSS 里留着引用也无害，不会发起请求）。
 *
 * 安全规则（重要）：
 *   Vite 给每种格式生成**不同的内容哈希**（KaTeX_AMS-Regular-BQhdFMY1.woff2 与 -DMm9YOAa.woff），
 *   所以不能按文件名相等判断"有替代品"，必须按「字体族 + 字重」归组，且**只有该组确实存在 woff2 时才删**。
 *   万一将来某个族只提供了 woff/ttf，这里的保守规则会把它留下并报警，不会把排版搞坏。
 *
 * 已知会被保留下来的 2 个文件（11.7 KB，不要当成漏删）：
 *   KaTeX_Size3 的 woff2 只有 3.5 KB，低于 Vite 默认的 4 KB 内联阈值，
 *   被内联成 CSS 里的 data:font/woff2（Chromium 命中的就是它），因此 dist 里看不到该 woff2 文件，
 *   保守规则按"没有 woff2 兄弟"处理，留下它的 .woff(4.3 KB) + .ttf(7.4 KB)。
 *   11.7 KB 换"绝不误删某族字体"，这个交换划得来；真要抹平得改 assetsInlineLimit，不值得。
 *
 * 验证：tests/cdp-font-load.mjs（真宿主里断言"只请求 woff2、全部 200、逐族字形落到真字体"，
 *       已并入 tests/run-all.ps1 总回归）。
 *
 * 用法：由 npm run build 自动调用（vite build && node scripts/prune-fonts.mjs）
 */
import fs from "node:fs";
import path from "node:path";

const DIST = path.resolve(import.meta.dirname, "..", "dist");
const DROP = new Set([".woff", ".ttf", ".otf", ".eot"]);

if (!fs.existsSync(DIST)) {
  console.error("找不到 dist/，先跑 vite build");
  process.exit(1);
}

/** 字体族+字重：KaTeX_Main-BoldItalic-DxDJ3AOS → katex_main-bolditalic */
function keyOf(file) {
  const stem = path.basename(file, path.extname(file));
  const known = /^(KaTeX_[A-Za-z0-9]+-(?:Regular|Bold|Italic|BoldItalic))/i.exec(stem);
  if (known) return known[1].toLowerCase();          // 本项目字体都是 KaTeX 族，优先走这条明确规则
  let s = stem;                                      // 兜底：从尾部逐段剥掉哈希段
  for (;;) {
    const next = s.replace(/-[A-Za-z0-9_]{4,12}$/, "");
    if (next === s || !next.includes("-")) break;
    s = next;
  }
  return s.toLowerCase();
}

const files = [];
const walk = (dir) => {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p);
    else if (/\.(woff2?|ttf|otf|eot)$/i.test(e.name)) files.push(p);
  }
};
walk(DIST);

const groups = new Map();
for (const f of files) {
  const k = keyOf(f);
  if (!groups.has(k)) groups.set(k, { woff2: [], other: [] });
  const g = groups.get(k);
  if (path.extname(f).toLowerCase() === ".woff2") g.woff2.push(f);
  else if (DROP.has(path.extname(f).toLowerCase())) g.other.push(f);
  else g.woff2.push(f); // 未知格式：当作保留项，绝不删
}

let removed = 0;
let saved = 0;
const kept = [];
for (const [k, g] of groups) {
  if (g.woff2.length === 0) { kept.push(`${k}（无 woff2，全保留 ${g.other.length} 个）`); continue; }
  for (const f of g.other) {
    saved += fs.statSync(f).size;
    fs.unlinkSync(f);
    removed++;
  }
}

const mb = (n) => (n / 1024 / 1024).toFixed(3);
const keptCount = groups.size - kept.length;
console.log(`prune-fonts: 删除 ${removed} 个冗余字体（.woff/.ttf/.otf/.eot），省下 ${mb(saved)} MB；保留 ${keptCount} 组 woff2`);
if (kept.length) {
  console.warn(`prune-fonts: 警告 —— ${kept.length} 组字体没有 woff2 版本，已全部保留（体积偏大但不会影响排版）：`);
  for (const k of kept) console.warn(`  · ${k}`);
}
