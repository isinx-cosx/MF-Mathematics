# -*- coding: utf-8 -*-
"""代数计算块 — 继承 BaseCalcBlock，覆写分派逻辑以支持三级守卫 + AI 加速。"""

from __future__ import annotations

import MF_Mathematics.algebra       # noqa
import MF_Mathematics.calculus       # noqa
import MF_Mathematics.complex_analysis  # noqa
from MF_Mathematics.core.math_object import MathObject
from MF_Mathematics.utils.translator import MathTranslator
from MF_Mathematics.utils.math_guard import ComplexityGuard, LimitGuard, GuardLevel
from MF_Mathematics.utils.ai_accelerator import get_accelerator
from MF_Mathematics.utils.config_manager import config as _cfg
from MF_UI.calc.base_calc_block import BaseCalcBlock
from calc_engine import calculate_direct


def _show_integral_bounds_dialog(
    parent, expr: str, default_var: str = "x"
) -> tuple[str, str, str, str] | None:
    """定积分上下限选择对话框。

    Returns:
        (func, var, a, b) 或用户取消时 None。
    """
    from PySide6.QtWidgets import (QDialog, QDoubleSpinBox,
                                    QHBoxLayout, QLabel, QLineEdit,
                                    QPushButton, QVBoxLayout)

    # 尝试从已有表达式解析，预填值
    parts = [p.strip() for p in expr.split(",")]
    func = parts[0] if parts else expr
    var = default_var
    pre_a, pre_b = 0.0, 1.0
    if len(parts) == 3:
        func, a_str, b_str = parts; var = "x"
        try: pre_a = float(a_str)
        except ValueError: pass
        try: pre_b = float(b_str)
        except ValueError: pass
    elif len(parts) >= 4:
        func, var, a_str, b_str = parts[0], parts[1], parts[2], parts[3]
        try: pre_a = float(a_str)
        except ValueError: pass
        try: pre_b = float(b_str)
        except ValueError: pass

    dlg = QDialog(parent)
    dlg.setWindowTitle("定积分 — 设定上下限")
    dlg.setMinimumWidth(380)
    dlg.setStyleSheet("QDialog{background:#f8fafc;}")

    layout = QVBoxLayout(dlg); layout.setSpacing(12)
    layout.setContentsMargins(20, 16, 20, 16)

    # 被积函数
    fl = QHBoxLayout()
    fl.addWidget(QLabel("函数 f ="))
    func_input = QLineEdit(func)
    func_input.setStyleSheet(
        "QLineEdit{border:1px solid #d1d5db;border-radius:4px;padding:6px 10px;"
        "font-size:14px;background:#fff;}")
    fl.addWidget(func_input, 1)
    layout.addLayout(fl)

    # 变量
    vl = QHBoxLayout()
    vl.addWidget(QLabel("变量"))
    var_input = QLineEdit(var)
    var_input.setMaximumWidth(60)
    var_input.setStyleSheet(
        "QLineEdit{border:1px solid #d1d5db;border-radius:4px;padding:6px 8px;"
        "font-size:14px;background:#fff;}")
    vl.addWidget(var_input)
    vl.addStretch()
    layout.addLayout(vl)

    # 上下限
    bl = QHBoxLayout(); bl.setSpacing(10)
    bl.addWidget(QLabel("下限"))
    spin_a = QDoubleSpinBox()
    spin_a.setRange(-1e6, 1e6); spin_a.setValue(pre_a); spin_a.setDecimals(6)
    spin_a.setStyleSheet(
        "QDoubleSpinBox{border:1px solid #d1d5db;border-radius:4px;"
        "padding:6px 10px;font-size:14px;background:#fff;}")
    bl.addWidget(spin_a, 1)
    bl.addWidget(QLabel("上限"))
    spin_b = QDoubleSpinBox()
    spin_b.setRange(-1e6, 1e6); spin_b.setValue(pre_b); spin_b.setDecimals(6)
    spin_b.setStyleSheet(
        "QDoubleSpinBox{border:1px solid #d1d5db;border-radius:4px;"
        "padding:6px 10px;font-size:14px;background:#fff;}")
    bl.addWidget(spin_b, 1)
    layout.addLayout(bl)

    # 按钮
    btn_row = QHBoxLayout(); btn_row.addStretch()
    cancel_btn = QPushButton("取消")
    cancel_btn.setStyleSheet(
        "QPushButton{background:#f1f5f9;color:#475569;border:1px solid #d1d5db;"
        "border-radius:6px;padding:8px 20px;font-size:13px;}"
        "QPushButton:hover{background:#e2e8f0;}")
    cancel_btn.clicked.connect(dlg.reject)
    btn_row.addWidget(cancel_btn)
    ok_btn = QPushButton("计算")
    ok_btn.setStyleSheet(
        "QPushButton{background:#3b82f6;color:#fff;border:none;"
        "border-radius:6px;padding:8px 24px;font-size:13px;font-weight:500;}"
        "QPushButton:hover{background:#2563eb;}")
    ok_btn.clicked.connect(dlg.accept)
    btn_row.addWidget(ok_btn)
    layout.addLayout(btn_row)

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return (
        func_input.text().strip(),
        var_input.text().strip() or "x",
        str(spin_a.value()),
        str(spin_b.value()),
    )


