# -*- coding: utf-8 -*-
"""BaseCalcBlock — 计算块基类。

消除 algebra / linear_algebra / numerical / probability 四个子模块中
的重复 UI 代码（布局、样式、信号连接）。子类仅需实现 get_mode_list /
get_action_map / do_dispatch 等差异化方法。
"""

from __future__ import annotations

import re as _re
from ast import literal_eval

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QWidget,
)

from MF_Mathematics.core.registry import dispatch
from MF_Mathematics.core.math_object import MathObject
# 确保 MF_UI/ 在 sys.path 中（原 calc_block 通过 main_window 保证此路径）
import sys as _sys, os as _os
_base = _os.path.dirname(_os.path.abspath(__file__))       # MF_UI/calc/
_ui   = _os.path.dirname(_base)                             # MF_UI/
_prj  = _os.path.dirname(_ui)                               # 项目根
for _p in (_prj, _ui):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

from calc.math_display import LatexLineEdit, ResultDialog


class BaseCalcBlock(QWidget):
    """计算块基类 — 输入框 + 模式下拉 + 计算/删除按钮 + 统一分派。"""

    def __init__(self, block_id: int, on_delete: callable,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.block_id = block_id
        self.on_delete = on_delete
        self._last_result: MathObject | None = None
        self._last_index = 0
        self._current_op: str = ""  # 当前选中模式名（Pattern A 子类使用）

        self._modes = self.get_mode_list()

        # ── 控件 ──
        self.input_box = LatexLineEdit(self)
        self.input_box.returnPressed.connect(self.on_calc_clicked)

        self.calc_mode_combo = QComboBox(self)
        self.calc_mode_combo.addItems(self._modes)
        self.calc_mode_combo.setCurrentIndex(self._last_index)
        self.calc_mode_combo.currentIndexChanged.connect(self.on_mode_changed)

        self.calc_btn = QPushButton("计算结果")
        self.calc_btn.setObjectName("calc_btn")
        self.calc_btn.clicked.connect(self.on_calc_clicked)

        self.delete_btn = QPushButton("✕")
        self.delete_btn.setObjectName("delete_btn")
        self.delete_btn.setFixedWidth(30)
        self.delete_btn.clicked.connect(self.on_delete_clicked)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet(
            "color: #dc2626; font-size: 11px; padding: 0 4px;")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        # ── 布局 ──
        row = QHBoxLayout()
        row.setSpacing(8)
        row.setContentsMargins(6, 6, 6, 6)
        row.addWidget(self.input_box, 1)
        row.addWidget(self.calc_mode_combo, 0)
        row.addWidget(self.calc_btn, 0)
        row.addWidget(self.delete_btn, 0)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(row)

        # 仅保留功能性内联样式（错误提示红色，不受主题影响）
        # 其他样式由 light.qss / dark.qss 统一管理

    # ── 子类覆盖 ──────────────────────────────────────────────

    def get_mode_list(self) -> list[str]:
        """返回模式名称列表。"""
        raise NotImplementedError

    def get_action_map(self) -> dict[str, tuple[str, str]]:
        """返回 {模式名: (module, action)} 映射。

        返回 {} 的模块使用 calc_engine.FUNC_MAP 作为全局映射（Pattern A）。
        """
        return {}

    def _get_module_name(self) -> str:
        """返回计算引擎模块名（如 "linear_algebra"）。"""
        raise NotImplementedError

    def on_calc_clicked(self) -> None:
        """默认分派逻辑（Pattern A：calc_engine 全局映射）。

        子类（algebra/linear_algebra/numerical/probability）可覆盖此方法。
        """
        expr = self.input_box.text().strip()
        if not expr:
            return

        action_map = self.get_action_map()
        mode = self.calc_mode_combo.currentText()

        if action_map:
            # 使用本地映射（非 Pattern A 模块）
            try:
                mod, act = action_map[mode]
            except KeyError:
                self._show_error(f"未知模式: {mode}")
                return
            expr = self._preprocess_expr(expr)
            try:
                result = self._do_dispatch(mod, act, expr)
                self._last_result = result
                dlg = ResultDialog(f"计算结果 — {mode}", self)
                dlg.set_result(result)
                dlg.exec()
            except (ValueError, TypeError, KeyError, RuntimeError,
                    AttributeError, ImportError) as e:
                dlg = ResultDialog("错误", self)
                dlg.set_result(MathObject(error=str(e)[:120]))
                dlg.exec()
        else:
            # Pattern A：使用 calc_engine.calculate()
            self._current_op = mode
            self._guarded_calculate(expr, mode)

    # ── 守卫+AI 通用计算流程 ──────────────────────────────────

    def _guarded_calculate(self, expr: str, op: str) -> None:
        """带三级守卫 + AI 加速 + 翻译的通用计算流程。

        子类（linear_algebra / numerical / probability）在
        on_calc_clicked 中调用此方法，仅需覆写 _get_module_name()
        和 _do_dispatch()。

        守卫检查在 UI 线程执行（快速），实际计算在 ComputeWorker
        后台线程执行（不阻塞 UI）。
        """
        from MF_Mathematics.utils.math_guard import ComplexityGuard, GuardLevel
        from MF_Mathematics.utils.ai_accelerator import get_accelerator
        from MF_UI.utils.math_guard_ui import show_guard_dialog, show_quota_exceeded

        # ── 数学翻译 ──
        try:
            from MF_Mathematics.utils.translator import MathTranslator
            expr = MathTranslator.human_to_computer(expr)
        except (ImportError, ValueError, TypeError):
            pass  # 翻译不可用时使用原始表达式

        # ── 三级守卫（UI 线程，快速） ──
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

        # ── 后台计算（不阻塞 UI） ──
        self._run_async(expr, op)

    def _get_compute_target(self, op: str, expr: str) -> tuple[callable, tuple]:
        """返回 (target, args) 供 ComputeWorker 执行。子类可覆写。

        Pattern A（get_action_map 为空）：使用 calc_engine.calculate(FUNC_MAP)
        非 Pattern A：使用 _do_dispatch → dispatch(module, action, **kwargs)
        """
        if self.get_action_map():
            return (self._do_dispatch, (self._get_module_name(), op, expr))
        else:
            from calc_engine import calculate as _calc
            return (_calc, (op, [expr]))

    def _run_async(self, expr: str, op: str) -> None:
        """在 ComputeWorker 后台线程中执行计算，通过信号返回结果。"""
        from compute_worker import ComputeWorker

        # 防止重复启动 — getattr 原子操作，消除 hasattr/检查 竞态窗口
        existing: ComputeWorker | None = getattr(self, '_worker', None)
        if existing is not None and existing.isRunning():
            return

        # 显示计算中状态
        self._show_computing(op)

        target, args = self._get_compute_target(op, expr)
        worker = ComputeWorker(self, target=target, args=args)
        self._worker = worker

        worker.result_ready.connect(
            lambda obj: self._on_result(obj, expr, op))
        worker.error_occurred.connect(
            lambda err: self._on_error(err, op))
        worker.finished.connect(self._on_worker_done)
        worker.start()

    def _show_computing(self, op: str) -> None:
        """显示计算中状态。"""
        self.calc_btn.setEnabled(False)
        self.calc_btn.setText("计算中…")

    def _hide_computing(self) -> None:
        """隐藏计算中状态。"""
        self.calc_btn.setEnabled(True)
        self.calc_btn.setText("计算结果")

    def _get_context_expr(self, expr: str) -> str:
        """返回用于步骤查看器上下文的表达式。子类可覆写以使用原始输入。"""
        return expr

    def _on_result(self, obj: MathObject, expr: str, op: str) -> None:
        """后台计算完成回调（主线程）。"""
        self._hide_computing()
        if obj is None:
            obj = MathObject(error="暂不支持此功能")
        self._last_result = obj
        ctx = self._get_context_expr(expr)
        dlg = ResultDialog(f"计算结果 — {op}", self)
        dlg.set_context(ctx, op)
        dlg.set_result(obj)
        dlg.exec()

    def _on_error(self, err: str, op: str) -> None:
        """后台计算错误回调（主线程）。"""
        self._hide_computing()
        dlg = ResultDialog("计算错误", self)
        dlg.set_result(MathObject(error=str(err)[:120]))
        dlg.exec()

    def _on_worker_done(self) -> None:
        """Worker 完成后的清理。"""
        self._hide_computing()
        worker: ComputeWorker | None = getattr(self, '_worker', None)
        if worker is not None:
            worker.deleteLater()
            self._worker = None

    def _preprocess_expr(self, expr: str) -> str:
        """分派前预处理表达式（子类可覆盖）。"""
        return expr

    def _do_dispatch(self, mod: str, act: str, expr: str) -> MathObject:
        """执行实际分派（子类可覆盖以添加守卫/AI 逻辑）。

        默认行为：literal_eval 解析参数 → dispatch(mod, act, ...)
        """
        if "=" in expr and expr.count("=") <= 3:
            parts = _re.split(r'[,;]\s*(?=[a-zA-Z_])', expr)
            kwargs = {}
            for p in parts:
                if "=" in p:
                    k, v = p.split("=", 1)
                    kwargs[k.strip()] = literal_eval(v.strip())
            return dispatch(mod, act, **kwargs)
        else:
            args = literal_eval(expr)
            if isinstance(args, (list, tuple)):
                return dispatch(mod, act, *args)
            else:
                return dispatch(mod, act, args)

    # ── 事件 ──────────────────────────────────────────────────

    def on_mode_changed(self, _index: int) -> None:
        self._last_result = None

    def on_delete_clicked(self) -> None:
        self.on_delete(self)

    def _show_error(self, msg: str) -> None:
        self.error_label.setText(msg)
        self.error_label.show()
