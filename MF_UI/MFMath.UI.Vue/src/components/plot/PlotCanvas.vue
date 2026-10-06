<script setup>
/**
 * PlotCanvas — 绘图画布（对齐 Desmos 的网格、坐标轴、曲线渲染与视图交互）
 * 网格：nice numbers（1/2/5×10ⁿ）；主/次网格线 + 轴线 + 刻度标签
 * 曲线：经 C++ 引擎 expr_eval_batch 采样（断点自动断开）
 * 交互：滚轮缩放（光标为不动点）、拖拽平移、（P3）点击曲线生成点
 */
import { ref, computed, onMounted, onBeforeUnmount, watch } from "vue";
import { engineCall, plotMode, onAppearanceChange } from "../../lib/bridge.js";
import { gridFor } from "../../lib/plot/colors.js";
import {
  defaultView, mapX, mapY, unmapX, unmapY, zoomAt, panBy,
  gridSteps, formatTick, viewW, viewH,
} from "../../lib/plot/view.js";

const props = defineProps({
  curves: { type: Array, default: () => [] },   // [{id, parsed, color, visible}]
  params: { type: Object, default: () => ({}) }, // {a: 1, b: 2}
  /**
   * 深浅色。**不要给 "light" 默认值**：PlotView 从不传这个 prop，给了默认值
   * plotMode("light") 就恒为浅色 → 深色配色下 2D 画布依然白底
   * （bridge.js:163-177 记录的正是这个历史事故）。留空 → 跟随当前配色的深浅。
   */
  theme: { type: String, default: undefined },
  /** 已求值的点（由父组件或本组件计算后缓存） */
  samples: { type: Object, default: () => ({}) }, // {curveId: [[x,y], ...]}
  /** 二元网格采样（隐式方程 / 二元区域用）：{curveId: {xs, ys, values}} */
  grids: { type: Object, default: () => ({}) },
  /** 用户创建的可拖点 [{id, curveId, x, y, color}] */
  points: { type: Array, default: () => [] },
  /** 自动求得的交点 [{x, y, xLabel, yLabel, exact}] */
  intersections: { type: Array, default: () => [] },
  /** 极值点 [{x, y, kind:'max'|'min'}]（由引擎符号求解 local_extrema） */
  extrema: { type: Array, default: () => [] },
  /** 网格模式：rect（直角）| polar（极坐标，π 制刻度） */
  gridMode: { type: String, default: "rect" },
  /** 是否显示网格线（Desmos 设置项） */
  showGrid: { type: Boolean, default: true },
});
const emit = defineEmits(["update:view", "pick-point", "drag-point", "drop-point"]);
const view = defineModel("view", { type: Object });

const canvas = ref(null);
let ctx = null;
let cssW = 0, cssH = 0, raf = 0;
let drag = null;
let hoverPick = null;
let hoverCurvePoint = null;   // 悬停命中的曲线点（Desmos 式追踪）

function scheduleDraw() {
  if (raf) return;
  raf = requestAnimationFrame(() => { raf = 0; draw(); });
}

function resize() {
  const el = canvas.value;
  if (!el) return;
  cssW = el.clientWidth; cssH = el.clientHeight;
  if (cssW <= 0 || cssH <= 0) return;
  const dpr = window.devicePixelRatio || 1;
  el.width = Math.round(cssW * dpr);
  el.height = Math.round(cssH * dpr);
  scheduleDraw();
}

