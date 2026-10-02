// 计算历史 + 顶栏「搜索」占位的端到端验证（在真实宿主窗口里跑）
//
// 覆盖的是"这两个按钮以前点了没反应"这件事，以及历史功能的关键性质：
//   · 算一次 → 顶栏「历史」里能看到这条（模式、表达式、结果摘要都在）
//   · 历史面板能搜、能点回填（回到原页面并填入表达式）、能清空（带二次确认）
//   · 历史**真的落盘**：sys.StoreList() 里能看到 history 文件
//   · 顶栏「搜索」打开的是说明面板（不再是死按钮），且能跳到设置里的搜索分组
// 用法: node cdp-history-search.mjs   （宿主需带 --remote-debugging-port=9222 启动）
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
/** 点顶栏按钮（按文字找，避免依赖按钮顺序） */
const clickTop = (text) => evalJs(`(() => {
  const box = document.querySelector('.topbar-actions');
  if (!box) return false;
  for (const b of box.querySelectorAll('button')) {
    if ((b.textContent || '').trim() === ${JSON.stringify(text)}) { b.click(); return true; }
  }
  return false;
})()`);

console.log("=== 先算一次，制造一条历史 ===");

await evalJs(`location.hash = "/calc/algebra"; true`);
await sleep(600);
await waitTrue(`!!document.querySelector('math-field.cb-input')`);
await evalJs(`(() => {
  const sel = document.querySelector('select.cb-mode');
  if (sel) { sel.value = '解方程/组'; sel.dispatchEvent(new Event('change', { bubbles: true })); }
  const f = document.querySelector('math-field.cb-input');
  if (f) f.value = "x^2-5*x+6";
  return true;
})()`);
await sleep(320);   // MathLive 的 value setter 异步生效，见 cdp-engine-solve.mjs 的说明
await evalJs(`(() => {
  const f = document.querySelector('math-field.cb-input');
  if (f) f.dispatchEvent(new Event('input', { bubbles: true }));
  const b = document.querySelector('.cb-calc');
  if (b) b.click();
  return true;
})()`);
await sleep(700);
await evalJs(`(() => {
  for (const b of document.querySelectorAll('button')) if ((b.textContent || '').trim() === '计算') { b.click(); return true; }
  return false;
})()`);
await sleep(1500);
const dlg = await evalJs(`(() => { const d = document.querySelector('.dialog'); return d ? d.textContent.replace(/\\s+/g, ' ').slice(0, 200) : ''; })()`);
check("这次计算确实算出了结果", /解集|精确形式/.test(String(dlg)), String(dlg).slice(0, 70));
await evalJs(`(() => {
  for (const b of document.querySelectorAll('button')) if ((b.textContent || '').trim() === '关闭') { b.click(); return true; }
  return false;
})()`);
await sleep(300);

console.log("=== 顶栏「历史」不再是死按钮 ===");

check("顶栏「历史」按钮可点", (await clickTop("历史")) === true);
check("打开了历史面板", await waitTrue(`!!document.querySelector('.hist-dialog')`));

const rowCount = await evalJs(`document.querySelectorAll('.hist-dialog .hist-row').length`);
check("面板里有记录", rowCount >= 1, `${rowCount} 条`);

const firstRow = await evalJs(`(() => {
  const r = document.querySelector('.hist-dialog .hist-row');
  return r ? r.textContent.replace(/\\s+/g, ' ').trim().slice(0, 160) : '';
})()`);
check("最新的那条就是刚算的（含模式与表达式）",
  /解方程\/组/.test(String(firstRow)) && /x\^2-5\*x\+6/.test(String(firstRow)), String(firstRow).slice(0, 90));
check("带上了结果摘要（不是只有表达式）",
  /解集|判别式|实根性|精确形式/.test(String(firstRow)), String(firstRow).slice(0, 90));

