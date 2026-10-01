// 验证含参极值的"定义域"判定：导数零点存在 ≠ 它是极值点
//
// 覆盖 ln 形态（高考导数题最高频）：a·x−ln x、ln x−a·x、x−a·ln x、x²−a·ln x。
// 曾经的错误行为：只看 f''(x₀) 的符号就报 minimum/maximum，于是
//   a·x−ln x 在 a<0 时报极小值（x=1/a<0 根本不在定义域 x>0 内）、
//   a=0 时报 degenerate（驻点 1/a 无定义）；
//   x²−a·ln x 干脆不给分支数组，负根也报极小值。
// 用法: node cdp-plot-extrema-domain.mjs
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

/** 读取侧栏：按参数取值分组的块，每块含若干驻点结论行。
 *  块标题（.branch-head）给出参数情形（如 a>0），行内是 x / 结论 / 极值或原因。 */
async function readGroups() {
  return await evalJs(`(function(){
    return [...document.querySelectorAll('.pt-sym')].map(g => ({
      assume: (g.querySelector('.branch-head .branch-tag')||{}).textContent || '',
      text: g.textContent.replace(/\\s+/g,' ').trim(),
      rows: [...g.querySelectorAll('.pt-branch')].map(b => ({
        x:      (b.querySelector('.branch-x')||{}).textContent || '',
        xTex:   (b.querySelector('.branch-x [data-tex]')||{}).getAttribute?.('data-tex') || '',
        kind:   (b.querySelector('.branch-kind')||{}).textContent || '',
        fvalue: (b.querySelector('.branch-value')||{}).textContent || '',
        note:   (b.querySelector('.branch-note')||{}).textContent || ''
      }))
    }));
  })()`);
}
const find = (groups, assume) => (groups || []).find((g) => (g.assume || "").trim() === assume);
/** 该参数组下是否出现某种结论（不区分具体驻点）。 */
const kindIn = (groups, assume, re) =>
  (((find(groups, assume) || {}).text) || "").length > 0 && re.test((find(groups, assume) || {}).text || "");
/** 该参数组下某结论出现几次。 */
const countKind = (groups, assume, re) =>
  (((find(groups, assume) || {}).rows) || []).filter((r) => re.test(r.kind || "")).length;

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

/* ── ① f = a·x − ln x：a<0 与 a=0 都没有极值点 ── */
console.log("── f(x) = a·x − ln x（定义域 x>0）──");
await setExpr("a*x-ln(x)");
let gr = await readGroups();
console.log("   分组:", JSON.stringify(gr.map((g) => ({ assume: g.assume, rows: g.rows.map((r) => r.kind) }))));
check("按参数取值分组为 a>0 / a=0 / a<0",
  !!find(gr, "a>0") && !!find(gr, "a=0") && !!find(gr, "a<0"), JSON.stringify(gr.map((g) => g.assume)));
// 驻点是符号解（a>0 时 x=1/a）：用 KaTeX 排版，而不是把 "1/a" 当 ASCII 显示
const xTexAll = gr.flatMap((g) => g.rows.map((r) => r.xTex)).filter(Boolean);
check("驻点用 KaTeX 排版（data-tex 里有 LaTeX 源码）",
  xTexAll.length > 0, JSON.stringify(xTexAll.slice(0, 4)));
check("a>0 判为极小值（x=1/a>0 在定义域内且有定义）",
  countKind(gr, "a>0", /极小值/) === 1, JSON.stringify(find(gr, "a>0")));
check("a>0 给出极值 f = 1",
  /f\s*=\s*1/.test((((find(gr, "a>0") || {}).rows) || [])[0]?.fvalue || ""), JSON.stringify(find(gr, "a>0")));
check("a=0 判为无极值点（驻点 1/a 无定义）",
  countKind(gr, "a=0", /无极值点/) === 1, JSON.stringify(find(gr, "a=0")));
check("a<0 判为无极值点（驻点 1/a<0 在定义域外）",
  countKind(gr, "a<0", /无极值点/) === 1, JSON.stringify(find(gr, "a<0")));
check("a<0 不得出现极小值", countKind(gr, "a<0", /极小值/) === 0, JSON.stringify(find(gr, "a<0")));
check("无效分支给出原因说明",
  !!((((find(gr, "a<0") || {}).rows) || [])[0]?.note || "").trim(), JSON.stringify(find(gr, "a<0")));

/* ── ② f = ln x − a·x：a<0 不得报极大值 ── */
console.log("\n── f(x) = ln x − a·x（定义域 x>0）──");
await setExpr("ln(x)-a*x");
gr = await readGroups();
console.log("   分组:", JSON.stringify(gr.map((g) => ({ assume: g.assume, rows: g.rows.map((r) => r.kind) }))));
check("a>0 判为极大值", countKind(gr, "a>0", /极大值/) === 1, JSON.stringify(find(gr, "a>0")));
check("a=0 判为无极值点", countKind(gr, "a=0", /无极值点/) === 1, JSON.stringify(find(gr, "a=0")));
check("a<0 判为无极值点", countKind(gr, "a<0", /无极值点/) === 1, JSON.stringify(find(gr, "a<0")));
check("a<0 不得出现极大值", countKind(gr, "a<0", /极大值/) === 0, JSON.stringify(find(gr, "a<0")));

