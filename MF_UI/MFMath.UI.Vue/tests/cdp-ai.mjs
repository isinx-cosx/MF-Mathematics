// cdp-ai.mjs — AI 助手端到端（宿主 AiBridge + 假端点 + 推送流式）
//
// 覆盖三层：
//   ① 配置与密钥：读写连通、**密钥不进渲染进程**（脱敏视图 + 配置文件里没有明文）；
//   ② 流式与七类异常：正常增量、停止、401/500、坏 SSE、无 usage、无 [DONE]、
//      连接失败、超时 —— 全都要求"不崩、有明确原因、下一轮还能继续"；
//   ③ 硬约束：**AI 不得成为计算源** —— 假端点故意回 "1+1=3"，
//      断言计算页的结果区仍然是引擎算出来的值（这条是整个 AI 功能的红线）。
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
const evalJs = async (expr, timeoutMs = 30000) => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }, timeoutMs);
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
 * 清掉可能残留的上一轮状态，并把配置指到假端点。
 * 两件事都要做：宿主侧取消连接（CancelAll）+ 页面侧复位 running 状态。
 * 只做前者时 JS 里可能还停在 running=true，下一次发送会被自己的单飞检查拒绝。
 */
async function resetTurn() {
  await evalJs(`(() => {
    const ai = window.chrome.webview.hostObjects.sync.ai;
    ai.CancelAll();
    try { window.__mfAi.stop(); } catch (e) { /* 没在跑就算了 */ }
    return true;
  })()`);
  await waitTrue(`window.__mfAi.state().running === false`, 5000);
  await sleep(200);
}

console.log("=== ① 配置与密钥（密钥不进渲染进程）===");

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

check("宿主提供 ai 桥", (await evalJs(`window.__mfAi.hosted()`)) === true);

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
check("密钥已设置", /"ok":true/.test(String(setKey)), String(setKey).slice(0, 120));

const info1 = String(await evalJs(`JSON.stringify(window.__mfAi.info())`));
check("脱敏视图：hasKey=true", /"hasKey":true/.test(info1));
check("脱敏视图：密钥来源说明存在", /"keySource":"(dpapi|memory)"/.test(info1), (info1.match(/"keySource":"[^"]*"/) || [""])[0]);
check("脱敏视图里**没有**密钥明文", !info1.includes(KEY));
check("脱敏视图里没有密文片段（apiKey 字段根本不存在）", !/"apiKeyProtected"/.test(info1));

// 配置文件里也不该有明文（sys.StoreRead 能读到密文，但读不出密钥）
const raw = String(await evalJs(`(() => {
  const sys = window.chrome.webview.hostObjects.sync.sys;
  const r = JSON.parse(sys.StoreRead("ai"));
  return r.ok ? r.json : "";
})()`));
check("落盘的 ai.json 里没有密钥明文", raw.length > 0 && !raw.includes(KEY), raw.length > 0 ? "" : "读不到文件");
check("落盘的 ai.json 用的是密文（apiKeyProtected）", /apiKeyProtected/.test(raw));

// 中继的闸门：页面**不能**让宿主把密钥发到任意地址（这是中继最危险的一面）
const evilAbsolute = String(await evalJs(`(() => {
  const ai = window.chrome.webview.hostObjects.sync.ai;
  return ai.Begin(JSON.stringify({ path: "https://evil.example/v1/chat/completions", body: {} }));
})()`));
check("中继拒绝绝对地址（密钥不会被发到任意地址）", /"ok":false/.test(evilAbsolute) && /"kind":"config"/.test(evilAbsolute),
  evilAbsolute.slice(0, 120));
const evilProtoRelative = String(await evalJs(`(() => {
  const ai = window.chrome.webview.hostObjects.sync.ai;
  return ai.Begin(JSON.stringify({ path: "//evil.example/v1", body: {} }));
})()`));
check("中继拒绝协议相对地址（//host）", /"ok":false/.test(evilProtoRelative), evilProtoRelative.slice(0, 90));
const evilDotDot = String(await evalJs(`(() => {
  const ai = window.chrome.webview.hostObjects.sync.ai;
  return ai.Begin(JSON.stringify({ path: "/../../x", body: {} }));
})()`));
check("中继拒绝 .. 穿越", /"ok":false/.test(evilDotDot), evilDotDot.slice(0, 90));

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
// 架构断言：字节是宿主经中继话题转过来的，解析在 TS 侧（不是宿主推"事件"）
const pushTopics = String(await evalJs(`JSON.stringify([...new Set(window.__mfPush.log().map(e => e.topic))])`));
check("走的是中继话题（ai.http + ai.raw*）", /"ai\.http"/.test(pushTopics) && /"ai\.raw"/.test(pushTopics), pushTopics.slice(0, 140));
check("宿主侧不再推 ai.delta（协议层只有一份 TS 实现）", !/"ai\.delta"/.test(pushTopics), pushTopics.slice(0, 140));

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

console.log("=== ⑦ 自检与设置页 ===");
const sc = String(await evalJs(`JSON.stringify(window.__mfAi.selfCheck())`));
check("自检有密钥保护一项", sc.includes("密钥保护"), sc.slice(0, 120));
check("自检的中继路径闸门通过（拒绝绝对地址）", /"name":"中继路径闸门（拒绝绝对地址）","ok":true/.test(sc), sc.slice(0, 260));
check("自检的字节转手无损（base64）通过", /"name":"响应字节转手无损（base64）","ok":true/.test(sc));
check("自检的配置目录可写通过", /"name":"配置目录可写","ok":true/.test(sc));

await evalJs(`location.hash = "#/settings?group=ai"`);
check("设置里有 AI 分组", await waitTrue(`!!document.querySelector('[data-setting="ai.enabled"]')`, 12000));
check("AI 分组显示密钥状态（只说在不在）", await waitTrue(`(document.querySelector('[data-ai=key-state]')?.textContent || '').includes('已配置')`));
check("密钥输入框是 password 类型（不明文展示）",
  await evalJs(`document.querySelector('[data-ai-set=apiKey]')?.type === "password"`) === true);
check("隐私开关齐全（表达式/结果/历史/代码）",
  await evalJs(`["sendExpr","sendResult","sendHistory","sendCode"].every(k => !!document.querySelector('[data-ai-set="' + k + '"]'))`) === true);
check("设置项 id 与 catalog 对齐（ai.privacy 存在）", await waitTrue(`!!document.querySelector('[data-setting="ai.privacy"]')`));

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

/* ── 收尾：清掉密钥与对话，避免污染用户环境 ── */
await evalJs(`window.__mfAi.clearKey(); window.__mfAi.clear(); window.__mfAi.configure({ enabled: false, baseUrl: "https://api.deepseek.com/v1", model: "deepseek-chat" })`);

console.log(`RESULT|cdp-ai|${pass}|${fail}`);
try { ws.close(); } catch { /* 忽略 */ }
try { fake.kill(); } catch { /* 忽略 */ }
process.exit(fail === 0 ? 0 : 1);
