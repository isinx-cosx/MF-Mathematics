/**
 * cdp-plot-workspace.mjs —— 绘图页 ↔ 工作区的**往返**验证（BUGS.md B14）
 *
 * 为什么需要它：B14 给 6 个绘图页接了工作区，但 `cdp-workspace` / `cdp-shortcuts-prefs`
 * **只碰 `/plot/2d`**。而 3D / 复平面 / 向量场 / 几何 / 分形这 5 页的载荷形状是**新设计**的
 * （它们在 Vue 版时代也从来没接过工作区，没有参照物），只过了类型检查与代码审阅 ——
 * 也就是"改了但没测"。这个用例就是补那一块。
 *
 * 每页验**两个方向**（缺一不可，只验一个方向很容易放过"存了但读不回"）：
 *   ① 存：改动页面上的控件 → 工作区里那一页的载荷必须跟着变（且 kind 正确）；
 *   ② 还原：离开该页再回来 → 控件必须显示改动后的值。
 *
 * ⚠ **这个用例对"别人同时在驱动同一个页面"极其敏感**（本仓库有并行会话时会互相踩）。
 * 所以每一步之后都核对 `location.hash` 是否仍是我们请求的那一页；一旦不是，
 * 立即把 **INTERFERENCE** 打出来并把那条判为失败 —— 而不是安静地给出错误结论。
 * （实测踩过：`location.hash='#/plot/2d'` 之后页面在 `#/plot/vector` 上，
 *   于是"钩子没了、按钮找不到、曲线位置全错"，看起来像产品坏了。）
 */
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* 连不上就**明确说清楚并退出**，不要甩一堆 `fetch failed` 堆栈：
 * 那既看不出"宿主没起"，也会让人误以为是用例自己坏了。
 * 退出码 2 且**不打印 RESULT 行** —— run-all 会把它报成 `???? (no RESULT line, exit=2)`，
 * 也就是"没跑成"，而不是"通过"（详见文件末尾那段说明）。 */
let list;
try {
  list = await (await fetch("http://127.0.0.1:9222/json/list")).json();
} catch (e) {
  console.error("连不上 CDP（http://127.0.0.1:9222/json/list）：" + String((e && e.message) || e));
  console.error("  宿主没起、或已经退出。起法见 AGENTS.md §4（优先**附着**到已运行的宿主，不要另起一个）。");
  console.error("  （不打印 RESULT 行：本轮没有可信结论，不能让 run-all 把它算成通过）");
  process.exit(2);
}
const page = list.find((t) => t.type === "page" && /mfmath\.local|index\.html/.test(t.url || ""));
if (!page) {
  console.error("CDP 通了但找不到宿主页面（列表里没有 mfmath.local）—— 宿主可能刚起、页面还没加载。");
  process.exit(2);
}
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; }).catch(() => {
  console.error("WebSocket 连不上调试端口 —— 宿主可能正在退出。");
  process.exit(2);
});

let id = 0;
const send = (method, params, timeoutMs = 20000) => new Promise((resolve) => {
  const mid = ++id;
  const h = (ev) => { const d = JSON.parse(ev.data); if (d.id === mid) { clearTimeout(timer); ws.removeEventListener("message", h); resolve(d); } };
  const timer = setTimeout(() => { ws.removeEventListener("message", h); resolve({ timeout: true }); }, timeoutMs);
  ws.addEventListener("message", h);
  ws.send(JSON.stringify({ id: mid, method, params }));
});
const ev = async (expr, timeoutMs) => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }, timeoutMs);
  if (r.timeout) return undefined;
  if (r.result?.exceptionDetails) return "[异常] " + (r.result.exceptionDetails.text || "");
  return r.result?.result?.value;
};
/** 对象一律走 JSON 字符串读：CDP 的 returnByValue 对某些对象会给出 {}（实测） */
const evJson = async (expr) => { const s = await ev(`JSON.stringify(${expr})`); try { return JSON.parse(s); } catch { return null; } };

await send("Runtime.enable");
await sleep(600);

let pass = 0, fail = 0;
const failures = [];
let interfered = false;   // 页面被别人开走了（并发）
let unavailable = false;  // 页面/宿主整个没了（读不到任何东西）—— 与并发分开报
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  if (!ok) failures.push({ label, detail });
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

