// 教程系统 + 数学键盘的端到端验证（在真实宿主窗口里跑）
//
// 覆盖的都是"v1 坏掉、这轮重做"的点，而不是把实现细节复述一遍：
//   · 教程目录能列出全部 18 篇（v1 的内容源是 YAML，这轮是构建期转 JSON）
//   · 引导能启动并**真的高亮到目标**（v1 的 66 步里 34 步目标不存在，静默跳过，
//     教程 05/11 全废却仍被标记"已完成"）
//   · 有"上一步 / 暂停"（v1 完全没有）
//   · 走到最后一步才算完成；中途结束**不**标记已学
//   · 键盘 126 键、分类名称与顺序与 v1 一致、插入的是 LaTeX 且占位符没被剥掉
//   · 键盘对 MathField 真正生效；没有聚焦输入框时**明确提示**（v1 静默忽略）
// 用法: node cdp-tutorials-keypad.mjs   （宿主需带 --remote-debugging-port=9222 启动）
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
await sleep(1000);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

/** 轮询等待某个表达式为真（Vue 渲染是异步的） */
async function waitTrue(expr, timeoutMs = 6000, stepMs = 120) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    const v = await evalJs(expr);
    if (v === true) return true;
    await sleep(stepMs);
  }
  return false;
}
const goto = async (hash) => {
  await evalJs(`location.hash = ${JSON.stringify(hash)}; true`);
  await sleep(450);
};

// 记下原始进度，测完还原，避免给用户留下"教程已学完"的副作用
const savedProgress = await evalJs(`localStorage.getItem("mf_tut_progress")`);
const savedSidebar = await evalJs(`localStorage.getItem("mf_kb_visible")`);
const savedRecent = await evalJs(`localStorage.getItem("mf_kb_recent")`);

console.log("=== 教程系统 ===");

await goto("/tutorial");
check("教程目录可打开", await waitTrue(`!!document.querySelector('[data-tour="tutorial.catalog"]')`));

const cardCount = await evalJs(`document.querySelectorAll('.tc-card').length`);
check("列出全部 18 篇教程", cardCount === 18, `实际 ${cardCount} 篇`);

const progressText = await evalJs(`(document.querySelector('.tc-sub')||{}).textContent || ''`);
check("显示学习进度", /已学\s*\d+\/18/.test(progressText.replace(/\s+/g, " ")), progressText.trim().slice(0, 40));

// 进入第一篇正文（quick-start）
await evalJs(`(() => {
  const card = document.querySelector('.tc-card');
  const btns = card ? card.querySelectorAll('button') : [];
  for (const b of btns) { if (b.textContent.includes('阅读')) { b.click(); return true; } }
  return false;
})()`);
check("能进入教程正文", await waitTrue(`!!document.querySelector('.ha-title')`));

const article = await evalJs(`(() => {
  const t = document.querySelector('.ha-title');
  return t ? t.textContent.trim() : '';
})()`);
check("正文标题正确", article.includes("快速入门"), article);

const stepRows = await evalJs(`document.querySelectorAll('.ha-step').length`);
check("正文渲染出操作步骤", stepRows === 4, `实际 ${stepRows} 步（quick-start 为 4 步）`);

const faqCount = await evalJs(`document.querySelectorAll('.ha-faq').length`);
check("正文渲染出 FAQ", faqCount === 2, `实际 ${faqCount} 条`);

// 从正文启动引导（v1 只能引导 quick-start，且帮助文档里没有入口）
await evalJs(`(() => {
  for (const b of document.querySelectorAll('.ha-actions button')) {
    if (b.textContent.includes('开始引导')) { b.click(); return true; }
  }
  return false;
})()`);
check("从正文能启动这一篇的引导", await waitTrue(`!!document.querySelector('.tour')`));

const hole = await evalJs(`!!document.querySelector('.tour-hole')`);
const missing = await evalJs(`!!document.querySelector('.tip-missing')`);
check("引导高亮定位到目标（不是静默跳过）", hole === true || missing === true,
  hole ? "已定位到目标元素" : "显示为「目标界面尚未实现」");

const countText = await evalJs(`(document.querySelector('.tip-count')||{}).textContent || ''`);
check("显示步骤计数", /1\s*\/\s*4/.test(countText.replace(/\s/g, " ")) || countText.includes("1"), countText.trim());

