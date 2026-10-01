/**
 * WebView2 桥封装 — 对齐 C# MathBridge
 * - 桌面壳（WebView2）：window.chrome.webview.hostObjects.sync.mf.{dispatch,ready,version}
 * - 浏览器（无桥）：全部优雅降级（返回 null / false），UI 显示"待接入"
 */
"use strict";

/* ── 外观：四组互相独立的预设 ────────────────────────────────────────────────
 *
 * 配色（THEME_LIST）与形状/疏密/字体分开，所以用户能"只换配色、保留圆角"。
 * 每套配色都标了 mode，供「跟随系统」挑选合适的深浅版本；
 * family 用来让「跟随系统」在切换浅/深时留在同一套风格里（玻璃↔玻璃）。 */
const THEME_LIST = [
  { id: "glass-light",   label: "液态玻璃", mode: "light", family: "glass",   desc: "半透明面板 + 蓝色渐变，与官网同源" },
  { id: "glass-dark",    label: "液态玻璃", mode: "dark",  family: "glass",   desc: "半透明面板 + 蓝色渐变（深色）" },
  { id: "minimal-light", label: "极简",     mode: "light", family: "minimal", desc: "纯白底 + 细描边，最省眼" },
  { id: "minimal-dark",  label: "极简",     mode: "dark",  family: "minimal", desc: "近黑底 + 细描边（深色）" },
  { id: "nord-light",    label: "北欧冷灰", mode: "light", family: "nord",    desc: "低饱和冷灰 + 雾蓝强调色" },
  { id: "nord-dark",     label: "北欧冷灰", mode: "dark",  family: "nord",    desc: "低饱和冷灰（深色）" },
  { id: "paper-light",   label: "纸质护眼", mode: "light", family: "paper",   desc: "米黄纸感 + 暖棕强调色，久看不累" },
  { id: "sakura-light",  label: "樱粉",     mode: "light", family: "sakura",  desc: "浅粉底 + 玫红强调色" },
  { id: "neon-dark",     label: "深色霓虹", mode: "dark",  family: "neon",    desc: "近黑底 + 青紫霓虹光" },
  { id: "terminal-dark", label: "终端绿",   mode: "dark",  family: "terminal", desc: "终端绿字 + 荧光强调色" },
];

/** 形状预设：圆角与阴影层级 */
const SHAPE_LIST = [
  { id: "glass", label: "玻璃感", desc: "大圆角 + 明显投影" },
  { id: "flat",  label: "极简硬朗", desc: "小圆角 + 几乎无阴影" },
  { id: "round", label: "圆润卡片", desc: "更大圆角 + 柔和扩散阴影" },
];

/** 疏密预设 */
const DENSITY_LIST = [
  { id: "cozy",    label: "舒适", desc: "默认留白" },
  { id: "compact", label: "紧凑", desc: "小屏幕上同屏放更多内容" },
];

/** 文字预设（公式与代码恒为等宽，不受这里影响） */
const FONT_LIST = [
  { id: "sans",  label: "默认", desc: "Inter / 系统无衬线" },
  { id: "serif", label: "衬线", desc: "Georgia / 宋体，偏阅读" },
  { id: "mono",  label: "等宽", desc: "全界面等宽，偏工程" },
];

const THEMES = THEME_LIST.map((t) => t.id);
const THEME_LABELS = Object.fromEntries(THEME_LIST.map((t) => [t.id, t.label]));

const DEFAULT_THEME = "glass-light";
const DEFAULT_SHAPE = "glass";
const DEFAULT_DENSITY = "cozy";
const DEFAULT_FONT = "sans";

/** 配色 mode → 跟随系统时的取值。只有单边配色的风格（霓虹、终端、纸质、樱粉）就固定用它自己那一版。 */
function themeForSystem() {
  let want = "light";
  try {
    if (window.matchMedia?.("(prefers-color-scheme: dark)").matches) want = "dark";
  } catch { /* 忽略 */ }
  const cur = THEME_LIST.find((t) => t.id === currentTheme());
  // 当前风格有对应深浅版本 → 留在同一套风格里换深浅，视觉跳跃最小
  if (cur) {
    const sibling = THEME_LIST.find((t) => t.family === cur.family && t.mode === want);
    if (sibling) return sibling.id;
    return cur.id;
  }
  return THEME_LIST.find((t) => t.mode === want)?.id || DEFAULT_THEME;
}

