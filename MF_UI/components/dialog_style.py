# -*- coding: utf-8 -*-
"""对话框阴影 + 圆角工具。

用法:
    from MF_UI.components.dialog_style import apply_shadow
    apply_shadow(dialog)  # 在 apply_dialog_title_bar 中自动调用
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QGraphicsDropShadowEffect, QVBoxLayout, QWidget,
)

_SHADOW_MARGIN = 10  # 阴影所需边距


def apply_shadow(dialog: QDialog) -> None:
    """为对话框添加圆角 + 主题适配投影。

    自动检测当前主题选择阴影色。
    通过容器包装为阴影腾出渲染空间。
    """
    # 透明背景 — 阴影必须
    dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    # 圆角
    s = dialog.styleSheet()
    if "border-radius" not in s:
        dialog.setStyleSheet(s + "QDialog { border-radius: 10px; }")

    # 获取现有布局，用带边距的容器包裹它
    old_layout = dialog.layout()
    # 防止双重包裹：如果对话框已有 dialogInner，跳过
    if dialog.findChild(QWidget, "dialogInner") is not None:
        return

    if old_layout is not None:
        # 将原布局从对话框中取出
        # 创建内容容器（带背景 + 圆角）
        inner = QWidget()
        inner.setObjectName("dialogInner")
        inner.setLayout(old_layout)

        # 外层布局：给阴影留空间
        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(_SHADOW_MARGIN, _SHADOW_MARGIN,
                                 _SHADOW_MARGIN, _SHADOW_MARGIN)
        outer.addWidget(inner)

    # 阴影
    color = _detect_shadow_color()
    shadow = QGraphicsDropShadowEffect(dialog)
    shadow.setBlurRadius(24)
    shadow.setOffset(0, 4)
    shadow.setColor(color)
    dialog.setGraphicsEffect(shadow)


def _detect_shadow_color() -> QColor:
    """根据当前主题返回阴影色。"""
    from PySide6.QtWidgets import QApplication
    for w in QApplication.topLevelWidgets():
        if hasattr(w, '_current_theme'):
            if w._current_theme == "dark":
                return QColor(160, 180, 208, 25)
            return QColor(26, 43, 74, 25)
    return QColor(26, 43, 74, 25)
