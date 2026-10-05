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
  // 教程里绘图示例写的是"复数着色"（旧版说法），落到复平面页
  ["复数着色", "/plot/complex"],
  ["向量场", "/plot/vector"],
  ["任意做图", "/plot/geometry"],
  ["几何", "/plot/geometry"],
  ["分形", "/plot/fractal"],
  ["3D", "/plot/3d"],
  ["2D", "/plot/2d"],
  ["绘图", "/plot/2d"],
  // 设置面板**已经实现**（8 个分组、搜索可跳到具体项），示例里指向它的模式
  // 现在能直接跳过去。之前这里挂着"设置面板尚未实现（方案 P1）"，那句理由早已过期。
  // 「配置 DeepSeek API」这类示例落在 AI 分组最贴近（设置页会自己滚/切到该分组）。
  ["设置", "/settings?group=ai"],
  // 联网搜索现在有**真实页面**（/tools/search），示例里的这个模式能落过去了：
  // SearchView 会读 ?q= 直接开搜，所以"什么是黎曼猜想"这种示例是"点开就在搜"。
  ["联网搜索", "/tools/search"],
  ["搜索", "/tools/search"],
];

/**
 * 无法用**路由**表达的模式：功能已实现，但它不是"一个页面"。
 *
 * ⚠ 这里原先写的是一句**假话** —— `["AI", "AI 助手尚未实现（方案 P3）"]`。
 *   AI 助手早已实现（端到端 tests/cdp-ai.mjs 127/0），只是它是顶栏的**抽屉**而不是页面，
 *   所以 `routeForMode` 无法把它表达成一条 route。用户当时点示例会看到"尚未实现"。
 *   现在按真实原因说，并给出可执行的动作。
 */
const NOT_ROUTABLE = [
  ["AI", "AI 助手是顶栏的抽屉、不是独立页面：请点顶栏的「AI」把它打开"],
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
  const ny = NOT_ROUTABLE.find(([needle]) => m.includes(needle));
  if (ny) return { ok: false, reason: ny[1] };
  return { ok: false, reason: `无法把模式「${m}」对应到现有界面（映射表里没有它）` };
}

/**
 * 操作名 → 真实模式名 的别名表。
 *
 * 教程数据（来自 v1）用的是**旧版界面**的操作名，与 v2.0 页面里的模式名有出入。
 * 不建这张表就会出现"示例说要去算积分、结果跳到解方程"这类错位——
 * 实测的错配正是下面这三条（另加已补进代数页的「因式分解」）。
 */
export const ALIASES = {
  "解线性方程组": "求解方程组",
  "辛普森积分": "辛普森法则",
  "ODE 求解": "ODE数值解",
  "ODE求解": "ODE数值解",
  "常微分方程": "ODE数值解",
  // 旧版把"化简"当作模式名，v2.0 代数页里叫"表达式化简"
  "化简": "表达式化简",
};

/**
 * 全局模式索引：模式名 → 所在页面路由。
 *
 * 为什么必须有它：教程示例里的 `mode` 字段是**计算分类**（"代数"、"数值分析"），
 * 而 `action` 才是具体操作（"不定积分"、"辛普森积分"）。原实现只按分类决定页面，
 * 于是「不定积分」被送到代数页；代数页没有这个模式 → 匹配失败 →
 * 模式停留在该页默认值（恰好是「解方程/组」）→ 用户点计算，
 * 引擎收到的是 solve_sym 而不是 integrate，报出"方程含超越函数"。
 * 正确做法：**先用操作名反查它属于哪个页面**，分类只作兜底。
 */
let modeHomeIndex = null;
let modeHomeLoading = null;

/** 查某操作名所属的页面路由；索引未就绪时返回 null（调用方先 await ensureModeIndex()） */
export function modeHome(operation) {
  if (!operation) return null;
  const name = ALIASES[operation] || operation;
  if (!modeHomeIndex) return null;
  return modeHomeIndex.get(name) || null;
}

/** 构建模式索引（动态 import 只为避开 pendingInput ↔ viewConfigs 的循环依赖） */
export async function ensureModeIndex() {
  if (modeHomeIndex) return modeHomeIndex;
  if (modeHomeLoading) return modeHomeLoading;
  modeHomeLoading = (async () => {
    const { getViewConfig } = await import("../engine/viewConfigs.js");
    const CALC_ROUTES = [
      "algebra", "calculus", "analytic-geometry", "sequences", "linear-algebra", "probability",
      "numerical", "number-theory", "real-analysis", "functional-analysis", "complex-analysis",
      "algebraic-topology", "measure-theory",
    ];
    const idx = new Map();
    for (const k of CALC_ROUTES) {
      const cfg = getViewConfig(k) || { modes: [] };
      for (const m of cfg.modes || []) if (!idx.has(m)) idx.set(m, `/calc/${k}`);
    }
    modeHomeIndex = idx;
    return idx;
  })();
  return modeHomeLoading;
}

/** 供工具/测试注入索引 */
export function __setModeIndex(map) {
  modeHomeIndex = map instanceof Map ? map : new Map(Object.entries(map || {}));
}

/**
 * 把一个示例解析成"跳哪、选哪个模式"。
 * @returns {{ok:true, route:string, mode:string|null, via:string} | {ok:false, reason:string}}
 */
export function resolveExample({ mode, operation } = {}) {
  const opRaw = String(operation || "").trim();
  const op = opRaw ? (ALIASES[opRaw] || opRaw) : "";
  if (op && modeHomeIndex) {
    const home = modeHome(op);
    if (home) return { ok: true, route: home, mode: op, via: "operation" };
    // 有具体操作但任何页面都没有这个模式：**不能**退回按分类乱跳，
    // 否则用户会落到不相干的页面、还带着一个不相干的默认模式（正是这次的 bug）。
    return { ok: false, reason: `操作「${opRaw}」在当前界面里没有对应模式` };
  }
  const info = routeForMode(mode);
  if (info.ok) return { ok: true, route: info.route, mode: null, via: "category" };
  return { ok: false, reason: info.reason || "无法定位到目标界面" };
}

/**
 * 操作名 → 目标视图里的模式名。
 * 先按别名表归一，再做包含匹配；**匹配不到时返回 null 让调用方说明**，
 * 而不是像 v1 那样静默忽略（那正是"跳到解方程"这类错位的根源）。
 */
export function pickMode(operation, availableModes) {
  const opRaw = String(operation || "").trim();
  if (!opRaw) return null;
  const op = ALIASES[opRaw] || opRaw;
  const list = Array.isArray(availableModes) ? availableModes : [];
  if (list.includes(op)) return op;
  return list.find((x) => x.includes(op) || op.includes(x)) || null;
}
