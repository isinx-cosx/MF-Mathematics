"""初等复函数 — e^z, log z, sqrt z, 幂函数、分式线性变换。

依赖: sympy, numpy
"""

from __future__ import annotations

from typing import Any, Tuple, Union

import sympy as sp
import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


# ── 工具：sympy 复数 ↔ Python complex ─────────────────────────────────

def _to_complex(val: Any) -> complex:
    """将 sympy 表达式或 Python 值转换为 complex。"""
    if isinstance(val, complex):
        return val
    if isinstance(val, (int, float)):
        return complex(val, 0)
    if isinstance(val, (tuple, list)) and len(val) == 2:
        return complex(float(val[0]), float(val[1]))
    try:
        c = complex(sp.N(val))
        return c
    except Exception:
        return complex(str(val))


# ── 公开函数 ──────────────────────────────────────────────────────────


@register(module="complex_analysis", action="exp_complex")
def exp_complex(
    z: Union[complex, str, Tuple[float, float]],
) -> MathObject:
    """复指数函数 e^z。

    e^(x+iy) = e^x (cos y + i sin y)

    Args:
        z: 复变量，complex / "x+iy" / (x, y)。

    Returns:
        MathObject，result 为 e^z 的数值或 sympy 表达式。
    """
    try:
        if isinstance(z, str):
            z_sym = sp.sympify(z)
            result = sp.exp(z_sym)
            steps = [
                f"输入: z = {z}",
                f"e^{z} = {result}",
            ]
            return MathObject(
                result=str(result),
                steps=steps,
                meaning="e^z 在整个复平面上全纯，|e^z| = e^{Re(z)}，arg(e^z) = Im(z)。",
            )
        elif isinstance(z, (int, float)):
            result = np.exp(float(z))
            return MathObject(
                result=result,
                steps=[f"e^{{{z}}} = {result}"],
                meaning="实数输入退化为实指数函数。",
            )
        else:
            if isinstance(z, (tuple, list)):
                x, y = float(z[0]), float(z[1])
            elif isinstance(z, complex):
                x, y = z.real, z.imag
            else:
                raise ValueError(f"不支持的输入类型: {type(z)}")
            magnitude = np.exp(x)
            real_part = magnitude * np.cos(y)
            imag_part = magnitude * np.sin(y)
            result = complex(real_part, imag_part)
            steps = [
                f"z = {x} + {y}i",
                f"e^z = e^{x} * (cos({y}) + i sin({y}))",
                f"e^x = {magnitude:.10g}",
                f"cos y = {np.cos(y):.10g}, sin y = {np.sin(y):.10g}",
                f"e^z = {real_part:.10g} + {imag_part:.10g}i",
            ]
            return MathObject(
                result=result,
                steps=steps,
                meaning="e^z = e^x (cos y + i sin y)，幅角为 y，模为 e^x。",
            )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="log_complex")
