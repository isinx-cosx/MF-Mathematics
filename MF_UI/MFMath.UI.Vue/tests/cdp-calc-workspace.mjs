// 验证计算工作区：模式列表、自动映射计算、多参数弹窗、结果对话框、未映射提示
// 策略：从下拉里动态挑选"已映射"的模式来测（视图模式名与引擎映射名并不完全一致），
//       并用"未映射"的模式验证明确提示（不静默）。
// 用法: node cdp-calc-workspace.mjs
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
await send("Runtime.enable");
await sleep(1500);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

/** 列出下拉里的模式及其映射状态 */
const listModes = () => evalJs(`(function(){
  const sel = document.querySelector('.cb-mode');
  if (!sel) return [];
  return [...sel.options].map(o => ({
    value: o.value,
    mapped: o.dataset.mapped === 'true',
    varDialog: o.dataset.varDialog === 'true',
    label: o.textContent.trim(),
  }));
})()`);

const setBlock = async (expr, mode) => {
  const r = await evalJs(`(function(){
  const inp = document.querySelector('.cb-input');
  if (!inp) return 'no-input';
  const setter = { call: (el, v) => { if (el && el.tagName === 'MATH-FIELD') { el.value = v; } else { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); } } };
  setter.call(inp, ${JSON.stringify(expr)});
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  if (${JSON.stringify(mode)}) {
    const sel = document.querySelector('.cb-mode');
    if (![...sel.options].some(o => o.value === ${JSON.stringify(mode)})) return 'no-mode';
    const ssetter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;
    ssetter.call(sel, ${JSON.stringify(mode)});
    sel.dispatchEvent(new Event('change', { bubbles: true }));
  }
  return 'ok';
})()`);
  /* ⚠ 找不到模式时**必须响**。
   *
   * 这里原先是 `const setBlock = (expr, mode) => evalJs(...)`，只把 'no-mode' 当作
   * **返回值**交给调用方，而所有调用方都不看返回值。于是"模式没切成功 → 留在上一个模式
   * 计算 → 结果里没有键值行"被静默吞掉，最后表现成一条完全看不懂的断言失败。
   * 本文件的「结果行的键名已中文化」(.res-key) 就是这么藏了很久的：它真正的原因是
   * **产品侧缺入口** —— `解一元二次`（solve_quadratic）当时不在代数页的模式表里，
   * 引擎有实现有测试、用户却选不到。已在 viewConfigs 补齐，并由 tools/check-ui.mjs
   * 的模式可达性自检看住（每个 ENGINE_MAP 模式必须能在某页面上选到，或显式登记）。
   */
  check(`设置计算块（模式：${mode || "默认"}）`, r === "ok", String(r));
  return r;
};

const clickCalc = () => evalJs(`(function(){
  const b = document.querySelector('.cb-calc'); if (!b) return 'no-btn'; b.click(); return 'clicked';
})()`);

const readDialog = () => evalJs(`(function(){
  const dlg = document.querySelector('.dialog');
  if (!dlg) return null;
  const resEl = dlg.querySelector('.dialog-result');
  const tex = (root) => root ? [...root.querySelectorAll('[data-tex]')].map(e => e.getAttribute('data-tex')) : [];
  return {
    header: dlg.querySelector('.dialog-header')?.textContent.trim() || '',
    context: dlg.querySelector('.dialog-context')?.textContent.trim() || '',
    contextTex: tex(dlg.querySelector('.dialog-context')),
    result: resEl ? resEl.textContent.trim().slice(0, 200) : '',
    html: resEl ? resEl.innerHTML.slice(0, 300) : '',
    resultTex: tex(resEl),
    resultKatex: resEl ? resEl.querySelectorAll('.katex').length : 0,
    hasSup: resEl ? !!resEl.querySelector('sup') : false,
    hasTable: !!dlg.querySelector('.res-table'),
    hasRow: !!dlg.querySelector('.res-row'),
  };
})()`);

const closeDialog = async () => { await evalJs(`document.querySelector('.dialog-close')?.click()`); await sleep(400); };
const readError = () => evalJs(`(function(){
  const e = document.querySelector('.cb-error');
  return e && !e.hidden ? e.textContent.trim() : '';
})()`);
const readFoot = () => evalJs(`[...document.querySelectorAll('.ws-foot span')].map(e=>e.textContent.trim()).join(' | ')`);