/* ── 网格与坐标轴 ── */
function drawGrid(g) {
  ctx.fillStyle = g.bg;
  ctx.fillRect(0, 0, cssW, cssH);

  const { major, minor } = gridSteps(view.value, cssW, cssH);
  const v = view.value;

  // 极坐标网格（Desmos「投影模式 → 极坐标」）：同心圆 + 角度射线 + π 制刻度
  if (props.gridMode === "polar") {
    drawPolarGrid(g, v, major, props.showGrid);
    drawHoverReadout(g);
    return;
  }

  // 次网格
  if (props.showGrid) {
    ctx.strokeStyle = g.minor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    const i0 = Math.ceil(v.x0 / minor), i1 = Math.floor(v.x1 / minor);
    if (i1 - i0 < 4000) {
      for (let i = i0; i <= i1; i++) {
        const x = i * minor;
        if (Math.abs(x / major - Math.round(x / major)) < 1e-9) continue; // 主网格单独画
        const px = Math.round(mapX(v, cssW, x)) + 0.5;
        ctx.moveTo(px, 0); ctx.lineTo(px, cssH);
      }
    }
    const j0 = Math.ceil(v.y0 / minor), j1 = Math.floor(v.y1 / minor);
    if (j1 - j0 < 4000) {
      for (let j = j0; j <= j1; j++) {
        const y = j * minor;
        if (Math.abs(y / major - Math.round(y / major)) < 1e-9) continue;
        const py = Math.round(mapY(v, cssH, y)) + 0.5;
        ctx.moveTo(0, py); ctx.lineTo(cssW, py);
      }
    }
    ctx.stroke();
  }

  // 主网格刻度索引（声明在 if 之外：后面的刻度标签绘制也要用）
  const k0 = Math.ceil(v.x0 / major), k1 = Math.floor(v.x1 / major);
  const l0 = Math.ceil(v.y0 / major), l1 = Math.floor(v.y1 / major);

  // 主网格
  if (props.showGrid) {
    ctx.strokeStyle = g.major;
    ctx.beginPath();
    if (k1 - k0 < 2000) {
      for (let k = k0; k <= k1; k++) {
        const px = Math.round(mapX(v, cssW, k * major)) + 0.5;
        ctx.moveTo(px, 0); ctx.lineTo(px, cssH);
      }
    }
    if (l1 - l0 < 2000) {
      for (let l = l0; l <= l1; l++) {
        const py = Math.round(mapY(v, cssH, l * major)) + 0.5;
        ctx.moveTo(0, py); ctx.lineTo(cssW, py);
      }
    }
    ctx.stroke();
  }

  // 坐标轴（y 轴在 x=0，x 轴在 y=0；若不在视野内则贴边显示不画）
  const axisY = mapY(v, cssH, 0);
  const axisX = mapX(v, cssW, 0);
  ctx.strokeStyle = g.axis;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  if (axisY >= 0 && axisY <= cssH) { ctx.moveTo(0, axisY); ctx.lineTo(cssW, axisY); }
  if (axisX >= 0 && axisX <= cssW) { ctx.moveTo(axisX, 0); ctx.lineTo(axisX, cssH); }
  ctx.stroke();

  // 刻度标签（沿坐标轴；轴不可见时贴边）
  ctx.fillStyle = g.label;
  ctx.font = "11px -apple-system, Segoe UI, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  const labelY = Math.min(Math.max(axisY + 4, 2), cssH - 16);
  if (k1 - k0 < 200) {
    for (let k = k0; k <= k1; k++) {
      if (k === 0) continue;
      const x = k * major;
      const px = mapX(v, cssW, x);
      if (px < 16 || px > cssW - 16) continue;
      ctx.fillText(formatTick(x, major), px, labelY);
    }
  }
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  const labelX = Math.min(Math.max(axisX - 6, 26), cssW - 4);
  if (l1 - l0 < 200) {
    for (let l = l0; l <= l1; l++) {
      if (l === 0) continue;
      const y = l * major;
      const py = mapY(v, cssH, y);
      if (py < 10 || py > cssH - 10) continue;
      ctx.fillText(formatTick(y, major), labelX, py);
    }
  }
  // 原点
  if (axisX >= 0 && axisX <= cssW && axisY >= 0 && axisY <= cssH) {
    ctx.textAlign = "right"; ctx.textBaseline = "top";
    ctx.fillText("0", axisX - 5, axisY + 3);
  }

  drawHoverReadout(g);
}

/** 光标处的世界坐标读数（无曲线命中时显示在左下角） */
function drawHoverReadout(g) {
  if (!hoverPick) return;
  ctx.textAlign = "left";
  ctx.textBaseline = "bottom";
  ctx.fillStyle = g.label;
  ctx.fillText(`(${fmt(hoverPick[0])}, ${fmt(hoverPick[1])})`, 8, cssH - 6);
}

/**
 * 悬停在曲线上时显示「曲线上的点」（对齐 Desmos：追踪曲线读坐标）
 * 用已采样点在屏幕空间做最近邻查找，不额外调用引擎。
 */
function findCurvePointAt(px, py, tolPx = 16) {
  const v = view.value;
  let best = null, bestDist = tolPx;
  for (const c of props.curves) {
    if (!c.visible) continue;
    const pts = props.samples[c.id];
    if (!pts || pts.length < 2) continue;
    const type = c.parsed?.type;
    if (type === "region" || type === "implicit") continue;   // 区域/隐式无单值坐标
    // 断点（null）不能参与命中检测：解构 null 会直接抛异常，把悬停整条打断
    for (const p of pts) {
      if (!p) continue;
      const [x, y] = p;
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
      const sx = mapX(v, cssW, x), sy = mapY(v, cssH, y);
      const d = Math.hypot(sx - px, sy - py);
      if (d < bestDist) { bestDist = d; best = { curve: c, x, y, sx, sy }; }
    }
  }
  return best;
}

