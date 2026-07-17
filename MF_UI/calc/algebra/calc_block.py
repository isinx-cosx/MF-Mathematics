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
from MF_Mathematics.core.helpers import safe_sympify

from PySide6.QtCore import QThread, QTimer, Signal


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
    dlg.setObjectName("integralBoundsDialog")

    layout = QVBoxLayout(dlg); layout.setSpacing(12)
    layout.setContentsMargins(20, 16, 20, 16)

    # 被积函数
    fl = QHBoxLayout()
    fl.addWidget(QLabel("函数 f ="))
    func_input = QLineEdit(func)
    fl.addWidget(func_input, 1)
    layout.addLayout(fl)

    # 变量
    vl = QHBoxLayout()
    vl.addWidget(QLabel("变量"))
    var_input = QLineEdit(var)
    var_input.setMaximumWidth(60)
    vl.addWidget(var_input)
    vl.addStretch()
    layout.addLayout(vl)

    # 上下限
    bl = QHBoxLayout(); bl.setSpacing(10)
    bl.addWidget(QLabel("下限"))
    spin_a = QDoubleSpinBox()
    spin_a.setRange(-1e6, 1e6); spin_a.setValue(pre_a); spin_a.setDecimals(6)
    bl.addWidget(spin_a, 1)
    bl.addWidget(QLabel("上限"))
    spin_b = QDoubleSpinBox()
    spin_b.setRange(-1e6, 1e6); spin_b.setValue(pre_b); spin_b.setDecimals(6)
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

    from MF_UI.components.mf_dialog import apply_dialog_title_bar
    apply_dialog_title_bar(dlg, "定积分")

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
    dlg.setObjectName("seriesDialog")
    l = QVBoxLayout(dlg); l.setSpacing(10); l.setContentsMargins(20, 16, 20, 16)

    def _row(label, default, ph=""):
        r = QHBoxLayout(); r.addWidget(QLabel(label))
        inp = QLineEdit(default); inp.setPlaceholderText(ph)
        r.addWidget(inp, 1); l.addLayout(r)
        return inp

    term_inp = _row("通项 a_n =", pre_term, "1/n**2")
    var_inp = _row("变量", pre_var, "n")
    a_inp = _row("起始", pre_a, "1")
    b_inp = _row("终止", pre_b, "oo")
    l.addWidget(QLabel("支持 oo（无穷）、pi、e 等"))

    btn = QHBoxLayout(); btn.addStretch()
    cancel = QPushButton("取消"); cancel.setObjectName("ai_secondary_btn"); cancel.clicked.connect(dlg.reject); btn.addWidget(cancel)
    ok = QPushButton("计算"); ok.setObjectName("ai_send_btn"); ok.clicked.connect(dlg.accept); btn.addWidget(ok)
    l.addLayout(btn)

    from MF_UI.components.mf_dialog import apply_dialog_title_bar
    apply_dialog_title_bar(dlg, "级数求和")

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return (term_inp.text().strip(), var_inp.text().strip() or "n",
            a_inp.text().strip() or "1", b_inp.text().strip() or "oo")


