/**
 * workspace/store.js — 工作区（各页面可编辑状态的唯一存放处）
 *
 * 「工作区」= 你正在算/正在画/正在写的东西：计算页的计算块、绘图页的表达式与视图范围、
 * 控制台里的代码。v1 有"保存工作区 / 加载工作区"（文件菜单），且有个真实的坑：
 * 它写在**安装目录**里、只存 3 个字段、恢复失败还谎报成功。
 *
 * 这一版的三条原则：
 *   ① 每个页面只负责声明自己的载荷形状（`{kind:"calc", blocks:[…]}`），
 *      store 不解释内容 —— 加新页面不用改这里；
 *   ② 「最近工作区」落 `%LOCALAPPDATA%\MFMath\settings\workspace.json`（走宿主原子写），
 *      「另存为文件」走宿主的文件对话框（页面不能读写任意路径）；
 *   ③ 载入失败**必须说出来**（版本不认、JSON 坏、字段缺），不静默当成空工作区。
 */
import { computed, ref } from "vue";
import { storeRead, storeWrite } from "../settings/bridge.js";
import { saveTextFile, openTextFile } from "../bridge.js";

/** 当前工作区格式版本。加载时只接受 <= 本版本的文件，将来好写迁移。 */
export const VERSION = 1;
const NAME = "workspace";
const FILE_FILTER = "MF 工作区 (*.mfws.json)|*.mfws.json|JSON 文件 (*.json)|*.json|所有文件 (*.*)|*.*";

/** route.path → 该页面的载荷 */
export const pages = ref({});
export const lastSavedAt = ref(0);
export const lastSavedRoute = ref("");
export const lastSavedPath = ref("");     // 上次"另存为"的文件路径（仅展示用）
/** 相对上次保存/载入是否有改动 */
export const dirty = ref(false);

const errorText = ref("");

export function setPage(route, payload) {
  if (!route) return;
  pages.value = { ...pages.value, [route]: payload };
  dirty.value = true;
}

export function getPage(route) {
  return (route && pages.value[route]) || null;
}

export function clearAll() {
  pages.value = {};
  dirty.value = true;
}

/** 当前内存里的工作区（存盘/另存为都用它） */
export function snapshot(route = "") {
  return { version: VERSION, savedAt: Date.now(), route, pages: pages.value };
}

/**
 * 校验并载入一份工作区。
 * @returns {{ok:true, route:string, pages:number} | {ok:false, error:string}}
 */
export function applySnapshot(obj) {
  if (!obj || typeof obj !== "object") return { ok: false, error: "不是合法的 JSON 对象" };
  const v = Number(obj.version || 0);
  if (!v) return { ok: false, error: "缺少 version 字段（不是本应用的工作区文件？）" };
  if (v > VERSION) return { ok: false, error: `工作区版本 ${v} 比当前程序（${VERSION}）新，请先更新应用` };
  if (!obj.pages || typeof obj.pages !== "object" || Array.isArray(obj.pages)) {
    return { ok: false, error: "缺少 pages 字段" };
  }
  const next = {};
  for (const [route, payload] of Object.entries(obj.pages)) {
    if (!route.startsWith("/") || !payload || typeof payload !== "object") continue;
    next[route] = payload;
  }
  const n = Object.keys(next).length;
  if (!n) return { ok: false, error: "工作区里没有任何页面内容" };
  pages.value = next;
  lastSavedAt.value = Number(obj.savedAt) || Date.now();
  lastSavedRoute.value = String(obj.route || "");
  dirty.value = false;
  errorText.value = "";
  return { ok: true, route: lastSavedRoute.value, pages: n };
}

/** 汇总（设置面板与测试用） */
export function summary() {
  const list = Object.entries(pages.value);
  let blocks = 0;
  let curves = 0;
  for (const [, p] of list) {
    if (Array.isArray(p?.blocks)) blocks += p.blocks.length;
    if (Array.isArray(p?.expressions)) curves += p.expressions.length;
  }
  return {
    pages: list.length,
    routes: list.map(([r]) => r),
    blocks,
    curves,
    savedAt: lastSavedAt.value,
    savedRoute: lastSavedRoute.value,
    savedPath: lastSavedPath.value,
    dirty: dirty.value,
  };
}

