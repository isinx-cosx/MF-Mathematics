# -*- coding: utf-8 -*-
"""core/helpers.py — 跨子包共享的工具函数。

提取自各数学子包中重复定义的辅助函数，避免代码重复。
"""

from __future__ import annotations

from typing import Callable, List, Union

import numpy as np
import sympy as sp


def to_sympy(expr: Union[str, sp.Expr]) -> sp.Expr:
    """将字符串或 sympy 表达式统一转为 sympy 表达式。"""
    if isinstance(expr, sp.Expr):
        return expr
    return sp.sympify(str(expr), locals=_SYMPIFY_LOCALS)


def to_matrix(mat: Union[List[List[float]], np.ndarray, sp.Matrix]) -> sp.Matrix:
    """统一转为 sympy Matrix。"""
    if isinstance(mat, sp.Matrix):
        return mat
    return sp.Matrix(mat)


def to_vector(vec: Union[List[float], np.ndarray, sp.Matrix]) -> sp.Matrix:
    """统一转为 sympy 列向量。"""
    if isinstance(vec, sp.Matrix):
        return vec
    v = sp.Matrix(vec)
    if v.rows == 1:
        return v.T  # 行向量 → 列向量
    return v


def parse_func(
    f: Union[str, Callable], var: sp.Symbol | None = None
) -> sp.Expr:
    """将字符串或可调用对象解析为 SymPy 表达式。"""
    if var is None:
        var = sp.Symbol("x", real=True)
    if isinstance(f, str):
        return sp.sympify(
            f,
            locals={
                "x": var, "pi": sp.pi, "PI": sp.pi,
                "n": sp.Symbol("n", integer=True, positive=True),
                "y": sp.Symbol("y", real=True),
                "z": sp.Symbol("z", real=True),
                # 常用函数别名
                "derivative": lambda expr, v=None: sp.diff(expr, v if v is not None else var),
                "integrate": lambda expr, v=None, a=None, b=None: (
                    sp.integrate(expr, (v if v is not None else var, a, b))
                    if a is not None and b is not None
                    else sp.integrate(expr, v if v is not None else var)
                ),
            },
        )
    elif callable(f):
        return f(var)
    else:
        raise TypeError(f"f 必须为字符串或可调用对象，当前类型: {type(f)}")

# ── sympify 通用 locals ──────────────────────────────────

# 共享的 sympify locals，避免各处重复声明
_SYMPIFY_LOCALS = {
    "pi": sp.pi, "PI": sp.pi,
    "n": sp.Symbol("n", integer=True, positive=True),
    "y": sp.Symbol("y", real=True),
    "z": sp.Symbol("z", real=True),
    "derivative": lambda expr, v=None: sp.diff(expr, v if v is not None else sp.Symbol("x", real=True)),
    "integrate": lambda expr, v=None, a=None, b=None: (
        sp.integrate(expr, (v if v is not None else sp.Symbol("x", real=True), a, b))
        if a is not None and b is not None
        else sp.integrate(expr, v if v is not None else sp.Symbol("x", real=True))
    ),
}

def safe_sympify(s: str) -> sp.Expr:
    """使用共享 locals 安全解析字符串表达式。"""
    return sp.sympify(s, locals=_SYMPIFY_LOCALS)