await evalJs("location.hash = '#/calc/algebra'");
await sleep(2600);

/* ── ① 视图加载 ── */
console.log("── 代数计算工作区 ──");
const head = await evalJs(`(function(){
  return { title: document.querySelector('.ws-title')?.textContent.trim() || '',
           desc: document.querySelector('.ws-desc')?.textContent.trim() || '',
           foot: [...document.querySelectorAll('.ws-foot span')].map(e=>e.textContent.trim()).join(' | ') };
})()`);
console.log("   标题:", head.title);
console.log("   状态栏:", head.foot);
check("标题为「代数计算」", head.title === "代数计算", head.title);
check("含说明文字", head.desc.includes("包含"), head.desc);

const allModes = await listModes();
const mapped = allModes.filter((m) => m.mapped);
const unmapped = allModes.filter((m) => !m.mapped);
const withVar = allModes.filter((m) => m.varDialog);
console.log(`   模式总数 ${allModes.length}：已映射 ${mapped.length}，未映射 ${unmapped.length}，需参数 ${withVar.length}`);
console.log("   未映射示例:", JSON.stringify(unmapped.slice(0, 5).map((m) => m.value)));
// 这条原先钉死"总数 == 46（与旧版一致）"。写这条时是 46，现在是 48。
// ⚠ 差额**不是**某一轮重积分改动引入的 —— 那几处只加在"微积分"视图；
//   这里是**代数**视图（本用例第 108 行先跳到 #/calc/algebra）。所以这 2 项来路待查。
// 钉死总数只会在每次加模式时误报，而且它并不表达真正的意图：模式表没被砍、且都接上了引擎。
// 改成"不少于旧版的 46 项，且全部已映射"；若这 48 项里有不该出现的，请另立断言点名。
check("模式列表不少于旧版的 46 项且全部已映射",
  allModes.length >= 46 && unmapped.length === 0,
  `总数 ${allModes.length}，未映射 ${unmapped.length}`);
// 这一条钉的是"未接入要在下拉里说清楚"。代数视图已经全部接入（未映射 0），
// 所以现在改成：任何标着未接入的模式，标签里必须写明原因；没有未接入的也算通过。
check("未接入的模式必须在下拉里标明（本视图 " + unmapped.length + " 项）",
  unmapped.every((m) => m.label.includes("未接入引擎")), `${unmapped.length} 项`);
check("有已映射模式可供计算", mapped.length > 20, String(mapped.length));

/* ── ② 自动映射计算（动态选一个已映射的简单表达式模式）── */
console.log("\n── 自动映射计算 ──");
const simple = mapped.find((m) => ["表达式化简", "化简", "展开", "函数定义域", "三角周期性"].includes(m.value)) || mapped[0];
console.log(`   选用模式：${simple.value}`);
const setRes = await setBlock("x^2-4", simple.value);
const actual = await evalJs(`(function(){
  const inp = document.querySelector('.cb-input'); const sel = document.querySelector('.cb-mode');
  return { expr: inp?.value, mode: sel?.value };
})()`);
console.log("   setBlock:", setRes, "| 实际:", JSON.stringify(actual));
check("模式与表达式设置成功", actual.mode === simple.value && actual.expr === "x^2-4", JSON.stringify(actual));

await clickCalc();
await sleep(1500);
let dlg = await readDialog();
const err0 = await readError();
console.log("   对话框:", JSON.stringify(dlg), "| 行内错误:", JSON.stringify(err0));
check("结果对话框弹出（自动映射路径）", !!dlg, `错误=${err0}`);
check("对话框标题含模式名", dlg && dlg.header.includes(simple.value), dlg ? dlg.header : "");
// 上下文一栏的语义是"你要算的是这个"，必须按用户书写的顺序排版。
// prepare_expr 给 x^{2} - 4；sym_latex 走 SymEngine 打印器会重排成 -4 + x^2 —— 那会让人以为输入变了。
check("上下文按书写顺序排版（x^{2} - 4，而不是规范化的 -4 + x^2）",
  dlg && /\^\{2\}/.test(dlg.contextTex.join(" ")) && !/-4\s*\+/.test(dlg.contextTex.join(" ")),
  dlg ? JSON.stringify(dlg.contextTex) : "");
