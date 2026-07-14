"""test_number_theory.py — 数论子模块测试。

用法: python -m MF_Mathematics.tests.test_number_theory
"""

from __future__ import annotations

import math
import sys
import os

# Add parent directory for direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from MF_Mathematics.number_theory.core_algorithms import (
    gcd,
    extended_gcd,
    mod_inverse,
    mod_pow,
)
from MF_Mathematics.number_theory.arithmetic_functions import (
    euler_phi,
    divisor_count,
    divisor_sum,
    mobius,
    mobius_prefix,
)
from MF_Mathematics.number_theory.modular_arithmetic import (
    crt,
    primitive_root,
    discrete_log,
)
from MF_Mathematics.number_theory.prime_sieves import (
    eratosthenes,
    segmented_sieve,
    is_prime,
    prime_factors,
)
from MF_Mathematics.number_theory.continued_fractions import (
    continued_fraction,
    convergents,
    best_rational_approximation,
)
from MF_Mathematics.number_theory.zeta_interface import (
    euler_product,
    zeta_dirichlet_series,
    dirichlet_l_function,
    bernoulli_number,
    zeta_negative,
)


def test_all() -> bool:
    """运行全部数论子模块测试。"""
    all_pass = True

    print("=" * 60)
    print("Number Theory 子模块测试")
    print("=" * 60)

    # ── core_algorithms ──
    print("\n[core_algorithms]")
    checks = []

    r = gcd(48, 18)
    checks.append(("gcd(48,18)=6", r.result == 6, r.result))
    print(f"  gcd(48, 18) = {r.result}")

    r = extended_gcd(48, 18)
    checks.append(("extended_gcd(48,18)=(6,-1,3)", r.result == (6, -1, 3), r.result))
    print(f"  extended_gcd(48, 18) = {r.result}")

    r = mod_inverse(3, 7)
    checks.append(("mod_inverse(3,7)=5", r.result == 5, r.result))
    print(f"  mod_inverse(3, 7) = {r.result}")

    r = mod_pow(2, 10, 1000)
    checks.append(("mod_pow(2,10,1000)=24", r.result == 24, r.result))
    print(f"  mod_pow(2, 10, 1000) = {r.result}")

    r = gcd(0, 7)
    checks.append(("gcd(0,7)=7", r.result == 7, r.result))
    print(f"  gcd(0, 7) = {r.result}")

    for name, ok, val in checks:
        status = "PASS" if ok else f"FAIL (got {val})"
        if not ok:
            all_pass = False
        print(f"    [{status}] {name}")

    # ── arithmetic_functions ──
    print("\n[arithmetic_functions]")
    checks2 = []

    r = euler_phi(10)
    checks2.append(("euler_phi(10)=4", r.result == 4, r.result))
    print(f"  euler_phi(10) = {r.result}")

    r = euler_phi(1)
    checks2.append(("euler_phi(1)=1", r.result == 1, r.result))
    print(f"  euler_phi(1) = {r.result}")

    r = divisor_count(12)
    checks2.append(("divisor_count(12)=6", r.result == 6, r.result))
    print(f"  divisor_count(12) = {r.result}")

    r = divisor_sum(12)
    checks2.append(("divisor_sum(12)=28", r.result == 28, r.result))
    print(f"  divisor_sum(12) = {r.result}")

    r = mobius(6)
    checks2.append(("mobius(6)=1", r.result == 1, r.result))
    print(f"  mobius(6) = {r.result}")

    r = mobius(12)
    checks2.append(("mobius(12)=0", r.result == 0, r.result))
    print(f"  mobius(12) = {r.result}")

    r = mobius(30)
    checks2.append(("mobius(30)=-1", r.result == -1, r.result))
    print(f"  mobius(30) = {r.result}")

    r = mobius_prefix(10)
    checks2.append(("M(10)=-1", r.result == -1, r.result))
    print(f"  mobius_prefix(10) = {r.result}")

    for name, ok, val in checks2:
        status = "PASS" if ok else f"FAIL (got {val})"
        if not ok:
            all_pass = False
        print(f"    [{status}] {name}")

    # ── modular_arithmetic ──
    print("\n[modular_arithmetic]")
    checks3 = []

    r = crt([2, 3, 2], [3, 5, 7])
    checks3.append(("crt([2,3,2],[3,5,7])=23", r.result == 23, r.result))
    print(f"  crt([2,3,2], [3,5,7]) = {r.result}")

    r = primitive_root(7)
    checks3.append(("primitive_root(7)=3", r.result == 3, r.result))
    print(f"  primitive_root(7) = {r.result}")

    r = discrete_log(3, 2, 7)
    dlog_ok = r.result is not None and pow(3, r.result, 7) == 2
    checks3.append(("discrete_log(3,2,7)", dlog_ok, r.result))
    print(f"  discrete_log(3, 2, 7) = {r.result}")

    r = crt([0, 0, 0], [2, 3, 5])
    checks3.append(("crt([0,0,0],[2,3,5])=0", r.result == 0, r.result))
    print(f"  crt([0,0,0], [2,3,5]) = {r.result}")

    for name, ok, val in checks3:
        status = "PASS" if ok else f"FAIL (got {val})"
        if not ok:
            all_pass = False
        print(f"    [{status}] {name}")

    # ── prime_sieves ──
    print("\n[prime_sieves]")
    checks4 = []

    r = eratosthenes(20)
    expected = [2, 3, 5, 7, 11, 13, 17, 19]
    checks4.append(("eratosthenes(20)", r.result == expected, r.result))
    print(f"  eratosthenes(20) = {r.result}")

    r = is_prime(17)
    checks4.append(("is_prime(17)=True", r.result is True, r.result))
    print(f"  is_prime(17) = {r.result}")

    r = is_prime(100)
    checks4.append(("is_prime(100)=False", r.result is False, r.result))
    print(f"  is_prime(100) = {r.result}")

    r = is_prime(2**31 - 1)
    checks4.append(("is_prime(2^31-1)=True", r.result is True, r.result))
    print(f"  is_prime(2^31-1) = {r.result}")

    r = prime_factors(84)
    checks4.append(("prime_factors(84)={2:2,3:1,7:1}", r.result == {2: 2, 3: 1, 7: 1}, r.result))
    print(f"  prime_factors(84) = {r.result}")

    r = prime_factors(97)
    checks4.append(("prime_factors(97)={97:1}", r.result == {97: 1}, r.result))
    print(f"  prime_factors(97) = {r.result}")

    r = segmented_sieve(100)
    checks4.append(("segmented_sieve(100): 25 primes", len(r.result) == 25, len(r.result)))
    print(f"  segmented_sieve(100): {len(r.result)} primes")

    for name, ok, val in checks4:
        status = "PASS" if ok else f"FAIL (got {val})"
        if not ok:
            all_pass = False
        print(f"    [{status}] {name}")

    # ── continued_fractions ──
    print("\n[continued_fractions]")
    checks5 = []

    r = continued_fraction(math.pi, 6)
    checks5.append(("continued_fraction(π)", r.result[:5] == [3, 7, 15, 1, 292], r.result[:6]))
    print(f"  continued_fraction(π, 6) = {r.result[:6]}")

    r = convergents([3, 7, 15, 1])
    conv = r.result
    checks5.append(("convergents C₀=3/1", conv[0][0] == 3 and conv[0][1] == 1, (conv[0][0], conv[0][1])))
    checks5.append(("convergents C₁=22/7", conv[1][0] == 22 and conv[1][1] == 7, (conv[1][0], conv[1][1])))
    checks5.append(("convergents C₃=355/113", conv[3][0] == 355 and conv[3][1] == 113, (conv[3][0], conv[3][1])))
    print(f"  convergents = {[(p, q) for p, q, _ in conv]}")

    r = best_rational_approximation(math.pi, 1000)
    p, q, _ = r.result
    checks5.append(("best_rational_approx(π,1000)=355/113", p == 355 and q == 113, (p, q)))
    print(f"  best_rational_approximation(π, 1000) = {p}/{q}")

    r = continued_fraction(math.sqrt(2), 8)
    checks5.append(("continued_fraction(√2)", r.result[:4] == [1, 2, 2, 2], r.result[:4]))
    print(f"  continued_fraction(√2, 8) = {r.result[:8]}")

    for name, ok, val in checks5:
        status = "PASS" if ok else f"FAIL (got {val})"
        if not ok:
            all_pass = False
        print(f"    [{status}] {name}")

    # ── zeta_interface ──
    print("\n[zeta_interface]")
    checks6 = []

    r = euler_product(2, 100)
    expected_zeta2 = math.pi**2 / 6.0
    checks6.append(("euler_product(2,100)≈π²/6", abs(r.result - expected_zeta2) < 0.05, r.result))
    print(f"  euler_product(2, 100) = {r.result:.6f} (π²/6 = {expected_zeta2:.6f})")

    r = zeta_dirichlet_series(2, 10000)
    checks6.append(("zeta_dirichlet_series(2,10000)≈π²/6", abs(r.result - expected_zeta2) < 0.01, r.result))
    print(f"  zeta_dirichlet_series(2, 10000) = {r.result:.6f}")

    r = dirichlet_l_function(1, n_terms=10000)
    expected_l = math.pi / 4.0
    checks6.append(("dirichlet_l_function(1,10000)≈π/4", abs(r.result - expected_l) < 0.01, r.result))
    print(f"  dirichlet_l_function(1, 10000) = {r.result:.6f} (π/4 = {expected_l:.6f})")

    r = bernoulli_number(2)
    checks6.append(("B₂=1/6", abs(float(r.result) - 1.0/6.0) < 1e-10, float(r.result)))
    print(f"  bernoulli_number(2) = {r.result}")

    r = bernoulli_number(4)
    checks6.append(("B₄=-1/30", abs(float(r.result) - (-1.0/30.0)) < 1e-10, float(r.result)))
    print(f"  bernoulli_number(4) = {r.result}")

    r = zeta_negative(1)
    checks6.append(("ζ(-1)=-1/12", abs(float(r.result) - (-1.0/12.0)) < 1e-10, float(r.result)))
    print(f"  zeta_negative(1) = {r.result}")

    r = zeta_negative(3)
    checks6.append(("ζ(-3)=1/120", abs(float(r.result) - 1.0/120.0) < 1e-10, float(r.result)))
    print(f"  zeta_negative(3) = {r.result}")

    for name, ok, val in checks6:
        status = "PASS" if ok else f"FAIL (got {val})"
        if not ok:
            all_pass = False
        print(f"    [{status}] {name}")

    # ── Summary ──
    print("\n" + "=" * 60)
    print(f"Number Theory: {'ALL PASSED' if all_pass else 'SOME FAILED'}")
    print("=" * 60)
    return all_pass


if __name__ == "__main__":
    success = test_all()
    sys.exit(0 if success else 1)
