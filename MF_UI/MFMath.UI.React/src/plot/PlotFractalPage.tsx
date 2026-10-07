import { useCallback, useEffect, useRef, useState } from "react";
import { engineCall, engineCallAsync, isHosted } from "@shared/bridge.js";
import { describeWork, shouldRunAsync } from "@shared/engine/asyncPolicy.js";
import { exportCanvas } from "@shared/plot/exportImage.js";
import { loadPlotPage, usePlotWorkspace, numOr, boolOr, strOr } from "../lib/plotWorkspace";
import type { JobProgress } from "../lib/jobProgress";
import "../styles/plot-fractal.css";

/**
 * PlotFractalPage — Mandelbrot 分形（对照 Vue 版 views/plot/PlotFractalView.vue 逐行移植）
 *  · 迭代计数由 C++ 引擎 mandelbrot 计算（复平面窗口 + 分辨率 + 最大迭代）
 *  · 左键单击放大 1.5×、右键把窗口中心挪到点击处、拖拽平移、双击/⟲ 重置、滚轮以光标为中心缩放
 *  · 多种配色方案；状态行报告"引擎 mandelbrot W×H · 耗时 ms"
 *
 * DOM 契约与 Vue 版逐字一致（cdp-plot-fractal 依赖）：
 *  `.status`、`input[type=range]`[0]=迭代/[1]=分辨率、`select`=配色、`.region-btn`（含「海马谷」）、
 *  `.vc-btn[title="重置视图"]`、`.field > label`（要含「最大迭代次数 300」）。
 */

type View = { xmin: number; xmax: number; ymin: number; ymax: number };

/* 后台任务进度的载荷形状见 ../lib/jobProgress —— 复平面页也要用同一份，
 * 所以抽出去了（原来这里有一份本地定义，两处容易各改一半）。 */

/** 复平面窗口。原版 plot/fractal/workspace.py:137-138 默认 x∈[-2,2]、y∈[-1.5,1.5]，
 *  且 origin="lower" 约定 y 向上（ymin 在屏幕下方）。 */
const DEFAULT_VIEW: View = { xmin: -2.0, xmax: 2.0, ymin: -1.5, ymax: 1.5 };

type Stop = [number, [number, number, number]];

const SCHEMES: Record<string, Stop[]> = {
  classic: [
    [0, [0, 7, 100]],
    [0.16, [32, 107, 203]],
    [0.42, [237, 255, 255]],
    [0.6425, [255, 170, 0]],
    [0.8575, [0, 2, 0]],
    [1.0, [0, 7, 100]],
  ],
  sunset: [
    [0, [10, 10, 40]],
    [0.3, [120, 20, 90]],
    [0.6, [240, 120, 40]],
    [0.85, [255, 220, 120]],
    [1.0, [10, 10, 40]],
  ],
  mono: [
    [0, [0, 0, 0]],
    [1.0, [255, 255, 255]],
  ],
  ocean: [
    [0, [2, 20, 60]],
    [0.35, [20, 120, 180]],
    [0.7, [120, 220, 220]],
    [1.0, [2, 20, 60]],
  ],
};

