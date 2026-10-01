// 两个「引擎算错但界面照样显示成功」的端到端验证：
//   ① 某点导数含参数 —— 原来抛"无法数值求值"，应当是 4a
//   ② 复数运算      —— 原来映射到 exp_complex，「1+2i」会静默算成 e^(1+2i)
//
// 两者都属于"答案错了但没人发现"那一类，所以断言都对着**用户看得见的结果**，
// 而不是只看引擎自己的返回值。
//
// 用法: node cdp-diff-at-param.mjs   （宿主需带 --remote-debugging-port=9222 启动）
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
const send = (method, params, timeoutMs = 40000) => new Promise((resolve) => {
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

const exceptions = [];
ws.addEventListener("message", (ev) => {
  let d; try { d = JSON.parse(ev.data); } catch { return; }
  if (d.method === "Runtime.exceptionThrown") {
    exceptions.push(String(d.params?.exceptionDetails?.exception?.description || d.params?.exceptionDetails?.text || "?"));
  }
});
await send("Runtime.enable");
await sleep(1000);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

/** 从下拉里选模式（用户操作的就是这个 combo） */
const pickMode = (name) => evalJs(`(function(){
  const sel = document.querySelector('.cb-mode');
  if (!sel) return 'no-select';
  const opt = [...sel.options].find(o => o.value === ${JSON.stringify(name)});
  if (!opt) return 'no-mode:' + [...sel.options].map(o=>o.value).join(',');
  Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set.call(sel, ${JSON.stringify(name)});
  sel.dispatchEvent(new Event('change', { bubbles: true }));
  return 'ok';
})()`);
const setInput = (v) => evalJs(`(function(){
  const inp = document.querySelector('.cb-input');
  if (!inp) return 'no-input';
  if (inp.tagName === 'MATH-FIELD') inp.value = ${JSON.stringify(v)};
  else Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(inp, ${JSON.stringify(v)});
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  return 'ok';
})()`);
const clickCalc = () => evalJs(`(function(){
  const b = document.querySelector('.cb-calc'); if (!b) return 'no-btn'; b.click(); return 'clicked';
})()`);
const readDialog = () => evalJs(`(function(){
  const dlg = document.querySelector('.dialog');
  if (!dlg) return null;
  const res = dlg.querySelector('.dialog-result');
  return {
    header: dlg.querySelector('.dialog-header')?.textContent.trim() || '',
    context: dlg.querySelector('.dialog-context')?.textContent.trim() || '',
    text: res ? res.textContent.trim() : '',
    tex: res ? [...res.querySelectorAll('[data-tex]')].map(e => e.getAttribute('data-tex')).join(' ') : '',
    katex: res ? res.querySelectorAll('.katex').length : 0,
  };
})()`);
const closeDialog = async () => { await evalJs("document.querySelector('.dialog-close')?.click()"); await sleep(250); };

/** 跑一题：选模式 → 填输入 → 计算 → 读弹窗 */
async function runOne(modeName, input) {
  const picked = await pickMode(modeName);
  if (picked !== "ok") return { error: "选模式失败：" + picked };
  await sleep(400);
  const setRes = await setInput(input);
  if (setRes !== "ok") return { error: "填输入失败：" + setRes };
  await sleep(300);
  await clickCalc();
  const t0 = Date.now();
  while (Date.now() - t0 < 15000) {
    const d = await readDialog();
    if (d && (d.text || d.tex)) return d;
    const err = await evalJs("(document.querySelector('.cb-error')||{}).textContent||''");
    if (err) return { error: String(err) };
    await sleep(250);
  }
  return { error: "15 秒内没有结果" };
}

console.log("── 某点导数（含参数）：界面复测 ──");
await evalJs("location.hash = '#/'");
await sleep(500);
await evalJs("location.hash = '#/calc/calculus'");
await sleep(1500);

// 这一题就是原先报错的那道：f(x)=a*x^2 在 x=2 处的导数，答案应当是 4a
let d = await runOne("某点导数", "a*x^2; 2");
console.log("   弹窗:", JSON.stringify(d).slice(0, 200));
check("界面给出了结果（不是报错）", !d?.error, d?.error || "");
const hay = `${d?.text || ""} ${d?.tex || ""}`.replace(/\s+/g, "");
check("结果显示为含参数的符号式（含 4*a）", /4\*?a/.test(hay), d?.text || d?.tex || "");
check("结果里没有把参数 a 丢掉（没算成 4）", !/^4$/.test((d?.text || "").trim()), d?.text || "");
await closeDialog();

// 无参数时仍必须是数值（别为了含参把原来的数值行为改坏）
d = await runOne("某点导数", "x^3; 2");
console.log("   弹窗:", JSON.stringify(d).slice(0, 160));
check("无参数时仍然给出数值 12", !d?.error && /(^|[^\d.])12([^\d.]|$)/.test(`${d?.text} ${d?.tex}`), d?.text || "");
await closeDialog();

// 两个参数的复合情形
d = await runOne("某点导数", "a*x^2+b*x; 1");
console.log("   弹窗:", JSON.stringify(d).slice(0, 180));
check("多参数也能给符号式（含 2*a 与 b）",
  !d?.error && /2\*?a/.test(`${d?.text}${d?.tex}`.replace(/\s+/g, "")) && /b/.test(`${d?.text}${d?.tex}`),
  d?.text || "");
await closeDialog();

/* ── 复数运算：原版写法的 1+2i 必须是 1+2i，绝不能是 e^(1+2i) ──
 *
 * 这是一个**静默错答**：原来「复数运算」映射到 exp_complex，而 parse_complex 能正确
 * 解析 "1+2i"，于是界面给出 e^(1+2i) = -1.13+2.47i 并显示"已计算"——
 * 用户完全看不出问题。所以这里同时断言"有正确分量"与"不是那个错值"。
 */
console.log("\n── 复数运算（应当是 1+2i，不是 e^(1+2i)）──");
await evalJs("location.hash = '#/calc/complex-analysis'");
await sleep(1200);
let z = await runOne("复数运算", "1+2i");
console.log("   弹窗:", JSON.stringify(z).slice(0, 220));
check("复数运算给出结果（不是报错）", !z?.error, z?.error || "");
const zt = `${z?.text || ""} ${z?.tex || ""}`.replace(/\s+/g, "");
check("结果含 1 与 2 两个分量", /1/.test(zt) && /2/.test(zt), zt.slice(0, 80));
check("结果不是 e^(1+2i)（没有 -1.13 / 2.47）",
  !/-?1\.13/.test(zt) && !/2\.47/.test(zt), zt.slice(0, 80));
await closeDialog();

z = await runOne("复数运算", "(1+i)^2");
console.log("   弹窗:", JSON.stringify(z).slice(0, 200));
check("(1+i)^2 应当是 2i", !z?.error && /2/.test(`${z?.text}${z?.tex}`), `${z?.text} ${z?.tex}`.slice(0, 60));
await closeDialog();

await evalJs("location.hash = '#/'");
await sleep(300);
check("全程没有 JS 异常", exceptions.length === 0, exceptions.slice(0, 2).join(" | "));

console.log(`\n═══ 某点导数（含参）验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|cdp-diff-at-param|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
