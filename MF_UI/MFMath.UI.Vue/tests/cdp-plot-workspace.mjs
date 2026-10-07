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

const list = await (await fetch("http://127.0.0.1:9222/json/list")).json();
const page = list.find((t) => t.type === "page" && /mfmath\.local|index\.html/.test(t.url || ""));
if (!page) { console.error("找不到宿主页面（宿主没起？）"); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

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
let interfered = false;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  if (!ok) failures.push({ label, detail });
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

/** 当前路由（同时作为"有没有别人在开页面"的判据） */
const hash = () => ev(`location.hash`);
/** 干扰检测：请求的页面与当前页面不一致 ⇒ 有人在并发驱动，结论不可信 */
const routeOk = async (want) => {
  const now = await hash();
  if (now !== want) { interfered = true; return false; }
  return true;
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

/* 每页：路由、控件选择器、写入值、工作区里应当出现的载荷片段（含 kind） */
const PAGES = [
  { name: "2D/极坐标（对照，cdp-workspace 已覆盖）", route: "#/plot/2d", sel: ".desmos-side math-field",
    sentinel: "sin(2*x)", kind: "plot", field: (v) => ({ expressions: [{ text: v }] }) },
  { name: "3D 曲面", route: "#/plot/3d", sel: ".input",
    sentinel: "0.5*x+0.25*y", kind: "plot3d", field: (v) => ({ exprInput: v }) },
  { name: "复平面", route: "#/plot/complex", sel: ".plot-side .input.mono",
    sentinel: "z^2+1", kind: "plot-complex", field: (v) => ({ funcExpr: v }) },
  { name: "向量场", route: "#/plot/vector", sel: ".input",
    sentinel: "2*x", kind: "plot-vector", field: (v) => ({ dxInput: v }) },
  { name: "自由几何（吸附开关）", route: "#/plot/geometry", sel: ".chk input",
    sentinel: null, kind: "plot-geometry", field: () => ({ snap: false }) },
  { name: "分形（迭代次数）", route: "#/plot/fractal", sel: "select",
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

  if (!(await routeOk(p.route))) {
    check(`  ${p.name}：页面停在了请求的路由上`, false, `请求 ${p.route}，实际 ${await hash()}（有并发驱动）`);
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

  const payload = await evJson(`(window.__mfWorkspace && window.__mfWorkspace.pages ? window.__mfWorkspace.pages()[${JSON.stringify(p.route)}] : null)`);
  check(`  ${p.name}：改动被写进工作区（kind=${p.kind}）`, payloadMatches(payload, p, p.sentinel === null ? null : p.sentinel),
    payload ? `载荷=${JSON.stringify(payload).slice(0, 110)}` : "工作区里没有这一页");

  /* ② 还原：离开再回来 → 控件显示改动后的值 */
  await ev(`location.hash='#/'`); await sleep(600);
  await ev(`location.hash=${JSON.stringify(p.route)}`);
  await sleep(2200);
  if (!(await routeOk(p.route))) {
    check(`  ${p.name}：还原时页面停在请求的路由上`, false, `实际 ${await hash()}（有并发驱动）`);
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

if (interfered) {
  console.log("\n⚠ 检测到并发驱动：有另一个进程在同一个宿主上切换页面。");
  console.log("  本用例的失败**不能**当作产品缺陷 —— 请在没有并行会话时重跑。");
}
console.log(`\n═══ 绘图页工作区往返：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|cdp-plot-workspace|${pass}|${fail}`);
ws.close();
process.exit(fail ? 1 : 0);
