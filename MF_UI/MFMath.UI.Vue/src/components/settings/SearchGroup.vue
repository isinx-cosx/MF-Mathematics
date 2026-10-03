<script setup>
/**
 * SearchGroup.vue — 设置 → 搜索
 *
 * 与 AI 那条同一套规矩：
 *   · **App ID 只写不读**（存在宿主、DPAPI 密文），这里只说"有没有、是不是明文"；
 *   · 面板上明确写出**查询会发往哪个站点**；
 *   · 自检不联网（解析器拿内置样本跑），因为最容易随对方改版而碎的就是解析那一层。
 */
import { computed, onMounted, ref } from "vue";
import {
  searchInfo, searchHosted, SEARCH_ENGINES,
  refreshSearchInfo, searchConfigure, setWolframKey, clearWolframKey,
  searchSelfCheck, clearCache, cacheStats,
} from "../../lib/search/bridge.js";

const keyDraft = ref("");
const keyMsg = ref("");
const saved = ref("");
const selfCheck = ref(null);
const cache = ref({ entries: 0, bytes: 0 });

onMounted(() => {
  refreshSearchInfo();
  selfCheck.value = searchSelfCheck();
  cache.value = cacheStats();
});

function flash(msg) {
  saved.value = msg;
  setTimeout(() => { if (saved.value === msg) saved.value = ""; }, 2500);
}

function set(patch, label) {
  const r = searchConfigure(patch);
  if (r && r.ok) flash(label + " 已保存");
  else flash((r && r.error) || "保存失败");
}

function saveKey() {
  const k = keyDraft.value.trim();
  if (!k) { keyMsg.value = "先粘贴一个 App ID"; return; }
  const r = setWolframKey(k);
  keyDraft.value = "";
  keyMsg.value = r && r.ok ? (r.warning || "App ID 已保存") : ((r && r.error) || "保存失败");
}

function dropKey() {
  const r = clearWolframKey();
  keyMsg.value = r && r.ok ? "App ID 已清除" : ((r && r.error) || "清除失败");
}

function doClearCache() {
  const r = clearCache();
  cache.value = cacheStats();
  flash(r && r.ok ? `已清空 ${r.cleared || 0} 条缓存` : "清空失败");
}

const cfg = searchInfo;
const keyState = computed(() => {
  if (!cfg.value.hasWolframKey) return "未配置";
  return cfg.value.wolframKeySource === "memory"
    ? "已配置（仅本次运行的内存里，未落盘）"
    : "已配置（DPAPI 密文落盘）";
});
const cacheKb = computed(() => Math.max(0, Math.round((cache.value.bytes || 0) / 1024)));
</script>

