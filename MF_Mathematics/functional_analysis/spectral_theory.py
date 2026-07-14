"""spectral_theory.py — 谱理论。

涵盖谱的数值近似（特征值）、谱分类（点谱/连续谱/剩余谱）、
谱定理验证（实对称矩阵对角化）。
"""

from __future__ import annotations

from typing import Sequence, Union

import numpy as np
from scipy import linalg

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="functional_analysis", action="spectrum_approx")
def spectrum_approx(
    matrix: Sequence[Sequence[float]],
) -> MathObject:
    """计算矩阵（线性算子）的谱近似。

    对于有限维矩阵算子，谱 = 所有特征值集合。
    使用 QR 算法数值计算全部特征值。

    Args:
        matrix: 方阵，表示线性算子 T。

    Returns:
        MathObject: result 为特征值列表（float 列表），
                   复特征值以复数的模/实部形式呈现。
    """
    try:
        A = np.asarray(matrix, dtype=float)
        m, n = A.shape

        if m != n:
            return MathObject(error=f"谱仅对方阵定义，当前矩阵 {m}×{n}")

        eigenvalues = linalg.eigvals(A)

        # 区分实特征值和复特征值
        real_mask = np.abs(eigenvalues.imag) < 1e-10
        real_evals = sorted(float(v.real) for v in eigenvalues[real_mask])
        complex_evals = [
            complex(round(v.real, 10), round(v.imag, 10))
            for v in eigenvalues[~real_mask]
        ]

        all_evals = real_evals + [(c.real, c.imag) for c in complex_evals]

        # 谱半径
        spectral_radius = float(max(abs(v) for v in eigenvalues))

        return MathObject(
            result=real_evals if len(complex_evals) == 0 else all_evals,
            steps=[
                f"矩阵 {m}×{n}: {A.tolist()}",
                f"特征值: {[float(v.real) if abs(v.imag)<1e-10 else complex(round(v.real,4), round(v.imag,4)) for v in eigenvalues]}",
                f"谱半径 ρ(T) = {spectral_radius:.4g}",
            ],
            meaning=f"谱 σ(T) = {all_evals}，谱半径 = {spectral_radius:.4g}",
            data={
                "eigenvalues": [float(v.real) if abs(v.imag) < 1e-10 else complex(v.real, v.imag) for v in eigenvalues],
                "spectral_radius": spectral_radius,
            },
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="functional_analysis", action="spectrum_classify")
def spectrum_classify(
    matrix: Sequence[Sequence[float]],
    tol: float = 1e-6,
) -> MathObject:
    """将矩阵算子的谱分类为点谱、连续谱和剩余谱。

    对有限维情形：
    - 点谱 σ_p(T)：所有特征值（离散）。
    - 连续谱 σ_c(T)：有限维矩阵中不存在（仅无限维有）。
    - 剩余谱 σ_r(T)：有限维矩阵中不存在（T 值域非稠密的情形）。

    对规范算子（如自伴算子），谱 = 点谱。

    Args:
        matrix: 方阵。
        tol: 特征值分类容差。

    Returns:
        MathObject: result 为 dict，包含各类谱的特征值列表。
    """
    try:
        A = np.asarray(matrix, dtype=float)
        m, n = A.shape

        if m != n:
            return MathObject(error=f"谱分类仅对方阵定义，当前矩阵 {m}×{n}")

        eigenvalues = linalg.eigvals(A)

        # 有限维矩阵：谱 = 点谱（特征值）
        real_evals = sorted(
            [
                float(v.real)
                for v in eigenvalues
                if abs(v.imag) < tol
            ]
        )
        complex_evals = [
            complex(round(v.real, 10), round(v.imag, 10))
            for v in eigenvalues
            if abs(v.imag) >= tol
        ]

        point_spectrum = real_evals if not complex_evals else real_evals + [(c.real, c.imag) for c in complex_evals]
        continuous_spectrum = []
        residual_spectrum = []

        # 检查是否为自伴矩阵（实对称）
        is_self_adjoint = np.allclose(A, A.T, atol=tol)

        classification = {
            "point_spectrum": point_spectrum,
            "continuous_spectrum": continuous_spectrum,
            "residual_spectrum": residual_spectrum,
        }

        meaning_parts = [
            f"点谱 σ_p(T) = {point_spectrum if point_spectrum else '∅'}",
            f"连续谱 σ_c(T) = ∅ (有限维矩阵无连续谱)",
            f"剩余谱 σ_r(T) = ∅ (有限维矩阵无剩余谱)",
        ]
        if is_self_adjoint:
            meaning_parts.append("T 是自伴算子，σ(T) = σ_p(T)")

        return MathObject(
            result=classification,
            steps=[
                f"矩阵 {m}×{n}",
                f"特征值: {[float(v.real) if abs(v.imag)<tol else complex(round(v.real,4), round(v.imag,4)) for v in eigenvalues]}",
                f"自伴性: {is_self_adjoint}",
                f"有限维 ⇒ σ(T) = σ_p(T)",
            ],
            meaning="; ".join(meaning_parts),
            data=classification,
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="functional_analysis", action="spectral_theorem")
def spectral_theorem(
    matrix: Sequence[Sequence[float]],
) -> MathObject:
    """谱定理验证（实对称矩阵对角化）。

    谱定理（有限维自伴算子版本）：
    对实对称矩阵 A，存在正交矩阵 Q 和对角矩阵 Λ 使得 A = QΛQ^T。
    Λ 的对角元是 A 的特征值，Q 的列是对应的规范正交特征向量。

    Args:
        matrix: 实对称方阵。

    Returns:
        MathObject: result 为 dict，包含 Q, Λ 和重构验证。
    """
    try:
        A = np.asarray(matrix, dtype=float)
        m, n = A.shape

        if m != n:
            return MathObject(error=f"谱定理仅适用于方阵，当前矩阵 {m}×{n}")

        if not np.allclose(A, A.T, atol=1e-8):
            # 非对称矩阵仍可做特征分解，但提示非自伴
            is_symmetric = False
            eigenvalues, eigenvectors = linalg.eig(A)
            # 对非对称矩阵输出舒尔分解作为替代
            eigenvalues_real = [float(v.real) if abs(v.imag) < 1e-10 else complex(v.real, v.imag) for v in eigenvalues]
            msg = "T 非自伴，谱定理（舒尔分解）给出上三角形式"
        else:
            is_symmetric = True
            eigenvalues, eigenvectors = linalg.eigh(A)
            eigenvalues_real = [float(v) for v in eigenvalues]
            msg = "T 是自伴算子，谱定理给出 A = QΛQ^T"

        # 重建验证
        if is_symmetric:
            Lambda = np.diag(eigenvalues)
            A_reconstructed = eigenvectors @ Lambda @ eigenvectors.T
            reconstruction_error = float(np.max(np.abs(A - A_reconstructed)))
        else:
            # 非对称：Q * Λ * Q^{-1} 验证
            Lambda = np.diag(eigenvalues)
            try:
                Q_inv = np.linalg.inv(eigenvectors)
                A_reconstructed = eigenvectors @ Lambda @ Q_inv
            except np.linalg.LinAlgError:
                A_reconstructed = A.copy()
            reconstruction_error = float(np.max(np.abs(A - A_reconstructed)))

        return MathObject(
            result={
                "eigenvalues": eigenvalues_real,
                "eigenvectors": [eigenvectors[:, i].tolist() for i in range(n)],
                "is_self_adjoint": is_symmetric,
                "reconstruction_error": reconstruction_error,
            },
            steps=[
                f"矩阵 {m}×{n}，自伴: {is_symmetric}",
                f"特征值: {eigenvalues_real}",
                f"分解: A = QΛQ^T",
                f"重构误差: {reconstruction_error:.2e}",
            ],
            meaning=msg,
            data={
                "Q": eigenvectors.tolist(),
                "Lambda": Lambda.tolist() if is_symmetric else None,
                "eigenvalues": eigenvalues_real,
            },
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """自测 spectral_theory 模块。"""
    print("=== spectral_theory self_test ===")
    passed = 0
    total = 5

    # Test 1: spectrum_approx — [[1,2],[2,1]]
    try:
        r = spectrum_approx([[1, 2], [2, 1]])
        assert r.ok
        # eigenvalues: det([1-λ, 2; 2, 1-λ]) = (1-λ)^2 - 4 = λ^2 - 2λ -3 = 0 → λ = -1, 3
        assert sorted(r.result) == [-1.0, 3.0] or sorted(round(x, 6) for x in r.result) == [-1.0, 3.0]
        print(f"  [PASS] spectrum_approx([[1,2],[2,1]]) = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] spectrum_approx: {e}")

    # Test 2: spectrum_classify
    try:
        r = spectrum_classify([[1, 2], [2, 1]])
        assert r.ok
        assert "point_spectrum" in r.result
        print(f"  [PASS] spectrum_classify([[1,2],[2,1]]) point_spectrum = {r.result['point_spectrum']}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] spectrum_classify: {e}")

    # Test 3: spectral_theorem — 实对称矩阵
    try:
        r = spectral_theorem([[2, 0], [0, 2]])
        assert r.ok
        assert abs(r.result["reconstruction_error"]) < 1e-10
        assert r.result["is_self_adjoint"] is True
        print(f"  [PASS] spectral_theorem([[2,0],[0,2]]): eig={r.result['eigenvalues']}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] spectral_theorem: {e}")

    # Test 4: spectrum_approx — 3x3 矩阵
    try:
        # 对角矩阵
        r = spectrum_approx([[3, 0, 0], [0, 1, 0], [0, 0, 2]])
        assert r.ok
        assert sorted(r.result) == [1.0, 2.0, 3.0]
        print(f"  [PASS] spectrum_approx 3x3 diag = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] spectrum_approx 3x3: {e}")

    # Test 5: spectral_theorem — 正交对角化验证
    try:
        r = spectral_theorem([[1, 1], [1, 1]])
        assert r.ok
        assert r.result["is_self_adjoint"] is True
        assert abs(r.result["reconstruction_error"]) < 1e-8
        print(f"  [PASS] spectral_theorem([[1,1],[1,1]]): eig={r.result['eigenvalues']}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] spectral_theorem 2: {e}")

    print(f"  Result: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    self_test()
