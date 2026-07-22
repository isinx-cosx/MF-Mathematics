# -*- coding: utf-8 -*-
"""设置对话框 — AI 配置选项卡 + 主题/通用设置。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from MF_AI.config import Config


# ── 测试连接 Worker ───────────────────────────────────────

class _TestConnectionWorker(QThread):
    finished = Signal(bool, str)  # success, message

    def __init__(self, api_key: str, base_url: str, model: str, parent=None):
        super().__init__(parent)
        self._key = api_key
        self._url = base_url
        self._model = model

    def run(self):
        try:
            from MF_AI.client import AIClient
            from MF_AI.config import Config as Cfg
            cfg = Cfg()
            cfg.set_api_key(self._key)
            cfg.set_base_url(self._url)
            client = AIClient(cfg)
            reply = client.chat(
                [{"role": "user", "content": "Hi"}],
                model=self._model, max_tokens=10,
            )
            if reply:
                self.finished.emit(True, "连接成功！AI 服务可用。")
            else:
                self.finished.emit(False, "连接返回空响应。")
        except Exception as e:
            self.finished.emit(False, f"连接失败: {e}")


# ═══════════════════════════════════════════════════════════════
#  SettingsDialog
# ═══════════════════════════════════════════════════════════════

class SettingsDialog(QDialog):
    """设置对话框 — 主题 / AI 配置。"""

    def __init__(self, parent=None, open_ai_tab: bool = False):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(800, 600)
        self.setMinimumSize(700, 500)
        self.setObjectName("settingsDialog")
        self._cfg = Config()

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        # Tab 1: 通用
        self._tabs.addTab(self._build_general_tab(), "通用")

        # Tab 2: AI 配置
        self._ai_tab = self._build_ai_tab()
        self._tabs.addTab(self._ai_tab, "AI 配置")

        # 底部按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                    QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self._on_save)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

        if open_ai_tab:
            self._tabs.setCurrentWidget(self._ai_tab)

        from MF_UI.components.mf_dialog import apply_dialog_title_bar
        apply_dialog_title_bar(self, "设置")

        # 继承主窗口的当前主题样式表
        if self.parent() is not None:
            self.setStyleSheet(self.parent().styleSheet())

    # ── 通用 Tab ──────────────────────────────────────────

    def _build_general_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(12)
        l.setContentsMargins(12, 12, 12, 12)

        # ── 主题 ──
        grp_theme = QGroupBox("外观")
        gl = QVBoxLayout(grp_theme)
        gl.setSpacing(8)
        row = QHBoxLayout(); row.setSpacing(8)
        row.addWidget(QLabel("默认主题:"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["亮色", "暗色"])
        row.addWidget(self._theme_combo, 1)
        gl.addLayout(row)
        l.addWidget(grp_theme)

        # ── 绘图 ──
        grp_plot = QGroupBox("绘图默认值")
        pl = QVBoxLayout(grp_plot)
        pl.setSpacing(8)

        row = QHBoxLayout(); row.setSpacing(8)
        row.addWidget(QLabel("X 轴范围:"))
        self._plot_x_min = QLineEdit()
        self._plot_x_min.setPlaceholderText("-10")
        self._plot_x_min.setFixedWidth(60)
        row.addWidget(self._plot_x_min)
        row.addWidget(QLabel("~"))
        self._plot_x_max = QLineEdit()
        self._plot_x_max.setPlaceholderText("10")
        self._plot_x_max.setFixedWidth(60)
        row.addWidget(self._plot_x_max)
        row.addStretch()
        pl.addLayout(row)

        row = QHBoxLayout(); row.setSpacing(8)
        row.addWidget(QLabel("Y 轴范围:"))
        self._plot_y_min = QLineEdit()
        self._plot_y_min.setPlaceholderText("-10")
        self._plot_y_min.setFixedWidth(60)
        row.addWidget(self._plot_y_min)
        row.addWidget(QLabel("~"))
        self._plot_y_max = QLineEdit()
        self._plot_y_max.setPlaceholderText("10")
        self._plot_y_max.setFixedWidth(60)
        row.addWidget(self._plot_y_max)
        row.addStretch()
        pl.addLayout(row)
        l.addWidget(grp_plot)

        # ── 通用 ──
        grp_gen = QGroupBox("通用")
        gl2 = QVBoxLayout(grp_gen)
        gl2.setSpacing(8)

        self._auto_update = QCheckBox("启动时自动检查更新")
        self._auto_update.setChecked(True)
        gl2.addWidget(self._auto_update)

        row = QHBoxLayout(); row.setSpacing(8)
        row.addWidget(QLabel("数值精度:"))
        self._precision_combo = QComboBox()
        self._precision_combo.addItems(["6", "8", "10", "12", "15"])
        self._precision_combo.setCurrentText("10")
        row.addWidget(self._precision_combo)
        row.addWidget(QLabel("位有效数字"))
        row.addStretch()
        gl2.addLayout(row)

        l.addWidget(grp_gen)

        # ── 加载当前设置 ──
        self._load_general_settings()
        l.addStretch()
        return w

    def _load_general_settings(self):
        """从配置加载通用设置。"""
        try:
            from MF_Mathematics.utils.config_manager import config
            cfg = config.raw
            theme = cfg.get("theme", "light")
            self._theme_combo.setCurrentText("亮色" if theme == "light" else "暗色")
            plot = cfg.get("plot", {})
            self._plot_x_min.setText(str(plot.get("x_min", "")))
            self._plot_x_max.setText(str(plot.get("x_max", "")))
            self._plot_y_min.setText(str(plot.get("y_min", "")))
            self._plot_y_max.setText(str(plot.get("y_max", "")))
            self._auto_update.setChecked(cfg.get("auto_update", True))
            self._precision_combo.setCurrentText(str(cfg.get("precision", 10)))
        except Exception:
            pass

    def _save_general_settings(self):
        """保存通用设置到配置文件。"""
        try:
            from MF_Mathematics.utils.config_manager import config
            config.update("theme", {
                "default": "light" if self._theme_combo.currentText() == "亮色" else "dark",
            })
            config.update("plot", {
                "x_min": self._plot_x_min.text().strip() or "-10",
                "x_max": self._plot_x_max.text().strip() or "10",
                "y_min": self._plot_y_min.text().strip() or "-10",
                "y_max": self._plot_y_max.text().strip() or "10",
            })
            config.update("auto_update", {
                "enabled": self._auto_update.isChecked(),
            })
            config.update("numerical", {
                "precision": int(self._precision_combo.currentText()),
            })
        except Exception:
            pass

    # ── AI 配置 Tab ────────────────────────────────────────

    def _build_ai_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(10)
        l.setContentsMargins(12, 12, 12, 12)

        # ── 远程 API 配置 ──
        grp_api = QGroupBox("远程 API 配置")
        gl = QVBoxLayout(grp_api)
        gl.setSpacing(8)

        # API Key
        row = QHBoxLayout(); row.setSpacing(8)
        row.addWidget(QLabel("API Key:"))
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setPlaceholderText("sk-...")
        if self._cfg.api_key:
            self._api_key_input.setText(self._cfg.api_key)
        row.addWidget(self._api_key_input, 1)
        self._show_key_btn = QPushButton("👁")
        self._show_key_btn.setFixedWidth(32)
        self._show_key_btn.setCheckable(True)
        self._show_key_btn.toggled.connect(self._toggle_key_visible)
        row.addWidget(self._show_key_btn)
        gl.addLayout(row)

        # 厂商
        row = QHBoxLayout(); row.setSpacing(8)
        row.addWidget(QLabel("厂商:"))
        self._provider_combo = QComboBox()
        self._provider_combo.addItems(["DeepSeek", "OpenAI", "Ollama"])
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)
        row.addWidget(self._provider_combo, 1)
        gl.addLayout(row)

        # 模型
        row = QHBoxLayout(); row.setSpacing(8)
        row.addWidget(QLabel("模型:"))
        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        row.addWidget(self._model_combo, 1)
        gl.addLayout(row)

        # API 端点
        row = QHBoxLayout(); row.setSpacing(8)
        row.addWidget(QLabel("端点:"))
        self._endpoint_input = QLineEdit()
        self._endpoint_input.setPlaceholderText("https://api.deepseek.com")
        row.addWidget(self._endpoint_input, 1)
        gl.addLayout(row)

        # 测试连接
        row = QHBoxLayout()
        self._test_btn = QPushButton("测试连接")
        self._test_btn.setObjectName("settings_secondary_btn")
        self._test_btn.clicked.connect(self._test_connection)
        row.addWidget(self._test_btn)
        self._test_status = QLabel("")
        self._test_status.setStyleSheet("font-size: 11px;")
        row.addWidget(self._test_status, 1)
        gl.addLayout(row)

        l.addWidget(grp_api)

        # ── 本地模型配置 ──
        grp_local = QGroupBox("本地模型配置")
        ll = QVBoxLayout(grp_local)
        ll.setSpacing(8)

        self._local_enabled = QCheckBox("启用本地模型（优先于远程 API）")
        self._local_enabled.setChecked(self._cfg.local_model_enabled)
        ll.addWidget(self._local_enabled)

        row = QHBoxLayout(); row.setSpacing(8)
        row.addWidget(QLabel("路径:"))
        self._local_path = QLineEdit()
        self._local_path.setPlaceholderText("http://localhost:11434/v1")
        if self._cfg.local_model_path:
            self._local_path.setText(self._cfg.local_model_path)
        row.addWidget(self._local_path, 1)
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._browse_local)
        row.addWidget(browse)
        ll.addLayout(row)

        l.addWidget(grp_local)
        l.addStretch()

        # 初始化
        self._provider_combo.setCurrentText(self._cfg.provider)
        self._on_provider_changed(self._cfg.provider)
        self._endpoint_input.setText(self._cfg.get_provider_endpoint())
        idx = self._model_combo.findText(self._cfg.get_default_model())
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)

        return w

    # ── 交互 ──────────────────────────────────────────────

    def _toggle_key_visible(self, checked: bool):
        self._api_key_input.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)

    def _on_provider_changed(self, provider: str):
        self._model_combo.clear()
        models = self._cfg.get_provider_models(provider)
        self._model_combo.addItems(models)
        ep = self._cfg.get_provider_endpoint(provider)
        self._endpoint_input.setText(ep)

    def _browse_local(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择本地模型", "", "所有文件 (*)")
        if path:
            self._local_path.setText(path)

    def _test_connection(self):
        key = self._api_key_input.text().strip()
        url = self._endpoint_input.text().strip()
        model = self._model_combo.currentText().strip()
        if not key:
            self._test_status.setText("请先输入 API Key")
            self._test_status.setStyleSheet("color: #ef4444; font-size: 11px;")
            return
        if not model:
            self._test_status.setText("请选择模型")
            return

        self._test_btn.setEnabled(False)
        self._test_status.setText("测试中…")
        self._test_status.setStyleSheet("color: #3b82f6; font-size: 11px;")

        # 断开旧 worker 信号，避免重复连接
        if hasattr(self, '_worker') and self._worker is not None:
            try:
                self._worker.finished.disconnect(self._on_test_result)
            except (TypeError, RuntimeError):
                pass
        self._worker = _TestConnectionWorker(key, url, model, self)
        self._worker.finished.connect(self._on_test_result)
        self._worker.start()

    def _on_test_result(self, success: bool, message: str):
        self._test_btn.setEnabled(True)
        color = "#10b981" if success else "#ef4444"
        self._test_status.setText(message)
        self._test_status.setStyleSheet(f"color: {color}; font-size: 11px;")

    def _on_save(self):
        # 保存 AI 配置
        cfg = self._cfg
        key = self._api_key_input.text().strip()
        if key:
            cfg.set_api_key(key)
        cfg.set_base_url(self._endpoint_input.text().strip())
        cfg.set_model(self._model_combo.currentText().strip())
        cfg.set_provider(self._provider_combo.currentText())
        cfg.set_local_model(
            self._local_enabled.isChecked(),
            self._local_path.text().strip(),
        )
        cfg.save_to_files()

        # 保存通用设置
        self._save_general_settings()

        # 立即应用主题
        self._apply_theme_now()

        self.accept()

    def _apply_theme_now(self):
        """将主题设置立即应用到主窗口。"""
        try:
            from MF_Mathematics.utils.config_manager import config
            theme = config.raw.get("theme", {}).get("default", "light")
            # 查找主窗口实例并切换主题
            from PySide6.QtWidgets import QApplication
            for w in QApplication.topLevelWidgets():
                if hasattr(w, "_switch_to_light") and hasattr(w, "_switch_to_dark"):
                    if theme == "dark":
                        w._switch_to_dark()
                    else:
                        w._switch_to_light()
                    break
        except Exception:
            pass
