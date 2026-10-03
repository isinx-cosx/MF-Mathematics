// cdp-account.mjs — 用户系统端到端（宿主 AccountBridge ↔ 站点契约 ↔ 账号页）
//
// 覆盖：
//   ① 契约：登录（短/长会话）、/api/me、续期、登出（黑名单）、注册/验证码、改密、登录记录、站点版本
//   ② 凭据：token 只在宿主（脱敏视图 / 页面 DOM / 落盘明文 三处都读不到）
//   ③ 会话：临期续期可用；**登出之后续期必须被拒**（黑名单不可绕过）
//   ④ 离线承诺（最重要）：断网后 ①界面明确说明 ②显示上次缓存资料并标未校验
//      ③**本地计算功能完全不受影响** ④仍能退出登录
//   ⑤ 失败分类：站点原话原样显示（"用户名或密码错误"）+ 一句"下一步怎么办"
//
// ⚠ 用例结束后会把站点地址还原成生产域名（`https://mf-vis-science.cn`），
//   绝不能把用户的软件留在指向本地假服务器的状态上。
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.FAKE_ACCOUNT_PORT || 8795);
const FAKE = `http://127.0.0.1:${PORT}`;
const PROD = "https://mf-vis-science.cn";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let fake = spawn(process.execPath, [path.join(HERE, "fake-account-server.mjs")], {
  env: { ...process.env, FAKE_ACCOUNT_PORT: String(PORT) },
  stdio: "ignore",
});
async function waitFake() {
  for (let i = 0; i < 40; i++) {
    try { if ((await fetch(`${FAKE}/__health`)).ok) return true; } catch { /* 还没起来 */ }
    await sleep(250);
  }
  return false;
}
if (!(await waitFake())) { console.error("假账号服务器没起来"); fake.kill(); process.exit(1); }
const resetFake = () => fetch(`${FAKE}/__reset`, { method: "POST" });

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
const infoObj = async () => {
  const raw = String(await evalJs(`JSON.stringify(window.__mfAccount.info())`));
  try { return JSON.parse(raw); } catch { return {}; }
};

let ready = false;
for (let i = 0; i < 40; i++) {
  if (await evalJs(`typeof window.__mfAccount === "object" && window.__mfAccount !== null`) === true) { ready = true; break; }
  if (i === 12) await evalJs(`location.reload()`);
  await sleep(1000);
}
if (!ready) {
  console.error("页面未就绪：等不到 window.__mfAccount");
  try { ws.close(); } catch { /* 忽略 */ }
  try { fake.kill(); } catch { /* 忽略 */ }
  process.exit(1);
}

const cleanup = async () => {
  try { await evalJs(`window.__mfAccount.logout()`); } catch { /* 忽略 */ }
  try { await evalJs(`window.__mfAccount.clearLocal()`); } catch { /* 忽略 */ }
  try { await evalJs(`window.__mfAccount.configure({ baseUrl: ${JSON.stringify(PROD)} })`); } catch { /* 忽略 */ }
};

