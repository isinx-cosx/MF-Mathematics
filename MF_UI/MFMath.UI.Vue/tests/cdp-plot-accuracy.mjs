// 绘制**几何准确性**验证（在真实宿主里跑）
//
// 为什么要单独一个套件：现有 14 个绘图用例基本都在数"某颜色的像素有多少个"
//    check("画布绘制了极大值标记", px.purple > 50)
//    check("右半轴画出了曲线", st.right > 50)
// 这只能证明"画了东西"，**证明不了"画在对的位置"**。于是"曲线贴着坐标轴断开一截"
// "e^x 在视口上沿附近整段缺失"这类问题，14 个套件一个都没抓住。
//
// 本套件的判据是几何的：
//   ① 命中：对若干 (x, f(x)) 已知点，按**已知的默认视口**换算出屏幕像素，
//      该处必须出现曲线颜色（允许 ±2px 容差，抗锯齿 + 线宽 2.5px）。
//   ② 连续：沿一条水平/竖直扫描线检查曲线像素，视口内不允许出现 > 6px 的空洞
//      （真渐近线如 1/x 单独排除，那种断开是**对的**）。
//
// 用法: node cdp-plot-accuracy.mjs     （宿主需带 --remote-debugging-port=9222 启动）
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage() {
  for (let i = 0; i < 30; i++) {
    try {
      const list = await (await fetch("http://127.0.0.1:9222/json/list")).json();
      const p = list.find((t) => t.type === "page" && /mfmath\.local|index\.html/.test(t.url || ""));
      if (p) return p.webSocketDebuggerUrl;
    } catch { /* 等宿主 */ }
    await sleep(1000);
  }
  return null;
}
const wsUrl = await findPage();
if (!wsUrl) { console.error("未找到宿主页面"); process.exit(1); }
const ws = new WebSocket(wsUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0;
const send = (method, params, t = 30000) => new Promise((resolve) => {
  const mid = ++id;
  const h = (ev) => { const d = JSON.parse(ev.data); if (d.id === mid) { clearTimeout(tm); ws.removeEventListener("message", h); resolve(d); } };
  const tm = setTimeout(() => { ws.removeEventListener("message", h); resolve({ timeout: true, result: { result: { value: "[超时]" } } }); }, t);
  ws.addEventListener("message", h);
  ws.send(JSON.stringify({ id: mid, method, params }));
});
const ev = async (expr) => (await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }))?.result?.result?.value;

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

await send("Runtime.enable");
/* 先绕到另一条绘图路由再回来，**强制 ReactPlotView 重挂**（它按 route.fullPath 卸载重建）。
 * 为什么必须：本套件的几何断言假定视口是默认的 [-10,10]（下文的 y 跨度按画布宽高比算），
 * 而 PlotPage 的视图存在 React state 里 —— 若上一个用例在同一路由上缩放过，只写
 * location.hash='#/plot/2d' 是**同一个值**、不触发路由变化，也就不会重挂，视口会带着上一个
 * 用例的缩放进来，几何断言会成片假失败。这样本套件就不再依赖"排在前面的用例有没有动过视图"。 */
await ev(`location.hash='#/plot/polar'`);
await sleep(600);
await ev(`location.hash='#/plot/2d'`);

/** 等画布真的挂出来（有界等待）。
 *  为什么不再用固定 sleep：① 慢机器上 1.8s 未必够；② 更要紧的是——**渲染进程可能被卡住**
 *  （例如宿主里还有没跑完的后台任务：bridge.js 写明 CancelJob 只停止等待、引擎会把这一步算完）。
 *  那种情况下任何 Runtime.evaluate 都会超时，固定 sleep 之后读画布会得到 undefined，
 *  然后在很远的地方抛一句 `Cannot read properties of undefined` —— 完全看不出真因（本套件
 *  实测踩过）。现在这里会**明确报出来**并指出该怎么办。 */
const waitCanvas = async (ms = 20000) => {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if (await ev(`!!document.querySelector('canvas')`)) return true;
    await sleep(300);
  }
  return false;
};
if (!(await waitCanvas())) {
  const h = await ev(`location.hash`);
  console.error(`画布没在 20 秒内出现（当前 hash=${h}）。两种可能：`);
  console.error("  · 页面没走到绘图页 —— 检查路由是否被别的用例改坏；");
  console.error("  · **渲染进程被卡住**（宿主里还有没跑完的重活），此时所有 evaluate 都会超时。");
  console.error("    重启宿主（先杀 mfmath-host-rust 再起来）即可恢复，然后再跑本套件。");
  process.exit(1);
}

const setExpr = (text) => ev(`(function(){
  const f=[...document.querySelectorAll('math-field')][0];
  if(!f) return 'no-field';
  f.value=${JSON.stringify(text)};
  f.dispatchEvent(new Event('input',{bubbles:true}));
  return 'ok'; })()`);

