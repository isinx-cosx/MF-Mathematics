/**
 * 参数弹窗「字段标签」的英文译文（D4 正文第二批）。
 *
 * 这些标签来自 `ENGINE_VAR_SPECS`（每个模式的弹窗字段名），共 381 个字段、**184 条唯一标签**
 * （大量模式共用「维数」「最高维数」这类字段名）。它们只在 `MultiVarDialog.vue` 一处渲染，
 * 所以同样是在渲染点包 `t()` —— **不动** ENGINE_VAR_SPECS 里的原文（它是查表用的键）。
 *
 * 标签末尾的「（输入框）」是有含义的：它标记"这一格是主输入框的镜像"，
 * 所以在英文里保留为 "(input box)"。
 *
 * 维护约束（由 tools/check-ui.mjs 第 9 项自检强制）：
 * ENGINE_VAR_SPECS 里每个字段标签都必须在这里有译文 —— 新增弹窗字段漏译会直接失败。
 */
export const EN_VARS = {
  /* ── 通用 ── */
  "被积函数": "Integrand",
  "被积函数（输入框）": "Integrand (input box)",
  "积分变量": "Integration variable",
  "积分变量 x": "Integration variable x",
  "积分变量 y": "Integration variable y",
  "积分变量 z": "Integration variable z",
  "下限": "Lower limit",
  "上限": "Upper limit",
  "函数": "Function",
  "函数（输入框）": "Function (input box)",
  "函数 f（输入框）": "Function f (input box)",
  "函数 g": "Function g",
  "f(x)（输入框）": "f(x) (input box)",
  "g(x)": "g(x)",
  "变量": "Variable",
  "自变量": "Independent variable",
  "维数": "Dimension",
  "维数 n": "Dimension n",
  "最高维数": "Highest dimension",
  "最高维数（输入框）": "Highest dimension (input box)",
  "项数": "Number of terms",
  "项数 n": "Number of terms n",
  "项号 n": "Term index n",
  "周期": "Period",
  "容差": "Tolerance",
  "半径": "Radius",
  "步长": "Step size",
  "步长 h": "Step size h",
  "方向（left/right）": "Direction (left/right)",
  "方向（left/right，留空为两侧）": "Direction (left/right; empty = both sides)",
  "方法(forward/backward/central)": "Method (forward/backward/central)",
  "方法（forward/backward/central）": "Method (forward/backward/central)",
  "a（输入框）": "a (input box)",
  "b": "b",
  "c": "c",
  "k": "k",
  "λ": "λ",
  "A（输入框）": "A (input box)",
  "B": "B",
  "C": "C",
  "向量": "Vector",
  "向量（输入框）": "Vector (input box)",
  "向量 x（输入框）": "Vector x (input box)",

  /* ── 微积分 ── */
  "求导变量": "Differentiation variable",
  "阶数": "Order",
  "阶数（1=一阶）": "Order (1 = first order)",
  "阶数（>=2）": "Order (≥ 2)",
  "求导点": "Point",
  "对哪个变量求偏导": "Variable to differentiate with respect to",
  "趋近值": "Approach value",
  "展开点": "Expansion point",
  "展开项数": "Number of terms",
  "判定点": "Test point",
  "区间左端": "Interval left endpoint",
  "区间右端": "Interval right endpoint",
  "区间 a,b": "Interval a,b",
  "数据点 x": "Data points x",
  "数据点 y": "Data points y",
  "数据点 x（输入框）": "Data points x (input box)",
  "目标函数（输入框）": "Objective function (input box)",
  "初始点": "Initial point",
  "学习率": "Learning rate",
  "迭代次数": "Iterations",
  "x 值": "x value",
  "求曲率的点": "Point for curvature",
  "系数（从 y 到最高阶，逗号分隔）（输入框）":
    "Coefficients (from y up to the highest order, comma-separated) (input box)",
  "未知函数": "Unknown function",
  "微分方程 dy/dx =（输入框）": "Differential equation dy/dx = (input box)",
  "初始 x₀": "Initial x₀",
  "初始 y₀": "Initial y₀",
  "终点 x": "End x",
  "系数矩阵 A（输入框）": "Coefficient matrix A (input box)",
  "右端向量 b": "Right-hand side vector b",
  "右端向量 b（可留空）": "Right-hand side vector b (may be empty)",

  /* ── 重积分 ── */
  "x 下限": "x lower limit",
  "x 上限": "x upper limit",
  "y 下限": "y lower limit",
  "y 上限": "y upper limit",
  "z 下限": "z lower limit",
  "z 上限": "z upper limit",
  "区域 [xa,xb,ya,yb]": "Region [xa,xb,ya,yb]",

  /* ── 概率统计 ── */
  "均值 μ": "Mean μ",
  "标准差 σ": "Standard deviation σ",
  "试验次数 n": "Number of trials n",
  "成功概率 p": "Success probability p",
  "k 值": "k value",
  "子区间数": "Number of subintervals",
  "样本 X（输入框）": "Sample X (input box)",
  "样本 Y": "Sample Y",
  "样本均值（输入框）": "Sample mean (input box)",
  "原假设均值 μ₀": "Null-hypothesis mean μ₀",
  "总体标准差 σ": "Population standard deviation σ",
  "样本量 n": "Sample size n",
  "显著性水平 α": "Significance level α",
  "备择假设": "Alternative hypothesis",
  "备择假设（two-sided/less/greater）": "Alternative hypothesis (two-sided/less/greater)",
  "样本数据（输入框）": "Sample data (input box)",
  "检验统计量（输入框）": "Test statistic (input box)",
  "分布（normal/t/chi2）": "Distribution (normal/t/chi2)",
  "自由度 df": "Degrees of freedom df",
  "第一组数据（输入框）": "First group of data (input box)",
  "第二组数据": "Second group of data",
  "概率表 P（键=值; 键=值）（输入框）": "Probability table P (key=value; key=value) (input box)",
  "事件 A": "Event A",
  "事件 B": "Event B",
  "完备事件组（逗号分隔）": "Complete set of events (comma-separated)",
  "条件 B": "Condition B",
  "已发生的事件": "Event that occurred",

  /* ── 线性代数 ── */
  "矩阵 A": "Matrix A",
  "矩阵 B": "Matrix B",
  "矩阵（输入框）": "Matrix (input box)",
  "矩阵 A（输入框）": "Matrix A (input box)",
  "增广矩阵（输入框）": "Augmented matrix (input box)",
  "系数 a（输入框）": "Coefficient a (input box)",
  "系数 b": "Coefficient b",
  "右端 c（缺省 0）": "Right-hand side c (default 0)",
  "系数类型（a/b）": "Coefficient type (a/b)",
  "变换矩阵（输入框）": "Transformation matrix (input box)",
  "定义域基": "Domain basis",
  "子空间维数": "Subspace dimension",
  "外围空间维数": "Ambient space dimension",
  "运算符（+ 或 *）": "Operator (+ or *)",
  "拟合次数": "Fit degree",

  /* ── 复分析 ── */
  "围道 circle(中心, 半径)": "Contour circle(center, radius)",
  "解析点 a": "Analytic point a",
  "采样点数": "Number of samples",
  "判定点 z（如 1+1i 或 0,1）": "Test point z (e.g. 1+1i or 0,1)",
  "展开中心 z0（如 0+0i）": "Expansion center z0 (e.g. 0+0i)",
  "复函数 f(z)（输入框）": "Complex function f(z) (input box)",
  "圆心（如 0,0）": "Center (e.g. 0,0)",
  "节点数": "Number of nodes",
  "s（输入框）": "s (input box)",
  "s（可为 2、0.5、1+14i）（输入框）": "s (may be 2, 0.5, 1+14i) (input box)",
  "区域（unit_disk / upper_half_plane / right_half_plane / slit_disk / first_quadrant）（输入框）":
    "Domain (unit_disk / upper_half_plane / right_half_plane / slit_disk / first_quadrant) (input box)",

  /* ── 解析几何 ── */
  "长半轴 a（输入框）": "Semi-major axis a (input box)",
  "短半轴 b": "Semi-minor axis b",
  "实半轴 a（输入框）": "Semi-transverse axis a (input box)",
  "虚半轴 b": "Semi-conjugate axis b",
  "焦准距 p（输入框）": "Focal parameter p (input box)",
  "对称轴（x 或 y）": "Axis of symmetry (x or y)",

  /* ── 数列 ── */
  "首项 a₁（输入框）": "First term a₁ (input box)",
  "公差 d": "Common difference d",
  "公比 q": "Common ratio q",
  "通项 aₖ（输入框）": "General term aₖ (input box)",
  "通项 aₙ（输入框）": "General term aₙ (input box)",
  "指标变量": "Index variable",
  "起始项": "Start index",
  "结束项": "End index",
  "级数项数": "Number of series terms",

  /* ── 调和分析 ── */
  "第一个函数（输入框）": "First function (input box)",
  "第二个函数": "Second function",
  "F(ξ)（输入框，引擎用 ξ 作变换变量）":
    "F(ξ) (input box; the engine uses ξ as the transform variable)",
  "使用角频率": "Use angular frequency",
  "x 范围 [min,max]（输入框）": "x range [min,max] (input box)",
  "y 范围 [min,max]": "y range [min,max]",

  /* ── 泛函分析 ── */
  "空间名（输入框）": "Space name (input box)",
  "收敛序列（每行一个向量）（输入框）": "Convergent sequence (one vector per row) (input box)",
  "泛函（如 1,0）": "Functional (e.g. 1,0)",
  "弱极限": "Weak limit",
  "算子族（每个算子一个矩阵）（输入框）": "Operator family (one matrix per operator) (input box)",
  "测试点（每行一个向量）": "Test points (one vector per row)",
  "初始泛函系数（输入框）": "Initial functional coefficients (input box)",

  /* ── 代数拓扑 ── */
  "点云（写成 [[0,0],[1,0],…]）（输入框）": "Point cloud (written as [[0,0],[1,0],…]) (input box)",
  "最大尺度": "Maximum scale",
  "显著性阈值": "Significance threshold",
  "单形列表（写成 [[0,1,2],[0,1,3]]）（输入框）":
    "Simplex list (written as [[0,1,2],[0,1,3]]) (input box)",
  "只保留极大单形": "Keep only maximal simplices",
  "空间名（T2/RP2/K/S1/S2/S3）（输入框）": "Space name (T2/RP2/K/S1/S2/S3) (input box)",
  "流形（S1/S2/S3/T2/RP2/K）（输入框）": "Manifold (S1/S2/S3/T2/RP2/K) (input box)",
  "复形（写成 2:0,1,2|1:0,1|0:0,1,2）（输入框）":
    "Complex (written as 2:0,1,2|1:0,1|0:0,1,2) (input box)",

  /* ── 测度论 ── */
  "X 的取值规则（输入框）": "Rule for X values (input box)",
  "样本空间 Ω（如 1,2,3,4）": "Sample space Ω (e.g. 1,2,3,4)",
  "子 σ-代数（如 parity）": "Sub-sigma-algebra (e.g. parity)",
  "第一个测度（数字或 lebesgue）（输入框）": "First measure (a number or lebesgue) (input box)",
  "第二个测度": "Second measure",
  "第一个区间 [a,b]": "First interval [a,b]",
  "第二个区间 [a,b]": "Second interval [a,b]",
  "随机变量取值规则（输入框）": "Rule for random-variable values (input box)",
  "分布（uniform / normal(0,1) / …）": "Distribution (uniform / normal(0,1) / …)",
  "分布（normal/exponential/…）": "Distribution (normal/exponential/…)",

  /* ── 微分方程 / 相图 ── */
  "dx/dt": "dx/dt",
  "dy/dt": "dy/dt",
  "轨迹条数": "Number of trajectories",
  "网格分辨率": "Grid resolution",
};
