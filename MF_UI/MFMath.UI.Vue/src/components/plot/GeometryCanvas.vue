<script setup>
/**
 * GeometryCanvas — 交互式几何作图画布（对齐 Python plot/arbitrary/geometry_canvas）
 *  · 10 种工具：选择/移动、平移、点、线段、圆、向量、直线、椭圆、矩形、多边形
 *  · 构造状态机：idle / awaitSecond / dragRadius / awaitHRad / awaitVRad / awaitCorner / buildPoly
 *  · 吸附：优先几何吸附（端点/中点/圆心），否则网格吸附
 *  · 命中检测（点到图形的屏幕距离）+ 拖拽移动
 *  · 坐标系复用 cartesian.js（与 2D 绘图一致）
 */
import { ref, computed, onMounted, onBeforeUnmount, watch } from "vue";
import { gridFor } from "../../lib/plot/colors.js";
import { plotMode, onAppearanceChange } from "../../lib/bridge.js";
import { drawCartesianGrid } from "../../lib/plot/cartesian.js";
import { mapX, mapY, unmapX, unmapY, zoomAt, panBy, gridSteps } from "../../lib/plot/view.js";

const props = defineProps({
  /** 图形列表：[{id, type, data, color, label, visible}] */
  shapes: { type: Array, default: () => [] },
  /** 当前工具 */
  tool: { type: String, default: "select" },
  /** 选中图形 id */
  selectedId: { type: [Number, String], default: null },
  /** 是否吸附 */
  snap: { type: Boolean, default: true },
  /**
   * 深浅色。**不要给 "light" 默认值**：PlotGeometryView 从不传这个 prop，
   * 给了默认值 plotMode("light") 就恒为浅色 → 深色配色下画布永远白底
   * （bridge.js:163-177 记录的同类历史事故）。留空 → 跟随当前配色的深浅。
   */
  theme: { type: String, default: undefined },
});
const emit = defineEmits(["create", "select", "move", "cursor"]);

const canvas = ref(null);
let ctx = null;
let cssW = 0, cssH = 0, raf = 0;
const view = ref({ x0: -8, y0: -6, x1: 8, y1: 6 });

/** 构造状态机 */
const state = ref("idle");
const tempPts = ref([]);      // 已确定的构造点
const cursor = ref([0, 0]);   // 当前光标（吸附后）
let drag = null;              // {kind:'shape'|'pan', ...}

const SNAP_HINT = {
  idle: "",
  awaitSecond: "点击终点",
  dragRadius: "拖拽确定半径",
  awaitHRad: "点击确定水平半轴",
  awaitVRad: "点击确定垂直半轴",
  awaitCorner: "点击对角",
  buildPoly: "继续点击顶点，双击或右键闭合",
};

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
  // 画布尺寸变化时把视图修正回等比（原版 resizeEvent 里 fitInView(..., KeepAspectRatio)，:825-830）
  const cy = (view.value.y0 + view.value.y1) / 2;
  view.value = equalAspectView(view.value.x0, view.value.x1, cy, cssW, cssH);
  scheduleDraw();
}

/**
 * 等比视图：x/y 每单位对应的像素数相同。
 * 原版全程保持等比（`scale(1,-1)` + `fitInView(INITIAL_VIEW, KeepAspectRatio)`，:203-204,825-830,1100），
 * 所以世界里的圆画出来还是圆；此前视图固定 16×12，画布不是 4:3 时网格与圆都被拉伸。
 */
function equalAspectView(x0, x1, cy, w, h) {
  const spanX = x1 - x0;
  const spanY = spanX * (h / Math.max(w, 1));
  return { x0, x1, y0: cy - spanY / 2, y1: cy + spanY / 2 };
}

/* ── 吸附 ── */
/**
 * 吸附/命中用的网格粒度。
 * 原版 arbitrary/geometry_canvas.py:700-703 `_grid_step` 用的是**次网格**粒度：
 *     calculate_step(rng) / 5
 * 此前这里直接返回主网格步长 major，于是吸附（以及吸附阈值 0.6*step）比原版粗 5 倍。
 */