/** 绘制曲线追踪点（实心圆 + 坐标标签） */
function drawTrace(g) {
  if (!hoverCurvePoint) return;
  const { curve, x, y, sx, sy } = hoverCurvePoint;
  ctx.beginPath();
  ctx.arc(sx, sy, 5, 0, Math.PI * 2);
  ctx.fillStyle = curve.color;
  ctx.fill();
  ctx.strokeStyle = "#fff";
  ctx.lineWidth = 1.6;
  ctx.stroke();
  ctx.fillStyle = g.axisLabel;
  ctx.font = "12px -apple-system, Segoe UI, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "bottom";
  ctx.fillText(`(${fmt(x)}, ${fmt(y)})`, sx + 9, sy - 7);
}

/**
 * 极坐标网格（对齐 Desmos「投影模式 → 极坐标」）
 * 同心圆（nice step 半径）+ 每 15° 射线 + π 制角度刻度 + 半径数值刻度
 */
function drawPolarGrid(g, v, major, showGridLines = true) {
  const ox = mapX(v, cssW, 0), oy = mapY(v, cssH, 0);
  const pxPerUnit = cssW / Math.max(viewW(v), 1e-12);
  const reach = Math.hypot(Math.max(cssW, cssH) * 1.2, Math.max(cssW, cssH) * 1.2);

  // 同心圆 + 角度射线（受网格开关控制，与 Desmos 一致）
  const rStep = major;   // 半径用与直角网格相同的 nice step

  // ⚠ 本函数里**两个**循环（同心圆、半径刻度）都必须用这个前置条件兜住，
  // 否则退化参数下它们是死循环，会把渲染进程同步卡死 —— 这就是
  // `cdp-plot-p5`「跑到极坐标网格就挂住页面」的成因
  // （docs/MIGRATION-GAPS.md、docs/STATUS-and-ROADMAP.md 都记了症状，但都搁置了）。
  //
  // 两条退化路径都会让 `r * pxPerUnit < reach` 永远成立：
  //   · rStep === 0     —— 视图范围退化成 0 时，niceStep 里 raw=0 → mag=10^-Infinity=0
  //                         → 返回 0；此时 `r += 0` 原地踏步，永远出不来。
  //   · pxPerUnit === 0 —— 画布宽度为 0 时 cssW / viewW = 0，r 一直增大也永远 < reach；
  //                         半径刻度那个循环里的 `if (lx > cssW - 10) break` 也失效（lx 恒为 ox）。
  // 直角网格那几个循环早就有 `i1 - i0 < 4000` 的同源护栏，这里当时漏了。
  const canRings = Number.isFinite(rStep) && rStep > 0 &&
                   Number.isFinite(pxPerUnit) && pxPerUnit > 0;

  if (showGridLines) {
    ctx.strokeStyle = g.major;
    ctx.lineWidth = 1;
    ctx.beginPath();
    if (canRings) {
      // 迭代上限与直角网格的 4000 同源：即使将来又冒出一条退化路径，也不会再卡死
      for (let r = rStep, rings = 0; r * pxPerUnit < reach && rings < 4000; r += rStep, rings++) {
        ctx.moveTo(ox + r * pxPerUnit, oy);
        ctx.arc(ox, oy, r * pxPerUnit, 0, Math.PI * 2);
      }
    }
    ctx.stroke();

    ctx.strokeStyle = g.minor;
    ctx.beginPath();
    for (let deg = 0; deg < 360; deg += 15) {
      const a = (deg * Math.PI) / 180;
      ctx.moveTo(ox, oy);
      ctx.lineTo(ox + reach * Math.cos(a), oy - reach * Math.sin(a));
    }
    ctx.stroke();
  }

  // 主方位轴（0/90/180/270）加重
  ctx.strokeStyle = g.axis;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(ox - reach, oy); ctx.lineTo(ox + reach, oy);
  ctx.moveTo(ox, oy - reach); ctx.lineTo(ox, oy + reach);
  ctx.stroke();

  // π 制角度刻度（对齐 Desmos 的弧度标注）
  ctx.fillStyle = g.label;
  ctx.font = "11px -apple-system, Segoe UI, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  if (showGridLines) {
    const ANGLE_LABELS = [
      [0, "0"], [30, "π/6"], [45, "π/4"], [60, "π/3"], [90, "π/2"],
      [120, "2π/3"], [135, "3π/4"], [150, "5π/6"], [180, "π"],
      [210, "7π/6"], [225, "5π/4"], [240, "4π/3"], [270, "3π/2"],
      [300, "5π/3"], [315, "7π/4"], [330, "11π/6"],
    ];
    const labelR = Math.min(cssW, cssH) * 0.42;
    for (const [deg, text] of ANGLE_LABELS) {
      const a = (deg * Math.PI) / 180;
      const lx = ox + labelR * Math.cos(a);
      const ly = oy - labelR * Math.sin(a);
      if (lx < 12 || lx > cssW - 12 || ly < 10 || ly > cssH - 10) continue;
      ctx.fillText(text, lx, ly);
    }

    // 半径数值刻度（沿 0° 方向）
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    // 与上面同心圆同一个护栏：`if (lx > cssW - 10) break` 只在"r 增大到超出画布"时
    // 才生效，rStep === 0 / pxPerUnit === 0 时它永远不触发。
    if (canRings) {
      for (let r = rStep, ticks = 0; r * pxPerUnit < reach && ticks < 4000; r += rStep, ticks++) {
        const lx = ox + r * pxPerUnit;
        if (lx > cssW - 10) break;
        ctx.fillText(formatTick(r, rStep), lx, oy + 3);
      }
    }
  }

  // 原点
  ctx.textAlign = "right";
  ctx.textBaseline = "top";
  ctx.fillText("0", ox - 5, oy + 3);
}

