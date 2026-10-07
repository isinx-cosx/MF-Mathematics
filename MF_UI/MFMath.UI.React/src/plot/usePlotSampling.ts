import { useCallback, useEffect, useRef, useState } from "react";
import { engineCall, isHosted } from "@shared/bridge.js";
import { parseExpr } from "@shared/plot/plotMath.js";
import { adaptiveSample } from "@shared/plot/sampling.js";
import { viewW, viewH } from "@shared/plot/view.js";
import type { ParsedExpr, Sample, UserPoint, View } from "./PlotCanvas";

/**
 * adaptiveSample 的真实契约。sampling.js 的 JSDoc 把 evalPoints 写成
 * `(ts:number[]) => Array<[number,number]>`，但它的实现**本来就**把 null 当
 * "这里断开"处理：端点或中点为 null 时照样加密、并且把 null 本身插进结果数组
 * （sampling.js:53-67），绘制层再据此断线（1/x 的渐近线、ln x 的定义域外都靠它）。
 * 本项目统一用 `Sample = [number,number] | null` 表示断点，所以这里按真实契约
 * 重新声明一次签名（运行时就是同一个函数、同一个参数顺序，不做任何改写）。
 * 回调也允许直接返回 null（批量求值整批失败时）：adaptiveSample 第一行就会
 * 判 `!world` 并返回空数组。
 */
type AdaptiveSampleFn = (
  evalPoints: (ts: number[]) => Sample[] | null,
  t0: number,
  t1: number,
  toScreen: (p: [number, number]) => [number, number],
  opt?: { initial?: number; maxRounds?: number; tolPx?: number; maxPoints?: number }
) => Sample[];

const sampleAdaptive = adaptiveSample as AdaptiveSampleFn;

export type ExprRow = {
  id: number;
  text: string;
  color: string;
  visible: boolean;
  emphasis?: boolean;
  error?: string | null;
};

export type PlotStatus = { okCount: number; errCount: number; totalPts: number; text: string };

/** 二元网格（隐式方程等值线 / 二元不等式区域）：引擎 expr_eval_grid 的结果，行优先 */
export type PlotGrid = { xs: number[]; ys: number[]; values: number[] };

/** 采样范围取视口的 1.5 倍（左右各外扩 25%）：小幅平移时曲线不断裂 */
const PAD = 0.25;

/** 二元网格每轴点数（与 Vue 版一致：180×180 = 32400，一次引擎调用） */
const GRID_N = 180;

function linspace(a: number, b: number, n: number) {
  const out = new Array(n);
  if (n === 1) { out[0] = a; return out; }
  for (let i = 0; i < n; i++) out[i] = a + ((b - a) * i) / (n - 1);
  return out;
}

/** 一次批量求值（引擎）——长度不符或报错一律当"这轮没有数据"，不猜 */
function batchEval(
  expr: string, varName: string, ts: number[], params: Record<string, number>
): number[] | null {
  const r = engineCall("expr_eval_vars_batch", { expr, var: varName, xs: ts, vars: params });
  if (!r || r.isError || !Array.isArray(r.value) || r.value.length !== ts.length) return null;
  return r.value as number[];
}

/** 非有限值一律留 null 表示"这里断开"。
 *
 * ⚠ 这里**不能**先做 `Number(x)` 再判：`Number(null) === 0`，于是引擎对域外点
 * 返回的 null 会变成合法的 y=0 —— ln(x) 在 x<0 会画出一条假的地平线、
 * 1/x 会横跨渐近线连成一条线（cdp-plot-truth 的左半轴 / 假连线两条断言就是这么挂的）。
 * 直接对原值用 `Number.isFinite`：它对 null/undefined/字符串一律为 false。 */
function pt(x: unknown, y: unknown): Sample {
  return Number.isFinite(x) && Number.isFinite(y) ? [x as number, y as number] : null;
}

/**
 * 采样：表达式列表 + 视口 → 每个表达式的世界坐标点序列。
 * 逻辑与 Vue 版 PlotView.sampleAll 一致（同一套引擎调用与自适应采样参数）。
 */
