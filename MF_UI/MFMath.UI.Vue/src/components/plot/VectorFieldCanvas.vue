<script setup>
/**
 * VectorFieldCanvas — 向量场渲染
 *  · 网格点上绘制箭头（dx、dy 由 C++ 引擎 expr_eval_grid 双网格求值）
 *  · 支持箭头归一化（只看方向）与按模长着色（颜色编码强度）
 *  · 复用 2D 视图数学：拖拽平移、光标中心缩放、nice 步长网格
 */
import { ref, computed, onMounted, onBeforeUnmount, watch } from "vue";
import { gridFor } from "../../lib/plot/colors.js";
import { plotMode, onAppearanceChange } from "../../lib/bridge.js";
import {
  mapX, mapY, unmapX, unmapY, zoomAt, panBy, gridSteps, formatTick, viewW, viewH,
} from "../../lib/plot/view.js";

const props = defineProps({
  /** {xs, ys, dx[], dy[]}：网格与两个分量（行优先，index = j*nx + i） */
  field: { type: Object, default: null },
  view: { type: Object, default: () => ({ x0: -5, y0: -5, x1: 5, y1: 5 }) },
  /**
   * 深浅色。**不要给 "light" 默认值**：视图层从不传这个 prop，给了默认值就永远
   * 走浅色（bridge.js:163-177 记录的历史事故）。留空 → 跟随当前配色。
   */
  theme: { type: String, default: undefined },
  /** 箭头长度缩放（0 表示自动） */
  arrowScale: { type: Number, default: 0 },
  /**
   * 归一化：所有箭头等长。
   * 默认 true —— 原版 vector_field/workspace.py:185 用 quiver(X,Y,U/M,V/M,M,...)，
   * 方向是单位向量、长度恒定，强度由颜色（模长）编码。
   */
  normalize: { type: Boolean, default: true },
  /** 按模长着色 */
  colorByMagnitude: { type: Boolean, default: true },
  showGrid: { type: Boolean, default: true },
});
const emit = defineEmits(["update:view"]);

const canvas = ref(null);
let ctx = null;
let cssW = 0, cssH = 0, raf = 0;
let drag = null;
let hover = null;

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

/** 模长 → 颜色（蓝 → 青 → 绿 → 黄 → 红） */
function magColor(t) {
  const stops = [
    [0.0, [59, 130, 246]],
    [0.35, [6, 182, 212]],
    [0.65, [16, 185, 129]],
    [1.0, [239, 68, 68]],
  ];
  const x = Math.max(0, Math.min(1, t));
  for (let i = 0; i + 1 < stops.length; i++) {
    const [t0, c0] = stops[i], [t1, c1] = stops[i + 1];
    if (x >= t0 && x <= t1) {
      const k = t1 === t0 ? 0 : (x - t0) / (t1 - t0);
      return `rgb(${Math.round(c0[0] + (c1[0] - c0[0]) * k)}, ${Math.round(c0[1] + (c1[1] - c0[1]) * k)}, ${Math.round(c0[2] + (c1[2] - c0[2]) * k)})`;
    }
  }
  return "rgb(239,68,68)";
}

