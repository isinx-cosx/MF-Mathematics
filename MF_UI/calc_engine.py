# -*- coding: utf-8 -*-
"""计算调度器 — 统一的 calc_block → dispatch 中间层。

所有 calc_block 通过 calculate() / calculate_direct() 调用后端，
确保 FUNC_MAP 是唯一的模式→(module, action) 映射入口。

用法:
    from calc_engine import calculate, calculate_direct

    # 代数模式：字符串参数
    result = calculate("求导", ["sin(x)", "x", "1"])

    # 矩阵/数值模式：已解析的 Python 对象
    result = calculate_direct("高斯消元", matrix=[[1,2],[3,4]])
"""

from __future__ import annotations

import sys, os
from ast import literal_eval as _le

_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _base not in sys.path:
    sys.path.insert(0, _base)

# ── 核心导入（无需延迟） ─────────────────────────────────────
from MF_Mathematics.core.registry import dispatch
from MF_Mathematics.core.math_object import MathObject

# ── 延迟导入数学子包（仅在首次使用时加载） ────────────────────
_MODULES: dict[str, object] = {}

def _ensure_module(name: str) -> None:
    """确保指定数学子包已导入（触发 @register 装饰器）。"""
    if name not in _MODULES:
        _MODULES[name] = __import__(
            f"MF_Mathematics.{name}", fromlist=[name]
        )


# ═══════════════════════════════════════════════════════════════════════
#  FUNC_MAP — 全模式映射（唯一真源）
# ═══════════════════════════════════════════════════════════════════════

