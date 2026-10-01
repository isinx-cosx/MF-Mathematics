/**
 * tour.js — 引导式走查的状态机
 *
 * 与 v1 的差异（都是刻意修的缺陷，不是顺手改的）：
 *   1. **有"上一步"**：v1 的 `_advance` 只会前进，全库没有 prev 实现。
 *   2. **有"暂停/继续"**：v1 没有暂停概念；唯一的"停"是 stop/skip，
 *      而它们会把 `_current_step` 归零（丢进度）。
 *   3. **能"接着上次走"**：v1 的 start() 永远从第 0 步开始，且不检查已学状态。
 *   4. **完成即真完成**：v1 在"所有步骤都被静默跳过"的空转后仍调用
 *      mark_completed —— 教程 05/11 就是这样变成"已完成"却什么都没显示的。
 *      这里只有**确实走到过最后一步**才算完成，且完成后若仍有缺目标的步骤，
 *      会把数量回报给界面明说。
 *   5. **缺目标不跳过**：改为把该步标成 critical，由界面显示"目标界面尚未实现"。
 */
import { reactive, computed } from "vue";
import { getTutorial, markCompleted, markIncomplete, saveTourStep, clearTourStep, savedTourStep } from "./store.js";

const state = reactive({
  active: false,
  paused: false,
  tutorialId: "",
  index: 0,
  /** 本次引导里到达过的步骤序号（0-based），用于判断"真的走完" */
  visited: [],
  /** 本次引导里缺目标的步骤序号 */
  missing: [],
  /** 上一次 finish 的结果，供界面提示 */
  lastResult: null,
});

export const tourState = state;
export const currentTutorial = computed(() => (state.tutorialId ? getTutorial(state.tutorialId) : null));
export const stepCount = computed(() => currentTutorial.value?.steps.length ?? 0);
export const currentStep = computed(() => currentTutorial.value?.steps[state.index] ?? null);
export const isLast = computed(() => stepCount.value > 0 && state.index >= stepCount.value - 1);
export const canPrev = computed(() => state.index > 0);
export const currentTargetName = computed(() => currentStep.value?.target || "");

export function start(id, { resume = false } = {}) {
  const t = getTutorial(id);
  if (!t || t.steps.length === 0) {
    state.active = false;
    return false;
  }
  state.active = true;
  state.paused = false;
  state.tutorialId = id;
  state.index = 0;
  state.visited = [0];
  state.missing = [];
  state.lastResult = null;
  if (resume) {
    // 内容版本变了 savedTourStep 会返回 null（见 store.js），不会拿旧步数硬接
    const saved = savedTourStep(id);
    if (saved !== null && saved > 0 && saved < t.steps.length) {
      state.index = saved;
      state.visited = [saved];
    }
  }
  saveTourStep(id, state.index);
  return true;
}

export function goto(i) {
  if (!state.active) return;
  const n = stepCount.value;
  if (i < 0 || i >= n) return;
  state.index = i;
  if (!state.visited.includes(i)) state.visited.push(i);
  saveTourStep(state.tutorialId, i);
}

export function next() {
  if (!state.active) return;
  if (isLast.value) { finish(); return; }
  goto(state.index + 1);
}

export function prev() {
  if (!state.active) return;
  goto(state.index - 1);
}

export function pause() {
  if (!state.active) return;
  state.paused = true;
}

export function resume() {
  if (!state.active) return;
  state.paused = false;
}

export function togglePause() {
  state.paused ? resume() : pause();
}

/** 标记当前步缺目标（由遮罩在定位失败时调用） */
export function noteMissing(i) {
  if (!state.missing.includes(i)) state.missing.push(i);
}

/**
 * 结束引导。
 * @param {"finish"|"abandon"} how
 *   finish   — 用户走完了（或点了"完成"）：只在**确实到过最后一步**时标记已学；
 *   abandon  — 跳过/放弃：不标记已学，清掉"接着上次"的步数。
 */
export function end(how = "abandon") {
  const id = state.tutorialId;
  const reachedEnd = state.visited.includes(stepCount.value - 1);
  let marked = false;
  if (how === "finish") {
    // 关键修正：v1 是"空转也标完成"。这里要求真的到过最后一步。
    if (reachedEnd && id) {
      markCompleted(id);
      marked = true;
    } else if (id) {
      markIncomplete(id);
      saveTourStep(id, state.index); // 保留进度，用户可以回来接着走
    }
  } else if (id) {
    clearTourStep(id);
  }
  state.lastResult = {
    id,
    how,
    marked,
    reachedEnd,
    missing: state.missing.slice(),
    visitedCount: state.visited.length,
    total: stepCount.value,
  };
  state.active = false;
  state.paused = false;
  return state.lastResult;
}

export function finish() { return end("finish"); }
export function skip() { return end("abandon"); }

export function clearResult() { state.lastResult = null; }
