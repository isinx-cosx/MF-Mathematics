import sys, traceback
sys.path.insert(0, r'C:\Users\fsafsafsa\Desktop\Multifunctional-Mathematics')

modules = [
    ("residue", "MF_Mathematics.complex_analysis.residue"),
    ("conformal", "MF_Mathematics.complex_analysis.conformal"),
    ("zeta", "MF_Mathematics.complex_analysis.zeta"),
]

all_ok = True
for name, modpath in modules:
    print(f"\n=== Running {name} self_test ===")
    try:
        mod = __import__(modpath, fromlist=['self_test'])
        mod.self_test()
        print(f"=== {name} self_test: ALL PASSED ===")
    except Exception:
        traceback.print_exc()
        all_ok = False
        print(f"=== {name} self_test: FAILED ===")

print(f"\n{'ALL TESTS PASSED' if all_ok else 'SOME TESTS FAILED'}")
