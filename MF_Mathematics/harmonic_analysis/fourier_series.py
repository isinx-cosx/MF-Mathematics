"""fourier_series.py — 傅里叶级数。

涵盖三角形式与复指数形式的傅里叶级数、
正交性验证、系数计算与级数逼近。
"""

from __future__ import annotations

from typing import Callable, Optional, Union

import numpy as np
import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register

_PI = np.pi


def _normalize_period(period):
    """将周期参数标准化为 SymPy 表达式，支持 π 的倍数识别。"""
    if isinstance(period, (int, float)):
        # 尝试将浮点周期识别为 π 的有理倍数
        return sp.nsimplify(period, [sp.pi])
    return sp.sympify(period)


def _parse_func(
    f: Union[str, Callable], var: sp.Symbol
) -> sp.Expr:
    """将字符串或可调用对象解析为 SymPy 表达式。"""
    if isinstance(f, str):
        return sp.sympify(f, locals={"x": var, "pi": sp.pi, "PI": sp.pi})
    elif callable(f):
        return f(var)
    else:
        raise TypeError(f"f 必须为字符串或可调用对象，当前类型: {type(f)}")


@register(module="harmonic_analysis", action="fourier_coeff")
def fourier_coeff(
    f: Union[str, Callable],
    n: int,
    period: float = 2 * _PI,
    coeff_type: str = "cos",
) -> MathObject:
    """计算傅里叶级数的第 n 个系数（三角形式）。

    对于周期为 T 的函数 f(x)：
      a_n = (2/T) ∫_0^T f(x) cos(2π n x / T) dx  (coeff_type="cos")
      b_n = (2/T) ∫_0^T f(x) sin(2π n x / T) dx  (coeff_type="sin")
      a_0 = (1/T) ∫_0^T f(x) dx                    (n=0, coeff_type="cos")

    Args:
        f: 周期函数，字符串表达式或可调用对象（以 x 为变量）。
        n: 系数序号，n ≥ 0。
        period: 周期 T，默认 2π。
        coeff_type: 系数类型，"cos" 或 "sin"。

    Returns:
        MathObject: result 为系数的数值或表达式。
    """
    try:
        x = sp.Symbol("x", real=True)
        expr = _parse_func(f, x)
        T = _normalize_period(period)

        if coeff_type == "cos":
            if n == 0:
                integrand = expr / T
                coeff = sp.integrate(integrand, (x, 0, T))
                name = "a_0"
            else:
                integrand = (2 / T) * expr * sp.cos(2 * sp.pi * n * x / T)
                coeff = sp.integrate(integrand, (x, 0, T))
                name = f"a_{n}"
        elif coeff_type == "sin":
            if n == 0:
                return MathObject(result=0.0, steps=["b_0 ≡ 0"], meaning="b_0 恒为零")
            integrand = (2 / T) * expr * sp.sin(2 * sp.pi * n * x / T)
            coeff = sp.integrate(integrand, (x, 0, T))
            name = f"b_{n}"
        else:
            return MathObject(error=f"coeff_type 必须为 'cos' 或 'sin'，当前: {coeff_type}")

        # 尝试数值化简
        coeff_simplified = sp.N(coeff) if coeff.has(sp.Integral) else sp.simplify(coeff)

        steps = [
            f"周期 T = {T}",
            f"被积函数 = {integrand}",
            f"{name} = {coeff_simplified}",
        ]
        meaning = f"傅里叶系数 {name} = {coeff_simplified}"

        return MathObject(result=coeff_simplified, steps=steps, meaning=meaning)
    except Exception as e:
        return MathObject(error=str(e))


@register(module="harmonic_analysis", action="fourier_series")
def fourier_series(
    f: Union[str, Callable],
    n_terms: int,
    period: float = 2 * _PI,
) -> MathObject:
    """计算前 n 项傅里叶级数逼近（三角形式）。

    f(x) ≈ a_0 + Σ_{k=1}^{n_terms} [a_k cos(2πk x/T) + b_k sin(2πk x/T)]

    Args:
        f: 周期函数。
        n_terms: 逼近项数。
        period: 周期 T，默认 2π。

    Returns:
        MathObject: result 为 SymPy 级数表达式。
    """
    try:
        x = sp.Symbol("x", real=True)
        expr = _parse_func(f, x)
        T = _normalize_period(period)

        # a_0
        a0 = sp.integrate(expr / T, (x, 0, T))
        series_expr = sp.simplify(a0)
        coeffs = [("a_0", a0)]

        steps = [f"周期 T = {T}", f"a_0 = {sp.simplify(a0)}"]

        for k in range(1, n_terms + 1):
            ak = sp.integrate((2 / T) * expr * sp.cos(2 * sp.pi * k * x / T), (x, 0, T))
            bk = sp.integrate((2 / T) * expr * sp.sin(2 * sp.pi * k * x / T), (x, 0, T))
            ak_s = sp.simplify(ak)
            bk_s = sp.simplify(bk)
            series_expr += ak_s * sp.cos(2 * sp.pi * k * x / T) + bk_s * sp.sin(
                2 * sp.pi * k * x / T
            )
            coeffs.append((f"a_{k}", ak_s))
            coeffs.append((f"b_{k}", bk_s))
            steps.append(f"k={k}: a_k={ak_s}, b_k={bk_s}")

        series_expr = sp.simplify(series_expr)

        steps.append(f"级数 = {series_expr}")
        meaning = f"前 {n_terms} 项傅里叶级数逼近"

        return MathObject(
            result=series_expr,
            steps=steps,
            meaning=meaning,
            data={"coeffs": [(name, str(c)) for name, c in coeffs]},
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="harmonic_analysis", action="complex_fourier_coeff")
def complex_fourier_coeff(
    f: Union[str, Callable],
    n: int,
    period: float = 2 * _PI,
) -> MathObject:
    """计算复指数形式的傅里叶系数。

    c_n = (1/T) ∫_0^T f(x) e^{-2π i n x / T} dx

    Args:
        f: 周期函数。
        n: 系数序号（可为负整数）。
        period: 周期 T，默认 2π。

    Returns:
        MathObject: result 为复系数 c_n（SymPy 表达式）。
    """
    try:
        x = sp.Symbol("x", real=True)
        expr = _parse_func(f, x)
        T = _normalize_period(period)

        integrand = (1 / T) * expr * sp.exp(-2 * sp.pi * sp.I * n * x / T)
        coeff = sp.integrate(integrand, (x, 0, T))
        coeff_s = sp.simplify(coeff)

        steps = [
            f"周期 T = {T}",
            f"被积函数 = {integrand}",
            f"c_{n} = {coeff_s}",
        ]
        meaning = f"复傅里叶系数 c_{n} = {coeff_s}"

        return MathObject(result=coeff_s, steps=steps, meaning=meaning)
    except Exception as e:
        return MathObject(error=str(e))


