import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { initPlotMathHook } from "@shared/plot/plotMath.js";
import { initTheme } from "@shared/bridge.js";

/* 与 Vue 版 main.js 同一批全局样式：MathLive / KaTeX / 主题。
 * theme.css 是整个设计系统（29 KB），**直接复用同一份文件**，界面才不会走样。 */
import "mathlive/static.css";
import "mathlive/fonts.css";
import "katex/dist/katex.min.css";
import "../../MFMath.UI.Vue/src/styles/theme.css";

/* 表达式解析的注入钩子（Vue 版在 App.vue 启动时调一次）：
 * 不初始化的话 parseExpr 对 x^2 这类输入会判成"非法表达式"。 */
initPlotMathHook();
initTheme();

createRoot(document.getElementById("app")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
