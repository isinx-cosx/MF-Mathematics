/**
 * WebView2 桥封装 — 对齐 C# MathBridge
 * - 桌面壳（WebView2）：window.chrome.webview.hostObjects.sync.mf.{Dispatch,Ready,Version}
 *   ⚠ 成员名是 **PascalCase 且大小写敏感**（写 `mf.dispatch` 会抛 0x80070057，
 *     而不是返回 undefined）—— 这里曾写成小写，排查过一次"日志一行都没记"的故障。
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

/* ── 异步通道：重活 ──────────────────────────────────────────────────────────
 *
 * 为什么要有它：同步的 engineCall 会**占住渲染进程主线程**，而引擎里确实有能跑到
 * 秒级甚至更久的动作 —— mandelbrot（1200×1200×1024 ≈ 1.5e9 次迭代）、
 * complex_grid（resolution ≤1000 → 1e6 点）、expr_eval_grid（工具箱参数自由，
 * 2000×2000 = 4e6 点），以及 factor_integer / integrate_double / taylor_series
 * 这类**没有上界**的符号运算。一跑就是"窗口白屏 + 系统判定未响应"。
 *
 * 分界线（见 lib/engine/asyncPolicy.js）：**毫秒级走 engineCall，可能重走 engineCallAsync**。
 *
 * 返回值与同步版逐条对齐（这样调用点从 sync 换 async 只需要加 await）：
 *   · 成功 → {isError,value}；失败 → {isError:true,value:"原因"}
 *   · 没有宿主（浏览器里）→ null
 *   · 宿主**没有** DispatchJob 方法（旧桥 / C# 宿主还没实现）→ **自动退回同步调用**
 *     —— 这一条是刻意的：前端不能因为宿主版本旧就不好用。
 *
 * 额外能力：
 *   · opts.onProgress({state, elapsedMs, ms}) —— 界面可以显示"计算中 3.2s"
 *   · opts.signal（AbortSignal）—— 触发时调 CancelJob；**注意语义**：引擎没有取消钩子，
 *     宿主只能"停止等待并丢弃结果"，它会把这一步算完。所以文案必须写"已取消等待"，
 *     不能写"已停止"（这条在 jobs.rs 里有同样的说明）。
 */
export function engineCallAsync(name, args, opts = {}) {
  const mf = bridgeObj();
  if (!mf) return Promise.resolve(null); // 浏览器：与同步版一致，调用方本来就处理 null

  // 旧桥退回同步（C# 宿主尚未实现 job 通道时的兼容路径）
  if (typeof mf.DispatchJob !== "function") {
    return Promise.resolve(engineCall(name, args));
  }

  let jobId = "";
  try {
    const raw = mf.DispatchJob(name, JSON.stringify(args || {}));
    const r = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (!r || !r.ok || !r.jobId) {
      return Promise.resolve({ isError: true, value: "派发后台任务失败: " + (r && r.error ? r.error : "未知原因") });
    }
    jobId = r.jobId;
  } catch (e) {
    return Promise.resolve(engineCall(name, args)); // 派发不了就退回同步，至少能用
  }

  const t0 = Date.now();
  const POLL_MS = 120;
  return new Promise((resolve) => {
    let canceled = false;
    let timer = null;

    const finish = (r) => {
      if (timer) { clearTimeout(timer); timer = null; }
      if (opts.signal) { try { opts.signal.removeEventListener("abort", onAbort); } catch { /* 忽略 */ } }
      resolve(r);
    };
    const onAbort = () => {
      if (canceled) return;
      canceled = true;
      try { mf.CancelJob(jobId); } catch { /* 宿主可能已经结束 */ }
      if (typeof opts.onProgress === "function") opts.onProgress({ state: "canceled", elapsedMs: Date.now() - t0 });
      finish({ isError: true, value: "已取消等待（引擎会把这一步算完后丢弃结果）", canceled: true });
    };
    if (opts.signal) {
      if (opts.signal.aborted) { onAbort(); return; }
      try { opts.signal.addEventListener("abort", onAbort); } catch { /* 忽略 */ }
    }

    const tick = () => {
      if (canceled) return;
      let st = null;
      try {
        const raw = mf.PollJob(jobId);
        st = typeof raw === "string" ? JSON.parse(raw) : raw;
      } catch { /* 下面按未知状态处理 */ }
      if (!st || st.ok === false) {
        finish({ isError: true, value: "后台任务状态读取失败: " + (st && st.error ? st.error : "未知原因") });
        return;
      }
      if (st.state === "done" || st.state === "error") {
        if (typeof opts.onProgress === "function") opts.onProgress({ state: st.state, elapsedMs: st.elapsedMs, ms: st.ms });
        let out = null;
        try { out = st.result ? JSON.parse(st.result) : null; } catch { out = null; }
        finish(out || { isError: true, value: "后台任务返回了无法解析的结果" });
        return;
      }
      if (st.state === "canceled") {
        finish({ isError: true, value: "已取消等待（引擎会把这一步算完后丢弃结果）", canceled: true });
        return;
      }
      if (typeof opts.onProgress === "function") {
        opts.onProgress({ state: st.state, elapsedMs: st.elapsedMs || (Date.now() - t0) });
      }
      timer = setTimeout(tick, POLL_MS);
    };
    tick();
  });
}

/** 查后台任务状态（诊断用；正常调用走 engineCallAsync 内部的轮询） */
export function engineJobPoll(jobId) {
  const mf = bridgeObj();
  if (!mf || typeof mf.PollJob !== "function") return null;
  try {
    const raw = mf.PollJob(jobId);
    return typeof raw === "string" ? JSON.parse(raw) : raw;
  } catch { return null; }
}

