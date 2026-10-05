// 把外观清回默认值 —— 供 run-all.ps1 在任何套件之前跑一次。
//
// 为什么需要：外观选择（配色/圆角/疏密/字体）存在 localStorage 里，
// 而 WebView2 的用户数据目录是跨次运行复用的。于是上一轮跑测试时留下的
// 深色配色会粘到这一轮，而绘图类套件是按浅色画布数像素的——会出现
// "单跑能过、整套跑失败"这种最难查的假失败。
// 这里显式归零，让整套回归从确定的状态出发。
//
// 用法: node reset-appearance.mjs   （宿主需带 --remote-debugging-port=9222 启动）
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
const send = (method, params, timeoutMs = 30000) => new Promise((resolve) => {
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

const before = await evalJs("document.documentElement.dataset.theme");
// 只清**外观**这几个键，然后重新加载页面。
//
// ⚠ 不要在这里做 `localStorage.clear()`（或顺手把工作区也清了）：
//   这把 `mf_tut_progress`（教程进度）一起清掉，引导遮罩会重新弹出并拦住点击 ——
//   实测代价是 cdp-plot-geometry 从 20/0 直接掉到 5/15；清掉 `mf_theme` 还会伤到
//   后面的 cdp-canvas-theme / cdp-modes-render / cdp-diff-at-param（实测整套
//   从 53 失败恶化到 236 失败）。外观复位就只做外观复位。
//
// 另注（未解决、别在这里顺手"修"）：绘图组在同一会话里仍受前序用例影响
//   （p4/region/p5/final/asymptote/extrema-domain 在整组里失败、单独跑能过）。
//   在进入绘图组前**只重载一次页面**能让这 15 条全部转绿，但那会打破后面一大批
//   用例（audit-modes 一族出现 `未知方法: c*e*n*t*r*a*l` 之类的参数错乱），
//   所以那个做法已回退，留待单独处理。
await evalJs(`(function(){
  try {
    ['mf_theme','mf_shape','mf_density','mf_font','mf_theme_follow'].forEach((k) => localStorage.removeItem(k));
  } catch (e) {}
  return 1;})()`);
// 重新加载让 initTheme 走"没有存档"的分支，落到默认值
await send("Page.enable");
await send("Page.reload", { ignoreCache: false });
await sleep(3000);

const after = await evalJs(`(function(){
  const el = document.documentElement;
  return [el.dataset.theme, el.dataset.shape, el.dataset.density, el.dataset.font, el.dataset.mode].join('/');})()`);
const expect = "glass-light/glass/cozy/sans/light";
const ok = after === expect;
console.log(`  ${ok ? "[OK]" : "[FAIL]"} 外观已归零   ${before} → ${after}   (期望 ${expect})`);
console.log(`RESULT|reset-appearance|${ok ? 1 : 0}|${ok ? 0 : 1}`);
ws.close();
process.exit(ok ? 0 : 1);
