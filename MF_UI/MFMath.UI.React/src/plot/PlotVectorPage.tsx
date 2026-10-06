import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import VectorFieldCanvas from "./VectorFieldCanvas";
import type { FieldView, VectorFieldData } from "./VectorFieldCanvas";
import ParamSlider from "./ParamSlider";
import { toEngineExpr, validate } from "@shared/plot/plotMath.js";
import { linspace } from "@shared/plot/sampling.js";
import { engineCall, isHosted } from "@shared/bridge.js";
import { exportCanvas } from "@shared/plot/exportImage.js";
import "../styles/plot-vector-view.css";

/**
 * PlotVectorPage — 向量场（对照 Vue 版 views/plot/PlotVectorView.vue 逐行移植）
 * 输入 dx = P(x,y)、dy = Q(x,y) → 网格箭头（引擎双网格求值）
 * 控制：网格密度、箭头比例、归一化、按模长着色、参数滑块
 *
 * DOM 契约与 Vue 版**逐字一致**（类名、顺序都不能改）：
 * cdp-plot-vector 靠 `.input`（两个，默认 -y / x）、`.status`（要含「引擎向量场 21×21」）、
 * `.preset-btn`（「径向源」）、`.chk input`（[0] 归一化 / [1] 着色）、
 * 第一个 `input[type=range]`（网格密度）、`.param-name`（参数滑块）来驱动与断言。
 */

const PRESETS = [
  { name: "旋转场", dx: "-y", dy: "x" },
  { name: "径向源", dx: "x", dy: "y" },
  { name: "鞍点", dx: "x", dy: "-y" },
  { name: "涡旋衰减", dx: "-y/(x^2+y^2+1)", dy: "x/(x^2+y^2+1)" },
  { name: "重力场", dx: "-x/(x^2+y^2)^1.5", dy: "-y/(x^2+y^2)^1.5" },
];

const KNOWN = new Set(["pi", "e", "sin", "cos", "tan", "exp", "log", "sqrt", "abs", "sinh", "cosh", "tanh",
  "asin", "acos", "atan", "floor", "ceil", "round", "sign", "pow", "cbrt", "log2", "log10"]);

const DEFAULT_CFG = { min: -10, max: 10, step: 0.1 };

/** 去掉 "dx=" / "P=" 之类前缀，取函数体 */
function bodyOf(text: string): string {
  const t = String(text || "").trim();
  if (!t) return "";
  const m = t.match(/^[a-zA-Z_]\w*\s*=\s*(.+)$/);
  return toEngineExpr(m ? m[1] : t);
}

/** 从两个分量里收集自由参数（排除已知函数名与自变量；后面跟 ( 的当函数调用） */
function collectParams(bodies: string[]): string[] {
  const out = new Set<string>();
  for (const body of bodies) {
    const re = /[a-zA-Z_][a-zA-Z0-9_]*/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(body)) !== null) {
      const name = m[0];
      if (/^\s*\(/.test(body.slice(m.index + name.length))) continue;
      if (KNOWN.has(name) || name === "x" || name === "y") continue;
      out.add(name);
    }
  }
  return [...out].sort();
}