/* 视口几何：**直接从页面读真实视图**，不再靠"猜"。
 *
 * ⚠ 这里原来写死 X_SPAN = Y_SPAN = 20（即假定视口是 ±10 × ±10），依据是作者当时用 y=x
 * 的红线拟合出"两边世界跨度相等"。**那个前提只在画布恰好是正方形时成立** ——
 * view.js 的默认视图是 x∈[-10,10]、而 **y 跨度 = 20 · h/w**。
 * 本机画布是 694×726（竖着），真实视口是 y∈[-10.46, 10.46]；照 20 换算，
 * |y| 越大偏得越多（y=8 差约 12.8 设备像素，远超 ±2 容差），于是 `x` 那条线
 * 在 (-7,-7)/(8,8) 被误判成"没画出来"。**这是套件的判据错，不是产品画错**
 * （其余 5 条表达式都过、连续性也过，正因为它们的 |y| 小）。
 *
 * 现在读 `window.__mfPlot.view()`（PlotPage 暴露的排障钩子，与 __mfWorkspace 等同一做法）：
 * 这样不仅对画布宽高比免疫，也顺带覆盖"设置里配了固定绘图范围"或"工作区还原了上次视野"的情形。
 *
 * ⚠ **读不到就直接失败，不再退回 ±10×±10。** 那个退路看着"温和"，实际是把一次时序问题
 * 变成 6 条含义不明的几何假失败 —— 实测踩过：钩子是 `useEffect` 里挂的（DOM 提交之后），
 * 所以"画布已在 DOM 里"并不保证钩子已就位；那次恰好落在窗口里，于是退回了 ±10×±10、
 * 几何全错、6 条命中断言集体失败，而真因只是一次竞争。宁可在这里明确报出来。 */
const hookReady = async (ms = 10000) => {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if (await ev(`!!(window.__mfPlot && typeof window.__mfPlot.view === "function")`)) return true;
    await sleep(200);
  }
  return false;
};
if (!(await hookReady())) {
  console.error("等不到排障钩子 window.__mfPlot（10 秒）。两种可能：");
  console.error("  · React 绘图页没挂起来（路由/构建问题）—— 检查 hash 与页面报错；");
  console.error("  · **渲染进程卡住了**：宿主里还有没跑完的重活时，所有 evaluate 都会超时。");
  console.error("    重启宿主（杀 mfmath-host-rust 再起）即可恢复。");
  process.exit(1);
}

const geom = await ev(`(function(){
  const c=document.querySelector('canvas');
  const r=c.getBoundingClientRect();
  return { cssW:Math.round(r.width), cssH:Math.round(r.height), dpr:window.devicePixelRatio||1 }; })()`);
if (!geom) {
  console.error("读不到画布尺寸（渲染进程可能刚被卡住）—— 重启宿主后重跑本套件");
  process.exit(1);
}
const realView = await ev(`window.__mfPlot.view()`);
if (!(realView && ["x0", "x1", "y0", "y1"].every((k) => Number.isFinite(realView[k])))) {
  console.error(`__mfPlot.view() 不是合法视图：${JSON.stringify(realView)}`);
  process.exit(1);
}
const VIEW = { x0: realView.x0, x1: realView.x1, y0: realView.y0, y1: realView.y1 };
const viewSource = "window.__mfPlot（真实视图）";
const toPx = (x, y) => ({
  px: ((x - VIEW.x0) / (VIEW.x1 - VIEW.x0)) * geom.cssW,
  py: ((VIEW.y1 - y) / (VIEW.y1 - VIEW.y0)) * geom.cssH,
});

/** 取画布像素（设备像素）；曲线色判断用「红分量明显大于蓝绿」这一条，
 *  避免把坐标轴（黑）、网格（浅灰）、标记（青/紫）误判成曲线。 */
const grab = async () => ev(`(function(){
  const c=document.querySelector('canvas');
  const g=c.getContext('2d');
  const d=g.getImageData(0,0,c.width,c.height);
  return { w:c.width, h:c.height, d:Array.from(d.data) }; })()`);

const isCurve = (d, i) => d[i] > 120 && d[i] - d[i + 1] > 45 && d[i] - d[i + 2] > 45;

/** 在 (px,py)（CSS 坐标）附近 ±tol 设备像素内找曲线像素 */
function hitAt(img, cssPx, cssPy, tol = 2) {
  const dpr = geom.dpr;
  const cx = Math.round(cssPx * dpr), cy = Math.round(cssPy * dpr);
  const t = Math.round(tol * dpr);
  for (let y = Math.max(0, cy - t); y <= Math.min(img.h - 1, cy + t); y++) {
    for (let x = Math.max(0, cx - t); x <= Math.min(img.w - 1, cx + t); x++) {
      const i = (y * img.w + x) * 4;
      if (isCurve(img.d, i)) return { x, y };
    }
  }
  return null;
}

/** 沿竖直线 x=cssPx 扫描，返回曲线像素在 y 上的最大空洞（CSS px） */
function maxGapOnColumn(img, cssPx) {
  const dpr = geom.dpr;
  const x = Math.round(cssPx * dpr);
  let lastY = null, maxGap = 0;
  for (let y = 0; y < img.h; y++) {
    const i = (y * img.w + x) * 4;
    if (isCurve(img.d, i)) {
      if (lastY !== null) maxGap = Math.max(maxGap, (y - lastY) / dpr);
      lastY = y;
    }
  }
  return maxGap;
}

