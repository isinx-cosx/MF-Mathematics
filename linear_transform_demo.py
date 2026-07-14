# -*- coding: utf-8 -*-
"""线性变换演示器 — 静态场景 + 视图变换 + 矩阵控制。

核心架构（可直接移植到 MF_UI/plot/）：
  1. 静态场景 — 网格/轴/刻度一次性创建，永不重建
  2. 视图变换 — 平移/缩放通过 QGraphicsView，不修改场景
  3. 矩阵应用 — 仅对演示形状组调用 setTransform()

性能目标：拖拽 60fps，无闪烁，无刻度丢失。
"""

from __future__ import annotations

import math
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QTransform,
)
from PySide6.QtWidgets import (
    QApplication, QDoubleSpinBox, QGraphicsItemGroup, QGraphicsLineItem,
    QGraphicsPathItem, QGraphicsPolygonItem, QGraphicsScene, QGraphicsTextItem,
    QGraphicsView, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QSlider, QStatusBar, QVBoxLayout, QWidget,
)


# ═══════════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════════

SCENE_RANGE = 1_000                 # 场景 ±1000
GRID_MAJOR  = 100                   # 主网格间距
GRID_MINOR  = 20                    # 次网格间距
ZOOM_MIN    = 0.02
ZOOM_MAX    = 500


# ═══════════════════════════════════════════════════════════════════════
#  StaticGridBuilder — 一次性创建所有静态场景元素
# ═══════════════════════════════════════════════════════════════════════

class StaticGridBuilder:
    """在 QGraphicsScene 中创建网格、轴、刻度标签（调用一次，永不重建）。"""

    @staticmethod
    def build(scene: QGraphicsScene) -> None:
        R = SCENE_RANGE

        # ── 画笔 ──
        pen_major = QPen(QColor("#d0d5dc"), 0)          # 主网格：浅灰
        pen_minor = QPen(QColor("#e8ecf0"), 0)          # 次网格：更浅
        pen_axis  = QPen(QColor("#1e293b"), 0)          # 坐标轴：深色
        font      = QFont("Segoe UI", 8)

        # ── 次网格线（间距 20）──
        for i in range(-R, R + 1, GRID_MINOR):
            if i % GRID_MAJOR == 0:
                continue  # 主网格位置跳过，由主网格线覆盖
            scene.addLine(i, -R, i, R, pen_minor)
            scene.addLine(-R, i, R, i, pen_minor)

        # ── 主网格线（间距 100）──
        for i in range(-R, R + 1, GRID_MAJOR):
            scene.addLine(i, -R, i, R, pen_major)
            scene.addLine(-R, i, R, i, pen_major)

        # ── 坐标轴（粗线）──
        pen_axis_line = QPen(QColor("#0f172a"), 0)
        pen_axis_line.setWidth(2)  # cosmetic 2px 会被忽略，用 0 得 1px
        scene.addLine(-R, 0, R, 0, QPen(QColor("#334155"), 0))
        scene.addLine(0, -R, 0, R, QPen(QColor("#334155"), 0))

        # ── 刻度标签（间距 100，跳过原点避免覆盖）──
        for i in range(-R, R + 1, GRID_MAJOR):
            if i == 0:
                continue
            # X 轴标签
            tx = QGraphicsTextItem(str(i))
            tx.setFont(font)
            tx.setDefaultTextColor(QColor("#64748b"))
            tx.setPos(i - 12, 4)
            tx.setTransform(QTransform.fromScale(1, -1))  # Y-up 矫正
            scene.addItem(tx)

            # Y 轴标签
            ty = QGraphicsTextItem(str(i))
            ty.setFont(font)
            ty.setDefaultTextColor(QColor("#64748b"))
            ty.setPos(-28, i - 6)
            ty.setTransform(QTransform.fromScale(1, -1))
            scene.addItem(ty)

        # 原点 O 标签
        to = QGraphicsTextItem("O")
        to.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        to.setDefaultTextColor(QColor("#0f172a"))
        to.setPos(4, 4)
        to.setTransform(QTransform.fromScale(1, -1))
        scene.addItem(to)


