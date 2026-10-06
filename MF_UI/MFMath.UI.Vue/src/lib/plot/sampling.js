/**
 * 自适应采样（对齐 Desmos 的曲线质量）
 *
 * 思路：先均匀采样获得整体形状，再对「屏幕偏差超过阈值」的区间插入中点，
 *       每轮只做一次批量求值（引擎调用次数可控），最多若干轮。
 * 判定标准在**屏幕空间**（像素），因此缩放时加密程度自动适配视觉需要。
 */
"use strict";

function linspace(a, b, n) {
  const out = new Array(n);
  if (n === 1) { out[0] = a; return out; }
  for (let i = 0; i < n; i++) out[i] = a + ((b - a) * i) / (n - 1);
  return out;
}

/**
 * @param {(ts:number[]) => Array<[number,number]>} evalPoints 批量求值：t 数组 → 世界坐标点数组
 * @param {number} t0 参数下界
 * @param {number} t1 参数上界
 * @param {(p:[number,number]) => [number,number]} toScreen 世界坐标 → 屏幕像素
 * @param {object} [opt]
 * @param {number} [opt.initial=300] 初始均匀采样点数
 * @param {number} [opt.maxRounds=3] 最大加密轮数
 * @param {number} [opt.tolPx=0.8] 屏幕偏差阈值（像素）——中点偏离线性插值超过它才加密
 * @param {number} [opt.maxPoints=6000] 点数上限（防爆）
 * @returns {Array<[number,number]>} 世界坐标点序列
 */
export function adaptiveSample(evalPoints, t0, t1, toScreen, opt = {}) {
  const {
    initial = 300,
    maxRounds = 3,
    tolPx = 0.8,
    maxPoints = 6000,
  } = opt;

  let ts = linspace(t0, t1, Math.max(2, initial));
  let world = evalPoints(ts);
  if (!world || world.length !== ts.length) return [];

  for (let round = 0; round < maxRounds && ts.length < maxPoints; round++) {
    // 收集所有区间中点，一次批量求值
    const midTs = new Array(Math.max(0, ts.length - 1));
    for (let i = 0; i + 1 < ts.length; i++) midTs[i] = (ts[i] + ts[i + 1]) / 2;
    if (!midTs.length) break;

    const midWorld = evalPoints(midTs);
    if (!midWorld || midWorld.length !== midTs.length) break;

    const keep = new Array(midTs.length).fill(false);
    let needed = 0;
    for (let i = 0; i < midTs.length; i++) {
      const A = world[i], B = world[i + 1], M = midWorld[i];
      if (!A || !B) continue;
      const a = toScreen(A), b = toScreen(B);
      // 端点不可绘制：在断点/渐近线附近也加密，让断点边界更准确
      if (!isFinite(a[0]) || !isFinite(a[1]) || !isFinite(b[0]) || !isFinite(b[1])) continue;
      /* 中点不可绘制（域外 / 未定义，如 1/x 在 x=0、ln x 在 x≤0）：
       * 这一格正是曲线**进出定义域**的地方，必须把中点本身插进数组 —— 它是 null，
       * 绘制时会在那里断开。以前这里直接 continue 跳过，于是端点被当成相邻点连线：
       * 实测 y=1/x 会连出一条贯穿画布的竖线（同 x 的 ±0.05 两点，y=∓19.9，
       * 而断点判据的 far 阈值是 4×视野=81.3，够不着 → 不判定为渐近线）。
       * 只有端点屏幕上确实跨得开才插，否则每个域外点都插会让点数爆炸。 */
      if (!M) {
        if (Math.hypot(b[0] - a[0], b[1] - a[1]) > tolPx) { keep[i] = true; needed++; }
        continue;
      }
      const m = toScreen(M);
      if (!isFinite(m[0]) || !isFinite(m[1])) { keep[i] = true; needed++; continue; }
      const lx = (a[0] + b[0]) / 2, ly = (a[1] + b[1]) / 2;
      const dev = Math.hypot(m[0] - lx, m[1] - ly);
      if (dev > tolPx) { keep[i] = true; needed++; }
    }
    if (!needed) break;   // 已足够平滑

    // 合并：区间 [i, i+1] 与其中点 i 交错排列
    const mergedTs = [], mergedWorld = [];
    for (let i = 0; i < ts.length; i++) {
      mergedTs.push(ts[i]);
      mergedWorld.push(world[i]);
      if (i < midTs.length && keep[i]) {
        mergedTs.push(midTs[i]);
        mergedWorld.push(midWorld[i]);
      }
    }
    ts = mergedTs;
    world = mergedWorld;
  }
  return world;
}

export { linspace };
