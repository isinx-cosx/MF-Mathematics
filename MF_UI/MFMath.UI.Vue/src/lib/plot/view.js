/**
 * 绘图视图数学（对齐 Desmos 的行为）
 *  - 视图 = 世界坐标矩形 {x0, x1, y0, y1}，y 向上
 *  - 网格步长用 "nice numbers"：1 / 2 / 5 × 10^n，使屏幕上主网格线间距约 80px
 *  - 缩放以光标为不动点；默认视图等比（x∈[-10,10]，y 按宽高比推出，网格为正方形）
 */
"use strict";

import { currentPlotRange } from "../settings/prefs.js";

export const DEFAULT_X_MIN = -10;
export const DEFAULT_X_MAX = 10;
export const ZOOM_MIN = 1e-6;     // 最小可视跨度
export const ZOOM_MAX = 2000;     // 最大可视跨度

/**
 * 默认视图。
 * 优先用「设置 → 计算与绘图 → 绘图默认范围」里配置的固定范围（v1 的"绘图默认值"）；
 * 没配就用等比自动：x∈[-10,10]，y 跨度按画布宽高比推出（网格为正方形）。
 */
export function defaultView(w = 1, h = 1) {
  const fixed = currentPlotRange();
  if (fixed) return { ...fixed };
  const x0 = DEFAULT_X_MIN, x1 = DEFAULT_X_MAX;
  const halfY = ((x1 - x0) / 2) * (h / Math.max(w, 1));
  return { x0, x1, y0: -halfY, y1: halfY };
}

/** 世界 → 屏幕（CSS 像素） */
export function mapX(view, w, x) {
  return ((x - view.x0) / (view.x1 - view.x0)) * w;
}
export function mapY(view, h, y) {
  return ((view.y1 - y) / (view.y1 - view.y0)) * h;
}
/** 屏幕 → 世界 */
export function unmapX(view, w, px) {
  return view.x0 + ((view.x1 - view.x0) * px) / Math.max(w, 1);
}
export function unmapY(view, h, py) {
  return view.y1 - ((view.y1 - view.y0) * py) / Math.max(h, 1);
}

/** 视图宽高（世界单位） */
export function viewW(view) { return view.x1 - view.x0; }
export function viewH(view) { return view.y1 - view.y0; }

/** 以画布上 (px,py) 为不动点缩放 factor 倍（Desmos 滚轮行为） */
export function zoomAt(view, w, h, px, py, factor) {
  const ax = unmapX(view, w, px);
  const ay = unmapY(view, h, py);
  let nw = viewW(view) * factor;
  let nh = viewH(view) * factor;
  nw = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, nw));
  nh = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, nh));
  const rx = px / Math.max(w, 1);
  const ry = py / Math.max(h, 1);
  return {
    x0: ax - rx * nw,
    x1: ax + (1 - rx) * nw,
    y0: ay - (1 - ry) * nh,
    y1: ay + ry * nh,
  };
}

/** 按屏幕位移平移视图（拖拽） */
export function panBy(view, w, h, dxPx, dyPx) {
  const sx = viewW(view) / Math.max(w, 1);
  const sy = viewH(view) / Math.max(h, 1);
  return {
    x0: view.x0 - dxPx * sx,
    x1: view.x1 - dxPx * sx,
    y0: view.y0 + dyPx * sy,
    y1: view.y1 + dyPx * sy,
  };
}

/**
 * nice 步长：返回 1/2/5×10^n 中最接近"每 targetPx 像素一格"的值
 * @param {number} range 世界跨度
 * @param {number} pixels 对应像素长度
 * @param {number} targetPx 期望的每格像素（Desmos 约 80）
 */
export function niceStep(range, pixels, targetPx = 80) {
  const raw = (range / Math.max(pixels, 1)) * targetPx;
  if (!isFinite(raw) || raw <= 0) return 1;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const mult = norm < 1.5 ? 1 : norm < 3.5 ? 2 : norm < 7.5 ? 5 : 10;
  return mult * mag;
}

/** 计算网格步长（主刻度 + 次刻度） */
export function gridSteps(view, w, h, targetPx = 80) {
  const major = niceStep(viewW(view), w, targetPx);
  return { major, minor: major / 5 };
}

/** 让视图刚好容纳给定点集（Zoom Fit），带边距 */
export function fitBounds(points, w, h, paddingRatio = 0.12) {
  if (!points || !points.length) return null;
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const [x, y] of points) {
    if (!isFinite(x) || !isFinite(y)) continue;
    if (x < x0) x0 = x;
    if (x > x1) x1 = x;
    if (y < y0) y0 = y;
    if (y > y1) y1 = y;
  }
  if (!isFinite(x0) || !isFinite(y0)) return null;
  if (x1 - x0 < 1e-9) { x0 -= 1; x1 += 1; }
  if (y1 - y0 < 1e-9) { y0 -= 1; y1 += 1; }
  const padX = (x1 - x0) * paddingRatio;
  const padY = (y1 - y0) * paddingRatio;
  let nx0 = x0 - padX, nx1 = x1 + padX;
  let ny0 = y0 - padY, ny1 = y1 + padY;
  // 保持等比（以画布宽高比为准），避免网格变形。
  // 但要设上限：x 与 y 量级差得多时（如 e^x 在 x=15 处 y≈3.3e6，x 只跨 30），
  // 无上限的等比修正会把 y 的量级搬到 x 上，x 跨度被放大 1e5 倍、整条曲线塌成一条线。
  const MAX_STRETCH = 8;
  const targetAspect = Math.max(w, 1) / Math.max(h, 1);
  const aspect = (nx1 - nx0) / (ny1 - ny0);
  if (aspect > targetAspect) {
    const need = Math.min((nx1 - nx0) / targetAspect, (ny1 - ny0) * MAX_STRETCH);
    const cy = (ny0 + ny1) / 2;
    ny0 = cy - need / 2; ny1 = cy + need / 2;
  } else {
    const need = Math.min((ny1 - ny0) * targetAspect, (nx1 - nx0) * MAX_STRETCH);
    const cx = (nx0 + nx1) / 2;
    nx0 = cx - need / 2; nx1 = cx + need / 2;
  }
  return { x0: nx0, x1: nx1, y0: ny0, y1: ny1 };
}

/** 刻度标签格式化（对齐 Desmos：避免浮点噪声、按步长决定小数位） */
export function formatTick(v, step) {
  if (Math.abs(v) < step * 1e-9) return "0";
  const exp = Math.floor(Math.log10(Math.abs(step)));
  let s;
  if (exp < -4 || exp > 6) {
    s = v.toExponential(2).replace(/e([+-])(\d)$/, "e$10$2");
  } else {
    const dec = Math.max(0, -exp);
    s = v.toFixed(Math.min(8, dec));
    if (s.includes(".")) s = s.replace(/0+$/, "").replace(/\.$/, "");
  }
  if (s === "-0") s = "0";
  return s;
}
