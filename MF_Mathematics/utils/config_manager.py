"""ConfigManager — 全局配置单例。

统一加载项目根目录的 config.json，提供类型安全的节级访问器。
所有阈值、颜色、限制等配置必须通过 ConfigManager 读取，禁止硬编码或多处
重复实现 _load_config()。

用法:
    from MF_Mathematics.utils.config_manager import config

    guard_cfg = config.math_guard          # 完整 math_guard 节
    level1    = config.math_guard_level1   # 快捷访问 level1
    colors    = config.plot_colors         # 快捷访问 plot.colors
"""

from __future__ import annotations

import json
import os
from typing import Any

# ── 项目根目录定位 ──────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CONFIG_PATH = os.path.join(_ROOT, "config.json")


def _resolve_config_path() -> str:
    """逐级向上查找 config.json，兜底为 MF_Mathematics 上级目录。"""
    if os.path.exists(_CONFIG_PATH):
        return _CONFIG_PATH
    # 回退：从当前文件向上搜索（兼容不同部署结构）
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        candidate = os.path.join(current, "config.json")
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return _CONFIG_PATH  # 文件不存在时返回默认路径，由 _load() 处理


class ConfigManager:
    """全局配置管理器（单例）。

    自动加载项目根目录的 config.json，提供节级属性和快捷子属性访问。
    若文件缺失，所有值退回空字典，不抛异常。
    """

    _instance: ConfigManager | None = None
    _data: dict[str, Any]

    # ── config.json 顶层节名 ──────────────────────────────────────
    _SECTIONS: tuple[str, ...] = ("math_guard", "plot", "ai", "numerical")

    def __new__(cls) -> ConfigManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    # ── 加载与重载 ────────────────────────────────────────────────

    def _load(self) -> None:
        """从 config.json 加载原始字典。文件缺失时退回空字典。"""
        path = _resolve_config_path()
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self._data = {}

    def reload(self) -> None:
        """重新加载配置文件（用于运行时修改 config.json 后刷新）。"""
        self._load()

    def save(self) -> None:
        """将当前配置写回 config.json。"""
        path = _resolve_config_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            raise OSError(f"无法写入配置文件 {path}: {e}")

    def update(self, section: str, data: dict) -> None:
        """更新指定节并立即保存。

        Args:
            section: 节名（如 \"theme\", \"plot\"）。
            data: 要合并的键值。
        """
        if section not in self._data:
            self._data[section] = {}
        self._data[section].update(data)
        self.save()

    # ── 原始访问 ──────────────────────────────────────────────────

    @property
    def raw(self) -> dict[str, Any]:
        """返回完整配置字典（只读参考，修改不会回写文件）。"""
        return dict(self._data)

    def get(self, *keys: str, default: Any = None) -> Any:
        """深层安全取值：config.get("math_guard", "level1", "max_ops")。

        Args:
            *keys: 逐级下钻的键序列。
            default: 键缺失时的默认值。

        Returns:
            嵌套字典中的最终值，或 default。
        """
        node: Any = self._data
        for k in keys:
            if isinstance(node, dict) and k in node:
                node = node[k]
            else:
                return default
        return node

    # ── 节级属性 ──────────────────────────────────────────────────

    @property
    def math_guard(self) -> dict[str, Any]:
        """math_guard 节完整字典。"""
        return self._data.get("math_guard", {})

    @property
    def plot(self) -> dict[str, Any]:
        """plot 节完整字典。"""
        return self._data.get("plot", {})

    @property
    def ai(self) -> dict[str, Any]:
        """ai 节完整字典。"""
        return self._data.get("ai", {})

    @property
    def numerical(self) -> dict[str, Any]:
        """numerical 节完整字典。"""
        return self._data.get("numerical", {})

    # ── math_guard 快捷子属性 ─────────────────────────────────────

    @property
    def math_guard_level1(self) -> dict[str, Any]:
        """math_guard.level1 — 慢速预警阈值。"""
        return self.math_guard.get("level1", {})

    @property
    def math_guard_level2(self) -> dict[str, Any]:
        """math_guard.level2 — 爆炸风险阈值。"""
        return self.math_guard.get("level2", {})

    @property
    def math_guard_level3(self) -> dict[str, Any]:
        """math_guard.level3 — 硬错误描述。"""
        return self.math_guard.get("level3", {})

    @property
    def math_guard_limit(self) -> dict[str, Any]:
        """math_guard.limit — 极限分析阈值。"""
        return self.math_guard.get("limit", {})

    # ── plot 快捷子属性 ───────────────────────────────────────────

    @property
    def plot_colors(self) -> list[str]:
        """plot.colors — 绘图配色列表。"""
        return self.plot.get(
            "colors",
            ["#e74c3c", "#3498db", "#2ecc71", "#f39c12",
             "#9b59b6", "#1abc9c", "#e67e22", "#e84393"],
        )

    @property
    def plot_range_limit(self) -> list[float]:
        """plot.range_limit — 坐标轴范围限制 [min, max]。"""
        return self.plot.get("range_limit", [-10000, 10000])

    # ── numerical 快捷子属性 ──────────────────────────────────────

    @property
    def numerical_max_iterations(self) -> int:
        """numerical.max_iterations — 最大迭代次数。"""
        return self.numerical.get("max_iterations", 10_000_000)

    @property
    def numerical_max_precision(self) -> int:
        """numerical.max_precision — 最大计算精度（小数位）。"""
        return self.numerical.get("max_precision", 15)

    @property
    def numerical_ramanujan_timeout(self) -> int:
        """numerical.ramanujan_timeout — 拉马努金算法超时（秒）。"""
        return self.numerical.get("ramanujan_timeout", 1)

    # ── ai 快捷子属性 ─────────────────────────────────────────────

    @property
    def ai_daily_free_steps(self) -> int:
        """ai.daily_free_steps — 每日免费 AI 计算步数。"""
        return self.ai.get("daily_free_steps", 5)

    @property
    def ai_daily_free_accelerations(self) -> int:
        """ai.daily_free_accelerations — 每日免费 AI 加速次数。"""
        return self.ai.get("daily_free_accelerations", 3)

    # ── 工具方法 ──────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """导出为字典（与 raw 相同，便于序列化）。"""
        return self.raw

    def __repr__(self) -> str:
        sections = ", ".join(
            f"{s}={len(self._data.get(s, {}))} keys"
            for s in self._SECTIONS
        )
        loaded = "loaded" if self._data else "empty"
        return f"ConfigManager({loaded}, {sections})"


