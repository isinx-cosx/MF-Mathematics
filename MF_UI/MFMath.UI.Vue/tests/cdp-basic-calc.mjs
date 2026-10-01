// 基础运算（计算器）验证：按键 → 引擎求值 → 结果
//
// 旧版这一页是空壳（30 键，`=` 只弹"计算功能待接入引擎"）。这一版必须真的算：
// 每次求值都走引擎 expr_eval，界面只拼表达式。
// 用法: node cdp-basic-calc.mjs
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
await send("Runtime.enable");
await sleep(1500);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

/** 按一个键（用 data-key 定位，不依赖位置） */
const press = async (k) => {
  const r = await evalJs(`(function(){
    const b = document.querySelector('.keypad .key[data-key=' + JSON.stringify(${JSON.stringify(k)}) + ']');
    if (!b) return 'no-key';
    b.click(); return 'ok';
  })()`);
  await sleep(120);
  return r;
};
const readLcd = () => evalJs(`(function(){
  const lcd = document.querySelector('.lcd');
  if (!lcd) return null;
  return {
    expr: (lcd.querySelector('.lcd-expr') || {}).textContent || '',
    result: (lcd.querySelector('.lcd-result') || {}).textContent || '',
    note: (document.querySelector('.calc-note') || {}).textContent || '',
    keys: document.querySelectorAll('.keypad .key').length,
    history: document.querySelectorAll('.calc-history-row').length,
  };
})()`);
const clear = async () => { await press("C"); await sleep(150); };
const typeKeys = async (seq) => { for (const k of seq) await press(k); };

/** 走一遍按键并求值 */
async function calc(seq) {
  await clear();
  await typeKeys(seq);
  await press("=");
  await sleep(700);
  return await readLcd();
}

console.log("── 基础运算（计算器）──");
// 先回首页再进来：多次运行共用同一个宿主，直接跳同路由不会重新挂载，
// 上一次的状态（LCD 内容、历史）会留下来，导致"初始显示 0"这类断言假失败。
await evalJs("location.hash = '#/'");
await sleep(700);
await evalJs("location.hash = '#/calc/basic'");
await sleep(1600);

let st = await readLcd();
console.log("   初始:", JSON.stringify(st));
check("这一页不再是占位视图", st !== null && !/占位|开发中/.test(String(st.note)), JSON.stringify(st));
check("键盘有 30 个键（沿用旧版布局）", st && st.keys === 30, st ? String(st.keys) : "");
check("初始显示 0", st && st.result === "0", st ? st.result : "");

console.log("\n── 四则运算经引擎求值 ──");
let r = await calc(["2", "×", "(", "3", "+", "4", ")"]);
console.log("   2×(3+4) =", r.result, "| 引擎理解为:", r.note.trim());
check("2×(3+4) = 14", r.result === "14", r.result);
// 求值后表达式行会追加 " ="（原版 calculator.py:235 就是这样），所以先去掉尾巴再比
check("显示课本写法（× 而不是 *）", r.expr.replace(/\s*=$/, "") === "2×(3+4)", r.expr);
check("求值后表达式行追加了「 =」", /=\s*$/.test(r.expr), r.expr);
check("给出「引擎理解为 2*(3+4)」", /2\*\(3\+4\)/.test(r.note), r.note.trim());

r = await calc(["2", "0", "÷", "6"]);
check("20÷6 = 3.3333333333（10 位有效）", /^3\.333333333/.test(r.result), r.result);

r = await calc(["2", "−", "5"]);
check("2−5 = -3", r.result === "-3", r.result);
r = await calc(["5", "−", "2"]);
check("5−2 = 3", r.result === "3", r.result);

console.log("\n── 幂 / 根 / 阶乘 / 倒数 ──");
r = await calc(["2", "xʸ", "1", "0"]);
check("2^10 = 1024", r.result === "1024", r.result);

r = await calc(["3", "x²"]);
check("3² = 9", r.result === "9", r.result);

r = await calc(["√", "9", ")"]);
check("√(9) = 3", r.result === "3", r.result + " | " + r.expr);

r = await calc(["5", "n!"]);
check("5! = 120（引擎新增的阶乘支持）", r.result === "120", r.result);

r = await calc(["2", "1/x"]);
check("1/(2) = 0.5", r.result === "0.5", r.result);

r = await calc(["π"]);
check("π = 3.1415926536", /^3\.141592653/.test(r.result), r.result);

r = await calc(["e"]);
check("e = 2.7182818285", /^2\.718281828/.test(r.result), r.result);

r = await calc(["ln", "e", ")"]);
check("ln(e) = 1", r.result === "1", r.result);

r = await calc(["log", "1", "0", "0", ")"]);
check("log10(100) = 2", r.result === "2", r.result);

r = await calc(["±"]);
r = await calc(["3", "±"]);
check("± 取反 → -3", r.result === "-3", r.result);

console.log("\n── 错误处理（不静默）──");
r = await calc(["1", "÷", "0"]);
console.log("   1÷0 →", JSON.stringify(r.note.trim()), "| 结果行:", r.result);
check("除以零给出明确错误而不是崩溃/空", /错误|除以|无穷|未定义/.test(r.note + r.result), r.note.trim());
check("出错时结果行不冒充数字", r.result !== "0" && r.result !== "inf", r.result);