/** 当前路由（同时作为"有没有别人在开页面"的判据）。
 *  ⚠ 读不到（evaluate 超时/失败）返回 undefined —— 那是**页面或宿主不可用**，
 *  与"页面被别人开走了"是两码事，必须分开报：本套件第一版把两者混成一句"有并发驱动"，
 *  于是在宿主进程被杀掉之后给出了一条**完全错误的归因**（把宿主没了说成别人抢页面）。 */
const hash = () => ev(`location.hash`, 8000);
/** 路由检查：'ok' | 'changed'（有人开走了）| 'unavailable'（读不到 = 页面/宿主没了） */
const routeState = async (want) => {
  const now = await hash();
  if (now === undefined) { unavailable = true; return "unavailable"; }
  if (now !== want) { interfered = true; return "changed"; }
  return "ok";
};

/** 往控件里写值（math-field 与普通 input 两种，照既有用例的做法） */
const writeControl = (sel, text) => ev(`(function(){
  const el = document.querySelector(${JSON.stringify(sel)});
  if (!el) return 'no-el';
  if (el.tagName === 'MATH-FIELD') { el.value = ${JSON.stringify(text)}; el.dispatchEvent(new Event('input', { bubbles: true })); return 'ok'; }
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(el, ${JSON.stringify(text)});
  el.dispatchEvent(new Event('input', { bubbles: true }));
  return 'ok'; })()`);
/** 读控件的当前值 */
const readControl = (sel) => ev(`(function(){
  const el = document.querySelector(${JSON.stringify(sel)});
  if (!el) return null;
  return String(el.value); })()`);

/* 每页：路由（location.hash）、**工作区的键**（store 按 `route.path` 存，没有 `#`）、
 * 控件选择器、写入值、工作区里应当出现的载荷片段（含 kind）。
 * ⚠ `path` 与 `route` 必须分开：本套件第一版拿 `"#/plot/2d"` 当工作区键去查，
 *   于是永远"工作区里没有这一页" —— 而同一轮里"重挂载后还原"却是通过的（自相矛盾，
 *   正说明是**读取的键写错了**，不是产品没存）。 */
const PAGES = [
  { name: "2D/极坐标（对照，cdp-workspace 已覆盖）", route: "#/plot/2d", path: "/plot/2d", sel: ".desmos-side math-field",
    sentinel: "sin(2*x)", kind: "plot", field: (v) => ({ expressions: [{ text: v }] }) },
  { name: "3D 曲面", route: "#/plot/3d", path: "/plot/3d", sel: ".input",
    sentinel: "0.5*x+0.25*y", kind: "plot3d", field: (v) => ({ exprInput: v }) },
  { name: "复平面", route: "#/plot/complex", path: "/plot/complex", sel: ".plot-side .input.mono",
    sentinel: "z^2+1", kind: "plot-complex", field: (v) => ({ funcExpr: v }) },
  { name: "向量场", route: "#/plot/vector", path: "/plot/vector", sel: ".input",
    sentinel: "2*x", kind: "plot-vector", field: (v) => ({ dxInput: v }) },
  { name: "自由几何（吸附开关）", route: "#/plot/geometry", path: "/plot/geometry", sel: ".chk input",
    sentinel: null, kind: "plot-geometry", field: () => ({ snap: false }) },
  { name: "分形（迭代次数）", route: "#/plot/fractal", path: "/plot/fractal", sel: "select",
    sentinel: "512", kind: "plot-fractal", field: () => ({ maxIter: 512 }) },
];

/** 该页工作区载荷里能否找到期望的片段（只比对我们关心的字段） */
const payloadMatches = (payload, page_, sentinel) => {
  if (!payload || payload.kind !== page_.kind) return false;
  const want = page_.field(sentinel);
  return Object.entries(want).every(([k, v]) => {
    const got = payload[k];
    if (Array.isArray(v)) {
      return Array.isArray(got) && got.length > 0 &&
        Object.entries(v[0]).every(([kk, vv]) => got.some((g) => String(g?.[kk] ?? "") === String(vv)));
    }
    return String(got) === String(v);
  });
};

