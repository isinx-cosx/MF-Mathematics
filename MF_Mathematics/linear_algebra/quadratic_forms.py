"""二次型与正定性 — 二次型计算、标准形、正定性判定。

依赖: sympy, numpy
"""

from __future__ import annotations
from MF_Mathematics.core.helpers import to_matrix

from typing import Any, Dict, List, Tuple, Union

import numpy as np
import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register
def _parse_vars(
    x: Union[str, List[str], List[sp.Symbol]],
    n: int,
) -> sp.Matrix:
    """解析变量列表，转为 sympy 列向量。"""
    if isinstance(x, list):
        if len(x) > 0 and isinstance(x[0], sp.Symbol):
            return sp.Matrix(x)
        return sp.Matrix([sp.Symbol(str(v)) for v in x])
    if isinstance(x, str):
        # 如 "x,y,z"
        names = [name.strip() for name in x.split(",")]
        return sp.Matrix([sp.Symbol(name) for name in names])

    # 自动生成 x0, x1, ...
    return sp.Matrix([sp.Symbol(f"x{i}") for i in range(n)])


@register(module="linear_algebra", action="quadratic_form")
def quadratic_form(
    matrix: Union[List[List[float]], np.ndarray],
    x: Union[str, List[str], List[sp.Symbol], None] = None,
) -> MathObject:
    """计算二次型 x^T A x。

    Args:
        matrix: 对称矩阵 A。
        x: 变量列表（字符串如 "x,y" 或符号列表），不传则自动生成 x0,x1,...

    Returns:
        MathObject，result 为二次型表达式。
    """
    try:
        A = to_matrix(matrix)
        n = A.rows

        if A.rows != A.cols:
            return MathObject(error="矩阵必须是方阵")

        x_vec = _parse_vars(x, n) if x is not None else _parse_vars(None, n)
        qf = (x_vec.T * A * x_vec)[0, 0]
        qf_simplified = sp.expand(qf)

        return MathObject(
            result=str(qf_simplified),
            steps=[
                f"对称矩阵 A:\n{A}",
                f"变量向量 x = {[str(s) for s in x_vec]}",
                f"二次型 x^T A x = {qf}",
                f"展开: {qf_simplified}",
            ],
            meaning=f"二次型: {qf_simplified}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="standard_form")
def standard_form(
    matrix: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """通过正交变换将二次型化为标准形。

    通过特征值分解得到正交变换矩阵 Q，使得 Q^T A Q = diag(λ1,...,λn)，
    标准形为 λ1 y1^2 + ... + λn yn^2。

    Args:
        matrix: 对称矩阵 A。

    Returns:
        MathObject，result 包含特征值、标准形表达式和正交变换矩阵。
    """
    try:
        A = to_matrix(matrix)
        n = A.rows

        if A.rows != A.cols:
            return MathObject(error="矩阵必须是方阵")

        # 检查对称性
        if A != A.T:
            return MathObject(error="矩阵必须是对称矩阵才能用正交变换化为标准形")

        # 特征值分解
        eigendata = A.eigenvects()

        eigenvalues_list = []
        eigenvectors_list = []

        for val, mult, basis_vecs in eigendata:
            eigenvalues_list.extend([float(val) if val.is_Number else val] * len(basis_vecs))
            for vec in basis_vecs:
                eigenvectors_list.append(vec)

        # 对特征向量做 Gram-Schmidt 得到正交矩阵 Q
        ortho_vecs = []
        for v in eigenvectors_list:
            w = v
            for u in ortho_vecs:
                proj = (v.dot(u)) * u
                w = w - proj
            w_norm = w.norm()
            if abs(float(w_norm)) > 1e-15:
                ortho_vecs.append(w / w_norm)

        Q = sp.Matrix.hstack(*ortho_vecs) if ortho_vecs else sp.eye(n)

        # 标准形表达式
        y_vars = [f"y{i+1}" for i in range(n)]
        terms = []
        for i, lam in enumerate(eigenvalues_list):
            lam_val = lam
            terms.append(f"{lam_val}*{y_vars[i]}^2")

        standard_expr = " + ".join(terms)

        return MathObject(
            result={
                "standard_form": standard_expr,
                "eigenvalues": eigenvalues_list,
                "orthogonal_matrix": Q.tolist(),
            },
            steps=[
                f"对称矩阵 A:\n{A}",
                f"特征值: {eigenvalues_list}",
                f"正交矩阵 Q:\n{Q}",
                "验证: Q^T A Q 应为对角阵",
                f"标准形: {standard_expr}",
            ],
            meaning=f"二次型的标准形: {standard_expr}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="is_positive_definite")
def is_positive_definite(
    matrix: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """用顺序主子式判断矩阵的正定性。

    若所有顺序主子式 > 0，则矩阵正定。

    Args:
        matrix: 对称矩阵。

    Returns:
        MathObject，result 为 bool。
    """
    try:
        A = to_matrix(matrix)
        n = A.rows

        if A.rows != A.cols:
            return MathObject(error="矩阵必须是方阵")

        # 检查对称性（Sylvester 准则要求对称矩阵）
        if A != A.T:
            return MathObject(error="矩阵必须是对称矩阵才能使用顺序主子式判定正定性",
                              result=False, meaning="Sylvester 准则要求矩阵对称")

        principal_minors = []
        all_positive = True

        for k in range(1, n + 1):
            sub_A = A[:k, :k]
            det_val = sub_A.det()
            principal_minors.append(float(det_val))
            if float(det_val) <= 0:
                all_positive = False

        return MathObject(
            result=all_positive,
            steps=[
                f"矩阵 A:\n{A}",
                "顺序主子式:",
            ]
            + [
                f"  Δ{k} = det(A_{k}×{k}) = {principal_minors[k-1]}"
                + (" > 0" if principal_minors[k-1] > 0 else " <= 0")
                for k in range(1, n + 1)
            ]
            + [
                f"所有顺序主子式 > 0: {all_positive}",
            ],
            meaning=(
                "矩阵正定" if all_positive else "矩阵非正定"
            ),
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="is_negative_definite")
def is_negative_definite(
    matrix: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """判断矩阵是否负定。

    奇数阶顺序主子式 < 0，偶数阶顺序主子式 > 0。

    Args:
        matrix: 对称矩阵。

    Returns:
        MathObject，result 为 bool。
    """
    try:
        A = to_matrix(matrix)
        n = A.rows

        if A.rows != A.cols:
            return MathObject(error="矩阵必须是方阵")

        # 检查对称性
        if A != A.T:
            return MathObject(error="矩阵必须是对称矩阵才能使用顺序主子式判定负定性",
                              result=False, meaning="Sylvester 准则要求矩阵对称")

        principal_minors = []
        is_neg_def = True

        for k in range(1, n + 1):
            sub_A = A[:k, :k]
            det_val = float(sub_A.det())
            principal_minors.append(det_val)

            if k % 2 == 1:  # 奇数阶
                if det_val >= 0:
                    is_neg_def = False
            else:  # 偶数阶
                if det_val <= 0:
                    is_neg_def = False

        return MathObject(
            result=is_neg_def,
            steps=[
                f"矩阵 A:\n{A}",
                "顺序主子式 (负定条件: 奇<0, 偶>0):",
            ]
            + [
                f"  Δ{k} = {principal_minors[k-1]}"
                + (" (符合)" if (k % 2 == 1 and principal_minors[k-1] < 0)
                   or (k % 2 == 0 and principal_minors[k-1] > 0)
                   else " (不符合)")
                for k in range(1, n + 1)
            ]
            + [
                f"负定: {is_neg_def}",
            ],
            meaning="矩阵负定" if is_neg_def else "矩阵非负定",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="is_indefinite")
def is_indefinite(
    matrix: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """判断矩阵是否不定（既非正定也非负定且非半定）。

    有正特征值和负特征值。

    Args:
        matrix: 对称矩阵。

    Returns:
        MathObject，result 为 bool。
    """
    try:
        A = to_matrix(matrix)
        n = A.rows

        if A.rows != A.cols:
            return MathObject(error="矩阵必须是方阵")

        eigvals = A.eigenvals()
        has_positive = False
        has_negative = False
        has_zero = False

        for val in eigvals.keys():
            fval = float(val)
            if fval > 1e-12:
                has_positive = True
            elif fval < -1e-12:
                has_negative = True
            else:
                has_zero = True

        is_indef = has_positive and has_negative

        return MathObject(
            result=is_indef,
            steps=[
                f"矩阵 A:\n{A}",
                f"特征值: {[float(v) for v in eigvals.keys()]}",
                f"有正特征值: {has_positive}",
                f"有负特征值: {has_negative}",
                f"不定: {is_indef} (同时有正负特征值)",
            ],
            meaning=(
                "矩阵不定" if is_indef
                else "矩阵非不定（可能为正定、负定或半定）"
            ),
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> None:
    """模块自测。"""
    print("=== quadratic_forms self_test ===")

    # 1. quadratic_form — x^T A x = x^2 + y^2
    r1 = quadratic_form([[1, 0], [0, 1]], x="x,y")
    assert r1.ok, f"quadratic_form error: {r1.error}"
    assert "x**2" in r1.result and "y**2" in r1.result
    print("  test1 (quadratic_form): PASSED")

    # 2. is_positive_definite — [[2,-1],[-1,2]] → True
    r2 = is_positive_definite([[2, -1], [-1, 2]])
    assert r2.ok, f"is_positive_definite error: {r2.error}"
    assert r2.result is True, f"Expected True, got {r2.result}"
    print("  test2 (is_positive_definite): PASSED")

    # 3. is_positive_definite — 非正定
    r3 = is_positive_definite([[1, 2], [2, 1]])
    assert r3.ok, f"is_positive_definite error: {r3.error}"
    assert r3.result is False
    print("  test3 (is_positive_definite False): PASSED")

    # 4. is_negative_definite
    r4 = is_negative_definite([[-2, 0], [0, -3]])
    assert r4.ok, f"is_negative_definite error: {r4.error}"
    assert r4.result is True
    print("  test4 (is_negative_definite): PASSED")

    # 5. is_indefinite
    r5 = is_indefinite([[1, 0], [0, -1]])
    assert r5.ok, f"is_indefinite error: {r5.error}"
    assert r5.result is True
    print("  test5 (is_indefinite): PASSED")

    # 6. standard_form
    r6 = standard_form([[2, 0], [0, 3]])
    assert r6.ok, f"standard_form error: {r6.error}"
    assert "2" in r6.result["standard_form"]
    print("  test6 (standard_form): PASSED")

    print("=== quadratic_forms: ALL PASSED ===\n")


if __name__ == "__main__":
    self_test()
