# -*- coding: utf-8 -*-
"""数学边界守卫 — 三级精准拦截法 + 极限专项防御 + 数域切换。

依赖: sympy, ConfigManager（均为核心层，无 PySide6 依赖）

用法:
    from MF_Mathematics.utils.math_guard import ComplexityGuard, LimitGuard, GuardLevel, GuardResult

    r = ComplexityGuard.check(expr, mode="不定积分")
    if r.level == GuardLevel.REJECT:
        return MathObject(error=r.message)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


# ═══════════════════════════════════════════════════════════════════════
#  Config（统一使用 ConfigManager）
# ═══════════════════════════════════════════════════════════════════════

def _cfg():
    try:
        from MF_Mathematics.utils.config_manager import config
        return config
    except Exception:
        pass
    # 极简回退
    class _Fallback:
        def get(self, *keys, default=None):
            return default
        @property
        def math_guard(self): return {}
        @property
        def math_guard_level1(self): return {}
        @property
        def math_guard_level2(self): return {}
        @property
        def math_guard_limit(self): return {}
    return _Fallback()


# ═══════════════════════════════════════════════════════════════════════
#  数据类型
# ═══════════════════════════════════════════════════════════════════════


class GuardLevel(Enum):
    PASS   = auto()   # 放行
    WARN   = auto()   # Level 1 — 慢速预警（可继续）
    BLOCK  = auto()   # Level 2 — 爆炸风险（三选一：本地/AI/取消）
    REJECT = auto()   # Level 3 — 硬错误（直接拒绝）
    COMPLEX = auto()  # 特殊：数域切换建议


@dataclass
class GuardResult:
    level: GuardLevel
    title: str = ""
    message: str = ""
    can_override: bool = False
    # Level 2 用户选择: "local" | "ai" | "cancel"
    user_choice: str = ""


# ═══════════════════════════════════════════════════════════════════════
#  ComplexityGuard — 三级精准拦截
# ═══════════════════════════════════════════════════════════════════════


class ComplexityGuard:
    """表达式复杂度三级拦截器。"""

    @staticmethod
    def check(expr: str, mode: str = "") -> GuardResult:
        """对表达式执行全三级检查 + 数域检测。

        Args:
            expr: 已翻译的 SymPy 兼容表达式。
            mode: 操作模式（"不定积分"、"定积分"、"极限" 等）。

        Returns:
            GuardResult — level=PASS 表示通过所有检查。
        """
        # ── 3 级优先：硬错误 ──
        r = ComplexityGuard._level3(expr)
        if r.level != GuardLevel.PASS:
            return r

        # ── 数域检测：复数域操作 ──
        r = ComplexityGuard._check_complex_domain(expr)
        if r.level != GuardLevel.PASS:
            return r

        # ── 2 级：爆炸风险 ──
        r = ComplexityGuard._level2(expr, mode)
        if r.level != GuardLevel.PASS:
            return r

        # ── 1 级：慢速预警 ──
        return ComplexityGuard._level1(expr)

    # ═══════════════════════════════════════════════════════════════
    #  3 级 — 数学硬错误
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _level3(expr: str) -> GuardResult:
        """检测除零、无穷不定理、未定义符号等硬错误。"""
        # 除零: 1/0, 1/(0), 1/(x-x)
        if re.search(r"/\s*0\b", expr):
            return GuardResult(GuardLevel.REJECT,
                "数学错误", "表达式包含除零操作（1/0），无数学意义，请检查输入。")
        if re.search(r"/\s*\(\s*0\s*\)", expr):
            return GuardResult(GuardLevel.REJECT,
                "数学错误", "分母为零，表达式无数学意义，请检查输入。")
        if re.search(r"/\s*\(\s*[a-zA-Z]\s*-\s*[a-zA-Z]\s*\)", expr):
            return GuardResult(GuardLevel.REJECT,
                "数学错误", "分母可能为零（形如 x-x），请检查输入。")

        # 无穷不定式: oo - oo, oo / oo
        if re.search(r"oo\s*-\s*oo|oo\s*/\s*oo", expr):
            return GuardResult(GuardLevel.REJECT,
                "数学错误", "表达式包含 ∞-∞ 或 ∞/∞ 不定式，无数学意义。")

        # 0 * oo
        if re.search(r"0\s*\*\s*oo|oo\s*\*\s*0", expr):
            return GuardResult(GuardLevel.REJECT,
                "数学错误", "表达式包含 0×∞ 不定式，无数学意义。")

        # 未定义符号检测：使用 sympy 解析
        try:
            import sympy as sp
            parsed = sp.sympify(expr)
            # 检查是否有未求值的 Derivative（如 f'(x) 且 f 未定义）
            if hasattr(parsed, 'atoms'):
                from sympy import Derivative
                for atom in parsed.atoms(Derivative):
                    return GuardResult(GuardLevel.REJECT,
                        "未定义符号",
                        f"表达式含未求值的导数 {atom}，请先定义被导函数。")
        except Exception:
            pass  # 解析失败交给后续处理

        return GuardResult(GuardLevel.PASS, "", "")

    # ═══════════════════════════════════════════════════════════════
    #  数域检测 — 实模式下出现复数操作
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _check_complex_domain(expr: str) -> GuardResult:
        """检测实数模式下是否出现复数域操作。"""
        # sqrt(-x) 或 sqrt(-数字)
        if re.search(r"sqrt\s*\(\s*-", expr):
            return GuardResult(GuardLevel.COMPLEX,
                "数域切换", "检测到 sqrt(负数)，是否切换至复数模式计算？",
                can_override=True)

        # log(-x) 或 log(-数字)
        if re.search(r"log\s*\(\s*-", expr):
            return GuardResult(GuardLevel.COMPLEX,
                "数域切换", "检测到 log(负数)，是否切换至复数模式计算？",
                can_override=True)

        # (-1)**(1/2) 等
        if re.search(r"\(\s*-1\s*\)\s*\*\*\s*\(\s*1\s*/\s*2\s*\)", expr):
            return GuardResult(GuardLevel.COMPLEX,
                "数域切换", "检测到 (-1)^(1/2)（即虚数单位），是否切换至复数模式？",
                can_override=True)

        return GuardResult(GuardLevel.PASS, "", "")

    # ═══════════════════════════════════════════════════════════════
    #  2 级 — 爆炸风险
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _level2(expr: str, mode: str) -> GuardResult:
        cf = _cfg()
        poly_thresh = cf.get("math_guard", "level2", "poly_degree_threshold", default=10)
        max_mat     = cf.get("math_guard", "level2", "max_matrix_dim", default=6)
        series_max  = cf.get("math_guard", "level2", "max_series_range", default=1000)

        # ── 超高次幂分式积分 ──
        if mode in ("不定积分", "定积分", "integrate"):
            m = re.search(r"/\s*\(.*?x\*\*(\d+)", expr)
            if m:
                deg = int(m.group(1))
                if deg >= poly_thresh:
                    return GuardResult(GuardLevel.BLOCK,
                        "爆炸风险",
                        f"检测到分母含 x^{deg}（≥{poly_thresh}），极可能导致程序卡死。\n请选择处理方式：",
                        can_override=True)
            m2 = re.search(r"1\s*/\s*\([^)]*x\*\*(\d+)\)", expr)
            if m2:
                deg = int(m2.group(1))
                if deg >= poly_thresh:
                    return GuardResult(GuardLevel.BLOCK,
                        "爆炸风险",
                        f"检测到超高次幂分式积分（x^{deg}），极可能导致程序卡死。\n请选择处理方式：",
                        can_override=True)

        # ── 超大矩阵 ──
        if re.search(r"(det|inv|matrix|Matrix)", expr, re.IGNORECASE):
            depth = expr.count("[") - expr.count("]")
            if abs(depth) >= max_mat * 2:
                return GuardResult(GuardLevel.BLOCK,
                    "爆炸风险",
                    f"矩阵维度可能 ≥ {max_mat}，行列式/逆矩阵运算极易卡死。\n请选择处理方式：",
                    can_override=True)

        # ── 大范围级数求和 ──
        m3 = re.search(r"Sum\([^,]+,\s*\([^,]+,\s*(\d+),\s*(\d+)\)", expr)
        if m3:
            lo, hi = int(m3.group(1)), int(m3.group(2))
            if hi - lo > series_max:
                return GuardResult(GuardLevel.BLOCK,
                    "爆炸风险",
                    f"级数求和范围 {hi - lo} > {series_max}，极可能卡死。\n请选择处理方式：",
                    can_override=True)

        return GuardResult(GuardLevel.PASS, "", "")

    # ═══════════════════════════════════════════════════════════════
    #  1 级 — 慢速预警
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _level1(expr: str) -> GuardResult:
        cf = _cfg()
        max_ops  = cf.get("math_guard", "level1", "max_ops", default=500)
        max_nest = cf.get("math_guard", "level1", "max_nest_depth", default=10)

        ops  = ComplexityGuard.count_ops(expr)
        nest = ComplexityGuard._nest_depth(expr)

        if ops > max_ops:
            return GuardResult(GuardLevel.WARN,
                "复杂表达式",
                f"表达式包含 {ops} 个运算符（阈值 {max_ops}），预计计算时间 > 10 秒。\n是否继续？",
                can_override=True)

        if nest > max_nest:
            return GuardResult(GuardLevel.WARN,
                "深度嵌套",
                f"表达式嵌套深度 {nest} > {max_nest}，计算可能较慢。\n是否继续？",
                can_override=True)

        return GuardResult(GuardLevel.PASS, "", "")

    # ── 辅助方法 ──────────────────────────────────────────────

    @staticmethod
    def count_ops(expr: str) -> int:
        """统计运算符数量。"""
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


# ═══════════════════════════════════════════════════════════════════════
#  LimitGuard — 极限计算专项防御
# ═══════════════════════════════════════════════════════════════════════


class LimitGuard:
    """极限计算三级防御：振荡检测 → 数值探针 → 超时计算。"""

    @staticmethod
    def check(expr: str, var: str, point: str) -> GuardResult:
        """对极限计算执行专项检查。

        Returns:
            GuardResult — PASS 表示可安全调用 sympy.limit。
        """
        # ── 1 级：高频振荡模式 ──
        cf = _cfg()
        osc_patterns = cf.get("math_guard", "limit", "oscillation_patterns",
                              default=["sin(1/", "cos(1/"])
        for pat in osc_patterns:
            if pat in expr:
                return GuardResult(GuardLevel.REJECT,
                    "极限不存在",
                    "函数在趋近点附近剧烈振荡（检测到 sin(1/x) 或 cos(1/x)），极限不存在。")

        # ── 2 级：数值探针 ──
        epsilons = cf.get("math_guard", "limit", "num_sample_epsilon",
                          default=[0.001, 1e-6])
        threshold = cf.get("math_guard", "limit", "max_diff_threshold",
                           default=0.001)
        try:
            left_vals  = LimitGuard._sample(expr, var, point, epsilons, side="left")
            right_vals = LimitGuard._sample(expr, var, point, epsilons, side="right")
            for lv, rv, eps in zip(left_vals, right_vals, epsilons):
                if lv is None or rv is None:
                    continue
                if abs(lv - rv) > threshold:
                    return GuardResult(GuardLevel.REJECT,
                        "极限不存在",
                        f"数值探针检测：左极限 ≈ {lv:.4g}，右极限 ≈ {rv:.4g}（ε={eps}），"
                        f"差异 > {threshold}，极限不存在（跳跃/振荡）。")
        except Exception:
            pass  # 采样失败，放行至 sympy

        # ── 3 级：放行（由调用方设置超时）──
        return GuardResult(GuardLevel.PASS, "", "")

    @staticmethod
    def _sample(expr: str, var: str, point: str,
                epsilons: list[float], side: str) -> list[float | None]:
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
                val = f(pt - eps) if side == "left" else f(pt + eps)
                results.append(float(val))
            except Exception:
                results.append(None)
        return results

    @staticmethod
    def compute_with_timeout(expr_str: str, var_str: str, point_str: str,
                             timeout: float = 5.0) -> GuardResult:
        """带超时的极限计算（使用 multiprocessing）。

        Returns:
            GuardResult with level=PASS and message=result string on success,
            or level=REJECT on timeout.
        """
        import sympy as sp
        import multiprocessing as mp

        def _compute(q: mp.Queue) -> None:
            try:
                x = sp.Symbol(var_str)
                parsed = sp.sympify(expr_str)
                pt = sp.sympify(point_str)
                result = sp.limit(parsed, x, pt)
                q.put(("ok", str(result)))
            except Exception as e:
                q.put(("error", str(e)))

        ctx = mp.get_context("spawn")
        q: mp.Queue = ctx.Queue()
        p = ctx.Process(target=_compute, args=(q,))
        p.start()
        p.join(timeout)

        if p.is_alive():
            p.terminate()
            p.join()
            return GuardResult(GuardLevel.REJECT,
                "计算超时",
                f"极限计算超过 {timeout} 秒，建议使用 AI 辅助。")

        if not q.empty():
            status, msg = q.get()
            if status == "ok":
                return GuardResult(GuardLevel.PASS, "", msg)
            return GuardResult(GuardLevel.REJECT, "计算错误", msg)

        return GuardResult(GuardLevel.REJECT, "未知错误", "极限计算进程异常。")


# ═══════════════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════════════

def self_test() -> None:
    """验证 ComplexityGuard 和 LimitGuard。"""
    print("=== math_guard self_test ===")

    # ── ComplexityGuard ──
    r = ComplexityGuard.check("x**2 + 2*x + 1", mode="求导")
    assert r.level == GuardLevel.PASS, f"简单表达式应 PASS，得到 {r.level}"
    print("  [PASS] 简单表达式 PASS")

    r = ComplexityGuard.check("1/0 + x", mode="求导")
    assert r.level == GuardLevel.REJECT, f"除零应 REJECT，得到 {r.level}"
    print("  [PASS] 除零 REJECT")

    r = ComplexityGuard.check("sqrt(-1)", mode="求导")
    assert r.level == GuardLevel.COMPLEX, f"sqrt(-1) 应 COMPLEX，得到 {r.level}"
    print("  [PASS] sqrt(-1) → COMPLEX")

    # 低度幂应 PASS
    r = ComplexityGuard.check("1/(1+x**3)", mode="不定积分")
    assert r.level == GuardLevel.PASS, f"x^3 分式积分应 PASS，得到 {r.level}"
    print("  [PASS] 低次幂分式积分 PASS")

    # ── LimitGuard ──
    r = LimitGuard.check("sin(1/x)", "x", "0")
    assert r.level == GuardLevel.REJECT, f"sin(1/x) 应 REJECT，得到 {r.level}"
    print("  [PASS] sin(1/x) 极限振荡 REJECT")

    r = LimitGuard.check("x**2", "x", "0")
    assert r.level == GuardLevel.PASS, f"x^2 应 PASS，得到 {r.level}"
    print("  [PASS] x^2 极限探针 PASS")

    # ── 辅助方法 ──
    ops = ComplexityGuard.count_ops("x + y * (z - 1) / 2")
    assert ops >= 5, f"运算符数应 ≥ 5，得到 {ops}"
    print(f"  [PASS] count_ops = {ops}")

    depth = ComplexityGuard._nest_depth("((x+1)*(y-2))")
    assert depth == 2, f"嵌套深度应为 2，得到 {depth}"
    print(f"  [PASS] nest_depth = {depth}")

    print("=== math_guard self_test: ALL PASSED ===\n")


if __name__ == "__main__":
    self_test()
