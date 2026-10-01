// 解方程（solve_sym）在真实界面里的端到端验证
//
// 为什么单独一个文件：这轮修的是引擎侧"超越方程拦截误伤 + 文案张冠李戴"，
// 引擎单测（准确性套件 2180 用例）只能证明算得对，证明不了**用户看得到**。
// 这里从界面输入 → 计算结果 → 弹窗内容走一遍，覆盖三类结局：
//   ① 三角方程 sin(x)-1/2 → 通解（generalSolution），且不再报"含超越函数"
//   ② 非有限但可分解 x*sin(x) → 给出可解因子 x=0，并附"只覆盖可因式分解部分"的说明
//   ③ 仍应拒绝的 sqrt(x)-2 → 报错文案必须**说清是根式**，不是笼统的"含超越函数"
// 另外用 x^2-5x+6 押一条回归：普通方程的解集显示不能被这轮改动带坏。
//
// 用法: node cdp-engine-solve.mjs   （宿主需带 --remote-debugging-port=9222 启动）
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
await sleep(800);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

async function waitTrue(expr, timeoutMs = 8000, stepMs = 120) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    const v = await evalJs(expr);
    if (v === true) return true;
    await sleep(stepMs);
  }
  return false;
}

const closeDialog = async () => {
  await evalJs(`(() => {
    for (const b of document.querySelectorAll('button')) {
      if ((b.textContent || '').trim() === '关闭') { b.click(); return true; }
    }
    return false;
  })()`);
  await sleep(250);
};

/**
 * 在代数页用「解方程/组」跑一条表达式，返回 { error, dialogText, rawJson }。
 * 输入用 MathLive 的 value + input 事件，与用户敲键盘走的是同一条 onInput 通路
 * （LaTeX → 引擎语法的转换是界面自己做的，不在这里绕过）。
 */
async function solve(expr) {
  await closeDialog();
  await evalJs(`location.hash = "/calc/algebra"; true`);
  await sleep(500);
  await waitTrue(`!!document.querySelector('math-field.cb-input')`);
  const ok = await evalJs(`(() => {
    const sel = document.querySelector('select.cb-mode');
    if (!sel) return 'no-select';
    sel.value = '解方程/组';
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    const f = document.querySelector('math-field.cb-input');
    if (!f) return 'no-input';
    f.value = ${JSON.stringify(expr)};
    return 'ok';
  })()`);
  if (ok !== "ok") return { error: `控件缺失: ${ok}`, dialogText: "", rawJson: "" };
  // MathLive 的 value setter 是异步生效的（内部排队处理）：紧接着读 mf.value 拿到的还是旧值，
  // 所以必须等一拍再派发 input 事件，否则界面读到空串 → 报"请输入表达式"。
  await sleep(300);
  const typed = await evalJs(`(() => {
    const f = document.querySelector('math-field.cb-input');
    if (!f) return '[无输入框]';
    f.dispatchEvent(new Event('input', { bubbles: true }));
    return String(f.value || '');
  })()`);
  if (!String(typed).trim()) return { error: `表达式没进输入框（value 为空）`, dialogText: "", rawJson: "" };
  await sleep(250);
  await evalJs(`(() => { const b = document.querySelector('.cb-calc'); if (b) b.click(); return true; })()`);
  await sleep(600);
  // 有的模式会先弹参数窗（解方程/组带 var 参数），确认后才真正计算
  await evalJs(`(() => {
    for (const b of document.querySelectorAll('button')) {
      if ((b.textContent || '').trim() === '计算') { b.click(); return true; }
    }
    return false;
  })()`);
  await sleep(1400);
  const error = await evalJs(`(document.querySelector('.cb-error') || {}).textContent || ''`);
  const dialogText = await evalJs(`(() => {
    const d = document.querySelector('.dialog');
    return d ? d.textContent.replace(/\\s+/g, ' ').slice(0, 400) : '';
  })()`);
  const rawJson = await evalJs(`(() => {
    for (const el of document.querySelectorAll('code, pre, textarea')) {
      const t = el.textContent || el.value || '';
      if (t.includes('isError') && t.length > 20) return t.slice(0, 2000);
    }
    return '';
  })()`);
  return { error: String(error), dialogText: String(dialogText), rawJson: String(rawJson) };
}

console.log("=== 解方程：三角方程应给通解（旧实现一律报「含超越函数」）===");

const r1 = await solve("sin(x)-1/2");
check("界面不再报「含超越函数」", !r1.error.includes("超越"), r1.error.trim().slice(0, 60) || "（无错误）");
// 字段名必须被翻成中文标签：直接显示 generalSolution 这种引擎键名等于没做界面
check("结果显示「通解」且不再露出引擎键名 generalSolution",
  r1.dialogText.includes("通解") && !r1.dialogText.includes("generalSolution"), r1.dialogText.slice(0, 140));
check("通解确实带整数参数 n（不是空壳）", /n\s*\*?\s*pi|\bn\b[^。]{0,12}pi/.test(r1.dialogText),
  (r1.dialogText.match(/通解[^参]{0,90}/) || [""])[0]);
check("附了「说明」解释为什么是无穷族", r1.dialogText.includes("说明") && r1.dialogText.includes("无穷族"),
  r1.dialogText.slice(0, 140));
// solutions 为空是"没有有限根"，与通解并排显示会像自相矛盾 —— 显示层必须把它收起来
check("不再同时显示「解集 =（空）」", !/解集[^ ]{0,4}（空）/.test(r1.dialogText), r1.dialogText.slice(0, 160));

console.log("=== 解方程：可因式分解但含超越因子（部分解 + 说明）===");

const r2 = await solve("x*sin(x)");
check("不再整条拒绝", !r2.error.includes("超越"), r2.error.trim().slice(0, 60) || "（无错误）");
check("解集给出可解因子 x=0", /解集/.test(r2.dialogText) && /\b0\b/.test(r2.dialogText), r2.dialogText.slice(0, 140));
check("说明里点明剩余因子需要数值方法",
  r2.dialogText.includes("说明") && /数值/.test(r2.dialogText), r2.dialogText.slice(0, 160));

console.log("=== 解方程：该拒绝的仍然拒绝，但文案必须说清原因 ===");

const r3 = await solve("sqrt(x)-2");
// 引擎报错时结果窗标题变成「错误」，正文是引擎原文（不再只是工作区那行 .cb-error）
check("根式方程仍被拒绝（不返回可能错的解集）", /错误/.test(r3.dialogText), r3.dialogText.slice(0, 90));
check("文案点明是「根式」而不是笼统的超越函数",
  r3.dialogText.includes("根式") && !r3.dialogText.includes("超越函数"), r3.dialogText.slice(0, 150));

console.log("=== 回归：普通方程的解集显示没被带坏 ===");

const r4 = await solve("x^2-5*x+6");
check("二次方程照常算出解集", !r4.error && r4.dialogText.includes("解集"), r4.dialogText.slice(0, 90));
check("两个根 2 与 3 都在", /\b2\b/.test(r4.dialogText) && /\b3\b/.test(r4.dialogText), r4.dialogText.slice(0, 90));
check("没有被误加上「通解」", !r4.dialogText.includes("通解"), r4.dialogText.slice(0, 90));

await closeDialog();

if (exceptions.length) {
  console.log(`  [WARN] 页面异常 ${exceptions.length} 条，首条：${exceptions[0].slice(0, 160)}`);
}

console.log(`RESULT|cdp-engine-solve|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
