// 分形「点击缩放」回归测试：左键单击放大 1.5×、右键单击重定中心（跨度不变）。
//
// 背景：
//   原版 MF_UI/plot/fractal/workspace.py:256-276 的鼠标行为是
//     · 左键单击：w = 跨度/3，新窗口 = (点击点 ∓ w) → 新跨度 = 2/3 旧跨度 = **放大 1.5×**，点击处成为新中心
//     · 右键单击：w = 跨度×0.5，新窗口 = (点击点 ∓ w) → 新跨度 = 2w = **原跨度**，即只重定中心
//       （原版注释写"右键缩小"，但按代码算没有缩放）
//     · 双击：重置视图
//   重写版原来只有"拖拽平移 + 滚轮缩放"，没有左键点击缩放、右键无处理（还会弹出 WebView2 右键菜单）。
//
// 判据（不依赖任何测试钩子，直接拿引擎当裁判）：
//   把画布按网格采样，判每个采样点是不是"集合内部"（近黑像素）；
//   再对两个候选窗口分别问引擎要同样的网格，比较逐点不一致率：
//     A = 什么都没发生（仍是默认窗口）   B = 左键点击 3 次后应有的窗口
//   若实现了左键缩放，B 的不一致率必须远低于 A。
//   右键同理（候选 C = 以点击点为中心、跨度不变）。
//
// 用法: node tests/cdp-fractal-clickzoom.mjs   （需宿主已带 --remote-debugging-port=9222 启动）
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
const send = (method, params, timeoutMs = 25000) => new Promise((resolve) => {
  const mid = ++id;
  const h = (ev) => {
    const d = JSON.parse(ev.data);
    if (d.id === mid) { clearTimeout(timer); ws.removeEventListener("message", h); resolve(d); }
  };
  const timer = setTimeout(() => {
    ws.removeEventListener("message", h);
    resolve({ timeout: true, result: { result: { value: "[超时]" } } });
  }, timeoutMs);
  ws.addEventListener("message", h);
  ws.send(JSON.stringify({ id: mid, method, params }));
});
const evalJs = async (expr) => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return "[异常] " + (r.result.exceptionDetails.text || "");
  return r.result?.result?.value;
};
const clickAt = async (x, y, button = "left") => {
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button, clickCount: 1 });
  await sleep(70);
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button, clickCount: 1 });
  await sleep(1600);   // 等引擎重算 + 重绘
};
await send("Runtime.enable");
await sleep(1500);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};
const fmt = (v) => (typeof v === "number" ? v.toFixed(3) : String(v));

await evalJs("location.hash = '#/plot/fractal'");
await sleep(4500);

const SX = 40, SY = 30;   // 采样网格（与引擎网格同构）

const meta = await evalJs(`(function(){
  const cv = document.querySelector('canvas');
  const r = cv.getBoundingClientRect();
  const label = [...document.querySelectorAll('.field > label')].map(e=>e.textContent).join('|');
  const m = label.match(/最大迭代次数\\s*(\\d+)/);
  const st = [...document.querySelectorAll('.status')].map(e=>e.textContent.trim()).join('|');
  const g = st.match(/(\\d+)×(\\d+)/);
  return { x: r.left, y: r.top, w: r.width, h: r.height, dpr: window.devicePixelRatio || 1,
           maxIter: m ? +m[1] : -1, gridW: g ? +g[1] : -1, status: st };
})()`);
console.log("   画布:", meta.w + "×" + meta.h, "dpr=" + meta.dpr, "| 迭代:", meta.maxIter, "|", meta.status);
check("读到画布/迭代元数据", meta.maxIter > 0 && meta.w > 0 && meta.h > 0, JSON.stringify(meta));

/** 画布上的"集合内部"掩码：与引擎网格同构，返回 [SY][SX] 布尔数组（row 0 = 屏幕顶部）
 *
 *  行序必须和 engineMask 对齐：
 *    · 引擎行 0 = ymin（已实测：ymin=-0.1,ymax=1.5 时第 0 行整行都是迭代上限=集合内）；
 *    · 本函数 row 0 取画布自上而下 (0+0.5)/SY 处 = 屏幕顶部；
 *    · 渲染是 y 向上（屏幕顶部 = ymax）→ 屏幕顶部对应引擎行的**最后一行**。
 *  所以 engineMask 用 py = SY-1-r 配对 row r —— 两边必须同时成立，
 *  早期版本这里取 fy=(SY-r-0.5)/SY（等于从下往上），配 y 不对称的窗口就会误判。
 */
