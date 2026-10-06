<script setup>
/**
 * PlotView — Desmos 式绘图器
 * 左：表达式列表（Desmos 式）+ 参数滑块
 * 右：画布 + 视图控制（Zoom In/Out / Fit / 重置）
 * 计算：全部经 C++ 引擎（expr_eval_vars_batch 带参数采样、solve/extrema 做精确标注）
 */
import { ref, computed, watch, onMounted, onBeforeUnmount } from "vue";
import { useRoute } from "vue-router";
import ExpressionList from "../../components/plot/ExpressionList.vue";
import ParamSlider from "../../components/plot/ParamSlider.vue";
import PlotCanvas from "../../components/plot/PlotCanvas.vue";
import MathLatex from "../../components/math/MathLatex.vue";
import { colorAt } from "../../lib/plot/colors.js";
import { textLatex } from "../../lib/engine/resultModel.js";
import { parseExpr, validate } from "../../lib/plot/plotMath.js";
import { defaultView, fitBounds, viewW, viewH, mapX, mapY } from "../../lib/plot/view.js";
import { adaptiveSample } from "../../lib/plot/sampling.js";
import { engineCall, isHosted } from "../../lib/bridge.js";
import { getPage, setPage } from "../../lib/workspace/store.js";
import { exportCanvas } from "../../lib/plot/exportImage.js";

/* ── 状态 ── */
let nextId = 1;
/**
 * 工作区还原：绘图页要存的是"你在画什么"——表达式（含颜色/可见性）、视图范围、
 * 网格与极坐标开关、参数滑块的值。求出来的曲线/交点不存（那是结果，能重算）。
 * 还原发生在**初始化时**，之后由 watch 回写；挂载前不回写，否则默认值会盖掉还原内容。
 *
 * 注意 route 必须在**用到它之前**声明：之前把 useRoute() 留在下面几十行，
 * 这里先用 route.path 会命中 TDZ（`Cannot access 'route' before initialization`），
 * 整个 PlotView 直接挂不起来——一个空白的绘图页，而且只在控制台里留一行报错。
 */
const route = useRoute();
const savedPage = getPage(route.path);
const restoredPlot = savedPage && savedPage.kind === "plot" ? savedPage : null;
const expressions = ref(
  restoredPlot?.expressions?.length
    ? restoredPlot.expressions.map((e, i) => ({
        id: i + 1,
        text: String(e.text ?? ""),
        color: e.color || colorAt(i),
        visible: e.visible !== false,
        error: null,
      }))
    : [{ id: nextId++, text: "y=x^2", color: colorAt(0), visible: true, error: null }]
);
// ⚠ 还原之后必须把 nextId 推到**下一个空 id**。
//
// 原实现写的是 `id: (nextId = i + 1)`：还原 N 行之后 nextId 停在 **N**（最后用掉的那个 id），
// 而 addRow 用的是 `nextId++` —— 新行于是拿到 id = N，**与第 N 行撞车**。
//
// 后果（实测，不是推测）：列表里出现两条**同 id** 的行 ——
//   · 它们永远显示同一个值（`v-for` 两条记录渲染同一个 row.text）；
//   · 写任意一行会改到所有行（`update(id, patch)` 同时命中两条）；
//   · 删一行会一次删掉两条（`removeRow(id)` 按 id 过滤）。
// 触发条件很常见：**这个页面存过工作区 → 页面重挂载时还原 → 点一次「＋ 添加表达式」**。
// （套件里正好由 cdp-plot-verify 留下一行触发，于是后面 6 条绘图用例全部读到
//  「引擎采样 0 条曲线」——整片假失败的根因就是这里，不在测试脚本。）
if (restoredPlot?.expressions?.length) nextId = restoredPlot.expressions.length + 1;
const activeId = ref(expressions.value[0].id);
const view = ref(restoredPlot?.view || defaultView(1, 1));
const params = ref(restoredPlot?.params && typeof restoredPlot.params === "object" ? { ...restoredPlot.params } : {});
const samples = ref({});
const gridsRef = ref({});        // 二元网格（隐式方程 / 区域）
const statusText = ref(restoredPlot ? "已从工作区还原" : "就绪");
const hosted = isHosted();
const canvasRef = ref(null);
let colorIdx = expressions.value.length;
let syncWorkspace = false;

/* ── 可拖动点（Desmos：点击曲线创建，可沿曲线拖动）── */
const points = ref([]);          // [{id, curveId, x, y, color}]
let pointId = 1;
const showIntersections = ref(false);
const intersectionList = ref([]); // [{x, y, xLabel, yLabel, exact}]
// 引擎给出的实根性结论（可能恒定，也可能依赖参数取值）——原样展示，不做二次解读
const intersectionNotice = ref("");
/** 网格模式与显示（Desmos：投影模式 / 网格开关）*/
// 初值取自路由 meta：原版「极坐标」是独立入口，进来就该是极坐标网格。
// 光有初值还不够——/plot/2d 与 /plot/polar 用的是**同一个组件**，vue-router 会复用
// 实例（setup 不会再跑），所以必须再 watch 一次 meta，否则从 2D 切到极坐标时
// 网格模式还留在 rect（实测就是这么发现的：两条路由的按钮标题一模一样）。
// 网格模式可还原：保存过就用保存的，否则按路由 meta 的初值
const gridMode = ref(restoredPlot?.gridMode === "polar" ? "polar" : (route.meta?.grid === "polar" ? "polar" : "rect"));   // rect | polar
watch(() => route.meta?.grid, (g) => { gridMode.value = g === "polar" ? "polar" : "rect"; });
const showGrid = ref(restoredPlot?.showGrid !== false);

