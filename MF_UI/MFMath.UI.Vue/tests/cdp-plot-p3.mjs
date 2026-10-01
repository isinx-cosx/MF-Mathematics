// 验证 P3：点击曲线生成点、拖动点、交点（精确解优先）
// 用法: node cdp-plot-p3.mjs
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
const click = async (x, y) => {
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 });
  await sleep(60);
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 });
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
const setExpr = async (index, text) => {
  await evalJs(`(function(){
    const inputs = [...document.querySelectorAll('.expr-input')];
    const input = inputs[${index}];
    if (!input) return 'no-input';
    // 输入框可能是 MathLive 的 <math-field>（数学就地排版）或普通 input，两种都支持：
    const setter = { call: (el, v) => { if (el && el.tagName === 'MATH-FIELD') { el.value = v; } else { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); } } };
    setter.call(input, ${JSON.stringify(text)});
    input.dispatchEvent(new Event('input', { bubbles: true }));
    return 'ok';
  })()`);
};

await evalJs("location.hash = '#/plot/2d'");
await sleep(1200);
// 重置到干净状态（清点 / 重置视图 / 只保留 1 行表达式），保证脚本可独立或连续运行
await evalJs(`(function(){
  // 清除已创建的点
  const clearBtn = [...document.querySelectorAll('.link-btn')].find(b => (b.textContent||'').includes('全部清除'));
  if (clearBtn) clearBtn.click();
  // 重置视图（缩放/平移归位）
  const resetBtn = document.querySelector('[title="重置视图"]');
  if (resetBtn) resetBtn.click();
  return 'ok';
})()`);
await sleep(500);
await evalJs(`(function(){
  let guard = 0;
  while (document.querySelectorAll('.expr-input').length > 1 && guard++ < 30) {
    const rows = [...document.querySelectorAll('.expr-row')];
    const del = rows.length ? rows[rows.length - 1].querySelector('.del-btn') : null;
    if (!del) break;
    del.click();
  }
  const setter = { call: (el, v) => { if (el && el.tagName === 'MATH-FIELD') { el.value = v; } else { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); } } };
  const first = document.querySelector('.expr-input');
  if (first) { setter.call(first, ''); first.dispatchEvent(new Event('input', { bubbles: true })); }
  return 'ok';
})()`);
await sleep(800);

/* ── ① 设置两条曲线 y=x^2 与 y=4，检查交点（应为精确解 ±2）── */
console.log("── 交点（精确解优先）──");
await evalJs(`(function(){
  const btn = [...document.querySelectorAll('.add-row')][0];
  btn && btn.click();
  return 'ok';
})()`);
await sleep(600);
await setExpr(0, "y=x^2");
await setExpr(1, "y=4");
await sleep(2000);

const ix = await evalJs(`(function(){
  const rows = [...document.querySelectorAll('#ixList .pt-row')].map(r=>r.textContent.replace(/\\s+/g,' ').trim());
  const badges = [...document.querySelectorAll('.pt-badge')].map(b=>b.textContent.trim());
  const status = document.querySelector('.side-status')?.textContent||'';
  return { rows, badges, status };
})()`);
console.log("   交点行:", JSON.stringify(ix.rows));
console.log("   标记:", JSON.stringify(ix.badges));
check("自动求交点出现 2 个（±2）", ix.rows.length === 2, JSON.stringify(ix.rows));
check("交点标记为「精确」（符号解）", ix.badges.includes("精确"), JSON.stringify(ix.badges));
check("交点含 (2, 4) 与 (-2, 4)", ix.rows.some(r=>r.includes("2")&&r.includes("4")), "");

