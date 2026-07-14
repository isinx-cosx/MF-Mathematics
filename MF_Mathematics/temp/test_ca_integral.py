import sys, traceback
sys.path.insert(0, r'C:\Users\fsafsafsa\Desktop\Multifunctional-Mathematics')

try:
    from MF_Mathematics.complex_analysis.complex_integral import self_test
    self_test()
except Exception:
    traceback.print_exc()