const canvasMask = () => evalJs(`(function(){
  const cv = document.querySelector('canvas');
  const dpr = window.devicePixelRatio || 1;
  const d = cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;
  const SX = ${SX}, SY = ${SY};
  const top = 26 / ${meta.h};      // 顶部 22px 是信息覆盖条，跳过
  const mask = [];
  for (let r = 0; r < SY; r++) {
    const fTop = (r + 0.5) / SY;             // 画布自上而下的比例
    const yPx = Math.round(fTop * ${meta.h} * dpr);
    const row = [];
    for (let c = 0; c < SX; c++) {
      const fx = (c + 0.5) / SX;
      const xPx = Math.round(fx * ${meta.w} * dpr);
      const i = (Math.min(cv.height - 1, Math.max(0, yPx)) * cv.width + Math.min(cv.width - 1, xPx)) * 4;
      row.push({ dark: d[i] < 40 && d[i+1] < 40 && d[i+2] < 50, skip: fTop < top });
    }
    mask.push(row);
  }
  return mask;
})()`);

/** 引擎真值掩码：给定窗口，返回同构的 [SY][SX] 内部布尔数组（row 0 = ymax 侧） */
const engineMask = (rect) => evalJs(`(function(){
  const mf = window.chrome?.webview?.hostObjects?.sync?.mf;
  if (!mf) return null;
  const SX = ${SX}, SY = ${SY};
  const out = mf.Dispatch("mandelbrot", JSON.stringify({
    xmin: ${rect.xmin}, xmax: ${rect.xmax}, ymin: ${rect.ymin}, ymax: ${rect.ymax},
    width: SX, height: SY, max_iter: ${meta.maxIter},
  }));
  const res = typeof out === "string" ? JSON.parse(out) : out;
  if (res && res.isError) return { error: String(res.value) };
  const arr = res && res.value;
  if (!arr || arr.length !== SX * SY) return null;
  const mask = [];
  for (let r = 0; r < SY; r++) {
    const py = SY - 1 - r;                 // 屏幕上方 = ymax = 引擎最后一行
    const row = [];
    for (let c = 0; c < SX; c++) row.push(arr[py * SX + c] >= ${meta.maxIter});
    mask.push(row);
  }
  return mask;
})()`);

/** 两个掩码的逐点不一致率（跳过信息条覆盖的样本） */
const mismatch = (canvas, engine) => {
  if (!canvas || !engine || engine.error) return null;
  let bad = 0, n = 0;
  for (let r = 0; r < SY; r++) {
    for (let c = 0; c < SX; c++) {
      if (canvas[r][c].skip) continue;
      n++;
      if (canvas[r][c].dark !== engine[r][c]) bad++;
    }
  }
  return n ? bad / n : null;
};

const reset = async () => {
  await evalJs(`(function(){ const b = document.querySelector('.vc-btn[title="重置视图"]'); if (b) b.click(); return 'ok'; })()`);
  await sleep(3500);
};

const DEFAULT = { xmin: -2, xmax: 2, ymin: -1.5, ymax: 1.5 };
const cen = [(meta.x + meta.w * 0.5), (meta.y + meta.h * 0.5)];

console.log("\n── 左键单击 ×3（画布正中）：应放大 1.5³ 倍并把该点变成新中心 ──");
await reset();
const mask0 = await canvasMask();
const m0 = mismatch(mask0, await engineMask(DEFAULT));
console.log("   基线：画布 vs 默认窗口 不一致率 =", fmt(m0));
check("基线自检：默认窗口能对上引擎真值（不一致率 < 0.15）", m0 !== null && m0 < 0.15, fmt(m0));

await clickAt(...cen);
await clickAt(...cen);
await clickAt(...cen);

