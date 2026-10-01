// 验证 P5 渐近线处理：y=1/x、y=tan(x) 的曲线不应在渐近线处出现竖向连线
// 判据：找到画布中"深色像素占列高比例 > 80%"的列（竖向长连线）
// 用法: node cdp-plot-asymptote.mjs
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

async function setExpr(text) {
  // 输入框现在是 MathLive 的 <math-field>（数学就地排版），不再是 <input>。
  // 这里两种都支持：老式 input 用原生 setter，math-field 直接赋 value。
  await evalJs(`(function(){
    const el = document.querySelector('.expr-input');
    if (!el) return 'no-input';
    if (el.tagName === 'MATH-FIELD') {
      el.value = ${JSON.stringify(text)};
      el.dispatchEvent(new Event('input', { bubbles: true }));
    } else {
      // 输入框可能是 MathLive 的 <math-field>（数学就地排版）或普通 input，两种都支持：
    const setter = { call: (el, v) => { if (el && el.tagName === 'MATH-FIELD') { el.value = v; } else { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); } } };
      setter.call(el, ${JSON.stringify(text)});
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }
    return 'ok';
  })()`);
  await sleep(2500);
}

/** 统计"竖直长连线"：某列深色像素占比超过阈值的列数，以及该曲线颜色像素总量 */
const verticalLineStats = () => evalJs(`(function(){
  const cv = document.querySelector('canvas');
  const W = cv.width, H = cv.height;
  const d = cv.getContext('2d').getImageData(0,0,W,H).data;
  // 判定"曲线色"像素：偏红（#c74440 系）；深色=曲线主色
  const isCurve = (r,g,b) => (r>140 && r<230 && g<130 && b<130);
  let tallCols = 0, curvePx = 0;
  for (let x = 0; x < W; x++) {
    let cnt = 0;
    for (let y = 0; y < H; y++) {
      const i = (y*W + x)*4;
      if (isCurve(d[i], d[i+1], d[i+2])) cnt++;
    }
    curvePx += cnt;
    if (cnt > H * 0.8) tallCols++;
  }
  return { W, H, tallCols, curvePx };
})()`);

await evalJs("location.hash = '#/plot/2d'");
await sleep(2500);

/* ① 基线：光滑曲线不应有竖向连线 */
console.log("── 基线 y=x^2 ──");
await setExpr("y=x^2");
let st = await verticalLineStats();
console.log("   竖直长连线列数:", st.tallCols, "| 曲线像素:", st.curvePx);
check("光滑曲线无竖向长连线", st.tallCols === 0, String(st.tallCols));

/* ② y=1/x：x=0 处为渐近线，必须断开 */
console.log("\n── 渐近线 y=1/x ──");
await setExpr("y=1/x");
st = await verticalLineStats();
console.log("   竖直长连线列数:", st.tallCols, "| 曲线像素:", st.curvePx);
check("y=1/x 采样成功（有曲线像素）", st.curvePx > 500, String(st.curvePx));
check("y=1/x 在 x=0 渐近线处断开（无竖向长连线）", st.tallCols === 0, String(st.tallCols));

/* ③ y=tan(x)：每 π/2 处有渐近线 */
console.log("\n── 渐近线 y=tan(x) ──");
await setExpr("y=tan(x)");
st = await verticalLineStats();
console.log("   竖直长连线列数:", st.tallCols, "| 曲线像素:", st.curvePx);
check("y=tan(x) 采样成功（有曲线像素）", st.curvePx > 500, String(st.curvePx));
check("y=tan(x) 各渐近线处断开（无竖向长连线）", st.tallCols === 0, String(st.tallCols));

/* ④ 对照：若把断点检测禁用会大量出现竖线——用极窄视图验证判据本身有效 */
console.log("\n── 缩放后仍无竖线（y=tan(x) 放大到渐近线附近）──");
await evalJs(`document.querySelector('[title="放大"]')?.click()`);
await evalJs(`document.querySelector('[title="放大"]')?.click()`);
await sleep(1500);
st = await verticalLineStats();
console.log("   放大后竖直长连线列数:", st.tallCols, "| 曲线像素:", st.curvePx);
check("放大后仍无竖向长连线", st.tallCols === 0, String(st.tallCols));

const errs = await evalJs("window.__plotErrors || null");
check("绘制无异常", !errs || errs.length === 0, JSON.stringify(errs));

console.log(`\n═══ 渐近线验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|plot-asymptote|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
