// 验证 MathLive 就地排版输入框 + 课本写法
//
// 设计已从"文本框 + 下方 LaTeX 预览"改为 MathLive 的 <math-field>：
// 数学**直接排版在输入框内部**（shadow DOM 里的 .ML__latex），输入 \frac 当场变成分数。
// 用法: node cdp-input-notation.mjs
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage() {
  for (let i = 0; i < 30; i++) {
    try {
      const list = await (await fetch("http://127.0.0.1:9222/json/list")).json();
      const p = list.find((t) => t.type === "page" && /mfmath\.local|index\.html/.test(t.url || ""));
      if (p) return p.webSocketDebuggerUrl;
    } catch { /* 等待中 */ }
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
  await evalJs(`(function(){
    const el = document.querySelector('.expr-input');
    if (!el) return 'no-input';
    if (el.tagName === 'MATH-FIELD') {
      el.value = ${JSON.stringify(text)};
      el.dispatchEvent(new Event('input', { bubbles: true }));
    } else {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(el, ${JSON.stringify(text)});
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }
    return 'ok';
  })()`);
  await sleep(2200);
}

/** 读取输入框（MathLive 渲染在 shadow DOM 内）与整行状态 */
async function readField() {
  return await evalJs(`(function(){
    const mf = document.querySelector('.expr-input');
    if (!mf) return { missing: true };
    const sr = mf.shadowRoot;
    const box = sr ? sr.querySelector('.ML__latex') : null;
    const row = document.querySelector('.expr-row');
    return {
      tag: mf.tagName,
      value: mf.value ?? '',
      hasShadow: !!sr,
      renderedText: box ? box.textContent.replace(/\\s+/g,'') : '',
      error: row && row.querySelector('.expr-error') ? row.querySelector('.expr-error').textContent.trim() : '',
      legacyPreviewRows: document.querySelectorAll('.expr-preview').length
    };
  })()`);
}

async function curveOk() {
  return await evalJs(`(function(){
    const c = document.querySelector('canvas');
    if (!c) return false;
    const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    let n = 0;
    for (let i = 3; i < d.length; i += 4 * 97) if (d[i] > 0) n++;
    return n > 20;
  })()`);
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
await sleep(600);

console.log("── 就地排版（而不是下方预览）──");
let st = await readField();
console.log("   元素:", st.tag, " shadowDOM:", st.hasShadow, " 框内文本:", JSON.stringify(st.renderedText));
check("输入框是 <math-field>", st.tag === "MATH-FIELD", String(st.tag));
check("MathLive 已注册", await evalJs("!!customElements.get('math-field')"), "");
check("框内有排版内容（shadow DOM 的 .ML__latex）", st.hasShadow && st.renderedText.length > 0, JSON.stringify(st.renderedText));
check("旧的下方预览行已不存在（数学改在框内显示）", st.legacyPreviewRows === 0, "剩余 " + st.legacyPreviewRows + " 行");

console.log("\n── cosx：函数名后无括号 ──");
await setExpr("cosx");
st = await readField();
console.log("   框内:", JSON.stringify(st.renderedText), " 报错:", JSON.stringify(st.error));
check("cosx 不再报错", st.error === "", st.error);
check("框内渲染出 cosx", /cos/.test(st.renderedText), st.renderedText);
check("曲线画出（引擎接受了该写法）", await curveOk(), "");

console.log("\n── 2x、x^2、√x、π ──");
for (const [expr, re] of [["2x", /2/], ["x^2", /2/], ["\u221Ax", /x/], ["\u03C0", /\u03C0/]]) {
  await setExpr(expr);
  st = await readField();
  check(expr + " 可解析、框内渲染、无报错",
    st.error === "" && st.renderedText.length > 0 && re.test(st.renderedText),
    JSON.stringify({ rendered: st.renderedText, error: st.error }));
}

console.log("\n── LaTeX 写法：\\frac{1}{2}x ──");
await setExpr("\\frac{1}{2}x");
st = await readField();
console.log("   字段 LaTeX:", JSON.stringify(st.value), " 框内文本:", JSON.stringify(st.renderedText));
check("字段保留 LaTeX 形式", /frac/.test(st.value), st.value);
check("框内渲染出分数内容（含 1 与 2）", /1/.test(st.renderedText) && /2/.test(st.renderedText), st.renderedText);
check("引擎接受（无报错）", st.error === "", st.error);
check("曲线画出", await curveOk(), "");

console.log("\n── 输入框：干净、够大、高度自适应 ──");
// MathLive 自带两种"花里胡哨"：右下角的软键盘角标与菜单角标，必须藏掉。
const parts = await evalJs(`(function(){
  const mf = document.querySelector('.expr-input');
  const sr = mf && mf.shadowRoot;
  if (!sr) return { missing: true };
  const probe = (p) => {
    const e = sr.querySelector('[part=' + p + ']');
    if (!e) return { absent: true };
    const r = e.getBoundingClientRect();
    return { w: Math.round(r.width), h: Math.round(r.height), display: getComputedStyle(e).display };
  };
  return { kb: probe('virtual-keyboard-toggle'), menu: probe('menu-toggle') };
})()`);
const hidden = (p) => !p || p.absent || p.display === "none" || p.w === 0;
check("软键盘角标已隐藏（不是缩小，是不显示）", hidden(parts.kb), JSON.stringify(parts.kb));
check("菜单角标已隐藏", hidden(parts.menu), JSON.stringify(parts.menu));

/** 量一次输入框几何：字号、显示方式、高度、内容是否溢出 */
async function measure(label) {
  const g = await evalJs(`(function(){
    const mf = document.querySelector('.expr-input');
    if (!mf) return { missing: true };
    const cs = getComputedStyle(mf);
    const r = mf.getBoundingClientRect();
    const sr = mf.shadowRoot;
    const box = (sel) => { const e = sr && sr.querySelector(sel); return e ? Math.round(e.getBoundingClientRect().height) : null; };
    const latex = sr ? sr.querySelector('.ML__latex') : null;
    const lr = latex ? latex.getBoundingClientRect() : null;
    const padTop = parseFloat(cs.paddingTop) + parseFloat(cs.borderTopWidth);
    const padBot = parseFloat(cs.paddingBottom) + parseFloat(cs.borderBottomWidth);
    return {
      fontSize: Math.round(parseFloat(cs.fontSize)),
      display: cs.display,
      height: Math.round(r.height),
      innerH: box('.ML__container'),
      latexH: box('.ML__latex'),
      topInset: lr ? Math.round((lr.top - r.top) - padTop) : null,
      bottomInset: lr ? Math.round((r.bottom - lr.bottom) - padBot) : null,
      inlineHeight: mf.style.height || '(无内联高度)',
      vOverflow: Math.round(mf.scrollHeight - mf.clientHeight),
      latexOutside: lr ? Math.round(Math.max(0, lr.bottom - r.bottom)) : 0
    };
  })()`);
  console.log("   [" + label + "] " + JSON.stringify(g));
  return g;
}
await setExpr("x^2");
const gPlain = await measure("x^2");
check("宿主是 block（不是 flex，否则 shadow DOM 会被当 flex 项排版）", gPlain.display === "block", gPlain.display);
check("字号够看清 LaTeX（>=21px，原来继承 13/15px）", gPlain.fontSize >= 21, gPlain.fontSize + "px");
check("空一行时最小高度 >= 56px", gPlain.height >= 56, gPlain.height + "px");
check("数学在框内上下大致居中（上下留白差 <= 4px）",
  Math.abs(gPlain.topInset - gPlain.bottomInset) <= 4,
  "上 " + gPlain.topInset + "px / 下 " + gPlain.bottomInset + "px");
check("普通表达式不溢出框外", gPlain.vOverflow <= 1 && gPlain.latexOutside <= 1, JSON.stringify(gPlain));

// 高度自适应：内容比一行高时，框必须跟着长，而不是把内容裁掉/压到下一行。
// 用两层嵌套分数（\frac 里再套 \frac），它在 17px 字号下必然高过最小高度。
await setExpr("\\frac{\\frac{1}{2}x}{3}");
const gTall = await measure("\\frac{\\frac{1}{2}x}{3}");
check("高内容把输入框撑高（高度自适应，而不是裁掉）",
  gTall.height > gPlain.height, gPlain.height + "px → " + gTall.height + "px");
check("框高确实包住排版结果（内部容器 <= 框高）",
  gTall.innerH !== null && gTall.innerH <= gTall.height,
  "容器 " + gTall.innerH + "px / 框 " + gTall.height + "px");
check("高内容完全落在框内（不溢出、不压到下一行）",
  gTall.vOverflow <= 1 && gTall.latexOutside <= 1, JSON.stringify(gTall));
check("MathLive 没有给宿主写死内联高度", gTall.inlineHeight === "(无内联高度)", String(gTall.inlineHeight));

console.log("\n── 符号面板 ──");
await setExpr("");
const nSym = await evalJs("document.querySelectorAll('.symbol-bar .symbol-btn').length");
check("符号面板有按钮", nSym >= 10, "按钮数 " + nSym);
await evalJs(`(function(){
  const btn = [...document.querySelectorAll('.symbol-bar .symbol-btn')]
    .find(b => b.textContent.trim() === '\u03C0');
  if (btn) btn.click();
  return 'ok';
})()`);
await sleep(400);
st = await readField();
check("点击 π 后在框内插入 \\pi", /pi/.test(st.value), st.value);

await setExpr("y=x^2");
console.log("\n   已恢复默认表达式 y=x^2");

console.log(`\n═══ MathLive 就地排版与写法验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|input-notation|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);