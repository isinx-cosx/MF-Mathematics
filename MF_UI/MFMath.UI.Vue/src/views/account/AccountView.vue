<script setup>
/**
 * AccountView.vue — 账号页（路由 /account）
 *
 * 这个页面就是"软件与服务器之间的那条线"的界面。三条要写在明面上的话：
 *   ① **未登录、断网都不影响任何计算功能** —— 计算全在本地 C++ 引擎里，这里只管身份与额度；
 *   ② 断网时显示的是**上次登录缓存的资料**，会明确标注"未校验"，不假装是刚取到的；
 *   ③ 站点说什么就显示什么（"用户名或密码错误"），本页只补一句"下一步怎么办"。
 *
 * 密码只在这一层停留瞬间，直接交给宿主去发请求，不落任何本地存储；token 也不会回到这里。
 */
import { computed, onMounted, ref } from "vue";
import {
  accountInfo, accountHosted, initAccount, refreshAccountInfo, ensureFresh,
  login, logout, refreshProfile, clearLocal, register, sendCode, verifyCode, resendCode,
  changePassword, loginHistory, siteVersion, hintFor, accountSelfCheck,
} from "../../lib/account/bridge.js";

const tab = ref("login");           // login | register | profile | password | history
const busy = ref("");
const msg = ref(null);              // {ok, text, hint}
const history = ref([]);
const version = ref(null);
const selfCheck = ref(null);

// 登录表单
const form = ref({ username: "", password: "", remember: accountInfo.value.remember });
// 注册表单
const reg = ref({ username: "", email: "", password: "", code: "" });
// 改密表单
const pwd = ref({ old: "", next: "" });

const info = accountInfo;
const loggedIn = computed(() => info.value.loggedIn === true);
const sessionText = computed(() => {
  const s = info.value.sessionExpiresInSec || 0;
  if (!info.value.loggedIn) return "";
  if (s <= 0) return "到期时间未知";
  if (s < 3600) return `${Math.round(s / 60)} 分钟后到期`;
  if (s < 86400) return `${Math.round(s / 3600)} 小时后到期`;
  return `${Math.round(s / 86400)} 天后到期`;
});
const roleText = computed(() => (info.value.role >= 2 ? "超级管理员" : info.value.role >= 1 ? "管理员" : "普通用户"));

onMounted(async () => {
  initAccount();
  refreshAccountInfo();
  selfCheck.value = accountSelfCheck();
  if (info.value.loggedIn) tab.value = "profile";
});

function note(result, extraHint = "") {
  if (!result) { msg.value = { ok: false, text: "无宿主：账号功能只在 MFMath.exe 里可用", hint: "" }; return; }
  if (result.ok) {
    msg.value = { ok: true, text: result.msg || result.warning || "完成", hint: extraHint || result.note || "" };
  } else {
    msg.value = { ok: false, text: result.error || "操作失败", hint: hintFor(result.kind) };
  }
}

async function wrap(name, fn, extraHint = "") {
  if (busy.value) return;
  busy.value = name;
  msg.value = null;
  try { note(await fn(), extraHint); } catch (e) { msg.value = { ok: false, text: String(e?.message || e), hint: "" }; }
  finally { busy.value = ""; }
}

const doLogin = () => wrap("login", () => login(form.value.username, form.value.password, form.value.remember),
  "登录只影响身份与额度显示：未登录时本地全部计算功能照常可用。");

const doLogout = () => wrap("logout", async () => {
  const r = await logout();
  history.value = [];
  tab.value = "login";
  return r;
});

const doRefresh = () => wrap("refresh", () => refreshProfile());
const doClear = () => wrap("clear", async () => {
  const r = await clearLocal();
  history.value = [];
  tab.value = "login";
  return r;
}, "本机凭据已清除。");