FUNC_MAP: dict[str, tuple[str, str]] = {
    # ── 代数 ──
    "化简":           ("algebra", "simplify_polynomial"),
    "展开":           ("algebra", "expand_expression"),
    "因式分解":       ("algebra", "factor"),
    "解方程":         ("algebra", "solve_linear"),
    "解方程组":       ("algebra", "solve_linear_system"),
    "解一元二次":     ("algebra", "solve_quadratic"),
    "判别式":         ("algebra", "discriminant"),
    "韦达定理":       ("algebra", "vieta_theorem"),
    "解分式方程":     ("algebra", "solve_fractional"),
    "解无理方程":     ("algebra", "solve_irrational"),
    "解线性不等式":   ("algebra", "solve_linear_inequality"),
    "解不等式组":     ("algebra", "solve_inequality_system"),
    "解二次不等式":   ("algebra", "solve_quadratic_inequality"),
    "AM-GM不等式":    ("algebra", "am_gm_inequality"),
    "表达式化简":     ("algebra", "simplify_polynomial"),
    "化简分式":       ("algebra", "simplify_fraction"),
    "化简根式":       ("algebra", "simplify_radical"),

    # ── 微积分 ──
    "求导":           ("calculus", "diff"),
    "某点导数":       ("calculus", "diff_at"),
    "隐函数求导":     ("calculus", "implicit_diff"),
    "参数方程求导":   ("calculus", "parametric_diff"),
    "不定积分":       ("calculus", "integrate"),
    "定积分":         ("calculus", "integrate"),
    "数值积分":       ("calculus", "integrate_numeric"),
    "反常积分":       ("calculus", "improper_integral"),
    "极限":           ("calculus", "limit"),
    "连续性判断":     ("calculus", "is_continuous"),
    "间断点分类":     ("calculus", "discontinuity_classify"),
    "洛必达法则":     ("calculus", "lhopital"),
    "单调性":         ("calculus", "monotonicity"),
    "局部极值":       ("calculus", "local_extrema"),
    "全局最值":       ("calculus", "global_extrema"),
    "泰勒展开":       ("calculus", "taylor"),
    "幂级数展开":     ("calculus", "power_series"),
    "级数求和":       ("calculus", "series_sum"),
    "级数敛散性":     ("calculus", "series_convergence"),

    # ── 复分析 ──
    "复数运算":       ("complex_analysis", "exp_complex"),
    "复指数":         ("complex_analysis", "exp_complex"),
    "复对数":         ("complex_analysis", "log_complex"),
    "复平方根":       ("complex_analysis", "sqrt_complex"),
    "莫比乌斯变换":   ("complex_analysis", "mobius_transform"),

    # ── 线性代数 ──
    "高斯消元":       ("linear_algebra", "gaussian_elimination"),
    "矩阵秩":         ("linear_algebra", "rank"),
    "求解方程组":     ("linear_algebra", "solve_linear_system"),
    "零空间":         ("linear_algebra", "nullspace"),
    "特征值":         ("linear_algebra", "eigenvalues"),
    "特征向量":       ("linear_algebra", "eigenvectors"),
    "特征多项式":     ("linear_algebra", "characteristic_polynomial"),
    "可对角化":       ("linear_algebra", "is_diagonalizable"),
    "对角化":         ("linear_algebra", "diagonalize"),
    "点积":           ("linear_algebra", "dot"),
    "范数":           ("linear_algebra", "norm"),
    "夹角":           ("linear_algebra", "angle"),
    "正交性":         ("linear_algebra", "is_orthogonal"),
    "施密特正交化":   ("linear_algebra", "gram_schmidt"),
    "正交投影":       ("linear_algebra", "orthogonal_projection"),
    "二次型":         ("linear_algebra", "quadratic_form"),
    "正定性判定":     ("linear_algebra", "is_positive_definite"),

    # ── 概率统计 ──
    "条件概率":       ("probability", "conditional_probability"),
    "独立性":         ("probability", "is_independent"),
    "全概率公式":     ("probability", "total_probability"),
    "贝叶斯公式":     ("probability", "bayes_theorem"),
    "伯努利分布":     ("probability", "bernoulli"),
    "二项分布":       ("probability", "binomial"),
    "泊松分布":       ("probability", "poisson"),
    "均匀分布":       ("probability", "uniform"),
    "指数分布":       ("probability", "exponential"),
    "正态分布":       ("probability", "normal"),
    "期望":           ("probability", "expectation"),
    "方差":           ("probability", "variance"),
    "协方差":         ("probability", "covariance"),
    "相关系数":       ("probability", "correlation_coefficient"),
    "大数定律":       ("probability", "law_of_large_numbers"),
    "中心极限定理":   ("probability", "central_limit_theorem"),
    "样本均值":       ("probability", "sample_mean"),
    "样本方差":       ("probability", "sample_variance"),
    "矩估计":         ("probability", "moment_estimate"),
    "MLE":            ("probability", "mle"),
    "置信区间":       ("probability", "confidence_interval"),
    "z检验":          ("probability", "z_test"),
    "t检验":          ("probability", "t_test"),
    "卡方检验":       ("probability", "chi_square_test"),
    "单因素ANOVA":     ("probability", "one_way_anova"),
    "双因素ANOVA":     ("probability", "two_way_anova"),
    "移动平均":        ("probability", "moving_average"),
    "指数平滑":        ("probability", "exp_smoothing"),
    "线性趋势":        ("probability", "linear_trend"),
    "p值":            ("probability", "p_value"),
    "线性回归":       ("probability", "linear_regression"),
    "预测":           ("probability", "predict"),
    "残差":           ("probability", "residuals"),
    "Mann-Whitney U": ("probability", "mann_whitney_u"),
    "Kruskal-Wallis": ("probability", "kruskal_wallis"),
    "Wilcoxon符号秩": ("probability", "wilcoxon_signed_rank"),

    # ── 数值分析 ──
    "条件数":         ("numerical", "condition_number"),
    "截断误差":       ("numerical", "truncation_error"),
    "舍入误差":       ("numerical", "rounding_error_estimate"),
    "稳定性判断":     ("numerical", "is_stable"),
    "拉格朗日插值":   ("numerical", "lagrange_interpolation"),
    "牛顿插值":       ("numerical", "newton_interpolation"),
    "三次样条":       ("numerical", "cubic_spline"),
    "最小二乘拟合":   ("numerical", "least_squares_fit"),
    "梯形法则":       ("numerical", "trapezoidal_rule"),
    "辛普森法则":     ("numerical", "simpson_rule"),
    "高斯求积":       ("numerical", "gauss_quadrature"),
    "数值求导":       ("numerical", "numerical_derivative"),
    "最优步长":       ("numerical", "optimal_step"),
    "LU分解":         ("numerical", "lu_decomposition"),
    "雅可比迭代":     ("numerical", "jacobi_iteration"),
    "高斯-赛德尔":    ("numerical", "gauss_seidel"),
    "共轭梯度":       ("numerical", "conjugate_gradient"),
    "幂法":           ("numerical", "power_method"),
    "QR算法":         ("numerical", "qr_algorithm"),
    "欧拉方法":       ("numerical", "euler_method"),
    "RK4":            ("numerical", "rk4"),
    "隐式欧拉":       ("numerical", "implicit_euler"),
    "刚性检测":       ("numerical", "stiff_detector"),

    # ── 傅里叶分析 ──
    "傅里叶系数":             ("harmonic_analysis", "fourier_coeff"),
    "傅里叶级数":             ("harmonic_analysis", "fourier_series"),
    "复傅里叶系数":           ("harmonic_analysis", "complex_fourier_coeff"),
    "正交性验证":             ("harmonic_analysis", "orthogonality_check"),
    "傅里叶变换":             ("harmonic_analysis", "fourier_transform"),
    "逆傅里叶变换":           ("harmonic_analysis", "inverse_fourier_transform"),
    "普兰舍利定理":           ("harmonic_analysis", "plancherel_theorem"),
    "高斯函数傅里叶变换":     ("harmonic_analysis", "ft_of_gaussian"),
    "卷积":                   ("harmonic_analysis", "convolution"),
    "卷积定理":               ("harmonic_analysis", "convolution_theorem"),
    "高斯模糊":               ("harmonic_analysis", "gaussian_blur"),
    "低通滤波器":             ("harmonic_analysis", "low_pass_filter"),
    "δ 分布":                 ("harmonic_analysis", "delta_distribution"),
    "δ 的傅里叶变换":         ("harmonic_analysis", "ft_delta"),
    "常数的傅里叶变换":       ("harmonic_analysis", "ft_constant"),
    "缓增分布":               ("harmonic_analysis", "tempered_distribution"),
    "不确定性原理":           ("harmonic_analysis", "uncertainty_principle"),
    "短时傅里叶变换":         ("harmonic_analysis", "stft"),
    "小波变换":               ("harmonic_analysis", "wavelet_transform"),
    "泊松求和":               ("harmonic_analysis", "poisson_summation"),
    "Theta 函数":             ("harmonic_analysis", "theta_function"),
    "函数方程演示":           ("harmonic_analysis", "functional_equation_demo"),

    # ── 微积分应用 ──
    "微分":                   ("calculus", "differential"),
    "罗尔定理":               ("calculus", "rolle_theorem"),
    "拉格朗日中值定理":       ("calculus", "lagrange_theorem"),
    "曲线间面积":             ("calculus", "area_between"),
    "旋转体体积(圆盘法)":     ("calculus", "volume_disk"),
    "旋转体体积(柱壳法)":     ("calculus", "volume_shell"),
    "弧长":                   ("calculus", "arc_length"),
    "幂级数收敛半径":         ("calculus", "power_series_radius"),
    "莱布尼茨判别法":         ("calculus", "leibniz_test"),
    "极限比较判别法":         ("calculus", "limit_comparison_test"),
    "积分判别法":             ("calculus", "integral_test"),
    "直接比较判别法":         ("calculus", "direct_comparison_test"),
    "p-级数判别法":           ("calculus", "p_series_test"),
    "综合判别与分类":         ("calculus", "classify_and_test"),

    # ── 解析几何 ──
    "两点距离":               ("algebra", "distance"),
    "中点":                   ("algebra", "midpoint"),
    "两点式直线":             ("algebra", "line_from_points"),
    "斜截式直线":             ("algebra", "line_from_slope_intercept"),
    "点斜式直线":             ("algebra", "line_from_point_slope"),
    "截距式直线":             ("algebra", "line_from_intercepts"),
    "直线一般式":             ("algebra", "line_general"),
    "圆标准方程":             ("algebra", "circle_standard"),
    "圆一般方程":             ("algebra", "circle_general"),

    # ── 数列 ──
    "数列通项":               ("algebra", "sequence_term"),
    "等差数列":               ("algebra", "arithmetic_sequence"),
    "等差数列求和":           ("algebra", "arithmetic_sum"),
    "等比数列":               ("algebra", "geometric_sequence"),
    "等比数列求和":           ("algebra", "geometric_sum"),
    "递推数列":               ("algebra", "recurrence_sequence"),

    # ── 排列组合 ──
    "排列数":                 ("algebra", "permutation"),
    "组合数":                 ("algebra", "combination"),
    "二项式展开":             ("algebra", "binomial_expand"),
    "二项式通项":             ("algebra", "binomial_term"),

    # ── 数值分析补充 ──
    "梯度下降":               ("numerical", "gradient_descent"),
    "相图":                   ("numerical", "phase_portrait"),

    # ── 复数分析补充 ──
    "回路积分":               ("complex_analysis", "contour_integral"),
    "柯西定理":               ("complex_analysis", "cauchy_theorem"),
    "柯西积分公式":           ("complex_analysis", "cauchy_integral_formula"),
    "洛朗级数":               ("complex_analysis", "laurent_series"),
    "奇点分类":               ("complex_analysis", "singularity_classify"),
    "留数":                   ("complex_analysis", "residue"),
    "留数定理":               ("complex_analysis", "residue_theorem"),
    "辐角原理":               ("complex_analysis", "argument_principle"),
    "Rouche 定理":            ("complex_analysis", "rouche_theorem"),
    "Zeta 级数":              ("complex_analysis", "zeta_series"),
    "Zeta 解析延拓":          ("complex_analysis", "analytic_continuation_zeta"),
    "Zeta 函数方程":          ("complex_analysis", "functional_equation_zeta"),
    "Zeta 非平凡零点":        ("complex_analysis", "nontrivial_zeros"),

    # ── 线性代数补充 ──
    "向量空间判定":           ("linear_algebra", "is_vector_space"),
    "线性组合":               ("linear_algebra", "linear_combination"),
    "线性无关判定":           ("linear_algebra", "is_linear_independent"),
    "基":                     ("linear_algebra", "basis"),
    "维数":                   ("linear_algebra", "dimension"),
    "张成子空间":             ("linear_algebra", "subspace_span"),
    "线性变换":               ("linear_algebra", "linear_transform"),
    "矩阵表示":               ("linear_algebra", "matrix_representation"),
    "核":                     ("linear_algebra", "kernel"),
    "像":                     ("linear_algebra", "image"),
    "秩-零化度":              ("linear_algebra", "rank_nullity"),
    "标准化":                 ("linear_algebra", "standard_form"),
    "负定判定":               ("linear_algebra", "is_negative_definite"),
    "不定判定":               ("linear_algebra", "is_indefinite"),

    # ── 数论 ──
    "最大公约数":             ("number_theory", "gcd"),
    "扩展欧几里得":           ("number_theory", "extended_gcd"),
    "模逆元":                 ("number_theory", "mod_inverse"),
    "模幂":                   ("number_theory", "mod_pow"),
    "欧拉函数":               ("number_theory", "euler_phi"),
    "约数个数":               ("number_theory", "divisor_count"),
    "约数和":                 ("number_theory", "divisor_sum"),
    "莫比乌斯函数":           ("number_theory", "mobius"),
    "中国剩余定理":           ("number_theory", "crt"),
    "原根":                   ("number_theory", "primitive_root"),
    "离散对数":               ("number_theory", "discrete_log"),
    "埃氏筛":                 ("number_theory", "eratosthenes"),
    "分段筛":                 ("number_theory", "segmented_sieve"),
    "素数判定":               ("number_theory", "is_prime"),
    "素因数分解":             ("number_theory", "prime_factors"),
    "连分数":                 ("number_theory", "continued_fraction"),
    "连分数逼近":             ("number_theory", "convergents"),
    "最佳有理逼近":           ("number_theory", "best_rational_approximation"),
    "欧拉乘积":               ("number_theory", "euler_product"),
    "Dirichlet L 函数":       ("number_theory", "dirichlet_l_function"),
    "伯努利数":               ("number_theory", "bernoulli_number"),

    # ── 基础运算 ──
    "绝对值":                 ("algebra", "abs_value"),
    "数轴距离":               ("algebra", "distance_on_number_line"),
    "比与比例":               ("algebra", "ratio"),
    "百分数":                 ("algebra", "percentage"),
    "百分变化率":             ("algebra", "percentage_change"),
    "科学记数法":             ("algebra", "to_scientific_notation"),
    "有效数字":               ("algebra", "significant_figures"),

    # ── 三角函数 ──
    "三角函数求值":           ("algebra", "sine_cosine_tangent"),
    "三角恒等式":             ("algebra", "trig_basic_identities"),
    "三角周期性":             ("algebra", "trig_periodicity"),

    # ── 函数分析 ──
    "函数定义域":             ("algebra", "domain"),
    "函数值域估计":           ("algebra", "range_estimate"),
    "线性函数":               ("algebra", "linear_function"),
    "二次函数":               ("algebra", "quadratic_function"),
    "二次函数极值":           ("algebra", "quadratic_extrema"),
    "幂函数":                 ("algebra", "power_function"),
    "指数函数":               ("algebra", "exponential_function"),
    "对数函数":               ("algebra", "log_function"),

    # ── 因式分解补充 ──
    "提取公因式":             ("algebra", "factor_common"),
    "完全平方公式":           ("algebra", "factor_perfect_square"),
    "平方差公式":             ("algebra", "factor_difference_squares"),
    "十字相乘法":             ("algebra", "factor_cross"),
    "分组分解法":             ("algebra", "factor_group"),
    # ── 分式/根式 ──
    "通分":                   ("algebra", "common_denominator"),
    "分式运算":               ("algebra", "fraction_operations"),
    "分母有理化":             ("algebra", "rationalize_denominator"),
    "同类根式判定":           ("algebra", "like_radicals"),
    "根式运算":               ("algebra", "radical_operations"),
    # ── 组合恒等式 ──
    "组合恒等式":             ("algebra", "comb_identities"),
    # ── 函数补充 ──
    "对应法则":               ("algebra", "correspondence_rule"),
    "斜率截距":               ("algebra", "slope_intercept"),
    "反比例函数":             ("algebra", "inverse_proportional"),
    # ── 不等式 ──
    "不等式性质":             ("algebra", "inequality_properties"),
    "最值初步":               ("algebra", "max_min_initial"),
    # ── 数列证明 ──
    "等差数列证明":           ("algebra", "arithmetic_proof"),
    "等比数列证明":           ("algebra", "geometric_proof"),
    # ── 计数原理 ──
    "加法原理":               ("algebra", "addition_principle"),
    "乘法原理":               ("algebra", "multiplication_principle"),
    # ── 运算律 ──
    "交换律验证":             ("algebra", "commutative_law"),
    "结合律验证":             ("algebra", "associative_law"),
    "分配律验证":             ("algebra", "distributive_law"),

    # ── 概率补充 ──
    "分布函数":               ("probability", "distribution_function"),
    "概率质量函数":           ("probability", "pmf"),
    "概率密度函数":           ("probability", "pdf"),

    # ── 实分析 ──
    "数列极限(ε-N)":          ("real_analysis", "sequence_limit"),
    "数列收敛判定":           ("real_analysis", "sequence_convergence"),
    "柯西收敛准则":           ("real_analysis", "cauchy_criterion"),
    "ε-δ 极限定义":           ("real_analysis", "limit_epsilon_delta"),
    "导数定义":               ("real_analysis", "derivative_definition"),
    "一致连续":               ("real_analysis", "uniform_continuity"),
    "介值定理":               ("real_analysis", "intermediate_value"),
    "极值定理":               ("real_analysis", "extreme_value"),
    "上确界":                 ("real_analysis", "supremum"),
    "下确界":                 ("real_analysis", "infimum"),
    "黎曼可积判定":           ("real_analysis", "riemann_integrable"),
    "达布和":                 ("real_analysis", "darboux_sum"),
    "微积分基本定理":         ("real_analysis", "fundamental_theorem"),
    "一致收敛":               ("real_analysis", "uniform_convergence"),
    "逐点收敛":               ("real_analysis", "pointwise_convergence"),
    "Weierstrass M-判别":     ("real_analysis", "weierstrass_m_test"),
    "逐项微分":               ("real_analysis", "termwise_differentiation"),
    "逐项积分":               ("real_analysis", "termwise_integration"),
}


