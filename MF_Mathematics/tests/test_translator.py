"""Tests for MF_Mathematics.utils.translator — MathTranslator.

Coverage: algebraic, trigonometric, exponential, logarithmic, integral
(indefinite & definite), derivative, limit, summation, sqrt, implicit
multiplication, symbols, reverse translation, and validation.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.translator import MathTranslator


class TestHumanToComputer(unittest.TestCase):
    """human_to_computer — natural language → computer expression."""

    def test_algebraic_polynomial(self):
        """x^2 + 2x + 1 → x**2 + 2*x + 1"""
        result = MathTranslator.human_to_computer("x^2 + 2x + 1")
        self.assertEqual(result, "x**2 + 2*x + 1")

    def test_trig_sin_bare(self):
        """sin x → sin(x)"""
        result = MathTranslator.human_to_computer("sin x")
        self.assertEqual(result, "sin(x)")

    def test_exponential_e_power(self):
        """e^x → exp(x)"""
        result = MathTranslator.human_to_computer("e^x")
        self.assertEqual(result, "exp(x)")

    def test_logarithm_ln(self):
        """ln x → log(x)"""
        result = MathTranslator.human_to_computer("ln x")
        self.assertEqual(result, "log(x)")

    def test_indefinite_integral(self):
        """∫ sin(x) dx → integrate(sin(x), x)"""
        result = MathTranslator.human_to_computer("∫ sin(x) dx")
        self.assertEqual(result, "integrate(sin(x), x)")

    def test_definite_integral(self):
        """∫_0^1 x^2 dx → integrate(x**2, (x, 0, 1))"""
        result = MathTranslator.human_to_computer("∫_0^1 x^2 dx")
        self.assertEqual(result, "integrate(x**2, (x, 0, 1))")

    def test_derivative_d_dx(self):
        """d/dx sin(x) → diff(sin(x), x)"""
        result = MathTranslator.human_to_computer("d/dx sin(x)")
        self.assertEqual(result, "diff(sin(x), x)")

    def test_limit(self):
        """lim_{x→0} sin(x)/x → limit(sin(x)/x, x, 0)"""
        result = MathTranslator.human_to_computer("lim_{x→0} sin(x)/x")
        self.assertEqual(result, "limit(sin(x)/x, x, 0)")

    def test_summation(self):
        """∑_{n=1}^{∞} 1/n^2 → Sum(1/n**2, (n, 1, oo))"""
        result = MathTranslator.human_to_computer("∑_{n=1}^{∞} 1/n^2")
        self.assertEqual(result, "Sum(1/n**2, (n, 1, oo))")

    def test_sqrt(self):
        """√(x²+y²) → sqrt(x**2+y**2)"""
        result = MathTranslator.human_to_computer("√(x²+y²)")
        self.assertEqual(result, "sqrt(x**2+y**2)")

    def test_implicit_mul_parens(self):
        """(x+1)(x-1) → (x+1)*(x-1)"""
        result = MathTranslator.human_to_computer("(x+1)(x-1)")
        self.assertEqual(result, "(x+1)*(x-1)")

    def test_symbol_pi(self):
        """π → pi"""
        result = MathTranslator.human_to_computer("π")
        self.assertEqual(result, "pi")

    def test_symbol_infinity(self):
        """∞ → oo"""
        result = MathTranslator.human_to_computer("∞")
        self.assertEqual(result, "oo")

    def test_symbol_leq(self):
        """≤ → <="""
        result = MathTranslator.human_to_computer("≤")
        self.assertEqual(result, "<=")

    def test_implicit_mul_number_func(self):
        """2sin(x) → 2*sin(x)"""
        result = MathTranslator.human_to_computer("2sin(x)")
        self.assertEqual(result, "2*sin(x)")

    def test_implicit_mul_letters(self):
        """x y → x*y"""
        result = MathTranslator.human_to_computer("x y")
        self.assertEqual(result, "x*y")

    def test_arcsin_alias(self):
        """arcsin x → asin(x)"""
        result = MathTranslator.human_to_computer("arcsin x")
        self.assertEqual(result, "asin(x)")

    def test_absolute_value(self):
        """|x| → Abs(x)"""
        result = MathTranslator.human_to_computer("|x|")
        self.assertEqual(result, "Abs(x)")

    def test_partial_derivative(self):
        """∂f/∂x → diff(f, x)"""
        result = MathTranslator.human_to_computer("∂f/∂x")
        self.assertEqual(result, "diff(f, x)")


class TestComputerToHuman(unittest.TestCase):
    """computer_to_human — computer expression → LaTeX."""

    def test_polynomial_latex(self):
        """x**2 + 2*x + 1 → x^{2} + 2 x + 1"""
        result = MathTranslator.computer_to_human("x**2 + 2*x + 1")
        self.assertIn("x^{2}", result)
        self.assertIn("2 x", result)

    def test_sin_latex(self):
        """sin(x) → \\sin{\\left(x \\right)}"""
        result = MathTranslator.computer_to_human("sin(x)")
        self.assertIn("sin", result)


class TestValidate(unittest.TestCase):
    """validate — check sympy parseability."""

    def test_valid_expression(self):
        self.assertTrue(MathTranslator.validate("x**2 + 2*x + 1"))

    def test_invalid_double_plus(self):
        self.assertFalse(MathTranslator.validate("x++x"))

    def test_valid_sin(self):
        self.assertTrue(MathTranslator.validate("sin(x)"))


class TestTranslateWithInfo(unittest.TestCase):
    """translate_with_info — full pipeline structured output."""

    def test_returns_all_keys(self):
        info = MathTranslator.translate_with_info("x^2")
        for key in ("original", "computer", "latex", "valid"):
            self.assertIn(key, info)

    def test_valid_expression_info(self):
        info = MathTranslator.translate_with_info("x^2 + 2x + 1")
        self.assertTrue(info["valid"])
        self.assertEqual(info["computer"], "x**2 + 2*x + 1")

    def test_invalid_expression_info(self):
        info = MathTranslator.translate_with_info("x++x")
        self.assertFalse(info["valid"])


if __name__ == "__main__":
    unittest.main()