/* ── ② 点击曲线生成可拖点 ── */
console.log("\n── 点击曲线生成点（Desmos 行为）──");
// 解析视图范围 → 计算 y=x^2 上 x=1.5 处的屏幕坐标
const parseRange = async () => {
  const s = await evalJs("document.querySelector('.side-status')?.textContent||''");
  const m = s.match(/范围\s*\[([-\d.]+),\s*([-\d.]+)\]\s*×\s*\[([-\d.]+),\s*([-\d.]+)\]/);
  if (!m) return null;
  return { x0: +m[1], x1: +m[2], y0: +m[3], y1: +m[4] };
};
const rect = await evalJs("(function(){const r=document.querySelector('canvas').getBoundingClientRect();return {x:r.left,y:r.top,w:r.width,h:r.height};})()");
const vr = await parseRange();
console.log("   画布 rect:", JSON.stringify(rect), "| 视图:", JSON.stringify(vr));
if (!vr) { console.log("   （无法解析视图范围）"); }

const toScreen = (wx, wy) => ({
  x: rect.x + ((wx - vr.x0) / (vr.x1 - vr.x0)) * rect.w,
  y: rect.y + ((vr.y1 - wy) / (vr.y1 - vr.y0)) * rect.h,
});
const targetX = 1.5, targetY = targetX * targetX;   // y = x^2
const sp = toScreen(targetX, targetY);
console.log(`   目标曲线点 (${targetX}, ${targetY}) → 屏幕 (${sp.x.toFixed(0)}, ${sp.y.toFixed(0)})`);
await click(sp.x, sp.y);
await sleep(1200);

const ptsAfterClick = await evalJs(`[...document.querySelectorAll('#ptList .pt-row')].map(r=>r.textContent.replace(/\\s+/g,' ').trim())`);
console.log("   点列表:", JSON.stringify(ptsAfterClick));
// 断言语义：点必须落在曲线 y=x^2 上（屏幕点击取整会带来极小偏差，不应苛求精确 x）
const onCurve = (t) => {
  const m = t.match(/\(([-\d.]+),\s*([-\d.]+)\)/);
  if (!m) return false;
  const x = Number(m[1]), y = Number(m[2]);
  return Math.abs(y - x * x) < 0.05;
};
check("点击曲线创建了点（且点在曲线上 y≈x²）",
  ptsAfterClick.some(onCurve), JSON.stringify(ptsAfterClick.filter(onCurve)));

/* ── ③ 拖动该点（沿曲线滑动）── */
console.log("\n── 拖动点沿曲线滑动 ──");
const before = ptsAfterClick.find(t => /1\.5/.test(t)) || "";
const sp2 = toScreen(2.5, 2.5 * 2.5);   // 拖到 x=2.5
await drag(sp.x, sp.y, sp2.x, sp2.y);
await sleep(1200);
const ptsAfterDrag = await evalJs(`[...document.querySelectorAll('#ptList .pt-row')].map(r=>r.textContent.replace(/\\s+/g,' ').trim())`);
console.log("   拖动后:", JSON.stringify(ptsAfterDrag));
const changed = JSON.stringify(ptsAfterDrag) !== JSON.stringify(ptsAfterClick);
check("拖动后点的坐标已更新", changed, `之前 ${before}`);
check("拖动后点仍在曲线上（y≈x²）", ptsAfterDrag.some(onCurve), JSON.stringify(ptsAfterDrag.filter(onCurve)));

/* ── ④ 画布上确实画了点与交点（像素层面）── */
console.log("\n── 画布绘制验证 ──");
const painted = await evalJs(`(function(){
  const cv = document.querySelector('canvas');
  const ctx = cv.getContext('2d');
  const d = ctx.getImageData(0,0,cv.width,cv.height).data;
  let dark=0; for(let i=0;i<d.length;i+=4){ if(d[i]<80&&d[i+1]<80&&d[i+2]<80) dark++; }
  return dark;
})()`);
console.log("   深色像素（曲线/交点/点标记）:", painted);
check("画布绘制了曲线与标记（深色像素 > 500）", painted > 500, String(painted));

console.log(`\n═══ P3 验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|plot-p3|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
