# -*- coding: utf-8 -*-
"""OverlayWidget — 半透明遮罩 + UI 高亮组件，用于交互式引导向导。"""

from __future__ import annotations

from PySide6.QtCore import (
    Qt, QRectF, QPointF, QPropertyAnimation, QEasingCurve,
    Signal, QTimer,
)
from PySide6.QtGui import (
    QPainter, QBrush, QColor, QPen, QPainterPath, QFont,
)
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QApplication,
)


# ── 样式常量 ──────────────────────────────────────────────────

_OVERLAY_LIGHT = QColor(0, 0, 0, 115)   # 亮色遮罩
_OVERLAY_DARK = QColor(0, 0, 0, 140)     # 暗色遮罩
_HIGHLIGHT_BORDER = QColor("#3b82f6")     # 高亮边框颜色
_HIGHLIGHT_GLOW = QColor(59, 130, 246, 60)  # 发光色

_TOOLTIP_STYLE = """
    QWidget#tooltip_container {
        background: #ffffff;
        border: 1px solid #d1d5db;
        border-radius: 10px;
    }
    QLabel#tooltip_text {
        color: #1e293b;
        font-size: 14px;
        line-height: 1.6;
        padding: 4px;
        background: transparent;
    }
    QLabel#tooltip_counter {
        color: #94a3b8;
        font-size: 11px;
        background: transparent;
    }
"""

_BTN_SKIP = """
    QPushButton {
        background: transparent;
        color: #94a3b8;
        border: none;
        font-size: 12px;
    }
    QPushButton:hover {
        color: #ef4444;
    }
"""

_BTN_NEXT = """
    QPushButton {
        background: #3b82f6;
        color: #fff;
        border: none;
        border-radius: 6px;
        padding: 8px 20px;
        font-size: 13px;
        font-weight: 500;
    }
    QPushButton:hover {
        background: #2563eb;
    }
"""


# ═══════════════════════════════════════════════════════════════
#  OverlayWidget
# ═══════════════════════════════════════════════════════════════

