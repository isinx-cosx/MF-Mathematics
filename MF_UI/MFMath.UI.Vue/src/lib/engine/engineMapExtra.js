/**
 * engineMapExtra.js — 对自动生成的 engineMap.js 的**增量与修正**
 *
 * 拆成独立文件的原因：engineMap.js 是从旧版 MFMath.UI 自动转换来的（保原样不动），
 * 这里集中放两类东西，便于 review 与回溯：
 *   ① 新增映射：以前下拉里标着「未接入引擎」、其实引擎已有对应函数的模式
 *   ② 修正映射：旧条目参数对不上（缺 point、把 matrix 当字符串塞），
 *      合并时后者覆盖前者（engineMap.js 里 `{...RAW, ...EXTRA}`）
 *
 * ⚠ 字段顺序约定：`args` 里**可选参数**的先后顺序要与 ENGINE_VAR_SPECS 字段顺序一致，
 *    因为弹窗的值是按顺序填进去的（见 calcArgs.buildEngineArgs）。
 * ⚠ 弹窗第一个字段是输入框的占位（值就是输入框内容），标签里带「（输入框）」的会被跳过。
 */
"use strict";

/* ── 复用的参数片段 ── */
const VAR_X = { key: "var", type: "string", opt: true };
const EXPR = { key: "expr", type: "string", opt: false };
const A_OPT = { key: "a", type: "string_or_number", opt: true };
const B_OPT = { key: "b", type: "string_or_number", opt: true };
const p1 = { key: "p1", type: "point", opt: false };
const p2 = { key: "p2", type: "point", opt: false };

