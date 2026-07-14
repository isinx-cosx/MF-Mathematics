"""inner_product_spaces.py — 内积空间与希尔伯特空间。

涵盖函数内积、正交性判断、格拉姆-施密特正交化、希尔伯特空间判断。
"""

from __future__ import annotations

import math
from typing import Callable, Sequence, Tuple, Union

import numpy as np
import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


def _parse_function(
    expr: Union[str, Callable[[float], float]]
) -> Callable[[float], float]:
    """将表达式字符串或可调用对象转为数值函数。"""
    if callable(expr):
        return expr
    # 处理字符串表达式
    expr_str = str(expr)
    x = sp.Symbol("x")
    parsed = sp.sympify(expr_str)
    return sp.lambdify(x, parsed, "numpy")


@register(module="functional_analysis", action="inner_product")
def inner_product(
    f: Union[str, Callable[[float], float]],
    g: Union[str, Callable[[float], float]],
    domain: Tuple[float, float],
    n_points: int = 1000,
) -> MathObject:
    """计算两个函数在给定区间上的 L^2 内积。

    ⟨f, g⟩ = ∫_a^b f(x)·g(x) dx

    使用复合辛普森法则进行数值积分。

    Args:
        f: 第一个函数，表达式字符串或可调用对象。
        g: 第二个函数。
        domain: 积分区间 (a, b)。
        n_points: 积分采样点数（须为偶数，辛普森法则要求）。

    Returns:
        MathObject: result 为内积值 (float)。
    """
    try:
        a, b = domain
        f_fn = _parse_function(f)
        g_fn = _parse_function(g)

        if n_points % 2 == 1:
            n_points += 1

        x = np.linspace(a, b, n_points)
        h = (b - a) / (n_points - 1)
        y = f_fn(x) * g_fn(x)

        # 复合辛普森积分
        result_val = y[0] + y[-1] + 4.0 * np.sum(y[1:-1:2]) + 2.0 * np.sum(y[2:-2:2])
        result_val = float(result_val * h / 3.0)

        f_name = f if isinstance(f, str) else (f.__name__ if hasattr(f, "__name__") else "f")
        g_name = g if isinstance(g, str) else (g.__name__ if hasattr(g, "__name__") else "g")

        return MathObject(
            result=result_val,
            steps=[
                f"定义域: [{a}, {b}]",
                f"计算 ⟨{f_name}, {g_name}⟩ = ∫_{a}^{b} {f_name}(x)·{g_name}(x) dx",
                f"使用 {n_points} 点复合辛普森积分",
                f"内积值 = {result_val}",
            ],
            meaning=f"L^2[{a},{b}] 上 ⟨{f_name}, {g_name}⟩ = {result_val}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="functional_analysis", action="is_orthogonal")
def is_orthogonal(
    f: Union[str, Callable[[float], float]],
    g: Union[str, Callable[[float], float]],
    domain: Tuple[float, float],
    tol: float = 1e-6,
) -> MathObject:
    """判断两个函数在给定区间上是否正交。

    正交条件: ⟨f, g⟩ = 0。

    Args:
        f: 第一个函数。
        g: 第二个函数。
        domain: 积分区间 (a, b)。
        tol: 容差，内积绝对值小于此值视为正交。

    Returns:
        MathObject: result 为 bool。
    """
    try:
        ip = inner_product(f, g, domain)
        orthogonal = abs(ip.result) < tol

        return MathObject(
            result=orthogonal,
            steps=ip.steps + [f"|⟨f,g⟩| = {abs(ip.result):.6g} < tol={tol} → {'正交' if orthogonal else '不正交'}"],
            meaning=f"在 L^2{domain} 上{'正交' if orthogonal else '不正交'}，内积 = {ip.result}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="functional_analysis", action="gram_schmidt")
def gram_schmidt(
    vectors: Sequence[Sequence[float]],
    inner_product_fn: Union[str, Callable] = "dot",
) -> MathObject:
    """对一组向量执行格拉姆-施密特正交化。

    将线性无关向量组 {v₁, v₂, ..., vₙ} 转化为标准正交基 {e₁, e₂, ..., eₙ}。
    经典算法:
        u₁ = v₁,  e₁ = u₁ / ‖u₁‖
        u_k = v_k - Σ_{j=1}^{k-1} ⟨v_k, e_j⟩ e_j,  e_k = u_k / ‖u_k‖

    Args:
        vectors: 输入向量组（线性无关）。
        inner_product_fn: 内积函数，"dot" 使用标准点积，或可调用对象。

    Returns:
        MathObject: result 为标准正交基列表，data 包含 u_k 中间向量。
    """
    try:
        vecs = [np.asarray(v, dtype=float) for v in vectors]
        n = len(vecs)

        if inner_product_fn == "dot":
            ip = lambda a, b: float(np.dot(a, b))
            ip_name = "标准点积"
        else:
            ip = inner_product_fn
            ip_name = "自定义内积"

        orthonormal = []
        u_list = []

        for k in range(n):
            vk = vecs[k].copy()
            uk = vk.copy()

            # 减去在之前正交基上的投影
            for j in range(k):
                proj = ip(vk, orthonormal[j]) * orthonormal[j]
                uk = uk - proj

            norm_uk = float(np.sqrt(ip(uk, uk)))
            if norm_uk < 1e-12:
                return MathObject(error=f"第 {k+1} 个向量与之前的线性相关")

            ek = uk / norm_uk
            orthonormal.append(ek)
            u_list.append(uk)

        return MathObject(
            result=[e.tolist() for e in orthonormal],
            steps=[
                f"输入 {n} 个向量",
                f"内积类型: {ip_name}",
                f"逐项执行格拉姆-施密特正交化",
                f"得到 {n} 个标准正交向量",
            ],
            meaning=f"通过格拉姆-施密特正交化得到 {n} 个标准正交基向量",
            data={
                "orthonormal_basis": [e.tolist() for e in orthonormal],
                "intermediate": [u.tolist() for u in u_list],
            },
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="functional_analysis", action="is_hilbert")
def is_hilbert(space: str, dimension: int = -1) -> MathObject:
    """判断给定空间是否为希尔伯特空间（概念性占位）。

    希尔伯特空间 = 完备的内积空间。
    有限维内积空间（如 R^n, C^n）自动是希尔伯特空间。

    Args:
        space: 空间名称，如 "R^n"、"L^2[0,1]"、"l^2"。
        dimension: 维度（-1 表示无限维）。

    Returns:
        MathObject: result 为 bool。
    """
    try:
        space_lower = space.lower()

        hilbert_spaces = {
            "r^n": True,
            "c^n": True,
            "l^2": True,
            "l^2(n)": True,
            "l^2(z)": True,
            "l^2(r)": True,
            "sobolev h^k": True,
            "hardy h^2": True,
        }

        not_hilbert = {
            "c[0,1] under l^2": False,
            "l^p for p≠2": False,
        }

        if space_lower in hilbert_spaces:
            result_val = True
            reason = f"{space} 是完备的内积空间，为希尔伯特空间。"
        elif space_lower in not_hilbert:
            result_val = False
            reason = f"{space} 不是希尔伯特空间（缺少内积或完备性）。"
        else:
            if dimension > 0 and dimension < float("inf"):
                result_val = True
                reason = f"{space} 是有限维内积空间，自动完备，为希尔伯特空间。"
            else:
                result_val = False
                reason = f"{space} 无限维，无法自动判定是否为希尔伯特空间。"

        return MathObject(
            result=result_val,
            steps=[f"空间: {space}", f"维度: {'无限' if dimension < 0 else dimension}"],
            meaning=reason,
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """自测 inner_product_spaces 模块。"""
    print("=== inner_product_spaces self_test ===")
    passed = 0
    total = 5

    # Test 1: inner_product — ⟨sin, cos⟩ on [0, 2π] = 0
    try:
        r = inner_product("sin(x)", "cos(x)", (0, 2 * math.pi), n_points=2000)
        assert r.ok
        assert abs(r.result) < 1e-4, f"Expected ~0, got {r.result}"
        print(f"  [PASS] inner_product(sin, cos, [0,2π]) = {r.result:.6g}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] inner_product sin·cos: {e}")

    # Test 2: is_orthogonal — sin 和 cos 在 [0,2π] 正交
    try:
        r = is_orthogonal("sin(x)", "cos(x)", (0, 2 * math.pi), tol=1e-4)
        assert r.ok
        assert r.result == True
        print(f"  [PASS] is_orthogonal(sin, cos, [0,2π]) = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] is_orthogonal: {e}")

    # Test 3: gram_schmidt — [(1,1), (1,0)]
    try:
        r = gram_schmidt([(1, 1), (1, 0)], inner_product_fn="dot")
        assert r.ok
        basis = r.result
        # 第一个标准正交向量: (1/√2, 1/√2)
        assert abs(basis[0][0] - 1.0 / np.sqrt(2)) < 1e-10
        # 正交性检验
        assert abs(np.dot(basis[0], basis[1])) < 1e-10
        # 归一化检验
        assert abs(np.linalg.norm(basis[0]) - 1.0) < 1e-10
        assert abs(np.linalg.norm(basis[1]) - 1.0) < 1e-10
        print(f"  [PASS] gram_schmidt([(1,1),(1,0)]) → {basis}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] gram_schmidt: {e}")

    # Test 4: is_hilbert
    try:
        r = is_hilbert("R^n", dimension=5)
        assert r.ok
        assert r.result is True
        print(f"  [PASS] is_hilbert('R^n', 5) = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] is_hilbert: {e}")

    # Test 5: inner_product — ⟨sin, sin⟩ on [0,π] = π/2
    try:
        r = inner_product("sin(x)", "sin(x)", (0, math.pi))
        assert r.ok
        assert abs(r.result - math.pi / 2) < 0.01
        print(f"  [PASS] inner_product(sin, sin, [0,π]) = {r.result:.6g}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] inner_product sin²: {e}")

    print(f"  Result: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    self_test()