r = await calc(["√", "(", ")"]);
check("残缺表达式给出错误提示", /错误|无法|多余|缺少/.test(r.note + r.result), r.note.trim());

console.log("\n── 退格 / 清空 / 历史 ──");
await clear();
await typeKeys(["1", "2", "3"]);
await press("⌫");
st = await readLcd();
check("退格删掉最后一位", st.expr === "12", st.expr);
await clear();
st = await readLcd();
check("C 清空", st.expr === "0" || st.expr === "", JSON.stringify(st.expr));

r = await calc(["7", "×", "6"]);
check("7×6 = 42 并进入历史", r.result === "42" && r.history >= 1, r.result + " / 历史 " + r.history + " 条");
const reuse = await evalJs(`(function(){
  const row = document.querySelector('.calc-history-row');
  if (!row) return 'no-row';
  row.click(); return document.querySelector('.lcd-expr').textContent;
})()`);
await sleep(200);
check("点击历史可回填表达式", String(reuse).includes("7"), String(reuse));

console.log("\n── 键盘输入 ──");
await clear();
for (const k of ["8", "*", "7", "+", "1"]) {
  await send("Input.dispatchKeyEvent", { type: "keyDown", key: k, text: k });
  await send("Input.dispatchKeyEvent", { type: "keyUp", key: k });
  await sleep(80);
}
st = await readLcd();
check("键盘输入进表达式（8×7+1）", /8×7\+1/.test(st.expr), st.expr);
await send("Input.dispatchKeyEvent", { type: "keyDown", key: "Enter", text: "\r" });
await send("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter" });
await sleep(700);
st = await readLcd();
check("回车求值 = 57", st.result === "57", st.result);

await send("Input.dispatchKeyEvent", { type: "keyDown", key: "Backspace" });
await send("Input.dispatchKeyEvent", { type: "keyUp", key: "Backspace" });
await sleep(200);
check("Backspace 能退格", (await readLcd()).expr.length < st.expr.length, "");

/* ══════════ 大号 LCD 行 = 当前操作数（原版 _current）══════════
 *
 * 原版 calculator.py:156-184：打数字累加、按运算符/函数显示那个符号、= 后显示结果。
 * 之前这一行直接绑 result，而 result 只在求值时才写 → 按 7 + 8 全程显示 0，
 * 用户看不到自己正在输入什么。 */
console.log("\n── 大号行跟随输入（原版语义）──");
await clear();
let lcd = await readLcd();
check("初始大号行是 0", lcd.result.trim() === "0", lcd.result);
await press("7");
lcd = await readLcd();
check("按 7 后大号行显示 7", lcd.result.trim() === "7", lcd.result);
await press("+");
lcd = await readLcd();
check("按 + 后大号行显示运算符", lcd.result.trim() === "+", lcd.result);
await press("8");
lcd = await readLcd();
check("按 8 后大号行显示 8（不是 0）", lcd.result.trim() === "8", lcd.result);
await press("=");
lcd = await readLcd();
check("按 = 后大号行显示结果 15", lcd.result.trim() === "15", lcd.result);
check("按 = 后表达式行追加「 =」", /=\s*$/.test(lcd.expr), lcd.expr);

/* ══════════ 自动补右括号（原版 calculator.py:226-227）══════════
 * √ 和 ( 这两个键只输入左括号，不补的话按了 √ 再按 9 就报「缺少右括号」，等于用不了。 */
console.log("\n── 自动补右括号 ──");
await clear();
await typeKeys(["√", "9"]);
lcd = await readLcd();
check("按 √ 9 时表达式还没有右括号", /√\(9$/.test(lcd.expr.replace(/\s*=$/, "")), lcd.expr);
await press("=");
lcd = await readLcd();
check("求值时自动补齐右括号 = 3", lcd.result.trim() === "3", `${lcd.result} | ${lcd.expr}`);

await clear();
await typeKeys(["(", "2", "+", "3"]);
await press("=");
lcd = await readLcd();
check("裸左括号 (2+3 也能算出 5", lcd.result.trim() === "5", `${lcd.result} | ${lcd.expr}`);

/* ══════════ 精度与整数显示（原版 _fmt_result）══════════
 * 原版：12 位小数去尾零；整数直接 str()（所以 20! 显示完整整数）；
 * 之前这里是 10 位、且 ≥1e12 一律转科学计数法 → 20! 显示 2.432902e+18。 */
console.log("\n── 精度与整数显示 ──");
await clear();
await typeKeys(["1", "÷", "3"]);
await press("=");
lcd = await readLcd();
check("1/3 保留 12 位小数", lcd.result.trim() === "0.333333333333", lcd.result);

await clear();
await typeKeys(["2", "0", "n!", "="]);
lcd = await readLcd();
console.log("   20! =", lcd.result.trim());
check("20! 显示完整整数（不是科学计数法）",
  lcd.result.trim() === "2432902008176640000", lcd.result);

console.log(`\n═══ 基础运算验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|cdp-basic-calc|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