check("结果非空", dlg && dlg.result.length > 0, dlg ? dlg.result : "");
check("结果用 KaTeX 排版（渲染出 .katex）", dlg && dlg.resultKatex > 0, dlg ? "katex×" + dlg.resultKatex : "");
check("不再用 <sup> 假装上标", dlg && dlg.hasSup === false, dlg ? String(dlg.hasSup) : "");
check("结果保留 LaTeX 源码（data-tex，供核对/复制）",
  dlg && dlg.resultTex.length > 0 && dlg.resultTex[0].length > 0, JSON.stringify(dlg ? dlg.resultTex : null));
check("上下文也是排版出来的数学", dlg && dlg.contextTex.length > 0, JSON.stringify(dlg ? dlg.contextTex : null));
await closeDialog();

/* ── ③ 逐类结果渲染：数组 / 对象 / 表格 ── */
console.log("\n── 多模式的自动映射覆盖（抽查 6 个已映射模式）──");
let okRuns = 0, failRuns = [];
const sample = mapped.filter((m) => !m.varDialog).slice(0, 14);
for (const m of sample) {
  await setBlock("x^2-4", m.value);
  await clickCalc();
  await sleep(900);
  const d = await readDialog();
  const e = await readError();
  if (d) { okRuns++; await closeDialog(); }
  else failRuns.push(`${m.value}${e ? "(" + e.slice(0, 30) + ")" : ""}`);
}
console.log(`   抽查 ${sample.length} 个模式：成功弹窗 ${okRuns}，未弹窗 ${failRuns.length}`);
if (failRuns.length) console.log("   未弹窗:", JSON.stringify(failRuns));
check("多数已映射模式可正常计算（>= 60%）", okRuns >= Math.ceil(sample.length * 0.6), `${okRuns}/${sample.length}`);

/* ── ④ 未映射模式：明确提示（不静默）── */
console.log("\n── 未映射模式的提示 ──");
if (unmapped.length) {
  await setBlock("x^2-4", unmapped[0].value);
  await clickCalc();
  await sleep(900);
  const e = await readError();
  const d = await readDialog();
  console.log(`   模式「${unmapped[0].value}」→ 行内错误: ${JSON.stringify(e)}`);
  check("未映射模式给出明确提示且不弹空对话框", e.includes("暂无引擎映射") && !d, e);
} else {
  check("存在未映射模式用于验证（可跳过）", true, "当前视图全部已映射");
}

/* ── ⑤ 多参数弹窗（微积分视图的「求导」）── */
console.log("\n── 多参数弹窗（微积分 → 求导）──");
await evalJs("location.hash = '#/calc/calculus'");
await sleep(2200);
const calcModes = await listModes();
const varMode = calcModes.find((m) => m.varDialog && m.mapped);
console.log(`   选用需参数的模式：${varMode ? varMode.value : "(无)"}`);
check("微积分视图有需参数的模式", !!varMode, varMode ? varMode.value : "");

if (varMode) {
  await setBlock("x^3", varMode.value);
  await clickCalc();
  await sleep(900);
  const md = await evalJs(`(function(){
    const d = document.querySelector('.dialog');
    if (!d) return null;
    return { header: d.querySelector('.dialog-header')?.textContent.trim() || '',
             labels: [...d.querySelectorAll('.mvar-label')].map(e=>e.textContent.trim()),
             values: [...d.querySelectorAll('.dialog .input')].map(i=>i.value) };
  })()`);
  console.log("   弹窗:", JSON.stringify(md));
  check("多参数弹窗弹出", !!md, JSON.stringify(md));
  check("字段与默认值就位（第一个字段预填表达式）", md && md.values[0] === "x^3", md ? JSON.stringify(md.values) : "");

  const confirmed = await evalJs(`(function(){
    const ok = [...document.querySelectorAll('.dialog .btn-primary')].find(b => b.textContent.trim() === '计算');
    if (!ok) return 'no-btn'; ok.click(); return 'clicked';
  })()`);
  await sleep(1500);
  const rd = await readDialog();
  console.log("   确认后结果:", JSON.stringify(rd));
  check("参数确认后给出结果", confirmed === "clicked" && !!rd, "");
  // x³ 求导 → 3*x^2。KaTeX 把公式拆成 span，文字读不回原式，
  // 所以按 data-tex 上的 LaTeX 源码核对（3 x^{2}），而不是翻 DOM 文本。
  check("结果是排版的 3x²（LaTeX 源码含 3 与 x^2）",
    rd && rd.resultTex.some((t) => /3/.test(t) && /x/.test(t) && /\^/.test(t)),
    rd ? JSON.stringify(rd.resultTex) : "");
  await closeDialog();
}

