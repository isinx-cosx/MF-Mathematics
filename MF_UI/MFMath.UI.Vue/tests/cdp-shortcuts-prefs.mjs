// 全局快捷键 + 两个设置项（数值精度 / 绘图默认范围）端到端验证
//
// 要证明的：
//   ① F1 跳到教程页，而且**不弹任何窗口**（用户明确要求：不要弹窗）
//   ② 计算页 Ctrl+Z / Ctrl+Y 真的撤销/重做计算块，界面上的两个按钮同步禁用状态
//   ③ **焦点在输入框里时不抢 Ctrl+Z**（MathLive/CodeMirror 有自己的撤销栈，
//      抢了就会出现"打字撤销不了、反而把整块还原了"）
//   ④ 数值精度改了就生效（结果里的位数变），默认 12 位不变
//   ⑤ 绘图默认范围改了就影响**新打开**的绘图页；非法范围退回自动并在行内说明
//   ⑥ 全程没有任何模态窗口（.dialog-overlay / alert）
//
// 用法: node cdp-shortcuts-prefs.mjs   （宿主需带 --remote-debugging-port=9222 启动）
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

// 页面里弹过 alert 就记下来（并自动关掉，免得测试卡住）
await evalJs(`(() => {
  window.__alerted = [];
  const orig = window.alert;
  window.alert = (m) => { window.__alerted.push(String(m)); };
  window.__origAlert = orig;
  return true;
})()`);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};
async function waitTrue(expr, timeoutMs = 8000, stepMs = 120) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    if ((await evalJs(expr)) === true) return true;
    await sleep(stepMs);
  }
  return false;
}
const goto = async (hash) => { await evalJs(`location.hash = ${JSON.stringify(hash)}; true`); await sleep(800); };
/** 没有模态窗口 / 没有 alert */
const noModal = async () => {
  const m = await evalJs(`document.querySelectorAll('.dialog-overlay').length`);
  const a = await evalJs(`(window.__alerted || []).length`);
  return m === 0 && a === 0;
};