/* 采样由 lib/plot/sampling.js 的自适应算法负责（高曲率处自动加密） */

/* ── 解析后的曲线 ── */
const curves = computed(() =>
  expressions.value.map((row) => {
    const parsed = parseExpr(row.text);
    return { id: row.id, parsed, color: row.color, visible: row.visible, emphasis: row.id === activeId.value };
  })
);

/* ── 参数收集：所有表达式里出现过的自由符号 → 滑块 ── */
const paramNames = computed(() => {
  const set = new Set();
  for (const c of curves.value) {
    for (const p of c.parsed.params || []) set.add(p);
  }
  return [...set].sort();
});

/** 新增参数时给默认值（对齐 Desmos：默认 1），并初始化滑块配置 */
const paramConfig = ref({});   // {a: {min, max, step}}
const DEFAULT_CFG = { min: -10, max: 10, step: 0.1 };

watch(paramNames, (names) => {
  const next = { ...params.value };
  const nextCfg = { ...paramConfig.value };
  let changed = false;
  for (const n of names) {
    if (!(n in next)) { next[n] = 1; changed = true; }
    if (!(n in nextCfg)) { nextCfg[n] = { ...DEFAULT_CFG }; changed = true; }
  }
  for (const k of Object.keys(next)) {
    if (!names.includes(k)) { delete next[k]; changed = true; }
  }
  for (const k of Object.keys(nextCfg)) {
    if (!names.includes(k)) { delete nextCfg[k]; changed = true; }
  }
  if (changed) { params.value = next; paramConfig.value = nextCfg; }
}, { immediate: true });

/** 滑块设置更新（最小值/最大值/步长），并把当前值钳制到新区间 */
function updateParamConfig(name, cfg) {
  const min = Math.min(cfg.min, cfg.max - 1e-9);
  const max = Math.max(cfg.max, min + 1e-9);
  paramConfig.value = { ...paramConfig.value, [name]: { min, max, step: cfg.step } };
  const v = params.value[name];
  if (typeof v === "number") {
    const clamped = Math.min(Math.max(v, min), max);
    if (clamped !== v) params.value = { ...params.value, [name]: clamped };
  }
}

/* ── 采样：引擎表达式求值（带参数）+ 自适应加密 ── */
function linspace(a, b, n) {
  const out = new Array(n);
  for (let i = 0; i < n; i++) out[i] = a + ((b - a) * i) / (n - 1);
  return out;
}

/** 一次批量求值（引擎），返回数值数组或 null */
function evalBatch(expr, varName, ts) {
  const r = engineCall("expr_eval_vars_batch", { expr, var: varName, xs: ts, vars: params.value });
  if (!r || r.isError || !Array.isArray(r.value) || r.value.length !== ts.length) return null;
  return r.value;
}

/**
 * 采样点 → 世界坐标点，**非有限值一律留 null 表示"这里断开"**。
 *
 * 引擎对域外点（ln x 在 x≤0、1/x 在 x=0）返回 null，算出 ±∞ 时也可能给 null；
 * 而 `Number(null) === 0`、`isFinite(null) === true` —— 直接塞进坐标换算会变成
 * 一个 y=0 的假点，把断点处连成一条不该存在的线（实测 e^x−ln x 就是这种情况）。
 */
function pt(x, y) {
  return Number.isFinite(x) && Number.isFinite(y) ? [x, y] : null;
}