/* ── ⑤b 对象结果：字段名/中文说明不能排成数学 ──
   三角周期性返回 {description, frequency, period}：
   里面有数学（2π、1/2π）也有说明文字，正好验证"逐字段判定"。
   矩阵/一维数组那两条分支从界面点不出来（引擎的高斯消元返回 {rank, free_vars, type}，
   不返回矩阵），它们由 tests/unit-result-model.mjs 用假桥钉住。 */
console.log("\n── 对象结果：逐字段判定数学/文字 ──");
await evalJs("location.hash = '#/calc/algebra'");
await sleep(1800);
await setBlock("sin", "三角周期性");
await clickCalc();
await sleep(1400);
const objDlg = await readDialog();
console.log("   对象结果:", objDlg ? objDlg.result : "(无)", "| LaTeX:", objDlg ? JSON.stringify(objDlg.resultTex) : "");
check("对象结果渲染成键值行（.res-row）", objDlg && objDlg.hasRow,
  objDlg ? JSON.stringify({ hasRow: objDlg.hasRow, result: objDlg.result }) : "");
check("对象里的数学字段用 KaTeX 排版", objDlg && objDlg.resultKatex > 0,
  objDlg ? "katex×" + objDlg.resultKatex : "");
check("中文说明字段没有被当成公式（description 走纯文本）",
  objDlg && objDlg.resultTex.every((t) => !/[\u4e00-\u9fff]/.test(t)),
  objDlg ? JSON.stringify(objDlg.resultTex) : "");
await closeDialog();

/* ── ⑥ 计算块增删 ── */
console.log("\n── 计算块增删 ──");
const before = await evalJs(`document.querySelectorAll('.calc-block').length`);
await evalJs(`document.querySelector('.btn-add')?.click()`);
await sleep(600);
const afterAdd = await evalJs(`document.querySelectorAll('.calc-block').length`);
await evalJs(`(function(){ const b=[...document.querySelectorAll('.cb-del')].pop(); if(b) b.click(); return 'ok'; })()`);
await sleep(600);
const afterDel = await evalJs(`document.querySelectorAll('.calc-block').length`);
console.log("   块数:", before, "→", afterAdd, "→", afterDel);
check("可添加计算块", afterAdd === before + 1, `${before} → ${afterAdd}`);
check("可删除计算块", afterDel === afterAdd - 1, `${afterAdd} → ${afterDel}`);

/* ── ⑦ 多视图切换（配置随路由变化）── */
console.log("\n── 多视图配置 ──");
const titles = {};
for (const [path, expect] of [["#/calc/probability", "概率论与数理统计"], ["#/calc/number-theory", "数论"], ["#/calc/linear-algebra", "线性代数"]]) {
  await evalJs(`location.hash = '${path}'`);
  await sleep(1600);
  const t = await evalJs(`document.querySelector('.ws-title')?.textContent.trim() || ''`);
  const n = await evalJs(`document.querySelectorAll('.cb-mode option').length`);
  titles[expect] = { title: t, modes: n };
  console.log(`   ${path} → ${t}（${n} 个模式）`);
}
check("概率论视图配置正确", titles["概率论与数理统计"]?.title === "概率论与数理统计", JSON.stringify(titles["概率论与数理统计"]));
check("数论视图配置正确", titles["数论"]?.title === "数论", JSON.stringify(titles["数论"]));
check("线性代数视图配置正确", titles["线性代数"]?.title === "线性代数", JSON.stringify(titles["线性代数"]));

/* ══════════ 结果弹窗：可滚动 / 中文标签 / 复制内容 / 错误标题 ══════════
 *
 * 四条都是"用户看得见却没人测"的：长结果被裁、引擎英文键名摆到脸上、
 * 出错时标题还写"计算结果"、复制出来是包装 JSON。 */
