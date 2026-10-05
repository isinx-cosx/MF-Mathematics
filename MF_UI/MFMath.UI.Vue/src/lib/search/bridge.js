/**
 * search/bridge.js — 联网搜索（宿主桥 + 推送订阅 + 状态）
 *
 * 分工与 AI 那条同源：
 *   · **宿主** 负责凭据（Wolfram App ID，DPAPI 密文，页面拿不到）、网络（页面在虚拟主机下
 *     直连外部站点会撞 CORS，DDG 的 HTML 页也不允许跨源读）、缓存与超时分类；
 *   · **页面** 负责发起查询、渲染结果、把结果里的表达式送去计算页。
 *
 * 事件话题（都带 requestId）：
 *   search.done  → {engine, results[], abstract, fromCache, cachedAt, elapsedMs}
 *   search.error → {kind, status, message}   kind: config|network|http|parse|timeout|aborted
 *
 * 无宿主（浏览器预览）时降级：页面照旧能开，但会明说"只在 MFMath.exe 里可用"，
 * 并且**不**提供假搜索框 —— 沿用之前占位面板那条判断（装一个搜不出东西的输入框更糟）。
 */
import { ref } from "vue";
import { onPush } from "../push.js";

function hostObj() {
  try {
    return window.chrome?.webview?.hostObjects?.sync?.search ?? null;
  } catch {
    return null;
  }
}

export function isSearchHosted() {
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
  try { return parse(c[method](...args)); } catch (e) { return { ok: false, error: String(e?.message || e) }; }
}

const DEFAULT_INFO = {
  engine: "duckduckgo",
  customUrl: "",
  timeoutSec: 15,
  resultCount: 8,
  cacheEnabled: true,
  cacheTtlHours: 24,
  hasWolframKey: false,
  wolframKeySource: "none",
  dpapiAvailable: false,
  configPath: "",
  endpoint: "",
  cache: { entries: 0, bytes: 0 },
  running: 0,
  lastError: "",
};

/** 脱敏状态（永远不含 App ID） */
export const searchInfo = ref({ ...DEFAULT_INFO });
export const searchHosted = ref(false);

export function refreshSearchInfo() {
  searchHosted.value = isSearchHosted();
  const info = call("Info");
  if (info && typeof info === "object" && "engine" in info) {
    searchInfo.value = { ...DEFAULT_INFO, ...info };
  }
  return searchInfo.value;
}

export function searchConfigure(patch) {
  if (!Object.keys(patch || {}).length) return { ok: true, changed: 0 };
  const r = call("Configure", JSON.stringify(patch));
  refreshSearchInfo();
  return r || { ok: false, error: "无宿主：搜索配置只在 MFMath.exe 里可改" };
}

export function setWolframKey(key) {
  const r = call("SetWolframKey", String(key || ""));
  refreshSearchInfo();
  return r || { ok: false, error: "无宿主" };
}

export function clearWolframKey() {
  const r = call("ClearWolframKey");
  refreshSearchInfo();
  return r || { ok: false, error: "无宿主" };
}

export function searchSelfCheck() {
  return call("SelfCheck") || { ok: false, error: "无宿主" };
}

export function cacheStats() {
  return call("CacheStats") || { entries: 0, bytes: 0 };
}

export function clearCache() {
  const r = call("ClearCache") || { ok: false, error: "无宿主" };
  refreshSearchInfo();
  return r;
}

/** 用系统默认浏览器打开结果链接（宿主侧只放行 http/https） */
export function openUrl(url) {
  return call("OpenUrl", String(url || "")) || { ok: false, error: "无宿主" };
}

/* ── 查询状态 ────────────────────────────────────────────────────────── */

export const searchState = ref({
  running: false,
  requestId: "",
  query: "",
  engine: "",
  results: [],
  abstract: "",
  fromCache: false,
  cachedAt: 0,
  elapsedMs: 0,
  error: null,
});

export const SEARCH_ENGINES = [
  { value: "duckduckgo", label: "DuckDuckGo（免密钥）" },
  { value: "wolfram", label: "Wolfram Alpha（需 App ID）" },
  { value: "custom", label: "自定义端点（SearXNG）" },
];

/**
 * 早退也要把原因写进 `searchState.error`。
 *
 * 调用方（SearchView.doSearch）是按"失败原因已经进 searchState.error"来写的：
 *   `const r = runSearch(...); if (!r.ok) return;`
 * 而这些前置校验原先只 return 一个被丢弃的对象 —— 于是"选了 Wolfram 但没填 App ID"
 * 时，点搜索 / 按回车 / 深链 `?q=…` 全都毫无反应，界面零变化零报错。
 */
function failSearch(message, kind = "config") {
  searchState.value = {
    ...searchState.value, running: false,
    error: { kind, status: 0, message },
  };
  return { ok: false, error: message };
}