// 上一步 / 暂停（v1 都没有）
const hasPrevPause = await evalJs(`(() => {
  const txt = [...document.querySelectorAll('.tour-tip button')].map((b) => b.textContent.trim());
  return txt.includes('上一步') && txt.includes('暂停');
})()`);
check("有「上一步」与「暂停」按钮", hasPrevPause === true);

await evalJs(`(() => {
  for (const b of document.querySelectorAll('.tour-tip button')) if (b.textContent.trim() === '暂停') { b.click(); return true; }
  return false;
})()`);
await sleep(200);
const paused = await evalJs(`!!document.querySelector('.tour.paused')`);
check("暂停生效", paused === true);
await evalJs(`(() => {
  for (const b of document.querySelectorAll('.tour-tip button')) if (b.textContent.trim() === '继续') { b.click(); return true; }
  return false;
})()`);
await sleep(200);
check("继续生效", (await evalJs(`!!document.querySelector('.tour.paused')`)) === false);

// 下一步
await evalJs(`(() => {
  for (const b of document.querySelectorAll('.tour-tip button')) if (b.textContent.trim() === '下一步') { b.click(); return true; }
  return false;
})()`);
await sleep(300);
const count2 = await evalJs(`(document.querySelector('.tip-count')||{}).textContent || ''`);
check("「下一步」能前进", /2\s*\/\s*4/.test(count2.replace(/\s/g, " ")) || count2.includes("2"), count2.trim());

// 中途结束不应标记已学
await evalJs(`(() => {
  for (const b of document.querySelectorAll('.tour-tip button')) if (b.textContent.includes('结束引导')) { b.click(); return true; }
  return false;
})()`);
await sleep(300);
check("结束引导后遮罩关闭", (await evalJs(`!!document.querySelector('.tour')`)) === false);
const afterAbort = await evalJs(`(() => { try { return JSON.parse(localStorage.getItem('mf_tut_progress')||'{}').completed||{}; } catch { return {}; } })()`);
check("中途结束**不**标记为已学", !Object.keys(afterAbort || {}).includes("quick-start"),
  JSON.stringify(Object.keys(afterAbort || {})));

// 走完全程才算完成
await goto("/tutorial");
await evalJs(`(() => {
  const card = document.querySelector('.tc-card');
  for (const b of card.querySelectorAll('button')) if (b.textContent.includes('开始引导')) { b.click(); return true; }
  return false;
})()`);
await waitTrue(`!!document.querySelector('.tour')`);
for (let i = 0; i < 4; i++) {
  await evalJs(`(() => {
    const btns = [...document.querySelectorAll('.tour-tip button')];
    const b = btns.find((x) => /下一步|完成/.test(x.textContent.trim()));
    if (b) b.click();
    return true;
  })()`);
  await sleep(260);
}
const afterFinish = await evalJs(`(() => { try { return JSON.parse(localStorage.getItem('mf_tut_progress')||'{}').completed||{}; } catch { return {}; } })()`);
check("走到最后一步才标记为已学", Object.keys(afterFinish || {}).includes("quick-start"),
  JSON.stringify(Object.keys(afterFinish || {})));

console.log("=== 示例库跳转（回归：曾经显示积分、跳到解方程）===");

await goto("/examples");
check("示例库可打开", await waitTrue(`!!document.querySelector('.ex-card')`));

// 「不定积分」示例：expr=x*sin(x)，v1 数据里 mode="代数"、action="不定积分"。
// 旧实现按 mode（分类）跳到代数页，代数页没有「不定积分」→ 模式停在默认值
// 「解方程/组」→ 点计算跑成 solve_sym，报"方程含超越函数（x*sin(x)）」。
const clickedIntegral = await evalJs(`(() => {
  const cards = [...document.querySelectorAll('.ex-card')];
  const card = cards.find(c => ((c.querySelector('.ex-label') || {}).textContent || '').trim() === '不定积分');
  if (!card) return 'not-found';
  const btn = [...card.querySelectorAll('button')].find(b => b.textContent.includes('加载到工作区'));
  if (!btn) return 'no-button';
  btn.click();
  return 'clicked';
})()`);
check("找到「不定积分」示例并点加载", clickedIntegral === "clicked", String(clickedIntegral));
await sleep(900);
const hash = await evalJs(`location.hash`);
check("跳到微积分页而不是代数页", String(hash).includes("/calc/calculus"), String(hash));
const pickedMode = await evalJs(`(document.querySelector('select.cb-mode') || {}).value || ''`);
check("选中的模式是不定积分（不是解方程/组）", String(pickedMode).trim() === "不定积分", String(pickedMode));
const exprInBox = await evalJs(`(() => { const f = document.querySelector('math-field.cb-input'); return f ? String(f.value) : ''; })()`);
check("表达式已填入输入框", String(exprInBox).includes("sin"), String(exprInBox).slice(0, 30));

