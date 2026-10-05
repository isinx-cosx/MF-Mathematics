/**
 * English 译文表（D4）。
 *
 * 键是**界面里的中文原文**（见 lib/i18n/index.js 的说明）。
 * 只放"已经用 t() 包起来"的文案；没包的地方照旧显示中文，不会出现空白。
 * 漏译不会静默：`npm run check` 会检查每个 t("…") 的字面量键都在这里存在。
 */
export const EN = {
  /* ── 导航分组 ── */
  "计算模式": "Calculation",
  "绘图模式": "Plotting",
  "工具": "Tools",
  "帮助": "Help",

  /* ── 导航条目 · 计算模式 ── */
  "基础运算": "Basic Arithmetic",
  "代数计算": "Algebra",
  "微积分": "Calculus",
  "解析几何": "Analytic Geometry",
  "数列": "Sequences",
  "线性代数": "Linear Algebra",
  "概率论与数理统计": "Probability & Statistics",
  "数值分析": "Numerical Analysis",
  "数论": "Number Theory",
  "实分析": "Real Analysis",
  "泛函分析": "Functional Analysis",
  "复分析": "Complex Analysis",
  "代数拓扑": "Algebraic Topology",
  "测度论": "Measure Theory",
  "调和分析": "Harmonic Analysis",

  /* ── 导航条目 · 绘图模式 ── */
  "2D 函数绘图": "2D Function Plot",
  "极坐标": "Polar",
  "3D 曲面": "3D Surface",
  "复平面": "Complex Plane",
  "向量场": "Vector Field",
  "自由几何": "Free Geometry",
  "分形": "Fractal",

  /* ── 导航条目 · 工具 / 帮助 ── */
  "搜索": "Search",
  "控制台": "Console",
  "函数工具箱": "Function Toolbox",
  "使用教程": "Tutorials",
  "示例任务库": "Examples",

  /* ── 顶栏与外壳 ── */
  "设置": "Settings",
  "历史": "History",
  "关于": "About",
  "键盘": "Keypad",
  "收起": "Collapse",
  "展开侧栏": "Expand sidebar",
  "收起侧栏": "Collapse sidebar",
  "切换主题": "Switch theme",
  "打开数学键盘": "Open math keypad",
  "收起数学键盘": "Hide math keypad",
  "AI 助手（解释与思路；计算仍由引擎完成）": "AI assistant (explanations only — all computation is done by the engine)",
  "有新版本": "Update available",

  /* ── 外观浮层 ── */
  "外观": "Appearance",
  "配色": "Color scheme",
  "圆角与阴影": "Corners & shadows",
  "疏密": "Density",
  "界面字体": "UI font",
  "跟随系统深浅色": "Follow system theme",
  "公式与代码始终等宽，不受界面字体影响。": "Formulas and code stay monospaced, regardless of UI font.",
  "深": "Dark",
  "浅": "Light",
  "关闭": "Close",
  "外观设置": "Appearance settings",

  /* ── 窗口控制 ── */
  "最小化": "Minimize",
  "最大化": "Maximize",
  "还原": "Restore",

  /* ── 设置：语言 ── */
  "语言": "Language",
  "界面语言": "Interface language",
  "切换到英文界面": "Switch to English",
  "语言只影响界面文字，计算与结果表示方式不变。":
    "Language affects interface text only; computation and result formatting are unchanged.",
};