console.log(`画布 ${geom.cssW}x${geom.cssH} @${geom.dpr}x，视口 x[${VIEW.x0},${VIEW.x1}] y[${VIEW.y0.toFixed(2)},${VIEW.y1.toFixed(2)}] —— 取自 ${viewSource}`);

/* ① 命中点：曲线必须经过这些已知坐标 */
const CASES = [
  ["x^2", [[-3, 9], [-1, 1], [0.5, 0.25], [2, 4], [3, 9]]],
  ["x", [[-7, -7], [-1, -1], [2, 2], [8, 8]]],
  ["e^x", [[-2, 0.1353], [0, 1], [1, 2.7183], [2, 7.3891], [2.3, 9.9742]]],
  ["ln(x)", [[0.5, -0.6931], [1, 0], [2, 0.6931], [5, 1.6094], [8, 2.0794]]],
  ["1/x", [[0.5, 2], [1, 1], [2, 0.5], [-1, -1], [-2, -0.5]]],
  ["sin(x)", [[1.5708, 1], [3.1416, 0], [4.7124, -1]]],
];
for (const [expr, pts] of CASES) {
  await setExpr(expr);
  await sleep(2400);
  const img = await grab();
  const misses = pts.filter(([x, y]) => { const { px, py } = toPx(x, y); return !hitAt(img, px, py); });
  check(`${expr}：曲线经过全部 ${pts.length} 个已知点`, misses.length === 0,
    misses.length ? "未命中 " + misses.map(([x, y]) => `(${x},${y})`).join(" ") : "");
}

/* ② 连续性：视口内不允许出现大空洞（真渐近线 1/x 不查） */
for (const [expr, cols] of [["x^2", [2, 5, 8]], ["e^x", [-5, 0, 2]], ["ln(x)", [2, 4, 6]], ["sin(x)", [1, 4, 7]]]) {
  await setExpr(expr);
  await sleep(2400);
  const img = await grab();
  const gaps = cols.map((x) => [x, maxGapOnColumn(img, toPx(x, 0).px)]);
  const worst = Math.max(...gaps.map(([, g]) => g));
  check(`${expr}：视口内曲线连续（最大空洞 ${worst.toFixed(1)}px）`, worst <= 6,
    gaps.map(([x, g]) => `x=${x}:${g.toFixed(1)}px`).join(" "));
}

/* ③ 「缩放到适应」必须真的改变视图，且不得抛异常（BUGS.md B3 的回归）
 *
 * 这条曾经是坏的：PlotPage.tsx 的 zoomFit 里 viewW / viewH 没有 import，又误用了
 * `view.value`（`view` 是 useState 的值，不是 Vue 的 ref）。点一下必抛 ReferenceError，
 * 而 React 的**错误边界不捕获事件处理器异常** —— 界面上就是"按钮点了没反应"，
 * 既不白屏、也不留提示，所以只数像素的用例一个都抓不住它。
 *
 * 因此判据不能是像素：必须读**真实视图**（window.__mfPlot 暴露），并单独断言没抛异常。 */
await ev(`window.__mfZoomErr=null;
  window.addEventListener('error', function h(e){
    window.__mfZoomErr = String((e && (e.message || e.error)) || 'unknown');
    window.removeEventListener('error', h);
  });`);
await setExpr("x^2");
await sleep(2400);

const hookOk = await ev(`!!(window.__mfPlot && window.__mfPlot.view)`);
check("排障钩子 window.__mfPlot 可用（React 侧已挂上）", hookOk === true,
  hookOk ? "" : "读不到视图就无法判定 —— 检查 PlotPage 是否仍挂着这个钩子");

const vBefore = await ev(`window.__mfPlot ? JSON.stringify(window.__mfPlot.view()) : null`);
const clicked = await ev(`(function(){
  const b=[...document.querySelectorAll('button')].find(x=>/缩放到适应/.test(x.title||''));
  if(!b) return 'no-button';
  b.click(); return 'ok'; })()`);
await sleep(1200);

const vAfter = await ev(`window.__mfPlot ? JSON.stringify(window.__mfPlot.view()) : null`);
const zoomErr = await ev(`window.__mfZoomErr || ''`);

check("「缩放到适应」按钮存在且可点", clicked === "ok",
  clicked === "no-button" ? "按 title 找不到按钮" : "");
check("点击「缩放到适应」不抛异常", !zoomErr, zoomErr ? "异常：" + zoomErr : "");
check("「缩放到适应」确实改变了视图", !!vBefore && !!vAfter && vBefore !== vAfter,
  "before=" + vBefore + " after=" + vAfter);

console.log(`\nRESULT|cdp-plot-accuracy|${pass}|${fail}`);
ws.close();
process.exit(fail ? 1 : 0);
