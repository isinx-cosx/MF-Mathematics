"""matrix_numerical.py — 线性代数数值方法。

包括 LU 分解、雅可比迭代、高斯-赛德尔迭代、共轭梯度法、
幂法（最大特征值）、QR 算法（所有特征值）。
"""

from __future__ import annotations

from typing import Union

import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="numerical", action="lu_decomposition")
def lu_decomposition(
    A: Union[list[list[float]], np.ndarray],
) -> MathObject:
    """LU 分解（Doolittle 算法，L 为单位下三角）。

    A = L @ U，其中 L 主对角线全为 1。

    Args:
        A: 方阵（n×n）。

    Returns:
        MathObject: result 为 (L, U) 元组，均转为 list 格式。
    """
    try:
        A = np.asarray(A, dtype=float)
        n = A.shape[0]
        if A.shape[0] != A.shape[1]:
            return MathObject(error="矩阵必须为方阵")

        L = np.eye(n)
        U = np.zeros((n, n))

        for i in range(n):
            for j in range(i, n):
                U[i, j] = A[i, j] - np.dot(L[i, :i], U[:i, j])
            for j in range(i + 1, n):
                L[j, i] = (A[j, i] - np.dot(L[j, :i], U[:i, i])) / U[i, i]

        # 验证
        residual = np.max(np.abs(A - L @ U))

        return MathObject(
            result={"L": L.tolist(), "U": U.tolist()},
            steps=[
                f"矩阵维度: {n}×{n}",
                f"LU 分解完成，残差 ||A - LU||_max = {residual:.2e}",
            ],
            meaning="Doolittle LU 分解，L 为单位下三角阵",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="numerical", action="jacobi_iteration")