let followSystem = false;
try {
  followSystem = localStorage.getItem("mf_theme_follow") === "1";
} catch { /* 忽略 */ }

export function isFollowingSystem() {
  return followSystem;
}

function stored(key, fallback, allowed) {
  try {
    const v = localStorage.getItem(key);
    return allowed.includes(v) ? v : fallback;
  } catch {
    return fallback;
  }
}

function bridgeObj() {
  try {
    return window.chrome?.webview?.hostObjects?.sync?.mf ?? null;
  } catch {
    return null;
  }
}

/** 是否运行在桌面壳（有 WebView2 桥） */
export function isHosted() {
  return bridgeObj() !== null;
}

/** 桥自检 */
export function bridgeReady() {
  const mf = bridgeObj();
  try {
    return mf ? !!mf.Ready() : false;
  } catch {
    return false;
  }
}

/** 版本信息 */
export function bridgeVersion() {
  const mf = bridgeObj();
  try {
    return mf ? String(mf.Version()) : "";
  } catch {
    return "";
  }
}

/**
 * 调引擎：name=引擎函数名，args=普通 JS 对象
 * 返回 {isError, value}；无桥/异常返回 null
 */
export function engineCall(name, args) {
  const mf = bridgeObj();
  if (!mf) return null;
  try {
    const out = mf.Dispatch(name, JSON.stringify(args || {}));
    return typeof out === "string" ? JSON.parse(out) : out;
  } catch (e) {
    return { isError: true, value: "桥调用失败: " + (e && e.message ? e.message : e) };
  }
}

/**
 * 函数是否存在（能力探测）。
 *
 * 走宿主方法 `mf.FunctionExists`，它内部调的是 C ABI 导出 `function_exists`。
 * **不能**用 engineCall("function_exists", …)：那是 C 导出，**不在 424 个已注册
 * 动作里**，当成动作去 Dispatch 必然返回错误信封，于是这个探测以前**恒为 false**
 * （连宿主里也一样，是本次引擎自检把它逼出来的）。
 * 保底分支只为兼容"没有宿主方法、只有 Dispatch 透传"的旧桥。
 */
export function functionExists(name) {
  const mf = bridgeObj();
  if (mf) {
    try {
      return !!mf.FunctionExists(name);
    } catch { /* 旧桥没有这个方法，退到下面的动作探测 */ }
  }
  const r = engineCall("function_exists", { name });
  return r && !r.isError ? !!r.value : false;
}

/* ── 主题 ── */

/** 读当前配色 */
export function currentTheme() {
  const t = document.documentElement.dataset.theme;
  return THEMES.includes(t) ? t : DEFAULT_THEME;
}

/** 当前配色是深色还是浅色（画布配色靠它，而不是靠"是不是某一个具体主题"） */
export function currentMode() {
  if (document.documentElement.dataset.mode === "dark") return "dark";
  return THEME_LIST.find((t) => t.id === currentTheme())?.mode || "light";
}

/** 当前配色的中文名（选择器与侧栏按钮显示用） */
export function themeLabel(id) {
  const t = THEME_LIST.find((x) => x.id === (id || currentTheme()));
  if (!t) return id || "";
  return t.mode === "dark" ? t.label + " · 深" : t.label + " · 浅";
}

/* ── 画布配色 ────────────────────────────────────────────────────────────────
 *
 * 画布是用 <canvas> 自己画的，不认 CSS 变量，所以得知道当前是深色还是浅色。
 * 它们又不在同一个 props 链上（视图不转发 theme），所以这里提供一个
 * DOM 事件当广播：外观一变就通知所有画布重绘。
 *
 * 以前的问题是：数据的 theme 属性**从来没有人传值**，画布永远走默认的 "light"，
 * 于是切到任何深色主题，画布依然是白底浅网格——多主题看着"没生效"。 */
