// 控制台组件的科学计算包 + 引擎门面（在真实宿主窗口里跑）
//
// 为什么要有这条：v1 的控制台是进程内 Python，numpy / sympy / scipy 直接可用；
// v2.0 的控制台跑的是**下载来的** CPython 组件，官方 embeddable 包不含 pip、
// 不含 site-packages —— 也就是说 `import sympy` 会失败，属于"迁了但降级"。
// 现在组件包已由 MFMath.Host/tools/build-python-component.ps1 重建（带三个包）。
//
// 本测试**不重装组件**（那是几分钟的破坏性操作）：组件没装就 SKIP 并说明；
// 装了就断言三个包能 import、能真算，以及门面仍能调 C++ 引擎。
// 用法: node cdp-console-sci.mjs   （宿主需带 --remote-debugging-port=9222 启动）
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
const send = (method, params, timeoutMs = 60000) => new Promise((resolve) => {
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
// 宿主对象不能被 CDP 按值序列化：一律在页面里先 String()/JSON.stringify()
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

async function components() {
  const raw = await evalJs(`window.chrome.webview.hostObjects.sync.con.Components()`);
  try { return JSON.parse(raw); } catch { return null; }
}

/** 在控制台里跑一段 Python，等它结束，返回 {stdout, stderr, exitCode, elapsedMs} */
async function runPython(code) {
  const runId = await evalJs(`String(window.chrome.webview.hostObjects.sync.con.Start("python", ${JSON.stringify(code)}, ""))`);
  const t0 = Date.now();
  let last = null;
  while (Date.now() - t0 < 90000) {
    const raw = await evalJs(`window.chrome.webview.hostObjects.sync.con.Poll(${JSON.stringify(runId)})`);
    try { last = JSON.parse(raw); } catch { last = null; }
    if (last && last.state === "done") break;
    await sleep(400);
  }
  return last || { stdout: "", stderr: "（未取到输出）", exitCode: -1 };
}

const comp = await components();
if (!comp || !comp.python?.installed) {
  console.log("  [SKIP] CPython 组件未安装（设置 → 组件 → 安装后本测试才有意义）");
  console.log("RESULT|cdp-console-sci|0|0");
  ws.close();
  process.exit(0);
}
console.log(`  组件：CPython ${comp.python.version}，${(comp.python.bytes / 1024 / 1024).toFixed(1)} MB`);
check("组件体积是「带科学计算包」的量级（>120 MB，官方 embed 只有 10 MB）",
  (comp.python.bytes || 0) > 120 * 1024 * 1024, `${(comp.python.bytes / 1024 / 1024).toFixed(1)} MB`);

console.log("=== 三个科学计算包能不能 import、能不能真算 ===");
const sci = await runPython([
  "import sympy, numpy, scipy, mpmath",
  'print("VERSIONS", sympy.__version__, numpy.__version__, scipy.__version__, mpmath.__version__)',
  "import sympy as sp, numpy as np",
  "x = sp.Symbol('x')",
  'print("SYMPY_DIFF", sp.diff(sp.sin(x)*x, x))',
  'print("NUMPY_DET", np.linalg.det(np.array([[1.0,2.0],[3.0,4.0]])))',
  'print("SCIPY_INT", round(float(scipy.integrate.quad(lambda t: t**2, 0, 1)[0]), 6))',
].join("\n"));
const out = String(sci.stdout || "");
check("import sympy / numpy / scipy / mpmath 成功（v1 控制台本来就有）", /VERSIONS/.test(out), out.trim().slice(0, 80) || String(sci.stderr).slice(0, 80));
check("sympy 真的能算（求导 sin(x)*x）", /x\*cos\(x\) \+ sin\(x\)/.test(out), (out.match(/SYMPY_DIFF[^\n]*/) || [""])[0]);
check("numpy 真的能算（2×2 行列式 = -2）", /-2\.0/.test(out), (out.match(/NUMPY_DET[^\n]*/) || [""])[0]);
check("scipy 真的能算（∫₀¹ t²dt = 1/3）", /0\.333333/.test(out), (out.match(/SCIPY_INT[^\n]*/) || [""])[0]);
check("进程正常退出", sci.exitCode === 0, "exit=" + sci.exitCode + " " + String(sci.stderr || "").slice(0, 60));

console.log("=== 门面仍然能调 C++ 引擎（装包没把这条路弄坏）===");
const eng = await runPython([
  "import mfmath",
  'print("ENGINE_DIFF", mfmath.call("diff", expr="x^2", var="x"))',
  'print("ENGINE_SOLVE", mfmath.call("solve_sym", expr="x^2-5*x+6"))',
].join("\n"));
const eout = String(eng.stdout || "");
check("mfmath.call 求导返回 2*x", /ENGINE_DIFF 2\*x/.test(eout), (eout.match(/ENGINE_DIFF[^\n]*/) || [""])[0]);
check("mfmath.call 解方程返回 2 与 3", /ENGINE_SOLVE/.test(eout) && /'2'/.test(eout) && /'3'/.test(eout),
  (eout.match(/ENGINE_SOLVE[^\n]*/) || [""])[0].slice(0, 90));

console.log(`RESULT|cdp-console-sci|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