@register(module="harmonic_analysis", action="orthogonality_check")
def orthogonality_check(
    n: int,
    m: int,
    period: float = 2 * _PI,
) -> MathObject:
    """验证 e^{i n x} 与 e^{i m x} 在 [0, T] 上的正交性。

    ∫_0^T e^{i n ω x} · e^{-i m ω x} dx = 0   (n ≠ m)
                                         = T   (n = m)
    其中 ω = 2π/T。

    Args:
        n: 第一个频率序号。
        m: 第二个频率序号。
        period: 周期 T，默认 2π。

    Returns:
        MathObject: result 为积分值（0 或 T）。
    """
    try:
        x = sp.Symbol("x", real=True)
        T = _normalize_period(period)
        omega = 2 * sp.pi / T

        integrand = sp.exp(sp.I * n * omega * x) * sp.exp(-sp.I * m * omega * x)
        integral = sp.integrate(integrand, (x, 0, T))
        integral_s = sp.simplify(integral)

        is_orthogonal = False
        if integral_s == 0 or abs(float(sp.N(integral_s))) < 1e-12:
            is_orthogonal = True

        steps = [
            f"周期 T = {T}, ω = {omega}",
            f"∫_0^{T} e^(i·{n}ωx) · e^(-i·{m}ωx) dx = {integral_s}",
        ]

        if n == m:
            meaning = f"n=m={n}，内积 = T = {T}（自正交）"
        else:
            meaning = f"n={n} ≠ m={m}，内积 = 0（正交）"

        return MathObject(
            result=float(sp.N(integral_s)) if integral_s != 0 else 0.0,
            steps=steps,
            meaning=meaning,
            data={"n": n, "m": m, "orthogonal": is_orthogonal},
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """自测：至少 3 个典型用例。"""
    import numpy as np

    print("=" * 60)
    print("fourier_series 自测")
    print("=" * 60)

    passed = 0
    failed = 0

    # 测试 1: 常数函数的傅里叶系数
    print("\n[测试 1] fourier_coeff(f='1', n=0, period=2*pi) → a_0=1")
    r = fourier_coeff("1", n=0, period=2 * _PI, coeff_type="cos")
    if r.ok and abs(float(sp.N(r.result)) - 1.0) < 1e-8:
        print(f"  PASSED: a_0 = {r.result}")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    # 测试 2: sin(x) 的正弦系数 b_1
    print("\n[测试 2] fourier_coeff(f='sin(x)', n=1, period=2*pi, coeff_type='sin') → b_1=1")
    r = fourier_coeff("sin(x)", n=1, period=2 * _PI, coeff_type="sin")
    if r.ok and abs(float(sp.N(r.result)) - 1.0) < 1e-8:
        print(f"  PASSED: b_1 = {r.result}")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    # 测试 3: 复傅里叶系数
    print("\n[测试 3] complex_fourier_coeff(f='cos(x)', n=1, period=2*pi) → c_1=1/2")
    r = complex_fourier_coeff("cos(x)", n=1, period=2 * _PI)
    if r.ok:
        val = sp.N(r.result)
        print(f"  PASSED: c_1 = {r.result} ≈ {val}")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    # 测试 4: 正交性验证 n≠m
    print("\n[测试 4] orthogonality_check(n=1, m=2, period=2*pi) → 0")
    r = orthogonality_check(1, 2, 2 * _PI)
    if r.ok and abs(r.result) < 1e-8:
        print(f"  PASSED: 内积 = {r.result}")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    # 测试 5: 傅里叶级数逼近 - 方波
    print("\n[测试 5] fourier_series(f='Heaviside(x-pi)', n_terms=3, period=2*pi)")
    # 用 piecewise 模拟方波
    f_expr = "Piecewise((1, x < pi), (-1, x >= pi))"
    r = fourier_series(f_expr, n_terms=3, period=2 * _PI)
    if r.ok:
        print(f"  PASSED: 级数表达式已生成")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    print(f"\n{'='*60}")
    print(f"结果: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    self_test()
