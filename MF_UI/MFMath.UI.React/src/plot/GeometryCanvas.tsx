import { useCallback, useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { gridFor } from "@shared/plot/colors.js";
import { plotMode, onAppearanceChange } from "@shared/bridge.js";
import { drawCartesianGrid } from "@shared/plot/cartesian.js";
import { mapX, mapY, unmapX, unmapY, zoomAt, panBy, gridSteps } from "@shared/plot/view.js";
import "../styles/geometry-canvas.css";

/**
 * GeometryCanvas — 交互式几何作图画布（对照 Vue 版 components/plot/GeometryCanvas.vue 逐行移植）
 *  · 10 种工具：选择/移动、平移、点、线段、圆、向量、直线、椭圆、矩形、多边形
 *  · 构造状态机：idle / awaitSecond / dragRadius / awaitHRad / awaitVRad / awaitCorner / buildPoly
 *  · 吸附：优先几何吸附（端点/中点/圆心），否则网格吸附
 *  · 命中检测（点到图形的屏幕距离）+ 拖拽移动
 *  · 坐标系复用 cartesian.js（与 2D 绘图一致）
 *
 * 移植时保持的判断（每条都对应一次历史事故，改了会回归）：
 *  · `theme` 默认 undefined：给了 "light" 就恒为浅色，深色配色下画布永远白底。
 *  · 等比视图：原版全程 KeepAspectRatio，世界里的圆画出来还是圆。
 *  · 吸附/命中粒度是**次网格**（major/5），原版 _grid_step；用 major 会粗 5 倍。
 *  · 直线要按"与视口矩形求交"画，否则退化成视口底边一条线段。
 *  · 点永远在线之上（原版 Z 序：点 Z=10、其余 Z=5）。
 */

export type ShapeType = "point" | "segment" | "circle" | "vector" | "line" | "ellipse" | "rect" | "polygon";
export type Shape = {
  id: number;
  type: ShapeType;
  data: unknown;
  color: string;
  label: string;
  visible: boolean;
};
export type GeoView = { x0: number; y0: number; x1: number; y1: number };
export type GeometryApi = { resetView: () => void; cancelConstruction: () => void };

type Props = {
  shapes: Shape[];
  tool: string;
  selectedId: number | null;
  snap: boolean;
  theme?: string;
  onCreate?: (v: { type: ShapeType; data: unknown }) => void;
  onSelect?: (id: number | null) => void;
  onMove?: (v: { id: number; dx: number; dy: number }) => void;
  canvasRef?: RefObject<HTMLCanvasElement | null>;
  apiRef?: RefObject<GeometryApi | null>;
};

const SNAP_HINT: Record<string, string> = {
  idle: "",
  awaitSecond: "点击终点",
  dragRadius: "拖拽确定半径",
  awaitHRad: "点击确定水平半轴",
  awaitVRad: "点击确定垂直半轴",
  awaitCorner: "点击对角",
  buildPoly: "继续点击顶点，双击或右键闭合",
};

/**
 * 等比视图：x/y 每单位对应的像素数相同。
 * 原版全程保持等比（`scale(1,-1)` + `fitInView(INITIAL_VIEW, KeepAspectRatio)`），
 * 所以世界里的圆画出来还是圆；固定 16×12 时画布不是 4:3 就会把网格与圆拉伸。
 */
function equalAspectView(x0: number, x1: number, cy: number, w: number, h: number): GeoView {
  const spanX = x1 - x0;
  const spanY = spanX * (h / Math.max(w, 1));
  return { x0, x1, y0: cy - spanY / 2, y1: cy + spanY / 2 };
}

/* ── 几何工具函数（纯函数，与 Vue 版逐字一致）────────────────────────── */
function distSeg(px: number, py: number, x1: number, y1: number, x2: number, y2: number): number {
  const dx = x2 - x1, dy = y2 - y1;
  if (!dx && !dy) return Math.hypot(px - x1, py - y1);
  const t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)));
  return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}