export const EXTRA_MAP = {
  /* ════════ 代数拓扑 ════════ */
  // cup_product 是引擎里的"结论型"结果（返回运算的定义与对应关系）
  "杯积": { fn: "cup_product", module: "at", args: [] },

  /* ════════ 代数 ════════ */
  // 解方程/组：引擎的通用符号求解（单个方程；线性方程组走「求解方程组」）
  "解方程/组": { fn: "solve_sym", module: "symbolic", args: [VAR_X, EXPR] },
  // 不等式组：输入用 `;` 分隔多条，引擎收 string 数组
  "解不等式/组": { fn: "solve_inequality_system", module: "algebra", args: [{ key: "ineqs", type: "string_array", opt: false }] },
  // 这两个是"恒等式清单"式结果（引擎返回现成的条目），无需参数
  "三角恒等式": { fn: "trig_basic_identities", module: "algebra", args: [] },
  "组合恒等式": { fn: "comb_identities", module: "algebra", args: [] },

  /* ════════ 解析几何 ════════ */
  // 两个点用 `;` 分隔：输入 "(1,2);(3,4)"
  "中点坐标": { fn: "midpoint", module: "algebra", args: [p1, p2] },
  "斜率": { fn: "line_from_points", module: "algebra", args: [p1, p2] },
  "直线方程": { fn: "line_from_points", module: "algebra", args: [p1, p2] },
  // 圆锥曲线（引擎新实现：标准位置，给出标准式/一般式/焦点/离心率/准线）
  "椭圆方程": { fn: "ellipse_standard", module: "algebra", args: [{ key: "a", type: "double", opt: true }, { key: "b", type: "double", opt: true }] },
  "双曲线方程": { fn: "hyperbola_standard", module: "algebra", args: [{ key: "a", type: "double", opt: true }, { key: "b", type: "double", opt: true }] },
  "抛物线方程": { fn: "parabola_standard", module: "algebra", args: [{ key: "p", type: "double", opt: true }, { key: "axis", type: "string", opt: true }] },

  /* ════════ 微积分 ════════ */
  "高阶导数": { fn: "diff", module: "calculus", args: [{ key: "var", type: "string", opt: true }, { key: "order", type: "int", opt: true }, EXPR] },
  "偏导": { fn: "diff", module: "calculus", args: [{ key: "var", type: "string", opt: true }, { key: "order", type: "int", opt: true }, EXPR] },
  "不定积分": { fn: "integrate", module: "calculus", args: [VAR_X, EXPR] },
  "定积分": { fn: "integrate", module: "calculus", args: [{ key: "var", type: "string", opt: true }, A_OPT, B_OPT, EXPR] },
  "广义积分": { fn: "improper_integral", module: "calculus", args: [{ key: "var", type: "string", opt: true }, A_OPT, B_OPT, EXPR] },
  "重积分": {
    fn: "integrate_double", module: "calculus",
    args: [
      { key: "x", type: "string", opt: true }, { key: "y", type: "string", opt: true },
      { key: "xa", type: "string_or_number", opt: true }, { key: "xb", type: "string_or_number", opt: true },
      { key: "ya", type: "string_or_number", opt: true }, { key: "yb", type: "string_or_number", opt: true },
      EXPR,
    ],
  },
  "单侧极限": { fn: "limit", module: "calculus", args: [VAR_X, { key: "point", type: "string_or_number", opt: true }, { key: "direction", type: "string", opt: true }, EXPR] },
  "无穷极限": { fn: "limit", module: "calculus", args: [VAR_X, { key: "point", type: "string_or_number", opt: true }, EXPR] },
  // calc_is_continuous 还要求一个"在哪一点判断"的 point（旧写法漏了，会报缺 point）
  "连续性判定": { fn: "calc_is_continuous", module: "calculus", args: [VAR_X, { key: "point", type: "string_or_number", opt: true }, EXPR] },
  "级数展开": { fn: "power_series", module: "calculus", args: [VAR_X, { key: "point", type: "double", opt: true }, { key: "n", type: "int", opt: true }, EXPR] },
  "幂级数": { fn: "power_series", module: "calculus", args: [VAR_X, { key: "point", type: "double", opt: true }, { key: "n", type: "int", opt: true }, EXPR] },
  "极值": { fn: "local_extrema", module: "calculus", args: [VAR_X, EXPR] },
  "最值": { fn: "global_extrema", module: "calculus", args: [VAR_X, A_OPT, B_OPT, EXPR] },
  "平均值": { fn: "integral_mean_value", module: "real_analysis", args: [A_OPT, B_OPT, EXPR] },
  "旋转体体积(圆盘)": { fn: "volume_disk", module: "calculus", args: [VAR_X, A_OPT, B_OPT, EXPR] },
  "旋转体体积(壳)": { fn: "volume_shell", module: "calculus", args: [VAR_X, A_OPT, B_OPT, EXPR] },
  "Rolle定理": { fn: "calc_rolle_theorem", module: "calculus", args: [VAR_X, A_OPT, B_OPT, EXPR] },
  "Lagrange中值定理": { fn: "calc_lagrange_theorem", module: "calculus", args: [VAR_X, A_OPT, B_OPT, EXPR] },
  "ODE数值解": { fn: "rk4", module: "numerical", args: [{ key: "h", type: "double", opt: true }, { key: "f", type: "string", opt: false }, { key: "t0", type: "double", opt: false }, { key: "y0", type: "double", opt: false }, { key: "t_end", type: "double", opt: false }] },
  "Fourier级数": { fn: "fourier_series", module: "harmonic_analysis", args: [{ key: "f", type: "string", opt: false }, { key: "n_terms", type: "int", opt: true }, { key: "period", type: "double", opt: true }] },
  "Fourier系数": { fn: "fourier_coeff", module: "harmonic_analysis", args: [{ key: "f", type: "string", opt: false }, { key: "n", type: "int", opt: true }, { key: "period", type: "double", opt: true }, { key: "coeff_type", type: "string", opt: true }] },
  "复Fourier系数": { fn: "complex_fourier_coeff", module: "harmonic_analysis", args: [{ key: "f", type: "string", opt: false }, { key: "n", type: "int", opt: true }, { key: "period", type: "double", opt: true }] },
  "Fourier变换": { fn: "fourier_transform", module: "harmonic_analysis", args: [{ key: "f", type: "string", opt: false }] },
  "逆Fourier变换": { fn: "inverse_fourier_transform", module: "harmonic_analysis", args: [{ key: "F", type: "string", opt: false }] },

  /* ════════ 复分析 ════════ */
  // complex_eval 只接受**已带具体复数**的表达式（z^2 这种含自由符号的会报错），
  // 需要代入点时用「复函数值」以外的方式（引擎暂无复数代入接口，这里如实标注）
  "复函数值": { fn: "complex_eval", module: "complex_analysis", args: [EXPR] },
  // 新增：共轭/模长/辐角（引擎本轮补齐）
  "复共轭": { fn: "complex_conjugate", module: "complex_analysis", args: [EXPR] },
  "复模长": { fn: "complex_modulus", module: "complex_analysis", args: [EXPR] },
  "复辐角": { fn: "complex_argument", module: "complex_analysis", args: [EXPR] },
  // Riemann ζ：引擎的 zeta_series 就是 ζ(s)（s 可为数字、[re,im] 或 "a±bi"）
  "Riemann ζ": { fn: "zeta_series", module: "complex_analysis", args: [{ key: "s", type: "string_or_number", opt: true }, { key: "n_terms", type: "int", opt: true }] },
  "Dirichlet η": { fn: "dirichlet_eta", module: "complex_analysis", args: [{ key: "s", type: "double", opt: true }] },
  // is_holomorphic 需要判定的点 z（复数：数字 / [re,im] / "a±bi"）
  "全纯判定": { fn: "is_holomorphic", module: "complex_analysis", args: [{ key: "z", type: "point", opt: true }, { key: "func", type: "string", opt: false }] },
  "Cauchy积分": { fn: "cauchy_integral_formula", module: "complex_analysis", args: [{ key: "contour", type: "string", opt: true }, { key: "a", type: "string", opt: true }, { key: "func", type: "string", opt: false }, { key: "n_points", type: "int", opt: true }] },
  // laurent_series 需要展开中心 z0
  "Laurent级数": { fn: "laurent_series", module: "complex_analysis", args: [{ key: "z0", type: "point", opt: true }, { key: "n", type: "int", opt: true }, { key: "func", type: "string", opt: false }] },
  "围道积分": { fn: "contour_integral", module: "complex_analysis", args: [{ key: "gamma", type: "string", opt: true }, { key: "func", type: "string", opt: false }, { key: "n_points", type: "int", opt: true }] },
  // riemann_mapping 只需要区域名（查表式结果），区域名见 EXTRA_VAR_SPECS 里的说明
  "共形映射": { fn: "riemann_mapping", module: "complex_analysis", args: [{ key: "region", type: "string", opt: true }] },

  /* ════════ 泛函分析 ════════ */
  "Lp范数": { fn: "lp_norm", module: "fa", args: [{ key: "vector", type: "double_array", opt: false }] },
  "Banach空间": { fn: "is_banach", module: "fa", args: [{ key: "space", type: "string", opt: true }, { key: "dimension", type: "int", opt: true }] },
  "Hilbert空间": { fn: "is_hilbert", module: "fa", args: [{ key: "space", type: "string", opt: true }, { key: "dimension", type: "int", opt: true }] },
  "线性算子": { fn: "linear_transform", module: "linear_algebra", args: [{ key: "matrix", type: "matrix", opt: false }, { key: "vector", type: "vec", opt: false }] },
  "Hahn-Banach定理": { fn: "hahn_banach_extension", module: "fa", args: [{ key: "a", type: "double_array", opt: false }, { key: "subspace_dim", type: "int", opt: false }, { key: "ambient_dim", type: "int", opt: true }] },
  // 声明顺序 = 用户输入顺序：先函数、再区间（`;` 分段按这个顺序吃）
  "内积空间": { fn: "inner_product", module: "fa", args: [{ key: "f", type: "string", opt: false }, { key: "g", type: "string", opt: false }, { key: "domain", type: "double_array", opt: true }, { key: "n_points", type: "int", opt: true }] },
  "正交性": { fn: "funct_is_orthogonal", module: "fa", args: [{ key: "f", type: "string", opt: false }, { key: "g", type: "string", opt: false }, { key: "domain", type: "double_array", opt: true }] },
  // weak_convergence 的序列是"二维数组：每一行是一个向量 x_n"（旧条目完全没传 sequence）
  "弱*收敛": { fn: "weak_convergence", module: "fa", args: [{ key: "sequence", type: "matrix", opt: true }, { key: "functional", type: "double_array", opt: true }, { key: "limit", type: "double_array", opt: true }, { key: "tol", type: "double", opt: true }] },
  "弱收敛": { fn: "weak_convergence", module: "fa", args: [{ key: "sequence", type: "matrix", opt: true }, { key: "functional", type: "double_array", opt: true }, { key: "limit", type: "double_array", opt: true }, { key: "tol", type: "double", opt: true }] },
  // uniform_boundedness 的 operators 是"矩阵的数组"（每个算子一个矩阵）
  "一致有界原理": { fn: "uniform_boundedness", module: "fa", args: [{ key: "operators", type: "matrix_list", opt: true }, { key: "test_points", type: "matrix", opt: true }] },
  // 算子范数/开映射/闭图像 只需要一个矩阵（旧条目的空矩阵会把引擎搞崩，现在会明确报错）
  "算子范数": { fn: "operator_norm", module: "fa", args: [{ key: "A", type: "matrix", opt: true }] },
  "开映射定理": { fn: "open_mapping", module: "fa", args: [{ key: "A", type: "matrix", opt: true }] },
  "闭图像定理": { fn: "closed_graph", module: "fa", args: [{ key: "A", type: "matrix", opt: true }] },
  "特征值问题": { fn: "spectrum_classify", module: "fa", args: [{ key: "A", type: "matrix", opt: false }, { key: "tol", type: "double", opt: true }] },

  /* ════════ 泛函分析（本轮补齐的 6 个）════════ */
  "谱半径": { fn: "spectral_radius", module: "fa", args: [{ key: "A", type: "matrix", opt: true }] },
  "共轭算子": { fn: "adjoint_operator", module: "fa", args: [{ key: "A", type: "matrix", opt: true }] },
  "自伴算子判定": { fn: "is_self_adjoint", module: "fa", args: [{ key: "A", type: "matrix", opt: true }] },
  "紧算子": { fn: "is_compact_operator", module: "fa", args: [{ key: "A", type: "matrix", opt: true }] },
  "Fredholm二择一": { fn: "fredholm_alternative", module: "fa", args: [{ key: "A", type: "matrix", opt: true }, { key: "b", type: "vec", opt: true }] },
  "Riesz表示定理": { fn: "riesz_representation", module: "fa", args: [{ key: "x", type: "double_array", opt: true }] },

  /* ════════ 数列（本轮补齐的 3 个）════════ */
  "数列求积": { fn: "product_sequence", module: "calculus", args: [VAR_X, { key: "a", type: "int", opt: true }, { key: "b", type: "int", opt: true }, EXPR] },
  "无穷乘积": { fn: "infinite_product", module: "calculus", args: [VAR_X, EXPR] },
  "级数绝对收敛": { fn: "absolute_convergence", module: "calculus", args: [VAR_X, EXPR] },

  /* ════════ 本轮补齐的微积分/复分析模式（引擎 extras/analysis.cpp）════════ */
  "凹凸性": { fn: "calc_concavity", module: "calculus", args: [VAR_X, A_OPT, B_OPT, EXPR] },
  "拐点": { fn: "calc_inflection", module: "calculus", args: [VAR_X, A_OPT, B_OPT, EXPR] },
  "渐近线": { fn: "calc_asymptotes", module: "calculus", args: [VAR_X, EXPR] },
  "曲率": { fn: "calc_curvature", module: "calculus", args: [VAR_X, { key: "point", type: "double", opt: true }, EXPR] },
  "曲率半径": { fn: "calc_curvature", module: "calculus", args: [VAR_X, { key: "point", type: "double", opt: true }, EXPR] },
  "Cauchy中值定理": { fn: "calc_cauchy_mvt", module: "calculus", args: [{ key: "g_expr", type: "string", opt: true }, VAR_X, A_OPT, B_OPT, EXPR] },
  "一阶ODE": { fn: "ode_first_order", module: "calculus", args: [{ key: "f", type: "string", opt: false }, { key: "var", type: "string", opt: true }, { key: "yvar", type: "string", opt: true }] },
  "高阶ODE": { fn: "ode_constant_coefficients", module: "calculus", args: [{ key: "coeffs", type: "double_array", opt: true }] },
  "ODE系统": { fn: "ode_linear_system", module: "calculus", args: [{ key: "A", type: "matrix", opt: true }] },
  "一阶PDE": { fn: "first_order_linear_pde", module: "calculus", args: [{ key: "a", type: "double", opt: false }, { key: "b", type: "double", opt: false }, { key: "c", type: "double", opt: true }] },
  "二阶PDE": { fn: "classify_second_order_pde", module: "calculus", args: [{ key: "A", type: "double", opt: false }, { key: "B", type: "double", opt: false }, { key: "C", type: "double", opt: false }] },
  "零点与极点": { fn: "zeros_and_poles", module: "complex_analysis", args: [EXPR, { key: "center", type: "point", opt: true }, { key: "radius", type: "double", opt: true }] },

  /* ════════ 线性代数 ════════ */
  "求解方程组": { fn: "lin_solve_linear_system", module: "linear_algebra", args: [{ key: "A", type: "matrix", opt: false }, { key: "b", type: "vec", opt: true }] },
  // 注意：视图里原名「正交性」在泛函分析与线性代数各有一个（含义不同），
  // 而 ENGINE_MAP 以模式名为键，只能映射一个 —— 线性代数侧改名为「向量正交性」。
  "向量正交性": { fn: "lin_is_orthogonal", module: "linear_algebra", args: [{ key: "u", type: "vec", opt: false }, { key: "v", type: "vec", opt: false }] },
  "施密特正交化": { fn: "lin_gram_schmidt", module: "linear_algebra", args: [{ key: "vectors", type: "matrix", opt: false }] },

  /* ════════ 测度论 ════════ */
  "测度性质": { fn: "measure_properties", module: "measure_theory", args: [] },
  // 区间一律用 [a,b]（E 作为字符串会被引擎当成"集合名"，写 "[0,1]" 以前静默返回 0）
  "勒贝格测度": { fn: "lebesgue_measure", module: "measure_theory", args: [{ key: "E", type: "vec", opt: true }] },
  "外测度": { fn: "outer_measure", module: "measure_theory", args: [{ key: "E", type: "vec", opt: true }, { key: "epsilon", type: "double", opt: true }] },
  "Caratheodory可测": { fn: "caratheodory_measurable", module: "measure_theory", args: [{ key: "E", type: "vec", opt: true }] },
  "乘积测度": { fn: "product_measure", module: "measure_theory", args: [{ key: "A", type: "vec", opt: true }, { key: "B", type: "vec", opt: true }] },
  "期望(测度论)": { fn: "meas_expectation", module: "measure_theory", args: [{ key: "X", type: "string", opt: true }, { key: "P", type: "string", opt: true }] },

  /* ════════ 概率 ════════ */
  // 期望：样本期望（E(X) 由数据给出）；分布期望走对应的分布模式
  "期望": { fn: "prob_expectation", module: "probability", args: [{ key: "data", type: "double_array", opt: false }] },

  /* ════════ 数列 ════════ */
  "等差数列第n项": { fn: "arithmetic_sequence", module: "algebra", args: [{ key: "a1", type: "double", opt: true }, { key: "d", type: "double", opt: true }, { key: "n", type: "int", opt: true }] },
  "等比数列第n项": { fn: "geometric_sequence", module: "algebra", args: [{ key: "a1", type: "double", opt: true }, { key: "q", type: "double", opt: true }, { key: "n", type: "int", opt: true }] },
  "数列求和": { fn: "series_sum", module: "calculus", args: [VAR_X, { key: "a", type: "string_or_number", opt: true }, { key: "b", type: "string_or_number", opt: true }, EXPR] },
  "无穷级数求和": { fn: "series_sum", module: "calculus", args: [VAR_X, EXPR] },
  "级数收敛判定": { fn: "series_convergence", module: "calculus", args: [VAR_X, EXPR] },

  /* ════════ 修正已有条目 ════════ */
  // 协方差/相关系数：旧条目一个参数都没声明（引擎要 X、Y 两个样本数组）→ 实际收到空参数
  "协方差": { fn: "covariance", module: "probability", args: [{ key: "X", type: "double_array", opt: true }, { key: "Y", type: "double_array", opt: true }] },
  "相关系数": { fn: "correlation_coefficient", module: "probability", args: [{ key: "X", type: "double_array", opt: true }, { key: "Y", type: "double_array", opt: true }] },
  // 检验类：把"必填参数"放在声明前面，输入框第一段才会落到它们身上
  "z检验": { fn: "z_test", module: "probability", args: [{ key: "sample_mean", type: "double", opt: true }, { key: "mu0", type: "double", opt: true }, { key: "sigma", type: "double", opt: true }, { key: "n", type: "int", opt: true }, { key: "alpha", type: "double", opt: true }, { key: "alternative", type: "string", opt: true }] },
  "t检验": { fn: "t_test", module: "probability", args: [{ key: "data", type: "double_array", opt: true }, { key: "mu0", type: "double", opt: true }, { key: "alpha", type: "double", opt: true }, { key: "alternative", type: "string", opt: true }] },
  "p值": { fn: "p_value", module: "probability", args: [{ key: "test_statistic", type: "double", opt: true }, { key: "dist", type: "string", opt: true }, { key: "df", type: "int", opt: true }, { key: "alternative", type: "string", opt: true }] },
  "Mann-Whitney U": { fn: "mann_whitney_u", module: "probability", args: [{ key: "group1", type: "double_array", opt: true }, { key: "group2", type: "double_array", opt: true }, { key: "alternative", type: "string", opt: true }, { key: "alpha", type: "double", opt: true }] },
  // Fubini：引擎要 range = [xa,xb,ya,yb]，旧条目完全没声明
  "Fubini定理": { fn: "fubini_theorem", module: "measure_theory", args: [{ key: "f", type: "string", opt: true }, { key: "range", type: "double_array", opt: true }] },
  // 条件期望：X（取值规则）、Omega（样本空间）、sub_sigma_algebra（引擎接受 "parity" 这类名字）
  "条件期望": { fn: "conditional_expectation", module: "measure_theory", args: [{ key: "X", type: "string", opt: true }, { key: "Omega", type: "int_array", opt: true }, { key: "sub_sigma_algebra", type: "string", opt: true }] },
  // 乘积测度：前两个是"测度"（数字或字符串 lebesgue），后两个是区间
  "乘积测度": { fn: "product_measure", module: "measure_theory", args: [{ key: "mu", type: "string_or_number", opt: true }, { key: "nu", type: "string_or_number", opt: true }, { key: "A", type: "vec", opt: true }, { key: "B", type: "vec", opt: true }] },
  // 相图：x_range/y_range 必须是 [min,max]
  "相图": { fn: "phase_portrait", module: "numerical", args: [{ key: "x_range", type: "vec", opt: true }, { key: "y_range", type: "vec", opt: true }, { key: "dx_dt", type: "string", opt: true }, { key: "dy_dt", type: "string", opt: true }, { key: "n_trajectories", type: "int", opt: true }, { key: "resolution", type: "int", opt: true }] },
  // 反傅里叶变换：引擎把被变换的函数当作 ξ 的函数（这是它内部的符号约定）
  "逆Fourier变换": { fn: "inverse_fourier_transform", module: "harmonic_analysis", args: [{ key: "F", type: "string", opt: true }, { key: "use_angular", type: "bool", opt: true }] },
  // 数值积分/求导这几条旧条目的参数顺序是 [n?, f, a, b] —— 可选参数声明在前，
  // 于是输入框的第一个数被当成子区间数 n，函数名反而拿不到（实测 "表达式后存在多余字符"）。
  // 统一改成自然顺序：先函数、再区间、最后细分数。
  "梯形法则": { fn: "trapezoidal_rule", module: "numerical", args: [{ key: "f", type: "string", opt: false }, { key: "a", type: "double", opt: true }, { key: "b", type: "double", opt: true }, { key: "n", type: "int", opt: true }] },
  "辛普森法则": { fn: "simpson_rule", module: "numerical", args: [{ key: "f", type: "string", opt: false }, { key: "a", type: "double", opt: true }, { key: "b", type: "double", opt: true }, { key: "n", type: "int", opt: true }] },
  "高斯求积": { fn: "gauss_quadrature", module: "numerical", args: [{ key: "f", type: "string", opt: false }, { key: "a", type: "double", opt: true }, { key: "b", type: "double", opt: true }, { key: "n", type: "int", opt: true }] },
  "数值求导": { fn: "numerical_derivative", module: "numerical", args: [{ key: "f", type: "string", opt: false }, { key: "x", type: "double", opt: true }, { key: "h", type: "double", opt: true }, { key: "method", type: "string", opt: true }] },
  "最优步长": { fn: "optimal_step", module: "numerical", args: [{ key: "f", type: "string", opt: false }, { key: "x", type: "double", opt: true }, { key: "method", type: "string", opt: true }] },
  "欧拉方法": { fn: "euler_method", module: "numerical", args: [{ key: "f", type: "string", opt: false }, { key: "t0", type: "double", opt: true }, { key: "y0", type: "double", opt: true }, { key: "t_end", type: "double", opt: true }, { key: "h", type: "double", opt: true }] },
  "RK4": { fn: "rk4", module: "numerical", args: [{ key: "f", type: "string", opt: false }, { key: "t0", type: "double", opt: true }, { key: "y0", type: "double", opt: true }, { key: "t_end", type: "double", opt: true }, { key: "h", type: "double", opt: true }] },
  "隐式欧拉": { fn: "implicit_euler", module: "numerical", args: [{ key: "f", type: "string", opt: false }, { key: "t0", type: "double", opt: true }, { key: "y0", type: "double", opt: true }, { key: "t_end", type: "double", opt: true }, { key: "h", type: "double", opt: true }] },
  "刚性检测": { fn: "stiff_detector", module: "numerical", args: [{ key: "f", type: "string", opt: false }, { key: "t0", type: "double", opt: true }, { key: "y0", type: "double", opt: true }, { key: "t_end", type: "double", opt: true }] },
  "梯度下降": { fn: "gradient_descent", module: "numerical", args: [{ key: "f", type: "string", opt: false }, { key: "x0", type: "double", opt: true }, { key: "learning_rate", type: "double", opt: true }, { key: "max_iter", type: "int", opt: true }] },
  // 点云参数：引擎要 [[x,y],…]，旧条目声明的类型前端不认识 → 当成字符串发过去
  "过滤复形": { fn: "filtration", module: "at", args: [{ key: "point_cloud", type: "point_cloud", opt: true }, { key: "max_scale", type: "double", opt: true }, { key: "max_dim", type: "int", opt: true }] },
  "持续同调图": { fn: "persistence_diagram", module: "at", args: [{ key: "point_cloud", type: "point_cloud", opt: true }, { key: "dim", type: "int", opt: true }, { key: "max_scale", type: "double", opt: true }, { key: "significance", type: "double", opt: true }] },
  "条形码": { fn: "barcode_plot", module: "at", args: [{ key: "point_cloud", type: "point_cloud", opt: true }, { key: "dim", type: "int", opt: true }, { key: "max_scale", type: "double", opt: true }] },
  // 代数拓扑这几个都支持**已知空间名**（T2/RP2/K/S1/S2/S3），比让用户手写复形对象实用得多
  "同调群": { fn: "homology_group", module: "at", args: [{ key: "space", type: "string", opt: true }, { key: "n", type: "int", opt: true }] },
  // betti_numbers 只接受复形对象（不像同调群那样支持空间名）
  "贝蒂数": { fn: "betti_numbers", module: "at", args: [{ key: "complex", type: "complex_obj", opt: true }, { key: "max_dim", type: "int", opt: true }] },
  "欧拉示性数": { fn: "euler_characteristic", module: "at", args: [{ key: "space", type: "string", opt: true }] },
  "上同调群": { fn: "cohomology_group", module: "at", args: [{ key: "space", type: "string", opt: true }, { key: "n", type: "int", opt: true }] },
  "庞加莱对偶": { fn: "poincare_duality", module: "at", args: [{ key: "manifold", type: "string", opt: true }, { key: "k", type: "int", opt: true }] },
  // simplices：单形列表，写成 [[0,1,2],[0,1,3]]（每个内层是一组顶点编号）
  "单纯复形": { fn: "simplicial_complex", module: "at", args: [{ key: "simplices", type: "matrix", opt: true }, { key: "maximal", type: "bool", opt: true }] },
  // 概率：条件概率/全概率/贝叶斯要的是"带键名的对象"，用 `键=值; 键=值` 写法
  "条件概率": { fn: "conditional_probability", module: "probability", args: [{ key: "P", type: "prob_table", opt: true }, { key: "A", type: "string", opt: true }, { key: "B", type: "string", opt: true }] },
  "独立性": { fn: "is_independent", module: "probability", args: [{ key: "P", type: "prob_table", opt: true }, { key: "A", type: "string", opt: true }, { key: "B", type: "string", opt: true }] },
  // events 是**对象**（事件名→概率），不是名字数组；P 里放 "B|Ai" 这样的条件概率
  "全概率公式": { fn: "total_probability", module: "probability", args: [{ key: "events", type: "prob_table", opt: true }, { key: "P", type: "prob_table", opt: true }, { key: "condition", type: "string", opt: true }] },
  "贝叶斯公式": { fn: "bayes_theorem", module: "probability", args: [{ key: "events", type: "prob_table", opt: true }, { key: "P", type: "prob_table", opt: true }, { key: "evidence", type: "string", opt: true }] },
  // 参数顺序修正：可选参数声明在前的模式，输入框的第一个值会被可选参数吃掉
  "二次型": { fn: "quadratic_form", module: "linear_algebra", args: [{ key: "matrix", type: "matrix", opt: true }, { key: "x", type: "string", opt: true }] },
  "矩阵表示": { fn: "matrix_representation", module: "linear_algebra", args: [{ key: "transform", type: "matrix", opt: true }, { key: "domain_basis", type: "matrix", opt: true }] },
  "矩估计": { fn: "moment_estimate", module: "probability", args: [{ key: "data", type: "double_array", opt: true }, { key: "dist", type: "string", opt: true }] },
  "MLE": { fn: "mle", module: "probability", args: [{ key: "data", type: "double_array", opt: true }, { key: "dist", type: "string", opt: true }] },
  "交换律验证": { fn: "commutative_law", module: "algebra", args: [{ key: "a", type: "double", opt: true }, { key: "b", type: "double", opt: true }, { key: "op", type: "string", opt: true }] },
  "结合律验证": { fn: "associative_law", module: "algebra", args: [{ key: "a", type: "double", opt: true }, { key: "b", type: "double", opt: true }, { key: "c", type: "double", opt: true }, { key: "op", type: "string", opt: true }] },
  "最小二乘拟合": { fn: "least_squares_fit", module: "numerical", args: [{ key: "x", type: "double_array", opt: true }, { key: "y", type: "double_array", opt: true }, { key: "degree", type: "int", opt: true }] },
  // 零点与极点：引擎的键名是 func（我上一轮写成 expr，引擎收不到）
  "零点与极点": { fn: "zeros_and_poles", module: "complex_analysis", args: [{ key: "func", type: "string", opt: true }, { key: "center", type: "point", opt: true }, { key: "radius", type: "double", opt: true }] },
  // 极限：旧条目漏了 point 参数，趋近值根本传不进引擎（get_string_or_number 读不到 key）
  "极限": { fn: "limit", module: "calculus", args: [VAR_X, { key: "point", type: "string_or_number", opt: true }, { key: "direction", type: "string", opt: true }, EXPR] },
  // 复指数/复数运算读的是 z（复数：数字 / [re,im] / "a±bi"），旧条目一个参数都没声明
  // ⚠ 注意 ENGINE_MAP = {...RAW_MAP, ...EXTRA_MAP}，**这里会覆盖 engineMap.js 里的同名条目**。
// 之前这里把「复数运算」固定成 exp_complex，于是输入 1+2i 会静默算成 e^(1+2i)（错答案）；
// 而且参数写成 type:"point" 时，1+2i 这种写法在转"点"时就失败了（报"无法解析为复数"）。
// 现在改成 complex_eval：它就是对复表达式求值，与"复数运算"这个名字相符，
// 并把参数声明成字符串 expr（引擎侧已能让它认小写 i / j）。
"复数运算": { fn: "complex_eval", module: "complex_analysis", args: [{ key: "expr", type: "string", opt: false }] },
  "复指数": { fn: "exp_complex", module: "complex_analysis", args: [{ key: "z", type: "point", opt: true }] },
  // 留数需要展开点 z0
  "留数": { fn: "residue", module: "complex_analysis", args: [{ key: "z0", type: "point", opt: true }, { key: "func", type: "string", opt: false }] },
};

