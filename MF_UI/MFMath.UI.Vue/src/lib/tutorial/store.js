/**
 * store.js — 教程数据与学习进度（v2）
 *
 * 数据源是构建期产物 `src/tutorials/tutorials.json`（由 tools/build-tutorials.mjs
 * 从 v1 的 18 个 YAML 转换而来，逐篇做过数量自检）。
 *
 * 进度存放：localStorage。
 *   · v1 把进度写在**安装目录**（Program Files 下必然写入失败），而且写入失败只
 *     logger.debug —— 用户丢了进度毫无感知。这里两条都改掉：
 *       ① 落到 localStorage（WebView2 的用户数据目录已在 %LOCALAPPDATA%\MFMath\WebView2，
 *          卸载不误删、重装不丢）；
 *       ② 写失败时把错误记进 lastError，由界面明确提示，不再静默。
 *   · 与 v1 的 tutorial_progress.json **不自动互通**：那个文件在旧的 Python 端目录里，
 *     读取需要宿主文件访问（C# 侧 store 桥，属后续任务）。此处保留 import 接口位，
 *     不假装已经支持。
 *
 * 进度与"内容版本"绑定：每篇教程在转换时算了一个内容指纹 version；
 * 教程内容一变（改了步骤/示例/FAQ），该篇的"已学"与引导步数即失效，
 * 避免"旧进度对上新内容"这种最难查的错位。
 */
import { reactive, computed } from "vue";
import data from "../../tutorials/tutorials.json";

const KEY = "mf_tut_progress";
const SCHEMA = 2;

export const TUTORIALS = data.tutorials.slice().sort((a, b) => a.order - b.order);
const BY_ID = new Map(TUTORIALS.map((t) => [t.id, t]));

export const CATEGORY_META = data.categories;

const state = reactive({
  schema: SCHEMA,
  /** id → { at, version } */
  completed: {},
  /** id → 引导进行到第几步（v1 完全没有这个能力，只记整篇是否完成） */
  tourSteps: {},
  lastTutorial: "",
  welcomeSeen: false,
  launchCount: 0,
});

/** 写失败时置为非空字符串；界面据此提示用户（v1 是静默失败）。 */
const lastError = reactive({ message: "" });

function readStorage() {
  let raw = null;
  try {
    raw = localStorage.getItem(KEY);
  } catch (e) {
    lastError.message = `无法读取本地进度（${e?.message || e}）`;
    return;
  }
  if (!raw) return;
  try {
    const p = JSON.parse(raw);
    if (!p || typeof p !== "object") throw new Error("不是对象");
    // 未知 schema：宁可从头开始，也不要把不认识的字段当数据用
    if (p.schema !== SCHEMA) {
      lastError.message = `进度文件版本为 ${p.schema ?? "未知"}，当前支持 ${SCHEMA}，已从空白开始`;
      return;
    }
    state.completed = p.completed && typeof p.completed === "object" ? p.completed : {};
    state.tourSteps = p.tourSteps && typeof p.tourSteps === "object" ? p.tourSteps : {};
    state.lastTutorial = typeof p.lastTutorial === "string" ? p.lastTutorial : "";
    state.welcomeSeen = !!p.welcomeSeen;
    state.launchCount = Number.isFinite(p.launchCount) ? p.launchCount : 0;
  } catch (e) {
    lastError.message = `进度文件已损坏（${e?.message || e}），已从空白开始`;
  }
}

function writeStorage() {
  try {
    localStorage.setItem(
      KEY,
      JSON.stringify({
        schema: SCHEMA,
        completed: state.completed,
        tourSteps: state.tourSteps,
        lastTutorial: state.lastTutorial,
        welcomeSeen: state.welcomeSeen,
        launchCount: state.launchCount,
      })
    );
    lastError.message = "";
    return true;
  } catch (e) {
    // 配额满 / 隐私模式：必须让用户知道，否则"进度又不涨了"无从排查
    lastError.message = `进度保存失败（${e?.message || e}）`;
    return false;
  }
}

let loaded = false;
export function initTutorials() {
  if (loaded) return;
  loaded = true;
  readStorage();
}

/* ── 查询 ─────────────────────────────────────────────────────────────── */

export function getTutorial(id) {
  return BY_ID.get(id) || null;
}

/** 该篇是否"按当前内容"已学完（内容版本不符则视为未学，并单独标记出失效） */
export function isCompleted(id) {
  const t = BY_ID.get(id);
  const rec = state.completed[id];
  if (!t || !rec) return false;
  return rec.version === t.version;
}

/** 进度记录存在但内容已变（用于在界面上说明"为什么又变成未学了"） */
export function isStale(id) {
  const t = BY_ID.get(id);
  const rec = state.completed[id];
  return !!(t && rec && rec.version !== t.version);
}

export const progress = computed(() => {
  const total = TUTORIALS.length;
  const done = TUTORIALS.filter((t) => isCompleted(t.id)).length;
  return { total, done, percent: total ? Math.round((done / total) * 1000) / 10 : 0 };
});

export const lastTutorial = computed(() => state.lastTutorial);
export const savedTourStep = (id) => {
  const t = BY_ID.get(id);
  const rec = state.tourSteps[id];
  if (!t || !rec) return null;
  if (rec.version !== t.version) return null; // 内容变了，别拿旧步数接着走
  return Number.isInteger(rec.step) ? rec.step : null;
};
export const storageError = computed(() => lastError.message);

/* ── 修改 ─────────────────────────────────────────────────────────────── */

export function markCompleted(id) {
  const t = BY_ID.get(id);
  if (!t) return false;
  state.completed[id] = { at: new Date().toISOString(), version: t.version };
  delete state.tourSteps[id]; // 学完了就不再需要"接着上次"的步数
  return writeStorage();
}

export function markIncomplete(id) {
  if (!state.completed[id]) return true;
  delete state.completed[id];
  return writeStorage();
}

export function setLastTutorial(id) {
  if (state.lastTutorial === id) return true;
  state.lastTutorial = id;
  return writeStorage();
}

export function saveTourStep(id, step) {
  const t = BY_ID.get(id);
  if (!t) return false;
  state.tourSteps[id] = { step, version: t.version };
  return writeStorage();
}

export function clearTourStep(id) {
  if (!state.tourSteps[id]) return true;
  delete state.tourSteps[id];
  return writeStorage();
}

/** 首次启动：v1 的语义是"弹过一次就永久置真"，这里保持一致；另外单独记 launchCount。 */
export const isFirstLaunch = computed(() => !state.welcomeSeen);
export const launchCount = computed(() => state.launchCount);

export function markLaunched() {
  state.welcomeSeen = true;
  state.launchCount += 1;
  return writeStorage();
}

export function resetAllProgress() {
  state.completed = {};
  state.tourSteps = {};
  state.lastTutorial = "";
  return writeStorage();
}

/** 供示例库/目录页筛选 */
export function listTutorials({ category = "", difficulty = "" } = {}) {
  return TUTORIALS.filter(
    (t) => (!category || t.category === category) && (!difficulty || t.difficulty === difficulty)
  );
}
