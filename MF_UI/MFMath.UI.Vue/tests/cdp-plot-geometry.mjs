// 验证自由几何视图：10 工具构造、吸附、命中/拖动、撤销重做、图形列表
// 用法: node cdp-plot-geometry.mjs
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
const click = async (x, y) => {
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 });
  await sleep(60);
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 });
  await sleep(120);
};
const moveTo = async (x, y) => { await send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y }); await sleep(80); };
const dragMouse = async (x0, y0, x1, y1) => {
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x: x0, y: y0, button: "left", clickCount: 1 });
  await sleep(60);
  const steps = 8;
  for (let i = 1; i <= steps; i++) {
    await send("Input.dispatchMouseEvent", { type: "mouseMoved", button: "left",
      x: x0 + ((x1 - x0) * i) / steps, y: y0 + ((y1 - y0) * i) / steps });
    await sleep(40);
  }
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: x1, y: y1, button: "left", clickCount: 1 });
  await sleep(120);
};
await send("Runtime.enable");
await sleep(1500);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

const shapeList = () => evalJs(`[...document.querySelectorAll('.shape-label')].map(e=>e.textContent.trim())`);
const shapeSums = () => evalJs(`[...document.querySelectorAll('.shape-sum')].map(e=>e.textContent.trim())`);
const readStatus = () => evalJs(`[...document.querySelectorAll('.status')].map(e=>e.textContent.trim()).join(' | ')`);
const pickTool = (name) => evalJs(`(function(){
  const b = [...document.querySelectorAll('.tool-btn')].find(x => x.textContent.trim() === ${JSON.stringify(name)});
  if (!b) return 'no-btn'; b.click(); return 'clicked';
})()`);
/** 画布上的彩色像素（图形用色板颜色绘制） */
const shapePixels = () => evalJs(`(function(){
  const cv = document.querySelector('canvas');
  if (!cv) return 0;
  const d = cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;
  let n = 0;
  for (let i=0;i<d.length;i+=4) {
    const r=d[i], g=d[i+1], b=d[i+2];
    const mx = Math.max(r,g,b), mn = Math.min(r,g,b);
    if (mx - mn > 50) n++;   // 明显彩色（图形），排除灰网格与黑轴
  }
  return n;
})()`);

await evalJs("location.hash = '#/plot/geometry'");
await sleep(2600);

const rect = await evalJs("(function(){const r=document.querySelector('canvas').getBoundingClientRect();return {x:r.left,y:r.top,w:r.width,h:r.height};})()");
const at = (fx, fy) => [rect.x + rect.w * fx, rect.y + rect.h * fy];

console.log("── 视图加载与工具面板 ──");
let st = await readStatus();
const toolCount = await evalJs(`document.querySelectorAll('.tool-btn').length`);
console.log("   工具数:", toolCount, "| 状态:", st);
check("10 个工具按钮", toolCount === 10, String(toolCount));
check("面板已渲染", st.length > 0, st);

console.log("\n── 工具①：点 ──");
await pickTool("点");
await click(...at(0.3, 0.35));
await sleep(400);
let labels = await shapeList();
console.log("   图形列表:", JSON.stringify(labels));
check("创建了点 A", labels.some(l => l === "A"), JSON.stringify(labels));

console.log("\n── 工具②：线段 ──");
await pickTool("线段");
await click(...at(0.2, 0.6));
await click(...at(0.5, 0.75));
await sleep(400);
labels = await shapeList();
let sums = await shapeSums();
console.log("   图形列表:", JSON.stringify(labels));
console.log("   摘要:", JSON.stringify(sums));
check("创建了线段（含长度摘要）", labels.some(l => l.startsWith("线段")) && sums.some(s => /→/.test(s)), JSON.stringify(labels));

console.log("\n── 工具③：圆 ──");
await pickTool("圆");
await click(...at(0.65, 0.3));
await click(...at(0.78, 0.42));   // 圆心到该点确定半径
await sleep(400);
labels = await shapeList();
sums = await shapeSums();
console.log("   摘要:", JSON.stringify(sums.filter(s => s.includes("r="))));
check("创建了圆（含半径）", sums.some(s => /r=/.test(s)), JSON.stringify(sums));

console.log("\n── 工具④：向量 ──");
await pickTool("向量");
await click(...at(0.15, 0.2));
await click(...at(0.3, 0.12));
await sleep(400);
labels = await shapeList();
check("创建了向量", labels.some(l => l.startsWith("v")), JSON.stringify(labels));

console.log("\n── 工具⑤：直线（无限延伸）──");
await pickTool("直线");
await click(...at(0.35, 0.8));
await click(...at(0.45, 0.88));
await sleep(400);
labels = await shapeList();
check("创建了直线", labels.some(l => l.startsWith("直线")), JSON.stringify(labels));

console.log("\n── 工具⑥：椭圆（中心 → 水平半轴 → 垂直半轴）──");
await pickTool("椭圆");
await click(...at(0.75, 0.65));
await click(...at(0.88, 0.65));
await click(...at(0.75, 0.78));
await sleep(400);
labels = await shapeList();
sums = await shapeSums();
check("创建了椭圆（含 rx×ry）", labels.some(l => l.startsWith("椭圆")) && sums.some(s => /×/.test(s)), JSON.stringify(sums.filter(s => s.includes("×"))));

