"""MathObject — 统一数学计算结果容器。

MathObject 是 MF_Mathematics 中所有函数的统一返回类型，
封装计算结果、步骤、几何意义、可视化数据等。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Union


@dataclass
class MathObject:
    """统一的数学计算结果对象。

    Attributes:
        result: 主要计算结果（数值、表达式、字符串等任意类型）。
        steps: 求解步骤列表，每步是一条简短描述。
        meaning: 几何意义或概念说明（可选）。
        error: 错误信息，正常计算结果时为空字符串。
        data: 附加的图数据或可视化信息（可选）。
        module: 所属模块名（由 register 装饰器自动设置）。
        action: 函数动作名（由 register 装饰器自动设置）。
    """

    result: Any = None
    steps: list[str] = field(default_factory=list)
    meaning: str = ""
    error: str = ""
    data: Optional[dict] = None
    module: str = ""
    action: str = ""

    @property
    def ok(self) -> bool:
        """是否正常（无错误）。"""
        return self.error == ""

    def __repr__(self) -> str:
        if self.error:
            return f"MathObject(error='{self.error}')"
        return f"MathObject(result={self.result!r}, module='{self.module}', action='{self.action}')"

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "result": str(self.result) if self.result is not None else None,
            "steps": self.steps,
            "meaning": self.meaning,
            "error": self.error,
            "module": self.module,
            "action": self.action,
        }


def self_test() -> tuple[int, int, int]:
    """自测试：验证 MathObject 的创建和 to_dict() 方法。"""
    try:
        obj = MathObject(
            result=3.14159,
            steps=["step1: approximate pi", "step2: rounding"],
            meaning="圆周率近似值",
            error="",
            data={"latex": r"\pi", "numeric": 3.14159},
            module="test",
            action="self_test",
        )

        d = obj.to_dict()
        assert "result" in d, "to_dict() 缺少 result 键"
        assert "steps" in d, "to_dict() 缺少 steps 键"
        assert "meaning" in d, "to_dict() 缺少 meaning 键"
        assert "error" in d, "to_dict() 缺少 error 键"
        assert "module" in d, "to_dict() 缺少 module 键"
        assert "action" in d, "to_dict() 缺少 action 键"
        assert d["result"] == "3.14159", f"result 值不匹配: {d['result']}"
        assert d["error"] == "", f"error 值不匹配: {d['error']}"
        assert d["module"] == "test", f"module 值不匹配: {d['module']}"
        assert d["action"] == "self_test", f"action 值不匹配: {d['action']}"

        print("math_object self_test: PASSED")
        return (1, 0, 0)
    except Exception as e:
        print(f"math_object self_test: FAILED - {e}")
        return (0, 0, 1)
