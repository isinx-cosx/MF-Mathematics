/**
 * 导航表 —— 零依赖模块，Vue 版与 React 版共用同一份。
 *
 * ⚠ 本文件在 `src/lib/` 下，**两个工程都会 import 它**（React 侧经 alias `@shared` →
 * `MFMath.UI.Vue/src/lib`，见 MFMath.UI.React/vite.config.ts 与 tsconfig.json）：
 *   · 不许 import Vue（.vue / vue-router）；
 *   · 不许在模块作用域碰 DOM 全局（window / document …）。
 * 之前 React 版把这张表**手抄**了一份（App.tsx 里有注释"后续应收口"），
 * 抄漏了这里的顺序说明、也已经开始漂移；抽到这里后两边就是同一份数据。
 */

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
      // 调和分析：本轮新增的第 14 个学科视图。引擎的 harmonic_analysis 模块
      // （傅里叶/卷积/小波/滤波器/δ 分布…）原先在 13 个视图里没有容身之处。
      { name: "调和分析", route: "/calc/harmonic-analysis" },
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
    items: [
      // 联网搜索是页面（不是浮层）：结果要来回看、要送进计算页，而且教程示例
      // 「联网搜索」需要有个能落地的路由（/tools/search?q=…）
      { name: "搜索", route: "/tools/search" },
      { name: "控制台", route: "/tools/console" },
      // 函数工具箱：把**全部 424 个引擎 action**列表化并可直接调用。
      // 为什么需要它：界面模式表（ENGINE_MAP）只覆盖 371 个，剩下 38 个
      // （matrix_multiply / simplify_sym / taylor_series / is_harmonic …）
      // 在界面上**没有任何入口** —— 引擎算得出来、人却点不出来。
      // 这里以 src/lib/ai/engine-signatures.json（从引擎 handler 生成、
      // 与注册表逐字一致的 424 条参数表）为唯一数据源，表驱动渲染，
      // 所以引擎将来新增 action 会自动出现在这里，不会再出现这种倒挂。
      { name: "函数工具箱", route: "/tools/toolbox" },
    ],
  },
  {
    // 教程系统的入口。v1 的帮助浏览器只能从菜单/F1 打开，且"交互式引导"
    // 硬编码只能引导 quick-start；这里把教程与示例库放进导航，任何人都能直接进。
    id: "help",
    title: "帮助",
    items: [
      { name: "使用教程", route: "/tutorial" },
      { name: "示例任务库", route: "/examples" },
    ],
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