export default function PlotVectorPage({ routePath = "#/plot/vector" }: { routePath?: string }) {
  const hosted = isHosted();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [statusText, setStatusText] = useState("就绪");

  const [dxInput, setDxInput] = useState("-y");
  const [dyInput, setDyInput] = useState("x");
  const [dxError, setDxError] = useState<string | null>(null);
  const [dyError, setDyError] = useState<string | null>(null);

  const dxBody = useMemo(() => bodyOf(dxInput), [dxInput]);
  const dyBody = useMemo(() => bodyOf(dyInput), [dyInput]);

  const paramNames = useMemo(() => collectParams([dxBody, dyBody]), [dxBody, dyBody]);
  const [params, setParams] = useState<Record<string, number>>({});
  const [paramConfig, setParamConfig] = useState<Record<string, { min: number; max: number; step: number }>>({});

  const [view, setView] = useState<FieldView>({ x0: -5, y0: -5, x1: 5, y1: 5 });
  const [density, setDensity] = useState(21);      // 每轴箭头数
  /* 原版 vector_field/workspace.py:185 的 quiver 用单位方向向量 (U/M, V/M) + 颜色编码模长，
   * 即"等长箭头"是原版默认行为；默认 false（长度随模长伸缩）与原版不符。 */
  const [normalize, setNormalize] = useState(true);
  const [colorByMagnitude, setColorByMagnitude] = useState(true);
  const [showGrid, setShowGrid] = useState(true);
  const [arrowScale, setArrowScale] = useState(0);  // 0 = 自动

  const [field, setField] = useState<VectorFieldData | null>(null);

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

  const updateParamConfig = useCallback((name: string, c: { min: number; max: number; step: number }) => {
    const min = Math.min(c.min, c.max - 1e-9);
    const max = Math.max(c.max, min + 1e-9);
    setParamConfig((prev) => ({ ...prev, [name]: { min, max, step: c.step } }));
    setParams((prev) => {
      const v = prev[name];
      if (typeof v !== "number") return prev;
      const clamped = Math.min(Math.max(v, min), max);
      return clamped !== v ? { ...prev, [name]: clamped } : prev;
    });
  }, []);

  /* ── 采样（引擎双网格） ── */
  const sampleField = useCallback(() => {
    if (!hosted) { setStatusText("浏览器预览：无引擎桥"); return; }
    const n = density;
    const xs = linspace(view.x0, view.x1, n);
    const ys = linspace(view.y0, view.y1, n);
    const need = n * n;
    const rdx = engineCall("expr_eval_grid", { expr: dxBody, xs, ys, vars: params });
    const rdy = engineCall("expr_eval_grid", { expr: dyBody, xs, ys, vars: params });
    if (rdx && !rdx.isError && rdy && !rdy.isError &&
        Array.isArray(rdx.value) && Array.isArray(rdy.value) &&
        rdx.value.length === need && rdy.value.length === need) {
      const dx = rdx.value as number[], dy = rdy.value as number[];
      setField({ xs, ys, dx, dy });
      let finite = 0;
      for (let i = 0; i < need; i++) if (isFinite(dx[i]) && isFinite(dy[i])) finite++;
      setStatusText(`引擎向量场 ${n}×${n} · 有效箭头 ${finite}`);
      setDxError(null); setDyError(null);
    } else {
      setField(null);
      setDxError(rdx && rdx.isError ? String(rdx.value).slice(0, 80) : null);
      setDyError(rdy && rdy.isError ? String(rdy.value).slice(0, 80) : null);
      setStatusText("求值失败");
    }
  }, [hosted, density, view, dxBody, dyBody, params]);

  /* 表达式/参数/密度/视图变化 → 重采（与 Vue 版 watch 一致）；首帧也跑一次 */
  useEffect(() => { sampleField(); }, [sampleField]);

  /* 输入行内校验 */
  useEffect(() => {
    setDxError(validate(dxInput));
    setDyError(validate(dyInput));
  }, [dxInput, dyInput]);

  /** 导出当前画布为 PNG（2x、不透明底），结果写进状态栏 */
  const exportImage = () => {
    const r = exportCanvas(canvasRef.current, { routePath, note: "向量场" });
    setStatusText(r.ok
      ? `已导出图片：${r.path}（${r.width}×${r.height}）`
      : (r.canceled ? "已取消导出" : `导出失败：${r.error}`));
  };

  const resetView = () => setView({ x0: -5, y0: -5, x1: 5, y1: 5 });

  return (
    <div className="vf-layout">
      <aside className="vf-side">
        <div className="field">
          <label>dx / dt = P(x, y)</label>
          <input className="input mono" spellCheck={false} placeholder="-y"
                 value={dxInput} onChange={(e) => setDxInput(e.target.value)} />
          {dxError && <div className="err">{dxError}</div>}
        </div>
        <div className="field">
          <label>dy / dt = Q(x, y)</label>
          <input className="input mono" spellCheck={false} placeholder="x"
                 value={dyInput} onChange={(e) => setDyInput(e.target.value)} />
          {dyError && <div className="err">{dyError}</div>}
        </div>

        <div className="field">
          <label>快速预设</label>
          <div className="presets">
            {PRESETS.map((p) => (
              <button key={p.name} className="preset-btn"
                      onClick={() => { setDxInput(p.dx); setDyInput(p.dy); }}>
                {p.name}
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <label>网格密度 {density}×{density}</label>
          <input className="slider" type="range" min={7} max={41} step={2}
                 value={density} onChange={(e) => setDensity(Number(e.target.value))} />
        </div>

        <div className="field">
          <label>箭头长度 {arrowScale === 0 ? "自动" : arrowScale.toFixed(1) + "×"}</label>
          <input className="slider" type="range" min={0} max={1.5} step={0.1}
                 value={arrowScale} onChange={(e) => setArrowScale(Number(e.target.value))} />
        </div>

        <div className="field opts">
          <label className="chk"><input type="checkbox" checked={normalize}
                 onChange={(e) => setNormalize(e.target.checked)} /> 归一化（等长）</label>
          <label className="chk"><input type="checkbox" checked={colorByMagnitude}
                 onChange={(e) => setColorByMagnitude(e.target.checked)} /> 按模长着色</label>
          <label className="chk"><input type="checkbox" checked={showGrid}
                 onChange={(e) => setShowGrid(e.target.checked)} /> 显示网格</label>
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

      <div className="vf-main">
        <VectorFieldCanvas
          canvasRef={canvasRef}
          view={view}
          onViewChange={setView}
          field={field}
          normalize={normalize}
          colorByMagnitude={colorByMagnitude}
          showGrid={showGrid}
          arrowScale={arrowScale}
        />
        <div className="view-controls">
          <button className="vc-btn" title="重置视图" onClick={resetView}>⟲</button>
          <button className="vc-btn" title="导出图片（PNG，2 倍像素）" onClick={exportImage}>⤓</button>
        </div>
      </div>
    </div>
  );
}
