"""MathTranslator: Natural Math Language ↔ Computer Language Bidirectional Translator.

Translates between human-readable math notation and computer-evaluable expressions
using regex-based rules and sympy.latex for reverse translation.
"""

import re
from typing import Any

import sympy


class MathTranslator:
    """Bidirectional translator for mathematical expressions.

    All methods are @staticmethod — the class holds no state.
    """

    # ── Symbol replacement table (order-sensitive) ────────────────────────────
    _SYMBOL_MAP: list[tuple[str, str]] = [
        ("π", "pi"),
        ("∞", "oo"),
        ("×", "*"),
        ("÷", "/"),
        ("²", "**2"),
        ("³", "**3"),
        ("≤", "<="),
        ("≥", ">="),
        ("≠", "!="),
        ("₀", "0"), ("₁", "1"), ("₂", "2"), ("₃", "3"), ("₄", "4"),
        ("₅", "5"), ("₆", "6"), ("₇", "7"), ("₈", "8"), ("₉", "9"),
        ("→", "->"),
        ("∂", "d"),
        ("^", "**"),   # generic superscript (after templates consume their ^)
    ]

    # ── Function alias map ────────────────────────────────────────────────────
    _FUNC_ALIAS: list[tuple[str, str]] = [
        ("ln", "log"),
        ("lg", "log10"),
        ("arcsin", "asin"),
        ("arccos", "acos"),
        ("arctan", "atan"),
    ]

    _KNOWN_FUNCS: set[str] = {
        "sin", "cos", "tan", "cot", "sec", "csc",
        "sinh", "cosh", "tanh", "coth", "sech", "csch",
        "arcsin", "arccos", "arctan",
        "asin", "acos", "atan",
        "ln", "lg", "log", "log10",
        "sqrt", "Abs", "exp",
        "integrate", "diff", "limit", "Sum",
    }

    # ── Structural / calculus templates (definite before indefinite!) ─────────
    _CALC_REPLACE: list[tuple[str, str]] = [
        # ∫_a^b expression dx  (definite — must come before indefinite)
        (r"∫_(\{[^}]+\}|[^ ^\n]+)\^(\{[^}]+\}|[^ ^\n]+)\s+(.+?)\s*d([a-zA-Z])",
         r"integrate(\3, (\4, \1, \2))"),
        # ∫ expression dx  (indefinite — only when no _ after ∫)
        (r"∫(?!_)\s*(.+?)\s*d([a-zA-Z])", r"integrate(\1, \2)"),
        # d/dx expression
        (r"d/d([a-zA-Z])\s+(.+)", r"diff(\2, \1)"),
        # ∂f/∂x
        (r"∂(\w+)/∂(\w+)", r"diff(\1, \2)"),
        # lim_{x→a} expression
        (r"lim_\{(\w+)\s*→\s*([^}]+)\}\s+(.+)", r"limit(\3, \1, \2)"),
        # ∑_{n=m}^{N} expression
        (r"∑_\{(\w+)=([^}]+?)\}\^\{([^}]+?)\}\s+(.+)",
         r"Sum(\4, (\1, \2, \3))"),
        # √(expression) → sqrt(expression)
        (r"√\((.+?)\)", r"sqrt(\1)"),
        # |expression| → Abs(expression)
        (r"\|([^|]+)\|", r"Abs(\1)"),
    ]

    # ── Implicit multiplication (applied AFTER normalise_calls) ───────────────
    _IMPLICIT_MUL: list[tuple[str, str]] = [
        # number immediately before letter: 2x → 2*x
        (r"(\d)\s*([a-zA-Zα-ω])", r"\1*\2"),
        # closing paren before opening: )( → )*(
        (r"\)\s*\(", r")*("),
        # closing paren before letter: )x → )*x
        (r"\)\s*([a-zA-Zα-ω])", r")*\1"),
        # number before opening paren: 2( → 2*(
        (r"(\d)\s*\(", r"\1*("),
        # two single-letter variables separated by space: x y → x*y
        #   (word-boundary guard stops "sin(x)" from being split as "sin( x )")
        (r"([a-zA-Zα-ω])\s+([a-zA-Zα-ω])\b", r"\1*\2"),
    ]

    # ═══════════════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def human_to_computer(expr: str) -> str:
        """Translate human-readable math expression → computer-evaluable string."""
        s = expr.strip()

        # --- phase 1: structural / calculus templates ---
        for pattern, replacement in MathTranslator._CALC_REPLACE:
            s, n = re.subn(pattern, replacement, s, flags=re.DOTALL)
            if n > 0:
                s = s.replace("{", "").replace("}", "")

        # --- phase 2: symbol replacement ---
        for sym, repl in MathTranslator._SYMBOL_MAP:
            s = s.replace(sym, repl)

        # --- phase 3: function aliases (word boundary) ---
        for alias, canonical in MathTranslator._FUNC_ALIAS:
            s = re.sub(rf"\b{re.escape(alias)}\b", canonical, s)

        # --- phase 4: normalise bare function calls BEFORE implicit mul ---
        s = MathTranslator._normalise_calls(s)

        # --- phase 5: implicit multiplication ---
        for pattern, replacement in MathTranslator._IMPLICIT_MUL:
            s = re.sub(pattern, replacement, s)

        # --- phase 6: clean-ups ---
        s = re.sub(r"\*\*\s*\*", "**", s)     # ** * → **
        s = re.sub(r"\s+", " ", s).strip()

        return s

    @staticmethod
    def computer_to_human(expr: str) -> str:
        """Translate computer expression → LaTeX via sympy."""
        parsed = sympy.sympify(expr)
        return sympy.latex(parsed)

    @staticmethod
    def validate(expr: str) -> bool:
        """Check whether *expr* is parseable by sympy.sympify.

        Additional check: reject expressions containing consecutive operators
        (``++``, ``--``, ``** *`` etc.) that sympy silently accepts but are
        semantically invalid for our use-case.
        """
        # Reject C-style increment/decrement operators (not valid math)
        if re.search(r"\+\+|--", expr):
            return False
        try:
            sympy.sympify(expr)
            return True
        except (sympy.SympifyError, TypeError, ValueError):
            return False

    @staticmethod
    def translate_with_info(expr: str) -> dict[str, Any]:
        """Full pipeline: translate → validate → LaTeX → structured result."""
        info: dict[str, Any] = {"original": expr}
        try:
            comp = MathTranslator.human_to_computer(expr)
            info["computer"] = comp
        except Exception as e:
            info["computer"] = f"[translation error: {e}]"
            info["valid"] = False
            info["latex"] = ""
            return info

        info["valid"] = MathTranslator.validate(comp)
        try:
            info["latex"] = MathTranslator.computer_to_human(comp)
        except Exception:
            info["latex"] = "[latex generation failed]"

        return info

    # ═══════════════════════════════════════════════════════════════════════════
    # Internal helpers
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _normalise_calls(s: str) -> str:
        """Convert bare function references to canonical parenthesised form."""
        # e^x → exp(x)  (not part of a word)
        s = re.sub(r"(?<![a-zA-Z])e\*\*(\S+)", r"exp(\1)", s)

        for fname in sorted(MathTranslator._KNOWN_FUNCS, key=len, reverse=True):
            # "func single_token" → "func(single_token)"
            s = re.sub(
                rf"(?<![a-zA-Z])({re.escape(fname)})\s+([a-zA-Z0-9_]+)(?!\()",
                rf"\1(\2)", s,
            )
            # "func ( ... )" → "func( ... )"
            s = re.sub(
                rf"(?<![a-zA-Z])({re.escape(fname)})\s+(\()",
                rf"\1\2", s,
            )
        return s