function sampleAll() {
  if (!hosted) { statusText.value = "浏览器预览：无引擎桥，曲线不绘制"; return; }
  const v = view.value;
  const { w: cw, h: ch } = canvasRef.value?.canvasSize() ?? { w: 0, h: 0 };
  // 采样范围取视图的 1.5 倍（左右各外扩 25%）：小幅平移时曲线不断裂
  const padX = viewW(v) * 0.25, padY = viewH(v) * 0.25;
  const sx0 = v.x0 - padX, sx1 = v.x1 + padX;
  const sy0 = v.y0 - padY, sy1 = v.y1 + padY;

  // 世界坐标 → 屏幕（自适应采样的偏差判据用屏幕像素）
  // 画布尚未就绪时用兜底尺寸，保证映射始终有限（否则偏差判据失效）
  const useW = cw > 0 ? cw : 800;
  const useH = ch > 0 ? ch : 600;
  const toScreen = ([x, y]) => [
    ((x - v.x0) / (v.x1 - v.x0)) * useW,
    ((v.y1 - y) / (v.y1 - v.y0)) * useH,
  ];

  const next = {};
  let okCount = 0, errCount = 0, totalPts = 0;

  for (const row of expressions.value) {
    const p = parseExpr(row.text);
    if (!p.valid || !row.text.trim()) continue;

    if (p.type === "point") {
      const m = row.text.trim().match(/^\(\s*([^,]+?)\s*,\s*([^,]+?)\s*\)$/);
      if (m) {
        // 幂统一用 ^：引擎的归一化会把 ** 也并成 ^，界面不做算符替换
        const xr = engineCall("expr_eval_vars", { expr: m[1], vars: params.value });
        const yr = engineCall("expr_eval_vars", { expr: m[2], vars: params.value });
        if (xr && !xr.isError && yr && !yr.isError) {
          next[row.id] = [[xr.value, yr.value]];
          row.error = null;
          okCount++;
        } else {
          // 点的坐标必须是确定的数：出现自变量（如写 (x, 2)）或缺参数时，
          // 引擎会明确报错而不是按 0 代入。把原因显示在输入框上，
          // 否则这个点会"凭空消失"，用户不知道哪里写错了。
          const msg = (xr && xr.isError) ? xr.value : (yr && yr.isError ? yr.value : "无法求值");
          row.error = String(msg);
          errCount++;
        }
      }
      continue;
    }
    if (p.type === "implicit" || p.type === "region") continue;   // 走二元网格路径（sampleGrids）

    // 每种类型：批量求值闭包 + 参数范围 + 世界坐标映射
    let evalPoints = null, t0 = 0, t1 = 1;
    if (p.type === "explicit") {
      t0 = sx0; t1 = sx1;
      evalPoints = (ts) => {
        const ys = evalBatch(p.body, "x", ts);
        return ys ? ts.map((t, i) => pt(t, ys[i])) : null;
      };
    } else if (p.type === "vertical") {
      t0 = sy0; t1 = sy1;
      evalPoints = (ts) => {
        const xs = evalBatch(p.body, "y", ts);
        return xs ? ts.map((t, i) => pt(xs[i], t)) : null;
      };
    } else if (p.type === "polar") {
      t0 = 0; t1 = Math.PI * 2;
      evalPoints = (ts) => {
        const rs = evalBatch(p.radius, "theta", ts);
        return rs ? ts.map((t, i) => pt(rs[i] * Math.cos(t), rs[i] * Math.sin(t))) : null;
      };
    } else if (p.type === "parametric") {
      t0 = 0; t1 = Math.PI * 2;
      evalPoints = (ts) => {
        const xs = evalBatch(p.xsExpr, "t", ts);
        const ys = evalBatch(p.ysExpr, "t", ts);
        return xs && ys ? ts.map((t, i) => pt(xs[i], ys[i])) : null;
      };
    }
    if (p.type === "inequality") {
      // 不等式：采样边界曲线（y ≷ f(x) 按 x 扫描；x ≷ g(y) 按 y 扫描）
      const isY = p.axis === "y";
      const a0 = isY ? sx0 : sy0, a1 = isY ? sx1 : sy1;
      evalPoints = (ts) => {
        const vals = evalBatch(p.boundary, isY ? "x" : "y", ts);
        return vals ? ts.map((t, i) => (isY ? pt(t, vals[i]) : pt(vals[i], t))) : null;
      };
      t0 = a0; t1 = a1;
    }
    if (!evalPoints) continue;

    // 自适应采样：初始 300 点，按屏幕偏差加密最多 3 轮
    const pts = adaptiveSample(evalPoints, t0, t1, toScreen, {
      initial: 300, maxRounds: 3, tolPx: 0.8, maxPoints: 6000,
    });
    if (pts && pts.length >= 2) {
      next[row.id] = pts;
      totalPts += pts.length;
      okCount++;
    } else if (pts && pts.length === 0) {
      errCount++;
      const rowRef = expressions.value.find((r) => r.id === row.id);
      if (rowRef && !rowRef.error) rowRef.error = "引擎未返回有效采样点";
    } else {
      errCount++;
      const rowRef = expressions.value.find((r) => r.id === row.id);
      if (rowRef && !rowRef.error) rowRef.error = "表达式无法求值（检查定义域或语法）";
    }
  }

  samples.value = next;
  // 二元网格（隐式方程 / 二元区域）与一元曲线分开采样
  sampleGrids();

  const v0 = view.value;
  const rangeTxt = `范围 [${v0.x0.toFixed(2)}, ${v0.x1.toFixed(2)}] × [${v0.y0.toFixed(2)}, ${v0.y1.toFixed(2)}]`;
  statusText.value = hosted
    ? `引擎采样 ${okCount} 条曲线${errCount ? `，${errCount} 条失败` : ""} · ${totalPts} 点 · ${rangeTxt}`
    : statusText.value;
}

/* ── 二元网格采样：隐式方程等值线 + 二元不等式区域 ── */
const GRID_N = 180;   // 每轴网格数（180×180 = 32400 点，一次引擎调用）
function sampleGrids() {
  const grids = {};
  if (!hosted) { gridsRef.value = grids; return; }
  const v = view.value;
  for (const row of expressions.value) {
    const p = parseExpr(row.text);
    if (!p.valid || !row.text.trim()) continue;
    if (p.type !== "implicit" && p.type !== "region") continue;
    const xs = linspace(v.x0, v.x1, GRID_N);
    const ys = linspace(v.y0, v.y1, GRID_N);
    const r = engineCall("expr_eval_grid", { expr: p.body, xs, ys, vars: params.value });
    if (r && !r.isError && Array.isArray(r.value) && r.value.length === GRID_N * GRID_N) {
      grids[row.id] = { xs, ys, values: r.value };
    } else {
      const rowRef = expressions.value.find((x) => x.id === row.id);
      if (rowRef && !rowRef.error) {
        rowRef.error = (r && r.isError ? String(r.value) : "二元网格求值失败").slice(0, 80);
      }
    }
  }
  gridsRef.value = grids;
}

/* 采样节流：滚动/拖拽时每帧最多重算一次（视图变换不阻塞交互） */
let sampleRaf = 0;
/** 组件已卸载：已排队的 rAF 不该再跑（那是 180×180 网格 + 每条曲线自适应采样） */
let disposed = false;
function scheduleSample() {
  if (sampleRaf) return;
  sampleRaf = requestAnimationFrame(() => {
    sampleRaf = 0;
    if (disposed) return;
    sampleAll();
  });
}

