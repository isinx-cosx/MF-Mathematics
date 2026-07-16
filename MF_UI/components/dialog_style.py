# -*- coding: utf-8 -*-
"""对话框阴影 + 圆角工具。

用法:
    from MF_UI.components.dialog_style import apply_shadow
    apply_shadow(dialog)  # 在对话框 _build_ui() 末尾调用
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QGraphicsDropShadowEffect


def apply_shadow(dialog: QDialog) -> None:
    """为对话框添加圆角 + 主题适配投影。"""
    # 圆角
    s = dialog.styleSheet()
    if "border-radius" not in s:
        dialog.setStyleSheet(s + "QDialog { border-radius: 10px; }")

    # 阴影颜色根据主题选择
    from PySide6.QtWidgets import QApplication
    color = _detect_shadow_color()

    shadow = QGraphicsDropShadowEffect(dialog)
    shadow.setBlurRadius(20)
    shadow.setOffset(0, 3)
    shadow.setColor(color)
    dialog.setGraphicsEffect(shadow)


def _detect_shadow_color() -> QColor:
    """根据当前主题返回阴影色。"""
    from PySide6.QtWidgets import QApplication
    for w in QApplication.topLevelWidgets():
        if hasattr(w, '_current_theme'):
            theme = w._current_theme
            if theme == "dark":
                return QColor(160, 180, 208, 25)   # #a0b4d0 10%
            return QColor(26, 43, 74, 25)          # #1a2b4a 10%
    # 默认亮色
    return QColor(26, 43, 74, 25)
