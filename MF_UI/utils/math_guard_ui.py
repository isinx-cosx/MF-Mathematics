# -*- coding: utf-8 -*-
"""数学守卫 UI 交互层 — 弹窗提示与用户选择。

将核心层的 GuardResult 转换为可视化的对话框，
提供统一的用户交互体验。

依赖: PySide6 + MF_Mathematics.utils.math_guard
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from MF_Mathematics.utils.math_guard import GuardLevel, GuardResult


# ═══════════════════════════════════════════════════════════════════════
#  GuardDialog — 统一守卫弹窗
# ═══════════════════════════════════════════════════════════════════════


def show_guard_dialog(parent: QWidget | None, result: GuardResult) -> str:
    """根据 GuardResult.level 显示对应弹窗并返回用户选择。

    Returns:
        "continue" | "cancel" | "local" | "ai" | "complex" | "rejected"
    """
    if result.level == GuardLevel.REJECT:
        QMessageBox.critical(parent, result.title, result.message)
        return "rejected"

    if result.level == GuardLevel.WARN:
        # 慢速预警 → 继续 / 取消
        reply = QMessageBox.warning(
            parent, result.title, result.message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return "continue" if reply == QMessageBox.StandardButton.Yes else "cancel"

    if result.level == GuardLevel.BLOCK:
        # 爆炸风险 → 本地硬算 / AI 加速 / 取消
        return _show_block_dialog(parent, result)

    if result.level == GuardLevel.COMPLEX:
        # 数域切换 → 切换复数 / 继续实数
        reply = QMessageBox.question(
            parent, result.title, result.message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return "complex" if reply == QMessageBox.StandardButton.Yes else "continue"

    return "continue"


def _show_block_dialog(parent: QWidget | None, result: GuardResult) -> str:
    """2 级拦截弹窗 — 三选项：本地硬算 / AI 加速 / 取消。"""
    dlg = QDialog(parent)
    dlg.setWindowTitle(result.title)
    dlg.setMinimumWidth(420)

    layout = QVBoxLayout(dlg)
    layout.setSpacing(16)
    layout.setContentsMargins(24, 20, 24, 20)

    # 消息
    msg = QLabel(result.message)
    msg.setWordWrap(True)
    msg.setStyleSheet("font-size: 14px; line-height: 1.6;")
    layout.addWidget(msg)

    # 按钮
    btn_box = QDialogButtonBox(dlg)

    btn_local = QPushButton("本地硬算")
    btn_local.setStyleSheet(
        "QPushButton { background: #f59e0b; color: #fff; border: none;"
        " border-radius: 6px; padding: 10px 20px; font-size: 13px; font-weight: 500; }"
        "QPushButton:hover { background: #d97706; }")
    btn_local.clicked.connect(lambda: dlg.done(1))

    btn_ai = QPushButton("AI 加速")
    btn_ai.setStyleSheet(
        "QPushButton { background: #8b5cf6; color: #fff; border: none;"
        " border-radius: 6px; padding: 10px 20px; font-size: 13px; font-weight: 500; }"
        "QPushButton:hover { background: #7c3aed; }")
    btn_ai.clicked.connect(lambda: dlg.done(2))

    btn_cancel = QPushButton("算了吧")
    btn_cancel.setStyleSheet(
        "QPushButton { background: #e2e8f0; color: #475569; border: none;"
        " border-radius: 6px; padding: 10px 20px; font-size: 13px; }"
        "QPushButton:hover { background: #cbd5e1; }")
    btn_cancel.clicked.connect(lambda: dlg.done(0))

    btn_box.addButton(btn_local, QDialogButtonBox.ButtonRole.AcceptRole)
    btn_box.addButton(btn_ai, QDialogButtonBox.ButtonRole.AcceptRole)
    btn_box.addButton(btn_cancel, QDialogButtonBox.ButtonRole.RejectRole)
    layout.addWidget(btn_box)

    dlg.setObjectName("guardDialog")

    from MF_UI.components.mf_dialog import apply_dialog_title_bar
    apply_dialog_title_bar(dlg, result.title)

    code = dlg.exec()
    if code == 1:
        return "local"
    elif code == 2:
        return "ai"
    return "cancel"


# ═══════════════════════════════════════════════════════════════════════
#  AI 配额提示
# ═══════════════════════════════════════════════════════════════════════


def show_quota_exceeded(parent: QWidget | None, quota_type: str = "步骤生成") -> None:
    """配额用完提示。"""
    QMessageBox.warning(
        parent, "配额不足",
        f"今日{quota_type}次数已用完。\n请配置 API Key 或明日再试。",
    )


def show_ai_error(parent: QWidget | None, detail: str = "") -> None:
    """AI 调用失败提示。"""
    QMessageBox.critical(
        parent, "AI 加速失败",
        f"AI 服务调用失败。{detail}\n请检查网络连接或 API Key 配置。",
    )
