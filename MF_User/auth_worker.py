# -*- coding: utf-8 -*-
"""AuthWorker — 后台线程执行 API 调用，不阻塞 PySide6 GUI。

用法:
    from MF_User.auth_worker import AuthWorker
    from MF_User.api_client import APIClient

    worker = AuthWorker(parent, lambda: APIClient().login("alice", "pass"))
    worker.succeeded.connect(on_success)
    worker.failed.connect(on_error)
    worker.start()
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QThread, Signal


class AuthWorker(QThread):
    """后台执行 API 调用的工作线程。

    Signals:
        started: 线程已启动。
        succeeded: API 调用成功，携带响应 dict。
        failed: API 调用失败，携带错误消息字符串。
    """

    started = Signal()
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, parent, target: Callable[[], dict]) -> None:
        """初始化工作线程。

        Args:
            parent: 父 QObject（用于生命周期管理）。
            target: 零参可调用对象，返回 API 响应 dict。
                    例如 lambda: APIClient().login("alice", "pass")
        """
        super().__init__(parent)
        self._target = target

    def run(self) -> None:
        """在后台线程中执行 API 调用。"""
        self.started.emit()
        try:
            result = self._target()
            self.succeeded.emit(result)
        except RuntimeError as e:
            self.failed.emit(str(e))
        except Exception as e:
            self.failed.emit(f"未知错误: {e}")

    def cancel(self) -> None:
        """请求中断并等待线程结束（最多 3 秒）。"""
        self.requestInterruption()
        self.wait(3000)


# ═══════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════

def self_test() -> tuple[int, int, list[str]]:
    """验证 AuthWorker 可导入（不实际启动线程，避免 QApplication 依赖）。"""
    passed, failed = 0, 0
    errors: list[str] = []

    print("=== MF_User.auth_worker self_test ===")

    try:
        from MF_User.auth_worker import AuthWorker
        assert AuthWorker is not None
        # 验证信号存在
        assert hasattr(AuthWorker, "started")
        assert hasattr(AuthWorker, "succeeded")
        assert hasattr(AuthWorker, "failed")
        passed += 1
        print("  [PASS] AuthWorker 可导入，信号存在")
    except Exception as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    try:
        from PySide6.QtCore import QCoreApplication
        app = QCoreApplication.instance()
        if app is None:
            app = QCoreApplication([])

        # 基本构造测试
        worker = AuthWorker(None, lambda: {"test": True})
        assert worker is not None
        assert callable(worker._target)
        passed += 1
        print("  [PASS] AuthWorker 可实例化")
    except Exception as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    print(f"  [{passed} passed, {failed} failed]")
    if errors:
        for e in errors:
            print(f"  [ERROR] {e}")
    print("=== MF_User.auth_worker self_test: DONE ===\n")
    return passed, failed, errors


if __name__ == "__main__":
    self_test()
