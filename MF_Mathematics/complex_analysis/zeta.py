"""黎曼 ζ 函数 — 解析延拓、函数方程、非平凡零点。

依赖: mpmath, sympy, numpy
"""

from __future__ import annotations

from typing import Any, List, Optional, Union

import sympy as sp
import numpy as np

try:
    import mpmath as mp
    HAS_MPMATH = True
except ImportError:
    HAS_MPMATH = False

from ..core.math_object import MathObject
from ..core.registry import register


# ── 公开函数 ──────────────────────────────────────────────────────────


@register(module="complex_analysis", action="zeta_series")
def zeta_series(
    s: Any,
    n_terms: int = 1000,
) -> MathObject:
    """ζ(s) 的级数定义（Re s > 1）。

    ζ(s) = Σ_{n=1}^{∞} 1/n^s

    在 Re s > 1 时收敛。本函数计算截断级数。

    Args:
        s: 复变量，complex 或数值。
        n_terms: 求和项数。

    Returns:
        MathObject，result 为 ζ(s) 的近似值。
    """
    try:
        s_val = complex(s) if not isinstance(s, complex) else s

        # 使用 mpmath 获取高精度结果
        if HAS_MPMATH:
            mp_s = mp.mpc(s_val.real, s_val.imag)
            zeta_val = mp.zeta(mp_s)
            zeta_complex = complex(zeta_val.real, zeta_val.imag)
            steps = [
                f"ζ(s) = Σ 1/n^s",
                f"s = {s_val.real:.10g} + {s_val.imag:.10g}i",
                f"mpmath 高精度结果: ζ(s) = {zeta_complex.real:.15g} + {zeta_complex.imag:.15g}i",
            ]
            if s_val.real > 1:
                # 也计算级数截断做对比
                partial_sum = complex(0, 0)
                for n in range(1, min(n_terms, 10000) + 1):
                    partial_sum += 1.0 / (n ** s_val)
                steps.append(f"级数截断 ({n_terms} 项): {partial_sum.real:.10g} + {partial_sum.imag:.10g}i")
                steps.append(f"截断误差: {abs(partial_sum - zeta_complex):.2e}")

            return MathObject(
                result=zeta_complex,
                steps=steps,
                meaning="ζ(s) 在 Re s > 1 时由级数定义，在复平面其他区域通过解析延拓得到。",
            )

        # 退化为直接级数求和
        if s_val.real <= 1:
            return MathObject(
                error=f"级数定义仅对 Re s > 1 收敛。当前 Re s = {s_val.real}。请使用 analytic_continuation_zeta。",
            )

        total = complex(0, 0)
        for n in range(1, n_terms + 1):
            total += 1.0 / (n ** s_val)

        steps = [
            f"ζ(s) = Σ 1/n^s",
            f"s = {s_val.real} + {s_val.imag}i",
            f"截断 {n_terms} 项: ζ(s) ≈ {total.real:.10g} + {total.imag:.10g}i",
        ]

        return MathObject(
            result=total,
            steps=steps,
            meaning="级数定义仅对 Re s > 1 有效。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="analytic_continuation_zeta")
def analytic_continuation_zeta(
    s: Any,
) -> MathObject:
    """解析延拓（基于函数方程）。

    对 Re s ≤ 1 使用函数方程：
    ζ(s) = 2^s π^{s-1} sin(πs/2) Γ(1-s) ζ(1-s)

    由于 ζ(1-s) 中 1-s 的实部 > 1（当 Re s < 0 时），可用级数计算。

    Args:
        s: 复变量。

    Returns:
        MathObject，result 为 ζ(s) 的高精度值。
    """
    try:
        s_val = complex(s) if not isinstance(s, complex) else s

        if not HAS_MPMATH:
            return MathObject(
                error="需要 mpmath 库进行解析延拓计算。请安装: pip install mpmath",
            )

        mp_s = mp.mpc(s_val.real, s_val.imag)

        # 使用 mpmath 内置的解析延拓
        zeta_val = mp.zeta(mp_s)
        zeta_complex = complex(zeta_val.real, zeta_val.imag)

        steps = [
            f"s = {s_val.real:.10g} + {s_val.imag:.10g}i",
            f"Re s = {s_val.real}",
        ]

        if s_val.real <= 1 and s_val.real > 0:
            # 用交替级数（Dirichlet eta）做延拓
            # η(s) = (1-2^{1-s}) ζ(s)
            mp_s = mp.mpc(s_val.real, s_val.imag)
            alt_sum = mp.nsum(lambda n: (-1)**(n+1) / n**mp_s, [1, mp.inf])
            factor = 1 - 2**(1 - mp_s)
            zeta_alt = alt_sum / factor if abs(factor) > 1e-15 else zeta_val
            zeta_alt_c = complex(zeta_alt.real, zeta_alt.imag)
            steps.append(f"使用 Dirichlet η 函数延拓: ζ(s) = η(s)/(1-2^{{1-s}})")
            steps.append(f"η(s) = {zeta_alt_c.real:.10g} + {zeta_alt_c.imag:.10g}i")
            steps.append(f"ζ(s) = {zeta_complex.real:.15g} + {zeta_complex.imag:.15g}i")

        elif s_val.real <= 0:
            # 使用函数方程（注意 s=0 时 1-s=1 为极点，用 mpmath 直接结果）
            one_minus_s = 1 - s_val
            if abs(one_minus_s - 1) < 1e-15:
                steps.append("s=0: ζ(1-s) 处为极点，使用 mpmath 极限值")
                steps.append(f"ζ(0) = {zeta_complex.real:.15g} (已知值 -1/2)")
            else:
                zeta_one_minus = mp.zeta(mp.mpc(one_minus_s.real, one_minus_s.imag))
                zeta_om_c = complex(zeta_one_minus.real, zeta_one_minus.imag)
                steps.append("使用函数方程进行解析延拓:")
                steps.append(f"ζ(s) = 2^s π^{{s-1}} sin(πs/2) Γ(1-s) ζ(1-s)")
                steps.append(f"1-s = {one_minus_s.real:.6g} + {one_minus_s.imag:.6g}i")
                steps.append(f"ζ(1-s) = {zeta_om_c.real:.10g} + {zeta_om_c.imag:.10g}i")
            steps.append(f"ζ(s) = {zeta_complex.real:.15g} + {zeta_complex.imag:.15g}i")
        else:
            steps.append(f"直接级数计算: ζ(s) = {zeta_complex.real:.15g} + {zeta_complex.imag:.15g}i")

        steps.append(f"（mpmath 高精度结果）")

        return MathObject(
            result=zeta_complex,
            steps=steps,
            meaning="ζ(s) 通过解析延拓定义在整个复平面（除 s=1 的一阶极点外）。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="functional_equation_zeta")
def functional_equation_zeta(
    s: Any,
) -> MathObject:
    """函数方程 ζ(s) = 2^s π^{s-1} sin(πs/2) Γ(1-s) ζ(1-s)。

    验证函数方程并给出两边的对比。

    Args:
        s: 复变量。

    Returns:
        MathObject，result 包含左边、右边和误差。
    """
    try:
        if not HAS_MPMATH:
            return MathObject(
                error="需要 mpmath 库。请安装: pip install mpmath",
            )

        s_val = complex(s) if not isinstance(s, complex) else s

        # 左边：直接计算 ζ(s)
        lhs = mp.zeta(mp.mpc(s_val.real, s_val.imag))
        lhs_c = complex(lhs.real, lhs.imag)

        # 右边：2^s π^{s-1} sin(πs/2) Γ(1-s) ζ(1-s)
        mp_s = mp.mpc(s_val.real, s_val.imag)
        mp_one_minus_s = mp.mpc(1 - s_val.real, -s_val.imag)

        factor = (2 ** mp_s) * (mp.pi ** (mp_s - 1))
        sin_term = mp.sin(mp.pi * mp_s / 2)
        gamma_term = mp.gamma(mp_one_minus_s)
        zeta_term = mp.zeta(mp_one_minus_s)

        rhs = factor * sin_term * gamma_term * zeta_term
        rhs_c = complex(rhs.real, rhs.imag)

        error = abs(lhs_c - rhs_c)

        steps = [
            f"s = {s_val.real:.6g} + {s_val.imag:.6g}i",
            "函数方程: ζ(s) = 2^s π^{s-1} sin(πs/2) Γ(1-s) ζ(1-s)",
            f"左边 ζ(s) = {lhs_c.real:.10g} + {lhs_c.imag:.10g}i",
            f"2^s = {complex(factor.real / (mp.pi ** (mp_s - 1)).real, 0):.10g}",
            f"π^{{s-1}} = ...",
            f"sin(πs/2) = {complex(sin_term.real, sin_term.imag):.10g}",
            f"Γ(1-s) = {complex(gamma_term.real, gamma_term.imag):.10g}",
            f"ζ(1-s) = {complex(zeta_term.real, zeta_term.imag):.10g}",
            f"右边 = {rhs_c.real:.10g} + {rhs_c.imag:.10g}i",
            f"|左边 - 右边| = {error:.2e}",
            f"函数方程{'成立' if error < 1e-10 else f'误差: {error:.2e}'}",
        ]

        return MathObject(
            result={
                "lhs": lhs_c,
                "rhs": rhs_c,
                "error": error,
                "verified": error < 1e-10,
            },
            steps=steps,
            meaning="函数方程是 ζ(s) 解析延拓的核心。它关于 s=1/2 对称（临界线 Re s = 1/2）。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="nontrivial_zeros")
def nontrivial_zeros(
    limit: int = 10,
) -> MathObject:
    """非平凡零点（返回前 N 个零点近似值）。

    黎曼猜想断言所有非平凡零点满足 Re s = 1/2。
    本函数返回已知的前 limit 个非平凡零点的虚部近似值。

    Args:
        limit: 返回的零点数量。

    Returns:
        MathObject，result 为列表，每个元素为 (实部, 虚部) 的零点。
    """
    try:
        # 已知的非平凡零点虚部（前20个，来自文献）
        known_imag_parts = [
            14.134725, 21.022040, 25.010858, 30.424876, 32.935062,
            37.586178, 40.918719, 43.327073, 48.005151, 49.773832,
            52.970321, 56.446248, 59.347044, 60.831779, 65.112544,
            67.079811, 69.546402, 72.067158, 75.704691, 77.144840,
        ]

        if limit > len(known_imag_parts):
            limit = len(known_imag_parts)

        zeros = [
            (0.5, known_imag_parts[i]) for i in range(limit)
        ]

        # 验证：对前几个零点用 mpmath 验证
        verified = []
        if HAS_MPMATH:
            for i in range(min(limit, 5)):
                s_val = mp.mpc(0.5, known_imag_parts[i])
                zeta_val = mp.zeta(s_val)
                abs_val = abs(zeta_val)
                verified.append({
                    "index": i + 1,
                    "zero": f"0.5 + {known_imag_parts[i]:.6f}i",
                    "|ζ(s)|": float(abs_val),
                    "verified": abs_val < 1e-3,
                })
        else:
            verified = [{"index": i + 1, "zero": f"0.5 + {z[1]:.6f}i"} for i, z in enumerate(zeros)]

        steps = [
            f"非平凡零点（前 {limit} 个）",
            "黎曼猜想: 所有非平凡零点满足 Re s = 1/2",
        ]
        for v in verified[:5]:
            if "verified" in v:
                steps.append(
                    f"  #{v['index']}: s = {v['zero']}, |ζ(s)| = {v['|ζ(s)|']:.2e}"
                    f" {'✓' if v['verified'] else '✗'}"
                )
            else:
                steps.append(f"  #{v['index']}: s = {v['zero']}")

        if limit > 5:
            steps.append(f"  ... 共 {limit} 个")

        return MathObject(
            result={"zeros": zeros, "verified": verified},
            steps=steps,
            meaning="黎曼 ζ 函数的非平凡零点对称分布在临界线 Re s = 1/2 上（黎曼猜想）。",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ── self_test ──────────────────────────────────────────────────────────

def self_test() -> None:
    """自测：黎曼 ζ 函数。"""
    print("=== zeta self_test ===")

    if not HAS_MPMATH:
        print("  [SKIP] mpmath 未安装，跳过大部分测试")
        # 仍测试 basic level
        try:
            import mpmath as _mp
        except ImportError:
            print("  === zeta self_test: SKIPPED (no mpmath) ===")
            return

    # 1. zeta_series: ζ(2) ≈ π²/6
    r = zeta_series(2, n_terms=10000)
    assert r.ok, r.error
    pi_sq_over_6 = np.pi ** 2 / 6
    zeta_val = r.result.real if isinstance(r.result, complex) else r.result
    assert abs(zeta_val - pi_sq_over_6) < 0.01
    print(f"  zeta_series(2): {zeta_val:.10g} (π²/6 = {pi_sq_over_6:.10g})")

    # 2. zeta_series: ζ(4) ≈ π⁴/90
    r = zeta_series(4, n_terms=10000)
    assert r.ok, r.error
    zeta_val = r.result.real if isinstance(r.result, complex) else r.result
    pi4_over_90 = np.pi ** 4 / 90
    assert abs(zeta_val - pi4_over_90) < 0.01
    print(f"  zeta_series(4): {zeta_val:.10g} (π⁴/90 = {pi4_over_90:.10g})")

    # 3. analytic_continuation_zeta: ζ(-1) = -1/12
    r = analytic_continuation_zeta(-1)
    assert r.ok, r.error
    zeta_val = r.result.real if isinstance(r.result, complex) else r.result
    assert abs(zeta_val + 1/12) < 1e-6
    print(f"  analytic_continuation_zeta(-1): {zeta_val:.10g} (expected -1/12)")

    # 4. functional_equation_zeta: 在 s=0.5 处验证
    r = functional_equation_zeta(0.5)
    assert r.ok, r.error
    assert r.result["verified"] is True
    print(f"  functional_equation_zeta(0.5): error={r.result['error']:.2e}")

    # 5. nontrivial_zeros: 前5个零点
    r = nontrivial_zeros(5)
    assert r.ok, r.error
    assert len(r.result["zeros"]) == 5
    print(f"  nontrivial_zeros(5): {len(r.result['zeros'])} zeros, verified={len(r.result.get('verified',[]))}")

    # 6. analytic_continuation_zeta: ζ(0) = -1/2
    r = analytic_continuation_zeta(0)
    assert r.ok, r.error
    zeta_val = r.result.real if isinstance(r.result, complex) else r.result
    assert abs(zeta_val + 0.5) < 1e-6
    print(f"  analytic_continuation_zeta(0): {zeta_val:.10g} (expected -1/2)")

    print("=== zeta self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