/* ── 点与探索（对齐 Desmos）─────────────────────────────────────────────── */

/** 曲线在给定自变量取值处的函数值（引擎求值，带参数） */
function curveValueAt(curve, t) {
  const p = curve.parsed;
  if (!p || !p.valid) return null;
  if (p.type === "explicit") {
    const r = engineCall("expr_eval_vars", { expr: p.body, var: "x", x: t, vars: params.value });
    return r && !r.isError ? r.value : null;
  }
  if (p.type === "vertical") {
    const r = engineCall("expr_eval_vars", { expr: p.body, var: "y", x: t, vars: params.value });
    return r && !r.isError ? r.value : null;   // 返回 x = f(y)
  }
  return null;
}

/** 数值标签美化：3.0 → 3；1.41421356 → 1.4142 */
function prettyNum(s) {
  const t = String(s ?? "");
  if (/^-?\d+(\.\d+)?$/.test(t)) {
    const v = Number(t);
    if (Number.isInteger(v)) return String(v);
    return String(Math.round(v * 1e4) / 1e4);
  }
  return t;   // 符号形式（如 sqrt(a)）原样保留
}

/** 参数分支的极值类型 → 中文标签 */
function branchLabel(kind) {
  switch (kind) {
    case "maximum": return "极大值";
    case "minimum": return "极小值";
    case "degenerate": return "退化(二阶导为0)";
    case "no-real-value": return "无实驻点";
    // 定义域相关的结论：导数零点存在不代表它是极值点
    case "no-critical-point": return "无极值点";
    case "outside-domain": return "无极值点(驻点在定义域外)";
    // 求解器给出的驻点未通过 f'=0 残差复核 → 不能据此判定极值
    case "solver-unreliable": return "结果不可信(驻点不满足 f′=0)";
    // 该参数区间内结论本身不唯一（如 a<0 中 -1<a<0 与 a≤-1 不同）
    case "conditional-within-branch": return "该参数范围内不唯一";
    default: return "不确定";
  }
}

/** 分支结论对应的样式类（共用 maximum/minimum/na 三档）。 */
function branchClass(kind) {
  if (kind === "maximum") return "max";
  if (kind === "minimum") return "min";
  return "na";
}

/** 点击曲线 → 创建可拖点（Desmos 行为：只在意点击处最近的曲线上生成） */
function handlePickPoint({ world, screen }) {
  const { w, h } = canvasRef.value?.canvasSize() ?? { w: 0, h: 0 };
  if (!w || !h) return;
  const [wx, wy] = world;
  let best = null, bestDist = 34;   // 屏幕像素阈值
  for (const c of curves.value) {
    if (!c.visible) continue;
    const type = c.parsed?.type;
    if (type !== "explicit" && type !== "vertical") continue;
    let px, py, point;
    if (type === "explicit") {
      const y = curveValueAt(c, wx);
      if (y === null || !isFinite(y)) continue;
      point = { x: wx, y };
    } else {
      const x = curveValueAt(c, wy);
      if (x === null || !isFinite(x)) continue;
      point = { x, y: wy };
    }
    px = mapX(view.value, w, point.x);
    py = mapY(view.value, h, point.y);
    const dist = Math.hypot(px - screen[0], py - screen[1]);
    if (dist < bestDist) { bestDist = dist; best = { curve: c, point }; }
  }
  if (!best) return;
  points.value = [
    ...points.value,
    { id: pointId++, curveId: best.curve.id, x: best.point.x, y: best.point.y, color: best.curve.color },
  ];
  statusText.value = `已创建点 (${prettyNum(best.point.x)}, ${prettyNum(best.point.y)})`;
}

/** 拖动点 → 沿其所属曲线滑动（重算另一坐标） */
function handleDragPoint({ id, world }) {
  const idx = points.value.findIndex((p) => p.id === id);
  if (idx < 0) return;
  const pt = points.value[idx];
  const curve = curves.value.find((c) => c.id === pt.curveId);
  if (!curve) return;
  const type = curve.parsed?.type;
  const [wx, wy] = world;
  let nx = pt.x, ny = pt.y;
  if (type === "explicit") {
    const y = curveValueAt(curve, wx);
    if (y === null || !isFinite(y)) return;
    nx = wx; ny = y;
  } else if (type === "vertical") {
    const x = curveValueAt(curve, wy);
    if (x === null || !isFinite(x)) return;
    nx = x; ny = wy;
  } else return;
  const next = [...points.value];
  next[idx] = { ...pt, x: nx, y: ny };
  points.value = next;
}

function clearPoints() {
  points.value = [];
}