function schemeColor(stops: Stop[], t: number): [number, number, number] {
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

/** 缩放到已知的兴趣区域 */
const REGIONS: { name: string; v: View }[] = [
  { name: "全景", v: { ...DEFAULT_VIEW } },
  { name: "海马谷", v: { xmin: -0.8, xmax: -0.72, ymin: 0.06, ymax: 0.12 } },
  { name: "象谷", v: { xmin: -0.76, xmax: -0.74, ymin: 0.1, ymax: 0.115 } },
  { name: "螺旋", v: { xmin: -1.79, xmax: -1.77, ymin: 0.0, ymax: 0.015 } },
  { name: "迷你集", v: { xmin: -1.768, xmax: -1.766, ymin: 0.0015, ymax: 0.0035 } },
];

export default function PlotFractalPage({ routePath = "#/plot/fractal" }: { routePath?: string }) {
  const hosted = isHosted();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const ctxRef = useRef<CanvasRenderingContext2D | null>(null);
  const sizeRef = useRef({ w: 0, h: 0 });
  const dragRef = useRef<{ x: number; y: number; v: View; fx: number; fy: number; moved: boolean } | null>(null);
  /** 正在跑的后台分形任务：新一次渲染会 abort 上一次（拖拽/缩放时不必手动取消） */
  const jobAbortRef = useRef<AbortController | null>(null);

  /* 工作区还原（BUGS.md B14）：这一页在 Vue 版时代也没接过工作区，属于补齐。
   * 视野要**保持合法**（xmin<xmax、ymin<ymax），坏值退回默认 —— 否则画布会塌成 0 宽。 */
  const saved = loadPlotPage(routePath, "plot-fractal");
  const savedFv = saved?.view as Record<string, unknown> | undefined;
  const [view, setView] = useState<View>(() => {
    const v: View = {
      xmin: numOr(savedFv?.xmin, DEFAULT_VIEW.xmin),
      xmax: numOr(savedFv?.xmax, DEFAULT_VIEW.xmax),
      ymin: numOr(savedFv?.ymin, DEFAULT_VIEW.ymin),
      ymax: numOr(savedFv?.ymax, DEFAULT_VIEW.ymax),
    };
    return v.xmin < v.xmax && v.ymin < v.ymax ? v : { ...DEFAULT_VIEW };
  });
  /** 原版默认迭代 256（下拉 [64,128,256,512,1024] 的第 3 项，workspace.py:135,173） */
  const [maxIter, setMaxIter] = useState(() => numOr(saved?.maxIter, 256));
  const [scheme, setScheme] = useState(() => strOr(saved?.scheme, "classic"));
  const [smooth, setSmooth] = useState(() => boolOr(saved?.smooth, true));
  /** 渲染分辨率上限（保证交互流畅；越大越清晰） */
  const [maxSide, setMaxSide] = useState(() => numOr(saved?.maxSide, 560));
  const [statusText, setStatusText] = useState("就绪");

  /* 变更即回写工作区；不存算出来的分形像素（能重算）。 */
  usePlotWorkspace(routePath, [view, maxIter, scheme, smooth, maxSide], () => ({
    kind: "plot-fractal",
    view: { ...view },
    maxIter,
    scheme,
    smooth,
    maxSide,
  }));

  /** 引擎计算 + 图像渲染（重活走异步，见下面的分流） */
  const render = useCallback(async () => {
    const ctx = ctxRef.current;
    const cv = canvasRef.current;
    if (!ctx || !cv) return;
    const { w: cssW0, h: cssH0 } = sizeRef.current;
    const cssW = cssW0 > 0 ? cssW0 : cv.clientWidth;
    const cssH = cssH0 > 0 ? cssH0 : cv.clientHeight;
    if (cssW <= 0 || cssH <= 0) return;
    if (sizeRef.current.w <= 0) sizeRef.current = { w: cssW, h: cssH };
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    if (!hosted) {
      ctx.fillStyle = "#0a0f1c";
      ctx.fillRect(0, 0, cssW, cssH);
      ctx.fillStyle = "#94a3b8";
      ctx.font = "13px -apple-system, Segoe UI, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("浏览器预览：无引擎桥，分形不渲染", cssW / 2, cssH / 2);
      setStatusText("浏览器预览：无引擎桥");
      return;
    }

    // 采样分辨率（保持宽高比，限制最长边）
    const scale = Math.min(1, maxSide / Math.max(cssW, cssH));
    const w = Math.max(32, Math.round(cssW * scale));
    const h = Math.max(32, Math.round(cssH * scale));

    const args = {
      xmin: view.xmin, xmax: view.xmax, ymin: view.ymin, ymax: view.ymax,
      width: w, height: h, max_iter: maxIter,
    };
    /* 重活走异步：规模 = w×h×max_iter，1200×1200×1024 ≈ 1.5e9 次迭代会把渲染进程主线程
     * 占满（窗口白屏 + 系统判定"未响应"）。分流依据见 shared/engine/asyncPolicy.js。
     * 新一次渲染先 abort 上一次 —— 拖拽/缩放时不需要用户手动点取消。 */
    jobAbortRef.current?.abort();
    const ac = new AbortController();
    jobAbortRef.current = ac;
    const t0 = performance.now();
    let r;
    if (shouldRunAsync("mandelbrot", args)) {
      setStatusText(`计算中… 0.0s · ${describeWork("mandelbrot", args)}`);
      r = await engineCallAsync("mandelbrot", args, {
        signal: ac.signal,
        onProgress: (p: JobProgress) =>
          setStatusText(`计算中… ${((p.elapsedMs || 0) / 1000).toFixed(1)}s · ${describeWork("mandelbrot", args)}`),
      });
      // 已被更新的一次渲染取代：直接收手，别把上一张图盖回来
      if (ac.signal.aborted || (r && r.canceled)) return;
    } else {
      r = engineCall("mandelbrot", args);
    }
    const dt = performance.now() - t0;

    if (!r || r.isError || !Array.isArray(r.value) || r.value.length !== w * h) {
      ctx.fillStyle = "#0a0f1c";
      ctx.fillRect(0, 0, cssW, cssH);
      ctx.fillStyle = "#f87171";
      ctx.font = "13px -apple-system, Segoe UI, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("引擎分形计算失败", cssW / 2, cssH / 2);
      setStatusText(r && r.isError ? String(r.value).slice(0, 80) : "分形计算失败");
      return;
    }

    // 生成图像（引擎返回行主序：第 0 行对应 ymin）
    const off = document.createElement("canvas");
    off.width = w; off.height = h;
    const octx = off.getContext("2d")!;
    const img = octx.createImageData(w, h);
    const data = img.data;
    const iters = r.value as number[];
    const mi = maxIter;
    const stops = SCHEMES[scheme] || SCHEMES.classic;
    for (let i = 0; i < w * h; i++) {
      /* 引擎行主序：第 0 行 = ymin（数学下方，见 MF_Mathematics/fractal_api.cpp:30-31）。
       * canvas 第 0 行在屏幕顶部，所以必须按 (h-1-row) 取行，才能让 y 轴朝上——
       * 原版 workspace.py:242 用 imshow(..., origin="lower")，是同一个约定。
       * 之前直接取 iters[i]，图像被上下镜像，与滚轮/拖拽的 y 约定相反。 */
      const row = (i / w) | 0, col = i % w;
      const it = iters[(h - 1 - row) * w + col];
      const idx = i * 4;
      if (it >= mi) {
        data[idx] = 12; data[idx + 1] = 12; data[idx + 2] = 20; data[idx + 3] = 255;
      } else if (smooth) {
        // 平滑着色：用迭代数做连续映射，减少色带
        const [cr, cg, cb] = schemeColor(stops, Math.pow(it / mi, 0.45));
        data[idx] = cr; data[idx + 1] = cg; data[idx + 2] = cb; data[idx + 3] = 255;
      } else {
        const [cr, cg, cb] = schemeColor(stops, it / mi);
        data[idx] = cr; data[idx + 1] = cg; data[idx + 2] = cb; data[idx + 3] = 255;
      }
    }
    octx.putImageData(img, 0, 0);
    // 图像已在上面按 (h-1-row) 翻转成"y 向上"（与原版 origin="lower" 一致）
    ctx.drawImage(off, 0, 0, w, h, 0, 0, cssW, cssH);

    // 信息叠加
    ctx.fillStyle = "rgba(0,0,0,.45)";
    ctx.fillRect(0, 0, cssW, 22);
    ctx.fillStyle = "#e2e8f0";
    ctx.font = "11.5px -apple-system, Segoe UI, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    const zoom = (DEFAULT_VIEW.xmax - DEFAULT_VIEW.xmin) / Math.max(1e-12, view.xmax - view.xmin);
    const cy = (view.ymin + view.ymax) / 2;
    ctx.fillText(
      `中心 ${((view.xmin + view.xmax) / 2).toFixed(6)} ${cy >= 0 ? "+" : "-"} ${Math.abs(cy).toFixed(6)}i` +
      ` · 缩放 ${zoom.toFixed(1)}× · 迭代 ${mi} · ${w}×${h} · ${dt.toFixed(0)}ms`,
      8, 11
    );
    setStatusText(`引擎 mandelbrot ${w}×${h} · ${dt.toFixed(0)} ms`);
  }, [hosted, view, maxIter, scheme, smooth, maxSide]);

  /* 任何参数/窗口变化 → 重绘（与 Vue 版的两个 watch 等价） */
  useEffect(() => { render(); }, [render]);

  /* 画布尺寸：首帧 + ResizeObserver（回调里用 ref 取最新 render，避免反复重订阅） */
  const renderRef = useRef(render);
  renderRef.current = render;
  useEffect(() => {
    const cv = canvasRef.current;
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
      renderRef.current();
    };
    resize();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
    ro?.observe(cv);
    return () => ro?.disconnect();
  }, []);

  /* ── 交互：拖拽平移 + 点击缩放（对齐原版 workspace.py:256-286）──
   *
   *   · 左键单击：w = 跨度/3 → 新跨度 = 2/3 旧跨度 = **放大 1.5×**，点击处成为新中心
   *   · 右键单击：把窗口重定中心到点击处、**不改变缩放**（原版注释写"缩小"，但按代码算没有缩放
   *     —— 这里按代码的实际行为对齐，不按注释）
   *   · 双击：重置视图；拖拽平移是 Vue 额外加的（原版状态栏宣称支持但没实现），只在"真的移动过"时平移
   */
  const fractionAt = (e: React.MouseEvent) => {
    const r = canvasRef.current!.getBoundingClientRect();
    const { w, h } = sizeRef.current;
    return [(e.clientX - r.left) / Math.max(w, 1), (e.clientY - r.top) / Math.max(h, 1)] as [number, number];
  };
  /** 屏幕比例 → 复坐标（屏幕上方 = ymax，与原版的 origin="lower" 一致） */
  const complexAt = (fx: number, fy: number): [number, number] => [
    view.xmin + fx * (view.xmax - view.xmin),
    view.ymax - fy * (view.ymax - view.ymin),
  ];
  /** 以 (cx, cy) 为中心、跨度乘以 factor */
  const setViewAround = (cx: number, cy: number, factor: number) => {
    const hw = (view.xmax - view.xmin) * factor / 2;
    const hh = (view.ymax - view.ymin) * factor / 2;
    setView({ xmin: cx - hw, xmax: cx + hw, ymin: cy - hh, ymax: cy + hh });
  };

  const resetView = () => setView({ ...DEFAULT_VIEW });

  /** 导出当前分形图为 PNG（2x、不透明底）；结果写进状态行 */
  const exportImage = () => {
    const r = exportCanvas(canvasRef.current, { routePath, note: "分形" });
    setStatusText(r.ok
      ? `已导出图片：${r.path}（${r.width}×${r.height}）`
      : (r.canceled ? "已取消导出" : `导出失败：${r.error}`));
  };

  return (
    <div className="frac-layout">
      <aside className="frac-side">
        <div className="field">
          <label>最大迭代次数 {maxIter}</label>
          {/* 原版迭代档位 [64,128,256,512,1024]（workspace.py:172）；这里保留连续滑块，
              但上限对齐到原版最大值 1024，默认 256 与原版一致 */}
          <input className="slider" type="range" min={30} max={1024} step={10}
                 value={maxIter} onChange={(e) => setMaxIter(Number(e.target.value))} />
        </div>
        <div className="field">
          <label>渲染分辨率 {maxSide} px（越长越慢）</label>
          <input className="slider" type="range" min={240} max={1200} step={40}
                 value={maxSide} onChange={(e) => setMaxSide(Number(e.target.value))} />
        </div>
        <div className="field">
          <label>配色方案</label>
          <select className="select" value={scheme} onChange={(e) => setScheme(e.target.value)}>
            <option value="classic">经典（蓝白橙）</option>
            <option value="sunset">日落</option>
            <option value="ocean">海洋</option>
            <option value="mono">黑白</option>
          </select>
        </div>
        <div className="field opts">
          <label className="chk">
            <input type="checkbox" checked={smooth} onChange={(e) => setSmooth(e.target.checked)} /> 平滑着色
          </label>
        </div>

        <div className="field">
          <label>兴趣区域</label>
          <div className="regions">
            {REGIONS.map((r) => (
              <button key={r.name} className="region-btn" onClick={() => setView({ ...r.v })}>{r.name}</button>
            ))}
          </div>
        </div>

        <div className="field hints">
          <div>左键单击：以点击处为中心放大 1.5×</div>
          <div>右键单击：把窗口中心挪到点击处（不改变缩放）</div>
          <div>拖拽：平移复平面　双击 / ⟲：重置视图</div>
          <div>滚轮：以光标处为中心缩放</div>
          <div>提示：迭代次数越高，边界细节越丰富</div>
        </div>

        <div className="status">{statusText}</div>
      </aside>

      <div className="frac-main">
        <canvas
          ref={canvasRef}
          className="frac-canvas"
          onMouseDown={(e) => {
            const [fx, fy] = fractionAt(e);
            if (e.button === 2) {
              // 原版 workspace.py:271-275：右键把窗口中心挪到点击处，跨度不变
              const [cx, cy] = complexAt(fx, fy);
              setViewAround(cx, cy, 1);
              return;
            }
            if (e.button !== 0) return;
            dragRef.current = { x: e.clientX, y: e.clientY, v: { ...view }, fx, fy, moved: false };
            if (canvasRef.current) canvasRef.current.style.cursor = "grabbing";
          }}
          onMouseMove={(e) => {
            const d = dragRef.current;
            if (!d) return;
            const { w, h } = sizeRef.current;
            if (Math.abs(e.clientX - d.x) > 2 || Math.abs(e.clientY - d.y) > 2) d.moved = true;
            const dx = (e.clientX - d.x) / Math.max(w, 1) * (d.v.xmax - d.v.xmin);
            const dy = (e.clientY - d.y) / Math.max(h, 1) * (d.v.ymax - d.v.ymin);
            setView({
              xmin: d.v.xmin - dx, xmax: d.v.xmax - dx,
              ymin: d.v.ymin + dy, ymax: d.v.ymax + dy,   // 屏幕向下 → 复平面 y 增大
            });
          }}
          onMouseUp={() => {
            const d = dragRef.current;
            dragRef.current = null;
            if (canvasRef.current) canvasRef.current.style.cursor = "grab";
            if (d && !d.moved) {
              // 单击（没拖动过）→ 原版左键行为：以点击处为中心放大 1.5×
              const [cx, cy] = complexAt(d.fx, d.fy);
              setViewAround(cx, cy, 2 / 3);
            }
          }}
          onMouseLeave={() => {
            const d = dragRef.current;
            dragRef.current = null;
            if (d && !d.moved) {
              const [cx, cy] = complexAt(d.fx, d.fy);
              setViewAround(cx, cy, 2 / 3);
            }
          }}
          onDoubleClick={resetView}
          onContextMenu={(e) => e.preventDefault()}
          onWheel={(e) => {
            e.preventDefault();
            const r = canvasRef.current!.getBoundingClientRect();
            const { w, h } = sizeRef.current;
            const fx = (e.clientX - r.left) / Math.max(w, 1);
            const fy = (e.clientY - r.top) / Math.max(h, 1);
            const cx = view.xmin + fx * (view.xmax - view.xmin);
            const cy = view.ymax - fy * (view.ymax - view.ymin);   // 屏幕 y 向下 → 复平面 y 减小
            const factor = e.deltaY < 0 ? 0.55 : 1.8;
            const nw = Math.max(1e-13, Math.min(8, (view.xmax - view.xmin) * factor));
            const nh = Math.max(1e-13, Math.min(8, (view.ymax - view.ymin) * factor));
            setView({
              xmin: cx - fx * nw, xmax: cx + (1 - fx) * nw,
              ymin: cy - (1 - fy) * nh, ymax: cy + fy * nh,
            });
          }}
        />
        <div className="view-controls">
          <button className="vc-btn" title="重置视图" onClick={resetView}>⟲</button>
          <button className="vc-btn" title="导出图片（PNG，2 倍像素）" onClick={exportImage}>⤓</button>
        </div>
      </div>
    </div>
  );
}
