/**
 * cdp-plot-fn.mjs —— 两件事的端到端判据：
 *
 * ① **切页回来不能变成引擎形态**（BUGS.md B16）
 *    用户写 `\frac{x^2}{5x-6}`，引擎会把它规范化成 `x^2/(5*x-6)`。这个规范化串
 *    **只能用来送引擎**；一旦拿它当 LaTeX 回填输入框，用户切走再回来就看到"分数变成
 *    一堆星号"。本套件钉住：输入框里回来仍是 `\frac`，且**不含 `*`**。
 *
 * ②④⑤ 用户自定义函数 `f(x)=e^x`（docs/PLAN-plot-user-functions.md）
 *    - 定义行**不参与绘制**，且不会给 `f` 生成参数滑块；
 *    - 引用行 `y=f(3)` 能正常采样（送引擎前已展开成定义体）；
 *    - 把定义行清空后，引用行**明确报"未定义的函数 f"**，而不是静默画空白。
 *
 * 判据只读 DOM 与 __mfPlot 钩子，不依赖并发敏感的内部状态。
 * 跑法：node tests/cdp-plot-fn.mjs（需要宿主带 CDP，`run-all.ps1 -NoLaunch` 同款）
 */
const PORT = 9222;
let pass = 0, fail = 0;
const check = (name, ok, detail = "") => {
  if (ok) { pass++; console.log("  [OK]   " + name); }
  else { fail++; console.log("  [FAIL] " + name + (detail ? "   " + detail : "")); }
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let list;
try {
  list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
} catch (e) {
  console.error(`连不上 CDP（http://127.0.0.1:${PORT}/json/list）：` + String((e && e.message) || e));
  console.error("宿主/页面不可用 —— 本用例**没有运行**，因此不打印 RESULT 行（避免假绿）。");
  process.exit(2);
}
const page = list.find((t) => t.type === "page" && /mfmath\.local|index\.html/.test(t.url || ""));
if (!page) {
  console.error("CDP 通了但找不到应用页面 —— 本用例没有运行，不打印 RESULT 行。");
  process.exit(2);
}
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
let seq = 0;
const send = (m, q, t = 20000) => new Promise((res) => {
  const id = ++seq;
  const h = (e) => { const d = JSON.parse(e.data); if (d.id === id) { clearTimeout(tm); ws.removeEventListener("message", h); res(d); } };
  const tm = setTimeout(() => { ws.removeEventListener("message", h); res({ timeout: true }); }, t);
  ws.addEventListener("message", h);
  ws.send(JSON.stringify({ id, method: m, params: q }));
});
const ev = async (x) => {
  const r = await send("Runtime.evaluate", { expression: x, returnByValue: true, awaitPromise: true });
  if (!r || r.timeout) return undefined;
  return r?.result?.result?.value;
};
/* 注意：CDP 的 returnByValue 对 hook 对象会序列化成 {}，所以一律在页面里 JSON.stringify */
const evJson = async (x) => {
  const s = await ev(`JSON.stringify(${x})`);
  try { return s == null ? null : JSON.parse(s); } catch { return null; }
};

const hash = () => ev("location.hash");
const goto = async (h) => { await ev(`location.hash=${JSON.stringify(h)}`); await sleep(1600); };
const fillMathField = (idx, text) => ev(`(function(){
  const fields = [...document.querySelectorAll('.desmos-side math-field')];
  const el = fields[${idx}];
  if (!el) return 'no-field';
  el.value = ${JSON.stringify(text)};
  el.dispatchEvent(new Event('input', { bubbles: true }));
  return 'ok';
})()`);
const rowTexts = () => evJson(`[...document.querySelectorAll('.desmos-side math-field')].map(f => f.value)`);
const rowErrors = () => evJson(`[...document.querySelectorAll('.expr-error')].map(e => e.textContent.trim())`);
const sideStatus = () => ev("(document.querySelector('.side-status')||{}).textContent || ''");

/* ═════════ ④⑤ 用户函数：定义行不画、引用行能画、清空定义后明确报错 ═════════ */
console.log("\n【④⑤ 用户函数 f(x)=x^2 + 引用行 y=f(3)】");
await goto("#/");
await goto("#/plot/2d");
check("页面停在 2D 绘图页", (await hash()) === "#/plot/2d", String(await hash()));

// 第一行写定义
let w = await fillMathField(0, "f(x)=x^2");
check("能在第一行写定义", w === "ok", String(w));
await sleep(1200);
const texts1 = await rowTexts();
console.log("   行文本:", JSON.stringify(texts1));
check("定义行**保留了 f(**（没被引擎改写成 f*(x）",
  JSON.stringify(texts1?.[0] || "").includes("f(x)") && !String(texts1?.[0] || "").includes("f*("),
  JSON.stringify(texts1?.[0]));

// 加一行引用
await ev(`(function(){ document.querySelector('.add-row')?.click(); return 'ok'; })()`);
await sleep(700);
w = await fillMathField(1, "y=f(3)");
check("能在第二行写引用 y=f(3)", w === "ok", String(w));
await sleep(1800);
const texts2 = await rowTexts();
console.log("   行文本:", JSON.stringify(texts2));
check("引用行也保留 f(（展开发生在送引擎前，不用改写用户输入）",
  JSON.stringify(texts2?.[1] || "").includes("f(3)"), JSON.stringify(texts2?.[1]));

const st1 = await sideStatus();
console.log("   状态行:", JSON.stringify(st1));
check("定义行不参与绘制（只采样 1 条曲线）", /引擎采样\s*1\s*条曲线/.test(st1), st1);
check("引用行没有行内错误", (await rowErrors()).length === 0, JSON.stringify(await rowErrors()));

const hint = await ev("(document.querySelector('.slider-hint-text')||{}).textContent || ''");
console.log("   参数提示:", JSON.stringify(hint));
check("定义行没有造出 f 滑块", !/(^|[^A-Za-z])f([^A-Za-z]|$)/.test(String(hint)), JSON.stringify(hint));

/* 清空定义行 → 引用行必须明确报"未定义的函数"，而不是静默空白 */
console.log("\n【清空定义行 → 引用行必须明确报错】");
await fillMathField(0, "");
await sleep(1800);
const errs = await rowErrors();
const st2 = await sideStatus();
console.log("   行内错误:", JSON.stringify(errs), "| 状态:", JSON.stringify(st2));
check("引用行报出「未定义的函数 f」（不静默）",
  JSON.stringify(errs).includes("未定义的函数 f"), JSON.stringify(errs));

/* ═════════ ① 切页回来不能被换成引擎形态 ═════════ */
console.log("\n【① 计算页：写分数 → 切走再回来 → 仍是 LaTeX，不是 x^2/(5*x-6)】");
await goto("#/calc/algebra");
check("页面停在代数计算页", (await hash()) === "#/calc/algebra", String(await hash()));
const FRAC = "\\frac{x^2}{5x-6}";
const w2 = await ev(`(function(){
  const el = document.querySelector('.cb-input');
  if (!el) return 'no-input';
  el.value = ${JSON.stringify(FRAC)};
  el.dispatchEvent(new Event('input', { bubbles: true }));
  return 'ok';
})()`);
check("能在计算块里写分数", w2 === "ok", String(w2));
await sleep(1000);
const before = await ev("document.querySelector('.cb-input').value");
console.log("   切走前:", JSON.stringify(before));

await goto("#/");            // 切走（组件卸载）
await goto("#/calc/algebra"); // 切回（重新挂载 → 从工作区还原）
const after = await ev("document.querySelector('.cb-input').value");
console.log("   切回后:", JSON.stringify(after));
check("切回后输入框里仍是 \\frac（不是引擎形态）", String(after).includes("\\frac"), JSON.stringify(after));
check("切回后**不含 `*`**（引擎规范化串没有泄漏到输入框）", !String(after).includes("*"), JSON.stringify(after));

/* 还原出来的值仍然能算（显示改了，语义不能改） */
await ev(`(function(){ document.querySelector('.cb-calc')?.click(); return 'ok'; })()`);
await sleep(2200);
const dlg = await ev("!!document.querySelector('.dialog')");
check("还原后仍能算出结果（显示与语义都没丢）", dlg === true, String(dlg));
await ev("document.querySelector('.dialog-close')?.click()");
await sleep(300);

console.log(`\n═══ 绘图页用户函数 + 输入框保真：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|cdp-plot-fn|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
