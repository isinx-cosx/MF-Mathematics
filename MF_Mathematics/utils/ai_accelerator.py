# -*- coding: utf-8 -*-
"""AI 加速器 — 基于 MF_AI 模块，提供步骤生成 + 复杂计算加速 + 配额管理。

特性:
  - 使用 MF_AI 统一客户端（支持 openai / httpx 后端）
  - 模型映射从 config.yaml 读取（角色→实际模型）
  - QuotaManager: 本地 usage.json 每日配额追踪
  - generate_steps: 生成数学推导步骤
  - accelerate: AI 辅助复杂计算

用法:
    from MF_Mathematics.utils.ai_accelerator import AIAccelerator

    ai = AIAccelerator()
    if ai.check_quota("steps"):
        mo = ai.generate_steps("求 x^2 的导数", "diff(x**2, x)")
"""

from __future__ import annotations

import json
import os
from datetime import date

from MF_Mathematics.core.math_object import MathObject
from MF_AI.config import Config as AIConfig
from MF_AI.exceptions import AIError, AIConfigError


# ═══════════════════════════════════════════════════════════════
#  QuotaManager — 每日配额追踪
# ═══════════════════════════════════════════════════════════════

def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _usage_path() -> str:
    return os.path.join(_project_root(), "usage.json")


class QuotaManager:
    """本地 usage.json 配额管理。

    usage.json 结构:
        {"2026-07-15": {"steps": 2, "accelerations": 1}, ...}
    """

    def __init__(self) -> None:
        self._path = _usage_path()
        self._data: dict[str, dict[str, int]] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = {}

    def _save(self) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except OSError:
            pass

    @property
    def today(self) -> str:
        return date.today().isoformat()

    def _today_data(self) -> dict[str, int]:
        if self.today not in self._data:
            self._data[self.today] = {"steps": 0, "accelerations": 0}
        return self._data[self.today]

    def used(self, key: str) -> int:
        return self._today_data().get(key, 0)

    def remaining(self, key: str) -> int:
        # 默认限额（可通过 config.yaml 或 config.json 覆盖）
        if key == "steps":
            limit = 5
        elif key == "accelerations":
            limit = 3
        else:
            limit = 5
        return max(0, limit - self.used(key))

    def consume(self, key: str) -> bool:
        if self.remaining(key) <= 0:
            return False
        td = self._today_data()
        td[key] = td.get(key, 0) + 1
        self._save()
        return True

    def refund(self, key: str) -> None:
        """退还一次配额（API 调用失败时）。"""
        td = self._today_data()
        if td.get(key, 0) > 0:
            td[key] -= 1
            self._save()


# ═══════════════════════════════════════════════════════════════
#  AIAccelerator — 主入口
# ═══════════════════════════════════════════════════════════════

