"""概率论与数理统计子模块测试。"""

from __future__ import annotations

import sys
import os

# 确保可以导入 MF_Mathematics
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def test_probability_space() -> bool:
    """测试 probability_space 模块。"""
    from MF_Mathematics.probability.probability_space import (
        conditional_probability,
        is_independent,
        total_probability,
        bayes_theorem,
    )

    ok = True

    # 条件概率
    r = conditional_probability("rain", "cloud", {"rain_and_cloud": 0.3, "cloud": 0.5})
    if not r.ok or abs(r.result - 0.6) > 0.01:
        print(f"  FAIL conditional_probability: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS conditional_probability: {r.result}")

    # 独立性（独立）
    r = is_independent("A", "B", {"A": 0.5, "B": 0.4, "A_and_B": 0.2})
    if not r.ok or r.result is not True:
        print(f"  FAIL is_independent (independent): {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS is_independent (independent)")

    # 独立性（不独立）
    r = is_independent("A", "B", {"A": 0.5, "B": 0.4, "A_and_B": 0.1})
    if not r.ok or r.result is not False:
        print(f"  FAIL is_independent (dependent): {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS is_independent (dependent)")

    # 全概率
    r = total_probability({"B1": 0.6, "B2": 0.4}, {"A|B1": 0.8, "A|B2": 0.3}, "A")
    if not r.ok or abs(r.result - 0.60) > 0.01:
        print(f"  FAIL total_probability: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS total_probability: {r.result}")

    # 贝叶斯
    r = bayes_theorem({"B1": 0.6, "B2": 0.4}, {"A|B1": 0.8, "A|B2": 0.3}, "A")
    if not r.ok or abs(r.result["B1"] - 0.8) > 0.01:
        print(f"  FAIL bayes_theorem: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS bayes_theorem: {r.result}")

    return ok


def test_random_variable() -> bool:
    """测试 random_variable 模块。"""
    from MF_Mathematics.probability.random_variable import (
        distribution_function,
        pmf,
        pdf,
        expectation,
    )

    ok = True

    # 经验分布函数
    r = distribution_function([1, 3, 5, 7, 9], x=5)
    if not r.ok or abs(r.result - 0.6) > 0.01:
        print(f"  FAIL distribution_function: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS distribution_function: F(5)={r.result}")

    # PMF
    r = pmf(["H", "T"], [0.5, 0.5])
    if not r.ok or r.result["H"] != 0.5:
        print(f"  FAIL pmf: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS pmf: {r.result}")

    # PDF
    r = pdf("exp(-x)", "x")
    if not r.ok:
        print(f"  FAIL pdf: {r.error}")
        ok = False
    else:
        print(f"  PASS pdf")

    # 离散型期望
    r = expectation("x", var="x", pmf_data={"values": [0, 1], "probs": [0.5, 0.5]})
    if not r.ok or abs(r.result - 0.5) > 0.01:
        print(f"  FAIL expectation discrete: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS expectation (discrete): {r.result}")

    return ok


def test_expectations() -> bool:
    """测试 expectations 模块。"""
    from MF_Mathematics.probability.expectations import (
        expectation,
        variance,
        covariance,
        correlation_coefficient,
    )

    ok = True

    # 期望
    r = expectation(data=[1, 2, 3, 4, 5])
    if not r.ok or abs(r.result - 3.0) > 0.01:
        print(f"  FAIL expectation: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS expectation: {r.result}")

    # 方差
    r = variance(data=[1, 2, 3, 4, 5])
    if not r.ok or abs(r.result - 2.5) > 0.01:
        print(f"  FAIL variance: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS variance: {r.result}")

    # 协方差
    r = covariance([1, 2, 3], [2, 4, 6])
    if not r.ok or r.result <= 0:
        print(f"  FAIL covariance: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS covariance: {r.result:.4f}")

    # 相关系数
    r = correlation_coefficient([1, 2, 3], [2, 4, 6])
    if not r.ok or abs(r.result - 1.0) > 0.01:
        print(f"  FAIL correlation_coefficient: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS correlation_coefficient: {r.result}")

    return ok


def test_distributions() -> bool:
    """测试 distributions 模块。"""
    from MF_Mathematics.probability.distributions import (
        bernoulli,
        binomial,
        poisson,
        uniform,
        exponential,
        normal,
    )

    ok = True

    # Bernoulli
    r = bernoulli(0.3)
    if not r.ok or abs(r.result["mean"] - 0.3) > 0.01:
        print(f"  FAIL bernoulli: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS bernoulli")

    # Binomial
    r = binomial(10, 0.5)
    if not r.ok or abs(r.result["mean"] - 5.0) > 0.01:
        print(f"  FAIL binomial: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS binomial: E={r.result['mean']}")

    # Poisson
    r = poisson(3.0)
    if not r.ok:
        print(f"  FAIL poisson: {r.error}")
        ok = False
    else:
        print(f"  PASS poisson")

    # Uniform
    r = uniform(0, 10)
    if not r.ok or abs(r.result["mean"] - 5.0) > 0.01:
        print(f"  FAIL uniform: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS uniform")

    # Exponential
    r = exponential(2.0)
    if not r.ok or abs(r.result["mean"] - 0.5) > 0.01:
        print(f"  FAIL exponential: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS exponential")

    # Normal
    r = normal(0, 1)
    if not r.ok or r.result["mean"] != 0 or r.result["variance"] != 1:
        print(f"  FAIL normal: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS normal: N(0,1)")

    return ok