/** 新增/覆盖的弹窗字段。第一个字段是输入框占位（用「（输入框）」显式标注）。 */
export const EXTRA_VAR_SPECS = {
  "高阶导数": [["函数（输入框）", ""], ["求导变量", "x"], ["阶数（>=2）", "2"]],
  "偏导": [["函数（输入框）", ""], ["对哪个变量求偏导", "y"], ["阶数", "1"]],
  "定积分": [["被积函数（输入框）", ""], ["积分变量", "x"], ["下限", "0"], ["上限", "1"]],
  "广义积分": [["被积函数（输入框）", ""], ["积分变量", "x"], ["下限", "0"], ["上限", "oo"]],
  "重积分": [["被积函数（输入框）", ""], ["积分变量 x", "x"], ["积分变量 y", "y"], ["x 下限", "0"], ["x 上限", "1"], ["y 下限", "0"], ["y 上限", "1"]],
  "单侧极限": [["函数（输入框）", ""], ["自变量", "x"], ["趋近值", "0"], ["方向（left/right）", "right"]],
  "无穷极限": [["函数（输入框）", ""], ["自变量", "x"], ["趋近值", "oo"]],
  "连续性判定": [["函数（输入框）", ""], ["自变量", "x"], ["判定点", "0"]],
  "幂级数": [["函数（输入框）", ""], ["自变量", "x"], ["展开点", "0"], ["阶数", "6"]],
  // 覆盖旧字段：旧字段里「变量」正好命中 isSkippedField 的等值规则而被丢掉，
  // 后面的字段就整体错位（展开点被当成 var）。字段顺序必须与 args 里可选参数顺序一致。
  "级数展开": [["函数（输入框）", ""], ["自变量", "x"], ["展开点", "0"], ["阶数", "6"]],
  "极限": [["函数（输入框）", ""], ["自变量", "x"], ["趋近值", "0"], ["方向（left/right，留空为两侧）", ""]],
  "最值": [["函数（输入框）", ""], ["自变量", "x"], ["区间左端", "-1"], ["区间右端", "1"]],
  "平均值": [["函数（输入框）", ""], ["区间左端", "0"], ["区间右端", "1"]],
  "旋转体体积(圆盘)": [["函数（输入框）", ""], ["自变量", "x"], ["区间左端", "0"], ["区间右端", "1"]],
  "旋转体体积(壳)": [["函数（输入框）", ""], ["自变量", "x"], ["区间左端", "0"], ["区间右端", "1"]],
  "Rolle定理": [["函数（输入框）", ""], ["自变量", "x"], ["区间左端", "0"], ["区间右端", "1"]],
  "Lagrange中值定理": [["函数（输入框）", ""], ["自变量", "x"], ["区间左端", "0"], ["区间右端", "1"]],
  // RK4：旧字段里「步数」不是引擎参数（引擎用终点 x），且首字段标签没被跳过 → 这里重写
  "ODE数值解": [["微分方程 dy/dx =（输入框）", ""], ["初始 x₀", "0"], ["初始 y₀", "1"], ["终点 x", "1"], ["步长 h", "0.1"]],
  "Cauchy积分": [["被积函数（输入框）", ""], ["围道 circle(中心, 半径)", "circle(0+0i,2)"], ["解析点 a", "0+0i"], ["采样点数", "1000"]],
  "围道积分": [["被积函数（输入框）", ""], ["围道 circle(中心, 半径)", "circle(0+0i,1)"], ["采样点数", "1000"]],
  "全纯判定": [["函数（输入框）", ""], ["判定点 z（如 1+1i 或 0,1）", "0,0"]],
  "Laurent级数": [["函数（输入框）", ""], ["展开中心 z0（如 0+0i）", "0,0"], ["展开项数", "4"]],
  "共形映射": [["区域（unit_disk / upper_half_plane / right_half_plane / slit_disk / first_quadrant）（输入框）", "upper_half_plane"]],
  "Banach空间": [["空间名（输入框）", "R^n"], ["维数", "3"]],
  "Hilbert空间": [["空间名（输入框）", "R^n"], ["维数", "3"]],
  "内积空间": [["第一个函数（输入框）", ""], ["第二个函数", "x"], ["区间 a,b", "-1,1"], ["采样点数", "1000"]],
  "正交性": [["第一个函数（输入框）", ""], ["第二个函数", "x"], ["区间 a,b", "-1,1"]],
  "弱*收敛": [["收敛序列（每行一个向量）（输入框）", "[[1,0],[0.5,0],[0.1,0]]"], ["泛函（如 1,0）", "1,0"], ["弱极限", "0,0"], ["容差", "1e-9"]],
  "弱收敛": [["收敛序列（每行一个向量）（输入框）", "[[1,0],[0.5,0],[0.1,0]]"], ["泛函（如 1,0）", "1,0"], ["弱极限", "0,0"], ["容差", "1e-9"]],
  "一致有界原理": [["算子族（每个算子一个矩阵）（输入框）", "[[[1,2],[3,4]],[[1,0],[0,1]]]"], ["测试点（每行一个向量）", "1,0"]],
  "算子范数": [["矩阵（输入框）", "[[1,2],[3,4]]"]],
  "开映射定理": [["矩阵（输入框）", "[[1,2],[3,4]]"]],
  "闭图像定理": [["矩阵（输入框）", "[[1,2],[3,4]]"]],
  "椭圆方程": [["长半轴 a（输入框）", "3"], ["短半轴 b", "2"]],
  "双曲线方程": [["实半轴 a（输入框）", "3"], ["虚半轴 b", "4"]],
  "抛物线方程": [["焦准距 p（输入框）", "2"], ["对称轴（x 或 y）", "x"]],
  "Riemann ζ": [["s（可为 2、0.5、1+14i）（输入框）", "2"], ["级数项数", "2000"]],
  "Dirichlet η": [["s（输入框）", "2"]],
  "谱半径": [["矩阵（输入框）", "[[2,0],[0,3]]"]],
  "共轭算子": [["矩阵（输入框）", "[[1,2],[3,4]]"]],
  "自伴算子判定": [["矩阵（输入框）", "[[2,1],[1,3]]"]],
  "紧算子": [["矩阵（输入框）", "[[1,2],[3,4]]"]],
  "Fredholm二择一": [["矩阵 A（输入框）", "[[1,2],[3,4]]"], ["右端向量 b（可留空）", "5,11"]],
  "Riesz表示定理": [["向量 x（输入框）", "3,4"]],
  "数列求积": [["通项 aₖ（输入框）", "k"], ["指标变量", "k"], ["起始项", "1"], ["结束项", "5"]],
  "无穷乘积": [["通项 aₖ（输入框）", "1+1/k^2"], ["指标变量", "k"]],
  "级数绝对收敛": [["通项 aₙ（输入框）", "1/k^2"], ["指标变量", "n"]],
  "凹凸性": [["函数（输入框）", ""], ["自变量", "x"], ["区间左端", "-3"], ["区间右端", "3"]],
  "拐点": [["函数（输入框）", ""], ["自变量", "x"], ["区间左端", "-3"], ["区间右端", "3"]],
  "渐近线": [["函数（输入框）", ""], ["自变量", "x"]],
  "曲率": [["函数（输入框）", ""], ["自变量", "x"], ["求曲率的点", "1"]],
  "曲率半径": [["函数（输入框）", ""], ["自变量", "x"], ["求曲率的点", "1"]],
  "Cauchy中值定理": [["f(x)（输入框）", ""], ["g(x)", "x^3"], ["自变量", "x"], ["区间左端", "0"], ["区间右端", "1"]],
  "一阶ODE": [["微分方程 dy/dx =（输入框）", ""], ["自变量", "x"], ["未知函数", "y"]],
  "高阶ODE": [["系数（从 y 到最高阶，逗号分隔）（输入框）", "1,0,1"]],
  "ODE系统": [["系数矩阵 A（输入框）", "[[0,1],[-1,0]]"]],
  "一阶PDE": [["系数 a（输入框）", "1"], ["系数 b", "1"], ["右端 c（缺省 0）", "0"]],
  "二阶PDE": [["A（输入框）", "1"], ["B", "0"], ["C", "1"]],
  "零点与极点": [["复函数 f(z)（输入框）", "(z^2-1)/(z-2)"], ["圆心（如 0,0）", "0,0"], ["半径", "3"]],
  "梯形法则": [["被积函数（输入框）", ""], ["下限", "0"], ["上限", "1"], ["子区间数", "100"]],
  "辛普森法则": [["被积函数（输入框）", ""], ["下限", "0"], ["上限", "1"], ["子区间数", "100"]],
  "高斯求积": [["被积函数（输入框）", ""], ["下限", "0"], ["上限", "1"], ["节点数", "5"]],
  "数值求导": [["函数（输入框）", ""], ["求导点", "1"], ["步长", "1e-6"], ["方法（forward/backward/central）", "central"]],
  "最优步长": [["函数（输入框）", ""], ["求导点", "1"], ["方法（forward/backward/central）", "central"]],
  "欧拉方法": [["微分方程 dy/dx =（输入框）", ""], ["初始 x₀", "0"], ["初始 y₀", "1"], ["终点 x", "1"], ["步长 h", "0.1"]],
  "RK4": [["微分方程 dy/dx =（输入框）", ""], ["初始 x₀", "0"], ["初始 y₀", "1"], ["终点 x", "1"], ["步长 h", "0.1"]],
  "隐式欧拉": [["微分方程 dy/dx =（输入框）", ""], ["初始 x₀", "0"], ["初始 y₀", "1"], ["终点 x", "1"], ["步长 h", "0.1"]],
  "刚性检测": [["微分方程 dy/dx =（输入框）", ""], ["初始 x₀", "0"], ["初始 y₀", "1"], ["终点 x", "1"]],
  "梯度下降": [["目标函数（输入框）", ""], ["初始点", "0"], ["学习率", "0.01"], ["迭代次数", "100"]],
  "过滤复形": [["点云（写成 [[0,0],[1,0],…]）（输入框）", "[[0,0],[1,0],[0,1],[1,1]]"], ["最大尺度", "2"], ["最高维数", "2"]],
  "持续同调图": [["点云（写成 [[0,0],[1,0],…]）（输入框）", "[[0,0],[1,0],[0,1],[1,1]]"], ["维数", "1"], ["最大尺度", "2"], ["显著性阈值", "0.01"]],
  "条形码": [["点云（写成 [[0,0],[1,0],…]）（输入框）", "[[0,0],[1,0],[0,1],[1,1]]"], ["维数", "1"], ["最大尺度", "2"]],
  "单纯复形": [["单形列表（写成 [[0,1,2],[0,1,3]]）（输入框）", "[[0,1,2],[0,1,3]]"], ["只保留极大单形", "true"]],
  "同调群": [["空间名（T2/RP2/K/S1/S2/S3）（输入框）", "T2"], ["维数 n", "1"]],
  "上同调群": [["空间名（T2/RP2/K/S1/S2/S3）（输入框）", "T2"], ["维数 n", "1"]],
  "欧拉示性数": [["空间名（T2/RP2/K/S1/S2/S3）（输入框）", "T2"]],
  "贝蒂数": [["最高维数（输入框）", "3"]],
  "协方差": [["样本 X（输入框）", "1,2,3,4,5"], ["样本 Y", "2,4,5,4,6"]],
  "相关系数": [["样本 X（输入框）", "1,2,3,4,5"], ["样本 Y", "2,4,5,4,6"]],
  "z检验": [["样本均值（输入框）", "3.2"], ["原假设均值 μ₀", "3"], ["总体标准差 σ", "1"], ["样本量 n", "25"], ["显著性水平 α", "0.05"], ["备择假设（two-sided/less/greater）", "two-sided"]],
  "t检验": [["样本数据（输入框）", "1,2,3,4,5"], ["原假设均值 μ₀", "3"], ["显著性水平 α", "0.05"], ["备择假设", "two-sided"]],
  "p值": [["检验统计量（输入框）", "1.96"], ["分布（normal/t/chi2）", "normal"], ["自由度 df", "1"], ["备择假设", "two-sided"]],
  "Mann-Whitney U": [["第一组数据（输入框）", "1,2,3"], ["第二组数据", "4,5,6"], ["备择假设", "two-sided"], ["显著性水平 α", "0.05"]],
  "Fubini定理": [["被积函数（输入框）", "x*y"], ["区域 [xa,xb,ya,yb]", "0,1,0,1"]],
  "条件期望": [["X 的取值规则（输入框）", "x"], ["样本空间 Ω（如 1,2,3,4）", "1,2,3,4"], ["子 σ-代数（如 parity）", "parity"]],
  "乘积测度": [["第一个测度（数字或 lebesgue）（输入框）", "lebesgue"], ["第二个测度", "lebesgue"], ["第一个区间 [a,b]", "[0,1]"], ["第二个区间 [a,b]", "[0,2]"]],
  "相图": [["x 范围 [min,max]（输入框）", "[-1,1]"], ["y 范围 [min,max]", "[-1,1]"], ["dx/dt", "-y"], ["dy/dt", "x"], ["轨迹条数", "9"], ["网格分辨率", "21"]],
  "逆Fourier变换": [["F(ξ)（输入框，引擎用 ξ 作变换变量）", "exp(-xi^2)"], ["使用角频率", "true"]],
  "贝蒂数（复形）": [["复形（写成 2:0,1,2|1:0,1|0:0,1,2）（输入框）", "2:0,1,2|1:0,1|0:0,1,2"], ["最高维数", "3"]],
  "庞加莱对偶": [["流形（S1/S2/S3/T2/RP2/K）（输入框）", "T2"], ["k", "1"]],
  "条件概率": [["概率表 P（键=值; 键=值）（输入框）", "A_and_B=0.2; B=0.5"], ["事件 A", "A"], ["事件 B", "B"]],
  "独立性": [["概率表 P（键=值; 键=值）（输入框）", "A_and_B=0.12; A=0.3; B=0.4"], ["事件 A", "A"], ["事件 B", "B"]],
  "全概率公式": [["概率表 P（键=值; 键=值）（输入框）", "A1=0.5; A2=0.5; B|A1=0.1; B|A2=0.2"], ["完备事件组（逗号分隔）", "A1,A2"], ["条件 B", "B"]],
  "贝叶斯公式": [["概率表 P（键=值; 键=值）（输入框）", "A1=0.5; A2=0.5; B|A1=0.1; B|A2=0.2"], ["完备事件组（逗号分隔）", "A1,A2"], ["已发生的事件", "B"]],
  "二次型": [["矩阵（输入框）", "[[1,2],[3,4]]"]],
  "矩阵表示": [["变换矩阵（输入框）", "[[1,0],[0,1]]"], ["定义域基", "[[1,0],[0,1]]"]],
  "矩估计": [["样本数据（输入框）", "1,2,3,4,5"], ["分布（normal/exponential/…）", "normal"]],
  "MLE": [["样本数据（输入框）", "1,2,3,4,5"], ["分布（normal/exponential/…）", "normal"]],
  "交换律验证": [["a（输入框）", "2"], ["b", "3"], ["运算符（+ 或 *）", "+"]],
  "结合律验证": [["a（输入框）", "1"], ["b", "2"], ["c", "3"], ["运算符（+ 或 *）", "+"]],
  "最小二乘拟合": [["数据点 x（输入框）", "0,1,2,3"], ["数据点 y", "1,3,5,7"], ["拟合次数", "2"]],
  "Hahn-Banach定理": [["初始泛函系数（输入框）", "1,1"], ["子空间维数", "1"], ["外围空间维数", "2"]],
  "期望(测度论)": [["随机变量取值规则（输入框）", "x"], ["分布（uniform / normal(0,1) / …）", "uniform"]],
  "等差数列第n项": [["首项 a₁（输入框）", "1"], ["公差 d", "1"], ["项数 n", "10"]],
  "等比数列第n项": [["首项 a₁（输入框）", "1"], ["公比 q", "2"], ["项数 n", "10"]],
  "数列求和": [["通项 aₙ（输入框）", ""], ["指标变量", "n"], ["起始项", "1"], ["结束项", "10"]],
  "无穷级数求和": [["通项 aₙ（输入框）", ""], ["指标变量", "n"]],
  "求解方程组": [["系数矩阵 A（输入框）", "[[1,2],[3,4]]"], ["右端向量 b", "5,11"]],
  "线性算子": [["矩阵（输入框）", "[[1,2],[3,4]]"], ["向量", "1,1"]],
  "Lp范数": [["向量（输入框）", "3,4"]],
  "期望": [["样本数据（输入框）", "1,2,3,4"]],
  "Fourier级数": [["函数（输入框）", ""], ["项数", "5"], ["周期", "6.283185307179586"]],
  "Fourier系数": [["函数（输入框）", ""], ["项号 n", "1"], ["周期", "6.283185307179586"], ["系数类型（a/b）", "a"]],
  "复Fourier系数": [["函数（输入框）", ""], ["项号 n", "1"], ["周期", "6.283185307179586"]],
  "Laurent级数": [["函数（输入框）", ""], ["展开项数", "4"]],
  // 高斯消元：旧字段把「未知数个数」塞给了 b（引擎的 b 是右端向量），会算出不同的问题
  "高斯消元": [["增广矩阵（输入框）", "[[1,2,5],[3,4,11]]"]],
};
