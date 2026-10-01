// test_functional_analysis.cpp — functional_analysis 包内核 + JSON 测试。
//
// 期望值取自 Python 版各模块 self_test() 的断言。

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <limits>
#include <string>
#include <vector>

#include "api.h"
#include "json.hpp"
#include "functional_analysis/core_theorems.h"
#include "functional_analysis/dual_spaces.h"
#include "functional_analysis/inner_product_spaces.h"
#include "functional_analysis/linear_operators.h"
#include "functional_analysis/normed_spaces.h"
#include "functional_analysis/spectral_theory.h"

namespace fa = mf::functional_analysis;

static int g_checks = 0;
static int g_failures = 0;

#define CHECK(cond, msg)                                     \
    do {                                                     \
        ++g_checks;                                          \
        if (!(cond)) {                                       \
            ++g_failures;                                    \
            std::printf("[FAIL] %s\n", msg);                 \
        }                                                    \
    } while (0)

#define CHECK_EQ(a, b, msg) CHECK((a) == (b), msg)

static bool near(double a, double b, double tol) { return std::abs(a - b) <= tol; }

// ── normed_spaces ───────────────────────────────────────────────────────────

static void test_normed_spaces() {
    CHECK(near(fa::lp_norm({1, 2, 3}, 2), std::sqrt(14.0), 1e-10), "ℓ² 范数 = √14");
    CHECK(near(fa::lp_norm({1, -5, 3}, std::numeric_limits<double>::infinity()), 5.0, 1e-10),
          "ℓ∞ 范数 = 5");
    CHECK(near(fa::lp_norm({1, -2, 3}, 1), 6.0, 1e-10), "ℓ¹ 范数 = 6");
    CHECK(fa::is_banach("R^n", 3), "R^n 是巴拿赫空间");

    std::vector<std::vector<double>> seq;
    for (int i = 0; i < 50; ++i) seq.push_back({1.0 / ((i + 1) * (i + 1))});
    const fa::CompletenessResult r = fa::space_completeness_check(seq, "l2");
    CHECK(r.is_cauchy, "1/n² 序列是柯西列");
}

// ── dual_spaces ─────────────────────────────────────────────────────────────

static void test_dual_spaces() {
    const Eigen::MatrixXd id = fa::dual_space_basis("R^n");
    CHECK((id - Eigen::MatrixXd::Identity(3, 3)).cwiseAbs().maxCoeff() < 1e-10,
          "R^n 对偶基 = 单位阵");

    Eigen::MatrixXd basis(2, 2);
    basis << 2, 0, 0, 3;
    const Eigen::MatrixXd dual = fa::dual_space_basis(basis);
    CHECK(near(dual(0, 0), 0.5, 1e-10) && near(dual(1, 1), 1.0 / 3.0, 1e-10),
          "[[2,0],[0,3]] 对偶基 = diag(1/2, 1/3)");

    std::vector<std::vector<double>> seq;
    for (int i = 0; i < 30; ++i)
        seq.push_back({1.0 / (i + 1), 1.0 / (i + 1) / (i + 1)});
    const std::vector<double> functional = {1, 0};
    const std::vector<double> limit = {0, 0};
    CHECK(fa::weak_convergence(seq, &functional, &limit, 0.1), "1/n 序列弱收敛到 0");

    CHECK(fa::is_reflexive("R^n", 10), "R^n 自反");
}

// ── linear_operators ────────────────────────────────────────────────────────

static void test_linear_operators() {
    Eigen::MatrixXd A2(2, 2);
    A2 << 2, 0, 0, 2;
    CHECK(near(fa::operator_norm(A2, "2"), 2.0, 1e-10), "谱范数([[2,0],[0,2]]) = 2");
    Eigen::MatrixXd Ainf(2, 2);
    Ainf << 1, 2, 3, 4;
    CHECK(near(fa::operator_norm(Ainf, "inf"), 7.0, 1e-10), "行和范数 = 7");
    CHECK(fa::is_bounded(A2), "矩阵算子有界");
    CHECK(near(fa::linear_functional_eval({1, 2, 3}, {4, 5, 6}), 32.0, 1e-10),
          "线性泛函 ⟨a,x⟩ = 32");

    Eigen::MatrixXd Ak(2, 2);
    Ak << 1, 1, 1, 1;
    const fa::KernelResult kr = fa::kernel_dimension(Ak);
    CHECK_EQ(kr.dim_ker, 1LL, "dim ker([[1,1],[1,1]]) = 1");
}

