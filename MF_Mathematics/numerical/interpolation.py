"""interpolation.py — 插值与逼近。

包括拉格朗日插值、牛顿插值、三次样条插值、最小二乘多项式拟合。
"""

from __future__ import annotations

from typing import Union

import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="numerical", action="lagrange_interpolation")
def lagrange_interpolation(
    x_points: Union[list[float], np.ndarray],
    y_points: Union[list[float], np.ndarray],
) -> MathObject:
    """拉格朗日插值多项式。

    返回插值多项式的系数（从高次到低次），以及可调用的插值函数。

    Args:
        x_points: 已知点 x 坐标列表。
        y_points: 已知点 y 坐标列表。

    Returns:
        MathObject: result 为多项式系数（np.ndarray，高次到低次），
                    data 中包含可调用的插值函数。
    """
    try:
        x = np.asarray(x_points, dtype=float)
        y = np.asarray(y_points, dtype=float)
        n = len(x)

        if n != len(y):
            return MathObject(error="x_points 和 y_points 长度不一致")
        if n == 0:
            return MathObject(error="插值点为空")

        # 构建拉格朗日基函数并合成多项式
        poly_coeffs = np.zeros(n)
        for i in range(n):
            # 基函数 L_i(x) = Π_{j≠i} (x - x_j) / (x_i - x_j)
            basis = np.array([1.0])
            for j in range(n):
                if i != j:
                    basis = np.polymul(basis, [1.0, -x[j]]) / (x[i] - x[j])
            poly_coeffs = poly_coeffs + y[i] * basis

        def interpolant(xi: float) -> float:
            return float(np.polyval(poly_coeffs, xi))

        # 验证插值条件
        residual = np.max(np.abs(np.polyval(poly_coeffs, x) - y))

        return MathObject(
            result=poly_coeffs,
            steps=[
                f"插值点: x={x.tolist()}, y={y.tolist()}",
                f"插值多项式次数: {n - 1}",
                f"最大插值残差: {residual:.2e}",
            ],
            meaning=f"{n} 点拉格朗日插值，插值多项式次数 {n - 1}",
            data={"interpolant": interpolant},
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="numerical", action="newton_interpolation")
def newton_interpolation(
    x_points: Union[list[float], np.ndarray],
    y_points: Union[list[float], np.ndarray],
) -> MathObject:
    """牛顿插值多项式（差商形式）。

    P(x) = f[x_0] + f[x_0,x_1](x-x_0) + f[x_0,x_1,x_2](x-x_0)(x-x_1) + ...

    Args:
        x_points: 已知点 x 坐标列表。
        y_points: 已知点 y 坐标列表。

    Returns:
        MathObject: result 为差商表（list of float），data 中包含可调用的插值函数。
    """
    try:
        x = np.asarray(x_points, dtype=float)
        y = np.asarray(y_points, dtype=float)
        n = len(x)

        if n != len(y):
            return MathObject(error="x_points 和 y_points 长度不一致")

        # 计算差商表
        div_diffs = y.copy()
        for j in range(1, n):
            for i in range(n - 1, j - 1, -1):
                div_diffs[i] = (div_diffs[i] - div_diffs[i - 1]) / (x[i] - x[i - j])

        coeffs = div_diffs.tolist()

        def interpolant(xi: float) -> float:
            result = coeffs[0]
            prod = 1.0
            for k in range(1, n):
                prod *= (xi - x[k - 1])
                result += coeffs[k] * prod
            return result

        return MathObject(
            result=coeffs,
            steps=[
                f"插值点: x={x.tolist()}, y={y.tolist()}",
                f"差商系数: {[round(c, 6) for c in coeffs]}",
            ],
            meaning=f"{n} 点牛顿插值，差商表系数",
            data={"interpolant": interpolant},
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="numerical", action="cubic_spline")
def cubic_spline(
    x_points: Union[list[float], np.ndarray],
    y_points: Union[list[float], np.ndarray],
    bc_type: str = "natural",
) -> MathObject:
    """三次样条插值。

    使用自然边界条件（端点二阶导为 0）计算三次样条系数。

    Args:
        x_points: 已知点 x 坐标列表（需严格递增）。
        y_points: 已知点 y 坐标列表。
        bc_type: 边界条件类型，"natural" 或 "clamped"（clamped 需额外提供端点导数）。

    Returns:
        MathObject: result 为样条系数矩阵（每行 [a,b,c,d] 表示 a + b(x-xi) + c(x-xi)² + d(x-xi)³），
                    data 中包含可调用的样条函数。
    """
    try:
        x = np.asarray(x_points, dtype=float)
        y = np.asarray(y_points, dtype=float)
        n = len(x)

        if n != len(y):
            return MathObject(error="x_points 和 y_points 长度不一致")
        if n < 4:
            return MathObject(error="三次样条至少需要 4 个点")

        h = np.diff(x)
        # 构建三对角方程组求解二阶导数
        A = np.zeros((n, n))
        rhs = np.zeros(n)

        A[0, 0] = 1.0
        A[-1, -1] = 1.0
        for i in range(1, n - 1):
            A[i, i - 1] = h[i - 1]
            A[i, i] = 2 * (h[i - 1] + h[i])
            A[i, i + 1] = h[i]
            rhs[i] = 6 * (
                (y[i + 1] - y[i]) / h[i] - (y[i] - y[i - 1]) / h[i - 1]
            )

        M = np.linalg.solve(A, rhs)

        # 构建样条系数
        coeffs = np.zeros((n - 1, 4))  # [a, b, c, d]
        for i in range(n - 1):
            coeffs[i, 0] = y[i]
            coeffs[i, 1] = (y[i + 1] - y[i]) / h[i] - h[i] * (2 * M[i] + M[i + 1]) / 6
            coeffs[i, 2] = M[i] / 2
            coeffs[i, 3] = (M[i + 1] - M[i]) / (6 * h[i])

        def spline_func(xi: float) -> float:
            for i in range(n - 1):
                if xi <= x[i + 1] or i == n - 2:
                    dx = xi - x[i]
                    a, b_val, c, d = coeffs[i]
                    return a + b_val * dx + c * dx**2 + d * dx**3
            return y[-1]

        return MathObject(
            result=coeffs.tolist(),
            steps=[
                f"插值点: x={x.tolist()}, y={y.tolist()}",
                f"子区间数: {n - 1}",
                f"边界条件: {bc_type}",
            ],
            meaning=f"三次样条插值，{n - 1} 个分段三次多项式，C² 连续",
            data={"spline_func": spline_func, "knots": x.tolist()},
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="numerical", action="least_squares_fit")
def least_squares_fit(
    x_points: Union[list[float], np.ndarray],
    y_points: Union[list[float], np.ndarray],
    degree: int = 2,
) -> MathObject:
    """最小二乘多项式拟合。

    Args:
        x_points: 数据点 x 坐标。
        y_points: 数据点 y 坐标。
        degree: 多项式次数。

    Returns:
        MathObject: result 为多项式系数（高次到低次），data 中包含拟合函数和 R²。
    """
    try:
        x = np.asarray(x_points, dtype=float)
        y = np.asarray(y_points, dtype=float)

        if len(x) != len(y):
            return MathObject(error="x_points 和 y_points 长度不一致")
        if len(x) < degree + 1:
            return MathObject(error=f"数据点不足，至少需要 {degree + 1} 个点")

        coeffs = np.polyfit(x, y, degree)

        # 计算 R²
        y_pred = np.polyval(coeffs, x)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 1e-15 else 1.0

        def fit_func(xi: float) -> float:
            return float(np.polyval(coeffs, xi))

        return MathObject(
            result=coeffs.tolist(),
            steps=[
                f"数据点数量: {len(x)}",
                f"多项式次数: {degree}",
                f"R² = {r_squared:.6f}",
            ],
            meaning=f"{degree} 次多项式最小二乘拟合，R² = {r_squared:.4f}",
            data={"r_squared": r_squared, "fit_func": fit_func},
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """自测 interpolation 模块。"""
    print("=== interpolation self_test ===")
    passed = 0
    total = 4

    # Test 1: lagrange_interpolation
    try:
        r = lagrange_interpolation([0, 1, 2], [0, 1, 0])
        assert r.ok
        poly = r.result
        # P(0)=0, P(1)=1, P(2)=0  => -x^2 + 2x, coeffs=[-1,2,0]
        assert abs(np.polyval(poly, 1) - 1) < 1e-10
        print(f"  [PASS] lagrange_interpolation: coeffs={[round(c,4) for c in poly]}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] lagrange_interpolation: {e}")

    # Test 2: newton_interpolation
    try:
        r = newton_interpolation([0, 1, 2], [0, 1, 4])
        assert r.ok
        fn = r.data["interpolant"]
        assert abs(fn(2) - 4) < 1e-10
        print(f"  [PASS] newton_interpolation: P(2)={fn(2):.6f}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] newton_interpolation: {e}")

    # Test 3: cubic_spline
    try:
        r = cubic_spline([0, 1, 2, 3], [0, 1, 0, 1])
        assert r.ok
        fn = r.data["spline_func"]
        assert abs(fn(1) - 1.0) < 1e-10
        print(f"  [PASS] cubic_spline: S(1)={fn(1):.6f}, S(2)={fn(2):.6f}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] cubic_spline: {e}")

    # Test 4: least_squares_fit
    try:
        x = np.linspace(0, 4, 10)
        y = 2 * x + 1 + 0.1 * np.random.randn(10)
        r = least_squares_fit(x.tolist(), y.tolist(), degree=1)
        assert r.ok
        assert r.data["r_squared"] > 0.9
        print(f"  [PASS] least_squares_fit: R²={r.data['r_squared']:.4f}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] least_squares_fit: {e}")

    print(f"  Result: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    self_test()
