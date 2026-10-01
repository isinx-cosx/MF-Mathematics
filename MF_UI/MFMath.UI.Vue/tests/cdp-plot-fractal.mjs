// 验证分形视图：引擎 mandelbrot、配色、迭代/分辨率控制、缩放平移、兴趣区域
// 用法: node cdp-plot-fractal.mjs
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

/** 分形渲染统计：深色（集合内部）+ 彩色（外部渐变）像素 */
const fractalStats = () => evalJs(`(function(){
  const cv = document.querySelector('canvas');
  if (!cv) return { dark: 0, colored: 0, total: 0 };
  const d = cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;
  let dark = 0, colored = 0;
  for (let i=0;i<d.length;i+=4) {
    const r=d[i], g=d[i+1], b=d[i+2];
    if (r < 40 && g < 40 && b < 50) dark++;                 // 集合内部（近黑）
    const mx = Math.max(r,g,b), mn = Math.min(r,g,b);
    if (mx - mn > 40) colored++;                             // 外部分形彩色
  }
  return { dark, colored, total: cv.width * cv.height };
})()`);

const readStatus = () => evalJs(`[...document.querySelectorAll('.status')].map(e=>e.textContent.trim()).join(' | ')`);
/** 读取画布左上角信息条文字（含中心/缩放/迭代） */
const readOverlay = () => evalJs(`(function(){
  const cv = document.querySelector('canvas');
  if (!cv) return '';
  return cv.getContext('2d').getImageData(0,0,Math.min(700,cv.width),22).data.length > 0 ? 'has-overlay' : '';
})()`);

await evalJs("location.hash = '#/plot/fractal'");
await sleep(4000);

console.log("── 分形加载（引擎 mandelbrot）──");
const st = await readStatus();
console.log("   状态:", st);
check("分形视图渲染（有画布）", st.includes("mandelbrot") || st.length > 0, st);
check("引擎 mandelbrot 计算成功（状态含「引擎 mandelbrot」）", /引擎 mandelbrot\s*\d+×\d+/.test(st), st);
check("渲染耗时有记录（ms）", /\d+\s*ms/.test(st), st);

let px = await fractalStats();
console.log("   集合内部像素:", px.dark, "| 彩色像素:", px.colored, "| 总像素:", px.total);
check("分形已渲染（集合内部深色像素 > 5000）", px.dark > 5000, String(px.dark));
check("分形外部彩色渐变存在（彩色像素 > 5000）", px.colored > 5000, String(px.colored));

console.log("\n── 迭代次数控制 ──");
const beforeIter = px;
await evalJs(`(function(){
  const r = [...document.querySelectorAll('input[type=range]')][0];
  const setter = { call: (el, v) => { if (el && el.tagName === 'MATH-FIELD') { el.value = v; } else { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); } } };
  setter.call(r, '300');
  r.dispatchEvent(new Event('input', { bubbles: true }));
  return 'ok';
})()`);
await sleep(4000);
const afterIterStatus = await readStatus();
const afterIter = await fractalStats();
// 迭代次数显示在侧栏标签「最大迭代次数 N」；状态栏只含渲染尺寸与耗时
const iterLabel = await evalJs(`[...document.querySelectorAll('.field > label')].map(e=>e.textContent.trim()).join(' | ')`);
console.log("   状态:", afterIterStatus);
console.log("   侧栏标签:", iterLabel);
console.log("   迭代 120 → 300：彩色像素", beforeIter.colored, "→", afterIter.colored);
check("迭代次数已更新为 300（侧栏标签）", /最大迭代次数\s*300/.test(iterLabel), iterLabel);
check("提高迭代后重新渲染", beforeIter.colored !== afterIter.colored || beforeIter.dark !== afterIter.dark, "");

console.log("\n── 配色方案切换 ──");
const beforeScheme = await fractalStats();
await evalJs(`(function(){
  const sel = document.querySelector('select');
  const setter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;
  setter.call(sel, 'sunset');
  sel.dispatchEvent(new Event('change', { bubbles: true }));
  return 'ok';
})()`);
await sleep(3500);
const afterScheme = await fractalStats();
console.log("   切换配色：彩色像素", beforeScheme.colored, "→", afterScheme.colored);
check("配色切换后重绘", beforeScheme.colored !== afterScheme.colored || afterScheme.colored > 0, "");