// ── spectral_theory ─────────────────────────────────────────────────────────

static void test_spectral_theory() {
    Eigen::MatrixXd A(2, 2);
    A << 1, 2, 2, 1;
    const fa::SpectrumResult sp = fa::spectrum_approx(A);
    CHECK(sp.real_evals.size() == 2 &&
              near(sp.real_evals[0], -1.0, 1e-6) && near(sp.real_evals[1], 3.0, 1e-6),
          "谱 [[1,2],[2,1]] = {-1, 3}");
    CHECK(near(sp.spectral_radius, 3.0, 1e-6), "谱半径 = 3");

    const fa::SpectrumClassifyResult sc = fa::spectrum_classify(A);
    CHECK(sc.is_self_adjoint, "[[1,2],[2,1]] 自伴");
    CHECK(sc.point_spectrum.size() == 2, "点谱含 2 个特征值");

    Eigen::MatrixXd sym(2, 2);
    sym << 2, 0, 0, 2;
    const fa::SpectralTheoremResult st = fa::spectral_theorem(sym);
    CHECK(st.is_self_adjoint && st.reconstruction_error < 1e-10, "谱定理 2I 重构精确");

    Eigen::MatrixXd diag3(3, 3);
    diag3 << 3, 0, 0, 0, 1, 0, 0, 0, 2;
    const fa::SpectrumResult sp3 = fa::spectrum_approx(diag3);
    CHECK(sp3.real_evals == std::vector<double>({1, 2, 3}), "对角阵谱 = [1,2,3]");

    Eigen::MatrixXd m11(2, 2);
    m11 << 1, 1, 1, 1;
    const fa::SpectralTheoremResult st2 = fa::spectral_theorem(m11);
    CHECK(st2.is_self_adjoint && st2.reconstruction_error < 1e-8, "谱定理 [[1,1],[1,1]]");
}

// ── core_theorems ───────────────────────────────────────────────────────────

static void test_core_theorems() {
    const std::vector<double> ext = fa::hahn_banach_extension({1, 2, 3}, 3, 5);
    CHECK(ext == std::vector<double>({1, 2, 3, 0, 0}), "哈恩-巴拿赫延拓补零");

    Eigen::MatrixXd o1(2, 2), o2(2, 2), o3(2, 2);
    o1 << 2, 0, 0, 1;
    o2 << 1, 0, 0, 3;
    o3 << 0.5, 0, 0, 0.5;
    const fa::UniformBoundednessResult ub = fa::uniform_boundedness({o1, o2, o3});
    CHECK(ub.uniformly_bounded, "一致有界原理:算子族有界");

    Eigen::MatrixXd inv(2, 2);
    inv << 2, 0, 0, 3;
    CHECK(fa::open_mapping(inv), "可逆矩阵是开映射");
    Eigen::MatrixXd idm(2, 2);
    idm << 1, 0, 0, 1;
    CHECK(fa::closed_graph(idm), "恒等算子有闭图像");

    // 近奇异矩阵:最小奇异值 1e-12。numpy matrix_rank 阈值 = s₀·max(M,N)·eps
    // ≈ 6.7e-16,故 1e-12 计入 → 满秩 → 开映射(非 tol·max(s₀,1)=1e-10 的判定)。
    Eigen::MatrixXd near_sing(3, 3);
    near_sing << 1, 0, 0, 0, 1e-12, 0, 0, 0, 1e-12;
    CHECK(fa::open_mapping(near_sing), "diag(1,1e-12,1e-12) 满秩 → 开映射");
}

// ── inner_product_spaces ────────────────────────────────────────────────────

