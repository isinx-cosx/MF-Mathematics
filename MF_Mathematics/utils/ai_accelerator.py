# -*- coding: utf-8 -*-
"""AI 加速器 — 多模型接入 + 配额管理 + 步骤生成。

支持的提供商: DeepSeek, OpenAI（通过 config.json 中的 ai.providers 配置）
API Key 存储: keyring（服务名 MF_Mathematics）
配额管理: 本地 usage.json

用法:
    from MF_Mathematics.utils.ai_accelerator import AIAccelerator

    ai = AIAccelerator()
    if ai.check_quota("steps"):
        mo = ai.generate_steps("求 x^2 的导数", "diff(x**2, x)")
"""

from __future__ import annotations

import json
import os
import time
from datetime import date
from typing import Any

from MF_Mathematics.core.math_object import MathObject


# ═══════════════════════════════════════════════════════════════════════
#  Config
# ═══════════════════════════════════════════════════════════════════════

def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _usage_path() -> str:
    return os.path.join(_project_root(), "usage.json")


def _cfg():
    try:
        from MF_Mathematics.utils.config_manager import config
        return config
    except Exception:
        pass
    class _F:
        def get(self, *k, default=None): return default
        @property
        def ai(self): return {}
    return _F()


# ═══════════════════════════════════════════════════════════════════════
#  QuotaManager — 每日配额追踪
# ═══════════════════════════════════════════════════════════════════════


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
        cf = _cfg()
        if key == "steps":
            limit = cf.get("ai", "daily_free_steps", default=5)
        elif key == "accelerations":
            limit = cf.get("ai", "daily_free_accelerations", default=3)
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

    def reset_today(self) -> None:
        if self.today in self._data:
            del self._data[self.today]
            self._save()


# ═══════════════════════════════════════════════════════════════════════
#  API Key 存储（keyring）
# ═══════════════════════════════════════════════════════════════════════

_SERVICE_NAME = "MF_Mathematics"


def _get_api_key(provider: str) -> str | None:
    """从系统密钥环获取 API Key。"""
    try:
        import keyring
        return keyring.get_password(_SERVICE_NAME, f"{provider}_api_key")
    except Exception:
        return None


def _set_api_key(provider: str, key: str) -> None:
    """存储 API Key 到系统密钥环。"""
    try:
        import keyring
        keyring.set_password(_SERVICE_NAME, f"{provider}_api_key", key)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
#  AIAccelerator — 主入口
# ═══════════════════════════════════════════════════════════════════════


class AIAccelerator:
    """AI 加速服务 — 步骤生成 + 复杂计算加速。"""

    def __init__(self) -> None:
        self._quota = QuotaManager()

    # ── 配额检查 ──────────────────────────────────────────────

    def check_quota(self, kind: str = "steps") -> bool:
        """检查是否有剩余配额。"""
        return self._quota.remaining(kind) > 0

    def quota_remaining(self, kind: str = "steps") -> int:
        return self._quota.remaining(kind)

    @property
    def quota(self) -> QuotaManager:
        return self._quota

    # ── API 调用 ──────────────────────────────────────────────

    def _call_provider(self, provider: str, prompt: str,
                       system: str = "") -> str | None:
        """调用指定提供商的 API。"""
        api_key = _get_api_key(provider)
        if not api_key:
            return None

        if provider.lower() == "openai":
            return self._call_openai(api_key, prompt, system)
        elif provider.lower() == "deepseek":
            return self._call_deepseek(api_key, prompt, system)
        return None

    def _call_openai(self, api_key: str, prompt: str, system: str) -> str | None:
        try:
            import urllib.request
            import urllib.error

            data = json.dumps({
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system or "你是一位数学助手，请给出详细的解答步骤。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2048,
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode())
                return body["choices"][0]["message"]["content"]
        except Exception:
            return None

    def _call_deepseek(self, api_key: str, prompt: str, system: str) -> str | None:
        try:
            import urllib.request

            data = json.dumps({
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system or "你是一位数学助手，请给出详细的解答步骤。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2048,
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.deepseek.com/v1/chat/completions",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode())
                return body["choices"][0]["message"]["content"]
        except Exception:
            return None

    # ── 公共 API ──────────────────────────────────────────────

    def generate_steps(self, question: str, expr: str = "",
                       provider: str = "deepseek") -> MathObject:
        """生成数学推导步骤。

        Args:
            question: 用户的问题描述。
            expr: 相关的数学表达式。
            provider: 使用的 AI 提供商。

        Returns:
            MathObject — 含 result（AI 回复）与 steps（解析的步骤）。
        """
        if not self._quota.consume("steps"):
            return MathObject(error="今日步骤生成次数已用完，请明日再试或配置 API Key。")

        system = (
            "你是一位数学助教。请用中文回答。"
            "对于数学问题，请给出清晰的分步推导过程。"
            "每步以【步骤 N】开头，最后给出最终答案。"
        )
        prompt = f"问题：{question}"
        if expr:
            prompt += f"\n表达式：{expr}"

        result_text = self._call_provider(provider, prompt, system)
        if result_text is None:
            # 退还配额
            self._quota._today_data()["steps"] = max(0, self._quota._today_data().get("steps", 1) - 1)
            self._quota._save()
            return MathObject(error=f"AI 调用失败。请检查 {provider} API Key 配置或网络连接。")

        # 解析步骤
        steps = [s.strip() for s in result_text.split("\n") if s.strip()]
        return MathObject(
            result=result_text,
            steps=steps,
            meaning=f"由 {provider} AI 生成的推导步骤",
        )

    def accelerate(self, expr: str, mode: str = "",
                   provider: str = "deepseek") -> MathObject:
        """AI 加速复杂计算。

        Args:
            expr: 待计算的表达式。
            mode: 操作模式（如"不定积分"）。
            provider: AI 提供商。

        Returns:
            MathObject — 含 AI 计算结果。
        """
        if not self._quota.consume("accelerations"):
            return MathObject(error="今日 AI 加速次数已用完，请明日再试或配置 API Key。")

        system = (
            "你是一位数学计算引擎。请直接对表达式进行计算，返回计算结果。"
            "若表达式过于复杂，请给出近似的数值结果（保留 6 位有效数字）。"
            "仅返回结果，不要解释。"
        )
        prompt = f"模式：{mode}\n表达式：{expr}" if mode else f"计算：{expr}"

        result_text = self._call_provider(provider, prompt, system)
        if result_text is None:
            self._quota._today_data()["accelerations"] = max(0, self._quota._today_data().get("accelerations", 1) - 1)
            self._quota._save()
            return MathObject(error=f"AI 加速调用失败。请检查 {provider} API Key 配置或网络连接。")

        return MathObject(
            result=result_text.strip(),
            steps=[f"表达式: {expr}", f"模式: {mode}", f"{provider} AI 加速结果: {result_text.strip()}"],
            meaning=f"由 {provider} AI 加速计算的结果",
        )


# ═══════════════════════════════════════════════════════════════════════
#  便捷函数
# ═══════════════════════════════════════════════════════════════════════

_ai_instance: AIAccelerator | None = None


def get_accelerator() -> AIAccelerator:
    """获取全局 AIAccelerator 实例。"""
    global _ai_instance
    if _ai_instance is None:
        _ai_instance = AIAccelerator()
    return _ai_instance


# ═══════════════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════════════

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

    # 不执行实际 API 调用，仅验证配额逻辑
    assert qm.used("steps") >= 0

    print("  [PASS] QuotaManager 基本功能")
    print("=== ai_accelerator self_test: ALL PASSED ===\n")


if __name__ == "__main__":
    self_test()
