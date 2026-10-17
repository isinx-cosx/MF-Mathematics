// 验证 P4：不等式区域填充 + 隐式方程（marching squares）
// 用法: node cdp-plot-region.mjs
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

async function setExprs(texts) {
  await evalJs(`(function(){
    const cur = document.querySelectorAll('.expr-input').length;
    const need = ${texts.length} - cur;
    for (let k = 0; k < need; k++) document.querySelector('.add-row')?.click();
    return 'ok';
  })()`);
  await sleep(500);
  await evalJs(`(function(){
    // 输入框可能是 MathLive 的 <math-field>（数学就地排版）或普通 input，两种都支持：
    const setter = { call: (el, v) => { if (el && el.tagName === 'MATH-FIELD') { el.value = v; } else { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); } } };
    const texts = ${JSON.stringify(texts)};
    [...document.querySelectorAll('.expr-input')].forEach((inp, i) => {
      setter.call(inp, texts[i] || '');
      inp.dispatchEvent(new Event('input', { bubbles: true }));
    });
    return 'ok';
  })()`);
  await sleep(2500);
}

/** 统计画布上「指定色相」的像素数：用于判断区域是否被填充为曲线色的半透明块 */
const colorStats = (hex) => evalJs(`(function(){
  const h = ${JSON.stringify(hex)}.replace('#','');
  const tr = parseInt(h.slice(0,2),16), tg = parseInt(h.slice(2,4),16), tb = parseInt(h.slice(4,6),16);
  const cv = document.querySelector('canvas');
  const status = document.querySelector('.side-status')?.textContent || '';
  const errors = [...document.querySelectorAll('.expr-error')].map(e=>e.textContent.trim());
  if (!cv) return { status, errors, tinted: 0, painted: 0 };
  const d = cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;
  let tinted = 0, painted = 0;
  for (let i=0;i<d.length;i+=4) {
    const r=d[i], g=d[i+1], b=d[i+2];
    if (!(r>250&&g>250&&b>250)) painted++;
    // "偏该色相"的像素：该通道明显高于其它两通道（半透明填充后仍偏色）
    const mx = Math.max(r,g,b), mn = Math.min(r,g,b);
    if (mx - mn > 12) {
      const dr = Math.abs(r-tr), dg = Math.abs(g-tg), db = Math.abs(b-tb);
      if (dr <= dg && dr <= db) tinted++;   // 红色通道最接近 → 认定为红色调
    }
  }
  return { status, errors, tinted, painted };
})()`);

await evalJs("location.hash = '#/plot/2d'");
await sleep(2500);

/* ── ① y > x^2：上侧区域填充 ── */
console.log("── 不等式 y > x^2 ──");
await setExprs(["y>x^2"]);
let st = await colorStats("#c74440");
console.log("   状态:", st.status);
console.log("   错误:", JSON.stringify(st.errors));
console.log("   红色调像素:", st.tinted, "| 非白像素:", st.painted);
check("y>x^2 采样成功", /引擎采样\s*1\s*条曲线/.test(st.status), st.status);
check("区域已填充（红色调像素 > 5000）", st.tinted > 5000, String(st.tinted));
const upperFill = st.tinted;

/* ── ② y < x^2：下侧区域填充（面积应与上侧不同，说明方向生效）── */
console.log("\n── 不等式 y < x^2 ──");
await setExprs(["y<x^2"]);
st = await colorStats("#c74440");
console.log("   红色调像素:", st.tinted, "| 非白像素:", st.painted);
check("y<x^2 采样成功", /引擎采样\s*1\s*条曲线/.test(st.status), st.status);
check("方向生效（下侧填充与上侧不同）", st.tinted !== upperFill, `${st.tinted} vs ${upperFill}`);

/* ── ③ x < g(y)：垂直界 ── */
console.log("\n── 不等式 x < 2 ──");
await setExprs(["x<2"]);
st = await colorStats("#c74440");
console.log("   红色调像素:", st.tinted);
check("x<2 采样成功", /引擎采样\s*1\s*条曲线/.test(st.status), st.status);
check("垂直区域已填充", st.tinted > 5000, String(st.tinted));

/* ── ④ 隐式方程 x^2+y^2=4：圆（marching squares）── */
console.log("\n── 隐式方程 x^2+y^2=4 ──");
await setExprs(["x^2+y^2=4"]);
st = await colorStats("#c74440");
console.log("   状态:", st.status, "| 错误:", JSON.stringify(st.errors));
console.log("   红色调像素:", st.tinted, "| 非白像素:", st.painted);
check("隐式方程无解析错误", st.errors.length === 0, JSON.stringify(st.errors));
check("隐式曲线已绘制（红色调像素 > 800）", st.tinted > 800, String(st.tinted));

/* ── ⑤ 二元不等式区域 x^2+y^2<4 ── */
console.log("\n── 二元区域 x^2+y^2<4 ──");
await setExprs(["x^2+y^2<4"]);
st = await colorStats("#c74440");
console.log("   红色调像素:", st.tinted, "| 非白像素:", st.painted);
check("二元区域已填充（红色调像素 > 20000）", st.tinted > 20000, String(st.tinted));

/* ── ⑥ 含参隐式方程（参数代入）── */
console.log("\n── 含参隐式 x^2+y^2=a ──");
await setExprs(["x^2+y^2=a"]);
st = await colorStats("#c74440");
  /* ③ 契约：参数滑块不再自动铺开，先提示、点「添加滑块」才出现 */
  await evalJs(`(function(){ const b = document.querySelector('.slider-add'); if (b) b.click(); return 'ok'; })()`);
  await sleep(600);  const sliders = await evalJs(`[...document.querySelectorAll('.param-name')].map(n=>n.textContent)`);
console.log("   滑块:", JSON.stringify(sliders), "| 红色调像素:", st.tinted, "| 错误:", JSON.stringify(st.errors));
check("含参隐式方程点添加后生成滑块 a", JSON.stringify(sliders) === JSON.stringify(["a"]), JSON.stringify(sliders));
check("含参隐式曲线已绘制", st.tinted > 800, String(st.tinted));

console.log(`\n═══ 不等式/隐式方程验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|plot-region|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
