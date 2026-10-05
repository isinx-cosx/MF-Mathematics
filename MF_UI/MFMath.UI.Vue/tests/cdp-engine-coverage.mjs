// 全模式点算覆盖：把每个视图下拉里的**每一个模式**都真跑一遍，看引擎有没有报错
//
// 为什么需要它：ENGINE_MAP 里的条目只要参数对不上（缺 key、类型写错、弹窗字段错位），
// 表现就是"对话框弹出但内容是错误信息"或者"压根不弹窗"—— 这类问题看代码看不出来，
// 只有真调一次才知道。本脚本就是"每个模式都必须真正可算"的执行者。
//
// 判定：对话框出现 且 结果不是「错误：…」→ 通过。
// 用法: node cdp-engine-coverage.mjs   （需宿主在 9222 开着）
import { MODE_SAMPLE } from "./fixtures/mode-samples.mjs";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage() {
  for (let i = 0; i < 30; i++) {
    try {
      const list = await (await fetch("http://127.0.0.1:9222/json/list")).json();
      const p = list.find((t) => t.type === "page" && /mfmath\.local|index\.html/.test(t.url || ""));
      if (p) return p.webSocketDebuggerUrl;
    } catch { /* 等宿主起来 */ }
    await sleep(1000);
  }
  return null;
}
const wsUrl = await findPage();
if (!wsUrl) { console.error("未找到宿主页面"); process.exit(1); }
const ws = new WebSocket(wsUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0;
const send = (method, params, timeoutMs = 30000) => new Promise((resolve) => {
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
const evalJs = async (expr, timeoutMs) => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }, timeoutMs);
  if (r.result?.exceptionDetails) return "[异常] " + (r.result.exceptionDetails.text || "");
  return r.result?.result?.value;
};
await send("Runtime.enable");
await sleep(1200);

let pass = 0, fail = 0;
const failures = [];
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  if (!ok) failures.push({ label, detail });
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

/* 视图 → 样本输入。默认按视图给一个能算的例子；个别模式用覆盖表。
   样本里的 `;` 分段顺序 = 该模式 args 的声明顺序（第一段是那条表达式）。 */
const VIEWS = [
  ["algebra", "x^2-4"],
  ["algebraic-topology", ""],
  ["analytic-geometry", "(1,2);(3,4)"],
  ["calculus", "x^2-4"],
  ["complex-analysis", "(1+I)^2"],
  ["functional-analysis", "x; x^2; -1,1"],
  ["harmonic-analysis", "exp(-x^2)"],
  ["linear-algebra", "[[1,2],[3,4]]"],
  ["measure-theory", ""],
  ["number-theory", "30"],
  ["numerical", "1,2,3"],
  ["probability", "1,2,3"],
  ["real-analysis", "1/n"],
  ["sequences", "1/n"],
];
/* 需要专门样本的模式（默认样本喂不出结果） */
// 样本表**不再各存一份**：这里原先复制了一份 227 条的 mode-samples 副本，结果两边漂移
// （`复数运算` 的值不同、`三角恒等式`/`组合恒等式` 只在一边）——正是 fixtures/mode-samples.mjs
// 当初要消灭的那种重复。现在直接引用共用 fixture，改一处两边都变。
const SAMPLE = MODE_SAMPLE;

const closeDialog = async () => {
  await evalJs(`document.querySelector('.dialog-close')?.click()`);
  await sleep(320);
};
const setBlock = (expr, mode) => evalJs(`(function(){
  const inp = document.querySelector('.cb-input');
  if (!inp) return 'no-input';
  if (inp.tagName === 'MATH-FIELD') inp.value = ${JSON.stringify("")};
  const sel = document.querySelector('.cb-mode');
  if (!sel) return 'no-select';
  if (![...sel.options].some(o => o.value === ${JSON.stringify(mode)})) return 'no-mode';
  const ssetter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;
  ssetter.call(sel, ${JSON.stringify(mode)});
  sel.dispatchEvent(new Event('change', { bubbles: true }));
  return 'ok';
})()`);

/** 输入框是 math-field：直接写 value 会被 LaTeX 解析器改写，
 *  所以把文本按引擎语法逐字转成 LaTeX 再塞进去（分号等按字面保留）。 */
