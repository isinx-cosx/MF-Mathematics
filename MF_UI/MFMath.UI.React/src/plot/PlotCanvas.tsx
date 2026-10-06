import { useCallback, useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { plotMode, onAppearanceChange } from "@shared/bridge.js";
import {
  mapX, mapY, unmapX, unmapY, viewH, zoomAt, panBy, gridSteps, formatTick,
} from "@shared/plot/view.js";
import { gridFor } from "@shared/plot/colors.js";
import { drawPolarGrid } from "@shared/plot/cartesian.js";
import "../styles/plot-canvas.css";

export type View = { x0: number; x1: number; y0: number; y1: number };
export type Sample = [number, number] | null;
export type Curve = {
  id: number;
  text?: string;
  color: string;
  visible: boolean;
  emphasis?: boolean;
};
export type UserPoint = { id: number; x: number; y: number; color?: string };
export type Intersection = { x: number; y: number; xLabel?: string; yLabel?: string };
export type Extremum = { x: number; y: number; kind: "max" | "min" };

type Props = {
  view: View;
  onViewChange: (v: View) => void;
  curves: Curve[];
  samples: Record<number, Sample[]>;
  /** 隐式方程网格：React 版尚未移植 marching squares，暂不绘制（行内会报"未迁移"） */
  grids?: Record<number, unknown>;
  points?: UserPoint[];
  intersections?: Intersection[];
  extrema?: Extremum[];
  gridMode?: "rect" | "polar";
  showGrid?: boolean;
  theme?: string;
  onSizeChange?: (w: number, h: number) => void;
  onPickPoint?: (x: number, y: number) => void;
  canvasRef?: RefObject<HTMLCanvasElement | null>;
};

const fmt = (n: number) => (Math.abs(n) < 1e-10 ? "0" : String(Math.round(n * 1e4) / 1e4));

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
      const px = mapX(view, w, x), py = mapY(view, h, y);
      if (drawing && lastY !== null && far(lastY) && far(y) && Math.sign(lastY) !== Math.sign(y)) {
        drawing = false;
      }
      if (!drawing) { ctx.moveTo(px, py); drawing = true; } else ctx.lineTo(px, py);
      lastY = y;
    }
    ctx.stroke();
  }
}

/** 极值菱形（紫色极大 / 青色极小）。画在曲线**之前**，曲线不会被标记切断。 */
function drawExtrema(
  ctx: CanvasRenderingContext2D, w: number, h: number, view: View, extrema: Extremum[]
) {
  if (!extrema.length) return;
  ctx.font = "11.5px -apple-system, Segoe UI, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "bottom";
  for (const e of extrema) {
    if (!Number.isFinite(e.x) || !Number.isFinite(e.y)) continue;
    const px = mapX(view, w, e.x), py = mapY(view, h, e.y);
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
    const px = mapX(view, w, it.x), py = mapY(view, h, it.y);
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
    const px = mapX(view, w, p.x), py = mapY(view, h, p.y);
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

export default function PlotCanvas({
  view, onViewChange, curves, samples, points = [], intersections = [], extrema = [],
  gridMode = "rect", showGrid = true, theme, onSizeChange, onPickPoint, canvasRef,
}: Props) {
  const innerRef = useRef<HTMLCanvasElement | null>(null);
  const ctxRef = useRef<CanvasRenderingContext2D | null>(null);
  const sizeRef = useRef({ w: 0, h: 0 });
  const [mode, setMode] = useState(() => plotMode(theme));
  const [hover, setHover] = useState<[number, number] | null>(null);
  const drag = useRef<{ x: number; y: number; moved: boolean } | null>(null);
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
    drawExtrema(ctx, w, h, view, extrema);
    drawIntersections(ctx, w, h, view, intersections);
    drawCurves(ctx, w, h, view, curves, samples);
    drawUserPoints(ctx, w, h, view, points);
  }, [view, curves, samples, points, intersections, extrema, gridMode, showGrid, mode, hover]);

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
      onMouseDown={(e) => { const { px, py } = pos(e); drag.current = { x: px, y: py, moved: false }; }}
      onMouseMove={(e) => {
        const { px, py } = pos(e);
        const { w, h } = sizeRef.current;
        if (drag.current) {
          const dx = px - drag.current.x, dy = py - drag.current.y;
          if (Math.abs(dx) + Math.abs(dy) > 2) drag.current.moved = true;
          drag.current.x = px; drag.current.y = py;
          if (drag.current.moved) onViewChange(panBy(viewRef.current, w, h, dx, dy));
          return;
        }
        const v = viewRef.current;
        setHover([unmapX(v, w, px), unmapY(v, h, py)]);
      }}
      onMouseUp={(e) => {
        const wasDrag = drag.current?.moved;
        drag.current = null;
        if (wasDrag) return;
        const { px, py } = pos(e);
        const { w, h } = sizeRef.current;
        const hit = findCurvePointAt(w, h, viewRef.current, curves, samples, px, py, 12);
        if (hit) onPickPoint?.(hit.x, hit.y);
      }}
      onMouseLeave={() => { drag.current = null; setHover(null); }}
    />
  );
}
