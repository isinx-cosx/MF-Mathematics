# -*- coding: utf-8 -*-
"""ComputeWorker — 通用后台计算 QThread。

所有数学计算（积分/求导/求解/矩阵/概率）通过此 Worker 在后台线程执行，
确保 UI 永不冻结。

特性:
  - 通用 target(*args, **kwargs) 模式
  - requestInterruption() 安全取消
  - QTimer 超时支持
  - 标准生命周期管理 (wait + deleteLater)

用法:
    worker = ComputeWorker(self, target=dispatch, args=("calculus", "integrate", "sin(x)", "x"))
    worker.result_ready.connect(self._on_result)
    worker.error_occurred.connect(self._on_error)
    worker.start()
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal, QTimer


class ComputeWorker(QThread):
    """通用后台计算线程 — 执行任意可调用对象并通过信号返回结果。"""

    result_ready = Signal(object)     # 成功时发射 MathObject
    error_occurred = Signal(str)      # 异常时发射错误消息
    started = Signal()                # 计算开始时发射

    def __init__(
        self,
        parent,
        target: callable,
        args: tuple = (),
        kwargs: dict | None = None,
        timeout_ms: int = 0,
    ):
        """初始化计算工作器。

        Args:
            parent: Qt 父对象（用于生命周期管理）。
            target: 要在后台线程执行的可调用对象。
            args: 位置参数。
            kwargs: 关键字参数。
            timeout_ms: 超时毫秒数。0 = 无超时。
        """
        super().__init__(parent)
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}
        self._timeout_ms = timeout_ms
        self._timer: QTimer | None = None

    def run(self) -> None:
        """在后台线程执行目标函数。"""
        self.started.emit()
        try:
            result = self._target(*self._args, **self._kwargs)
            if not self.isInterruptionRequested():
                self.result_ready.emit(result)
        except Exception as e:
            if not self.isInterruptionRequested():
                self.error_occurred.emit(str(e))

    def start_with_timeout(self) -> None:
        """启动计算并设置超时。超时后自动 requestInterruption。"""
        if self._timeout_ms > 0:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._on_timeout)
            self._timer.start(self._timeout_ms)
        self.start()

    def _on_timeout(self) -> None:
        """超时回调 — 请求中断。"""
        self.requestInterruption()

    def cancel(self) -> None:
        """安全取消计算。"""
        self.requestInterruption()
        if self._timer and self._timer.isActive():
            self._timer.stop()
        if self.isRunning():
            self.wait(5000)

    def cleanup(self) -> None:
        """标准清理 — 确保线程安全退出。"""
        if self._timer and self._timer.isActive():
            self._timer.stop()
        if self.isRunning():
            self.requestInterruption()
            self.wait(5000)
        self.deleteLater()