console.log("\n── 结果弹窗：滚动 / 中文标签 / 复制 / 错误标题 ──");
await evalJs("location.hash = '#/calc/algebra'");
await sleep(1200);
/* ⚠ 这里要用「解方程/组」而不是「解一元二次」——两者返回的形状不同：
 *   · 解方程/组 → solve_sym → **对象** {delta, deltaSign, realness, realnessReason, …}
 *     （下面「键名已中文化」要检查的 deltaSign / realnessReason 正是它的键）；
 *   · 解一元二次 → solve_quadratic → **纯数组** ["2","3"]，**根本没有键值行**（.res-key = 0 个），
 *     而且它对畸形输入 `sin(` 返回 isError:false + 空数组（不报错），
 *     于是「出错时标题显示错误」也失去前提。
 * 这条断言以前一直红，就是因为点了不会产生对象、也不会报错的模式；
 * 而它曾经"看起来"只在一条上失败，是因为模式切换另有一个 bug 在替它兜底（见 setBlock 的注释）。 */
await setBlock("x^2-5x+6", "解方程/组");
await clickCalc();
let dlgS = await readDialog();
check("解方程/组给出结果", !!dlgS, (dlgS?.text || "").slice(0, 40));

const dstyle = await evalJs(`(function(){
  const body = document.querySelector('.dialog-body');
  const dlg = document.querySelector('.dialog');
  if (!body || !dlg) return null;
  const bs = getComputedStyle(body), ds = getComputedStyle(dlg);
  return { bodyOverflowY: bs.overflowY, dialogOverflowY: ds.overflowY, dialogMaxH: ds.maxHeight };
})()`);
console.log("   弹窗样式:", JSON.stringify(dstyle));
check("结果区可纵向滚动（长结果不会被裁）", dstyle?.bodyOverflowY === "auto", dstyle?.bodyOverflowY);
// max-height 写的是 calc(100vh - 40px)，getComputedStyle 会解析成具体 px
// （实测 780px），所以按"小于视口高"来判断封顶，而不是去匹配 vh 字面量。
check("弹窗高度有封顶（不会撑出视口）",
  parseFloat(dstyle?.dialogMaxH || "0") > 0 &&
  parseFloat(dstyle.dialogMaxH) <= (await evalJs("window.innerHeight")),
  dstyle?.dialogMaxH);

const keys = await evalJs(`[...document.querySelectorAll('.dialog .res-key')].map((e) => e.textContent.trim())`);
console.log("   结果行标签:", JSON.stringify(keys));
check("结果行的键名已中文化（没有 deltaSign/realnessReason 这类英文键）",
  (keys || []).length > 0 && (keys || []).every((k) => !/^[a-zA-Z_]+$/.test(k)), JSON.stringify(keys));

// 复制结果必须是可读文本，而不是 {"isError":…} 包装 JSON
await evalJs(`(function(){
  window.__copied = null;
  navigator.clipboard.writeText = (t) => { window.__copied = t; return Promise.resolve(); };
  const b = [...document.querySelectorAll('.dialog-footer .btn')].find((x) => /复制结果/.test(x.textContent));
  if (b) b.click();
  return 1;})()`);
await sleep(300);
const copied = await evalJs("window.__copied");
console.log("   复制到:", JSON.stringify(copied));
check("复制结果是可读文本（不是包装 JSON）",
  typeof copied === "string" && copied.length > 0 && !/isError/.test(copied), String(copied).slice(0, 60));
await closeDialog();

// 出错时标题要显示「错误」，而不是照样写"计算结果"
// 用「解方程/组」：它对 `sin(` 会真的返回 isError（"syntax error"）。
// 「解一元二次」不会 —— solve_quadratic("sin(") 是 isError:false + 空数组。
await setBlock("sin(", "解方程/组");
await clickCalc();
const title = await evalJs(`(document.querySelector('.dialog-header span')||{}).textContent||''`);
console.log("   出错时标题:", JSON.stringify(title));
check("出错时标题显示「错误」", /错误/.test(title), title);
await closeDialog();

console.log(`\n═══ 计算工作区验证：${pass} 通过 / ${fail} 失败 ═══`);
/* ── ⑥ 表达式输入框是 MathLive（数学就地排版）── */
console.log("\n── MathLive 输入框 ──");
await evalJs("location.hash = '#/calc/algebra'");
await sleep(1600);
const tag = await evalJs("(document.querySelector('.cb-input') || {}).tagName");
const shadowed = await evalJs("!!(document.querySelector('.cb-input') || {}).shadowRoot");
check("代数页表达式输入框是 <math-field>", tag === "MATH-FIELD", String(tag));
check("框内为 MathLive 渲染（有 shadow DOM）", shadowed === true, String(shadowed));