for (const p of PAGES) {
  console.log(`\n【${p.name}】${p.route}`);

  /* 先离开再进来，确保是**重新挂载**（还原只发生在挂载时） */
  await ev(`location.hash='#/'`); await sleep(500);
  await ev(`location.hash=${JSON.stringify(p.route)}`);
  await sleep(2200);

  if ((await routeState(p.route)) !== "ok") {
    const now = await hash();
    check(`  ${p.name}：页面停在了请求的路由上`, false,
      now === undefined ? "读不到 location.hash —— 页面或宿主已经不可用（不是并发）" : `请求 ${p.route}，实际 ${now}（有并发驱动）`);
    if (now === undefined) break;   // 宿主没了，后面的检查都没有意义
    continue;
  }

  const selOk = await ev(`!!document.querySelector(${JSON.stringify(p.sel)})`);
  check(`  ${p.name}：找到可编辑控件（${p.sel}）`, selOk === true, selOk === true ? "" : "控件不在页面上");
  if (selOk !== true) continue;

  /* ① 存：改控件 → 工作区载荷跟着变 */
  if (p.sentinel === null) {
    // 布尔型（几何页的吸附默认 true，置反）
    await ev(`(function(){ const el=document.querySelector(${JSON.stringify(p.sel)}); el.checked=false; el.dispatchEvent(new Event('change',{bubbles:true})); el.dispatchEvent(new Event('input',{bubbles:true})); return 'ok'; })()`);
  } else {
    const w = await writeControl(p.sel, p.sentinel);
    check(`  ${p.name}：能写入控件`, w === "ok", String(w));
  }
  await sleep(900);

  const payload = await evJson(`(window.__mfWorkspace && window.__mfWorkspace.pages ? window.__mfWorkspace.pages()[${JSON.stringify(p.path)}] : null)`);
  check(`  ${p.name}：改动被写进工作区（键 ${p.path}，kind=${p.kind}）`, payloadMatches(payload, p, p.sentinel === null ? null : p.sentinel),
    payload ? `载荷=${JSON.stringify(payload).slice(0, 110)}` : `工作区里没有 ${p.path} 这一页`);

  /* ② 还原：离开再回来 → 控件显示改动后的值 */
  await ev(`location.hash='#/'`); await sleep(600);
  await ev(`location.hash=${JSON.stringify(p.route)}`);
  await sleep(2200);
  if ((await routeState(p.route)) !== "ok") {
    const now = await hash();
    check(`  ${p.name}：还原时页面停在请求的路由上`, false,
      now === undefined ? "读不到 location.hash —— 页面或宿主已经不可用（不是并发）" : `实际 ${now}（有并发驱动）`);
    if (now === undefined) break;
    continue;
  }
  const back = await readControl(p.sel);
  if (p.sentinel === null) {
    const checked = await ev(`(function(){ const el=document.querySelector(${JSON.stringify(p.sel)}); return el ? el.checked : null; })()`);
    check(`  ${p.name}：重挂载后还原了改动（吸附=false）`, checked === false, `实际 checked=${checked}`);
  } else {
    check(`  ${p.name}：重挂载后还原了改动`, String(back) === p.sentinel, `期望 ${JSON.stringify(p.sentinel)}，实际 ${JSON.stringify(back)}`);
  }
}

/* 收尾：回首页，别把别的用例留在某个绘图页上 */
await ev(`location.hash='#/'`); await sleep(400);

if (unavailable) {
  console.log("\n✘ **页面或宿主已经不可用**（location.hash 都读不到）—— 本轮什么都没验成。");
  console.log("  检查：宿主进程是否还在、CDP 9222 是否在监听（起法见 AGENTS.md §4）。");
  /* ⚠ **这里故意不打印 RESULT 行。** run-all.ps1 只看 `RESULT|名|pass|fail` 的计数
   * （run-all.ps1:190-197），只有"没有 RESULT 行"才会报成 `???? (no RESULT line, exit=N)`。
   * 若在这里印一行 `0|0`，**会被读成 OK** —— 明明什么都没验，却显示通过，
   * 那正是纪律①（不编造结果）禁止的事。所以走"没有 RESULT 行"这条路，退出码 2 表"没跑成"。 */
  console.log("  （不打印 RESULT 行：本轮没有可信结论，不能让 run-all 把它算成通过）");
  ws.close();
  process.exit(2);
}
if (interfered) {
  console.log("\n⚠ 检测到并发驱动：有另一个进程在同一个宿主上切换页面（路由被改成了我没请求的那一个）。");
  console.log("  本用例的失败**不能**当作产品缺陷 —— 请在没有并行会话时重跑（AGENTS.md §4）。");
}
console.log(`\n═══ 绘图页工作区往返：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|cdp-plot-workspace|${pass}|${fail}`);
ws.close();
process.exit(fail ? 1 : 0);