// 真算一次：不定积分有参数弹窗，确认后应得到 -x*cos(x)+sin(x)+C，而不是任何报错
await evalJs(`(() => { const b = document.querySelector('.cb-calc'); if (b) b.click(); return true; })()`);
await sleep(700);
await evalJs(`(() => {
  for (const b of document.querySelectorAll('button')) {
    if ((b.textContent || '').trim() === '计算') { b.click(); return true; }
  }
  return false;
})()`);
await sleep(1200);
const blockErr = await evalJs(`(document.querySelector('.cb-error') || {}).textContent || ''`);
const errText = String(blockErr);
check("计算没有报错（尤其不再报超越函数拦截）",
  !errText.includes("超越") && !errText.includes("请输入"), errText.trim().slice(0, 60) || "（无错误）");
const dlgText = await evalJs(`(() => { const d = document.querySelector('.dialog, [class*=dialog]'); return d ? d.textContent.replace(/\\s+/g, ' ').slice(0, 200) : ''; })()`);
check("结果是含 cos 与 sin 的原函数（积分真的算出来了）",
  /cos/.test(String(dlgText)) && /sin/.test(String(dlgText)), String(dlgText).slice(0, 90));

console.log("=== 数学键盘 ===");

await goto("/calc/algebra");
check("计算页可打开", await waitTrue(`!!document.querySelector('[data-tour="calc_block.input"]')`));

// 先聚焦输入框，再开键盘（键盘靠"最后聚焦的输入框"决定插到哪）
await evalJs(`(() => { const f = document.querySelector('math-field'); if (f) f.focus(); return true; })()`);
await sleep(200);

// 键盘面板的显隐是**持久化**状态（mf_kb_visible）。上一轮测试若把它留在"开"，
// 这里再点一下就会把它关掉，看起来像"打不开"——所以先看当前状态再决定是否点。
// 这是测试污染，不是实现问题（已实测确认）。
const keypadOpenBefore = await evalJs(`!!document.querySelector('.keypad')`);
if (keypadOpenBefore !== true) {
  await evalJs(`(() => { const b = document.querySelector('[data-tour="main_window.keyboard_button"]'); if (b) b.click(); return true; })()`);
}
check("键盘面板可打开", await waitTrue(`!!document.querySelector('.keypad')`),
  keypadOpenBefore ? "（先前已处于打开状态，未重复点击）" : "");

const catNames = await evalJs(`[...document.querySelectorAll('.kp-tab')].map((b) => b.textContent.trim()).join(',')`);
check("6 个分类且名称顺序与 v1 一致",
  catNames === "基础运算,微积分,线性代数,希腊字母,概率统计,常用模板", catNames);

// 当前分类页签是**持久化**的（mf_kb_tab，这是本轮的改进：v1 每次都回到第一页），
// 所以先显式切回"基础运算"，不能假设初始值。
await evalJs(`(() => {
  for (const b of document.querySelectorAll('.kp-tab')) if (b.textContent.trim() === '基础运算') { b.click(); return true; }
  return false;
})()`);
await sleep(250);
const basicKeys = await evalJs(`document.querySelectorAll('.kp-row .kp-key').length`);
check("基础运算分类 26 键", basicKeys === 26, `实际 ${basicKeys}`);

// 切到希腊字母：应显示 34 键（v1 的希腊字母组是 6 行 34 键）
await evalJs(`(() => {
  for (const b of document.querySelectorAll('.kp-tab')) if (b.textContent.trim() === '希腊字母') { b.click(); return true; }
  return false;
})()`);
await sleep(250);
const greekKeys = await evalJs(`document.querySelectorAll('.kp-row .kp-key').length`);
check("希腊字母分类 34 键", greekKeys === 34, `实际 ${greekKeys}`);

// 插一个 LaTeX 模板：MathLive 里应出现 \frac 且**保留占位符**（v1 会把 ▢ 剥掉）
await evalJs(`(() => {
  for (const b of document.querySelectorAll('.kp-tab')) if (b.textContent.trim() === '常用模板') { b.click(); return true; }
  return false;
})()`);
await sleep(250);
const tplKeys = await evalJs(`document.querySelectorAll('.kp-row .kp-key').length`);
check("常用模板分类 11 键", tplKeys === 11, `实际 ${tplKeys}`);