def log_complex(
    z: Union[complex, str, Tuple[float, float]],
    branch_cut: float = -np.pi,
) -> MathObject:
    """复对数（主值），支持分支切割。

    Log z = ln|z| + i Arg(z)，其中 Arg(z) ∈ (branch_cut, branch_cut + 2π]。

    Args:
        z: 复变量。
        branch_cut: 分支切割角度（默认 -π，即主值 (-π, π]）。

    Returns:
        MathObject，result 为 log z 的复数数值。
    """
    try:
        if isinstance(z, str):
            z_val = complex(sp.N(sp.sympify(z)))
        elif isinstance(z, (tuple, list)):
            z_val = complex(float(z[0]), float(z[1]))
        elif isinstance(z, complex):
            z_val = z
        elif isinstance(z, (int, float)):
            z_val = complex(float(z), 0)
        else:
            raise ValueError(f"不支持的输入类型: {type(z)}")

        if z_val == 0:
            return MathObject(
                result="undefined",
                steps=["log(0) 无定义"],
                meaning="0 是复对数的支点。",
            )

        r = abs(z_val)
        # 计算幅角，映射到 (branch_cut, branch_cut + 2π]
        theta = np.arctan2(z_val.imag, z_val.real)
        # 归一化到 (branch_cut, branch_cut + 2π]
        while theta <= branch_cut:
            theta += 2 * np.pi
        while theta > branch_cut + 2 * np.pi:
            theta -= 2 * np.pi

        log_val = complex(np.log(r), theta)
        steps = [
            f"z = {z_val.real:.10g} + {z_val.imag:.10g}i",
            f"|z| = {r:.10g}",
            f"Arg(z) = {theta:.10g} rad (branch_cut={branch_cut})",
            f"Log z = ln({r:.10g}) + {theta:.10g}i = {log_val.real:.10g} + {log_val.imag:.10g}i",
        ]

        return MathObject(
            result=log_val,
            steps=steps,
            meaning="Log z 在去掉分支切割的复平面上全纯。主值 Arg(z) ∈ (-π, π]。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="sqrt_complex")
def sqrt_complex(
    z: Union[complex, str, Tuple[float, float]],
    branch_cut: float = -np.pi,
) -> MathObject:
    """复平方根（主值）。

    √z = √|z| * e^(i * Arg(z)/2)

    Args:
        z: 复变量。
        branch_cut: 分支切割角度。

    Returns:
        MathObject，result 为 √z 的复数数值。
    """
    try:
        log_obj = log_complex(z, branch_cut)
        if log_obj.error:
            return log_obj
        log_val = log_obj.result
        if not isinstance(log_val, complex):
            return MathObject(error=f"log 返回非复数: {log_val}")

        half_log = complex(log_val.real / 2, log_val.imag / 2)
        sqrt_val = complex(np.exp(half_log.real) * np.cos(half_log.imag),
                           np.exp(half_log.real) * np.sin(half_log.imag))

        if isinstance(z, str):
            z_str = z
        elif isinstance(z, (tuple, list)):
            z_str = f"{z[0]}+{z[1]}i"
        elif isinstance(z, complex):
            z_str = f"{z.real}+{z.imag}i"
        else:
            z_str = str(z)

        steps = [
            f"z = {z_str}",
            f"Log z = {log_val.real:.10g} + {log_val.imag:.10g}i",
            f"√z = e^(Log z / 2)",
            f"√z = {sqrt_val.real:.10g} + {sqrt_val.imag:.10g}i",
        ]

        return MathObject(
            result=sqrt_val,
            steps=steps,
            meaning="√z 有两个分支，主值 √z = exp(Log z / 2)。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="mobius_transform")
def mobius_transform(
    z: Union[complex, str, Tuple[float, float]],
    a: complex,
    b: complex,
    c: complex,
    d: complex,
) -> MathObject:
    """分式线性变换 (Möbius 变换)。

    f(z) = (a·z + b) / (c·z + d)，其中 ad - bc ≠ 0。

    Args:
        z: 复变量。
        a, b, c, d: 复系数，满足 ad - bc ≠ 0。

    Returns:
        MathObject，result 为 f(z) 的数值或 sympy 表达式。
    """
    try:
        det = a * d - b * c
        if abs(det) < 1e-15:
            return MathObject(
                result="undefined",
                steps=[f"ad - bc = {det} ≈ 0", "退化为常值映射，不是 Möbius 变换"],
                meaning="Möbius 变换要求 ad - bc ≠ 0。",
            )

        if isinstance(z, str):
            z_sym = sp.sympify(z)
            a_sym = sp.sympify(str(a))
            b_sym = sp.sympify(str(b))
            c_sym = sp.sympify(str(c))
            d_sym = sp.sympify(str(d))
            result_sym = (a_sym * z_sym + b_sym) / (c_sym * z_sym + d_sym)
            steps = [
                f"z = {z}",
                f"a={a}, b={b}, c={c}, d={d}",
                f"f(z) = ({a}z + {b}) / ({c}z + {d})",
                f"f(z) = {sp.simplify(result_sym)}",
            ]
            return MathObject(
                result=str(result_sym),
                steps=steps,
                meaning="Möbius 变换将广义圆映射为广义圆，保持交比不变。",
            )
        else:
            if isinstance(z, (tuple, list)):
                z_val = complex(float(z[0]), float(z[1]))
            elif isinstance(z, (int, float)):
                z_val = complex(float(z), 0)
            else:
                z_val = z

            numerator = a * z_val + b
            denominator = c * z_val + d

            if abs(denominator) < 1e-15:
                return MathObject(
                    result="∞ (无穷远点)",
                    steps=[f"分母 cz+d = {denominator}", "映射到无穷远点 ∞"],
                    meaning="分母为零时 Möbius 变换映射到 ∞。",
                )

            result = numerator / denominator
            steps = [
                f"z = {z_val.real:.10g} + {z_val.imag:.10g}i",
                f"a={a}, b={b}, c={c}, d={d}",
                f"分子 = {numerator.real:.10g} + {numerator.imag:.10g}i",
                f"分母 = {denominator.real:.10g} + {denominator.imag:.10g}i",
                f"f(z) = {result.real:.10g} + {result.imag:.10g}i",
            ]
            return MathObject(
                result=result,
                steps=steps,
                meaning=f"Möbius 变换 ad-bc={det}，是复球面上的共形自同构。",
            )
    except Exception as e:
        return MathObject(error=str(e))


# ── self_test ──────────────────────────────────────────────────────────

def self_test() -> None:
    """自测：初等复函数。"""
    import numpy as np

    print("=== elementary_funcs self_test ===")

    # 1. exp_complex: e^(iπ) = -1
    r = exp_complex(complex(0, np.pi))
    assert r.ok, r.error
    assert abs(r.result.real + 1) < 1e-10
    assert abs(r.result.imag) < 1e-10
    print(f"  exp_complex(iπ): {r.result}")

    # 2. exp_complex: e^(1+2j) 数值
    r = exp_complex(complex(1, 2))
    assert r.ok, r.error
    print(f"  exp_complex(1+2i): {r.result}")

    # 3. log_complex: log(-1) = iπ
    r = log_complex(-1.0)
    assert r.ok, r.error
    c = r.result
    assert isinstance(c, complex)
    assert abs(c.real) < 1e-10
    assert abs(c.imag - np.pi) < 1e-10
    print(f"  log_complex(-1): {r.result}")

    # 4. sqrt_complex: √(-1) = i
    r = sqrt_complex(-1.0)
    assert r.ok, r.error
    c = r.result
    assert isinstance(c, complex)
    assert abs(c.real) < 1e-10
    assert abs(c.imag - 1.0) < 1e-10
    print(f"  sqrt_complex(-1): {r.result}")

    # 5. mobius_transform: f(z) = z/(z-1) at z=2
    r = mobius_transform(2.0, 1, 0, 1, -1)
    assert r.ok, r.error
    assert abs(r.result - 2) < 1e-10
    print(f"  mobius_transform(z/(z-1) at z=2): {r.result}")

    # 6. mobius_transform: f(z) = 1/z at z=i
    r = mobius_transform(1j, 0, 1, 1, 0)
    assert r.ok, r.error
    assert abs(r.result + 1j) < 1e-10  # 1/i = -i
    print(f"  mobius_transform(1/z at z=i): {r.result}")

    print("=== elementary_funcs self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
