# -*- coding: utf-8 -*-
"""NumericalEstimation — 无理数探索与逼近模块。

支持的常数: π, e, √2
支持的算法:
  - 拉马努金级数 (π) — 极速收敛，5 次迭代~15 位精度
  - 莱布尼茨级数 (π) — 慢速演示
  - 蒙特卡洛 (π) — 概率模拟
  - 泰勒级数 (e)
  - 牛顿法 (√2)
"""

from __future__ import annotations

import json
import math
import os
import random
import time
from typing import Callable

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLCDNumber,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


def _load_numerical_config() -> dict:
    try:
        from MF_Mathematics.utils.config_manager import config
        return config.numerical
    except Exception:
        pass
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    p = os.path.join(root, "config.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f).get("numerical", {})
    return {}

_CFG = _load_numerical_config()
_MAX_ITER = _CFG.get("max_iterations", 10_000_000)
_MAX_PREC = _CFG.get("max_precision", 15)
_RAM_TIMEOUT = _CFG.get("ramanujan_timeout", 1)


# ═══════════════════════════════════════════════════════════════════
#  Algorithm implementations
# ═══════════════════════════════════════════════════════════════════

def _ramanujan_pi(iterations: int) -> float:
    """拉马努金级数 for π. 每项 ~8 位精度."""
    s = 0.0
    factor = 2 * math.sqrt(2) / 9801
    for k in range(iterations):
        num = math.factorial(4 * k) * (1103 + 26390 * k)
        den = (math.factorial(k) ** 4) * (396 ** (4 * k))
        s += num / den
    return 1.0 / (factor * s)


def _leibniz_pi(iterations: int) -> float:
    """莱布尼茨级数. π/4 = 1 - 1/3 + 1/5 - ... (极慢)"""
    s = 0.0
    for k in range(iterations):
        s += (-1) ** k / (2 * k + 1)
    return 4 * s


def _monte_carlo_pi(samples: int) -> float:
    """蒙特卡洛模拟. 随机点落入圆内的比例 → π."""
    inside = 0
    for _ in range(samples):
        x = random.random()
        y = random.random()
        if x * x + y * y <= 1:
            inside += 1
    return 4 * inside / samples


def _taylor_e(iterations: int) -> float:
    """泰勒级数 for e = Σ 1/k!."""
    s = 1.0
    fact = 1.0
    for k in range(1, iterations):
        fact *= k
        s += 1.0 / fact
    return s


def _newton_sqrt2(iterations: int) -> float:
    """牛顿法 for √2. x_{n+1} = (x_n + 2/x_n) / 2."""
    x = 1.0
    for _ in range(iterations):
        x = (x + 2.0 / x) / 2.0
    return x


ALGORITHMS: dict[str, dict] = {
    "拉马努金 (π)": {"fn": _ramanujan_pi, "target": math.pi, "name": "π"},
    "莱布尼茨 (π)": {"fn": _leibniz_pi, "target": math.pi, "name": "π"},
    "蒙特卡洛 (π)": {"fn": _monte_carlo_pi, "target": math.pi, "name": "π"},
    "泰勒级数 (e)": {"fn": _taylor_e, "target": math.e, "name": "e"},
    "牛顿法 (√2)": {"fn": _newton_sqrt2, "target": math.sqrt(2), "name": "√2"},
}


# ═══════════════════════════════════════════════════════════════════
#  Worker thread
# ═══════════════════════════════════════════════════════════════════

class _EstimationWorker(QThread):
    """后台计算线程。"""

    progress = Signal(int, float, float)  # iteration, value, error
    finished = Signal(float, int)          # final_value, iterations
    error = Signal(str)

    def __init__(self, algo_key: str, max_iter: int, parent=None):
        super().__init__(parent)
        self._algo_key = algo_key
        self._max_iter = max_iter

    def run(self) -> None:
        try:
            algo = ALGORITHMS[self._algo_key]
            fn = algo["fn"]
            target = algo["target"]
            start = time.time()

            # 拉马努金特判：极速，每 1 次迭代报告一次
            if "拉马努金" in self._algo_key:
                for k in range(1, self._max_iter + 1):
                    if self.isInterruptionRequested():
                        return
                    val = fn(k)
                    err = abs(val - target)
                    self.progress.emit(k, val, err)
                    if time.time() - start > _RAM_TIMEOUT:
                        break
                if not self.isInterruptionRequested():
                    val = fn(self._max_iter)
                    self.finished.emit(val, self._max_iter)
                return

            # 通用：分批报告
            report_every = max(1, self._max_iter // 50)
            val = 0.0
            for k in range(1, self._max_iter + 1):
                if self.isInterruptionRequested():
                    return
                val = fn(k)
                if k % report_every == 0 or k == self._max_iter:
                    err = abs(val - target)
                    self.progress.emit(k, val, err)
            if not self.isInterruptionRequested():
                self.finished.emit(val, self._max_iter)

        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════════════════
#  NumericalEstimation Widget
# ═══════════════════════════════════════════════════════════════════

class NumericalEstimation(QWidget):
    """无理数逼近探索控件。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._worker: _EstimationWorker | None = None

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        # ── 标题 ──
        title = QLabel("<b>无理数逼近探索</b>")
        title.setStyleSheet("font-size:18px; color:#0f172a")
        root.addWidget(title)

        # ── 选择区 ──
        sel_row = QHBoxLayout()
        sel_row.addWidget(QLabel("常数:"))

        self._const_combo = QComboBox()
        self._const_combo.addItems(["π", "e", "√2"])
        self._const_combo.currentTextChanged.connect(self._on_const_changed)
        sel_row.addWidget(self._const_combo)

        sel_row.addWidget(QLabel("  算法:"))

        self._algo_combo = QComboBox()
        self._update_algo_list()
        sel_row.addWidget(self._algo_combo)

        sel_row.addWidget(QLabel("  迭代:"))

        self._iter_spin = QSpinBox()
        self._iter_spin.setRange(1, 100000)
        self._iter_spin.setValue(1000)
        sel_row.addWidget(self._iter_spin)

        sel_row.addStretch()
        root.addLayout(sel_row)

        # ── 显示区 ──
        self._lcd = QLCDNumber(15)
        self._lcd.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
        self._lcd.setStyleSheet(
            "QLCDNumber{background:#0f172a; color:#22d3ee;"
            " border-radius:8px; padding:12px; min-height:80px}"
        )
        root.addWidget(self._lcd)

        # 信息行
        info_row = QHBoxLayout()
        self._iter_label = QLabel("迭代: 0")
        self._error_label = QLabel("误差: —")
        self._iter_label.setStyleSheet("color:#475569; font-size:13px")
        self._error_label.setStyleSheet("color:#475569; font-size:13px")
        info_row.addWidget(self._iter_label)
        info_row.addWidget(self._error_label)
        info_row.addStretch()
        root.addLayout(info_row)

        # ── 进度条 ──
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # ── 按钮 ──
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("开始逼近")
        self._start_btn.setStyleSheet(
            "QPushButton{background:#3b82f6; color:#fff; border:none;"
            " border-radius:6px; padding:10px 24px; font-size:14px; font-weight:500}"
            "QPushButton:hover{background:#2563eb}"
        )
        self._start_btn.clicked.connect(self._start)
        btn_row.addWidget(self._start_btn)

        self._stop_btn = QPushButton("停止")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        root.addStretch()

    # ── Slots ──────────────────────────────────────────────

    def _on_const_changed(self, name: str) -> None:
        self._update_algo_list()
        # 预设: π→π, e→e, √2→√2
        self._lcd.display(0)

    def _update_algo_list(self) -> None:
        self._algo_combo.clear()
        const = self._const_combo.currentText()
        mapping = {
            "π": ["拉马努金 (π)", "莱布尼茨 (π)", "蒙特卡洛 (π)"],
            "e": ["泰勒级数 (e)"],
            "√2": ["牛顿法 (√2)"],
        }
        self._algo_combo.addItems(mapping.get(const, []))

    def _start(self) -> None:
        if self._worker and self._worker.isRunning():
            return  # 已有任务在运行
        algo_key = self._algo_combo.currentText()
        if not algo_key:
            return

        max_iter = min(self._iter_spin.value(), _MAX_ITER)

        # 拉马努金：限制迭代
        if "拉马努金" in algo_key:
            max_iter = min(max_iter, 10)

        self._worker = _EstimationWorker(algo_key, max_iter)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._progress.setMaximum(max_iter)
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

        self._worker.start()

    def _stop(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            if not self._worker.wait(3000):
                import logging
                logging.warning(
                    "NumericalEstimation worker 线程 3 秒内未响应 requestInterruption，"
                    "回退到 terminate()")
                self._worker.terminate()  # 最后手段
                self._worker.wait()
            self._worker.deleteLater()
            self._worker = None
        self._reset_ui()

    def _on_progress(self, iteration: int, value: float, error: float) -> None:
        self._lcd.display(value)
        self._iter_label.setText(f"迭代: {iteration}")
        self._error_label.setText(f"误差: {error:.2e}")
        self._progress.setValue(iteration)

    def _on_finished(self, value: float, iterations: int) -> None:
        self._lcd.display(value)
        target = ALGORITHMS[self._algo_combo.currentText()]["target"]
        err = abs(value - target)
        self._error_label.setText(f"最终误差: {err:.2e}")
        self._progress.setValue(self._progress.maximum())
        self._reset_ui()

    def _on_error(self, msg: str) -> None:
        self._error_label.setText(f"错误: {msg}")
        self._reset_ui()

    def _reset_ui(self) -> None:
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
