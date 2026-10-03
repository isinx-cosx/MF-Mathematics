<script setup>
/**
 * SearchView.vue — 联网搜索页（路由 /tools/search）
 *
 * 为什么是**页面**而不是弹窗：搜索结果是要来回看、要复制、要送进计算页的内容，
 * 做成路由页面之后还能被别处引用（教程示例「联网搜索」直接落到 /tools/search?q=…，
 * 顶栏「搜索」也是跳到这儿），而不是只能从顶栏点开的一个浮层。
 *
 * 三条纪律：
 *   ① **结果只以文本渲染**（插值），网址只作为文本展示；打开链接经宿主 `OpenUrl`，
 *      那条闸门只放行 http/https —— 搜索结果是外部内容，不能让它变成"启动本机程序"的入口。
 *   ② **面板上明说查询会发往哪个站点**（宿主 Info 里给的 endpoint），隐私说明不是装饰。
 *   ③ 结果里的表达式只是**建议**，用户点「算这个」才送去计算页，且由**引擎**计算 ——
 *      搜索引擎和 AI 都不当计算源。
 */
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  searchInfo, searchState, searchHosted, SEARCH_ENGINES,
  initSearch, refreshSearchInfo, runSearch, cancelSearch,
  openUrl, extractExpr,
} from "../../lib/search/bridge.js";
import { setPending } from "../../lib/workspace/pendingInput.js";

const route = useRoute();
const router = useRouter();

const draft = ref("");
const engine = ref("");
const copied = ref("");

onMounted(() => {
  initSearch();
  refreshSearchInfo();
  engine.value = searchInfo.value.engine;
  const q = String(route.query.q || "").trim();
  if (q) { draft.value = q; doSearch(); }
});

// 深链 /tools/search?q=… 在页面已挂载时也要生效（教程示例会这样进来）
watch(() => route.query.q, (q) => {
  const s = String(q || "").trim();
  if (s && s !== searchState.value.query) { draft.value = s; doSearch(); }
});

function doSearch(noCache = false) {
  const r = runSearch(draft.value, { engine: engine.value, noCache });
  if (!r.ok) return;   // 失败原因已经进 searchState.error，由页面显示
}

function onKeydown(e) {
  if (e.key === "Enter") { e.preventDefault(); doSearch(); }
}

const endpointLine = computed(() => searchInfo.value.endpoint || "（未配置）");

const errorHint = computed(() => {
  const e = searchState.value.error;
  if (!e) return "";
  switch (e.kind) {
    case "config": return "这类问题要先补配置：去「设置 → 搜索」看一眼。";
    case "network": return "网络没通。检查网络或代理，也可以换个引擎试试。";
    case "http": return "对方站点拒绝了这次请求（可能是反爬或限流）。稍后再试，或改用自定义端点。";
    case "parse": return "对方返回的形状变了（通常是站点改版）。可以改用自定义端点。";
    case "timeout": return "超时了。可以在「设置 → 搜索」里把超时调大，或换个引擎。";
    case "aborted": return "已取消。";
    default: return "可以重试，或用「忽略缓存」再搜一次。";
  }
});

function open(url) { openUrl(url); }

async function copy(text) {
  try {
    await navigator.clipboard?.writeText(String(text || ""));
    copied.value = String(text || "").slice(0, 40);
    setTimeout(() => { copied.value = ""; }, 1500);
  } catch { /* 忽略 */ }
}

/** 把结果里的表达式送去计算页：走 pendingInput 的既有通路，算的是引擎 */
function sendToCalc(expr) {
  const e = String(expr || "").trim();
  if (!e) return;
  setPending({ expr: e, mode: "基础运算", operation: "基础运算", label: e });
  router.push("/calc/basic");
}
</script>