def _show_series_dialog(parent, expr: str) -> tuple[str, str, str, str] | None:
    """级数求和参数对话框 — 通项/变量/起始/终止。"""
    from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel,
                                    QLineEdit, QPushButton, QVBoxLayout)
    parts = [p.strip() for p in expr.split(",")]
    pre_term = parts[0] if parts else expr
    pre_var = parts[1] if len(parts) > 1 else "n"
    pre_a = parts[2] if len(parts) > 2 else "1"
    pre_b = parts[3] if len(parts) > 3 else "oo"

    dlg = QDialog(parent); dlg.setWindowTitle("级数求和 — 参数"); dlg.setMinimumWidth(400)
    dlg.setStyleSheet("QDialog{background:#f8fafc;}")
    l = QVBoxLayout(dlg); l.setSpacing(10); l.setContentsMargins(20, 16, 20, 16)

    def _row(label, default, ph=""):
        r = QHBoxLayout(); r.addWidget(QLabel(label))
        inp = QLineEdit(default); inp.setPlaceholderText(ph)
        inp.setStyleSheet("QLineEdit{border:1px solid #d1d5db;border-radius:4px;padding:6px 10px;font-size:13px;background:#fff;}")
        r.addWidget(inp, 1); l.addLayout(r)
        return inp

    term_inp = _row("通项 a_n =", pre_term, "1/n**2")
    var_inp = _row("变量", pre_var, "n")
    a_inp = _row("起始", pre_a, "1")
    b_inp = _row("终止", pre_b, "oo")
    l.addWidget(QLabel("支持 oo（无穷）、pi、e 等"))

    btn = QHBoxLayout(); btn.addStretch()
    cancel = QPushButton("取消"); cancel.setStyleSheet("QPushButton{background:#f1f5f9;color:#475569;border:1px solid #d1d5db;border-radius:6px;padding:8px 20px;font-size:13px;}QPushButton:hover{background:#e2e8f0;}"); cancel.clicked.connect(dlg.reject); btn.addWidget(cancel)
    ok = QPushButton("计算"); ok.setStyleSheet("QPushButton{background:#3b82f6;color:#fff;border:none;border-radius:6px;padding:8px 24px;font-size:13px;font-weight:500;}QPushButton:hover{background:#2563eb;}"); ok.clicked.connect(dlg.accept); btn.addWidget(ok)
    l.addLayout(btn)

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return (term_inp.text().strip(), var_inp.text().strip() or "n",
            a_inp.text().strip() or "1", b_inp.text().strip() or "oo")


