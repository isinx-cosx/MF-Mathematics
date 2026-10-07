// cdp-ai.mjs — AI 助手端到端（页面直连假端点 + 明文密钥配置 + fetch 流式）
//
// 覆盖三层：
//   ① 配置与密钥：**页面直连**用户填的端点；密钥**明文**存 ai.json（脱敏视图里仍然没有它），
//      baseUrl 只接受 http/https，且拼接时不会退回内置站点；
//   ② 流式与七类异常：正常增量、停止、401/500、坏 SSE、无 usage、无 [DONE]、
//      连接失败、超时 —— 全都要求"不崩、有明确原因、下一轮还能继续"；
//   ③ 硬约束：**AI 不得成为计算源** —— 假端点故意回 "1+1=3"，
//      断言计算页的结果区仍然是引擎算出来的值（这条是整个 AI 功能的红线）。
//
// 架构断言（本轮改动的核心，别删）：
//   · 请求由**页面**发出：假端点收到的 Origin 头 = 页面 origin
//     （旧架构里是宿主 HttpClient，不会有这个头）；
//   · 对话**不再依赖任何宿主推送**：push log 里没有 ai.* 话题，
//     流是页面自己从 fetch 的 body 里读的。
//
// 前置：本套件自己拉起 tests/fake-ai-server.mjs，不需要网络也不需要真 key。
//
// 用法: node cdp-ai.mjs   （宿主需带 --remote-debugging-port=9222 启动）
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.FAKE_AI_PORT || 8791);
const BASE = `http://127.0.0.1:${PORT}/v1`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ── 假端点 ─────────────────────────────────────────────────────────── */

const fake = spawn(process.execPath, [path.join(HERE, "fake-ai-server.mjs")], {
  env: { ...process.env, FAKE_AI_PORT: String(PORT) },
  stdio: "ignore",
});

async function waitFake() {
  for (let i = 0; i < 40; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/__health`);
      if (r.ok) return true;
    } catch { /* 还没起来 */ }
    await sleep(250);
  }
  return false;
}
const fakeUp = await waitFake();
if (!fakeUp) { console.error("假端点没起来"); fake.kill(); process.exit(1); }
const resetFake = () => fetch(`http://127.0.0.1:${PORT}/__reset`, { method: "POST" });
const fakeRequests = async () => (await (await fetch(`http://127.0.0.1:${PORT}/__requests`)).json());

/* ── CDP ────────────────────────────────────────────────────────────── */

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
/** 最后开始的那条检查（页面卡死时报出来，比"看哪一条 FAIL 了"准得多） */
let lastCheck = "";

/**
 * 求值一次。
 *
 * ⚠ 页面**卡死**（渲染进程不再响应 CDP，例如某个宿主桥调用没有返回）时必须**立刻报一次并停下**：
 * 否则后面每条检查都会各自等满 30 秒、报成"功能坏了"，把真正的病因埋掉
 * —— 实测踩过：一次卡死产生了 8 条互不相干的假失败，还顺带吃掉了收尾的复位。
 */
const evalJs = async (expr, timeoutMs = 30000) => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }, timeoutMs);
  if (r.timeout === true) {
    console.error(`\n[HANG] 页面在「${lastCheck || "(启动阶段)"}」之后不再响应 CDP（渲染进程卡死 / 宿主桥调用没返回）。`);
    console.error("[HANG] 后续检查已跳过；请把这一行与它上面最后几条输出一起报上来。");
    console.error("[HANG] 已知残留：%LOCALAPPDATA%\\MFMath\\settings\\ai.json 会停在最后一次成功写入的状态（收尾复位没跑到）。");
    console.log(`RESULT|cdp-ai|${pass}|${fail}`);
    try { ws.close(); } catch { /* 忽略 */ }
    try { fake.kill(); } catch { /* 忽略 */ }
    process.exit(2);
  }
  if (r.result?.exceptionDetails) return "[异常] " + (r.result.exceptionDetails.text || "");
  return r.result?.result?.value;
};

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  lastCheck = label;
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

async function waitTrue(expr, ms = 12000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if (await evalJs(expr) === true) return true;
    await sleep(150);
  }
  return false;
}

/** 等这一轮结束（running=false） */
const waitIdle = (ms = 20000) => waitTrue(`window.__mfAi.state().running === false`, ms);
/** 等这一轮真的开始 —— 不先等它开始就等它结束，会在"发送被拒"时**假装通过** */
const waitRunning = (ms = 8000) => waitTrue(`window.__mfAi.state().running === true`, ms);

/**
 * 清掉可能残留的上一轮状态。
 *
 * 页面直连之后请求只活在这个页面里（AbortController + fetch），
 * 宿主侧没有"刷新后还活着的旧连接"，所以这里只需要页面侧停止；
 * 停完再确认 running 已经落回 false，免得下一次发送被自己的单飞检查拒绝。
 */
async function resetTurn() {
  await evalJs(`(() => {
    try { window.__mfAi.stop(); } catch (e) { /* 没在跑就算了 */ }
    return true;
  })()`);
  await waitTrue(`window.__mfAi.state().running === false`, 5000);
  await sleep(200);
}

console.log("=== ① 配置与密钥（明文存 ai.json，请求由页面直连）===");

// 先等页面把 __mfAi 钩子挂上。宿主刚换过 wwwroot 时首屏会更慢（WebView2 缓存是冷的），
// 用固定 sleep 赌这一刻的结果就是"同一构建有时 52/0、有时满屏 Uncaught"。
// 所以这里显式轮询，并允许一次重载兜底；等不到就**明确报错退出**，而不是继续跑出一堆假失败。
let pageReady = false;
for (let i = 0; i < 40; i++) {
  if (await evalJs(`typeof window.__mfAi === "object" && window.__mfAi !== null`) === true) { pageReady = true; break; }
  if (i === 12) await evalJs(`location.reload()`);
  await sleep(1000);
}
if (!pageReady) {
  console.error("页面未就绪：等不到 window.__mfAi（App 没挂载？前端构建没同步到 wwwroot？）");
  try { ws.close(); } catch { /* 忽略 */ }
  try { fake.kill(); } catch { /* 忽略 */ }
  process.exit(1);
}

// 干净起点：上一个跑挂了的会话可能在 ai.json 里留下密钥，而下面的"未配置"断言要靠它为空
await evalJs(`window.__mfAi.clearKey()`);
// "就绪"的语义已经变了：不再是"宿主提供了 ai 桥"，而是"**配置齐备**"
// （能读到设置文件 + 开关打开 + 有明文密钥 + 端点合法）。没密钥时不能自称就绪。
check("没有密钥时不假装就绪（就绪 = 配置齐备）", (await evalJs(`window.__mfAi.hosted()`)) === false);

// 先清掉**已落盘的旧会话**：否则"回答只出现一次""思考过程只出现一次"这类断言
// 会被上一次运行留下的 ai-chat.json 影响，变成看运气的用例。
await evalJs(`window.__mfAi.clear()`);
await sleep(200);

const info0 = await evalJs(`JSON.stringify(window.__mfAi.info())`);
check("读到脱敏配置", typeof info0 === "string" && info0.includes("baseUrl"), String(info0).slice(0, 80));

// 配到假端点并启用
const configured = await evalJs(`JSON.stringify(window.__mfAi.configure({
  enabled: true, baseUrl: ${JSON.stringify(BASE)}, model: "fake-model",
  timeoutSec: 20, includeUsage: true, sendExpr: true, sendResult: true,
  sendHistory: false, sendCode: false
}))`);
check("配置写入成功", /"ok":true/.test(String(configured)), String(configured).slice(0, 80));