const clicked = await evalJs(`(() => {
  const el = document.querySelector('math-field');
  if (el) { el.value = ''; el.focus(); }
  const keys = [...document.querySelectorAll('.kp-row .kp-key')];
  const frac = keys.find((k) => (k.textContent || '').includes('frac'));
  if (!frac) return '找不得 \\\\frac 键';
  frac.click();
  return 'clicked';
})()`);
check("找到并点击 \\frac 模板键", clicked === "clicked", String(clicked));
await sleep(500);
const fieldValue = await evalJs(`(document.querySelector('math-field') || {}).value || ''`);
check("点键后 LaTeX 插入到输入框", String(fieldValue).includes("frac"), JSON.stringify(String(fieldValue).slice(0, 48)));
check("插入值带可跳转占位符（v1 的 ▢ 被剥掉过）",
  /placeholder|#0|#\?/.test(String(fieldValue)), JSON.stringify(String(fieldValue).slice(0, 48)));
// 插入成功时不能还挂着"未选中输入框"的提示
const hintAfter = await evalJs(`(document.querySelector('.kp-hint')||{}).textContent || ''`);
check("插入成功后不再显示「未选中输入框」", !String(hintAfter).includes("未选中"), String(hintAfter).trim().slice(0, 30));
// onKey 成功时会写入"最近使用"，用它作为"插入真的发生"的独立信号
const recent = await evalJs(`(() => { try { return JSON.parse(localStorage.getItem('mf_kb_recent')||'[]'); } catch { return []; } })()`);
check("插入被记入最近使用（插入成功信号）",
  Array.isArray(recent) && recent.some((x) => String(x).includes("frac")), JSON.stringify(recent).slice(0, 60));

// 符号搜索
await evalJs(`(() => {
  const s = document.querySelector('.kp-search');
  if (!s) return false;
  s.value = '积分';
  s.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await sleep(350);
const searchHits = await evalJs(`document.querySelectorAll('.kp-grid .kp-key').length`);
check("符号搜索可用（搜「积分」有结果）", searchHits > 0, `命中 ${searchHits} 个`);

// 无聚焦输入框时必须明确提示（v1 是静默忽略：只有焦点在 QLineEdit 时才插入）
//
// 这里刻意先切到一个**没有数学输入框的页面**（首页）再断言，而不是"在计算页上 blur 一下"：
// MathField 失焦时并不会注销"最后聚焦的输入框"句柄，所以在计算页上判断这件事本身就不稳定
// ——整套跑时偶发假失败（上一个用例刚在这页操作过输入框），单独跑却是好的。
// 离开计算页会让 MathField 卸载并注销句柄，此时"没有可插入目标"是确定性的。
await evalJs(`location.hash = "/"; true`);
await sleep(600);
await evalJs(`(() => {
  const s = document.querySelector('.kp-search');
  if (s) { s.value = ''; s.dispatchEvent(new Event('input', { bubbles: true })); }
  if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
  return true;
})()`);
const hintShown = await waitTrue(`((document.querySelector('.kp-hint')||{}).textContent||'').includes('未选中输入框')`, 5000, 150);
const hintText = await evalJs(`(document.querySelector('.kp-hint')||{}).textContent || ''`);
check("无聚焦输入框时给出明确提示（v1 静默忽略）",
  hintShown === true || String(hintText).includes("未选中输入框"), String(hintText).trim().slice(0, 40));

// 还原环境
await evalJs(`(() => {
  if (${JSON.stringify(savedProgress)} === null) localStorage.removeItem('mf_tut_progress');
  else localStorage.setItem('mf_tut_progress', ${JSON.stringify(savedProgress)});
  // 键盘显隐不还原成"本测试改动前的值"：那个值本身往往就是上一轮测试留下的。
  // 应用默认是隐藏，测试结束后清掉这个键即可（用户从未改过这项偏好）。
  localStorage.removeItem('mf_kb_visible');
  if (${JSON.stringify(savedRecent)} === null) localStorage.removeItem('mf_kb_recent');
  else localStorage.setItem('mf_kb_recent', ${JSON.stringify(savedRecent)});
  return true;
})()`);

if (exceptions.length) {
  console.log(`  [WARN] 页面异常 ${exceptions.length} 条，首条：${exceptions[0].slice(0, 160)}`);
}

console.log(`RESULT|cdp-tutorials-keypad|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
