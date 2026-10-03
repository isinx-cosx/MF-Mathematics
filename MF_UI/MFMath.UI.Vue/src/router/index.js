/**
 * vue-router — 单页多路由（替代旧 iframe 多页）
 * 骨架阶段：首页 + 占位计算视图；功能视图迁移时逐个替换
 */
import { createRouter, createWebHashHistory } from "vue-router";
import { NAV_GROUPS, findNav } from "./registry.js";

const HomeView = () => import("../views/HomeView.vue");
const PlaceholderView = () => import("../views/PlaceholderView.vue");

/** 已迁移为真实组件的路由（其余仍为占位） */
const REAL_VIEWS = {
  // 基础运算：计算器视图（旧版是空壳，这里经引擎真算）
  "/calc/basic": () => import("../views/calc/BasicCalcView.vue"),
  "/plot/2d": () => import("../views/plot/PlotView.vue"),
  // 极坐标：原版是独立入口（i18n.py 的 get_plot_modes 第 2 项），
  // 能力早就在 plotMath/PlotView 里，缺的只是入口；grid 经 meta 传给 PlotView。
  "/plot/polar": () => import("../views/plot/PlotView.vue"),
  "/plot/3d": () => import("../views/plot/Plot3DView.vue"),
  "/plot/vector": () => import("../views/plot/PlotVectorView.vue"),
  "/plot/fractal": () => import("../views/plot/PlotFractalView.vue"),
  "/plot/complex": () => import("../views/plot/PlotComplexView.vue"),
  "/plot/geometry": () => import("../views/plot/PlotGeometryView.vue"),
  // 控制台：在应用里写 Python/C++ 小程序，两条语言都通过 mfmath 调同一个 C++ 引擎
  "/tools/console": () => import("../views/tools/ConsoleView.vue"),
  // 联网搜索：抓取与解析在宿主（C#），凭据不进渲染进程；这里是一个页面
  // （搜索结果是内容，值得有路由：教程示例「联网搜索」直接落到 /tools/search?q=…）
  "/tools/search": () => import("../views/tools/SearchView.vue"),
  // 教程系统（v1 只有帮助浏览器一个入口，这里教程目录与示例库都在导航里）
  "/tutorial": () => import("../views/tutorial/TutorialCatalogView.vue"),
  "/examples": () => import("../components/tutorial/ExampleLibrary.vue"),
  // 设置面板：**容器**而非单页，分组按依赖分三批填内容（外观/引擎/组件/存储先做，
  // 搜索依赖 P1、AI 依赖 P3、更新依赖 P5，先以占位列出并向用户说明依赖）。
  "/settings": () => import("../views/settings/SettingsView.vue"),
};

/** 学科计算视图统一走 CalcView（按路由末段读取 VIEW_CONFIGS 的配置） */
const CALC_VIEW = () => import("../views/calc/CalcView.vue");
const CALC_ROUTES = [
  "/calc/algebra", "/calc/calculus", "/calc/analytic-geometry", "/calc/linear-algebra",
  "/calc/numerical", "/calc/number-theory", "/calc/probability", "/calc/real-analysis",
  "/calc/sequences", "/calc/complex-analysis", "/calc/functional-analysis",
  "/calc/algebraic-topology", "/calc/measure-theory",
];

const routes = [
  { path: "/", name: "home", component: HomeView, meta: { title: "首页", desc: "多功能可视化科学计算" } },
];

for (const g of NAV_GROUPS) {
  for (const it of g.items) {
    const real = REAL_VIEWS[it.route];
    const isCalc = CALC_ROUTES.includes(it.route);
    routes.push({
      path: it.route,
      name: it.route.slice(1).replace(/\//g, "-"),
      component: real || (isCalc ? CALC_VIEW : PlaceholderView),
      props: real || isCalc ? undefined : { name: it.name },
      // grid 用于"极坐标"这类共用同一个视图、只是初始网格不同的入口
      meta: { title: it.name, desc: g.title, calc: isCalc, grid: it.grid },
    });
  }
}

// 教程正文：不在 NAV_GROUPS 里（不是导航项，而是从目录或引导进入的详情页）
routes.push({
  path: "/tutorial/:id",
  name: "tutorial-article",
  component: () => import("../views/tutorial/HelpArticleView.vue"),
  meta: { title: "教程", desc: "帮助" },
});

// 设置：同样不在 NAV_GROUPS 里（入口是侧栏底部的「设置」按钮，面板内部自带分组导航）。
// ⚠️ 必须在这里显式注册：上面的路由是**按 NAV_GROUPS 的项循环生成**的，
// 不放进导航就等于没有路由 —— 之前漏了这一步，点「设置」后内容区一片空白。
routes.push({
  path: "/settings",
  name: "settings",
  component: () => import("../views/settings/SettingsView.vue"),
  meta: { title: "设置", desc: "外观 · 引擎 · 组件 · 数据" },
});

const router = createRouter({
  // hash 模式：file:// 与 dev server 都可用，无需服务端配合
  history: createWebHashHistory(),
  routes,
});

router.afterEach((to) => {
  document.title = to.meta?.title ? `${to.meta.title} · MF-Mathematics` : "MF-Mathematics";
});

export default router;
