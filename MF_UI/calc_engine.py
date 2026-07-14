"""计算调度器 — 根据 UI 的模式和功能，调用 MF_Mathematics 库函数。"""

import sys
import os

# 确保 MF_Mathematics 可导入
_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _base not in sys.path:
    sys.path.insert(0, _base)

# 导入子模块以触发 @register 装饰器
import MF_Mathematics.algebra           # noqa: E402
import MF_Mathematics.calculus          # noqa: E402
import MF_Mathematics.complex_analysis  # noqa: E402

from MF_Mathematics.core.registry import dispatch  # noqa: E402
from MF_Mathematics.core.math_object import MathObject  # noqa: E402

# ---- 功能名 → (module, registered_action) 映射 ----
FUNC_MAP: dict[str, tuple[str, str]] = {
    # 代数计算
    "化简":     ("algebra", "simplify_polynomial"),
    "展开":     ("algebra", "expand_expression"),
    "因式分解": ("algebra", "factor"),
    "解方程":   ("algebra", "solve_linear"),
    "解方程组": ("algebra", "solve_linear_system"),
    "解一元二次":("algebra", "solve_quadratic"),
    "判别式":   ("algebra", "discriminant"),
    "韦达定理": ("algebra", "vieta_theorem"),
    "解分式方程":("algebra", "solve_fractional"),
    "解无理方程":("algebra", "solve_irrational"),
    "解线性不等式":("algebra", "solve_linear_inequality"),
    "解不等式组":("algebra", "solve_inequality_system"),
    "解二次不等式":("algebra", "solve_quadratic_inequality"),
    "AM-GM不等式":("algebra", "am_gm_inequality"),
    # 微积分
    "求导":     ("calculus", "diff"),
    "某点导数": ("calculus", "diff_at"),
    "隐函数求导":("calculus", "implicit_diff"),
    "参数方程求导":("calculus", "parametric_diff"),
    "不定积分": ("calculus", "integrate"),
    "定积分":   ("calculus", "integrate"),
    "数值积分": ("calculus", "integrate_numeric"),
    "反常积分": ("calculus", "improper_integral"),
    "极限":     ("calculus", "limit"),
    "连续性判断":("calculus", "is_continuous"),
    "间断点分类":("calculus", "discontinuity_classify"),
    "洛必达法则":("calculus", "lhopital"),
    "单调性":   ("calculus", "monotonicity"),
    "局部极值": ("calculus", "local_extrema"),
    "全局最值": ("calculus", "global_extrema"),
    "泰勒展开": ("calculus", "taylor"),
    "幂级数展开":("calculus", "power_series"),
    "级数求和": ("calculus", "series_sum"),
    "级数收敛性":("calculus", "series_convergence"),
    # 复分析
    "复数运算": ("complex_analysis", "exp_complex"),
}


def _build_kwargs(action_name: str, params: list[str]) -> dict | None:
    """根据 action_name 将字符串参数列表构造为函数实参。"""
    if not params:
        return None

    if action_name in ("simplify_polynomial", "expand_expression", "factor"):
        return {"expr": params[0]}

    if action_name == "diff":
        expr = params[0]
        var = params[1] if len(params) > 1 else "x"
        order = 1
        if len(params) > 2:
            try:
                order = int(params[2])
            except ValueError:
                order = 1
        return {"expr": expr, "var": var, "order": order}

    if action_name in ("integrate", "integrate_numeric"):
        expr = params[0]
        var = params[1] if len(params) > 1 else "x"
        if len(params) >= 3:
            a = params[2]
            b = params[3] if len(params) > 3 else None
            return {"expr": expr, "var": var, "a": a, "b": b}
        return {"expr": expr, "var": var}

    if action_name == "limit":
        expr = params[0]
        var = params[1] if len(params) > 1 else "x"
        point = params[2] if len(params) > 2 else "0"
        direction = params[3] if len(params) > 3 else None
        return {"expr": expr, "var": var, "point": point, "direction": direction}

    if action_name in ("solve_linear", "solve_quadratic", "solve_fractional", "solve_irrational"):
        expr = params[0]
        var = params[1] if len(params) > 1 else "x"
        return {"expr": expr, "var": var}

    if action_name == "solve_linear_system":
        if len(params) >= 2:
            eq1, eq2 = params[0], params[1]
            var1 = params[2] if len(params) > 2 else "x"
            var2 = params[3] if len(params) > 3 else "y"
            return {"eq1": eq1, "eq2": eq2, "var1": var1, "var2": var2}

    if action_name == "exp_complex":
        return {"z": params[0]}

    return None


def calculate(action_display: str, params: list[str]) -> MathObject:
    """调度计算入口。

    Args:
        action_display: 下拉框中显示的功能名称（如 "化简"、"求导"）。
        params: 用户输入的逗号分隔参数列表（如 ["sin(x)", "x"]）。

    Returns:
        MathObject 结果对象。若功能未映射，返回 error 非空的 MathObject。
    """
    entry = FUNC_MAP.get(action_display)
    if entry is None:
        return MathObject(error=f"未找到功能映射: {action_display}")

    module, action = entry
    kwargs = _build_kwargs(action, params)
    if kwargs is None:
        return MathObject(error="请至少输入表达式")

    try:
        result = dispatch(module, action, **kwargs)
    except KeyError:
        return MathObject(error=f"数学库中未找到函数: {module}.{action}")
    except Exception as e:
        return MathObject(error=str(e))

    # 确保返回值是 MathObject
    if not isinstance(result, MathObject):
        result = MathObject(result=str(result))

    return result
