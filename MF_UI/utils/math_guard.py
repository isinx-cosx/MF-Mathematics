# -*- coding: utf-8 -*-
"""数学边界守卫 — 三级精准拦截法。

- Level 1 (YELLOW): 慢速预警 — 表达式复杂，预计>10s
- Level 2 (RED):    爆炸风险 — 超高次幂积分/大矩阵/大范围求和
- Level 3 (BLACK):  硬错误   — 除零/未定义符号/无意义操作

所有阈值从 config.json 的 math_guard 段读取，禁止硬编码。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


# ── 加载配置 ──────────────────────────────────────────────

def _load_config() -> dict:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(root, "config.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


_cfg = _load_config()
_G = _cfg.get("math_guard", {})
_L1 = _G.get("level1", {})
_L2 = _G.get("level2", {})
_L3 = _G.get("level3", {})
_LIM = _G.get("limit", {})


# ═══════════════════════════════════════════════════════════════════
#  Data types
# ═══════════════════════════════════════════════════════════════════


class GuardLevel(Enum):
    PASS = auto()       # 放行
    WARN = auto()       # Level 1 — 警告但允许继续
    BLOCK = auto()      # Level 2 — 硬拦截（可 override）
    REJECT = auto()     # Level 3 — 直接拒绝


@dataclass
class GuardResult:
    level: GuardLevel
    title: str
    message: str
    can_override: bool = False


# ═══════════════════════════════════════════════════════════════════
#  ComplexityGuard
# ═══════════════════════════════════════════════════════════════════


class ComplexityGuard:
    """三级精准拦截器。"""

    @staticmethod
    def check(expr: str, mode: str = "") -> GuardResult:
        """对表达式执行全三级检查。

        Args:
            expr: 已翻译的 SymPy 兼容表达式。
            mode: 操作模式（如 "不定积分"、"定积分"、"极限" 等），
                  用于精确匹配 2 级规则。

        Returns:
            GuardResult，level=PASS 表示通过所有检查。
        """
        # ── 3 级优先：硬错误 ──
        result = ComplexityGuard._level3(expr)
        if result.level != GuardLevel.PASS:
            return result

        # ── 2 级：爆炸风险 ──
        result = ComplexityGuard._level2(expr, mode)
        if result.level != GuardLevel.PASS:
            return result

        # ── 1 级：慢速预警 ──
        return ComplexityGuard._level1(expr)

    # ═══════════════════════════════════════════════════════════
    #  3 级 — 数学硬错误
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _level3(expr: str) -> GuardResult:
        # 除零：1/0, 1/(x-x)
        if re.search(r"/\s*0\b", expr):
            return GuardResult(
                GuardLevel.REJECT,
                "数学错误",
                "表达式包含除零操作（1/0），无数学意义，请检查输入。",
            )
        if re.search(r"/\s*\(\s*0\s*\)", expr):
            return GuardResult(
                GuardLevel.REJECT,
                "数学错误",
                "分母为零，表达式无数学意义，请检查输入。",
            )

        # 无穷运算：oo - oo, oo / oo
        if re.search(r"oo\s*-\s*oo|oo\s*/\s*oo", expr):
            return GuardResult(
                GuardLevel.REJECT,
                "数学错误",
                "表达式包含 ∞ - ∞ 或 ∞ / ∞ 等不定式，无数学意义。",
            )

        return GuardResult(GuardLevel.PASS, "", "")

    # ═══════════════════════════════════════════════════════════
    #  2 级 — 爆炸风险
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _level2(expr: str, mode: str) -> GuardResult:
        threshold = _L2.get("poly_degree_threshold", 10)

        # 超高次幂分式积分
        if mode in ("不定积分", "定积分", "integrate"):
            # 检测分母中的 x**n
            m = re.search(r"/\s*\(.*?x\*\*(\d+)", expr)
            if m:
                degree = int(m.group(1))
                if degree >= threshold:
                    return GuardResult(
                        GuardLevel.BLOCK,
                        "爆炸风险",
                        f"检测到分母含 x^{degree}（≥{threshold}），"
                        f"可能导致程序卡死。\n请选择处理方式：",
                        can_override=True,
                    )
            # 也检测 1/(1+x**n) 模式
            m2 = re.search(r"1\s*/\s*\([^)]*x\*\*(\d+)\)", expr)
            if m2:
                degree = int(m2.group(1))
                if degree >= threshold:
                    return GuardResult(
                        GuardLevel.BLOCK,
                        "爆炸风险",
                        f"检测到超高次幂分式积分（x^{degree}），"
                        f"sympy 可能卡死。\n请选择处理方式：",
                        can_override=True,
                    )

        # 超大矩阵
        max_mat = _L2.get("max_matrix_dim", 6)
        if re.search(r"(det|inv|matrix)", expr, re.IGNORECASE):
            # 统计嵌套列表深度估算维度
            depth = expr.count("[") - expr.count("]")
            if abs(depth) >= max_mat * 2:
                return GuardResult(
                    GuardLevel.BLOCK,
                    "爆炸风险",
                    f"矩阵维度可能 ≥ {max_mat}，行列式/逆矩阵运算极易卡死。",
                    can_override=True,
                )

        # 大范围级数求和
        max_range = _L2.get("max_series_range", 1000)
        m3 = re.search(r"Sum\([^,]+,\s*\([^,]+,\s*(\d+),\s*(\d+)\)", expr)
        if m3:
            lo, hi = int(m3.group(1)), int(m3.group(2))
            if hi - lo > max_range:
                return GuardResult(
                    GuardLevel.BLOCK,
                    "爆炸风险",
                    f"级数求和范围 {hi - lo} > {max_range}，可能极慢。",
                    can_override=True,
                )

        return GuardResult(GuardLevel.PASS, "", "")

    # ═══════════════════════════════════════════════════════════
    #  1 级 — 慢速预警
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _level1(expr: str) -> GuardResult:
        max_ops = _L1.get("max_ops", 500)
        max_nest = _L1.get("max_nest_depth", 10)

        ops = ComplexityGuard.count_ops(expr)
        nest = ComplexityGuard._nest_depth(expr)

        if ops > max_ops:
            return GuardResult(
                GuardLevel.WARN,
                "复杂表达式",
                f"表达式包含 {ops} 个运算符（阈值 {max_ops}），"
                f"预计计算时间 > 10 秒。\n是否继续？",
                can_override=True,
            )

        if nest > max_nest:
            return GuardResult(
                GuardLevel.WARN,
                "深度嵌套",
                f"表达式嵌套深度 {nest} > {max_nest}，计算可能较慢。\n是否继续？",
                can_override=True,
            )

        return GuardResult(GuardLevel.PASS, "", "")

    # ═══════════════════════════════════════════════════════════
    #  Helpers
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def count_ops(expr: str) -> int:
        """统计表达式中的运算符数量。"""
        ops = re.findall(r"[+\-*/^(){}\[\],=]", expr)
        return len(ops)

    @staticmethod
    def _nest_depth(expr: str) -> int:
        """估算括号嵌套深度。"""
        depth = 0
        max_depth = 0
        for ch in expr:
            if ch in "({[":
                depth += 1
                max_depth = max(max_depth, depth)
            elif ch in ")}]":
                depth -= 1
        return max_depth


# ═══════════════════════════════════════════════════════════════════
#  LimitGuard — 极限计算专项防御
# ═══════════════════════════════════════════════════════════════════


class LimitGuard:
    """极限计算三级防御。"""

    @staticmethod
    def check(expr: str, var: str, point: str) -> GuardResult:
        """对极限计算执行专项检查。

        Returns:
            GuardResult — PASS 表示可以安全调用 sympy.limit。
        """
        # ── 1级：高频振荡模式 ──
        osc_patterns = _LIM.get("oscillation_patterns", ["sin(1/", "cos(1/"])
        for pat in osc_patterns:
            if pat in expr:
                return GuardResult(
                    GuardLevel.REJECT,
                    "极限不存在",
                    "函数在趋近点附近剧烈振荡（检测到 sin(1/x) 或 cos(1/x)），极限不存在。",
                )

        # ── 2级：数值探针 ──
        epsilons = _LIM.get("num_sample_epsilon", [0.001, 1e-6])
        threshold = _LIM.get("max_diff_threshold", 0.001)
        try:
            left_vals = LimitGuard._sample(expr, var, point, epsilons, side="left")
            right_vals = LimitGuard._sample(expr, var, point, epsilons, side="right")
            for lv, rv, eps in zip(left_vals, right_vals, epsilons):
                if lv is None or rv is None:
                    continue
                if abs(lv - rv) > threshold:
                    return GuardResult(
                        GuardLevel.REJECT,
                        "极限不存在",
                        f"数值探针检测：左极限≈{lv:.4g}，右极限≈{rv:.4g}（ε={eps}），"
                        f"差异>{threshold}，极限不存在（跳跃/振荡）。",
                    )
        except Exception:
            pass  # 数值采样失败，放行

        return GuardResult(GuardLevel.PASS, "", "")

    @staticmethod
    def _sample(expr: str, var: str, point: str, epsilons: list[float], side: str) -> list[float | None]:
        """在 point±ε 处采样函数值。"""
        import sympy as sp
        x = sp.Symbol(var)
        try:
            parsed = sp.sympify(expr)
            f = sp.lambdify(x, parsed, "numpy")
            pt = float(sp.N(sp.sympify(point)))
        except Exception:
            return [None] * len(epsilons)

        results = []
        for eps in epsilons:
            try:
                if side == "left":
                    val = f(pt - eps)
                else:
                    val = f(pt + eps)
                results.append(float(val))
            except Exception:
                results.append(None)
        return results