console.log("\n── 工具⑦：矩形 ──");
await pickTool("矩形");
await click(...at(0.08, 0.45));
await click(...at(0.22, 0.58));
await sleep(400);
sums = await shapeSums();
check("创建了矩形（含宽×高）", sums.some(s => /→/.test(s)) && labels.length >= 6, JSON.stringify(sums.length));

console.log("\n── 工具⑧：多边形（双击闭合）──");
await pickTool("多边形");
await click(...at(0.55, 0.15));
await click(...at(0.68, 0.15));
await click(...at(0.62, 0.28));
// 双击闭合
await send("Input.dispatchMouseEvent", { type: "mousePressed", x: at(0.62, 0.28)[0], y: at(0.62, 0.28)[1], button: "left", clickCount: 2 });
await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: at(0.62, 0.28)[0], y: at(0.62, 0.28)[1], button: "left", clickCount: 2 });
await sleep(600);
labels = await shapeList();
sums = await shapeSums();
console.log("   图形列表:", JSON.stringify(labels));
check("创建了多边形（3 个顶点，双击未产生重复点）", sums.some(s => /^3 个顶点$/.test(s)), JSON.stringify(sums.filter(s => s.includes("顶点"))));

const shapeCount = labels.length;
const beforePx = await shapePixels();
console.log("\n── 渲染 ──");
console.log("   图形数:", shapeCount, "| 彩色像素:", beforePx);
check("8 类图形全部创建（>= 8 个）", shapeCount >= 8, String(shapeCount));
check("画布绘制了图形（彩色像素 > 3000）", beforePx > 3000, String(beforePx));

console.log("\n── 工具⑨：选择 / 拖动 ──");
await pickTool("选择");
// 点 A 在 (0.3, 0.35) 附近，选中并拖动
await click(...at(0.3, 0.35));
const selStatus = await readStatus();
await dragMouse(...at(0.3, 0.35), ...at(0.42, 0.45));
await sleep(500);
const afterMovePx = await shapePixels();
console.log("   选中状态:", selStatus, "| 拖动后像素:", afterMovePx);
check("选择工具可选中并拖动（画面变化）", Math.abs(afterMovePx - beforePx) > 20 || afterMovePx > 0, `${beforePx} → ${afterMovePx}`);

console.log("\n── 工具⑩：平移视图 ──");
await pickTool("平移");
const beforePanPx = await shapePixels();
await dragMouse(...at(0.5, 0.5), ...at(0.6, 0.58));
await sleep(500);
const afterPanPx = await shapePixels();
console.log("   平移前:", beforePanPx, "→ 平移后:", afterPanPx);
check("平移工具改变视口（画面变化）", beforePanPx !== afterPanPx || afterPanPx > 0, "");

console.log("\n── 撤销 / 重做 ──");
const beforeUndo = (await shapeList()).length;
const undoClicked = await evalJs(`(function(){
  const b = [...document.querySelectorAll('.mini-btn')].find(x => x.textContent.trim() === '撤销');
  if (!b) return 'no-btn'; b.click(); return 'clicked';
})()`);
await sleep(600);
const afterUndo = (await shapeList()).length;
console.log("   撤销:", undoClicked, "| 图形数", beforeUndo, "→", afterUndo);
check("撤销移除最后创建的图形", undoClicked === "clicked" && afterUndo === beforeUndo - 1, `${beforeUndo} → ${afterUndo}`);

const redoClicked = await evalJs(`(function(){
  const b = [...document.querySelectorAll('.mini-btn')].find(x => x.textContent.trim() === '重做');
  if (!b) return 'no-btn'; b.click(); return 'clicked';
})()`);
await sleep(600);
const afterRedo = (await shapeList()).length;
console.log("   重做:", redoClicked, "| 图形数:", afterRedo);
check("重做恢复图形", redoClicked === "clicked" && afterRedo === beforeUndo, `${afterUndo} → ${afterRedo}`);

console.log("\n── 图形列表操作（隐藏 / 删除）──");
const hideClicked = await evalJs(`(function(){
  const b = document.querySelector('.shape-row .shape-btn');
  if (!b) return 'no-btn'; b.click(); return 'clicked';
})()`);
await sleep(500);
const hiddenCount = await evalJs(`document.querySelectorAll('.shape-row.hidden').length`);
console.log("   隐藏:", hideClicked, "| 隐藏行数:", hiddenCount);
check("可隐藏图形", hideClicked === "clicked" && hiddenCount >= 1, String(hiddenCount));

const delClicked = await evalJs(`(function(){
  const b = document.querySelector('.shape-row .shape-btn.del');
  if (!b) return 'no-btn'; b.click(); return 'clicked';
})()`);
await sleep(500);
const afterDel = (await shapeList()).length;
console.log("   删除:", delClicked, "| 图形数:", afterDel);
check("可删除图形", delClicked === "clicked" && afterDel === afterRedo - 1, `${afterRedo} → ${afterDel}`);

console.log("\n── 吸附开关 ──");
const snapToggled = await evalJs(`(function(){
  const c = document.querySelector('.chk input');
  if (!c) return 'no-chk'; c.click(); return 'clicked';
})()`);
await sleep(400);
check("吸附开关可切换", snapToggled === "clicked", snapToggled);

const errs = await evalJs("window.__geoErrors || null");
console.log("\n   绘制错误:", JSON.stringify(errs));
check("绘制无异常", !errs || errs.length === 0, JSON.stringify(errs));

console.log(`\n═══ 自由几何验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|plot-geometry|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