def _show_taylor_dialog(parent, func: str) -> tuple[str, str, str, int] | None:
    """泰勒展开参数对话框 — 函数/变量/展开点/阶数。"""
    from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit,
                                    QPushButton, QSpinBox, QVBoxLayout)
    dlg = QDialog(parent); dlg.setWindowTitle("泰勒展开 — 参数"); dlg.setMinimumWidth(380)
    dlg.setObjectName("taylorDialog")
    l = QVBoxLayout(dlg); l.setSpacing(10); l.setContentsMargins(20, 16, 20, 16)

    def _row(label, default, ph=""):
        r = QHBoxLayout(); r.addWidget(QLabel(label))
        inp = QLineEdit(default); inp.setPlaceholderText(ph)
        r.addWidget(inp, 1); l.addLayout(r)
        return inp

    func_inp = _row("函数 f =", func)
    var_inp = _row("变量", "x")
    point_inp = _row("展开点", "0")
    r = QHBoxLayout(); r.addWidget(QLabel("阶数")); order_spin = QSpinBox(); order_spin.setRange(1, 20); order_spin.setValue(3)
    r.addWidget(order_spin, 1); l.addLayout(r)

    btn = QHBoxLayout(); btn.addStretch()
    cancel = QPushButton("取消"); cancel.setObjectName("ai_secondary_btn"); cancel.clicked.connect(dlg.reject); btn.addWidget(cancel)
    ok = QPushButton("计算"); ok.setObjectName("ai_send_btn"); ok.clicked.connect(dlg.accept); btn.addWidget(ok)
    l.addLayout(btn)

    from MF_UI.components.mf_dialog import apply_dialog_title_bar
    apply_dialog_title_bar(dlg, "泰勒展开")

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return (func_inp.text().strip(), var_inp.text().strip() or "x",
            point_inp.text().strip() or "0", order_spin.value())


