/**
 * 视图注册表 — Vue 版（对应旧版 MODES / 视图 HTML 映射）
 * 迁移进度：占位视图逐步替换为真实组件
 */
import HomeView from "../views/HomeView.vue";

/* 懒加载：每新增一个真实视图，把 lazy 换成 import 即可 */
const lazy = (p) => () => import(`../views/${p}.vue`);

/**
 * 导航表（NAV_GROUPS / findNav）已抽到零依赖模块 src/lib/router/nav.js ——
 * React 版经 alias `@shared` 直接复用它，两边不再各存一份手抄件。
 * 这里只做**转出**：原有 `from "./router/registry.js"` 的 import 一律不受影响。
 */
export { NAV_GROUPS, findNav } from "../lib/router/nav.js";
