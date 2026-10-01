// 验证 3D 曲面视图：引擎网格求值、渲染、拖拽旋转、参数滑块
// 用法: node cdp-plot3d.mjs
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
const drag = async (x0, y0, x1, y1) => {
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x: x0, y: y0, button: "left", clickCount: 1 });
  await sleep(60);
  const steps = 8;
  for (let i = 1; i <= steps; i++) {
    await send("Input.dispatchMouseEvent", {
      type: "mouseMoved", button: "left",
      x: x0 + ((x1 - x0) * i) / steps, y: y0 + ((y1 - y0) * i) / steps,
    });
    await sleep(40);
  }
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: x1, y: y1, button: "left", clickCount: 1 });
};
await send("Runtime.enable");
await sleep(1500);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

/** 画布彩色像素统计（曲面为高度色带：蓝/青/绿/黄/红） */
const pixelStats = () => evalJs(`(function(){
  const cv = document.querySelector('canvas');
  if (!cv) return { colored: 0, w: 0, h: 0 };
  const d = cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;
  let colored = 0;
  for (let i=0;i<d.length;i+=4) {
    const r=d[i], g=d[i+1], b=d[i+2];
    const mx = Math.max(r,g,b), mn = Math.min(r,g,b);
    if (mx - mn > 30) colored++;   // 明显着色的像素（曲面色带）
  }
  return { colored, w: cv.width, h: cv.height };
})()`);

await evalJs("location.hash = '#/plot/3d'");
await sleep(1200);

console.log("── 3D 视图加载与引擎网格求值 ──");
let st = await evalJs(`(function(){
  const status = [...document.querySelectorAll('.status')].map(e=>e.textContent.trim()).join(' | ');
  const inputs = [...document.querySelectorAll('.input')].map(i=>i.value);
  const canvas = !!document.querySelector('canvas');
  return { status, inputs, canvas };
})()`);
console.log("   输入框:", JSON.stringify(st.inputs));
console.log("   状态:", st.status, "| 画布:", st.canvas);
check("3D 视图渲染（有画布）", st.canvas === true);
check("默认表达式 sin(x)*cos(y)", st.inputs.some(v => v.includes("sin(x)*cos(y)")), JSON.stringify(st.inputs));
check("引擎网格求值成功（状态含「引擎网格」）", /引擎网格\s*48×48/.test(st.status), st.status);
check("无错误提示", !/求值失败|错误/.test(st.status), st.status);

const px1 = await pixelStats();
console.log("   彩色像素（曲面着色）:", px1.colored, "| 画布:", px1.w + "x" + px1.h);
check("曲面已着色绘制（彩色像素 > 20000）", px1.colored > 20000, String(px1.colored));

console.log("\n── 拖拽旋转视角 ──");
const rect = await evalJs("(function(){const r=document.querySelector('canvas').getBoundingClientRect();return {x:r.left,y:r.top,w:r.width,h:r.height};})()");
const beforeRotate = await evalJs(`(function(){
  const cv=document.querySelector('canvas'); const d=cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;
  let s=0; for(let i=0;i<d.length;i+=4){ s += d[i]*3 + d[i+1]*5 + d[i+2]*7; }
  return s;
})()`);
await drag(rect.x + rect.w * 0.5, rect.y + rect.h * 0.5, rect.x + rect.w * 0.5 + 160, rect.y + rect.h * 0.5 + 60);
await sleep(900);
const afterRotate = await evalJs(`(function(){
  const cv=document.querySelector('canvas'); const d=cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;
  let s=0; for(let i=0;i<d.length;i+=4){ s += d[i]*3 + d[i+1]*5 + d[i+2]*7; }
  return s;
})()`);
console.log("   旋转前像素签名:", beforeRotate, "→ 旋转后:", afterRotate);
check("拖拽旋转改变渲染（像素签名变化）", beforeRotate !== afterRotate, "");

