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

_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _base not in sys.path:
    sys.path.insert(0, _base)

# ── 导入所有子模块以触发 @register ─────────────────────────
import MF_Mathematics.algebra            # noqa
import MF_Mathematics.calculus           # noqa
import MF_Mathematics.complex_analysis   # noqa
import MF_Mathematics.linear_algebra     # noqa
import MF_Mathematics.probability        # noqa
import MF_Mathematics.numerical          # noqa

from MF_Mathematics.core.registry import dispatch
from MF_Mathematics.core.math_object import MathObject


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
    "p值":            ("probability", "p_value"),
    "线性回归":       ("probability", "linear_regression"),
    "预测":           ("probability", "predict"),
    "残差":           ("probability", "residuals"),

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

    Returns:
        MathObject。
    """
    entry = FUNC_MAP.get(action_name)
    if entry is None:
        return MathObject(error=f"功能未实现: {action_name}")

    module, action = entry
    try:
        result = dispatch(module, action, *args, **kwargs)
    except KeyError:
        return MathObject(error=f"后端未找到函数: {module}.{action}")
    except Exception as e:
        return MathObject(error=str(e))

    if not isinstance(result, MathObject):
        result = MathObject(result=str(result))
    return result


# ═══════════════════════════════════════════════════════════════════════
#  _build_kwargs — 字符串参数 → 函数 kwargs
# ═══════════════════════════════════════════════════════════════════════

def _build_kwargs(action: str, action_name: str, params: list[str]) -> dict | None:
    """根据 action 将字符串参数列表构造为 kwargs。"""
    if not params:
        return None

    # ── 求导类 ──
    if action in ("diff", "diff_at", "implicit_diff", "parametric_diff"):
        expr = params[0]
        var = params[1] if len(params) > 1 else "x"
        kwargs: dict = {"expr": expr, "var": var}
        if action == "diff" and len(params) > 2:
            try: kwargs["order"] = int(params[2])
            except ValueError: kwargs["order"] = 1
        return kwargs

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

    # ── 其他单参数操作 ──
    if action in ("is_continuous", "discontinuity_classify", "lhopital",
                  "monotonicity", "local_extrema", "global_extrema",
                  "discriminant", "vieta_theorem", "am_gm_inequality"):
        expr = params[0]
        var = params[1] if len(params) > 1 else "x"
        return {"expr": expr, "var": var}

    # ── 通用回退：单参数 → expr ──
    if len(params) == 1:
        return {"expr": params[0]}
    # 多参数 → 位置展开
    return {f"arg{i}": v for i, v in enumerate(params)}