function fmt(v) {
  if (!isFinite(v)) return "—";
  const a = Math.abs(v);
  if (a !== 0 && (a < 1e-3 || a >= 1e5)) return v.toExponential(2);
  return String(Math.round(v * 1e4) / 1e4);
}

/* ── 曲线绘制 ── */
function drawCurves() {
  const v = view.value;
  for (const c of props.curves) {
    if (!c.visible) continue;
    const pts = props.samples[c.id];
    if (!pts || pts.length < 2) continue;
    ctx.strokeStyle = c.color;
    ctx.lineWidth = c.emphasis ? 4 : 2.5;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.beginPath();
    let drawing = false;
    let lastPx = null, lastPy = null;
    for (const p of pts) {
      // 断点（域外 / 未定义 / 引擎返回 null）：断开路径，绝不跨过去连线
      // （Number(null) === 0，直接换算会画出假的 y=0 段）
      if (!p) { drawing = false; continue; }
      const [x, y] = p;
      if (!Number.isFinite(x) || !Number.isFinite(y)) { drawing = false; continue; }
      const px = mapX(v, cssW, x), py = mapY(v, cssH, y);
      // 断点：屏幕跳变过大（渐近线）时断开
      if (drawing && lastPx !== null) {
        if (Math.abs(py - lastPy) > cssH * 1.6) { drawing = false; }
      }
      if (!drawing) { ctx.moveTo(px, py); drawing = true; }
      else ctx.lineTo(px, py);
      lastPx = px; lastPy = py;
    }
    ctx.stroke();
  }
}

/** 绘制用户创建的可拖动点（Desmos 风格：空心圆 + 坐标标签） */
function drawPoints() {
  const v = view.value;
  ctx.font = "12px -apple-system, Segoe UI, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "bottom";
  for (const p of props.points) {
    if (!isFinite(p.x) || !isFinite(p.y)) continue;
    const px = mapX(v, cssW, p.x), py = mapY(v, cssH, p.y);
    ctx.beginPath();
    ctx.arc(px, py, 5.5, 0, Math.PI * 2);
    ctx.fillStyle = "#fff";
    ctx.fill();
    ctx.strokeStyle = p.color || "#c74440";
    ctx.lineWidth = 2.5;
    ctx.stroke();
    label(`${fmt(p.x)}, ${fmt(p.y)}`, px + 9, py - 7, p.color || "#444");
  }
}

/** 绘制极值点（菱形标记 + 「极大/极小」标签；由引擎符号求解得到） */
function drawExtrema() {
  if (!props.extrema || !props.extrema.length) return;
  const v = view.value;
  ctx.font = "11.5px -apple-system, Segoe UI, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "bottom";
  for (const e of props.extrema) {
    if (!isFinite(e.x) || !isFinite(e.y)) continue;
    const px = mapX(v, cssW, e.x), py = mapY(v, cssH, e.y);
    if (px < -40 || px > cssW + 40 || py < -40 || py > cssH + 40) continue;
    const isMax = e.kind === "max";
    const color = isMax ? "#7c3aed" : "#0891b2";
    // 菱形标记（区别于交点圆点、用户点空心圆）
    // ⚠ 不要给它加白色描边：那圈白边会把底下的曲线"切断"，在平坦的极值点处看起来
    //   就像"曲线画不出来"（这正是用户报的那个问题）。标记现在画在曲线**之前**，
    //   所以只需要一个实心菱形；曲线压在上面，两侧仍然看得见标记。
    const r = 4;
    ctx.beginPath();
    ctx.moveTo(px, py - r);
    ctx.lineTo(px + r, py);
    ctx.lineTo(px, py + r);
    ctx.lineTo(px - r, py);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
    ctx.fillStyle = color;
    ctx.fillText(`${isMax ? "极大" : "极小"} (${fmt(e.x)}, ${fmt(e.y)})`, px + 8, py - 6);
  }
}