function gridStep() {
  const { major } = gridSteps(view.value, cssW, cssH);
  return major / 5;
}
function snapPoint(x, y) {
  if (!props.snap) return [x, y];
  const step = gridStep();
  const th = step * 0.6;
  let best = null, bd = th;
  for (const s of props.shapes) {
    if (!s.visible) continue;
    for (const [px, py] of shapeSnapPoints(s)) {
      const d = Math.hypot(x - px, y - py);
      if (d < bd) { bd = d; best = [px, py]; }
    }
  }
  if (best) return best;
  return [Math.round(x / step) * step, Math.round(y / step) * step];
}
function shapeSnapPoints(s) {
  const d = s.data, t = s.type, out = [];
  if (t === "point") out.push([d[0], d[1]]);
  else if (t === "segment" || t === "vector" || t === "line") {
    out.push([d[0][0], d[0][1]], [d[1][0], d[1][1]],
             [(d[0][0] + d[1][0]) / 2, (d[0][1] + d[1][1]) / 2]);   // 两端点 + 中点
  } else if (t === "circle") {
    // 原版 arbitrary/geometry_canvas.py:681-685：圆心 + 右端点 + 上端点
    out.push([d[0][0], d[0][1]], [d[0][0] + d[1], d[0][1]], [d[0][0], d[0][1] + d[1]]);
  } else if (t === "ellipse") {
    // 原版 :686-690 把 ((cx,cy),rx,ry) 当成两点解包了（原版自身缺陷），这里不照抄：
    // 给"圆心 + 两个轴端点"。
    out.push([d[0][0], d[0][1]], [d[0][0] + d[1], d[0][1]], [d[0][0], d[0][1] + d[2]]);
  } else if (t === "rect") {
    // 原版 :686-690：两角 + 两角中点
    out.push([d[0][0], d[0][1]], [d[1][0], d[1][1]],
             [(d[0][0] + d[1][0]) / 2, (d[0][1] + d[1][1]) / 2]);
  } else if (t === "polygon") {
    // 原版 :691-697：每个顶点 + 每条边中点
    for (let i = 0; i < d.length; i++) {
      out.push([d[i][0], d[i][1]]);
      const n = d[(i + 1) % d.length];
      out.push([(d[i][0] + n[0]) / 2, (d[i][1] + n[1]) / 2]);
    }
  }
  return out;
}

/* ── 命中检测 ── */
function distSeg(px, py, x1, y1, x2, y2) {
  const dx = x2 - x1, dy = y2 - y1;
  if (!dx && !dy) return Math.hypot(px - x1, py - y1);
  const t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)));
  return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}
function distLine(px, py, x1, y1, x2, y2) {
  const dx = x2 - x1, dy = y2 - y1;
  if (!dx && !dy) return Math.hypot(px - x1, py - y1);
  return Math.abs(dx * (y1 - py) - (x1 - px) * dy) / Math.hypot(dx, dy);
}

/**
 * 无限直线与视口矩形的交点（最多 2 个）。
 * 与原版 plot/arbitrary/geometry_canvas.py:1175-1195 `_line_viewport_intersection` 同算法：
 * 先与左右边界求交，不足 2 个再与上下边界求交。
 */