# ═══════════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════════

def calculate(action_name: str, params: list[str]) -> MathObject:
    """通过 FUNC_MAP 调度计算（字符串参数模式）。

    用于代数/微积分等以逗号分隔字符串为输入的 calc_block。

    Args:
        action_name: 下拉框显示名（如 "求导"、"高斯消元"）。
        params: 逗号分隔的参数列表（如 ["sin(x)", "x", "2"]）。

    Returns:
        MathObject。若 action_name 不在 FUNC_MAP 中，返回 error。
    """
    entry = FUNC_MAP.get(action_name)
    if entry is None:
        return MathObject(error=f"功能未实现: {action_name}")

    module, action = entry
    kwargs = _build_kwargs(action, action_name, params)
    if kwargs is None:
        return MathObject(error="参数解析失败，请检查输入格式")

    try:
        _ensure_module(module)
        result = dispatch(module, action, **kwargs)
    except KeyError:
        return MathObject(error=f"后端未找到函数: {module}.{action}")
    except Exception as e:
        return MathObject(error=str(e))

    if not isinstance(result, MathObject):
        result = MathObject(result=str(result))
    return result


def calculate_direct(action_name: str, *args, **kwargs) -> MathObject:
    """直接传递已解析参数（用于 literal_eval 模式的 calc_block）。

    Args:
        action_name: 下拉框显示名。
        *args / **kwargs: 已解析的位置/关键字参数。
    """
    entry = FUNC_MAP.get(action_name)
    if entry is None:
        return MathObject(error=f"功能未实现: {action_name}")

    module, action = entry
    # ── 参数名标准化：UI 友好名 → 后端内部名 ──
    kwargs = _normalize_kwargs(action, kwargs)
    try:
        _ensure_module(module)
        result = dispatch(module, action, *args, **kwargs)
    except KeyError:
        return MathObject(error=f"后端未找到函数: {module}.{action}")
    except Exception as e:
        return MathObject(error=str(e))

    if not isinstance(result, MathObject):
        result = MathObject(result=str(result))
    return result