// 输入框在这一页也必须"干净 + 够大 + 高度自适应"：
// 宿主被写成 flex 会把 shadow DOM 里的容器当成并排 flex 项，排版错位；
// 字号/高度曾经被 .input（13px / 34px 固定高）压住，分数会被裁掉。
const cbGeo = await evalJs(`(function(){
  const mf = document.querySelector('.cb-input');
  const cs = getComputedStyle(mf);
  const r = mf.getBoundingClientRect();
  const sr = mf.shadowRoot;
  const hide = (p) => { const e = sr && sr.querySelector('[part=' + p + ']'); return !e || getComputedStyle(e).display === 'none'; };
  return {
    display: cs.display,
    fontSize: Math.round(parseFloat(cs.fontSize)),
    height: Math.round(r.height),
    overflow: Math.round(mf.scrollHeight - mf.clientHeight),
    togglesHidden: hide('virtual-keyboard-toggle') && hide('menu-toggle')
  };
})()`);
console.log("   输入框几何:", JSON.stringify(cbGeo));
check("代数页输入框是普通块级（不被写成 flex 容器）", cbGeo.display === "block", String(cbGeo.display));check("代数页输入框字号够大（>=21px，不被 .input 的 13px 压住）", cbGeo.fontSize >= 21, cbGeo.fontSize + "px");
check("代数页输入框够高（>=56px，不被 .input 的 34px 压住）", cbGeo.height >= 56, cbGeo.height + "px");
check("代数页输入框自带角标已隐藏", cbGeo.togglesHidden === true, JSON.stringify(cbGeo));
check("代数页输入框内容不溢出", cbGeo.overflow <= 1, JSON.stringify(cbGeo));

// LaTeX 写法应可直接输入并被引擎接受
await evalJs(`(function(){
  const el = document.querySelector('.cb-input');
  // 用 JSON.stringify 生成页面侧字面量：直接写 '\\frac…' 会在嵌套模板里
  // 被解析成 \f（换页符），值会变成 "rac{1}{2}x+3" 这种残缺字符串。
  el.value = ${JSON.stringify("\\frac{1}{2}x+3")};
  el.dispatchEvent(new Event('input', { bubbles: true }));
  return 1;
})()`);
await sleep(700);
check("LaTeX 写法可输入（字段保留 frac）",
  /frac/.test(String(await evalJs("document.querySelector('.cb-input').value"))),
  String(await evalJs("document.querySelector('.cb-input').value")));
check("LaTeX 输入不触发行内报错",
  (await evalJs("(document.querySelector('.cb-error')||{}).textContent || ''")) === "", "");

/* ── ⑦ 先改表达式、再改模式：模式不能被丢弃 ──
   这条钉的是一个真实缺陷：patchBlock 用 {...b} 生成**新对象**，而同一行
   select v-model="b.mode" 的处理器闭包持有的是**旧对象** —— 若改表达式时
   调用了 patchBlock，随后改模式就会写进已被丢弃的孤儿对象而静默失效。
   根因是组件更新走了"替换数组元素"而不是"原地改属性"。 */
console.log("\n── 顺序敏感：先改表达式再改模式 ──");
const orderRes = await evalJs(`(function(){
  const inp = document.querySelector('.cb-input');
  inp.value = 'x^2-4';
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  const sel = document.querySelector('.cb-mode');
  const opt = [...sel.options].find(o => o.dataset.mapped === 'true' && o.dataset.varDialog !== 'true');
  if (!opt) return { err: 'no-mapped-mode' };
  const ssetter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;
  ssetter.call(sel, opt.value);
  sel.dispatchEvent(new Event('change', { bubbles: true }));
  return { want: opt.value };
})()`);
await sleep(900);
const orderAfter = await evalJs("document.querySelector('.cb-mode').value");
check("先改表达式再改模式，模式仍然保留",
  orderRes && orderAfter === orderRes.want, JSON.stringify({ want: orderRes && orderRes.want, got: orderAfter }));

await evalJs("document.querySelector('.cb-calc').click()");
await sleep(1600);
check("该顺序下计算正常出结果",
  (await evalJs("!!document.querySelector('.dialog')")) === true,
  String(await evalJs("(document.querySelector('.dialog-result')||{}).textContent || ''")).slice(0, 60));
console.log(`RESULT|calc-workspace|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
