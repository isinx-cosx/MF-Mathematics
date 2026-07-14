"""test_runner.py — 便捷测试入口。

用法: python -m MF_Mathematics.tests.test_runner
"""

if __name__ == "__main__":
    from .test_algebra import test_all as test_algebra_all
    from .test_calculus import test_all as test_calculus_all
    from .test_linear_algebra import test_all as test_linear_algebra_all
    from .test_probability import test_all as test_probability_all
    from .test_real_analysis import test_all as test_real_analysis_all
    from .test_complex_analysis import test_all as test_complex_analysis_all
    from .test_numerical import test_all as test_numerical_all
    from .test_functional_analysis import test_all as test_functional_analysis_all
    from .test_harmonic_analysis import test_all as test_harmonic_analysis_all
    from .test_measure_theory import test_all as test_measure_theory_all
    from .test_algebraic_topology import test_all as test_algebraic_topology_all
    from .test_number_theory import test_all as test_number_theory_all

    algebra_ok = test_algebra_all()
    print()
    calculus_ok = test_calculus_all()
    print()
    linear_algebra_ok = test_linear_algebra_all()
    print()
    probability_ok = test_probability_all()
    print()
    real_analysis_ok = test_real_analysis_all()
    print()
    complex_analysis_ok = test_complex_analysis_all()
    print()
    numerical_ok = test_numerical_all()
    print()
    functional_analysis_ok = test_functional_analysis_all()
    print()
    harmonic_analysis_ok = test_harmonic_analysis_all()
    print()
    measure_theory_ok = test_measure_theory_all()
    print()
    algebraic_topology_ok = test_algebraic_topology_all()
    print()
    number_theory_ok = test_number_theory_all()

    print("\n" + "=" * 60)
    print(
        f"全量结果: Algebra {'PASSED' if algebra_ok else 'FAILED'}, "
        f"Calculus {'PASSED' if calculus_ok else 'FAILED'}, "
        f"Linear Algebra {'PASSED' if linear_algebra_ok else 'FAILED'}, "
        f"Probability {'PASSED' if probability_ok else 'FAILED'}, "
        f"Real Analysis {'PASSED' if real_analysis_ok else 'FAILED'}, "
        f"Complex Analysis {'PASSED' if complex_analysis_ok else 'FAILED'}, "
        f"Numerical {'PASSED' if numerical_ok else 'FAILED'}, "
        f"Functional Analysis {'PASSED' if functional_analysis_ok else 'FAILED'}, "
        f"Harmonic Analysis {'PASSED' if harmonic_analysis_ok else 'FAILED'}, "
        f"Measure Theory {'PASSED' if measure_theory_ok else 'FAILED'}, "
        f"Algebraic Topology {'PASSED' if algebraic_topology_ok else 'FAILED'}, "
        f"Number Theory {'PASSED' if number_theory_ok else 'FAILED'}"
    )
    print("=" * 60)
