// 推送通道（宿主 → 页面）端到端验证
//
// 这条通道是"宿主主动说话"的唯一路径，出问题时的现象是"界面一直不更新"，
// 而最难判断的正是"宿主没发"还是"页面没收到"。所以这里按三段验证：
//   ① 通道在不在：`push` 桥 + Info() 的 ready
//   ② 往返通不通：push.Emit → 页面收到 → 信封形状（topic/seq/ts/payload）齐全
//   ③ 真实生产者：控制台跑一段代码，宿主主动推 console.run（阶段 + 结束）
//   ④ 真实生产者：组件安装时推 component.install（收到一条就取消安装，不真装完）
//
// 注：宿主对象不能被 CDP 按值序列化，所有宿主调用都在页面里先 String()/JSON.stringify()。
// 用法: node cdp-push.mjs   （宿主需带 --remote-debugging-port=9222 启动）
import { existsSync } from "node:fs";
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
async function waitTrue(expr, timeoutMs = 8000, stepMs = 100) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    if ((await evalJs(expr)) === true) return true;
    await sleep(stepMs);
  }
  return false;
}

console.log("=== ① 通道可用性 ===");
const hasHook = await evalJs(`!!(window.__mfPush && window.__mfPush.info)`);
check("页面侧已挂上推送监听（lib/push.js 的 initPush）", hasHook === true);
const hostInfoRaw = await evalJs(`window.chrome.webview.hostObjects.sync.push.Info()`);
let hostInfo = null;
try { hostInfo = JSON.parse(hostInfoRaw); } catch { hostInfo = null; }
check("宿主 push 桥在线（PushHub 已挂上 CoreWebView2）", !!hostInfo && hostInfo.ready === true,
  hostInfo ? `sent=${hostInfo.sent} failed=${hostInfo.failed}` : String(hostInfoRaw).slice(0, 60));

const before = JSON.parse(await evalJs(`JSON.stringify(window.__mfPush.state())`));

console.log("=== ② JS → 宿主 → JS 往返（信封形状）===");
const emitRes = await evalJs(`JSON.stringify(window.__mfPush.emit("test.echo", {hello:"world", n:42}))`);
let emit = null;
try { emit = JSON.parse(emitRes); } catch { emit = null; }
check("emit 被宿主接受", !!emit && emit.ok === true, emitRes);
const got = await waitTrue(`window.__mfPush.log().some(e => e.topic === "test.echo")`);
check("页面收到了自己触发的那条消息", got === true);
const env = JSON.parse(await evalJs(`JSON.stringify(window.__mfPush.log().filter(e => e.topic === "test.echo").pop() || null)`));
check("信封含 topic/seq/ts/payload 四项", !!env && typeof env.topic === "string" && typeof env.seq === "number"
  && typeof env.ts === "number" && env.payload && env.payload.hello === "world", JSON.stringify(env).slice(0, 120));
check("seq 单调递增（比上一条大）", !!env && typeof before.lastSeq === "number" && env.seq > before.lastSeq,
  `before=${before.lastSeq} now=${env.seq}`);
const after = JSON.parse(await evalJs(`JSON.stringify(window.__mfPush.state())`));
check("页面侧计数 +1", after.received === before.received + 1, `${before.received} → ${after.received}`);

console.log("=== ③ 真实生产者：控制台运行（console.run）===");
const runId = await evalJs(`String(window.chrome.webview.hostObjects.sync.con.Start("python", "print('push-check')", ""))`);
// 阶段推送（stage）会先到，这里要等的是**结束**那一条（event === "done"）
const gotStage = await waitTrue(`window.__mfPush.log().some(e => e.topic === "console.run" && e.payload && e.payload.runId === ${JSON.stringify(runId)} && e.payload.event === "stage")`, 30000);
check("运行开始时就有阶段推送", gotStage === true, "runId=" + runId);
const gotDone = await waitTrue(`window.__mfPush.log().some(e => e.topic === "console.run" && e.payload && e.payload.runId === ${JSON.stringify(runId)} && e.payload.event === "done")`, 30000);
check("宿主主动推了「跑完了」（不用轮询也知道）", gotDone === true);
const runEnv = JSON.parse(await evalJs(`JSON.stringify(window.__mfPush.log().filter(e => e.topic === "console.run" && e.payload && e.payload.runId === ${JSON.stringify(runId)} && e.payload.event === "done").pop() || null)`));
check("结束那条带 exitCode 与耗时",
  !!runEnv && runEnv.payload.exitCode === 0 && typeof runEnv.payload.elapsedMs === "number" && runEnv.payload.elapsedMs > 0,
  runEnv ? JSON.stringify(runEnv.payload).slice(0, 140) : "null");

