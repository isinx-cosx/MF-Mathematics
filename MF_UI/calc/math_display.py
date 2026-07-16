# -*- coding: utf-8 -*-
"""数学公式显示组件 — 纯 PySide6，无 WebEngine 依赖。

LatexLineEdit : 普通文本输入框 (QLineEdit 子类)
MathDisplay   : 只读 LaTeX 渲染控件 (matplotlib, Computer Modern 字体)
ResultDialog  : 计算结果弹窗 (含 MathDisplay + 步骤按钮)
"""

from __future__ import annotations

import re
import sys as _sys
import os as _os
from io import BytesIO
from typing import Any

_proj_root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
if _proj_root not in _sys.path:
    _sys.path.insert(0, _proj_root)

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

DEFAULT_FONT_SIZE = 10

# ═══════════════════════════════════════════════════════════════════
#  LatexLineEdit
# ═══════════════════════════════════════════════════════════════════


class LatexLineEdit(QLineEdit):
    """普通文本输入框。"""
    pass


# ═══════════════════════════════════════════════════════════════════
#  LaTeX 符号映射 & 工具函数
# ═══════════════════════════════════════════════════════════════════

_LATEX_MAP: dict[str, str] = {
    "sin": r"\sin","cos": r"\cos","tan": r"\tan","cot": r"\cot","sec": r"\sec","csc": r"\csc",
    "arcsin": r"\arcsin","arccos": r"\arccos","arctan": r"\arctan",
    "sinh": r"\sinh","cosh": r"\cosh","tanh": r"\tanh",
    "ln": r"\ln","log": r"\log","exp": r"\exp","sqrt": r"\sqrt","abs": r"\left|",
    "lim": r"\lim","max": r"\max","min": r"\min","det": r"\det","gcd": r"\gcd",
    "alpha": r"\alpha","beta": r"\beta","gamma": r"\gamma","delta": r"\delta",
    "epsilon": r"\epsilon","zeta": r"\zeta","eta": r"\eta","theta": r"\theta",
    "iota": r"\iota","kappa": r"\kappa","lambda": r"\lambda","mu": r"\mu",
    "nu": r"\nu","xi": r"\xi","pi": r"\pi","rho": r"\rho","sigma": r"\sigma",
    "tau": r"\tau","upsilon": r"\upsilon","phi": r"\phi","chi": r"\chi",
    "psi": r"\psi","omega": r"\omega",
    "Gamma": r"\Gamma","Delta": r"\Delta","Theta": r"\Theta","Lambda": r"\Lambda",
    "Xi": r"\Xi","Pi": r"\Pi","Sigma": r"\Sigma","Phi": r"\Phi","Psi": r"\Psi","Omega": r"\Omega",
    "infty": r"\infty","inf": r"\infty",
    "cdot": r"\cdot","times": r"\times","div": r"\div","pm": r"\pm","mp": r"\mp",
    "leq": r"\leq","geq": r"\geq","neq": r"\neq","approx": r"\approx","equiv": r"\equiv",
    "int": r"\int","sum": r"\sum","prod": r"\prod","partial": r"\partial","nabla": r"\nabla",
    "forall": r"\forall","exists": r"\exists","emptyset": r"\emptyset","to": r"\to",
    "rightarrow": r"\rightarrow","Rightarrow": r"\Rightarrow",
    "leftarrow": r"\leftarrow","Leftarrow": r"\Leftarrow",
}
_SORTED_KEYS = sorted(_LATEX_MAP.keys(), key=len, reverse=True)
_SYM_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in _SORTED_KEYS) + r")\b")
_FRAC_RE = re.compile(r"([a-zA-Z0-9_^{}]+)\s*/\s*([a-zA-Z0-9_^{}]+)")
_SUP1_RE = re.compile(r"\^(\d|[a-zA-Z])(?![{])")
_SUB1_RE = re.compile(r"_(\d|[a-zA-Z])(?![{])")


def natural_to_latex(text: str) -> str:
    """自然数学符号 → 标准 LaTeX。"""
    if not text or not text.strip():
        return ""
    s = text.strip().replace("**", "^")
    s = _SYM_RE.sub(lambda m: _LATEX_MAP[m.group(0)], s)
    s = _SUP1_RE.sub(r"^{\1}", s)
    s = _SUB1_RE.sub(r"_{\1}", s)
    s = _FRAC_RE.sub(lambda m: r"\frac{" + m.group(1) + "}{" + m.group(2) + "}", s)
    return s


