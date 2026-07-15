# -*- coding: utf-8 -*-
"""数值分析计算块 — 通过 calc_engine.calculate_direct 统一调度 + 三级守卫 + AI 加速。"""

from __future__ import annotations

import MF_Mathematics.numerical  # noqa
from MF_Mathematics.core.math_object import MathObject
from MF_Mathematics.utils.math_guard import ComplexityGuard, GuardLevel
from MF_Mathematics.utils.ai_accelerator import get_accelerator
from MF_UI.calc.base_calc_block import BaseCalcBlock
from calc_engine import calculate_direct


class CalcBlock(BaseCalcBlock):
    """数值分析计算块 — 含守卫 + AI 加速。"""

    def get_mode_list(self) -> list[str]:
        return [
            "条件数", "截断误差", "舍入误差", "稳定性判断",
            "拉格朗日插值", "牛顿插值", "三次样条", "最小二乘拟合",
            "梯形法则", "辛普森法则", "高斯求积", "数值求导", "最优步长",
            "LU分解", "雅可比迭代", "高斯-赛德尔", "共轭梯度", "幂法", "QR算法",
            "欧拉方法", "RK4", "隐式欧拉", "刚性检测",
        ]

    def get_action_map(self) -> dict[str, tuple[str, str]]:
        return {}

    def on_calc_clicked(self) -> None:
        expr = self.input_box.text().strip()
        if not expr:
            return

        op = self.calc_mode_combo.currentText()

        # ── 数学翻译 ──
        try:
            from MF_Mathematics.utils.translator import MathTranslator
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

        if guard_result.level == GuardLevel.BLOCK:
            choice = show_guard_dialog(self, guard_result)
            if choice == "ai":
                ai = get_accelerator()
                if ai.check_quota("accelerations"):
                    obj = ai.accelerate(expr, mode=op)
                    self._last_result = obj
                    dlg = ResultDialog(f"AI 加速 — {op}", self)
                    dlg.set_context(expr, op)
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

        # ── 执行计算 ──
        QApplication.processEvents()
        obj: MathObject | None = None
        try:
            obj = self._do_dispatch("numerical", op, expr)
        except Exception as e:
            obj = MathObject(error=str(e))
        QApplication.processEvents()

        if obj is None:
            obj = MathObject(error="暂不支持此功能")

        self._last_result = obj
        dlg = ResultDialog(f"计算结果 — {op}", self)
        dlg.set_context(expr, op)
        dlg.set_result(obj)
        dlg.exec()

    def _do_dispatch(self, mod: str, act: str, expr: str):
        """通过 calc_engine 统一调度。"""
        from ast import literal_eval
        import re as _re

        if "=" in expr and expr.count("=") <= 3:
            parts = _re.split(r'[,;]\s*(?=[a-zA-Z_])', expr)
            kwargs = {}
            for p in parts:
                if "=" in p:
                    k, v = p.split("=", 1)
                    kwargs[k.strip()] = literal_eval(v.strip())
            return calculate_direct(self.calc_mode_combo.currentText(), **kwargs)
        else:
            args = literal_eval(expr)
            if isinstance(args, (list, tuple)):
                return calculate_direct(self.calc_mode_combo.currentText(), *args)
            else:
                return calculate_direct(self.calc_mode_combo.currentText(), args)


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    def dummy_delete(block):
        print(f"删除 block {block.block_id}")
    block = CalcBlock(0, dummy_delete)
    block.show()
    sys.exit(app.exec())