export function workspaceError() {
  return errorText.value;
}

// ── 应用数据（最近工作区） ────────────────────────────────────────────────

export function saveToApp(route = "") {
  const r = storeWrite(NAME, snapshot(route));
  if (r && r.ok === false) {
    errorText.value = r.error || "写入失败";
    return { ok: false, error: errorText.value };
  }
  lastSavedAt.value = Date.now();
  lastSavedRoute.value = route;
  dirty.value = false;
  errorText.value = "";
  return { ok: true };
}

export function loadFromApp() {
  const r = storeRead(NAME);
  if (r && r.ok === false) {
    const msg = r.corrupt ? `工作区文件已损坏（保留原文件）：${r.error}` : (r.error || "读取失败");
    errorText.value = msg;
    return { ok: false, error: msg };
  }
  if (!r?.exists || !r.json) return { ok: false, error: "还没有保存过工作区" };
  let obj = null;
  try { obj = JSON.parse(r.json); } catch (e) {
    errorText.value = `工作区内容无法解析：${e?.message || e}`;
    return { ok: false, error: errorText.value };
  }
  const res = applySnapshot(obj);
  if (!res.ok) errorText.value = res.error;
  return res;
}

export function hasAppWorkspace() {
  const r = storeRead(NAME);
  return !!(r?.ok && r.exists && r.json);
}

// ── 文件（另存为 / 从文件打开） ──────────────────────────────────────────

export function saveToFile(route = "", path = "") {
  const content = JSON.stringify(snapshot(route), null, 2);
  const r = saveTextFile({
    title: "另存工作区",
    defaultName: "workspace.mfws.json",
    filter: FILE_FILTER,
    content,
    // path 非空 = 跳过对话框（自动化/命令行场景，见 WindowBridge.SaveTextFile 的说明）
    path,
  });
  if (!r || r.ok !== true) {
    const msg = r?.canceled ? "" : (r?.error || "宿主不支持文件对话框");
    if (msg) errorText.value = msg;
    return { ok: false, error: msg, canceled: !!r?.canceled };
  }
  lastSavedAt.value = Date.now();
  lastSavedRoute.value = route;
  lastSavedPath.value = r.path || "";
  dirty.value = false;
  return { ok: true, path: r.path, bytes: r.bytes };
}

export function loadFromFile(path = "") {
  const r = openTextFile({ title: "打开工作区", filter: FILE_FILTER, path });
  if (!r || r.ok !== true) {
    const msg = r?.canceled ? "" : (r?.error || "宿主不支持文件对话框");
    if (msg) errorText.value = msg;
    return { ok: false, error: msg, canceled: !!r?.canceled };
  }
  let obj = null;
  try { obj = JSON.parse(r.content || ""); } catch (e) {
    errorText.value = `${r.path || "文件"} 不是合法 JSON：${e?.message || e}`;
    return { ok: false, error: errorText.value };
  }
  const res = applySnapshot(obj);
  if (res.ok) lastSavedPath.value = r.path || "";
  else errorText.value = res.error;
  return res;
}

/** 组合式入口 */
export function useWorkspace() {
  return {
    pages,
    dirty: computed(() => dirty.value),
    error: computed(() => errorText.value),
    summary,
    setPage,
    getPage,
    clearAll,
    saveToApp,
    loadFromApp,
    saveToFile,
    loadFromFile,
    hasAppWorkspace,
    VERSION,
  };
}

/**
 * 挂上测试/排障钩子 `window.__mfWorkspace`。
 *
 * 与推送通道同一做法：CDP 里够不着模块作用域，而"工作区到底存了什么、载入失败为什么失败"
 * 恰恰是最需要能一眼看到的东西。App 启动时调一次即可。
 */
export function initWorkspace() {
  try {
    window.__mfWorkspace = {
      summary,
      pages: () => JSON.parse(JSON.stringify(pages.value)),
      saveToApp,
      loadFromApp,
      saveToFile,
      loadFromFile,
      clearAll,
      setPage,
      applySnapshot,
      VERSION,
    };
  } catch { /* 忽略 */ }
}
