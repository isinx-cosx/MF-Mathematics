import { useCallback, useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { plotMode, onAppearanceChange } from "@shared/bridge.js";
import {
  mapX, mapY, unmapX, unmapY, viewH, zoomAt, panBy, gridSteps, formatTick,
} from "@shared/plot/view.js";
import { gridFor } from "@shared/plot/colors.js";
import { drawPolarGrid } from "@shared/plot/cartesian.js";
import { resolveExpr } from "@shared/plot/plotMath.js";
import "../styles/plot-canvas.css";

export type View = { x0: number; x1: number; y0: number; y1: number };
export type Sample = [number, number] | null;

/**
 * parseExpr() 的解析结果。plotMath.js 的 JSDoc `@returns` 只列了公共字段，
 * 而实现里 inequality / region 这两类分支**额外挂了** op / axis / boundary
 * （见 plotMath.js:140-177：axis 取 "y"/"x"/"xy"，inequality 另有 boundary 边界表达式）。
 * 这里把这几个"按类型才出现"的字段按实际情况声明成可选：类型没对上时访问它们
 * 得到 undefined，与运行时一致，不需要断言也不需要删掉访问。
 */
export type ParsedExpr = {
  type: string;
  valid: boolean;
  error: string | null;
  var: string;
  body: string;
  radius: string | null;
  xsExpr: string | null;
  ysExpr: string | null;
  params: string[];
  display: string;
  /** 不等式/区域的比较运算符（parseExpr 已把 >= / <= 归一成 ≥ / ≤） */
  op?: ">" | "<" | "≥" | "≤";
  /** 不等式的分界轴："y" = y ≷ f(x)，"x" = x ≷ g(y)；区域为 "xy" */
  axis?: "x" | "y" | "xy";
  /** 不等式的边界表达式（引擎写法） */
  boundary?: string;
};

export type Curve = {
  id: number;
  text?: string;
  color: string;
  visible: boolean;
  emphasis?: boolean;
};
export type UserPoint = { id: number; x: number; y: number; color?: string; curveId?: number };
export type Intersection = { x: number; y: number; xLabel?: string; yLabel?: string };
export type Extremum = { x: number; y: number; kind: "max" | "min" };

type Props = {
  view: View;
  onViewChange: (v: View) => void;
  curves: Curve[];
  samples: Record<number, Sample[]>;
  /** 二元网格（隐式方程等值线 / 二元区域）：由 expr_eval_grid 采样后传进来 */
  grids?: Record<number, GridData>;
  points?: UserPoint[];
  intersections?: Intersection[];
  extrema?: Extremum[];
  gridMode?: "rect" | "polar";
  showGrid?: boolean;
  theme?: string;
  onSizeChange?: (w: number, h: number) => void;
  onPickPoint?: (x: number, y: number, curveId: number) => void;
  /** 拖动已有点：把光标的世界坐标交给父组件，由它按曲线类型吸附 */
  onDragPoint?: (id: number, world: [number, number]) => void;
  canvasRef?: RefObject<HTMLCanvasElement | null>;
};

const fmt = (n: number) => (Math.abs(n) < 1e-10 ? "0" : String(Math.round(n * 1e4) / 1e4));

/* ── 画布坐标安全钳制 ────────────────────────────────────────────────────────
 * Canvas 2D 内部用 float32 存路径点。世界坐标换算到屏幕后一旦到 1e38 量级
 * （更别说溢出成 Infinity），**Skia 会把整条路径全部丢掉** —— 不是画到画外，
 * 而是这一段路径一个像素都不出。
 *
 * 实测（y=e^x，窗口 620x560，画布 346x252）：
 *   视图 [-61.59, 61.47]×[-44.72, 44.91] → 采样上界 x=92.23 → e^92.23≈1.14e40
 *   → 屏幕 y ≈ -3.2e40（float32 溢出）→ 网格照画（非背景 37441 px）、
 *     曲线 0 px、无任何异常；视图再缩回去才恢复。
 * 前 12 档缩小（屏幕 y 到 2.19e35）都正常。
 *
 * 钳到 ±1e6：约画布尺寸（~1000px）的 1000 倍，远超可视区，
 * 而相对于 1e40 的真值又微不足道 —— 可见部分的几何变化远小于 1 像素。 */
const PX_LIMIT = 1e6;
function clampPx(v: number): number {
  return v > PX_LIMIT ? PX_LIMIT : v < -PX_LIMIT ? -PX_LIMIT : v;
}

/* ── 网格与坐标轴（与 Vue 版 PlotCanvas 的 drawGrid 同一套参数）───────────── */
function drawGrid(
  ctx: CanvasRenderingContext2D, w: number, h: number, view: View,
  g: ReturnType<typeof gridFor>, gridMode: "rect" | "polar", showGrid: boolean,
  hover: [number, number] | null
) {
  /* 每帧先铺底色：不铺的话平移/缩放后上一帧的网格与曲线会残留成鬼影 */
  ctx.fillStyle = g.bg;
  ctx.fillRect(0, 0, w, h);

  const { major, minor } = gridSteps(view, w, h);

  if (gridMode === "polar") {
    drawPolarGrid(ctx, w, h, view, g, major, showGrid);
    drawHoverReadout(ctx, h, g, hover);
    return;
  }

  if (showGrid) {
    ctx.strokeStyle = g.minor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    const i0 = Math.ceil(view.x0 / minor), i1 = Math.floor(view.x1 / minor);
    if (i1 - i0 < 4000) {
      for (let i = i0; i <= i1; i++) {
        const x = i * minor;
        if (Math.abs(x / major - Math.round(x / major)) < 1e-9) continue;
        const px = Math.round(mapX(view, w, x)) + 0.5;
        ctx.moveTo(px, 0); ctx.lineTo(px, h);
      }
    }
    const j0 = Math.ceil(view.y0 / minor), j1 = Math.floor(view.y1 / minor);
    if (j1 - j0 < 4000) {
      for (let j = j0; j <= j1; j++) {
        const y = j * minor;
        if (Math.abs(y / major - Math.round(y / major)) < 1e-9) continue;
        const py = Math.round(mapY(view, h, y)) + 0.5;
        ctx.moveTo(0, py); ctx.lineTo(w, py);
      }
    }
    ctx.stroke();
  }

  const k0 = Math.ceil(view.x0 / major), k1 = Math.floor(view.x1 / major);
  const l0 = Math.ceil(view.y0 / major), l1 = Math.floor(view.y1 / major);

  if (showGrid) {
    ctx.strokeStyle = g.major;
    ctx.beginPath();
    if (k1 - k0 < 2000) {
      for (let k = k0; k <= k1; k++) {
        const px = Math.round(mapX(view, w, k * major)) + 0.5;
        ctx.moveTo(px, 0); ctx.lineTo(px, h);
      }
    }
    if (l1 - l0 < 2000) {
      for (let l = l0; l <= l1; l++) {
        const py = Math.round(mapY(view, h, l * major)) + 0.5;
        ctx.moveTo(0, py); ctx.lineTo(w, py);
      }
    }
    ctx.stroke();
  }

  const axisY = mapY(view, h, 0);
  const axisX = mapX(view, w, 0);
  ctx.strokeStyle = g.axis;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  if (axisY >= 0 && axisY <= h) { ctx.moveTo(0, axisY); ctx.lineTo(w, axisY); }
  if (axisX >= 0 && axisX <= w) { ctx.moveTo(axisX, 0); ctx.lineTo(axisX, h); }
  ctx.stroke();

  ctx.fillStyle = g.label;
  ctx.font = "11px -apple-system, Segoe UI, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  const labelY = Math.min(Math.max(axisY + 4, 2), h - 16);
  if (k1 - k0 < 200) {
    for (let k = k0; k <= k1; k++) {
      if (k === 0) continue;
      const x = k * major;
      const px = mapX(view, w, x);
      if (px < 16 || px > w - 16) continue;
      ctx.fillText(formatTick(x, major), px, labelY);
    }
  }
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  const labelX = Math.min(Math.max(axisX - 6, 26), w - 4);
  if (l1 - l0 < 200) {
    for (let l = l0; l <= l1; l++) {
      if (l === 0) continue;
      const y = l * major;
      const py = mapY(view, h, y);
      if (py < 10 || py > h - 10) continue;
      ctx.fillText(formatTick(y, major), labelX, py);
    }
  }
  if (axisX >= 0 && axisX <= w && axisY >= 0 && axisY <= h) {
    ctx.textAlign = "right"; ctx.textBaseline = "top";
    ctx.fillText("0", axisX - 5, axisY + 3);
  }

  drawHoverReadout(ctx, h, g, hover);
}

function drawHoverReadout(
  ctx: CanvasRenderingContext2D, h: number,
  g: ReturnType<typeof gridFor>, hover: [number, number] | null
) {
  if (!hover) return;
  ctx.textAlign = "left";
  ctx.textBaseline = "bottom";
  ctx.fillStyle = g.label;
  ctx.fillText(`(${fmt(hover[0])}, ${fmt(hover[1])})`, 8, h - 6);
}

/** 曲线。断点判据用**世界坐标符号翻转**，不用屏幕像素跳变
 * （后者会把 e^x 这类陡而连续的曲线整段丢掉 —— 大 |x| 处画不全的根因）。 */
function drawCurves(
  ctx: CanvasRenderingContext2D, w: number, h: number, view: View,
  curves: Curve[], samples: Record<number, Sample[]>
) {
  const spanY = Math.abs(viewH(view)) || 1;
  const far = (t: number) => Math.abs(t) > spanY * 4;

  for (const c of curves) {
    if (!c.visible) continue;
    const pts = samples[c.id];
    if (!pts || pts.length < 2) continue;
    ctx.strokeStyle = c.color;
    ctx.lineWidth = c.emphasis ? 4 : 2.5;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.beginPath();
    let drawing = false;
    let lastY: number | null = null;
    for (const p of pts) {
      if (!p) { drawing = false; lastY = null; continue; }
      const [x, y] = p;
      if (!Number.isFinite(x) || !Number.isFinite(y)) { drawing = false; lastY = null; continue; }
      /* ⚠ 必须钳制：不钳的话，像 e^x 这种"采样范围里有一段天文数字"的曲线，
       * 屏幕坐标会到 1e38 量级/溢出 float32，Skia 直接丢掉整条路径（曲线凭空消失）。 */
      const px = clampPx(mapX(view, w, x)), py = clampPx(mapY(view, h, y));
      if (drawing && lastY !== null && far(lastY) && far(y) && Math.sign(lastY) !== Math.sign(y)) {
        drawing = false;
      }
      if (!drawing) { ctx.moveTo(px, py); drawing = true; } else ctx.lineTo(px, py);
      lastY = y;
    }
    ctx.stroke();
  }
}

/* ── 二元网格：区域填充 / 隐式等值线（移植自 Vue 版 PlotCanvas）────────────────
 * 数据来自引擎 `expr_eval_grid`（行优先，nx×ny），由 usePlotSampling 采样后传进来。
 * 这几段必须与 Vue 版逐字对应：判据、颜色透明度、marching squares 的鞍点分支
 * 任何一处不同，同一份数据在两个版本上就会画出不同的图。 */
type GridData = { xs: number[]; ys: number[]; values: number[] };

/** 十六进制色 → rgba（半透明区域填充；与 Vue 版 PlotCanvas.withAlpha 同一实现） */
function withAlpha(hex: string, a: number): string {
  const h = String(hex || "#c74440").replace("#", "");
  const n = h.length === 3 ? h.split("").map((c) => c + c).join("") : h.padEnd(6, "0").slice(0, 6);
  const r = parseInt(n.slice(0, 2), 16), g = parseInt(n.slice(2, 4), 16), b = parseInt(n.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

/** 二元区域填充（如 x²+y²<4）：逐格判定格心符号是否满足不等式 */
function drawRegions(
  ctx: CanvasRenderingContext2D, w: number, h: number, view: View,
  curves: Curve[], grids: Record<number, GridData>
) {
  for (const c of curves) {
    if (c.visible === false) continue;
    const p: ParsedExpr = resolveExpr(c.text);
    if (!p || p.type !== "region" || !p.valid) continue;
    const g = grids[c.id];
    if (!g || !g.values) continue;

    const nx = g.xs.length, ny = g.ys.length;
    if (nx < 2 || ny < 2) continue;
    const cellW = w / (nx - 1), cellH = h / (ny - 1);
    ctx.fillStyle = withAlpha(c.color, c.emphasis ? 0.22 : 0.16);

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
        ctx.fillRect(mapX(view, w, g.xs[i]), mapY(view, h, g.ys[j + 1]), cellW + 1, cellH + 1);
      }
    }
  }
}

/** 隐式方程等值线（如 x²+y²=4）—— marching squares */
function drawImplicit(
  ctx: CanvasRenderingContext2D, w: number, h: number, view: View,
  g: GridData, color: string, emphasis?: boolean
) {
  const nx = g.xs.length, ny = g.ys.length;
  if (nx < 2 || ny < 2) return;

  const sx = new Array<number>(nx), sy = new Array<number>(ny);
  for (let i = 0; i < nx; i++) sx[i] = clampPx(mapX(view, w, g.xs[i]));
  for (let j = 0; j < ny; j++) sy[j] = clampPx(mapY(view, h, g.ys[j]));

  ctx.strokeStyle = color;
  ctx.lineWidth = emphasis ? 3 : 2.2;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.beginPath();

  /** 两点间线性插值出 f=0 的位置（返回 0..1） */
  const lerp = (fa: number, fb: number) => {
    const denom = fa - fb;
    if (Math.abs(denom) < 1e-12) return 0.5;
    return Math.max(0, Math.min(1, fa / denom));
  };

  for (let j = 0; j + 1 < ny; j++) {
    for (let i = 0; i + 1 < nx; i++) {
      const f00 = g.values[j * nx + i];
      const f10 = g.values[j * nx + i + 1];
      const f01 = g.values[(j + 1) * nx + i];
      const f11 = g.values[(j + 1) * nx + i + 1];
      if (![f00, f10, f01, f11].every((t) => typeof t === "number" && isFinite(t))) continue;

      let idx = 0;
      if (f00 > 0) idx |= 1;
      if (f10 > 0) idx |= 2;
      if (f11 > 0) idx |= 4;
      if (f01 > 0) idx |= 8;
      if (idx === 0 || idx === 15) continue;

      const bx = sx[i] + (sx[i + 1] - sx[i]) * lerp(f00, f10), by = sy[j];
      const rx = sx[i + 1], ry = sy[j] + (sy[j + 1] - sy[j]) * lerp(f10, f11);
      const tx = sx[i] + (sx[i + 1] - sx[i]) * lerp(f01, f11), ty = sy[j + 1];
      const lx = sx[i], ly = sy[j] + (sy[j + 1] - sy[j]) * lerp(f00, f01);

      const seg = (x1: number, y1: number, x2: number, y2: number) => {
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
      };
      switch (idx) {
        case 1: case 14: seg(lx, ly, bx, by); break;
        case 2: case 13: seg(bx, by, rx, ry); break;
        case 3: case 12: seg(lx, ly, rx, ry); break;
        case 4: case 11: seg(rx, ry, tx, ty); break;
        case 5: seg(lx, ly, tx, ty); seg(bx, by, rx, ry); break; // 鞍点
        case 6: case 9: seg(bx, by, tx, ty); break;
        case 7: case 8: seg(lx, ly, tx, ty); break;
        case 10: seg(lx, ly, bx, by); seg(rx, ry, tx, ty); break; // 鞍点
        default: break;
      }
    }
  }
  ctx.stroke();
}

function drawImplicits(
  ctx: CanvasRenderingContext2D, w: number, h: number, view: View,
  curves: Curve[], grids: Record<number, GridData>
) {
  for (const c of curves) {
    if (c.visible === false) continue;
    const p: ParsedExpr = resolveExpr(c.text);
    if (!p || p.type !== "implicit" || !p.valid) continue;
    const g = grids[c.id];
    if (!g) continue;
    drawImplicit(ctx, w, h, view, g, c.color, c.emphasis);
  }
}

/** 不等式区域填充（对齐 Desmos：半透明色块 + 实线边界）
 * 支持 y ≷ f(x)（上下界）与 x ≷ g(y)（左右界）；边界曲线已由采样阶段给出。 */
function drawInequalities(
  ctx: CanvasRenderingContext2D, w: number, h: number, view: View,
  curves: Curve[], samples: Record<number, Sample[]>
) {
  for (const c of curves) {
    if (c.visible === false) continue;
    const p: ParsedExpr = resolveExpr(c.text);
    if (!p || p.type !== "inequality" || !p.valid) continue;
    const pts = samples[c.id];
    if (!pts || pts.length < 2) continue;

    ctx.fillStyle = withAlpha(c.color, c.emphasis ? 0.22 : 0.16);

    const valid = (q: Sample): q is [number, number] =>
      !!q && Number.isFinite(q[0]) && Number.isFinite(q[1]);

    if (p.axis === "y") {
      const upper = p.op === ">" || p.op === "≥";
      const edge = upper ? 0 : h;
      ctx.beginPath();
      let started = false;
      for (const q of pts) {
        if (!valid(q)) continue;                       // 断点：不参与填充
        const px = mapX(view, w, q[0]);
        const py = Math.max(-h, Math.min(2 * h, mapY(view, h, q[1])));  // 钳制，避免巨值路径
        if (!started) {
          ctx.moveTo(px, edge);
          ctx.lineTo(px, py);
          started = true;
        } else ctx.lineTo(px, py);
      }
      if (started) {
        const last = [...pts].reverse().find(valid);
        if (last) ctx.lineTo(clampPx(mapX(view, w, last[0])), edge);
        ctx.closePath();
        ctx.fill();
      }
    } else if (p.axis === "x") {
      const right = p.op === ">" || p.op === "≥";
      const edge = right ? w : 0;
      ctx.beginPath();
      let started = false;
      for (const q of pts) {
        if (!valid(q)) continue;
        const px = Math.max(-w, Math.min(2 * w, mapX(view, w, q[0])));
        const py = mapY(view, h, q[1]);
        if (!started) {
          ctx.moveTo(edge, py);
          ctx.lineTo(px, py);
          started = true;
        } else ctx.lineTo(px, py);
      }
      if (started) {
        const last = [...pts].reverse().find(valid);
        if (last) ctx.lineTo(edge, clampPx(mapY(view, h, last[1])));
        ctx.closePath();
        ctx.fill();
      }
    }

    // 边界线（Desmos 的区域边界用实线）——断点判据与 drawCurves 完全一致
    ctx.strokeStyle = c.color;
    ctx.lineWidth = c.emphasis ? 3 : 2;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.beginPath();
    let drawing = false;
    let lastY: number | null = null;
    const spanY = Math.abs(viewH(view)) || 1;
    const far = (t: number) => Math.abs(t) > spanY * 4;
    for (const q of pts) {
      if (!valid(q)) { drawing = false; lastY = null; continue; }
      const [x, y] = q;
      const px = clampPx(mapX(view, w, x)), py = clampPx(mapY(view, h, y));
      if (drawing && lastY !== null && far(lastY) && far(y) && Math.sign(lastY) !== Math.sign(y)) {
        drawing = false;
      }
      if (!drawing) { ctx.moveTo(px, py); drawing = true; } else ctx.lineTo(px, py);
      lastY = y;
    }
    ctx.stroke();
  }
}

/** 悬停追踪：命中曲线时在**曲线上的点**画实心圆 + 白圈 + 坐标（Desmos 行为）。
 * 与 Vue 版 drawTrace 同一实现；不是"角落里的坐标读数"——那个看不出对应曲线上的哪个点。 */
function drawTrace(
  ctx: CanvasRenderingContext2D, w: number, h: number, view: View,
  g: ReturnType<typeof gridFor>,
  trace: { x: number; y: number; color: string } | null
) {
  if (!trace) return;
  const sx = clampPx(mapX(view, w, trace.x)), sy = clampPx(mapY(view, h, trace.y));
  ctx.beginPath();
  ctx.arc(sx, sy, 5, 0, Math.PI * 2);
  ctx.fillStyle = trace.color;
  ctx.fill();
  ctx.strokeStyle = "#fff";
  ctx.lineWidth = 1.6;
  ctx.stroke();
  ctx.fillStyle = g.axisLabel;
  ctx.font = "12px -apple-system, Segoe UI, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "bottom";
  ctx.fillText(`(${fmt(trace.x)}, ${fmt(trace.y)})`, sx + 9, sy - 7);
}

/** 极值菱形（紫色极大 / 青色极小）。画在曲线**之前**，曲线不会被标记切断。 */function drawExtrema(
  ctx: CanvasRenderingContext2D, w: number, h: number, view: View, extrema: Extremum[]
) {
  if (!extrema.length) return;
  ctx.font = "11.5px -apple-system, Segoe UI, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "bottom";
  for (const e of extrema) {
    if (!Number.isFinite(e.x) || !Number.isFinite(e.y)) continue;
    const px = clampPx(mapX(view, w, e.x)), py = clampPx(mapY(view, h, e.y));
    const isMax = e.kind === "max";
    const color = isMax ? "#7c3aed" : "#0891b2";
    const r = 4;
    ctx.beginPath();
    ctx.moveTo(px, py - r);
    ctx.lineTo(px + r, py);
    ctx.lineTo(px, py + r);
    ctx.lineTo(px - r, py);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
    ctx.fillText(`${isMax ? "极大" : "极小"} (${fmt(e.x)}, ${fmt(e.y)})`, px + 8, py - 6);
  }
}

/** 交点圆点（画在曲线之前，同上） */
function drawIntersections(
  ctx: CanvasRenderingContext2D, w: number, h: number, view: View, its: Intersection[]
) {
  if (!its.length) return;
  ctx.font = "11.5px -apple-system, Segoe UI, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "bottom";
  for (const it of its) {
    const px = clampPx(mapX(view, w, it.x)), py = clampPx(mapY(view, h, it.y));
    ctx.beginPath();
    ctx.arc(px, py, 4.5, 0, Math.PI * 2);
    ctx.fillStyle = "#0891b2";
    ctx.fill();
    ctx.fillStyle = "#475569";
    ctx.fillText(`(${it.xLabel ?? fmt(it.x)}, ${it.yLabel ?? fmt(it.y)})`, px + 8, py - 6);
  }
}

/** 用户自己创建的点：空心圆 + 坐标标签（点必须用户自己添加） */
function drawUserPoints(
  ctx: CanvasRenderingContext2D, w: number, h: number, view: View, points: UserPoint[]
) {
  if (!points.length) return;
  ctx.font = "12px -apple-system, Segoe UI, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "bottom";
  for (const p of points) {
    if (!Number.isFinite(p.x) || !Number.isFinite(p.y)) continue;
    const px = clampPx(mapX(view, w, p.x)), py = clampPx(mapY(view, h, p.y));
    ctx.beginPath();
    ctx.arc(px, py, 5.5, 0, Math.PI * 2);
    ctx.fillStyle = "#fff";
    ctx.fill();
    ctx.strokeStyle = p.color || "#c74440";
    ctx.lineWidth = 2.5;
    ctx.stroke();
    ctx.fillStyle = p.color || "#444";
    ctx.fillText(`${fmt(p.x)}, ${fmt(p.y)}`, px + 9, py - 7);
  }
}

/** 在采样点里找离光标最近的曲线点（屏幕空间最近邻，不额外调引擎） */
function findCurvePointAt(
  w: number, h: number, view: View, curves: Curve[], samples: Record<number, Sample[]>,
  px: number, py: number, tolPx = 16
): { x: number; y: number; curveId: number } | null {
  let best: { x: number; y: number; curveId: number } | null = null;
  let bestD = tolPx;
  for (const c of curves) {
    if (!c.visible) continue;
    const pts = samples[c.id];
    if (!pts) continue;
    for (const p of pts) {
      if (!p) continue;
      const d = Math.hypot(mapX(view, w, p[0]) - px, mapY(view, h, p[1]) - py);
      if (d < bestD) { bestD = d; best = { x: p[0], y: p[1], curveId: c.id }; }
    }
  }
  return best;
}

/** 命中用户点（拖动用）：屏幕距离 < tolPx 的最近一个点 */
function hitUserPoint(
  w: number, h: number, view: View, points: UserPoint[], px: number, py: number, tolPx = 10
): UserPoint | null {
  let best: UserPoint | null = null;
  let bestD = tolPx;
  for (const p of points) {
    const d = Math.hypot(mapX(view, w, p.x) - px, mapY(view, h, p.y) - py);
    if (d < bestD) { bestD = d; best = p; }
  }
  return best;
}

export default function PlotCanvas({
  view, onViewChange, curves, samples, grids = {}, points = [], intersections = [], extrema = [],
  gridMode = "rect", showGrid = true, theme, onSizeChange, onPickPoint, onDragPoint, canvasRef,
}: Props) {
  const innerRef = useRef<HTMLCanvasElement | null>(null);
  const ctxRef = useRef<CanvasRenderingContext2D | null>(null);
  const sizeRef = useRef({ w: 0, h: 0 });
  const [mode, setMode] = useState(() => plotMode(theme));
  const [hover, setHover] = useState<[number, number] | null>(null);
  /* 悬停命中曲线时记录"曲线上的那个点"（画追踪标记）；没命中则 null */
  const [trace, setTrace] = useState<{ x: number; y: number; color: string } | null>(null);
  const drag = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  /** 正在拖动的用户点 id（拖动时不平移视图） */
  const dragPt = useRef<number | null>(null);
  const viewRef = useRef(view);
  viewRef.current = view;

  /* 主题跟随外观设置（与 Vue 版一致：plotMode(theme) + onAppearanceChange） */
  useEffect(() => {
    setMode(plotMode(theme));
    const off = onAppearanceChange?.(() => setMode(plotMode(theme)));
    return () => { if (typeof off === "function") off(); };
  }, [theme]);

  const setRefs = (el: HTMLCanvasElement | null) => {
    innerRef.current = el;
    if (canvasRef) canvasRef.current = el;
  };

  const draw = useCallback(() => {
    const cv = innerRef.current;
    const ctx = ctxRef.current;
    if (!cv || !ctx) return;
    const { w, h } = sizeRef.current;
    if (w <= 0 || h <= 0) return;
    const g = gridFor(mode);
    drawGrid(ctx, w, h, view, g, gridMode, showGrid, hover);
    /* 绘制顺序与 Vue 版一致：网格 → 区域 → 不等式 → 标记 → 曲线 → 隐式等值线 → 用户点。
     * 标记必须在曲线之前（不透明的菱形画在曲线之后会把曲线盖掉一截，
     * 在平坦极值点处看起来就像"曲线断了"）。 */
    drawRegions(ctx, w, h, view, curves, grids);
    drawInequalities(ctx, w, h, view, curves, samples);
    drawExtrema(ctx, w, h, view, extrema);
    drawIntersections(ctx, w, h, view, intersections);
    drawCurves(ctx, w, h, view, curves, samples);
    drawImplicits(ctx, w, h, view, curves, grids);
    drawUserPoints(ctx, w, h, view, points);
    drawTrace(ctx, w, h, view, g, trace);   // 追踪标记画在最上层（与 Vue 版一致）
  }, [view, curves, samples, grids, points, intersections, extrema, gridMode, showGrid, mode, hover, trace]);

  useEffect(() => {
    const cv = innerRef.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    ctxRef.current = ctx;
    const resize = () => {
      const w = cv.clientWidth, h = cv.clientHeight;
      if (w <= 0 || h <= 0) return;
      const dpr = window.devicePixelRatio || 1;
      cv.width = Math.round(w * dpr);
      cv.height = Math.round(h * dpr);
      sizeRef.current = { w, h };
      ctx?.setTransform(dpr, 0, 0, dpr, 0, 0);
      onSizeChange?.(w, h);
      draw();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(cv);
    return () => ro.disconnect();
  }, [draw, onSizeChange]);

  useEffect(() => { draw(); }, [draw]);

  const pos = (e: React.MouseEvent) => {
    const r = innerRef.current!.getBoundingClientRect();
    return { px: e.clientX - r.left, py: e.clientY - r.top };
  };

  return (
    <canvas
      ref={setRefs}
      className="plot-canvas-desmos"
      data-tour="plot_canvas"
      onWheel={(e) => {
        e.preventDefault();
        const { px, py } = pos(e);
        const { w, h } = sizeRef.current;
        onViewChange(zoomAt(viewRef.current, w, h, px, py, e.deltaY > 0 ? 1.15 : 1 / 1.15));
      }}
      onMouseDown={(e) => {
        const { px, py } = pos(e);
        const { w, h } = sizeRef.current;
        /* 拖点优先于平移：光标压在已有点上时，这一拖是"沿曲线滑点"，不是挪视图 */
        const hitPt = hitUserPoint(w, h, viewRef.current, points, px, py);
        if (hitPt) { dragPt.current = hitPt.id; return; }
        drag.current = { x: px, y: py, moved: false };
      }}
      onMouseMove={(e) => {
        const { px, py } = pos(e);
        const { w, h } = sizeRef.current;
        const v = viewRef.current;
        if (dragPt.current !== null) {
          onDragPoint?.(dragPt.current, [unmapX(v, w, px), unmapY(v, h, py)]);
          return;
        }
        if (drag.current) {
          const dx = px - drag.current.x, dy = py - drag.current.y;
          if (Math.abs(dx) + Math.abs(dy) > 2) drag.current.moved = true;
          drag.current.x = px; drag.current.y = py;
          if (drag.current.moved) onViewChange(panBy(viewRef.current, w, h, dx, dy));
          return;
        }
        setHover([unmapX(v, w, px), unmapY(v, h, py)]);
        /* 悬停追踪：命中曲线就记下曲线上的那个点（画标记），否则清掉 */
        const hit = findCurvePointAt(w, h, v, curves, samples, px, py, 12);
        setTrace(hit
          ? { x: hit.x, y: hit.y, color: curves.find((c) => c.id === hit.curveId)?.color ?? "#c74440" }
          : null);
      }}
      onMouseUp={(e) => {
        if (dragPt.current !== null) { dragPt.current = null; return; }   // 松手：不当作"点选加点"
        const wasDrag = drag.current?.moved;
        drag.current = null;
        if (wasDrag) return;
        const { px, py } = pos(e);
        const { w, h } = sizeRef.current;
        const hit = findCurvePointAt(w, h, viewRef.current, curves, samples, px, py, 12);
        if (hit) onPickPoint?.(hit.x, hit.y, hit.curveId);
      }}
      onMouseLeave={() => { drag.current = null; dragPt.current = null; setHover(null); setTrace(null); }}
    />
  );
}
