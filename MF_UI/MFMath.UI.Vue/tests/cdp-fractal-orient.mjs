// 分形 y 轴朝向回归测试：屏幕顶部必须是复平面 y 增大的一侧。
//
// 背景（为什么要单独测这一条）：
//   引擎 mandelbrot 返回行主序数组，第 0 行对应 ymin（数学下方）。
//   原版 MF_UI/plot/fractal/workspace.py:242 用 imshow(..., origin="lower")，即 y 向上。
//   重写版曾把第 0 行直接画到 canvas 第 0 行（屏幕顶部），图像被上下镜像；
//   而滚轮/拖拽按"屏幕上方 = ymax"计算，于是渲染与交互互为镜像。
//   Mandelbrot 集关于实轴对称、默认视图 y 也对称，所以这个 bug 在默认视图下
//   完全看不出来 —— 必须用一个"整体在 y>0 之上方"或"整体在 y<0 之下方"的不对称窗口才暴露。
//
// 判据：
//   把视图平移到 y∈[-3,0]（整个集合位于窗口顶部，y=0 在上边缘）。
//   · 引擎真值：row 0 = ymin = -3 → 前 20% 行几乎无集合内部点，后 20% 行（靠近 y=0）大量内部点。
//   · 画布像素：顶部 20% 应是深色（集合内部），底部 20% 应几乎无深色。
//   两者必须一致；若上下颠倒，顶部/底部的深色像素数会对调。
//
// 用法: node tests/cdp-fractal-orient.mjs   （需宿主已带 --remote-debugging-port=9222 启动）
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
await send("Runtime.enable");
await sleep(1500);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

/** 引擎真值：给定矩形，统计前/后 20% 行里"集合内部"（迭代未逃逸）的点数 */
const engineBands = (rect, w, h, maxIter) => evalJs(`(function(){
  const mf = window.chrome?.webview?.hostObjects?.sync?.mf;
  if (!mf) return null;
  const out = mf.Dispatch("mandelbrot", JSON.stringify({
    xmin: ${rect.xmin}, xmax: ${rect.xmax}, ymin: ${rect.ymin}, ymax: ${rect.ymax},
    width: ${w}, height: ${h}, max_iter: ${maxIter},
  }));
  // 宿主 Dispatch 的返回形状是 {isError, value}（MathBridge.cs:17-27）
  const res = typeof out === "string" ? JSON.parse(out) : out;
  const arr = res && res.value;
  if (res && res.isError) return { error: String(res.value) };
  if (!arr || !arr.length) return null;
  const band = Math.max(1, Math.round(${h} * 0.2));
  let first = 0, last = 0;
  for (let py = 0; py < ${h}; py++) {
    for (let px = 0; px < ${w}; px++) {
      if (arr[py * ${w} + px] >= ${maxIter}) {
        if (py < band) first++; else if (py >= ${h} - band) last++;
      }
    }
  }
  return { first, last, band };
})()`);

/** 画布像素：顶部 / 底部条带里的"深色"像素（集合内部 = 近黑）*/
const pixelBands = () => evalJs(`(function(){
  const cv = document.querySelector('canvas');
  if (!cv) return null;
  const dpr = window.devicePixelRatio || 1;
  const d = cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;
  // 顶部 22 CSS px 是信息覆盖条，跳过它，从 26px 起算
  const y0 = Math.round(26 * dpr);
  const y1 = Math.round(cv.height * 0.20);
  const y2 = Math.round(cv.height * 0.80);
  const y3 = Math.round(cv.height - 4 * dpr);
  const dark = (ya, yb) => {
    let n = 0;
    for (let y = ya; y < yb; y++) {
      for (let x = 0; x < cv.width; x++) {
        const i = (y * cv.width + x) * 4;
        if (d[i] < 40 && d[i+1] < 40 && d[i+2] < 50) n++;
      }
    }
    return n;
  };
  return { top: dark(y0, y1), bottom: dark(y2, y3) };
})()`);

await evalJs("location.hash = '#/plot/fractal'");
await sleep(4500);

console.log("── 分形 y 轴朝向（屏幕上方 = 复平面 y 大）──");
const rect = await evalJs("(function(){const r=document.querySelector('canvas').getBoundingClientRect();return {x:r.left,y:r.top,w:r.width,h:r.height};})()");
const resetClicked = await evalJs(`(function(){
  const b = document.querySelector('.vc-btn[title="重置视图"]');
  if (!b) return 'no-btn'; b.click(); return 'clicked';
})()`);
await sleep(3500);
check("重置视图按钮可用", resetClicked === "clicked", resetClicked);

// 视图默认 y∈[-1.5,1.5]（跨度 3）。向上拖半个画布高度 → 视口整体下移，窗口变成 y∈[-3,0]。
// 拖拽公式见 PlotFractalView.vue onMouseMove：dy_world = (dyPix/cssH) * span，与 cssH 无关。
await send("Input.dispatchMouseEvent", { type: "mousePressed", x: rect.x + rect.w * 0.5, y: rect.y + rect.h * 0.5, button: "left", clickCount: 1 });
await sleep(80);
await send("Input.dispatchMouseEvent", { type: "mouseMoved", button: "left", x: rect.x + rect.w * 0.5, y: rect.y + rect.h * 0.5 - rect.h * 0.499 });
await sleep(120);
await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: rect.x + rect.w * 0.5, y: rect.y + rect.h * 0.5 - rect.h * 0.499, button: "left", clickCount: 1 });
await sleep(4500);

const W = 240, H = 180, MAXITER = 256;
const truth = await engineBands({ xmin: -2, xmax: 2, ymin: -2.997, ymax: -0.003 }, W, H, MAXITER);
console.log("   引擎真值（y∈[-2.997,-0.003]）：前 20% 行内部点 =", truth && truth.first, " 后 20% 行内部点 =", truth && truth.last);
check("引擎真值可取得（集合内部集中在靠近 y=0 的上边缘）",
      !!truth && truth.last > truth.first * 10 && truth.last > 200,
      truth ? `first=${truth.first} last=${truth.last}` : "null");

const px = await pixelBands();
console.log("   画布像素：顶部条带深色 =", px && px.top, " 底部条带深色 =", px && px.bottom);
check("渲染 y 轴朝上：顶部条带是集合内部（深色）",
      !!px && px.top > 1000 && px.top > px.bottom * 3,
      px ? `top=${px.top} bottom=${px.bottom}` : "null");

// 收尾：刷新页面，把复平面窗口复位（本套件把视图拖到了 y∈[-3,0]）。
// 必须做：不清干净会污染后面跑的 cdp-plot-fractal.mjs 的像素统计。
await evalJs("location.reload(); 'ok'");
await sleep(3500);

console.log(`\n═══ 分形朝向验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|fractal-orient|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