/** 自动求交点（引擎：符号精确解优先，超越方程走数值回退） */
function computeIntersections() {
  intersectionNotice.value = "";
  if (!hosted) { intersectionList.value = []; return; }   // 计算不受"是否画到画布上"影响
  const v = view.value;
  const vis = curves.value.filter((c) => c.visible && c.parsed?.valid && c.parsed.type === "explicit");
  const out = [];
  for (let i = 0; i < vis.length; i++) {
    for (let j = i + 1; j < vis.length; j++) {
      const r = engineCall("intersections", {
        expr1: vis[i].parsed.body,
        expr2: vis[j].parsed.body,
        var: "x",
        vars: params.value,
        xmin: v.x0, xmax: v.x1,
      });
      if (!r || r.isError || !r.value || !Array.isArray(r.value.points)) continue;
      // 实根性依赖参数取值时明确提示：此时交点数会随参数变化，
      // 只按当前参数值画出来的点不能当成"恒成立"的结论。
      if (r.value.realness === "conditional" && r.value.realnessReason) {
        intersectionNotice.value = r.value.delta
          ? `Δ = ${r.value.delta}，符号随参数变化：${r.value.realnessReason}`
          : r.value.realnessReason;
      }
      for (const pt of r.value.points) {
        // 只画能数值化的实轴交点（复数解/未定参数已在引擎侧过滤或标记）
        if (typeof pt.xNum !== "number" || typeof pt.yNum !== "number") continue;
        out.push({
          x: pt.xNum, y: pt.yNum,
          xLabel: prettyNum(pt.x), yLabel: prettyNum(pt.y),
          exact: !!r.value.exact,
          method: r.value.method,
          realness: pt.realness,
        });
      }
    }
  }
  intersectionList.value = out;
}

/* 视图变化 → 重采样（节流）；表达式/参数变化 → 校验 + 重采样 + 重算交点/极值 */
watch([() => view.value.x0, () => view.value.x1, () => view.value.y0, () => view.value.y1], scheduleSample);
watch([expressions, params], () => {
  validateAll();
  scheduleSample();
  computeIntersections();
  computeExtrema();
  computeSymbolicExtrema();
}, { deep: true });

/* ── 极值标注（用引擎的符号能力求精确驻点）── */
const extremaList = ref([]);      // 无参曲线：[{x, y, kind:'max'|'min', curveId}]
const symbolicExtrema = ref([]);  // 含参曲线：extrema_sym 的符号驻点 + 参数分支
// 极值标注**默认关闭**：点必须由用户自己添加，不自动往画布上画（Desmos 的做法）。
// 手动入口是点击曲线（PlotCanvas 的 pick-point）。
const showExtrema = ref(false);

function computeExtrema() {
  if (!hosted) { extremaList.value = []; return; }        // 同上：算出来给侧栏用
  const out = [];
  for (const c of curves.value) {
    if (!c.visible || c.parsed?.type !== "explicit") continue;
    // 含自由参数时极值位置依赖参数（引擎会显式报错），改由 computeSymbolicExtrema 处理
    if ((c.parsed.params || []).length > 0) continue;
    const r = engineCall("local_extrema", { expr: c.parsed.body, var: "x" });
    if (!r || r.isError || !r.value) continue;
    for (const [x, y] of (r.value.maxima || [])) {
      if (isFinite(x) && isFinite(y)) out.push({ x, y, kind: "max", curveId: c.id });
    }
    for (const [x, y] of (r.value.minima || [])) {
      if (isFinite(x) && isFinite(y)) out.push({ x, y, kind: "min", curveId: c.id });
    }
  }
  extremaList.value = out;
}

/** 含参曲线：求符号驻点 + 参数分类讨论（展示在侧栏，不做图上定位） */
function computeSymbolicExtrema() {
  if (!hosted) { symbolicExtrema.value = []; return; }
  const out = [];
  for (const c of curves.value) {
    if (!c.visible || c.parsed?.type !== "explicit") continue;
    if (!(c.parsed.params || []).length) continue;
    const r = engineCall("extrema_sym", { expr: c.parsed.body, var: "x" });
    // 引擎拒绝求解时（超出其符号/数值能力）也要把原因显示出来，
    // 不能静默什么都不显示——那会让人以为"这条曲线没有极值"。
    if (!r) { out.push({ expr: c.parsed.body, color: c.color, error: "引擎无响应" }); continue; }
    if (r.isError) { out.push({ expr: c.parsed.body, color: c.color, error: String(r.value) }); continue; }
    if (!r.value || !Array.isArray(r.value.points)) continue;
    out.push({
      expr: c.parsed.body,
      points: r.value.points,
      params: r.value.params || [],
      color: c.color,
      method: r.value.solveMethod || "symbolic",
      note: r.value.solveNote || "",
      domain: r.value.domain || [],
    });
  }
  symbolicExtrema.value = out;
}

/** 求解手段 → 侧栏徽标文字（精确解与数值近似必须一眼可分）。 */
function methodLabel(m) {
  switch (m) {
    case "symbolic": return "精确";
    case "substitution-sqrt": return "精确(换元 √)";
    case "substitution-tan": return "精确(换元 tan)";
    case "elimination-radical": return "精确(根式消元)";
    case "numeric": return "数值";
    default: return "";
  }
}

/**
 * 侧栏展示用：把「按驻点分组」改成「按参数取值分组」。
 *
 * 引擎返回的结构是 点 → 分支（每个驻点各带一套 a>0/a=0/a<0），
 * 于是 x²−a·ln x 这种两个驻点的情况会摊成 6 行、同一参数情形被拆散。
 * 分类讨论的阅读顺序本来就该是「先看参数在哪一段，再看该段下每个驻点是什么」，
 * 所以这里反过来汇总：一个参数情形一块，块内列出各驻点的结论。
 * 同一驻点在多行重复出现时（如 a=0 时两根重合）按内容去重。
 */
const symbolicGroups = computed(() => {
  const groups = [];
  const byAssume = new Map();
  for (const s of symbolicExtrema.value) {
    for (const p of s.points || []) {
      for (const b of p.branches || []) {
        const key = b.assume || "";
        let g = byAssume.get(key);
        if (!g) { g = { assume: key, rows: [] }; byAssume.set(key, g); groups.push(g); }
        const note = b.note || "";
        const dup = g.rows.some((r) => r.x === p.x && r.kind === b.kind && r.note === note);
        if (!dup) {
          g.rows.push({
            x: p.x,
            kind: b.kind,
            note,
            exists: b.exists,
            fvalue: b.f_value,
            color: s.color,
          });
        }
      }
    }
  }
  return groups;
});