# ── 全局单例 ──────────────────────────────────────────────────────
config = ConfigManager()


# ═══════════════════════════════════════════════════════════════════
# self_test
# ═══════════════════════════════════════════════════════════════════

def self_test() -> None:
    """验证 ConfigManager 单例、节访问、快捷属性与 get() 方法。"""
    print("=== config_manager self_test ===")

    # 1. 单例性
    c1 = ConfigManager()
    c2 = ConfigManager()
    assert c1 is c2, "ConfigManager 不是单例"
    print("  [PASS] 单例模式")

    # 2. 顶层节存在
    assert isinstance(config.math_guard, dict), "math_guard 应为 dict"
    assert isinstance(config.plot, dict), "plot 应为 dict"
    assert isinstance(config.ai, dict), "ai 应为 dict"
    assert isinstance(config.numerical, dict), "numerical 应为 dict"
    print("  [PASS] 四个顶层节均为 dict")

    # 3. 快捷属性
    assert isinstance(config.math_guard_level1, dict), "level1 应为 dict"
    assert isinstance(config.plot_colors, list), "plot_colors 应为 list"
    assert isinstance(config.numerical_max_iterations, int), "max_iterations 应为 int"
    assert isinstance(config.ai_daily_free_steps, int), "daily_free_steps 应为 int"
    print("  [PASS] 快捷属性类型正确")

    # 4. get() 深层取值
    max_ops = config.get("math_guard", "level1", "max_ops")
    assert isinstance(max_ops, int), f"max_ops 应为 int，得到 {type(max_ops)}"
    print(f"  [PASS] get('math_guard','level1','max_ops') = {max_ops}")

    # 5. get() 缺失键返回 default
    missing = config.get("nonexistent", "key", default=42)
    assert missing == 42, f"缺失键应返回 42，得到 {missing}"
    print("  [PASS] get() 缺失键返回 default")

    # 6. raw 与 to_dict 一致
    raw = config.raw
    d = config.to_dict()
    assert raw == d, "raw 与 to_dict 应一致"
    print(f"  [PASS] raw/to_dict 一致，含 {len(raw)} 个顶层键")

    # 7. reload 不抛异常
    config.reload()
    print("  [PASS] reload() 成功")

    print("=== config_manager self_test: ALL PASSED ===\n")


if __name__ == "__main__":
    self_test()
