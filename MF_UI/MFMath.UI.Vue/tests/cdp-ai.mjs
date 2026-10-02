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
 * 用宿主自己的 CancelAll（而不是 JS 里那个按 requestId 停的 stop）：后者在
 * requestId 不同步时停不到真正在跑的那一轮，会让下一轮被宿主的单飞检查拒绝。
 */
async function resetTurn() {
  await evalJs(`(() => { window.chrome.webview.hostObjects.sync.ai.CancelAll(); return true; })()`);
  await sleep(350);
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

console.log("=== ② 正常流式 ===");
await resetTurn();
await resetFake();
// 先把面板打开：后面几节都要断言 DOM（面板是 v-if 渲染的，不开就什么都查不到）
await evalJs(`document.querySelector('[data-ai=open]').click()`);
check("顶栏 AI 按钮能打开面板", await waitTrue(`!!document.querySelector('[data-ai=panel]')`, 8000));
const sent = await evalJs(`JSON.stringify(window.__mfAi.send("你好"))`);
check("发送被受理", /"ok":true/.test(String(sent)), String(sent).slice(0, 90));
check("这一轮真的开始了（running=true）", await waitRunning());
check("流式增量渲染到面板", await waitTrue(`window.__mfAi.state().stream.length > 0`, 8000));
check("本轮结束后 running=false", await waitIdle());
const st1 = await evalJs(`JSON.stringify(window.__mfAi.state())`);
check("usage 收到（假端点给了尾包）", /"inputTokens":42/.test(String(st1)), String(st1).slice(0, 120));
check("回复进入会话记录", await evalJs(`window.__mfAi.messages().some(m => m.role === "assistant")`) === true);
check("面板 DOM 里能看到正文", await waitTrue(`(document.querySelector('[data-ai=stream]')?.textContent || '').includes('收到') || document.querySelector('[data-ai=msgs]').textContent.includes('收到')`));

console.log("=== ③ 停止（流式进行时按下）===");
await resetTurn();
const sendSlow = String(await evalJs(`JSON.stringify(window.__mfAi.send("慢速"))`));
check("慢速请求被受理", /"ok":true/.test(sendSlow), sendSlow.slice(0, 80));
check("慢速流已开始", await waitRunning() && await waitTrue(`window.__mfAi.state().stream.length > 0`, 8000));
const stopRes = await evalJs(`JSON.stringify(window.__mfAi.stop())`);
check("停止被受理", /"ok":true/.test(String(stopRes)), String(stopRes).slice(0, 80));
check("停止后 running=false", await waitIdle(8000));
const st2 = await evalJs(`JSON.stringify(window.__mfAi.state())`);
check("结束原因是 aborted（不是 error）", /"doneReason":"aborted"/.test(String(st2)) || /"doneReason":"stop"/.test(String(st2)), String(st2).slice(0, 160));

console.log("=== ④ 七类异常：不崩、有原因、还能继续 ===");
async function scenario(prompt, expectKind, label, extra = () => true) {
  await resetTurn();
  const res = String(await evalJs(`JSON.stringify(window.__mfAi.send(${JSON.stringify(prompt)}))`));
  if (!/"ok":true/.test(res)) {
    check(label, false, "发送被拒：" + res.slice(0, 120));
    return res;
  }
  // 必须先看到"真的开始了"，否则"等它结束"会在陈旧状态上秒过
  if (!await waitRunning(8000)) {
    check(label, false, "这一轮没有进入 running 状态");
    return "";
  }
  const idle = await waitIdle(30000);
  const st = await evalJs(`JSON.stringify(window.__mfAi.state())`);
  const ok = idle && expectKind.test(String(st)) && extra(String(st));
  check(label, ok, String(st).slice(0, 180));
  return String(st);
}

await scenario("这轮会 401", /"kind":"http"[^}]*"status":401|"status":401/, "密钥错（401）→ http/401");
await scenario("这轮会 500", /"kind":"http"[^}]*"status":500|"status":500/, "服务端 500 → http/500");
await scenario("给我坏JSON", /"code":"bad_sse_data"/, "坏 SSE data → bad_sse_data 降级（不算失败）");
await scenario("无usage 的回复", /"code":"missing_usage"/, "无 usage 尾包 → missing_usage 降级");
await scenario("无DONE 的流", /"code":"truncated_stream"/, "无 [DONE]/finish_reason → truncated_stream 降级");
await scenario("断开 吧", /"kind":"network"/, "流被掐断 → network 错误（与「没开始」区分开）");

