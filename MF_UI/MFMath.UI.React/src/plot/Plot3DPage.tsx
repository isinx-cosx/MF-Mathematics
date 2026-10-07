import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import SurfaceCanvas from "./SurfaceCanvas";
import type { SurfaceGrid, SurfaceView } from "./SurfaceCanvas";
import { loadPlotPage, usePlotWorkspace, numOr, boolOr, strOr, numsOr } from "../lib/plotWorkspace";
import ParamSlider from "./ParamSlider";
import { validate, toEngineExpr } from "@shared/plot/plotMath.js";
import { linspace } from "@shared/plot/sampling.js";
import { engineCall, isHosted } from "@shared/bridge.js";
import { exportCanvas } from "@shared/plot/exportImage.js";
import "../styles/plot-3d.css";

/**
 * Plot3DPage — 3D 曲面（对照 Vue 版 views/plot/Plot3DView.vue 逐行移植）
 * 左：表达式 z = f(x, y) + 参数滑块 + 渲染选项
 * 右：曲面画布（拖拽旋转 / 滚轮缩放 / 重置视角）
 * 计算：网格值由 C++ 引擎 expr_eval_grid 求值（支持参数代入）
 *
 * DOM 契约与 Vue 版逐字一致（cdp-plot-3d 依赖）：`.input`（默认 sin(x)*cos(y)）、
 * `.status`（要含「引擎网格 48×48」）、`.chk input`（[0] 曲面填充 / [1] 线框叠加）、
 * `input[type=range]`（[0] 定义域 / [1] 网格密度）、`.param-name`/`.param-slider`、
 * `.vc-btn[title="重置视角"]`。
 */

const KNOWN = new Set(["pi", "e", "sin", "cos", "tan", "exp", "log", "sqrt", "abs", "sinh", "cosh", "tanh",
  "asin", "acos", "atan", "floor", "ceil", "round", "sign", "pow", "cbrt", "log2", "log10"]);

const DEFAULT_CFG = { min: -10, max: 10, step: 0.1 };
/** 默认视角：yaw/pitch/zoom。pitch 就是仰角，取原版 view_init(elev=25) 的 25°=0.4363 rad */
const DEFAULT_VIEW: SurfaceView = { yaw: -0.6, pitch: 0.4363, zoom: 1 };

/** 提取 z = f(x,y) 的函数体：
 *  支持 "z=..." / "f(x,y)=..." / 直接写表达式（隐含 z = ...） */
function surfaceBodyOf(text: string): string {
  const t = String(text || "").trim();
  if (!t) return "";
  let body = t;
  const m = t.match(/^[a-zA-Z_]\w*(\([^)]*\))?\s*=\s*(.+)$/);
  if (m) {
    const lhs = t.slice(0, t.indexOf("=")).trim();
    if (/^z$/i.test(lhs) || /^\w+\(/.test(lhs)) body = m[2];
    else return "";   // 非 z=f(x,y) 形式
  }
  return toEngineExpr(body);
}

/** 自由参数（除 x、y 外的标识符；后面跟 ( 的当函数调用） */
function collectParams(body: string): string[] {
  if (!body) return [];
  const out = new Set<string>();
  const re = /[a-zA-Z_][a-zA-Z0-9_]*/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(body)) !== null) {
    const name = m[0];
    if (/^\s*\(/.test(body.slice(m.index + name.length))) continue;
    if (KNOWN.has(name) || name === "x" || name === "y") continue;
    out.add(name);
  }
  return [...out].sort();
}