def _normalize_kwargs(action: str, kwargs: dict) -> dict:
    """将 UI 层参数名映射为后端函数期望的参数名。"""
    kw = dict(kwargs)

    # func → f（数值类函数），同时处理 integrate_numeric 的 f → expr
    _FUNC_TO_F = {"trapezoidal_rule", "simpson_rule", "gauss_quadrature",
                  "euler_method", "rk4", "implicit_euler"}
    if action in _FUNC_TO_F and "func" in kw:
        kw.setdefault("f", kw.pop("func"))
    # integrate_numeric 使用 expr 而非 f
    if action == "integrate_numeric" and "f" in kw:
        kw.setdefault("expr", kw.pop("f"))

    # mean/std → mu/sigma（概率分布 normal 等）
    if action in ("normal",) and "mean" in kw:
        kw.setdefault("mu", kw.pop("mean"))
    if action in ("normal",) and "std" in kw:
        kw.setdefault("sigma", kw.pop("std"))

    # 数值 ODE: x0 → t0, n → t_end（euler_method, rk4, implicit_euler）
    if action in ("euler_method", "rk4", "implicit_euler"):
        if "x0" in kw:
            kw.setdefault("t0", kw.pop("x0"))
        if "n" in kw and "h" in kw:
            n_val = kw.pop("n")
            h_val = kw.get("h", kw.get("h_val", 0.1))
            t0_val = kw.get("t0", kw.get("t0_val", 0))
            try:
                kw.setdefault("t_end", float(t0_val) + float(h_val) * int(n_val))
            except (ValueError, TypeError):
                pass

    # 数值矩阵: matrix → A（lu_decomposition, qr_algorithm, power_method 等）
    _MATRIX_TO_A = {"lu_decomposition", "qr_algorithm", "power_method",
                    "jacobi_iteration", "gauss_seidel", "conjugate_gradient",
                    "solve_linear_system"}
    if action in _MATRIX_TO_A and "matrix" in kw:
        kw.setdefault("A", kw.pop("matrix"))

    # 线性代数: expr → matrix（eigenvalues, rank, gaussian_elimination 等）
    _EXPR_TO_MATRIX = {
        "gaussian_elimination", "rank", "solve_linear_system", "nullspace",
        "eigenvalues", "eigenvectors", "characteristic_polynomial",
        "is_diagonalizable", "diagonalize", "gram_schmidt",
        "orthogonal_projection", "quadratic_form", "is_positive_definite",
    }
    if action in _EXPR_TO_MATRIX and "expr" in kw:
        val = kw.pop("expr")
        if isinstance(val, str):
            try:
                val = _le(val)
            except (ValueError, SyntaxError):
                pass
        kw.setdefault("matrix", val)

    # 线性代数向量: expr → vector（norm）
    if action in ("norm",) and "expr" in kw:
        val = kw.pop("expr")
        if isinstance(val, str):
            try:
                val = _le(val)
            except (ValueError, SyntaxError):
                pass
        kw.setdefault("vector", val)

    # 概率/统计: expr → data
    if action in ("expectation", "variance", "sample_mean", "sample_variance",
                  "moment_estimate", "covariance", "correlation_coefficient") and "expr" in kw:
        val = kw.pop("expr")
        if isinstance(val, str):
            try:
                val = _le(val)
            except (ValueError, SyntaxError):
                pass
        kw.setdefault("data", val)

    # 数值插值: points → x_points, y_points
    if action in ("lagrange_interpolation", "newton_interpolation", "cubic_spline",
                  "least_squares_fit"):
        if "points" in kw:
            pts = kw.pop("points")
            if isinstance(pts, (list, tuple)) and len(pts) > 0:
                if isinstance(pts[0], (list, tuple)):
                    # [(x1,y1), (x2,y2), ...]
                    kw.setdefault("x_points", [p[0] for p in pts])
                    kw.setdefault("y_points", [p[1] for p in pts])
                else:
                    kw.setdefault("x_points", pts)
                    kw.setdefault("y_points", pts)

    # 概率回归: x → x_data, y → y_data
    if action in ("linear_regression", "predict", "residuals") and "x" in kw:
        kw.setdefault("x_data", kw.pop("x"))
    if action in ("linear_regression", "predict", "residuals") and "y" in kw:
        kw.setdefault("y_data", kw.pop("y"))

    # 线性代数内积: v1/v2 → u/v（dot 函数期望 u, v 参数名）
    if action in ("dot", "angle", "is_orthogonal") and "v1" in kw:
        kw.setdefault("u", kw.pop("v1"))
    if action in ("dot", "angle", "is_orthogonal") and "v2" in kw:
        kw.setdefault("v", kw.pop("v2"))

    # 概率正态分布: 无参调用时给默认值
    if action == "normal" and "mu" not in kw and "sigma" not in kw:
        kw.setdefault("mu", 0)
        kw.setdefault("sigma", 1)

    # 傅里叶分析: expr → f (后端函数参数名统一为 f)
    _FOURIER_ACTIONS = {
        "fourier_coeff", "fourier_series", "complex_fourier_coeff",
        "fourier_transform", "inverse_fourier_transform",
        "plancherel_theorem", "ft_of_gaussian",
        "convolution", "convolution_theorem", "gaussian_blur", "low_pass_filter",
        "delta_distribution", "ft_delta", "ft_constant", "tempered_distribution",
        "uncertainty_principle", "stft", "wavelet_transform",
        "poisson_summation", "theta_function", "functional_equation_demo",
    }
    if action in _FOURIER_ACTIONS and "expr" in kw:
        kw.setdefault("f", kw.pop("expr"))
    # orthogonality_check: var → n
    if action == "orthogonality_check" and "var" in kw:
        try:
            kw.setdefault("n", int(kw.pop("var")))
        except (ValueError, TypeError):
            kw.setdefault("n", 1)

    return kw