function lineViewportIntersection(x1, y1, x2, y2, vx0, vx1, vy0, vy1) {
  const dx = x2 - x1, dy = y2 - y1;
  const pts = [];
  if (Math.abs(dx) < 1e-10) {
    pts.push([x1, vy0], [x1, vy1]);
  } else if (Math.abs(dy) < 1e-10) {
    pts.push([vx0, y1], [vx1, y1]);
  } else {
    const m = dy / dx;
    const yl = y1 + m * (vx0 - x1);
    if (yl >= vy0 && yl <= vy1) pts.push([vx0, yl]);
    const yr = y1 + m * (vx1 - x1);
    if (yr >= vy0 && yr <= vy1) pts.push([vx1, yr]);
    if (pts.length < 2) {
      const xb = x1 + (vy0 - y1) / m;
      if (xb >= vx0 && xb <= vx1) pts.push([xb, vy0]);
    }
    if (pts.length < 2) {
      const xt = x1 + (vy1 - y1) / m;
      if (xt >= vx0 && xt <= vx1) pts.push([xt, vy1]);
    }
  }
  return pts;
}
function hitTest(s, mx, my, th) {
  const d = s.data, t = s.type;
  if (t === "point") return Math.hypot(mx - d[0], my - d[1]) <= th;
  if (t === "segment" || t === "vector") return distSeg(mx, my, d[0][0], d[0][1], d[1][0], d[1][1]) <= th;
  if (t === "circle") return Math.abs(Math.hypot(mx - d[0][0], my - d[0][1]) - d[1]) <= th;
  if (t === "line") return distLine(mx, my, d[0][0], d[0][1], d[1][0], d[1][1]) <= th;
  if (t === "ellipse") {
    const [, rx, ry] = d;
    if (rx < 1e-10 || ry < 1e-10) return false;
    return Math.abs(Math.hypot((mx - d[0][0]) / rx, (my - d[0][1]) / ry) - 1) * ((rx + ry) / 2) <= th;
  }
  if (t === "rect") {
    const [x1, y1] = d[0], [x2, y2] = d[1];
    const xmin = Math.min(x1, x2), xmax = Math.max(x1, x2);
    const ymin = Math.min(y1, y2), ymax = Math.max(y1, y2);
    const c = [[xmin, ymin], [xmax, ymin], [xmax, ymax], [xmin, ymax]];
    for (let i = 0; i < 4; i++) {
      const a = c[i], b = c[(i + 1) % 4];
      if (distSeg(mx, my, a[0], a[1], b[0], b[1]) <= th) return true;
    }
    return false;
  }
  if (t === "polygon" && d.length >= 3) {
    for (let i = 0; i < d.length; i++) {
      const a = d[i], b = d[(i + 1) % d.length];
      if (distSeg(mx, my, a[0], a[1], b[0], b[1]) <= th) return true;
    }
  }
  return false;
}
/** 命中检测的世界阈值：原版 _pick_shape 用 grid_step * 0.8（geometry_canvas.py:705-707） */
function worldThreshold() {
  return gridStep() * 0.8;
}

/**
 * 光标到图形的近似距离 —— 照搬原版 arbitrary/geometry_canvas.py:1136-1157
 * `_shape_approx_dist`（用于"取最近"的选中判定）。
 */
function shapeApproxDist(s, mx, my) {
  const d = s.data, t = s.type;
  if (t === "point") return Math.hypot(mx - d[0], my - d[1]);
  if (t === "segment" || t === "vector") return distSeg(mx, my, d[0][0], d[0][1], d[1][0], d[1][1]);
  if (t === "circle") return Math.abs(Math.hypot(mx - d[0][0], my - d[0][1]) - d[1]);
  if (t === "line") return distLine(mx, my, d[0][0], d[0][1], d[1][0], d[1][1]);
  if (t === "ellipse") {
    const rx = Math.abs(d[1]), ry = Math.abs(d[2]);
    if (rx < 0.01 || ry < 0.01) return Infinity;
    return Math.abs(Math.hypot((mx - d[0][0]) / rx, (my - d[0][1]) / ry) - 1) * ((rx + ry) / 2);
  }
  if (t === "rect") {
    const [x1, y1] = d[0], [x2, y2] = d[1];
    const xmin = Math.min(x1, x2), xmax = Math.max(x1, x2);
    const ymin = Math.min(y1, y2), ymax = Math.max(y1, y2);
    const c = [[xmin, ymin], [xmax, ymin], [xmax, ymax], [xmin, ymax]];
    let best = Infinity;
    for (let i = 0; i < 4; i++) {
      const a = c[i], b = c[(i + 1) % 4];
      best = Math.min(best, distSeg(mx, my, a[0], a[1], b[0], b[1]));
    }
    return best;
  }
  if (t === "polygon" && d.length >= 2) {
    let best = Infinity;
    for (let i = 0; i < d.length; i++) {
      const a = d[i], b = d[(i + 1) % d.length];
      best = Math.min(best, distSeg(mx, my, a[0], a[1], b[0], b[1]));
    }
    return best;
  }
  return Infinity;
}

/**
 * 选中图形：遍历全部可见图形，在命中者里取"近似距离最近"的那个。
 * 原版 geometry_canvas.py:705-716 `_pick_shape` 就是这个语义。
 * 旧实现是"取最后添加的命中者"，并且前一半循环（break + 用同一个阈值 bd 做无意义比较）
 * 是永远走不到实际效果的死代码。
 */
function pickShape(mx, my) {
  const th = worldThreshold();
  let best = null, bestDist = Infinity;
  for (const s of props.shapes) {
    if (!s.visible) continue;
    if (hitTest(s, mx, my, th)) {
      const dist = shapeApproxDist(s, mx, my);
      if (dist < bestDist) { bestDist = dist; best = s; }
    }
  }
  return best;
}

