import { useCallback, useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { gridFor } from "@shared/plot/colors.js";
import { plotMode, onAppearanceChange } from "@shared/bridge.js";
import {
  mapX, mapY, unmapX, unmapY, zoomAt, panBy, gridSteps, formatTick, viewW,
} from "@shared/plot/view.js";
import "../styles/plot-vector.css";

/**
 * VectorFieldCanvas — 向量场渲染（对照 Vue 版 components/plot/VectorFieldCanvas.vue 逐行移植）
 *  · 网格点上绘制箭头（dx、dy 由 C++ 引擎 expr_eval_grid 双网格求值）
 *  · 支持箭头归一化（只看方向）与按模长着色（颜色编码强度）
 *  · 复用 2D 视图数学：拖拽平移、光标中心缩放、nice 步长网格
 *
 * 移植时保持的几处判断（都有历史原因，改动会回归）：
 *  · `theme` 默认 **undefined**，不要给 "light"：视图层从不传这个 prop，
 *    给了默认值就永远走浅色（bridge.js 记录的历史事故）。留空 → 跟随当前配色。
 *  · normalize 默认 true：原版 vector_field/workspace.py:185 用单位方向向量 + 颜色编码模长。
 *  · 屏幕 y 向下、世界 y 向上 → 箭头的竖直分量取反。
 */

export type FieldView = { x0: number; y0: number; x1: number; y1: number };
export type VectorFieldData = { xs: number[]; ys: number[]; dx: number[]; dy: number[] };

type Props = {
  field: VectorFieldData | null;
  view: FieldView;
  theme?: string;
  /** 箭头长度缩放（0 表示自动） */
  arrowScale?: number;
  /** 归一化：所有箭头等长（默认 true） */
  normalize?: boolean;
  /** 按模长着色（默认 true） */
  colorByMagnitude?: boolean;
  showGrid?: boolean;
  onViewChange?: (v: FieldView) => void;
  canvasRef?: RefObject<HTMLCanvasElement | null>;
};

/** 模长 → 颜色（蓝 → 青 → 绿 → 黄 → 红） */
function magColor(t: number): string {
  const stops: [number, [number, number, number]][] = [
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

function drawGrid(
  ctx: CanvasRenderingContext2D, w: number, h: number, view: FieldView,
  g: ReturnType<typeof gridFor>, showGrid: boolean
) {
  ctx.fillStyle = g.bg;
  ctx.fillRect(0, 0, w, h);
  const { major, minor } = gridSteps(view, w, h);
  /* 刻度索引声明在 if 之外：后面画刻度标签也要用（Vue 版曾因作用域错误导致参考系不绘制） */
  const k0 = Math.ceil(view.x0 / major), k1 = Math.floor(view.x1 / major);
  const l0 = Math.ceil(view.y0 / major), l1 = Math.floor(view.y1 / major);

  if (showGrid) {
    ctx.strokeStyle = g.minor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    const i0 = Math.ceil(view.x0 / minor), i1 = Math.floor(view.x1 / minor);
    for (let i = i0; i <= i1 && i1 - i0 < 4000; i++) {
      if (Math.abs((i * minor) / major - Math.round((i * minor) / major)) < 1e-9) continue;
      const px = Math.round(mapX(view, w, i * minor)) + 0.5;
      ctx.moveTo(px, 0); ctx.lineTo(px, h);
    }
    const j0 = Math.ceil(view.y0 / minor), j1 = Math.floor(view.y1 / minor);
    for (let j = j0; j <= j1 && j1 - j0 < 4000; j++) {
      if (Math.abs((j * minor) / major - Math.round((j * minor) / major)) < 1e-9) continue;
      const py = Math.round(mapY(view, h, j * minor)) + 0.5;
      ctx.moveTo(0, py); ctx.lineTo(w, py);
    }
    ctx.stroke();

    ctx.strokeStyle = g.major;
    ctx.beginPath();
    for (let k = k0; k <= k1 && k1 - k0 < 2000; k++) {
      const px = Math.round(mapX(view, w, k * major)) + 0.5;
      ctx.moveTo(px, 0); ctx.lineTo(px, h);
    }
    for (let l = l0; l <= l1 && l1 - l0 < 2000; l++) {
      const py = Math.round(mapY(view, h, l * major)) + 0.5;
      ctx.moveTo(0, py); ctx.lineTo(w, py);
    }
    ctx.stroke();
  }

  // 坐标轴
  const axisY = mapY(view, h, 0), axisX = mapX(view, w, 0);
  ctx.strokeStyle = g.axis;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  if (axisY >= 0 && axisY <= h) { ctx.moveTo(0, axisY); ctx.lineTo(w, axisY); }
  if (axisX >= 0 && axisX <= w) { ctx.moveTo(axisX, 0); ctx.lineTo(axisX, h); }
  ctx.stroke();

  // 刻度
  ctx.fillStyle = g.label;
  ctx.font = "11px -apple-system, Segoe UI, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  const ly = Math.min(Math.max(axisY + 4, 2), h - 16);
  for (let k = k0; k <= k1 && k1 - k0 < 200; k++) {
    if (k === 0) continue;
    const px = mapX(view, w, k * major);
    if (px < 16 || px > w - 16) continue;
    ctx.fillText(formatTick(k * major, major), px, ly);
  }
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  const lx = Math.min(Math.max(axisX - 6, 26), w - 4);
  for (let l = l0; l <= l1 && l1 - l0 < 200; l++) {
    if (l === 0) continue;
    const py = mapY(view, h, l * major);
    if (py < 10 || py > h - 10) continue;
    ctx.fillText(formatTick(l * major, major), lx, py);
  }
}

type FieldOpts = {
  normalize: boolean;
  colorByMagnitude: boolean;
  arrowScale: number;
  dark: boolean;
  hover: [number, number] | null;
};

function drawField(
  ctx: CanvasRenderingContext2D, w: number, h: number, view: FieldView,
  f: VectorFieldData | null, o: FieldOpts
): number {
  if (!f || !f.xs || !f.ys || !f.dx || !f.dy) return 0;
  const nx = f.xs.length, ny = f.ys.length;
  let arrowCount = 0;

  // 模长范围（用于归一化与着色）
  let mmax = 0;
  const mags = new Array<number>(nx * ny);
  for (let i = 0; i < nx * ny; i++) {
    const dx = f.dx[i], dy = f.dy[i];
    const m = (typeof dx === "number" && typeof dy === "number" && isFinite(dx) && isFinite(dy))
      ? Math.hypot(dx, dy) : NaN;
    mags[i] = m;
    if (isFinite(m) && m > mmax) mmax = m;
  }
  if (mmax <= 0) return 0;

  // 箭头基础长度：取相邻网格点间距的一半（自适应）
  const spacingPx = nx > 1 ? (w / (nx - 1)) : 40;
  const baseLen = o.arrowScale > 0 ? o.arrowScale * spacingPx : spacingPx * 0.85;

  ctx.lineWidth = 1.4;
  ctx.lineCap = "round";
  for (let j = 0; j < ny; j++) {
    for (let i = 0; i < nx; i++) {
      const idx = j * nx + i;
      const m = mags[idx];
      if (!isFinite(m) || m === 0) continue;
      const dx = f.dx[idx], dy = f.dy[idx];
      const px = mapX(view, w, f.xs[i]);
      const py = mapY(view, h, f.ys[j]);
      if (px < -20 || px > w + 20 || py < -20 || py > h + 20) continue;

      // 箭头长度：按模长相对最大值缩放（不归一化时体现强度差异）
      const lenPx = o.normalize ? baseLen : baseLen * (m / mmax);
      const ux = dx / m, uy = dy / m;
      // 屏幕 y 向下，世界 y 向上 → 箭头的竖直分量取反
      const ex = px + ux * lenPx;
      const ey = py - uy * lenPx;

      const color = o.colorByMagnitude ? magColor(m / mmax) : (o.dark ? "#60a5fa" : "#2d70b3");
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
  if (o.hover) {
    ctx.fillStyle = o.dark ? "#9aa4b2" : "#64748b";
    ctx.font = "11.5px -apple-system, Segoe UI, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "bottom";
    ctx.fillText(`(${o.hover[0].toFixed(2)}, ${o.hover[1].toFixed(2)})`, 8, h - 6);
  }
  return arrowCount;
}

const errText = (e: unknown) => (e && (e as Error).message ? (e as Error).message : String(e));

export default function VectorFieldCanvas({
  field, view, theme, arrowScale = 0, normalize = true, colorByMagnitude = true,
  showGrid = true, onViewChange, canvasRef,
}: Props) {
  const innerRef = useRef<HTMLCanvasElement | null>(null);
  const ctxRef = useRef<CanvasRenderingContext2D | null>(null);
  const sizeRef = useRef({ w: 0, h: 0 });
  const hoverRef = useRef<[number, number] | null>(null);
  const dragRef = useRef<{ x: number; y: number; view: FieldView } | null>(null);
  const [mode, setMode] = useState(() => plotMode(theme));

  /* 主题跟随外观设置（与 Vue 版一致：plotMode(theme) + onAppearanceChange） */
  useEffect(() => {
    setMode(plotMode(theme));
    const off = onAppearanceChange?.(() => setMode(plotMode(theme)));
    return () => { if (typeof off === "function") off(); };
  }, [theme]);

  const dark = mode === "dark";

  const setRefs = (el: HTMLCanvasElement | null) => {
    innerRef.current = el;
    if (canvasRef) canvasRef.current = el;
  };

  const draw = useCallback(() => {
    const cv = innerRef.current;
    const ctx = ctxRef.current;
    const { w, h } = sizeRef.current;
    const diag = {
      w, h, hasCtx: !!ctx, hasField: !!field,
      fieldLen: field && field.dx ? field.dx.length : 0,
      drawn: 0, errors: [] as string[],
    };
    if (!ctx || w <= 0 || h <= 0) {
      if (typeof window !== "undefined") (window as unknown as { __vfDiag: unknown }).__vfDiag = diag;
      return;
    }
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    try {
      drawGrid(ctx, w, h, view, gridFor(mode), showGrid);
    } catch (e) { diag.errors.push("grid: " + errText(e)); }
    try {
      diag.drawn = drawField(ctx, w, h, view, field, {
        normalize, colorByMagnitude, arrowScale, dark, hover: hoverRef.current,
      });
    } catch (e) { diag.errors.push("field: " + errText(e)); }
    if (typeof window !== "undefined") (window as unknown as { __vfDiag: unknown }).__vfDiag = diag;
  }, [view, field, mode, normalize, colorByMagnitude, showGrid, arrowScale, dark]);

  useEffect(() => {
    const cv = innerRef.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    ctxRef.current = ctx;
    cv.style.cursor = "grab";
    const resize = () => {
      const w = cv.clientWidth, h = cv.clientHeight;
      if (w <= 0 || h <= 0) return;
      const dpr = window.devicePixelRatio || 1;
      cv.width = Math.round(w * dpr);
      cv.height = Math.round(h * dpr);
      sizeRef.current = { w, h };
      draw();
    };
    resize();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
    ro?.observe(cv);
    return () => ro?.disconnect();
  }, [draw]);

  useEffect(() => { draw(); }, [draw]);

  const pos = (e: React.MouseEvent) => {
    const r = innerRef.current!.getBoundingClientRect();
    return { px: e.clientX - r.left, py: e.clientY - r.top };
  };

  return (
    <canvas
      ref={setRefs}
      className="vf-canvas"
      onMouseDown={(e) => {
        if (e.button !== 0) return;
        dragRef.current = { x: e.clientX, y: e.clientY, view: { ...view } };
        if (innerRef.current) innerRef.current.style.cursor = "grabbing";
      }}
      onMouseMove={(e) => {
        const { px, py } = pos(e);
        const { w, h } = sizeRef.current;
        hoverRef.current = [unmapX(view, w, px), unmapY(view, h, py)];
        if (dragRef.current) {
          const dx = e.clientX - dragRef.current.x, dy = e.clientY - dragRef.current.y;
          onViewChange?.(panBy(dragRef.current.view, w, h, dx, dy));
          draw();
          return;
        }
        draw();
      }}
      onMouseUp={() => {
        dragRef.current = null;
        if (innerRef.current) innerRef.current.style.cursor = "grab";
      }}
      onMouseLeave={() => {
        hoverRef.current = null;
        dragRef.current = null;
        draw();
      }}
      onWheel={(e) => {
        e.preventDefault();
        const { px, py } = pos(e);
        const { w, h } = sizeRef.current;
        onViewChange?.(zoomAt(view, w, h, px, py, e.deltaY < 0 ? 0.88 : 1.14));
        draw();
      }}
    />
  );
}
