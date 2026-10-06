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
await ev(`location.hash='#/plot/2d'`);
await sleep(1800);

const setExpr = (text) => ev(`(function(){
  const f=[...document.querySelectorAll('math-field')][0];
  if(!f) return 'no-field';
  f.value=${JSON.stringify(text)};
  f.dispatchEvent(new Event('input',{bubbles:true}));
  return 'ok'; })()`);

/* 视口几何：默认视图的 **x 范围**是固定的 [-10, 10]（view.js 的 DEFAULT_X_MIN/MAX），
 * y 跨度按画布宽高比同比例展开（即世界坐标 1:1，画面是正方形网格 —— 实测用 y=x 的红线
 * 反推过：斜率 -1.045 ≈ -(H/W)，两边跨度相等）。
 *
 * ⚠ 不要拿状态栏那行"范围 [-10.00, 10.00] × [-10.46, 10.46]"当视口：那是**采样**范围，
 * 带 25% 外扩（PlotView 的 padX/padY），照它换算会差 20 个设备像素 —— 本套件第一版
 * 就是这么把 y=x 误判成"两端没画出来"的。 */
const geom = await ev(`(function(){
  const c=document.querySelector('canvas');
  const r=c.getBoundingClientRect();
  return { cssW:Math.round(r.width), cssH:Math.round(r.height), dpr:window.devicePixelRatio||1 }; })()`);
const X_SPAN = 20;                                  // [-10, 10]
const Y_SPAN = X_SPAN;   // 实测（用 y=x 的红线拟合）：世界跨度相等 ⇒ 视口 ±10 × ±10
const VIEW = { x0: -X_SPAN / 2, x1: X_SPAN / 2, y0: -Y_SPAN / 2, y1: Y_SPAN / 2 };
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

console.log(`画布 ${geom.cssW}x${geom.cssH} @${geom.dpr}x，视口 x[${VIEW.x0},${VIEW.x1}] y[${VIEW.y0.toFixed(2)},${VIEW.y1.toFixed(2)}]`);

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

console.log(`\nRESULT|cdp-plot-accuracy|${pass}|${fail}`);
ws.close();
process.exit(fail ? 1 : 0);