/** @returns {{ok:boolean, error?:string, engine?:string}} */
export function runSearch(query, { engine = "", noCache = false } = {}) {
  const q = String(query || "").trim();
  // 空输入不算错误：用户只是按了回车，弹一块红色错误反而更吵
  if (!q) return { ok: false, error: "先输入要搜的内容" };
  if (!isSearchHosted()) {
    return failSearch("无宿主：联网搜索只在 MFMath.exe 里可用", "config");
  }

  const wantEngine = engine || searchInfo.value.engine || "duckduckgo";
  if (wantEngine === "wolfram" && !searchInfo.value.hasWolframKey) {
    return failSearch("Wolfram 需要 App ID：去「设置 → 搜索」填一个，或改用其他引擎");
  }
  if (wantEngine === "custom" && !searchInfo.value.customUrl) {
    return failSearch("自定义端点还没填：去「设置 → 搜索」写上 SearXNG 的地址");
  }

  searchState.value = {
    running: true, requestId: "", query: q, engine: wantEngine,
    results: [], abstract: "", fromCache: false, cachedAt: 0, elapsedMs: 0, error: null,
  };

  const r = call("Start", JSON.stringify({ query: q, engine: wantEngine, noCache: !!noCache }));
  if (!r || r.ok === false) {
    const err = r?.error || "搜索启动失败";
    searchState.value = { ...searchState.value, running: false, error: { kind: "config", status: 0, message: err } };
    return { ok: false, error: err };
  }
  searchState.value = { ...searchState.value, requestId: String(r.requestId || "") };
  return { ok: true, engine: wantEngine };
}

export function cancelSearch() {
  const id = searchState.value.requestId;
  if (!id) return { ok: false, error: "当前没有在跑的搜索" };
  const r = call("Cancel", id) || { ok: false, error: "无宿主" };
  return r;
}

export function clearSearchState() {
  searchState.value = {
    running: false, requestId: "", query: "", engine: "",
    results: [], abstract: "", fromCache: false, cachedAt: 0, elapsedMs: 0, error: null,
  };
}

/* ── 推送订阅 ────────────────────────────────────────────────────────── */

let inited = false;

export function initSearch() {
  if (inited) return;
  inited = true;
  // 启动就把配置读回来：页面顶部的"查询会发往哪里"与设置组都依赖它，
  // 各视图再自己去 refresh 的话，第一屏就会先显示一份默认值（实测踩过）。
  refreshSearchInfo();
  onPush((env) => {
    const topic = String(env?.topic || "");
    if (!topic.startsWith("search.")) return;
    const p = env.payload || {};
    // 只认当前这一轮：上一轮的迟到消息不能覆盖新结果
    if (p.requestId && searchState.value.requestId && p.requestId !== searchState.value.requestId) return;

    if (topic === "search.done") {
      searchState.value = {
        ...searchState.value,
        running: false,
        results: Array.isArray(p.results) ? p.results : [],
        abstract: String(p.abstract || ""),
        fromCache: p.fromCache === true,
        cachedAt: Number(p.cachedAt || 0),
        elapsedMs: Number(p.elapsedMs || 0),
        error: null,
      };
    } else if (topic === "search.error") {
      searchState.value = {
        ...searchState.value,
        running: false,
        error: { kind: String(p.kind || ""), status: Number(p.status || 0), message: String(p.message || "") },
      };
    }
  });
}

/* ── 结果里的表达式：送去计算页（走 pendingInput 的既有通路）───────────── */

/**
 * 从一段文本里挑一个"看起来像数学表达式"的片段。
 *
 * 这是**启发式**，所以有两个纪律：
 *   ① 只是**建议**——界面上由用户点"算这个"才送走，不自动算；
 *   ② 送进计算页后由**引擎**计算（AI/搜索都不当计算源），送的是原文而不是"我化简过的东西"。
 */
export function extractExpr(text) {
  const s = String(text || "");
  const candidates = s.match(/[0-9A-Za-zπθ∞√^_+\-*/×÷().,']{3,80}/g) || [];
  const scored = candidates
    .map((c) => c.trim())
    .filter((c) => /[0-9]/.test(c) && /[+\-*/^=]|sqrt|sin|cos|tan|log|ln|exp|int|sum|lim/.test(c))
    .filter((c) => !/^[\d.]+$/.test(c));          // 纯数字不算"表达式"
  return scored.length ? scored.sort((a, b) => b.length - a.length)[0] : "";
}

/** 测试/排障钩子 */
export function initSearchHook() {
  try {
    window.__mfSearch = {
      info: () => searchInfo.value,
      state: () => searchState.value,
      refresh: refreshSearchInfo,
      configure: searchConfigure,
      setKey: setWolframKey,
      clearKey: clearWolframKey,
      selfCheck: searchSelfCheck,
      cacheStats,
      clearCache,
      openUrl,
      run: (q, opts) => runSearch(q, opts || {}),
      cancel: cancelSearch,
      clear: clearSearchState,
      extractExpr,
      hosted: isSearchHosted,
      engines: () => SEARCH_ENGINES,
    };
  } catch { /* 忽略 */ }
}