class OverlayWidget(QWidget):
    """全窗口半透明遮罩 + 高亮挖空。

    信号:
        step_completed: 用户点击了高亮区域或「下一步」按钮。
        walkthrough_skipped: 用户点击「跳过」或按 Esc。
    """

    step_completed = Signal()
    walkthrough_skipped = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self._target: QWidget | None = None
        self._highlight_rect: QRectF = QRectF()
        self._shape: str = "rect"
        self._pulse_anim: QPropertyAnimation | None = None
        self._pulse_value: float = 0.0
        self._tooltip: QWidget | None = None
        self._next_btn: QPushButton | None = None
        self._skip_btn: QPushButton | None = None
        self._setup_tooltip()

    # ── 公开 API ──────────────────────────────────────────

    def highlight(
        self,
        target: QWidget,
        text: str,
        shape: str = "rect",
        placement: str = "bottom",
        step_index: int = 1,
        total_steps: int = 1,
    ) -> None:
        """设置高亮目标并显示遮罩。

        Args:
            target: 要高亮的控件。
            text: tooltip 说明文字。
            shape: 高亮形状 ("rect" | "circle")。
            placement: tooltip 位置 ("top" | "bottom" | "left" | "right")。
            step_index: 当前步骤序号 (从1开始)。
            total_steps: 总步骤数。
        """
        self._target = target
        self._shape = shape
        self._update_highlight_rect()
        self._place_tooltip(placement, text, step_index, total_steps)
        self._start_pulse()
        self.show()
        self.raise_()
        self.update()

    def clear(self) -> None:
        """清除高亮并隐藏遮罩。"""
        self._stop_pulse()
        self._target = None
        self._highlight_rect = QRectF()
        if self._tooltip:
            self._tooltip.hide()
        self.hide()

    # ── 高亮区域计算 ──────────────────────────────────────

    def _update_highlight_rect(self) -> None:
        """计算目标控件在 OverlayWidget 坐标系中的位置。"""
        if not self._target:
            return
        parent_widget = self.parent()
        if not parent_widget:
            return
        # 目标控件在父窗口中的全局坐标
        top_left = self._target.mapTo(parent_widget, self._target.rect().topLeft())
        size = self._target.size()
        # 加 padding
        pad = 8
        self._highlight_rect = QRectF(
            top_left.x() - pad,
            top_left.y() - pad,
            size.width() + pad * 2,
            size.height() + pad * 2,
        )

    # ── 绘制 ──────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # noqa: N803
        """自绘遮罩 + 挖空高亮。"""
        if not self._target:
            return
        self._update_highlight_rect()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # 判断主题
        is_dark = self._is_dark_theme()
        overlay_color = _OVERLAY_DARK if is_dark else _OVERLAY_LIGHT

        # 1. 画遮罩
        mask_path = QPainterPath()
        mask_path.addRect(0, 0, w, h)

        if self._shape == "circle":
            center = self._highlight_rect.center()
            rx = self._highlight_rect.width() / 2
            ry = self._highlight_rect.height() / 2
            hole = QPainterPath()
            hole.addEllipse(center, rx, ry)
            mask_path = mask_path.subtracted(hole)
        else:
            hole = QPainterPath()
            hole.addRoundedRect(self._highlight_rect, 8, 8)
            mask_path = mask_path.subtracted(hole)

        painter.fillPath(mask_path, QBrush(overlay_color))

        # 2. 画发光边框
        glow = QPen(_HIGHLIGHT_GLOW, 12 + self._pulse_value * 4)
        glow.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        border = QPen(_HIGHLIGHT_BORDER, 2.5)

        if self._shape == "circle":
            painter.setPen(glow)
            painter.drawEllipse(self._highlight_rect.center(),
                               self._highlight_rect.width() / 2,
                               self._highlight_rect.height() / 2)
            painter.setPen(border)
            painter.drawEllipse(self._highlight_rect.center(),
                               self._highlight_rect.width() / 2,
                               self._highlight_rect.height() / 2)
        else:
            painter.setPen(glow)
            painter.drawRoundedRect(self._highlight_rect, 8, 8)
            painter.setPen(border)
            painter.drawRoundedRect(self._highlight_rect, 8, 8)

        painter.end()

    # ── tooltip ───────────────────────────────────────────

    def _setup_tooltip(self) -> None:
        """创建 tooltip 浮层。"""
        self._tooltip = QWidget(self)
        self._tooltip.setObjectName("tooltip_container")
        self._tooltip.setStyleSheet(_TOOLTIP_STYLE)
        self._tooltip.setMaximumWidth(340)
        self._tooltip.setMinimumWidth(220)

        layout = QVBoxLayout(self._tooltip)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # 文字
        self._tooltip_label = QLabel()
        self._tooltip_label.setObjectName("tooltip_text")
        self._tooltip_label.setWordWrap(True)
        layout.addWidget(self._tooltip_label)

        # 底部行
        bottom = QHBoxLayout()
        bottom.setSpacing(8)

        # 步骤计数
        self._counter_label = QLabel()
        self._counter_label.setObjectName("tooltip_counter")
        bottom.addWidget(self._counter_label)
        bottom.addStretch()

        # 跳过
        self._skip_btn = QPushButton("跳过")
        self._skip_btn.setStyleSheet(_BTN_SKIP)
        self._skip_btn.clicked.connect(self._on_skip)
        bottom.addWidget(self._skip_btn)

        # 下一步
        self._next_btn = QPushButton("下一步")
        self._next_btn.setStyleSheet(_BTN_NEXT)
        self._next_btn.clicked.connect(self._on_next)
        bottom.addWidget(self._next_btn)

        layout.addLayout(bottom)
        self._tooltip.hide()

    def _place_tooltip(
        self, placement: str, text: str,
        step_index: int, total_steps: int,
    ) -> None:
        """定位 tooltip 到高亮区域旁边。"""
        if not self._tooltip:
            return

        self._tooltip_label.setText(text)
        self._counter_label.setText(f"{step_index} / {total_steps}")

        # 如果只剩最后一步
        if step_index >= total_steps:
            self._next_btn.setText("完成")

        self._tooltip.adjustSize()
        tt_w = self._tooltip.width()
        tt_h = self._tooltip.height()
        rect = self._highlight_rect
        margin = 16

        if placement == "bottom":
            x = rect.center().x() - tt_w / 2
            y = rect.bottom() + margin
        elif placement == "top":
            x = rect.center().x() - tt_w / 2
            y = rect.top() - tt_h - margin
        elif placement == "right":
            x = rect.right() + margin
            y = rect.center().y() - tt_h / 2
        else:  # left
            x = rect.left() - tt_w - margin
            y = rect.center().y() - tt_h / 2

        # 边界约束
        x = max(10, min(x, self.width() - tt_w - 10))
        y = max(10, min(y, self.height() - tt_h - 10))

        self._tooltip.move(int(x), int(y))
        self._tooltip.show()
        self._tooltip.raise_()

    # ── 动画 ──────────────────────────────────────────────

    def _start_pulse(self) -> None:
        """启动高亮边框脉冲动画。"""
        self._pulse_value = 0.0
        self._pulse_anim = QPropertyAnimation(self, b"_pulse_value")
        self._pulse_anim.setDuration(1200)
        self._pulse_anim.setStartValue(0.0)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse_anim.setLoopCount(-1)  # 无限循环
        self._pulse_anim.start()

    def _stop_pulse(self) -> None:
        """停止脉冲动画。"""
        if self._pulse_anim:
            self._pulse_anim.stop()
            self._pulse_anim = None

    def _get_pulse_value(self) -> float:
        return self._pulse_value

    def _set_pulse_value(self, value: float) -> None:
        self._pulse_value = value
        self.update()

    # Qt 属性绑定（用于动画）
    _pulse_value_prop = property(_get_pulse_value, _set_pulse_value)

    # ── 事件处理 ──────────────────────────────────────────

    def mousePressEvent(self, event) -> None:  # noqa: N803
        """点击遮罩空白区域 → 弹出确认跳过。"""
        if self._highlight_rect.contains(event.position()):
            # 点击高亮区域 → 完成当前步骤
            self.step_completed.emit()
        # 点击其他区域不响应

    def keyPressEvent(self, event) -> None:  # noqa: N803
        """Esc → 跳过引导。"""
        if event.key() == Qt.Key.Key_Escape:
            self._on_skip()

    def resizeEvent(self, event) -> None:  # noqa: N803
        """窗口大小变化时刷新。"""
        super().resizeEvent(event)
        if self._target:
            self._update_highlight_rect()
            self.update()

    def _on_next(self) -> None:
        """点击「下一步」。"""
        self.step_completed.emit()

    def _on_skip(self) -> None:
        """点击「跳过」。"""
        self.clear()
        self.walkthrough_skipped.emit()

    # ── 辅助 ──────────────────────────────────────────────

    @staticmethod
    def _is_dark_theme() -> bool:
        """检测当前是否为暗色主题。"""
        app = QApplication.instance()
        if not app:
            return False
        bg = app.palette().color(app.palette().ColorRole.Window)
        # 亮度低于 128 视为暗色
        return (bg.red() + bg.green() + bg.blue()) / 3 < 128


# ═══════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════

def self_test() -> tuple[int, int, list[str]]:
    """验证 OverlayWidget 基本功能（非 GUI 部分）。"""
    passed, failed = 0, 0
    errors: list[str] = []

    print("=== MF_Tutorial.overlay self_test ===")

    # 无法在无 QApplication 环境下创建 QWidget，
    # 此处只验证模块可正确导入
    try:
        from MF_Tutorial.overlay import OverlayWidget
        assert OverlayWidget is not None
        passed += 1
        print("  [PASS] OverlayWidget 类可导入")
    except Exception as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    print(f"  [PASS] {passed} passed, {failed} failed")
    print("=== MF_Tutorial.overlay self_test: DONE ===\n")
    return passed, failed, errors


if __name__ == "__main__":
    self_test()
