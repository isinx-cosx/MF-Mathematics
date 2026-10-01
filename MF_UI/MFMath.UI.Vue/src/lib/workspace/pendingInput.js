/**
 * pendingInput.js — 把一个表达式"带到"目标界面去
 *
 * 用途：示例库里点「加载到工作区」时，需要跨路由把表达式 + 操作名交给计算/绘图视图。
 * v1 的做法是 `MainWindow.load_tutorial_example()` 里直接抓控件 `setText`，
 * 而它的 mode→子模式映射**只覆盖了 14 个计算子模式里的 4 个**，像 `mode: "2D 绘图"`
 * 这种匹配不到就**静默不切换**，示例的语义直接丢掉。
 * 这里给一张完整映射表；匹配不到时返回理由，由界面明确说明，不装成功。
 */
import { ref } from "vue";

const pending = ref(null);

export function setPending(p) {
  pending.value = p ? { ...p } : null;
}

export function peekPending() {
  return pending.value;
}

/** 取一次即清空：避免下次进入同一视图时被旧示例反复覆盖 */
export function takePending() {
  const v = pending.value;
  pending.value = null;
  return v;
}

/** mode 文本 → 路由。按关键词长度降序匹配，避免"代数"抢先命中"代数拓扑"。 */
const MODE_ROUTES = [
  ["代数拓扑", "/calc/algebraic-topology"],
  ["解析几何", "/calc/analytic-geometry"],
  ["泛函分析", "/calc/functional-analysis"],
  ["复分析", "/calc/complex-analysis"],
  ["测度论", "/calc/measure-theory"],
  ["实分析", "/calc/real-analysis"],
  ["数值", "/calc/numerical"],
  ["数论", "/calc/number-theory"],
  ["数列", "/calc/sequences"],
  ["线性代数", "/calc/linear-algebra"],
  ["微积分", "/calc/calculus"],
  ["概率", "/calc/probability"],
  ["代数", "/calc/algebra"],
  ["极坐标", "/plot/polar"],
  ["复平面", "/plot/complex"],
  ["向量场", "/plot/vector"],
  ["任意做图", "/plot/geometry"],
  ["几何", "/plot/geometry"],
  ["分形", "/plot/fractal"],
  ["3D", "/plot/3d"],
  ["2D", "/plot/2d"],
  ["绘图", "/plot/2d"],
];

/** 目前尚未实现、因而无法接收示例的功能 */
const NOT_YET = [
  ["联网搜索", "在线搜索面板尚未实现（方案 P1）"],
  ["搜索", "在线搜索面板尚未实现（方案 P1）"],
  ["设置", "设置面板尚未实现（方案 P1）"],
  ["AI", "AI 助手尚未实现（方案 P3）"],
];

const SORTED = [...MODE_ROUTES].sort((a, b) => b[0].length - a[0].length);

/**
 * @returns {{ok:true, route:string, matched:string} | {ok:false, reason:string}}
 */
export function routeForMode(mode) {
  const m = String(mode || "").trim();
  if (!m) return { ok: false, reason: "该示例没有指定模式" };
  const hit = SORTED.find(([needle]) => m.includes(needle));
  if (hit) return { ok: true, route: hit[1], matched: hit[0] };
  const ny = NOT_YET.find(([needle]) => m.includes(needle));
  if (ny) return { ok: false, reason: ny[1] };
  return { ok: false, reason: `无法把模式「${m}」对应到现有界面（映射表里没有它）` };
}

/**
 * 操作名 → 目标视图里的模式名。
 * v1 是 `calc_mode_combo` 里找 itemText 包含该串的项；这里做同样的包含匹配，
 * 但**匹配不到时返回 null 让调用方说明**，而不是像 v1 那样静默忽略。
 */
export function pickMode(operation, availableModes) {
  const op = String(operation || "").trim();
  if (!op) return null;
  const list = Array.isArray(availableModes) ? availableModes : [];
  if (list.includes(op)) return op;
  return list.find((x) => x.includes(op) || op.includes(x)) || null;
}