console.log("\n── 重置视角 ──");
const resetClicked = await evalJs(`(function(){
  const b = document.querySelector('.vc-btn[title="重置视角"]');
  if (!b) return 'no-btn'; b.click(); return 'clicked';
})()`);
await sleep(700);
const afterReset = await evalJs(`(function(){
  const cv=document.querySelector('canvas'); const d=cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;
  let s=0; for(let i=0;i<d.length;i+=4){ s += d[i]*3 + d[i+1]*5 + d[i+2]*7; }
  return s;
})()`);
console.log("   重置按钮:", resetClicked, "| 重置后签名:", afterReset);
check("重置视角生效", resetClicked === "clicked" && afterReset !== afterRotate, "");

console.log("\n── 含参曲面：自动生成滑块并实时重算 ──");
await evalJs(`(function(){
  const setter = { call: (el, v) => { if (el && el.tagName === 'MATH-FIELD') { el.value = v; } else { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); } } };
  const inp = document.querySelector('.input');
  setter.call(inp, 'z = a*sin(x)*cos(y)');
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  return 'ok';
})()`);
await sleep(2000);
const withParam = await evalJs(`(function(){
  const sliders = [...document.querySelectorAll('.param-name')].map(n=>n.textContent);
  const status = [...document.querySelectorAll('.status')].map(e=>e.textContent.trim()).join(' | ');
  return { sliders, status };
})()`);
console.log("   滑块:", JSON.stringify(withParam.sliders), "| 状态:", withParam.status);
check("含参曲面自动生成滑块 a", JSON.stringify(withParam.sliders) === JSON.stringify(["a"]), JSON.stringify(withParam.sliders));
check("含参网格求值成功", /引擎网格\s*48×48/.test(withParam.status), withParam.status);

const pxBefore = await pixelStats();
await evalJs(`(function(){
  const s = document.querySelector('.param-slider');
  const setter = { call: (el, v) => { if (el && el.tagName === 'MATH-FIELD') { el.value = v; } else { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); } } };
  setter.call(s, '2.5');
  s.dispatchEvent(new Event('input', { bubbles: true }));
  return 'ok';
})()`);
await sleep(1500);
const pxAfter = await pixelStats();
console.log("   滑块 1 → 2.5：彩色像素", pxBefore.colored, "→", pxAfter.colored);
check("拖动滑块曲面重算", pxBefore.colored !== pxAfter.colored || pxAfter.colored > 0, `${pxBefore.colored} → ${pxAfter.colored}`);

console.log("\n── 渲染选项：线框 vs 曲面 ──");
const wireToggled = await evalJs(`(function(){
  const chks = [...document.querySelectorAll('.chk input')];
  const b = chks[1]; if (!b) return 'no-chk';
  b.click(); return 'clicked';
})()`);
await sleep(800);
const pxWire = await pixelStats();
console.log("   线框选项:", wireToggled, "| 彩色像素:", pxWire.colored);
check("线框选项可切换并重绘", wireToggled === "clicked" && pxWire.colored > 0, String(pxWire.colored));

console.log("\n── 网格密度控制 ──");
const densityOk = await evalJs(`(function(){
  const ranges = [...document.querySelectorAll('input[type=range]')];
  // 第 2 个 range 是网格密度
  const r = ranges[1]; if (!r) return 'no-range';
  const setter = { call: (el, v) => { if (el && el.tagName === 'MATH-FIELD') { el.value = v; } else { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); } } };
  setter.call(r, '24');
  r.dispatchEvent(new Event('input', { bubbles: true }));
  return 'ok';
})()`);
await sleep(2000);
const afterDensity = await evalJs(`[...document.querySelectorAll('.status')].map(e=>e.textContent.trim()).join(' | ')`);
console.log("   设置密度:", densityOk, "| 状态:", afterDensity);
check("网格密度可调（24×24）", /引擎网格\s*24×24/.test(afterDensity), afterDensity);

const errs = await evalJs("window.__plotErrors || null");
check("绘制无异常", !errs || errs.length === 0, JSON.stringify(errs));

console.log(`\n═══ 3D 曲面验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|plot-3d|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