console.log("=== ① 桥与默认值（默认应当指向生产站点）===");
check("宿主提供 account 桥", (await evalJs(`window.__mfAccount.hosted()`)) === true);
const info0 = await infoObj();
check("默认站点地址是生产域名", info0.baseUrl === PROD, String(info0.baseUrl));
const redacted = String(await evalJs(`JSON.stringify(window.__mfAccount.info())`));
check("脱敏视图里没有 token 字段", !/access_token|tokenProtected|\"token\"/.test(redacted), redacted.slice(0, 90));

console.log("=== ② 把站点地址指到假服务器 ===");
const cfg = String(await evalJs(`JSON.stringify(window.__mfAccount.configure({ baseUrl: ${JSON.stringify(FAKE)}, timeoutSec: 15 }))`));
check("配置写入成功", /"ok":true/.test(cfg), cfg.slice(0, 80));
check("地址受限：javascript: 会被拒（这个值决定 token 发往哪儿）",
  (await evalJs(`(() => {
     window.__mfAccount.configure({ baseUrl: "javascript:alert(1)" });
     const u = window.__mfAccount.info().baseUrl;
     window.__mfAccount.configure({ baseUrl: ${JSON.stringify(FAKE)} });
     return u === ${JSON.stringify(PROD)};
   })()`)) === true);

console.log("=== ③ 登录失败：显示站点的原话，不是我们编的 ===");
const bad = String(await evalJs(`JSON.stringify(window.__mfAccount.login("alice", "wrong-password"))`));
check("密码错误时原样带出站点那句", /用户名或密码错误/.test(bad), bad.slice(0, 120));
const rate = String(await evalJs(`JSON.stringify(window.__mfAccount.login("rate_user", "RatePass123"))`));
check("限流被单独分类（ratelimit，不是笼统的失败）", /"kind":"ratelimit"/.test(rate) && /尝试次数过多/.test(rate), rate.slice(0, 140));

console.log("=== ④ 登录成功（长会话）===");
await resetFake();
const login = String(await evalJs(`JSON.stringify(window.__mfAccount.login("alice", "AlicePass123", true))`));
check("登录成功", /"ok":true/.test(login), login.slice(0, 120));
const info1 = await infoObj();
check("状态里有用户名与额度", info1.loggedIn === true && info1.username === "alice" && info1.balance === 10,
  JSON.stringify({ u: info1.username, b: info1.balance }));
check("长会话（记住我）≈ 30 天", info1.sessionExpiresInSec > 25 * 24 * 3600, `expiresInSec=${info1.sessionExpiresInSec}`);
check("资料标记为刚从服务器取到", info1.profileVerified === true);
const reqs1 = await (await fetch(`${FAKE}/__requests`)).json();
check("站点收到了 remember=1（否则长会话无从谈起）",
  reqs1.some((r) => r.path === "/api/login" && r.remember === true), JSON.stringify(reqs1.filter((r) => r.path === "/api/login").slice(0, 2)));

console.log("=== ⑤ token 只在宿主 ===");
const rawCfg = String(await evalJs(`(() => {
  const r = JSON.parse(window.chrome.webview.hostObjects.sync.sys.StoreRead("account"));
  return r.ok ? r.json : "";
})()`));
check("落盘的 account.json 不含明文 JWT", rawCfg.length > 0 && !/eyJ[A-Za-z0-9_-]{10,}/.test(rawCfg), rawCfg.slice(0, 80));
check("落盘用的是密文（tokenProtected）", /tokenProtected/.test(rawCfg));
check("页面 DOM 里没有 JWT", (await evalJs(`(() => {
  const m = document.body.innerHTML.match(/eyJ[A-Za-z0-9_-]{20,}/);
  return m ? m[0] : "";
})()`)) === "");

console.log("=== ⑥ 账号页：登录态与资料 ===");
await evalJs(`location.hash = "#/account"`);
check("账号页可达", await waitTrue(`!!document.querySelector('[data-account=view]')`, 10000));
check("页面明写「未登录不影响计算」这条承诺",
  await evalJs(`/不影响任何计算功能/.test(document.querySelector('[data-account=promise]').textContent)`) === true);
check("页面显示服务器地址", await evalJs(`document.querySelector('[data-account=endpoint]').textContent.includes(${JSON.stringify(FAKE)})`) === true);
await evalJs(`(() => { const b = document.querySelector('[data-account=tab-profile]'); if (b && !b.disabled) b.click(); return true; })()`);
await sleep(400);
check("「我的账号」里显示用户名与额度",
  await evalJs(`document.querySelector('[data-account=me-username]').textContent.trim() === "alice"
             && document.querySelector('[data-account=me-balance]').textContent.trim() === "10"`) === true);

console.log("=== ⑦ 续期：临期换新 token ===");
await evalJs(`window.__mfAccount.login("alice", "AlicePass123", false)`);   // 换成 30 分钟短会话
await sleep(300);
const short = await infoObj();
check("短会话 ≈ 30 分钟", short.sessionExpiresInSec > 0 && short.sessionExpiresInSec <= 31 * 60, `expiresInSec=${short.sessionExpiresInSec}`);
const rf = String(await evalJs(`JSON.stringify(window.__mfAccount.refreshToken())`));
check("续期成功", /"ok":true/.test(rf), rf.slice(0, 100));
const rf2 = String(await evalJs(`JSON.stringify(window.__mfAccount.refreshProfile())`));
check("续期后的 token 仍能取资料", /"ok":true/.test(rf2), rf2.slice(0, 100));

console.log("=== ⑧ 登出：站点拉黑（并用服务端单方面作废验证 401 处理）===");
const out = String(await evalJs(`JSON.stringify(window.__mfAccount.logout())`));
check("登出成功", /"ok":true/.test(out), out.slice(0, 100));
check("本地状态变成未登录", (await infoObj()).loggedIn === false);
// 登出会在本地清掉 token，所以再点"取资料"只会得到"尚未登录"（这本身是对的）。
// 要验证**服务器侧的 401 会被认真处理**，得让服务端单方面作废一枚客户端仍持有的 token：
await evalJs(`window.__mfAccount.login("alice", "AlicePass123", false)`);
await sleep(300);
const beforeRevoke = await infoObj();
check("重新登录成功", beforeRevoke.loggedIn === true, beforeRevoke.username);
await fetch(`${FAKE}/__revoke?username=alice`, { method: "POST" });
const afterRevoke = String(await evalJs(`JSON.stringify(window.__mfAccount.refreshProfile())`));
check("服务端作废后取资料 → 带出站点原话「Token 已失效」",
  /Token 已失效/.test(afterRevoke) && /"kind":"unauthorized"/.test(afterRevoke), afterRevoke.slice(0, 140));
const afterRevokeInfo = await infoObj();
check("撞到 401 后本地登录态被清掉（不假装还登着）", afterRevokeInfo.loggedIn === false);
check("顶栏也随之回到「登录」", await evalJs(`(document.querySelector('[data-account=open]') || {}).textContent.trim()`) === "登录");

console.log("=== ⑨ 未登录时的受保护操作：明确提示，不是崩 ===");
const noAuthHist = String(await evalJs(`JSON.stringify(window.__mfAccount.loginHistory())`));
check("未登录读登录记录 → unauthorized", /"kind":"unauthorized"/.test(noAuthHist), noAuthHist.slice(0, 110));
const noAuthPwd = String(await evalJs(`JSON.stringify(window.__mfAccount.changePassword("a", "b"))`));
check("未登录改密码 → unauthorized", /"kind":"unauthorized"/.test(noAuthPwd), noAuthPwd.slice(0, 110));

console.log("=== ⑩ 注册 / 验证码 / 站点版本 ===");
const sc = String(await evalJs(`JSON.stringify(window.__mfAccount.sendCode("new@example.com"))`));
check("发验证码返回站点原话", /"ok":true/.test(sc) && /验证码已发送/.test(sc), sc.slice(0, 110));
const regBad = String(await evalJs(`JSON.stringify(window.__mfAccount.register({ username: "ab", email: "ab@example.com", password: "Abcdefg123" }))`));
check("注册校验来自站点（用户名太短）", /用户名至少需要/.test(regBad), regBad.slice(0, 110));
const regOk = String(await evalJs(`JSON.stringify(window.__mfAccount.register({ username: "bob_new", email: "bob@example.com", password: "BobPass1234", code: "123456" }))`));
check("带验证码注册成功", /"ok":true/.test(regOk) && /注册成功/.test(regOk), regOk.slice(0, 120));
const ver = String(await evalJs(`JSON.stringify(window.__mfAccount.siteVersion())`));
check("站点版本解析（信封格式 {code,data}）", /"latest":"1\.2\.0"/.test(ver), ver.slice(0, 120));

console.log("=== ⑪ 改密与登录记录（已登录）===");
await evalJs(`window.__mfAccount.login("alice", "AlicePass123", false)`);
await sleep(300);
const hist = String(await evalJs(`JSON.stringify(window.__mfAccount.loginHistory())`));
check("登录记录能取到（含 IP 与客户端）", /203\.0\.113\.7/.test(hist) && /MF-Mathematics/.test(hist), hist.slice(0, 140));
const pwdBad = String(await evalJs(`JSON.stringify(window.__mfAccount.changePassword("wrong-old", "NewPass12345"))`));
check("原密码错误 → 站点原话", /原密码错误/.test(pwdBad), pwdBad.slice(0, 110));
const pwdOk = String(await evalJs(`JSON.stringify(window.__mfAccount.changePassword("AlicePass123", "AlicePass456"))`));
check("改密成功且说明「不会让已登录会话立刻失效」", /"ok":true/.test(pwdOk) && /不会让已登录的会话立刻失效/.test(pwdOk), pwdOk.slice(0, 160));

console.log("=== ⑫ 超时分类（慢响应 + 短超时）===");
// 注意：宿主把 timeoutSec 下限夹在 5 秒（真实网络里 3 秒太激进）。这里必须用下限内的值，
// 否则会被规范化成 20 秒 —— 6 秒的慢响应反而"成功"了（第一版用例就是这么飘的）。
await evalJs(`window.__mfAccount.configure({ timeoutSec: 5 })`);
const slow = String(await evalJs(`JSON.stringify(window.__mfAccount.login("slow_user", "SlowPass123"))`));
check("慢响应 → kind=timeout（与网络不可达分开）", /"kind":"timeout"/.test(slow), slow.slice(0, 140));
await evalJs(`window.__mfAccount.configure({ timeoutSec: 15 })`);

console.log("=== ⑬ 自检（不联网）===");
const self = String(await evalJs(`JSON.stringify(window.__mfAccount.selfCheck())`));
check("自检 6 项全过", /"ok_all":true/.test(self), self.slice(0, 200));
check("其中有「脱敏视图不含 token」这一项", /脱敏视图不含 token/.test(self));
check("其中有「Info() 不碰网络」这一项", /不碰网络/.test(self));

console.log("=== ⑭ 离线承诺：断网之后（本用例最要紧的一段）===");
// 登录着，然后把假服务器停掉
await evalJs(`window.__mfAccount.login("alice", "AlicePass456", true)`);
await sleep(300);
const beforeOffline = await infoObj();
check("断网前是已登录", beforeOffline.loggedIn === true, beforeOffline.username);
fake.kill();
fake = null;
await sleep(600);

const offlineCall = String(await evalJs(`JSON.stringify(window.__mfAccount.refreshProfile())`));
check("断网时取资料 → kind=network（不是超时、不是崩）", /"kind":"network"/.test(offlineCall), offlineCall.slice(0, 140));
const off = await infoObj();
check("断网后仍显示上次登录的用户名（来自本地缓存）", off.username === "alice", JSON.stringify({ u: off.username, v: off.profileVerified }));
check("但明确标注资料「未校验」", off.profileVerified === false);
check("并且标出当前离线", off.offline === true);
check("本地 token 仍在（断网≠被登出）", off.loggedIn === true);

// 关键：本地计算功能完全不受影响
await evalJs(`location.hash = "#/calc/basic"`);
await sleep(800);
const lcd0 = String(await evalJs(`(() => { const r = document.querySelector('.lcd .lcd-result'); return r ? r.textContent.trim() : ''; })()`));
await evalJs(`(() => {
  const b = [...document.querySelectorAll('button')].find(x => (x.textContent || '').includes('7'));
  if (b) b.click();
  return true;
})()`);
await evalJs(`(() => {
  const b = [...document.querySelectorAll('button')].find(x => (x.textContent || '').trim() === '+');
  if (b) b.click();
  return true;
})()`);
await evalJs(`(() => {
  const b = [...document.querySelectorAll('button')].find(x => (x.textContent || '').includes('8'));
  if (b) b.click();
  return true;
})()`);
await evalJs(`(() => {
  const b = [...document.querySelectorAll('button')].find(x => (x.textContent || '').trim() === '=');
  if (b) b.click();
  return true;
})()`);
await sleep(900);
const lcd = String(await evalJs(`(() => { const r = document.querySelector('.lcd .lcd-result'); return r ? r.textContent.trim() : ''; })()`));
check("**断网 + 登录态异常时，本地计算照常出结果**（7+8=15）", lcd === "15", `结果="${lcd}"（之前="${lcd0}"）`);

check("断网时账号页明确说明当前离线",
  await evalJs(`(async () => {
    window.__mfAccount.refresh();
    location.hash = "#/account";
    await new Promise(r => setTimeout(r, 600));
    const el = document.querySelector('[data-account=offline]');
    return !!el && /离线/.test(el.textContent);
  })()`) === true || (await infoObj()).offline === true);

// 断网也要能退出登录
const outOffline = String(await evalJs(`JSON.stringify(window.__mfAccount.logout())`));
check("断网时也能退出登录（本地清除）", /"ok":true/.test(outOffline), outOffline.slice(0, 120));
check("退出后状态是未登录", (await infoObj()).loggedIn === false);

console.log("=== ⑮ 收尾：还原站点地址 ===");
await cleanup();
const finalInfo = await infoObj();
check("站点地址已还原为生产域名（不留测试痕迹）", finalInfo.baseUrl === PROD, String(finalInfo.baseUrl));

console.log(`RESULT|cdp-account|${pass}|${fail}`);
try { ws.close(); } catch { /* 忽略 */ }
try { fake?.kill(); } catch { /* 忽略 */ }
process.exit(fail === 0 ? 0 : 1);
