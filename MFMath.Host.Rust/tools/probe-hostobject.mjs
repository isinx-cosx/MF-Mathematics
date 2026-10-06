// probe-hostobject.mjs —— 只读探针：看 WebView2 的宿主对象代理**实际**给了我们什么形状
//
// 背景：S2 卡在 `typeof window.chrome.webview.hostObjects.sync.mf.Dispatch === "string"`。
// 猜测没用，先把代理的真实行为摊开：
//   · 每个成员读出来是函数还是值？值是什么（如果是我们自己的错误 JSON，说明它走了 PROPERTYGET）
//   · 异步命名空间（hostObjects.mf，不带 .sync）的形状是否不同
//   · 代理对象本身的原型/自有键（能看出它是不是 Proxy、能不能枚举）
//
// 用法：node MFMath.Host.Rust/tools/probe-hostobject.mjs
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage() {
  for (let i = 0; i < 20; i++) {
    try {
      const list = await (await fetch("http://127.0.0.1:9222/json/list")).json();
      const p = list.find((t) => t.type === "page" && /mfmath\.local|index\.html/.test(t.url || ""));
      if (p) return p;
    } catch { /* 等宿主 */ }
    await sleep(500);
  }
  return null;
}

const page = await findPage();
if (!page) { console.error("未找到宿主页面"); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0;
const pending = new Map();
ws.onmessage = (e) => { const m = JSON.parse(e.data); if (pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cmd = (method, params = {}, ms = 20000) => new Promise((resolve) => {
  const mid = ++id;
  const tm = setTimeout(() => { pending.delete(mid); resolve({ timeout: true }); }, ms);
  pending.set(mid, (m) => { clearTimeout(tm); resolve(m); });
  ws.send(JSON.stringify({ id: mid, method, params }));
});
const ev = async (expr) => {
  const r = await cmd("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r?.result?.exceptionDetails) return { __exception: r.result.exceptionDetails.text };
  return r?.result?.result?.value;
};

await cmd("Runtime.enable");
await sleep(800);

const out = await ev(`(function(){
  const ho = window.chrome.webview.hostObjects;
  const sync = ho.sync;
  const mf = sync.mf;
  const asy = ho.mf;
  const safe = (f) => { try { return f(); } catch (e) { return "EXC: " + (e && e.message || e); } };
  const show = (v) => { const s = String(v); return s.length > 160 ? s.slice(0,160) + "…" : s; };
  return {
    syncKeys: safe(() => Object.keys(sync)),
    mfOwnNames: safe(() => Object.getOwnPropertyNames(mf)),
    mfProtoCtor: safe(() => Object.getPrototypeOf(mf) && Object.getPrototypeOf(mf).constructor && Object.getPrototypeOf(mf).constructor.name),
    mfIsProxyLike: safe(() => Object.prototype.toString.call(mf)),
    // 同步命名空间下，每个成员读出来是什么
    sync_typeof_Dispatch: safe(() => typeof mf.Dispatch),
    sync_value_Dispatch: safe(() => show(mf.Dispatch)),
    sync_typeof_Ready: safe(() => typeof mf.Ready),
    sync_value_Ready: safe(() => show(mf.Ready)),
    sync_typeof_Version: safe(() => typeof mf.Version),
    sync_value_Version: safe(() => show(mf.Version)),
    sync_typeof_FunctionExists: safe(() => typeof mf.FunctionExists),
    sync_value_FunctionExists: safe(() => show(mf.FunctionExists)),
    sync_typeof_NoSuch: safe(() => typeof mf.NoSuchMethod),
    sync_value_NoSuch: safe(() => show(mf.NoSuchMethod)),
    // 异步命名空间（不带 .sync）作对照
    async_typeof_Dispatch: safe(() => typeof asy.Dispatch),
    async_value_Dispatch: safe(() => show(asy.Dispatch)),
    async_ownNames: safe(() => Object.getOwnPropertyNames(asy)),
  };
})()`);

console.log(JSON.stringify(out, null, 2));
ws.close();
