/**
 * vue-router — 单页多路由（替代旧 iframe 多页）
 *
 * 迁移已完成：registry.js 里的 25 个导航项**全部**有真实组件
 * （14 个在 REAL_VIEWS、13 个 CALC_ROUTES 走 CalcView，另加首页）。
 * 原先的 PlaceholderView（文案是"该模式正由旧版 MFMath.UI 迁移到 Vue，暂未接入"）
 * 已经**没有任何路由会走到**，故删除；这里留一个最小兜底，
 * 防止将来往导航里加条目却忘了配视图时直接白屏。
 */
import { h } from "vue";
import { createRouter, createWebHashHistory } from "vue-router";
import { NAV_GROUPS, findNav } from "./registry.js";

const HomeView = () => import("../views/HomeView.vue");

/** 兜底视图：每个导航项都应在 REAL_VIEWS 或 CALC_ROUTES 里有归宿（当前 25/25） */
const FallbackView = {
  name: "FallbackView",
  render: () => h("div", { class: "placeholder" }, "这个入口还没有对应的界面。"),
};

/** 有独立组件的路由（其余学科计算视图统一走 CalcView） */
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
  // 函数工具箱：把全部 424 个引擎 action 列表化并可直接调用
  // （界面模式表只覆盖 371 个，余下 38 个原本没有任何入口）
  "/tools/toolbox": () => import("../views/tools/ToolboxView.vue"),
  // 账号：与站点（mf-vis-science.cn）的账号接口对接。token 只存宿主，页面读不到。
  // 未登录/断网都不影响任何计算功能（见 docs/ACCOUNT.md）。
  "/account": () => import("../views/account/AccountView.vue"),
  // 教程系统（v1 只有帮助浏览器一个入口，这里教程目录与示例库都在导航里）
  "/tutorial": () => import("../views/tutorial/TutorialCatalogView.vue"),
  "/examples": () => import("../components/tutorial/ExampleLibrary.vue"),
  // 设置面板：**容器**而非单页。9 个分组全部已落地（外观 / 计算与绘图 / 引擎 / 组件 /
  // AI / 搜索 / 账号 / 更新 / 存储与数据）—— catalog.js 里已无 status != "ready" 的项。
  "/settings": () => import("../views/settings/SettingsView.vue"),
};

/** 学科计算视图统一走 CalcView（按路由末段读取 VIEW_CONFIGS 的配置） */
const CALC_VIEW = () => import("../views/calc/CalcView.vue");
const CALC_ROUTES = [
  "/calc/algebra", "/calc/calculus", "/calc/analytic-geometry", "/calc/linear-algebra",
  "/calc/numerical", "/calc/number-theory", "/calc/probability", "/calc/real-analysis",
  "/calc/sequences", "/calc/complex-analysis", "/calc/functional-analysis",
  "/calc/algebraic-topology", "/calc/measure-theory",
  // 调和分析：本轮新增的第 14 个学科视图（走同一个 CalcView）
  "/calc/harmonic-analysis",
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
      component: real || (isCalc ? CALC_VIEW : FallbackView),
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

// 账号：入口是顶栏的用户名/登录按钮（不占侧栏一项），所以同样必须显式注册。
// 这条注释不是礼节 —— 我在这一轮里又把同一个坑踩了一次：只加进 REAL_VIEWS 而没加路由，
// 结果 /account 点进去内容区空白。凡是不在 NAV_GROUPS 里的页面，都要在这里补一行。
routes.push({
  path: "/account",
  name: "account",
  component: () => import("../views/account/AccountView.vue"),
  meta: { title: "账号", desc: "登录 · 额度 · 会话" },
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
