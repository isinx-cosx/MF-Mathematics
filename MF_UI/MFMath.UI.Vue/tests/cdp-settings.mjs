// 设置面板的端到端验证（在真实宿主里跑）
//
// 覆盖"这一轮到底做了什么、有没有假控件"：
//   · 顶栏「设置」从 alert("待实现") 变成真实页面
//   · 7 个分组都在导航里且带 x/y 进度；未实现的分组**不隐藏、不留空白**，
//     而是显示"待实现 + 依赖什么"（v1 的「搜索/历史」是无事件绑定的死按钮）
//   · 外观：改了就生效（无保存按钮）、亮/暗切同家族、恢复默认
//   · 引擎：依赖 DLL 6 项全在、函数数 424、自检逐项比对真实返回值
//   · 组件：状态与目录（复用 ConsoleBridge 的能力）
//   · 存储：数据目录、设置文件列表、导出诊断包
//   · 搜索：能搜到**未实现分组**里的项并跳过去（否则用户搜"密钥"会以为没这功能）
// 用法: node cdp-settings.mjs （宿主需带 --remote-debugging-port=9222 启动）
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
const send = (m, p, t = 30000) => new Promise((res) => {
  const mid = ++id;
  const h = (ev) => { const d = JSON.parse(ev.data); if (d.id === mid) { clearTimeout(tm); ws.removeEventListener("message", h); res(d); } };
  const tm = setTimeout(() => { ws.removeEventListener("message", h); res({ timeout: true, result: { result: { value: "[超时]" } } }); }, t);
  ws.addEventListener("message", h);
  ws.send(JSON.stringify({ id: mid, method: m, params: p }));
});
const ev = async (e) => {
  const r = await send("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return "[异常] " + (r.result.exceptionDetails.text || "");
  return r.result?.result?.value;
};
const exceptions = [];
ws.addEventListener("message", (e) => {
  let d; try { d = JSON.parse(e.data); } catch { return; }
  if (d.method === "Runtime.exceptionThrown") {
    exceptions.push(String(d.params?.exceptionDetails?.exception?.description || "?").slice(0, 200));
  }
});
await send("Runtime.enable");
await sleep(1000);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => { ok ? pass++ : fail++; console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`); };
async function waitTrue(expr, timeoutMs = 6000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) { if ((await ev(expr)) === true) return true; await sleep(120); }
  return false;
}
const clickText = (sel, text) => ev(`(() => {
  for (const b of document.querySelectorAll(${JSON.stringify(sel)})) {
    if ((b.textContent || '').trim().includes(${JSON.stringify(text)})) { b.click(); return true; }
  }
  return false;
})()`);

// 保存外观与设置的原始值，测完还原（测试不该改用户的偏好）
const savedAppearance = await ev(`JSON.stringify(['mf_theme','mf_shape','mf_density','mf_font','mf_theme_follow'].map(k => [k, localStorage.getItem(k)]))`);

console.log("=== 入口与分组 ===");
await clickText('[data-tour="toolbar.settings_button"]', "设置");
check("顶栏「设置」打开真实页面（不再是 alert）", await waitTrue(`!!document.querySelector('.set-groups')`));
// 没有弹窗阻塞：若还是 alert，页面会因为模态而卡住，后面的断言都会超时
const groups = await ev(`[...document.querySelectorAll('.set-groups li .g-label')].map(x => x.textContent.trim()).join(',')`);
// 「计算与绘图」是本轮新增的（v1 的数值精度 + 绘图默认值），所以从 7 组变 8 组
check("分组齐全（含本轮新增的「计算与绘图」）", groups === "外观,计算与绘图,引擎,组件,AI,搜索,更新,存储与数据", groups);
const counts = await ev(`document.querySelectorAll('.set-groups li .g-count').length`);
check("每个分组显示完成度 x/y", counts === 8, `实际 ${counts}`);

console.log("=== 外观（现在就能做，改了就生效）===");
await clickText('.set-groups li', "外观");
check("外观分组可打开", await waitTrue(`!!document.querySelector('[data-setting="appearance.mode"]')`));
const themeCards = await ev(`document.querySelectorAll('.theme-card').length`);
check("配色卡 10 张", themeCards === 10, `实际 ${themeCards}`);
// 先切到一张**非默认**的配色，确认"改了就生效"，再验证"恢复默认"确实把它改回来
const before = await ev(`document.documentElement.dataset.theme`);
await ev(`(() => { const cards = document.querySelectorAll('.theme-card'); (cards[3] || cards[0]).click(); return true; })()`);
await sleep(350);
const afterPick = await ev(`document.documentElement.dataset.theme`);
check("点配色卡立刻生效（无保存按钮）", afterPick !== before, `${before} → ${afterPick}`);
await clickText('.s-ctl button', "暗");
await sleep(350);
check("点「暗」切到深色（data-mode=dark）", (await ev(`document.documentElement.dataset.mode`)) === "dark");
await clickText('[data-setting="appearance.reset"] button', "恢复默认");
await sleep(400);
const afterReset = await ev(`document.documentElement.dataset.theme`);
check("「恢复默认外观」确实改回默认配色", afterReset === "glass-light" && afterReset !== afterPick, String(afterReset));

console.log("=== 引擎（只读展示 + 自检）===");
await clickText('.set-groups li', "引擎");
check("引擎分组可打开", await waitTrue(`!!document.querySelector('[data-setting="engine.deps"]')`));
const depRows = await ev(`document.querySelectorAll('.dep-table tbody tr').length`);
const depBad = await ev(`document.querySelectorAll('.dep-table .dep-ok.bad').length`);
check("依赖 DLL 列出 6 项且全部就位", depRows === 6 && depBad === 0, `列出 ${depRows} 项，缺失 ${depBad} 项`);
const fnCount = await ev(`(document.querySelector('[data-setting="engine.functions"] b') || {}).textContent || ''`);
check("已注册函数数 = 424（来自 list_functions）", String(fnCount).trim() === "424", String(fnCount).trim());
await clickText('[data-setting="engine.selftest"] button', "开始自检");
check("自检结果出现", await waitTrue(`!!document.querySelector('.s-result')`));
const self = await ev(`(() => {
  const items = [...document.querySelectorAll('.s-result .s-item')];
  const bad = items.filter(x => x.classList.contains('bad'))
    .map(x => (x.querySelector('.s-name') || {}).textContent + ' → ' + (x.querySelector('.s-detail') || {}).textContent);
  return { total: items.length, bad: bad.length, badDetail: bad.join(' ｜ ') };
})()`);
// 失败时必须说清是**哪一项、返回了什么**，否则"自检失败"等于没说
check("自检全部通过（逐项比对真实返回值）", self && self.total >= 6 && self.bad === 0,
  self?.bad ? self.badDetail : JSON.stringify(self));

console.log("=== 组件（复用 ConsoleBridge 能力）===");
await clickText('.set-groups li', "组件");
check("组件分组可打开", await waitTrue(`!!document.querySelector('[data-setting="components.python"]')`));
const compTags = await ev(`[...document.querySelectorAll('[data-setting^="components."] .tag')].map(x => x.textContent.trim()).join(',')`);
check("CPython 与 MinGW 组件都显示状态", /已安装|未安装/.test(compTags) && compTags.split(",").length >= 2, compTags);
const compRoot = await ev(`(document.querySelector('[data-setting="components.dir"] .s-hint') || {}).textContent || ''`);
check("组件目录显示为真实路径", /MFMath|components/i.test(compRoot), String(compRoot).trim());

console.log("=== 存储与数据 ===");
await clickText('.set-groups li', "存储与数据");
check("存储分组可打开", await waitTrue(`!!document.querySelector('[data-setting="storage.dir"]')`));
const dataDir = await ev(`(document.querySelector('[data-setting="storage.dir"] .s-hint') || {}).textContent || ''`);
check("数据目录是宿主报的真实路径", /MFMath/.test(dataDir), String(dataDir).trim());
await clickText('[data-setting="storage.diagnostics"] button', "导出");
await sleep(700);
const diagMsg = await ev(`(document.querySelector('.s-warn') || {}).textContent || ''`);
check("导出诊断包成功", /诊断包已导出/.test(diagMsg), String(diagMsg).trim());
const pendingTags = await ev(`document.querySelectorAll('[data-setting^="storage."] .pending-tag').length`);
// 存储组里"待实现"的只剩导入/导出设置（依赖文件对话框的批量迁移）：
// 历史记录、工作区都已经是真实控件，所以阈值一路从 3 调到 1，
// 并补上"它们确实变成了真实控件"的正向断言（否则这条只剩个空壳）。
check("未实现项以「待实现」显式列出（不隐藏不留空）", pendingTags >= 1, `实际 ${pendingTags} 项`);
const histReady = await ev(`!!document.querySelector('[data-setting="storage.history"] .s-btn')`);
check("历史记录已从「待实现」变成真实控件（清空按钮）", histReady === true);
const wsReady = await ev(`(() => {
  const row = document.querySelector('[data-setting="storage.workspace"]');
  if (!row) return false;
  const labels = [...row.querySelectorAll('button')].map((b) => (b.textContent || '').trim());
  return labels.includes('保存') && labels.includes('载入') && labels.includes('另存为文件…');
})()`);
check("工作区已从「待实现」变成真实控件（保存/载入/另存为）", wsReady === true);

console.log("=== AI 组（已从占位变成真实设置）+ 仍占位的搜索组 ===");
await clickText('.set-groups li', "AI");
await sleep(300);
// AI 现在是**真实**设置组：不再是"将在后续版本提供"的占位。
// 这里保留"占位必须说清依赖"这条覆盖，但把它挪到**仍然**是占位的搜索组上
// （占位断言的价值在于"不许留空白或死控件"，不在于指定哪一个分组）。
const aiReady = await ev(`!!document.querySelector('[data-setting="ai.enabled"] input[type=checkbox]')`);
check("AI 分组已是真实设置（有可用的启用开关）", aiReady === true);
const aiPendingTags = await ev(`document.querySelectorAll('[data-setting^="ai."] .pending-tag').length`);
check("AI 分组不再有待实现标记", aiPendingTags === 0, `实际 ${aiPendingTags} 项`);
const aiPrivacy = await ev(`document.querySelectorAll('[data-setting="ai.privacy"] input[type=checkbox]').length`);
check("AI 分组列出了「会发送什么」的逐项开关", aiPrivacy >= 4, `实际 ${aiPrivacy} 项`);
// 密钥那一栏必须说清"在不在"与"是不是明文"，而不是只给一个打码串
const keyStateText = await ev(`(document.querySelector('[data-ai=key-state]') || {}).textContent || ''`);
check("密钥状态说清了来源（未配置 / DPAPI 密文 / 仅内存）",
  /未配置|DPAPI|内存/.test(keyStateText), keyStateText.slice(0, 60));

await clickText('.set-groups li', "搜索");
await sleep(250);
const phText = await ev(`document.querySelector('.set-content').textContent`);
const searchPending = await ev(`document.querySelectorAll('[data-setting^="search."] .pending-tag').length`);
check("搜索分组仍显示占位与依赖说明（不是空白）",
  /该功能将在后续版本提供/.test(phText) && searchPending >= 1, `待实现 ${searchPending} 项`);

await clickText('.set-groups li', "AI");
await sleep(200);
await ev(`(() => { const s = document.querySelector('.set-search'); s.value = '密钥'; s.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
await sleep(300);
const hits = await ev(`document.querySelectorAll('.set-results li').length`);
check("搜索「密钥」能搜到 AI 组里的项", hits > 0, `命中 ${hits} 项`);
await ev(`(() => { const li = document.querySelector('.set-results li'); if (li) li.click(); return true; })()`);
await sleep(400);
const inAi = await ev(`(document.querySelector('.set-groups li.on .g-label') || {}).textContent || ''`);
check("点搜索结果能切到对应分组", String(inAi).trim() === "AI", String(inAi).trim());

console.log("=== 引导目标 ===");
const tourTargets = await ev(`!!document.querySelector('[data-tour="settings_dialog.appearance_tab"]') && !!document.querySelector('[data-tour="settings_dialog.ai_tab"]')`);
check("设置分组已登记为引导目标（教程里那两步不再是「目标不存在」）", tourTargets === true);

// 还原外观偏好
await ev(`(() => {
  for (const [k, v] of JSON.parse(${JSON.stringify(savedAppearance)})) {
    if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v);
  }
  return true;
})()`);

if (exceptions.length) console.log(`  [WARN] 页面异常 ${exceptions.length} 条，首条：${exceptions[0]}`);
console.log(`RESULT|cdp-settings|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
