import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import PlotCanvas from "./PlotCanvas";
import type { Curve, Intersection, Sample, UserPoint, View } from "./PlotCanvas";
import ExpressionList, { type Expr } from "./ExpressionList";
import ParamSlider from "./ParamSlider";
import { usePlotSampling } from "./usePlotSampling";
import { parseExpr, extractParams } from "@shared/plot/plotMath.js";
import { colorAt } from "@shared/plot/colors.js";
import { engineCall, isHosted } from "@shared/bridge.js";
import { defaultView, fitBounds } from "@shared/plot/view.js";
import { exportCanvas } from "@shared/plot/exportImage.js";
import { prettyNum, textLatex } from "../lib/plotText";
import MathLatex from "../components/MathLatex";
import "../styles/plot-view.css";

/* ── 符号驻点的展示辅助（与 Vue 版 PlotView 的 branchLabel / branchClass 逐字一致）──
 * 引擎返回的 kind 是英文字段名，界面必须给中文；否则用户看到的是 "outside-domain"
 * 这种内部词。未知 kind 原样返回，不猜（不静默变成空白）。 */
function branchLabel(kind?: string): string {
  switch (kind) {
    case "maximum": return "极大值";
    case "minimum": return "极小值";
    case "degenerate": return "退化(二阶导为0)";
    case "no-real-value": return "无实驻点";
    case "no-critical-point": return "无极值点";
    case "outside-domain": return "无极值点(驻点在定义域外)";
    default: return String(kind || "");
  }
}
function branchClass(kind?: string): string {
  if (kind === "maximum") return "max";
  if (kind === "minimum") return "min";
  return "na";
}

/** extrema_sym 返回的 branches 形状（只声明用到的字段） */
type SymBranch = { assume?: string; kind?: string; note?: string; exists?: boolean; f_value?: string };
type SymPoint = { x: string; branches?: SymBranch[] };

type SymbolicExtremum = {
  expr: string;
  color: string;
  error?: string;
  note?: string;
  points?: unknown[];
  params?: string[];
  method?: string;
  domain?: unknown[];
};

let nextId = 1;

