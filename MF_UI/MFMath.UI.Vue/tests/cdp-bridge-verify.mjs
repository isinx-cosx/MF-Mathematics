// 验证：JS → C# MathBridge（类型化符号方法）→ C++ 引擎符号 API
// 用法: node cdp-bridge-verify.mjs
const wsUrlFrom = async () => {
  for (let i = 0; i < 30; i++) {
    try {
      const r = await fetch("http://127.0.0.1:9222/json/list");
      const list = await r.json();
      const page = list.find((t) => t.type === "page" && /mfmath\.local|index\.html/.test(t.url || ""));
      if (page) return page.webSocketDebuggerUrl;
    } catch { /* 等待宿主启动 */ }
    await new Promise((r) => setTimeout(r, 1000));
  }
  return null;
};

const wsUrl = await wsUrlFrom();
if (!wsUrl) { console.error("未找到宿主页面（确认宿主已启动且带 --remote-debugging-port=9222）"); process.exit(1); }

const ws = new WebSocket(wsUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0;
function send(method, params) {
  return new Promise((resolve) => {
    const mid = ++id;
    const h = (ev) => {
      const d = JSON.parse(ev.data);
      if (d.id === mid) { ws.removeEventListener("message", h); resolve(d); }
    };
    ws.addEventListener("message", h);
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
}
await send("Runtime.enable");
await new Promise((r) => setTimeout(r, 2500)); // 等 Vue 挂载 + 桥注入

async function evalJs(expr) {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
  if (r.result?.exceptionDetails) return "[异常] " + JSON.stringify(r.result.exceptionDetails.text);
  return r.result?.result?.value;
}

// 1) 桥是否可用
console.log("hosted      :", await evalJs("!!window.chrome?.webview?.hostObjects?.sync?.mf"));
console.log("FunctionExists(solve_sym):", await evalJs("window.chrome.webview.hostObjects.sync.mf.FunctionExists('solve_sym')"));
console.log("FunctionExists(extrema_sym):", await evalJs("window.chrome.webview.hostObjects.sync.mf.FunctionExists('extrema_sym')"));

// 2) 类型化符号方法（同一次求值内写入 DOM，避免跨调用封送问题）
const probe = `(function(){
  const mf = window.chrome.webview.hostObjects.sync.mf;
  const out = {};
  const safe = (label, fn) => { try { out[label] = String(fn()); } catch (e) { out[label] = '[异常] ' + e.message; } };
  safe('solve_sym x^2-a',        () => mf.SolveSymbolic('x^2-a', 'x'));
  safe('discriminant_sym x^2-a', () => mf.DiscriminantSymbolic('x^2-a', 'x'));
  safe('factor_sym x^2-4',       () => mf.FactorSymbolic('x^2-4', 'x'));
  safe('compare_expr',           () => mf.CompareExpr('(x+1)^2', 'x^2+2*x+1'));
  safe('free_symbols',           () => mf.FreeSymbols('x^2-3*a*x'));
  safe('diff 含参',              () => mf.Differentiate('x^3-3*a*x', 'x'));
  safe('extrema_sym 含参',       () => mf.ExtremaSymbolic('x^3-3*a*x', 'x'));
  const el = document.createElement('pre');
  el.id = '__bridge_verify';
  el.textContent = JSON.stringify(out);
  document.body.appendChild(el);
  return 'written';
})()`;
console.log("probe       :", await evalJs(probe));

const raw = await evalJs("(document.getElementById('__bridge_verify')||{}).textContent");
const results = JSON.parse(raw || "{}");
console.log("\n── 桥调用结果 ──");
let pass = 0, fail = 0;
const expect = [
  ["solve_sym x^2-a", (v) => v.includes("-sqrt(a)") && v.includes("sqrt(a)")],
  ["discriminant_sym x^2-a", (v) => v.includes("4*a")],
  ["factor_sym x^2-4", (v) => v.includes("-2") && v.includes("2")],
  ["compare_expr", (v) => v.includes("true")],
  ["free_symbols", (v) => v.includes("a") && v.includes("x")],
  ["diff 含参", (v) => v.includes("-3*a + 3*x**2")],
  ["extrema_sym 含参", (v) => v.includes("sqrt(a)") && v.includes("maximum")],
];
for (const [label, check] of expect) {
  const v = results[label] ?? "(缺失)";
  const ok = check(v);
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label.padEnd(26)} => ${v.slice(0, 110)}`);
}
console.log(`\n桥端到端：${pass} 通过 / ${fail} 失败`);
console.log(`RESULT|bridge-verify|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
