"""probability_measure.py — 概率论中的测度论。

涵盖概率空间、随机变量、期望、条件期望和独立性判定。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import scipy.integrate as integrate
import scipy.stats as stats
import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="measure_theory", action="probability_space")
def probability_space(
    Omega: Union[str, List, Tuple],
    sigma_algebra: Any = None,
    P: Union[str, Callable, None] = None,
) -> MathObject:
    """构造概率空间三元组 (Ω, F, P)。

    概率空间 = 样本空间 Ω + σ-代数 F + 概率测度 P（P(Ω)=1）。

    Args:
        Omega: 样本空间。
            - 字符串 "finite:n" → {1, 2, ..., n}
            - 列表 → 自定义样本点集
        sigma_algebra: σ-代数（可选）。默认取幂集（离散情况）。
        P: 概率测度。
            - 字符串 "uniform" → 均匀分布
            - 可调用对象 → 自定义测度

    Returns:
        MathObject: result 含概率空间描述。
    """
    try:
        # 解析 Omega
        if isinstance(Omega, str):
            if Omega.startswith("finite:"):
                n = int(Omega.split(":")[1])
                omega_set = list(range(1, n + 1))
            elif Omega == "coin":
                omega_set = ["H", "T"]
            elif Omega == "dice":
                omega_set = list(range(1, 7))
            else:
                omega_set = list(range(1, 7))
        elif isinstance(Omega, (list, tuple)):
            omega_set = list(Omega)
        else:
            return MathObject(error=f"Omega 类型不支持: {type(Omega)}")

        N = len(omega_set)

        # 解析 P
        if P is None or P == "uniform":
            prob = {w: 1.0 / N for w in omega_set}
            prob_desc = "均匀分布"
        elif callable(P):
            prob = {w: float(P(w)) for w in omega_set}
            total = sum(prob.values())
            prob = {w: p / total for w, p in prob.items()}
            prob_desc = f"自定义分布（归一化后 ΣP = {sum(prob.values()):.4f}）"
        else:
            return MathObject(error=f"P 类型不支持: {type(P)}")

        steps = [
            f"样本空间 Ω = {omega_set}（{N} 个样本点）",
            f"σ-代数 F = 2^Ω（幂集，{2**N} 个事件）" if sigma_algebra is None else f"σ-代数: {sigma_algebra}",
            f"概率测度 P: {prob_desc}",
            f"Σ P(ω) = {sum(prob.values()):.6f} {'← 归一化 ✓' if abs(sum(prob.values()) - 1) < 1e-10 else '← 需要归一化'}",
        ]

        return MathObject(
            result={
                "Omega": omega_set,
                "sigma_algebra": f"2^Ω (幂集，|F|={2**N})",
                "P": prob,
                "is_probability_space": abs(sum(prob.values()) - 1) < 1e-10,
            },
            steps=steps,
            meaning="概率空间 (Ω, F, P) — 测度论中满足 P(Ω)=1 的正测度空间",
        )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="measure_theory", action="random_variable")
def random_variable(
    X: Union[str, Callable],
    Omega: Union[str, List, None] = None,
    sigma_algebra: Any = None,
) -> MathObject:
    """定义随机变量（即 Ω 上的可测函数）。

    随机变量 X: Ω → R 是可测函数。

    Args:
        X: 随机变量的映射规则。
            - 字符串 "identity" → 恒等映射
            - 字符串 "sum" → 对 Ω 元素求和（用于离散空间）
            - 可调用对象 → 自定义映射
        Omega: 样本空间（可选）。
        sigma_algebra: σ-代数（可选）。

    Returns:
        MathObject: result 含随机变量描述。
    """
    try:
        if Omega is None:
            Omega = list(range(1, 7))

        if isinstance(Omega, str):
            if Omega.startswith("finite:"):
                n = int(Omega.split(":")[1])
                omega_set = list(range(1, n + 1))
            else:
                omega_set = list(range(1, 7))
        elif isinstance(Omega, (list, tuple)):
            omega_set = list(Omega)
        else:
            omega_set = list(range(1, 7))

        # 解析 X
        if X == "identity":
            mapping = {w: w for w in omega_set}
            desc = "X(ω) = ω（恒等映射）"
        elif X == "square":
            mapping = {w: w**2 if isinstance(w, (int, float)) else 0 for w in omega_set}
            desc = "X(ω) = ω²"
        elif callable(X):
            mapping = {w: float(X(w)) for w in omega_set}
            desc = f"X(ω) = 自定义映射"
        elif isinstance(X, str):
            try:
                x_sym = sp.Symbol("x", real=True)
                expr = sp.sympify(X, locals={"x": x_sym})
                f_lambda = sp.lambdify(x_sym, expr, "numpy")
                mapping = {w: float(f_lambda(w)) if isinstance(w, (int, float)) else 0.0 for w in omega_set}
                desc = f"X(ω) = {X}"
            except Exception:
                mapping = {w: w for w in omega_set}
                desc = "X(ω) = ω"
        else:
            mapping = {w: w for w in omega_set}
            desc = "X(ω) = ω"

        values = list(mapping.values())

        steps = [
            f"样本空间 Ω = {omega_set}",
            f"映射规则: {desc}",
            f"取值集合: X(Ω) = {sorted(set(values))}",
        ]

        return MathObject(
            result={
                "mapping": mapping,
                "values": list(set(values)),
                "description": desc,
            },
            steps=steps,
            meaning=f"随机变量 X: Ω → R，{desc}",
        )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="measure_theory", action="expectation")
def expectation(
    X: Union[str, Callable, Dict],
    P: Union[str, Dict, None] = None,
    Omega: Union[str, List, None] = None,
) -> MathObject:
    """计算随机变量 X 的期望 E[X] = ∫ X dP。

    对于离散空间: E[X] = Σ X(ω) · P({ω})。
    对于连续分布（如正态分布 N(μ,σ²)）: E[X] = ∫ x f(x) dx。

    支持特殊分布字符串: "normal(μ,σ)", "uniform(a,b)", "exponential(λ)"。

    Args:
        X: 随机变量。
            - 字符串 "x" → 恒等随机变量
            - 字符串表达式 → 自定义函数
            - 字典 → {ω: X(ω)}
        P: 概率测度或分布描述。
            - 字典 → 离散分布
            - "uniform" → 均匀分布
            - "normal(0,1)" → 标准正态分布
        Omega: 样本空间（可选）。

    Returns:
        MathObject: result 为期望值。
    """
    try:
        # 处理连续分布
        if isinstance(P, str) and P.startswith("normal"):
            # 解析 normal(μ, σ)
            import re
            match = re.match(r"normal\(([^,]+),([^)]+)\)", P.replace(" ", ""))
            if match:
                mu_val = float(match.group(1))
                sigma_val = float(match.group(2))
            else:
                mu_val, sigma_val = 0.0, 1.0

            if X == "x" or X is None:
                expected = mu_val
            elif isinstance(X, str):
                x_sym = sp.Symbol("x", real=True)
                expr = sp.sympify(X, locals={"x": x_sym, "pi": sp.pi})
                f_lambda = sp.lambdify(x_sym, expr, "numpy")

                def integrand(t):
                    return float(f_lambda(t)) * stats.norm.pdf(t, mu_val, sigma_val)

                expected, _ = integrate.quad(integrand, mu_val - 10 * sigma_val, mu_val + 10 * sigma_val, limit=200)
            else:
                return MathObject(error=f"连续分布下 X 类型不支持: {type(X)}")

            steps = [
                f"分布: N({mu_val}, {sigma_val}²)",
                f"随机变量: X = {X}",
                f"E[X] = ∫ X · f(x) dx = {expected:.10f}",
            ]

            return MathObject(
                result=expected,
                steps=steps,
                meaning=f"正态分布 N({mu_val},{sigma_val}²) 下 E[{X}] = {mu_val}",
            )

        elif isinstance(P, str) and P.startswith("uniform"):
            match = re.match(r"uniform\(([^,]+),([^)]+)\)", P.replace(" ", ""))
            if match:
                a_val = float(match.group(1))
                b_val = float(match.group(2))
            else:
                a_val, b_val = 0.0, 1.0

            if X == "x" or X is None:
                expected = (a_val + b_val) / 2
            elif isinstance(X, str):
                x_sym = sp.Symbol("x", real=True)
                expr = sp.sympify(X, locals={"x": x_sym})
                f_lambda = sp.lambdify(x_sym, expr, "numpy")
                expected, _ = integrate.quad(lambda t: float(f_lambda(t)) / (b_val - a_val), a_val, b_val, limit=200)
            else:
                return MathObject(error=f"连续分布下 X 类型不支持: {type(X)}")

            steps = [
                f"分布: U({a_val}, {b_val})",
                f"E[X] = {expected:.10f}",
            ]
            return MathObject(
                result=expected,
                steps=steps,
                meaning=f"均匀分布 U({a_val},{b_val}) 下 E[{X}] = {expected}",
            )

        # 离散情况
        if Omega is None:
            Omega = list(range(1, 7))

        if isinstance(Omega, str):
            if Omega.startswith("finite:"):
                n = int(Omega.split(":")[1])
                omega_set = list(range(1, n + 1))
            else:
                omega_set = list(range(1, 7))
        elif isinstance(Omega, (list, tuple)):
            omega_set = list(Omega)
        else:
            omega_set = list(range(1, 7))

        N = len(omega_set)

        # 解析 X
        if isinstance(X, dict):
            x_mapping = X
        elif X == "x" or X == "identity" or X is None:
            x_mapping = {w: float(w) if isinstance(w, (int, float)) else 0.0 for w in omega_set}
        elif callable(X):
            x_mapping = {w: float(X(w)) for w in omega_set}
        elif isinstance(X, str):
            x_sym = sp.Symbol("x", real=True)
            expr = sp.sympify(X, locals={"x": x_sym})
            f_lambda = sp.lambdify(x_sym, expr, "numpy")
            x_mapping = {w: float(f_lambda(w)) if isinstance(w, (int, float)) else 0.0 for w in omega_set}
        else:
            return MathObject(error=f"X 类型不支持: {type(X)}")

        # 解析 P
        if isinstance(P, dict):
            prob = P
        elif P == "uniform" or P is None:
            prob = {w: 1.0 / N for w in omega_set}
        elif callable(P):
            prob = {w: float(P(w)) for w in omega_set}
            total = sum(prob.values())
            prob = {w: p / total for w, p in prob.items()}
        else:
            return MathObject(error=f"P 类型不支持: {type(P)}")

        # 计算期望
        exp_value = 0.0
        terms = []
        for w in omega_set:
            if w in x_mapping and w in prob:
                term = x_mapping[w] * prob[w]
                exp_value += term
                terms.append(f"X({w}) · P({w}) = {x_mapping[w]} · {prob[w]:.4f} = {term:.4f}")

        steps = [
            f"Ω = {omega_set}, P = {'均匀分布' if P is None or P == 'uniform' else '自定义分布'}",
        ]
        steps.extend(terms[:10])  # 最多展示10项
        if len(terms) > 10:
            steps.append(f"... 共 {len(terms)} 项")
        steps.append(f"E[X] = Σ X(ω)·P(ω) = {exp_value:.10f}")

        return MathObject(
            result=exp_value,
            steps=steps,
            meaning=f"离散空间上 E[X] = {exp_value}",
        )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="measure_theory", action="conditional_expectation")
def conditional_expectation(
    X: Union[str, Callable, Dict],
    sub_sigma_algebra: Any = None,
    Omega: Union[str, List, None] = None,
    P: Union[str, Dict, None] = None,
) -> MathObject:
    """计算条件期望 E[X | G]（概念性占位）。

    条件期望 E[X | G] 是关于子 σ-代数 G 可测的随机变量，
    满足对任意 G ∈ G: ∫_G E[X | G] dP = ∫_G X dP。

    本实现针对离散情况：按 G 的原子（最小非空集合）给出条件期望值。

    Args:
        X: 随机变量。
        sub_sigma_algebra: 子 σ-代数。字符串 "parity" → 奇数/偶数分类。
        Omega: 样本空间。
        P: 概率测度。

    Returns:
        MathObject: result 为条件期望值字典。
    """
    try:
        if Omega is None:
            omega_set = list(range(1, 7))
        elif isinstance(Omega, str) and Omega.startswith("finite:"):
            n = int(Omega.split(":")[1])
            omega_set = list(range(1, n + 1))
        elif isinstance(Omega, (list, tuple)):
            omega_set = list(Omega)
        else:
            omega_set = list(range(1, 7))

        N = len(omega_set)

        # 解析 X
        if isinstance(X, dict):
            x_mapping = X
        elif X == "x" or X is None:
            x_mapping = {w: float(w) if isinstance(w, (int, float)) else 0.0 for w in omega_set}
        elif callable(X):
            x_mapping = {w: float(X(w)) for w in omega_set}
        else:
            x_mapping = {w: float(w) if isinstance(w, (int, float)) else 0.0 for w in omega_set}

        # 解析 P
        if isinstance(P, dict):
            prob = P
        else:
            prob = {w: 1.0 / N for w in omega_set}

        # 构建子 σ-代数的原子
        if sub_sigma_algebra == "parity":
            atoms = {
                "偶数": [w for w in omega_set if isinstance(w, (int, float)) and w % 2 == 0],
                "奇数": [w for w in omega_set if isinstance(w, (int, float)) and w % 2 != 0],
            }
            atoms = {k: v for k, v in atoms.items() if v}
        elif isinstance(sub_sigma_algebra, dict):
            atoms = sub_sigma_algebra
        elif isinstance(sub_sigma_algebra, list):
            # 列表的列表作为原子
            atoms = {f"原子{i}": atom for i, atom in enumerate(sub_sigma_algebra)}
        else:
            # 默认按奇偶分类
            atoms = {
                "偶数": [w for w in omega_set if isinstance(w, (int, float)) and w % 2 == 0],
                "奇数": [w for w in omega_set if isinstance(w, (int, float)) and w % 2 != 0],
            }
            atoms = {k: v for k, v in atoms.items() if v}

        # 计算每个原子上的条件期望
        cond_exp = {}
        steps = [f"样本空间 Ω = {omega_set}", "子 σ-代数的原子:"]

        for atom_name, atom_elements in atoms.items():
            total_prob = sum(prob.get(w, 0) for w in atom_elements)
            weighted_sum = sum(x_mapping.get(w, 0) * prob.get(w, 0) for w in atom_elements)

            if total_prob > 0:
                ce_val = weighted_sum / total_prob
                for w in atom_elements:
                    cond_exp[w] = ce_val
                steps.append(
                    f"  {atom_name}: E[X|G]({atom_elements}) = {weighted_sum:.4f} / {total_prob:.4f} = {ce_val:.4f}"
                )
            else:
                steps.append(f"  {atom_name}: P(原子)=0，条件期望未定义")

        return MathObject(
            result={
                "conditional_expectation": cond_exp,
                "atoms": atoms,
            },
            steps=steps,
            meaning="条件期望 E[X | G] — 在子 σ-代数 G 的每个原子上取平均值",
        )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="measure_theory", action="independence_check")
def independence_check(
    A: Union[set, List],
    B: Union[set, List],
    P: Union[str, Dict, None] = None,
    Omega: Union[str, List, None] = None,
) -> MathObject:
    """事件独立性判定: P(A ∩ B) == P(A) · P(B)。

    Args:
        A: 事件 A（Ω 的子集）。
        B: 事件 B（Ω 的子集）。
        P: 概率测度。
            - "uniform" → 均匀分布
            - 字典 → 自定义分布
        Omega: 样本空间。

    Returns:
        MathObject: result=True 表示独立。
    """
    try:
        if Omega is None:
            omega_set = list(range(1, 7))
        elif isinstance(Omega, str) and Omega.startswith("finite:"):
            n = int(Omega.split(":")[1])
            omega_set = list(range(1, n + 1))
        elif isinstance(Omega, (list, tuple)):
            omega_set = list(Omega)
        else:
            omega_set = list(range(1, 7))

        N = len(omega_set)

        if isinstance(P, dict):
            prob = P
        else:
            prob = {w: 1.0 / N for w in omega_set}

        A_set = set(A)
        B_set = set(B)
        A_inter_B = A_set & B_set

        p_A = sum(prob.get(w, 0) for w in A_set)
        p_B = sum(prob.get(w, 0) for w in B_set)
        p_inter = sum(prob.get(w, 0) for w in A_inter_B)

        product = p_A * p_B
        is_independent = abs(p_inter - product) < 1e-10

        steps = [
            f"Ω = {omega_set}",
            f"A = {sorted(A_set)}, B = {sorted(B_set)}",
            f"A ∩ B = {sorted(A_inter_B)}",
            f"P(A) = {p_A:.6f}",
            f"P(B) = {p_B:.6f}",
            f"P(A∩B) = {p_inter:.6f}",
            f"P(A)·P(B) = {product:.6f}",
            f"P(A∩B) == P(A)·P(B): {'是 → 独立 ✓' if is_independent else '否 → 不独立'}",
        ]

        return MathObject(
            result=is_independent,
            steps=steps,
            meaning=f"事件 A 与 B {'独立' if is_independent else '不独立'}",
        )

    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """probability_measure 模块自测。"""
    print("=== probability_measure self_test ===")
    all_ok = True

    # 测试 1: probability_space
    r = probability_space("dice")
    assert r.ok and r.result["is_probability_space"], f"失败: {r}"
    print(f"  [PASS] probability_space('dice'): ΣP = {sum(r.result['P'].values())}")

    # 测试 2: random_variable
    r = random_variable("identity", Omega="finite:6")
    assert r.ok, f"失败: {r}"
    print(f"  [PASS] random_variable: {r.result['description']}")

    # 测试 3: expectation 标准正态 N(0,1) → 0
    r = expectation("x", P="normal(0,1)")
    assert r.ok and abs(r.result) < 0.01, f"期望非零: {r}"
    print(f"  [PASS] expectation('x', N(0,1)) = {r.result:.6f} ≈ 0")

    # 测试 4: conditional_expectation
    r = conditional_expectation("x", sub_sigma_algebra="parity", Omega="finite:6")
    assert r.ok, f"失败: {r}"
    print(f"  [PASS] conditional_expectation: {r.result['conditional_expectation']}")

    # 测试 5: independence_check
    r = independence_check({1}, {2}, P="uniform", Omega="finite:6")
    assert r.ok, f"失败: {r}"
    print(f"  [PASS] independence_check: {r.result}")

    print("=== probability_measure: ALL PASSED ===\n")
    return all_ok


if __name__ == "__main__":
    self_test()
