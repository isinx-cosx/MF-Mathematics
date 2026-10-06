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

  /* ── 计算页：界面文案 ── */
  "计算中…": "Computing…",
  "计算结果": "Compute",
  "错误": "Error",
  "删除": "Delete",
  "输入参数": "Parameters",
  "取消": "Cancel",
  "计算": "Compute",
  "（未接入引擎）": " (not wired to the engine)",
  "输入表达式，如 x^2+3*x-1": "Enter an expression, e.g. x^2+3*x-1",

  /* ── 数学键盘（6 个分类名里 4 个与导航同名，已在上面的导航条目里）── */
  "希腊字母": "Greek Letters",
  "概率统计": "Probability & Statistics",
  "常用模板": "Common Templates",
  "数学键盘": "Math Keypad",
  "最近使用": "Recently used",
  "最近": "Recent",
  "收藏": "Favorites",
  "搜索符号（如 积分 / sqrt / alpha）": "Search symbols (e.g. integral / sqrt / alpha)",
  "未选中输入框 —— 点一下计算或绘图里的输入格，再点符号即可插入":
    "No input field selected — click a field in a calculation or plot first, then tap a symbol",
  "没有匹配的符号": "No matching symbols",
  "还没有收藏。点键位右上角的 ★ 即可收藏。": "No favorites yet. Tap the ★ in a key's top-right corner to add one.",
  "还没有使用记录。": "No recent keys yet.",
  "共 {n} 键 ·": "{n} keys ·",
  "模板类键面按数学排版显示 · 插入的是 LaTeX":
    "Template keys are typeset as math · inserting LaTeX",

  /* ── 计算页：视图描述 ──
   * 视图**标题**与导航条目同名，已被上面的导航译文覆盖；这里只需要描述。 */
  "包含：表达式化简、求导、积分、极限、级数展开、复数运算等":
    "Includes expression simplification, derivatives, integrals, limits, series expansion, complex arithmetic and more",
  "包含：基本群、同调群、上同调、贝蒂数、欧拉示性数、映射度、不动点定理、持续同调等":
    "Includes fundamental groups, homology and cohomology, Betti numbers, Euler characteristic, mapping degree, fixed point theorems, persistent homology and more",
  "包含：两点距离、中点、直线方程、圆方程等":
    "Includes distances, midpoints, line and circle equations and more",
  "包含：求导/积分/极限/级数/微分应用/积分应用/收敛判别等":
    "Includes derivatives, integrals, limits, series, differential and integral applications, convergence tests and more",
  "包含：复数运算、回路积分、柯西定理、留数、洛朗级数、Zeta函数等":
    "Includes complex arithmetic, loop integrals, Cauchy's theorem, residues, Laurent series, the zeta function and more",
  "包含：Banach/Hilbert空间、算子理论、Hahn-Banach、谱定理等":
    "Includes Banach/Hilbert spaces, operator theory, Hahn-Banach, the spectral theorem and more",
  "包含：高斯消元、特征值、对角化、施密特正交化、二次型等":
    "Includes Gaussian elimination, eigenvalues, diagonalization, Gram-Schmidt, quadratic forms and more",
  "包含：σ-代数、勒贝格测度、可测函数、勒贝格积分、收敛定理、乘积测度、Fubini定理、概率测度等":
    "Includes sigma-algebras, Lebesgue measure, measurable functions, the Lebesgue integral, convergence theorems, product measures, Fubini's theorem, probability measures and more",
  "包含：素数、模运算、欧拉函数、连分数、中国剩余定理等":
    "Includes primes, modular arithmetic, Euler's totient, continued fractions, the Chinese remainder theorem and more",
  "包含：插值、数值积分、ODE 数值解、非线性方程求根等":
    "Includes interpolation, numerical integration, numerical ODE solutions, root finding and more",
  "包含：概率空间、随机变量、分布族、统计推断、回归分析等":
    "Includes probability spaces, random variables, distribution families, statistical inference, regression analysis and more",
  "包含：ε-δ极限、一致收敛、黎曼积分、介值/极值定理等":
    "Includes ε-δ limits, uniform convergence, the Riemann integral, the intermediate and extreme value theorems and more",
  "包含：等差/等比数列、递推数列等":
    "Includes arithmetic and geometric sequences, recurrence sequences and more",
  "包含：傅里叶变换与级数、卷积与卷积定理、小波与短时傅里叶、滤波器、δ 分布与缓增分布、泊松求和、不确定性原理等":
    "Includes Fourier transforms and series, convolution and the convolution theorem, wavelets and the short-time Fourier transform, filters, the delta and tempered distributions, Poisson summation, the uncertainty principle and more",
};
