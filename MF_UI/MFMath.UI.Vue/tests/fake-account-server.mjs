// fake-account-server.mjs — 本地假账号服务器（照站点 src/app/api/* 的契约实现）
//
// 为什么照抄契约而不是自创：这一层的价值就在于"软件的假设与服务器一致"。
// 形状全部对齐站点现成实现：
//   POST /api/login            表单 username,password[,remember] → {access_token,token_type,expires_in}
//   失败一律 {detail:"…"}（站点注释里写明"桌面端依赖 detail"）
//   GET  /api/me               Bearer → 公开用户
//   POST /api/token/refresh    表单(可带 remember) + Bearer → 新 token；**登出过的 token 必须 401**
//   POST /api/logout           Bearer → 把 jti 拉黑
//   POST /api/register|send-code（JSON）、verify-code|resend-code|change-password（表单）
//   GET  /api/login-history    Bearer → {items:[…]}
//   GET  /api/version          信封 {code,data:{latest,date,download_url}}
//
// 触发词（用户名）：
//   slow_user → 延迟 3 秒（测超时/取消）      rate_user → 429 + 站点原话
//   boom_user → 500                          inactive_user → 403 未激活
//   noexp_user → 200 但**不带 expires_in**（测客户端解 JWT exp 的退路）
//   坏JSON_user → 200 但响应体不是 JSON
import http from "node:http";
import { createHmac } from "node:crypto";

const PORT = Number(process.env.FAKE_ACCOUNT_PORT || 8795);
const SECRET = "fake-secret";
const users = new Map();      // username → {password, email, balance, active, role}
const blacklist = new Set();  // jti 黑名单
const issued = new Map();     // username → [jti…]（供 /__revoke 用）
const requests = [];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

users.set("alice", { password: "AlicePass123", email: "alice@example.com", balance: 10, active: true, role: 0 });
users.set("slow_user", { password: "SlowPass123", email: "slow@example.com", balance: 3, active: true, role: 0 });
users.set("rate_user", { password: "RatePass123", email: "rate@example.com", balance: 1, active: true, role: 0 });
users.set("boom_user", { password: "BoomPass123", email: "boom@example.com", balance: 1, active: true, role: 0 });
users.set("inactive_user", { password: "InactivePass123", email: "inactive@example.com", balance: 0, active: false, role: 0 });
users.set("noexp_user", { password: "NoExpPass123", email: "noexp@example.com", balance: 5, active: true, role: 0 });

const b64url = (obj) => Buffer.from(JSON.stringify(obj)).toString("base64url");

function makeToken(username, minutes, extra = {}) {
  const jti = "jti-" + Math.random().toString(36).slice(2);
  const exp = Math.floor(Date.now() / 1000) + minutes * 60;
  const header = b64url({ alg: "HS256", typ: "JWT" });
  const payload = b64url({ sub: username, jti, exp, ...extra });
  const sig = createHmac("sha256", SECRET).update(`${header}.${payload}`).digest("base64url");
  if (!issued.has(username)) issued.set(username, []);
  issued.get(username).push(jti);
  return { token: `${header}.${payload}.${sig}`, jti, exp };
}

function verify(req) {
  const h = req.headers.authorization || "";
  const m = h.match(/^Bearer\s+(.+)$/i);
  if (!m) return { error: { status: 401, detail: "未认证" } };
  const parts = m[1].split(".");
  if (parts.length !== 3) return { error: { status: 401, detail: "无效凭证" } };
  let payload;
  try { payload = JSON.parse(Buffer.from(parts[1], "base64url").toString("utf8")); }
  catch { return { error: { status: 401, detail: "无效凭证" } }; }
  if (!payload.sub) return { error: { status: 401, detail: "无效凭证" } };
  if (blacklist.has(payload.jti)) return { error: { status: 401, detail: "Token 已失效，请重新登录" } };
  if (payload.exp && payload.exp * 1000 < Date.now()) return { error: { status: 401, detail: "凭证已过期" } };
  const user = users.get(payload.sub);
  if (!user) return { error: { status: 401, detail: "用户不存在" } };
  return { user, username: payload.sub, payload };
}

