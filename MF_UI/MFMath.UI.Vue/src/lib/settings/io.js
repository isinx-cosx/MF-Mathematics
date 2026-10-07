/**
 * settings/io.js — 设置备份：导出 / 导入（换机迁移）
 *
 * 一个**内容选择**上的决定，比实现更重要：**凭据不进备份**。
 *   · `ai.json`（API Key，**本轮起是明文** —— `apiKey` 字段）、`account.json`（登录 token 密文）、
 *     `search.json`（Wolfram App ID 密文）整份排除，并在包里写清 `excluded` ——
 *     换机迁移不该搬密钥（明文搬过去等于把钥匙抄了一份；旧的 DPAPI 密文换台机器也解不开，
 *     搬过去只是一串没用的字节，却让人误以为"密钥跟着走了"）；
 *   · 其余文件里再按字段名剥一遍（`*protected` / `password` / `secret` / `token` / `apikey`），
 *     并记录剥掉了哪些字段名 —— **双保险，且是可见的**。
 *     注意 `apiKey` 这条正则命中：`api[-_]?key` 在忽略大小写下匹配 `apiKey`。
 *
 * 导入同样**不写**上面那三类文件：所以导入一个旧备份**不会**把你现在的密钥清掉。
 * 这一点有断言守着（写错的话用户会静默失去密钥，很难查）。
 *
 * 包格式（`kind` 与 `version` 都参与校验，坏包一律拒绝并给可读原因）：
 * ```json
 * { "app":"MF-Mathematics", "kind":"settings-bundle", "version":1,
 *   "exportedAt":"…", "appVersion":"2.0.0",
 *   "files": { "history": {…}, … }, "prefs": { "mf_theme": "dark" },
 *   "excluded": ["ai","account","search"], "stripped": ["someFile.apiKey"] }
 * ```
 */
import { ref } from "vue";

export const BUNDLE_APP = "MF-Mathematics";
export const BUNDLE_KIND = "settings-bundle";
export const BUNDLE_VERSION = 1;

/** 整份排除的设置文件（里面有凭据；导不进也不导出） */
export const CREDENTIAL_FILES = ["ai", "account", "search"];

/** 字段级剥离：命中即不写入包 */
const SECRET_FIELD = /(protected|password|passwd|secret|token|api[-_]?key)/i;

function sysObj() {
  try { return window.chrome?.webview?.hostObjects?.sync?.sys ?? null; } catch { return null; }
}
function winObj() {
  try { return window.chrome?.webview?.hostObjects?.sync?.win ?? null; } catch { return null; }
}
function parse(text, fallback = null) {
  if (text == null) return fallback;
  if (typeof text === "object") return text;
  try { return JSON.parse(String(text)); } catch { return fallback; }
}

export const settingsIoState = ref({ busy: "", lastExport: null, lastImport: null, error: null });

/** 本机版本（给包里留个来源标记；读不到就留空） */
function appVersion() {
  try { return String(window.__mfUpdate?.info?.().appVersion || ""); } catch { return ""; }
}

/** localStorage 里属于本应用的偏好（外观/主题等，都是 `mf_` 前缀） */
export function collectPrefs() {
  const out = {};
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith("mf_")) out[k] = localStorage.getItem(k);
    }
  } catch { /* localStorage 不可用就算了 */ }
  return out;
}

/**
 * 打包当前设置。**不联网、不碰凭据**。
 * @returns {{ok:boolean, bundle?:object, error?:string}}
 */
export function buildBundle() {
  const sys = sysObj();
  if (!sys) return { ok: false, error: "无宿主：设置文件由宿主管理，导出只在 MFMath.exe 里可用" };

  const listRaw = parse(sys.StoreList());
  // StoreList 出错时返回 {"error":…}（SettingsBridge.StoreList 的异常分支），**不是数组**。
  // 原先静默当成空列表 → 导出"0 个设置文件"却报 ok:true，界面显示"已导出 0 个…"，
  // 用户以为备份好了，真去恢复时什么都没有。这里改成如实失败。
  if (!Array.isArray(listRaw)) {
    return { ok: false, error: String(listRaw?.error || "读不到设置文件清单，导出已中止") };
  }
  const files = listRaw;
  const bundleFiles = {};
  const stripped = [];
  const skippedCorrupt = [];

  for (const item of files) {
    const name = String(item?.name || "");
    if (!name) continue;
    if (CREDENTIAL_FILES.includes(name)) continue;          // 整份排除
    const r = parse(sys.StoreRead(name));
    if (!r || r.ok !== true) {
      // 读失败 / JSON 已损坏：原先直接 continue，**连痕迹都不留** ——
      // 包是"成功"的，但少了一份设置且无人知道。现在记进 skippedCorrupt。
      if (r && r.corrupt) skippedCorrupt.push(name);
      continue;
    }
    if (r.exists === false || !r.json) continue;
    const value = parse(r.json, null);
    if (value === null) { skippedCorrupt.push(name); continue; }
    bundleFiles[name] = stripSecrets(value, name, stripped);
  }

  return {
    ok: true,
    bundle: {
      app: BUNDLE_APP,
      kind: BUNDLE_KIND,
      version: BUNDLE_VERSION,
      exportedAt: new Date().toISOString(),
      appVersion: appVersion(),
      files: bundleFiles,
      prefs: collectPrefs(),
      excluded: [...CREDENTIAL_FILES],
      stripped,
      ...(skippedCorrupt.length ? { skippedCorrupt } : {}),
    },
  };
}

