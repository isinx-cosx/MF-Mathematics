# -*- coding: utf-8 -*-
"""AI 配置管理 — 单例模式，支持 config.yaml + .env + 环境变量。

优先级: 运行时 set_xxx() > config.yaml > 环境变量 > .env > 默认值
"""

from __future__ import annotations

import os
import sys
from typing import Any, ClassVar

from MF_AI.exceptions import AIConfigError

# ── 硬编码后备默认值 ──────────────────────────────────────
_DEFAULT_BASE_URL = "https://api.deepseek.com"
_DEFAULT_MODEL = "deepseek-v4-pro"
_DEFAULT_MAX_TOKENS = 8192
_DEFAULT_TEMPERATURE = 0.7
_DEFAULT_CONTEXT_LENGTH = 1_048_576


# ── .env 加载 ─────────────────────────────────────────────

def _load_dotenv(path: str | None = None) -> dict[str, str]:
    """手动解析 .env 文件（避免 python-dotenv 依赖）。

    支持: KEY=VALUE, KEY="VALUE", 注释 #, 空行。
    """
    search_paths = []
    if path:
        search_paths.append(path)
    if os.getcwd():
        search_paths.append(os.path.join(os.getcwd(), ".env"))
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        search_paths.append(os.path.join(root, ".env"))
    except Exception:
        pass

    result: dict[str, str] = {}
    for p in search_paths:
        try:
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key:
                        result[key] = value
        except FileNotFoundError:
            pass
    return result


# ── config.yaml 加载 ──────────────────────────────────────

def _find_yaml_path() -> str | None:
    """查找 config.yaml 路径。"""
    candidates = []
    # 1. MF_AI 同级目录
    try:
        ai_dir = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(ai_dir, "config.yaml"))
    except Exception:
        pass
    # 2. 当前工作目录
    if os.getcwd():
        candidates.append(os.path.join(os.getcwd(), "config.yaml"))
        candidates.append(os.path.join(os.getcwd(), "MF_AI", "config.yaml"))
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def _load_yaml(path: str | None = None) -> dict[str, Any]:
    """加载 config.yaml，返回解析后的字典。

    yaml 格式错误或 pyyaml 不可用时打印警告，返回空字典。
    """
    yaml_path = path or _find_yaml_path()
    if yaml_path is None:
        return {}

    # 尝试 pyyaml → 手动解析
    try:
        import yaml as _yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = _yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except ImportError:
        pass
    except Exception as e:
        print(f"[MF_AI] 警告: config.yaml 解析失败 ({e})，使用默认配置。",
              file=sys.stderr)
        return {}

    # 回退：简单的手动 YAML 解析（仅支持顶层 key: value 和嵌套一层）
    try:
        return _parse_yaml_manual(yaml_path)
    except Exception as e:
        print(f"[MF_AI] 警告: config.yaml 手动解析失败 ({e})，使用默认配置。",
              file=sys.stderr)
        return {}


def _parse_yaml_manual(path: str) -> dict[str, Any]:
    """简易 YAML 解析器（无需 pyyaml）。

    支持:
      - key: value（标量、数字、字符串）
      - key:（嵌套块，缩进 2 空格）
      - # 注释
    """
    result: dict[str, Any] = {}
    current_map: dict[str, Any] | None = None
    current_key: str | None = None
    current_section: str | None = None

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # 检测缩进（顶级 vs 嵌套）
        indent = len(line) - len(line.lstrip())

        if indent == 0 and ":" in stripped and not stripped.startswith("-"):
            # 顶级键
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            current_section = key
            current_map = None
            current_key = None

            if val:
                # 标量值
                result[key] = _yaml_scalar(val)

        elif indent >= 2 and stripped and not stripped.startswith("-"):
            # 嵌套键（缩进块内）
            if ":" in stripped:
                k, _, v = stripped.partition(":")
                k = k.strip()
                v = v.strip().strip('"').strip("'")

                if current_section and current_section not in result:
                    result[current_section] = {}
                if isinstance(result.get(current_section), dict):
                    result[current_section][k] = _yaml_scalar(v) if v else v

    return result


def _yaml_scalar(val: str) -> Any:
    """将 YAML 字符串值转换为 Python 类型。"""
    if val.lower() in ("true", "yes", "on"):
        return True
    if val.lower() in ("false", "no", "off"):
        return False
    if val.lower() in ("null", "~", ""):
        return None
    try:
        if "." in val or "e" in val.lower():
            return float(val)
        return int(val)
    except ValueError:
        return val


# ═══════════════════════════════════════════════════════════════
#  Config 单例
# ═══════════════════════════════════════════════════════════════