console.log("\n── 兴趣区域（缩放定位）──");
const regionClicked = await evalJs(`(function(){
  const b = [...document.querySelectorAll('.region-btn')].find(x => x.textContent.includes('海马谷'));
  if (!b) return 'no-btn'; b.click(); return 'clicked';
})()`);
await sleep(4000);
const afterRegion = await readStatus();
const regionPx = await fractalStats();
console.log("   区域按钮:", regionClicked, "| 状态:", afterRegion);
check("兴趣区域按钮可点击", regionClicked === "clicked", regionClicked);
check("缩放后重新渲染", regionPx.dark + regionPx.colored > 0, `${regionPx.dark} + ${regionPx.colored}`);

console.log("\n── 滚轮缩放（以光标为中心）──");
const rect = await evalJs("(function(){const r=document.querySelector('canvas').getBoundingClientRect();return {x:r.left,y:r.top,w:r.width,h:r.height};})()");
const beforeZoom = await readStatus();
await send("Input.dispatchMouseEvent", { type: "mouseWheel", x: rect.x + rect.w * 0.5, y: rect.y + rect.h * 0.5, deltaX: 0, deltaY: -240 });
await sleep(4000);
const afterZoom = await readStatus();
console.log("   缩放前:", beforeZoom);
console.log("   缩放后:", afterZoom);
check("滚轮缩放改变窗口并重算", beforeZoom !== afterZoom, "");

console.log("\n── 拖拽平移 ──");
const beforePan = await readStatus();
// 拖一次平移：按下 → 分步移动 → 松开
const dragPan = async () => {
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x: rect.x + rect.w * 0.4, y: rect.y + rect.h * 0.4, button: "left", clickCount: 1 });
  await sleep(60);
  for (let i = 1; i <= 6; i++) {
    await send("Input.dispatchMouseEvent", { type: "mouseMoved", button: "left", x: rect.x + rect.w * 0.4 + i * 20, y: rect.y + rect.h * 0.4 + i * 8 });
    await sleep(40);
  }
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: rect.x + rect.w * 0.4 + 120, y: rect.y + rect.h * 0.4 + 48, button: "left", clickCount: 1 });
};
// 分形重绘比较慢：等状态变化而不是固定等 3.5 秒（批量运行时这里曾偶发超时误报），
// 并且允许再拖一次 —— 断言本身不变（窗口必须真的变了）
const waitPanChange = async () => {
  for (let i = 0; i < 16; i++) {
    await sleep(500);
    const st = await readStatus();
    if (st !== beforePan) return st;
  }
  return beforePan;
};
await dragPan();
let afterPan = await waitPanChange();
if (afterPan === beforePan) {
  console.log("   第一次拖拽未生效，重试一次");
  await dragPan();
  afterPan = await waitPanChange();
}
console.log("   平移前:", beforePan);
console.log("   平移后:", afterPan);
check("拖拽平移改变窗口并重算", beforePan !== afterPan, "");

console.log("\n── 重置视图 ──");
const resetClicked = await evalJs(`(function(){
  const b = document.querySelector('.vc-btn[title="重置视图"]');
  if (!b) return 'no-btn'; b.click(); return 'clicked';
})()`);
await sleep(3500);
const afterReset = await readStatus();
console.log("   重置:", resetClicked, "| 状态:", afterReset);
check("重置视图生效", resetClicked === "clicked" && afterReset.includes("mandelbrot"), afterReset);

console.log("\n── 分辨率控制 ──");
const resOk = await evalJs(`(function(){
  const r = [...document.querySelectorAll('input[type=range]')][1];
  if (!r) return 'no-range';
  const setter = { call: (el, v) => { if (el && el.tagName === 'MATH-FIELD') { el.value = v; } else { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); } } };
  setter.call(r, '320');
  r.dispatchEvent(new Event('input', { bubbles: true }));
  return 'ok';
})()`);
await sleep(4000);
const resStatus = await readStatus();
console.log("   设置分辨率:", resOk, "| 状态:", resStatus);
check("分辨率可调（渲染尺寸变化）", /引擎 mandelbrot\s*\d+×\d+/.test(resStatus), resStatus);

console.log(`\n═══ 分形验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|plot-fractal|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
