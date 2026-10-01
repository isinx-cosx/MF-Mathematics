import "mathlive/static.css";
import "mathlive/fonts.css";
import "katex/dist/katex.min.css";
/**
 * MFMath UI（Vue 3 + Vite）入口
 */
import { createApp } from "vue";
import { winStartDrag, winToggleMaximize } from "./lib/bridge.js";
import App from "./App.vue";
import router from "./router/index.js";
import { initTheme } from "./lib/bridge.js";

import "./styles/theme.css";

initTheme();

const app = createApp(App).use(router);
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
