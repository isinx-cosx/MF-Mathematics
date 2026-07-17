"""共形映射 — 共形判定、黎曼映射定理、边界对应。

依赖: sympy, numpy
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

import sympy as sp
import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


# ── 工具 ───────────────────────────────────────────────────────────────

def _parse_expr_var(func: Any, var: Any = None):
    """解析函数表达式和变量。"""
    if isinstance(func, str):
        expr = sp.sympify(func)
    else:
        expr = func
    if var is None:
        syms = list(expr.free_symbols)
        var = syms[0] if syms else sp.Symbol('z')
    elif isinstance(var, str):
        var = sp.Symbol(var)
    return expr, var


# ── 公开函数 ──────────────────────────────────────────────────────────


@register(module="complex_analysis", action="is_conformal")
def is_conformal(
    func: Any,
    z: Any,
    var: Any = None,
) -> MathObject:
    """检查映射是否共形（导数非零）。

    全纯函数 f 在 z₀ 处共形 ⇔ f'(z₀) ≠ 0。
    此时 f 在 z₀ 附近保持角度（保角）且是局部一对一。

    Args:
        func: 复函数表达式。
        z: 检查点。
        var: 复变量符号。

    Returns:
        MathObject，result 为 bool。
    """
    try:
        expr, var_sym = _parse_expr_var(func, var)
        z_val = sp.sympify(z)

        deriv = sp.diff(expr, var_sym)
        deriv_at_z = sp.simplify(deriv.subs(var_sym, z_val))
        deriv_numeric = complex(sp.N(deriv_at_z))

        is_zero = abs(deriv_numeric) < 1e-15
        conformal = not is_zero

        steps = [
            f"f(z) = {expr}",
            f"f'(z) = {deriv}",
            f"在 z = {z_val} 处: f'(z) = {deriv_at_z} ≈ {deriv_numeric.real:.10g} + {deriv_numeric.imag:.10g}i",
            f"|f'(z)| = {abs(deriv_numeric):.10g}",
            f"导数{'非零' if conformal else '为零'} → {'是共形映射' if conformal else '不是共形映射（临界点）'}",
        ]

        return MathObject(
            result=conformal,
            steps=steps,
            meaning="全纯函数 f'(z₀)≠0 ⇒ 在 z₀ 附近共形（保角+局部一对一）。",
            data={"derivative": deriv_numeric, "magnitude": abs(deriv_numeric)},
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="riemann_mapping")
def riemann_mapping(
    region: str,
) -> MathObject:
    """黎曼映射定理 — 单连通真子集共形等价于单位圆盘。

    任意非空单连通真子集 D ⊂ C（非全平面）共形等价于单位圆盘。
    本函数给出概念说明和典型样例。

    Args:
        region: 区域描述，如 "unit_disk" / "upper_half_plane" / "right_half_plane"。

    Returns:
        MathObject，result 为共形映射表达式。
    """
    try:
        mappings: Dict[str, Dict[str, Any]] = {
            "unit_disk": {
                "map": "f(z) = z（恒等映射）",
                "target": "单位圆盘 D = {|w| < 1}",
                "explanation": "单位圆盘到自身的共形映射为 Möbius 变换 f(z)=e^{iθ}(z-a)/(1-āz)。",
            },
            "upper_half_plane": {
                "map": "f(z) = (z - i) / (z + i)（Cayley 变换）",
                "target": "单位圆盘 D = {|w| < 1}",
                "explanation": "上半平面 H = {Im z > 0} 通过 Cayley 变换共形映射到单位圆盘。",
            },
            "right_half_plane": {
                "map": "f(z) = (z - 1) / (z + 1)",
                "target": "单位圆盘 D = {|w| < 1}",
                "explanation": "右半平面 {Re z > 0} 共形映射到单位圆盘。",
            },
            "slit_disk": {
                "map": "f(z) = (√z + 1)² / (√z - 1)² 等",
                "target": "有割缝的区域",
                "explanation": "黎曼映射定理保证存在共形映射，但显式构造可能涉及椭圆函数等。",
            },
            "first_quadrant": {
                "map": "f(z) = z²（将第一象限映射到上半平面）→ Cayley 变换",
                "target": "单位圆盘",
                "explanation": "第一象限共形等价于上半平面（z²），进而共形等价于圆盘。",
            },
        }

        region_key = region.lower().replace(" ", "_")
        if region_key not in mappings:
            available = list(mappings.keys())
            return MathObject(
                result={"available_regions": available},
                steps=[f"不支持的区域: {region}", f"可用区域: {available}"],
                meaning="请选择支持的预定义区域。",
            )

        info = mappings[region_key]
        steps = [
            f"区域: {region}",
            f"映射: {info['map']}",
            f"目标: {info['target']}",
            info['explanation'],
        ]

        return MathObject(
            result=info,
            steps=steps,
            meaning="黎曼映射定理：任意非空单连通真子集共形等价于单位圆盘。映射不唯一（差一个 Aut(D) 自同构）。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="boundary_correspondence")
def boundary_correspondence(
    func: Any,
    region: str,
    var: Any = None,
) -> MathObject:
    """边界对应（占位）。

    若 f 将区域 D 共形映射到 D'，且 ∂D 是分段光滑的简单闭曲线，
    则 f 可连续延拓到边界，将 ∂D 一一映射到 ∂D'。

    本函数通过采样边界点来演示边界对应。

    Args:
        func: 共形映射 f(z)。
        region: 原区域边界描述。
        var: 复变量符号。

    Returns:
        MathObject，result 包含边界采样点映射结果。
    """
    try:
        expr, var_sym = _parse_expr_var(func, var)

        # 采样边界点
        if "circle" in region.lower() or "unit" in region.lower():
            # 单位圆边界
            n_samples = 16
            boundary_pts = []
            for k in range(n_samples):
                theta = 2 * np.pi * k / n_samples
                z_pt = complex(np.cos(theta), np.sin(theta))
                w_pt = complex(sp.N(expr.subs(var_sym, z_pt)))
                boundary_pts.append({
                    "z": z_pt,
                    "w": w_pt,
                    "angle_z": theta,
                })
            region_desc = "单位圆 |z|=1"
        elif "upper" in region.lower() and "half" in region.lower():
            # 上半平面边界（实轴 + 上半圆）
            n_samples = 20
            boundary_pts = []
            for k in range(n_samples // 2):
                t = -5 + 10 * k / (n_samples // 2 - 1)
                z_pt = complex(t, 0)
                w_pt = complex(sp.N(expr.subs(var_sym, z_pt)))
                boundary_pts.append({"z": z_pt, "w": w_pt, "angle_z": np.arctan2(0, t)})
            for k in range(n_samples // 2):
                theta = np.pi * k / (n_samples // 2 - 1)
                z_pt = 10 * complex(np.cos(theta), np.sin(theta))
                w_pt = complex(sp.N(expr.subs(var_sym, z_pt)))
                boundary_pts.append({"z": z_pt, "w": w_pt, "angle_z": theta})
            region_desc = "上半平面边界"
        else:
            # 默认：单位圆
            n_samples = 16
            boundary_pts = []
            for k in range(n_samples):
                theta = 2 * np.pi * k / n_samples
                z_pt = complex(np.cos(theta), np.sin(theta))
                w_pt = complex(sp.N(expr.subs(var_sym, z_pt)))
                boundary_pts.append({"z": z_pt, "w": w_pt, "angle_z": theta})
            region_desc = f"区域边界（默认 |z|=1）"

        steps = [
            f"f(z) = {expr}",
            f"原区域边界: {region_desc}",
            f"采样 {len(boundary_pts)} 个边界点",
        ]
        for pt in boundary_pts[:6]:
            steps.append(
                f"  z = {pt['z'].real:.4g} + {pt['z'].imag:.4g}i"
                f"  →  w = {pt['w'].real:.4g} + {pt['w'].imag:.4g}i"
            )
        if len(boundary_pts) > 6:
            steps.append(f"  ... 共 {len(boundary_pts)} 个点")

        steps.append("边界对应: f(∂D) ⊂ ∂D'（在光滑边界条件下成立）")

        return MathObject(
            result={"boundary_points": [(pt["z"], pt["w"]) for pt in boundary_pts]},
            steps=steps,
            meaning="共形映射可将边界连续延拓为边界到边界的一一映射（Carathéodory 定理）。",
            data={"region_desc": region_desc, "n_points": len(boundary_pts)},
        )
    except Exception as e:
        return MathObject(error=str(e))


# ── self_test ──────────────────────────────────────────────────────────

def self_test() -> None:
    """自测：共形映射。"""
    print("=== conformal self_test ===")

    # 1. is_conformal: f(z)=z^2 at z=1 (f'(1)=2≠0)
    r = is_conformal("z**2", 1)
    assert r.ok, r.error
    assert r.result is True
    print(f"  is_conformal(z², 1): {r.result}")

    # 2. is_conformal: f(z)=z^2 at z=0 (f'(0)=0)
    r = is_conformal("z**2", 0)
    assert r.ok, r.error
    assert r.result is False
    print(f"  is_conformal(z², 0): {r.result}")

    # 3. is_conformal: f(z)=e^z at z=0 (f'(0)=1≠0)
    r = is_conformal("exp(z)", 0)
    assert r.ok, r.error
    assert r.result is True
    print(f"  is_conformal(exp(z), 0): {r.result}")

    # 4. riemann_mapping: upper_half_plane
    r = riemann_mapping("upper_half_plane")
    assert r.ok, r.error
    assert "Cayley" in r.result["explanation"]
    print(f"  riemann_mapping(upper_half_plane): {r.result['map']}")

    # 5. riemann_mapping: unit_disk
    r = riemann_mapping("unit_disk")
    assert r.ok, r.error
    print(f"  riemann_mapping(unit_disk): {r.result['map']}")

    # 6. boundary_correspondence: Cayley 变换
    r = boundary_correspondence("(z - I) / (z + I)", "unit")
    assert r.ok, r.error
    print(f"  boundary_correspondence(Cayley, unit): {len(r.result['boundary_points'])} pts")

    print("=== conformal self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
