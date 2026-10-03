// cdp-update.mjs — 更新链端到端（宿主 UpdateBridge + 设置→更新 + 顶栏提示）
//
// 本轮定的形态：**只提示 + 显示 sha256 + 把下载交给浏览器**。软件不自动下载、更不执行安装包。
// 所以这里断言的重点不是"能下载"，而是：
//   ① **站点更旧时不提示更新**（本轮最重要的陷阱：站点还报 1.2.0，若按"版本不同即有新版"，
//      v2 用户会被引去下载 v1 安装包 —— 那是降级）；
//   ② 站点没给校验值时**如实说没有 + 原因**，不显示成"已校验"；
//   ③ 打开链接只放行 http/https（用例**不点真按钮**，免得在跑测试时弹出用户的浏览器）；
//   ④ 自动检查默认关（启动不偷偷联网）；
//   ⑤ 检查失败只报错，不影响任何计算功能。
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.FAKE_ACCOUNT_PORT || 8795);
const FAKE = `http://127.0.0.1:${PORT}`;
const PROD = "https://mf-vis-science.cn";
const APP_VERSION = "2.0.0";     // 与 MFMath.Host.csproj 的 <Version> 一致
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let fake = spawn(process.execPath, [path.join(HERE, "fake-account-server.mjs")], {
  env: { ...process.env, FAKE_ACCOUNT_PORT: String(PORT) },
  stdio: "ignore",
});
async function waitFake() {
  for (let i = 0; i < 40; i++) {
    try { if ((await fetch(`${FAKE}/__health`)).ok) return true; } catch { /* 等它起来 */ }
    await sleep(250);
  }
  return false;
}
if (!(await waitFake())) { console.error("假账号服务器没起来"); fake.kill(); process.exit(1); }
const setVersion = (q) => fetch(`${FAKE}/__setversion?${new URLSearchParams(q)}`, { method: "POST" });

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
const send = (method, params, timeoutMs = 40000) => new Promise((resolve) => {
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
const stateObj = async () => {
  const raw = String(await evalJs(`JSON.stringify(window.__mfUpdate.state())`));
  try { return JSON.parse(raw); } catch { return {}; }
};

let ready = false;
for (let i = 0; i < 40; i++) {
  if (await evalJs(`typeof window.__mfUpdate === "object" && window.__mfUpdate !== null`) === true) { ready = true; break; }
  if (i === 12) await evalJs(`location.reload()`);
  await sleep(1000);
}
if (!ready) {
  console.error("页面未就绪：等不到 window.__mfUpdate");
  try { ws.close(); } catch { /* 忽略 */ }
  try { fake.kill(); } catch { /* 忽略 */ }
  process.exit(1);
}

console.log("=== ① 桥与自检（不联网）===");
check("宿主提供 update 桥", (await evalJs(`window.__mfUpdate.hosted()`)) === true);
const info = JSON.parse(String(await evalJs(`JSON.stringify(window.__mfUpdate.info())`)));
check("本机版本来自 csproj（不是默认的 1.0.0.0）", info.appVersion === APP_VERSION, String(info.appVersion));
check("策略写明不自动执行安装包", /不自动执行安装包|交给浏览器/.test(String(info.policy)), String(info.policy).slice(0, 80));
const self = String(await evalJs(`JSON.stringify(window.__mfUpdate.selfCheck())`));
check("自检五项全过", /"ok_all":true/.test(self), self.slice(0, 200));
check("自检覆盖 1.10.0 > 1.9.9 这个字符串比较会错的例子", /1\.10\.0/.test(self));
check("自检覆盖「站点更旧时不提示更新」", /站点更旧时不提示更新/.test(self));

console.log("=== ② 自动检查默认关（启动不偷偷联网）===");
const prefs = JSON.parse(String(await evalJs(`JSON.stringify(window.__mfUpdate.prefs())`)));
check("autoCheck 默认为 false", prefs.autoCheck === false, JSON.stringify(prefs));

console.log("=== ③ 站点版本比本机旧 → 不提示更新（本轮最重要的陷阱）===");
// 先把站点地址指到假服务器（与账号共用同一个地址，一处真相）
await evalJs(`window.chrome.webview.hostObjects.sync.account.Configure(JSON.stringify({ baseUrl: ${JSON.stringify(FAKE)} }))`);
await setVersion({ latest: "1.2.0", sha256: "a".repeat(64), size: "139467557" });
const older = String(await evalJs(`JSON.stringify(window.__mfUpdate.check())`));
const olderObj = (() => { try { return JSON.parse(older); } catch { return {}; } })();
check("判定为 older（不是 newer）", olderObj.relation === "older", JSON.stringify(olderObj).slice(0, 160));
check("hasUpdate=false（不提示下载）", olderObj.hasUpdate === false);
check("并说明原因（站点上是 1.2.0，比本机旧）", /比本机旧/.test(String(olderObj.note)), String(olderObj.note).slice(0, 120));
check("顶栏**不出现**「有新版本」徽标", (await evalJs(`!!document.querySelector('[data-update=badge]')`)) === false);

console.log("=== ④ 站点有新版 → 提示 + 显示校验值 ===");
await setVersion({ latest: "9.9.9", date: "2026-12-31", sha256: "b".repeat(64), size: "2048" });
const newer = String(await evalJs(`JSON.stringify(window.__mfUpdate.check())`));
const newerObj = (() => { try { return JSON.parse(newer); } catch { return {}; } })();
check("判定为 newer", newerObj.relation === "newer" && newerObj.hasUpdate === true, JSON.stringify(newerObj).slice(0, 160));
check("带回 sha256 与大小", newerObj.sha256 === "b".repeat(64) && newerObj.size === 2048);
check("顶栏出现「有新版本」徽标", await waitTrue(`!!document.querySelector('[data-update=badge]')`, 6000));
check("徽标提示里写着站点版本号", /9\.9\.9/.test(String(await evalJs(`(document.querySelector('[data-update=badge]')||{}).title||''`))));

console.log("=== ⑤ 设置 → 更新：显示当前版本 / 差异 / 校验值 ===");
await evalJs(`location.hash = "#/settings?group=update"`);
check("更新分组可达", await waitTrue(`!!document.querySelector('[data-setting="update.version"]')`, 10000));
check("显示当前版本", (await evalJs(`document.querySelector('[data-update=current]').textContent.includes(${JSON.stringify(APP_VERSION)})`)) === true);
check("更新源显示的是账号里那个站点地址（一处真相）",
  (await evalJs(`document.querySelector('[data-update=source]').textContent.trim()`)) === FAKE);
const resultText = String(await evalJs(`(document.querySelector('[data-update=result]')||{}).textContent||''`));
check("结果行写明本机与站点版本", /9\.9\.9/.test(resultText) && new RegExp(APP_VERSION.replace(/\./g, "\\.")).test(resultText), resultText.replace(/\s+/g, " ").slice(0, 120));
const shaText = String(await evalJs(`(document.querySelector('[data-update=sha]')||{}).textContent||''`));
check("显示 SHA-256 与大小", /b{64}/.test(shaText) && /2\s*KB/.test(shaText), shaText.replace(/\s+/g, " ").slice(0, 110));
check("有下载入口（打开浏览器）", (await evalJs(`!!document.querySelector('[data-update=download]')`)) === true);

console.log("=== ⑥ 站点没给校验值 → 如实说没有（不显示成已校验）===");
await setVersion({ latest: "9.9.9", sha256: "", reason: "服务器上还没有安装包文件（构建产物未上传）" });
await evalJs(`window.__mfUpdate.check()`);
const noSha = await stateObj();
check("sha256 为 null 且带原因", noSha.result?.sha256 === null && /服务器上还没有安装包文件/.test(String(noSha.result?.sha256Reason)),
  JSON.stringify({ sha: noSha.result?.sha256, reason: noSha.result?.sha256Reason }).slice(0, 150));
const shaLine = String(await evalJs(`(document.querySelector('[data-update=sha]')||{}).textContent||''`));
check("界面上写的是「站点未提供校验值」而不是空白", /未提供校验值/.test(shaLine), shaLine.replace(/\s+/g, " ").slice(0, 110));

console.log("=== ⑦ 打开链接的协议闸门（不点真按钮，免得弹出浏览器）===");
const bad = String(await evalJs(`JSON.stringify(window.__mfUpdate.openDownload("javascript:alert(1)"))`));
check("拒绝 javascript:", /"ok":false/.test(bad) && /http\/https|相对路径/.test(bad), bad.slice(0, 110));
const badFile = String(await evalJs(`JSON.stringify(window.__mfUpdate.openDownload("file:///C:/Windows/System32/cmd.exe"))`));
check("拒绝 file:", /"ok":false/.test(badFile), badFile.slice(0, 110));
const badMs = String(await evalJs(`JSON.stringify(window.__mfUpdate.openDownload("ms-settings:"))`));
check("拒绝自定义协议", /"ok":false/.test(badMs), badMs.slice(0, 110));
// 拼接逻辑单独验（宿主只算地址、不打开 —— 所以这条断言不会弹浏览器）
const preview = JSON.parse(String(await evalJs(`JSON.stringify({
  slash: window.__mfUpdate.preview("/download"),
  bare: window.__mfUpdate.preview("download"),
  protoRel: window.__mfUpdate.preview("//evil.example/x"),
  traversal: window.__mfUpdate.preview("/a/../b"),
  absolute: window.__mfUpdate.preview("https://mf-vis-science.cn/download")
})`)));
check("相对地址 /download 拼成站点地址", preview.slash?.ok === true && preview.slash.url === `${FAKE}/download`, JSON.stringify(preview.slash));
check("不带斜杠的 download 也能拼", preview.bare?.ok === true && preview.bare.url === `${FAKE}/download`, JSON.stringify(preview.bare));
check("**协议相对地址 //host 被拒**（否则是个跳出站点的口子）", preview.protoRel?.ok === false, JSON.stringify(preview.protoRel));
check("路径穿越 .. 被拒", preview.traversal?.ok === false, JSON.stringify(preview.traversal));
check("绝对 http(s) 地址原样通过", preview.absolute?.ok === true && preview.absolute.url === "https://mf-vis-science.cn/download", JSON.stringify(preview.absolute));
check("界面在点之前就显示「将打开：」的地址",
  (await evalJs(`(document.querySelector('[data-update=target]')||{}).textContent?.includes(${JSON.stringify(FAKE + "/download")}) || false`)) === true,
  String(await evalJs(`(document.querySelector('[data-update=target]')||{}).textContent||''`)).replace(/\s+/g, " ").slice(0, 110));

console.log("=== ⑧ 检查失败只报错，不影响计算 ===");
fake.kill();
fake = null;
await sleep(500);
const failed = String(await evalJs(`JSON.stringify(window.__mfUpdate.check())`));
check("站点不通时给出网络类错误", /"ok":false/.test(failed) && /"kind":"network"/.test(failed), failed.slice(0, 140));
const hint = String(await evalJs(`window.__mfUpdate.hintFor("network")`));
check("并给出「下一步怎么办」", /稍后再试|照常可用/.test(hint), hint.slice(0, 80));

// 本地计算照常（与账号那条同一个承诺：这一层永不挡住计算）
await evalJs(`location.hash = "#/calc/basic"`);
await sleep(800);
for (const key of ["7", "+", "8", "="]) {
  await evalJs(`(() => {
    const b = [...document.querySelectorAll('button')].find(x => (x.textContent || '').trim() === ${JSON.stringify(key)});
    if (b) b.click();
    return true;
  })()`);
}
await sleep(900);
const lcd = String(await evalJs(`(() => { const r = document.querySelector('.lcd .lcd-result'); return r ? r.textContent.trim() : ''; })()`));
check("**站点不通时本地计算照常**（7+8=15）", lcd === "15", `结果="${lcd}"`);

// ⚠ 收尾时必须把这个页面清干净再离开：第一版留下了 "7+8"，
// 下一个用例（cdp-ai）在后面接着敲 "1+1" 就变成了 "7+81+1=89"，
// 于是它的"结果区等于引擎值"断言失败 —— 顺序依赖是这套用例最忌讳的东西。
await evalJs(`window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))`);
await sleep(300);
await evalJs(`location.hash = "#/"`);
await sleep(500);
const cleared = String(await evalJs(`(() => { const r = document.querySelector('.lcd .lcd-result'); return r ? r.textContent.trim() : ''; })()`));
check("离开前把计算页显示清空了（不留状态给下一个用例）", cleared === "" || cleared === "0", `结果="${cleared}"`);

console.log("=== ⑨ 收尾：站点地址还原为生产域名 ===");
await evalJs(`window.chrome.webview.hostObjects.sync.account.Configure(JSON.stringify({ baseUrl: ${JSON.stringify(PROD)} }))`);
await evalJs(`window.__mfUpdate.savePrefs({ autoCheck: false, lastCheckAt: 0 })`);
// ⚠ 必须 refresh 一次：info() 返回的是页面里的 ref（上次刷新的快照），
// 直接读会把刚才的假地址当成"没还原"（第一版就是栽在这儿）
await evalJs(`window.__mfUpdate.refresh()`);
const back = String(await evalJs(`window.__mfUpdate.info().baseUrl`));
check("站点地址已还原", back === PROD, back);

console.log(`RESULT|cdp-update|${pass}|${fail}`);
try { ws.close(); } catch { /* 忽略 */ }
try { fake?.kill(); } catch { /* 忽略 */ }
process.exit(fail === 0 ? 0 : 1);
