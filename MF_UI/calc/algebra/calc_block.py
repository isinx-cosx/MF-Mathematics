# -*- coding: utf-8 -*-
"""代数计算块 — 继承 BaseCalcBlock，覆写分派逻辑以支持三级守卫 + AI 加速。"""

from __future__ import annotations

import MF_Mathematics.algebra       # noqa
import MF_Mathematics.calculus       # noqa
import MF_Mathematics.complex_analysis  # noqa
from MF_Mathematics.core.registry import dispatch
from MF_Mathematics.core.math_object import MathObject
from MF_Mathematics.utils.translator import MathTranslator
from MF_Mathematics.utils.math_guard import ComplexityGuard, LimitGuard, GuardLevel
from MF_Mathematics.utils.ai_accelerator import get_accelerator
from MF_Mathematics.utils.config_manager import config as _cfg
from MF_UI.calc.base_calc_block import BaseCalcBlock


class CalcBlock(BaseCalcBlock):
    """代数计算块 — 含守卫 + AI 加速 + 极限超时。"""

    def get_mode_list(self) -> list[str]:
        return [
            "求导", "定积分", "不定积分", "极限", "解方程/组", "解不等式/组",
            "表达式化简", "泰勒展开", "级数求和", "级数敛散性",
            "复数运算",
            "常微分方程", "偏微分方程",
        ]

    def get_action_map(self) -> dict[str, tuple[str, str]]:
        # algebra 使用自定义分派逻辑（_do_calculate），不使用 action_map
        return {}

    # ── 覆写：完整分派流程 ───────────────────────────────────

    def on_calc_clicked(self) -> None:
        expr = self.input_box.text().strip()
        if not expr:
            return

        op = self.calc_mode_combo.currentText()

        # ── 翻译 ──
        try:
            expr = MathTranslator.human_to_computer(expr)
        except Exception:
            pass

        # ── 三级守卫 ──
        from MF_UI.utils.math_guard_ui import show_guard_dialog, show_quota_exceeded
        from PySide6.QtWidgets import QApplication

        guard_result = ComplexityGuard.check(expr, mode=op)

        if guard_result.level == GuardLevel.REJECT:
            show_guard_dialog(self, guard_result)
            return

        if guard_result.level == GuardLevel.COMPLEX:
            choice = show_guard_dialog(self, guard_result)
            if choice == "complex":
                op = "复数运算"
            elif choice == "cancel":
                return

        if guard_result.level == GuardLevel.BLOCK:
            choice = show_guard_dialog(self, guard_result)
            if choice == "ai":
                ai = get_accelerator()
                if ai.check_quota("accelerations"):
                    obj = ai.accelerate(expr, mode=op)
                    self._last_result = obj
                    dlg = ResultDialog(f"AI 加速 — {op}", self)
                    dlg.set_result(obj)
                    dlg.exec()
                    return
                else:
                    show_quota_exceeded(self, "AI 加速")
                    choice = "cancel"
            if choice == "cancel":
                return

        if guard_result.level == GuardLevel.WARN:
            choice = show_guard_dialog(self, guard_result)
            if choice == "cancel":
                return

        # ── 极限专项防御 ──
        if op == "极限":
            from calc.math_display import ResultDialog
            import threading
            parts = [p.strip() for p in expr.split(",")]
            var = parts[1] if len(parts) > 1 else "x"
            point = parts[2] if len(parts) > 2 else "0"
            lim_result = LimitGuard.check(expr, var, point)
            if lim_result.level == GuardLevel.REJECT:
                show_guard_dialog(self, lim_result)
                return

            timeout = _cfg.get("math_guard", "limit", "timeout_seconds", default=5)
            lim_obj: list[MathObject | None] = [None]

            def _run_limit():
                try:
                    lim_obj[0] = self._do_calculate(op, expr)
                except Exception as e:
                    lim_obj[0] = MathObject(error=str(e))

            t = threading.Thread(target=_run_limit, daemon=True)
            t.start()
            t.join(timeout)
            if t.is_alive():
                obj = MathObject(error=f"极限计算超过 {timeout} 秒，建议使用 AI 辅助。")
            else:
                obj = lim_obj[0] or MathObject(error="暂不支持此功能")

            self._last_result = obj
            dlg = ResultDialog(f"计算结果 — {op}", self)
            dlg.set_result(obj)
            dlg.exec()
            return

        # ── 执行计算 ──
        from PySide6.QtWidgets import QApplication
        from calc.math_display import ResultDialog
        QApplication.processEvents()
        obj: MathObject | None = None
        try:
            obj = self._do_calculate(op, expr)
        except Exception as e:
            obj = MathObject(error=str(e))
        QApplication.processEvents()

        if obj is None:
            obj = MathObject(error="暂不支持此功能")

        self._last_result = obj
        dlg = ResultDialog(f"计算结果 — {op}", self)
        dlg.set_result(obj)
        dlg.exec()

    # ── 自定义分派逻辑 ───────────────────────────────────────

    def _do_calculate(self, op: str, expr: str) -> MathObject | None:
        """代数 / 微积分 / 复分析 操作分派。"""
        # ========== 求导 ==========
        if op == "求导":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]; var = parts[1] if len(parts) > 1 else "x"
            order = int(parts[2]) if len(parts) > 2 else 1
            return dispatch("calculus", "diff", expr=func, var=var, order=order)

        # ========== 不定积分 ==========
        if op == "不定积分":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]; var = parts[1] if len(parts) > 1 else "x"
            return dispatch("calculus", "integrate", expr=func, var=var)

        # ========== 定积分 ==========
        if op == "定积分":
            parts = [p.strip() for p in expr.split(",")]
            if len(parts) == 3:
                func, a, b = parts; var = "x"
            elif len(parts) >= 4:
                func, var, a, b = parts[0], parts[1], parts[2], parts[3]
            else:
                return MathObject(error="定积分格式：函数, 下限, 上限 或 函数, 变量, 下限, 上限")
            return dispatch("calculus", "integrate", expr=func, var=var, a=a, b=b)

        # ========== 极限 ==========
        if op == "极限":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]; var = parts[1] if len(parts) > 1 else "x"
            point = parts[2] if len(parts) > 2 else "0"
            direction = parts[3] if len(parts) > 3 else None
            return dispatch("calculus", "limit", expr=func, var=var, point=point, direction=direction)

        # ========== 解方程/组 ==========
        if op == "解方程/组":
            import re as _re_eq
            if "," in expr:
                eqs = [e.strip() for e in expr.split(",")]
                all_vars = set()
                for eq in eqs:
                    for v in _re_eq.findall(r'[a-zA-Z_]\w*', eq):
                        if v not in ("sin", "cos", "tan", "exp", "log", "sqrt", "abs"):
                            all_vars.add(v)
                all_vars = sorted(all_vars)
                if len(eqs) == 2 and len(all_vars) >= 2:
                    var1, var2 = all_vars[0], all_vars[1]
                    return dispatch("algebra", "solve_linear_system", eq1=eqs[0], eq2=eqs[1], var1=var1, var2=var2)
                else:
                    import sympy as sp
                    try:
                        syms = [sp.Symbol(v) for v in all_vars]
                        parsed_eqs = []
                        for eq in eqs:
                            if "=" in eq:
                                lhs, rhs = eq.split("=", 1)
                                parsed_eqs.append(sp.Eq(sp.sympify(lhs.strip()), sp.sympify(rhs.strip())))
                            else:
                                parsed_eqs.append(sp.sympify(eq.strip()))
                        sol = sp.solve(parsed_eqs, syms, dict=True)
                        if sol:
                            sol_dict = {str(k): str(v) for k, v in sol[0].items()}
                            return MathObject(result=sol_dict, steps=[f"方程组: {eqs}", f"解: {sol_dict}"], meaning=f"解: {sol_dict}")
                        return MathObject(result="无解", steps=[f"方程组: {eqs}", "无解"])
                    except Exception as e:
                        return MathObject(error=str(e))
            else:
                import re as _re_single
                vars_in_expr = set()
                for v in _re_single.findall(r'[a-zA-Z_]\w*', expr):
                    if v not in ("sin", "cos", "tan", "exp", "log", "sqrt", "abs"):
                        vars_in_expr.add(v)
                var = vars_in_expr.pop() if vars_in_expr else "x"
                if "**2" in expr or "^2" in expr:
                    return dispatch("algebra", "solve_quadratic", expr=expr, var=var)
                else:
                    return dispatch("algebra", "solve_linear", expr=expr, var=var)

        # ========== 表达式化简 ==========
        if op == "表达式化简":
            if "=" in expr and not expr.strip().startswith("("):
                return MathObject(error="请切换到解方程/组模式求解方程")
            has_paren = "(" in expr and ")" in expr
            has_fraction = "/" in expr
            has_sqrt = "sqrt" in expr or "**0.5" in expr
            if has_sqrt:
                return dispatch("algebra", "simplify_radical", expr=expr)
            if has_fraction:
                return dispatch("algebra", "simplify_fraction", expr=expr)
            if has_paren:
                return dispatch("algebra", "expand_expression", expr=expr)
            r1 = dispatch("algebra", "simplify_polynomial", expr=expr)
            if r1.ok:
                r2 = dispatch("algebra", "factor", expr=expr)
                if r2.ok and r2.result != r1.result:
                    r1.steps.append(f"可因式分解为: {r2.result}")
            return r1

        # ========== 泰勒展开 ==========
        if op == "泰勒展开":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]
            if len(parts) == 3:
                point, order = parts[1], int(parts[2]); var = "x"
            elif len(parts) >= 4:
                var, point, order = parts[1], parts[2], int(parts[3])
            else:
                point, order = "0", 3; var = "x"
            return dispatch("calculus", "taylor", expr=func, var=var, point=point, order=order)

        # ========== 级数求和 ==========
        if op == "级数求和":
            parts = [p.strip() for p in expr.split(",")]
            if len(parts) < 4:
                return MathObject(error="级数求和格式：通项, 变量, 起始, 终止\n示例: 1/n**2, n, 1, oo")
            term, var, a, b = parts[0], parts[1], parts[2], parts[3]
            return dispatch("calculus", "series_sum", expr=term, var=var, a=a, b=b)

        # ========== 级数敛散性 ==========
        if op == "级数敛散性":
            parts = [p.strip() for p in expr.split(",")]
            term = parts[0]; var = parts[1] if len(parts) > 1 else "n"
            return dispatch("calculus", "series_convergence", expr=term, var=var)

        # ========== 复数运算 ==========
        if op == "复数运算":
            import sympy as _sp
            expr_lower = expr.lower().strip()
            if expr_lower.startswith("exp(") and expr_lower.endswith(")"):
                return dispatch("complex_analysis", "exp_complex", z=expr[4:-1].strip())
            if expr_lower.startswith("log(") and expr_lower.endswith(")"):
                return dispatch("complex_analysis", "log_complex", z=expr[4:-1].strip())
            if expr_lower.startswith("sqrt(") and expr_lower.endswith(")"):
                return dispatch("complex_analysis", "sqrt_complex", z=expr[5:-1].strip())
            if expr_lower.startswith("mobius(") or expr_lower.startswith("mobius_transform("):
                inner = expr[expr.index("(")+1:expr.rindex(")")]
                mob_parts = [p.strip() for p in inner.split(",")]
                if len(mob_parts) == 5:
                    z_str, a, b, c, d = mob_parts
                    return dispatch("complex_analysis", "mobius_transform",
                                    z=z_str, a=complex(a), b=complex(b), c=complex(c), d=complex(d))
                return MathObject(error="mobius格式: mobius(z, a, b, c, d)")
            try:
                z_expr = expr.replace("i", "I").replace("j", "I")
                z_sym = _sp.sympify(z_expr)
                result = _sp.N(z_sym)
                return MathObject(result=complex(result), steps=[f"表达式: {expr}", f"计算结果: {result}"], meaning=f"复数运算结果: {result}")
            except Exception:
                return MathObject(error="无法解析复数表达式。支持:\nexp(1+2i) / log(-1) / sqrt(-4) / mobius(z,a,b,c,d)")

        # ========== 解不等式/组 ==========
        if op == "解不等式/组":
            import re as _re_ineq
            if "," in expr:
                ineqs = [e.strip() for e in expr.split(",")]
                vars_set = set()
                for ie in ineqs:
                    for v in _re_ineq.findall(r'[a-zA-Z_]\w*', ie):
                        if v not in ("sin", "cos", "tan", "exp", "log", "sqrt", "abs"):
                            vars_set.add(v)
                var = vars_set.pop() if vars_set else "x"
                return dispatch("algebra", "solve_inequality_system", exprs=ineqs, var=var)
            else:
                var = "x"
                for v in _re_ineq.findall(r'[a-zA-Z_]\w*', expr):
                    if v not in ("sin", "cos", "tan", "exp", "log", "sqrt", "abs"):
                        var = v; break
                if "**2" in expr or "^2" in expr:
                    return dispatch("algebra", "solve_quadratic_inequality", expr=expr, var=var)
                else:
                    return dispatch("algebra", "solve_linear_inequality", expr=expr, var=var)

        # ========== 常微分 / 偏微分（占位）==========
        if op == "常微分方程":
            return MathObject(error="常微分方程求解功能开发中")
        if op == "偏微分方程":
            return MathObject(error="偏微分方程求解功能开发中")

        return None


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    def dummy_delete(block):
        print(f"删除 block {block.block_id}")
    block = CalcBlock(0, dummy_delete)
    block.show()
    sys.exit(app.exec())
