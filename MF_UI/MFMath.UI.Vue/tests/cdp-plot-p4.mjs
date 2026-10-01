// 验证 P4：表达式类型识别与绘制（y=f(x) / x=f(y) / r=f(θ) / 参数方程 / 点）
// 用法: node cdp-plot-p4.mjs
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

/** 把表达式列表整体替换为给定文本数组（按需补足行）
 *  注意：Vue 的 DOM 更新是异步的——点击"添加"后必须等 DOM 再填充 */
async function setList(texts) {
  // 第一步：补足行数（同步连点，状态同步更新，DOM 稍后刷新）
  await evalJs(`(function(){
    const texts = ${JSON.stringify(texts)};
    const cur = document.querySelectorAll('.expr-input').length;
    const need = texts.length - cur;
    for (let k = 0; k < need; k++) document.querySelector('.add-row')?.click();
    return 'ok';
  })()`);
  await sleep(600);
  // 第二步：逐行写入（多余行清空）
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
  await sleep(2200);
}

const readState = async () => evalJs(`(function(){
  const status = document.querySelector('.side-status')?.textContent || '';
  const errors = [...document.querySelectorAll('.expr-error')].map(e=>e.textContent.trim());
  const inputs = [...document.querySelectorAll('.expr-input')].map(i=>i.value);
  const sliders = [...document.querySelectorAll('.param-name')].map(n=>n.textContent);
  const cv = document.querySelector('canvas');
  let dark = 0;
  if (cv) {
    const d = cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;
    for (let i=0;i<d.length;i+=4) if (d[i]<80&&d[i+1]<80&&d[i+2]<80) dark++;
  }
  return { status, errors, inputs, sliders, dark };
})()`);

await evalJs("location.hash = '#/plot/2d'");
await sleep(2500);

/* ① 显式函数 y=f(x) */
console.log("── y = f(x) ──");
await setList(["y=sin(x)"]);
let st = await readState();
console.log("   状态:", st.status, "| 深色像素:", st.dark, "| 错误:", JSON.stringify(st.errors));
check("y=sin(x) 采样成功", /引擎采样\s*1\s*条曲线/.test(st.status), st.status);

/* ② 垂直关系 x = f(y) */
console.log("\n── x = f(y) ──");
await setList(["x=y^2"]);
st = await readState();
console.log("   状态:", st.status, "| 深色像素:", st.dark);
check("x=y^2（垂直关系）采样成功", /引擎采样\s*1\s*条曲线/.test(st.status), st.status);

/* ③ 极坐标 r = f(θ) */
console.log("\n── r = f(θ)（极坐标）──");
await setList(["r=2*cos(3*theta)"]);
st = await readState();
console.log("   状态:", st.status, "| 深色像素:", st.dark);
check("r=2cos(3θ)（三叶玫瑰线）采样成功", /引擎采样\s*1\s*条曲线/.test(st.status), st.status);
check("极坐标曲线已绘制（深色像素 > 300）", st.dark > 300, String(st.dark));

/* ④ 参数方程 */
console.log("\n── 参数方程 (x(t), y(t)) ──");
await setList(["(cos(t), sin(t))"]);
st = await readState();
console.log("   状态:", st.status, "| 深色像素:", st.dark);
check("(cos(t), sin(t))（单位圆）采样成功", /引擎采样\s*1\s*条曲线/.test(st.status), st.status);

/* ⑤ 点 */
console.log("\n── 点 ──");
await setList(["(2, -3)"]);
st = await readState();
console.log("   状态:", st.status, "| 深色像素:", st.dark);
check("(2, -3) 点表达式被接受（无错误）", st.errors.length === 0, JSON.stringify(st.errors));

/* ⑥ 含参 + 多类型混合（Desmos 常见用法）*/
console.log("\n── 混合：含参显式 + 极坐标 ──");
await setList(["y=a*x^2", "r=1+0.5*cos(theta)"]);
st = await readState();
console.log("   输入框:", JSON.stringify(st.inputs), "| 状态:", st.status);
console.log("   滑块:", JSON.stringify(st.sliders));
check("两条曲线同时采样成功", /引擎采样\s*2\s*条曲线/.test(st.status), st.status);
check("仅显式曲线的参数 a 生成滑块（极坐标 θ 不算参数）",
  JSON.stringify(st.sliders) === JSON.stringify(["a"]), JSON.stringify(st.sliders));

/* ⑦ 非法表达式 → 行内错误提示（不静默） */
console.log("\n── 非法表达式错误反馈 ──");
await setList(["y=(x+1"]);
st = await readState();
console.log("   输入框:", JSON.stringify(st.inputs), "| 错误提示:", JSON.stringify(st.errors));
check("括号不匹配 → 行内错误提示", st.errors.some(e => e.includes("括号")), JSON.stringify(st.errors));

console.log(`\n═══ P4 验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|plot-p4|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