/* ── 行内校验 ── */
function validateAll() {
  for (const row of expressions.value) {
    if (!row.text.trim()) { row.error = null; continue; }
    const basic = validate(row.text);
    row.error = basic;
  }
}

/* ── 表达式列表操作（对齐 Desmos 的 Enter/Backspace 行为）── */
function addRow(afterIndex) {
  const row = { id: nextId++, text: "", color: colorAt(colorIdx++), visible: true, error: null };
  const arr = [...expressions.value];
  arr.splice(afterIndex + 1, 0, row);
  expressions.value = arr;
  activeId.value = row.id;
}

function removeRow(id) {
  if (expressions.value.length <= 1) return;
  const arr = expressions.value.filter((r) => r.id !== id);
  expressions.value = arr;
  const s = { ...samples.value }; delete s[id]; samples.value = s;
  if (activeId.value === id) activeId.value = arr[0]?.id ?? null;
}

/* ── 视图控制（Desmos 右侧浮动按钮）── */
function zoomBy(factor) {
  const { w, h } = canvasRef.value?.canvasSize() ?? { w: 800, h: 600 };
  const v = view.value;
  const cx = (v.x0 + v.x1) / 2, cy = (v.y0 + v.y1) / 2;
  const nw = viewW(v) * factor, nh = viewH(v) * factor;
  view.value = { x0: cx - nw / 2, x1: cx + nw / 2, y0: cy - nh / 2, y1: cy + nh / 2 };
}
function zoomFit() {
  // 只喂"当前视图里看得见"的点：采样范围是视图的 1.5 倍，里面的离群值
  // （e^x 在 x=15 处 y≈3.3e6）会把范围算爆，等比修正再把量级搬到另一轴 ——
  // 实测点「缩放到适应」后 x0 变成 −2.7e6，整条曲线塌成一条线。
  const v = view.value;
  const padX = viewW(v) * 0.02, padY = viewH(v) * 0.02;
  const all = [], inside = [];
  for (const id of Object.keys(samples.value)) {
    const row = expressions.value.find((r) => String(r.id) === String(id));
    if (row && !row.visible) continue;
    for (const p of samples.value[id]) {
      if (!p) continue;
      const [x, y] = p;
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
      all.push(p);
      if (x >= v.x0 - padX && x <= v.x1 + padX && y >= v.y0 - padY && y <= v.y1 + padY) inside.push(p);
    }
  }
  const { w, h } = canvasRef.value?.canvasSize() ?? { w: 800, h: 600 };
  // 视图内的点太少（例如刚进页面就点适应）时退回全部有限点
  const fit = fitBounds(inside.length >= 2 ? inside : all, w, h);
  if (fit) view.value = fit;   // 视图一变，watch 会自动重采样
}
function resetView() {
  const { w, h } = canvasRef.value?.canvasSize() ?? { w: 800, h: 600 };
  view.value = defaultView(w, h);
  sampleAll();
}

/**
 * 导出图片：把画布按 2x 重绘（不透明底）后交给宿主写文件。
 * 结果写进状态栏——"点了没反应"和"导出了但不知道存哪"都要避免。
 */
function exportImage() {
  const el = canvasRef.value?.canvasEl?.();
  const r = exportCanvas(el, { routePath: route.path, note: "2D 函数绘图" });
  statusText.value = r.ok
    ? `已导出图片：${r.path}（${r.width}×${r.height}，${(r.bytes / 1024).toFixed(0)} KB）`
    : (r.canceled ? "已取消导出" : `导出失败：${r.error}`);
}

/** 采集本页要存进工作区的内容：在画什么 + 视野 + 参数值（结果一律不存，能重算） */function capturePlot() {
  return {
    kind: "plot",
    expressions: expressions.value.map((e) => ({ text: e.text, color: e.color, visible: e.visible })),
    view: { ...view.value },
    gridMode: gridMode.value,
    showGrid: showGrid.value,
    params: { ...params.value },
  };
}

/** 首帧初始化用的 rAF 句柄（卸载时要能取消） */
let bootRaf = 0;

onMounted(() => {
  // 等首次布局完成后再按画布宽高比初始化视图
  bootRaf = requestAnimationFrame(() => {
    bootRaf = 0;
    if (disposed) return;   // 挂载后立即卸载：整轮首帧采样/求交都不必跑
    const { w, h } = canvasRef.value?.canvasSize() ?? { w: 0, h: 0 };
    // **还原过视野就不要再按画布比例重置**，否则用户存下来的范围会被冲掉
    if (w > 0 && h > 0 && !restoredPlot?.view) view.value = defaultView(w, h);
    sampleAll();
    computeIntersections();
    computeExtrema();
    computeSymbolicExtrema();
  });
  syncWorkspace = true;   // 挂载完成，之后的变化才写回工作区
});

// 本视图自己不挂 window 监听、也不建 ResizeObserver（那些都在子画布组件里，已各自收尾），
// 唯一需要在这里收尾的是**已排队的 rAF**：不取消的话，卸载后它仍会跑一整轮
// 采样与求交（180×180 网格 × 每条曲线），白白过桥若干次，还写已销毁组件的状态。
onBeforeUnmount(() => {
  disposed = true;
  if (bootRaf) { cancelAnimationFrame(bootRaf); bootRaf = 0; }
  if (sampleRaf) { cancelAnimationFrame(sampleRaf); sampleRaf = 0; }
});