// 连接失败：把端点指到一个没人监听的端口
await resetTurn();
await evalJs(`window.__mfAi.configure({ baseUrl: "http://127.0.0.1:9/v1" })`);
const connRes = String(await evalJs(`JSON.stringify(window.__mfAi.send("连不上"))`));
const startedNet = /"ok":true/.test(connRes) ? await waitRunning(8000) : false;
const idleNet = startedNet ? await waitIdle(30000) : false;
const stNet = String(await evalJs(`JSON.stringify(window.__mfAi.state())`));
check("端点连不上 → network 错误且不崩", idleNet && /"kind":"network"/.test(stNet),
  startedNet ? stNet.slice(0, 160) : "发送被拒：" + connRes.slice(0, 100));

// 超时：挂起场景 + 5 秒超时
await resetTurn();
await evalJs(`window.__mfAi.configure({ baseUrl: ${JSON.stringify(BASE)}, timeoutSec: 5 })`);
const hangRes = String(await evalJs(`JSON.stringify(window.__mfAi.send("挂起 吧"))`));
const startedHang = /"ok":true/.test(hangRes) ? await waitRunning(8000) : false;
const idleTimeout = startedHang ? await waitIdle(25000) : false;
const stTimeout = String(await evalJs(`JSON.stringify(window.__mfAi.state())`));
check("挂起 → 超时收尾（done=timeout/aborted，不是一直挂着）",
  idleTimeout && /"doneReason":"(timeout|aborted)"/.test(stTimeout),
  startedHang ? stTimeout.slice(0, 160) : "发送被拒：" + hangRes.slice(0, 100));

// 异常之后还能正常聊：证明状态没被搞坏
await resetTurn();
await evalJs(`window.__mfAi.configure({ baseUrl: ${JSON.stringify(BASE)}, timeoutSec: 20 })`);
await resetFake();
const recRes = String(await evalJs(`JSON.stringify(window.__mfAi.send("恢复正常"))`));
const startedRec = /"ok":true/.test(recRes) ? await waitRunning(8000) : false;
check("异常之后仍能正常对话", startedRec && await waitIdle() && await evalJs(`window.__mfAi.state().stream.includes("收到")`) === true,
  startedRec ? "" : "发送被拒：" + recRes.slice(0, 100));

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
await waitRunning(); await waitIdle();
await evalJs(`window.__mfAi.send("第二轮")`);
await waitRunning(); await waitIdle();
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
await waitRunning(); await waitIdle();
await evalJs(`window.__mfAi.send("第二轮")`);
await waitRunning(); await waitIdle();
reqs = await fakeRequests();
const last2 = reqs[reqs.length - 1];
check("打开历史：第二个请求带上了历史（消息数变多）", !!last2 && last2.messageCount > (last?.messageCount ?? 0),
  `${last?.messageCount} → ${last2?.messageCount}`);

console.log("=== ⑥ 硬约束：AI 不得成为计算源 ===");
// 先在计算页算出引擎值（按 data-key 定位按键，读 .lcd 里的结果——与 cdp-basic-calc 一致）
await evalJs(`location.hash = "#/calc/basic"`);
await waitTrue(`!!document.querySelector('.keypad .key')`, 12000);
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
await waitRunning(); await waitIdle();
const aiText = String(await evalJs(`window.__mfAi.state().stream`));
check("AI 回复里确实出现了那个错的等式（否则这条断言没有意义）", aiText.includes("1+1=3"), aiText.slice(0, 60));
const afterVal = String(await evalJs(`((document.querySelector('.lcd .lcd-result') || {}).textContent || '').trim()`));
check("AI 回复**没有**改写结果区（结果仍是引擎的值 2）", afterVal === engineVal && afterVal === "2",
  `引擎=${JSON.stringify(engineVal)} 之后=${JSON.stringify(afterVal)}`);

console.log("=== ⑦ 自检与设置页 ===");
const sc = String(await evalJs(`JSON.stringify(window.__mfAi.selfCheck())`));
check("自检有密钥保护一项", sc.includes("密钥保护"), sc.slice(0, 120));
check("自检的 SSE 分帧（任意切分一致）通过", /"name":"SSE 分帧（任意切分一致）","ok":true/.test(sc), sc.slice(0, 220));
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