class CalcBlock(BaseCalcBlock):
    """代数计算块 — 含守卫 + AI 加速 + 极限超时。"""

    def get_mode_list(self) -> list[str]:
        return [
            "求导", "某点导数", "隐函数求导", "参数方程求导",
            "定积分", "不定积分", "数值积分", "反常积分",
            "极限", "连续性判断", "间断点分类", "洛必达法则",
            "单调性", "局部极值", "全局最值",
            "解方程/组", "解不等式/组",
            "表达式化简", "泰勒展开", "幂级数展开", "级数求和", "级数敛散性",
            "复数运算",
            "常微分方程", "偏微分方程",
            # ── 微积分应用 ──
            "微分", "罗尔定理", "拉格朗日中值定理",
            "曲线间面积", "旋转体体积(圆盘法)", "旋转体体积(柱壳法)", "弧长",
            "幂级数收敛半径",
            "莱布尼茨判别法", "极限比较判别法", "积分判别法",
            "直接比较判别法", "p-级数判别法", "综合判别与分类",
            # ── 排列组合 ──
            "排列数", "组合数", "二项式展开", "二项式通项",
            # ── 数值补充 ──
            "梯度下降", "相图",
            # ── 复数分析补充 ──
            "回路积分", "柯西定理", "柯西积分公式",
            "洛朗级数", "奇点分类", "留数", "留数定理",
            "辐角原理", "Rouche 定理",
            "Zeta 级数", "Zeta 解析延拓", "Zeta 函数方程", "Zeta 非平凡零点",
            # ── 基础运算 ──
            "绝对值", "数轴距离", "比与比例", "百分数", "百分变化率",
            "科学记数法", "有效数字",
            # ── 三角函数 ──
            "三角函数求值", "三角恒等式", "三角周期性",
            # ── 函数分析 ──
            "函数定义域", "函数值域估计", "线性函数",
            "二次函数", "二次函数极值", "幂函数", "指数函数", "对数函数",
            # ── 因式分解 ──
            "提取公因式", "完全平方公式", "平方差公式", "十字相乘法", "分组分解法",
            # ── 分式/根式 ──
            "通分", "分式运算", "分母有理化", "同类根式判定", "根式运算",
            # ── 组合/不等式/证明 ──
            "组合恒等式", "对应法则", "斜率截距", "反比例函数",
            "不等式性质", "最值初步",
            "加法原理", "乘法原理",
            "交换律验证", "结合律验证", "分配律验证",
            # ── 概率补充 ──
            "分布函数", "概率质量函数", "概率密度函数",
            # ── 傅里叶分析 ──
            "傅里叶系数", "傅里叶级数", "复傅里叶系数", "正交性验证",
            "傅里叶变换", "逆傅里叶变换", "普兰舍利定理",
            "高斯函数傅里叶变换",
            "卷积", "卷积定理", "高斯模糊", "低通滤波器",
            "δ 分布", "δ 的傅里叶变换", "常数的傅里叶变换", "缓增分布",
            "不确定性原理", "短时傅里叶变换", "小波变换",
            "泊松求和", "Theta 函数", "函数方程演示",
        ]

    def get_action_map(self) -> dict[str, tuple[str, str]]:
        # algebra 使用自定义分派逻辑（_do_calculate），不使用 action_map
        return {}

    def _get_compute_target(self, op: str, expr: str) -> tuple[callable, tuple]:
        """代数计算使用 _do_calculate 而非 _do_dispatch。"""
        return (self._do_calculate, (op, expr))

    def _get_context_expr(self, expr: str) -> str:
        """使用用户原始输入作为步骤查看器上下文。"""
        return getattr(self, '_original_expr', expr)

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
            # 防止重复启动极限计算
            if hasattr(self, '_limit_worker') and self._limit_worker is not None:
                if self._limit_worker.isRunning():
                    return

            parts = [p.strip() for p in expr.split(",")]
            var = parts[1] if len(parts) > 1 else "x"
            point = parts[2] if len(parts) > 2 else "0"
            lim_result = LimitGuard.check(expr, var, point)
            if lim_result.level == GuardLevel.REJECT:
                show_guard_dialog(self, lim_result)
                return

            timeout = _cfg.get("math_guard", "limit", "timeout_seconds", default=5)

            # 使用 QThread 代替 threading.Thread，避免阻塞 UI 线程。
            # ★ 传 target 函数而非依赖 parent() → 防止 widget 销毁后 segfault
            _calc_target = self._do_calculate  # bound method，持有 self 引用

            class _LimitWorker(QThread):
                result_ready = Signal(object)

                def __init__(self, target, op, expr, parent=None):
                    super().__init__(parent)
                    self._target = target
                    self._op = op
                    self._expr = expr

                def run(self):
                    try:
                        obj = self._target(self._op, self._expr)
                    except Exception as e:
                        obj = MathObject(error=str(e))
                    if not self.isInterruptionRequested():
                        self.result_ready.emit(obj)

            worker = _LimitWorker(_calc_target, op, expr, self)
            worker.setObjectName("LimitWorker")
            self._limit_worker = worker

            # 超时定时器 — connect finished→stop 防止 worker 结束后 timer 仍触发
            timeout_timer = QTimer(worker)
            timeout_timer.setSingleShot(True)
            worker.finished.connect(timeout_timer.stop)

            def _on_timeout():
                worker.requestInterruption()
                timeout_obj = MathObject(
                    error=f"极限计算超过 {timeout} 秒，建议使用 AI 辅助。"
                )
                self._last_result = timeout_obj
                dlg = ResultDialog(f"计算结果 — {op}", self)
                dlg.set_context(original_expr, op)
                dlg.set_result(timeout_obj)
                dlg.exec()

            def _on_result(obj: MathObject):
                timeout_timer.stop()
                self._limit_worker = None
                self._last_result = obj
                dlg = ResultDialog(f"计算结果 — {op}", self)
                dlg.set_context(original_expr, op)
                dlg.set_result(obj)
                dlg.exec()

            def _on_cleanup():
                timeout_timer.stop()
                self._limit_worker = None

            timeout_timer.timeout.connect(_on_timeout)
            worker.result_ready.connect(_on_result)
            worker.finished.connect(_on_cleanup)
            timeout_timer.start(int(timeout * 1000))
            worker.start()
            return

        # ── 执行计算（后台线程，不阻塞 UI） ──
        self._original_expr = original_expr
        self._run_async(expr, op)

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
                                parsed_eqs.append(sp.Eq(safe_sympify(lhs.strip()), safe_sympify(rhs.strip())))
                            else:
                                parsed_eqs.append(safe_sympify(eq.strip()))
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

            # 总是先调用化简（已内置 factor vs simplify 对比）
            r1 = calculate_direct("化简", expr=expr)

            # 对特殊形式也尝试专用函数，取最佳结果
            has_fraction = "/" in expr
            has_sqrt = "sqrt" in expr or "**0.5" in expr

            if has_sqrt and r1.ok:
                r_sqrt = calculate_direct("化简根式", expr=expr)
                if r_sqrt.ok:
                    try:
                        import sympy as _sp2
                        if _sp2.count_ops(_sp2.sympify(str(r_sqrt.result))) < _sp2.count_ops(_sp2.sympify(str(r1.result))):
                            return r_sqrt
                    except Exception:
                        pass

            if has_fraction and r1.ok:
                r_frac = calculate_direct("化简分式", expr=expr)
                if r_frac.ok:
                    try:
                        import sympy as _sp2
                        if _sp2.count_ops(_sp2.sympify(str(r_frac.result))) < _sp2.count_ops(_sp2.sympify(str(r1.result))):
                            return r_frac
                    except Exception:
                        pass

            if r1.ok:
                r2 = calculate_direct("因式分解", expr=expr)
                if r2.ok and str(r2.result) != str(r1.result):
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
                z_sym = safe_sympify(z_expr)
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

        # ========== 某点导数 ==========
        if op == "某点导数":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]; var = parts[1] if len(parts) > 1 else "x"
            point = parts[2] if len(parts) > 2 else "0"
            return calculate_direct("某点导数", expr=func, var=var, point=point)

        # ========== 隐函数求导 ==========
        if op == "隐函数求导":
            parts = [p.strip() for p in expr.split(",")]
            eq = parts[0]; var = parts[1] if len(parts) > 1 else "x"
            dep_var = parts[2] if len(parts) > 2 else "y"
            return calculate_direct("隐函数求导", eq=eq, var=var, dep_var=dep_var)

        # ========== 参数方程求导 ==========
        if op == "参数方程求导":
            parts = [p.strip() for p in expr.split(",")]
            x_expr = parts[0]; y_expr = parts[1] if len(parts) > 1 else ""
            t_var = parts[2] if len(parts) > 2 else "t"
            return calculate_direct("参数方程求导", x_expr=x_expr, y_expr=y_expr, t=t_var)

        # ========== 数值积分 ==========
        if op == "数值积分":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]; var = parts[1] if len(parts) > 1 else "x"
            kwargs = {"f": func, "var": var}
            if len(parts) >= 4:
                kwargs["a"] = float(parts[2]) if len(parts) > 2 else 0
                kwargs["b"] = float(parts[3]) if len(parts) > 3 else 1
            return calculate_direct("数值积分", **kwargs)

        # ========== 反常积分 ==========
        if op == "反常积分":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]; var = parts[1] if len(parts) > 1 else "x"
            a = parts[2] if len(parts) > 2 else "-oo"
            b = parts[3] if len(parts) > 3 else "oo"
            return calculate_direct("反常积分", expr=func, var=var, a=a, b=b)

        # ========== 连续性判断 ==========
        if op == "连续性判断":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]; var = parts[1] if len(parts) > 1 else "x"
            point = parts[2] if len(parts) > 2 else "0"
            return calculate_direct("连续性判断", expr=func, var=var, point=point)

        # ========== 间断点分类 ==========
        if op == "间断点分类":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]; var = parts[1] if len(parts) > 1 else "x"
            point = parts[2] if len(parts) > 2 else "0"
            return calculate_direct("间断点分类", expr=func, var=var, point=point)

        # ========== 洛必达法则 ==========
        if op == "洛必达法则":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]; var = parts[1] if len(parts) > 1 else "x"
            point = parts[2] if len(parts) > 2 else "0"
            return calculate_direct("洛必达法则", expr=func, var=var, point=point)

        # ========== 单调性 ==========
        if op == "单调性":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]; var = parts[1] if len(parts) > 1 else "x"
            return calculate_direct("单调性", expr=func, var=var)

        # ========== 局部极值 ==========
        if op == "局部极值":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]; var = parts[1] if len(parts) > 1 else "x"
            return calculate_direct("局部极值", expr=func, var=var)

        # ========== 全局最值 ==========
        if op == "全局最值":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]; var = parts[1] if len(parts) > 1 else "x"
            interval_start = parts[2] if len(parts) > 2 else "0"
            interval_end = parts[3] if len(parts) > 3 else "1"
            try:
                a_val = float(interval_start); b_val = float(interval_end)
                interval = (a_val, b_val)
            except ValueError:
                interval = (0, 1)
            return calculate_direct("全局最值", expr=func, var=var, interval=interval)

        # ========== 幂级数展开 ==========
        if op == "幂级数展开":
            parts = [p.strip() for p in expr.split(",")]
            func = parts[0]; var = parts[1] if len(parts) > 1 else "x"
            point_str = parts[2] if len(parts) > 2 else "0"
            try:
                point_val = int(point_str) if point_str.isdigit() or point_str.lstrip('-').isdigit() else float(point_str)
            except (ValueError, AttributeError):
                point_val = point_str  # 符号如 "a", "pi" 保持原样
            try: order = int(parts[3]) if len(parts) > 3 else 5
            except ValueError: order = 5
            return calculate_direct("幂级数展开", expr=func, var=var, point=point_val, n=order)

        # ========== 常微分方程 ==========
        if op == "常微分方程":
            try:
                import sympy as _sp
                import re as _re

                # 1. 分离左右
                if "=" in expr:
                    lhs, rhs = expr.split("=", 1)
                    lhs = lhs.strip(); rhs = rhs.strip()
                else:
                    rhs = expr; lhs = "y'"

                # 2. 识别自变量（默认 x）
                x_sym = _sp.Symbol("x")

                # 3. 识别 lhs 中的函数名和导数阶数
                # 支持: y', y'', y''', dy/dx, d2y/dx2, f'(x)
                fname = "y"
                order = 1
                var = "x"

                # y''' / y'' / y'
                m_deriv = _re.match(r"^([a-zA-Z]+)('+)$", lhs)
                # dy/dx 或 d2y/dx2
                m_leibniz = _re.match(r"^d(\d*)([a-zA-Z]+)/d([a-zA-Z]+)\^?\d*$", lhs)
                # f(x)' 或 f(x)''
                m_func = _re.match(r"^([a-zA-Z]+)\(([a-zA-Z]+)\)('+)$", lhs)

                if m_deriv:
                    fname = m_deriv.group(1)
                    order = len(m_deriv.group(2))
                elif m_leibniz:
                    order = int(m_leibniz.group(1)) if m_leibniz.group(1) else 1
                    fname = m_leibniz.group(2)
                    var = m_leibniz.group(3)
                elif m_func:
                    fname = m_func.group(1)
                    var = m_func.group(2)
                    order = len(m_func.group(3))

                x_sym = _sp.Symbol(var)
                f = _sp.Function(fname)(x_sym)

                # 4. 构建导数项
                if order == 1:
                    deriv = f.diff(x_sym)
                else:
                    deriv = f.diff(x_sym, order)

                # 5. 解析 rhs — 将函数名替换为 sympy Function 引用
                #    例如 rhs="y/x" → y 是 Function("y")(x)
                rhs_clean = rhs
                # 先替换 f(x) 形式
                rhs_clean = _re.sub(rf'\b{fname}\s*\(\s*{var}\s*\)', f'{fname}_func', rhs_clean)
                if not rhs_clean:
                    rhs_clean = rhs
                try:
                    # 建立局部变量映射
                    local_dict = {fname: f, var: x_sym,
                                  "sin": _sp.sin, "cos": _sp.cos, "tan": _sp.tan,
                                  "exp": _sp.exp, "log": _sp.log, "sqrt": _sp.sqrt,
                                  "pi": _sp.pi, "E": _sp.E, "oo": _sp.oo,
                                  "derivative": lambda e, v=None:
                                      _sp.diff(e, v if v is not None else x_sym)}
                    rhs_sym = _sp.sympify(rhs, locals=local_dict)
                except Exception:
                    # 回退：直接 sympify
                    rhs_sym = safe_sympify(rhs)

                eq = _sp.Eq(deriv, rhs_sym)
                sol = _sp.dsolve(eq)
                result = _sp.simplify(sol.rhs) if hasattr(sol, 'rhs') else sol

                return MathObject(
                    result=str(sol),
                    steps=[
                        f"微分方程: {eq}",
                        f"类型: {order} 阶常微分方程",
                        f"通解: {sol}",
                    ],
                    meaning=f"常微分方程 {eq} 的通解为 {sol}",
                )
            except Exception as e:
                return MathObject(
                    error=f"ODE 求解失败: {e}\n"
                          f"支持格式: y'=f(x,y), y''+y=0, dy/dx=f(x,y), f(x)'=expr")
        if op == "偏微分方程":
            try:
                import sympy as _sp
                x, y = _sp.symbols("x y")
                f = _sp.Function("f")(x, y)
                if "=" in expr:
                    lhs, rhs = expr.split("=", 1)
                    eq = _sp.Eq(safe_sympify(lhs.strip()), safe_sympify(rhs.strip()))
                else:
                    eq = _sp.Eq(f.diff(x, 2) + f.diff(y, 2), 0)
                try:
                    sol = _sp.pdsolve(eq)
                except Exception:
                    return MathObject(
                        result="PDE 解析求解暂不支持此类型",
                        steps=[f"PDE: {eq}", "请使用数值方法或 AI 辅助求解"],
                        meaning="偏微分方程需要用数值方法求解")
                return MathObject(result=str(sol),
                    steps=[f"PDE: {eq}", f"解: {sol}"],
                    meaning=f"偏微分方程的解为 {sol}")
            except Exception as e:
                return MathObject(error=f"PDE 求解失败: {e}")

        # ========== 微积分应用 / 组合 / 数值 / 复数 / 基础 / 三角 / 函数 / 因式分解 / 概率 ==========
        _PASS_THROUGH = {
            "微分", "罗尔定理", "拉格朗日中值定理",
            "曲线间面积", "旋转体体积(圆盘法)", "旋转体体积(柱壳法)", "弧长",
            "幂级数收敛半径",
            "莱布尼茨判别法", "极限比较判别法", "积分判别法",
            "直接比较判别法", "p-级数判别法", "综合判别与分类",
            "排列数", "组合数", "二项式展开", "二项式通项",
            "梯度下降", "相图",
            "回路积分", "柯西定理", "柯西积分公式",
            "洛朗级数", "奇点分类", "留数", "留数定理",
            "辐角原理", "Rouche 定理",
            "Zeta 级数", "Zeta 解析延拓", "Zeta 函数方程", "Zeta 非平凡零点",
            "绝对值", "数轴距离", "比与比例", "百分数", "百分变化率",
            "科学记数法", "有效数字",
            "三角函数求值", "三角恒等式", "三角周期性",
            "函数定义域", "函数值域估计", "线性函数",
            "二次函数", "二次函数极值", "幂函数", "指数函数", "对数函数",
            "提取公因式", "完全平方公式", "平方差公式", "十字相乘法", "分组分解法",
            "通分", "分式运算", "分母有理化", "同类根式判定", "根式运算",
            "组合恒等式", "对应法则", "斜率截距", "反比例函数",
            "不等式性质", "最值初步",
            "加法原理", "乘法原理",
            "交换律验证", "结合律验证", "分配律验证",
            "分布函数", "概率质量函数", "概率密度函数",
        }
        if op in _PASS_THROUGH:
            return calculate(op, [expr])

        # ========== 傅里叶分析 ==========
        if op in ("傅里叶系数", "傅里叶级数", "复傅里叶系数", "正交性验证",
                  "傅里叶变换", "逆傅里叶变换", "普兰舍利定理",
                  "高斯函数傅里叶变换",
                  "卷积", "卷积定理", "高斯模糊", "低通滤波器",
                  "δ 分布", "δ 的傅里叶变换", "常数的傅里叶变换", "缓增分布",
                  "不确定性原理", "短时傅里叶变换", "小波变换",
                  "泊松求和", "Theta 函数", "函数方程演示"):
            return calculate(op, [expr])

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
