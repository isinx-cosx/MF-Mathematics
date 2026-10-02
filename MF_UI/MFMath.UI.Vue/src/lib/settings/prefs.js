/**
 * settings/prefs.js — 计算与绘图偏好（v1 设置里那两个一直没迁过来的项）
 *
 * v1 的 settings_dialog.py 里有两项 v2.0 一直没有：
 *   · **数值精度**（`_precision_combo`，"位有效数字"）—— v1 实际按 `f"{v:.12f}"` 显示
 *   · **绘图默认值**（X/Y 轴范围）
 * 它们既不是外观也不是引擎信息，所以这里单独建一个「计算与绘图」分组。
 *
 * 存放：宿主键值存储的 `prefs.json`（浏览器预览时自动降级到 localStorage，见 settings/bridge.js）。
 * 生效方式：**改了就生效**（与外观组一致，没有保存按钮）——
 *   · `decimals` 被 `lib/engine/resultFormat.js` 的 `fmtNum()` 读取；
 *   · `plotRange` 被 `lib/plot/view.js` 的 `defaultView()` 读取。
 * 两者都是响应式读取，所以设置一改，下次渲染/下次开图就是新值，不需要刷新页面。
 */
import { computed, ref } from "vue";
import { loadSettings, saveSettings } from "./bridge.js";

/** 数值精度：小数位数。默认 12 —— 与 v1 的 `:.12f` 对齐（改默认值会影响所有已有截图/用例）。 */
export const MIN_DECIMALS = 0;
export const MAX_DECIMALS = 15;
export const DEFAULT_DECIMALS = 12;

export const DEFAULTS = {
  decimals: DEFAULT_DECIMALS,
  // 绘图默认范围：四项都填才生效；留空（null）= 按画布宽高比自动（v1 的行为）
  plotXMin: null,
  plotXMax: null,
  plotYMin: null,
  plotYMax: null,
};

export const prefs = ref({ ...DEFAULTS });
const errorText = ref("");
let loaded = false;
let saveTimer = null;

function clampDecimals(n) {
  const v = Math.round(Number(n));
  if (!Number.isFinite(v)) return DEFAULT_DECIMALS;
  return Math.min(MAX_DECIMALS, Math.max(MIN_DECIMALS, v));
}

/** 只接受"有效数字或 null"的范围值；非法值一律当没填 */
function numOrNull(v) {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export function loadPrefs(force = false) {
  if (loaded && !force) return prefs.value;
  loaded = true;
  const r = loadSettings("prefs", DEFAULTS);
  errorText.value = r.error || "";
  const v = r.value || {};
  prefs.value = {
    decimals: clampDecimals(v.decimals ?? DEFAULT_DECIMALS),
    plotXMin: numOrNull(v.plotXMin),
    plotXMax: numOrNull(v.plotXMax),
    plotYMin: numOrNull(v.plotYMin),
    plotYMax: numOrNull(v.plotYMax),
  };
  return prefs.value;
}

function persist() {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    saveTimer = null;
    const r = saveSettings("prefs", prefs.value);
    if (r && r.ok === false) errorText.value = r.error || "写入失败";
  }, 200);
}

export function setDecimals(n) {
  loadPrefs();
  prefs.value = { ...prefs.value, decimals: clampDecimals(n) };
  persist();
}

/**
 * 设置绘图默认范围。传 null/"" 表示"这一项留空"。
 * 返回是否是一组**可用**的范围（四项都填、且 min < max）——
 * 界面据此给出内联提示（不弹窗）。
 */
export function setPlotRange({ xMin, xMax, yMin, yMax }) {
  loadPrefs();
  prefs.value = {
    ...prefs.value,
    plotXMin: numOrNull(xMin),
    plotXMax: numOrNull(xMax),
    plotYMin: numOrNull(yMin),
    plotYMax: numOrNull(yMax),
  };
  persist();
  return plotRangeState();
}

/** 当前范围配置的状态：怎么用、为什么不能用（供界面显示，不弹窗） */
export function plotRangeState() {
  const p = prefs.value;
  const vals = [p.plotXMin, p.plotXMax, p.plotYMin, p.plotYMax];
  const filled = vals.filter((v) => v !== null).length;
  if (filled === 0) return { mode: "auto", text: "按画布宽高比自动（与 v1 默认一致）" };
  if (filled < 4) return { mode: "partial", text: "四项都填才会生效；现在只有 " + filled + " 项，仍按自动" };
  if (!(p.plotXMin < p.plotXMax)) return { mode: "invalid", text: "X 轴：最小必须小于最大，现在按自动" };
  if (!(p.plotYMin < p.plotYMax)) return { mode: "invalid", text: "Y 轴：最小必须小于最大，现在按自动" };
  return {
    mode: "fixed",
    text: `固定 x∈[${p.plotXMin}, ${p.plotXMax}]、y∈[${p.plotYMin}, ${p.plotYMax}]`,
  };
}

/** 供 resultFormat / view.js 读取：当前小数位数 */
export function currentDecimals() {
  loadPrefs();
  return prefs.value.decimals;
}

/** 供 view.js 读取：可用的固定视图，或 null（表示按宽高比自动） */
export function currentPlotRange() {
  loadPrefs();
  const st = plotRangeState();
  if (st.mode !== "fixed") return null;
  const p = prefs.value;
  return { x0: p.plotXMin, x1: p.plotXMax, y0: p.plotYMin, y1: p.plotYMax };
}

export function resetPrefs() {
  prefs.value = { ...DEFAULTS };
  persist();
}

export function prefsError() {
  loadPrefs();
  return errorText.value;
}

export function usePrefs() {
  loadPrefs();
  return {
    prefs,
    state: computed(() => plotRangeState()),
    error: computed(() => errorText.value),
    setDecimals,
    setPlotRange,
    resetPrefs,
    MIN_DECIMALS,
    MAX_DECIMALS,
    DEFAULT_DECIMALS,
  };
}

/**
 * 测试/排障钩子 `window.__mfPrefs`：设置页里的两个控件在 CDP 里点得到，
 * 但"当前精度/范围到底存成什么了"看得见才好评判。
 * 注意**不在这里暴露 fmtNum**：resultFormat.js 依赖本模块，反过来引会成环；
 * 精度是否生效由设置行里的示例文本（它走真实 fmtNum）与真实计算来验。
 */
export function initPrefs() {
  loadPrefs();
  try {
    window.__mfPrefs = {
      get: () => ({ ...prefs.value }),
      state: plotRangeState,
      setDecimals,
      setPlotRange,
      reset: resetPrefs,
    };
  } catch { /* 忽略 */ }
}
