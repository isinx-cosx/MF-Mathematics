/**
 * 各学科视图的测试样本（共享 fixture）
 *
 * 为什么单独一个文件：`audit-modes.mjs`（绕过界面直调引擎）与 `cdp-modes-render.mjs`
 * （走界面渲染）必须**用同一份输入**，否则两边测的根本不是同一件事——
 * 一个套件改样本、另一个没改，就会出现"直调对、界面错"或反过来的假结论。
 *
 * 约定：`;` 分段的顺序 = 该视图 args 的声明顺序（见 VIEW_CONFIGS / ENGINE_VAR_SPECS）。
 */

/** 每个学科视图（路由末段）的代表性输入 */
export const VIEW_SAMPLE = {
  algebra: "x^2-4",
  "algebraic-topology": "",
  "analytic-geometry": "(1,2);(3,4)",
  calculus: "x^2-4",
  "complex-analysis": "(1+I)^2",
  "functional-analysis": "x; x^2; -1,1",
  "linear-algebra": "[[1,2],[3,4]]",
  "measure-theory": "",
  "number-theory": "30",
  numerical: "1,2,3",
  probability: "1,2,3",
  "real-analysis": "1/n",
  sequences: "1/n",
  // 调和分析（本轮新增的第 14 个视图）：高斯函数是傅里叶变换的经典样本
  "harmonic-analysis": "exp(-x^2)",
};