# ═══════════════════════════════════════════════════════════════════════
#  _build_kwargs — 字符串参数 → 函数 kwargs
# ═══════════════════════════════════════════════════════════════════════

def _build_kwargs(action: str, action_name: str, params: list[str]) -> dict | None:
    """根据 action 将字符串参数列表构造为 kwargs。"""

    def _safe_le(s: str, default=None):
        try:
            val = _le(s.strip())
            if isinstance(val, list):
                val = tuple(val)
            return val
        except (ValueError, SyntaxError):
            return s.strip()

    if not params:
        return None

    # ── 求导类 ──
    if action == "diff":
        expr = params[0]
        var = params[1] if len(params) > 1 else "x"
        kwargs: dict = {"expr": expr, "var": var}
        if len(params) > 2:
            try: kwargs["order"] = int(params[2])
            except ValueError: kwargs["order"] = 1
        return kwargs

    if action == "diff_at":
        expr = params[0]
        var = params[1] if len(params) > 1 else "x"
        point = params[2] if len(params) > 2 else "0"
        return {"expr": expr, "var": var, "point": point}

    if action == "implicit_diff":
        eq = params[0]
        var = params[1] if len(params) > 1 else "x"
        dep_var = params[2] if len(params) > 2 else "y"
        return {"eq": eq, "var": var, "dep_var": dep_var}

    if action == "parametric_diff":
        x_expr = params[0]
        y_expr = params[1] if len(params) > 1 else ""
        t = params[2] if len(params) > 2 else "t"
        return {"x_expr": x_expr, "y_expr": y_expr, "t": t}

    # ── 积分类 ──
    if action in ("integrate", "integrate_numeric", "improper_integral"):
        expr = params[0]
        var = params[1] if len(params) > 1 else "x"
        kwargs = {"expr": expr, "var": var}
        if len(params) >= 4:
            kwargs["a"] = params[2]
            kwargs["b"] = params[3]
        return kwargs

    # ── 极限 ──
    if action == "limit":
        expr = params[0]
        var = params[1] if len(params) > 1 else "x"
        point = params[2] if len(params) > 2 else "0"
        direction = params[3] if len(params) > 3 else None
        return {"expr": expr, "var": var, "point": point, "direction": direction}

    # ── 泰勒展开 ──
    if action == "taylor":
        expr = params[0]
        var = params[1] if len(params) > 1 else "x"
        point = params[2] if len(params) > 2 else "0"
        try: order = int(params[3]) if len(params) > 3 else 5
        except ValueError: order = 5
        return {"expr": expr, "var": var, "point": point, "order": order}

    # ── 级数 ──
    if action == "series_sum":
        if len(params) < 4:
            return None
        return {"expr": params[0], "var": params[1], "a": params[2], "b": params[3]}

    if action == "series_convergence":
        return {"expr": params[0], "var": params[1] if len(params) > 1 else "n"}

    # ── 解方程类 ──
    if action in ("solve_linear", "solve_quadratic", "solve_fractional",
                  "solve_irrational", "solve_linear_system"):
        if action == "solve_linear_system" and len(params) >= 2:
            eq1, eq2 = params[0], params[1]
            var1 = params[2] if len(params) > 2 else "x"
            var2 = params[3] if len(params) > 3 else "y"
            return {"eq1": eq1, "eq2": eq2, "var1": var1, "var2": var2}
        expr = params[0]
        var = params[1] if len(params) > 1 else "x"
        return {"expr": expr, "var": var}

    # ── 解不等式 ──
    if action in ("solve_linear_inequality", "solve_quadratic_inequality"):
        expr = params[0]
        var = params[1] if len(params) > 1 else "x"
        return {"expr": expr, "var": var}

    if action == "solve_inequality_system":
        exprs = [p.strip() for p in params[0].split(",")] if len(params) == 1 else params
        var = params[1] if len(params) > 1 else "x"
        return {"exprs": exprs, "var": var}

    # ── 化简 / 展开 / 因式分解 ──
    if action in ("simplify_polynomial", "expand_expression", "factor",
                  "simplify_fraction", "simplify_radical"):
        return {"expr": params[0]}

    # ── 复数 ──
    if action in ("exp_complex", "log_complex", "sqrt_complex"):
        return {"z": params[0]}

    # ── 幂级数 / 收敛半径 ──
    if action == "power_series":
        return {"expr": params[0], "var": params[1] if len(params) > 1 else "x"}

    # ── 解析几何: p1, p2 参数 ──
    if action in ("distance", "midpoint"):
        p1 = _le(params[0].strip()) if len(params) > 0 else (0, 0)
        p2 = _le(params[1].strip()) if len(params) > 1 else (1, 0)
        return {"p1": p1, "p2": p2}

    # ── 排列组合: n, m (整数) ──
    if action in ("permutation", "combination"):
        n = _le(params[0]) if len(params) > 0 else 5
        m = _le(params[1]) if len(params) > 1 else 2
        return {"n": n, "m": m}

    # ── 梯度下降: f, x0 ──
    if action == "gradient_descent":
        return {"f": params[0]} if params else {"f": "x**2"}
    if action == "phase_portrait":
        return {"f": params[0]} if params else {"f": "[-y, x]"}

    # ── 数列: a1, d/q, n ──
    if action == "arithmetic_sum":
        a1 = _le(params[0]) if len(params) > 0 else 0
        d = _le(params[1]) if len(params) > 1 else 1
        n = _le(params[2]) if len(params) > 2 else 10
        return {"a1": a1, "d": d, "n": n}
    if action == "geometric_sequence":
        a1 = _le(params[0]) if len(params) > 0 else 1
        q = _le(params[1]) if len(params) > 1 else 2
        n = _le(params[2]) if len(params) > 2 else 10
        return {"a1": a1, "q": q, "n": n}
    if action == "arithmetic_sequence":
        a1 = _le(params[0]) if len(params) > 0 else 1
        d = _le(params[1]) if len(params) > 1 else 1
        n = _le(params[2]) if len(params) > 2 else 10
        return {"a1": a1, "d": d, "n": n}
    if action == "geometric_sum":
        a1 = _le(params[0]) if len(params) > 0 else 1
        q = _le(params[1]) if len(params) > 1 else 1
        n = _le(params[2]) if len(params) > 2 else 10
        return {"a1": a1, "q": q, "n": n}
    if action == "sequence_term":
        return {"expr": params[0], "n": _le(params[1]) if len(params) > 1 else 1}

    # ── 二项式: a, b, n ──
    if action == "binomial_expand":
        a = _le(params[0]) if len(params) > 0 else "a"
        b = _le(params[1]) if len(params) > 1 else "b"
        n = _le(params[2]) if len(params) > 2 else 2
        return {"a": a, "b": b, "n": n}
    if action == "binomial_term":
        a = _le(params[0]) if len(params) > 0 else "a"
        b = _le(params[1]) if len(params) > 1 else "b"
        n = _le(params[2]) if len(params) > 2 else 2
        k = _le(params[3]) if len(params) > 3 else 1
        return {"a": a, "b": b, "n": n, "k": k}

    # ── 复数分析: func/z 参数 ──
    if action in ("residue", "residue_theorem"):
        func = params[0] if params else "1/z"
        if len(params) > 1:
            try: z0 = _le(params[1])
            except (ValueError, SyntaxError): z0 = params[1]
        else:
            z0 = 0
        return {"func": func, "z0": z0}
    if action in ("contour_integral", "cauchy_theorem", "cauchy_integral_formula",
                  "laurent_series", "singularity_classify"):
        return {"f": params[0]} if params else {"f": "1/z"}

    # ── 数论: 单整数参数 ──
    if action in ("euler_phi", "divisor_count", "divisor_sum", "mobius",
                  "is_prime", "prime_factors", "continued_fraction",
                  "eratosthenes", "segmented_sieve", "bernoulli_number"):
        n = int(_le(params[0])) if params else 1
        return {"n": n}
    if action in ("gcd", "extended_gcd"):
        a = int(_le(params[0])) if len(params) > 0 else 1
        b = int(_le(params[1])) if len(params) > 1 else 2
        return {"a": a, "b": b}
    if action == "mod_inverse":
        a = int(_le(params[0])) if len(params) > 0 else 1
        m = int(_le(params[1])) if len(params) > 1 else 7
        return {"a": a, "m": m}
    if action == "mod_pow":
        base = int(_le(params[0])) if len(params) > 0 else 2
        exp = int(_le(params[1])) if len(params) > 1 else 3
        mod = int(_le(params[2])) if len(params) > 2 else 7
        return {"base": base, "exp": exp, "mod": mod}
    if action == "primitive_root":
        p = int(_le(params[0])) if params else 7
        return {"p": p}
    if action == "discrete_log":
        g = int(_le(params[0])) if len(params) > 0 else 2
        h = int(_le(params[1])) if len(params) > 1 else 1
        p = int(_le(params[2])) if len(params) > 2 else 7
        return {"g": g, "h": h, "p": p}
    if action == "crt":
        a = _le(params[0]) if len(params) > 0 else [2, 3, 2]
        m = _le(params[1]) if len(params) > 1 else [3, 5, 7]
        return {"remainders": a, "moduli": m} if isinstance(a, list) else {"a": a, "m": m}
    if action in ("convergents", "best_rational_approximation"):
        x = _le(params[0]) if params else 3.14159
        n = int(_le(params[1])) if len(params) > 1 else 10
        return {"x": x, "n": n}
    if action == "mobius_prefix":
        n = int(_le(params[0])) if params else 100
        return {"n": n}
    if action == "euler_product":
        s = _le(params[0]) if params else 2
        terms = int(_le(params[1])) if len(params) > 1 else 10
        return {"s": s, "terms": terms}
    if action == "dirichlet_l_function":
        s = _le(params[0]) if params else 2
        return {"s": s}
    if action == "zeta_dirichlet_series":
        s = _le(params[0]) if params else 2
        n_terms = int(_le(params[1])) if len(params) > 1 else 100
        return {"s": s, "n_terms": n_terms}
    if action == "zeta_negative":
        n = int(_le(params[0])) if params else 1
        return {"n": n}

    # ── 基础运算 + 三角 + 函数分析 ──
    if action in ("abs_value", "distance_on_number_line", "to_scientific_notation",
                  "significant_figures"):
        x = _safe_le(params[0]) if params else 0
        return {"x": x}
    if action in ("ratio", "percentage", "percentage_change"):
        a = _safe_le(params[0]) if len(params) > 0 else 1
        b = _safe_le(params[1]) if len(params) > 1 else 1
        return {"a": a, "b": b}
    if action == "sine_cosine_tangent":
        angle = _safe_le(params[0]) if params else 0
        mode = params[1] if len(params) > 1 else "degrees"
        return {"angle": angle, "mode": mode}
    if action in ("trig_basic_identities", "trig_periodicity"):
        func = params[0] if params else "sin"
        return {"func": func}
    # ── 单参数 expr ──
    if action in ("factor_common", "factor_perfect_square", "factor_difference_squares",
                  "factor_cross", "factor_group", "rationalize_denominator",
                  "comb_identities", "inequality_properties", "max_min_initial",
                  "arithmetic_proof", "geometric_proof", "correspondence_rule"):
        return {"expr": params[0]} if params else {"expr": "x"}
    # ── 分式/根式双参数: expr1, expr2 ──
    if action in ("common_denominator", "like_radicals"):
        expr1 = params[0] if len(params) > 0 else "1/x"
        expr2 = params[1] if len(params) > 1 else "1/y"
        return {"expr1": expr1, "expr2": expr2}
    if action == "fraction_operations":
        expr1 = params[0] if len(params) > 0 else "1/x"
        op = params[1] if len(params) > 1 else "+"
        expr2 = params[2] if len(params) > 2 else "1/y"
        return {"expr1": expr1, "op": op, "expr2": expr2}
    if action == "radical_operations":
        expr1 = params[0] if len(params) > 0 else "sqrt(2)"
        op = params[1] if len(params) > 1 else "+"
        expr2 = params[2] if len(params) > 2 else "sqrt(3)"
        return {"expr1": expr1, "op": op, "expr2": expr2}
    # ── 计数原理: a, b (整数) ──
    if action in ("addition_principle", "multiplication_principle"):
        a = _safe_le(params[0]) if len(params) > 0 else 1
        b = _safe_le(params[1]) if len(params) > 1 else 1
        return {"a": a, "b": b}
    # ── 运算律 a, b (数值) ──
    if action in ("commutative_law", "associative_law", "distributive_law"):
        a = _safe_le(params[0]) if len(params) > 0 else 1
        b = _safe_le(params[1]) if len(params) > 1 else 2
        return {"a": a, "b": b}
    # ── 函数分析 expr + var ──
    if action in ("domain", "range_estimate", "linear_function",
                  "quadratic_function", "quadratic_extrema",
                  "power_function", "exponential_function", "log_function",
                  "slope_intercept", "inverse_proportional"):
        expr = params[0] if params else "x"
        var = params[1] if len(params) > 1 else "x"
        return {"expr": expr, "var": var}

    # ── 实分析 function_series: seq_expr 参数名 ──
    if action in ("pointwise_convergence", "uniform_convergence",
                  "weierstrass_m_test", "termwise_differentiation",
                  "termwise_integration"):
        seq_expr = params[0] if params else "x**n"
        var = params[1] if len(params) > 1 else "x"
        return {"seq_expr": seq_expr, "var": var}

    # ── 实分析: 单参数 s (集合/列表) ──
    if action in ("supremum", "infimum"):
        try:
            s = _le(params[0]) if params else [0, 1]
            if isinstance(s, list): s = tuple(s)  # LRU cache 需要 hashable
        except (ValueError, SyntaxError):
            s = params[0] if params else (0, 1)
        return {"s": s}

    # ── 概率: data/values 参数 (tuple 化) ──
    if action == "distribution_function":
        try:
            data = _le(params[0]) if params else [1,2,3]
            if isinstance(data, list): data = tuple(data)
        except (ValueError, SyntaxError):
            data = tuple(params[0].strip("[]()").split(",")) if params else (1,2,3)
        x = float(_le(params[1])) if len(params) > 1 else None
        return {"data": data, "x": x}
    if action == "pmf":
        try:
            values = _le(params[0]) if params else ("x1","x2")
            if isinstance(values, list): values = tuple(values)
        except (ValueError, SyntaxError):
            values = params[0] if params else ("x1","x2")
        try:
            probs = _le(params[1]) if len(params) > 1 else (0.5, 0.5)
            if isinstance(probs, list): probs = tuple(probs)
        except (ValueError, SyntaxError):
            probs = params[1] if len(params) > 1 else (0.5, 0.5)
        return {"values": values, "probs": probs}

    # ── 解析几何直线/圆: expr+var ──
    if action in ("line_from_points", "line_from_slope_intercept",
                  "line_from_point_slope", "line_from_intercepts",
                  "line_general", "circle_standard", "circle_general",
                  "recurrence_sequence"):
        expr = params[0]
        var = params[1] if len(params) > 1 else "x"
        return {"expr": expr, "var": var}

    # ── 其他单参数操作 ──
    if action in ("is_continuous", "discontinuity_classify", "lhopital",
                  "monotonicity", "local_extrema", "global_extrema",
                  "discriminant", "vieta_theorem", "am_gm_inequality",
                  "differential", "rolle_theorem", "lagrange_theorem",
                  "area_between", "volume_disk", "volume_shell", "arc_length",
                  "power_series_radius",
                  "leibniz_test", "limit_comparison_test", "integral_test",
                  "direct_comparison_test", "p_series_test", "classify_and_test",
                  "argument_principle", "rouche_theorem",
                  "zeta_series", "analytic_continuation_zeta",
                  "functional_equation_zeta", "nontrivial_zeros",
                  "recurrence_sequence", "line_from_points",
                  "line_from_slope_intercept", "line_from_point_slope",
                  "line_from_intercepts", "line_general",
                  "circle_standard", "circle_general",
                  # 实分析
                  "sequence_limit", "sequence_convergence", "cauchy_criterion",
                  "limit_epsilon_delta", "derivative_definition",
                  "uniform_continuity", "intermediate_value", "extreme_value",
                  "is_continuous", "is_differentiable",
                  "riemann_integrable", "darboux_sum", "fundamental_theorem",
                  "uniform_convergence", "pointwise_convergence",
                  "weierstrass_m_test", "termwise_differentiation",
                  "termwise_integration",
                  "supremum", "infimum",
                  # 概率补充
                  "distribution_function", "pmf", "pdf"):
        expr = params[0]
        var = params[1] if len(params) > 1 else "x"
        return {"expr": expr, "var": var}

    # ── 傅里叶分析 — 后端参数名统一为 f ──
    if action in ("fourier_coeff", "complex_fourier_coeff"):
        result = {"f": params[0]}
        if len(params) >= 2:
            try: result["n"] = int(params[1])
            except ValueError: result["n"] = 1
        else:
            result["n"] = 1
        return result

    if action == "fourier_series":
        result = {"f": params[0]}
        if len(params) >= 2:
            try: result["n_terms"] = int(params[1])
            except ValueError: result["n_terms"] = 3
        else:
            result["n_terms"] = 3
        return result

    if action == "inverse_fourier_transform":
        return {"F": params[0]}  # 逆变换参数名为 F

    if action in ("fourier_transform",
                  "plancherel_theorem", "convolution", "convolution_theorem",
                  "gaussian_blur", "low_pass_filter", "delta_distribution",
                  "ft_delta", "ft_constant", "tempered_distribution",
                  "uncertainty_principle", "stft", "wavelet_transform",
                  "poisson_summation", "theta_function", "functional_equation_demo"):
        return {"f": params[0]}

    if action == "ft_of_gaussian":
        a = float(params[0]) if params else 1.0
        return {"a": a}

    if action == "orthogonality_check":
        n = int(params[0]) if params else 1
        m = int(params[1]) if len(params) > 1 else 2
        return {"n": n, "m": m}

    # ── 通用回退：单参数 → expr，多参数 → 位置展开 ──
    import logging
    logging.debug(
        "calc_engine._build_kwargs: 未专门处理的操作 %r, 使用通用回退", action_name)
    if len(params) == 1:
        return {"expr": params[0]}
    return {f"arg{i}": v for i, v in enumerate(params)}
