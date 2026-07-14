# -*- coding: utf-8 -*-
"""表达式翻译器 — 自然数学语言 → SymPy 兼容表达式。

处理规则（按顺序）:
  1. Unicode 符号替换:  π→pi, ∞→oo, ×→*, ÷→/, ≤→<=, ≥→>=, ≠→!=
  2. 上下标数字: ²→**2, ₁→1
  3. 幂运算: ^ → **
  4. 函数规范化: sin x → sin(x), e^x → exp(x)
  5. 隐式乘法: 2x→2*x, (x+1)(x+2)→(x+1)*(x+2), x y→x*y
  6. 微积分模板: ∫, d/dx, lim, Σ → integrate/diff/limit/Sum
"""

from __future__ import annotations

import re
import json
import os


class MathTranslator:
    """双向数学表达式翻译器（全部静态方法）。"""

    # ── Unicode 符号 → SymPy ──────────────────────────────────────
    _SYMBOL_MAP: list[tuple[str, str]] = [
        ("π", "pi"), ("∞", "oo"), ("×", "*"), ("÷", "/"),
        ("²", "**2"), ("³", "**3"),
        ("≤", "<="), ("≥", ">="), ("≠", "!="),
        ("₀", "0"), ("₁", "1"), ("₂", "2"), ("₃", "3"),
        ("₄", "4"), ("₅", "5"), ("₆", "6"), ("₇", "7"),
        ("₈", "8"), ("₉", "9"), ("→", "->"), ("∂", "d"),
    ]

    # ── 函数别名 ──────────────────────────────────────────────────
    _FUNC_ALIAS: list[tuple[str, str]] = [
        ("ln", "log"), ("lg", "log10"),
        ("arcsin", "asin"), ("arccos", "acos"), ("arctan", "atan"),
    ]

    _KNOWN_FUNCS: set[str] = {
        "sin", "cos", "tan", "cot", "sec", "csc",
        "sinh", "cosh", "tanh", "coth",
        "arcsin", "arccos", "arctan", "asin", "acos", "atan",
        "ln", "lg", "log", "log10", "sqrt", "Abs", "exp",
        "integrate", "diff", "limit", "Sum",
    }

    # ── 微积分模板（定积分必须先于不定积分）──────────────
    _CALC_REPLACE: list[tuple[str, str]] = [
        (r"∫_(\{[^}]+\}|[^ ^\n]+)\^(\{[^}]+\}|[^ ^\n]+)\s+(.+?)\s*d([a-zA-Z])",
         r"integrate(\3, (\4, \1, \2))"),
        (r"∫(?!_)\s*(.+?)\s*d([a-zA-Z])", r"integrate(\1, \2)"),
        (r"d/d([a-zA-Z])\s+(.+)", r"diff(\2, \1)"),
        (r"∂(\w+)/∂(\w+)", r"diff(\1, \2)"),
        (r"lim_\{(\w+)\s*→\s*([^}]+)\}\s+(.+)", r"limit(\3, \1, \2)"),
        (r"∑_\{(\w+)=([^}]+?)\}\^\{([^}]+?)\}\s+(.+)", r"Sum(\4, (\1, \2, \3))"),
        (r"√\((.+?)\)", r"sqrt(\1)"),
        (r"\|([^|]+)\|", r"Abs(\1)"),
        # 导数记号: func'(var) → Derivative(func(var), var)
        (r"([a-zA-Z]\w*)\s*'\s*\(\s*([a-zA-Z])\s*\)",
         r"Derivative(\1(\2), \2)"),
        # 导数记号: (expr)' → Derivative(expr, x)
        (r"\((.+)\)\s*'",
         r"Derivative(\1, x)"),
    ]

    # ── 隐式乘法 ──────────────────────────────────────────────────
    _IMPLICIT_MUL: list[tuple[str, str]] = [
        (r"(\d)\s*([a-zA-Zα-ω])", r"\1*\2"),       # 2x → 2*x
        (r"\)\s*\(", r")*("),                        # )( → )*(
        (r"\)\s*([a-zA-Zα-ω])", r")*\1"),            # )x → )*x
        (r"(\d)\s*\(", r"\1*("),                      # 2( → 2*(
        (r"([a-zA-Zα-ω])\s+([a-zA-Zα-ω])\b", r"\1*\2"),  # x y → x*y
    ]

    # ═══════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def human_to_computer(expr: str) -> str:
        """自然数学表达式 → SymPy 可解析表达式。"""
        s = expr.strip()

        # Phase 1: 微积分模板
        for pattern, repl in MathTranslator._CALC_REPLACE:
            s, n = re.subn(pattern, repl, s, flags=re.DOTALL)
            if n > 0:
                s = s.replace("{", "").replace("}", "")

        # Phase 2: Unicode 符号
        for sym, repl in MathTranslator._SYMBOL_MAP:
            s = s.replace(sym, repl)

        # Phase 3: 函数别名
        for alias, canonical in MathTranslator._FUNC_ALIAS:
            s = re.sub(rf"\b{re.escape(alias)}\b", canonical, s)

        # Phase 4: ^ → **（必须在函数规范化之前）
        s = s.replace("^", "**")

        # Phase 4b: e^ → exp(  (e^x → exp(x), e^(...) → exp(...))
        s = re.sub(r"\be\*\*(\w+)", r"exp(\1)", s)
        s = re.sub(r"\be\*\*\(", "exp(", s)

        # Phase 4c: 裸函数调用（func+字母/数字 → func(字母/数字)）
        F = "sin|cos|tan|cot|sec|csc|sinh|cosh|tanh|log|ln|sqrt|exp|abs|asin|acos|atan"
        s = re.sub(rf"\b({F})(\d+)([a-zA-Z])", r"\1(\2*\3)", s)
        s = re.sub(rf"\b({F})([a-zA-Z])", r"\1(\2)", s)
        s = re.sub(rf"\b({F})(\d+)", r"\1(\2)", s)

        # Phase 5: 函数调用规范化（sin x → sin(x), e**x → exp(x)）
        s = MathTranslator._normalise_calls(s)

        # Phase 6: 隐式乘法
        for pattern, repl in MathTranslator._IMPLICIT_MUL:
            s = re.sub(pattern, repl, s)

        # Phase 7: 清理 ** * → **
        s = re.sub(r"\*\*\s*\*", "**", s)
        s = re.sub(r"\s+", " ", s).strip()

        return s

    @staticmethod
    def computer_to_human(expr: str) -> str:
        """SymPy 表达式 → LaTeX。"""
        import sympy
        parsed = sympy.sympify(expr)
        return sympy.latex(parsed)

    @staticmethod
    def validate(expr: str) -> bool:
        """检查表达式是否可被 SymPy 解析。"""
        if re.search(r"\+\+|--", expr):
            return False
        try:
            import sympy
            sympy.sympify(expr)
            return True
        except Exception:
            return False

    # ═══════════════════════════════════════════════════════════════
    # Internal
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _normalise_calls(s: str) -> str:
        """e^x → exp(x); sin x → sin(x); sin (x) → sin(x)。"""
        s = re.sub(
            r"(?<![a-zA-Z])e\*\*([a-zA-Z0-9_.]*(?:\([^)]*\))?)",
            lambda m: f"exp({m.group(1)[1:-1]})" if m.group(1).startswith("(") else f"exp({m.group(1)})",
            s,
        )
        for fname in sorted(MathTranslator._KNOWN_FUNCS, key=len, reverse=True):
            s = re.sub(
                rf"(?<![a-zA-Z])({re.escape(fname)})\s+([a-zA-Z0-9_]+)(?!\()",
                rf"\1(\2)", s,
            )
            s = re.sub(
                rf"(?<![a-zA-Z])({re.escape(fname)})\s+(\()",
                rf"\1\2", s,
            )
        return s