const KEY = "sk-fake-DO-NOT-LEAK-9f3c";
const setKey = await evalJs(`JSON.stringify(window.__mfAi.setKey(${JSON.stringify(KEY)}))`);
check("密钥已设置（明文写进 ai.json）", /"ok":true/.test(String(setKey)), String(setKey).slice(0, 120));
check("配置齐备后自称就绪（AI 直连就绪）", (await evalJs(`window.__mfAi.hosted()`)) === true);

const info1 = String(await evalJs(`JSON.stringify(window.__mfAi.info())`));
check("脱敏视图：hasKey=true", /"hasKey":true/.test(info1));
check("脱敏视图：密钥来源是配置文件", /"keySource":"file"/.test(info1), (info1.match(/"keySource":"[^"]*"/) || [""])[0]);
check("脱敏视图：密钥已落盘", /"keyPersisted":true/.test(info1));
check("脱敏视图里**没有**密钥明文", !info1.includes(KEY));
check("脱敏视图里没有密钥字段（apiKey / apiKeyProtected 都不在）",
  !/"apiKey"/.test(info1) && !/"apiKeyProtected"/.test(info1));

// 配置文件里**就是明文** —— 这是本轮的明确决定（不再 DPAPI、不再走宿主 SetKey）。
// 页面直连要用它，所以它必须可读；同时上面那条断言保证它不会出现在脱敏视图里。
const raw = String(await evalJs(`(() => {
  const sys = window.chrome.webview.hostObjects.sync.sys;
  const r = JSON.parse(sys.StoreRead("ai"));
  return r.ok ? r.json : "";
})()`));
check("落盘的 ai.json 里是**明文** apiKey（用户已决定不再加密）",
  raw.length > 0 && raw.includes(KEY), raw.length > 0 ? "" : "读不到文件");
check("旧版密文字段已被清掉（不会出现两把钥匙打架）", !/"apiKeyProtected"/.test(raw));

// 新架构下**仍然成立**的安全属性：端点只接受 http/https，且拼接时**不会退回内置站点**。
// （旧架构那条"页面不能让宿主把密钥发到任意地址"随中继一起消失，换成这两条。）
const urlFacts = JSON.parse(String(await evalJs(`JSON.stringify({
  ok: window.__mfAi.relay.join("https://api.example.com/v1", "/chat/completions"),
  badScheme: (() => { try { window.__mfAi.relay.join("ftp://evil.example/v1", "/chat/completions"); return "没报错"; } catch (e) { return String(e.message || e); } })(),
  empty: (() => { try { window.__mfAi.relay.join("", "/chat/completions"); return "没报错"; } catch (e) { return String(e.message || e); } })(),
  protoRelative: (() => { try { window.__mfAi.relay.join("//evil.example/v1", "/chat/completions"); return "没报错"; } catch (e) { return String(e.message || e); } })(),
  usableHttp: window.__mfAi.relay.usable("http://127.0.0.1:8791/v1"),
  usableHttps: window.__mfAi.relay.usable("https://api.deepseek.com/v1"),
  usableFtp: window.__mfAi.relay.usable("ftp://api.deepseek.com/v1"),
  usableEmpty: window.__mfAi.relay.usable("")
})`)));
check("端点只接受 http/https（https 与 http 都收，ftp 被拒）",
  urlFacts.usableHttp === true && urlFacts.usableHttps === true && urlFacts.usableFtp === false,
  JSON.stringify(urlFacts).slice(0, 160));
check("空地址不算可用（不会被当成默认站点）", urlFacts.usableEmpty === false);
check("拼接只是 baseUrl + path（同源，不改写站点）",
  urlFacts.ok === "https://api.example.com/v1/chat/completions", String(urlFacts.ok));
check("非 http/https 地址**直接报错**，不退回内置站点",
  !/没报错/.test(urlFacts.badScheme) && !urlFacts.badScheme.includes("api.deepseek.com"), urlFacts.badScheme.slice(0, 130));
check("空地址同样报错（不会悄悄用内置站点）",
  !/没报错/.test(urlFacts.empty) && !urlFacts.empty.includes("api.deepseek.com"), urlFacts.empty.slice(0, 130));
check("协议相对地址（//host）被拒", !/没报错/.test(urlFacts.protoRelative), urlFacts.protoRelative.slice(0, 130));

// 行为层面再钉一次：配置里写一个非法协议，发送必须**在本地就失败**，
// 一个请求都不许出去（否则就是"把密钥发给别的站点"这类事故）。
//
// ⚠ 这里**必须先真的把 baseUrl 改成非法值**（第一版漏了这一步，于是发送用的还是
// 上一轮的合法端点：既 ok:true、又真的发出去一个请求，还顺手往会话里塞了一条回答，
// 让后面"同一段回答只出现一次"跟着一起挂）。
await resetTurn();
check("把端点改成非 http/https", /"ok":true/.test(String(await evalJs(`JSON.stringify(window.__mfAi.configure({ baseUrl: "ftp://evil.example/v1" }))`))));
check("非法端点下不自称就绪", (await evalJs(`window.__mfAi.hosted()`)) === false);
const beforeBadUrl = (await fakeRequests()).length;
const badSend = String(await evalJs(`JSON.stringify(window.__mfAi.send("这条不该发出去"))`));
await sleep(400);
check("非法 baseUrl：发送被本地拒绝",
  /"ok":false/.test(badSend) && /端点地址不合法/.test(badSend), badSend.slice(0, 140));
check("非法 baseUrl：一个请求都没发出去",
  (await fakeRequests()).length === beforeBadUrl, `${beforeBadUrl} → ${(await fakeRequests()).length}`);
check("非法 baseUrl：没有往会话里塞东西", (await evalJs(`window.__mfAi.messages().length`)) === 0);
// 复位：端点回到假端点，并把这一节留下的错误状态清干净（§② 的"只出现一次"要靠这个）
await evalJs(`window.__mfAi.configure({ baseUrl: ${JSON.stringify(BASE)} })`);
await evalJs(`window.__mfAi.clear()`);
check("复位后重新就绪", (await evalJs(`window.__mfAi.hosted()`)) === true);

console.log("=== ② 正常流式 ===");
await resetTurn();
await resetFake();
// 先把面板打开：后面几节都要断言 DOM（面板是 v-if 渲染的，不开就什么都查不到）
await evalJs(`document.querySelector('[data-ai=open]').click()`);
check("顶栏 AI 按钮能打开面板", await waitTrue(`!!document.querySelector('[data-ai=panel]')`, 8000));
const sent = await evalJs(`JSON.stringify(window.__mfAi.send("你好"))`);
check("发送被受理", /"ok":true/.test(String(sent)), String(sent).slice(0, 90));
check("这一轮真的开始了（running=true）", await waitRunning());
// 注意：**不在这里断言 state().stream 非空** —— 假端点毫秒级就把整段吐完，
// 轮询常常落在"已经收尾、缓冲已清空"之后（这正是修掉的那个重复渲染 bug 的副作用）。
// 真·流式的证据放在 ③ 的慢速场景里（300ms 一个字，长度必然在增长）。
check("本轮结束后 running=false", await waitIdle());
const st1 = await evalJs(`JSON.stringify(window.__mfAi.state())`);
check("usage 收到（假端点给了尾包）", /"inputTokens":42/.test(String(st1)), String(st1).slice(0, 120));
check("回复进入会话记录", await evalJs(`window.__mfAi.messages().some(m => m.role === "assistant")`) === true);
check("面板 DOM 里能看到正文", await waitTrue(`(document.querySelector('[data-ai=stream]')?.textContent || '').includes('收到') || document.querySelector('[data-ai=msgs]').textContent.includes('收到')`));
// 架构断言：**不再依赖宿主推送**。
// 旧架构是宿主把响应字节经 ai.http / ai.raw* 推回来、页面订阅话题；
// 现在是页面自己 fetch、自己 `resp.body.getReader()` 读流 —— 所以：
//   ① 假端点真的收到了这次请求（fetch 确实发出去了）；
//   ② push log 里**不该再有**任何 ai.* 话题（没有 ai.http / ai.raw* / ai.delta / ai.test）。
check("这一轮的请求真的打到了假端点（页面自己 fetch，不经宿主推送）",
  (await fakeRequests()).length >= 1, `收到 ${(await fakeRequests()).length} 次`);
const pushTopics = String(await evalJs(`JSON.stringify([...new Set(window.__mfPush.log().map(e => e.topic))])`));
check("对话不再依赖宿主推送（push log 里没有任何 ai.* 话题）",
  !/"ai\./.test(pushTopics), pushTopics.slice(0, 140));
check("流是页面直接从 fetch 读的（没有 ai.raw / ai.http / ai.delta 这类中继话题）",
  !/"ai\.raw/.test(pushTopics) && !/"ai\.http"/.test(pushTopics) && !/"ai\.delta"/.test(pushTopics),
  pushTopics.slice(0, 140));

// 回归：一轮结束后**不能有残留的实时缓冲**，否则同一段回答会被渲染两次
// （实测踩过：running 置假了但 aiState.stream 没清，面板里回答出现两遍）
const afterDone = String(await evalJs(`JSON.stringify({
  stream: window.__mfAi.state().stream,
  reasoning: window.__mfAi.state().reasoning,
  streamBlock: !!document.querySelector('[data-ai=stream]')
})`));
check("收尾后实时缓冲已清空（不会和消息重复）",
  /"stream":""/.test(afterDone) && /"reasoning":""/.test(afterDone) && /"streamBlock":false/.test(afterDone),
  afterDone.slice(0, 120));
const dupCount = await evalJs(`(() => {
  const panel = document.querySelector('[data-ai=panel]');
  const text = (panel ? panel.textContent : "").replace(/\\s+/g, " ");
  const needle = "收到";
  let n = 0, i = 0;
  while ((i = text.indexOf(needle, i)) !== -1) { n++; i += needle.length; }
  return n;
})()`);
check("面板里同一段回答只出现一次（重复渲染回归）", dupCount === 1, `出现 ${dupCount} 次`);

// 思考过程归属：收尾后跟着消息走，不再挂在面板底部
await resetTurn();
await evalJs(`window.__mfAi.send("思考 一下")`);
await waitIdle(20000);
const reasonState = String(await evalJs(`JSON.stringify({
  live: window.__mfAi.state().reasoning,
  last: (window.__mfAi.messages().slice(-1)[0] || {}).reasoning || ""
})`));
check("思考过程挂在消息上（收尾后实时块清空）",
  /"live":""/.test(reasonState) && /"last":"[^"]+"/.test(reasonState), reasonState.slice(0, 160));
// 只在**最后一条助手消息**里数「思考过程」：面板级计数会被历史消息干扰
check("思考过程只挂在最后一条消息上（不重复、不悬空）", await evalJs(`(() => {
  const panel = document.querySelector('[data-ai=panel]');
  const list = panel.querySelectorAll('.ai-asst');
  const last = list[list.length - 1];
  return last ? (last.textContent.match(/思考过程/g) || []).length : -1;
})()`) === 1);

// 公式切分的占位符回归：模型把 $...$ 当占位符写出来时，不该被当成空公式吃掉
const splitCase = String(await evalJs(`JSON.stringify({
  placeholder: window.__mfAi.splitMath("行内 $...$ 与 $$...$$"),
  real: window.__mfAi.splitMath("取 $x^2+1$ 的导数")
})`));
const splitObj = (() => { try { return JSON.parse(splitCase); } catch { return {}; } })();
const flatPlaceholder = (splitObj.placeholder || []).map((t) => t.value).join("");
check("$...$ 占位符原样保留（不当空公式）",
  flatPlaceholder === "行内 $...$ 与 $$...$$", JSON.stringify(flatPlaceholder));
check("真公式仍然被摘出来交给 KaTeX", /"kind":"math"/.test(splitCase) && /x\^2\+1/.test(splitCase), splitCase.slice(0, 160));

console.log("=== ②b markdown 渲染（且不引入注入面）===");
await runTurn("给我一段 markdown", /"doneReason":"stop"/);
const md = String(await evalJs(`(() => {
  const panel = document.querySelector('[data-ai=panel]');
  // ⚠ 必须取"最后一个"：querySelector 配 :last-of-type 返回的是文档里**第一个**
  // 满足"自己是父级里最后一个同类元素"的节点，也就是最早那条消息，不是最新那条。
  const all = panel.querySelectorAll('[data-ai=markdown]');
  const last = all[all.length - 1];
  if (!last) return JSON.stringify({ none: true });
  return JSON.stringify({
    strong: [...last.querySelectorAll('strong')].map(e => e.textContent.trim()),
    em: [...last.querySelectorAll('em')].map(e => e.textContent.trim()),
    strike: [...last.querySelectorAll('s')].map(e => e.textContent.trim()),
    code: [...last.querySelectorAll('code')].map(e => e.textContent.trim()),
    li: [...last.querySelectorAll('li')].map(e => e.textContent.trim()),
    h: [...last.querySelectorAll('h3')].map(e => e.textContent.trim()),
    pre: last.querySelectorAll('pre').length,
    quote: last.querySelectorAll('blockquote').length,
    table: last.querySelectorAll('table').length,
    th: [...last.querySelectorAll('th')].map(e => e.textContent.trim()),
    katex: last.querySelectorAll('.katex').length,
    linkHref: (last.querySelector('a.md-link') || {}).getAttribute ? last.querySelector('a.md-link').getAttribute('href') : '',
    unsafeLinks: last.querySelectorAll('.md-link-unsafe').length,
    imgs: last.querySelectorAll('img').length,
    scripts: last.querySelectorAll('script').length,
    escapedHtml: last.innerHTML.includes('&lt;img') && last.innerHTML.includes('&lt;script'),
    rawText: last.textContent.includes('<img src=x onerror=alert(1)>')
  });
})()`));
const mdObj = (() => { try { return JSON.parse(md); } catch { return {}; } })();
check("粗体渲染成 <strong>", Array.isArray(mdObj.strong) && mdObj.strong.includes("粗体"), md.slice(0, 80));
check("斜体/删除线渲染", (mdObj.em || []).includes("斜体") && (mdObj.strike || []).includes("删除"), md.slice(0, 80));
check("行内代码渲染成 <code>", (mdObj.code || []).includes("行内代码"));
check("无序列表渲染成 <li>", (mdObj.li || []).includes("无序甲") && (mdObj.li || []).includes("无序乙"));
check("有序列表也在（甲/乙）", (mdObj.li || []).includes("有序甲"));
check("标题渲染成 <h3>", (mdObj.h || []).includes("标题一"));
check("围栏代码块渲染成 <pre>", mdObj.pre >= 1, String(mdObj.pre));
check("代码块里的 $ 不被当公式（literal）", (mdObj.code || []).some((c) => c.includes("$这个不该被当公式$")), JSON.stringify(mdObj.code || []).slice(0, 80));
check("引用渲染成 <blockquote>", mdObj.quote >= 1);
check("表格渲染成 <table> 且有表头", mdObj.table >= 1 && (mdObj.th || []).includes("量"), JSON.stringify(mdObj.th || []));
check("公式仍交给 KaTeX（表格单元里的 $x$ 也算）", mdObj.katex >= 2, String(mdObj.katex));
check("$...$ 占位符在正文里原样显示", String(await evalJs(`document.querySelector('[data-ai=panel]').textContent.includes('占位符 $...$')`)) === "true");
check("安全链接可点但 href 正确", String(mdObj.linkHref || "").startsWith("https://example.com"), String(mdObj.linkHref));
check("危险协议链接不生成 <a>", mdObj.unsafeLinks >= 1);
check("模型写的 HTML **没有**变成元素（img/script 数量为 0）", mdObj.imgs === 0 && mdObj.scripts === 0,
  `img=${mdObj.imgs} script=${mdObj.scripts}`);
check("HTML 被转义成文本显示（不是被吃掉）", mdObj.escapedHtml === true && mdObj.rawText === true);

console.log("=== ②c 工具调用：AI 调引擎算，而不是自己算 ===");
// 先钉住"引导能指到面板里的控件"：教程用的是 v1 的语义 ID（ai_dialog.*），
// 界面必须真的挂上同名 data-tour —— 否则引导只显示一句"尚未实现"的假话（本轮修的就是这个）。
const tourTargets = JSON.parse(String(await evalJs(`JSON.stringify((() => {
  const out = {};
  for (const n of ["ai_dialog.input", "ai_dialog.send_button", "ai_dialog.context_label"]) {
    const el = document.querySelector('[data-tour="' + n + '"]');
    const r = el && el.getBoundingClientRect();
    out[n] = !!el && r.width > 0 && r.height > 0;
  }
  return out;
})())`)));
check("引导目标 ai_dialog.input 能定位到可见控件", tourTargets["ai_dialog.input"] === true, JSON.stringify(tourTargets));
check("引导目标 ai_dialog.send_button 能定位到可见控件", tourTargets["ai_dialog.send_button"] === true);
check("引导目标 ai_dialog.context_label 能定位到可见控件", tourTargets["ai_dialog.context_label"] === true);
// 工具层的边界先单独验一遍（不起对话，直接调）
const toolFacts = JSON.parse(String(await evalJs(`JSON.stringify({
  count: window.__mfAi.tools.count(),
  names: window.__mfAi.tools.schemas().map((t) => t.name),
  ok: window.__mfAi.tools.execute("engine_call", { fn: "solve_quadratic", args: { expr: "x^2-4", var: "x" } }, true),
  badfn: window.__mfAi.tools.execute("engine_call", { fn: "definitely_not_here", args: {} }, true),
  badargs: window.__mfAi.tools.execute("engine_call", { fn: "solve_quadratic", args: { exprr: "x^2-4" } }, true),
  privilege: window.__mfAi.tools.execute("engine_call", { fn: "SaveTextFile", args: { path: "C:/evil.txt" } }, true),
  notatool: window.__mfAi.tools.execute("file_write", { path: "C:/evil.txt" }, true),
  gated: window.__mfAi.tools.execute("engine_call", { fn: "gcd", args: { a: 12, b: 18 } }, false)
})`)));
check("引擎函数目录够大（424 个动作 → 唯一的函数名）", toolFacts.count >= 300, `${toolFacts.count} 个`);
check("只暴露两个工具（查 + 调），不是把 370 个函数都塞进 schema",
  JSON.stringify(toolFacts.names) === '["engine_find","engine_call"]', JSON.stringify(toolFacts.names));
check("engine_call 真的调到了引擎（x^2-4 的根由引擎给出）",
  toolFacts.ok.ok === true && /"value"/.test(toolFacts.ok.content) && /2/.test(toolFacts.ok.content), toolFacts.ok.content.slice(0, 110));
check("表外的函数名被拒（不会盲调）", toolFacts.badfn.ok === false && /引擎里没有/.test(toolFacts.badfn.content), toolFacts.badfn.content.slice(0, 110));
check("参数写错时回的是「缺什么/多了什么」并附上正确签名",
  toolFacts.badargs.ok === false && /缺少必填参数 expr/.test(toolFacts.badargs.content) && /solve_quadratic\(/.test(toolFacts.badargs.content),
  toolFacts.badargs.content.slice(0, 150));
check("**工具只能碰引擎**：想调 SaveTextFile（能写文件）被拒", toolFacts.privilege.ok === false, toolFacts.privilege.content.slice(0, 90));
check("未注册的工具名被拒", toolFacts.notatool.ok === false && /没有这个工具/.test(toolFacts.notatool.content), toolFacts.notatool.content.slice(0, 90));
check("「发送引擎结果」关着时工具被拒（结果要回传给模型）",
  toolFacts.gated.ok === false && /发送引擎结果/.test(toolFacts.gated.content), toolFacts.gated.content.slice(0, 120));

// 端到端：模型先要工具 → 页面执行引擎 → 结果回传 → 模型收尾
const beforeToolReqs = (await fakeRequests()).length;
await runTurn("用工具算 x^2-4=0", /"doneReason":"stop"/);
const toolReqs = await fakeRequests();
const roundReqs = toolReqs.slice(beforeToolReqs);
check("工具轮里发起了两次请求（先要工具、拿到结果再回答）", roundReqs.length === 2, `实际 ${roundReqs.length} 次`);
const secondBody = roundReqs[1]?.body || {};
const toolMsgs = (secondBody.messages || []).filter((m) => m.role === "tool");
check("第二次请求里带了 role:tool 的消息", toolMsgs.length === 1, JSON.stringify((secondBody.messages || []).map((m) => m.role)));
check("**回传给模型的是引擎的输出**（含引擎算出的两个根）",
  /"ok":true/.test(String(toolMsgs[0]?.content)) && /2/.test(String(toolMsgs[0]?.content)), String(toolMsgs[0]?.content).slice(0, 130));
check("请求里确实声明了工具（tools 字段）", Array.isArray(secondBody.tools) && secondBody.tools.length === 2,
  JSON.stringify((secondBody.tools || []).map((t) => t.function?.name)));
const assistantWire = (secondBody.messages || []).find((m) => m.role === "assistant" && m.tool_calls);
check("助手那条带 tool_calls（协议形状对得上）", !!assistantWire && assistantWire.tool_calls[0].function.name === "engine_call",
  JSON.stringify(assistantWire?.tool_calls || []).slice(0, 120));

// 界面：工具块挂在消息上，显示的是引擎结果
const toolUi = JSON.parse(String(await evalJs(`JSON.stringify((() => {
  const panel = document.querySelector('[data-ai=panel]');
  const blocks = [...panel.querySelectorAll('[data-ai^=tool-]')].filter((e) => !/tool-live/.test(e.getAttribute('data-ai')));
  return {
    count: blocks.length,
    text: blocks.map((b) => b.textContent.replace(/\\s+/g, ' ').trim()).join(' || ').slice(0, 300),
    live: panel.querySelectorAll('[data-ai=tools-live]').length,
    messageToolCalls: (window.__mfAi.messages().slice(-1)[0] || {}).toolCalls?.length || 0
  };
})())`)));
check("面板里渲染出了工具块", toolUi.count >= 1, toolUi.text.slice(0, 140));
check("工具块里是引擎的函数名与结果", /solve_quadratic/.test(toolUi.text), toolUi.text.slice(0, 160));
check("收尾后实时工具块消失（不重复）", toolUi.live === 0);
check("工具记录挂在消息上", toolUi.messageToolCalls === 1, String(toolUi.messageToolCalls));
const lastMsg = String(await evalJs(`JSON.stringify(window.__mfAi.messages().slice(-1)[0])`));
check("模型那句错的数字只是文本，工具块显示的才是引擎的值",
  /99/.test(lastMsg) && /2/.test(toolUi.text), "模型说 99，工具块给的是引擎的根");

// 坏例子与越权：模型必须看到拒绝原因
for (const [say, expect, label] of [
  ["用工具坏函数 算一下", /引擎里没有/, "表外函数"],
  ["用工具错参数 算一下", /缺少必填参数/, "参数写错"],
  ["用工具越权 试一下", /引擎里没有/, "越权调用非引擎函数"],
]) {
  const before = (await fakeRequests()).length;
  await runTurn(say, /"doneReason":"stop"/);
  const reqs = (await fakeRequests()).slice(before);
  const toolMsg = (reqs[1]?.body?.messages || []).find((m) => m.role === "tool");
  const recs = JSON.parse(String(await evalJs(`JSON.stringify((window.__mfAi.messages().slice(-1)[0] || {}).toolCalls || [])`)));
  check(`${label}：工具被拒且原因回给了模型`, expect.test(String(toolMsg?.content)) && recs[0]?.ok === false,
    String(toolMsg?.content).slice(0, 120));
  check(`${label}：界面上标成失败`, JSON.parse(String(await evalJs(`JSON.stringify(
    !!document.querySelector('[data-ai=panel] .ai-tool.bad'))`))) === true);
}

// 轮次上限：模型一直要工具也必须被截断
const beforeLoop = (await fakeRequests()).length;
await runTurn("用工具循环 算个没完", /"doneReason":"stop"/);
const loopReqs = (await fakeRequests()).length - beforeLoop;
check(`工具循环被轮次上限截断（最多 ${String(await evalJs(`window.__mfAi.tools.maxRounds()`))} 轮）`,
  loopReqs <= Number(await evalJs(`window.__mfAi.tools.maxRounds()`)), `实际发了 ${loopReqs} 次请求`);
const loopNotice = String(await evalJs(`JSON.stringify(window.__mfAi.state().notices)`));
check("被截断时给出了说明（不是默默停住）", /已达上限|上限/.test(loopNotice), loopNotice.slice(0, 130));

// 隐私闸门（端到端）
await evalJs(`window.__mfAi.configure({ sendResult: false })`);
const beforeGate = (await fakeRequests()).length;
await runTurn("用工具算 1+1", /"doneReason":"stop"/);
const gatedMsg = ((await fakeRequests()).slice(beforeGate)[1]?.body?.messages || []).find((m) => m.role === "tool");
const gatedRec = JSON.parse(String(await evalJs(`JSON.stringify((window.__mfAi.messages().slice(-1)[0] || {}).toolCalls || [])`)));
check("关掉「发送引擎结果」后：工具被拒且明确告诉模型原因",
  /发送引擎结果/.test(String(gatedMsg?.content)) && gatedRec[0]?.ok === false, String(gatedMsg?.content).slice(0, 120));
await evalJs(`window.__mfAi.configure({ sendResult: true })`);

// ── 分步显示的**渲染层**：把工具记录按步骤排开（数值全部来自引擎）──
console.log("=== ②d 分步显示（渲染层：步骤 = AI 调引擎的记录）===");
// 先跑一轮**成功的**工具调用再打开步骤：上面 ②c 的最后几条是隐私闸门/轮次上限的失败场景，
// 直接取"最后一个"会拿到被拦住的那条（第一版就是这么错的）。
await evalJs(`window.__mfAi.configure({ sendResult: true, toolsEnabled: true })`);
await runTurn("用工具算 x^2-4=0", /"doneReason":"stop"/);
const stepsBtn = await evalJs(`(() => {
  const b = [...document.querySelectorAll('[data-ai^=view-steps-]')].pop();
  if (!b) return "无";
  b.click();
  return "点了";
})()`);
check("回答上有「查看步骤」按钮", stepsBtn === "点了", stepsBtn);
check("步骤视图打开了", await waitTrue(`!!document.querySelector('[data-steps=view]')`, 6000));
check("**教程目标 step_viewer.content 能定位到可见内容**（本轮的引导接线也覆盖了它）",
  await evalJs(`(() => {
    const el = document.querySelector('[data-tour="step_viewer.content"]');
    const r = el && el.getBoundingClientRect();
    return !!el && r.width > 0 && r.height > 0;
  })()`) === true);
const stepFacts = JSON.parse(String(await evalJs(`JSON.stringify({
  count: document.querySelectorAll('[data-steps^=step-]:not([data-steps=view])').length,
  fn0: (document.querySelector('[data-steps=fn-0]') || {}).textContent || "",
  value0: (document.querySelector('[data-steps=value-0]') || {}).textContent || "",
  args0: (document.querySelector('[data-steps=args-0]') || {}).textContent || "",
  prose: !!document.querySelector('.sv-prose'),
  okState: (document.querySelector('[data-steps=step-0] .sv-state') || {}).textContent || ""
})`)));
check("步骤被编号列出（≥1 步）", stepFacts.count >= 1, `实际 ${stepFacts.count} 步`);
check("步骤里写着用的是哪个引擎函数", stepFacts.fn0 === "solve_quadratic", stepFacts.fn0);
check("**步骤的结果是引擎的值**（x^2-4 的根，不是模型那句 99）",
  /2/.test(stepFacts.value0) && !/99/.test(stepFacts.value0), stepFacts.value0.slice(0, 90));
check("步骤里带着传入参数", /expr/.test(stepFacts.args0), stepFacts.args0.slice(0, 70));
check("标出这一步「引擎已算出」", /引擎已算出/.test(stepFacts.okState), stepFacts.okState);
check("步骤下面是 AI 的说明（模型措辞与引擎数值分开显示）", stepFacts.prose === true);
// 关闭后目标应消失（弹层不是常驻的）
await evalJs(`(() => { const b = document.querySelector('[data-steps=close]'); if (b) b.click(); return true; })()`);
check("关闭后步骤视图消失", await waitTrue(`!document.querySelector('[data-steps=view]')`, 6000));

// ── 由别处发起（计算页的「查看步骤」走的就是这条通路）──
console.log("=== ②e 由别处发起分步讲解（结果对话框的路径）===");
await evalJs(`window.__mfAi.requestTurn("用工具算 x^2-4=0", { autoSteps: true })`);
check("请求会把 AI 面板打开（App 监听 aiRequest）", await waitTrue(`!!document.querySelector('[data-ai=panel]')`, 6000));
await waitIdle(60000);
const lastUser = String(await evalJs(`(() => {
  const m = [...window.__mfAi.messages()].reverse().find((x) => x.role === "user");
  return m ? m.content : "";
})()`));
check("请求内容成了用户那条消息（预填并自动发出，用户不用再点一次发送）", /x\^2-4/.test(lastUser), lastUser.slice(0, 80));
check("**收尾后自动弹出步骤**（这就是「查看步骤」要的结果）", await waitTrue(`!!document.querySelector('[data-steps=view]')`, 8000));
await evalJs(`(() => { const b = document.querySelector('[data-steps=ok]'); if (b) b.click(); return true; })()`);

// ── 计算页结果对话框里的「查看步骤」真的接上了（不是死按钮）──
console.log("=== ②f 计算页的结果对话框 → 查看步骤 ===");
// 用**工作区恢复**把表达式放进计算块：直接给 math-field 赋值不可靠（Vue 的 v-model 不一定会跟上），
// 这条配方在 cdp-workspace 里已经用了很久。
await evalJs(`(() => {
  window.__mfWorkspace.setPage("/calc/algebra", { kind: "calc", blocks: [{ id: "b1", expr: "x^2-4", mode: "因式分解", operation: "因式分解" }] });
  location.hash = "#/";
  return true;
})()`);
await sleep(600);
await evalJs(`location.hash = "#/calc/algebra"`);
check("计算块被恢复（表达式在）", await waitTrue(`(() => { const f = document.querySelector('math-field.cb-input'); return !!f && f.value === "x^2-4"; })()`, 12000));
await evalJs(`(() => { const b = document.querySelector('button.cb-calc'); if (b) b.click(); return true; })()`);
check("算完弹出结果对话框（v1 的 showResultDialog 对应物）",
  await waitTrue(`!!document.querySelector('[data-tour="result_dialog.steps_button"]')`, 12000));
const beforeStepsReq = String(await evalJs(`JSON.stringify(window.__mfAi.state())`));
await evalJs(`(() => { const b = document.querySelector('[data-tour="result_dialog.steps_button"]'); if (b) b.click(); return true; })()`);
await waitTrue(`!!document.querySelector('[data-ai=panel]')`, 8000);
const askedForSteps = String(await evalJs(`(() => {
  const msgs = window.__mfAi.messages();
  const m = [...msgs].reverse().find((x) => x.role === "user");
  return m ? m.content : "";
})()`));
check("**「查看步骤」不再是死按钮**：它请 AI 分步讲解（并带上题目）",
  /分步/.test(askedForSteps) && /x\^2-4/.test(askedForSteps), askedForSteps.replace(/\n/g, " ").slice(0, 120));
await waitIdle(60000);
check("这一轮也自动弹出了步骤视图", await waitTrue(`!!document.querySelector('[data-steps=view]')`, 8000));
await evalJs(`(() => { const b = document.querySelector('[data-steps=ok]'); if (b) b.click(); return true; })()`);

console.log("=== ③ 停止（流式进行时按下）===");
await resetTurn();
const sendSlow = String(await evalJs(`JSON.stringify(window.__mfAi.send("慢速"))`));
check("慢速请求被受理", /"ok":true/.test(sendSlow), sendSlow.slice(0, 80));
check("慢速流已开始", await waitRunning() && await waitTrue(`window.__mfAi.state().stream.length > 0`, 8000));
// 真·流式：长度必须在增长（不是一次性把整段贴上去）
const len1 = Number(await evalJs(`window.__mfAi.state().stream.length`));
await sleep(900);
const len2 = Number(await evalJs(`window.__mfAi.state().stream.length`));
check("流式是**逐字增长**的（不是一次性渲染）", len2 > len1, `${len1} → ${len2}`);
const stopRes = await evalJs(`JSON.stringify(window.__mfAi.stop())`);
check("停止被受理", /"ok":true/.test(String(stopRes)), String(stopRes).slice(0, 80));
check("停止后 running=false", await waitIdle(8000));
const st2 = await evalJs(`JSON.stringify(window.__mfAi.state())`);
check("结束原因是 aborted（不是 error）", /"doneReason":"aborted"/.test(String(st2)) || /"doneReason":"stop"/.test(String(st2)), String(st2).slice(0, 160));

console.log("=== ④ 七类异常：不崩、有原因、还能继续 ===");

/**
 * 发一轮并等它收尾，然后断言状态符合预期。
 *
 * 两个坑都在这里堵住：
 *   ① **不能用"先看到 running 再等 idle"当必要条件** —— 有的场景（无 usage）
 *      毫秒级就结束了，第一次轮询时它已经收尾，"没看到 running"会被误判成失败；
 *   ② 反过来也不能只看"当前是 idle"：上一轮的陈旧状态会让断言假装通过。
 * 所以用 `startedAt` 是否变新来确认"这份状态属于刚发出去的这一轮"。
 */
async function runTurn(prompt, expect) {
  await resetTurn();
  const before = await evalJs(`window.__mfAi.state().startedAt`);
  const res = String(await evalJs(`JSON.stringify(window.__mfAi.send(${JSON.stringify(prompt)}))`));
  if (!/"ok":true/.test(res)) return { ok: false, reason: "发送被拒：" + res.slice(0, 120), state: "" };

  await waitRunning(6000);                 // 尽力观察，不作为必要条件
  const idle = await waitIdle(30000);
  const st = String(await evalJs(`JSON.stringify(window.__mfAi.state())`));
  const fresh = JSON.parse(st).startedAt !== before;
  return { ok: idle && fresh && expect.test(st), reason: fresh ? st.slice(0, 180) : "状态仍是上一轮的（startedAt 未变）", state: st };
}

for (const [prompt, expect, label] of [
  ["这轮会 401", /"kind":"http"[^}]*"status":401|"status":401/, "密钥错（401）→ http/401"],
  ["这轮会 500", /"kind":"http"[^}]*"status":500|"status":500/, "服务端 500 → http/500"],
  ["给我坏JSON", /"code":"bad_sse_data"/, "坏 SSE data → bad_sse_data 降级（不算失败）"],
  ["无usage 的回复", /"code":"missing_usage"/, "无 usage 尾包 → missing_usage 降级"],
  ["无DONE 的流", /"code":"truncated_stream"/, "无 [DONE]/finish_reason → truncated_stream 降级"],
  ["断开 吧", /"kind":"network"/, "流被掐断 → network 错误（与「没开始」区分开）"],
]) {
  const r = await runTurn(prompt, expect);
  check(label, r.ok, r.reason);
}

// 连接失败：把端点指到一个没人监听的端口
await resetTurn();
await evalJs(`window.__mfAi.configure({ baseUrl: "http://127.0.0.1:9/v1" })`);
{
  const r = await runTurn("连不上", /"kind":"network"/);
  check("端点连不上 → network 错误且不崩", r.ok, r.reason);
}

// 超时：挂起场景 + 5 秒超时（这一轮确实会跑满 5 秒，所以 running 是能观察到的）
await resetTurn();
await evalJs(`window.__mfAi.configure({ baseUrl: ${JSON.stringify(BASE)}, timeoutSec: 5 })`);
{
  const r = await runTurn("挂起 吧", /"doneReason":"timeout"/);
  check("挂起 → 超时收尾（done=timeout，且与手动取消区分开）", r.ok, r.reason);
}

// 异常之后还能正常聊：证明状态没被搞坏（读**消息**，因为收尾后实时缓冲会被清空）
await evalJs(`window.__mfAi.configure({ baseUrl: ${JSON.stringify(BASE)}, timeoutSec: 20 })`);
await resetFake();
{
  const r = await runTurn("恢复正常", /"doneReason":"stop"/);
  const lastMsg = String(await evalJs(`(window.__mfAi.messages().slice(-1)[0] || {}).content || ""`));
  check("异常之后仍能正常对话", r.ok && lastMsg.includes("收到"), r.ok ? lastMsg.slice(0, 60) : r.reason);
}

console.log("=== ⑤ 隐私：关掉的开关真的没发出去 ===");
// 前端组装逻辑（不必真发）：sendCode 关掉时，控制台代码不进消息数组
const builtNoCode = String(await evalJs(`JSON.stringify(window.__mfAi.build({
  userText: "看看这段代码", context: { page: "/tools/console", code: "SECRET_CODE_XYZ", lang: "python" }
}))`));
check("sendCode=off 时控制台代码不进消息", !builtNoCode.includes("SECRET_CODE_XYZ"));

// 真实请求体：关掉历史时，第二个请求不该带上第一轮的助手回复
await resetTurn();
await evalJs(`window.__mfAi.configure({ sendHistory: false })`);
await resetFake();
await evalJs(`window.__mfAi.send("第一轮")`);
await waitIdle();
await evalJs(`window.__mfAi.send("第二轮")`);
await waitIdle();
let reqs = await fakeRequests();
const last = reqs[reqs.length - 1];
check("关掉历史：第二个请求没有把整段对话带上", !!last && last.messageCount <= 3,
  `消息数 ${last?.messageCount}，roles=${JSON.stringify(last?.roles)}`);
check("请求里带了密钥（否则端点会 401）", !!last?.authPresent, last ? "authTail=" + last.authTail : "无请求");
check("假端点收到的认证尾部与设置的一致", !!last && last.authTail === KEY.slice(-4), last?.authTail || "");
// 架构对照：这条请求是**页面**发的（浏览器跨源 fetch 一定带 Origin，
// 而旧架构里那个 .NET HttpClient 不会带）—— 与"push log 里没有 ai.* 话题"互相印证。
{
  const pageOrigin = String(await evalJs(`location.origin`));
  check("请求确由**页面**发出（Origin 头 = 页面 origin）",
    !!last?.origin && last.origin === pageOrigin,
    `origin=${last?.origin || "（无）"} 页面=${pageOrigin}`);
}

// 打开历史后，第二个请求应该多出第一轮的往返
await resetTurn();
await evalJs(`window.__mfAi.configure({ sendHistory: true, historyTurns: 6 })`);
await resetFake();
await evalJs(`window.__mfAi.send("第一轮")`);
await waitIdle();
await evalJs(`window.__mfAi.send("第二轮")`);
await waitIdle();
reqs = await fakeRequests();
const last2 = reqs[reqs.length - 1];
check("打开历史：第二个请求带上了历史（消息数变多）", !!last2 && last2.messageCount > (last?.messageCount ?? 0),
  `${last?.messageCount} → ${last2?.messageCount}`);

console.log("=== ⑥ 硬约束：AI 不得成为计算源 ===");
// 先在计算页算出引擎值（按 data-key 定位按键，读 .lcd 里的结果——与 cdp-basic-calc 一致）
await evalJs(`location.hash = "#/calc/basic"`);
await waitTrue(`!!document.querySelector('.keypad .key')`, 12000);
// ⚠ 先清空显示再按：别的用例可能在这个页面留过内容（本轮的 cdp-update 留下 "7+8"，
// 于是这里的 "1+1" 变成 "7+81+1=89"）。**不依赖上一条用例的收尾**才稳。
await evalJs(`window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))`);
await sleep(300);
const press = async (keys) => {
  for (const k of keys) {
    await evalJs(`(() => {
      const b = document.querySelector('.keypad .key[data-key=' + JSON.stringify(${JSON.stringify(k)}) + ']');
      if (b) b.click();
      return !!b;
    })()`);
    await sleep(140);
  }
  await sleep(600);
  return String(await evalJs(`((document.querySelector('.lcd .lcd-result') || {}).textContent || '').trim()`));
};
const engineVal = await press(["1", "+", "1", "="]);
check("引擎算出 1+1=2（作为对照基准）", engineVal === "2", engineVal);
// 假端点对默认请求回的就是 "1+1=3"（故意错的）
await resetTurn();
await evalJs(`window.__mfAi.configure({ sendHistory: false })`);
await evalJs(`window.__mfAi.send("1+1 等于几")`);
await waitIdle();
// 读**消息**：收尾后实时缓冲会被清空（stream 只在输出过程中有内容）
const aiText = String(await evalJs(`(window.__mfAi.messages().slice(-1)[0] || {}).content || ""`));
check("AI 回复里确实出现了那个错的等式（否则这条断言没有意义）", aiText.includes("1+1=3"), aiText.slice(0, 60));
const afterVal = String(await evalJs(`((document.querySelector('.lcd .lcd-result') || {}).textContent || '').trim()`));
check("AI 回复**没有**改写结果区（结果仍是引擎的值 2）", afterVal === engineVal && afterVal === "2",
  `引擎=${JSON.stringify(engineVal)} 之后=${JSON.stringify(afterVal)}`);

console.log("=== ⑦ 自检、连通性测试与设置页 ===");
// 「测试连接」以前是宿主发 + ai.test 推回来；现在也是页面自己发：
// 非流式、max_tokens=1、body 里只有一句 ping。
await resetFake();
const testRes = String(await evalJs(`(async () => JSON.stringify(await window.__mfAi.test()))()`));
check("连通性测试：页面自己发一次请求并成功",
  /"ok":true/.test(testRes) && /"status":200/.test(testRes), testRes.slice(0, 150));
{
  const tReq = (await fakeRequests()).slice(-1)[0];
  check("连通性测试的请求体是 stream:false + max_tokens:1（不会顺手跑起一条流）",
    !!tReq && tReq.stream === false && tReq.body?.max_tokens === 1 &&
      (tReq.body?.messages || [])[0]?.content === "ping",
    JSON.stringify(tReq?.body || {}).slice(0, 170));
  check("连通性测试同样是页面的 fetch（Origin 头在）", !!tReq?.origin, tReq?.origin || "（无）");
}

// 自检现在全是**本地**检查（不联网、也不再有"宿主侧"的那几项）：
// 配置可解析 / 端点合法 / 密钥在不在 / 端点不退回内置站点。
const sc = String(await evalJs(`JSON.stringify(window.__mfAi.selfCheck())`));
check("自检的「配置文件可解析」通过", sc.includes('"name":"配置文件可解析","ok":true'), sc.slice(0, 200));
check("自检的「端点合法（只接受 http/https）」通过",
  sc.includes('"name":"端点合法（只接受 http/https）","ok":true'), sc.slice(0, 300));
check("自检的「密钥已配置」通过，且如实说是明文",
  sc.includes('"name":"密钥已配置（明文存 ai.json）","ok":true') && sc.includes("明文"), sc.slice(0, 400));
check("自检的「端点不退回内置站点」通过",
  sc.includes('"name":"端点不退回内置站点","ok":true'), sc.slice(0, 500));
check("自检整体 ok_all=true", sc.includes('"ok_all":true'), sc.slice(0, 500));
// 旧的四项随架构一起没了，不该再出现（留着就是"测试在验一个不存在的实现"）
check("自检里不再有宿主侧那几项（DPAPI / base64 转手 / 中继闸门 / 配置目录可写）",
  !/密钥保护（DPAPI）/.test(sc) && !/base64/.test(sc) && !/中继路径闸门/.test(sc) && !/配置目录可写/.test(sc));

await evalJs(`location.hash = "#/settings?group=ai"`);
check("设置里有 AI 分组", await waitTrue(`!!document.querySelector('[data-setting="ai.enabled"]')`, 12000));
check("AI 分组显示密钥状态（只说在不在）", await waitTrue(`(document.querySelector('[data-ai=key-state]')?.textContent || '').includes('已配置')`));
// 文案必须**如实**：密钥是明文写在 ai.json 里、页面直连时会用它 ——
// 不能再出现"宿主侧保管 / 页面拿不到 / DPAPI 保护"这类旧说法（它们现在是假的）
check("密钥那一栏如实说是明文（不再暗示受保护）", await evalJs(`(() => {
  const el = document.querySelector('[data-setting="ai.apiKey"]');
  const t = el ? el.textContent : "";
  return t.includes("明文") && !/页面拿不到/.test(t) && !/DPAPI/.test(t) && !/宿主/.test(t);
})()`) === true, String(await evalJs(`document.querySelector('[data-setting="ai.apiKey"]')?.textContent?.slice(0,120)`)));
check("密钥输入框是 password 类型（不明文展示）",
  await evalJs(`document.querySelector('[data-ai-set=apiKey]')?.type === "password"`) === true);
check("隐私开关齐全（表达式/结果/历史/代码）",
  await evalJs(`["sendExpr","sendResult","sendHistory","sendCode"].every(k => !!document.querySelector('[data-ai-set="' + k + '"]'))`) === true);
check("设置项 id 与 catalog 对齐（ai.privacy 存在）", await waitTrue(`!!document.querySelector('[data-setting="ai.privacy"]')`));

// 设置页上的那个「测试」按钮：点下去必须真的发一次、并把结果落进界面
// （aiTestState 的形状与显示链路：{testing, result} → data-ai=test-line）
await resetFake();
await evalJs(`(() => { const b = document.querySelector('[data-ai=test]'); if (b) b.click(); return true; })()`);
check("「测试」按钮真的发出请求并在界面上显示结果",
  await waitTrue(`(document.querySelector('[data-ai=test-line]')?.textContent || '').includes('连接正常')`, 12000),
  String(await evalJs(`document.querySelector('[data-ai=test-line]')?.textContent || "（没有结果行）"`)));
check("「测试」的这一轮也是页面自己发的", (await fakeRequests()).length >= 1);
// 按钮**不禁用**：没配好时点它也必须有结果（写清楚"为什么测不了"），
// 否则用户面对的是一个点不动的按钮、测试也查不到链路。
await evalJs(`window.__mfAi.configure({ enabled: false })`);
await sleep(300);
await evalJs(`(() => { const b = document.querySelector('[data-ai=test]'); if (b) b.click(); return true; })()`);
check("未启用时点「测试」也会给出原因（不是点不动）",
  await waitTrue(`/未启用/.test(document.querySelector('[data-ai=test-line]')?.textContent || '')`, 8000),
  String(await evalJs(`document.querySelector('[data-ai=test-line]')?.textContent || "（没有结果行）"`)));
await evalJs(`window.__mfAi.configure({ enabled: true })`);
await sleep(200);

console.log("=== ⑧ 面板可用性与不可用时的诚实提示 ===");
await evalJs(`location.hash = "#/calc/basic"`);
await waitTrue(`!!document.querySelector('.keypad .key')`, 12000);
await evalJs(`document.querySelector('[data-ai=open]').click()`);
check("顶栏 AI 按钮能打开面板", await waitTrue(`!!document.querySelector('[data-ai=panel]')`, 8000));
check("面板是抽屉而非模态（没有全屏遮罩）",
  await evalJs(`(() => { const p = document.querySelector('[data-ai=panel]'); return !!p && getComputedStyle(p).position === 'fixed'; })()`) === true);
// 关掉 AI：面板仍能开，但会说明原因
await evalJs(`window.__mfAi.configure({ enabled: false })`);
await sleep(300);
check("关掉 AI 后仍能打开面板并说明原因",
  await evalJs(`(document.querySelector('[data-ai=blocked]')?.textContent || '').length > 0`) === true);
await evalJs(`window.__mfAi.configure({ enabled: true })`);
await sleep(200);
check("重新启用后阻塞提示消失", await evalJs(`!document.querySelector('[data-ai=blocked]')`) === true);

console.log("=== ⑨ 旧版密钥迁移（只有 DPAPI 密文时不许假装有密钥）===");
// 为什么放在**最后**：这一节会把配置写成"旧版样子"（只有 apiKeyProtected、没有明文 apiKey），
// 一旦这里出问题，前面 150 多项不该跟着一起变红 —— 上一版放在中间，就是这样连锁挂了 8 条。
//
// 为什么**不直接读写宿主桥**：写配置走的是正常 API（configure / setKey），与全流程其它地方
// 同一种调用姿势。上一版在用例里直接 `sys.StoreRead/StoreWrite` 一套自己的写法，
// 出问题时没法区分"功能坏了"和"姿势不对"，实测就是在那一节之后页面不再响应 CDP。
await evalJs(`location.hash = "#/settings?group=ai"`);
check("迁移一节回到设置页", await waitTrue(`!!document.querySelector('[data-setting="ai.apiKey"]')`, 12000));

await evalJs(`window.__mfAi.clearKey()`);
const legacy = String(await evalJs(`JSON.stringify((() => {
  const write = window.__mfAi.configure({ apiKeyProtected: "AQAAANCMND8BFdERjHoAwE_Cl-sBAAAA" });
  const c = window.__mfAi.info();
  return {
    write: write, hasKey: c.hasKey, keySource: c.keySource, legacy: c.legacyProtectedKey,
    hosted: window.__mfAi.hosted(), note: c.keyNote,
  };
})())`));
check("旧版密文密钥：配置写入成功", /"ok":true/.test((legacy.match(/"write":\{[^}]*\}/) || [""])[0]), legacy.slice(0, 200));
check("旧版密文密钥：不假装有密钥、不自称就绪",
  /"hasKey":false/.test(legacy) && /"keySource":"none"/.test(legacy) && /"legacy":true/.test(legacy) && /"hosted":false/.test(legacy),
  legacy.slice(0, 220));
check("旧版密文密钥：给的是「重填一次」的说明（不是'已配置'）",
  /"note":"[^"]*重填/.test(legacy), (legacy.match(/"note":"[^"]*"/) || [""])[0]);
check("旧版密文密钥：脱敏视图里没有密文本身", !/AQAAANCMND8BFdERjHoAwE/.test(legacy));
check("旧版密文密钥：设置页如实提示「重填一次」",
  await waitTrue(`(document.querySelector('[data-ai=key-note]')?.textContent || '').includes('重填')`, 8000),
  String(await evalJs(`document.querySelector('[data-ai=key-note]')?.textContent || "（没有提示行）"`)));
check("旧版密文密钥：密钥状态那一行也说清了（未配置，不是已配置）",
  await waitTrue(`/未配置/.test(document.querySelector('[data-ai=key-state]')?.textContent || '')`, 6000));

// 重填一次（这就是迁移动作）：状态必须立刻恢复，提示必须消失
await evalJs(`window.__mfAi.setKey(${JSON.stringify(KEY)})`);
check("重填一次后立刻恢复就绪", (await evalJs(`window.__mfAi.hosted()`)) === true);
check("重填后提示消失", await waitTrue(`!document.querySelector('[data-ai=key-note]')`, 6000));

/* ── 收尾：清掉密钥与对话，避免污染用户环境（含迁移一节写进去的假密文占位符）── */
await evalJs(`window.__mfAi.clearKey(); window.__mfAi.clear(); window.__mfAi.configure({ enabled: false, baseUrl: "https://api.deepseek.com/v1", model: "deepseek-chat" })`);
{
  // 收尾必须**真的**落地：上一版残留成了 {enabled:true, baseUrl:127.0.0.1:8791, apiKeyProtected:"…"}
  const residue = String(await evalJs(`(() => {
    const sys = window.chrome.webview.hostObjects.sync.sys;
    const r = JSON.parse(sys.StoreRead("ai"));
    return r.ok ? r.json : "";
  })()`));
  check("收尾：ai.json 里既没有明文密钥、也没有假密文占位符",
    residue.length > 0 && !residue.includes("sk-fake") && !/"apiKeyProtected"\s*:\s*"[^"]+"/.test(residue),
    residue.replace(/\s+/g, " ").slice(0, 160));
  check("收尾：ai.json 里回到生产端点且 AI 关闭",
    /"baseUrl"\s*:\s*"https:\/\/api\.deepseek\.com\/v1"/.test(residue) && /"enabled"\s*:\s*false/.test(residue),
    residue.replace(/\s+/g, " ").slice(0, 160));
}

console.log(`RESULT|cdp-ai|${pass}|${fail}`);
try { ws.close(); } catch { /* 忽略 */ }
try { fake.kill(); } catch { /* 忽略 */ }
process.exit(fail === 0 ? 0 : 1);
