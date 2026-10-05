import "mathlive/static.css";
import "mathlive/fonts.css";
import "katex/dist/katex.min.css";
/**
 * MFMath UI（Vue 3 + Vite）入口
 */
import { createApp } from "vue";
import { winStartDrag, winToggleMaximize } from "./lib/bridge.js";
import { installErrorReporting } from "./lib/diagnostics/errors.js";
import App from "./App.vue";
import router from "./router/index.js";
import { initTheme } from "./lib/bridge.js";

import "./styles/theme.css";

initTheme();

const app = createApp(App).use(router);
/* 尽早上报钩子（在 mount 之前）：之后发生的任何未捕获异常、未处理 Promise、
 * 以及 Vue 组件内部抛的错，都会经宿主日志桥写进 app.log —— 否则 WebView2 里
 * 的异常宿主完全看不到，用户遇到的就是"点了没反应"且日志空白。 */
installErrorReporting(app);
app.mount("#app");

/* 窗口留白也能拖动窗口。
   #app 加了 --pane-gap 的内边距，面板之外的这一圈"空白"如果不可拖动，
   拖窗口就只能靠顶栏，手感会很局促。
   这里只在**点击目标就是 #app 本身**（即那一圈留白）时触发拖动，
   点面板或里面的控件一律不拦，导航项/按钮不受影响。 */
const root = document.getElementById("app");
if (root) {
  root.addEventListener("mousedown", (e) => {
    if (e.button !== 0 || e.target !== root) return;
    winStartDrag();
  });
  root.addEventListener("dblclick", (e) => {
    if (e.target !== root) return;
    winToggleMaximize();
  });
}