function distLine(px: number, py: number, x1: number, y1: number, x2: number, y2: number): number {
  const dx = x2 - x1, dy = y2 - y1;
  if (!dx && !dy) return Math.hypot(px - x1, py - y1);
  return Math.abs(dx * (y1 - py) - (x1 - px) * dy) / Math.hypot(dx, dy);
}
/**
 * 无限直线与视口矩形的交点（最多 2 个）。
 * 与原版 plot/arbitrary/geometry_canvas.py:1175-1195 `_line_viewport_intersection` 同算法。
 */
function lineViewportIntersection(
  x1: number, y1: number, x2: number, y2: number,
  vx0: number, vx1: number, vy0: number, vy1: number
): [number, number][] {
  const dx = x2 - x1, dy = y2 - y1;
  const pts: [number, number][] = [];
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

type Pt = [number, number];

function shapeSnapPoints(s: Shape): Pt[] {
  const d = s.data as never, t = s.type, out: Pt[] = [];
  if (t === "point") out.push([d[0], d[1]]);
  else if (t === "segment" || t === "vector" || t === "line") {
    out.push([d[0][0], d[0][1]], [d[1][0], d[1][1]],
      [(d[0][0] + d[1][0]) / 2, (d[0][1] + d[1][1]) / 2]);   // 两端点 + 中点
  } else if (t === "circle") {
    // 原版 arbitrary/geometry_canvas.py:681-685：圆心 + 右端点 + 上端点
    out.push([d[0][0], d[0][1]], [d[0][0] + d[1], d[0][1]], [d[0][0], d[0][1] + d[1]]);
  } else if (t === "ellipse") {
    // 原版 :686-690 把 ((cx,cy),rx,ry) 当成两点解包了（原版自身缺陷），这里不照抄
    out.push([d[0][0], d[0][1]], [d[0][0] + d[1], d[0][1]], [d[0][0], d[0][1] + d[2]]);
  } else if (t === "rect") {
    out.push([d[0][0], d[0][1]], [d[1][0], d[1][1]],
      [(d[0][0] + d[1][0]) / 2, (d[0][1] + d[1][1]) / 2]);
  } else if (t === "polygon") {
    for (let i = 0; i < d.length; i++) {
      out.push([d[i][0], d[i][1]]);
      const n = d[(i + 1) % d.length];
      out.push([(d[i][0] + n[0]) / 2, (d[i][1] + n[1]) / 2]);
    }
  }
  return out;
}

function hitTest(s: Shape, mx: number, my: number, th: number): boolean {
  const d = s.data as never, t = s.type;
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
    const c: Pt[] = [[xmin, ymin], [xmax, ymin], [xmax, ymax], [xmin, ymax]];
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

/** 光标到图形的近似距离 —— 照搬原版 _shape_approx_dist（用于"取最近"的选中判定） */
function shapeApproxDist(s: Shape, mx: number, my: number): number {
  const d = s.data as never, t = s.type;
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
    const c: Pt[] = [[xmin, ymin], [xmax, ymin], [xmax, ymax], [xmin, ymax]];
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

function withAlpha(hex: string, a: number): string {
  const h = String(hex || "#3498db").replace("#", "");
  const n = h.length === 3 ? h.split("").map((c) => c + c).join("") : h.padEnd(6, "0").slice(0, 6);
  return `rgba(${parseInt(n.slice(0, 2), 16)}, ${parseInt(n.slice(2, 4), 16)}, ${parseInt(n.slice(4, 6), 16)}, ${a})`;
}

export default function GeometryCanvas({
  shapes, tool, selectedId, snap, theme, onCreate, onSelect, onMove, canvasRef, apiRef,
}: Props) {
  const innerRef = useRef<HTMLCanvasElement | null>(null);
  const ctxRef = useRef<CanvasRenderingContext2D | null>(null);
  const sizeRef = useRef({ w: 0, h: 0 });
  const dragRef = useRef<
    | { kind: "pan"; x: number; y: number; view: GeoView }
    | { kind: "shape"; id: number; last: Pt }
    | null
  >(null);

  const [view, setView] = useState<GeoView>({ x0: -8, y0: -6, x1: 8, y1: 6 });
  /** 构造状态机 */
  const [phase, setPhase] = useState("idle");
  const [tempPts, setTempPts] = useState<Pt[]>([]);   // 已确定的构造点
  const [cursor, setCursor] = useState<Pt>([0, 0]);   // 当前光标（吸附后）
  const [mode, setMode] = useState(() => plotMode(theme));

  useEffect(() => {
    setMode(plotMode(theme));
    const off = onAppearanceChange?.(() => setMode(plotMode(theme)));
    return () => { if (typeof off === "function") off(); };
  }, [theme]);

  const setRefs = (el: HTMLCanvasElement | null) => {
    innerRef.current = el;
    if (canvasRef) canvasRef.current = el;
  };

  /* ── 吸附 ── */
  /**
   * 吸附/命中用的网格粒度。原版 `_grid_step` 用的是**次网格**粒度 calculate_step(rng)/5；
   * 直接用主网格步长会让吸附（以及阈值 0.6*step）比原版粗 5 倍。
   */
  const gridStep = useCallback(() => {
    const { major } = gridSteps(view, sizeRef.current.w, sizeRef.current.h);
    return major / 5;
  }, [view]);

  const snapPoint = useCallback((x: number, y: number): Pt => {
    if (!snap) return [x, y];
    const step = gridStep();
    const th = step * 0.6;
    let best: Pt | null = null, bd = th;
    for (const s of shapes) {
      if (!s.visible) continue;
      for (const [px, py] of shapeSnapPoints(s)) {
        const d = Math.hypot(x - px, y - py);
        if (d < bd) { bd = d; best = [px, py]; }
      }
    }
    if (best) return best;
    return [Math.round(x / step) * step, Math.round(y / step) * step];
  }, [snap, gridStep, shapes]);

  /** 命中检测的世界阈值：原版 _pick_shape 用 grid_step * 0.8 */
  const worldThreshold = useCallback(() => gridStep() * 0.8, [gridStep]);

  /**
   * 选中图形：遍历全部可见图形，在命中者里取"近似距离最近"的那个（原版 _pick_shape 语义）。
   */
  const pickShape = useCallback((mx: number, my: number): Shape | null => {
    const th = worldThreshold();
    let best: Shape | null = null, bestDist = Infinity;
    for (const s of shapes) {
      if (!s.visible) continue;
      if (hitTest(s, mx, my, th)) {
        const dist = shapeApproxDist(s, mx, my);
        if (dist < bestDist) { bestDist = dist; best = s; }
      }
    }
    return best;
  }, [shapes, worldThreshold]);

  const cancelConstruction = useCallback(() => {
    setPhase("idle");
    setTempPts([]);
  }, []);

  const resetView = useCallback(() => {
    const el = innerRef.current;
    const w = el?.clientWidth || sizeRef.current.w || 1;
    const h = el?.clientHeight || sizeRef.current.h || 1;
    setView(equalAspectView(-8, 8, 0, w, h));   // 原版回落 INITIAL_VIEW x∈[-8,8] 并保持等比
  }, []);

  /* ── 绘制 ── */
  const drawShape = (ctx: CanvasRenderingContext2D, s: Shape, w: number, h: number, v: GeoView) => {
    const d = s.data as never, t = s.type;
    const selected = s.id === selectedId;
    // 选中高亮色 = 原版 HIGHLIGHT_COLOR #3b82f6（用 #e74c3c 会与色板首色同色系，难分辨）
    const color = selected ? "#3b82f6" : s.color;
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = selected ? 3 : 1.8;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    const px = (x: number, y: number): Pt => [mapX(v, w, x), mapY(v, h, y)];

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
      ctx.fillText(`${s.label || ""}(${dx.toFixed(2)}, ${dy.toFixed(2)})`, (A[0] + B[0]) / 2 + 6, (A[1] + B[1]) / 2 - 6);
    } else if (t === "circle") {
      const [C] = [px(d[0][0], d[0][1])];
      const rPx = Math.abs(d[1]) * (w / Math.max(v.x1 - v.x0, 1e-12));
      ctx.beginPath(); ctx.arc(C[0], C[1], rPx, 0, Math.PI * 2); ctx.stroke();
      ctx.beginPath(); ctx.arc(C[0], C[1], 3, 0, Math.PI * 2); ctx.fill();
      if (s.label) {
        ctx.fillStyle = "#475569"; ctx.font = "11px -apple-system, Segoe UI, sans-serif";
        ctx.textAlign = "left"; ctx.textBaseline = "bottom";
        ctx.fillText(`${s.label} r=${Math.abs(d[1]).toFixed(2)}`, C[0] + rPx * 0.7, C[1] - rPx * 0.7);
      }
    } else if (t === "line") {
      // 无限直线：与视图矩形求交后绘制（视口四角恒在视口内，用它们当交点会让所有直线退化成一条线段）
      const [x1, y1] = d[0], [x2, y2] = d[1];
      const cuts = lineViewportIntersection(x1, y1, x2, y2, v.x0, v.x1, v.y0, v.y1);
      if (cuts.length >= 2) {
        const A = px(cuts[0][0], cuts[0][1]), B = px(cuts[1][0], cuts[1][1]);
        ctx.beginPath(); ctx.moveTo(A[0], A[1]); ctx.lineTo(B[0], B[1]); ctx.stroke();
      }
    } else if (t === "ellipse") {
      const [[cx, cy], rx, ry] = d;
      const sc = w / Math.max(v.x1 - v.x0, 1e-12);
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
      const bw = Math.abs(p2[0] - p1[0]), bh = Math.abs(p2[1] - p1[1]);
      if (s.label) {
        ctx.fillStyle = "#475569"; ctx.font = "11px -apple-system, Segoe UI, sans-serif";
        ctx.textAlign = "left"; ctx.textBaseline = "bottom";
        ctx.fillText(`${s.label} ${bw.toFixed(2)}×${bh.toFixed(2)}`, Math.min(A[0], B[0]) + 6, Math.min(A[1], B[1]) - 6);
      }
    } else if (t === "polygon" && d.length >= 3) {
      ctx.beginPath();
      d.forEach(([X, Y]: Pt, i: number) => {
        const P = px(X, Y);
        if (i === 0) ctx.moveTo(P[0], P[1]); else ctx.lineTo(P[0], P[1]);
      });
      ctx.closePath(); ctx.stroke();
      for (const [X, Y] of d as Pt[]) { const P = px(X, Y); ctx.beginPath(); ctx.arc(P[0], P[1], 2.5, 0, Math.PI * 2); ctx.fill(); }
      if (s.label) {
        const cxw = (d as Pt[]).reduce((a, p) => a + p[0], 0) / d.length;
        const cyw = (d as Pt[]).reduce((a, p) => a + p[1], 0) / d.length;
        const C = px(cxw, cyw);
        ctx.fillStyle = "#475569"; ctx.font = "11px -apple-system, Segoe UI, sans-serif";
        ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText(s.label, C[0], C[1]);
      }
    }
  };

  const draw = useCallback(() => {
    const ctx = ctxRef.current;
    const { w, h } = sizeRef.current;
    if (!ctx || w <= 0 || h <= 0) return;
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const g = gridFor(mode);
    const errs: string[] = [];
    const msg = (e: unknown) => (e && (e as Error).message ? (e as Error).message : String(e));
    try {
      drawCartesianGrid(ctx, w, h, view, g, { showGrid: true });
    } catch (e) { errs.push("grid: " + msg(e)); }
    try {
      // 原版按类型固定 Z 序：点永远在线之上（点 Z=10、其余 Z=5），
      // 所以先画非点图形，再画点；按数组顺序画会让后建的线段盖住先前的点。
      for (const s of shapes) if (s.visible && s.type !== "point") drawShape(ctx, s, w, h, view);
      for (const s of shapes) if (s.visible && s.type === "point") drawShape(ctx, s, w, h, view);
    } catch (e) { errs.push("shapes: " + msg(e)); }
    try {
      /* 构造中的预览（虚线） */
      if (phase !== "idle") {
        const [cx, cy] = cursor;
        ctx.strokeStyle = "rgba(94,129,244,.9)";
        ctx.fillStyle = "rgba(94,129,244,.9)";
        ctx.lineWidth = 1.4;
        ctx.setLineDash([5, 4]);
        const px = (x: number, y: number): Pt => [mapX(view, w, x), mapY(view, h, y)];

        if (phase === "awaitSecond" && tempPts.length) {
          const A = px(tempPts[0][0], tempPts[0][1]), B = px(cx, cy);
          ctx.beginPath(); ctx.moveTo(A[0], A[1]); ctx.lineTo(B[0], B[1]); ctx.stroke();
        } else if (phase === "dragRadius" && tempPts.length) {
          const [ox, oy] = tempPts[0];
          const r = Math.hypot(cx - ox, cy - oy);
          const O = px(ox, oy);
          ctx.beginPath(); ctx.arc(O[0], O[1], r * (w / Math.max(view.x1 - view.x0, 1e-12)), 0, Math.PI * 2); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(O[0], O[1]); ctx.lineTo(mapX(view, w, cx), mapY(view, h, cy)); ctx.stroke();
        } else if (phase === "awaitHRad" && tempPts.length) {
          const [ox, oy] = tempPts[0];
          const O = px(ox, oy);
          ctx.beginPath(); ctx.moveTo(O[0], O[1]); ctx.lineTo(mapX(view, w, cx), O[1]); ctx.stroke();
        } else if (phase === "awaitVRad" && tempPts.length >= 2) {
          const [ox, oy] = tempPts[0];
          const hx = tempPts[1][0];
          const rx = Math.abs(hx - ox), ry = Math.abs(cy - oy);
          if (rx > 0.01 && ry > 0.01) {
            const O = px(ox, oy);
            const sc = w / Math.max(view.x1 - view.x0, 1e-12);
            ctx.beginPath(); ctx.ellipse(O[0], O[1], rx * sc, ry * sc, 0, 0, Math.PI * 2); ctx.stroke();
          }
        } else if (phase === "awaitCorner" && tempPts.length) {
          const [ox, oy] = tempPts[0];
          const A = px(ox, oy), B = px(cx, cy);
          ctx.strokeRect(Math.min(A[0], B[0]), Math.min(A[1], B[1]), Math.abs(B[0] - A[0]), Math.abs(B[1] - A[1]));
        } else if (phase === "buildPoly" && tempPts.length) {
          const pts = tempPts.concat([[cx, cy]]);
          ctx.beginPath();
          pts.forEach(([X, Y], i) => { const P = px(X, Y); if (i === 0) ctx.moveTo(P[0], P[1]); else ctx.lineTo(P[0], P[1]); });
          ctx.stroke();
          for (const [X, Y] of tempPts) { const P = px(X, Y); ctx.beginPath(); ctx.arc(P[0], P[1], 3.5, 0, Math.PI * 2); ctx.fill(); }
        }
        ctx.setLineDash([]);
      }
    } catch (e) { errs.push("preview: " + msg(e)); }
    // 提示文字
    ctx.fillStyle = gridFor(mode).label;
    ctx.font = "11.5px -apple-system, Segoe UI, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "bottom";
    const hint = SNAP_HINT[phase];
    ctx.fillText(
      `光标 (${cursor[0].toFixed(2)}, ${cursor[1].toFixed(2)})${hint ? " · " + hint : ""}` +
      ` · 网格 ${gridStep().toFixed(2)}`,
      8, h - 6
    );
    if (typeof window !== "undefined") {
      const ww = window as unknown as { __geoErrors?: unknown; __geoState?: unknown };
      ww.__geoErrors = errs;
      // 与 __geoErrors 同类的诊断出口：让测试能精确读到构造状态机与视图（不靠像素猜）
      ww.__geoState = { state: phase, tempPts: tempPts.length, cursor: [...cursor], view: { ...view }, cssW: w, cssH: h };
    }
  }, [shapes, view, selectedId, mode, phase, tempPts, cursor, gridStep]);

  useEffect(() => { draw(); }, [draw]);

  /* 工具切换时取消未完成的构造，并清空选中（原版 set_tool 会 _setSelection(None)） */
  useEffect(() => {
    setPhase("idle");
    setTempPts([]);
    onSelect?.(null);
    // onSelect 变化不该重置构造状态：只在 tool 变化时跑
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tool]);

  /* apiRef：把 cancelConstruction / resetView 交给页面（等价 Vue 的 defineExpose） */
  useEffect(() => {
    if (apiRef) apiRef.current = { cancelConstruction, resetView };
    return () => { if (apiRef) apiRef.current = null; };
  }, [apiRef, cancelConstruction, resetView]);

  /* 画布尺寸：首帧 + ResizeObserver；尺寸变化时把视图修正回等比（原版 fitInView KeepAspectRatio） */
  const drawRef = useRef(draw);
  drawRef.current = draw;
  const viewRef = useRef(view);
  viewRef.current = view;
  useEffect(() => {
    const cv = innerRef.current;
    if (!cv) return;
    ctxRef.current = cv.getContext("2d");
    const resize = () => {
      const w = cv.clientWidth, h = cv.clientHeight;
      if (w <= 0 || h <= 0) return;
      const dpr = window.devicePixelRatio || 1;
      cv.width = Math.round(w * dpr);
      cv.height = Math.round(h * dpr);
      sizeRef.current = { w, h };
      const v = viewRef.current;
      const cy = (v.y0 + v.y1) / 2;
      const next = equalAspectView(v.x0, v.x1, cy, w, h);
      viewRef.current = next;
      setView(next);
      drawRef.current();
    };
    resize();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
    ro?.observe(cv);
    return () => ro?.disconnect();
  }, []);

  const worldAt = (e: React.MouseEvent): Pt => {
    const el = innerRef.current!;
    const rect = el.getBoundingClientRect();
    const { w, h } = sizeRef.current;
    return [unmapX(view, w, e.clientX - rect.left), unmapY(view, h, e.clientY - rect.top)];
  };

  return (
    <canvas
      ref={setRefs}
      className="geo-canvas"
      data-tour="geometry_canvas"
      onMouseDown={(e) => {
        // 中键：原版任意工具下都临时切"拖手"平移、不改当前工具
        if (e.button === 1) {
          e.preventDefault();
          dragRef.current = { kind: "pan", x: e.clientX, y: e.clientY, view: { ...view } };
          if (innerRef.current) innerRef.current.style.cursor = "grabbing";
          return;
        }
        if (e.button !== 0) return;
        const [wx, wy] = worldAt(e);
        const p = snapPoint(wx, wy);

        if (tool === "pan") {
          dragRef.current = { kind: "pan", x: e.clientX, y: e.clientY, view: { ...view } };
          if (innerRef.current) innerRef.current.style.cursor = "grabbing";
          return;
        }

        if (tool === "select") {
          const s = pickShape(wx, wy);
          onSelect?.(s ? s.id : null);
          if (s) dragRef.current = { kind: "shape", id: s.id, last: [wx, wy] };
          drawRef.current();
          return;
        }

        // 构造类工具：状态机
        switch (tool) {
          case "point":
            onCreate?.({ type: "point", data: [p[0], p[1]] });
            break;
          case "segment":
          case "vector":
          case "line":
            if (phase === "idle") { setTempPts([p]); setPhase("awaitSecond"); }
            else {
              if (Math.hypot(p[0] - tempPts[0][0], p[1] - tempPts[0][1]) > 1e-9) {
                onCreate?.({ type: tool as ShapeType, data: [tempPts[0], p] });
              }
              setPhase("idle"); setTempPts([]);
            }
            break;
          case "circle":
            if (phase === "idle") { setTempPts([p]); setPhase("dragRadius"); }
            else {
              const r = Math.hypot(p[0] - tempPts[0][0], p[1] - tempPts[0][1]);
              if (r > 0.01) onCreate?.({ type: "circle", data: [tempPts[0], r] });
              setPhase("idle"); setTempPts([]);
            }
            break;
          case "ellipse":
            if (phase === "idle") { setTempPts([p]); setPhase("awaitHRad"); }
            else if (phase === "awaitHRad") { setTempPts([tempPts[0], [p[0], 0]]); setPhase("awaitVRad"); }
            else if (phase === "awaitVRad") {
              const rx = Math.abs(tempPts[1][0] - tempPts[0][0]);
              const ry = Math.abs(p[1] - tempPts[0][1]);
              if (rx > 0.01 && ry > 0.01) onCreate?.({ type: "ellipse", data: [tempPts[0], rx, ry] });
              setPhase("idle"); setTempPts([]);
            }
            break;
          case "rect":
            if (phase === "idle") { setTempPts([p]); setPhase("awaitCorner"); }
            else {
              if (Math.hypot(p[0] - tempPts[0][0], p[1] - tempPts[0][1]) > 1e-9) {
                onCreate?.({ type: "rect", data: [tempPts[0], p] });
              }
              setPhase("idle"); setTempPts([]);
            }
            break;
          case "polygon":
            if (phase === "buildPoly") setTempPts(tempPts.concat([p]));
            else { setTempPts([p]); setPhase("buildPoly"); }
            break;
          default: break;
        }
        drawRef.current();
      }}
      onMouseMove={(e) => {
        const [wx, wy] = worldAt(e);
        const p = snapPoint(wx, wy);
        setCursor(p);

        const d = dragRef.current;
        if (d && d.kind === "pan") {
          const { w, h } = sizeRef.current;
          setView(panBy(d.view, w, h, e.clientX - d.x, e.clientY - d.y));
          return;
        }
        if (d && d.kind === "shape") {
          const dx = wx - d.last[0], dy = wy - d.last[1];
          onMove?.({ id: d.id, dx, dy });
          d.last = [wx, wy];
          return;
        }
        // 悬停光标反馈
        if (innerRef.current) {
          if (tool === "select") innerRef.current.style.cursor = pickShape(wx, wy) ? "grab" : "default";
          else if (tool === "pan") innerRef.current.style.cursor = "grab";
          else innerRef.current.style.cursor = "crosshair";
        }
      }}
      onMouseUp={() => {
        if (dragRef.current?.kind === "pan" && innerRef.current) innerRef.current.style.cursor = "grab";
        dragRef.current = null;
      }}
      onMouseLeave={() => { dragRef.current = null; }}
      onDoubleClick={(e) => {
        /* 双击 / 右键。原版 geometry_canvas.py:731-737：右键在"构造多边形且已 ≥3 点"时提交，
         * 否则**取消当前构造**（此前非多边形场景直接 return，既不取消也不阻止默认行为）。 */
        e.preventDefault();
        if (tool === "polygon" && phase === "buildPoly") {
          const pts = tempPts.slice();
          // DOM 双击会在 dblclick 之前投递**两次** mousedown（每次都会追加一个顶点），
          // 所以要把所有与前一顶点重合的点都去掉，而不是只弹一个。
          while (
            pts.length >= 2 &&
            Math.hypot(pts[pts.length - 1][0] - pts[pts.length - 2][0],
                       pts[pts.length - 1][1] - pts[pts.length - 2][1]) < gridStep() * 0.25
          ) {
            pts.pop();
          }
          if (pts.length >= 3) onCreate?.({ type: "polygon", data: pts });
          setPhase("idle"); setTempPts([]);
          drawRef.current();
          return;
        }
        cancelConstruction();
      }}
      onContextMenu={(e) => {
        e.preventDefault();
        if (tool === "polygon" && phase === "buildPoly") {
          const pts = tempPts.slice();
          while (
            pts.length >= 2 &&
            Math.hypot(pts[pts.length - 1][0] - pts[pts.length - 2][0],
                       pts[pts.length - 1][1] - pts[pts.length - 2][1]) < gridStep() * 0.25
          ) {
            pts.pop();
          }
          if (pts.length >= 3) onCreate?.({ type: "polygon", data: pts });
          setPhase("idle"); setTempPts([]);
          drawRef.current();
          return;
        }
        cancelConstruction();
      }}
      onWheel={(e) => {
        e.preventDefault();
        const el = innerRef.current!;
        const rect = el.getBoundingClientRect();
        const px = e.clientX - rect.left, py = e.clientY - rect.top;
        const { w, h } = sizeRef.current;
        // 原版滚轮步长 1.15（此前是 0.9/1.11）
        setView(zoomAt(view, w, h, px, py, e.deltaY < 0 ? 1 / 1.15 : 1.15));
      }}
    />
  );
}
