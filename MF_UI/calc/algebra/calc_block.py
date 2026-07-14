# ————————————MF-Mathematics 代数计算块———————————

# 连接后台引擎
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt

import sys
import os
# 将项目根目录加入 sys.path
_calc_block_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_calc_block_dir)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 导入后端数学库
import MF_Mathematics.algebra
import MF_Mathematics.calculus
import MF_Mathematics.complex_analysis
from MF_Mathematics.core.registry import dispatch
from MF_Mathematics.core.math_object import MathObject
from MF_Mathematics.utils.translator import MathTranslator
from MF_Mathematics.utils.math_guard import ComplexityGuard, LimitGuard, GuardLevel, GuardResult
from MF_Mathematics.utils.ai_accelerator import get_accelerator
from MF_Mathematics.utils.config_manager import config as _cfg

# 导入 LaTeX 组件
from calc.math_display import LatexLineEdit, ResultDialog


def _fix_implicit_mul(expr: str) -> str:
    """自动修复数学表达式中的隐式乘法，使 SymPy 能正确解析。

    例如:
        "6(x^3)+9(x^2)+5x-9"   → "6*(x^3)+9*(x^2)+5*x-9"
        "2sin(x)"              → "2*sin(x)"
        "(x+1)(x+2)"           → "(x+1)*(x+2)"
        "3(2+x)4"              → "3*(2+x)*4"
    """
    import re as _re

    # 数字 + 左括号: "6(" → "6*("
    expr = _re.sub(r'(\d)\(', r'\1*(', expr)
    # 右括号 + 数字: ")5" → ")*5"
    expr = _re.sub(r'\)(\d)', r')*\1', expr)
    # 数字 + 英文字母/函数名: "5x" → "5*x", "2sin" → "2*sin"
    expr = _re.sub(r'(\d)([a-zA-Z])', r'\1*\2', expr)
    # 右括号 + 左括号: ")( "→ ")*("
    expr = _re.sub(r'\)\(', r')*(', expr)
    # 右括号 + 字母: ")x" → ")*x"
    expr = _re.sub(r'\)([a-zA-Z])', r')*\1', expr)
    # 字母/数字 + 左括号（如 "x(2)" → "x*(2)" 但保留 "sin(" 等函数名）
    # 仅在不是已知函数名时插入 *
    _known_funcs = {'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
                    'arcsin', 'arccos', 'arctan',
                    'sinh', 'cosh', 'tanh',
                    'ln', 'log', 'exp', 'sqrt', 'abs',
                    'lim', 'max', 'min', 'det', 'gcd', 'lcm',
                    'int', 'sum', 'prod'}
    # 匹配 字母/数字+左括号，但仅当前面不是已知函数名
    def _insert_mul(match: _re.Match) -> str:
        before = match.group(1)
        if before.lower() in _known_funcs:
            return before + '('
        return before + '*('
    expr = _re.sub(r'([a-zA-Z]\w*|\)|\d)\(', _insert_mul, expr)

    return expr


