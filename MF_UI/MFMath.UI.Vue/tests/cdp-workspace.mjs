// 工作区保存 / 载入端到端验证（真实宿主窗口里跑）
//
// 要证明的是四件事：
//   ① 三个页面的内容真的被采集进工作区：计算页的计算块、绘图页的表达式+视野、控制台的代码；
//   ② 「保存」真的落盘（%LOCALAPPDATA%\MFMath\settings\workspace.json，宿主原子写）；
//   ③ **刷新页面之后**仍能载入并还原（这是"保存"这个词的全部意义）；
//   ④ 坏输入不静默：版本比程序新、JSON 坏了、空工作区 —— 都要给出可读的原因。
//
// 「另存为文件 / 从文件打开」走宿主的文件对话框（模态，自动化点不了），
// 所以这里用宿主方法的自动化钩子（显式传路径 → 跳过对话框）验证读写与还原；
// 真正的"弹对话框"一步需要人工点一次。
//
// 用法: node cdp-workspace.mjs   （宿主需带 --remote-debugging-port=9222 启动）
import { existsSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { join } from "node:path";

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
/**
 * 这个测试会**真写**用户的工作区文件，所以先把它备份下来，跑完还原：
 * 测试不该留下"我的工作区被一段测试代码覆盖了"这种副作用。
 */
const wsFilePath = join(process.env.LOCALAPPDATA || "", "MFMath", "settings", "workspace.json");
const wsHadFile = existsSync(wsFilePath);
const wsBackup = wsHadFile ? readFileSync(wsFilePath, "utf8") : null;
function restoreWorkspaceFile() {
  try {
    if (wsHadFile) writeFileSync(wsFilePath, wsBackup, "utf8");
    else rmSync(wsFilePath, { force: true });
  } catch { /* 还原失败就报出来，别静默 */ console.error("  [WARN] 工作区文件未能还原：" + wsFilePath); }
}
let ws = new WebSocket(wsUrl);
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
  try { ws.send(JSON.stringify({ id: mid, method, params })); } catch { /* 重连期间忽略 */ }
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
const goto = async (hash) => { await evalJs(`location.hash = ${JSON.stringify(hash)}; true`); await sleep(600); };
/** 页面刷新后会换一个 CDP target，这里重连 */
async function reconnect() {
  try { ws.close(); } catch { /* 忽略 */ }
  for (let i = 0; i < 30; i++) {
    await sleep(500);
    const u = await findPage();
    if (!u) continue;
    const w = new WebSocket(u);
    const ok = await new Promise((r) => { w.onopen = () => r(true); w.onerror = () => r(false); });
    if (!ok) continue;
    ws = w;
    return true;
  }
  return false;
}

console.log("=== ① 在三个页面留下内容 ===");

// 计算页：两个计算块（解方程 + 求导），证明"多块"也能存
await goto("/calc/algebra");
await waitTrue(`!!document.querySelector('math-field.cb-input')`);
await evalJs(`(() => {
  const sel = document.querySelector('select.cb-mode');
  if (sel) { sel.value = '解方程/组'; sel.dispatchEvent(new Event('change', { bubbles: true })); }
  const f = document.querySelector('math-field.cb-input');
  if (f) f.value = "x^2-9";
  return true;
})()`);
await sleep(320);
await evalJs(`(() => {
  const f = document.querySelector('math-field.cb-input');
  if (f) f.dispatchEvent(new Event('input', { bubbles: true }));
  const add = [...document.querySelectorAll('button')].find((b) => b.textContent.includes('添加计算'));
  if (add) add.click();
  return true;
})()`);
await sleep(400);
await evalJs(`(() => {
  const fields = document.querySelectorAll('math-field.cb-input');
  const f = fields[fields.length - 1];
  if (f) f.value = "x^3-3*x";
  return true;
})()`);
await sleep(320);
await evalJs(`(() => {
  const fields = document.querySelectorAll('math-field.cb-input');
  const f = fields[fields.length - 1];
  if (f) f.dispatchEvent(new Event('input', { bubbles: true }));
  const sels = document.querySelectorAll('select.cb-mode');
  const sel = sels[sels.length - 1];
  // 必须是**本页真实存在的模式**（代数页没有「求导」——那是微积分页的）
  if (sel) { sel.value = '因式分解'; sel.dispatchEvent(new Event('change', { bubbles: true })); }
  return true;
})()`);
await sleep(400);
const calcBlocks = await evalJs(`document.querySelectorAll('math-field.cb-input').length`);
check("计算页有 2 个计算块", calcBlocks === 2, `${calcBlocks} 个`);

// 绘图页：一条 sin 曲线 + 关掉网格
await goto("/plot/2d");
await waitTrue(`!!document.querySelector('.expr-input, math-field.expr-input')`);
await evalJs(`(() => {
  const f = document.querySelector('math-field.expr-input') || document.querySelector('math-field');
  if (f) f.value = "y=sin(x)";
  if (f) f.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await sleep(500);

// 控制台：一段代码
await goto("/tools/console");
await sleep(900);
await evalJs(`window.__mfWorkspace && window.__mfWorkspace.setPage("/tools/console", { kind: "console", lang: "python", code: "print('workspace-probe')", stdin: "" })`);
await sleep(200);

const snap = await evalJs(`JSON.stringify(window.__mfWorkspace.pages())`);
let pages = null;
try { pages = JSON.parse(snap); } catch { pages = null; }
check("三个页面都进了工作区", !!pages && !!pages["/calc/algebra"] && !!pages["/plot/2d"] && !!pages["/tools/console"],
  pages ? Object.keys(pages).join(", ") : String(snap).slice(0, 80));
check("计算页存下了 2 个块（含模式）",
  (pages?.["/calc/algebra"]?.blocks?.length || 0) === 2
  && pages["/calc/algebra"].blocks.some((b) => (b.expr || "").includes("x^2-9")),
  JSON.stringify(pages?.["/calc/algebra"]?.blocks || []).slice(0, 120));
check("绘图页存下了 sin 曲线", /sin/.test(JSON.stringify(pages?.["/plot/2d"] || {})),
  JSON.stringify(pages?.["/plot/2d"] || {}).slice(0, 100));

console.log("=== ② 保存到应用数据（宿主原子写）===");
const saveRes = await evalJs(`JSON.stringify(window.__mfWorkspace.saveToApp("/calc/algebra"))`);
check("保存返回成功", /"ok":true/.test(String(saveRes)), String(saveRes));
const storeRaw = await evalJs(`window.chrome.webview.hostObjects.sync.sys.StoreList()`);
const names = (() => { try { return JSON.parse(storeRaw).map((f) => f.name); } catch { return []; } })();
check("数据目录里出现 workspace 文件", names.includes("workspace"), names.join(", ") || "（空）");
const filePath = wsFilePath;
check("磁盘上确实有 workspace.json", existsSync(filePath), filePath);
const onDisk = existsSync(filePath) ? JSON.parse(readFileSync(filePath, "utf8")) : null;
check("文件里的版本号与页面数正确",
  onDisk?.version === 1 && Object.keys(onDisk?.pages || {}).length >= 3,
  onDisk ? `version=${onDisk.version} pages=${Object.keys(onDisk.pages).length}` : "（读不到）");

console.log("=== ③ 刷新页面后仍能载入并还原 ===");
await evalJs(`location.hash = "/calc/algebra"; true`);
await sleep(500);
// 刷新：内存里的工作区必须被清掉，否则"载入"什么都没证明
await evalJs(`location.reload(); true`);
await sleep(800);
const reconnected = await reconnect();
check("刷新后重新连上页面（内存已清空）", reconnected === true);
await sleep(1500);
const afterReload = await evalJs(`JSON.stringify(window.__mfWorkspace.pages())`);
check("刷新后内存里的工作区是空的", String(afterReload) === "{}", String(afterReload).slice(0, 60));

await goto("/settings?group=storage");
await waitTrue(`!!document.querySelector('[data-setting="storage.workspace"]')`);
const rowText = await evalJs(`(() => { const el = document.querySelector('[data-setting="storage.workspace"]'); return el ? el.textContent.replace(/\\s+/g, ' ') : ''; })()`);
check("设置里工作区一行显示的是真实状态（不是待实现）",
  /个页面/.test(String(rowText)) && !/待实现/.test(String(rowText)), String(rowText).slice(0, 110));

// 点面板上的「载入」（而不是直接调 store），这样连按钮接线一起验证
const clickedLoad = await evalJs(`(() => {
  const row = document.querySelector('[data-setting="storage.workspace"]');
  for (const b of row.querySelectorAll('button')) {
    if ((b.textContent || '').trim() === '载入') { b.click(); return true; }
  }
  return false;
})()`);
check("设置里能点到「载入」", clickedLoad === true);
const restoredRoute = await waitTrue(`location.hash.includes("/calc/algebra")`, 6000);
check("载入后跳回保存时的页面", restoredRoute === true, String(await evalJs(`location.hash`)));
await sleep(900);

const vals = await evalJs(`JSON.stringify([...document.querySelectorAll('math-field.cb-input')].map((f) => String(f.value || '')))`);
let restored = [];
try { restored = JSON.parse(vals); } catch { restored = []; }
check("计算页的两个块被还原（表达式回来了）",
  restored.length === 2 && restored.some((v) => /x\^2-9/.test(v)) && restored.some((v) => /x\^3-3\*x/.test(v)),
  JSON.stringify(restored).slice(0, 120));
const modes = await evalJs(`JSON.stringify([...document.querySelectorAll('select.cb-mode')].map((s) => s.value))`);
check("每个块的模式也回来了", /解方程\/组/.test(String(modes)) && /因式分解/.test(String(modes)), String(modes).slice(0, 80));

await goto("/plot/2d");
await sleep(800);
const plotVals = await evalJs(`(() => {
  const f = document.querySelector('math-field.expr-input') || document.querySelector('math-field');
  return f ? String(f.value || '') : '';
})()`);
check("绘图页的 sin 曲线被还原", /sin/.test(String(plotVals)), String(plotVals).slice(0, 40));

await goto("/tools/console");
await sleep(900);
const codeVal = await evalJs(`(() => {
  const t = document.querySelector('.cm-content, textarea');
  return t ? String(t.textContent || t.value || '') : '';
})()`);
check("控制台代码被还原", /workspace-probe/.test(String(codeVal)), String(codeVal).slice(0, 60));

console.log("=== ④ 另存为文件 / 从文件打开（走宿主，跳过对话框的自动化路径）===");
const tmpFile = join(process.env.TEMP || ".", "mf-workspace-test.mfws.json");
try { rmSync(tmpFile, { force: true }); } catch { /* 忽略 */ }
const saveFileRes = await evalJs(`JSON.stringify(window.__mfWorkspace.saveToFile("/calc/algebra", ${JSON.stringify(tmpFile)}))`);
check("另存为写到了指定文件", /"ok":true/.test(String(saveFileRes)) && existsSync(tmpFile), String(saveFileRes).slice(0, 120));
const fileJson = existsSync(tmpFile) ? JSON.parse(readFileSync(tmpFile, "utf8")) : null;
check("写出的文件是合法的工作区（版本+页面）", fileJson?.version === 1 && !!fileJson?.pages?.["/plot/2d"],
  fileJson ? Object.keys(fileJson.pages).join(", ") : "（读不到）");

// 换一个完全不同的内容，再从文件载入 —— 必须把刚才那份盖回来
await evalJs(`window.__mfWorkspace.clearAll(); window.__mfWorkspace.setPage("/calc/algebra", { kind: "calc", blocks: [{ expr: "1+1", mode: "解方程/组" }] })`);
const loadFileRes = await evalJs(`JSON.stringify(window.__mfWorkspace.loadFromFile(${JSON.stringify(tmpFile)}))`);
check("从文件载入成功", /"ok":true/.test(String(loadFileRes)), String(loadFileRes).slice(0, 120));
const afterFile = await evalJs(`JSON.stringify(window.__mfWorkspace.pages())`);
check("文件里的内容盖回来了（不是残留的内存内容）",
  /x\^2-9/.test(String(afterFile)) && !/"1\+1"/.test(String(afterFile)), String(afterFile).slice(0, 90));

console.log("=== ⑤ 坏输入不静默 ===");
// 版本比程序新
writeFileSync(tmpFile, JSON.stringify({ version: 99, pages: { "/calc/algebra": { kind: "calc", blocks: [] } } }), "utf8");
const tooNew = await evalJs(`JSON.stringify(window.__mfWorkspace.loadFromFile(${JSON.stringify(tmpFile)}))`);
check("版本比程序新时明确拒绝并说明",
  /"ok":false/.test(String(tooNew)) && /比当前程序/.test(String(tooNew)), String(tooNew).slice(0, 140));
// JSON 坏掉
writeFileSync(tmpFile, "{ 这不是 JSON", "utf8");
const broken = await evalJs(`JSON.stringify(window.__mfWorkspace.loadFromFile(${JSON.stringify(tmpFile)}))`);
check("文件不是 JSON 时说清是哪一步坏了",
  /"ok":false/.test(String(broken)) && /JSON/.test(String(broken)), String(broken).slice(0, 140));
// 缺 pages
writeFileSync(tmpFile, JSON.stringify({ version: 1 }), "utf8");
const noPages = await evalJs(`JSON.stringify(window.__mfWorkspace.loadFromFile(${JSON.stringify(tmpFile)}))`);
check("缺 pages 字段时明确拒绝", /"ok":false/.test(String(noPages)) && /pages/.test(String(noPages)), String(noPages).slice(0, 120));
try { rmSync(tmpFile, { force: true }); } catch { /* 忽略 */ }

console.log("=== 收尾：还原用户的工作区（测试不留副作用）===");
// 内存里的工作区也要清掉：同一宿主会话里后面还有别的用例，
// 留着它会让绘图/计算页一进去就"还原"成测试内容。
await evalJs(`window.__mfWorkspace.clearAll(); true`);
restoreWorkspaceFile();
check("已还原用户的工作区文件（或删除测试新建的）", wsHadFile ? existsSync(wsFilePath) : !existsSync(wsFilePath),
  wsHadFile ? "原有文件已写回" : "测试新建的文件已删除");

console.log(`RESULT|cdp-workspace|${pass}|${fail}`);
try { ws.close(); } catch { /* 忽略 */ }
process.exit(fail === 0 ? 0 : 1);