/** 2D 函数绘图页（照抄 Vue 版 PlotView.vue 的模板与样式，只把渲染层换成 React） */
export default function PlotPage({
  gridMode = "rect" as "rect" | "polar",
  onStatusText,
}: {
  gridMode?: "rect" | "polar";
  /** 采样状态回传给外壳的状态栏（Vue 版由 App 持有 statusText） */
  onStatusText?: (t: string) => void;
}) {
  const [rows, setRows] = useState<Expr[]>([
    { id: nextId++, text: "y=x^2", color: colorAt(0), visible: true, error: null },
  ]);
  const [activeId, setActiveId] = useState<number | null>(1);
  const [view, setView] = useState<View>(() => defaultView(800, 600));
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [showGrid, setShowGrid] = useState(true);
  const [mode, setMode] = useState<"rect" | "polar">(gridMode);
  const [paramValues, setParamValues] = useState<Record<string, number>>({});
  const [paramConfig, setParamConfig] = useState<Record<string, { min: number; max: number; step: number }>>({});
  const [intersectionList, setIntersectionList] = useState<(Intersection & { exact?: boolean })[]>([]);
  const [intersectionNotice, setIntersectionNotice] = useState("");
  const [extremaList, setExtremaList] = useState<{ x: number; y: number; kind: "max" | "min" }[]>([]);
  const [symbolicExtrema, setSymbolicExtrema] = useState<SymbolicExtremum[]>([]);
  /* 极值/交点**默认不自动画到画布上**：点必须由用户自己添加（点击曲线）。
   * 分析照算，只进侧栏。 */
  const [showExtrema] = useState(false);
  const [showIntersections] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  /* 参数：从各行表达式提取自由参数，生成滑块 */
  const paramNames = useMemo(() => {
    const set = new Set<string>();
    for (const r of rows) for (const n of extractParams(r.text, ["x", "y", "t", "theta"])) set.add(n);
    return [...set];
  }, [rows]);

  const params = useMemo(() => {
    const out: Record<string, number> = {};
    for (const n of paramNames) out[n] = paramValues[n] ?? 1;
    return out;
  }, [paramNames, paramValues]);

  const curves: Curve[] = useMemo(
    () => rows.map((r) => ({ id: r.id, text: r.text, color: r.color, visible: r.visible, emphasis: r.emphasis })),
    [rows]
  );

  const { samples, userPoints, status, addUserPoint, clearUserPoints } =
    usePlotSampling(rows, view, params, size);

  /* 画布真实尺寸一到就按它重设视野 —— 对齐 Vue 版 PlotView.onMounted 的那一步。
   *
   * 为什么必须有：`defaultView(800,600)` 只是**占位**（世界 y 只有 ±7.5），真实的
   * 视野要由画布的宽高比决定（x∈[-10,10]，y 跨度 = 10 · h/w，世界 1:1）。
   * 少了这一步，画布是竖的而视野还是按 4:3 算的 —— 表现为"曲线贴不上坐标、
   * 上下两边大片空白"，几何类断言（cdp-plot-accuracy / truth / extrema-domain）会成片失败。
   * 只在第一次拿到真实尺寸时设，之后用户平移缩放不再被覆盖。 */
  const sizedRef = useRef(false);
  useEffect(() => {
    if (sizedRef.current || size.w <= 0 || size.h <= 0) return;
    sizedRef.current = true;
    setView(defaultView(size.w, size.h));
  }, [size.w, size.h]);

  /* 采样状态 → 外壳状态栏 */
  useEffect(() => { onStatusText?.(status.text); }, [status.text, onStatusText]);

  /** 校验：解析失败就写在行内（对齐 Desmos） */
  const validateAll = useCallback(() => {
    setRows((prev) =>
      prev.map((r) => {
        if (!r.text.trim()) return { ...r, error: null };
        const p = parseExpr(r.text);
        return { ...r, error: p.valid ? null : (p.error || "表达式无法解析") };
      })
    );
  }, []);

  useEffect(() => { validateAll(); }, [rows.length, validateAll]);

  /** 求交点（引擎：符号精确解优先，超越方程走数值回退） */
  const computeIntersections = useCallback(() => {
    setIntersectionNotice("");
    if (!isHosted()) { setIntersectionList([]); return; }
    const vis = rows
      .map((r) => ({ row: r, parsed: parseExpr(r.text) }))
      .filter((x) => x.row.visible && x.parsed.valid && x.parsed.type === "explicit");
    const out: (Intersection & { exact?: boolean })[] = [];
    for (let i = 0; i < vis.length; i++) {
      for (let j = i + 1; j < vis.length; j++) {
        const r = engineCall("intersections", {
          expr1: vis[i].parsed.body,
          expr2: vis[j].parsed.body,
          var: "x",
          vars: params,
          xmin: view.x0, xmax: view.x1,
        });
        if (!r || r.isError || !r.value || !Array.isArray(r.value.points)) continue;
        if (r.value.realness === "conditional" && r.value.realnessReason) {
          setIntersectionNotice(
            r.value.delta ? `Δ = ${r.value.delta}，符号随参数变化：${r.value.realnessReason}` : r.value.realnessReason
          );
        }
        for (const pt of r.value.points) {
          if (typeof pt.xNum !== "number" || typeof pt.yNum !== "number") continue;
          out.push({
            x: pt.xNum, y: pt.yNum,
            xLabel: prettyNum(pt.x), yLabel: prettyNum(pt.y),
            exact: !!r.value.exact,
          });
        }
      }
    }
    setIntersectionList(out);
  }, [rows, params, view.x0, view.x1]);

  /** 极值（无参曲线：引擎 local_extrema 精确驻点） */
  const computeExtrema = useCallback(() => {
    if (!isHosted()) { setExtremaList([]); return; }
    const out: { x: number; y: number; kind: "max" | "min" }[] = [];
    for (const r of rows) {
      if (!r.visible) continue;
      const p = parseExpr(r.text);
      if (p.type !== "explicit") continue;
      if ((p.params || []).length > 0) continue;
      const res = engineCall("local_extrema", { expr: p.body, var: "x" });
      if (!res || res.isError || !res.value) continue;
      for (const [x, y] of (res.value.maxima || [])) if (isFinite(x) && isFinite(y)) out.push({ x, y, kind: "max" });
      for (const [x, y] of (res.value.minima || [])) if (isFinite(x) && isFinite(y)) out.push({ x, y, kind: "min" });
    }
    setExtremaList(out);
  }, [rows]);

  /** 含参曲线的符号驻点（展示在侧栏；引擎拒绝求解时也把原因显示出来） */
  const computeSymbolicExtrema = useCallback(() => {
    if (!isHosted()) { setSymbolicExtrema([]); return; }
    const out: SymbolicExtremum[] = [];
    for (const r of rows) {
      if (!r.visible) continue;
      const p = parseExpr(r.text);
      if (p.type !== "explicit" || !(p.params || []).length) continue;
      const res = engineCall("extrema_sym", { expr: p.body, var: "x" });
      if (!res) { out.push({ expr: p.body, color: r.color, error: "引擎无响应" }); continue; }
      if (res.isError) { out.push({ expr: p.body, color: r.color, error: String(res.value) }); continue; }
      if (!res.value || !Array.isArray(res.value.points)) continue;
      out.push({
        expr: p.body, color: r.color, points: res.value.points,
        params: res.value.params || [], method: res.value.solveMethod || "symbolic",
        note: res.value.solveNote || "", domain: res.value.domain || [],
      });
    }
    setSymbolicExtrema(out);
  }, [rows]);

  /* 表达式/参数变化 → 重算交点/极值（与 Vue 版 watch 一致） */
  useEffect(() => {
    computeIntersections();
    computeExtrema();
    computeSymbolicExtrema();
  }, [computeIntersections, computeExtrema, computeSymbolicExtrema]);

  /* 含参曲线的驻点：按**参数取值**分组（先看参数在哪一段，再看该段下各驻点）。
   * 与 Vue 版 symbolicGroups 同构：key = branch.assume，行内去重按 (x, kind, note)。 */
  const symbolicGroups = useMemo(() => {
    const groups: { assume: string; rows: { x: string; kind?: string; note: string; exists?: boolean; fvalue?: string }[] }[] = [];
    const byAssume = new Map<string, (typeof groups)[number]>();
    for (const s of symbolicExtrema) {
      for (const p of (s.points || []) as SymPoint[]) {
        for (const b of p.branches || []) {
          const key = b.assume || "";
          let g = byAssume.get(key);
          if (!g) {
            g = { assume: key, rows: [] };
            byAssume.set(key, g);
            groups.push(g);
          }
          const note = b.note || "";
          const dup = g.rows.some((r) => r.x === p.x && r.kind === b.kind && r.note === note);
          if (!dup) {
            g.rows.push({ x: p.x, kind: b.kind, note, exists: b.exists, fvalue: b.f_value });
          }
        }
      }
    }
    return groups;
  }, [symbolicExtrema]);

  const zoomBy = (factor: number) => {
    const cv = canvasRef.current;
    const w = cv?.clientWidth ?? size.w, h = cv?.clientHeight ?? size.h;
    /* 以画布中心为不动点缩放（与 Vue 版 zoomBy 一致） */
    setView((v) => {
      const cx = w / 2, cy = h / 2;
      const ax = v.x0 + (v.x1 - v.x0) * (cx / Math.max(w, 1));
      const ay = v.y1 - (v.y1 - v.y0) * (cy / Math.max(h, 1));
      return {
        x0: ax - (ax - v.x0) * factor,
        x1: ax + (v.x1 - ax) * factor,
        y0: ay - (ay - v.y0) * factor,
        y1: ay + (v.y1 - ay) * factor,
      };
    });
  };

  const zoomFit = () => {
    const all: [number, number][] = Object.values(samples).flat().filter(Boolean) as [number, number][];
    if (!all.length) return;
    const cv = canvasRef.current;
    setView(fitBounds(all, cv?.clientWidth ?? size.w, cv?.clientHeight ?? size.h));
  };

  const resetView = () => {
    const cv = canvasRef.current;
    setView(defaultView(cv?.clientWidth ?? size.w, cv?.clientHeight ?? size.h));
  };

  const exportImage = () => {
    const cv = canvasRef.current;
    if (!cv) return;
    exportCanvas(cv, { routePath: "#/plot/2d", defaultName: "plot" });
  };

  const handlePickPoint = (x: number, y: number) => {
    addUserPoint(x, y, rows[0]?.color ?? "#c74440");
  };

  const addRow = (index: number) => {
    const id = nextId++;
    setRows((prev) => {
      const next = [...prev];
      next.splice(index + 1, 0, { id, text: "", color: colorAt(next.length), visible: true, error: null });
      return next;
    });
    setActiveId(id);
  };

  const removeRow = (id: number) => setRows((prev) => prev.filter((r) => r.id !== id));

  return (
    <div className="desmos-layout">
      {/* 左侧：表达式列表 + 参数滑块（Desmos 左栏） */}
      <aside className="desmos-side">
        <ExpressionList
          rows={rows}
          activeId={activeId}
          onRowsChange={setRows}
          onActiveIdChange={setActiveId}
          onAdd={addRow}
          onRemove={removeRow}
          onChange={validateAll}
        />

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
                onValueChange={(val) => setParamValues((prev) => ({ ...prev, [n]: val }))}
                onConfigChange={(cfg) => setParamConfig((prev) => ({ ...prev, [n]: cfg }))}
              />
            ))}
          </div>
        )}

        {/* 交点列表（精确解优先） */}
        {intersectionList.length > 0 && (
          <div id="ixList" className="slider-box">
            <div className="slider-title">
              交点
              <span className="pt-count">{intersectionList.length}</span>
            </div>
            {intersectionList.map((it, i) => (
              <div key={i} className="pt-row">
                <span className="pt-dot" />
                <span className="pt-text">({it.xLabel}, {it.yLabel})</span>
                <span className={"pt-badge " + (it.exact ? "exact" : "num")}>
                  {it.exact ? "精确" : "数值"}
                </span>
              </div>
            ))}
            {intersectionNotice && <div className="ix-note">{intersectionNotice}</div>}
          </div>
        )}

        {/* 已创建的点 */}
        {userPoints.length > 0 && (
          <div id="ptList" className="slider-box">
            <div className="slider-title">
              点
              <button className="link-btn" onClick={clearUserPoints}>全部清除</button>
            </div>
            {userPoints.map((p: UserPoint) => (
              <div key={p.id} className="pt-row">
                <span className="pt-dot hollow" style={{ borderColor: p.color }} />
                <span className="pt-text">({prettyNum(p.x)}, {prettyNum(p.y)})</span>
              </div>
            ))}
          </div>
        )}

        {/* 极值（引擎符号求解） */}
        {(extremaList.length > 0 || symbolicExtrema.length > 0) && (
          <div id="extList" className="slider-box">
            <div className="slider-title">
              极值
              <span className="pt-count">{extremaList.length}</span>
            </div>
            {extremaList.map((e, i) => (
              <div key={"e" + i} className="pt-row">
                <span className={"pt-dot diamond " + (e.kind === "max" ? "max" : "min")} />
                <span className="pt-text">
                  {e.kind === "max" ? "极大" : "极小"} ({prettyNum(e.x)}, {prettyNum(e.y)})
                </span>
                <span className="pt-badge exact">精确</span>
              </div>
            ))}
            {symbolicExtrema.map((s, si) => (
              <div key={"se" + si}>
                {s.error && (
                  <div className="pt-sym">
                    <div className="branch-note">该曲线暂无法分析极值：{s.error}</div>
                  </div>
                )}
                {!s.error && s.note && (
                  <div className="pt-sym">
                    <div className="branch-note">{s.note}</div>
                  </div>
                )}
              </div>
            ))}
            {/* 含参曲线：按参数取值分组（块结构 .pt-sym / .branch-head / .pt-branch
                必须与 Vue 版一致 —— 教程引导与端到端用例都按这些类名定位）。
                驻点是符号解（-sqrt(a)、a/2…）：用 KaTeX 排版（MathLatex 带 data-tex），
                而不是把 ASCII 原样贴出来。 */}
            {symbolicGroups.map((g, gi) => (
              <div key={"g" + gi} className="pt-sym">
                <div className="branch-head">
                  <span className="branch-tag strong">{g.assume}</span>
                </div>
                {g.rows.map((r, ri) => (
                  <div key={"r" + ri} className="pt-branch">
                    <span className="branch-x">
                      x = <MathLatex latex={textLatex(r.x)} fallback={r.x} />
                    </span>
                    <span className={"branch-kind " + branchClass(r.kind)}>{branchLabel(r.kind)}</span>
                    {r.exists !== true ? (
                      <span className="branch-note">{r.note}</span>
                    ) : r.fvalue && r.fvalue !== "—" ? (
                      <span className="branch-value">
                        f = <MathLatex latex={textLatex(r.fvalue)} fallback={r.fvalue} />
                      </span>
                    ) : null}
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}

        <div className="side-status">{status.text}</div>
      </aside>

      {/* 右侧：画布 + 浮动视图控制（Desmos 右上角按钮） */}
      <div className="desmos-main">
        <PlotCanvas
          view={view}
          onViewChange={setView}
          curves={curves}
          samples={samples as Record<number, Sample[]>}
          points={userPoints}
          intersections={showIntersections ? intersectionList : []}
          extrema={showExtrema ? extremaList : []}
          gridMode={mode}
          showGrid={showGrid}
          onSizeChange={(w, h) => setSize({ w, h })}
          onPickPoint={handlePickPoint}
          canvasRef={canvasRef}
        />
        <div className="view-controls">
          <button className="vc-btn" title="放大" onClick={() => zoomBy(0.7)}>＋</button>
          <button className="vc-btn" title="缩小" onClick={() => zoomBy(1.4)}>－</button>
          <button className="vc-btn" title="缩放到适应" onClick={zoomFit}>⤢</button>
          <button className="vc-btn" title="重置视图" onClick={resetView}>⟲</button>
          <button className="vc-btn" data-tour="plot.export_button" title="导出图片（PNG，2 倍像素）" onClick={exportImage}>⤓</button>
          <button
            className={"vc-btn" + (mode === "polar" ? " on" : "")}
            title={mode === "polar" ? "切换为直角网格" : "切换为极坐标网格"}
            onClick={() => setMode(mode === "polar" ? "rect" : "polar")}
          >◉</button>
          <button
            className={"vc-btn" + (!showGrid ? " on" : "")}
            title={showGrid ? "隐藏网格" : "显示网格"}
            onClick={() => setShowGrid(!showGrid)}
          >▦</button>
        </div>
      </div>
    </div>
  );
}
