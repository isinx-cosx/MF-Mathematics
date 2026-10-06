import { useCallback, useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { plotMode, plotBackground, onAppearanceChange } from "@shared/bridge.js";
import "../styles/surface-canvas.css";

/**
 * SurfaceCanvas — 3D 曲面渲染（对照 Vue 版 components/plot/SurfaceCanvas.vue 逐行移植）
 *  · 等轴/透视投影：绕 z 轴 yaw、绕水平轴 pitch，可拖拽旋转
 *  · 曲面填充（画家算法按深度排序）+ 简单光照（法向量点积）+ 高度色带
 *  · 可选线框叠加；滚轮缩放
 * 数据来自 C++ 引擎的 expr_eval_grid（网格值由父组件采样后传入）
 *
 * 移植时保持的判断：
 *  · `theme` 默认 **undefined**，不要给 "light"：给了默认值就永远走浅色，
 *    切到深色配色时画布依旧白底（bridge.js:163-177 记录的历史事故）。
 *  · 默认仰角 0.4363 rad = 原版 plot_3d/canvas.py:101 的 view_init(elev=25)。
 */

export type SurfaceView = { yaw: number; pitch: number; zoom: number };
export type SurfaceGrid = { xs: number[]; ys: number[]; values: number[] };

type Props = {
  /** 网格：{xs:[], ys:[], values:[]}（行优先：index = j*nx + i，j 对应 ys） */
  grid: SurfaceGrid | null;
  view: SurfaceView;
  showSurface?: boolean;
  showWireframe?: boolean;
  theme?: string;
  /** z 值裁剪上下限（超出按边界颜色处理） */
  zClamp?: number;
  onViewChange?: (v: SurfaceView) => void;
  canvasRef?: RefObject<HTMLCanvasElement | null>;
};

/** 高度色带（蓝 → 青 → 绿 → 黄 → 红），t ∈ [0,1] */
function heightColor(t: number): [number, number, number] {
  const stops: [number, [number, number, number]][] = [
    [0.0, [59, 130, 246]],
    [0.25, [6, 182, 212]],
    [0.5, [16, 185, 129]],
    [0.75, [250, 204, 21]],
    [1.0, [239, 68, 68]],
  ];
  const x = Math.max(0, Math.min(1, t));
  for (let i = 0; i + 1 < stops.length; i++) {
    const [t0, c0] = stops[i], [t1, c1] = stops[i + 1];
    if (x >= t0 && x <= t1) {
      const k = t1 === t0 ? 0 : (x - t0) / (t1 - t0);
      return [
        Math.round(c0[0] + (c1[0] - c0[0]) * k),
        Math.round(c0[1] + (c1[1] - c0[1]) * k),
        Math.round(c0[2] + (c1[2] - c0[2]) * k),
      ];
    }
  }
  return stops[stops.length - 1][1];
}

export default function SurfaceCanvas({
  grid, view, showSurface = true, showWireframe = false, theme, zClamp = 12,
  onViewChange, canvasRef,
}: Props) {
  const innerRef = useRef<HTMLCanvasElement | null>(null);
  const ctxRef = useRef<CanvasRenderingContext2D | null>(null);
  const sizeRef = useRef({ w: 0, h: 0 });
  const dragRef = useRef<{ x: number; y: number; view: SurfaceView } | null>(null);
  const [mode, setMode] = useState(() => plotMode(theme));

  /* 深浅由「当前配色」决定（theme 只作为显式覆盖）；换主题时重新求值 */
  useEffect(() => {
    setMode(plotMode(theme));
    const off = onAppearanceChange?.(() => setMode(plotMode(theme)));
    return () => { if (typeof off === "function") off(); };
  }, [theme]);

  const isDark = mode === "dark";

  const setRefs = (el: HTMLCanvasElement | null) => {
    innerRef.current = el;
    if (canvasRef) canvasRef.current = el;
  };

  const draw = useCallback(() => {
    const cv = innerRef.current;
    const ctx = ctxRef.current;
    const { w: cssW, h: cssH } = sizeRef.current;
    if (!ctx || cssW <= 0 || cssH <= 0) return;
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // 背景
    ctx.fillStyle = plotBackground();   // 取自当前配色的 --plot-bg，纸质/樱粉等配色下也是同色系
    ctx.fillRect(0, 0, cssW, cssH);

    const g = grid;
    if (!g || !g.xs || !g.ys || !g.values) {
      ctx.fillStyle = isDark ? "#7d8590" : "#94a3b8";
      ctx.font = "13px -apple-system, Segoe UI, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("输入 z = f(x, y) 以绘制曲面", cssW / 2, cssH / 2);
      return;
    }

    const nx = g.xs.length, ny = g.ys.length;
    if (nx < 2 || ny < 2) return;

    const { yaw, pitch, zoom } = view;
    const cx = cssW / 2, cy = cssH / 2;
    const scale = Math.min(cssW, cssH) * 0.22 * zoom;
    const cyaw = Math.cos(yaw), syaw = Math.sin(yaw);
    const cp = Math.cos(pitch), sp = Math.sin(pitch);

    /** 世界坐标 → 屏幕 + 深度（深度越大越远） */
    const project = (x: number, y: number, z: number): [number, number, number] => {
      const x1 = x * cyaw - y * syaw;
      const y1 = x * syaw + y * cyaw;
      const y2 = y1 * cp - z * sp;   // 屏幕竖直分量
      const z2 = y1 * sp + z * cp;   // 深度分量
      return [cx + x1 * scale, cy - y2 * scale, z2];
    };

    // 预投影所有顶点
    const P = new Array<[number, number, number] | null>(nx * ny);
    let zmin = Infinity, zmax = -Infinity;
    for (let j = 0; j < ny; j++) {
      for (let i = 0; i < nx; i++) {
        const idx = j * nx + i;
        const raw = g.values[idx];
        let z = typeof raw === "number" && isFinite(raw) ? raw : NaN;
        if (isFinite(z)) {
          if (z < zmin) zmin = z;
          if (z > zmax) zmax = z;
        }
        const zv = isFinite(z) ? Math.max(-zClamp, Math.min(zClamp, z)) : NaN;
        P[idx] = isFinite(zv) ? project(g.xs[i], g.ys[j], zv) : null;
      }
    }
    if (!isFinite(zmin)) { zmin = -1; zmax = 1; }
    const zspan = Math.max(1e-9, zmax - zmin);

    // 收集四边形 + 深度（画家算法）
    type Quad = { a: number[]; b: number[]; c: number[]; d: number[]; depth: number; zavg: number; shade: number };
    const quads: Quad[] = [];
    for (let j = 0; j + 1 < ny; j++) {
      for (let i = 0; i + 1 < nx; i++) {
        const a = P[j * nx + i], b = P[j * nx + i + 1];
        const c = P[(j + 1) * nx + i + 1], d = P[(j + 1) * nx + i];
        if (!a || !b || !c || !d) continue;
        const depth = (a[2] + b[2] + c[2] + d[2]) / 4;
        // 高度用四顶点均值
        const zs = [
          g.values[j * nx + i], g.values[j * nx + i + 1],
          g.values[(j + 1) * nx + i + 1], g.values[(j + 1) * nx + i],
        ];
        const zavg = zs.reduce((s, v) => s + (isFinite(v) ? v : 0), 0) / 4;
        // 法向量（世界空间近似，用于光照）
        const e1 = [g.xs[i + 1] - g.xs[i], 0, (zs[1] - zs[0]) || 0];
        const e2 = [0, g.ys[j + 1] - g.ys[j], (zs[3] - zs[0]) || 0];
        const nrm = [
          e1[1] * e2[2] - e1[2] * e2[1],
          e1[2] * e2[0] - e1[0] * e2[2],
          e1[0] * e2[1] - e1[1] * e2[0],
        ];
        const nlen = Math.hypot(nrm[0], nrm[1], nrm[2]) || 1;
        const light = [0.4, 0.5, 0.75];
        const llen = Math.hypot(...light);
        const cos = Math.abs((nrm[0] * light[0] + nrm[1] * light[1] + nrm[2] * light[2]) / (nlen * llen));
        quads.push({ a, b, c, d, depth, zavg, shade: 0.55 + 0.45 * cos });
      }
    }
    // 远 → 近
    quads.sort((p, q) => p.depth - q.depth);

    // 绘制
    for (const q of quads) {
      const t = (q.zavg - zmin) / zspan;
      const [r, gch, bch] = heightColor(t);
      const sh = q.shade;
      ctx.fillStyle = `rgb(${Math.round(r * sh)}, ${Math.round(gch * sh)}, ${Math.round(bch * sh)})`;
      ctx.beginPath();
      ctx.moveTo(q.a[0], q.a[1]);
      ctx.lineTo(q.b[0], q.b[1]);
      ctx.lineTo(q.c[0], q.c[1]);
      ctx.lineTo(q.d[0], q.d[1]);
      ctx.closePath();
      if (showSurface) ctx.fill();
      if (showWireframe || !showSurface) {
        ctx.strokeStyle = showSurface
          ? (isDark ? "rgba(255,255,255,.25)" : "rgba(0,0,0,.18)")
          : ctx.fillStyle;
        ctx.lineWidth = showSurface ? 0.6 : 1;
        ctx.stroke();
      }
    }

    // 坐标轴提示（简易：x / y / z 方向线）
    // 三轴颜色取原版 plot_3d/canvas.py:53-55 的 AXIS_X/Y/Z（红/绿/蓝）
    const axes = [
      { to: project(1.2, 0, 0), label: "x", color: "#e74c3c" },
      { to: project(0, 1.2, 0), label: "y", color: "#2ecc71" },
      { to: project(0, 0, Math.max(1.2, (zmax - zmin) * 0.5)), label: "z", color: "#3498db" },
    ];
    const origin = project(0, 0, 0);
    ctx.lineWidth = 1.4;
    ctx.font = "11px -apple-system, Segoe UI, sans-serif";
    ctx.textAlign = "left";
    for (const ax of axes) {
      ctx.strokeStyle = ax.color;
      ctx.beginPath();
      ctx.moveTo(origin[0], origin[1]);
      ctx.lineTo(ax.to[0], ax.to[1]);
      ctx.stroke();
      ctx.fillStyle = ax.color;
      ctx.fillText(ax.label, ax.to[0] + 3, ax.to[1] - 3);
    }

    // 统计信息
    ctx.fillStyle = isDark ? "#7d8590" : "#94a3b8";
    ctx.textAlign = "left";
    ctx.fillText(`网格 ${nx}×${ny} · z ∈ [${zmin.toFixed(2)}, ${zmax.toFixed(2)}]`, 8, cssH - 8);
  }, [grid, view, showSurface, showWireframe, isDark, zClamp]);

  useEffect(() => {
    const cv = innerRef.current;
    if (!cv) return;
    ctxRef.current = cv.getContext("2d");
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

  return (
    <canvas
      ref={setRefs}
      className="surface-canvas"
      onMouseDown={(e) => {
        if (e.button !== 0) return;
        dragRef.current = { x: e.clientX, y: e.clientY, view: { ...view } };
        if (innerRef.current) innerRef.current.style.cursor = "grabbing";
      }}
      onMouseMove={(e) => {
        const d = dragRef.current;
        if (!d) return;
        const dx = e.clientX - d.x, dy = e.clientY - d.y;
        const yaw = d.view.yaw + dx * 0.008;
        // pitch 限制在 (-π/2, π/2)，避免翻转
        const pitch = Math.max(-1.5, Math.min(1.5, d.view.pitch + dy * 0.008));
        onViewChange?.({ ...view, yaw, pitch });
      }}
      onMouseUp={() => {
        dragRef.current = null;
        if (innerRef.current) innerRef.current.style.cursor = "grab";
      }}
      onMouseLeave={() => {
        dragRef.current = null;
        if (innerRef.current) innerRef.current.style.cursor = "grab";
      }}
      onWheel={(e) => {
        e.preventDefault();
        const factor = e.deltaY < 0 ? 1.1 : 0.9;
        const zoom = Math.max(0.2, Math.min(5, view.zoom * factor));
        onViewChange?.({ ...view, zoom });
      }}
    />
  );
}