class AIAccelerator:
    """AI 加速服务 — 基于 MF_AI 模块。

    自动读取 MF_AI/config.yaml 中的模型映射和参数。
    """

    def __init__(self, ai_config: AIConfig | None = None) -> None:
        self._quota = QuotaManager()
        self._ai_cfg = ai_config or AIConfig()

    # ── 配额检查 ──────────────────────────────────────────

    @property
    def _has_api_key(self) -> bool:
        """是否配置了 API Key — 有 Key 则无限制。"""
        return bool(self._ai_cfg.api_key)

    def check_quota(self, kind: str = "steps") -> bool:
        if self._has_api_key:
            return True
        return self._quota.remaining(kind) > 0

    def quota_remaining(self, kind: str = "steps") -> int:
        if self._has_api_key:
            return 999999  # 无限制
        return self._quota.remaining(kind)

    @property
    def quota(self) -> QuotaManager:
        return self._quota

    # ── 内部调用 ──────────────────────────────────────────

    def _call_ai(self, prompt: str, system: str = "",
                 role: str = "Sonnet") -> str | None:
        """通过 MF_AI 调用 AI。

        Args:
            prompt: 用户提示词。
            system: 系统提示词。
            role: 角色名（如 "Sonnet", "Reasoner"），映射到 config.yaml model_map。

        Returns:
            AI 回复文本，失败返回 None。
        """
        try:
            from MF_AI import chat as ai_chat
            from MF_AI.config import Config

            # 如果未设置 API Key，尝试用 ai_config 的
            cfg = Config()
            if not cfg.api_key and self._ai_cfg.api_key:
                cfg.set_api_key(self._ai_cfg.api_key)

            cfg.validate()

            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            return ai_chat(messages, model=role)
        except AIConfigError:
            return None
        except (AIError, Exception):
            return None

    # ── 公共 API ──────────────────────────────────────────

    def generate_steps(self, question: str, expr: str = "",
                       role: str = "Sonnet") -> MathObject:
        """生成数学推导步骤。

        Args:
            question: 用户的问题描述。
            expr: 相关的数学表达式。
            role: 角色名（Sonnet → config.yaml 中映射的实际模型）。

        Returns:
            MathObject — 含 result（AI 回复）和 steps（解析的步骤）。
        """
        if not self._quota.consume("steps"):
            return MathObject(
                error="今日步骤生成次数已用完（5 次/天），请明日再试。"
            )

        system = (
            "你是一位数学助教。请用中文回答。"
            "对于数学问题，请给出清晰的分步推导过程。"
            "每步以【步骤 N】开头，最后给出最终答案。"
        )
        prompt = f"问题：{question}"
        if expr:
            prompt += f"\n表达式：{expr}"

        result_text = self._call_ai(prompt, system, role=role)
        if result_text is None:
            self._quota.refund("steps")
            return MathObject(
                error="AI 调用失败。请检查 API Key 配置或网络连接。"
            )

        steps = [s.strip() for s in result_text.split("\n") if s.strip()]
        return MathObject(
            result=result_text,
            steps=steps[:20],
            meaning=f"由 AI 生成的推导步骤",
        )

    def accelerate(self, expr: str, mode: str = "",
                   role: str = "Sonnet") -> MathObject:
        """AI 加速复杂计算。

        Args:
            expr: 待计算的表达式。
            mode: 操作模式（如"不定积分"）。
            role: 角色名。

        Returns:
            MathObject — 含 AI 计算结果。
        """
        if not self._quota.consume("accelerations"):
            return MathObject(
                error="今日 AI 加速次数已用完（3 次/天），请明日再试。"
            )

        system = (
            "你是一位数学计算引擎。请直接对表达式进行计算，返回计算结果。"
            "若表达式过于复杂，请给出近似的数值结果（保留 6 位有效数字）。"
            "仅返回结果，不要解释。"
        )
        prompt = f"模式：{mode}\n表达式：{expr}" if mode else f"计算：{expr}"

        result_text = self._call_ai(prompt, system, role=role)
        if result_text is None:
            self._quota.refund("accelerations")
            return MathObject(
                error="AI 加速调用失败。请检查 API Key 配置或网络连接。"
            )

        return MathObject(
            result=result_text.strip(),
            steps=[
                f"表达式: {expr}",
                f"模式: {mode}",
                f"AI 计算结果: {result_text.strip()}",
            ],
            meaning="由 AI 加速计算的结果",
        )

    def chat(self, question: str, system: str = "",
             role: str = "Sonnet") -> MathObject:
        """自由对话（不消耗配额，用于 AI 对话框等场景）。

        Args:
            question: 用户问题。
            system: 系统提示词（可选）。
            role: 角色名。

        Returns:
            MathObject — 含 AI 回复。
        """
        result_text = self._call_ai(question, system, role=role)
        if result_text is None:
            return MathObject(
                error="AI 调用失败。请检查 API Key 配置或网络连接。"
            )
        return MathObject(
            result=result_text,
            meaning="AI 对话回复",
        )


# ═══════════════════════════════════════════════════════════════
#  便捷函数
# ═══════════════════════════════════════════════════════════════

_ai_instance: AIAccelerator | None = None


def get_accelerator() -> AIAccelerator:
    """获取全局 AIAccelerator 实例。"""
    global _ai_instance
    if _ai_instance is None:
        _ai_instance = AIAccelerator()
    return _ai_instance


# ═══════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════

def self_test() -> None:
    """验证 QuotaManager 基本功能。"""
    print("=== ai_accelerator self_test ===")

    qm = QuotaManager()
    today = qm.today
    print(f"  今日: {today}")

    remaining_steps = qm.remaining("steps")
    remaining_acc = qm.remaining("accelerations")
    print(f"  剩余步骤生成: {remaining_steps}, 剩余 AI 加速: {remaining_acc}")

    assert remaining_steps >= 0, "剩余次数不应为负"
    assert remaining_acc >= 0, "剩余次数不应为负"
    assert qm.used("steps") >= 0

    # 测试 consume + refund
    initial = qm.remaining("steps")
    if initial > 0:
        assert qm.consume("steps"), "consume 应成功"
        assert qm.used("steps") == initial + 1 - qm.remaining("steps") + 1
        qm.refund("steps")
        assert qm.remaining("steps") == initial, "refund 后应恢复"

    print("  [PASS] QuotaManager 基本功能")
    print("=== ai_accelerator self_test: ALL PASSED ===\n")


if __name__ == "__main__":
    self_test()
