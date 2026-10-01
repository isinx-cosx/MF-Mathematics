// 验证向量场视图：引擎双网格求值、箭头渲染、预设/归一化/着色/密度控制
// 用法: node cdp-plot-vector.mjs
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
await send("Runtime.enable");
await sleep(1500);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

/** 统计画布上的箭头像素（蓝色系/色带）：非背景、非网格的显著色彩像素 */
const arrowStats = () => evalJs(`(function(){
  const cv = document.querySelector('canvas');
  if (!cv) return { arrows: 0, saturated: 0 };
  const d = cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;
  let arrows = 0, saturated = 0;
  for (let i=0;i<d.length;i+=4) {
    const r=d[i], g=d[i+1], b=d[i+2];
    const mx = Math.max(r,g,b), mn = Math.min(r,g,b);
    if (mx - mn > 40) { arrows++; }            // 明显彩色（箭头本身）
    if (mx > 180 && mn < 120 && mx - mn > 80) saturated++;   // 高饱和
  }
  return { arrows, saturated };
})()`);

const readStatus = () => evalJs(`[...document.querySelectorAll('.status')].map(e=>e.textContent.trim()).join(' | ')`);

await evalJs("location.hash = '#/plot/vector'");
await sleep(3000);   // 等引擎求值 + Vue 更新 + rAF 绘制完成

console.log("── 向量场加载（引擎双网格求值）──");
const st = await evalJs(`(function(){
  const inputs = [...document.querySelectorAll('.input')].map(i=>i.value);
  const status = [...document.querySelectorAll('.status')].map(e=>e.textContent.trim()).join(' | ');
  return { inputs, status, canvas: !!document.querySelector('canvas') };
})()`);
console.log("   输入:", JSON.stringify(st.inputs));
console.log("   状态:", st.status);
check("向量场视图渲染（有画布）", st.canvas === true);
check("默认 dx=-y / dy=x（旋转场）", st.inputs.includes("-y") && st.inputs.includes("x"), JSON.stringify(st.inputs));
check("引擎双网格求值成功", /引擎向量场\s*21×21/.test(st.status), st.status);

let px = await arrowStats();
console.log("   箭头彩色像素:", px.arrows, "| 高饱和:", px.saturated);
check("箭头已绘制（彩色像素 > 3000）", px.arrows > 3000, String(px.arrows));

console.log("\n── 预设切换 ──");
const presetClicked = await evalJs(`(function(){
  const b = [...document.querySelectorAll('.preset-btn')].find(x => x.textContent.includes('径向源'));
  if (!b) return 'no-btn'; b.click(); return 'clicked';
})()`);
await sleep(1800);
const afterPreset = await evalJs(`(function(){
  const inputs = [...document.querySelectorAll('.input')].map(i=>i.value);
  const status = [...document.querySelectorAll('.status')].map(e=>e.textContent.trim()).join(' | ');
  return { inputs, status };
})()`);
console.log("   预设:", presetClicked, "→ 输入:", JSON.stringify(afterPreset.inputs));
check("预设「径向源」写入输入框", afterPreset.inputs.includes("x") && afterPreset.inputs.includes("y"), JSON.stringify(afterPreset.inputs));
check("预设后重新求值成功", /引擎向量场/.test(afterPreset.status), afterPreset.status);

console.log("\n── 归一化（等长箭头）──");
const beforeNorm = await arrowStats();
await evalJs(`(function(){
  const chk = [...document.querySelectorAll('.chk input')][0];
  chk.click(); return 'ok';
})()`);
await sleep(1200);
const afterNorm = await arrowStats();
console.log("   归一化前:", beforeNorm.arrows, "→ 归一化后:", afterNorm.arrows);
check("归一化切换后重绘", beforeNorm.arrows !== afterNorm.arrows, `${beforeNorm.arrows} → ${afterNorm.arrows}`);

console.log("\n── 按模长着色开关 ──");
await evalJs(`(function(){
  const chk = [...document.querySelectorAll('.chk input')][1];
  chk.click(); return 'ok';
})()`);
await sleep(1000);
const afterColorOff = await arrowStats();
console.log("   关闭着色后高饱和像素:", afterColorOff.saturated, "（开启时:", afterNorm.saturated, "）");
check("着色开关生效（像素分布变化）", afterColorOff.arrows !== afterNorm.arrows || afterColorOff.saturated !== afterNorm.saturated, "");

console.log("\n── 网格密度控制 ──");
const densitySet = await evalJs(`(function(){
  const ranges = [...document.querySelectorAll('input[type=range]')];
  const r = ranges[0]; if (!r) return 'no-range';
  const setter = { call: (el, v) => { if (el && el.tagName === 'MATH-FIELD') { el.value = v; } else { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); } } };
  setter.call(r, '11');
  r.dispatchEvent(new Event('input', { bubbles: true }));
  return 'ok';
})()`);
await sleep(1800);
const densityStatus = await readStatus();
console.log("   设置密度:", densitySet, "| 状态:", densityStatus);
check("网格密度可调（11×11）", /引擎向量场\s*11×11/.test(densityStatus), densityStatus);

console.log("\n── 参数滑块（含参向量场）──");
await evalJs(`(function(){
  const setter = { call: (el, v) => { if (el && el.tagName === 'MATH-FIELD') { el.value = v; } else { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); } } };
  const inp = document.querySelector('.input');
  setter.call(inp, '-a*y');
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  return 'ok';
})()`);
await sleep(1800);
const withParam = await evalJs(`(function(){
  const sliders = [...document.querySelectorAll('.param-name')].map(n=>n.textContent);
  const status = [...document.querySelectorAll('.status')].map(e=>e.textContent.trim()).join(' | ');
  return { sliders, status };
})()`);
console.log("   滑块:", JSON.stringify(withParam.sliders), "| 状态:", withParam.status);
check("含参向量场生成滑块 a", JSON.stringify(withParam.sliders) === JSON.stringify(["a"]), JSON.stringify(withParam.sliders));
check("含参向量场求值成功", /引擎向量场/.test(withParam.status), withParam.status);

console.log("\n── 缩放/平移重采样 ──");
const rect = await evalJs("(function(){const r=document.querySelector('canvas').getBoundingClientRect();return {x:r.left,y:r.top,w:r.width,h:r.height};})()");
await send("Input.dispatchMouseEvent", { type: "mouseWheel", x: rect.x + rect.w / 2, y: rect.y + rect.h / 2, deltaX: 0, deltaY: -240 });
await sleep(1500);
const afterZoom = await readStatus();
console.log("   缩放后状态:", afterZoom);
check("缩放后按新范围重采样", /引擎向量场/.test(afterZoom), afterZoom);

const errs = await evalJs("window.__plotErrors || null");
check("绘制无异常", !errs || errs.length === 0, JSON.stringify(errs));

console.log(`\n═══ 向量场验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|plot-vector|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