const doSendCode = () => wrap("sendcode", () => sendCode(reg.value.email), "验证码会发到填写的邮箱（站点发信）。");
const doRegister = () => wrap("register", async () => {
  const r = await register({
    username: reg.value.username, email: reg.value.email,
    password: reg.value.password, code: reg.value.code,
  });
  if (r && r.ok) { form.value.username = reg.value.username; tab.value = "login"; }
  return r;
}, "注册成功后可回到登录页登录；若站点要求邮箱验证，先去邮箱拿验证码再点「验证邮箱」。");
const doVerify = () => wrap("verify", () => verifyCode(reg.value.username, reg.value.code));
const doResend = () => wrap("resend", () => resendCode(reg.value.username, reg.value.email));
const doChangePwd = () => wrap("password", () => changePassword(pwd.value.old, pwd.value.next));
const doLoadHistory = () => wrap("history", async () => {
  const r = await loginHistory();
  history.value = (r && r.items) || [];
  return r;
});
const doVersion = () => wrap("version", async () => {
  const r = await siteVersion();
  if (r && r.ok) version.value = r;
  return { ok: r?.ok, msg: r?.ok ? `站点最新版本 ${r.latest}（${r.date}）` : r?.error, error: r?.error, kind: r?.kind };
});
</script>

<template>
  <div class="ac" data-account="view">
    <header class="ac-head">
      <h2>账号</h2>
      <p class="ac-note" data-account="endpoint">
        服务器：<b>{{ info.baseUrl }}</b>
        <span v-if="info.offline" class="bad" data-account="offline"> · 当前离线，显示的是上次登录的资料（未校验）</span>
      </p>
      <p class="ac-promise" data-account="promise">
        未登录、要不要登录、断网 —— <b>都不影响任何计算功能</b>。计算全部在本机 C++ 引擎里完成，
        这里只负责身份与额度显示。
      </p>
    </header>

    <div v-if="!accountHosted" class="ac-blocked" data-account="blocked">
      <p>浏览器预览里没有宿主桥。账号功能需要宿主（token 只存宿主、由宿主发请求），所以这里不能用。</p>
      <p class="ac-sub">之所以不做"前端直接 fetch"：页面跑在虚拟主机下直连站点会撞 CORS，凭据也不该进渲染进程。</p>
    </div>

    <template v-else>
      <nav class="ac-tabs">
        <button :class="{ on: tab === 'login' }" data-account="tab-login" @click="tab = 'login'">登录</button>
        <button :class="{ on: tab === 'register' }" data-account="tab-register" @click="tab = 'register'">注册</button>
        <button :class="{ on: tab === 'profile' }" data-account="tab-profile" :disabled="!loggedIn" @click="tab = 'profile'">我的账号</button>
        <button :class="{ on: tab === 'password' }" data-account="tab-password" :disabled="!loggedIn" @click="tab = 'password'">修改密码</button>
        <button :class="{ on: tab === 'history' }" data-account="tab-history" :disabled="!loggedIn" @click="tab = 'history'">登录记录</button>
      </nav>

      <p v-if="msg" class="ac-msg" :class="{ bad: !msg.ok }" data-account="msg">
        {{ msg.text }}<span v-if="msg.hint" class="ac-hint"> —— {{ msg.hint }}</span>
      </p>

      <!-- 登录 -->
      <section v-if="tab === 'login'" class="ac-body" data-account="pane-login">
        <label class="ac-f">
          <span>用户名</span>
          <input v-model="form.username" data-account="username" type="text" autocomplete="username"
                 @keydown.enter="doLogin" />
        </label>
        <label class="ac-f">
          <span>密码</span>
          <input v-model="form.password" data-account="password" type="password" autocomplete="current-password"
                 @keydown.enter="doLogin" />
        </label>
        <label class="ac-sw">
          <input v-model="form.remember" data-account="remember" type="checkbox" />
          <span>记住我（长会话：桌面端不必每 30 分钟重登一次）</span>
        </label>
        <div class="ac-actions">
          <button class="btn btn-primary" data-account="do-login" :disabled="busy === 'login'" @click="doLogin">
            {{ busy === "login" ? "登录中…" : "登录" }}
          </button>
          <button class="btn btn-ghost" data-account="go-register" @click="tab = 'register'">还没有账号？去注册</button>
        </div>
        <p v-if="loggedIn" class="ac-sub" data-account="already-in">
          当前已登录：{{ info.username }}<span v-if="sessionText"> · {{ sessionText }}</span>
        </p>
      </section>

      <!-- 注册 -->
      <section v-else-if="tab === 'register'" class="ac-body" data-account="pane-register">
        <label class="ac-f"><span>用户名</span>
          <input v-model="reg.username" data-account="reg-username" type="text" placeholder="3 个字符以上，字母/数字/下划线" /></label>
        <label class="ac-f"><span>邮箱</span>
          <input v-model="reg.email" data-account="reg-email" type="email" placeholder="用于接收验证码" /></label>
        <label class="ac-f"><span>密码</span>
          <input v-model="reg.password" data-account="reg-password" type="password" placeholder="8 位以上，含字母与数字" /></label>
        <label class="ac-f"><span>邮箱验证码</span>
          <input v-model="reg.code" data-account="reg-code" type="text" placeholder="可留空：留空则由站点发验证码到邮箱" /></label>
        <div class="ac-actions">
          <button class="btn" data-account="send-code" :disabled="!!busy" @click="doSendCode">发送验证码</button>
          <button class="btn btn-primary" data-account="do-register" :disabled="!!busy" @click="doRegister">注册</button>
          <button class="btn btn-ghost" data-account="verify-code" :disabled="!!busy" @click="doVerify">验证邮箱</button>
          <button class="btn btn-ghost" data-account="resend-code" :disabled="!!busy" @click="doResend">重发验证码</button>
        </div>
        <p class="ac-sub">校验规则由站点决定（用户名 3 位以上且仅字母数字下划线、密码 8 位以上含字母和数字、不支持临时邮箱）。
          站点返回什么这里就显示什么。</p>
      </section>

      <!-- 我的账号 -->
      <section v-else-if="tab === 'profile'" class="ac-body" data-account="pane-profile">
        <table class="ac-table">
          <tbody>
            <tr><th>用户名</th><td data-account="me-username">{{ info.username || "—" }}</td></tr>
            <tr><th>邮箱</th><td data-account="me-email">{{ info.email || "—" }}</td></tr>
            <tr><th>身份</th><td>{{ roleText }}</td></tr>
            <tr><th>可用额度</th><td data-account="me-balance">{{ info.balance }}</td></tr>
            <tr><th>AI 服务</th><td data-account="me-ai">{{ info.hasAiService ? "已开通" : "未开通" }}</td></tr>
            <tr><th>账号状态</th><td>{{ info.isActive ? "已激活" : "未激活（需邮箱验证）" }}</td></tr>
            <tr><th>会话</th><td data-account="me-session">{{ sessionText || "—" }}</td></tr>
            <tr><th>资料校验</th><td data-account="me-verified">
              {{ info.profileVerified ? "刚从服务器取到" : "来自缓存（未校验，可能已过期）" }}</td></tr>
          </tbody>
        </table>
        <div class="ac-actions">
          <button class="btn" data-account="do-refresh" :disabled="!!busy" @click="doRefresh">重新校验</button>
          <button class="btn" data-account="do-version" :disabled="!!busy" @click="doVersion">查站点版本</button>
          <button class="btn btn-ghost" data-account="do-logout" :disabled="!!busy" @click="doLogout">退出登录</button>
          <button class="btn btn-ghost" data-account="do-clear" :disabled="!!busy" @click="doClear">清除本机凭据</button>
        </div>
        <p v-if="version" class="ac-sub" data-account="version">
          站点最新：{{ version.latest }}（{{ version.date }}）
        </p>
        <p class="ac-sub">「退出登录」会通知站点把这次会话加入黑名单；断网时也会先在本机退出。
          AI 这项显示的是站点侧的服务开通状态，桌面端的 AI 助手用的是你自己填的接口与密钥，两者互不影响。</p>
      </section>

      <!-- 修改密码 -->
      <section v-else-if="tab === 'password'" class="ac-body" data-account="pane-password">
        <label class="ac-f"><span>当前密码</span>
          <input v-model="pwd.old" data-account="pwd-old" type="password" /></label>
        <label class="ac-f"><span>新密码</span>
          <input v-model="pwd.next" data-account="pwd-new" type="password" /></label>
        <div class="ac-actions">
          <button class="btn btn-primary" data-account="do-password" :disabled="!!busy" @click="doChangePwd">修改密码</button>
        </div>
        <p class="ac-sub">改密码不会让已登录的会话立刻失效（token 在有效期内仍可用）；要立刻踢掉请在站点上登出。</p>
      </section>

      <!-- 登录记录 -->
      <section v-else-if="tab === 'history'" class="ac-body" data-account="pane-history">
        <div class="ac-actions">
          <button class="btn" data-account="do-history" :disabled="!!busy" @click="doLoadHistory">读取最近登录记录</button>
        </div>
        <table v-if="history.length" class="ac-table" data-account="history-table">
          <thead><tr><th>时间</th><th>IP</th><th>客户端</th></tr></thead>
          <tbody>
            <tr v-for="(h, i) in history" :key="i">
              <td>{{ h.at ? new Date(h.at).toLocaleString() : "—" }}</td>
              <td class="mono">{{ h.ip || "—" }}</td>
              <td class="mono">{{ h.ua || "—" }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="ac-sub" data-account="history-empty">还没有读取，或这个账号没有记录。</p>
      </section>

      <!-- 自检（脱敏 + 离线可用性） -->
      <details class="ac-check">
        <summary>连接自检（不联网）</summary>
        <ul data-account="selfcheck">
          <li v-for="(c, i) in (selfCheck?.checks || [])" :key="i" :class="{ bad: !c.ok }">
            <span>{{ c.ok ? "✔" : "✗" }}</span>
            <b>{{ c.name }}</b>
            <span class="ac-sub">{{ c.detail }}</span>
          </li>
        </ul>
      </details>
    </template>
  </div>
</template>

<style scoped>
.ac { padding: 14px 18px 28px; max-width: 860px; }
.ac-head h2 { margin: 0 0 4px; font-size: 17px; }
.ac-note { margin: 0 0 6px; font-size: 12px; color: var(--muted); }
.ac-note .bad { color: var(--warn, #c77); }
.ac-promise { margin: 0 0 12px; font-size: 12px; line-height: 1.7; color: var(--text); }
.ac-sub { font-size: 11.5px; color: var(--muted); line-height: 1.7; margin: 6px 0 0; }

.ac-blocked { border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
.ac-blocked p { margin: 0 0 6px; font-size: 13px; }

.ac-tabs { display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }
.ac-tabs button {
  background: none; border: 1px solid var(--border); color: var(--muted);
  border-radius: 7px; padding: 4px 12px; font-size: 12.5px; cursor: pointer;
}
.ac-tabs button.on { color: var(--accent, #5a82f0); border-color: var(--accent, #5a82f0); }
.ac-tabs button:disabled { opacity: .45; cursor: not-allowed; }

.ac-body { display: flex; flex-direction: column; gap: 9px; max-width: 460px; }
.ac-f { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--muted); }
.ac-f span { width: 78px; flex: none; }
.ac-f input {
  flex: 1; min-width: 0; font: inherit; font-size: 12.5px; padding: 6px 8px;
  border: 1px solid var(--border); border-radius: 7px; background: var(--bg); color: var(--text);
}
.ac-sw { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--muted); }
.ac-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 2px; }

.ac-msg { margin: 0 0 10px; font-size: 12.5px; color: var(--accent, #5a82f0); }
.ac-msg.bad { color: var(--danger, #d05a5a); }
.ac-hint { color: var(--muted); }

.ac-table { width: 100%; border-collapse: collapse; font-size: 12.5px; max-width: 520px; }
.ac-table th, .ac-table td { text-align: left; padding: 4px 8px 4px 0; border-bottom: 1px solid var(--border); }
.ac-table th { color: var(--muted); font-weight: 600; width: 96px; }
.mono { font-family: ui-monospace, Consolas, monospace; font-size: 11.5px; }

.ac-check { margin-top: 16px; font-size: 12px; color: var(--muted); }
.ac-check summary { cursor: pointer; }
.ac-check ul { list-style: none; margin: 8px 0 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.ac-check li { display: flex; gap: 6px; }
.ac-check li.bad { color: var(--danger, #d05a5a); }
</style>
