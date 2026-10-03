/**
 * account/bridge.js — 用户系统（宿主桥 + 状态）
 *
 * 软件与服务器之间的那条线在**宿主**里（C# AccountBridge）：token 只存宿主（DPAPI 密文），
 * 页面拿到的是脱敏状态（loggedIn / username / balance…）。理由与 AI、搜索一致：
 * 页面跑在虚拟主机下直连站点会撞 CORS，而凭据不该进渲染进程。
 *
 * 三条纪律写在这里，也写在界面上：
 *   ① **未登录不影响任何计算功能**。所有计算都在本地 C++ 引擎里，这一层只管身份与额度显示。
 *   ② **断网不阻塞**。info() 只读本地缓存；断网时显示上次的资料并标 `profileVerified=false`。
 *   ③ **站点的原话原样带给用户**（"用户名或密码错误"），不翻译成笼统一句"登录失败"。
 */
import { ref } from "vue";
import { onPush } from "../push.js";

function hostObj() {
  try {
    return window.chrome?.webview?.hostObjects?.sync?.account ?? null;
  } catch {
    return null;
  }
}

export function isAccountHosted() {
  return hostObj() !== null;
}

function parse(text, fallback = null) {
  if (text == null) return fallback;
  if (typeof text === "object") return text;
  try { return JSON.parse(String(text)); } catch { return fallback; }
}

function call(method, ...args) {
  const c = hostObj();
  if (!c || typeof c[method] !== "function") return null;
  try { return parse(c[method](...args)); } catch (e) { return { ok: false, kind: "unknown", error: String(e?.message || e) }; }
}

const DEFAULT_INFO = {
  baseUrl: "https://mf-vis-science.cn",
  timeoutSec: 20,
  remember: true,
  autoRefresh: true,
  loggedIn: false,
  username: "",
  email: "",
  balance: 0,
  hasAiService: false,
  role: 0,
  isActive: false,
  sessionExpiresAt: 0,
  sessionExpiresInSec: 0,
  profileVerified: false,
  profileCheckedAt: 0,
  offline: false,
  dpapiAvailable: false,
  tokenSource: "none",
  busy: "",
  lastError: "",
  lastErrorKind: "",
  configPath: "",
};

export const accountInfo = ref({ ...DEFAULT_INFO });
export const accountHosted = ref(false);

export function refreshAccountInfo() {
  accountHosted.value = isAccountHosted();
  const info = call("Info");
  if (info && typeof info === "object" && "baseUrl" in info) {
    accountInfo.value = { ...DEFAULT_INFO, ...info };
  }
  return accountInfo.value;
}

export function accountConfigure(patch) {
  if (!Object.keys(patch || {}).length) return { ok: true, changed: 0 };
  const r = call("Configure", JSON.stringify(patch));
  refreshAccountInfo();
  return r || { ok: false, kind: "nohost", error: "无宿主：账号设置只在 MFMath.exe 里可改" };
}

export function login(username, password, remember = null) {
  const payload = { username: String(username || ""), password: String(password || "") };
  if (remember !== null) payload.remember = !!remember;
  const r = call("LoginEx", JSON.stringify(payload));
  refreshAccountInfo();
  return r || { ok: false, kind: "nohost", error: "无宿主：登录只在 MFMath.exe 里可用" };
}

export function logout() {
  const r = call("Logout") || { ok: false, kind: "nohost", error: "无宿主" };
  refreshAccountInfo();
  return r;
}

export function refreshProfile() {
  const r = call("RefreshProfile") || { ok: false, kind: "nohost", error: "无宿主" };
  refreshAccountInfo();
  return r;
}

export function refreshToken() {
  const r = call("RefreshToken") || { ok: false, kind: "nohost", error: "无宿主" };
  refreshAccountInfo();
  return r;
}

export function ensureFresh() {
  const r = call("EnsureFresh", 300);
  if (r === true) refreshAccountInfo();
  return r === true;
}

export function clearLocal() {
  const r = call("ClearLocal") || { ok: false, kind: "nohost", error: "无宿主" };
  refreshAccountInfo();
  return r;
}

export function register(payload) {
  const r = call("Register", JSON.stringify(payload || {})) || { ok: false, kind: "nohost", error: "无宿主" };
  refreshAccountInfo();
  return r;
}

export function sendCode(email) {
  return call("SendCode", String(email || "")) || { ok: false, kind: "nohost", error: "无宿主" };
}

export function verifyCode(username, code) {
  const r = call("VerifyCode", String(username || ""), String(code || "")) || { ok: false, kind: "nohost", error: "无宿主" };
  refreshAccountInfo();
  return r;
}

export function resendCode(username, email) {
  return call("ResendCode", String(username || ""), String(email || "")) || { ok: false, kind: "nohost", error: "无宿主" };
}

export function changePassword(oldPassword, newPassword) {
  const r = call("ChangePassword", String(oldPassword || ""), String(newPassword || "")) || { ok: false, kind: "nohost", error: "无宿主" };
  refreshAccountInfo();
  return r;
}

export function loginHistory() {
  return call("LoginHistory") || { ok: false, kind: "nohost", error: "无宿主" };
}

export function siteVersion() {
  return call("SiteVersion") || { ok: false, kind: "nohost", error: "无宿主" };
}

export function accountSelfCheck() {
  return call("SelfCheck") || { ok: false, error: "无宿主" };
}

/** 失败分类 → 一句"下一步怎么办"。站点的原话在 result.error 里，这里只补建议。 */
export function hintFor(kind) {
  switch (kind) {
    case "unauthorized": return "登录状态已失效：重新登录即可（本地计算不受影响）。";
    case "ratelimit": return "站点在限流（多为连续失败尝试）。等一会儿再试，别连点。";
    case "network": return "网络没通。检查网络/代理，或确认站点地址填对了。断网时本地功能全部照常可用。";
    case "timeout": return "站点响应太慢。可在设置里调大超时，或稍后再试。";
    case "aborted": return "已取消。";
    case "parse": return "站点返回的形状和约定不一致（可能是版本差异）。";
    case "config": return "先检查设置：站点地址、用户名、密码。";
    default: return "可以重试。";
  }
}

/* ── 推送订阅 ────────────────────────────────────────────────────────── */

let inited = false;

export function initAccount() {
  if (inited) return;
  inited = true;
  refreshAccountInfo();
  onPush((env) => {
    const topic = String(env?.topic || "");
    if (topic !== "account.changed") return;
    const payload = env.payload || {};
    if (payload.info && typeof payload.info === "object") accountInfo.value = { ...DEFAULT_INFO, ...payload.info };
    else refreshAccountInfo();
  });
}

/** 测试/排障钩子 */
export function initAccountHook() {
  try {
    window.__mfAccount = {
      info: () => accountInfo.value,
      refresh: refreshAccountInfo,
      configure: accountConfigure,
      login,
      logout,
      refreshProfile,
      refreshToken,
      ensureFresh,
      clearLocal,
      register,
      sendCode,
      verifyCode,
      resendCode,
      changePassword,
      loginHistory,
      siteVersion,
      selfCheck: accountSelfCheck,
      hintFor,
      hosted: isAccountHosted,
    };
  } catch { /* 忽略 */ }
}