watch([expressions, view, gridMode, showGrid, params], () => {
  if (syncWorkspace) setPage(route.path, capturePlot());
}, { deep: true });
</script>

<template>
  <div class="desmos-layout">
    <!-- 左侧：表达式列表 + 参数滑块（Desmos 左栏）-->
    <aside class="desmos-side">
      <ExpressionList
        v-model="expressions"
        v-model:activeId="activeId"
        @add="addRow"
        @remove="removeRow"
        @change="validateAll"
      />

      <div v-if="paramNames.length" class="slider-box">
        <div class="slider-title">参数</div>
        <ParamSlider
          v-for="n in paramNames"
          :key="n"
          :name="n"
          :value="params[n] ?? 1"
          :min="paramConfig[n]?.min ?? -10"
          :max="paramConfig[n]?.max ?? 10"
          :step="paramConfig[n]?.step ?? 0.1"
          @update:value="(val) => (params = { ...params, [n]: val })"
          @update:config="(cfg) => updateParamConfig(n, cfg)"
        />
      </div>

      <!-- 交点列表（Desmos：自动标记两曲线交点；本实现精确解优先）-->
      <div v-if="intersectionList.length" id="ixList" class="slider-box">
        <div class="slider-title">
          交点
          <span class="pt-count">{{ intersectionList.length }}</span>
        </div>
        <div v-for="(it, i) in intersectionList" :key="i" class="pt-row">
          <span class="pt-dot" />
          <span class="pt-text">({{ it.xLabel }}, {{ it.yLabel }})</span>
          <span class="pt-badge" :class="it.exact ? 'exact' : 'num'">
            {{ it.exact ? "精确" : "数值" }}
          </span>
        </div>
        <!-- 含参时实根性可能依赖参数取值：显式说明，不静默当作固定交点数 -->
        <div v-if="intersectionNotice" class="ix-note">{{ intersectionNotice }}</div>
      </div>

      <!-- 已创建的点 -->
      <div v-if="points.length" id="ptList" class="slider-box">
        <div class="slider-title">
          点
          <button class="link-btn" @click="clearPoints">全部清除</button>
        </div>
        <div v-for="p in points" :key="p.id" class="pt-row">
          <span class="pt-dot hollow" :style="{ borderColor: p.color }" />
          <span class="pt-text">({{ prettyNum(p.x) }}, {{ prettyNum(p.y) }})</span>
        </div>
      </div>

      <!-- 极值（引擎符号求解：精确驻点 + 参数分类讨论）-->
      <div v-if="extremaList.length || symbolicExtrema.length" id="extList" class="slider-box">
        <div class="slider-title">
          极值
          <span class="pt-count">{{ extremaList.length }}</span>
        </div>
        <div v-for="(e, i) in extremaList" :key="'e' + i" class="pt-row">
          <span class="pt-dot diamond" :class="e.kind === 'max' ? 'max' : 'min'" />
          <span class="pt-text">{{ e.kind === "max" ? "极大" : "极小" }} ({{ prettyNum(e.x) }}, {{ prettyNum(e.y) }})</span>
          <span class="pt-badge exact">精确</span>
        </div>
        <!-- 引擎无法求解时把原因显示出来，而不是静默什么都不显示 -->
        <div v-for="(s, si) in symbolicExtrema" :key="'se' + si">
          <div v-if="s.error" class="pt-sym">
            <div class="branch-note">该曲线暂无法分析极值：{{ s.error }}</div>
          </div>
          <div v-else-if="s.note" class="pt-sym">
            <div class="branch-note">{{ s.note }}</div>
          </div>
        </div>
        <!-- 含参曲线：按**参数取值**分组（先看参数在哪一段，再看该段下各驻点） -->
        <div v-for="(g, gi) in symbolicGroups" :key="'g' + gi" class="pt-sym">
          <div class="branch-head">
            <span class="branch-tag strong">{{ g.assume }}</span>
          </div>
          <div v-for="(r, ri) in g.rows" :key="'r' + ri" class="pt-branch">
            <!-- 驻点是符号解（-sqrt(a)、a/2…）：用 KaTeX 排版，而不是 ASCII 原样显示 -->
            <span class="branch-x">x = <MathLatex :latex="textLatex(r.x)" :fallback="r.x" /></span>
            <span class="branch-kind" :class="branchClass(r.kind)">
              {{ branchLabel(r.kind) }}
            </span>
            <!-- 驻点不存在/在定义域外/结论不唯一时说明原因；f_value 才是极值本身 -->
            <span v-if="r.exists !== true" class="branch-note">{{ r.note }}</span>
            <span v-else-if="r.fvalue && r.fvalue !== '—'" class="branch-value">
              f = <MathLatex :latex="textLatex(r.fvalue)" :fallback="r.fvalue" />
            </span>
          </div>
        </div>
      </div>

      <div class="side-status">{{ statusText }}</div>
    </aside>

    <!-- 右侧：画布 + 浮动视图控制（Desmos 右上角按钮）-->
    <div class="desmos-main">
      <PlotCanvas
        ref="canvasRef"
        data-tour="plot_canvas"
        v-model="view"
        :curves="curves"
        :params="params"
        :samples="samples"
        :grids="gridsRef"
        :points="points"
        :intersections="showIntersections ? intersectionList : []"
        :extrema="showExtrema ? extremaList : []"
        :grid-mode="gridMode"
        :show-grid="showGrid"
        @pick-point="handlePickPoint"
        @drag-point="handleDragPoint"
      />
      <div class="view-controls">
        <button class="vc-btn" title="放大" @click="zoomBy(0.7)">＋</button>
        <button class="vc-btn" title="缩小" @click="zoomBy(1.4)">－</button>
        <button class="vc-btn" title="缩放到适应" @click="zoomFit">⤢</button>
        <button class="vc-btn" title="重置视图" @click="resetView">⟲</button>
        <button class="vc-btn" data-tour="plot.export_button" title="导出图片（PNG，2 倍像素）" @click="exportImage">⤓</button>
        <button
          class="vc-btn"
          :class="{ on: gridMode === 'polar' }"
          :title="gridMode === 'polar' ? '切换为直角网格' : '切换为极坐标网格'"
          @click="gridMode = gridMode === 'polar' ? 'rect' : 'polar'"
        >◉</button>
        <button
          class="vc-btn"
          :class="{ on: !showGrid }"
          :title="showGrid ? '隐藏网格' : '显示网格'"
          @click="showGrid = !showGrid"
        >▦</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.desmos-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  height: 100%;
  min-height: 520px;
}
.desmos-side {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px;
  border-right: 1px solid var(--border);
  background: var(--surface-alt);
  overflow-y: auto;
}
.slider-box {
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
}
.slider-title {
  font-size: 11.5px;
  color: var(--text-subtle);
  margin-bottom: 4px;
}
.side-status {
  margin-top: auto;
  font-size: 11.5px;
  color: var(--text-subtle);
}
.desmos-main { position: relative; min-width: 0; }
.view-controls {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.vc-btn {
  width: 32px; height: 32px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--glass);
  backdrop-filter: blur(8px);
  color: var(--text);
  font-size: 15px;
  cursor: pointer;
  transition: background .12s, border-color .12s;
}
.vc-btn:hover { background: var(--surface); border-color: var(--accent); color: var(--accent); }
.vc-btn.on {
  background: var(--accent-soft);
  border-color: var(--accent);
  color: var(--accent);
  font-weight: 700;
}

