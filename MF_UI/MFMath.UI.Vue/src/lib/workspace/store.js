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
import { saveDocFile, openDocFile } from "../bridge.js";

/**
 * 文档格式版本。加载时只接受 <= 本版本的文件。
 *
 * 版本分两层：`version` 管容器与信封，各页载荷自带 `v`（如控制台 `v: 2`）。
 * 这样以后加功能只涨对应载荷的 `v`，不逼着整体版本涨。
 */
export const VERSION = 2;
/** 文档魔数。认错文件时能说人话，判断只信内容不信扩展名。 */
export const FORMAT = "mfmath.document";
const NAME = "workspace";
const FILE_FILTER =
  "MF 工作区 (*.mfws)|*.mfws|旧版工作区 (*.mfws.json)|*.mfws.json|所有文件 (*.*)|*.*";

/* ── 上限。数字与宿主 docfile.rs 保持一致，两边都要拦 ─────────────── */
/** 一个工作区最多几段控制台代码 */
export const MAX_SNIPPETS = 20;
/** 单段控制台代码的字数上限（按 UTF-8 字节算） */
export const MAX_SNIPPET_BYTES = 64 * 1024;
/** 正文（document.json）上限 */
export const MAX_DOC_BYTES = 4 * 1024 * 1024;

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

/** 本版本认识的顶层键。不在这张表里的键一律进 `preserved`，保存时原样写回。 */
const KNOWN_TOP = [
  "format", "version", "kind", "savedAt", "route", "pages",
  "steps", "assets", "meta", "createdAt", "updatedAt", "app",
];

/** 不认识的顶层键（旧版打开新文件时不能丢）。 */
let preserved = {};

/** 当前内存里的工作区（存盘/另存为都用它）。 */
export function snapshot(route = "") {
  return {
    format: FORMAT,
    version: VERSION,
    kind: "workspace",
    savedAt: Date.now(),
    route,
    pages: pages.value,
    // 原样带回本版本不认识的键，避免"旧版打开新文档、存一下把内容抹了"
    ...preserved,
  };
}

/** UTF-8 字节数（上限按字节算，不按 JS 的字符数）。 */
export function utf8Bytes(s) {
  try {
    return new TextEncoder().encode(s).length;
  } catch {
    return String(s).length * 3;
  }
}

/** 把 v1 的单段控制台载荷升级成 v2 的多段结构；其它载荷原样返回。 */
function migratePayload(route, payload, fromVersion, onMigrate) {
  const p = { ...payload };
  if (route === "/tools/console" && Array.isArray(p.snippets) === false) {
    const code = typeof p.code === "string" ? p.code : "";
    p.kind = p.kind || "console";
    p.v = 2;
    p.snippets = code
      ? [{ id: "c1", name: "控制台", lang: p.lang || "python", code, stdin: p.stdin || "" }]
      : [];
    p.activeId = p.snippets[0]?.id || "";
    delete p.code;
    delete p.stdin;
    delete p.lang;
    if (fromVersion < 2) onMigrate();
  }
  return p;
}