const setInput = (text) => evalJs(`(function(){
  const inp = document.querySelector('.cb-input');
  if (!inp) return 'no-input';
  const t = ${JSON.stringify(text)};
  if (inp.tagName === 'MATH-FIELD') {
    // 用引擎的 to_engine_expr 反向不必要；直接给 LaTeX 字面量即可，
    // 逗号/分号/方括号在数学模式里都是普通字符。
    inp.value = t;
    inp.dispatchEvent(new Event('input', { bubbles: true }));
    return 'ok:' + inp.value;
  }
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(inp, t);
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  return 'ok';
})()`);

/** 弹窗（多参数）里按默认值确认 */
const confirmVarDialog = async () => {
  const has = await evalJs(`!!document.querySelector('.mvar-label')`);
  if (!has) return false;
  await evalJs(`(function(){
    const ok = [...document.querySelectorAll('.dialog .btn-primary')].find(b => b.textContent.trim() === '计算');
    if (ok) ok.click(); return 'ok';
  })()`);
  await sleep(1200);
  return true;
};
const readResult = () => evalJs(`(function(){
  const dlg = document.querySelector('.dialog');
  if (!dlg) return { none: true };
  const res = dlg.querySelector('.dialog-result');
  if (!res) return { askParams: true };            // 这是多参数弹窗，还没有结果
  return { text: String(res.textContent || '').trim().slice(0, 160),
           isError: !!dlg.querySelector('.rv-error') };
})()`);

let total = 0;
for (const [view, defaultSample] of VIEWS) {
  await evalJs(`location.hash = '#/calc/${view}'`);
  await sleep(1500);
  const modes = await evalJs(`(function(){
    const sel = document.querySelector('.cb-mode');
    return sel ? [...sel.options].map(o => o.value) : [];
  })()`);
  if (!Array.isArray(modes) || !modes.length) { check(`${view} 视图有模式`, false, String(modes)); continue; }
  console.log(`\n── ${view}（${modes.length} 个模式）──`);
  for (const mode of modes) {
    total++;
    // 上一轮如果留下弹窗，先关掉，否则后面的模式点不动（第一版就卡在这里超时）
    await evalJs(`document.querySelector('.dialog-close')?.click()`);
    await sleep(120);
    const sample = Object.prototype.hasOwnProperty.call(SAMPLE, mode) ? SAMPLE[mode] : defaultSample;
    const set = await setBlock(sample, mode);
    let set2 = set;
    if (set !== "ok") {
      await setInput(sample);
      set2 = await setBlock("", mode);
    } else {
      await setInput(sample);
    }
    /* ⚠ 模式没切成功时必须**显式记录**：以前这里只看返回值、不判成败，于是模式切换失败时
     * 用例会拿**上一个模式**去算，却仍然按本模式的标签记录结果 —— 报告里就会出现
     * "某个模式报了个跟它不相干的错"，极难定位（乘积测度那条"值不是数字"就是这么来的：
     * 它单独跑是好的 → 结果 "2"）。 */
    if (set2 !== "ok") {
      check(`${view} · ${mode}`, false, `模式没切成功（${set2}）—— 结果不可信`);
      continue;
    }
    await sleep(200);
    await evalJs(`document.querySelector('.cb-calc')?.click()`);
    await sleep(650);
    let r = await readResult();
    if (r && r.askParams) {           // 多参数弹窗：用默认值点「计算」
      await confirmVarDialog();
      r = await readResult();
    }
    const hasText = r && typeof r.text === "string" && r.text.length > 0;
    const ok = !!r && !r.none && !r.isError && hasText;
    const detail = !r || r.none ? "无结果对话框"
                 : r.askParams ? "多参数弹窗未返回结果"
                 : r.isError ? "错误：" + r.text
                 : hasText ? "" : "结果为空";
    check(`${view} · ${mode}`, ok, detail);
    if (r && !r.none) await closeDialog();
  }
}

console.log(`\n═══ 全模式点算覆盖：${pass} 通过 / ${fail} 失败（共 ${total} 个模式）═══`);
if (failures.length) {
  console.log("失败清单：");
  for (const f of failures) console.log(`  - ${f.label}   ${f.detail}`);
}

