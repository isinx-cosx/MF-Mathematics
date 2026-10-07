/**
 * plotWorkspace.ts —— 绘图页 ↔ 工作区的契约（BUGS.md B14）
 *
 * 为什么需要这个模块：绘图组从 Vue 迁到 React 时**只搬了渲染层与算法**
 * （`@shared/plot/*`），把"与外层的契约"漏了 —— 工作区就是其中之一。
 * 后果：保存/载入工作区对绘图页**完全无效**（`cdp-workspace` 的失败清单里
 * 一条 `/plot/*` 都没有，`cdp-shortcuts-prefs` 也读不到 `/plot/2d` 的 `view`）。
 *
 * 与 Vue 版的关系：可用的那份参考实现在 **已冻结** 的 `src/views/plot/PlotView.vue`
 * （`:35` 还原、`:701` 回写、`:661` 的 `capturePlot()`），**而且只有它接了**
 * —— 3D / 复平面 / 向量场 / 几何 / 分形这 5 页在 Vue 版里从来就没接过。
 * 2D 与极坐标的载荷形状**保持与 Vue 版逐字一致**（`kind: "plot"` + expressions/view/
 * gridMode/showGrid/params），这样老的工作区文件仍然能读、测试里那句
 * `pages()["/plot/2d"].view` 也继续成立。
 *
 * 三条规矩（与 Vue 版一致）：
 *   ① **只存"你在编辑什么"**，不存结果（曲线采样、交点、极值都能重算）；
 *   ② **首帧不回写** —— 否则"刚打开一页"就被标成脏，而用户什么都没改；
 *   ③ 形状不符就**当作没有**（返回 null），绝不猜、也不半途还原一半。
 */
import { useEffect, useRef } from "react";
import { getPage, setPage } from "@shared/workspace/store.js";

/** 一页工作区载荷的共同部分：kind 用来认领"这是我这一页的" */
export type PlotPayload = { kind: string } & Record<string, unknown>;

/**
 * 读回本页存过的工作区内容。
 * @param route 当前路由（与 Vue 版一样按 `route.path` 存，所以 `/plot/2d` 与 `/plot/polar` 各存一份）
 * @param kind  本页的载荷类型（如 `"plot"` / `"plot3d"`）
 */
export function loadPlotPage(route: string, kind: string): PlotPayload | null {
  if (!route) return null;
  const saved = getPage(route);
  if (!saved || typeof saved !== "object" || Array.isArray(saved)) return null;
  const p = saved as PlotPayload;
  return p.kind === kind ? p : null;
}

/** 回写本页的工作区内容 */
export function savePlotPage(route: string, payload: PlotPayload): void {
  if (!route) return;
  setPage(route, payload);
}

/**
 * 把"变更即回写"接到 React 上（对应 Vue 版的 `watch([...], () => setPage(...))`）。
 *
 * `deps` 必须**覆盖所有会被存下来的状态**，否则会出现"改了但不落盘"。
 * 长度要在本组件内保持恒定（React 对 deps 数组长度变化会告警）。
 *
 * 首帧刻意不回写：`useRef(true)` 吞掉第一次 effect。这样"只是打开一页"不会把
 * 工作区标成脏 —— 与 Vue 版 `syncWorkspace = false` 到挂载后才置真的语义一致。
 *
 * @param route   本页路由
 * @param deps    变化即回写的依赖
 * @param capture 采集当前要存的内容（用 ref 取最新闭包，避免闭包过期）
 */
export function usePlotWorkspace(
  route: string,
  deps: unknown[],
  capture: () => PlotPayload
): void {
  const captureRef = useRef(capture);
  captureRef.current = capture;
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    savePlotPage(route, captureRef.current());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

/** `{x0,x1,y0,y1}` 全为有限数才算可用（工作区里的 view 可能被手改坏） */
export function isViewLike(v: unknown): v is { x0: number; x1: number; y0: number; y1: number } {
  if (!v || typeof v !== "object") return false;
  const o = v as Record<string, unknown>;
  return ["x0", "x1", "y0", "y1"].every((k) => Number.isFinite(o[k]));
}

/** 工作区文件是**用户可手改的**，所以每一项都要过一遍类型检查再采信 —— 不符就用默认值，
 *  绝不让一个坏字段把整页带崩（这些 helper 让各页的惰性初值保持一行一个）。 */
export function numOr(v: unknown, fallback: number): number {
  return Number.isFinite(v) ? (v as number) : fallback;
}
export function boolOr(v: unknown, fallback: boolean): boolean {
  return typeof v === "boolean" ? v : fallback;
}
export function strOr(v: unknown, fallback: string): string {
  return typeof v === "string" ? v : fallback;
}
/** `{[k]: number}` 形状的参数值表；坏值逐项丢掉 */
export function numsOr(v: unknown): Record<string, number> {
  const out: Record<string, number> = {};
  if (v && typeof v === "object" && !Array.isArray(v)) {
    for (const [k, n] of Object.entries(v as Record<string, unknown>)) {
      if (Number.isFinite(n)) out[k] = n as number;
    }
  }
  return out;
}
