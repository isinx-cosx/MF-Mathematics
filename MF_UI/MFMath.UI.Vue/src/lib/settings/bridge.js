/**
 * settings/bridge.js — 设置面板与宿主 `sys` 桥的封装（含无宿主降级）
 *
 * 宿主侧是 MFMath.Host/SettingsBridge.cs（hostObjects.sync.sys）。
 * 浏览器里 `npm run dev` 预览时没有宿主，此时：
 *   · 只读信息（路径、依赖清单）返回空值并标记 browser:true，界面显示"浏览器预览：无宿主"；
 *   · 设置读写**降级到 localStorage**，功能仍可点通，只是不落文件。
 * 与 console/bridge.js 的 `if (!c) return null` 风格保持一致：**不抛错、明确说明**。
 */
const LS_PREFIX = "mf_set_";

function sysObj() {
  try {
    return window.chrome?.webview?.hostObjects?.sync?.sys ?? null;
  } catch {
    return null;
  }
}

export function isSettingsHosted() {
  return sysObj() !== null;
}

function parse(text) {
  if (text == null) return null;
  if (typeof text === "object") return text;
  try {
    return JSON.parse(String(text));
  } catch {
    return null;
  }
}

function call(fn, args, fallback) {
  const c = sysObj();
  if (!c) return fallback;
  try {
    const r = c[fn](...args);
    return parse(r) ?? fallback;
  } catch (e) {
    return { ok: false, error: String(e?.message || e) };
  }
}

/** 宿主与运行环境信息；无宿主时返回 { browser:true } 形态的最小对象 */
export function info() {
  const r = call("Info", [], null);
  if (r) return r;
  return {
    browser: true,
    dataDir: "（浏览器预览：无宿主）",
    settingsDir: "（浏览器预览：无宿主）",
    appDir: "",
    hostVersion: "无宿主",
    runtime: "-",
    os: typeof navigator !== "undefined" ? navigator.userAgent : "-",
    arch: "-",
    is64: true,
    componentBase: "",
  };
}

/** 引擎产物清单：主 DLL 与运行时依赖在不在、多大 */
export function engineReport() {
  const r = call("EngineReport", [], null);
  if (r) return r;
  return { browser: true, dir: "（浏览器预览：无宿主）", files: [] };
}

export function storeList() {
  const r = call("StoreList", [], null);
  if (Array.isArray(r)) return r;
  // 无宿主：列出降级存储里有什么
  const out = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith(LS_PREFIX)) {
        out.push({ name: k.slice(LS_PREFIX.length), bytes: (localStorage.getItem(k) || "").length, mtime: "(localStorage)" });
      }
    }
  } catch { /* 忽略 */ }
  return out;
}

/** @returns {{ok:boolean, json?:string, exists?:boolean, error?:string, corrupt?:boolean}} */
export function storeRead(name) {
  const c = sysObj();
  if (c) return call("StoreRead", [name], { ok: false, error: "桥调用失败" });
  try {
    const raw = localStorage.getItem(LS_PREFIX + name);
    return raw ? { ok: true, exists: true, json: raw } : { ok: true, exists: false, json: "" };
  } catch (e) {
    return { ok: false, error: String(e?.message || e) };
  }
}

/** 写设置。obj 可以是对象（会被 JSON.stringify）或字符串 */
export function storeWrite(name, obj) {
  const json = typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
  const c = sysObj();
  if (c) return call("StoreWrite", [name, json], { ok: false, error: "桥调用失败" });
  try {
    JSON.parse(json); // 与宿主同样的校验：坏 JSON 不落盘
    localStorage.setItem(LS_PREFIX + name, json);
    return { ok: true, fallback: true };
  } catch (e) {
    return { ok: false, error: String(e?.message || e) };
  }
}

export function storeDelete(name) {
  const c = sysObj();
  if (c) return call("StoreDelete", [name], { ok: false, error: "桥调用失败" });
  try {
    localStorage.removeItem(LS_PREFIX + name);
    return { ok: true, fallback: true };
  } catch (e) {
    return { ok: false, error: String(e?.message || e) };
  }
}

export function openPath(path) {
  return call("OpenPath", [path], { ok: false, error: "浏览器预览：无法打开目录" });
}

export function exportDiagnostics() {
  return call("ExportDiagnostics", [], { ok: false, error: "浏览器预览：无法导出诊断包" });
}

/** 读一个设置文件并合并默认值；损坏时返回 defaults 并把错误带出来（不覆盖原文件） */
export function loadSettings(name, defaults) {
  const r = storeRead(name);
  if (!r?.ok) {
    return { value: { ...defaults }, error: r?.corrupt ? `配置文件已损坏，已用默认值：${r.error}` : (r?.error || "读取失败"), exists: false };
  }
  if (!r.exists || !r.json) return { value: { ...defaults }, error: "", exists: false };
  try {
    const parsed = JSON.parse(r.json);
    return { value: { ...defaults, ...parsed }, error: "", exists: true };
  } catch (e) {
    return { value: { ...defaults }, error: `配置内容无法解析，已用默认值：${e?.message || e}`, exists: true };
  }
}

/** 写设置；自动补 version 字段（方案要求所有设置文件都带版本） */
export function saveSettings(name, value, version = 1) {
  return storeWrite(name, { version, ...value });
}
