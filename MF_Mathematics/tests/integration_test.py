"""Integration test suite for all modules."""
import sys, os
sys.path.insert(0, '.')
sys.path.insert(0, 'MF_UI')

# ── Qt 应用实例（PlotCanvas / FunctionBox / 对话框测试需要）──
_app = None
try:
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication(sys.argv)
except Exception:
    pass

passed = 0
failed = 0

def test(name):
    def decorator(fn):
        global passed, failed
        try:
            fn()
            passed += 1
            print(f"  [OK] {name}")
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {name}: {e}")
    return decorator

@test("Translator")
def _():
    from MF_UI.utils.translator import MathTranslator
    assert '**' in MathTranslator.human_to_computer('x^2')
    assert 'pi' in MathTranslator.human_to_computer('π')
    assert '*x' in MathTranslator.human_to_computer('2x')
    assert 'exp(' in MathTranslator.human_to_computer('e^x')
    assert ')*(' in MathTranslator.human_to_computer('(x+1)(x+2)')

@test("MathGuard L3")
def _():
    from MF_UI.utils.math_guard import ComplexityGuard, GuardLevel
    r = ComplexityGuard.check('1/0', '')
    assert r.level == GuardLevel.REJECT

@test("MathGuard L2 block")
def _():
    from MF_UI.utils.math_guard import ComplexityGuard, GuardLevel
    r = ComplexityGuard.check('1/(1+x**2026)', mode='不定积分')
    assert r.level == GuardLevel.BLOCK

@test("MathGuard L2 pass x^5")
def _():
    from MF_UI.utils.math_guard import ComplexityGuard, GuardLevel
    r = ComplexityGuard.check('1/(1+x**5)', mode='不定积分')
    assert r.level == GuardLevel.PASS

@test("MathGuard L1 warn")
def _():
    from MF_UI.utils.math_guard import ComplexityGuard, GuardLevel
    r = ComplexityGuard.check('+'.join(['x']*600), '')
    assert r.level == GuardLevel.WARN

@test("MathGuard normal pass")
def _():
    from MF_UI.utils.math_guard import ComplexityGuard, GuardLevel
    r = ComplexityGuard.check('x**2+2*x+1', '')
    assert r.level == GuardLevel.PASS

@test("LimitGuard sin(1/x)")
def _():
    from MF_UI.utils.math_guard import LimitGuard, GuardLevel
    r = LimitGuard.check('sin(1/x)', 'x', '0')
    assert r.level == GuardLevel.REJECT

@test("LimitGuard sin(x)/x pass")
def _():
    from MF_UI.utils.math_guard import LimitGuard, GuardLevel
    r = LimitGuard.check('sin(x)/x', 'x', '0')
    assert r.level == GuardLevel.PASS

@test("PlotCanvas")
def _():
    if _app is None:
        print("  [SKIP] QApplication not available")
        return
    from MF_UI.plot.basic.plot_canvas import PlotCanvas
    pc = PlotCanvas()
    assert hasattr(pc, 'add_function')
    assert hasattr(pc, 'update_axes')

@test("FunctionBox")
def _():
    if _app is None:
        print("  [SKIP] QApplication not available")
        return
    from MF_UI.plot.basic.function_box import FunctionBox
    fb = FunctionBox(index=1, color='#e74c3c')
    assert fb.is_visible

@test("NumericalEstimation Ramanujan")
def _():
    from MF_UI.calc.numerical_estimation import _ramanujan_pi
    pi_est = _ramanujan_pi(5)
    assert abs(pi_est - 3.141592653589793) < 1e-10

@test("NumericalEstimation Taylor e")
def _():
    from MF_UI.calc.numerical_estimation import _taylor_e
    e_est = _taylor_e(20)
    assert abs(e_est - 2.718281828) < 1e-5

@test("UserSystem register+login")
def _():
    if _app is None:
        print("  [SKIP] QApplication not available")
        return
    from MF_UI.auth.user_system import UserSystem
    UserSystem.init(os.getcwd())
    ok, msg = UserSystem.register('itest_user', 'pass1234')
    assert ok, f'register: {msg}'
    ok, msg = UserSystem.login('itest_user', 'pass1234')
    assert ok, f'login: {msg}'
    ok, msg = UserSystem.login('itest_user', 'wrong')
    assert not ok, 'wrong pw should fail'
    UserSystem.logout()

@test("CalcBlock implicit_mul")
def _():
    from MF_UI.calc.algebra.calc_block import _fix_implicit_mul
    r = _fix_implicit_mul('(x+1)(x+2)')
    assert ')*(' in r

@test("MathDisplay render")
def _():
    if _app is None:
        print("  [SKIP] QApplication not available")
        return
    from MF_UI.calc.math_display import _render_single
    pix = _render_single('x^2 + 2x + 1', font_size=10)
    assert pix is not None and not pix.isNull()

@test("ResultDialog")
def _():
    if _app is None:
        print("  [SKIP] QApplication not available")
        return
    from MF_UI.calc.math_display import ResultDialog
    from MF_Mathematics.core.math_object import MathObject
    rd = ResultDialog()
    obj = MathObject(result=42.0, steps=['a', 'b'])
    rd.set_result(obj)

print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
print(f"{'='*40}")