<template>
  <div class="sg">
    <p v-if="!searchHosted" class="sg-warn" data-setting="search.engine">
      浏览器预览里没有宿主桥：联网搜索的抓取与凭据都在 MFMath.exe 中，这里只能看不能改。
    </p>

    <!-- ① 引擎 -->
    <section class="row" data-setting="search.engine">
      <div class="lab">
        <span>搜索引擎</span>
        <small>免密钥的只有 DuckDuckGo；Wolfram 的答案最"数学"，但需要自备 App ID</small>
      </div>
      <div class="ctl col">
        <label v-for="e in SEARCH_ENGINES" :key="e.value" class="sw">
          <input type="radio" name="search-engine" :value="e.value" :checked="cfg.engine === e.value"
                 :data-search-set="'engine-' + e.value"
                 @change="set({ engine: e.value }, '引擎')" />
          <span>{{ e.label }}</span>
        </label>
        <p class="state">
          查询会发往：<b>{{ cfg.endpoint }}</b>
        </p>
      </div>
    </section>

    <!-- ② Wolfram App ID -->
    <section class="row" data-setting="search.wolframKey">
      <div class="lab">
        <span>Wolfram App ID</span>
        <small>只写不读：App ID 存在宿主侧，页面拿不到它（与 AI 密钥同一条规矩）</small>
      </div>
      <div class="ctl col">
        <p class="state" data-search="key-state">
          {{ keyState }}
          <span v-if="!cfg.dpapiAvailable" class="warn">· 本机 DPAPI 不可用，只留内存（不写明文）</span>
        </p>
        <div class="inline">
          <input class="inp mono" type="password" placeholder="粘贴 App ID（留空表示不改）"
                 data-search-set="appid" v-model="keyDraft" @keydown.enter="saveKey" />
          <button class="btn" data-search="save-key" @click="saveKey">保存</button>
          <button class="btn btn-ghost" data-search="clear-key" @click="dropKey">清除</button>
        </div>
        <p class="hint">
          App ID 去 Wolfram 开发者门户申请（免费的 Short Answers API 就够用）。
          没有它也能用：DuckDuckGo 与自定义端点都不需要。
        </p>
        <p v-if="keyMsg" class="note" data-search="key-msg">{{ keyMsg }}</p>
      </div>
    </section>

    <!-- ③ 自定义端点 -->
    <section class="row" data-setting="search.customUrl">
      <div class="lab">
        <span>自定义端点</span>
        <small>需要一个 **SearXNG 兼容的 JSON 接口**（很多公共实例默认关掉了 format=json）</small>
      </div>
      <div class="ctl col">
        <input class="inp mono" data-search-set="customUrl" :value="cfg.customUrl"
               placeholder="https://searx.example.com"
               @change="set({ customUrl: $event.target.value }, '自定义端点')" />
        <p class="hint">
          填根地址即可，查询时会请求 <code>{端点}/search?q=…&amp;format=json</code>。
          自建实例通常需要在 settings.yml 里把 <code>search.formats</code> 打开 json。
        </p>
      </div>
    </section>

    <!-- ④ 超时与条数 -->
    <section class="row" data-setting="search.timeout">
      <div class="lab">
        <span>超时</span>
        <small>单个来源最多等多久；超时会明确报"超时"，不是笼统的"搜索失败"</small>
      </div>
      <div class="ctl col">
        <label class="inline">
          超时
          <input class="inp num" type="number" min="3" max="120" data-search-set="timeoutSec"
                 :value="cfg.timeoutSec" @change="set({ timeoutSec: Number($event.target.value) }, '超时')" />
          秒
        </label>
      </div>
    </section>

    <section class="row" data-setting="search.results">
      <div class="lab">
        <span>结果条数</span>
        <small>每个来源最多取多少条</small>
      </div>
      <div class="ctl col">
        <label class="inline">
          最多
          <input class="inp num" type="number" min="1" max="20" data-search-set="resultCount"
                 :value="cfg.resultCount" @change="set({ resultCount: Number($event.target.value) }, '结果条数')" />
          条
        </label>
      </div>
    </section>

    <!-- ⑤ 缓存 -->
    <section class="row" data-setting="search.cache">
      <div class="lab">
        <span>本地缓存</span>
        <small>缓存键**含引擎**：换了引擎不会误命中旧结果（v1 的缺陷）</small>
      </div>
      <div class="ctl col">
        <label class="sw">
          <input type="checkbox" data-search-set="cacheEnabled" :checked="cfg.cacheEnabled"
                 @change="set({ cacheEnabled: $event.target.checked }, '缓存开关')" />
          <span>启用缓存（命中时不出网）</span>
        </label>
        <label class="inline">
          有效期
          <input class="inp num" type="number" min="0" max="720" data-search-set="cacheTtlHours"
                 :value="cfg.cacheTtlHours" @change="set({ cacheTtlHours: Number($event.target.value) }, '缓存有效期')" />
          小时（0 = 不过期）
        </label>
        <p class="state" data-search="cache-stats">
          当前 {{ cache.entries }} 条 · {{ cacheKb }} KB
        </p>
        <button class="btn btn-ghost" data-search="clear-cache" @click="doClearCache">清空缓存</button>
      </div>
    </section>

    <!-- ⑥ 隐私说明 -->
    <section class="row" data-setting="search.privacy">
      <div class="lab">
        <span>隐私说明</span>
        <small>说清楚什么会离开这台机器</small>
      </div>
      <div class="ctl col">
        <p class="hint">
          只有你点「搜索」时才会发出请求：**查询词**会发给上面写的那个站点。
          结果会缓存到 <code>%LOCALAPPDATA%\MFMath\search_cache.json</code>（可关、可清）。
          Wolfram 的 App ID 只在你选择 Wolfram 时随请求发给 api.wolframalpha.com。
          页面本身不直连任何站点，也不接触任何凭据。
        </p>
      </div>
    </section>

    <!-- ⑦ 自检 -->
    <section class="row" data-setting="search.selftest">
      <div class="lab">
        <span>自检</span>
        <small>解析器拿内置样本跑、缓存键含引擎、打开链接的协议闸门 —— **不联网**</small>
      </div>
      <div class="ctl col">
        <button class="btn" data-search="selfcheck" @click="selfCheck = searchSelfCheck()">重新自检</button>
        <ul class="checks" data-search="selfcheck-list">
          <li v-for="(c, i) in (selfCheck?.checks || [])" :key="i" :class="{ bad: !c.ok }">
            <span class="dot">{{ c.ok ? "✔" : "✗" }}</span>
            <span class="ck-name">{{ c.name }}</span>
            <span class="ck-detail">{{ c.detail }}</span>
          </li>
        </ul>
      </div>
    </section>

    <p v-if="saved" class="sg-saved" data-search="saved">{{ saved }}</p>
  </div>
</template>

<style scoped>
.sg { display: flex; flex-direction: column; gap: 2px; }
.row { display: flex; gap: 16px; padding: 12px 4px; border-bottom: 1px solid var(--border); align-items: flex-start; }
.lab { width: 190px; flex: none; display: flex; flex-direction: column; gap: 3px; }
.lab span { font-size: 13.5px; }
.lab small { color: var(--muted); font-size: 11.5px; line-height: 1.5; }
.ctl { flex: 1; min-width: 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ctl.col { flex-direction: column; align-items: stretch; gap: 7px; }
.inline { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--muted); }
.inp {
  background: var(--bg); color: var(--text); border: 1px solid var(--border);
  border-radius: 6px; padding: 5px 7px; font-size: 12.5px; min-width: 0; flex: 1;
}
.inp.num { max-width: 96px; flex: none; }
.mono { font-family: ui-monospace, Consolas, monospace; }
.sw { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--muted); }
.state { margin: 0; font-size: 12.5px; color: var(--text); }
.state .warn, .sg-warn { color: var(--warn, #c77); }
.hint { margin: 0; font-size: 11.5px; line-height: 1.7; color: var(--muted); }
.hint code { font-family: ui-monospace, Consolas, monospace; }
.note { margin: 0; font-size: 11.5px; color: var(--muted); }
.checks { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.checks li { display: flex; gap: 6px; font-size: 11.5px; color: var(--muted); }
.checks li.bad { color: var(--danger, #d05a5a); }
.ck-name { color: var(--text); flex: none; }
.ck-detail { overflow: hidden; text-overflow: ellipsis; }
.sg-saved { position: sticky; bottom: 0; margin: 0; padding: 6px 4px; font-size: 11.5px; color: var(--accent, #5a82f0); }
</style>
