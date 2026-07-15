# -*- coding: utf-8 -*-
"""线性代数计算块 — 通过 calc_engine.calculate_direct 统一调度 + 三级守卫 + AI 加速。"""

from __future__ import annotations

import MF_Mathematics.linear_algebra  # noqa
from MF_Mathematics.core.math_object import MathObject
from MF_Mathematics.utils.math_guard import ComplexityGuard, GuardLevel
from MF_Mathematics.utils.ai_accelerator import get_accelerator
from MF_UI.calc.base_calc_block import BaseCalcBlock
from calc_engine import calculate_direct


class CalcBlock(BaseCalcBlock):
    """线性代数计算块 — 含守卫 + AI 加速。"""

    def get_mode_list(self) -> list[str]:
        return [
            "高斯消元", "矩阵秩", "求解方程组", "零空间",
            "特征值", "特征向量", "特征多项式", "可对角化", "对角化",
            "点积", "范数", "夹角", "正交性",
            "施密特正交化", "正交投影", "二次型", "正定性判定",
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
            obj = self._do_dispatch("linear_algebra", op, expr)
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
        """通过 calc_engine 统一调度（智能参数解析）。"""
        from ast import literal_eval
        import re as _re

        op = self.calc_mode_combo.currentText()

        # 1. 尝试 key=value 格式解析
        if "=" in expr and not expr.strip().startswith(("[", "(")):
            # 用逗号或分号分隔
            parts = _re.split(r'[,;]\s*', expr)
            kwargs = {}
            all_kv = True
            for p in parts:
                p = p.strip()
                if "=" in p:
                    k, v = p.split("=", 1)
                    k = k.strip(); v = v.strip()
                    try: kwargs[k] = literal_eval(v)
                    except (ValueError, SyntaxError): kwargs[k] = v
                elif p:
                    # 没有 = 的部分 → 尝试作为值或 var=value
                    all_kv = False
            if kwargs and all_kv:
                return calculate_direct(op, **kwargs)

        # 2. 尝试 literal_eval
        try:
            val = literal_eval(expr)
        except (ValueError, SyntaxError):
            # 3. 不是字面量 → 作为表达式字符串
            return calculate_direct(op, expr=expr)

        # 4. 字面量成功 → 根据操作类型路由参数
        if isinstance(val, (list, tuple)):
            if op in ("高斯消元", "矩阵秩", "求解方程组", "零空间",
                      "特征值", "特征向量", "特征多项式", "可对角化",
                      "对角化", "二次型", "正定性判定",
                      "施密特正交化", "正交投影"):
                return calculate_direct(op, matrix=val)
            elif op in ("范数",):
                return calculate_direct(op, vector=val)
            elif op in ("点积", "夹角", "正交性"):
                if len(val) == 2:
                    return calculate_direct(op, v1=val[0], v2=val[1])
                return calculate_direct(op, matrix=val)
            else:
                return calculate_direct(op, matrix=val)
        else:
            return calculate_direct(op, val=val)


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    def dummy_delete(block):
        print(f"删除 block {block.block_id}")
    block = CalcBlock(0, dummy_delete)
    block.show()
    sys.exit(app.exec())
