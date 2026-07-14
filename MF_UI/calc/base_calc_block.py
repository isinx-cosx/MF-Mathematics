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
        """返回 {模式名: (module, action)} 映射。"""
        raise NotImplementedError

    def on_calc_clicked(self) -> None:
        """默认分派逻辑 — 子类可覆盖。"""
        expr = self.input_box.text().strip()
        if not expr:
            return

        mode = self.calc_mode_combo.currentText()
        action_map = self.get_action_map()

        try:
            mod, act = action_map[mode]
        except KeyError:
            self._show_error(f"未知模式: {mode}")
            return

        # 允许子类在分派前预处理表达式
        expr = self._preprocess_expr(expr)

        try:
            result = self._do_dispatch(mod, act, expr)
            self._last_result = result

            dlg = ResultDialog(f"计算结果 — {mode}", self)
            dlg.set_result(result)
            dlg.exec()

        except Exception as e:
            dlg = ResultDialog("错误", self)
            dlg.set_result(MathObject(error=str(e)[:120]))
            dlg.exec()

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
