// 字体加载验证：前端裁剪掉 .woff/.ttf/.otf/.eot 之后，数学排版必须仍然正常。
//
// 背景：dist 里同一套字形被 MathLive / KaTeX 各带一份，且每套都有 woff2+woff+ttf 三种格式，
// 字体占了打包体积的一大半。scripts/prune-fonts.mjs 只保留 woff2（Chromium 100% 支持）。
// 本套件用真实宿主验证四件事：
//   ① 网络层：浏览器只请求 .woff2，全部 200，没有任何 woff/ttf 回退请求（这是删除它们的前提）
//   ② 字体真的加载（document.fonts.check / status=loaded）
//   ③ 真字体真的参与排版（canvas 量宽与回退字体不同）
//   ④ 每一族都被真的用上：\mathbb→AMS、\mathcal→Caligraphic、\mathfrak→Fraktur、√→Size1、∫→Size2
//      —— 逐族断言的意义在于：某一族字体文件被误删时，这里会直接点名
// 用法: node cdp-font-load.mjs   （宿主需带 --remote-debugging-port=9222 启动）
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
const send = (method, params, timeoutMs = 25000) => new Promise((resolve) => {
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

/* ── 网络层：记录所有字体请求与结果 ── */
const reqs = new Map();
const failed = [];
ws.addEventListener("message", (ev) => {
  let d; try { d = JSON.parse(ev.data); } catch { return; }
  if (d.method === "Network.responseReceived") {
    const r = d.params.response;
    reqs.set(d.params.requestId, { url: r.url, status: r.status, mime: r.mimeType || "", bytes: 0 });
  } else if (d.method === "Network.loadingFinished") {
    const e = reqs.get(d.params.requestId);
    if (e) e.bytes = d.params.encodedDataLength || 0;
  } else if (d.method === "Network.loadingFailed") {
    const e = reqs.get(d.params.requestId);
    failed.push({ url: e ? e.url : d.params.requestId, err: d.params.errorText });
  }
});

await send("Runtime.enable");
await send("Network.enable");
await send("Network.setCacheDisabled", { cacheDisabled: true }); // 强制真实走一遍网络，否则测不出回退请求
await sleep(1200);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

/** 填表达式 + 选模式（MathLive 需要派发 input，Vue 才收得到） */
const setBlock = (expr, mode) => evalJs(`(function(){
  const inp = document.querySelector('.cb-input');
  if (!inp) return 'no-input';
  inp.value = ${JSON.stringify(expr)};
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  const sel = document.querySelector('.cb-mode');
  if (${JSON.stringify(mode)} && sel) {
    Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set.call(sel, ${JSON.stringify(mode)});
    sel.dispatchEvent(new Event('change', { bubbles: true }));
  }
  return 'ok';
})()`);

console.log("── 字体加载（裁剪后只剩 woff2）──");
await evalJs("location.hash = '#/'");
await sleep(700);
await evalJs("location.hash = '#/calc/algebra'");
await sleep(2200);

/* ① KaTeX 结果路径：正常计算一次，让结果对话框排版出来 */
await setBlock("x^2-4", "表达式化简");
await sleep(300);
await evalJs("document.querySelector('.cb-calc')?.click()");
await sleep(2000);
const dlg = await evalJs(`(function(){
  const d = document.querySelector('.dialog');
  const r = d ? d.querySelector('.dialog-result') : null;
  const mord = r ? r.querySelector('.katex .mord, .katex .mbin, .katex .minner') : null;
  const err = document.querySelector('.cb-error');
  return {
    dialog: !!d,
    katex: document.querySelectorAll('.katex').length,
    mordFam: mord ? getComputedStyle(mord).fontFamily : null,
    mordText: mord ? mord.textContent.slice(0, 16) : null,
    tex: r ? [...r.querySelectorAll('[data-tex]')].map((e) => e.getAttribute('data-tex')).slice(0, 2) : [],
    err: err && !err.hidden ? err.textContent.trim().slice(0, 120) : '',
  };
})()`);
console.log("   结果对话框:", JSON.stringify({ dialog: dlg && dlg.dialog, katex: dlg && dlg.katex, mordFam: dlg && dlg.mordFam, mordText: dlg && dlg.mordText }));

/* ② MathLive 输入路径：喂满各族字形，逼出所有需要 woff2 的字体 */
await setBlock("\\mathfrak{g}+\\mathcal{L}+\\mathbb{R}+\\sqrt{2}+\\frac{a}{b}+\\int_0^1 x^2 dx", null);
await sleep(1500);

/* ③ 等字体落到 loaded */
await evalJs("document.fonts.ready.then(function(){ return true; })");
let loadedFams = [];
for (let i = 0; i < 20; i++) {
  loadedFams = await evalJs("[...new Set([...document.fonts].filter(f => f.status === 'loaded').map(f => String(f.family).replace(/[\"']/g, '')))]");
  if (Array.isArray(loadedFams) && loadedFams.length > 0) break;
  await sleep(300);
}
if (!Array.isArray(loadedFams)) loadedFams = [];
console.log("   已加载字体族:", loadedFams.join(", "));

/* ── 检查 ①：网络层 ── */
const fontReqs = [...reqs.values()].filter((r) => /\.(woff2?|ttf|otf|eot)(\?|$)/i.test(r.url));
const woff2 = fontReqs.filter((r) => /\.woff2(\?|$)/i.test(r.url));
const older = fontReqs.filter((r) => !/\.woff2(\?|$)/i.test(r.url));
const bad = fontReqs.filter((r) => r.status !== 200);
const totalKB = fontReqs.reduce((a, r) => a + r.bytes, 0) / 1024;
const fontFail = failed.filter((f) => /font|woff|ttf/i.test(f.url));
console.log(`   字体请求 ${fontReqs.length} 个（woff2 ${woff2.length} / 其它格式 ${older.length}），合计 ${totalKB.toFixed(0)} KB`);
check("浏览器确实请求了字体（不是缓存里什么都没发）", fontReqs.length > 0, String(fontReqs.length));
check("所有字体请求都是 200", bad.length === 0, bad.map((r) => r.url.split("/").pop() + "=" + r.status).join(","));
check("没有任何 woff/ttf/otf/eot 回退请求（删除它们的前提）", older.length === 0, older.map((r) => r.url.split("/").pop()).join(","));
check("没有字体加载失败", fontFail.length === 0, fontFail.map((f) => f.url.split("/").pop()).join(","));
check("字体传输量合理（< 400 KB）", totalKB > 0 && totalKB < 400, totalKB.toFixed(0) + " KB");

/* ── 检查 ②：字体真的加载 ── */
const has = (n) => loadedFams.includes(n);
check("KaTeX_Main 已加载（数字/运算符/正文）", has("KaTeX_Main"), `${loadedFams.length} 族`);
check("KaTeX_Math 已加载（斜体变量）", has("KaTeX_Math"));
check("KaTeX_Size 已加载（根号/积分/大括号）", has("KaTeX_Size1") && has("KaTeX_Size2"));
check("KaTeX_AMS / Caligraphic / Fraktur 已加载（\\mathbb \\mathcal \\mathfrak）",
  has("KaTeX_AMS") && has("KaTeX_Caligraphic") && has("KaTeX_Fraktur"));

/* ── 检查 ③：真字体参与排版（与回退字体量宽不同） ── */
const glyph = await evalJs(`(function(){
  const c = document.createElement('canvas').getContext('2d');
  const w = (font, text) => { c.font = font; return c.measureText(text).width; };
  const real = w('400 40px "KaTeX_Main", serif', 'Mx');
  const fallback = w('400 40px "NoSuchFont_ZZZ", serif', 'Mx');
  return { real: +real.toFixed(2), fallback: +fallback.toFixed(2), diff: +Math.abs(real - fallback).toFixed(2) };
})()`);
console.log("   字形测宽:", JSON.stringify(glyph));
check("真字体参与排版（与回退字体量宽不同）", glyph && typeof glyph.diff === "number" && glyph.diff > 0.5, JSON.stringify(glyph));

/* ── 检查 ④：两条渲染路径逐族落到真字体 ── */
const used = await evalJs(`(function(){
  const inp = document.querySelector('.cb-input');
  const sr = inp && inp.shadowRoot ? inp.shadowRoot : null;
  const leaves = sr ? [...sr.querySelectorAll('*')].filter((e) => !e.children.length && e.textContent.trim()) : [];
  return leaves.map((e) => ({ t: e.textContent.trim().slice(0, 3), fam: String(getComputedStyle(e).fontFamily).replace(/[\"']/g, '').split(',')[0].trim() }));
})()`);
const famOf = (ch) => { const hit = (used || []).find((u) => u.t.includes(ch)); return hit ? hit.fam : "(无)"; };
console.log("   输入框各族落点:", JSON.stringify((used || []).map((u) => u.t + "→" + u.fam)));

check("结果对话框里渲染出 KaTeX", !!dlg && dlg.katex > 0, dlg ? "katex×" + dlg.katex + " | " + dlg.mordText : "");
check("KaTeX 结果的字形用 KaTeX 字体族", !!dlg && /KaTeX_Main/.test(String(dlg.mordFam)), String(dlg && dlg.mordFam));
check("结果保留 LaTeX 源码（data-tex）", !!dlg && dlg.tex.length > 0 && String(dlg.tex[0]).length > 0, JSON.stringify(dlg && dlg.tex));
check("变量 x 用 KaTeX_Math（输入框）", famOf("x") === "KaTeX_Math", "x→" + famOf("x"));
check("\\mathbb{R} 用 KaTeX_AMS", famOf("R") === "KaTeX_AMS", "R→" + famOf("R"));
check("\\mathcal{L} 用 KaTeX_Caligraphic", famOf("L") === "KaTeX_Caligraphic", "L→" + famOf("L"));
check("\\mathfrak{g} 用 KaTeX_Fraktur", famOf("g") === "KaTeX_Fraktur", "g→" + famOf("g"));
check("√ 用 KaTeX_Size1、∫ 用 KaTeX_Size2", famOf("√") === "KaTeX_Size1" && famOf("∫") === "KaTeX_Size2",
  "√→" + famOf("√") + " ∫→" + famOf("∫"));

console.log(`\n═══ 字体加载验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|cdp-font-load|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
