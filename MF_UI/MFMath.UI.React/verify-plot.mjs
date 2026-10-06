// React 绘图页的宿主内验证：真引擎、真画布、结构与 Vue 版一致。
// 用法: node verify-plot.mjs [截图输出目录]
import fs from "node:fs";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage() {
  for (let i = 0; i < 40; i++) {
    try {
      const list = await (await fetch("http://127.0.0.1:9222/json/list")).json();
      const p = list.find((t) => t.type === "page" && /mfmath\.local|index\.html/.test(t.url || ""));
      if (p) return p.webSocketDebuggerUrl;
    } catch { /* 等宿主 */ }
    await sleep(300);
  }
  return null;
}

const wsUrl = await findPage();
if (!wsUrl) { console.error("未找到宿主页面"); process.exit(1); }
const ws = new WebSocket(wsUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0;
const pend = new Map();
ws.onmessage = (e) => { const m = JSON.parse(e.data); if (pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
function cmd(method, params = {}, ms = 30000) {
  return new Promise((res) => {
    const i = ++id; let done = false;
    const t = setTimeout(() => { if (!done) { done = true; pend.delete(i); res(null); } }, ms);
    pend.set(i, (m) => { if (!done) { done = true; clearTimeout(t); res(m.result); } });
    ws.send(JSON.stringify({ id: i, method, params }));
  });
}
const ev = async (expr) => (await cmd("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }))?.result?.value;

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

await cmd("Page.enable");
await cmd("Runtime.enable");
await sleep(1800);

/* ① 结构：与 Vue 版同一套 DOM（类名/层级来自同一份模板与 theme.css） */
const dom = await ev(`(function(){
  const q = (s) => !!document.querySelector(s);
  return {
    shell: q('.app-shell'), sidebar: q('#sidebar'), nav: q('#nav'), navGroups: document.querySelectorAll('.nav-group').length,
    topbar: q('#topbar'), statusbar: q('#statusbar'), modeTitle: (document.querySelector('#modeTitle')||{}).textContent,
    layout: q('.desmos-layout'), side: q('.desmos-side'), main: q('.desmos-main'),
    exprList: q('.expr-list'), symbolBar: document.querySelectorAll('.symbol-bar .symbol-btn').length,
    mathfield: q('math-field.expr-input'), addRow: q('.add-row'),
    viewControls: document.querySelectorAll('.view-controls .vc-btn').length,
    canvas: q('canvas.plot-canvas-desmos'),
  }; })()`);
console.log("  结构: " + JSON.stringify(dom));
check("外壳结构一致（#sidebar/#nav/#topbar/#statusbar/.app-shell）",
  dom.shell && dom.sidebar && dom.nav && dom.topbar && dom.statusbar);
check("导航分组=4、模式标题=2D 函数绘图", dom.navGroups === 4 && dom.modeTitle === "2D 函数绘图", `${dom.navGroups} / ${dom.modeTitle}`);
check("绘图页结构一致（.desmos-layout/.desmos-side/.desmos-main）", dom.layout && dom.side && dom.main);
check("表达式列表与符号面板一致（16 个符号按钮 + math-field 输入框）",
  dom.exprList && dom.symbolBar === 16 && dom.mathfield && dom.addRow, String(dom.symbolBar));
check("右上角视图控制 7 个按钮", dom.viewControls === 7, String(dom.viewControls));
check("画布是 .plot-canvas-desmos", !!dom.canvas);

/** 用 MathLive 元素的值写入表达式（与用户输入同一条路径） */
async function setExpr(text) {
  await ev(`(function(){
    const f=document.querySelector('math-field.expr-input'); if(!f) return 0;
    f.value=${JSON.stringify(text)};
    f.dispatchEvent(new Event('input',{bubbles:true}));
    return 1; })()`);
  await sleep(2600);
}

const stats = () => ev(`(function(){
  const c=document.querySelector('canvas.plot-canvas-desmos'); if(!c) return null;
  const g=c.getContext('2d'); const d=g.getImageData(0,0,c.width,c.height).data;
  const isCurve=(i)=>d[i]>120 && d[i]-d[i+1]>45 && d[i]-d[i+2]>45;
  const W=c.width,H=c.height;
  const cols=[];
  for(let k=0;k<9;k++){
    const x=Math.min(W-1, Math.round(k*(W-1)/8));
    let n=0, lo=-1, hi=-1;
    for(let y=0;y<H;y++){ const i=(y*W+x)*4; if(isCurve(i)){ n++; if(lo<0)lo=y; hi=y; } }
    cols.push([Math.round(k*100/8)+'%', n, lo<0?null:[lo,hi]]);
  }
  let total=0; for(let i=0;i<d.length;i+=4) if(isCurve(i)) total++;
  return JSON.stringify({ size:[W,H], total, cols });
})()`);

console.log("\n── e^x 默认视口 ──");
await setExpr("e^x");
console.log("  状态栏: " + await ev(`(document.querySelector('#statusText')||{}).textContent`));
const base = JSON.parse(await stats());
console.log("  像素: total=" + base.total + "  " + JSON.stringify(base.cols));
check("e^x 画出了曲线", base.total > 500, String(base.total));

console.log("\n── 缩小两次（视口变大）：检查大 |x| 处是否还在画 ──");
for (let k = 0; k < 2; k++) {
  await ev(`(function(){const b=[...document.querySelectorAll('.vc-btn')].find(x=>x.getAttribute('title')==='缩小'); if(b)b.click(); return !!b;})()`);
  await sleep(1000);
}
await sleep(1800);
console.log("  状态栏: " + await ev(`(document.querySelector('#statusText')||{}).textContent`));
const big = JSON.parse(await stats());
console.log("  像素: total=" + big.total + "  " + JSON.stringify(big.cols));
check("缩小后仍然有曲线像素（大 |x| 侧没被整段丢掉）", big.total > 200, String(big.total));
const leftCols = big.cols.slice(0, 3).filter((c) => c[1] > 0).length;
const rightCols = big.cols.slice(-3).filter((c) => c[1] > 0).length;
check("左侧（负 x 方向）有曲线", leftCols > 0, JSON.stringify(big.cols.slice(0, 3)));
check("右侧（正 x 方向）有曲线", rightCols > 0, JSON.stringify(big.cols.slice(-3)));

const outDir = process.argv[2] || ".";
const shot = await cmd("Page.captureScreenshot", { format: "png" });
if (shot?.data) {
  const p = outDir + "/react-plot.png";
  fs.writeFileSync(p, Buffer.from(shot.data, "base64"));
  console.log("  截图: " + p);
}

console.log(`\nRESULT|react-plot-verify|${pass}|${fail}`);
ws.close();
process.exit(fail ? 1 : 0);