function drawGrid(g) {
  ctx.fillStyle = g.bg;
  ctx.fillRect(0, 0, cssW, cssH);
  const v = props.view;
  const { major, minor } = gridSteps(v, cssW, cssH);
  // 刻度索引声明在 if 之外：后面的刻度标签绘制也要用（曾因作用域错误导致参考系不绘制）
  const k0 = Math.ceil(v.x0 / major), k1 = Math.floor(v.x1 / major);
  const l0 = Math.ceil(v.y0 / major), l1 = Math.floor(v.y1 / major);

  if (props.showGrid) {
    ctx.strokeStyle = g.minor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    const i0 = Math.ceil(v.x0 / minor), i1 = Math.floor(v.x1 / minor);
    for (let i = i0; i <= i1 && i1 - i0 < 4000; i++) {
      if (Math.abs((i * minor) / major - Math.round((i * minor) / major)) < 1e-9) continue;
      const px = Math.round(mapX(v, cssW, i * minor)) + 0.5;
      ctx.moveTo(px, 0); ctx.lineTo(px, cssH);
    }
    const j0 = Math.ceil(v.y0 / minor), j1 = Math.floor(v.y1 / minor);
    for (let j = j0; j <= j1 && j1 - j0 < 4000; j++) {
      if (Math.abs((j * minor) / major - Math.round((j * minor) / major)) < 1e-9) continue;
      const py = Math.round(mapY(v, cssH, j * minor)) + 0.5;
      ctx.moveTo(0, py); ctx.lineTo(cssW, py);
    }
    ctx.stroke();

    ctx.strokeStyle = g.major;
    ctx.beginPath();
    for (let k = k0; k <= k1 && k1 - k0 < 2000; k++) {
      const px = Math.round(mapX(v, cssW, k * major)) + 0.5;
      ctx.moveTo(px, 0); ctx.lineTo(px, cssH);
    }
    for (let l = l0; l <= l1 && l1 - l0 < 2000; l++) {
      const py = Math.round(mapY(v, cssH, l * major)) + 0.5;
      ctx.moveTo(0, py); ctx.lineTo(cssW, py);
    }
    ctx.stroke();
  }

  // 坐标轴
  const axisY = mapY(v, cssH, 0), axisX = mapX(v, cssW, 0);
  ctx.strokeStyle = g.axis;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  if (axisY >= 0 && axisY <= cssH) { ctx.moveTo(0, axisY); ctx.lineTo(cssW, axisY); }
  if (axisX >= 0 && axisX <= cssW) { ctx.moveTo(axisX, 0); ctx.lineTo(axisX, cssH); }
  ctx.stroke();

  // 刻度
  ctx.fillStyle = g.label;
  ctx.font = "11px -apple-system, Segoe UI, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  const ly = Math.min(Math.max(axisY + 4, 2), cssH - 16);
  for (let k = k0; k <= k1 && k1 - k0 < 200; k++) {
    if (k === 0) continue;
    const px = mapX(v, cssW, k * major);
    if (px < 16 || px > cssW - 16) continue;
    ctx.fillText(formatTick(k * major, major), px, ly);
  }
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  const lx = Math.min(Math.max(axisX - 6, 26), cssW - 4);
  for (let l = l0; l <= l1 && l1 - l0 < 200; l++) {
    if (l === 0) continue;
    const py = mapY(v, cssH, l * major);
    if (py < 10 || py > cssH - 10) continue;
    ctx.fillText(formatTick(l * major, major), lx, py);
  }
}

function drawField() {
  const f = props.field;
  if (!f || !f.xs || !f.ys || !f.dx || !f.dy) return 0;
  const v = props.view;
  const nx = f.xs.length, ny = f.ys.length;
  let arrowCount = 0;
  const dxWorld = viewW(v) / Math.max(cssW, 1);   // 每像素多少世界单位

  // 模长范围（用于归一化与着色）
  let mmax = 0;
  const mags = new Array(nx * ny);
  for (let i = 0; i < nx * ny; i++) {
    const dx = f.dx[i], dy = f.dy[i];
    const m = (typeof dx === "number" && typeof dy === "number" && isFinite(dx) && isFinite(dy))
      ? Math.hypot(dx, dy) : NaN;
    mags[i] = m;
    if (isFinite(m) && m > mmax) mmax = m;
  }
  if (mmax <= 0) return 0;

  // 箭头基础长度：取相邻网格点间距的一半（自适应）
  const spacingPx = nx > 1 ? (cssW / (nx - 1)) : 40;
  const baseLen = props.arrowScale > 0
    ? props.arrowScale * spacingPx
    : spacingPx * 0.85;

  ctx.lineWidth = 1.4;
  ctx.lineCap = "round";
  for (let j = 0; j < ny; j++) {
    for (let i = 0; i < nx; i++) {
      const idx = j * nx + i;
      const m = mags[idx];
      if (!isFinite(m) || m === 0) continue;
      const dx = f.dx[idx], dy = f.dy[idx];
      const px = mapX(v, cssW, f.xs[i]);
      const py = mapY(v, cssH, f.ys[j]);
      if (px < -20 || px > cssW + 20 || py < -20 || py > cssH + 20) continue;

      // 箭头长度：按模长相对最大值缩放（不归一化时体现强度差异）
      const lenPx = props.normalize ? baseLen : baseLen * (m / mmax);
      const ux = dx / m, uy = dy / m;
      // 屏幕 y 向下，世界 y 向上 → 箭头的竖直分量取反
      const ex = px + ux * lenPx;
      const ey = py - uy * lenPx;

      const color = props.colorByMagnitude ? magColor(m / mmax) : (effectiveTheme.value === "dark" ? "#60a5fa" : "#2d70b3");
      ctx.strokeStyle = color;
      ctx.fillStyle = color;

      ctx.beginPath();
      ctx.moveTo(px, py);
      ctx.lineTo(ex, ey);
      ctx.stroke();

      // 箭头头部
      const ang = Math.atan2(ey - py, ex - px);
      const head = Math.max(3.5, Math.min(7, lenPx * 0.35));
      ctx.beginPath();
      ctx.moveTo(ex, ey);
      ctx.lineTo(ex - head * Math.cos(ang - 0.42), ey - head * Math.sin(ang - 0.42));
      ctx.lineTo(ex - head * Math.cos(ang + 0.42), ey - head * Math.sin(ang + 0.42));
      ctx.closePath();
      ctx.fill();
      arrowCount++;
    }
  }

  // 悬停读数：该点场向量
  if (hover) {
    ctx.fillStyle = effectiveTheme.value === "dark" ? "#9aa4b2" : "#64748b";
    ctx.font = "11.5px -apple-system, Segoe UI, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "bottom";
    ctx.fillText(`(${hover[0].toFixed(2)}, ${hover[1].toFixed(2)})`, 8, cssH - 6);
  }
  return arrowCount;
}

