import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import PlotCanvas from "./PlotCanvas";
import type { Curve, Intersection, Sample, UserPoint, View } from "./PlotCanvas";
import ExpressionList, { type Expr } from "./ExpressionList";
import ParamSlider from "./ParamSlider";
import { usePlotSampling } from "./usePlotSampling";
import { parseExpr, validate } from "@shared/plot/plotMath.js";
import { colorAt } from "@shared/plot/colors.js";
import { engineCall, isHosted } from "@shared/bridge.js";
import { defaultView, fitBounds, viewW, viewH, DEFAULT_X_MIN, DEFAULT_X_MAX } from "@shared/plot/view.js";
import { exportCanvas } from "@shared/plot/exportImage.js";
import { loadPlotPage, isViewLike, usePlotWorkspace } from "../lib/plotWorkspace";
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

/**
 * 初始视图。defaultView() 在 TS 里的返回类型带着 `| null`：那是 JS 侧 prefs 的类型
 * （「绘图默认范围」的四个输入框都可以留空，类型上都是 number|null）。
 * 但 view.js:21-27 只在 plotRangeState() === "fixed"（四项都填好、且 min<max）时才
 * 返回那份固定范围，返回时四项必然都是数字；否则它自己按宽高比算出数字 ——
 * 两种情况拿到的都是完整视图。这里把这条不变式写成显式判断（数值原样使用，
 * 一个字节都不改）：万一真拿到 null（正常路径不可达），退回等比自动视图 ——
 * 与 view.js 的默认分支用同一组常量、同一套算法。
 */
function initialView(w: number, h: number): View {
  const v = defaultView(w, h);
  if (typeof v.x0 === "number" && typeof v.x1 === "number"
    && typeof v.y0 === "number" && typeof v.y1 === "number") {
    return { x0: v.x0, x1: v.x1, y0: v.y0, y1: v.y1 };
  }
  const halfY = ((DEFAULT_X_MAX - DEFAULT_X_MIN) / 2) * (h / Math.max(w, 1));
  return { x0: DEFAULT_X_MIN, x1: DEFAULT_X_MAX, y0: -halfY, y1: halfY };
}

