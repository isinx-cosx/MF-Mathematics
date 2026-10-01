/**
 * 直角坐标 / 极坐标网格绘制（可复用）
 * 从 PlotCanvas 的网格实现中提取：复平面、自由几何、向量场等视图共用，
 * 避免每个视图复制一份网格代码（此前已因复制引入过作用域 bug）。
 */
"use strict";

import { mapX, mapY, viewW, gridSteps, formatTick } from "./view.js";

/**
 * 绘制直角坐标系（背景 + 主/次网格 + 轴线 + 刻度 + 原点）
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} w 画布 CSS 宽
 * @param {number} h 画布 CSS 高
 * @param {{x0:number,y0:number,x1:number,y1:number}} view
 * @param {{bg:string,minor:string,major:string,axis:string,label:string}} gridColors
 * @param {object} [opt] { showGrid=true, showTicks=true, xLabel='', yLabel='' }
 * @returns {{major:number, minor:number}}
 */
export function drawCartesianGrid(ctx, w, h, view, gridColors, opt = {}) {
  const showGrid = opt.showGrid !== false;
  const showTicks = opt.showTicks !== false;

  ctx.fillStyle = gridColors.bg;
  ctx.fillRect(0, 0, w, h);

  const { major, minor } = gridSteps(view, w, h);
  // 刻度索引在 if 之外声明：后面的刻度标签绘制也要用
  const k0 = Math.ceil(view.x0 / major), k1 = Math.floor(view.x1 / major);
  const l0 = Math.ceil(view.y0 / major), l1 = Math.floor(view.y1 / major);

  if (showGrid) {
    ctx.strokeStyle = gridColors.minor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    const i0 = Math.ceil(view.x0 / minor), i1 = Math.floor(view.x1 / minor);
    if (i1 - i0 < 4000) {
      for (let i = i0; i <= i1; i++) {
        const x = i * minor;
        if (Math.abs(x / major - Math.round(x / major)) < 1e-9) continue;
        const px = Math.round(mapX(view, w, x)) + 0.5;
        ctx.moveTo(px, 0); ctx.lineTo(px, h);
      }
    }
    const j0 = Math.ceil(view.y0 / minor), j1 = Math.floor(view.y1 / minor);
    if (j1 - j0 < 4000) {
      for (let j = j0; j <= j1; j++) {
        const y = j * minor;
        if (Math.abs(y / major - Math.round(y / major)) < 1e-9) continue;
        const py = Math.round(mapY(view, h, y)) + 0.5;
        ctx.moveTo(0, py); ctx.lineTo(w, py);
      }
    }
    ctx.stroke();

    ctx.strokeStyle = gridColors.major;
    ctx.beginPath();
    if (k1 - k0 < 2000) {
      for (let k = k0; k <= k1; k++) {
        const px = Math.round(mapX(view, w, k * major)) + 0.5;
        ctx.moveTo(px, 0); ctx.lineTo(px, h);
      }
    }
    if (l1 - l0 < 2000) {
      for (let l = l0; l <= l1; l++) {
        const py = Math.round(mapY(view, h, l * major)) + 0.5;
        ctx.moveTo(0, py); ctx.lineTo(w, py);
      }
    }
    ctx.stroke();
  }

  // 坐标轴
  const axisY = mapY(view, h, 0);
  const axisX = mapX(view, w, 0);
  ctx.strokeStyle = gridColors.axis;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  if (axisY >= 0 && axisY <= h) { ctx.moveTo(0, axisY); ctx.lineTo(w, axisY); }
  if (axisX >= 0 && axisX <= w) { ctx.moveTo(axisX, 0); ctx.lineTo(axisX, h); }
  ctx.stroke();

  if (showTicks) {
    ctx.fillStyle = gridColors.label;
    ctx.font = "11px -apple-system, Segoe UI, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const labelY = Math.min(Math.max(axisY + 4, 2), h - 16);
    if (k1 - k0 < 200) {
      for (let k = k0; k <= k1; k++) {
        if (k === 0) continue;
        const x = k * major;
        const px = mapX(view, w, x);
        if (px < 16 || px > w - 16) continue;
        ctx.fillText(formatTick(x, major), px, labelY);
      }
    }
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    const labelX = Math.min(Math.max(axisX - 6, 26), w - 4);
    if (l1 - l0 < 200) {
      for (let l = l0; l <= l1; l++) {
        if (l === 0) continue;
        const y = l * major;
        const py = mapY(view, h, y);
        if (py < 10 || py > h - 10) continue;
        ctx.fillText(formatTick(y, major), labelX, py);
      }
    }
    // 原点
    if (axisX >= 0 && axisX <= w && axisY >= 0 && axisY <= h) {
      ctx.textAlign = "right"; ctx.textBaseline = "top";
      ctx.fillText("0", axisX - 5, axisY + 3);
    }
  }

  // 轴标签（如复平面的 Re / Im）
  if (opt.xLabel) {
    ctx.fillStyle = gridColors.axis;
    ctx.font = "12px -apple-system, Segoe UI, sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "bottom";
    ctx.fillText(opt.xLabel, w - 8, Math.min(Math.max(axisY - 6, 14), h - 4));
  }
  if (opt.yLabel) {
    ctx.fillStyle = gridColors.axis;
    ctx.font = "12px -apple-system, Segoe UI, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    ctx.fillText(opt.yLabel, Math.min(Math.max(axisX + 6, 6), w - 20), 8);
  }

  return { major, minor };
}