export function usePlotSampling(
  rows: ExprRow[], view: View, params: Record<string, number>, size: { w: number; h: number }
) {
  const [samples, setSamples] = useState<Record<number, Sample[]>>({});
  const [userPoints, setUserPoints] = useState<UserPoint[]>([]);
  const [status, setStatus] = useState<PlotStatus>({ okCount: 0, errCount: 0, totalPts: 0, text: "" });
  /* 二元网格（隐式方程 / 二元区域）与一元曲线分开走：前者由 expr_eval_grid 出整块数据，
   * 后者由 expr_eval_vars_batch 出点列（与 Vue 版 sampleAll / sampleGrids 的分工一致）。 */
  const [grids, setGrids] = useState<Record<number, PlotGrid>>({});
  const [errors, setErrors] = useState<Record<number, string>>({});
  const timer = useRef<number | null>(null);
  const seq = useRef(0);
  const userPointsRef = useRef<UserPoint[]>([]);
  userPointsRef.current = userPoints;

  const sampleAll = useCallback(() => {
    if (!isHosted()) {
      setStatus({ okCount: 0, errCount: 0, totalPts: 0, text: "浏览器预览：无引擎桥，曲线不绘制" });
      return;
    }
    const w = size.w > 0 ? size.w : 800;
    const h = size.h > 0 ? size.h : 600;
    const padX = viewW(view) * PAD, padY = viewH(view) * PAD;
    const sx0 = view.x0 - padX, sx1 = view.x1 + padX;
    const sy0 = view.y0 - padY, sy1 = view.y1 + padY;
    const toScreen = ([x, y]: [number, number]): [number, number] => [
      ((x - view.x0) / (view.x1 - view.x0)) * w,
      ((view.y1 - y) / (view.y1 - view.y0)) * h,
    ];

    const next: Record<number, Sample[]> = {};
    const nextErr: Record<number, string> = {};
    const pts: UserPoint[] = [];
    /* 二元网格的行（隐式方程 / 二元区域）——循环里只登记，采完曲线后统一求值 */
    const gridRows: { id: number; body: string }[] = [];
    let okCount = 0, errCount = 0, totalPts = 0;

    for (const row of rows) {
      /* 按解析结果的真实字段用（op / axis / boundary 只有不等式/区域分支才有） */
      const p: ParsedExpr = parseExpr(row.text);
      if (!row.text.trim()) continue;
      if (!p.valid) { nextErr[row.id] = p.error || "表达式无法解析"; errCount++; continue; }

      const opts = { initial: 300, maxRounds: 3, tolPx: 0.8, maxPoints: 6000 };

      if (p.type === "point") {
        const m = row.text.trim().match(/^\(\s*([^,]+?)\s*,\s*([^,]+?)\s*\)$/);
        if (!m) continue;
        const xr = engineCall("expr_eval_vars", { expr: m[1], vars: params });
        const yr = engineCall("expr_eval_vars", { expr: m[2], vars: params });
        if (xr && !xr.isError && yr && !yr.isError) {
          pts.push({ id: row.id, x: Number(xr.value), y: Number(yr.value), color: row.color });
          okCount++;
        } else {
          nextErr[row.id] = String((xr && xr.isError) ? xr.value : (yr && yr.isError ? yr.value : "无法求值"));
          errCount++;
        }
        continue;
      }

      let got: Sample[] | null = null;

      if (p.type === "polar") {
        const ts = linspace(0, Math.PI * 2, 300);
        const rs = batchEval(p.radius!, "theta", ts, params);
        if (rs) got = sampleAdaptive(
          (tt: number[]) => {
            const rr = batchEval(p.radius!, "theta", tt, params);
            return rr ? tt.map((t, i) => pt(rr[i] * Math.cos(t), rr[i] * Math.sin(t))) : null;
          }, 0, Math.PI * 2, toScreen, opts);
      } else if (p.type === "parametric") {
        got = sampleAdaptive(
          (tt: number[]) => {
            const xs = batchEval(p.xsExpr!, "t", tt, params);
            const ys = batchEval(p.ysExpr!, "t", tt, params);
            return xs && ys ? tt.map((_, i) => pt(xs[i], ys[i])) : null;
          }, sx0, sx1, toScreen, opts);
      } else if (p.type === "vertical") {
        got = sampleAdaptive(
          (tt: number[]) => {
            const vs = batchEval(p.body, "y", tt, params);
            return vs ? tt.map((t, i) => pt(vs[i], t)) : null;
          }, sy0, sy1, toScreen, opts);
      } else if (p.type === "explicit") {
        got = sampleAdaptive(
          (tt: number[]) => {
            const vs = batchEval(p.body, "x", tt, params);
            return vs ? tt.map((t, i) => pt(t, vs[i])) : null;
          }, sx0, sx1, toScreen, opts);
      } else if (p.type === "inequality") {
        /* 不等式 y ≷ f(x) / x ≷ g(y)：**采的是边界曲线**（与 Vue 版同一策略），
         * 所以它计入"引擎采样 N 条曲线"；填充由画布用这批点做（drawInequalities）。 */
        const isY = p.axis === "y";
        const a0 = isY ? sx0 : sy0, a1 = isY ? sx1 : sy1;
        got = sampleAdaptive(
          (tt: number[]) => {
            const vals = batchEval(p.boundary!, isY ? "x" : "y", tt, params);
            return vals ? tt.map((t, i) => (isY ? pt(t, vals[i]) : pt(vals[i], t))) : null;
          }, a0, a1, toScreen, opts);
      } else if (p.type === "implicit" || p.type === "region") {
        /* 二元网格：不在这里采，循环后统一走 expr_eval_grid。
         * 也**不计入曲线数**（Vue 版的 okCount 只数一元曲线）。 */
        gridRows.push({ id: row.id, body: p.body });
        continue;
      } else {
        nextErr[row.id] = `React 绘图版暂未支持该类型（${p.type}）`;
        errCount++;
        continue;
      }

      if (got && got.length) {
        next[row.id] = got;
        totalPts += got.length;
        okCount++;
      } else {
        nextErr[row.id] = "引擎未返回可用采样点";
        errCount++;
      }
    }

    /* 二元网格：隐式方程等值线 + 二元不等式区域（Vue 版 sampleGrids 的等价物）。
     * 180×180 = 32400 点，一次引擎调用拿回整块数据。
     * ⚠ **刻意保持同步**（BUGS.md B5）：① 32400 远低于 asyncPolicy 给 expr_eval_grid 的
     * 2.5e5 阈值（shouldRunAsync 恒为 false）；② asyncPolicy.js:12-15 明确要求
     * "绘图页每条曲线/每行一次的采样保持同步" —— 一条一个 await 会把采样时序拆碎。
     * 若将来把 GRID_N 提到 500 以上（>2.5e5），要重新评估这一条。 */
    const grids: Record<number, PlotGrid> = {};
    for (const g of gridRows) {
      const xs = linspace(view.x0, view.x1, GRID_N);
      const ys = linspace(view.y0, view.y1, GRID_N);
      const r = engineCall("expr_eval_grid", { expr: g.body, xs, ys, vars: params });
      if (r && !r.isError && Array.isArray(r.value) && r.value.length === GRID_N * GRID_N) {
        grids[g.id] = { xs, ys, values: r.value as number[] };
      } else {
        nextErr[g.id] = String(r && r.isError ? r.value : "二元网格求值失败").slice(0, 80);
      }
    }
    setGrids(grids);

    setSamples(next);
    setErrors(nextErr);
    // 用户手动加的点保留；表达式里的 (a,b) 点也画出来
    const kept = userPointsRef.current.filter((up) => rows.some((r) => r.id === up.id));
    setUserPoints([...kept, ...pts]);
    /* 状态行必须带当前视野范围，格式与 Vue 版逐字一致（`范围 [x0, x1] × [y0, y1]`）：
     * 端到端用例（cdp-plot-p3 / cdp-plot-final）就是从 `.side-status` 里正则抠这一段，
     * 再据此把世界坐标换算成屏幕像素的 —— 少了它，它们连坐标都算不出来。 */
    const rangeTxt = `范围 [${view.x0.toFixed(2)}, ${view.x1.toFixed(2)}] × [${view.y0.toFixed(2)}, ${view.y1.toFixed(2)}]`;
    setStatus({
      okCount, errCount, totalPts,
      text: `引擎采样 ${okCount} 条曲线${errCount ? `，${errCount} 条失败` : ""} · ${totalPts} 点 · ${rangeTxt}`,
    });
  }, [rows, view, params, size.w, size.h]);

  /* 视口 / 表达式 / 参数变化 → 去抖重采样（与 Vue 版 scheduleSample 同策略） */
  useEffect(() => {
    if (timer.current) window.clearTimeout(timer.current);
    const my = ++seq.current;
    timer.current = window.setTimeout(() => { if (my === seq.current) sampleAll(); }, 60);
    return () => { if (timer.current) window.clearTimeout(timer.current); };
  }, [sampleAll]);

  /** 用户点击曲线加点（点必须用户自己添加，渲染层不自动造点）
   * curveId 记下"这个点属于哪条曲线"——拖动时要沿着它吸附回去。 */
  const addUserPoint = useCallback((x: number, y: number, color: string, curveId?: number) => {
    setUserPoints((prev) => [
      ...prev.filter((p) => !(Math.abs(p.x - x) < 1e-9 && Math.abs(p.y - y) < 1e-9)),
      { id: -Date.now(), x, y, color, curveId },
    ]);
  }, []);

  /** 拖动改点位置（父组件已按曲线类型吸附好坐标） */
  const moveUserPoint = useCallback((id: number, x: number, y: number) => {
    setUserPoints((prev) => prev.map((p) => (p.id === id ? { ...p, x, y } : p)));
  }, []);

  const removeUserPoint = useCallback((id: number) => {
    setUserPoints((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const clearUserPoints = useCallback(() => setUserPoints([]), []);

  return { samples, userPoints, status, errors, grids, addUserPoint, moveUserPoint, removeUserPoint, clearUserPoints, resample: sampleAll };
}
