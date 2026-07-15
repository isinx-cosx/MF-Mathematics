# -*- coding: utf-8 -*-
"""GuidedWalkthrough — 交互式逐步引导向导。

使用 OverlayWidget 高亮 UI 元素，引导用户完成操作。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QApplication

from MF_Tutorial.engine import TutorialEngine
from MF_Tutorial.models import Tutorial, Step
from MF_Tutorial.overlay import OverlayWidget


# ═══════════════════════════════════════════════════════════════
#  GuidedWalkthrough
# ═══════════════════════════════════════════════════════════════

class GuidedWalkthrough:
    """交互式引导向导。

    管理 OverlayWidget 的生命周期，按步骤推进，
    监听用户操作（点击/选择/输入）完成每一步。

    用法:
        walkthrough = GuidedWalkthrough(main_window)
        walkthrough.start("quick-start")
    """

    def __init__(self, parent: QWidget) -> None:
        """初始化引导。

        Args:
            parent: 父窗口（通常是 MainWindow）。
        """
        self._parent = parent
        self._engine = TutorialEngine()
        self._overlay = OverlayWidget(parent)
        self._overlay.step_completed.connect(self._on_step_completed)
        self._overlay.walkthrough_skipped.connect(self._on_skipped)

        self._tutorial: Tutorial | None = None
        self._current_step: int = 0
        self._ui_elements: dict[str, QWidget] = {}
        self._on_finished_callback: callable | None = None

    # ── 公开 API ──────────────────────────────────────────

    def register_element(self, name: str, widget: QWidget) -> None:
        """注册 UI 元素，供教程步骤通过 target 名称引用。

        Args:
            name: 元素名称（如 "toolbar.calc_button"）。
            widget: 对应的 QWidget。
        """
        self._ui_elements[name] = widget

    def register_elements(self, mapping: dict[str, QWidget]) -> None:
        """批量注册 UI 元素。

        Args:
            mapping: {name: widget} 映射。
        """
        self._ui_elements.update(mapping)

    def set_on_finished(self, callback: callable) -> None:
        """设置引导完成后的回调。"""
        self._on_finished_callback = callback

    def start(self, tutorial_id: str = "quick-start") -> None:
        """开始引导。

        Args:
            tutorial_id: 教程 ID。
        """
        self._tutorial = self._engine.get(tutorial_id)
        if not self._tutorial:
            print(f"[Walkthrough] 教程 {tutorial_id} 未找到")
            return
        if not self._tutorial.steps:
            print(f"[Walkthrough] 教程 {tutorial_id} 无步骤")
            self._finish()
            return

        self._current_step = 0
        self._overlay.setGeometry(self._parent.rect())
        self._overlay.show()
        self._overlay.raise_()
        self._show_current_step()

    def stop(self) -> None:
        """停止引导。"""
        self._overlay.clear()
        self._current_step = 0

    # ── 内部 ──────────────────────────────────────────────

    def _show_current_step(self) -> None:
        """显示当前步骤。"""
        if not self._tutorial or self._current_step >= len(self._tutorial.steps):
            self._finish()
            return

        step = self._tutorial.steps[self._current_step]

        # 查找目标控件
        target = self._ui_elements.get(step.target)
        if not target:
            # 尝试通过 objectName 查找
            target = self._find_by_object_name(step.target)

        if not target:
            print(f"[Walkthrough] 目标控件未找到: {step.target}")
            # 跳过此步
            self._current_step += 1
            self._show_current_step()
            return

        # 如果目标是隐藏的，先处理 action
        self._execute_action(step)

        # 显示高亮
        self._overlay.setGeometry(self._parent.rect())
        self._overlay.highlight(
            target=target,
            text=step.text,
            shape=step.highlight,
            placement=step.placement,
            step_index=self._current_step + 1,
            total_steps=len(self._tutorial.steps),
        )

    def _execute_action(self, step: Step) -> None:
        """执行步骤中的预设动作（自动填值、选择等）。"""
        if not step.action or not step.action_value:
            return

        target = self._ui_elements.get(step.target)
        if not target:
            target = self._find_by_object_name(step.target)
        if not target:
            return

        # 根据动作类型执行
        if step.action == "type":
            # 尝试 setText / setPlainText / 模拟输入
            if hasattr(target, "setText"):
                target.setText(step.action_value)
            elif hasattr(target, "setPlainText"):
                target.setPlainText(step.action_value)

        elif step.action == "select":
            # 尝试 setCurrentText / setCurrentIndex
            if hasattr(target, "setCurrentText"):
                target.setCurrentText(step.action_value)
            elif hasattr(target, "setCurrentIndex"):
                for i in range(target.count()):
                    if target.itemText(i) == step.action_value:
                        target.setCurrentIndex(i)
                        break

        elif step.action == "click":
            # 自动点击
            if hasattr(target, "click"):
                target.click()
            elif hasattr(target, "animateClick"):
                target.animateClick()

        # "wait" 类型不需要自动操作

    def _find_by_object_name(self, name: str) -> QWidget | None:
        """通过 objectName 递归查找控件。"""
        parts = name.split(".")
        target_name = parts[-1]  # 取最后一段作为 objectName

        def _search(widget: QWidget) -> QWidget | None:
            if widget.objectName() == target_name:
                return widget
            for child in widget.findChildren(QWidget):
                result = _search(child)
                if result:
                    return result
            return None

        return _search(self._parent)

    def _advance(self) -> None:
        """前进到下一步。"""
        self._current_step += 1
        self._show_current_step()

    # ── 信号处理 ──────────────────────────────────────────

    def _on_step_completed(self) -> None:
        """当前步骤完成。"""
        self._advance()

    def _on_skipped(self) -> None:
        """用户跳过引导。"""
        self._overlay.clear()
        self._current_step = 0

    def _finish(self) -> None:
        """引导完成。"""
        self._overlay.clear()
        if self._tutorial:
            self._engine.mark_completed(self._tutorial.id)
        if self._on_finished_callback:
            self._on_finished_callback()
        self._current_step = 0


# ═══════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════

def self_test() -> tuple[int, int, list[str]]:
    """模块导入测试。"""
    passed, failed = 0, 0
    errors: list[str] = []

    print("=== MF_Tutorial.walkthrough self_test ===")
    try:
        from MF_Tutorial.walkthrough import GuidedWalkthrough
        assert GuidedWalkthrough is not None
        passed += 1
        print("  [PASS] GuidedWalkthrough 类可导入")
    except Exception as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    print(f"  [PASS] {passed} passed, {failed} failed")
    print("=== MF_Tutorial.walkthrough self_test: DONE ===\n")
    return passed, failed, errors


if __name__ == "__main__":
    self_test()