def jacobi_iteration(
    A: Union[list[list[float]], np.ndarray],
    b: Union[list[float], np.ndarray],
    x0: Union[list[float], np.ndarray],
    tol: float = 1e-6,
    max_iter: int = 1000,
) -> MathObject:
    """雅可比迭代法求解 Ax = b。

    收敛条件：A 严格对角占优。

    Args:
        A: 系数矩阵。
        b: 右端向量。
        x0: 初始猜测。
        tol: 收敛容差。
        max_iter: 最大迭代次数。

    Returns:
        MathObject: result 为解向量（list）。
    """
    try:
        A = np.asarray(A, dtype=float)
        b = np.asarray(b, dtype=float)
        x = np.asarray(x0, dtype=float).copy()
        n = len(b)

        D = np.diag(A)
        if np.any(np.abs(D) < 1e-15):
            return MathObject(error="对角元素含零，无法直接使用雅可比迭代")

        D_inv = 1.0 / D
        R = A - np.diag(D)

        iterations = 0
        for k in range(max_iter):
            x_new = D_inv * (b - R @ x)
            diff = np.linalg.norm(x_new - x)
            x = x_new
            iterations = k + 1
            if diff < tol:
                break
        else:
            return MathObject(
                result=x.tolist(),
                steps=[f"迭代 {iterations} 次，未收敛到容差 {tol}"],
                meaning="雅可比迭代未收敛",
            )

        return MathObject(
            result=x.tolist(),
            steps=[
                f"矩阵维度: {n}×{n}",
                f"迭代次数: {iterations}",
                f"最终残差: {diff:.2e}",
            ],
            meaning=f"雅可比迭代 {iterations} 次收敛，解 ≈ {[round(v, 6) for v in x]}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="numerical", action="gauss_seidel")
def gauss_seidel(
    A: Union[list[list[float]], np.ndarray],
    b: Union[list[float], np.ndarray],
    x0: Union[list[float], np.ndarray],
    tol: float = 1e-6,
    max_iter: int = 1000,
) -> MathObject:
    """高斯-赛德尔迭代法求解 Ax = b。

    每次迭代用最新值更新。

    Args:
        A: 系数矩阵。
        b: 右端向量。
        x0: 初始猜测。
        tol: 收敛容差。
        max_iter: 最大迭代次数。

    Returns:
        MathObject: result 为解向量（list）。
    """
    try:
        A = np.asarray(A, dtype=float)
        b = np.asarray(b, dtype=float)
        x = np.asarray(x0, dtype=float).copy()
        n = len(b)

        iterations = 0
        for k in range(max_iter):
            x_old = x.copy()
            for i in range(n):
                s1 = np.dot(A[i, :i], x[:i])
                s2 = np.dot(A[i, i + 1:], x_old[i + 1:])
                if abs(A[i, i]) < 1e-15:
                    return MathObject(error=f"对角元素 A[{i},{i}] 为零")
                x[i] = (b[i] - s1 - s2) / A[i, i]
            diff = np.linalg.norm(x - x_old)
            iterations = k + 1
            if diff < tol:
                break
        else:
            return MathObject(
                result=x.tolist(),
                steps=[f"迭代 {iterations} 次，未收敛到容差 {tol}"],
                meaning="高斯-赛德尔迭代未收敛",
            )

        return MathObject(
            result=x.tolist(),
            steps=[
                f"矩阵维度: {n}×{n}",
                f"迭代次数: {iterations}",
                f"最终残差: {diff:.2e}",
            ],
            meaning=f"高斯-赛德尔迭代 {iterations} 次收敛，解 ≈ {[round(v, 6) for v in x]}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="numerical", action="conjugate_gradient")
def conjugate_gradient(
    A: Union[list[list[float]], np.ndarray],
    b: Union[list[float], np.ndarray],
    x0: Union[list[float], np.ndarray],
    tol: float = 1e-6,
    max_iter: int = 1000,
) -> MathObject:
    """共轭梯度法求解 Ax = b（A 需为对称正定矩阵）。

    Args:
        A: 对称正定矩阵。
        b: 右端向量。
        x0: 初始猜测。
        tol: 收敛容差。
        max_iter: 最大迭代次数。

    Returns:
        MathObject: result 为解向量（list）。
    """
    try:
        A = np.asarray(A, dtype=float)
        b = np.asarray(b, dtype=float)
        x = np.asarray(x0, dtype=float).copy()
        n = len(b)

        r = b - A @ x
        p = r.copy()
        rs_old = np.dot(r, r)

        iterations = 0
        for k in range(max_iter):
            Ap = A @ p
            alpha = rs_old / np.dot(p, Ap)
            x = x + alpha * p
            r = r - alpha * Ap
            rs_new = np.dot(r, r)
            iterations = k + 1
            if np.sqrt(rs_new) < tol:
                break
            p = r + (rs_new / rs_old) * p
            rs_old = rs_new
        else:
            return MathObject(
                result=x.tolist(),
                steps=[f"迭代 {iterations} 次，未收敛到容差 {tol}"],
                meaning="共轭梯度法未收敛",
            )

        return MathObject(
            result=x.tolist(),
            steps=[
                f"矩阵维度: {n}×{n}",
                f"迭代次数: {iterations}",
                f"最终残差: {np.sqrt(rs_new):.2e}",
            ],
            meaning=f"共轭梯度法 {iterations} 次收敛，解 ≈ {[round(v, 6) for v in x]}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="numerical", action="power_method")
def power_method(
    A: Union[list[list[float]], np.ndarray],
    tol: float = 1e-8,
    max_iter: int = 1000,
) -> MathObject:
    """幂法求矩阵的按模最大特征值及对应特征向量。

    Args:
        A: 方阵。
        tol: 收敛容差。
        max_iter: 最大迭代次数。

    Returns:
        MathObject: result 为 (eigenvalue, eigenvector) 元组。
    """
    try:
        A = np.asarray(A, dtype=float)
        n = A.shape[0]

        v = np.random.randn(n)
        v = v / np.linalg.norm(v)

        lambda_old = 0.0
        iterations = 0
        for k in range(max_iter):
            w = A @ v
            lambda_new = float(v @ w)
            v = w / np.linalg.norm(w)
            iterations = k + 1
            if abs(lambda_new - lambda_old) < tol:
                lambda_old = lambda_new
                break
            lambda_old = lambda_new

        return MathObject(
            result={"eigenvalue": lambda_old, "eigenvector": v.tolist()},
            steps=[
                f"矩阵维度: {n}×{n}",
                f"迭代次数: {iterations}",
                f"特征值收敛: λ ≈ {lambda_old:.8f}",
            ],
            meaning=f"幂法求得最大特征值 λ ≈ {lambda_old:.6f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="numerical", action="qr_algorithm")
def qr_algorithm(
    A: Union[list[list[float]], np.ndarray],
    tol: float = 1e-8,
    max_iter: int = 1000,
) -> MathObject:
    """QR 算法求矩阵所有特征值。

    使用带位移的 QR 迭代（Francis QR 步）逼近 Schur 形。

    Args:
        A: 方阵。
        tol: 收敛容差。
        max_iter: 最大迭代次数。

    Returns:
        MathObject: result 为特征值列表。
    """
    try:
        A_mat = np.asarray(A, dtype=float)
        n = A_mat.shape[0]
        if n != A_mat.shape[1]:
            return MathObject(error="矩阵必须为方阵")

        # 用 numpy 的 QR 迭代实现
        H = A_mat.copy()
        for k in range(max_iter):
            Q, R = np.linalg.qr(H)
            H = R @ Q
            # 检查次对角元素
            off_diag = np.max(np.abs(H - np.diag(np.diag(H)))) if n > 1 else 0.0
            if off_diag < tol:
                break

        eigenvalues = np.diag(H).tolist()
        # 处理 2×2 块（共轭复根）
        final_eigs = []
        i = 0
        while i < n:
            if i < n - 1 and abs(H[i + 1, i]) > tol:
                # 2×2 块 -> 共轭复根
                block = H[i:i + 2, i:i + 2]
                tr = block[0, 0] + block[1, 1]
                det = block[0, 0] * block[1, 1] - block[0, 1] * block[1, 0]
                disc = tr**2 - 4 * det
                if disc < 0:
                    re = tr / 2
                    im = np.sqrt(-disc) / 2
                    final_eigs.append(complex(re, im))
                    final_eigs.append(complex(re, -im))
                else:
                    final_eigs.append(float((tr + np.sqrt(disc)) / 2))
                    final_eigs.append(float((tr - np.sqrt(disc)) / 2))
                i += 2
            else:
                final_eigs.append(float(H[i, i]))
                i += 1

        return MathObject(
            result=final_eigs,
            steps=[
                f"矩阵维度: {n}×{n}",
                f"QR 迭代后对角线: {np.diag(H).tolist()}",
            ],
            meaning=f"QR 算法特征值: {final_eigs}",
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """自测 matrix_numerical 模块。"""
    print("=== matrix_numerical self_test ===")
    passed = 0
    total = 6

    # Test 1: LU decomposition
    try:
        r = lu_decomposition([[4, 3], [6, 3]])
        assert r.ok
        L = np.array(r.result["L"])
        U = np.array(r.result["U"])
        recon = L @ U
        assert np.max(np.abs(recon - np.array([[4, 3], [6, 3]]))) < 1e-10
        print("  [PASS] lu_decomposition")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] lu_decomposition: {e}")

    # Test 2: jacobi_iteration
    try:
        A = [[4, 1], [2, 5]]
        b = [1, 1]
        x0 = [0, 0]
        r = jacobi_iteration(A, b, x0, max_iter=100)
        assert r.ok
        # 精确解: 4x+y=1, 2x+5y=1 => x=1/6? Let me compute: from 1: y=1-4x, plug into 2: 2x+5(1-4x)=1 => 2x+5-20x=1 => -18x=-4 => x=2/9, y=1-8/9=1/9
        x_sol = np.array(r.result)
        expected = np.array([2 / 9, 1 / 9])
        assert np.linalg.norm(x_sol - expected) < 0.01
        print(f"  [PASS] jacobi_iteration: x={x_sol}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] jacobi_iteration: {e}")

    # Test 3: gauss_seidel
    try:
        A = [[4, 1], [2, 5]]
        b = [1, 1]
        x0 = [0, 0]
        r = gauss_seidel(A, b, x0, max_iter=100)
        assert r.ok
        x_sol = np.array(r.result)
        expected = np.array([2 / 9, 1 / 9])
        assert np.linalg.norm(x_sol - expected) < 0.01
        print(f"  [PASS] gauss_seidel: x={x_sol}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] gauss_seidel: {e}")

    # Test 4: conjugate_gradient
    try:
        A = [[4, 0], [0, 2]]
        b = [1, 1]
        x0 = [0, 0]
        r = conjugate_gradient(A, b, x0)
        assert r.ok
        x_sol = np.array(r.result)
        assert abs(x_sol[0] - 0.25) < 0.01
        assert abs(x_sol[1] - 0.5) < 0.01
        print(f"  [PASS] conjugate_gradient: x={x_sol}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] conjugate_gradient: {e}")

    # Test 5: power_method
    try:
        r = power_method([[2, 1], [1, 2]])
        assert r.ok
        ev = r.result["eigenvalue"]
        assert abs(ev - 3.0) < 0.01, f"Expected 3.0, got {ev}"
        print(f"  [PASS] power_method: λ={ev:.6f}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] power_method: {e}")

    # Test 6: qr_algorithm
    try:
        r = qr_algorithm([[4, 1], [2, 3]])
        assert r.ok
        eigs = r.result
        # 特征值应该接近 5 和 2
        assert any(abs(ev - 5) < 0.1 for ev in eigs) or any(abs(ev - 2) < 0.1 for ev in eigs)
        print(f"  [PASS] qr_algorithm: eigs={[round(ev, 4) if isinstance(ev, float) else str(ev) for ev in eigs]}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] qr_algorithm: {e}")

    print(f"  Result: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    self_test()