/** 2D 函数绘图页（照抄 Vue 版 PlotView.vue 的模板与样式，只把渲染层换成 React） */
export default function PlotPage({
  gridMode = "rect" as "rect" | "polar",
  onStatusText,
  routePath = "#/plot/2d",
}: {
  gridMode?: "rect" | "polar";
  /** 采样状态回传给外壳的状态栏（Vue 版由 App 持有 statusText） */
  onStatusText?: (t: string) => void;
  /** 本页路由。工作区按 `route.path` 分页存（2d 与 polar 各一份），
   *  导出文件名也用它 —— 所以必须由外层如实传进来，不能在本页写死（BUGS.md B14/B15）。 */
  routePath?: string;
}) {
  /* ── 工作区还原（BUGS.md B14）──────────────────────────────────────────────
   * 载荷形状与 Vue 版 PlotView.vue 的 capturePlot() **逐字一致**（`kind:"plot"` +
   * expressions/view/gridMode/showGrid/params），这样老工作区文件照样能读、
   * `pages()["/plot/2d"].view` 这些断言也继续成立。
   * 还原放在 useState 的**惰性初值**里（不是 effect）：首帧就带着还原值渲染，
   * 于是"默认值盖掉还原内容"这个问题从根上不存在。 */
  const saved = loadPlotPage(routePath, "plot");
  const savedExprs = Array.isArray(saved?.expressions) ? (saved!.expressions as { text?: unknown; color?: unknown; visible?: unknown }[]) : null;
  const [rows, setRows] = useState<Expr[]>(() =>
    savedExprs && savedExprs.length
      ? savedExprs.map((e, i) => ({
          id: nextId++,
          text: String(e.text ?? ""),
          color: typeof e.color === "string" ? e.color : colorAt(i),
          visible: e.visible !== false,
          error: null,
        }))
      : [{ id: nextId++, text: "y=x^2", color: colorAt(0), visible: true, error: null }]
  );
  const [activeId, setActiveId] = useState<number | null>(() => rows[0]?.id ?? 1);
  const [view, setView] = useState<View>(() =>
    isViewLike(saved?.view) ? (saved!.view as View) : initialView(800, 600)
  );
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [showGrid, setShowGrid] = useState(() => saved?.showGrid !== false);
  const [mode, setMode] = useState<"rect" | "polar">(() =>
    saved?.gridMode === "polar" ? "polar" : saved?.gridMode === "rect" ? "rect" : gridMode
  );
  const [paramValues, setParamValues] = useState<Record<string, number>>(() =>
    saved?.params && typeof saved.params === "object" ? { ...(saved.params as Record<string, number>) } : {}
  );
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

  /* 参数：从各行表达式的**解析结果**里取自由符号（与 Vue 版同一来源）。
   * ⚠ 不能用 extractParams(text, [...]) 那种"按名字排除"的做法：极坐标 r=f(θ) 里的
   * r 是**因变量**、不是参数，按名字排除会把它当成滑块（cdp-plot-p4 就是这么挂的）；
   * parseExpr 知道表达式类型，才能正确区分。 */
  const paramNames = useMemo(() => {
    const set = new Set<string>();
    for (const r of rows) {
      const p = parseExpr(r.text);
      for (const n of (p.params || [])) set.add(n);
    }
    return [...set].sort();
  }, [rows]);

  const params = useMemo(() => {
    const out: Record<string, number> = {};
    for (const n of paramNames) out[n] = paramValues[n] ?? 1;
    return out;
  }, [paramNames, paramValues]);

  /* 聚焦的那条曲线画粗一点（与 Vue 版 PlotView.vue:95 一致）。
   * ⚠ 这一段以前传的是 `emphasis: r.emphasis` —— 而**全 React 工程没有任何地方给它赋过值**，
   * 于是画布侧 `PlotCanvas.tsx:224` 那句 `ctx.lineWidth = c.emphasis ? 4 : 2.5` 永远走 else 分支：
   * 字段有人消费、却没人生产（BUGS.md B13）。现在由这里产生。 */
  const curves: Curve[] = useMemo(
    () => rows.map((r) => ({ id: r.id, text: r.text, color: r.color, visible: r.visible, emphasis: r.id === activeId })),
    [rows, activeId]
  );

  /* 变更即回写工作区（对应 Vue 版 PlotView.vue:701 的 `watch([...], () => setPage(...))`）。
   * 只存"你在编辑什么"：表达式、视野、网格/极坐标、参数值；**结果一律不存**（能重算）。
   * ⚠ deps 必须覆盖所有会被存下来的状态，否则会出现"改了但不落盘"。 */
  usePlotWorkspace(routePath, [rows, view, mode, showGrid, paramValues], () => ({
    kind: "plot",
    expressions: rows.map((r) => ({ text: r.text, color: r.color, visible: r.visible })),
    view: { x0: view.x0, x1: view.x1, y0: view.y0, y1: view.y1 },
    gridMode: mode,
    showGrid,
    params: { ...params },
  }));

  const { samples, userPoints, status, grids, addUserPoint, moveUserPoint, clearUserPoints } =
    usePlotSampling(rows, view, params, size);

  /* 画布真实尺寸一到就按它重设视野 —— 对齐 Vue 版 PlotView.onMounted 的那一步。
   *
   * 为什么必须有：`defaultView(800,600)` 只是**占位**（世界 y 只有 ±7.5），真实的
   * 视野要由画布的宽高比决定（x∈[-10,10]，y 跨度 = 10 · h/w，世界 1:1）。
   * 少了这一步，画布是竖的而视野还是按 4:3 算的 —— 表现为"曲线贴不上坐标、
   * 上下两边大片空白"，几何类断言（cdp-plot-accuracy / truth / extrema-domain）会成片失败。
   * 只在第一次拿到真实尺寸时设，之后用户平移缩放不再被覆盖。 */
  const sizedRef = useRef(!!saved);   // 从工作区还原过视野 → 首次拿到真实尺寸时**不要**再覆盖它
  useEffect(() => {
    if (sizedRef.current || size.w <= 0 || size.h <= 0) return;
    sizedRef.current = true;
    setView(initialView(size.w, size.h));
  }, [size.w, size.h]);

  /* 页内状态行：**采样状态与导出结果共用一行**（与 Vue 版一致）。
   * 为什么要一个本地 state 而不是直接渲染 status.text：导出结果需要能暂时盖住采样状态，
   * 否则用户刚点完导出、采样一刷新就把"已导出图片：…"冲掉了（BUGS.md B15）。 */
  const [line, setLine] = useState(() => (saved ? "已从工作区还原" : ""));
  const showLine = (msg: string) => { setLine(msg); onStatusText?.(msg); };
  useEffect(() => {
    setLine(status.text);
    onStatusText?.(status.text);
  }, [status.text, onStatusText]);

  /* 测试/排障钩子 `window.__mfPlot` —— 与项目里 `__mfWorkspace` / `__mfPrefs` /
   * `__mfSanitize` / `__mfPush` 同一做法：CDP 够不到 React 的 state，而这些状态
   * 恰恰是端到端最需要能读的东西。
   *
   * 为什么必须暴露「视图」：视图 {x0,x1,y0,y1} 是缩放/平移/「缩放到适应」这类交互
   * **唯一**可观测的结果。只靠数像素证明不了"视图真的变了"（曲线在原地也能有像素），
   * 于是 BUGS.md B3 那种"按钮点了抛异常、视图纹丝不动"的缺陷没有任何用例抓得住。
   *
   * 刻意**不写依赖数组**：每次渲染都重跑，闭包里的 view/size/status 才不会过期。 */
  const viewRef = useRef(view);
  useEffect(() => {
    viewRef.current = view;
    try {
      (window as unknown as { __mfPlot?: unknown }).__mfPlot = {
        view: () => viewRef.current,
        size: () => size,
        status: () => status.text,
      };
    } catch { /* 非浏览器环境忽略 */ }
  });

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

  /* 行内校验：任何一次表达式改动都要重算（Vue 版是 watch(expressions, deep)）。
   * ⚠ 原来只在 rows.length 变化时跑，而且是从 ExpressionList 的 onChange() 里调——
   * 那一刻父组件的 rows 还是**改之前**的，于是"括号不匹配"这类错误永远晚一拍、
   * 界面上根本不显示。这里改成对 rows 变化做校验，并且**无变化时返回原数组**，
   * 既不会多渲染一次，也不会自激成死循环。 */
  useEffect(() => {
    setRows((prev) => {
      let changed = false;
      const next = prev.map((r) => {
        let err: string | null = null;
        if (r.text.trim()) {
          /* 先做语法体检（括号配对等），再问解析器 —— 与 Vue 版 validateAll 同一顺序：
           * parseExpr 对"y=(x+1" 这类输入是宽容的，只靠它会一声不响。 */
          err = validate(r.text);
          if (!err) {
            const p = parseExpr(r.text);
            if (!p.valid) err = p.error || "表达式无法解析";
          }
        }
        if (err !== r.error) { changed = true; return { ...r, error: err }; }
        return r;
      });
      return changed ? next : prev;
    });
  }, [rows]);

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
    /* 只喂"当前视图里看得见"的点（Vue 版同一策略，也是实测 bug 的修法）：
     * 采样范围是视图的 1.5 倍，里面的离群值（e^x 在 x=15 处 y≈3.3e6）会把范围算爆，
     * 等比修正再把量级搬到另一轴 —— 点「缩放到适应」后 x0 变成 -2.7e6、
     * 整条曲线塌成一条线（cdp-plot-truth 的"适应后曲线仍然可见/仍有横向展开"两条）。 */
    /* ⚠ 这里必须用 React 的 state 值本身：`view` 是 useState 的值，不是 Vue 的 ref
     * （写成 view.value 会得到 undefined，紧接着的 v.x0 就抛 TypeError）。
     * 本行曾是 Vue 版 PlotView.vue 搬迁时漏改的残留，见 BUGS.md B3。 */
    const v = view;
    const padX = viewW(v) * 0.02, padY = viewH(v) * 0.02;
    const all: [number, number][] = [];
    const inside: [number, number][] = [];
    for (const [id, list] of Object.entries(samples)) {
      const row = rows.find((r) => String(r.id) === String(id));
      if (row && row.visible === false) continue;
      for (const p of list) {
        if (!p) continue;
        const [x, y] = p;
        if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
        all.push([x, y]);
        if (x >= v.x0 - padX && x <= v.x1 + padX && y >= v.y0 - padY && y <= v.y1 + padY) inside.push([x, y]);
      }
    }
    const cv = canvasRef.current;
    const w = cv?.clientWidth ?? size.w, h = cv?.clientHeight ?? size.h;
    // 视图内的点太少（例如刚进页面就点适应）时退回全部有限点
    const fit = fitBounds(inside.length >= 2 ? inside : all, w, h);
    if (fit) setView(fit);   // 视图一变，采样 effect 会自动重采
  };

  const resetView = () => {
    const cv = canvasRef.current;
    setView(initialView(cv?.clientWidth ?? size.w, cv?.clientHeight ?? size.h));
  };

  /* 导出图片。**必须把结果显示出来**（BUGS.md B15）：只调 exportCanvas() 不管返回值，
   * 用户就完全不知道导到哪去了、失败也没有原因 —— 正是套件里"不是静默"那两条断言抓的东西。
   * 另外 routePath 以前写死成 "#/plot/2d"，于是极坐标页导出的默认文件名也是 plot-2d（已改用它传进来的真路由）。 */
  const exportImage = () => {
    const cv = canvasRef.current;
    if (!cv) return;
    const r = exportCanvas(cv, { routePath, defaultName: mode === "polar" ? "polar-plot" : "plot", note: mode === "polar" ? "极坐标" : "2D 函数" });
    showLine(
      r.ok
        ? `已导出图片：${r.path}（${r.width}×${r.height}，${Math.round((r.bytes || 0) / 1024)} KB）`
        : (r.canceled ? "已取消导出" : `导出失败：${r.error}`)
    );
  };

  /** 曲线在给定自变量取值处的函数值（引擎求值，带参数）—— 拖动点吸附用 */
  const curveValueAt = (curveId: number, t: number, axis: "x" | "y"): number | null => {
    const row = rows.find((r) => r.id === curveId);
    if (!row) return null;
    const p = parseExpr(row.text);
    if (!p || !p.valid) return null;
    const r = engineCall("expr_eval_vars", { expr: p.body, var: axis, x: t, vars: params });
    const v = r && !r.isError ? Number(r.value) : NaN;
    return Number.isFinite(v) ? v : null;
  };

  /** 点击曲线加点：把"属于哪条曲线"一起记下来（拖动时要沿它吸附） */
  const handlePickPoint = (x: number, y: number, curveId: number) => {
    addUserPoint(x, y, rows.find((r) => r.id === curveId)?.color ?? rows[0]?.color ?? "#c74440", curveId);
  };

  /** 拖动已有点：沿它所属的曲线滑动（对齐 Vue 版 handleDragPoint）
   * —— 显式曲线跟 x、竖直曲线跟 y，其它类型不动。绝不把点拖到曲线外。 */
  const handleDragPoint = (id: number, world: [number, number]) => {
    const pt = userPoints.find((p) => p.id === id);
    if (!pt || pt.curveId == null) return;
    const row = rows.find((r) => r.id === pt.curveId);
    if (!row) return;
    const type = parseExpr(row.text)?.type;
    const [wx, wy] = world;
    if (type === "explicit") {
      const y = curveValueAt(pt.curveId, wx, "x");
      if (y === null) return;
      moveUserPoint(id, wx, y);
    } else if (type === "vertical") {
      const x = curveValueAt(pt.curveId, wy, "y");
      if (x === null) return;
      moveUserPoint(id, x, wy);
    }
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

        <div className="side-status">{line}</div>
      </aside>

      {/* 右侧：画布 + 浮动视图控制（Desmos 右上角按钮） */}
      <div className="desmos-main">
        <PlotCanvas
          view={view}
          onViewChange={setView}
          curves={curves}
          samples={samples as Record<number, Sample[]>}
          grids={grids}
          points={userPoints}
          intersections={showIntersections ? intersectionList : []}
          extrema={showExtrema ? extremaList : []}
          gridMode={mode}
          showGrid={showGrid}
          onSizeChange={(w, h) => setSize({ w, h })}
          onPickPoint={handlePickPoint}
          onDragPoint={handleDragPoint}
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