console.log("=== ④ 真实生产者：组件安装（component.install）===");
const jobId = await evalJs(`String(window.chrome.webview.hostObjects.sync.con.Install("python"))`);
const gotJob = await waitTrue(`window.__mfPush.log().some(e => e.topic === "component.install" && e.payload && e.payload.jobId === ${JSON.stringify(jobId)})`, 20000);
check("安装开始即有进度推送", gotJob === true, "jobId=" + jobId);
const jobEnv = JSON.parse(await evalJs(`JSON.stringify(window.__mfPush.log().filter(e => e.topic === "component.install" && e.payload && e.payload.jobId === ${JSON.stringify(jobId)}).pop() || null)`));
check("进度推送带 percent 与 message",
  !!jobEnv && typeof jobEnv.payload.percent === "number" && typeof jobEnv.payload.message === "string",
  jobEnv ? JSON.stringify(jobEnv.payload).slice(0, 120) : "null");
// 只是验证"推送会来"，不真等它装完；但**必须等作业进入终态**再收工：
// 解压阶段不响应取消，直接杀掉宿主会留下 `<组件目录>.staging` 半成品
// （实测：留下 804 个文件 / 31.6 MB，还会让 cdp-console 的"不留半装状态"断言失败）。
await evalJs(`String(window.chrome.webview.hostObjects.sync.con.CancelInstall(${JSON.stringify(jobId)}))`);
const done = await waitTrue(`(() => {
  const raw = window.chrome.webview.hostObjects.sync.con.InstallStatus(${JSON.stringify(jobId)});
  try { return JSON.parse(raw).state !== "running"; } catch { return false; }
})()`, 120000, 500);
check("取消后作业会走到终态（不把半装状态留给下一个用例）", done === true);
// 暂存目录只能在文件系统上看（页面里没有这个信息），所以这里直接查盘
const staging = join(process.env.LOCALAPPDATA || "", "MFMath", "components", "python-3.13.15.staging");
check("没有留下 .staging 半成品（CleanStaging 生效）", !existsSync(staging), staging);

console.log("=== ⑤ 设置面板里的通道自检入口 ===");
await evalJs(`location.hash = "/settings?group=engine"; true`);
await sleep(700);
const rowThere = await waitTrue(`!!document.querySelector('[data-setting="engine.push"]')`);
check("设置 → 引擎里有「推送通道」这一行", rowThere === true);
const rowText = await evalJs(`(() => { const el = document.querySelector('[data-setting="engine.push"]'); return el ? el.textContent.replace(/\\s+/g, ' ') : ''; })()`);
check("行里同时显示宿主发出与本页收到两个计数", /宿主发出/.test(String(rowText)) && /本页收到/.test(String(rowText)), String(rowText).slice(0, 110));
// 点一下"发一条测试消息"：宿主 sent 应增加，页面 received 也应增加
const s0 = JSON.parse(await evalJs(`JSON.stringify(window.__mfPush.state())`));
await evalJs(`(() => {
  const row = document.querySelector('[data-setting="engine.push"]');
  for (const b of row.querySelectorAll('button')) if (b.textContent.includes('发一条测试消息')) { b.click(); return true; }
  return false;
})()`);
const gotTest = await waitTrue(`window.__mfPush.log().some(e => e.topic === "settings.test")`, 5000);
check("面板上的按钮真的发出了一条（宿主→页面）", gotTest === true);
const s1 = JSON.parse(await evalJs(`JSON.stringify(window.__mfPush.state())`));
check("计数随按钮增长", s1.received > s0.received, `${s0.received} → ${s1.received}`);
const hostAfter = JSON.parse(await evalJs(`window.chrome.webview.hostObjects.sync.push.Info()`));
check("宿主侧计数也在涨（两边能对上）", hostAfter.sent >= hostInfo.sent + 2, `${hostInfo.sent} → ${hostAfter.sent}`);
check("没有丢消息（seq 连续）", s1.gaps === 0, `gaps=${s1.gaps}`);

console.log(`RESULT|cdp-push|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