# ═══════════════════════════════════════════════════════════════════════
#  TransformCanvas
# ═══════════════════════════════════════════════════════════════════════

class TransformCanvas(QGraphicsView):
    """静态场景 + 视图变换画布。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        # ── Scene ──
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(QRectF(-SCENE_RANGE, -SCENE_RANGE,
                                         SCENE_RANGE * 2, SCENE_RANGE * 2))
        self.setScene(self._scene)

        # ── View ──
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QBrush(QColor("#fafbfc")))
        self.scale(1, -1)  # Y-up

        # ── Static grid (built once) ──
        StaticGridBuilder.build(self._scene)

        # ── Demo shape group (transformed by matrix) ──
        self._demo_group = self._create_demo_shape()
        self._scene.addItem(self._demo_group)

        # ── Initial view ──
        self.fitInView(QRectF(-6, -6, 12, 12), Qt.AspectRatioMode.KeepAspectRatio)

    # ── Demo shape ─────────────────────────────────────────────

    def _create_demo_shape(self) -> QGraphicsItemGroup:
        """创建演示形状组：参考正方形 + 变换正方形 + 基向量。"""
        group = QGraphicsItemGroup()

        # ── 参考正方形（虚线，始终为单位正方形）──
        ref_pen = QPen(QColor("#94a3b8"), 0)
        ref_pen.setStyle(Qt.PenStyle.DashLine)
        ref_pen.setWidth(2)
        ref_path = QPainterPath()
        ref_path.addRect(QRectF(0, 0, 1, 1))
        ref = QGraphicsPathItem(ref_path)
        ref.setPen(ref_pen)
        ref.setBrush(QBrush(QColor(148, 163, 184, 30)))
        ref.setZValue(-1)
        group.addToGroup(ref)

        # ── 变换正方形（实心，蓝色半透明）──
        self._square_path = QPainterPath()
        self._square_path.addRect(QRectF(0, 0, 1, 1))
        self._square = QGraphicsPathItem(self._square_path)
        self._square.setPen(QPen(QColor("#3b82f6"), 0))
        self._square.setBrush(QBrush(QColor(59, 130, 246, 60)))
        self._square.setZValue(0)
        group.addToGroup(self._square)

        # ── e₁ 基向量（红色）──
        self._e1_line = QGraphicsLineItem(0, 0, 1, 0)
        self._e1_line.setPen(QPen(QColor("#ef4444"), 0))
        self._e1_line.setZValue(1)
        group.addToGroup(self._e1_line)

        # e₁ 箭头
        self._e1_head = QGraphicsPolygonItem()
        self._e1_head.setPolygon([
            QPointF(1, 0), QPointF(0.85, -0.05), QPointF(0.85, 0.05),
        ])
        self._e1_head.setBrush(QBrush(QColor("#ef4444")))
        self._e1_head.setPen(QPen(QColor("#ef4444"), 0))
        self._e1_head.setZValue(1)
        group.addToGroup(self._e1_head)

        # ── e₂ 基向量（绿色）──
        self._e2_line = QGraphicsLineItem(0, 0, 0, 1)
        self._e2_line.setPen(QPen(QColor("#10b981"), 0))
        self._e2_line.setZValue(1)
        group.addToGroup(self._e2_line)

        # e₂ 箭头
        self._e2_head = QGraphicsPolygonItem()
        self._e2_head.setPolygon([
            QPointF(0, 1), QPointF(-0.05, 0.85), QPointF(0.05, 0.85),
        ])
        self._e2_head.setBrush(QBrush(QColor("#10b981")))
        self._e2_head.setPen(QPen(QColor("#10b981"), 0))
        self._e2_head.setZValue(1)
        group.addToGroup(self._e2_head)

        return group

    # ── Public API ──────────────────────────────────────────────

    def set_matrix(self, a: float, b: float, c: float, d: float) -> None:
        """更新演示形状组的线性变换矩阵 [[a,b],[c,d]]。

        映射: (x, y) → (a*x + b*y, c*x + d*y)
        QTransform(m11, m12, m21, m22, dx, dy):
          x' = m11*x + m21*y + dx
          y' = m12*x + m22*y + dy
        """
        t = QTransform(a, c, b, d, 0, 0)
        self._demo_group.setTransform(t)

    def reset_view(self) -> None:
        """重置视图到初始状态。"""
        self.fitInView(QRectF(-6, -6, 12, 12), Qt.AspectRatioMode.KeepAspectRatio)

    # ── Zoom ────────────────────────────────────────────────────

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        current = self.transform().m11()
        if current * factor < 1.0 / ZOOM_MAX or current * factor > 1.0 / ZOOM_MIN:
            return
        self.scale(factor, factor)
        event.accept()


# ═══════════════════════════════════════════════════════════════════════
#  MatrixControl — 滑块 + 数值输入
# ═══════════════════════════════════════════════════════════════════════

class MatrixControl(QWidget):
    """4 参数矩阵控制面板。"""

    matrix_changed = Signal(float, float, float, float)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedWidth(280)

        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        # ── 标题 ──
        title = QLabel("<b>变换矩阵</b>  [[a, b], [c, d]]")
        title.setStyleSheet("font-size:14px; color:#0f172a")
        root.addWidget(title)

        # ── 矩阵显示 ──
        mat_group = QGroupBox()
        mat_layout = QVBoxLayout(mat_group)
        mat_layout.setSpacing(4)
        self._mat_label = QLabel("[[1.00, 0.00]\n [0.00, 1.00]]")
        self._mat_label.setStyleSheet(
            "font-family:Consolas,monospace; font-size:18px; color:#1e293b;"
            "padding:8px; background:#f1f5f9; border-radius:6px;"
        )
        mat_layout.addWidget(self._mat_label)
        root.addWidget(mat_group)

        # ── 4 个参数滑块 + 数值输入 ──
        self._sliders: dict[str, tuple[QSlider, QDoubleSpinBox]] = {}
        for name, row_idx in [("a", 0), ("b", 1), ("c", 2), ("d", 3)]:
            self._sliders[name] = self._make_row(name, root)

        # ── 行列式 ──
        self._det_label = QLabel("det = 1.00")
        self._det_label.setStyleSheet(
            "font-family:Consolas,monospace; font-size:13px; color:#475569;"
        )
        root.addWidget(self._det_label)

        # ── 预设按钮 ──
        presets = QHBoxLayout()
        presets.setSpacing(4)
        for label, a, b, c, d in [
            ("单位", 1, 0, 0, 1),
            ("X2", 2, 0, 0, 1),
            ("旋转90°", 0, -1, 1, 0),
            ("错切X", 1, 0.8, 0, 1),
            ("投影X", 1, 0, 0, 0),
            ("反射Y", -1, 0, 0, 1),
        ]:
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setStyleSheet(
                "QPushButton{background:#f1f5f9; border:1px solid #cbd5e1;"
                "border-radius:4px; font-size:12px; padding:2px 6px; color:#334155}"
                "QPushButton:hover{background:#e2e8f0}"
            )
            btn.clicked.connect(lambda _, a=a, b=b, c=c, d=d: self._set_all(a, b, c, d))
            presets.addWidget(btn)
        root.addLayout(presets)

        root.addStretch()

        # ── 按钮 ──
        btn_row = QHBoxLayout()
        reset_m = QPushButton("重置矩阵")
        reset_m.setStyleSheet(
            "QPushButton{background:#3b82f6; color:#fff; border:none;"
            "border-radius:6px; padding:8px 16px; font-weight:500}"
            "QPushButton:hover{background:#2563eb}"
        )
        reset_m.clicked.connect(lambda: self._set_all(1, 0, 0, 1))
        btn_row.addWidget(reset_m)
        root.addLayout(btn_row)

    def _make_row(self, name: str, parent: QVBoxLayout):
        row = QHBoxLayout()
        row.setSpacing(6)
        lbl = QLabel(f"{name} =")
        lbl.setFixedWidth(24)
        lbl.setStyleSheet("font-family:Consolas,monospace; font-size:14px; color:#0f172a")
        row.addWidget(lbl)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(-300, 300)
        slider.setValue(100 if name in ("a", "d") else 0)
        slider.setTickPosition(QSlider.TickPosition.NoTicks)
        row.addWidget(slider, 1)

        spin = QDoubleSpinBox()
        spin.setRange(-5.0, 5.0)
        spin.setSingleStep(0.05)
        spin.setDecimals(2)
        spin.setFixedWidth(64)
        spin.setValue(1.0 if name in ("a", "d") else 0.0)
        spin.setStyleSheet(
            "QDoubleSpinBox{border:1px solid #d1d5db; border-radius:4px;"
            "padding:2px 4px; font-size:13px}"
        )
        row.addWidget(spin)

        # 双向同步
        slider.valueChanged.connect(lambda v, s=spin: self._slider_to_spin(v, s))
        spin.valueChanged.connect(lambda v, s=slider: self._spin_to_slider(v, s))
        # 任一变化 → 发射矩阵
        slider.valueChanged.connect(lambda: self._emit())
        spin.valueChanged.connect(lambda: self._emit())

        parent.addLayout(row)
        return (slider, spin)

    def _slider_to_spin(self, v: int, spin: QDoubleSpinBox) -> None:
        spin.blockSignals(True)
        spin.setValue(v / 100.0)
        spin.blockSignals(False)

    def _spin_to_slider(self, v: float, slider: QSlider) -> None:
        slider.blockSignals(True)
        slider.setValue(int(round(v * 100)))
        slider.blockSignals(False)

    def _emit(self) -> None:
        a = self._sliders["a"][1].value()
        b = self._sliders["b"][1].value()
        c = self._sliders["c"][1].value()
        d = self._sliders["d"][1].value()
        self._mat_label.setText(f"[[{a:.2f}, {b:.2f}]\n [{c:.2f}, {d:.2f}]]")
        det = a * d - b * c
        self._det_label.setText(f"det = {det:.2f}")
        self.matrix_changed.emit(a, b, c, d)

    def _set_all(self, a: float, b: float, c: float, d: float) -> None:
        """程序化设置所有参数（用于预设和重置）。"""
        for name, val in [("a", a), ("b", b), ("c", c), ("d", d)]:
            slider, spin = self._sliders[name]
            slider.setValue(int(round(val * 100)))
            spin.setValue(val)


# ═══════════════════════════════════════════════════════════════════════
#  MainWindow
# ═══════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("线性变换演示器 — Linear Transform Demo")
        self.resize(1100, 720)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── 左侧：矩阵控件 ──
        left = QWidget()
        left.setStyleSheet("background:#ffffff; border-right:1px solid #e2e8f0")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self._matrix_ctrl = MatrixControl()
        left_layout.addWidget(self._matrix_ctrl)

        reset_view_btn = QPushButton("重置视图")
        reset_view_btn.setStyleSheet(
            "QPushButton{background:#f1f5f9; border:1px solid #cbd5e1;"
            "border-radius:6px; padding:8px 16px; font-weight:500; color:#334155}"
            "QPushButton:hover{background:#e2e8f0}"
        )
        reset_view_btn.clicked.connect(self._on_reset_view)
        left_layout.addWidget(reset_view_btn)
        left_layout.addSpacing(8)
        root.addWidget(left)

        # ── 右侧：画布 ──
        self._canvas = TransformCanvas()
        root.addWidget(self._canvas, 1)

        # ── 信号 ──
        self._matrix_ctrl.matrix_changed.connect(self._canvas.set_matrix)

        # ── 状态栏 ──
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("就绪 | 左键拖拽平移 | 滚轮缩放 | 调整滑块观察线性变换")

    def _on_reset_view(self) -> None:
        self._canvas.reset_view()
        self._status.showMessage("视图已重置", 2000)


# ═══════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    app.setApplicationName("LinearTransformDemo")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