// 点击画布正中 → 复平面 (0,0)；每次跨度 ×2/3
const s = Math.pow(2 / 3, 3);
const ZOOMED = { xmin: -2 * s, xmax: 2 * s, ymin: -1.5 * s, ymax: 1.5 * s };
const mask1 = await canvasMask();
const mZoom = mismatch(mask1, await engineMask(ZOOMED));
const mNoZoom = mismatch(mask1, await engineMask(DEFAULT));
console.log("   3 次点击后：vs 放大后的窗口 =", fmt(mZoom), " | vs 什么都没发生 =", fmt(mNoZoom));
check("左键单击放大：画面与「放大 1.5³ 倍」的引擎真值一致（< 0.15）", mZoom !== null && mZoom < 0.15, fmt(mZoom));
check("左键单击放大：明显比「没缩放」更贴合（至少好 3 倍）",
      mZoom !== null && mNoZoom !== null && mNoZoom > mZoom * 3, `${fmt(mZoom)} vs ${fmt(mNoZoom)}`);

console.log("\n── 右键单击（左上方向）：应把中心挪到点击处、跨度不变 ──");
await reset();
const rx = meta.x + meta.w * 0.28, ry = meta.y + meta.h * 0.30;
await clickAt(rx, ry, "right");
// 点击处对应的复坐标：fx=0.28, fy=0.30（屏幕上方 = ymax）
const cx = -2 + 0.28 * 4, cy = 1.5 - 0.30 * 3;
const RECENTERED = { xmin: cx - 2, xmax: cx + 2, ymin: cy - 1.5, ymax: cy + 1.5 };
const mask2 = await canvasMask();
const mRe = mismatch(mask2, await engineMask(RECENTERED));
const mNoOp = mismatch(mask2, await engineMask(DEFAULT));
console.log("   复坐标中心 =", cx.toFixed(2) + "," + cy.toFixed(2),
            "| vs 重定中心后的窗口 =", fmt(mRe), " | vs 什么都没发生 =", fmt(mNoOp));
check("右键重定中心：画面与「以点击点为中心、跨度不变」一致（< 0.15）", mRe !== null && mRe < 0.15, fmt(mRe));
check("右键重定中心：明显比「什么都没发生」更贴合（至少好 3 倍）",
      mRe !== null && mNoOp !== null && mNoOp > mRe * 3, `${fmt(mRe)} vs ${fmt(mNoOp)}`);

console.log("\n── 拖拽仍然是平移（不能被单击缩放抢走）──");
await reset();
const beforePan = await canvasMask();
await send("Input.dispatchMouseEvent", { type: "mousePressed", x: cen[0], y: cen[1], button: "left", clickCount: 1 });
await sleep(60);
for (let i = 1; i <= 5; i++) {
  await send("Input.dispatchMouseEvent", { type: "mouseMoved", button: "left", x: cen[0] + i * 18, y: cen[1] });
  await sleep(40);
}
await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: cen[0] + 90, y: cen[1], button: "left", clickCount: 1 });
await sleep(2500);
const mask3 = await canvasMask();
// 拖拽 +90px：屏幕 x 比例漂移 = 90/cssW → 窗口左移 90/cssW*4（跨度不变）
const shift = (90 / meta.w) * 4;
const PANNED = { xmin: DEFAULT.xmin - shift, xmax: DEFAULT.xmax - shift, ymin: DEFAULT.ymin, ymax: DEFAULT.ymax };
const mPan = mismatch(mask3, await engineMask(PANNED));
const mPanNoop = mismatch(mask3, await engineMask(DEFAULT));
const changed = JSON.stringify(beforePan) !== JSON.stringify(mask3);
console.log("   拖拽后：vs 平移窗口 =", fmt(mPan), " | vs 默认窗口 =", fmt(mPanNoop), " | 画面变化:", changed);
check("拖拽仍然平移（且没有触发单击缩放）",
      changed && mPan !== null && mPan < 0.15 && mPanNoop > mPan * 3, `${fmt(mPan)} vs ${fmt(mPanNoop)}`);

// 收尾：复位视图，避免污染后续套件
await reset();
await evalJs("location.reload(); 'ok'");
await sleep(3000);

console.log(`\n═══ 分形点击缩放验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|fractal-clickzoom|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