console.log("=== 搜索过滤 ===");
await evalJs(`(() => {
  const s = document.querySelector('.hist-dialog .hist-search');
  if (!s) return false;
  s.value = 'x^2-5*x+6';
  s.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await sleep(320);
const filtered = await evalJs(`document.querySelectorAll('.hist-dialog .hist-row').length`);
check("按表达式过滤生效", filtered >= 1 && filtered < rowCount + 1, `过滤后 ${filtered} 条（过滤前 ${rowCount}）`);

await evalJs(`(() => {
  const s = document.querySelector('.hist-dialog .hist-search');
  if (!s) return false;
  s.value = '这条肯定搜不到 zzz';
  s.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await sleep(320);
const noneHit = await evalJs(`document.querySelectorAll('.hist-dialog .hist-row').length`);
check("搜不到时给空状态而不是空白", noneHit === 0 && (await evalJs(`!!document.querySelector('.hist-dialog .hist-empty')`)) === true, `${noneHit} 条`);

console.log("=== 点一条 → 回到原页面并回填 ===");
await evalJs(`(() => {
  const s = document.querySelector('.hist-dialog .hist-search');
  if (!s) return false;
  s.value = '';
  s.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await sleep(300);
// 先离开代数页，才能看出"回填是跨页面发生的"
await evalJs(`location.hash = "/"; true`);
await sleep(500);
await clickTop("历史");
await waitTrue(`!!document.querySelector('.hist-dialog')`);
await evalJs(`(() => { const b = document.querySelector('.hist-dialog .hist-main'); if (b) b.click(); return true; })()`);
await sleep(900);
const afterHash = String(await evalJs(`location.hash`));
check("回填把页面带回原路由", afterHash.includes("/calc/algebra"), afterHash);
const filled = await evalJs(`(() => { const f = document.querySelector('math-field.cb-input'); return f ? String(f.value || '') : ''; })()`);
check("表达式已填回输入框", /x\^2|-5/.test(String(filled)), String(filled).slice(0, 40));

console.log("=== 清空要二次确认（这里只确认弹了确认，不真的清）===");
await clickTop("历史");
await waitTrue(`!!document.querySelector('.hist-dialog')`);
const beforeClear = await evalJs(`document.querySelectorAll('.hist-dialog .hist-row').length`);
await evalJs(`(() => {
  for (const b of document.querySelectorAll('.hist-dialog .dialog-footer button')) {
    if ((b.textContent || '').trim() === '清空全部') { b.click(); return true; }
  }
  return false;
})()`);
await sleep(250);
const hasConfirm = await evalJs(`!!document.querySelector('.hist-dialog .hist-warn')`);
check("点清空先要确认", hasConfirm === true);
const stillThere = await evalJs(`document.querySelectorAll('.hist-dialog .hist-row').length`);
check("确认之前一条都没删", stillThere === beforeClear, `${stillThere} / ${beforeClear}`);
await evalJs(`(() => {
  for (const b of document.querySelectorAll('.hist-dialog .dialog-footer button')) {
    if ((b.textContent || '').trim() === '取消') { b.click(); return true; }
  }
  return false;
})()`);
await sleep(200);
await evalJs(`(() => {
  for (const b of document.querySelectorAll('.hist-dialog button')) if ((b.textContent || '').trim() === '关闭') { b.click(); return true; }
  return false;
})()`);
await sleep(250);

console.log("=== 历史真的落盘（不是只在内存里）===");
const storeRaw = await evalJs(`window.chrome.webview.hostObjects.sync.sys.StoreList()`);
const names = (() => { try { return JSON.parse(storeRaw).map((f) => f.name); } catch { return []; } })();
check("数据目录里存在 history 文件", names.includes("history"), names.join(", ") || "（空）");
const stored = await evalJs(`window.chrome.webview.hostObjects.sync.sys.StoreRead("history")`);
const storedOk = (() => {
  try { const d = JSON.parse(JSON.parse(stored).json); return Array.isArray(d.entries) && d.entries.length > 0; }
  catch { return false; }
})();
check("history 文件里有条目（跨会话保留的依据）", storedOk === true);

console.log("=== 顶栏「搜索」是说明面板，不是死按钮 ===");
check("顶栏「搜索」按钮可点", (await clickTop("搜索")) === true);
check("打开了搜索占位面板", await waitTrue(`!!document.querySelector('.sp-dialog')`));
const spText = await evalJs(`(() => { const d = document.querySelector('.sp-dialog'); return d ? d.textContent.replace(/\\s+/g, ' ') : ''; })()`);
check("面板明确说明「尚未接入」（不装作有搜索）",
  /尚未接入/.test(String(spText)) && /DuckDuckGo|Wolfram/.test(String(spText)), String(spText).slice(0, 80));
check("面板里没有假装能用的搜索框", (await evalJs(`document.querySelectorAll('.sp-dialog input').length`)) === 0);

await evalJs(`(() => {
  for (const b of document.querySelectorAll('.sp-dialog .dialog-footer button')) {
    if ((b.textContent || '').includes('看设置里的搜索项')) { b.click(); return true; }
  }
  return false;
})()`);
await sleep(700);
const setHash = String(await evalJs(`location.hash`));
check("能跳到设置里的搜索分组", setHash.includes("/settings") && setHash.includes("group=search"), setHash);
const activeGroup = await evalJs(`(() => {
  const el = document.querySelector('.set-nav li.on');
  return el ? el.textContent.replace(/\\s+/g, ' ').trim() : '';
})()`);
check("设置页停在「搜索」分组上", /搜索/.test(String(activeGroup)), String(activeGroup).slice(0, 40));

console.log(`RESULT|cdp-history-search|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
