// verify-spike.mjs —— Rust 宿主 spike 的验收（S1 + S2）
//
// 验的是**这个迁移唯一可能翻车的点**：前端那套 **同步** 宿主对象接缝
// （`window.chrome.webview.hostObjects.sync.*`）在 wry/WebView2 下能不能原样成立。
//
// 用法：
//   1) 先跑 Rust 宿主（它自己会开 CDP 9222）：
//        MFMath.Host.Rust\target\debug\mfmath-host-rust.exe
//   2) node MFMath.Host.Rust/tools/verify-spike.mjs
//
// 输出沿用本仓库测试脚本的约定：最后一行 `RESULT|名字|通过|失败`，逐条 [OK]/[FAIL]。
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage() {
  for (let i = 0; i < 30; i++) {
    try {
      const list = await (await fetch("http://127.0.0.1:9222/json/list")).json();
      const p = list.find((t) => t.type === "page" && /mfmath\.local|index\.html/.test(t.url || ""));
      if (p) return p;
    } catch { /* 等宿主 */ }
    await sleep(1000);
  }
  return null;
}

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

const page = await findPage();
if (!page) {
  console.error("未找到宿主页面（Rust 宿主没在跑？或它不是用 --remote-debugging-port=9222 启动的）");
  console.log("RESULT|verify-spike|0|1");
  process.exit(1);
}
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

let id = 0;
const pending = new Map();
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
};
function cmd(method, params = {}, ms = 20000) {
  return new Promise((resolve) => {
    const mid = ++id;
    const tm = setTimeout(() => { pending.delete(mid); resolve({ timeout: true }); }, ms);
    pending.set(mid, (m) => { clearTimeout(tm); resolve(m); });
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
}
const ev = async (expr) => {
  const r = await cmd("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  return r?.result?.result?.value;
};

await cmd("Runtime.enable");
await sleep(1500);

console.log("── S1：窗口 + wwwroot 是否真的加载了 ──");
const pageInfo = await ev(`(function(){
  return { title: document.title, app: document.getElementById('app') ? document.getElementById('app').children.length : -1,
           nav: document.querySelectorAll('.nav-btn, nav a, [data-tour]').length, url: location.href };
})()`);
console.log("   ", JSON.stringify(pageInfo));
check("页面来自虚拟主机 mfmath.local", /^https:\/\/mfmath\.local\//.test(pageInfo?.url || ""), pageInfo?.url);
check("Vue 应用已挂载（#app 有子节点）", (pageInfo?.app ?? 0) > 0, "children=" + pageInfo?.app);
check("界面元素已渲染（导航/按钮 > 10）", (pageInfo?.nav ?? 0) > 10, "nav=" + pageInfo?.nav);

console.log("\n── S2：同步宿主对象（前端那 45 处调用的形状）──");
const host = await ev(`(function(){
  const sync = window.chrome && window.chrome.webview && window.chrome.webview.hostObjects
             ? window.chrome.webview.hostObjects.sync : null;
  return { hasSync: !!sync, names: sync ? Object.keys(sync) : [], hasMf: !!(sync && sync.mf) };
})()`);
console.log("   ", JSON.stringify(host));
check("hostObjects.sync 存在", !!host?.hasSync);
check("宿主对象 mf 已注册（同步命名空间里可见）", !!host?.hasMf, "names=" + JSON.stringify(host?.names));

// 关键：**同步**取回引擎结果（不是 Promise）。前端 engineCall 就靠这个形状。
const call = await ev(`(function(){
  const mf = window.chrome.webview.hostObjects.sync.mf;
  const t = typeof mf.Dispatch;
  let raw, err = null;
  try { raw = mf.Dispatch("list_functions", "{}"); } catch (e) { err = String(e && e.message || e); }
  let count = null, kind = typeof raw;
  if (!err && raw != null) {
    try { count = JSON.parse(raw).value.count; } catch (e) { err = "返回值不是 JSON 字符串：" + String(e); }
  }
  return { t, kind, isPromise: !!(raw && typeof raw.then === "function"), count, err };
})()`);
console.log("   ", JSON.stringify(call));
check("mf.Dispatch 是同步函数（typeof === 'function'）", call?.t === "function", String(call?.t));
check("返回值是**字符串**而非 Promise（同步接缝成立）", call?.kind === "string" && call?.isPromise === false,
  `kind=${call?.kind} isPromise=${call?.isPromise}`);
check("引擎真的算了：list_functions.count === 424", call?.count === 424, "count=" + call?.count + (call?.err ? " err=" + call.err : ""));

const exists = await ev(`(function(){
  const mf = window.chrome.webview.hostObjects.sync.mf;
  return { yes: mf.FunctionExists("solve_quadratic"), no: mf.FunctionExists("no_such_fn") };
})()`);
check("FunctionExists 正例为真", exists?.yes === true, JSON.stringify(exists));
check("FunctionExists 反例为假", exists?.no === false, JSON.stringify(exists));

console.log(`\nRESULT|verify-spike|${pass}|${fail}`);
ws.close();
process.exit(fail ? 1 : 0);