static void test_inner_product_spaces() {
    const double kPi = 3.14159265358979323846;
    CHECK(std::abs(fa::inner_product("sin(x)", "cos(x)", 0, 2 * kPi, 2000)) < 1e-4,
          "⟨sin,cos⟩ 在 [0,2π] ≈ 0");
    CHECK(fa::funct_is_orthogonal("sin(x)", "cos(x)", 0, 2 * kPi, 1e-4),
          "sin 与 cos 正交");
    CHECK(near(fa::inner_product("sin(x)", "sin(x)", 0, kPi), kPi / 2, 0.01),
          "⟨sin,sin⟩ 在 [0,π] = π/2");

    const auto basis = fa::funct_gram_schmidt({{1, 1}, {1, 0}});
    CHECK(near(basis[0][0], 1.0 / std::sqrt(2.0), 1e-10), "GS 首个向量 (1/√2,1/√2)");
    const double dot01 = basis[0][0] * basis[1][0] + basis[0][1] * basis[1][1];
    CHECK(std::abs(dot01) < 1e-10, "GS 向量正交");
    const double n0 = std::sqrt(basis[0][0] * basis[0][0] + basis[0][1] * basis[0][1]);
    CHECK(near(n0, 1.0, 1e-10), "GS 向量归一化");

    CHECK(fa::is_hilbert("R^n", 5), "R^n 是希尔伯特空间");
}

// ── 分发层测试(JSON + C ABI)────────────────────────────────────────────────

static std::string call(const char* name, const char* args) {
    char buf[8192];
    const int n = math_call(name, args, buf, sizeof(buf));
    if (n < 0) return "<math_call 失败>";
    return std::string(buf, buf + n);
}

static void test_dispatch() {
    CHECK(function_exists("lp_norm"), "function_exists(lp_norm)");
    CHECK(function_exists("spectral_theorem"), "function_exists(spectral_theorem)");

    const mf::json::Value lp = mf::json::Value::parse(
        call("lp_norm", "{\"vector\":[1,2,3],\"p\":2}"));
    CHECK(near(lp["value"].as_double(), std::sqrt(14.0), 1e-9),
          "math_call lp_norm([1,2,3],2) = √14");
    CHECK(call("is_banach", "{\"space\":\"R^n\",\"dimension\":3}") ==
              "{\"isError\":false,\"value\":true}",
          "math_call is_banach(R^n)");
    CHECK(call("linear_functional_eval", "{\"func\":[1,2,3],\"x\":[4,5,6]}") ==
              "{\"isError\":false,\"value\":32}",
          "math_call linear_functional_eval = 32");
    CHECK(call("open_mapping", "{\"A\":[[2,0],[0,3]]}") ==
              "{\"isError\":false,\"value\":true}",
          "math_call open_mapping");
    CHECK(call("is_hilbert", "{\"space\":\"R^n\",\"dimension\":5}") ==
              "{\"isError\":false,\"value\":true}",
          "math_call is_hilbert(R^n)");

    const std::string st = call("spectral_theorem", "{\"A\":[[2,0],[0,2]]}");
    CHECK(st.find("\"isError\":false") != std::string::npos &&
              st.find("\"is_self_adjoint\":true") != std::string::npos,
          "math_call spectral_theorem 2I");
    const std::string sp = call("spectrum_approx", "{\"A\":[[1,2],[2,1]]}");
    CHECK(sp.find("\"isError\":false") != std::string::npos, "math_call spectrum_approx");

    const std::string bad = call("lp_norm", "{\"vector\":[1],\"p\":0}");
    CHECK(bad.find("\"isError\":true") != std::string::npos, "lp_norm p=0 → isError");
}

int main() {
    std::system("chcp 65001 > nul");
    std::printf("===== functional_analysis 内核测试 =====\n");
    test_normed_spaces();
    test_dual_spaces();
    test_linear_operators();
    test_spectral_theory();
    test_core_theorems();
    test_inner_product_spaces();
    std::printf("===== 分发层测试(JSON) =====\n");
    test_dispatch();

    std::printf("\n%d 项检查,%d 项失败\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