export default function Plot3DPage({ routePath = "#/plot/3d" }: { routePath?: string }) {
  const hosted = isHosted();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [statusText, setStatusText] = useState("就绪");

  /* 工作区还原（BUGS.md B14）：形状不符就用默认值，逐项类型检查（文件是用户可手改的）。
   * 这一页在 Vue 版时代也**没有**接过工作区，所以这是补齐而不是回退。 */
  const saved = loadPlotPage(routePath, "plot3d");
  const savedView = saved?.view as Record<string, unknown> | undefined;
  const [exprInput, setExprInput] = useState(() => strOr(saved?.exprInput, "sin(x)*cos(y)"));
  const [exprError, setExprError] = useState<string | null>(null);
  const [params, setParams] = useState<Record<string, number>>(() => numsOr(saved?.params));
  const [paramConfig, setParamConfig] = useState<Record<string, { min: number; max: number; step: number }>>({});

  const [view, setView] = useState<SurfaceView>(() => {
    const zoom = numOr(savedView?.zoom, DEFAULT_VIEW.zoom);
    return {
      yaw: numOr(savedView?.yaw, DEFAULT_VIEW.yaw),
      pitch: numOr(savedView?.pitch, DEFAULT_VIEW.pitch),
      zoom: zoom > 0 ? zoom : DEFAULT_VIEW.zoom,   // zoom=0 会让曲面消失，坏值就退回默认
    };
  });
  const [showSurface, setShowSurface] = useState(() => boolOr(saved?.showSurface, true));
  const [showWireframe, setShowWireframe] = useState(() => boolOr(saved?.showWireframe, false));
  const [gridN, setGridN] = useState(() => numOr(saved?.gridN, 48));   // 网格密度（每轴）
  const [domain, setDomain] = useState(() => numOr(saved?.domain, 5)); // x,y ∈ [-domain, domain]

  /* 变更即回写工作区；只存输入与视野，不存算出来的网格。 */
  usePlotWorkspace(routePath, [exprInput, view, showSurface, showWireframe, gridN, domain, params], () => ({
    kind: "plot3d",
    exprInput,
    view: { ...view },
    showSurface,
    showWireframe,
    gridN,
    domain,
    params: { ...params },
  }));

  const [grid, setGrid] = useState<SurfaceGrid | null>(null);

  const surfaceBody = useMemo(() => surfaceBodyOf(exprInput), [exprInput]);
  const paramNames = useMemo(() => collectParams(surfaceBody), [surfaceBody]);

  /** 参数集合变化 → 补默认值 / 删掉不再出现的（与 Vue 版 watch(paramNames) 一致） */
  useEffect(() => {
    setParams((prev) => {
      const next = { ...prev };
      let changed = false;
      for (const n of paramNames) if (!(n in next)) { next[n] = 1; changed = true; }
      for (const k of Object.keys(next)) if (!paramNames.includes(k)) { delete next[k]; changed = true; }
      return changed ? next : prev;
    });
    setParamConfig((prev) => {
      const cfg = { ...prev };
      let changed = false;
      for (const n of paramNames) if (!(n in cfg)) { cfg[n] = { ...DEFAULT_CFG }; changed = true; }
      for (const k of Object.keys(cfg)) if (!paramNames.includes(k)) { delete cfg[k]; changed = true; }
      return changed ? cfg : prev;
    });
  }, [paramNames]);

  const updateParamConfig = useCallback((name: string, conf: { min: number; max: number; step: number }) => {
    const min = Math.min(conf.min, conf.max - 1e-9);
    const max = Math.max(conf.max, min + 1e-9);
    setParamConfig((prev) => ({ ...prev, [name]: { min, max, step: conf.step } }));
    setParams((prev) => {
      const v = prev[name];
      if (typeof v !== "number") return prev;
      const clamped = Math.min(Math.max(v, min), max);
      return clamped !== v ? { ...prev, [name]: clamped } : prev;
    });
  }, []);

  /* ── 网格采样（引擎） ── */
  const sampleSurface = useCallback(() => {
    if (!surfaceBody) { setGrid(null); setStatusText("请输入 z = f(x, y)"); return; }
    if (!hosted) { setStatusText("浏览器预览：无引擎桥，曲面不绘制"); return; }
    const n = gridN;
    const xs = linspace(-domain, domain, n);
    const ys = linspace(-domain, domain, n);
    /* ⚠ 这里**刻意保持同步**，是算过的、不是漏接（BUGS.md B5）：
     * 规模 = n²，而上面 gridN 滑块的 max 是 **96** ⇒ 最多 96² = 9216 个点，
     * 远低于 asyncPolicy 给 expr_eval_grid 的 2.5e5 阈值 —— 即 shouldRunAsync() 在这一页
     * 恒为 false，接上后台通道也只会空转（还要把整条调用链拆成 async）。
     * **将来若把滑块上限提到 500 以上（>2.5e5），必须改成 engineCallAsync**，
     * 照 PlotFractalPage.tsx 里 mandelbrot 那段（shouldRunAsync + engineCallAsync + 进度）。 */
    const r = engineCall("expr_eval_grid", { expr: surfaceBody, xs, ys, vars: params });
    if (r && !r.isError && Array.isArray(r.value) && r.value.length === n * n) {
      const values = r.value as number[];
      setGrid({ xs, ys, values });
      let finite = 0;
      for (const v of values) if (typeof v === "number" && isFinite(v)) finite++;
      setStatusText(`引擎网格 ${n}×${n} = ${finite} 个有效值`);
      setExprError(null);
    } else {
      setGrid(null);
      setExprError(r && r.isError ? String(r.value).slice(0, 90) : "网格求值失败");
      setStatusText("求值失败");
    }
  }, [surfaceBody, hosted, gridN, domain, params]);

  /* 表达式/参数/密度/定义域变化 → 重采；首帧也跑一次（Vue 版用 rAF 排到首帧） */
  useEffect(() => { sampleSurface(); }, [sampleSurface]);

  /* 输入行内校验 */
  useEffect(() => { setExprError(validate(exprInput)); }, [exprInput]);

  /** 导出当前画布为 PNG（2x、不透明底），结果写进状态栏 */
  const exportImage = () => {
    const r = exportCanvas(canvasRef.current, { routePath, note: "3D 曲面" });
    setStatusText(r.ok
      ? `已导出图片：${r.path}（${r.width}×${r.height}）`
      : (r.canceled ? "已取消导出" : `导出失败：${r.error}`));
  };

  /** 重置视角：与 Vue 版 SurfaceCanvas.resetView 落点一致（原版 view_init(elev=25, azim=-50)） */
  const resetView = () => setView({ ...DEFAULT_VIEW });

  return (
    <div className="plot3d-layout">
      <aside className="plot3d-side">
        <div className="field">
          <label>曲面表达式</label>
          <input className="input mono" spellCheck={false} placeholder="z = sin(x)*cos(y)"
                 value={exprInput} onChange={(e) => setExprInput(e.target.value)} />
          {exprError && <div className="err">{exprError}</div>}
        </div>

        <div className="field">
          <label>定义域 x,y ∈ [-{domain}, {domain}]</label>
          <input className="slider" type="range" min={1} max={20} step={0.5}
                 value={domain} onChange={(e) => setDomain(Number(e.target.value))} />
        </div>

        <div className="field">
          <label>网格密度 {gridN}×{gridN}</label>
          <input className="slider" type="range" min={16} max={96} step={4}
                 value={gridN} onChange={(e) => setGridN(Number(e.target.value))} />
        </div>

        <div className="field opts">
          <label className="chk"><input type="checkbox" checked={showSurface}
                 onChange={(e) => setShowSurface(e.target.checked)} /> 曲面填充</label>
          <label className="chk"><input type="checkbox" checked={showWireframe}
                 onChange={(e) => setShowWireframe(e.target.checked)} /> 线框叠加</label>
        </div>

        {paramNames.length > 0 && (
          <div className="slider-box">
            <div className="slider-title">参数</div>
            {paramNames.map((n) => (
              <ParamSlider
                key={n}
                name={n}
                value={params[n] ?? 1}
                min={paramConfig[n]?.min ?? -10}
                max={paramConfig[n]?.max ?? 10}
                step={paramConfig[n]?.step ?? 0.1}
                onValueChange={(val) => setParams((prev) => ({ ...prev, [n]: val }))}
                onConfigChange={(c) => updateParamConfig(n, c)}
              />
            ))}
          </div>
        )}

        <div className="status">{statusText}</div>
      </aside>

      <div className="plot3d-main">
        <SurfaceCanvas
          canvasRef={canvasRef}
          grid={grid}
          view={view}
          onViewChange={setView}
          showSurface={showSurface}
          showWireframe={showWireframe}
        />
        <div className="view-controls">
          <button className="vc-btn" title="重置视角" onClick={resetView}>⟲</button>
          <button className="vc-btn" title="导出图片（PNG，2 倍像素）" onClick={exportImage}>⤓</button>
        </div>
      </div>
    </div>
  );
}