def test_limit_theorems() -> bool:
    """测试 limit_theorems 模块。"""
    from MF_Mathematics.probability.limits_theorems import (
        law_of_large_numbers,
        central_limit_theorem,
    )
    import numpy as np

    ok = True

    # LLN
    r = law_of_large_numbers(sample_mean=50.2, true_mean=50.0, n=100)
    if not r.ok:
        print(f"  FAIL LLN: {r.error}")
        ok = False
    else:
        print(f"  PASS LLN: deviation={r.result['deviation']:.4f}")

    # CLT
    rng = np.random.default_rng(42)
    sample = rng.normal(50, 10, 100).tolist()
    r = central_limit_theorem(sample, mu=50, sigma=10, n=100)
    if not r.ok:
        print(f"  FAIL CLT: {r.error}")
        ok = False
    else:
        print(f"  PASS CLT: Z={r.result['Z']:.4f}")

    return ok


def test_statistics() -> bool:
    """测试 statistics 模块。"""
    from MF_Mathematics.probability.statistics import (
        sample_mean,
        sample_variance,
        moment_estimate,
        mle,
        confidence_interval,
    )

    ok = True

    r = sample_mean([1, 2, 3, 4, 5])
    if not r.ok or abs(r.result - 3.0) > 0.01:
        print(f"  FAIL sample_mean: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS sample_mean")

    r = sample_variance([1, 2, 3, 4, 5])
    if not r.ok or abs(r.result - 2.5) > 0.01:
        print(f"  FAIL sample_variance: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS sample_variance")

    r = moment_estimate([1, 2, 3, 4, 5], "normal")
    if not r.ok:
        print(f"  FAIL moment_estimate: {r.error}")
        ok = False
    else:
        print(f"  PASS moment_estimate")

    r = mle([1, 2, 3, 4, 5], "normal")
    if not r.ok:
        print(f"  FAIL mle: {r.error}")
        ok = False
    else:
        print(f"  PASS mle")

    r = confidence_interval([1, 2, 3, 4, 5], 0.95)
    if not r.ok or not (r.result["lower"] < 3.0 < r.result["upper"]):
        print(f"  FAIL confidence_interval: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS confidence_interval: [{r.result['lower']:.3f}, {r.result['upper']:.3f}]")

    return ok


def test_hypothesis_test() -> bool:
    """测试 hypothesis_test 模块。"""
    from MF_Mathematics.probability.hypothesis_test import (
        z_test,
        t_test,
        chi_square_test,
        p_value,
    )

    ok = True

    r = z_test(sample_mean=2.5, mu0=3, sigma=1.5, n=100, alpha=0.05)
    if not r.ok:
        print(f"  FAIL z_test: {r.error}")
        ok = False
    else:
        print(f"  PASS z_test: Z={r.result['Z']:.4f}, reject={r.result['reject_H0']}")

    r = t_test([1, 2, 3, 4, 5], mu0=3, alpha=0.05)
    if not r.ok:
        print(f"  FAIL t_test: {r.error}")
        ok = False
    else:
        print(f"  PASS t_test: t={r.result['t']:.4f}")

    r = chi_square_test([50, 30, 20], [40, 40, 20])
    if not r.ok:
        print(f"  FAIL chi_square_test: {r.error}")
        ok = False
    else:
        print(f"  PASS chi_square_test: chi2={r.result['chi2']:.4f}")

    r = p_value(1.96, "normal", alternative="two-sided")
    if not r.ok or abs(r.result - 0.05) > 0.01:
        print(f"  FAIL p_value: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS p_value")

    return ok


def test_regression() -> bool:
    """测试 regression 模块。"""
    from MF_Mathematics.probability.regression import (
        linear_regression,
        predict,
        residuals,
    )

    ok = True

    # 完美线性
    r = linear_regression([1, 2, 3], [2, 4, 6])
    if not r.ok or abs(r.result["slope"] - 2.0) > 0.01 or abs(r.result["intercept"]) > 0.01:
        print(f"  FAIL linear_regression: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS linear_regression: {r.result['model']}")

    # 保存回归模型用于残差测试
    model_result = r.result

    r = predict(model_result, x=4)
    if not r.ok or abs(r.result - 8.0) > 0.01:
        print(f"  FAIL predict: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS predict")

    r = residuals(model_result, [1, 2, 3], [2, 4, 6])
    if not r.ok or abs(r.result["SSE"]) > 0.01:
        print(f"  FAIL residuals: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS residuals: SSE=0")

    # 带截距
    r = linear_regression([0, 1, 2, 3, 4], [1, 3, 5, 7, 9])
    if not r.ok or abs(r.result["slope"] - 2.0) > 0.01 or abs(r.result["intercept"] - 1.0) > 0.01:
        print(f"  FAIL linear_regression v2: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS linear_regression v2: {r.result['model']}, R²={r.result['r_squared']:.4f}")

    return ok


def test_all() -> bool:
    """运行全部测试。"""
    print("=" * 60)
    print("概率论与数理统计 子模块测试")
    print("=" * 60)
    print()

    modules = [
        ("probability_space", test_probability_space),
        ("random_variable", test_random_variable),
        ("expectations", test_expectations),
        ("distributions", test_distributions),
        ("limit_theorems", test_limit_theorems),
        ("statistics", test_statistics),
        ("hypothesis_test", test_hypothesis_test),
        ("regression", test_regression),
    ]

    passed = 0
    failed = 0
    for name, test_func in modules:
        print(f"--- {name} ---")
        if test_func():
            passed += 1
        else:
            failed += 1
        print()

    print("=" * 60)
    print(f"结果: {passed}/{len(modules)} PASSED, {failed} FAILED")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = test_all()
    sys.exit(0 if success else 1)