/* ── 图形渲染 ── */
function withAlpha(hex, a) {
  const h = String(hex || "#3498db").replace("#", "");
  const n = h.length === 3 ? h.split("").map((c) => c + c).join("") : h.padEnd(6, "0").slice(0, 6);
  return `rgba(${parseInt(n.slice(0, 2), 16)}, ${parseInt(n.slice(2, 4), 16)}, ${parseInt(n.slice(4, 6), 16)}, ${a})`;
}

function drawShape(s) {
  const v = view.value;
  const d = s.data, t = s.type;
  const selected = s.id === props.selectedId;
  // 选中高亮色 = 原版 HIGHLIGHT_COLOR #3b82f6（geometry_canvas.py:120,425）。
  // 之前用 #e74c3c，与色板首色 #c74440 同色系，选中态与"第 1 个图形的正常色"难分辨。
  const color = selected ? "#3b82f6" : s.color;
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = selected ? 3 : 1.8;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  const px = (x, y) => [mapX(v, cssW, x), mapY(v, cssH, y)];

  if (t === "point") {
    const [X, Y] = px(d[0], d[1]);
    ctx.beginPath(); ctx.arc(X, Y, 5, 0, Math.PI * 2); ctx.fill();
    if (s.label) {
      ctx.fillStyle = "#1e293b"; ctx.font = "12px -apple-system, Segoe UI, sans-serif";
      ctx.textAlign = "left"; ctx.textBaseline = "bottom";
      ctx.fillText(s.label, X + 7, Y - 6);
    }
  } else if (t === "segment") {
    const [A, B] = [px(d[0][0], d[0][1]), px(d[1][0], d[1][1])];
    ctx.beginPath(); ctx.moveTo(A[0], A[1]); ctx.lineTo(B[0], B[1]); ctx.stroke();
    for (const P of [A, B]) { ctx.beginPath(); ctx.arc(P[0], P[1], 2.5, 0, Math.PI * 2); ctx.fill(); }
    const dist = Math.hypot(d[1][0] - d[0][0], d[1][1] - d[0][1]);
    ctx.fillStyle = "#475569"; ctx.font = "11px -apple-system, Segoe UI, sans-serif";
    ctx.textAlign = "left"; ctx.textBaseline = "bottom";
    ctx.fillText(`${s.label || ""} (${dist.toFixed(2)})`, (A[0] + B[0]) / 2 + 6, (A[1] + B[1]) / 2 - 6);
  } else if (t === "vector") {
    const [A, B] = [px(d[0][0], d[0][1]), px(d[1][0], d[1][1])];
    ctx.beginPath(); ctx.moveTo(A[0], A[1]); ctx.lineTo(B[0], B[1]); ctx.stroke();
    const ang = Math.atan2(B[1] - A[1], B[0] - A[0]);
    const head = 11;
    ctx.beginPath();
    ctx.moveTo(B[0], B[1]);
    ctx.lineTo(B[0] - head * Math.cos(ang - 0.35), B[1] - head * Math.sin(ang - 0.35));
    ctx.lineTo(B[0] - head * Math.cos(ang + 0.35), B[1] - head * Math.sin(ang + 0.35));
    ctx.closePath(); ctx.fill();
    const dx = d[1][0] - d[0][0], dy = d[1][1] - d[0][1];
    ctx.fillStyle = color; ctx.font = "11px -apple-system, Segoe UI, sans-serif";
    ctx.textAlign = "left"; ctx.textBaseline = "bottom";
    ctx.fillText(`${s.label || ""}(⟨${dx.toFixed(2)}, ${dy.toFixed(2)}⟩)`.replace("⟨", "(").replace("⟩", ")"), (A[0] + B[0]) / 2 + 6, (A[1] + B[1]) / 2 - 6);
  } else if (t === "circle") {
    const [C] = [px(d[0][0], d[0][1])];
    const rPx = Math.abs(d[1]) * (cssW / Math.max(view.value.x1 - view.value.x0, 1e-12));
    ctx.beginPath(); ctx.arc(C[0], C[1], rPx, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.arc(C[0], C[1], 3, 0, Math.PI * 2); ctx.fill();
    if (s.label) {
      ctx.fillStyle = "#475569"; ctx.font = "11px -apple-system, Segoe UI, sans-serif";
      ctx.textAlign = "left"; ctx.textBaseline = "bottom";
      ctx.fillText(`${s.label} r=${Math.abs(d[1]).toFixed(2)}`, C[0] + rPx * 0.7, C[1] - rPx * 0.7);
    }
  } else if (t === "line") {
    // 无限直线：与视图矩形求交后绘制（交点算法见 lineViewportIntersection）。
    // 旧实现把"视口角点是否在视口内"当成交点判定，而四个角点恒在视口内，
    // 于是一切直线都退化成视口底边那一条线段（pts 恒为 4 个角点，只画前两个）。
    const [x1, y1] = d[0], [x2, y2] = d[1];
    const cuts = lineViewportIntersection(x1, y1, x2, y2, v.x0, v.x1, v.y0, v.y1);
    if (cuts.length >= 2) {
      const A = px(cuts[0][0], cuts[0][1]), B = px(cuts[1][0], cuts[1][1]);
      ctx.beginPath(); ctx.moveTo(A[0], A[1]); ctx.lineTo(B[0], B[1]); ctx.stroke();
    }
  } else if (t === "ellipse") {
    const [[cx, cy], rx, ry] = d;
    const sc = cssW / Math.max(view.value.x1 - view.value.x0, 1e-12);
    const C = px(cx, cy);
    ctx.beginPath(); ctx.ellipse(C[0], C[1], Math.abs(rx) * sc, Math.abs(ry) * sc, 0, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.arc(C[0], C[1], 2.5, 0, Math.PI * 2); ctx.fill();
    if (s.label) {
      ctx.fillStyle = "#475569"; ctx.font = "11px -apple-system, Segoe UI, sans-serif";
      ctx.textAlign = "left"; ctx.textBaseline = "bottom";
      ctx.fillText(`${s.label} ${Math.abs(rx).toFixed(2)}×${Math.abs(ry).toFixed(2)}`, C[0] + 8, C[1] - 8);
    }
  } else if (t === "rect") {
    const [p1, p2] = d;
    const A = px(p1[0], p1[1]), B = px(p2[0], p2[1]);
    ctx.strokeRect(Math.min(A[0], B[0]), Math.min(A[1], B[1]), Math.abs(B[0] - A[0]), Math.abs(B[1] - A[1]));
    const w = Math.abs(p2[0] - p1[0]), h = Math.abs(p2[1] - p1[1]);
    if (s.label) {
      ctx.fillStyle = "#475569"; ctx.font = "11px -apple-system, Segoe UI, sans-serif";
      ctx.textAlign = "left"; ctx.textBaseline = "bottom";
      ctx.fillText(`${s.label} ${w.toFixed(2)}×${h.toFixed(2)}`, Math.min(A[0], B[0]) + 6, Math.min(A[1], B[1]) - 6);
    }
  } else if (t === "polygon" && d.length >= 3) {
    ctx.beginPath();
    d.forEach(([X, Y], i) => {
      const P = px(X, Y);
      i === 0 ? ctx.moveTo(P[0], P[1]) : ctx.lineTo(P[0], P[1]);
    });
    ctx.closePath(); ctx.stroke();
    for (const [X, Y] of d) { const P = px(X, Y); ctx.beginPath(); ctx.arc(P[0], P[1], 2.5, 0, Math.PI * 2); ctx.fill(); }
    if (s.label) {
      const cxw = d.reduce((a, p) => a + p[0], 0) / d.length;
      const cyw = d.reduce((a, p) => a + p[1], 0) / d.length;
      const C = px(cxw, cyw);
      ctx.fillStyle = "#475569"; ctx.font = "11px -apple-system, Segoe UI, sans-serif";
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(s.label, C[0], C[1]);
    }
  }
}

/** 构造中的预览（虚线） */
function drawPreview() {
  if (state.value === "idle") return;
  const v = view.value;
  const [cx, cy] = cursor.value;
  ctx.strokeStyle = "rgba(94,129,244,.9)";
  ctx.fillStyle = "rgba(94,129,244,.9)";
  ctx.lineWidth = 1.4;
  ctx.setLineDash([5, 4]);
  const px = (x, y) => [mapX(v, cssW, x), mapY(v, cssH, y)];

  if (state.value === "awaitSecond" && tempPts.value.length) {
    const A = px(tempPts.value[0][0], tempPts.value[0][1]), B = px(cx, cy);
    ctx.beginPath(); ctx.moveTo(A[0], A[1]); ctx.lineTo(B[0], B[1]); ctx.stroke();
  } else if (state.value === "dragRadius" && tempPts.value.length) {
    const [ox, oy] = tempPts.value[0];
    const r = Math.hypot(cx - ox, cy - oy);
    const O = px(ox, oy);
    ctx.beginPath(); ctx.arc(O[0], O[1], r * (cssW / Math.max(v.x1 - v.x0, 1e-12)), 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(O[0], O[1]); ctx.lineTo(mapX(v, cssW, cx), mapY(v, cssH, cy)); ctx.stroke();
  } else if (state.value === "awaitHRad" && tempPts.value.length) {
    const [ox, oy] = tempPts.value[0];
    const O = px(ox, oy);
    ctx.beginPath(); ctx.moveTo(O[0], O[1]); ctx.lineTo(mapX(v, cssW, cx), O[1]); ctx.stroke();
  } else if (state.value === "awaitVRad" && tempPts.value.length >= 2) {
    const [ox, oy] = tempPts.value[0];
    const hx = tempPts.value[1][0];
    const rx = Math.abs(hx - ox), ry = Math.abs(cy - oy);
    if (rx > 0.01 && ry > 0.01) {
      const O = px(ox, oy);
      const sc = cssW / Math.max(v.x1 - v.x0, 1e-12);
      ctx.beginPath(); ctx.ellipse(O[0], O[1], rx * sc, ry * sc, 0, 0, Math.PI * 2); ctx.stroke();
    }
  } else if (state.value === "awaitCorner" && tempPts.value.length) {
    const [ox, oy] = tempPts.value[0];
    const A = px(ox, oy), B = px(cx, cy);
    ctx.strokeRect(Math.min(A[0], B[0]), Math.min(A[1], B[1]), Math.abs(B[0] - A[0]), Math.abs(B[1] - A[1]));
  } else if (state.value === "buildPoly" && tempPts.value.length) {
    const pts = tempPts.value.concat([[cx, cy]]);
    ctx.beginPath();
    pts.forEach(([X, Y], i) => { const P = px(X, Y); i === 0 ? ctx.moveTo(P[0], P[1]) : ctx.lineTo(P[0], P[1]); });
    ctx.stroke();
    for (const [X, Y] of tempPts.value) { const P = px(X, Y); ctx.beginPath(); ctx.arc(P[0], P[1], 3.5, 0, Math.PI * 2); ctx.fill(); }
  }
  ctx.setLineDash([]);
}

function draw() {
  if (!ctx) return;
  if (cssW <= 0) { const el = canvas.value; cssW = el?.clientWidth || 0; cssH = el?.clientHeight || 0; }
  if (cssW <= 0 || cssH <= 0) return;
  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const g = gridFor(effectiveTheme.value);
  const errs = [];
  try {
    drawCartesianGrid(ctx, cssW, cssH, view.value, g, { showGrid: true });
  } catch (e) { errs.push("grid: " + (e && e.message ? e.message : e)); }
  try {
    // 原版按类型固定 Z 序：点永远在线之上（geometry_canvas.py:441-455 点 Z=10、其余 Z=5），
    // 所以先画非点图形，再画点；此前按数组顺序画，后建的线段会盖住先前的点。
    for (const s of props.shapes) if (s.visible && s.type !== "point") drawShape(s);
    for (const s of props.shapes) if (s.visible && s.type === "point") drawShape(s);
  } catch (e) { errs.push("shapes: " + (e && e.message ? e.message : e)); }
  try {
    drawPreview();
  } catch (e) { errs.push("preview: " + (e && e.message ? e.message : e)); }
  // 提示文字
  ctx.fillStyle = gridFor(effectiveTheme.value).label;
  ctx.font = "11.5px -apple-system, Segoe UI, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "bottom";
  const hint = SNAP_HINT[state.value];
  ctx.fillText(
    `光标 (${cursor.value[0].toFixed(2)}, ${cursor.value[1].toFixed(2)})${hint ? " · " + hint : ""}` +
    ` · 网格 ${gridStep().toFixed(2)}`,
    8, cssH - 6
  );
  if (typeof window !== "undefined") {
    window.__geoErrors = errs;
    // 与 __geoErrors 同类的诊断出口：让测试能精确读到构造状态机与视图（不靠像素猜）
    window.__geoState = {
      state: state.value, tempPts: tempPts.value.length,
      cursor: [...cursor.value], view: { ...view.value }, cssW, cssH,
    };
  }
}

/* ── 鼠标交互 ── */
function worldAt(e) {
  const rect = canvas.value.getBoundingClientRect();
  return [unmapX(view.value, cssW, e.clientX - rect.left), unmapY(view.value, cssH, e.clientY - rect.top)];
}

function onMouseDown(e) {
  // 中键：原版任意工具下都临时切"拖手"平移、不改当前工具（geometry_canvas.py:724-729）
  if (e.button === 1) {
    e.preventDefault();
    drag = { kind: "pan", x: e.clientX, y: e.clientY, view: { ...view.value } };
    canvas.value.style.cursor = "grabbing";
    return;
  }
  if (e.button !== 0) return;
  const [wx, wy] = worldAt(e);
  const p = snapPoint(wx, wy);

  if (props.tool === "pan") {
    drag = { kind: "pan", x: e.clientX, y: e.clientY, view: { ...view.value } };
    canvas.value.style.cursor = "grabbing";
    return;
  }

  if (props.tool === "select") {
    const s = pickShape(wx, wy);
    emit("select", s ? s.id : null);
    if (s) drag = { kind: "shape", id: s.id, last: [wx, wy] };
    scheduleDraw();
    return;
  }

  // 构造类工具：状态机
  switch (props.tool) {
    case "point":
      emit("create", { type: "point", data: [p[0], p[1]] });
      break;
    case "segment":
    case "vector":
    case "line":
      if (state.value === "idle") { tempPts.value = [p]; state.value = "awaitSecond"; }
      else {
        if (Math.hypot(p[0] - tempPts.value[0][0], p[1] - tempPts.value[0][1]) > 1e-9) {
          emit("create", { type: props.tool, data: [tempPts.value[0], p] });
        }
        state.value = "idle"; tempPts.value = [];
      }
      break;
    case "circle":
      if (state.value === "idle") { tempPts.value = [p]; state.value = "dragRadius"; }
      else {
        const r = Math.hypot(p[0] - tempPts.value[0][0], p[1] - tempPts.value[0][1]);
        if (r > 0.01) emit("create", { type: "circle", data: [tempPts.value[0], r] });
        state.value = "idle"; tempPts.value = [];
      }
      break;
    case "ellipse":
      if (state.value === "idle") { tempPts.value = [p]; state.value = "awaitHRad"; }
      else if (state.value === "awaitHRad") { tempPts.value = [tempPts.value[0], [p[0], 0]]; state.value = "awaitVRad"; }
      else if (state.value === "awaitVRad") {
        const rx = Math.abs(tempPts.value[1][0] - tempPts.value[0][0]);
        const ry = Math.abs(p[1] - tempPts.value[0][1]);
        if (rx > 0.01 && ry > 0.01) emit("create", { type: "ellipse", data: [tempPts.value[0], rx, ry] });
        state.value = "idle"; tempPts.value = [];
      }
      break;
    case "rect":
      if (state.value === "idle") { tempPts.value = [p]; state.value = "awaitCorner"; }
      else {
        if (Math.hypot(p[0] - tempPts.value[0][0], p[1] - tempPts.value[0][1]) > 1e-9) {
          emit("create", { type: "rect", data: [tempPts.value[0], p] });
        }
        state.value = "idle"; tempPts.value = [];
      }
      break;
    case "polygon":
      if (state.value === "buildPoly") tempPts.value = tempPts.value.concat([p]);
      else { tempPts.value = [p]; state.value = "buildPoly"; }
      break;
    default: break;
  }
  scheduleDraw();
}

function onMouseMove(e) {
  const [wx, wy] = worldAt(e);
  cursor.value = snapPoint(wx, wy);
  emit("cursor", cursor.value);

  if (drag && drag.kind === "pan") {
    view.value = panBy(drag.view, cssW, cssH, e.clientX - drag.x, e.clientY - drag.y);
    scheduleDraw();
    return;
  }
  if (drag && drag.kind === "shape") {
    const dx = wx - drag.last[0], dy = wy - drag.last[1];
    emit("move", { id: drag.id, dx, dy });
    drag.last = [wx, wy];
    scheduleDraw();
    return;
  }
  // 悬停光标反馈
  if (props.tool === "select") {
    canvas.value.style.cursor = pickShape(wx, wy) ? "grab" : "default";
  } else if (props.tool === "pan") {
    canvas.value.style.cursor = "grab";
  } else {
    canvas.value.style.cursor = "crosshair";
  }
  scheduleDraw();
}

function onMouseUp() {
  if (drag && drag.kind === "pan") canvas.value.style.cursor = "grab";
  drag = null;
}

/**
 * 双击 / 右键。
 * 原版 geometry_canvas.py:731-737：右键在"构造多边形且已 ≥3 点"时提交，否则**取消当前构造**；
 * 此前非多边形场景直接 return，既不取消构造也不阻止默认行为（会弹出 WebView2 右键菜单）。
 */
function closePolygon(e) {
  e.preventDefault();
  if (props.tool === "polygon" && state.value === "buildPoly") {
    const pts = tempPts.value.slice();
    // DOM 双击会在 dblclick 之前投递**两次** mousedown（每次都会追加一个顶点），
    // 所以要把所有与前一顶点重合的点都去掉，而不是只弹一个。
    while (
      pts.length >= 2 &&
      Math.hypot(pts[pts.length - 1][0] - pts[pts.length - 2][0],
                 pts[pts.length - 1][1] - pts[pts.length - 2][1]) < gridStep() * 0.25
    ) {
      pts.pop();
    }
    if (pts.length >= 3) emit("create", { type: "polygon", data: pts });
    state.value = "idle"; tempPts.value = [];
    scheduleDraw();
    return;
  }
  // 非多边形构造：右键 = 取消（原版行为）
  cancelConstruction();
}

function onWheel(e) {
  const rect = canvas.value.getBoundingClientRect();
  const px = e.clientX - rect.left, py = e.clientY - rect.top;
  // 原版滚轮步长 1.15（geometry_canvas.py:816-823）；此前是 0.9/1.11
  view.value = zoomAt(view.value, cssW, cssH, px, py, e.deltaY < 0 ? 1 / 1.15 : 1.15);
  scheduleDraw();
}

/** 工具切换时取消未完成的构造，并清空选中（原版 set_tool 会 _set_selection(None)，:1033-1043） */
watch(() => props.tool, () => {
  state.value = "idle";
  tempPts.value = [];
  emit("select", null);
  scheduleDraw();
});
watch(() => [props.shapes, props.selectedId, props.theme], scheduleDraw, { deep: true });

function cancelConstruction() { state.value = "idle"; tempPts.value = []; scheduleDraw(); }
function resetView() {
  const el = canvas.value;
  const w = el?.clientWidth || cssW || 1;
  const h = el?.clientHeight || cssH || 1;
  view.value = equalAspectView(-8, 8, 0, w, h);   // 原版回落 INITIAL_VIEW x∈[-8,8] 并保持等比
  scheduleDraw();
}
function getState() {
  return { state: state.value, tempPts: tempPts.value.length, view: { ...view.value }, cssW, cssH };
}
defineExpose({ cancelConstruction, resetView, getState, scheduleDraw, canvasEl: () => canvas.value });

let ro = null;
// 配色深浅变化时重绘网格与坐标轴（画布不认 CSS 变量，见 bridge.js 的说明）
const modeTick = ref(0);
const effectiveTheme = computed(() => { modeTick.value; return plotMode(props.theme); });
const offAppearance = onAppearanceChange(() => { modeTick.value++; scheduleDraw(); });

onMounted(() => {
  ctx = canvas.value.getContext("2d");
  resize();
  if (window.ResizeObserver) { ro = new ResizeObserver(resize); ro.observe(canvas.value); }
});
onBeforeUnmount(() => {
  if (ro) ro.disconnect();
  cancelAnimationFrame(raf);
  offAppearance();
});
</script>

<template>
  <canvas
    ref="canvas"
    class="geo-canvas"
    @mousedown="onMouseDown"
    @mousemove="onMouseMove"
    @mouseup="onMouseUp"
    @mouseleave="onMouseUp"
    @dblclick="closePolygon"
    @contextmenu="closePolygon"
    @wheel.prevent="onWheel"
  />
</template>

<style scoped>
.geo-canvas { display: block; width: 100%; height: 100%; touch-action: none; }
</style>