/**
 * 已知失败基线（每一条都要写清原因）。
 *
 * 这个用例是"每个视图 × 每个模式都点一遍计算"，之前**没有被登记进 run-all**，
 * 所以下面这些问题是它第一次跑就暴露出来的既有缺陷，不是某次改动引入的。
 * 之所以做成"允许清单"而不是放宽断言：一旦有人修好其中一条，它会被下面的
 * "过时条目"检查报出来，逼着把这条从清单里删掉；而**新出现**的失败仍然会让用例变红。
 *
 * 三类原因（都是真的，别当成"测试太严"）：
 *   ① 关键词字段被当表达式归一化：主输入框是 MathLive，emit 时会把整串（含 `;` 后的
 *      关键词段）交给引擎的 to_engine_expr 归一化，而它会把未知的多字母标识符拆成
 *      变量乘积 —— `central` → `c*e*n*t*r*a*l`、`circle(0,2)` → `c*i*r*c*l*e*(0,2)`。
 *      走多参数弹窗（纯 <input>）时不受影响，所以这些模式的**弹窗路径是好的**，
 *      只有"用 `;` 把关键词写进主输入框"这条便利路径走不通。
 *   ② 结果没有对话框：这些模式算完了但界面不弹结果（拓扑/测度论的部分模式），
 *      属于界面缺口而不是引擎问题。
 *   ③ 个别模式的参数/期望本身有问题（缺数组参数、条件概率表解析、极限的语义期望）。
 */
const KNOWN_FAIL = {
  /* ★ 现已为空：这个用例的**全部 10 处**已知失败都已修好，不再需要允许清单。
   *
   * 它们此前被归成三类"无法修复"的原因，逐条查下来**三类都有别的真因**：
   *
   * ① 「关键词被归一化」（Cauchy积分/围道积分/数值求导/最优步长/p值/复数运算）
   *    真因在 **MathField.vue → lib/plot/prepare.js 的 toEngineExpr**：它把**整串**
   *    （含 `;` 之后的关键词段）交给引擎的 to_engine_expr 补隐式乘号，于是
   *    "x^2; 1; 1e-6; central" 变成 "…; c*e*n*t*r*a*l"。现在只归一化第一段
   *    （表达式），后面的参数段原样透传 —— 6 条一起通过。
   *    另：「复数运算」是**样本写错**（本文件以前自带的副本里写的是 "1,1"），
   *    改用共用 fixture 的 "1+2i" 后通过。
   *
   * ② 「结果没有对话框（界面缺口）」（代数拓扑 7 + 测度论 2）是**误判**：
   *    这两个视图的默认样本是空串 → 前端如实提示"请输入表达式" → 当然不弹框。
   *    它们没有参数弹窗，参数本来就写在输入框里（已补样本）。
   *
   * ③ 「参数构造问题」（条件期望/全概率公式/贝叶斯公式/单侧极限）：随
   *    CalcView 的 modeNeedsInput 修复（有弹窗的模式不再要求输入框非空）
   *    与 buildEngineArgsFromValues 的**字段错位**修复一起通过 —— 那两处
   *    会让弹窗字段整体错位一格，参数自然构造不出来。
   *
   * 保留这个空对象是为了机制：将来若确有修不动的失败，按 "视图 · 模式": "原因" 登记；
   * 自检会双向校验 —— 没登记的失败让用例变红，登记了却能过的报"过时条目"。
   */
};

const knownLabels = new Set(Object.keys(KNOWN_FAIL));
const unexpected = failures.filter((f) => !knownLabels.has(f.label));
const stale = [...knownLabels].filter((l) => !failures.some((f) => f.label === l));
if (stale.length) {
  console.log("过时条目（已经能过了，请从 KNOWN_FAIL 里删掉）：");
  for (const l of stale) console.log(`  - ${l}   （${KNOWN_FAIL[l]}）`);
}

console.log(`\n已知失败 ${failures.length - unexpected.length} 处（见上，均有原因）`
  + `，非预期失败 ${unexpected.length} 处，过时条目 ${stale.length} 处`);
console.log(`RESULT|engine-coverage|${pass}|${unexpected.length + stale.length}`);
ws.close();
process.exit(unexpected.length + stale.length === 0 ? 0 : 1);