export const APPEARANCE_EVENT = "mf-appearance";

/** 画布该用深色还是浅色：显式传了就用显式的，否则跟随当前配色。 */
export function plotMode(explicit) {
  if (explicit === "dark" || explicit === "light") return explicit;
  return currentMode() === "dark" ? "dark" : "light";
}

/** 订阅外观变化；返回取消订阅函数。 */
export function onAppearanceChange(fn) {
  const h = () => fn();
  document.addEventListener(APPEARANCE_EVENT, h);
  return () => document.removeEventListener(APPEARANCE_EVENT, h);
}

/** 画布底色：取自当前配色的 --plot-bg，保证纸质/樱粉等配色下画布也是同色系 */
export function plotBackground() {
  try {
    const v = getComputedStyle(document.documentElement).getPropertyValue("--plot-bg").trim();
    if (v) return v;
  } catch { /* 忽略 */ }
  return currentMode() === "dark" ? "#0d1117" : "#ffffff";
}

/** 取当前主题的背景色（用于回设窗口背景，避免加载/缩放瞬间闪白）。 */
export function themeBackgroundColor() {
  try {
    const v = getComputedStyle(document.documentElement).getPropertyValue("--bg").trim();
    return v || "";
  } catch {
    return "";
  }
}

/**
 * 应用外观到 <html> 的属性并存 localStorage。
 *
 * 四个维度分别落在 data-theme / data-shape / data-density / data-font 上，
 * 互不覆盖——这正是"只换配色、保留圆角"能成立的原因。
 * 另外把窗口背景同步给桌面壳：窗口**没有原生标题栏**（见 MainWindow.xaml），
 * 整条顶栏由本 UI 绘制，所以外壳颜色也必须跟着主题走，
 * 否则切到深色时缩放/最大化的一瞬间会露出浅色底。
 */
export function applyAppearance(patch = {}) {
  const el = document.documentElement;
  if (patch.theme !== undefined && THEMES.includes(patch.theme)) {
    el.dataset.theme = patch.theme;
    // data-mode 是给画布用的**显式**深浅标记：不依赖"主题名里有没有 dark"
    el.dataset.mode = THEME_LIST.find((t) => t.id === patch.theme)?.mode || "light";
    try { localStorage.setItem("mf_theme", patch.theme); } catch { /* 忽略 */ }
  }
  if (patch.shape !== undefined && SHAPE_LIST.some((s) => s.id === patch.shape)) {
    el.dataset.shape = patch.shape;
    try { localStorage.setItem("mf_shape", patch.shape); } catch { /* 忽略 */ }
  }
  if (patch.density !== undefined && DENSITY_LIST.some((d) => d.id === patch.density)) {
    el.dataset.density = patch.density;
    try { localStorage.setItem("mf_density", patch.density); } catch { /* 忽略 */ }
  }
  if (patch.font !== undefined && FONT_LIST.some((f) => f.id === patch.font)) {
    el.dataset.font = patch.font;
    try { localStorage.setItem("mf_font", patch.font); } catch { /* 忽略 */ }
  }
  if (patch.followSystem !== undefined) {
    followSystem = !!patch.followSystem;
    try { localStorage.setItem("mf_theme_follow", followSystem ? "1" : "0"); } catch { /* 忽略 */ }
    el.dataset.follow = followSystem ? "1" : "0";
    if (followSystem) applyAppearance({ theme: themeForSystem() });
  }
  // 等样式生效后再读颜色，确保读到的是新主题的值；
  // 同时广播给画布（它们不认 CSS 变量，得自己收到通知重绘）
  requestAnimationFrame(() => {
    winSetChromeBackground(themeBackgroundColor());
    try { document.dispatchEvent(new CustomEvent(APPEARANCE_EVENT)); } catch { /* 忽略 */ }
  });
}

/** 兼容旧调用：只换配色 */
export function applyTheme(theme) {
  applyAppearance({ theme });
}

