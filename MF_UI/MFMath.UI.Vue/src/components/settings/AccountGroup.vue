<script setup>
/**
 * AccountGroup.vue — 设置 → 账号
 *
 * 只放"影响连接方式"的几项（站点地址、会话策略、凭据清除、自检）。
 * 登录/注册/改密这些操作在账号页（顶栏用户名 → /account），不在这里重复一遍。
 */
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  accountInfo, accountHosted, refreshAccountInfo, accountConfigure,
  clearLocal, accountSelfCheck, refreshProfile, refreshToken,
} from "../../lib/account/bridge.js";

const router = useRouter();
const baseDraft = ref("");
const saved = ref("");
const check = ref(null);

onMounted(() => {
  refreshAccountInfo();
  baseDraft.value = accountInfo.value.baseUrl;
  check.value = accountSelfCheck();
});

function flash(text) {
  saved.value = text;
  setTimeout(() => { if (saved.value === text) saved.value = ""; }, 2500);
}

function set(patch, label) {
  const r = accountConfigure(patch);
  if (r && r.ok) { flash(label + " 已保存"); refreshAccountInfo(); }
  else flash((r && r.error) || "保存失败");
}

function saveBase() {
  const r = accountConfigure({ baseUrl: baseDraft.value });
  if (r && r.ok) {
    baseDraft.value = accountInfo.value.baseUrl;
    refreshAccountInfo();
    flash("站点地址已保存");
  } else flash((r && r.error) || "保存失败");
}

/* ⚠ 下面三个桥函数是**同步**的（返回普通对象，不是 Promise）。
 *
 * 原来模板里写成 `clearLocal().then(...)` —— 点击必抛
 *   TypeError: clearLocal(...).then is not a function
 * 宿主调用其实执行了（凭据真被清掉、续期真发了），但**用户看不到任何反馈**，
 * 控制台还留着未处理异常。
 *
 * cdp-account 之所以 52/0 也没抓到：它直接调 `window.__mfAccount.*` 这个调试钩子，
 * **从来没有点过这三个按钮** —— 测了桥，没测控件。 */
function onClearLocal() {
  const r = clearLocal();
  flash(r && r.ok === false ? (r.error || "清除失败") : "本机凭据已清除");
  refreshAccountInfo();
}
function onRefreshProfile() {
  const r = refreshProfile();
  flash(r && r.ok ? "已重新校验" : ((r && r.error) || "校验失败"));
}
function onRefreshToken() {
  const r = refreshToken();
  flash(r && r.ok ? "已续期" : ((r && r.error) || "续期失败"));
}

const info = accountInfo;
const sessionText = computed(() => {
  if (!info.value.loggedIn) return "未登录";
  const s = info.value.sessionExpiresInSec || 0;
  if (s <= 0) return "已登录（到期时间未知）";
  if (s < 3600) return `已登录 · ${Math.round(s / 60)} 分钟后到期`;
  if (s < 86400) return `已登录 · ${Math.round(s / 3600)} 小时后到期`;
  return `已登录 · ${Math.round(s / 86400)} 天后到期`;
});
const tokenText = computed(() => ({
  dpapi: "已加密落盘（DPAPI，仅本机当前用户可解）",
  memory: "仅本次运行的内存里（未落盘）",
  none: "无",
}[info.value.tokenSource] || "未知"));
</script>