console.log("=== ① F1 打开教程页（只跳路由，不弹窗）===");
await goto("/calc/algebra");
await evalJs(`document.body.focus(); true`);
await evalJs(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'F1', bubbles: true })); true`);
await evalJs(`window.dispatchEvent(new KeyboardEvent('keydown', { key: 'F1', bubbles: true })); true`);
const onTutorial = await waitTrue(`location.hash.includes("/tutorial")`, 4000);
check("F1 跳到教程页", onTutorial === true, String(await evalJs(`location.hash`)));
check("F1 没有弹任何窗口", await noModal());

console.log("=== ② 计算页 Ctrl+Z / Ctrl+Y ===");
await goto("/calc/algebra");
await waitTrue(`!!document.querySelector('math-field.cb-input')`);
// 造两步改动：填表达式 → 再加一个计算块
await evalJs(`(() => {
  const f = document.querySelector('math-field.cb-input');
  if (f) f.value = "x^2-9";
  return true;
})()`);
await sleep(320);
await evalJs(`(() => {
  const f = document.querySelector('math-field.cb-input');
  if (f) f.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await sleep(400);
await evalJs(`(() => {
  const add = [...document.querySelectorAll('button')].find((b) => (b.textContent || '').includes('添加计算'));
  if (add) add.click();
  return true;
})()`);
await sleep(400);
const before = await evalJs(`document.querySelectorAll('math-field.cb-input').length`);
check("准备状态：2 个计算块", before === 2, `${before} 个`);

const undoVia = (key, shift = false) => evalJs(`(() => {
  document.body.focus();
  window.dispatchEvent(new KeyboardEvent('keydown', { key: ${JSON.stringify(key)}, ctrlKey: true, shiftKey: ${shift}, bubbles: true, cancelable: true }));
  return true;
})()`);

await undoVia("z");
await sleep(500);
const afterUndo = await evalJs(`document.querySelectorAll('math-field.cb-input').length`);
check("Ctrl+Z 撤掉了刚加的那个块", afterUndo === 1, `${afterUndo} 个`);
await undoVia("y");
await sleep(500);
const afterRedo = await evalJs(`document.querySelectorAll('math-field.cb-input').length`);
check("Ctrl+Y 把它重做回来", afterRedo === 2, `${afterRedo} 个`);
await undoVia("z");
await sleep(400);
await undoVia("z");
await sleep(500);
const exprBack = await evalJs(`(() => { const f = document.querySelector('math-field.cb-input'); return f ? String(f.value) : ''; })()`);
check("继续撤销能退回到刚进页面时的（空表达式）状态", !/x\^2-9/.test(String(exprBack)), String(exprBack).slice(0, 30));
check("撤销/重做期间没有弹窗", await noModal());

const btnState = await evalJs(`(() => {
  const u = document.querySelector('.cb-undo'), r = document.querySelector('.cb-redo');
  return u && r ? { undoDisabled: u.disabled, redoDisabled: r.disabled } : null;
})()`);
check("撤销/重做按钮存在且禁用状态正确（还有可重做的）",
  !!btnState && btnState.redoDisabled === false, JSON.stringify(btnState));
const undoTip = await evalJs(`(document.querySelector('.cb-undo') || {}).title || ''`);
check("按钮上写明了快捷键（可发现）", /Ctrl\+Z/.test(String(undoTip)), String(undoTip));

console.log("=== ③ 输入框里不抢 Ctrl+Z ===");
const blocksBefore = await evalJs(`document.querySelectorAll('math-field.cb-input').length`);
await evalJs(`(() => {
  const f = document.querySelector('math-field.cb-input');
  if (f) { f.focus(); f.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', ctrlKey: true, bubbles: true, cancelable: true })); }
  return true;
})()`);
await sleep(500);
const blocksAfter = await evalJs(`document.querySelectorAll('math-field.cb-input').length`);
check("焦点在输入框里时，Ctrl+Z 不会去撤销整块（留给输入法/编辑器）",
  blocksAfter === blocksBefore, `${blocksBefore} → ${blocksAfter}`);

console.log("=== ④ 数值精度改了就生效 ===");
/** 按基础运算页的真实键盘算一个式子（先按 C 清干净，免得上一题拼进来） */
async function pressKeys(labels) {
  for (const label of ["C", ...labels]) {
    await evalJs(`(() => {
      const b = document.querySelector('.keypad .key[data-key=' + JSON.stringify(${JSON.stringify(label)}) + ']')
             || [...document.querySelectorAll('.keypad .key')].find((x) => (x.textContent || '').trim() === ${JSON.stringify(label)});
      if (b) b.click();
      return true;
    })()`);
    await sleep(180);
  }
  await sleep(600);
  return String(await evalJs(`(document.querySelector('.lcd-result') || {}).textContent || ''`)).trim();
}
await goto("/calc/basic");
await waitTrue(`!!document.querySelector('.keypad .key')`);
const oneThird12 = await pressKeys(["1", "÷", "3", "="]);
check("默认 12 位小数（与旧版一致）", oneThird12 === "0.333333333333", oneThird12);

await goto("/settings?group=calc");
await waitTrue(`!!document.querySelector('[data-setting="calc.precision"]')`);
const setDecimals = (n) => evalJs(`(() => {
  const inp = document.querySelector('[data-setting="calc.precision"] input[type=number]');
  if (!inp) return false;
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(inp, ${JSON.stringify(String(n))});
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
check("设置里有「数值精度」输入框", (await setDecimals(4)) === true);
await sleep(400);
const rowText = await evalJs(`(() => { const el = document.querySelector('[data-setting="calc.precision"]'); return el ? el.textContent.replace(/\\s+/g, ' ') : ''; })()`);
check("行内当场显示示例（不弹窗也能看出效果）", /0\.3333[^3]/.test(String(rowText)), String(rowText).slice(0, 120));
const stored = await evalJs(`JSON.stringify(window.__mfPrefs.get())`);
check("精度已存进偏好（4 位）", /"decimals":4/.test(String(stored)), String(stored).slice(0, 80));

await goto("/calc/basic");
await waitTrue(`!!document.querySelector('.keypad .key')`);
const oneThird4 = await pressKeys(["1", "÷", "3", "="]);
check("改成 4 位后**真实计算结果**跟着变短", oneThird4 === "0.3333", `${oneThird12} → ${oneThird4}`);
const intResult = await pressKeys(["7", "×", "6", "="]);
check("整数不受精度影响", intResult === "42", intResult);

console.log("=== ④b 精度 = 0 不能吃掉整数位的零（回归）===");
await goto("/settings?group=calc");
await waitTrue(`!!document.querySelector('[data-setting="calc.precision"]')`);
await setDecimals(0);
await sleep(300);
await goto("/calc/basic");
await waitTrue(`!!document.querySelector('.keypad .key')`);
// 10.4 若按"无条件剥尾零"的老写法会显示成 1；-0.4 会显示成一个孤零零的负号
const tenPointFour = await pressKeys(["1", "0", ".", "4", "="]);
check("精度 0 时 10.4 显示 10（不是 1）", tenPointFour === "10", tenPointFour);
const negFraction = await pressKeys(["0", ".", "4", "±", "="]);
check("精度 0 时 -0.4 不会显示成一个负号", negFraction !== "-" && /^-?0$/.test(negFraction), negFraction);

// 还原成 12
await goto("/settings?group=calc");
await waitTrue(`!!document.querySelector('[data-setting="calc.precision"]')`);
await setDecimals(12);
await sleep(300);

console.log("=== ⑤ 绘图默认范围 ===");
const setRange = (xmin, xmax, ymin, ymax) => evalJs(`(() => {
  const row = document.querySelector('[data-setting="calc.plotRange"]');
  if (!row) return false;
  const inputs = [...row.querySelectorAll('input[type=number]')];
  if (inputs.length < 4) return false;
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  const vals = [${JSON.stringify(String(xmin))}, ${JSON.stringify(String(xmax))}, ${JSON.stringify(String(ymin))}, ${JSON.stringify(String(ymax))}];
  inputs.forEach((inp, i) => { setter.call(inp, vals[i]); inp.dispatchEvent(new Event('input', { bubbles: true })); });
  return true;
})()`);

// 非法在前：x 最大 < x 最小 → 行内说明 + 退回自动
await setRange(5, -5, -1, 1);
await sleep(400);
const invalidText = await evalJs(`(() => { const row = document.querySelector('[data-setting="calc.plotRange"]'); return row ? row.parentElement.textContent.replace(/\\s+/g, ' ') : ''; })()`);
check("非法范围在行内说明并退回自动（不弹窗）", /最小必须小于最大|按画布宽高比自动/.test(String(invalidText)), String(invalidText).slice(0, 110));

// 合法：x∈[-5,5]、y∈[-1,1]
await setRange(-5, 5, -1, 1);
await sleep(400);
const okText = await evalJs(`(() => { const row = document.querySelector('[data-setting="calc.plotRange"]'); return row ? row.parentElement.textContent.replace(/\\s+/g, ' ') : ''; })()`);
check("合法时明确写出当前范围", /固定 x∈\[-5, 5\]/.test(String(okText)), String(okText).slice(0, 110));

// 新开的绘图页应该用这个范围（从别的页面进，确保是"新打开"）
await goto("/");
await sleep(400);
await goto("/plot/2d");
await sleep(1500);
const plotView = JSON.parse(await evalJs(`JSON.stringify((window.__mfWorkspace.pages()["/plot/2d"] || {}).view || null)`));
check("新打开的绘图页用的就是配置的范围",
  !!plotView && Math.abs(plotView.x0 + 5) < 1e-9 && Math.abs(plotView.x1 - 5) < 1e-9
  && Math.abs(plotView.y0 + 1) < 1e-9 && Math.abs(plotView.y1 - 1) < 1e-9,
  JSON.stringify(plotView));

// 收尾：范围恢复默认（留空）
await goto("/settings?group=calc");
await waitTrue(`!!document.querySelector('[data-setting="calc.plotRange"]')`);
await evalJs(`(() => {
  const row = document.querySelector('[data-setting="calc.plotRange"]');
  for (const b of row.querySelectorAll('button')) if ((b.textContent || '').includes('恢复默认')) { b.click(); return true; }
  return false;
})()`);
await sleep(400);
const resetText = await evalJs(`(() => { const row = document.querySelector('[data-setting="calc.plotRange"]'); return row ? row.parentElement.textContent.replace(/\\s+/g, ' ') : ''; })()`);
check("「恢复默认」把范围退回自动", /按画布宽高比自动/.test(String(resetText)), String(resetText).slice(0, 90));
check("整段测试没有弹过任何窗口", await noModal());

console.log(`RESULT|cdp-shortcuts-prefs|${pass}|${fail}`);
try { ws.close(); } catch { /* 忽略 */ }
process.exit(fail === 0 ? 0 : 1);