/** 循环到下一套配色（保留：键盘/快捷方式仍可用） */
export function cycleTheme() {
  const idx = THEMES.indexOf(currentTheme());
  const next = THEMES[(idx + 1) % THEMES.length];
  applyAppearance({ theme: next });
  return next;
}

/** 读回当前外观（选择器用它显示选中项） */
export function currentAppearance() {
  const el = document.documentElement;
  return {
    theme: currentTheme(),
    shape: SHAPE_LIST.some((s) => s.id === el.dataset.shape) ? el.dataset.shape : DEFAULT_SHAPE,
    density: DENSITY_LIST.some((d) => d.id === el.dataset.density) ? el.dataset.density : DEFAULT_DENSITY,
    font: FONT_LIST.some((f) => f.id === el.dataset.font) ? el.dataset.font : DEFAULT_FONT,
    followSystem,
  };
}

/** 初始化外观（从 localStorage 读回上次的选择） */
export function initTheme() {
  const shape = stored("mf_shape", DEFAULT_SHAPE, SHAPE_LIST.map((s) => s.id));
  const density = stored("mf_density", DEFAULT_DENSITY, DENSITY_LIST.map((d) => d.id));
  const font = stored("mf_font", DEFAULT_FONT, FONT_LIST.map((f) => f.id));
  const theme = stored("mf_theme", DEFAULT_THEME, THEMES);
  // 先用存下来的值铺好三个维度，再看要不要跟随系统覆盖配色
  document.documentElement.dataset.shape = shape;
  document.documentElement.dataset.density = density;
  document.documentElement.dataset.font = font;
  applyAppearance({ theme: followSystem ? themeForSystem() : theme });
  document.documentElement.dataset.follow = followSystem ? "1" : "0";
}

/**
 * 跟随系统：系统深浅色一变就换到对应版本。
 * 返回取消订阅函数，App.vue 在 onBeforeUnmount 里调用。
 */
export function watchSystemTheme() {
  let mq = null;
  try {
    mq = window.matchMedia?.("(prefers-color-scheme: dark)") || null;
  } catch { /* 忽略 */ }
  if (!mq) return () => {};
  const onChange = () => {
    if (followSystem) applyAppearance({ theme: themeForSystem() });
  };
  mq.addEventListener?.("change", onChange);
  return () => mq.removeEventListener?.("change", onChange);
}

/* ── 窗口外壳（拖动 / 最小化 / 最大化 / 关闭）──────────────────────────────
 *
 * 窗口不再由 WPF 画标题栏，顶部这条就是 JS 顶栏本身，
 * 因此窗口操作要从这里回调到宿主（hostObjects.sync.win）。
 * 浏览器里没有宿主时全部降级为 no-op，并且顶栏不显示这三个按钮。
 */

function winBridge() {
  try {
    return window.chrome?.webview?.hostObjects?.sync?.win ?? null;
  } catch {
    return null;
  }
}

export function windowControlsAvailable() {
  return winBridge() !== null;
}

// 窗口操作失败必须可见：全吞掉的话"点了没反应"就无从排查。
// 桥不存在（浏览器里）是正常情况，不算错误。
function callWin(method, ...args) {
  const b = winBridge();
  if (!b) return;
  try {
    b[method](...args);
  } catch (e) {
    console.error("[win] " + method + " 调用失败:", e && e.message ? e.message : e);
  }
}

export function winMinimize() { callWin("Minimize"); }
export function winToggleMaximize() { callWin("ToggleMaximize"); }
export function winClose() { callWin("Close"); }

export function winIsMaximized() {
  try { return winBridge()?.IsMaximized() === true; } catch { return false; }
}

/** 开始拖动窗口（顶栏空白处 mousedown 时调用）。 */
export function winStartDrag() { callWin("StartDrag"); }

export function winSetChromeBackground(color) {
  if (!color) return;
  callWin("SetChromeBackground", color);
}

export { THEMES, THEME_LABELS, THEME_LIST, SHAPE_LIST, DENSITY_LIST, FONT_LIST };
