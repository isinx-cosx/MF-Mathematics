// 表达式归一化的语义不变性（界面侧不许改数学语义）
//
// 由来：`lib/plot/plotMath.js` 的 toEngineExpr 曾经在本地插隐式乘号
// （`1/2x` → `1/2*x`）。引擎把隐式乘法绑得比除号更紧（`1/2x` = 1/(2x) = 0.125），
// 本地插了 `*` 之后 2D/3D/向量场会画出**另一个函数**（x=4 时差 16 倍）。
// 它还替换过希腊字母（`π` → `pi`），会把 `πx` 粘成标识符 `pix`。
//
// 这条用例的死规矩只有一句：**把本地归一化的结果交给引擎，取值必须与原串一致**。
// 同一个输入在任何页面都必须算出同一个数。
//
// 用法: node cdp-expr-normalize.mjs   （宿主需带 --remote-debugging-port=9222 启动）
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

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

console.log("=== 钩子与「界面不改字面」 ===");
const hookOk = await evalJs(`typeof window.__mfToEngineExpr === "function"`);
check("归一化钩子可用（window.__mfToEngineExpr）", hookOk === true);

// ① 本地归一化**不许**动这些字面（它们要么含隐式乘法、要么含课本常量）
const literals = ["1/2x", "1/2(x+1)", "1/(x+1)(x-1)", "(x+1)(x-1)", "2x", "3sin(x)", "πx", "2π", "x²", "θ"];
for (const s of literals) {
  const out = String(await evalJs(`window.__mfToEngineExpr(${JSON.stringify(s)})`));
  check(`不改写「${s}」`, out === s, out === s ? "" : `变成 ${JSON.stringify(out)}`);
}

// ② 该保留的字面替换仍然生效（全角、×÷−）
const conv = [
  ["（x＋1）", "(x+1)"],
  ["2×x", "2*x"],
  ["6÷2", "6/2"],
  ["x−1", "x-1"],
];
for (const [input, want] of conv) {
  const out = String(await evalJs(`window.__mfToEngineExpr(${JSON.stringify(input)})`));
  check(`全角/算符符号仍转换：${input} → ${want}`, out === want, out);
}

console.log("=== 语义不变性：归一化前后交给引擎必须同值 ===");
// 用真实引擎取值；同一个表达式在 2D/3D/向量场都会走这条路径
const valueOf = async (expr, x) => {
  const code = `(() => {
    const r = window.chrome.webview.hostObjects.sync.mf.Dispatch("expr_eval_vars",
      JSON.stringify({ expr: ${JSON.stringify(expr)}, var: "x", x: ${x} }));
    const env = JSON.parse(String(r));
    return env.isError ? ("ERR:" + String(env.value).slice(0, 40)) : String(env.value);
  })()`;
  return String(await evalJs(code));
};
const samePairs = ["1/2x", "1/2(x+1)", "1/(x+1)(x-1)", "(x+1)(x-1)", "2x", "3sin(x)", "πx", "2π", "x²"];
for (const e of samePairs) {
  const raw = await valueOf(e, 4);
  const normalized = String(await evalJs(`window.__mfToEngineExpr(${JSON.stringify(e)})`));
  const viaNorm = await valueOf(normalized, 4);
  const same = raw === viaNorm && !raw.startsWith("ERR:");
  check(`「${e}」归一化前后同值`, same, `${raw} vs ${viaNorm}`);
}
// 抽查几个具体数值，防止"两边一起错"
const oneOver2x = await valueOf("1/2x", 4);
check("1/2x 在 x=4 是 0.125（= 1/(2x)，教材语义）", oneOver2x === "0.125", oneOver2x);
const piX = await valueOf("πx", 2);
check("πx 在 x=2 是 2π", Math.abs(Number(piX) - 2 * Math.PI) < 1e-9, piX);

console.log(`RESULT|cdp-expr-normalize|${pass}|${fail}`);
try { ws.close(); } catch { /* 忽略 */ }
process.exit(fail === 0 ? 0 : 1);
