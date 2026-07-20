"""MF_UI.dialogs — 对话框子包。

包含 AI 对话、联网搜索、设置等独立对话框。
"""
from .ai_dialog import AIDialog
from .ai_config_prompt import AIConfigPrompt
from .settings_dialog import SettingsDialog
from .search_panel import SearchPanel
from .history_dialog import HistoryDialog
from .about_dialog import AboutDialog

__all__ = [
    "AIDialog", "AIConfigPrompt", "SettingsDialog",
    "SearchPanel", "HistoryDialog", "AboutDialog",
]