/** 上限校验。超了返回 `{ok:false,error}`，由调用方整份拒绝（不静默截断）。 */
export function checkLimits(map) {
  const con = map["/tools/console"];
  if (con && Array.isArray(con.snippets)) {
    if (con.snippets.length > MAX_SNIPPETS) {
      return {
        ok: false,
        error: `这个工作区含 ${con.snippets.length} 段控制台代码，超过上限 ${MAX_SNIPPETS} 段，本版本打不开`,
      };
    }
    for (const s of con.snippets) {
      const n = utf8Bytes(s?.code || "");
      if (n > MAX_SNIPPET_BYTES) {
        return {
          ok: false,
          error: `控制台代码「${s?.name || s?.id || "?"}」${Math.round(n / 1024)} KiB，超过单段上限 ${MAX_SNIPPET_BYTES / 1024} KiB`,
        };
      }
    }
    const ids = new Set();
    for (const s of con.snippets) {
      const id = String(s?.id || "");
      if (!/^[A-Za-z0-9_-]{1,32}$/.test(id)) {
        return { ok: false, error: `控制台代码段的 id 不合法：${id || "(空)"}` };
      }
      if (ids.has(id)) return { ok: false, error: `控制台代码段的 id 重复：${id}` };
      ids.add(id);
    }
  }
  return { ok: true };
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
  if (obj.kind && obj.kind !== "workspace") {
    const label = obj.kind === "courseware" ? "课件" : obj.kind;
    return { ok: false, error: `这是「${label}」文档，请从对应入口打开（不是工作区）` };
  }
  if (obj.format && obj.format !== FORMAT) {
    return { ok: false, error: `不认识的文档格式：${obj.format}` };
  }
  if (!obj.pages || typeof obj.pages !== "object" || Array.isArray(obj.pages)) {
    return { ok: false, error: "缺少 pages 字段" };
  }

  // 逐页迁移（v1 的控制台是单段 code，v2 是 snippets 数组）
  const next = {};
  let migrated = 0;
  for (const [route, payload] of Object.entries(obj.pages)) {
    if (!route.startsWith("/") || !payload || typeof payload !== "object") continue;
    next[route] = migratePayload(route, payload, v, () => { migrated += 1; });
  }
  const n = Object.keys(next).length;
  if (!n) return { ok: false, error: "工作区里没有任何页面内容" };

  // 上限：超了整份拒绝，别让用户以为代码被"吞"了一部分
  const lim = checkLimits(next);
  if (!lim.ok) return lim;

  // 记住本版本不认识的顶层键，保存时原样写回
  preserved = {};
  for (const [k, val] of Object.entries(obj)) {
    if (!KNOWN_TOP.includes(k)) preserved[k] = val;
  }

  pages.value = next;
  lastSavedAt.value = Number(obj.savedAt) || Date.now();
  lastSavedRoute.value = String(obj.route || "");
  dirty.value = false;
  errorText.value = "";
  return { ok: true, route: lastSavedRoute.value, pages: n, migrated };
}

/** 汇总（设置面板与测试用） */
export function summary() {
  const list = Object.entries(pages.value);
  let blocks = 0;
  let curves = 0;
  let snippets = 0;
  for (const [, p] of list) {
    if (Array.isArray(p?.blocks)) blocks += p.blocks.length;
    if (Array.isArray(p?.expressions)) curves += p.expressions.length;
    if (Array.isArray(p?.snippets)) snippets += p.snippets.length;
  }
  return {
    pages: list.length,
    routes: list.map(([r]) => r),
    blocks,
    curves,
    snippets,
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
  const obj = snapshot(route);
  const lim = checkLimits(obj.pages || {});
  if (!lim.ok) {
    errorText.value = lim.error;
    return { ok: false, error: lim.error };
  }
  const content = JSON.stringify(obj, null, 2);
  if (utf8Bytes(content) > MAX_DOC_BYTES) {
    const msg = `工作区太大（${Math.round(utf8Bytes(content) / 1024)} KiB），超过上限 ${MAX_DOC_BYTES / 1024} KiB`;
    errorText.value = msg;
    return { ok: false, error: msg };
  }
  // 写进 zip 容器（宿主负责压包），工作区没有二进制资产
  const r = saveDocFile({
    title: "另存工作区",
    defaultName: "未命名.mfws",
    filter: FILE_FILTER,
    document: content,
    assets: "[]",
    // path 非空 = 跳过对话框（自动化/命令行场景）
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
  // 宿主返回的 document 可能是 zip 容器里的正文，也可能是旧版纯 JSON —— 形状一致
  const r = openDocFile({ title: "打开工作区", filter: FILE_FILTER, path });
  if (!r || r.ok !== true) {
    const msg = r?.canceled ? "" : (r?.error || "宿主不支持文件对话框");
    if (msg) errorText.value = msg;
    return { ok: false, error: msg, canceled: !!r?.canceled };
  }
  let obj = null;
  try { obj = JSON.parse(r.document || ""); } catch (e) {
    errorText.value = `${r.path || "文件"} 不是合法的文档：${e?.message || e}`;
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