/**
 * 绘制极坐标网格（同心圆 + 每 15° 射线 + π 制角度刻度 + 半径刻度）
 */
export function drawPolarGrid(ctx, w, h, view, gridColors, major, showGridLines = true) {
  const ox = mapX(view, w, 0), oy = mapY(view, h, 0);
  const pxPerUnit = w / Math.max(viewW(view), 1e-12);
  const reach = Math.hypot(Math.max(w, h) * 1.2, Math.max(w, h) * 1.2);
  const rStep = major;

  if (showGridLines) {
    ctx.strokeStyle = gridColors.major;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let r = rStep; r * pxPerUnit < reach; r += rStep) {
      ctx.moveTo(ox + r * pxPerUnit, oy);
      ctx.arc(ox, oy, r * pxPerUnit, 0, Math.PI * 2);
    }
    ctx.stroke();

    ctx.strokeStyle = gridColors.minor;
    ctx.beginPath();
    for (let deg = 0; deg < 360; deg += 15) {
      const a = (deg * Math.PI) / 180;
      ctx.moveTo(ox, oy);
      ctx.lineTo(ox + reach * Math.cos(a), oy - reach * Math.sin(a));
    }
    ctx.stroke();
  }

  // 主方位轴
  ctx.strokeStyle = gridColors.axis;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(ox - reach, oy); ctx.lineTo(ox + reach, oy);
  ctx.moveTo(ox, oy - reach); ctx.lineTo(ox, oy + reach);
  ctx.stroke();

  ctx.fillStyle = gridColors.label;
  ctx.font = "11px -apple-system, Segoe UI, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  if (showGridLines) {
    const ANGLE_LABELS = [
      [0, "0"], [30, "π/6"], [45, "π/4"], [60, "π/3"], [90, "π/2"],
      [120, "2π/3"], [135, "3π/4"], [150, "5π/6"], [180, "π"],
      [210, "7π/6"], [225, "5π/4"], [240, "4π/3"], [270, "3π/2"],
      [300, "5π/3"], [315, "7π/4"], [330, "11π/6"],
    ];
    const labelR = Math.min(w, h) * 0.42;
    for (const [deg, text] of ANGLE_LABELS) {
      const a = (deg * Math.PI) / 180;
      const lx = ox + labelR * Math.cos(a);
      const ly = oy - labelR * Math.sin(a);
      if (lx < 12 || lx > w - 12 || ly < 10 || ly > h - 10) continue;
      ctx.fillText(text, lx, ly);
    }
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (let r = rStep; r * pxPerUnit < reach; r += rStep) {
      const lx = ox + r * pxPerUnit;
      if (lx > w - 10) break;
      ctx.fillText(formatTick(r, rStep), lx, oy + 3);
    }
  }

  ctx.textAlign = "right";
  ctx.textBaseline = "top";
  ctx.fillText("0", ox - 5, oy + 3);
}
