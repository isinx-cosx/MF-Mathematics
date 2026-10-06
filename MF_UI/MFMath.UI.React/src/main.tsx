import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { initPlotMathHook } from "@shared/plot/plotMath.js";
import { initTheme } from "@shared/bridge.js";
import { installErrorReporting, safe } from "./lib/hostSafe";

/* 与 Vue 版 main.js 同一批全局样式：MathLive / KaTeX / 主题。
 * theme.css 是整个设计系统（29 KB），**直接复用同一份文件**，界面才不会走样。 */
import "mathlive/static.css";
import "mathlive/fonts.css";
import "katex/dist/katex.min.css";
import "../../MFMath.UI.Vue/src/styles/theme.css";

/* 错误上报要**最先装**：宿主对象缺失、模块求值失败这类问题必须在它之后发生才抓得到。
 * 宿主日志里会以 `[前端] …` 出现（对齐 Vue 版 lib/diagnostics/errors.js）。 */
installErrorReporting();

/* 表达式解析的注入钩子（Vue 版在 App.vue 启动时调一次）：
 * 不初始化的话 parseExpr 对 x^2 这类输入会判成"非法表达式"。 */
safe(() => initPlotMathHook(), undefined);
/* 主题：宿主对象可能还没挂上，失败就退回默认（不能让它把首帧带崩） */
safe(() => initTheme(), undefined);

/* 错误边界：组件抛错时给出可见提示，而不是整页空白（白屏是最难查的失败方式） */
class Boundary extends React.Component<{ children: React.ReactNode }, { err: Error | null }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { err: null };
  }
  static getDerivedStateFromError(err: Error) { return { err }; }
  componentDidCatch(err: Error) {
    try {
      const w = window as unknown as {
        chrome?: { webview?: { hostObjects?: { sync?: Record<string, { Front?: (l: string, m: string) => void }> } } };
      };
      w.chrome?.webview?.hostObjects?.sync?.diag?.Front?.("ERROR", "[前端] 渲染失败：" + (err.stack || err.message));
    } catch { /* 宿主不可用则忽略 */ }
  }
  render() {
    if (this.state.err) {
      return (
        <div style={{ padding: 24, font: "13px/1.6 Inter, 'Microsoft YaHei', sans-serif", color: "#0f172a" }}>
          <h2 style={{ margin: "0 0 8px" }}>界面渲染失败</h2>
          <pre style={{ whiteSpace: "pre-wrap", color: "#b91c1c" }}>{String(this.state.err?.stack || this.state.err)}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById("app")!).render(
  <React.StrictMode>
    <Boundary>
      <App />
    </Boundary>
  </React.StrictMode>
);
