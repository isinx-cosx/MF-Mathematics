// 自由几何 —— 无限直线（直线工具）绘制回归测试。
//
// 背景：
//   原版 plot/arbitrary/geometry_canvas.py:522-532 用 `_line_viewport_intersection`
//   （:1175-1195）求直线与视口的两个交点，再画这条线段。
//   重写版曾把"视口角点是否在视口内"当成交点判据，而四个角点恒在视口内，
//   于是 pts 恒为 4 个角点、只画前两个 → **任何直线都退化成视口底边那一条水平线段**。
//   现有 cdp-plot-geometry.mjs 只断言"直线出现在图形列表里"，查不出这个问题。
//
// 判据：
//   清空后只画一条斜率为正的直线，然后看这条线在画布上的纵向跨度：
//   · 正确：直线斜穿整个视口，彩色像素的纵向跨度接近画布高度。
//   · 退化成底边：所有彩色像素挤在底边一行，纵向跨度 ≈ 0。
//
// 用法: node tests/cdp-geometry-line.mjs   （需宿主已带 --remote-debugging-port=9222 启动）
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
const send = (method, params, timeoutMs = 20000) => new Promise((resolve) => {
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
const clickAt = async (x, y) => {
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 });
  await sleep(60);
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 });
  await sleep(150);
};
await send("Runtime.enable");
await sleep(1500);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

await evalJs("location.hash = '#/plot/geometry'");
await sleep(2600);

const rect = await evalJs("(function(){const r=document.querySelector('canvas').getBoundingClientRect();return {x:r.left,y:r.top,w:r.width,h:r.height};})()");
const at = (fx, fy) => [rect.x + rect.w * fx, rect.y + rect.h * fy];

console.log("── 准备：清空画布，只保留一条直线 ──");
const cleared = await evalJs(`(function(){
  const b = document.querySelector('.mini-btn.danger');
  if (!b) return 'no-btn'; b.click(); return 'clicked';
})()`);
await sleep(400);
const left = await evalJs(`document.querySelectorAll('.shape-label').length`);
check("清空按钮可用且画布已清空", cleared === "clicked" && left === 0, `${cleared} left=${left}`);

const picked = await evalJs(`(function(){
  const b = [...document.querySelectorAll('.tool-btn')].find(x => x.textContent.trim() === '直线');
  if (!b) return 'no-btn'; b.click(); return 'clicked';
})()`);
check("直线工具可选中", picked === "clicked", picked);

// 斜率明显为正的斜线：屏幕分数坐标 (0.30,0.28) → (0.70,0.72)
await clickAt(...at(0.30, 0.28));
await clickAt(...at(0.70, 0.72));
await sleep(500);

const labels = await evalJs(`[...document.querySelectorAll('.shape-label')].map(e=>e.textContent.trim())`);
check("已创建直线", labels.some((l) => l.startsWith("直线")), JSON.stringify(labels));

// 从图形列表读出这条直线自己的颜色（id 递增 → 颜色索引不定，不能写死）
const color = await evalJs(`(function(){
  const rows = [...document.querySelectorAll('.shape-row')];
  const row = rows.find(r => (r.querySelector('.shape-label')||{}).textContent?.startsWith('直线'));
  if (!row) return null;
  const m = (row.querySelector('.shape-dot').style.background || '').match(/(\\d+)\\D+(\\d+)\\D+(\\d+)/);
  return m ? [ +m[1], +m[2], +m[3] ] : null;
})()`);
console.log("   直线颜色:", JSON.stringify(color));
check("读到直线颜色", Array.isArray(color), JSON.stringify(color));

/** 统计与直线同色的像素：总数 + 纵向跨度（占画布高度比例）+ 靠近屏幕中点的数量 */
const linePixels = (rgb) => evalJs(`(function(){
  const cv = document.querySelector('canvas');
  if (!cv) return null;
  const d = cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;
  let n = 0, ymin = 1e9, ymax = -1e9, mid = 0;
  const cx0 = cv.width * 0.35, cx1 = cv.width * 0.65, cy0 = cv.height * 0.35, cy1 = cv.height * 0.65;
  for (let y = 0; y < cv.height; y++) {
    for (let x = 0; x < cv.width; x++) {
      const i = (y * cv.width + x) * 4;
      if (Math.abs(d[i]-${rgb[0]}) <= 46 && Math.abs(d[i+1]-${rgb[1]}) <= 46 && Math.abs(d[i+2]-${rgb[2]}) <= 46) {
        n++;
        if (y < ymin) ymin = y;
        if (y > ymax) ymax = y;
        if (x >= cx0 && x <= cx1 && y >= cy0 && y <= cy1) mid++;
      }
    }
  }
  return { n, span: n ? (ymax - ymin) / cv.height : 0, mid, h: cv.height };
})()`);

const px = await linePixels(color);
console.log("   同色像素:", px && px.n, "| 纵向跨度占画布:", px && px.span.toFixed(3), "| 画布中部像素:", px && px.mid);
// 像素计数只是"确实画了东西"的下限：±46 的颜色容差会漏掉抗锯齿边缘像素，
// 计数随画布尺寸/线宽变化，所以阈值取得很松；真正的判据是下面两条几何判据。
check("直线已绘制（同色像素 ≥ 100）", !!px && px.n >= 100, px ? String(px.n) : "null");
check("直线斜穿视口（纵向跨度 > 0.5 画布高）", !!px && px.span > 0.5, px ? px.span.toFixed(3) : "null");
check("直线经过画布中部（中点附近有像素）", !!px && px.mid > 20, px ? String(px.mid) : "null");

// 收尾：刷新页面，把图形列表与 id 计数清零。
// 必须做：本套件会留下一条直线，且图形 id 只会递增 —— 而 cdp-plot-geometry.mjs
// 断言"第一个点标签是 A"（依赖 id=1）。不清干净会让它在后面跑时误报失败。
await evalJs("location.reload(); 'ok'");
await sleep(3000);

console.log(`\n═══ 自由几何直线验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|geometry-line|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
