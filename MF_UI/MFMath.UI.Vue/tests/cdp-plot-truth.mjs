// 绘图"真图"验证：域外断点 + 缩放适应不塌
//
// 两个用户实测报过的 bug：
//   A. e^x − ln x 画不出来 —— 引擎批量求值遇到域外点（ln x 在 x≤0）整批报错、
//      界面拿到 null 后又把 null 当 0（Number(null)===0），于是要么整条消失、
//      要么在断点处连出一条假的 y=0 线。
//   B. 点「缩放到适应」后视图塌掉 —— 采样范围是视图的 1.5 倍，里面的离群值
//      （e^x 在 x=15 处 y≈3.3e6）把范围算爆，等比修正再把量级搬到 x 轴，
//      实测 x0 变成 −2.7e6，曲线挤成一条线。
//
// 判据全部落在**画布像素**上（按曲线色 #c74440 计数），不看"有没有报错"这种假信号。
// 用法: node cdp-plot-truth.mjs   （宿主需带 --remote-debugging-port=9222 启动）
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

// 收集页面异常（悬停命中检测遇到 null 会抛，这类必须抓到）
const exceptions = [];
ws.addEventListener("message", (ev) => {
  let d; try { d = JSON.parse(ev.data); } catch { return; }
  if (d.method === "Runtime.exceptionThrown") {
    exceptions.push(String(d.params?.exceptionDetails?.exception?.description || d.params?.exceptionDetails?.text || "?"));
  }
});
await send("Runtime.enable");
await sleep(1200);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

/** 按曲线色 #c74440（Desmos 第一个颜色）统计像素：总数 / 横向跨度 / 分左右半轴 */
const RED_STATS = `(function(){
  const cv = document.querySelector('canvas');
  if (!cv) return null;
  const ctx = cv.getContext('2d');
  const d = ctx.getImageData(0, 0, cv.width, cv.height).data;
  let n = 0, minX = 1e9, maxX = -1e9, left = 0, right = 0, nearCenter = 0, midBand = 0, edgeBand = 0;
  const mid = cv.width / 2, midY = cv.height / 2;
  for (let y = 0; y < cv.height; y++) {
    for (let x = 0; x < cv.width; x++) {
      const i = (y * cv.width + x) * 4;
      // #c74440 ≈ (199,68,64)，容差放宽到 ±40 以吸收抗锯齿
      if (Math.abs(d[i] - 199) < 45 && Math.abs(d[i+1] - 68) < 45 && Math.abs(d[i+2] - 64) < 45) {
        n++;
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (x < mid) left++; else right++;
        if (Math.abs(x - mid) <= 3) nearCenter++;
        // 中带：假连线（跨渐近线直连）一定会穿过这里；
        // 而 1/x 的合法分支只在画布上/下边缘收口，不会出现在中带。
        if (Math.abs(x - mid) <= 6) {
          if (Math.abs(y - midY) <= cv.height * 0.25) midBand++; else edgeBand++;
        }
      }
    }
  }
  return { n, span: n ? (maxX - minX) : 0, left, right, nearCenter, midBand, edgeBand, w: cv.width, h: cv.height };
})()`;

/** 设置第 1 行表达式 */
const setExpr = (text) => evalJs(`(function(){
  const inp = document.querySelector('.expr-input') || document.querySelector('math-field');
  if (!inp) return 'no-input';
  inp.value = ${JSON.stringify(text)};
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  inp.dispatchEvent(new Event('change', { bubbles: true }));
  return 'ok';
})()`);

console.log("── A. 域外点必须「断开」，不能连出假线 ──");
await evalJs("location.hash = '#/'");
await sleep(700);
await evalJs("location.hash = '#/plot/2d'");
await sleep(2600);

// ① e^x − ln x：ln 的定义域是 x>0，左半轴应当没有曲线像素
await setExpr("e^x-ln x");
await sleep(2600);
let st = await evalJs(RED_STATS);
console.log("    e^x−ln x:", JSON.stringify(st));
check("引擎接受了这个写法（无处可去则整条消失）", st && st.n > 0, st ? "红色像素 " + st.n : "无画布");
check("右半轴（x>0）画出了曲线", st && st.right > 50, st ? "右半轴 " + st.right : "");
check("左半轴（x≤0，ln 域外）没有曲线 —— 断开而不是硬画",
  st && st.left <= Math.max(5, st.right * 0.02), st ? "左半轴 " + st.left + "（右半轴 " + st.right + "）" : "");

// ② 1/x：两侧都有曲线，但 x=0 处必须断开（不能横跨一条假线）
await setExpr("1/x");
await sleep(2600);
st = await evalJs(RED_STATS);
console.log("    1/x:", JSON.stringify(st));
check("1/x 两侧都画出", st && st.left > 20 && st.right > 20, st ? "左 " + st.left + " / 右 " + st.right : "");
check("1/x 没有横跨渐近线的假连线（中带无红色像素）", st && st.midBand <= 20,
  st ? `中带 ${st.midBand} 像素 / 边缘收口 ${st.edgeBand} 像素` : "");

console.log("\n── B. 缩放到适应不能把视图弄塌 ──");
await setExpr("e^x");
await sleep(2600);
const before = await evalJs(RED_STATS);
console.log("    fit 前:", JSON.stringify(before));
const clicked = await evalJs(`(function(){
  const b = document.querySelector('[title="缩放到适应"]');
  if (!b) return 'no-btn';
  b.click(); return 'clicked';
})()`);
await sleep(2600);
const after = await evalJs(RED_STATS);
console.log("    fit 后:", JSON.stringify(after), "| 按钮:", clicked);
check("找到并点到「缩放到适应」", clicked === "clicked", String(clicked));
check("适应后曲线仍然可见（像素数不塌）",
  after && before && after.n >= Math.max(80, before.n * 0.5),
  after && before ? `${before.n} → ${after.n}` : "");
check("适应后曲线仍有横向展开（没被挤成一条竖线）",
  after && after.span >= after.w * 0.1, after ? `横向跨度 ${after.span}px / 画布 ${after.w}px` : "");

console.log("\n── C. 悬停命中检测不能因断点抛异常 ──");
await setExpr("e^x-ln x");
await sleep(2200);
await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 620, y: 260, button: "none" });
await sleep(400);
await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 640, y: 300, button: "none" });
await sleep(900);
const hoverErr = exceptions.filter((e) => /Cannot read|undefined|null|destructur/i.test(e));
console.log("    页面异常数:", exceptions.length, hoverErr.length ? "（其中解构相关 " + hoverErr.length + "）" : "");
check("移动鼠标到曲线上没有 JS 异常", hoverErr.length === 0, hoverErr.slice(0, 2).join(" | "));

console.log(`\n═══ 绘图真图验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|cdp-plot-truth|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