/** 取消后台任务（诊断用；正常调用走 engineCallAsync 的 opts.signal） */
export function engineJobCancel(jobId) {
  const mf = bridgeObj();
  if (!mf || typeof mf.CancelJob !== "function") return null;
  try {
    const raw = mf.CancelJob(jobId);
    return typeof raw === "string" ? JSON.parse(raw) : raw;
  } catch { return null; }
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

/**
 * Tauri 的命令通道（换壳后宿主不再注入宿主对象，只有 `invoke`）。
 *
 * 为什么要单独一个探测：Tauri 底下**仍然是 WebView2**，所以 `window.chrome.webview`
 * 依然存在，`hostObjects.sync` 甚至可能是个"看着像对象"的东西 —— 只判它存在会误判成
 * "有同步桥"，于是窗口按钮点了没反应。所以这里反过来：**Tauri 优先**，同步桥兜底。
 */
function tauriInvoke() {
  try {
    const t = window.__TAURI_INTERNALS__;
    return t && typeof t.invoke === "function" ? t.invoke.bind(t) : null;
  } catch {
    return null;
  }
}

/** 通用桥调用（Tauri）：`invoke("call", {object, method, args})` → Promise<string|null> */
function tauriHostCall(object, method, args = []) {
  const invoke = tauriInvoke();
  if (!invoke) return null;
  return invoke("call", { object, method, args });
}

export function windowControlsAvailable() {
  return winBridge() !== null || tauriInvoke() !== null;
}

// 窗口操作失败必须可见：全吞掉的话"点了没反应"就无从排查。
// 桥不存在（浏览器里）是正常情况，不算错误。
function callWin(method, ...args) {
  const b = winBridge();
  if (b) {
    try {
      b[method](...args);
    } catch (e) {
      console.error("[win] " + method + " 调用失败:", e && e.message ? e.message : e);
    }
    return;
  }
  // Tauri：命令是异步的，但最小化/最大化/关闭/拖拽都是"发出去就不管结果"的动作，
  // 不需要调用点 await —— 这里就地发、失败记日志。
  const p = tauriHostCall("win", method, args);
  if (p && typeof p.then === "function") {
    p.catch((e) => console.error("[win] " + method + " 调用失败:", e && e.message ? e.message : e));
  }
}

export function winMinimize() { callWin("Minimize"); }
export function winToggleMaximize() { callWin("ToggleMaximize"); }
export function winClose() { callWin("Close"); }

/**
 * 是否最大化。
 *
 * 同步桥能直接问；Tauri 的 `invoke` 只能给 Promise，而这个函数被顶栏的按钮图标同步读取 ——
 * 所以这里**返回上次已知值并异步刷新**：App.vue 在切换最大化后与 resize 时都会再同步一次
 * （`syncMaximized`），图标自然就跟上了，不必把整条渲染路径改成异步。
 */
let lastMaximized = false;
export function winIsMaximized() {
  const b = winBridge();
  if (b) {
    try { lastMaximized = b.IsMaximized() === true; } catch { /* 保持上次值 */ }
    return lastMaximized;
  }
  const p = tauriHostCall("win", "IsMaximized", []);
  if (p && typeof p.then === "function") {
    p.then((v) => { lastMaximized = v === "true" || v === true; }).catch(() => {});
  }
  return lastMaximized;
}

/** 开始拖动窗口（顶栏空白处 mousedown 时调用）。 */
export function winStartDrag() { callWin("StartDrag"); }

export function winSetChromeBackground(color) {
  if (!color) return;
  callWin("SetChromeBackground", color);
}

/* ── 文件对话框（宿主侧 Microsoft.Win32，页面无法读写任意路径） ──────────────
 *
 * 工作区"另存为 / 从文件打开"用它们；将来导出图片也走同一对方法。
 * 返回统一是 {ok:true,…} | {canceled:true} | {ok:false,error}，**不抛异常**：
 * 用户点取消是正常操作，不该让调用处去 try/catch。
 * path 参数是自动化钩子（非空则跳过对话框直接读写），正常调用不传。
 */
function callWinJson(method, ...args) {
  const b = winBridge();
  if (!b) return { ok: false, error: "无宿主：文件对话框只在 MFMath.exe 里可用" };
  try {
    const raw = b[method](...args);
    if (raw == null) return { ok: false, error: "宿主没有返回结果" };
    return typeof raw === "object" ? raw : JSON.parse(String(raw));
  } catch (e) {
    return { ok: false, error: String(e && e.message ? e.message : e) };
  }
}

/**
 * 保存文本到文件（无 path 时弹"另存为"对话框）。
 * @param {{title?:string, defaultName?:string, filter?:string, content:string, path?:string}} o
 */
export function saveTextFile({ title = "保存", defaultName = "", filter = "", content = "", path = "" } = {}) {
  return callWinJson("SaveTextFile", title, defaultName, filter, content, path);
}

/** 从文件读文本（无 path 时弹"打开"对话框） */
export function openTextFile({ title = "打开", filter = "", path = "" } = {}) {
  return callWinJson("OpenTextFile", title, filter, path);
}

/**
 * 保存二进制（base64）到文件 —— 导出图片用。
 * 可以直接传完整的 `data:image/png;base64,…`，宿主会自己剥前缀。
 */
export function saveBinaryFile({ title = "保存", defaultName = "", filter = "", base64 = "", path = "" } = {}) {
  return callWinJson("SaveBinaryFile", title, defaultName, filter, base64, path);
}

export { THEMES, THEME_LABELS, THEME_LIST, SHAPE_LIST, DENSITY_LIST, FONT_LIST };