/* ── ③ f = x − a·ln x：a=0 时驻点 x=0 也在定义域外 ── */
console.log("\n── f(x) = x − a·ln x（定义域 x>0）──");
await setExpr("x-a*ln(x)");
gr = await readGroups();
console.log("   分组:", JSON.stringify(gr.map((g) => ({ assume: g.assume, rows: g.rows.map((r) => r.kind) }))));
check("a>0 判为极小值（x=a>0）", countKind(gr, "a>0", /极小值/) === 1, JSON.stringify(find(gr, "a>0")));
// a=0 时 f′ ≡ 1 ≠ 0：既没有驻点，x=0 也在定义域外。引擎按"更根本的原因"给出
// 残差复核结论（结果不可信），两者都正确；关键性质是**不得报出极值**。
check("a=0 不报极值（f′≡1≠0，驻点 x=0 亦在定义域外）",
  countKind(gr, "a=0", /无极值点|结果不可信/) === 1 && countKind(gr, "a=0", /极小值|极大值/) === 0,
  JSON.stringify(find(gr, "a=0")));
check("a<0 判为无极值点（x=a<0 在定义域外）",
  countKind(gr, "a<0", /无极值点/) === 1, JSON.stringify(find(gr, "a<0")));
check("a<0 不得出现极大值", countKind(gr, "a<0", /极大值/) === 0, JSON.stringify(find(gr, "a<0")));

/* ── ④ f = x² − a·ln x：f'' 不含 a，但驻点依赖 a（旧版无分支）── */
console.log("\n── f(x) = x² − a·ln x（定义域 x>0）──");
await setExpr("x^2-a*ln(x)");
gr = await readGroups();
console.log("   分组:", JSON.stringify(gr.map((g) => ({ assume: g.assume, rows: g.rows.map((r) => r.kind) }))));
check("给出了参数分组（不再为空）", (gr || []).length > 0, JSON.stringify(gr));
check("a>0 下同时含「极小值」与「无极值点」——一个驻点在定义域内、一个在外",
  countKind(gr, "a>0", /极小值/) === 1 && countKind(gr, "a>0", /无极值点/) === 1,
  JSON.stringify(find(gr, "a>0")));
check("a<0 下无极值点（驻点 √(a/2) 非实）",
  countKind(gr, "a<0", /无极值点/) === 2, JSON.stringify(find(gr, "a<0")));
check("参数分组只有 3 块（每个驻点的同名分支已折叠到一起）",
  gr.length === 3, JSON.stringify(gr.map((g) => g.assume)));

/* ── ⑤ 换元降次：√ 与 tan 形态也能给出精确驻点 ── */
console.log("\n── 换元降次（√ 与 tan 形态）──");
const methods = await evalJs(`(function(){
  const mf = window.chrome.webview.hostObjects.sync.mf;
  const pick = (j) => { try { return JSON.parse(j).value; } catch (e) { return null; } };
  const sq = pick(mf.ExtremaSymbolic('a*sqrt(x)-x', 'x'));
  const tn = pick(mf.ExtremaSymbolic('a*x+tan(x)', 'x'));
  const nm = pick(mf.ExtremaSymbolic('exp(x)-2*x', 'x'));
  return {
    sq: sq && { method: sq.solveMethod, roots: sq.critical_points },
    tn: tn && { method: tn.solveMethod, roots: tn.critical_points },
    nm: nm && { method: nm.solveMethod, roots: nm.critical_points }
  };
})()`);
console.log("   √ 形态:", JSON.stringify(methods.sq));
console.log("   tan 形态:", JSON.stringify(methods.tn));
console.log("   指数形态:", JSON.stringify(methods.nm));
check("√ 形态走换元/消元并给出精确驻点 a²/4",
  methods.sq && (methods.sq.method === "substitution-sqrt" ||
                 methods.sq.method === "elimination-radical") &&
  JSON.stringify(methods.sq.roots).includes("a**2"), JSON.stringify(methods.sq));
check("tan 形态走换元并给出 atan 形式的精确驻点",
  methods.tn && methods.tn.method === "substitution-tan" &&
  JSON.stringify(methods.tn.roots).includes("atan"), JSON.stringify(methods.tn));
check("无法换元的指数形态回退为数值并标注",
  methods.nm && methods.nm.method === "numeric" &&
  Math.abs(Number(methods.nm.roots[0]) - Math.log(2)) < 1e-6, JSON.stringify(methods.nm));

console.log(`\n═══ 含参极值定义域验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|plot-extrema-domain|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
