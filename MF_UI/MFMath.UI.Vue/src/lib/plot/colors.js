/**
 * Desmos 风格色板与配色工具
 * 依据 Desmos 绘图器的表达式列表配色（行颜色圆点 → 对应曲线颜色）
 */
"use strict";

/** 默认循环色（顺序与 Desmos 表达式列表一致） */
export const PLOT_COLORS = [
  "#c74440", // 红
  "#2d70b3", // 蓝
  "#388c46", // 绿
  "#6042a6", // 紫
  "#fa7e19", // 橙
  "#000000", // 黑
];

/** 可选扩展色（用户点击颜色圆点时的候选） */
export const EXTRA_COLORS = [
  "#0d9ca6", // 青
  "#e8a33d", // 琥珀
  "#b03a8c", // 品红
  "#4a4a4a", // 深灰
];

export const ALL_COLORS = [...PLOT_COLORS, ...EXTRA_COLORS];

/** 按索引取循环色 */
export function colorAt(index) {
  return PLOT_COLORS[index % PLOT_COLORS.length];
}

/** 网格 / 坐标轴配色（Desmos 风格浅灰细线） */
export const GRID = {
  bg: "#ffffff",
  minor: "#e5e5e5",
  major: "#cccccc",
  axis: "#000000",
  label: "#666666",
  axisLabel: "#000000",
};

/** 深色主题下的网格配色 */
export const GRID_DARK = {
  bg: "#12161f",
  minor: "#232a36",
  major: "#333c4c",
  axis: "#e6e9ef",
  label: "#9aa4b2",
  axisLabel: "#e6e9ef",
};

export function gridFor(theme) {
  return theme === "dark" ? GRID_DARK : GRID;
}