/* 交点 / 点 列表 */
.pt-count {
  display: inline-block; margin-left: 4px; padding: 0 6px;
  background: var(--accent-soft); color: var(--accent);
  border-radius: 999px; font-size: 10.5px;
}
.pt-row {
  display: grid;
  grid-template-columns: 14px 1fr auto;
  align-items: center;
  gap: 6px;
  padding: 3px 2px;
  font-size: 12px;
}
.pt-dot {
  width: 9px; height: 9px; border-radius: 50%;
  background: #1e293b;
  justify-self: center;
}
.pt-dot.hollow { background: #fff; border: 2px solid #c74440; }
.pt-text {
  font-family: 'Cascadia Code', Consolas, monospace;
  color: var(--text);
}
.pt-badge {
  font-size: 10px; padding: 0 5px; border-radius: 999px;
}
.pt-badge.exact { background: #dcfce7; color: #15803d; }
.pt-badge.num { background: #f1f5f9; color: #64748b; }
.link-btn {
  float: right; background: none; border: none;
  color: var(--text-subtle); font-size: 11px; cursor: pointer;
}
.link-btn:hover { color: var(--danger); }

/* 极值标记与参数分支 */
.pt-dot.diamond {
  width: 10px; height: 10px; border-radius: 2px;
  transform: rotate(45deg);
}
.pt-dot.diamond.max { background: #7c3aed; }
.pt-dot.diamond.min { background: #0891b2; }
.pt-sym {
  padding: 4px 2px 2px;
  border-top: 1px dashed var(--border);
  margin-top: 3px;
}
.pt-branch { display: flex; align-items: center; gap: 6px; padding: 1px 0 1px 10px; font-size: 11.5px; flex-wrap: wrap; }
/* 参数情形标题：一块对应一个参数取值区间（如 a>0） */
.branch-head { display: flex; align-items: center; gap: 6px; padding: 2px 0 1px; }
.branch-tag.strong {
  font-weight: 600;
  color: var(--text);
  background: var(--hover, rgba(127, 127, 127, 0.12));
  border-radius: 4px;
  padding: 0 5px;
}
/* 按参数分组后，行首是驻点表达式而非假设条件 */
.branch-x {
  font-family: 'Cascadia Code', Consolas, monospace;
  color: var(--text-muted);
  min-width: 92px;
}
.branch-tag {
  font-family: 'Cascadia Code', Consolas, monospace;
  color: var(--text-muted);
  min-width: 52px;
}
.branch-kind { font-size: 11px; }
.branch-kind.max { color: #7c3aed; }
.branch-kind.min { color: #0891b2; }
.branch-kind.na { color: var(--text-subtle); }
.branch-value {
  font-family: 'Cascadia Code', Consolas, monospace;
  font-size: 11px;
  color: var(--text-muted);
  margin-left: auto;
}
/* 驻点不存在/在定义域外时的原因说明（如 "驻点 x = -1 落在定义域之外"） */
.branch-note {
  font-size: 10.5px;
  color: var(--text-subtle);
  margin-left: auto;
  text-align: right;
}
/* 含参交点的实根性提示：Δ 符号随参数变化时交点数并非恒定 */
.ix-note {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed var(--border);
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-muted);
}
</style>