<template>
  <div class="sv">
    <header class="sv-head">
      <h2>联网搜索</h2>
      <p class="sv-note" data-search="endpoint">
        查询会发往：<b>{{ endpointLine }}</b>
        <span v-if="searchInfo.cacheEnabled"> · 命中缓存时不出网（TTL {{ searchInfo.cacheTtlHours }} 小时）</span>
      </p>
    </header>

    <div v-if="!searchHosted" class="sv-blocked" data-search="blocked">
      <p>浏览器预览里没有宿主桥。联网搜索的凭据与网络都在 MFMath.exe 里，所以这里不能用。</p>
      <p class="sv-sub">
        之所以不做"前端直接 fetch"：页面跑在虚拟主机下，直连外部站点会撞 CORS；
        而 Wolfram 的 App ID 也不该进渲染进程。这两条与 AI 那条边界是同一个理由。
      </p>
    </div>

    <template v-else>
      <div class="sv-bar">
        <!-- 教程引导的目标名沿用 v1 的语义 ID（search_panel.*） -->
        <input v-model="draft" data-search="input" data-tour="search_panel.input" class="sv-input" type="search"
               placeholder="搜概念、找公式、查定义…（Enter 开始）" @keydown="onKeydown" />
        <select v-model="engine" data-search="engine" class="sv-select" @change="searchInfo.engine !== engine && null">
          <option v-for="e in SEARCH_ENGINES" :key="e.value" :value="e.value">{{ e.label }}</option>
        </select>
        <button v-if="!searchState.running" class="btn btn-primary" data-search="go" @click="doSearch()">搜索</button>
        <button v-else class="btn" data-search="stop" @click="cancelSearch">停止</button>
        <button class="btn btn-ghost" data-search="nocache" title="跳过缓存，强制重新抓取"
                @click="doSearch(true)">忽略缓存</button>
      </div>

      <p v-if="engine === 'wolfram' && !searchInfo.hasWolframKey" class="sv-warn" data-search="need-key">
        Wolfram 需要 App ID：<router-link to="/settings?group=search">去设置里填一个</router-link>，或改用 DuckDuckGo。
      </p>
      <p v-if="engine === 'custom' && !searchInfo.customUrl" class="sv-warn" data-search="need-url">
        自定义端点还没填：<router-link to="/settings?group=search">去设置里写上</router-link>（SearXNG 的 JSON 接口地址）。
      </p>

      <p v-if="searchState.running" class="sv-running" data-search="running">正在搜索…</p>

      <div v-if="searchState.error" class="sv-error" data-search="error">
        <p class="sv-error-msg">{{ searchState.error.message }}</p>
        <p class="sv-sub">类别：{{ searchState.error.kind }}<span v-if="searchState.error.status"> · HTTP {{ searchState.error.status }}</span> —— {{ errorHint }}</p>
      </div>

      <template v-if="!searchState.running && !searchState.error && searchState.query">
        <div class="sv-meta" data-search="meta">
          <span v-if="searchState.fromCache" class="tag cache" data-search="from-cache">
            来自缓存 · {{ new Date(searchState.cachedAt).toLocaleString() }}
          </span>
          <span v-else-if="!searchState.results.length && !searchState.abstract" class="tag" data-search="empty">
            没有找到结果
          </span>
          <span v-else class="tag">共 {{ searchState.results.length }} 条 · {{ searchState.elapsedMs }} ms</span>
        </div>

        <section v-if="searchState.abstract" class="sv-abstract" data-search="abstract">
          <h3>摘要</h3>
          <p>{{ searchState.abstract }}</p>
        </section>

        <ol v-if="searchState.results.length" class="sv-list" data-search="results" data-tour="search_panel.results">
          <li v-for="(r, i) in searchState.results" :key="i" class="sv-item" :data-search="'r' + i">
            <div class="sv-r-head">
              <a class="sv-title" :href="r.url" :title="'用系统浏览器打开：' + r.url"
                 @click.prevent="open(r.url)">{{ r.title }}</a>
              <span class="sv-src">{{ r.source }}</span>
            </div>
            <p v-if="r.snippet" class="sv-snippet">{{ r.snippet }}</p>
            <p class="sv-url">{{ r.url }}</p>
            <div class="sv-actions">
              <button class="sv-act" @click="open(r.url)">打开</button>
              <button class="sv-act" @click="copy(r.url)">复制链接</button>
              <button v-if="extractExpr(r.title + ' ' + r.snippet)" class="sv-act"
                      :data-search="'calc-' + i"
                      :title="'把这个表达式送去计算页（由引擎计算）：' + extractExpr(r.title + ' ' + r.snippet)"
                      @click="sendToCalc(extractExpr(r.title + ' ' + r.snippet))">算这个</button>
            </div>
          </li>
        </ol>
      </template>

      <p v-if="copied" class="sv-copied" data-search="copied">已复制：{{ copied }}</p>
    </template>
  </div>
