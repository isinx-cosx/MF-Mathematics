/**
 * jobProgress.ts —— `engineCallAsync` 的 `onProgress` 载荷形状
 *
 * 为什么要单独一个文件：宿主桥 `@shared/bridge.js` 把 `opts` 声明成 `{}`，于是
 * `onProgress: (p) => …` 里的 `p` 在 TS 里是隐式 any（plot-fractal 当初就因此报 TS7006）。
 * 现在有两个页面（分形、复平面）要收进度，所以形状**共用一份**，而不是各写一遍 ——
 * 两处各自演化出不同字段名是最容易发生的漂移。
 *
 * 字段取自宿主实际推的内容（`state` + 已跑毫秒），两个时间字段都标可选：
 * 不同宿主实现里它们不一定都在，取的时候兜底即可。
 */
export type JobProgress = { state: string; elapsedMs?: number; ms?: number };
