// cdp-search.mjs — 联网搜索端到端（宿主 SearchBridge + 假端点）
//
// 覆盖：
//   ① 页面与配置：/tools/search 可达、引擎/端点/超时/条数可配、隐私行写明发往哪里
//   ② 三条后端：DuckDuckGo（HTML 结果 + IA 摘要）、Wolfram（需 App ID）、SearXNG JSON
//   ③ 缓存：命中不出网（假端点请求数不增加）、忽略缓存能绕开、键含引擎（换引擎不误命中）
//   ④ 异常分类：500→http、慢速+短超时→timeout、改版→parse、空结果→**不是错误**
//   ⑤ 凭据：App ID 只在宿主（页面/配置/落盘都读不到明文），且只发给配置的端点
//   ⑥ 安全：OpenUrl 只放行 http/https（javascript:/file: 被拒）
//   ⑦ 与计算页的衔接：结果里的表达式"算这个"→ 送到计算页（由**引擎**算）
//
// ⚠ 前置：宿主必须带 MF_SEARCH_ENDPOINTS 启动（指向本用例拉起的假端点）。
//   这不是"测试专用开关"：端点覆盖走环境变量，是因为**页面能改端点就等于能把 App ID
//   发到任意地址**。没带的话本用例会明确报出来，而不是去连真的 DuckDuckGo。
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.FAKE_SEARCH_PORT || 8792);
const FAKE = `http://127.0.0.1:${PORT}`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const fake = spawn(process.execPath, [path.join(HERE, "fake-search-server.mjs")], {
  env: { ...process.env, FAKE_SEARCH_PORT: String(PORT) },
  stdio: "ignore",
});

