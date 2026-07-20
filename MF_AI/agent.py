# -*- coding: utf-8 -*-
"""Agent 推理链 — AI 自主调用数学工具完成多步推理。"""

from __future__ import annotations
import json, logging, re
from typing import Any

logger = logging.getLogger(__name__)

TOOLS = [
    {"name": "calculate", "description": "Execute math: diff/integrate/solve/limit/simplify/eigenvalues etc",
     "parameters": {"module": {"type": "string"}, "action": {"type": "string"},
                    "args": {"type": "array"}, "kwargs": {"type": "object"}}},
    {"name": "eval_expression", "description": "Evaluate numeric expression",
     "parameters": {"expr": {"type": "string"}}},
]

SYSTEM_PROMPT = (
    "You are a math agent. Use calculate(module,action,args,kwargs) for exact symbolic math. "
    "Use eval_expression(expr) for numeric evaluation. "
    "Call one tool at a time. Max 10 tool calls. "
    "Put final answer in \\boxed{answer}."
)


class MathAgent:
    """Math Agent with Function Calling loop."""

    def __init__(self):
        self._history = []
        self._iterations = 0
        self._max_iterations = 10

    def solve(self, question: str) -> str:
        from MF_AI import chat
        self._history = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        self._iterations = 0
        while self._iterations < self._max_iterations:
            self._iterations += 1
            try:
                response = chat(self._history)
                if not response:
                    return "AI service unavailable"
            except Exception as e:
                return f"AI error: {e}"
            self._history.append({"role": "assistant", "content": response})
            tool_call = self._parse_tool_call(response)
            if not tool_call:
                return response
            tool_result = self._execute_tool(tool_call)
            self._history.append({
                "role": "user",
                "content": f"[Tool result] {tool_call['name']}: {tool_result}",
            })
        return "Max iterations reached."

    def _parse_tool_call(self, response: str):
        m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                logger.debug("JSON 解析失败 (code block), 尝试备用模式")
        m = re.search(r'\{[^{}]*"name"\s*:\s*"[^"]+"[^{}]*\}', response)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                logger.debug("JSON 解析失败 (inline pattern)")
        return None

    def _execute_tool(self, call: dict) -> str:
        name = call.get("name", "")
        try:
            if name == "calculate":
                return self._tool_calculate(call)
            elif name == "eval_expression":
                return self._tool_eval(call)
            return f"Unknown tool: {name}"
        except Exception as e:
            return f"Tool error: {e}"

    def _tool_calculate(self, call: dict) -> str:
        from MF_Mathematics.core.registry import dispatch
        module = call.get("module", "calculus")
        action = call.get("action", "")
        args = tuple(call.get("args", []))
        kwargs = call.get("kwargs", {})
        try:
            __import__(f"MF_Mathematics.{module}", fromlist=[module])
        except ImportError:
            logger.debug("数学模块导入失败: %s", module)
        result = dispatch(module, action, *args, **kwargs)
        if hasattr(result, "ok") and hasattr(result, "result"):
            return str(result.result) if result.ok else f"Error: {result.error}"
        return str(result)

    def _tool_eval(self, call: dict) -> str:
        import numpy as np
        safe = {"np": np, "pi": np.pi, "e": np.e, "sqrt": np.sqrt,
                "sin": np.sin, "cos": np.cos, "tan": np.tan,
                "exp": np.exp, "log": np.log, "abs": abs}
        try:
            return str(eval(call.get("expr", ""), {"__builtins__": {}}, safe))
        except Exception as e:
            return f"Eval error: {e}"


def self_test() -> bool:
    print("=== MF_AI.agent self_test ===")
    agent = MathAgent()
    r = '```json\n{"name":"eval_expression","expr":"2+3"}\n```'
    call = agent._parse_tool_call(r)
    assert call == {"name": "eval_expression", "expr": "2+3"}, f"Parse fail: {call}"
    assert "14" in agent._tool_eval({"expr": "2+3*4"})
    assert "2*x" in agent._tool_calculate(
        {"module": "calculus", "action": "diff", "args": ["x**2", "x"], "kwargs": {}})
    print("  ALL PASSED")
    return True


if __name__ == "__main__":
    self_test()
