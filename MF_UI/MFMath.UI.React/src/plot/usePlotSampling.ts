import { useCallback, useEffect, useRef, useState } from "react";
import { engineCall, isHosted } from "@shared/bridge.js";
import { parseExpr } from "@shared/plot/plotMath.js";
import { adaptiveSample } from "@shared/plot/sampling.js";
import { viewW, viewH } from "@shared/plot/view.js";
import type { Sample, UserPoint, View } from "./PlotCanvas";

export type ExprRow = {
  id: number;
  text: string;
  color: string;
  visible: boolean;
  emphasis?: boolean;
  error?: string | null;
};

export type PlotStatus = { okCount: number; errCount: number; totalPts: number; text: string };

/** 采样范围取视口的 1.5 倍（左右各外扩 25%）：小幅平移时曲线不断裂 */
const PAD = 0.25;

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

/** 非有限值一律留 null 表示"这里断开"（Number(null) === 0 会画出假的 y=0 段） */
function pt(x: unknown, y: unknown): Sample {
  const nx = Number(x), ny = Number(y);
  return Number.isFinite(nx) && Number.isFinite(ny) ? [nx, ny] : null;
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
    let okCount = 0, errCount = 0, totalPts = 0;

    for (const row of rows) {
      const p = parseExpr(row.text);
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
        if (rs) got = adaptiveSample(
          (tt: number[]) => {
            const rr = batchEval(p.radius!, "theta", tt, params);
            return rr ? tt.map((t, i) => pt(rr[i] * Math.cos(t), rr[i] * Math.sin(t))) : null!;
          }, 0, Math.PI * 2, toScreen, opts);
      } else if (p.type === "parametric") {
        got = adaptiveSample(
          (tt: number[]) => {
            const xs = batchEval(p.xsExpr!, "t", tt, params);
            const ys = batchEval(p.ysExpr!, "t", tt, params);
            return xs && ys ? tt.map((_, i) => pt(xs[i], ys[i])) : null!;
          }, sx0, sx1, toScreen, opts);
      } else if (p.type === "vertical") {
        got = adaptiveSample(
          (tt: number[]) => {
            const vs = batchEval(p.body, "y", tt, params);
            return vs ? tt.map((t, i) => pt(vs[i], t)) : null!;
          }, sy0, sy1, toScreen, opts);
      } else if (p.type === "explicit") {
        got = adaptiveSample(
          (tt: number[]) => {
            const vs = batchEval(p.body, "x", tt, params);
            return vs ? tt.map((t, i) => pt(t, vs[i])) : null!;
          }, sx0, sx1, toScreen, opts);
      } else {
        /* implicit / region / inequality：Vue 版走 expr_eval_grid + marching squares，
         * React 版尚未移植 —— 明确报"未迁移"，不静默画错。 */
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

    setSamples(next);
    setErrors(nextErr);
    // 用户手动加的点保留；表达式里的 (a,b) 点也画出来
    const kept = userPointsRef.current.filter((up) => rows.some((r) => r.id === up.id));
    setUserPoints([...kept, ...pts]);
    setStatus({
      okCount, errCount, totalPts,
      text: `引擎采样 ${okCount} 条曲线${errCount ? `，${errCount} 条失败` : ""} · ${totalPts} 点`,
    });
  }, [rows, view, params, size.w, size.h]);

  /* 视口 / 表达式 / 参数变化 → 去抖重采样（与 Vue 版 scheduleSample 同策略） */
  useEffect(() => {
    if (timer.current) window.clearTimeout(timer.current);
    const my = ++seq.current;
    timer.current = window.setTimeout(() => { if (my === seq.current) sampleAll(); }, 60);
    return () => { if (timer.current) window.clearTimeout(timer.current); };
  }, [sampleAll]);

  /** 用户点击曲线加点（点必须用户自己添加，渲染层不自动造点） */
  const addUserPoint = useCallback((x: number, y: number, color: string) => {
    setUserPoints((prev) => [
      ...prev.filter((p) => !(Math.abs(p.x - x) < 1e-9 && Math.abs(p.y - y) < 1e-9)),
      { id: -Date.now(), x, y, color },
    ]);
  }, []);

  const removeUserPoint = useCallback((id: number) => {
    setUserPoints((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const clearUserPoints = useCallback(() => setUserPoints([]), []);

  return { samples, userPoints, status, errors, addUserPoint, removeUserPoint, clearUserPoints, resample: sampleAll };
}