const json = (res, status, body) => {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(typeof body === "string" ? body : JSON.stringify(body));
};
const fail = (res, status, detail) => json(res, status, { detail });

async function readForm(req) {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  return new URLSearchParams(Buffer.concat(chunks).toString("utf8"));
}
async function readJson(req) {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://127.0.0.1:${PORT}`);
  const path = url.pathname;

  if (path === "/__requests") return json(res, 200, requests);
  if (path === "/__reset") { requests.length = 0; blacklist.clear(); return json(res, 200, { ok: true }); }
  if (path === "/__health") return json(res, 200, { ok: true });
  // 测试钩子：把某用户已签发的 token 全部拉黑，模拟"服务器侧会话被作废"——
  // 客户端并不知道，只有下一次请求才会撞上 401。登出路径走的是**本地清除**，测不到这条，
  // 所以必须有一个"服务端单方面作废"的入口才能真的验证客户端认真处理了服务器的 401。
  if (path === "/__revoke") {
    const who = url.searchParams.get("username") || "";
    const list = issued.get(who) || [];
    for (const j of list) blacklist.add(j);
    return json(res, 200, { ok: true, revoked: list.length });
  }

  const entry = { at: Date.now(), path, method: req.method, hasAuth: !!(req.headers.authorization || "") };
  requests.push(entry);

  // ── 登录 ──────────────────────────────────────────────────────────────
  if (path === "/api/login" && req.method === "POST") {
    const form = await readForm(req);
    const username = String(form.get("username") || "").trim();
    const password = String(form.get("password") || "");
    const remember = ["1", "true", "yes", "on"].includes(String(form.get("remember") || "").toLowerCase());
    entry.username = username;
    entry.remember = remember;

    if (username === "slow_user") await sleep(8000);   // 远大于用例设的超时（等长会变成掷硬币；也别小于配置下限 5 秒）
    if (username === "rate_user") return fail(res, 429, "登录尝试次数过多，请 15 分 0 秒后再试");
    if (username === "boom_user") return fail(res, 500, "服务器内部错误");

    const u = users.get(username);
    if (!u || u.password !== password) return fail(res, 400, "用户名或密码错误");
    if (!u.active) return fail(res, 403, "账户未激活，请先验证邮箱");

    const minutes = remember ? 30 * 24 * 60 : 30;
    const { token } = makeToken(username, minutes);
    const body = { access_token: token, token_type: "bearer" };
    // noexp_user 故意不回 expires_in：客户端要能退回解 JWT 的 exp
    if (username !== "noexp_user") body.expires_in = minutes * 60;
    return json(res, 200, body);
  }

  // ── 续期（本轮为桌面端新增的端点）─────────────────────────────────────
  if (path === "/api/token/refresh" && req.method === "POST") {
    const v = verify(req);
    if (v.error) return fail(res, v.error.status, v.error.detail);
    let remember = false;
    try { remember = ["1", "true", "yes", "on"].includes(String((await readForm(req)).get("remember") || "").toLowerCase()); }
    catch { /* 空体也正常 */ }
    entry.remember = remember;
    const minutes = remember ? 30 * 24 * 60 : 30;
    const { token } = makeToken(v.username, minutes);
    return json(res, 200, { access_token: token, token_type: "bearer", expires_in: minutes * 60 });
  }

  // ── 当前用户 ──────────────────────────────────────────────────────────
  if (path === "/api/me" && req.method === "GET") {
    const v = verify(req);
    if (v.error) return fail(res, v.error.status, v.error.detail);
    if (v.username === "坏JSON_user") { res.writeHead(200, { "content-type": "application/json" }); return res.end("<html>not json</html>"); }
    const u = v.user;
    return json(res, 200, {
      username: v.username, email: u.email, balance: u.balance,
      has_ai_service: u.balance > 5, role: u.role, is_active: u.active,
    });
  }

  // ── 登出（把 jti 拉黑）────────────────────────────────────────────────
  if (path === "/api/logout" && req.method === "POST") {
    const v = verify(req);
    if (v.error) return fail(res, v.error.status, v.error.detail);
    blacklist.add(v.payload.jti);
    return json(res, 200, { msg: "已成功登出" });
  }

  // ── 注册 / 验证码 ─────────────────────────────────────────────────────
  if (path === "/api/send-code" && req.method === "POST") {
    const body = await readJson(req);
    entry.email = body.email || "";
    if (!body.email) return fail(res, 400, "请求体格式错误");
    return json(res, 200, { msg: `验证码已发送至 ${body.email}，请查收` });
  }
  if (path === "/api/register" && req.method === "POST") {
    const body = await readJson(req);
    entry.username = body.username || "";
    if (!body.username || body.username.length < 3) return fail(res, 400, "用户名至少需要 3 个字符");
    if (users.has(body.username)) return fail(res, 400, "用户名已存在");
    if (!body.password || body.password.length < 8) return fail(res, 400, "密码至少需要 8 个字符");
    if (!body.code) return json(res, 200, { msg: `注册成功！验证码已发送至 ${body.email}，请查收并输入验证码完成激活。` });
    if (body.code !== "123456") return fail(res, 400, "验证码错误");
    users.set(body.username, { password: body.password, email: body.email, balance: 10, active: true, role: 0 });
    return json(res, 200, { msg: "注册成功！已赠送 10 次免费额度" });
  }
  if (path === "/api/verify-code" && req.method === "POST") {
    const form = await readForm(req);
    const u = users.get(String(form.get("username") || ""));
    if (!u) return fail(res, 400, "用户不存在");
    if (u.active) return fail(res, 400, "账户已激活，无需重复验证");
    if (String(form.get("code") || "") !== "123456") return fail(res, 400, "验证码错误");
    u.active = true;
    return json(res, 200, { msg: "账户已激活，可以登录了" });
  }
  if (path === "/api/resend-code" && req.method === "POST") {
    const form = await readForm(req);
    if (!users.has(String(form.get("username") || ""))) return fail(res, 400, "用户不存在");
    return json(res, 200, { msg: "验证码已重新发送" });
  }

  // ── 需登录的操作 ──────────────────────────────────────────────────────
  if (path === "/api/change-password" && req.method === "POST") {
    const v = verify(req);
    if (v.error) return fail(res, v.error.status, v.error.detail);
    const form = await readForm(req);
    if (String(form.get("old_password") || "") !== v.user.password) return fail(res, 400, "原密码错误");
    const next = String(form.get("new_password") || "");
    if (next.length < 8) return fail(res, 400, "密码至少需要 8 个字符");
    v.user.password = next;
    return json(res, 200, { msg: "密码修改成功" });
  }
  if (path === "/api/login-history" && req.method === "GET") {
    const v = verify(req);
    if (v.error) return fail(res, v.error.status, v.error.detail);
    return json(res, 200, {
      items: [
        { login_at: new Date(Date.now() - 3600_000).toISOString(), ip: "203.0.113.7", user_agent: "MF-Mathematics/2.0 (Windows; desktop)" },
        { login_at: new Date(Date.now() - 86400_000).toISOString(), ip: "198.51.100.9", user_agent: "Mozilla/5.0 (site)" },
      ],
    });
  }
  if (path === "/api/version" && req.method === "GET") {
    return json(res, 200, { code: 0, data: { latest: "1.2.0", date: "2026-07-21", download_url: "/download", changelog: "/changelog" }, msg: "success" });
  }

  fail(res, 404, "没有这个接口");
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`[fake-account] listening on http://127.0.0.1:${PORT}`);
});
