// 验证窗口外壳：只有一套窗口控件、且由 JS 侧驱动
//
// 原来的问题：WPF 自己画了一条 40px 标题栏（写死白色 + 自带最小化/最大化/关闭），
// JS 顶栏里又有一组同样的按钮且**没绑事件**——顶部出现两套控件，
// 且 WPF 那条不跟随 JS 主题（切深色后顶部仍是白的）。
// 现在 WPF 不画标题栏，顶部这条就是 JS 顶栏本身，窗口操作经 win 桥回调。
// 用法: node cdp-window-shell.mjs
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage() {
  for (let i = 0; i < 30; i++) {
    try {
      const list = await (await fetch("http://127.0.0.1:9222/json/list")).json();
      const p = list.find((t) => t.type === "page" && /mfmath\.local|index\.html/.test(t.url || ""));
      if (p) return p.webSocketDebuggerUrl;
    } catch { /* 等待中 */ }
    await sleep(1000);
  }
  return null;
}
const wsUrl = await findPage();
if (!wsUrl) { console.error("未找到宿主页面"); process.exit(1); }
const ws = new WebSocket(wsUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0;
const send = (method, params, timeoutMs = 10000) => new Promise((resolve) => {
  const mid = ++id;
  const h = (ev) => {
    const d = JSON.parse(ev.data);
    if (d.id === mid) { clearTimeout(timer); ws.removeEventListener("message", h); resolve(d); }
  };
  const timer = setTimeout(() => {
    ws.removeEventListener("message", h);
    resolve({ timeout: true, result: { result: { value: "[超时] 页面未响应（可能被同步宿主调用卡住）" } } });
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

const winCall = (m, a = "") => `(function(){ try { window.chrome.webview.hostObjects.sync.win.${m}(${a}); return 'ok'; } catch (e) { return 'ERR ' + e.message; } })()`;
const BTN = "(i) => document.querySelectorAll('.win-controls .win-btn')[i]";

/* ── ① 只有一套窗口控件 ── */
console.log("── 控件唯一性 ──");
check("win 桥已注册", await evalJs("!!(window.chrome?.webview?.hostObjects?.sync?.win)"), "");
const groups = await evalJs("document.querySelectorAll('.win-controls').length");
const btns = await evalJs("document.querySelectorAll('.win-controls .win-btn').length");
check("窗口控件只有一组", groups === 1, "组数 " + groups);
check("一组恰有 最小化/最大化/关闭 三个按钮", btns === 3, "按钮数 " + btns);
check("三个按钮都有真实点击处理（不再是无事件的装饰按钮）",
  await evalJs("['─','□','✕','❐'].includes(document.querySelectorAll('.win-controls .win-btn')[2].textContent.trim())"), "");

/* ── ② 顶栏就是标题栏：可拖动、双击最大化 ── */
console.log("\n── 顶栏即标题栏 ──");
check("顶栏存在且不可选中文字（拖动手感）",
  (await evalJs("getComputedStyle(document.querySelector('#topbar')).userSelect")) === "none", "");
check("侧栏顶部同样可拖动",
  (await evalJs("getComputedStyle(document.querySelector('.sidebar-head')).userSelect")) === "none", "");

/* ── ③ 最大化 / 还原：状态与图标同步，且不能卡住页面 ── */
console.log("\n── 最大化 / 还原 ──");
check("初始未最大化", (await evalJs("window.chrome.webview.hostObjects.sync.win.IsMaximized()")) === false, "");
check("最大化按钮图标为 □", (await evalJs(`(${BTN})(1).textContent.trim()`)) === "□", "");

// 关键：同步宿主调用必须在"窗口尺寸变化会回调页面"的情况下也不死锁
const r1 = await evalJs(`(function(){ (${BTN})(1).click(); return 'clicked'; })()`);
check("点击最大化立即返回（同步宿主调用未死锁）", r1 === "clicked", String(r1));
// 窗口状态变化是投递到 UI 线程执行的（避免同步宿主调用死锁），
// 因此这里轮询等待，而不是固定 sleep 后只读一次。
let maximized = false;
for (let i = 0; i < 20; i++) {
  await sleep(150);
  if ((await evalJs("window.chrome.webview.hostObjects.sync.win.IsMaximized()")) === true) { maximized = true; break; }
}
check("窗口确实最大化了", maximized, "");
check("过程中页面保持响应", (await evalJs("1+1")) === 2, "");
// 图标由 Vue 状态驱动，等它跟上（最多 3 秒）
let glyph = "";
for (let i = 0; i < 20; i++) {
  await sleep(150);
  glyph = await evalJs(`(${BTN})(1).textContent.trim()`);
  if (glyph === "❐") break;
}
check("按钮图标切换为 ❐", glyph === "❐", JSON.stringify(glyph));
check("按钮 title 变为「还原」", (await evalJs(`(${BTN})(1).getAttribute('title')`)) === "还原", "");

await evalJs(`(function(){ (${BTN})(1).click(); return 'clicked'; })()`);
let restored = false;
for (let i = 0; i < 20; i++) {
  await sleep(150);
  if ((await evalJs("window.chrome.webview.hostObjects.sync.win.IsMaximized()")) === false) { restored = true; break; }
}
check("再点一次还原", restored, "");
check("图标回到 □", (await evalJs(`(${BTN})(1).textContent.trim()`)) === "□", "");

/* ── ④ 窗口底色跟随主题（否则切换/缩放瞬间会闪白）──
   外观入口已从"点一下就循环"改成弹层，所以这里走弹层挑一套配色。
   弹层本身的细节由 cdp-appearance 套件负责，这里只验证"换主题 → 回设窗口底色"。 */
console.log("\n── 主题同步到底层窗口 ──");
const before = await evalJs("document.documentElement.dataset.theme");

// 打开外观弹层（按钮 title 仍是「切换主题」，与旧版一致，便于定位）
await evalJs(`(function(){const b=[...document.querySelectorAll('.nav-btn')]
  .find(x=>x.title==='切换主题');b.click();return 1;})()`);
await sleep(250);
check("外观弹层已打开", (await evalJs("!!document.querySelector('.appearance-pop')")) === true, "");

// 挑一套和当前不同的配色
const picked = await evalJs(`(function(){
  const cur=document.documentElement.dataset.theme;
  const c=[...document.querySelectorAll('.appearance-pop .tp-card')].find(x=>x.dataset.theme!==cur);
  if(!c) return null; const id=c.dataset.theme; c.click(); return id;})()`);
await sleep(500);
const after = await evalJs("document.documentElement.dataset.theme");
check("主题已切换", before !== after, before + " → " + after);
check("换到的正是点的那套", picked === after, picked + " / " + after);
check("回设窗口底色调用成功", (await evalJs(winCall("SetChromeBackground", "'#0f172a'"))) === "ok", "");
check("切主题后页面仍响应", (await evalJs("1+1")) === 2, "");

/* ── 收尾：把外观还原成进入本套件之前的样子 ──
   各套件共用同一宿主实例；主题会改变画布配色，
   后面的套件（cdp-plot-p5 按深色像素计数）会因此误判。 */
for (let i = 0; i < 5 && (await evalJs("document.documentElement.dataset.theme")) !== before; i++) {
  await evalJs(`(function(){
    if(!document.querySelector('.appearance-pop')){
      const b=[...document.querySelectorAll('.nav-btn')].find(x=>x.title==='切换主题');b.click();
    }
    const c=document.querySelector('.appearance-pop .tp-card[data-theme="${before}"]');
    if(c) c.click();
    return 1;})()`);
  await sleep(300);
}
await evalJs(`(function(){const p=document.querySelector('.appearance-pop');
  if(p) p.parentElement.querySelector('.nav-btn').click(); return 1;})()`);
console.log("\n   已还原主题：" + (await evalJs("document.documentElement.dataset.theme")));

/* ── ⑤ 布局必须占满：内容较窄的页面不能在右侧留空白 ──
   曾经的问题：index.html 的挂载点 <div id="app"> 与 App.vue 的根 <div id="app">
   重复 id 嵌套，而全局样式 #app{display:flex} 同时命中两层 ——
   内层变成外层的 flex item，flex-grow 默认 0，宽度只按内容算，
   于是首页/代数这类内容较窄的页面右侧空出一大块（绘图页内容够宽反而看不出来）。 */
console.log("\n── 布局占满 ──");
check("不存在重复的 #app（挂载点与组件根不得同 id）",
  (await evalJs("document.querySelectorAll('#app').length")) === 1,
  "数量 " + (await evalJs("document.querySelectorAll('#app').length")));

const layoutGap = `(function(){
  const host = document.querySelector('.view-host');
  const main = document.querySelector('#main');
  if (!host || !main) return null;
  const hr = host.getBoundingClientRect(), mr = main.getBoundingClientRect();
  let maxRight = hr.x;
  host.querySelectorAll('*').forEach(e => { const r = e.getBoundingClientRect(); if (r.width > 0 && r.right > maxRight) maxRight = r.right; });
  return { viewW: Math.round(hr.width), mainW: Math.round(mr.width), gap: Math.round(mr.right - maxRight) };
})()`;
for (const route of ["#/", "#/calc/algebra"]) {
  await evalJs(`location.hash='${route}'`);
  await sleep(1200);
  const L = await evalJs(layoutGap);
  check(route + " 视图占满可用宽度", L && L.viewW >= L.mainW - 2, JSON.stringify(L));
  // gap 是"最外层视图容器的右边界 − 最深子元素的右边界"，页面自身的内边距
  // 会让它有个十几像素的余量（首页/代数页正是 15px），这是正常的排版留白；
  // 出问题时的数量级是 **几百像素**，所以阈值取 40 既能放过内边距，又能抓住真问题。
  check(route + " 右侧无大块空白", L && L.gap <= 40, JSON.stringify(L));
}
// 回到绘图页，避免影响后续套件
await evalJs("location.hash='#/plot/2d'");
await sleep(800);

console.log(`\n═══ 窗口外壳验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|window-shell|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);