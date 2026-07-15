# -*- coding: utf-8 -*-
"""概率统计计算块 — 通过 calc_engine.calculate_direct 统一调度 + 三级守卫 + AI 加速。"""

from __future__ import annotations

import MF_Mathematics.probability  # noqa
from MF_Mathematics.core.math_object import MathObject
from MF_Mathematics.utils.math_guard import ComplexityGuard, GuardLevel
from MF_Mathematics.utils.ai_accelerator import get_accelerator
from MF_UI.calc.base_calc_block import BaseCalcBlock
from calc_engine import calculate_direct


class CalcBlock(BaseCalcBlock):
    """概率统计计算块 — 含守卫 + AI 加速。"""

    def get_mode_list(self) -> list[str]:
        return [
            "条件概率", "独立性", "全概率公式", "贝叶斯公式",
            "伯努利分布", "二项分布", "泊松分布",
            "均匀分布", "指数分布", "正态分布",
            "期望", "方差", "协方差", "相关系数",
            "大数定律", "中心极限定理",
            "样本均值", "样本方差", "矩估计", "MLE",
            "置信区间", "z检验", "t检验", "卡方检验", "p值",
            "线性回归", "预测", "残差",
        ]

    def get_action_map(self) -> dict[str, tuple[str, str]]:
        return {}

    def on_calc_clicked(self) -> None:
        expr = self.input_box.text().strip()
        if not expr:
            return

        op = self.calc_mode_combo.currentText()

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
            obj = self._do_dispatch("probability", op, expr)
        except Exception as e:
            obj = MathObject(error=str(e))
        QApplication.processEvents()

        if obj is None:
            obj = MathObject(error="暂不支持此功能")

        self._last_result = obj
        dlg = ResultDialog(f"计算结果 — {op}", self)
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