# ═══════════════════════════════════════════════════════════════════
#  MathDisplay — 长图 + 水平滚动
# ═══════════════════════════════════════════════════════════════════

class MathDisplay(QWidget):
    """只读 LaTeX 渲染控件。

    - 整段 LaTeX → 一张长图，不做任何换行分割
    - QScrollArea 水平滚动查看完整公式
    - 字体固定 10pt，清晰可读
    - Ctrl+滚轮 缩放，双击重置
    - setDarkTheme 控制亮/暗色主题

    公共接口
    --------
    - setLatex(latex)
    - setDarkTheme(enabled)
    - clear()
    - setFontSize(size)
    - zoomIn / zoomOut / zoomReset
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._latex: str = ""
        self._dark: bool = False
        self._font_size: int = DEFAULT_FONT_SIZE
        self._dpi: int = 200
        self._zoom: float = 1.0
        self._base_pixmap: QPixmap | None = None

        # ── QScrollArea（仅水平滚动）──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # ── QLabel 承载长图 ──
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._scroll.setWidget(self._label)

        # ── 外层布局 ──
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._scroll)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._update_style()

    # ── 公共 API ─────────────────────────────────────────

    def setLatex(self, latex: str) -> None:
        self._latex = latex
        self._zoom = 1.0
        self._render()

    def setDarkTheme(self, enabled: bool) -> None:
        self._dark = enabled
        self._update_style()
        self._render()

    def clear(self) -> None:
        self._latex = ""
        self._base_pixmap = None
        self._zoom = 1.0
        self._label.clear()

    def setFontSize(self, size: int) -> None:
        self._font_size = max(8, min(48, size))
        self._render()

    def zoomIn(self) -> None:
        self._zoom = min(5.0, self._zoom * 1.2)
        self._apply()

    def zoomOut(self) -> None:
        self._zoom = max(0.3, self._zoom / 1.2)
        self._apply()

    def zoomReset(self) -> None:
        self._zoom = 1.0
        self._apply()

    # ── 交互 ─────────────────────────────────────────────

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoomIn()
            else:
                self.zoomOut()
            event.accept()
        else:
            super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self.zoomReset()
        event.accept()

    def sizeHint(self) -> QSize:
        if self._base_pixmap and not self._base_pixmap.isNull():
            h = self._base_pixmap.height() + 4  # padding
        else:
            h = 40
        return QSize(400, h)

    def minimumSizeHint(self) -> QSize:
        return QSize(100, 30)

    # ── 内部 ─────────────────────────────────────────────

    def _update_style(self) -> None:
        if self._dark:
            bg = "#1e293b"; border = "#475569"
        else:
            bg = "#fafbfc"; border = "#e2e8f0"
        self._label.setStyleSheet(
            f"QLabel{{background:{bg}; border:2px solid {border};"
            f" border-radius:10px; padding:4px 8px;}}"
        )
        self.setStyleSheet(f"QScrollArea{{background:{bg}; border:none;}}")

    def _render(self) -> None:
        """整段 LaTeX → 一张长图。"""
        if not self._latex:
            self._base_pixmap = None
            self._label.clear()
            return

        clean = _to_implicit_mul(self._latex)
        self._base_pixmap = _render_single(
            clean, font_size=self._font_size, dpi=self._dpi, dark=self._dark,
        )
        self._apply()

    def _apply(self) -> None:
        """应用缩放，设置 pixmap。"""
        if not self._base_pixmap or self._base_pixmap.isNull():
            self._label.setText("(render failed)")
            return

        pix = self._base_pixmap
        if abs(self._zoom - 1.0) > 0.01:
            zw = int(pix.width() * self._zoom)
            zh = int(pix.height() * self._zoom)
            pix = pix.scaled(zw, zh, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self._label.setPixmap(pix)
        self._label.resize(pix.size())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # 不重新渲染，只调整滚动区视图


# ═══════════════════════════════════════════════════════════════════
#  单行渲染（整段 LaTeX → 一张长图）
# ═══════════════════════════════════════════════════════════════════

def _sanitize(s: str) -> str:
    s = s.replace("\\displaystyle", "")
    s = re.sub(r"\\text\{([^}]*)\}", r"\\mathrm{\1}", s)
    s = re.sub(r"\\operatorname\{([^}]*)\}", r"\\mathrm{\1}", s)
    s = re.sub(r"\\\\\[\d+pt\]", r" ", s)
    s = s.replace("\\backslash", "").replace("\\$", "$")
    return s


def _render_single(
    latex: str,
    font_size: int = DEFAULT_FONT_SIZE,
    dpi: int = 200,
    dark: bool = False,
) -> QPixmap | None:
    """整段 LaTeX → 一张 QPixmap。"""
    if not latex or not latex.strip():
        return None
    try:
        import matplotlib as _mpl
        _mpl.use("agg")
        _mpl.rcParams["mathtext.fontset"] = "cm"
        import matplotlib.pyplot as _plt

        face = "#1e293b" if dark else "#fafbfc"
        text_color = "#e2e8f0" if dark else "#0f172a"

        safe = _sanitize(latex)
        fig = _plt.figure(figsize=(8, 0.45), dpi=dpi, facecolor=face)
        fig.text(0.02, 0.5, f"$ {safe} $",
                 fontsize=font_size, va="center", ha="left",
                 color=text_color)
        fig.canvas.draw()

        with BytesIO() as buf:
            fig.savefig(buf, format="png", dpi=dpi,
                        bbox_inches="tight", pad_inches=0.10,
                        transparent=False, facecolor=face, edgecolor="none")
            _plt.close(fig)
            pix = QPixmap()
            pix.loadFromData(buf.getvalue(), "PNG")
        return pix
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
#  ResultDialog
# ═══════════════════════════════════════════════════════════════════

class ResultDialog(QDialog):
    """计算结果弹窗。MathDisplay 渲染 + 步骤按钮（本地步骤 / AI 生成）。"""

    def __init__(self, title: str = "计算结果", parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(660, 520)
        self.setMinimumSize(460, 320)
        self._result_obj: Any = None
        self._context_expr = ""
        self._context_mode = ""

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        self._result_stack = QStackedWidget()
        self._result_stack.setMinimumHeight(60)

        self._math_display = MathDisplay()
        self._math_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._result_stack.addWidget(self._math_display)

        self._text_label = QLabel()
        self._text_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._text_label.setWordWrap(True)
        self._text_label.setMinimumHeight(60)
        self._text_label.setStyleSheet(
            "QLabel{background:#fafbfc; border:2px solid #e2e8f0;"
            " border-radius:10px; padding:20px; font-size:15px;}"
        )
        self._result_stack.addWidget(self._text_label)

        self._result_stack.setCurrentIndex(1)

        root.addWidget(self._result_stack, 1)

        btn_row = QHBoxLayout(); btn_row.setSpacing(12)

        self._step_btn = QPushButton("查看步骤 ▼")
        self._step_btn.setStyleSheet(
            "QPushButton{background:#f1f5f9; border:1px solid #cbd5e1;"
            " border-radius:6px; padding:8px 20px; font-size:13px; color:#334155}"
            "QPushButton:hover{background:#e2e8f0}"
        )
        self._step_btn.clicked.connect(self._on_step_clicked)
        btn_row.addWidget(self._step_btn); btn_row.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(
            "QPushButton{background:#3b82f6; color:#fff; border:none;"
            " border-radius:6px; padding:8px 24px; font-size:13px; font-weight:500}"
            "QPushButton:hover{background:#2563eb}"
        )
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        from MF_UI.components.mf_dialog import apply_dialog_title_bar
        apply_dialog_title_bar(self, title)

        from MF_UI.components.dialog_style import apply_shadow
        apply_shadow(self)

    def set_result(self, obj: Any) -> None:
        self._result_obj = obj
        if obj is None:
            self._show_text("no result", "#94a3b8"); return
        if not obj.ok:
            err = getattr(obj, "error", "")
            if _is_undefined(err):
                self._show_text("未定义", "#dc2626"); return
            self._show_text(f"error: {err}", "#dc2626"); return

        # 检查结果是否为未定义值
        result = getattr(obj, "result", None)
        if _is_undefined_value(result):
            self._show_text("未定义", "#dc2626"); return

        latex = self._obj_to_latex(obj).replace("*", "")
        if latex:
            self._result_stack.setCurrentIndex(0)
            self._math_display.setLatex(latex)
        else:
            self._show_text(self._format_plain(result), "#0f172a")

    def setDarkTheme(self, enabled: bool) -> None:
        self._math_display.setDarkTheme(enabled)

    def set_context(self, expr: str = "", mode: str = ""):
        """设置计算上下文（表达式 + 模式），供步骤查看器使用。"""
        self._context_expr = expr
        self._context_mode = mode

    def _on_step_clicked(self) -> None:
        """查看步骤 — 弹窗 StepViewer（优先本地 steps，其次 AI 生成）。"""
        obj = self._result_obj
        if obj is None:
            return

        from MF_UI.calc.step_viewer import StepViewer

        # 使用用户输入的原始表达式（不是计算结果）
        expr = str(self._context_expr) if self._context_expr else ""
        mode = self._context_mode or ""

        viewer = StepViewer(self, expr=expr, mode=mode)

        # 如果有本地步骤，传入
        local_steps = getattr(obj, "steps", None)
        if local_steps and len(local_steps) > 1:
            viewer.set_local_steps(local_steps)

        viewer.exec()

    def _obj_to_latex(self, obj: Any) -> str:
        r = getattr(obj, "result", None)
        if r is None: return ""
        d = getattr(obj, "data", None)
        if isinstance(d, dict) and d.get("latex"): return d["latex"]
        if hasattr(r, "result") and not callable(r.result): return self._obj_to_latex(r)
        return _result_to_latex(r)

    def _format_plain(self, result: Any) -> str:
        if result is None: return "no result"
        if isinstance(result, bool): return "True" if result else "False"
        if isinstance(result, (list, tuple)):
            return "empty" if not result else ", ".join(str(v) for v in result)
        if isinstance(result, dict): return "\n".join(f"{k} = {v}" for k, v in result.items())
        if isinstance(result, complex):
            rp, ip = result.real, result.imag
            if abs(ip) < 1e-12: return f"{rp:.6g}"
            if abs(rp) < 1e-12: return f"{ip:.6g}i"
            sign = "+" if ip >= 0 else "-"
            return f"{rp:.6g} {sign} {abs(ip):.6g}i"
        if isinstance(result, float): return f"{result:.6g}"
        return str(result)

    def _show_text(self, text: str, color: str) -> None:
        self._result_stack.setCurrentIndex(1)
        self._text_label.setText(text)
        self._text_label.setStyleSheet(
            f"QLabel{{background:#fafbfc; border:2px solid #e2e8f0;"
            f" border-radius:10px; padding:20px; font-size:15px; color:{color}}}"
        )


# ═══════════════════════════════════════════════════════════════════
#  结果 → LaTeX
# ═══════════════════════════════════════════════════════════════════

def _to_implicit_mul(latex: str) -> str:
    s = re.sub(r'(\d)\s+([a-zA-Z\\])', r'\1\2', latex)
    s = re.sub(r'\\left\(\s*', '(', s)
    s = re.sub(r'\s*\\right\)', ')', s)
    s = re.sub(r'\s*\\cdot\s*', '', s)
    s = s.replace('\\ ', ' ')
    return s


def _is_undefined(err: str) -> bool:
    """判断错误是否为未定义结果。"""
    if not err:
        return False
    keywords = ["undefined", "nan", "zoo", "oo", "inf", "singular",
                "not defined", "not finite", "indeterminate",
                "未定义", "无定义", "无穷", "发散", "不存在"]
    return any(k in err.lower() for k in keywords)


def _is_undefined_value(val: Any) -> bool:
    """判断值是否为未定义（NaN, Inf, zoo 等）。"""
    import math as _math
    import numpy as _np
    if val is None:
        return False
    # float NaN/Inf
    if isinstance(val, float):
        return _math.isnan(val) or _math.isinf(val)
    # complex NaN/Inf
    if isinstance(val, complex):
        return (_math.isnan(val.real) or _math.isinf(val.real) or
                _math.isnan(val.imag) or _math.isinf(val.imag))
    # sympy nan/zoo/oo
    try:
        import sympy as _sp
        if val in (_sp.nan, _sp.zoo, _sp.oo, -_sp.oo):
            return True
        if isinstance(val, _sp.Basic) and val.has(_sp.nan, _sp.zoo, _sp.oo):
            return True
    except Exception:
        pass
    # numpy nan/inf
    try:
        if isinstance(val, _np.ndarray):
            return bool(_np.any(_np.isnan(val)) or _np.any(_np.isinf(val)))
    except Exception:
        pass
    return False


def _result_to_latex(result: Any) -> str:
    if result is None: return ""
    if isinstance(result, bool):
        return r"\mathrm{True}" if result else r"\mathrm{False}"
    if isinstance(result, complex):
        rp, ip = result.real, result.imag
        if abs(ip) < 1e-12: return _format_float(rp)
        if abs(rp) < 1e-12: return _format_float(ip) + "i"
        sign = "+" if ip >= 0 else "-"
        return f"{_format_float(rp)} {sign} {_format_float(abs(ip))}i"
    if isinstance(result, (int, float)):
        return _format_float(result)
    if isinstance(result, dict):
        parts = [f"{k} = {_result_to_latex(v)}" for k, v in result.items()]
        return r" \\ ".join(parts)
    if isinstance(result, (list, tuple)):
        if not result: return r"\emptyset"
        if len(result) == 1: return _result_to_latex(result[0])
        return r",\ ".join(_result_to_latex(v) for v in result)
    s = str(result)
    if any(op in s for op in ("**", "*", "/", "sin", "cos", "exp", "log", "sqrt")):
        try:
            from MF_Mathematics.utils.translator import MathTranslator
            return _to_implicit_mul(MathTranslator.computer_to_human(s))
        except (ValueError, TypeError, ImportError) as e:
            import logging
            logging.debug(f"MathTranslator 转换失败: {e}")
    return r"\mathrm{" + s.replace("\\", "").replace("$", "").replace("_", r"\_") + "}"


def _format_float(val: float) -> str:
    if abs(val) < 1e-12: return "0"
    if abs(val - round(val)) < 1e-10: return str(int(round(val)))
    if abs(val) >= 1e6 or (abs(val) <= 1e-4 and val != 0):
        s = f"{val:.4e}"
        if "e" in s:
            mant, exp = s.split("e")
            return f"{mant} \\times 10^{{{int(exp)}}}"
        return s
    return f"{val:.6g}"


# ═══════════════════════════════════════════════════════════════════
#  independent test
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys as _s
    app = QApplication(_s.argv)

    w = QWidget()
    w.setWindowTitle("MathDisplay — long image + h-scroll, 10pt")
    w.resize(720, 400)
    w.setStyleSheet("QWidget{background:#f8fafc}")

    lay = QVBoxLayout(w); lay.setSpacing(14); lay.setContentsMargins(24, 24, 24, 24)

    lay.addWidget(QLabel("<b>MathDisplay — 整段长图 + 水平滚动</b>"))

    display = MathDisplay(w)
    display.setLatex(
        r"\frac{-b\pm\sqrt{b^{2}-4ac}}{2a},\;"
        r"\int_{0}^{\infty}e^{-x^{2}}dx=\frac{\sqrt{\pi}}{2},\;"
        r"\sin^{2}\theta+\cos^{2}\theta=1"
    )
    lay.addWidget(display, 1)

    row = QHBoxLayout(); row.setSpacing(10)
    inp = QLineEdit()
    inp.setPlaceholderText("LaTeX")
    inp.setStyleSheet("QLineEdit{border:1px solid #d1d5db;border-radius:6px;padding:8px 12px}")
    row.addWidget(inp, 1)
    def go(): display.setLatex(inp.text())
    btn = QPushButton("render"); btn.clicked.connect(go)
    btn.setStyleSheet("QPushButton{background:#3b82f6;color:#fff;border:none;"
                      "border-radius:6px;padding:8px 20px;font-weight:500}"
                      "QPushButton:hover{background:#2563eb}")
    row.addWidget(btn); lay.addLayout(row)

    tr = QHBoxLayout(); tr.setSpacing(10)
    dk = [False]
    def td():
        dk[0] = not dk[0]; display.setDarkTheme(dk[0])
        db.setText("light" if dk[0] else "dark")
    db = QPushButton("dark"); db.clicked.connect(td)
    db.setStyleSheet("QPushButton{background:#334155;color:#e2e8f0;border:none;"
                     "border-radius:6px;padding:8px 16px}")
    tr.addWidget(db)
    for label, fs in [("8pt", 8), ("10pt", 10), ("14pt", 14), ("18pt", 18)]:
        b = QPushButton(label); b.clicked.connect(lambda _, s=fs: display.setFontSize(s))
        tr.addWidget(b)
    tr.addStretch(); lay.addLayout(tr)

    inp.setText(r"\int_0^{\infty} e^{-x^2}\,dx = \frac{\sqrt{\pi}}{2}")
    inp.returnPressed.connect(go); go()

    w.show(); _s.exit(app.exec())