/** 绘制自动求得的交点（实心小圆 + 坐标；精确解标记为实心，数值解略淡） */function drawIntersections() {
  const v = view.value;
  ctx.font = "11.5px -apple-system, Segoe UI, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "bottom";
  for (const it of props.intersections) {
    if (!isFinite(it.x) || !isFinite(it.y)) continue;
    const px = mapX(v, cssW, it.x), py = mapY(v, cssH, it.y);
    if (px < -40 || px > cssW + 40 || py < -40 || py > cssH + 40) continue;
    ctx.beginPath();
    ctx.arc(px, py, 4.5, 0, Math.PI * 2);
    ctx.fillStyle = it.exact ? "#1e293b" : "#64748b";
    ctx.globalAlpha = it.exact ? 1 : 0.75;
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 1.5;
    ctx.stroke();
    label(`(${it.xLabel}, ${it.yLabel})`, px + 8, py - 6, "#475569");
  }
}

function label(text, x, y, color) {
  ctx.fillStyle = color;
  ctx.fillText(text, x, y);
}

/** 十六进制色 → rgba（用于半透明区域填充） */
function withAlpha(hex, a) {
  const h = String(hex || "#c74440").replace("#", "");
  const n = h.length === 3
    ? h.split("").map((c) => c + c).join("")
    : h.padEnd(6, "0").slice(0, 6);
  const r = parseInt(n.slice(0, 2), 16), g = parseInt(n.slice(2, 4), 16), b = parseInt(n.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

/**
 * 不等式区域填充（对齐 Desmos：半透明色块 + 实线边界）
 * 支持 y ≷ f(x)（水平界）与 x ≷ g(y)（垂直界）；
 * 区域用「沿边界的路径 + 闭合到画布边缘」一次填充。
 */
function drawInequalities() {
  const v = view.value;
  for (const c of props.curves) {
    if (!c.visible) continue;
    const p = c.parsed;
    if (!p || p.type !== "inequality" || !p.valid) continue;
    const pts = props.samples[c.id];
    if (!pts || pts.length < 2) continue;

    const fill = withAlpha(c.color, c.emphasis ? 0.22 : 0.16);
    ctx.fillStyle = fill;

    if (p.axis === "y") {
      // y ≷ f(x)：上/下填充
      const upper = p.op === ">" || p.op === "≥";
      ctx.beginPath();
      let started = false;
      const edge = upper ? 0 : cssH;
      for (const p of pts) {
        if (!p) continue;                       // 断点：不参与填充
        const [x, y] = p;
        if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
        const px = mapX(v, cssW, x);
        const py = Math.max(-cssH, Math.min(2 * cssH, mapY(v, cssH, y)));   // 钳制避免巨值路径
        if (!started) {
          ctx.moveTo(px, edge);
          ctx.lineTo(px, py);
          started = true;
        } else ctx.lineTo(px, py);
      }
      if (started) {
        // 收尾：最后一个**有效**点回到边缘，闭合（末项可能是断点）
        const last = [...pts].reverse().find((q) => q && Number.isFinite(q[0]) && Number.isFinite(q[1]));
        if (last) ctx.lineTo(mapX(v, cssW, last[0]), edge);
        ctx.closePath();
        ctx.fill();
      }
    } else if (p.axis === "x") {
      // x ≷ g(y)：右/左填充（pts 为 [x, t] 形式，t 是 y）
      const right = p.op === ">" || p.op === "≥";
      const edge = right ? cssW : 0;
      ctx.beginPath();
      let started = false;
      for (const p of pts) {
        if (!p) continue;                       // 断点：不参与填充
        const [x, y] = p;
        if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
        const px = Math.max(-cssW, Math.min(2 * cssW, mapX(v, cssW, x)));
        const py = mapY(v, cssH, y);
        if (!started) {
          ctx.moveTo(edge, py);
          ctx.lineTo(px, py);
          started = true;
        } else ctx.lineTo(px, py);
      }
      if (started) {
        const last = [...pts].reverse().find((q) => q && Number.isFinite(q[0]) && Number.isFinite(q[1]));
        if (last) ctx.lineTo(edge, mapY(v, cssH, last[1]));
        ctx.closePath();
        ctx.fill();
      }
    }

    // 边界线（Desmos 的区域边界用实线）
    ctx.strokeStyle = c.color;
    ctx.lineWidth = c.emphasis ? 3 : 2;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.beginPath();
    let drawing = false;
    let lastPx = null, lastPy = null;
    for (const p of pts) {
      // 断点（域外 / 未定义 / 引擎返回 null）：断开路径，绝不跨过去连线
      // （Number(null) === 0，直接换算会画出假的 y=0 段）
      if (!p) { drawing = false; continue; }
      const [x, y] = p;
      if (!Number.isFinite(x) || !Number.isFinite(y)) { drawing = false; continue; }
      const px = mapX(v, cssW, x), py = mapY(v, cssH, y);
      if (drawing && lastPx !== null && Math.abs(py - lastPy) > cssH * 1.6) drawing = false;
      if (!drawing) { ctx.moveTo(px, py); drawing = true; } else ctx.lineTo(px, py);
      lastPx = px; lastPy = py;
    }
    ctx.stroke();
  }
}

/**
 * 二元区域填充（如 x²+y²<4）：按屏幕格子判定
 * grid: {xs, ys, values}（引擎 expr_eval_grid 结果，行优先）
 */
function drawRegions() {
  const v = view.value;
  for (const c of props.curves) {
    if (!c.visible) continue;
    const p = c.parsed;
    if (!p || p.type !== "region" || !p.valid) continue;
    const g = props.grids && props.grids[c.id];
    if (!g || !g.values) continue;

    const nx = g.xs.length, ny = g.ys.length;
    if (nx < 2 || ny < 2) continue;
    const cellW = cssW / (nx - 1), cellH = cssH / (ny - 1);
    ctx.fillStyle = withAlpha(c.color, c.emphasis ? 0.22 : 0.16);

    // 逐格判定：格心符号满足不等式则填充该格（Desmos 区域为像素级，这里用格级近似）
    for (let j = 0; j + 1 < ny; j++) {
      for (let i = 0; i + 1 < nx; i++) {
        const a = g.values[j * nx + i];
        const b = g.values[j * nx + i + 1];
        const d = g.values[(j + 1) * nx + i];
        const e = g.values[(j + 1) * nx + i + 1];
        if (![a, b, d, e].every((t) => typeof t === "number" && isFinite(t))) continue;
        const mean = (a + b + d + e) / 4;
        const inside = p.op === ">" || p.op === "≥" ? mean > 0 : mean < 0;
        if (!inside) continue;
        const px = mapX(v, cssW, g.xs[i]);
        const py = mapY(v, cssH, g.ys[j + 1]);
        ctx.fillRect(px, py, cellW + 1, cellH + 1);
      }
    }
  }
}

/**
 * 隐式方程等值线（如 x²+y²=4）—— marching squares
 * grid: 引擎 expr_eval_grid 的采样网格
 */
function drawImplicit(p, g, color, emphasis) {
  const v = view.value;
  const nx = g.xs.length, ny = g.ys.length;
  if (nx < 2 || ny < 2) return;

  const sx = new Array(nx), sy = new Array(ny);
  for (let i = 0; i < nx; i++) sx[i] = mapX(v, cssW, g.xs[i]);
  for (let j = 0; j < ny; j++) sy[j] = mapY(v, cssH, g.ys[j]);

  ctx.strokeStyle = color;
  ctx.lineWidth = emphasis ? 3 : 2.2;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.beginPath();

  /** 在两点间线性插值出 f=0 的位置（返回 0..1 比例） */
  const lerp = (fa, fb) => {
    const denom = fa - fb;
    if (Math.abs(denom) < 1e-12) return 0.5;
    const t = fa / denom;
    return Math.max(0, Math.min(1, t));
  };

  for (let j = 0; j + 1 < ny; j++) {
    for (let i = 0; i + 1 < nx; i++) {
      // 格子四顶点值（行优先：行 j 是 y[j]）
      const f00 = g.values[j * nx + i];
      const f10 = g.values[j * nx + i + 1];
      const f01 = g.values[(j + 1) * nx + i];
      const f11 = g.values[(j + 1) * nx + i + 1];
      if (![f00, f10, f01, f11].every((t) => typeof t === "number" && isFinite(t))) continue;

      // 四个顶点的符号位
      let idx = 0;
      if (f00 > 0) idx |= 1;
      if (f10 > 0) idx |= 2;
      if (f11 > 0) idx |= 4;
      if (f01 > 0) idx |= 8;
      if (idx === 0 || idx === 15) continue;

      // 边上插值点：底(b)、右(r)、顶(t)、左(l)
      const bx = sx[i] + (sx[i + 1] - sx[i]) * lerp(f00, f10);
      const by = sy[j];
      const rx = sx[i + 1];
      const ry = sy[j] + (sy[j + 1] - sy[j]) * lerp(f10, f11);
      const tx = sx[i] + (sx[i + 1] - sx[i]) * lerp(f01, f11);
      const ty = sy[j + 1];
      const lx = sx[i];
      const ly = sy[j] + (sy[j + 1] - sy[j]) * lerp(f00, f01);

      const seg = (x1, y1, x2, y2) => { ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); };
      switch (idx) {
        case 1: case 14: seg(lx, ly, bx, by); break;
        case 2: case 13: seg(bx, by, rx, ry); break;
        case 3: case 12: seg(lx, ly, rx, ry); break;
        case 4: case 11: seg(rx, ry, tx, ty); break;
        case 5: seg(lx, ly, tx, ty); seg(bx, by, rx, ry); break;   // 鞍点
        case 6: case 9: seg(bx, by, tx, ty); break;
        case 7: case 8: seg(lx, ly, tx, ty); break;
        case 10: seg(lx, ly, bx, by); seg(rx, ry, tx, ty); break;  // 鞍点
        default: break;
      }
    }
  }
  ctx.stroke();
}

/** 绘制所有隐式方程（对每条 implicit 曲线调用 marching squares） */
function drawImplicits() {
  for (const c of props.curves) {
    if (!c.visible) continue;
    const p = c.parsed;
    if (!p || p.type !== "implicit" || !p.valid) continue;
    const g = props.grids && props.grids[c.id];
    if (!g) continue;
    drawImplicit(p, g, c.color, c.emphasis);
  }
}

function draw() {
  if (!ctx) return;
  if (cssW <= 0) { const el = canvas.value; cssW = el?.clientWidth || 0; cssH = el?.clientHeight || 0; }
  if (cssW <= 0 || cssH <= 0) return;
  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const g = gridFor(effectiveTheme.value);
  // 分步绘制并隔离异常：某一步出错不应让整块画布停止绘制（同时把错误暴露出来）
  const steps = [
    ["grid", () => drawGrid(g)],
    ["regions", () => drawRegions()],
    ["inequalities", () => drawInequalities()],
    /* ⚠ 标记（极值/交点）必须画在**曲线之前**：它们是不透明的实心块（菱形/圆点），
     * 画在曲线之后就会把曲线盖掉一截。在**平坦的极值点**上后果最明显 ——
     * 用户看到的是"曲线在贴着 x 轴的地方断开了"（一个 10px 的标记在顶点处能遮掉很宽一段 x），
     * 而实际上采样与绘制完全正常（引擎在 x=0 返回的就是 0，没有任何 null）。
     * 顺序改成"标记在下、曲线在上"后，曲线始终连续，标记仍然露在曲线两侧。 */
    ["extrema", () => drawExtrema()],
    ["intersections", () => drawIntersections()],
    ["curves", () => drawCurves()],
    ["implicits", () => drawImplicits()],
    // 用户自己创建的点仍画在最上面（空心圆的样式是刻意的，且要能拖动/命中）
    ["points", () => drawPoints()],
    ["trace", () => drawTrace(g)],
  ];
  const errs = [];
  for (const [name, fn] of steps) {
    try { fn(); } catch (e) { errs.push(`${name}: ${e && e.message ? e.message : e}`); }
  }
  if (typeof window !== "undefined") window.__plotErrors = errs;
}

/* ── 交互：滚轮缩放（光标不动点）── */
function onWheel(e) {
  e.preventDefault();
  if (!view.value) return;
  const rect = canvas.value.getBoundingClientRect();
  const px = e.clientX - rect.left, py = e.clientY - rect.top;
  const factor = e.deltaY < 0 ? 0.88 : 1.14;
  view.value = zoomAt(view.value, cssW, cssH, px, py, factor);
  emit("update:view", view.value);
  scheduleDraw();
}

/* ── 交互：拖拽平移 / 拖动已创建的点 ── */
let draggingPoint = null;   // 正在拖动的点 id

/** 命中检测：返回鼠标附近的已创建点（屏幕距离 < 10px） */
function hitPoint(px, py) {
  const v = view.value;
  for (const p of props.points) {
    if (!isFinite(p.x) || !isFinite(p.y)) continue;
    const dx = mapX(v, cssW, p.x) - px;
    const dy = mapY(v, cssH, p.y) - py;
    if (Math.hypot(dx, dy) < 10) return p;
  }
  return null;
}

function onMouseDown(e) {
  if (e.button !== 0) return;
  const rect = canvas.value.getBoundingClientRect();
  const px = e.clientX - rect.left, py = e.clientY - rect.top;

  // 优先拖动已有点（Desmos：点可沿曲线滑动）
  const hit = hitPoint(px, py);
  if (hit) {
    draggingPoint = hit.id;
    canvas.value.style.cursor = "grabbing";
    return;
  }

  drag = { x: e.clientX, y: e.clientY, view: { ...view.value } };
  canvas.value.style.cursor = "grabbing";
}
function onMouseMove(e) {
  const rect = canvas.value.getBoundingClientRect();
  const px = e.clientX - rect.left, py = e.clientY - rect.top;
  hoverPick = [unmapX(view.value, cssW, px), unmapY(view.value, cssH, py)];

  // 拖动点：把光标的世界坐标交给父组件（父组件按曲线类型决定更新 x 还是 y）
  if (draggingPoint !== null) {
    emit("drag-point", { id: draggingPoint, world: [unmapX(view.value, cssW, px), unmapY(view.value, cssH, py)] });
    scheduleDraw();
    return;
  }

  if (drag) {
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    const base = drag.view;
    const sx = viewW(base) / Math.max(cssW, 1), sy = viewH(base) / Math.max(cssH, 1);
    view.value = {
      x0: base.x0 - dx * sx, x1: base.x1 - dx * sx,
      y0: base.y0 + dy * sy, y1: base.y1 + dy * sy,
    };
    emit("update:view", view.value);
    scheduleDraw();
    return;
  }

  // 悬停追踪：命中曲线则显示曲线上的点（Desmos 行为），否则显示光标坐标
  hoverCurvePoint = findCurvePointAt(px, py);
  // 悬停到已有点上时给出可拖动光标
  canvas.value.style.cursor = hitPoint(px, py) ? "grab" : (hoverCurvePoint ? "pointer" : "crosshair");
  scheduleDraw();
}
function onMouseUp(e) {
  if (draggingPoint !== null) {
    emit("drop-point", { id: draggingPoint });
    draggingPoint = null;
    canvas.value.style.cursor = "";
    return;
  }
  if (drag) {
    const moved = Math.hypot(e.clientX - drag.x, e.clientY - drag.y);
    if (moved < 4) {
      // 视为点击：交给父组件做"点击曲线生成点"
      const rect = canvas.value.getBoundingClientRect();
      emit("pick-point", {
        world: [unmapX(view.value, cssW, e.clientX - rect.left), unmapY(view.value, cssH, e.clientY - rect.top)],
        screen: [e.clientX - rect.left, e.clientY - rect.top],
      });
    }
  }
  drag = null;
  canvas.value.style.cursor = "";
}
function onMouseLeave() {
  hoverPick = null;
  hoverCurvePoint = null;
  // ⚠ 拖拽状态也必须在离开画布时清掉：mouseup 只会落在画布上，
  // 用户"按下 → 移出画布 → 松开"时 onMouseUp 根本不会触发，
  // drag / draggingPoint 于是永久残留 —— 之后**不按键**移动鼠标也会继续平移视图
  // （或继续拖动曲线点），光标还卡在 grabbing。这里只做清理，不补发点击事件，
  // 免得"移出画布松手"被当成一次点击而多创建一个点。
  if (draggingPoint !== null) {
    emit("drop-point", { id: draggingPoint });
    draggingPoint = null;
  }
  drag = null;
  if (canvas.value) canvas.value.style.cursor = "";
  scheduleDraw();
}

/* 对外暴露：供父组件做 Zoom Fit / 重置；canvasEl 供"导出图片"重绘到离屏画布 */
function canvasSize() { return { w: cssW, h: cssH }; }
defineExpose({ canvasSize, scheduleDraw, redraw: draw, canvasEl: () => canvas.value });

let ro = null;
// 外观（配色深浅）变化时重绘：画布不认 CSS 变量，只能靠这个广播刷新网格与坐标轴配色。
// modeTick 只是为了让 effectiveTheme 这个 computed 有可响应的依赖。
const modeTick = ref(0);
const effectiveTheme = computed(() => { modeTick.value; return plotMode(props.theme); });
const offAppearance = onAppearanceChange(() => { modeTick.value++; scheduleDraw(); });

onMounted(() => {
  ctx = canvas.value.getContext("2d");
  if (!view.value) view.value = defaultView(1, 1);
  resize();
  if (window.ResizeObserver) {
    ro = new ResizeObserver(() => {
      const first = cssW <= 0;
      resize();
      if (first) { view.value = defaultView(cssW || 1, cssH || 1); emit("update:view", view.value); }
    });
    ro.observe(canvas.value);
  }
});
onBeforeUnmount(() => {
  if (ro) ro.disconnect();
  cancelAnimationFrame(raf);
  offAppearance();
});

/**
 * 重绘触发：这里**必须用浅比较**（不传 deep）。
 * samples（自适应采样后可达数千点）与 grids（如 180×180 = 3 万数字）都是大对象，
 * 若做深度监听，Vue 每次更新都要遍历整棵树，会造成主线程卡死（实测会导致页面无响应）。
 * 父组件每次采样都赋新对象/新数组，引用变化即可触发。
 */
watch(
  () => [props.curves, props.samples, props.grids, props.theme, props.points,
         props.intersections, props.extrema, props.gridMode, props.showGrid],
  scheduleDraw
);
watch(() => [view.value?.x0, view.value?.x1, view.value?.y0, view.value?.y1], scheduleDraw);
</script>

<template>
  <canvas
    ref="canvas"
    class="plot-canvas-desmos"
    @wheel="onWheel"
    @mousedown="onMouseDown"
    @mousemove="onMouseMove"
    @mouseup="onMouseUp"
    @mouseleave="onMouseLeave"
  />
</template>

<style scoped>
.plot-canvas-desmos {
  display: block;
  width: 100%;
  height: 100%;
  cursor: crosshair;
  touch-action: none;
}
</style>