function draw() {
  if (cssW <= 0) { const el = canvas.value; cssW = el?.clientWidth || 0; cssH = el?.clientHeight || 0; }
  const diag = { w: cssW, h: cssH, hasCtx: !!ctx, hasField: !!props.field,
                 fieldLen: props.field && props.field.dx ? props.field.dx.length : 0,
                 drawn: 0, errors: [] };
  if (!ctx) { if (typeof window !== "undefined") window.__vfDiag = diag; return; }
  if (cssW <= 0 || cssH <= 0) { if (typeof window !== "undefined") window.__vfDiag = diag; return; }
  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  try {
    const g = gridFor(effectiveTheme.value);
    drawGrid(g);
  } catch (e) { diag.errors.push("grid: " + (e && e.message ? e.message : e)); }
  try {
    diag.drawn = drawField();
  } catch (e) { diag.errors.push("field: " + (e && e.message ? e.message : e)); }
  if (typeof window !== "undefined") window.__vfDiag = diag;
}

/* ── 交互 ── */
function onMouseDown(e) {
  if (e.button !== 0) return;
  drag = { x: e.clientX, y: e.clientY, view: { ...props.view } };
  canvas.value.style.cursor = "grabbing";
}
function onMouseMove(e) {
  const rect = canvas.value.getBoundingClientRect();
  const px = e.clientX - rect.left, py = e.clientY - rect.top;
  hover = [unmapX(props.view, cssW, px), unmapY(props.view, cssH, py)];
  if (drag) {
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    emit("update:view", panBy(drag.view, cssW, cssH, dx, dy));
    scheduleDraw();
    return;
  }
  scheduleDraw();
}
function onMouseUp() { drag = null; if (canvas.value) canvas.value.style.cursor = "grab"; }
function onWheel(e) {
  e.preventDefault();
  const rect = canvas.value.getBoundingClientRect();
  const px = e.clientX - rect.left, py = e.clientY - rect.top;
  const factor = e.deltaY < 0 ? 0.88 : 1.14;
  emit("update:view", zoomAt(props.view, cssW, cssH, px, py, factor));
  scheduleDraw();
}
function onMouseLeave() { hover = null; onMouseUp(); scheduleDraw(); }

function canvasSize() { return { w: cssW, h: cssH }; }
defineExpose({ canvasSize, scheduleDraw });

let ro = null;
// 配色深浅变化时重绘（画布不认 CSS 变量，见 bridge.js 的说明）
const modeTick = ref(0);
const effectiveTheme = computed(() => { modeTick.value; return plotMode(props.theme); });
const offAppearance = onAppearanceChange(() => { modeTick.value++; scheduleDraw(); });

onMounted(() => {
  ctx = canvas.value.getContext("2d");
  canvas.value.style.cursor = "grab";
  resize();
  if (window.ResizeObserver) { ro = new ResizeObserver(resize); ro.observe(canvas.value); }
});
onBeforeUnmount(() => {
  if (ro) ro.disconnect();
  cancelAnimationFrame(raf);
  offAppearance();
});

watch(() => [props.field, props.view, props.theme, props.normalize, props.colorByMagnitude,
             props.showGrid, props.arrowScale], scheduleDraw, { deep: true });
</script>

<template>
  <canvas
    ref="canvas"
    class="vf-canvas"
    @mousedown="onMouseDown"
    @mousemove="onMouseMove"
    @mouseup="onMouseUp"
    @mouseleave="onMouseLeave"
    @wheel="onWheel"
  />
</template>

<style scoped>
.vf-canvas { display: block; width: 100%; height: 100%; touch-action: none; }
</style>
