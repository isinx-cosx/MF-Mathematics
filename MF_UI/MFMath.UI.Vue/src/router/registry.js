/**
 * 视图注册表 — Vue 版（对应旧版 MODES / 视图 HTML 映射）
 * 迁移进度：占位视图逐步替换为真实组件
 */
import HomeView from "../views/HomeView.vue";

/* 懒加载：每新增一个真实视图，把 lazy 换成 import 即可 */
const lazy = (p) => () => import(`../views/${p}.vue`);

/** 左侧导航：分组 → [{name 显示名, route 路由路径, icon?}] */
export const NAV_GROUPS = [
  {
    id: "calc",
    title: "计算模式",
    // 顺序与**原版**对齐：见 MF_UI/i18n.py 的 get_calc_modes()。
    // 之前这一组是 5~12 位被重排过的（数列被挪到第 10、概率与数值互换…），
    // 原因是从更早的网页壳 MFMath.UI/js/app.js 继承而来，不是按原版。
    // 以原版为准（原版才是功能基准）。
    items: [
      { name: "基础运算", route: "/calc/basic" },
      { name: "代数计算", route: "/calc/algebra" },
      { name: "微积分", route: "/calc/calculus" },
      { name: "解析几何", route: "/calc/analytic-geometry" },
      { name: "数列", route: "/calc/sequences" },
      { name: "线性代数", route: "/calc/linear-algebra" },
      { name: "概率论与数理统计", route: "/calc/probability" },
      { name: "数值分析", route: "/calc/numerical" },
      { name: "数论", route: "/calc/number-theory" },
      { name: "实分析", route: "/calc/real-analysis" },
      { name: "泛函分析", route: "/calc/functional-analysis" },
      { name: "复分析", route: "/calc/complex-analysis" },
      { name: "代数拓扑", route: "/calc/algebraic-topology" },
      { name: "测度论", route: "/calc/measure-theory" },
    ],
  },
  {
    id: "plot",
    title: "绘图模式",
    // 同样按原版 i18n.py 的 get_plot_modes()：7 项，且极坐标排在第 2。
    // 极坐标之前是**整项缺失**——能力其实早就有（plotMath.js 已把 r=f(θ) 解析成
    // type:"polar"，PlotView 也做了 r·cosθ/r·sinθ 映射与极坐标网格切换），
    // 只是没有入口。这里补上 route，grid:"polar" 让 PlotView 进去就用极坐标网格。
    items: [
      { name: "2D 函数绘图", route: "/plot/2d" },
      { name: "极坐标", route: "/plot/polar", grid: "polar" },
      { name: "3D 曲面", route: "/plot/3d" },
      { name: "复平面", route: "/plot/complex" },
      { name: "向量场", route: "/plot/vector" },
      { name: "自由几何", route: "/plot/geometry" },
      { name: "分形", route: "/plot/fractal" },
    ],
  },
  {
    id: "tools",
    title: "工具",
    items: [{ name: "控制台", route: "/tools/console" }],
  },
];

/** 按路径查导航项 */
export function findNav(routePath) {
  for (const g of NAV_GROUPS) {
    for (const it of g.items) {
      if (it.route === routePath) return { group: g, item: it };
    }
  }
  return null;
}
