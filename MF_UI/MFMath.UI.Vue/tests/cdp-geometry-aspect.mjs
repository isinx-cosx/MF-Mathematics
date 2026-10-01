// 自由几何：等比视图 + 本轮修复的交互（中键平移 / 右键取消构造 / 切工具清空选中）。
//
// 背景（原版基准 arbitrary/geometry_canvas.py）：
//   · 全程保持等比：`scale(1,-1)` + `fitInView(INITIAL_VIEW, KeepAspectRatio)`（:203-204），
//     resize 时再 `fitInView(vr, KeepAspectRatio)`（:825-830）→ 任意窗口下 x/y 每单位像素数相同，
//     网格是正方形、世界里的圆画出来还是圆。重写版原来固定 16×12 视图，画布不是 4:3 就被拉伸。
//   · 中键：任意工具下临时切"拖手"平移（:724-729）。
//   · 右键：构造多边形且 ≥3 点则提交，否则**取消当前构造**（:731-737）。
//   · 切换工具会清空选中（set_tool 里 _set_selection(None)，:1033-1043）。
//
// 判据：
//   ① 视图不变量 spanY/spanX == cssH/cssW（等比，精确）；
//   ② 世界里的圆画出来包围盒是正方形（渲染侧不拉伸）；
//   ③ 中键拖拽改变视图且不改当前工具；
//   ④ 右键把"awaitSecond"状态取消掉、且不提交图形；
//   ⑤ 切工具后列表里不再有选中行。
//
// 用法: node tests/cdp-geometry-aspect.mjs   （需宿主已带 --remote-debugging-port=9222 启动）
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
const clickAt = async (x, y, button = "left") => {
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button, clickCount: 1 });
  await sleep(60);
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button, clickCount: 1 });
  await sleep(250);
};
const pickTool = (name) => evalJs(`(function(){
  const b = [...document.querySelectorAll('.tool-btn')].find(x => x.textContent.trim() === ${JSON.stringify(name)});
  if (!b) return 'no-btn'; b.click(); return 'clicked';
})()`);
const geo = () => evalJs("window.__geoState || null");
await send("Runtime.enable");
await sleep(1500);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

await evalJs("location.hash = '#/plot/geometry'");
await sleep(2600);

const rect = await evalJs("(function(){const r=document.querySelector('canvas').getBoundingClientRect();return {x:r.left,y:r.top,w:r.width,h:r.height};})()");
const at = (fx, fy) => [rect.x + rect.w * fx, rect.y + rect.h * fy];

console.log("── ① 等比视图不变量 ──");
await evalJs(`(function(){ const b=document.querySelector('.mini-btn.danger'); if(b) b.click(); return 'ok'; })()`);
await sleep(300);
const s0 = await geo();
console.log("   __geoState.view =", JSON.stringify(s0 && s0.view), "| 画布 =", s0 && (s0.cssW + "×" + s0.cssH));
const ratioView = s0 ? (s0.view.y1 - s0.view.y0) / (s0.view.x1 - s0.view.x0) : NaN;
const ratioCanvas = s0 ? s0.cssH / s0.cssW : NaN;
console.log("   spanY/spanX =", ratioView.toFixed(4), " cssH/cssW =", ratioCanvas.toFixed(4));
check("视图等比：spanY/spanX == cssH/cssW（原版 KeepAspectRatio）",
      isFinite(ratioView) && Math.abs(ratioView - ratioCanvas) < 1e-6,
      `${ratioView.toFixed(4)} vs ${ratioCanvas.toFixed(4)}`);

console.log("\n── ② 世界里的圆应画成圆 ──");
await pickTool("圆");
await clickAt(...at(0.50, 0.50));
await clickAt(...at(0.68, 0.50));
await sleep(500);
const labels = await evalJs(`[...document.querySelectorAll('.shape-label')].map(e=>e.textContent.trim())`);
check("圆已创建", labels.some((l) => l.startsWith("圆")), JSON.stringify(labels));

