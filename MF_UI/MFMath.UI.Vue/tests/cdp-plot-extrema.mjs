// 验证极值标注：引擎符号求解 → 画布菱形标记 + 侧栏列表 + 含参分支讨论
// 用法: node cdp-plot-extrema.mjs
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
const send = (method, params, timeoutMs = 20000) => new Promise((resolve) => {
  const mid = ++id;
  const h = (ev) => {
    const d = JSON.parse(ev.data);
    if (d.id === mid) { clearTimeout(timer); ws.removeEventListener("message", h); resolve(d); }
  };
  // 超时保护：页面无响应时不让脚本永久挂起
  const timer = setTimeout(() => {
    ws.removeEventListener("message", h);
    resolve({ timeout: true, result: { result: { value: "[超时] 页面未在 " + timeoutMs + "ms 内响应" } } });
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

async function setExpr(text) {
  // 输入框现在是 MathLive 的 <math-field>（数学就地排版），不再是 <input>。
  // 这里两种都支持：老式 input 用原生 setter，math-field 直接赋 value。
  await evalJs(`(function(){
    const el = document.querySelector('.expr-input');
    if (!el) return 'no-input';
    if (el.tagName === 'MATH-FIELD') {
      el.value = ${JSON.stringify(text)};
      el.dispatchEvent(new Event('input', { bubbles: true }));
    } else {
      // 输入框可能是 MathLive 的 <math-field>（数学就地排版）或普通 input，两种都支持：
    const setter = { call: (el, v) => { if (el && el.tagName === 'MATH-FIELD') { el.value = v; } else { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); } } };
      setter.call(el, ${JSON.stringify(text)});
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }
    return 'ok';
  })()`);
  await sleep(2500);
}

await evalJs("location.hash = '#/plot/2d'");
await sleep(1200);
await evalJs(`(function(){
  let guard = 0;
  while (document.querySelectorAll('.expr-input').length > 1 && guard++ < 30) {
    const rows = [...document.querySelectorAll('.expr-row')];
    const del = rows.length ? rows[rows.length - 1].querySelector('.del-btn') : null;
    if (!del) break; del.click();
  }
  return 'ok';
})()`);
await sleep(800);

/* ── ① 无参曲线 y=x^3-3x：极值 (-1,2) 与 (1,-2) ── */
console.log("── 无参曲线极值标注 y=x^3-3*x ──");
await setExpr("y=x^3-3*x");
const st1 = await evalJs(`(function(){
  const rows = [...document.querySelectorAll('#extList .pt-row')].map(r => r.textContent.replace(/\\s+/g,' ').trim());
  const diamonds = document.querySelectorAll('.pt-dot.diamond').length;
  const status = document.querySelector('.side-status')?.textContent || '';
  return { rows, diamonds, status };
})()`);
console.log("   极值行:", JSON.stringify(st1.rows));
console.log("   菱形标记数:", st1.diamonds);
check("识别出 2 个极值", st1.rows.some(r => r.includes("极大")) && st1.rows.some(r => r.includes("极小")), JSON.stringify(st1.rows));
check("极大值为 (-1, 2)", st1.rows.some(r => r.includes("极大") && r.includes("-1") && r.includes("2")), "");
check("极小值为 (1, -2)", st1.rows.some(r => r.includes("极小") && r.includes("1") && r.includes("-2")), "");
check("标记为「精确」", st1.rows.every(r => r.includes("精确")), JSON.stringify(st1.rows));

/* ── ② 画布上**不应该**自动出现菱形标记 ──
 *
 * 规则（用户定的）：**点必须由用户自己添加，不能自动往画布上画** —— Desmos 也是如此，
 * 极值/交点不会自己冒出来。所以这里断言的是"默认没有标记"，而不是"有标记"。
 * 分析本身照旧（上面的 st1.rows 仍要求算出极大/极小且标「精确」）—— 数据进侧栏，
 * 不进画布。用户要看点，自己点曲线（PlotCanvas 的 pick-point）。 */
console.log("\n── 画布菱形标记像素（应为 0：不自动标注）──");
const px = await evalJs(`(function(){
  const cv = document.querySelector('canvas');
  const d = cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;
  let purple = 0, cyan = 0;
  for (let i=0;i<d.length;i+=4) {
    const r=d[i], g=d[i+1], b=d[i+2];
    // 紫 #7c3aed ≈ (124,58,237)；青 #0891b2 ≈ (8,145,178)
    if (Math.abs(r-124)<40 && Math.abs(g-58)<40 && Math.abs(b-237)<40) purple++;
    if (Math.abs(r-8)<40 && Math.abs(g-145)<40 && Math.abs(b-178)<40) cyan++;
  }
  return { purple, cyan };
})()`);
console.log("   紫色像素(极大):", px.purple, "| 青色像素(极小):", px.cyan);
// 一枚菱形约 200+ 像素；用 <10 容忍抗锯齿/其它元素的零星同色像素
check("不自动画极大值标记（点须用户自己添加）", px.purple < 10, String(px.purple));
check("不自动画极小值标记（点须用户自己添加）", px.cyan < 10, String(px.cyan));

/* ── ③ 无参数时不应有符号分支列表 ── */
const sym1 = await evalJs(`document.querySelectorAll('.pt-sym').length`);
check("无参曲线不显示符号分支", sym1 === 0, String(sym1));

/* ── ④ 含参曲线 y=x^3-3*a*x：符号驻点 + 参数分支讨论 ── */
console.log("\n── 含参曲线符号驻点与分类讨论 y=x^3-3*a*x ──");
await setExpr("y=x^3-3*a*x");
/* ③ 契约：参数滑块不再自动铺开，先提示、点「添加滑块」才出现 */
  await evalJs(`(function(){ const b = document.querySelector('.slider-add'); if (b) b.click(); return 'ok'; })()`);
  await sleep(600);
  const st2 = await evalJs(`(function(){
  // 侧栏按**参数取值**分组：一块 .pt-sym 对应一个参数情形（如 a>0），
  // 块内 .pt-branch 是折叠起来的各个驻点结论。
  const groups = [...document.querySelectorAll('.pt-sym')].map(g => ({
    assume: (g.querySelector('.branch-head .branch-tag')||{}).textContent || '',
    text: g.textContent.replace(/\\s+/g,' ').trim(),
    rows: [...g.querySelectorAll('.pt-branch')].map(b => b.textContent.replace(/\\s+/g,' ').trim())
  }));
  const sliders = [...document.querySelectorAll('.param-name')].map(n => n.textContent);
  return { groups, sliders };
})()`);
const gAll = st2.groups.map(g => g.text).join(' | ');
console.log("   参数分组:", JSON.stringify(st2.groups.map(g => g.assume)));
console.log("   分支行:", JSON.stringify(st2.groups.flatMap(g => g.rows)));
check("含参曲线点添加后生成滑块 a", JSON.stringify(st2.sliders) === JSON.stringify(["a"]), JSON.stringify(st2.sliders));
check("显示符号驻点（含 sqrt(a)）", gAll.includes("sqrt(a)"), gAll);
check("按参数取值分组 a>0 / a=0 / a<0",
  st2.groups.some(g => g.assume === "a>0") && st2.groups.some(g => g.assume === "a=0") && st2.groups.some(g => g.assume === "a<0"),
  JSON.stringify(st2.groups.map(g => g.assume)));
check("a>0 组判为极大值",
  ((st2.groups.find(g => g.assume === "a>0") || {}).text || "").includes("极大"), "");
check("a>0 组含极小值",
  ((st2.groups.find(g => g.assume === "a>0") || {}).text || "").includes("极小"), "");

/* ── ⑤ 无参数切换回数值极值 ── */
console.log("\n── 切回无参曲线 ──");
await setExpr("y=x^2-4*x+3");
const st3 = await evalJs(`(function(){
  const rows = [...document.querySelectorAll('#extList .pt-row')].map(r => r.textContent.replace(/\\s+/g,' ').trim());
  return { rows, syms: document.querySelectorAll('.pt-sym').length };
})()`);
console.log("   极值行:", JSON.stringify(st3.rows), "| 符号分支:", st3.syms);
check("y=x^2-4x+3 极值为 (2,-1) 极小", st3.rows.some(r => r.includes("极小") && r.includes("2") && r.includes("-1")), JSON.stringify(st3.rows));
check("符号分支已清空", st3.syms === 0, String(st3.syms));

const errs = await evalJs("window.__plotErrors || null");
check("绘制无异常", !errs || errs.length === 0, JSON.stringify(errs));

console.log(`\n═══ 极值标注验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|plot-extrema|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