</template>

<style scoped>
.sv { padding: 14px 18px 28px; max-width: 920px; }
.sv-head h2 { margin: 0 0 4px; font-size: 17px; }
.sv-note { margin: 0 0 12px; font-size: 12px; color: var(--muted); }
.sv-sub { font-size: 12px; color: var(--muted); line-height: 1.7; margin: 4px 0 0; }
.sv-blocked { border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
.sv-blocked p { margin: 0 0 6px; font-size: 13px; }

.sv-bar { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; }
.sv-input {
  flex: 1; min-width: 0; font: inherit; font-size: 13px;
  padding: 7px 10px; border: 1px solid var(--border); border-radius: 8px;
  background: var(--surface); color: var(--text);
}
.sv-select {
  font: inherit; font-size: 12.5px; padding: 7px 8px; max-width: 240px;
  border: 1px solid var(--border); border-radius: 8px; background: var(--surface); color: var(--text);
}
.sv-warn { font-size: 12px; color: var(--warn, #c77); margin: 0 0 8px; }
.sv-running { font-size: 12.5px; color: var(--muted); }

.sv-error { border: 1px solid var(--danger, #d05a5a); border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; }
.sv-error-msg { margin: 0; font-size: 13px; color: var(--danger, #d05a5a); }

.sv-meta { margin: 6px 0 10px; }
.tag { font-size: 11.5px; color: var(--muted); border: 1px solid var(--border); border-radius: 999px; padding: 2px 8px; }
.tag.cache { color: var(--accent, #5a82f0); border-color: var(--accent, #5a82f0); }

.sv-abstract { border-left: 2px solid var(--border); padding-left: 10px; margin-bottom: 14px; }
.sv-abstract h3 { margin: 0 0 4px; font-size: 12.5px; color: var(--muted); font-weight: 600; }
.sv-abstract p { margin: 0; font-size: 13.5px; line-height: 1.75; }

.sv-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 14px; }
.sv-item { border-bottom: 1px solid var(--border); padding-bottom: 12px; }
.sv-item:last-child { border-bottom: none; }
.sv-r-head { display: flex; align-items: baseline; gap: 8px; }
.sv-title { font-size: 14px; color: var(--accent, #5a82f0); cursor: pointer; text-decoration: none; }
.sv-title:hover { text-decoration: underline; }
.sv-src { font-size: 11px; color: var(--muted); }
.sv-snippet { margin: 4px 0; font-size: 12.5px; line-height: 1.7; color: var(--text); }
.sv-url { margin: 0 0 6px; font-size: 11px; color: var(--muted); word-break: break-all; }
.sv-actions { display: flex; gap: 8px; }
.sv-act {
  background: none; border: 1px solid var(--border); color: var(--muted);
  border-radius: 6px; padding: 2px 9px; font-size: 11.5px; cursor: pointer;
}
.sv-act:hover { color: var(--text); border-color: var(--accent, #5a82f0); }
.sv-copied { font-size: 11.5px; color: var(--accent, #5a82f0); }
</style>