class Config:
    """AI 配置单例。

    加载顺序: config.yaml → .env → 环境变量
    运行时 set_xxx() 覆盖一切。

    用法:
        cfg = Config()
        cfg.set_api_key("sk-xxx")
        model = cfg.get_model_for_role("Sonnet")  # → "deepseek-v4-pro"
    """

    _instance: ClassVar[Config | None] = None

    def __new__(cls) -> Config:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # ── 1. config.yaml ──
        self._yaml = _load_yaml()

        # ── 2. .env ──
        dotenv = _load_dotenv()

        # ── 3. 合并配置 ──
        self._api_base = self._yaml_val("api_base") or os.environ.get(
            "AI_BASE_URL", dotenv.get("AI_BASE_URL", _DEFAULT_BASE_URL))

        self._default_model = self._yaml_val("default_model") or os.environ.get(
            "AI_MODEL", dotenv.get("AI_MODEL", _DEFAULT_MODEL))

        self._context_length = self._yaml_val("context_length") or _DEFAULT_CONTEXT_LENGTH

        self._model_map: dict[str, str] = self._yaml.get("model_map", {})

        self._model_params: dict[str, dict] = self._yaml.get("model_params", {})

        # API Key — 仅从环境变量 / .env 获取（不在 yaml 中）
        self._api_key = os.environ.get("AI_API_KEY", dotenv.get("AI_API_KEY", ""))
        self._max_tokens = int(os.environ.get("AI_MAX_TOKENS", dotenv.get(
            "AI_MAX_TOKENS", str(_DEFAULT_MAX_TOKENS))))
        self._temperature = float(os.environ.get("AI_TEMPERATURE", dotenv.get(
            "AI_TEMPERATURE", str(_DEFAULT_TEMPERATURE))))
        self._system_prompt = os.environ.get(
            "AI_SYSTEM_PROMPT", dotenv.get("AI_SYSTEM_PROMPT", ""))

        # 启动时未配置 API Key 仅警告
        if not self._api_key:
            print("[MF_AI] 警告: AI_API_KEY 未设置。可通过 set_api_key() 运行时配置。",
                  file=sys.stderr)

    # ── YAML 辅助 ─────────────────────────────────────────

    def _yaml_val(self, key: str, default: Any = None) -> Any:
        return self._yaml.get(key, default)

    # ── 属性（保持向后兼容）───────────────────────────────

    @property
    def api_key(self) -> str:
        return self._api_key

    @property
    def base_url(self) -> str:
        return self._api_base

    @property
    def model(self) -> str:
        return self._default_model

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    @property
    def temperature(self) -> float:
        return self._temperature

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    @property
    def context_length(self) -> int:
        return self._context_length

    # ── 新增方法 ──────────────────────────────────────────

    def get_api_base(self) -> str:
        """返回 API 端点（优先 config.yaml → env → 默认）。"""
        return self._api_base

    def get_default_model(self) -> str:
        """返回默认模型名。"""
        return self._default_model

    def get_model_for_role(self, role: str) -> str:
        """根据角色名返回实际模型名。

        Args:
            role: 角色标识，如 "Sonnet", "Opus", "Chat", "Reasoner"。

        Returns:
            实际模型名。若 role 不在 model_map 中，返回 default_model。
        """
        return self._model_map.get(role, self._default_model)

    def get_model_params(self, model: str | None = None) -> dict:
        """返回指定模型的独立参数。

        Args:
            model: 模型名。为 None 时使用 default_model。

        Returns:
            {"max_tokens": N, "temperature": float, ...} 或空 dict。
        """
        model = model or self._default_model
        return self._model_params.get(model, {}).copy()

    @property
    def model_map(self) -> dict[str, str]:
        """返回完整的角色→模型映射表（只读）。"""
        return dict(self._model_map)

    @property
    def available_roles(self) -> list[str]:
        """返回所有已注册的角色名。"""
        return list(self._model_map.keys())

    @property
    def available_models(self) -> list[str]:
        """返回所有已注册的模型参数键名。"""
        return list(self._model_params.keys())

    # ── 运行时设置 ────────────────────────────────────────

    def set_api_key(self, key: str) -> None:
        if not key or not key.strip():
            raise AIConfigError("API Key 不能为空")
        self._api_key = key.strip()

    def set_model(self, model: str) -> None:
        """运行时覆盖默认模型。"""
        if not model or not model.strip():
            raise AIConfigError("模型名不能为空")
        self._default_model = model.strip()

    def set_base_url(self, url: str) -> None:
        self._api_base = url.strip()

    def set_temperature(self, t: float) -> None:
        self._temperature = max(0.0, min(2.0, t))

    def set_max_tokens(self, n: int) -> None:
        self._max_tokens = max(1, n)

    def set_system_prompt(self, prompt: str) -> None:
        self._system_prompt = prompt

    def validate(self) -> None:
        """校验必要配置，缺失则抛出 AIConfigError。"""
        if not self._api_key:
            raise AIConfigError(
                "AI_API_KEY 未设置。请设置环境变量或调用 set_api_key()。"
            )

    def reload_yaml(self) -> None:
        """重新加载 config.yaml（用于用户编辑后热更新）。"""
        self._yaml = _load_yaml()
        self._api_base = self._yaml_val("api_base") or self._api_base
        self._default_model = self._yaml_val("default_model") or self._default_model
        self._context_length = self._yaml_val("context_length") or self._context_length
        self._model_map = self._yaml.get("model_map", {}) or self._model_map
        self._model_params = self._yaml.get("model_params", {}) or self._model_params