/** 递归剥掉凭据字段（顺带记下剥了哪些字段名）；数组也走一遍 */
function stripSecrets(value, file, stripped) {
  if (Array.isArray(value)) return value.map((v) => stripSecrets(v, file, stripped));
  if (!value || typeof value !== "object") return value;
  const out = {};
  for (const [k, v] of Object.entries(value)) {
    if (SECRET_FIELD.test(k)) { stripped.push(`${file}.${k}`); continue; }
    out[k] = stripSecrets(v, file, stripped);
  }
  return out;
}

/**
 * 应用一个包。**只写包里有的东西**，且不写凭据文件/字段。
 * @returns {{ok:boolean, files?:number, prefs?:number, skipped?:string[], needsRestart?:boolean, error?:string}}
 */
export function applyBundle(input) {
  const sys = sysObj();
  if (!sys) return { ok: false, error: "无宿主：导入只在 MFMath.exe 里可用" };

  const bundle = typeof input === "string" ? parse(input, null) : input;
  if (!bundle || typeof bundle !== "object") return { ok: false, error: "不是合法的 JSON" };
  if (bundle.app !== BUNDLE_APP) return { ok: false, error: `这不是 ${BUNDLE_APP} 的设置备份（app=${bundle.app || "空"}）` };
  if (bundle.kind !== BUNDLE_KIND) return { ok: false, error: `备份类型不对（kind=${bundle.kind || "空"}）` };
  const v = Number(bundle.version);
  if (!Number.isFinite(v)) return { ok: false, error: "备份缺少版本号" };
  if (v > BUNDLE_VERSION) return { ok: false, error: `备份来自更新的版本（v${v}）；请先更新软件再导入` };

  const files = bundle.files && typeof bundle.files === "object" ? bundle.files : {};
  const skipped = [];
  let written = 0;
  for (const [name, value] of Object.entries(files)) {
    // 双保险：即便包里带了凭据文件/字段也不写（否则会覆盖用户现在的密钥）
    if (CREDENTIAL_FILES.includes(name)) { skipped.push(name); continue; }
    const clean = stripSecrets(value, name, []);
    const r = parse(sys.StoreWrite(name, JSON.stringify(clean)));
    if (r && r.ok) written++;
    // 单个文件写失败不中断整包（其余能救回来的先写进去），但要记下来
    else skipped.push(name);
  }

  let prefs = 0;
  const p = bundle.prefs && typeof bundle.prefs === "object" ? bundle.prefs : {};
  for (const [k, val] of Object.entries(p)) {
    if (!k.startsWith("mf_")) { skipped.push(`pref:${k}`); continue; }
    try { localStorage.setItem(k, String(val)); prefs++; } catch { skipped.push(`pref:${k}`); }
  }

  settingsIoState.value = { ...settingsIoState.value, lastImport: { files: written, prefs, at: Date.now() } };
  return {
    ok: true, files: written, prefs,
    ...(skipped.length ? { skipped } : {}),
    // 设置文件与外观偏好都在启动时读取 → 如实说要重启（不假装即时生效）
    needsRestart: true,
  };
}

/* ── 与文件对话框配合（宿主自带自动化钩子：path 非空则跳过对话框）──────── */

export function exportToFile(path = "") {
  const built = buildBundle();
  if (!built.ok) return built;
  const w = winObj();
  if (!w) return { ok: false, error: "无宿主：文件对话框只在 MFMath.exe 里可用" };
  const content = JSON.stringify(built.bundle, null, 2);
  const stamp = new Date().toISOString().slice(0, 10);
  const r = parse(w.SaveTextFile("导出设置", `mfmath-settings-${stamp}.json`, "JSON 文件 (*.json)|*.json|所有文件 (*.*)|*.*", content, path));
  if (!r) return { ok: false, error: "保存没有返回结果" };
  if (r.canceled) return { ok: true, canceled: true };
  if (r.ok !== true) return { ok: false, error: r.error || "保存失败" };
  settingsIoState.value = { ...settingsIoState.value, lastExport: { path: r.path, bytes: r.bytes, at: Date.now() } };
  return { ok: true, path: r.path, bytes: r.bytes, files: Object.keys(built.bundle.files).length, prefs: Object.keys(built.bundle.prefs).length };
}

export function importFromFile(path = "") {
  const w = winObj();
  if (!w) return { ok: false, error: "无宿主：文件对话框只在 MFMath.exe 里可用" };
  const r = parse(w.OpenTextFile("导入设置", "JSON 文件 (*.json)|*.json|所有文件 (*.*)|*.*", path));
  if (!r) return { ok: false, error: "打开没有返回结果" };
  if (r.canceled) return { ok: true, canceled: true };
  if (r.ok !== true) return { ok: false, error: r.error || "读取失败" };
  return applyBundle(r.content);
}

/* ── 测试/排障钩子 ────────────────────────────────────────────────────── */

export function initSettingsIoHook() {
  try {
    window.__mfSettingsIo = {
      build: buildBundle,
      apply: applyBundle,
      exportToFile,
      importFromFile,
      prefs: collectPrefs,
      state: () => settingsIoState.value,
      constants: { app: BUNDLE_APP, kind: BUNDLE_KIND, version: BUNDLE_VERSION, credentialFiles: CREDENTIAL_FILES },
    };
  } catch { /* 忽略 */ }
}