await pickTool("选择");   // 同时验证 ⑤：切工具清空选中 → 圆不再用高亮色画
await sleep(400);
const activeRows = await evalJs(`document.querySelectorAll('.shape-row.active').length`);
check("切换工具后不再有选中行（原版 set_tool 清空选中）", activeRows === 0, String(activeRows));

const bbox = await evalJs(`(function(){
  const cv = document.querySelector('canvas');
  const d = cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;
  let x0=1e9,x1=-1e9,y0=1e9,y1=-1e9,n=0;
  for (let y=0;y<cv.height;y++) for (let x=0;x<cv.width;x++) {
    const i=(y*cv.width+x)*4, r=d[i], b=d[i+2];
    if (b - r > 40 && b > 120) { n++; if(x<x0)x0=x; if(x>x1)x1=x; if(y<y0)y0=y; if(y>y1)y1=y; }
  }
  return n ? { w: x1-x0, h: y1-y0, n } : null;
})()`);
console.log("   圆像素包围盒:", bbox && (bbox.w + "×" + bbox.h), "| 蓝色像素:", bbox && bbox.n);
check("圆被画成圆（包围盒宽高差 ≤ 3px）",
      !!bbox && bbox.w > 40 && Math.abs(bbox.w - bbox.h) <= 3,
      bbox ? `${bbox.w}×${bbox.h}` : "null");

console.log("\n── ③ 中键拖拽平移（不改工具）──");
await pickTool("点");
await sleep(300);
const vBefore = (await geo()).view;
await send("Input.dispatchMouseEvent", { type: "mousePressed", x: at(0.5, 0.5)[0], y: at(0.5, 0.5)[1], button: "middle", buttons: 4, clickCount: 1 });
await sleep(60);
for (let i = 1; i <= 5; i++) {
  await send("Input.dispatchMouseEvent", { type: "mouseMoved", button: "middle", buttons: 4, x: at(0.5, 0.5)[0] + i * 16, y: at(0.5, 0.5)[1] });
  await sleep(40);
}
await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: at(0.5, 0.5)[0] + 80, y: at(0.5, 0.5)[1], button: "middle", buttons: 0, clickCount: 1 });
await sleep(600);
const afterMid = await geo();
const toolStill = await evalJs(`(document.querySelector('.tool-btn.active')||{}).textContent`);
console.log("   视图 x0:", vBefore.x0.toFixed(3), "→", afterMid.view.x0.toFixed(3), "| 工具 =", (toolStill || "").trim());
check("中键拖拽平移视图", Math.abs(afterMid.view.x0 - vBefore.x0) > 0.05, `${vBefore.x0.toFixed(3)} → ${afterMid.view.x0.toFixed(3)}`);
check("中键平移不改当前工具", (toolStill || "").trim() === "点", String(toolStill));

console.log("\n── ④ 右键取消半成品构造 ──");
await pickTool("线段");
await sleep(300);
await clickAt(...at(0.30, 0.30));
const stMid = await geo();
check("点一次后进入 awaitSecond 构造态", stMid && stMid.state === "awaitSecond", stMid && stMid.state);
const nBefore = await evalJs(`document.querySelectorAll('.shape-label').length`);
await clickAt(...at(0.60, 0.60), "right");
await sleep(400);
const stAfter = await geo();
const nAfter = await evalJs(`document.querySelectorAll('.shape-label').length`);
console.log("   右键后 state:", stAfter && stAfter.state, "| 图形数:", nBefore, "→", nAfter);
check("右键取消了半成品构造（state 回到 idle）", stAfter && stAfter.state === "idle", stAfter && stAfter.state);
check("右键没有提交图形", nAfter === nBefore, `${nBefore} → ${nAfter}`);

// 收尾：清空 + 刷新，避免污染后续套件
await evalJs(`(function(){ const b=document.querySelector('.mini-btn.danger'); if(b) b.click(); return 'ok'; })()`);
await sleep(300);
await evalJs("location.reload(); 'ok'");
await sleep(3000);

console.log(`\n═══ 自由几何等比/交互验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|geometry-aspect|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