async function waitFake() {
  for (let i = 0; i < 40; i++) {
    try { if ((await fetch(`${FAKE}/__health`)).ok) return true; } catch { /* 还没起来 */ }
    await sleep(250);
  }
  return false;
}
if (!(await waitFake())) { console.error("假搜索端点没起来"); fake.kill(); process.exit(1); }
const resetFake = () => fetch(`${FAKE}/__reset`, { method: "POST" });
const fakeRequests = async () => (await (await fetch(`${FAKE}/__requests`)).json());

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
if (!wsUrl) { console.error("未找到宿主页面"); fake.kill(); process.exit(1); }
const ws = new WebSocket(wsUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0;
const send = (method, params, timeoutMs = 30000) => new Promise((resolve) => {
  const mid = ++id;
  const h = (ev) => { const d = JSON.parse(ev.data); if (d.id === mid) { clearTimeout(timer); ws.removeEventListener("message", h); resolve(d); } };
  const timer = setTimeout(() => { ws.removeEventListener("message", h); resolve({ timeout: true, result: { result: { value: "[超时]" } } }); }, timeoutMs);
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
async function waitTrue(expr, ms = 12000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { if (await evalJs(expr) === true) return true; await sleep(150); }
  return false;
}
const waitIdle = (ms = 30000) => waitTrue(`window.__mfSearch.state().running === false`, ms);
const waitRunning = (ms = 8000) => waitTrue(`window.__mfSearch.state().running === true`, ms);

/** 读一次搜索状态并解析（写成 async 助手，免得在同步箭头里 await） */
const stateObj = async () => {
  const raw = String(await evalJs(`JSON.stringify(window.__mfSearch.state())`));
  try { return JSON.parse(raw); } catch { return {}; }
};

/** 页面就绪（宿主刚换过 wwwroot 时首屏更慢，别拿固定 sleep 赌） */
let ready = false;
for (let i = 0; i < 40; i++) {
  if (await evalJs(`typeof window.__mfSearch === "object" && window.__mfSearch !== null`) === true) { ready = true; break; }
  if (i === 12) await evalJs(`location.reload()`);
  await sleep(1000);
}
if (!ready) {
  console.error("页面未就绪：等不到 window.__mfSearch");
  try { ws.close(); } catch { /* 忽略 */ }
  try { fake.kill(); } catch { /* 忽略 */ }
  process.exit(1);
}

console.log("=== ① 前置：宿主是否指到了假端点 ===");
const info0 = await evalJs(`JSON.stringify(window.__mfSearch.info())`);
const info0Obj = (() => { try { return JSON.parse(info0); } catch { return {}; } })();
const eps = info0Obj.endpoints || {};
check("宿主提供 search 桥", (await evalJs(`window.__mfSearch.hosted()`)) === true);
check("主机端点是假端点（宿主必须带 MF_SEARCH_ENDPOINTS 启动）",
  String(eps.ddgHtml || "").includes(`127.0.0.1:${PORT}`) && String(eps.wolfram || "").includes(`127.0.0.1:${PORT}`),
  JSON.stringify(eps));
if (!String(eps.ddgHtml || "").includes(`127.0.0.1:${PORT}`)) {
  console.error("  → 请用 MF_SEARCH_ENDPOINTS 指向 tests/fake-search-server.mjs 后重跑（本用例不连真站点）");
  try { ws.close(); } catch { /* 忽略 */ }
  try { fake.kill(); } catch { /* 忽略 */ }
  process.exit(1);
}

console.log("=== ② 页面与配置 ===");
await evalJs(`location.hash = "#/tools/search"`);
check("搜索页可达且有输入框", await waitTrue(`!!document.querySelector('[data-search=input]')`, 10000));
check("引擎选择器在", (await evalJs(`!!document.querySelector('[data-search=engine]')`)) === true);
const cfg = String(await evalJs(`JSON.stringify(window.__mfSearch.configure({
  engine: "duckduckgo", customUrl: ${JSON.stringify(FAKE + "/searxng")},
  timeoutSec: 15, resultCount: 8, cacheEnabled: true, cacheTtlHours: 24
}))`));
check("配置写入成功", /"ok":true/.test(cfg), cfg.slice(0, 80));
const privacy = String(await evalJs(`(document.querySelector('[data-search=endpoint]') || {}).textContent || ''`));
check("隐私行写明查询会发往哪里", /duckduckgo/i.test(privacy), privacy.replace(/\s+/g, " ").slice(0, 90));

console.log("=== ③ DuckDuckGo（结果页 + IA 摘要）===");
// 先清缓存：search_cache.json 是跨运行保留的，否则"请求确实带上了查询词"这条
// 会因为上次运行留下的缓存而变成看运气的用例（实测踩过）。
await evalJs(`window.__mfSearch.clearCache()`);
await resetFake();
const r1 = String(await evalJs(`JSON.stringify(window.__mfSearch.run("黎曼猜想"))`));
check("搜索被受理", /"ok":true/.test(r1), r1.slice(0, 80));
check("搜索确实开始了", await waitRunning());
check("结束后 running=false", await waitIdle());
const st1 = String(await evalJs(`JSON.stringify(window.__mfSearch.state())`));
const st1Obj = (() => { try { return JSON.parse(st1); } catch { return {}; } })();
check("结果条数正确（3 条，坏协议链接被丢弃）", (st1Obj.results || []).length === 3, `实际 ${(st1Obj.results || []).length} 条`);
check("跳转链接还原成真实地址", (st1Obj.results || [])[0]?.url === "https://zh.wikipedia.org/wiki/黎曼猜想", (st1Obj.results || [])[0]?.url);
check("摘要来自 Instant Answer 且去掉了标记", /摘要/.test(String(st1Obj.abstract)) && !/<b>/.test(String(st1Obj.abstract)), String(st1Obj.abstract).slice(0, 80));
check("页面渲染出结果列表", await waitTrue(`document.querySelectorAll('[data-search=results] li').length === 3`));
check("摘要块渲染出来了", (await evalJs(`!!document.querySelector('[data-search=abstract]')`)) === true);
check("请求确实带上了查询词", (await fakeRequests()).some((r) => r.query.includes("黎曼猜想")));
// 引导目标：教程用的是 v1 的语义 ID（search_panel.*），页面必须挂同名 data-tour，
// 否则引导只能显示一句"尚未实现"（本轮修的就是这类"名字对不上"）
const tourOk = JSON.parse(String(await evalJs(`JSON.stringify((() => {
  const out = {};
  for (const n of ["search_panel.input", "search_panel.results"]) {
    const el = document.querySelector('[data-tour="' + n + '"]');
    const r = el && el.getBoundingClientRect();
    out[n] = !!el && r.width > 0 && r.height > 0;
  }
  return out;
})())`)));
check("引导目标 search_panel.input 能定位到可见控件", tourOk["search_panel.input"] === true, JSON.stringify(tourOk));
check("引导目标 search_panel.results 能定位到可见控件", tourOk["search_panel.results"] === true);

console.log("=== ④ 缓存：命中不出网 ===");
const before = (await fakeRequests()).length;
await evalJs(`window.__mfSearch.clear()`);
await evalJs(`window.__mfSearch.run("黎曼猜想")`);
await waitRunning(); await waitIdle();
const st2 = await stateObj();
const after = (await fakeRequests()).length;
check("第二次同查询命中缓存", st2.fromCache === true, `fromCache=${st2.fromCache}`);
check("命中缓存时**没有**再发请求（不出网）", after === before, `${before} → ${after}`);
check("页面显示「来自缓存」标记", (await evalJs(`!!document.querySelector('[data-search=from-cache]')`)) === true);
await evalJs(`window.__mfSearch.run("黎曼猜想", { noCache: true })`);
await waitRunning(); await waitIdle();
check("忽略缓存时会重新抓取", (await fakeRequests()).length > after, `${after} → ${(await fakeRequests()).length}`);

console.log("=== ⑤ 换引擎不误命中缓存（v1 的缺陷）===");
await evalJs(`window.__mfSearch.configure({ engine: "custom" })`);
await evalJs(`window.__mfSearch.run("黎曼猜想")`);
await waitRunning(); await waitIdle();
const st3 = await stateObj();
check("换到自定义引擎后拿到的是**它自己的**结果（不是缓存里的 DDG 结果）",
  st3.fromCache !== true && (st3.results || []).some((r) => /自建实例/.test(r.title)), JSON.stringify((st3.results || []).map((r) => r.title)));

console.log("=== ⑥ Wolfram（App ID 只在宿主）===");
const KEY = "WOLFRAM-FAKE-APPID-7788";
await evalJs(`window.__mfSearch.clearKey()`);
await evalJs(`window.__mfSearch.configure({ engine: "wolfram" })`);
const noKey = String(await evalJs(`JSON.stringify(window.__mfSearch.run("1+1"))`));
check("没 App ID 时给出明确的配置提示（不是笼统失败）", /"ok":false/.test(noKey) && /App ID/.test(noKey), noKey.slice(0, 120));

const setKey = String(await evalJs(`JSON.stringify(window.__mfSearch.setKey(${JSON.stringify(KEY)}))`));
check("App ID 已保存", /"ok":true/.test(setKey), setKey.slice(0, 100));
await resetFake();
await evalJs(`window.__mfSearch.run("integrate x^2")`);
await waitRunning(); await waitIdle();
const st4 = await stateObj();
check("Wolfram 简答渲染成结果", (st4.results || []).length === 1 && /42/.test(String(st4.results[0]?.snippet)), JSON.stringify(st4.results || []).slice(0, 100));
const wreq = (await fakeRequests()).find((r) => r.path.startsWith("/wolfram"));
check("App ID 确实发给了配置的端点", !!wreq?.hasAppid, wreq ? `appidTail=${wreq.appidTail}` : "无请求");
const infoW = String(await evalJs(`JSON.stringify(window.__mfSearch.info())`));
check("脱敏视图里没有 App ID 明文", !infoW.includes(KEY));
const rawCfg = String(await evalJs(`(() => {
  const sys = window.chrome.webview.hostObjects.sync.sys;
  const r = JSON.parse(sys.StoreRead("search"));
  return r.ok ? r.json : "";
})()`));
check("落盘的 search.json 里没有 App ID 明文", rawCfg.length > 0 && !rawCfg.includes(KEY), rawCfg.slice(0, 60));
check("落盘用的是密文（wolframKeyProtected）", /wolframKeyProtected/.test(rawCfg));
check("页面里也读不到 App ID", (await evalJs(`document.body.textContent.includes(${JSON.stringify(KEY)})`)) === false);

console.log("=== ⑦ 异常分类（不崩、原因可指导下一步）===");
await evalJs(`window.__mfSearch.configure({ engine: "duckduckgo", cacheEnabled: false })`);
async function runCase(q, expectKind, label, timeoutSec = 15) {
  await evalJs(`window.__mfSearch.configure({ timeoutSec: ${timeoutSec} })`);
  const r = String(await evalJs(`JSON.stringify(window.__mfSearch.run(${JSON.stringify(q)}))`));
  if (!/"ok":true/.test(r)) { check(label, false, "发送被拒：" + r.slice(0, 100)); return ""; }
  if (!await waitRunning()) { check(label, false, "没有进入 running"); return ""; }
  const idle = await waitIdle(40000);
  const st = String(await evalJs(`JSON.stringify(window.__mfSearch.state())`));
  check(label, idle && new RegExp(`"kind":"${expectKind}"`).test(st), st.slice(0, 170));
  return st;
}
await runCase("会 500 的查询", "http", "端点 500 → kind=http");
await runCase("会 改版 的查询", "parse", "形状变了（没有结果块）→ kind=parse");
await runCase("会 慢速 的查询", "timeout", "慢速 + 短超时 → kind=timeout", 3);

// 空结果**不是**错误
await evalJs(`window.__mfSearch.configure({ timeoutSec: 15 })`);
await evalJs(`window.__mfSearch.run("空")`);
await waitRunning(); await waitIdle();
const stEmpty = await stateObj();
check("空结果不算错误，而是明确的状态", stEmpty.error === null && (stEmpty.results || []).length === 0, JSON.stringify(stEmpty).slice(0, 120));
check("页面显示「没有找到结果」", (await evalJs(`!!document.querySelector('[data-search=empty]')`)) === true);

// 取消
await evalJs(`window.__mfSearch.configure({ timeoutSec: 30 })`);
await evalJs(`window.__mfSearch.run("会 慢速 的查询")`);
await waitRunning();
await evalJs(`window.__mfSearch.cancel()`);
await waitIdle(15000);
const stCancel = String(await evalJs(`JSON.stringify(window.__mfSearch.state())`));
check("取消 → kind=aborted（与超时分开）", /"kind":"aborted"/.test(stCancel), stCancel.slice(0, 140));

console.log("=== ⑧ 安全：打开链接的协议闸门 ===");
const openBad = String(await evalJs(`JSON.stringify(window.__mfSearch.openUrl("javascript:alert(1)"))`));
check("拒绝 javascript: 链接", /"ok":false/.test(openBad), openBad.slice(0, 90));
const openFile = String(await evalJs(`JSON.stringify(window.__mfSearch.openUrl("file:///C:/Windows/System32/cmd.exe"))`));
check("拒绝 file: 链接", /"ok":false/.test(openFile), openFile.slice(0, 90));
const openMs = String(await evalJs(`JSON.stringify(window.__mfSearch.openUrl("ms-settings:"))`));
check("拒绝自定义协议", /"ok":false/.test(openMs), openMs.slice(0, 90));

console.log("=== ⑨ 与计算页的衔接（表达式由引擎算）===");
const expr = String(await evalJs(`window.__mfSearch.extractExpr("零点分布 Re(s)=1/2 前 10^13 个")`));
check("能从结果文本里提出候选表达式", expr.length > 0, expr);
// 先回到搜索页并**重新搜一次**：⑧ 之前的用例已经把状态改成了错误/空，那里没有结果项可点。
// （这也是"上一轮状态会污染下一轮断言"的老毛病，显式重跑一次最省事。）
await evalJs(`location.hash = "#/tools/search"`);
await waitTrue(`!!document.querySelector('[data-search=input]')`, 10000);
await evalJs(`window.__mfSearch.configure({ engine: "duckduckgo", cacheEnabled: false })`);
await evalJs(`window.__mfSearch.run("黎曼猜想 的零点")`);
await waitRunning(); await waitIdle();
check("结果里有可算的表达式（按钮才会出现）", await evalJs(`!!document.querySelector('[data-search^=calc-]')`) === true);
const calcBtn = String(await evalJs(`(() => {
  const b = document.querySelector('[data-search^=calc-]');
  if (!b) return "无";
  b.click();
  return "点了";
})()`));
check("结果项上有「算这个」按钮", calcBtn === "点了", calcBtn);
await sleep(900);
const hash = String(await evalJs(`location.hash`));
check("点了之后跳到基础运算页（pendingInput 的既有通路）", /\/calc\/basic/.test(hash), hash);
// 关键：表达式**进了计算页**，但结果仍由引擎产出（搜索答案不当计算源）
const lcd = String(await evalJs(`(() => {
  const el = document.querySelector('.lcd');
  return el ? el.textContent.replace(/\\s+/g, ' ').trim() : '';
})()`));
const shownExpr = await evalJs(`(() => {
  const el = document.querySelector('.lcd .lcd-expr');
  return el ? el.textContent.trim() : '';
})()`);
check("表达式已经填进计算页（用户不必手抄）", String(shownExpr).length > 0 || lcd.includes(expr.slice(0, 4)),
  `expr=${JSON.stringify(shownExpr)} lcd=${lcd.slice(0, 60)}`);
check("结果区没有被搜索结果写死（要算就得过引擎）",
  (await evalJs(`(() => { const r = document.querySelector('.lcd .lcd-result'); return r ? r.textContent.trim() : '0'; })()`)) === "0",
  String(await evalJs(`(() => { const r = document.querySelector('.lcd .lcd-result'); return r ? r.textContent.trim() : '0'; })()`)));

console.log("=== ⑩ 深链与自检 ===");
await evalJs(`location.hash = "#/tools/search?q=深链查询"`);
await waitTrue(`window.__mfSearch.state().query === "深链查询"`, 10000);
check("?q= 深链会自动开搜", (await evalJs(`window.__mfSearch.state().query === "深链查询"`)) === true);

const sc = String(await evalJs(`JSON.stringify(window.__mfSearch.selfCheck())`));
check("自检：DDG 结果解析", /"name":"DuckDuckGo 结果解析","ok":true/.test(sc), sc.slice(0, 140));
check("自检：Instant Answer 摘要解析", /"name":"Instant Answer 摘要解析","ok":true/.test(sc));
check("自检：SearXNG JSON 解析", /"name":"SearXNG JSON 解析","ok":true/.test(sc));
check("自检：缓存键含引擎 + TTL", /"name":"缓存键含引擎 \+ TTL","ok":true/.test(sc));
check("自检：打开链接只放行 http/https", /"name":"打开链接只放行 http\/https","ok":true/.test(sc));

console.log("=== ⑪ 设置页的搜索分组 ===");
await evalJs(`location.hash = "#/settings?group=search"`);
check("搜索分组可达", await waitTrue(`!!document.querySelector('[data-setting="search.engine"]')`, 10000));
check("App ID 输入框是 password（不明文展示）",
  (await evalJs(`document.querySelector('[data-search-set=appid]')?.type === "password"`)) === true);
check("分组里写明查询会发往哪里",
  await evalJs(`(() => { const t = document.querySelector('[data-setting="search.engine"]').textContent; return /发往/.test(t); })()`) === true);
check("缓存统计是真实数字", await waitTrue(`/当前 \\d+ 条/.test(document.querySelector('[data-search=cache-stats]')?.textContent || '')`));
// 收尾：清掉 App ID 与缓存，别污染用户环境
await evalJs(`window.__mfSearch.clearKey(); window.__mfSearch.clearCache(); window.__mfSearch.configure({ engine: "duckduckgo" })`);

console.log(`RESULT|cdp-search|${pass}|${fail}`);
try { ws.close(); } catch { /* 忽略 */ }
try { fake.kill(); } catch { /* 忽略 */ }
process.exit(fail === 0 ? 0 : 1);
