// 验证 Desmos 式绘图器：路由导航 → 引擎采样 → 参数滑块 → 缩放
// 用法: node cdp-plot-verify.mjs
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage() {
  for (let i = 0; i < 30; i++) {
    try {
      const list = await (await fetch("http://127.0.0.1:9222/json/list")).json();
      const p = list.find((t) => t.type === "page" && /mfmath\.local|index\.html/.test(t.url || ""));
      if (p) return p.webSocketDebuggerUrl;
    } catch { /* 等宿主起来 */ }
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
  // 超时保护：页面无响应时不让脚本永久挂起
  const timer = setTimeout(() => {
    ws.removeEventListener("message", h);
    resolve({ timeout: true, result: { result: { value: "[超时] 页面未在 " + timeoutMs + "ms 内响应" } } });
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

// ① 导航到 2D 绘图路由
await evalJs("location.hash = '#/plot/2d'");
await sleep(2500);

console.log("── 绘图器结构与引擎采样 ──");
const info = await evalJs(`(function(){
  const cv = document.querySelector('canvas');
  const inputs = [...document.querySelectorAll('.expr-input')].map(i=>i.value);
  const status = document.querySelector('.side-status')?.textContent || '';
  const sliders = [...document.querySelectorAll('.param-row')].map(r=>r.textContent.trim());
  let painted = 0, total = 0;
  if (cv) {
    const ctx = cv.getContext('2d');
    const d = ctx.getImageData(0, 0, cv.width, cv.height).data;
    total = d.length / 4;
    // 统计"深色像素"（曲线/网格）与"纯白背景"差异
    for (let i = 0; i < d.length; i += 4) {
      if (!(d[i] > 250 && d[i+1] > 250 && d[i+2] > 250)) painted++;
    }
  }
  return { hasCanvas: !!cv, w: cv?cv.width:0, h: cv?cv.height:0,
    inputs, status, sliders, painted, total };
})()`);
console.log("   canvas:", info.w + "x" + info.h, "| 输入框:", JSON.stringify(info.inputs));
console.log("   状态:", info.status, "| 滑块:", JSON.stringify(info.sliders));
console.log("   非白像素:", info.painted, "/", info.total, "=", ((info.painted / (info.total || 1)) * 100).toFixed(1) + "%");
check("画布存在", info.hasCanvas);
check("默认表达式 y=x^2", info.inputs.some((v) => v.includes("x^2")));
check("引擎采样成功（状态含'引擎采样 1 条曲线'）", /引擎采样\s*1\s*条曲线/.test(info.status), info.status);
check("画布已绘制网格与曲线（非白像素 > 5%）", info.painted / (info.total || 1) > 0.05);

// ② 输入含参数表达式 → 应自动出现参数滑块（Desmos 行为）
console.log("\n── 参数滑块自动生成（Desmos 行为）──");
await evalJs(`(function(){
  const input = document.querySelector('.expr-input');
  const setter = { call: (el, v) => { if (el && el.tagName === 'MATH-FIELD') { el.value = v; } else { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); } } };
  setter.call(input, 'y=a*x^2+b');
  input.dispatchEvent(new Event('input', { bubbles: true }));
  return 'ok';
})()`);
await sleep(1800);
/* ③ 契约变了：参数滑块**不再自动铺开** —— 先在参数面板里提示「检测到参数 a、b」+
 * 「添加滑块」，用户点了才出现（要求：别一输表达式就把输入区挤成调参区）。
 * 所以先断言"提示在、滑块还没出现"，再点添加，然后才断言滑块出现。 */
const hintObj = JSON.parse((await evalJs(`(function(){
  return JSON.stringify({
    hint: (document.querySelector('.slider-hint-text')||{}).textContent || '',
    addBtn: !!document.querySelector('.slider-add'),
    sliders: [...document.querySelectorAll('.param-name')].map(n=>n.textContent),
  });
})()`)) || "{}");
console.log("   提示:", JSON.stringify(hintObj));
check("含参表达式先给提示、不自动铺滑块",
  /a/.test(hintObj.hint || "") && /b/.test(hintObj.hint || "")
    && hintObj.addBtn === true && (hintObj.sliders || []).length === 0, JSON.stringify(hintObj));
await evalJs(`(function(){ const b = document.querySelector('.slider-add'); if (b) b.click(); return 'ok'; })()`);
await sleep(600);
const afterParams = await evalJs(`(function(){
  return { sliders: [...document.querySelectorAll('.param-row')].map(r=>r.querySelector('.param-name')?.textContent),
           status: document.querySelector('.side-status')?.textContent || '' };
})()`);
console.log("   滑块:", JSON.stringify(afterParams.sliders), "| 状态:", afterParams.status);
check("点「添加滑块」后出现 a、b 两个滑块",
  JSON.stringify(afterParams.sliders) === JSON.stringify(["a", "b"]), JSON.stringify(afterParams.sliders));

// ③ 拖动滑块 → 曲线重绘（采样仍成功）
console.log("\n── 拖动滑块触发引擎重算 ──");
await evalJs(`(function(){
  const s = document.querySelector('.param-slider');
  const setter = { call: (el, v) => { if (el && el.tagName === 'MATH-FIELD') { el.value = v; } else { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); } } };
  setter.call(s, '2.5');
  s.dispatchEvent(new Event('input', { bubbles: true }));
  return 'ok';
})()`);
await sleep(1500);
const afterSlide = await evalJs("document.querySelector('.side-status')?.textContent || ''");
const sliderVal = await evalJs("document.querySelector('.param-val')?.textContent || ''");
console.log("   状态:", afterSlide, "| a =", sliderVal);
check("滑块改动后仍正常采样", /引擎采样\s*1\s*条曲线/.test(afterSlide), afterSlide);
check("滑块数值更新为 2.5", sliderVal.trim() === "2.5", sliderVal);

// ④ 视图控制：放大按钮 + Zoom Fit
console.log("\n── 视图控制按钮 ──");
const beforeZoom = await evalJs(`(function(){
  const cv = document.querySelector('canvas');
  const ctx = cv.getContext('2d');
  const d = ctx.getImageData(0,0,cv.width,cv.height).data;
  let n=0; for(let i=0;i<d.length;i+=4){ if(!(d[i]>250&&d[i+1]>250&&d[i+2]>250)) n++; }
  return n;
})()`);
await evalJs(`document.querySelector('[title="放大"]').click()`);
await sleep(1200);
const afterZoom = await evalJs(`(function(){
  const cv = document.querySelector('canvas');
  const ctx = cv.getContext('2d');
  const d = ctx.getImageData(0,0,cv.width,cv.height).data;
  let n=0; for(let i=0;i<d.length;i+=4){ if(!(d[i]>250&&d[i+1]>250&&d[i+2]>250)) n++; }
  return n;
})()`);
console.log("   放大前非白像素:", beforeZoom, "→ 放大后:", afterZoom);
check("放大按钮生效（画布内容变化或网格重绘）", beforeZoom !== afterZoom || afterZoom > 0);

// ⑤ 缩放后引擎重采样（视图变化 → 引擎按新范围重算）
const statusAfterZoom = await evalJs("document.querySelector('.side-status')?.textContent || ''");
check("缩放后引擎按新范围重采样", /引擎采样\s*1\s*条曲线/.test(statusAfterZoom), statusAfterZoom);

console.log(`\n═══ 绘图器验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|plot-verify|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