class CalcBlock(QWidget):
    def __init__(self, block_id: int, on_delete: callable, parent=None):
        super().__init__(parent)
        self.block_id = block_id
        self.on_delete = on_delete
        self._last_result: MathObject | None = None

        self._algebra_modes = [
            "求导", "定积分", "不定积分", "极限", "解方程/组", "解不等式/组",
            "表达式化简", "泰勒展开", "级数求和", "级数敛散性",
            "复数运算",
            "常微分方程", "偏微分方程",
        ]
        self.last_algebra_index = 0

        self.input_box = LatexLineEdit(self)
        self.input_box.returnPressed.connect(self.on_calc_clicked)

        self.calc_mode_combo = QComboBox(self)
        self.calc_mode_combo.addItems(self._algebra_modes)
        self.calc_mode_combo.setCurrentIndex(self.last_algebra_index)
        self.calc_mode_combo.currentIndexChanged.connect(self.on_calc_mode_changed)

        self.calc_btn = QPushButton("计算结果")
        self.calc_btn.setObjectName("calc_btn")
        self.calc_btn.clicked.connect(self.on_calc_clicked)

        self.delete_btn = QPushButton("✕")
        self.delete_btn.setObjectName("delete_btn")
        self.delete_btn.setFixedWidth(30)
        self.delete_btn.clicked.connect(self.on_delete_btn_clicked)

        layout = QHBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 6, 6, 6)

        layout.addWidget(self.input_box, 1)
        layout.addWidget(self.calc_mode_combo, 0)
        layout.addWidget(self.calc_btn, 0)
        layout.addWidget(self.delete_btn, 0)

        self.setStyleSheet("""
            CalcBlock {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 8px;
                margin: 4px 0px;
            }

            QLineEdit {
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
                background-color: #fafafa;
                selection-background-color: #3b82f6;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
                background-color: #ffffff;
                outline: none;
            }
            QComboBox {
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
                background-color: #fafafa;
                min-width: 100px;
            }
            QComboBox:hover {
                background-color: #9ca3af;
            }
            QComboBox:on {
                background-color: #3b82f6;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::drop-arrow {
                width: 12px;
                height: 12px;
            }

            QPushButton#calc_btn {
                background-color: #3b82f6;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton#calc_btn:hover {
                background-color: #2563eb;
            }
            QPushButton#calc_btn:pressed {
                background-color: #1d4ed8;
            }

            QPushButton#delete_btn {
                background-color: transparent;
                border: none;
                color: #94a3b8;
                font-size: 16px;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton#delete_btn:hover {
                background-color: #fee2e2;
                color: #ef4444;
            }
            QPushButton#delete_btn:pressed {
                background-color: #fecaca;
            }
        """)

    # ---- 事件处理 ----
    def on_calc_clicked(self):
        """点击计算结果按钮或按回车触发计算"""
        expr = self.input_box.text().strip()
        if not expr:
            return

        # ── 数学语言 → 计算机语言 ──
        try:
            expr = MathTranslator.human_to_computer(expr)
        except Exception:
            pass

        op = self.calc_mode_combo.currentText()

        # ── 三级数学守卫 ──
        from MF_UI.utils.math_guard_ui import show_guard_dialog, show_quota_exceeded, show_ai_error

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
            # "continue" → 继续实数模式

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
            # choice == "local" → 继续本地硬算

        if guard_result.level == GuardLevel.WARN:
            choice = show_guard_dialog(self, guard_result)
            if choice == "cancel":
                return
            # "continue" → 继续

        # ── 极限专项防御 ──
        if op == "极限":
            parts = [p.strip() for p in expr.split(",")]
            var = parts[1] if len(parts) > 1 else "x"
            point = parts[2] if len(parts) > 2 else "0"
            lim_result = LimitGuard.check(expr, var, point)
            if lim_result.level == GuardLevel.REJECT:
                show_guard_dialog(self, lim_result)
                return

            # 超时计算
            import threading
            cf = _cfg()
            timeout = cf.get("math_guard", "limit", "timeout_seconds", default=5)
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
        obj: MathObject | None = None
        try:
            obj = self._do_calculate(op, expr)
        except Exception as e:
            obj = MathObject(error=str(e))

        if obj is None:
            obj = MathObject(error="暂不支持此功能")

        self._last_result = obj

        dlg = ResultDialog(f"计算结果 — {op}", self)
        dlg.set_result(obj)
        dlg.exec()

    def on_calc_mode_changed(self, index: int):
        """切换模式时清空"""
        self._last_result = None

    def on_delete_btn_clicked(self):
        """点击删除"""
        self.on_delete(self)

    def _do_calculate(self, op: str, expr: str) -> MathObject | None:
        """根据操作类型分发到后端函数。"""

        # ========== 求导 ==========
        if op == "求导":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]
            var = parts[1] if len(parts) > 1 else "x"
            order = int(parts[2]) if len(parts) > 2 else 1
            return dispatch("calculus", "diff", expr=func, var=var, order=order)

        # ========== 不定积分 ==========
        if op == "不定积分":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]
            var = parts[1] if len(parts) > 1 else "x"
            return dispatch("calculus", "integrate", expr=func, var=var)

        # ========== 定积分 ==========
        if op == "定积分":
            parts = [p.strip() for p in expr.split(",")]
            if len(parts) == 3:
                func, a, b = parts
                var = "x"
            elif len(parts) >= 4:
                func, var, a, b = parts[0], parts[1], parts[2], parts[3]
            else:
                return MathObject(error="定积分格式：函数, 下限, 上限 或 函数, 变量, 下限, 上限")
            return dispatch("calculus", "integrate", expr=func, var=var, a=a, b=b)

        # ========== 极限 ==========
        if op == "极限":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]
            var = parts[1] if len(parts) > 1 else "x"
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
                    from MF_Mathematics.core.math_object import MathObject as MO
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
                            return MO(result=sol_dict, steps=[f"方程组: {eqs}", f"解: {sol_dict}"], meaning=f"解: {sol_dict}")
                        return MO(result="无解", steps=[f"方程组: {eqs}", "无解"])
                    except Exception as e:
                        return MO(error=str(e))
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
                return MathObject(error='请切换到解方程/组模式求解方程')
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
                point, order = parts[1], int(parts[2])
                var = "x"
            elif len(parts) >= 4:
                var, point, order = parts[1], parts[2], int(parts[3])
            else:
                point, order = "0", 3
                var = "x"
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
            term = parts[0]
            var = parts[1] if len(parts) > 1 else "n"
            return dispatch("calculus", "series_convergence", expr=term, var=var)

        # ========== 复数运算 ==========
        if op == "复数运算":
            import re as _re2
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
                                    z=z_str, a=complex(a), b=complex(b),
                                    c=complex(c), d=complex(d))
                return MathObject(error="mobius格式: mobius(z, a, b, c, d)")
            try:
                z_expr = expr.replace("i", "I").replace("j", "I")
                z_sym = _sp.sympify(z_expr)
                result = _sp.N(z_sym)
                return MathObject(result=complex(result),
                                  steps=[f"表达式: {expr}", f"计算结果: {result}"],
                                  meaning=f"复数运算结果: {result}")
            except Exception:
                return MathObject(error=f"无法解析复数表达式。支持:\nexp(1+2i) / log(-1) / sqrt(-4) / mobius(z,a,b,c,d)")

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
                        var = v
                        break
                if "**2" in expr or "^2" in expr:
                    return dispatch("algebra", "solve_quadratic_inequality", expr=expr, var=var)
                else:
                    return dispatch("algebra", "solve_linear_inequality", expr=expr, var=var)

        # ========== 常微分方程 (占位) ==========
        if op == "常微分方程":
            return MathObject(error="常微分方程求解功能开发中")

        # ========== 偏微分方程 (占位) ==========
        if op == "偏微分方程":
            return MathObject(error="偏微分方程求解功能开发中")

        return None


if __name__ == "__main__":
    import sys as _sys
    app = QApplication(_sys.argv)
    def dummy_delete(block):
        print(f"删除 block {block if isinstance(block, int) else block.block_id}")
    block = CalcBlock(0, dummy_delete)
    block.show()
    _sys.exit(app.exec())