<template>
  <div class="ag">
    <p v-if="!accountHosted" class="warn" data-setting="account.baseUrl">
      浏览器预览里没有宿主桥：账号功能需要宿主发请求（token 也只存宿主），这里只能看不能改。
    </p>

    <!-- ① 服务器地址 -->
    <section class="row" data-setting="account.baseUrl">
      <div class="lab">
        <span>站点地址</span>
        <small>软件访问的服务器；自建部署可以改。只接受 http/https</small>
      </div>
      <div class="ctl col">
        <div class="inline">
          <input class="inp mono" data-account-set="baseUrl" v-model="baseDraft" @keydown.enter="saveBase" />
          <button class="btn" data-account="save-base" @click="saveBase">保存</button>
        </div>
        <p class="hint">
          这个值决定 token 会被发往哪里，所以只接受 http/https，且不接受带查询串、片段或用户信息的地址。
          当前：<b>{{ info.baseUrl }}</b>
        </p>
      </div>
    </section>

    <!-- ② 会话 -->
    <section class="row" data-setting="account.session">
      <div class="lab">
        <span>登录会话</span>
        <small>「记住我」会换一枚长 token（站点侧 30 天），免得每 30 分钟重登</small>
      </div>
      <div class="ctl col">
        <label class="sw">
          <input type="checkbox" data-account-set="remember" :checked="info.remember"
                 @change="set({ remember: $event.target.checked }, '记住我')" />
          <span>记住我（下次登录默认使用长会话）</span>
        </label>
        <label class="sw">
          <input type="checkbox" data-account-set="autoRefresh" :checked="info.autoRefresh"
                 @change="set({ autoRefresh: $event.target.checked }, '自动续期')" />
          <span>临期自动续期（剩余不足 5 分钟时静默换新 token）</span>
        </label>
        <p class="state" data-account="session-state">{{ sessionText }}</p>
        <p class="hint">
          续期只在"当前 token 仍然有效"时成功；一旦你登出（站点把该会话加入黑名单），续期也会被拒 —— 
          这是有意的：不能让登出被绕过。
        </p>
      </div>
    </section>

    <!-- ③ 凭据 -->
    <section class="row" data-setting="account.credentials">
      <div class="lab">
        <span>本机凭据</span>
        <small>token 只存在本机（DPAPI 加密），页面读不到它</small>
      </div>
      <div class="ctl col">
        <p class="state" data-account="token-state">token：{{ tokenText }}</p>
        <p class="hint">保存位置：<code>{{ info.configPath }}</code></p>
        <div class="inline">
          <button class="btn btn-ghost" data-account="clear" @click="onClearLocal()">
            清除本机凭据
          </button>
          <button class="btn" data-account="refresh-profile" :disabled="!info.loggedIn"
                  @click="onRefreshProfile()">
            重新校验登录状态
          </button>
          <button class="btn btn-ghost" data-account="refresh-token" :disabled="!info.loggedIn"
                  @click="onRefreshToken()">
            立即续期
          </button>
        </div>
        <p class="hint">「清除本机凭据」只清本机，不通知服务器（断网也能用）；要同时让服务器把会话作废，去账号页点「退出登录」。</p>
      </div>
    </section>

    <!-- ④ 离线承诺 -->
    <section class="row" data-setting="account.offline">
      <div class="lab">
        <span>离线承诺</span>
        <small>这一层永远不会挡住计算</small>
      </div>
      <div class="ctl col">
        <p class="hint">
          <b>未登录、不登录、断网、站点挂了 —— 本地全部功能照常可用。</b>
          所有计算都在本机 C++ 引擎里完成，账号只负责身份与额度显示；
          站点的接口调用全部异步 + 有超时，界面不会因为网络等待而卡住。
          断网时账号页显示的是上次登录缓存的资料，并明确标注「未校验」。
        </p>
        <button class="btn btn-ghost" data-account="go-page" @click="router.push('/account')">打开账号页</button>
      </div>
    </section>

    <!-- ⑤ 自检 -->
    <section class="row" data-setting="account.selftest">
      <div class="lab">
        <span>连接自检</span>
        <small>站点地址闸门 / 错误体解析 / JWT 到期解析 / 脱敏 —— **不联网**</small>
      </div>
      <div class="ctl col">
        <button class="btn" data-account="selfcheck" @click="check = accountSelfCheck()">重新自检</button>
        <ul class="checks" data-account="selfcheck-list">
          <li v-for="(c, i) in (check?.checks || [])" :key="i" :class="{ bad: !c.ok }">
            <span class="dot">{{ c.ok ? "✔" : "✗" }}</span>
            <span class="ck-name">{{ c.name }}</span>
            <span class="ck-detail">{{ c.detail }}</span>
          </li>
        </ul>
      </div>
    </section>

    <p v-if="saved" class="saved" data-account="saved">{{ saved }}</p>
  </div>
</template>

<style scoped>
.ag { display: flex; flex-direction: column; gap: 2px; }
.row { display: flex; gap: 16px; padding: 12px 4px; border-bottom: 1px solid var(--border); align-items: flex-start; }
.lab { width: 190px; flex: none; display: flex; flex-direction: column; gap: 3px; }
.lab span { font-size: 13.5px; }
.lab small { color: var(--muted); font-size: 11.5px; line-height: 1.5; }
.ctl { flex: 1; min-width: 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ctl.col { flex-direction: column; align-items: stretch; gap: 7px; }
.inline { display: flex; align-items: center; gap: 6px; }
.inp {
  background: var(--bg); color: var(--text); border: 1px solid var(--border);
  border-radius: 6px; padding: 5px 7px; font-size: 12.5px; min-width: 0; flex: 1;
}
.mono { font-family: ui-monospace, Consolas, monospace; }
.sw { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--muted); }
.state { margin: 0; font-size: 12.5px; }
.hint { margin: 0; font-size: 11.5px; line-height: 1.7; color: var(--muted); }
.hint code { font-family: ui-monospace, Consolas, monospace; }
.warn { color: var(--warn, #c77); font-size: 12.5px; }
.checks { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.checks li { display: flex; gap: 6px; font-size: 11.5px; color: var(--muted); }
.checks li.bad { color: var(--danger, #d05a5a); }
.ck-name { color: var(--text); flex: none; }
.ck-detail { overflow: hidden; text-overflow: ellipsis; }
.saved { position: sticky; bottom: 0; margin: 0; padding: 6px 4px; font-size: 11.5px; color: var(--accent, #5a82f0); }
</style>