def _show_taylor_dialog(parent, func: str) -> tuple[str, str, str, int] | None:
    """泰勒展开参数对话框 — 函数/变量/展开点/阶数。"""
    from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit,
                                    QPushButton, QSpinBox, QVBoxLayout)
    dlg = QDialog(parent); dlg.setWindowTitle("泰勒展开 — 参数"); dlg.setMinimumWidth(380)
    dlg.setStyleSheet("QDialog{background:#f8fafc;}")
    l = QVBoxLayout(dlg); l.setSpacing(10); l.setContentsMargins(20, 16, 20, 16)

    def _row(label, default, ph=""):
        r = QHBoxLayout(); r.addWidget(QLabel(label))
        inp = QLineEdit(default); inp.setPlaceholderText(ph)
        inp.setStyleSheet("QLineEdit{border:1px solid #d1d5db;border-radius:4px;padding:6px 10px;font-size:13px;background:#fff;}")
        r.addWidget(inp, 1); l.addLayout(r)
        return inp

    func_inp = _row("函数 f =", func)
    var_inp = _row("变量", "x")
    point_inp = _row("展开点", "0")
    r = QHBoxLayout(); r.addWidget(QLabel("阶数")); order_spin = QSpinBox(); order_spin.setRange(1, 20); order_spin.setValue(3)
    order_spin.setStyleSheet("QSpinBox{border:1px solid #d1d5db;border-radius:4px;padding:6px 10px;font-size:13px;background:#fff;}"); r.addWidget(order_spin, 1); l.addLayout(r)

    btn = QHBoxLayout(); btn.addStretch()
    cancel = QPushButton("取消"); cancel.setStyleSheet("QPushButton{background:#f1f5f9;color:#475569;border:1px solid #d1d5db;border-radius:6px;padding:8px 20px;font-size:13px;}QPushButton:hover{background:#e2e8f0;}"); cancel.clicked.connect(dlg.reject); btn.addWidget(cancel)
    ok = QPushButton("计算"); ok.setStyleSheet("QPushButton{background:#3b82f6;color:#fff;border:none;border-radius:6px;padding:8px 24px;font-size:13px;font-weight:500;}QPushButton:hover{background:#2563eb;}"); ok.clicked.connect(dlg.accept); btn.addWidget(ok)
    l.addLayout(btn)

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return (func_inp.text().strip(), var_inp.text().strip() or "x",
            point_inp.text().strip() or "0", order_spin.value())


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
        original_expr = self.input_box.text().strip()   # 用户原始输入（步骤查看器用）
        if not original_expr:
            return

        op = self.calc_mode_combo.currentText()

        # ── 翻译 ──
        expr = original_expr
        try:
            expr = MathTranslator.human_to_computer(expr)
        except Exception:
            pass

        # ── 三级守卫 ──
        from MF_UI.utils.math_guard_ui import show_guard_dialog, show_quota_exceeded
        from calc.math_display import ResultDialog
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
                    # 定积分 → 让用户确认积分上下限
                    ai_prompt = expr
                    if op == "定积分":
                        bounds = _show_integral_bounds_dialog(self, expr)
                        if bounds is None:
                            return  # 用户取消
                        func_part, var, a, b = bounds
                        ai_prompt = f"计算 ∫({func_part})d{var}, 从 {a} 到 {b}"
                    obj = ai.accelerate(ai_prompt, mode=op)
                    self._last_result = obj
                    dlg = ResultDialog(f"AI 加速 — {op}", self)
                    dlg.set_context(original_expr, op)
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
            dlg.set_context(original_expr, op)
            dlg.set_result(obj)
            dlg.exec()
            return

        # ── 执行计算 ──
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
        dlg.set_context(original_expr, op)
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
            return calculate_direct("求导", expr=func, var=var, order=order)

        # ========== 不定积分 ==========
        if op == "不定积分":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]; var = parts[1] if len(parts) > 1 else "x"
            return calculate_direct("不定积分", expr=func, var=var)

        # ========== 定积分 ==========
        if op == "定积分":
            parts = [p.strip() for p in expr.split(",")]
            if len(parts) == 3:
                func, a, b = parts; var = "x"
            elif len(parts) >= 4:
                func, var, a, b = parts[0], parts[1], parts[2], parts[3]
            else:
                # 无上下限 → 弹窗让用户选择，默认变量 x
                func = parts[0] if parts else expr
                bounds = _show_integral_bounds_dialog(self, func, "x")
                if bounds is None:
                    return MathObject(error="已取消", meaning="用户取消")
                func, var, a, b = bounds
            return calculate_direct("定积分", expr=func, var=var, a=a, b=b)

        # ========== 极限 ==========
        if op == "极限":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]; var = parts[1] if len(parts) > 1 else "x"
            point = parts[2] if len(parts) > 2 else "0"
            direction = parts[3] if len(parts) > 3 else None
            return calculate_direct("极限", expr=func, var=var, point=point, direction=direction)

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
                    return calculate_direct("解方程组", eq1=eqs[0], eq2=eqs[1], var1=var1, var2=var2)
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
                    return calculate_direct("解一元二次", expr=expr, var=var)
                else:
                    return calculate_direct("解方程", expr=expr, var=var)

        # ========== 表达式化简 ==========
        if op == "表达式化简":
            if "=" in expr and not expr.strip().startswith("("):
                return MathObject(error="请切换到解方程/组模式求解方程")
            has_paren = "(" in expr and ")" in expr
            has_fraction = "/" in expr
            has_sqrt = "sqrt" in expr or "**0.5" in expr
            if has_sqrt:
                return calculate_direct("化简根式", expr=expr)
            if has_fraction:
                return calculate_direct("化简分式", expr=expr)
            if has_paren:
                return calculate_direct("展开", expr=expr)
            r1 = calculate_direct("化简", expr=expr)
            if r1.ok:
                r2 = calculate_direct("因式分解", expr=expr)
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
                params = _show_taylor_dialog(self, func)
                if params is None:
                    return MathObject(error="已取消", meaning="用户取消")
                func, var, point, order = params
            return calculate_direct("泰勒展开", expr=func, var=var, point=point, order=order)

        # ========== 级数求和 ==========
        if op == "级数求和":
            parts = [p.strip() for p in expr.split(",")]
            if len(parts) >= 4:
                term, var, a, b = parts[0], parts[1], parts[2], parts[3]
            else:
                params = _show_series_dialog(self, expr)
                if params is None:
                    return MathObject(error="已取消", meaning="用户取消")
                term, var, a, b = params
            return calculate_direct("级数求和", expr=term, var=var, a=a, b=b)

        # ========== 级数敛散性 ==========
        if op == "级数敛散性":
            parts = [p.strip() for p in expr.split(",")]
            term = parts[0]; var = parts[1] if len(parts) > 1 else "n"
            return calculate_direct("级数敛散性", expr=term, var=var)

        # ========== 复数运算 ==========
        if op == "复数运算":
            import sympy as _sp
            expr_lower = expr.lower().strip()
            if expr_lower.startswith("exp(") and expr_lower.endswith(")"):
                return calculate_direct("复指数", z=expr[4:-1].strip())
            if expr_lower.startswith("log(") and expr_lower.endswith(")"):
                return calculate_direct("复对数", z=expr[4:-1].strip())
            if expr_lower.startswith("sqrt(") and expr_lower.endswith(")"):
                return calculate_direct("复平方根", z=expr[5:-1].strip())
            if expr_lower.startswith("mobius(") or expr_lower.startswith("mobius_transform("):
                inner = expr[expr.index("(")+1:expr.rindex(")")]
                mob_parts = [p.strip() for p in inner.split(",")]
                if len(mob_parts) == 5:
                    z_str, a, b, c, d = mob_parts
                    return calculate_direct("莫比乌斯变换",
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
                return calculate_direct("解不等式组", exprs=ineqs, var=var)
            else:
                var = "x"
                for v in _re_ineq.findall(r'[a-zA-Z_]\w*', expr):
                    if v not in ("sin", "cos", "tan", "exp", "log", "sqrt", "abs"):
                        var = v; break
                if "**2" in expr or "^2" in expr:
                    return calculate_direct("解二次不等式", expr=expr, var=var)
                else:
                    return calculate_direct("解线性不等式", expr=expr, var=var)

        # ========== 常微分方程 ==========
        if op == "常微分方程":
            try:
                import sympy as _sp
                # 解析 dy/dx = expr 或 f'(x) = expr 或直接 dsolve
                if "=" in expr:
                    lhs, rhs = expr.split("=", 1)
                    lhs = lhs.strip(); rhs = rhs.strip()
                else:
                    rhs = expr; lhs = "f(x)"
                # 构建 sympy 函数
                x = _sp.Symbol("x")
                f = _sp.Function("f")(x)
                # 尝试识别 lhs 中的函数名
                import re as _re
                func_match = _re.match(r"([a-zA-Z]+)\(x\)", lhs)
                if func_match:
                    fname = func_match.group(1)
                    f = _sp.Function(fname)(x)
                # 将 rhs 中的 f(x) 替换
                rhs_sym = _sp.sympify(rhs.replace("f(x)", "f").replace(f"{fname}(x)" if func_match else "f(x)", "f"))
                eq = _sp.Eq(f.diff(x), rhs_sym) if func_match else _sp.Eq(_sp.Function("f")(x).diff(x), rhs_sym)
                sol = _sp.dsolve(eq)
                result = _sp.simplify(sol)
                return MathObject(result=str(result),
                    steps=[f"微分方程: {eq}", f"通解: {result}"],
                    meaning=f"常微分方程的通解为 {result}")
            except Exception as e:
                return MathObject(error=f"ODE 求解失败: {e}\n格式: dy/dx = 表达式 或 f(x) = 表达式")
        if op == "偏微分方程":
            try:
                import sympy as _sp
                x, y = _sp.symbols("x y")
                f = _sp.Function("f")(x, y)
                # 尝试 pdsolve（可能不支持所有类型）
                if "=" in expr:
                    lhs, rhs = expr.split("=", 1)
                    eq = _sp.Eq(_sp.sympify(lhs.strip()), _sp.sympify(rhs.strip()))
                else:
                    eq = _sp.Eq(f.diff(x, 2) + f.diff(y, 2), 0)
                try:
                    sol = _sp.pdsolve(eq)
                except Exception:
                    # 回退：返回特征线分析
                    return MathObject(
                        result="PDE 解析求解暂不支持此类型",
                        steps=[f"PDE: {eq}", "请使用数值方法或 AI 辅助求解"],
                        meaning="偏微分方程需要用数值方法求解")
                return MathObject(result=str(sol),
                    steps=[f"PDE: {eq}", f"解: {sol}"],
                    meaning=f"偏微分方程的解为 {sol}")
            except Exception as e:
                return MathObject(error=f"PDE 求解失败: {e}")

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
