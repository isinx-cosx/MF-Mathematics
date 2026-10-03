/**
 * update/bridge.js — 更新链（页面侧）
 *
 * 本项目的既定取舍：**只提示 + 显示校验值 + 把下载交给浏览器**。
 * 软件不自动下载、更不执行安装包 —— 那等于给自己装一条"下载并运行可执行文件"的通路。
 *
 * 三条与"诚实"有关的规矩：
 *   ① 站点给不出 sha256 时**如实显示原因**（`sha256Reason`），不显示成"已校验"、也不留空白；
 *   ② 站点版本比本机**旧**时不叫"有更新"，而是说明"站点上的是 X（比本机旧）"——
 *      否则 v2 用户会被引去下载 v1 安装包；
 *   ③ 自动检查默认**关**：启动就联网属于替用户做决定（何况这一条会暴露 IP 与使用时间）。
 */
import { ref } from "vue";

function hostObj() {
  try { return window.chrome?.webview?.hostObjects?.sync?.update ?? null; } catch { return null; }
}
function sysObj() {
  try { return window.chrome?.webview?.hostObjects?.sync?.sys ?? null; } catch { return null; }
}

export function isUpdateHosted() { return hostObj() !== null; }

function parse(text, fallback = null) {
  if (text == null) return fallback;
  if (typeof text === "object") return text;
  try {
    return JSON.parse(String(text));
  } catch (e) {
    // 宿主返回了不合法 JSON 时**别静默吞掉**：本轮就因此把一个"少了个 }"的拼写错误
    // 表现成了"宿主没有响应"，查了半天。把片段打到控制台（诊断包会带走 console 输出）。
    try {
      console.warn("[update] 宿主返回的不是合法 JSON：", String(e?.message || e), String(text).slice(0, 200));
    } catch { /* 忽略 */ }
    return fallback;
  }
}
function call(method, ...args) {
  const c = hostObj();
  if (!c || typeof c[method] !== "function") return null;
  try { return parse(c[method](...args)); } catch (e) { return { ok: false, error: String(e?.message || e) }; }
}

const STORE = "update";
const DEFAULT_PREFS = { autoCheck: false, intervalDays: 7, lastCheckAt: 0 };

export const updateInfo = ref({ appVersion: "", baseUrl: "", lastCheckAt: 0, lastError: "" });
export const updateState = ref({
  checking: false,
  result: null,        // {ok, current, latest, relation, hasUpdate, sha256, size, sha256Reason, note}
  error: null,
  checkedAt: 0,
});
export const updatePrefs = ref({ ...DEFAULT_PREFS });
export const updateHosted = ref(false);

/* ── 偏好（非机密 → 走通用设置存储）──────────────────────────────────── */

export function loadUpdatePrefs() {
  const sys = sysObj();
  if (!sys) return updatePrefs.value;
  try {
    const r = parse(sys.StoreRead(STORE));
    if (r?.ok && r.json) updatePrefs.value = { ...DEFAULT_PREFS, ...parse(r.json, {}) };
  } catch { /* 读不到就用默认 */ }
  return updatePrefs.value;
}

export function saveUpdatePrefs(patch) {
  updatePrefs.value = { ...updatePrefs.value, ...patch };
  const sys = sysObj();
  if (!sys) return { ok: false, error: "无宿主" };
  try {
    return parse(sys.StoreWrite(STORE, JSON.stringify(updatePrefs.value))) || { ok: false };
  } catch (e) { return { ok: false, error: String(e?.message || e) }; }
}

/* ── 检查 ─────────────────────────────────────────────────────────────── */

export function refreshUpdateInfo() {
  updateHosted.value = isUpdateHosted();
  const info = call("Info");
  if (info && typeof info === "object" && "appVersion" in info) updateInfo.value = { ...updateInfo.value, ...info };
  return updateInfo.value;
}

/** 查一次站点版本。**同步**返回（宿主里是同步等待 + 超时），所以界面上要显示"检查中"。 */
export function checkUpdate() {
  if (!isUpdateHosted()) {
    updateState.value = { ...updateState.value, checking: false, error: { kind: "nohost", message: "无宿主：更新检查只在 MFMath.exe 里可用" } };
    return { ok: false, error: "无宿主" };
  }
  updateState.value = { ...updateState.value, checking: true, error: null };
  try {
    const r = call("Check");
    if (!r) {
      // 诊断信息写进消息：出现过"宿主没有响应"但查不出原因的情况，把桥的方法可见性带上
      const bridgeType = (() => { try { return typeof hostObj()?.Check; } catch { return "?"; } })();
      updateState.value = {
        ...updateState.value, checking: false,
        error: { kind: "unknown", message: `宿主没有响应（bridge.Check=${bridgeType}）` },
      };
      return { ok: false, error: `宿主没有响应（bridge.Check=${bridgeType}）` };
    }
    if (r.ok) {
      updateState.value = { checking: false, result: r, error: null, checkedAt: Date.now() };
      saveUpdatePrefs({ lastCheckAt: Date.now() });
      refreshUpdateInfo();
      return r;
    }
    updateState.value = { ...updateState.value, checking: false, error: { kind: r.kind || "unknown", message: r.error || "检查失败" } };
    refreshUpdateInfo();
    return r;
  } catch (e) {
    updateState.value = { ...updateState.value, checking: false, error: { kind: "unknown", message: String(e?.message || e) } };
    return { ok: false, error: String(e?.message || e) };
  }
}

/** 把下载页交给浏览器（相对地址由宿主拼到站点地址上） */
export function openDownloadPage(url) {
  const r = call("OpenDownloadPage", String(url || "")) || { ok: false, error: "无宿主" };
  return r;
}

/** 只算出"将会打开的地址"，不真的打开（界面显示"将打开：…"用） */
export function previewDownloadUrl(url) {
  return call("PreviewDownloadUrl", String(url || "")) || { ok: false, reason: "无宿主" };
}

export function updateSelfCheck() {
  return call("SelfCheck") || { ok: false, error: "无宿主" };
}

export function hintFor(kind) {
  switch (kind) {
    case "network": return "站点联系不上。本地功能全部照常可用，稍后再试即可。";
    case "timeout": return "站点响应太慢，稍后再试。";
    case "http": return "站点拒绝了这次请求（可能站点在维护）。";
    case "parse": return "站点返回的形状不认识（可能是版本差异）。";
    default: return "可以重试。";
  }
}

/* ── 启动 ─────────────────────────────────────────────────────────────── */

let inited = false;

export function initUpdate() {
  if (inited) return;
  inited = true;
  refreshUpdateInfo();
  loadUpdatePrefs();
  // 自动检查：默认关。开了的话只在**超过间隔**时查一次（不是每次启动都查）
  const p = updatePrefs.value;
  if (p.autoCheck) {
    const days = Number(p.intervalDays) || 7;
    const due = !p.lastCheckAt || Date.now() - p.lastCheckAt > days * 86400000;
    if (due) setTimeout(() => checkUpdate(), 1500);   // 让界面先画出来，别在启动路径上等网络
  }
}

export function initUpdateHook() {
  try {
    window.__mfUpdate = {
      info: () => updateInfo.value,
      state: () => updateState.value,
      prefs: () => updatePrefs.value,
      refresh: refreshUpdateInfo,
      loadPrefs: loadUpdatePrefs,
      savePrefs: saveUpdatePrefs,
      check: checkUpdate,
      openDownload: openDownloadPage,
      preview: previewDownloadUrl,
      selfCheck: updateSelfCheck,
      hintFor,
      hosted: isUpdateHosted,
    };
  } catch { /* 忽略 */ }
}
