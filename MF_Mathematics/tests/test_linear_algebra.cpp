// test_linear_algebra.cpp — linear_algebra 包内核 + JSON 测试。
//
// 期望值取自 Python 版各模块 self_test() 的断言。

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "api.h"
#include "json.hpp"
#include "linear_algebra/eigen.h"
#include "linear_algebra/inner_product.h"
#include "linear_algebra/linear_systems.h"
#include "linear_algebra/linear_transforms.h"
#include "linear_algebra/quadratic_forms.h"
#include "linear_algebra/vector_spaces.h"

namespace la = mf::linear_algebra;

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

static bool near(double a, double b, double tol) { return std::abs(a - b) <= tol; }

static bool vec_near(const la::Vector& v, const std::vector<double>& e,
                     double tol = 1e-6) {
    if (v.size() != static_cast<Eigen::Index>(e.size())) return false;
    for (Eigen::Index i = 0; i < v.size(); ++i)
        if (!near(v(i), e[i], tol)) return false;
    return true;
}

// ── 内核层:vector_spaces ────────────────────────────────────────────────────

static void test_vector_spaces() {
    CHECK(vec_near(la::linear_combination({{1, 0}, {0, 1}}, {3, 4}), {3, 4}),
          "linear_combination [[1,0],[0,1]]·[3,4] = [3,4]");

    CHECK(la::is_linear_independent({{1, 0}, {0, 1}}), "[[1,0],[0,1]] 线性无关");
    CHECK(!la::is_linear_independent({{1, 2}, {2, 4}}), "[[1,2],[2,4]] 线性相关");

    const la::BasisResult bs = la::basis({{1, 0, 0}, {0, 1, 0}, {1, 1, 0}});
    CHECK(bs.dimension == 2, "basis([[1,0,0],[0,1,0],[1,1,0]]) 维数 2");

    CHECK(la::dimension({{1, 2, 3}, {2, 4, 6}}) == 1,
          "dimension([[1,2,3],[2,4,6]]) = 1");

    const la::VectorSpaceResult vs = la::is_vector_space({{0, 0}});
    CHECK(vs.zero_vector && vs.closed_under_addition &&
              vs.closed_under_scalar_multiplication && vs.is_vector_space,
          "is_vector_space({0}) 平凡向量空间");
    // 抽样集 [[1,0],[0,1],[1,1],[0,0]] 不封闭(如 2·(1,0)=(2,0) 不在集中)。
    CHECK(!la::is_vector_space({{1, 0}, {0, 1}, {1, 1}, {0, 0}}).is_vector_space,
          "抽样集不构成向量空间(加法不封闭)");

    CHECK(la::subspace_span({{1, 0, 0}, {0, 1, 0}}).dimension == 2,
          "span([[1,0,0],[0,1,0]]) 维数 2");
}

// ── 内核层:linear_transforms ────────────────────────────────────────────────

static void test_linear_transforms() {
    CHECK(vec_near(la::linear_transform({{2, 1}, {0, 3}}, {1, 2}), {4, 6}),
          "T(v)=A·v: [[2,1],[0,3]]·[1,2] = [4,6]");

    const la::MatrixRepresentationResult mr =
        la::matrix_representation({{1, 0}, {0, 2}}, {{1, 0}, {0, 1}});
    CHECK(mr.is_standard_basis, "matrix_representation 标准基");

    const la::KernelResult k = la::kernel({{1, 2, 3}, {0, 0, 0}});
    CHECK(k.nullity == 2, "kernel([[1,2,3],[0,0,0]]) 零化度 2");

    CHECK(la::image({{1, 0}, {0, 1}}).rank == 2, "image(I) 秩 2");

    const la::RankNullityResult rn = la::rank_nullity({{1, 2, 3}, {4, 5, 6}});
    CHECK(rn.theorem_holds, "rank+nullity = dim(V) 成立");
}

// ── 内核层:inner_product ────────────────────────────────────────────────────

static void test_inner_product() {
    CHECK(near(la::dot({1, 2, 3}, {4, 5, 6}), 32.0, 1e-9), "dot = 32");
    CHECK(near(la::norm({3, 4}), 5.0, 1e-9), "||(3,4)|| = 5");
    const la::AngleResult a = la::angle({1, 0}, {0, 1});
    CHECK(near(a.degrees, 90.0, 0.01), "夹角 90°");
    CHECK(la::is_orthogonal({1, 0}, {0, 1}), "正交");
    CHECK(la::gram_schmidt({{1, 1}, {1, 0}}).size() == 2,
          "gram_schmidt 输出 2 个向量");
    CHECK(vec_near(la::orthogonal_projection({1, 2, 3}, {{1, 0, 0}, {0, 1, 0}}),
                   {1, 2, 0}),
          "投影到 xy 平面 = [1,2,0]");
}

// ── 内核层:quadratic_forms ──────────────────────────────────────────────────

static void test_quadratic_forms() {
    const std::string qf = la::quadratic_form({{1, 0}, {0, 1}}, "x,y");
    CHECK(qf.find("x**2") != std::string::npos &&
              qf.find("y**2") != std::string::npos,
          "x^T A x = x**2 + y**2");
    CHECK(la::is_positive_definite({{2, -1}, {-1, 2}}), "[[2,-1],[-1,2]] 正定");
    CHECK(!la::is_positive_definite({{1, 2}, {2, 1}}), "[[1,2],[2,1]] 非正定");
    CHECK(la::is_negative_definite({{-2, 0}, {0, -3}}), "[[-2,0],[0,-3]] 负定");
    CHECK(la::is_indefinite({{1, 0}, {0, -1}}), "[[1,0],[0,-1]] 不定");
    const la::StandardFormResult sf = la::standard_form({{2, 0}, {0, 3}});
    CHECK(sf.standard_form.find("2") != std::string::npos,
          "standard_form 含 2*y1^2");
}

// ── 内核层:linear_systems ───────────────────────────────────────────────────

static void test_linear_systems() {
    const la::GaussianResult g1 = la::gaussian_elimination({{1, 2}, {3, 4}}, {5, 6}, true);
    CHECK(g1.type == "unique", "高斯消元: 唯一解");
    const la::GaussianResult g2 =
        la::gaussian_elimination({{1, 2, 3}, {2, 4, 6}}, {5, 10}, true);
    CHECK(g2.type == "infinite", "高斯消元: 无穷多解");
    const la::GaussianResult g3 = la::gaussian_elimination({{1, 2}, {2, 4}}, {5, 11}, true);
    CHECK(g3.type == "none", "高斯消元: 无解");

    CHECK(la::rank({{1, 2, 3}, {2, 4, 6}}) == 1, "rank = 1");

    const la::SolveResult s = la::solve_linear_system({{1, 0}, {0, 1}}, {3, 4}, true);
    CHECK(s.type == "unique" && vec_near(s.solution, {3, 4}), "Ax=b 唯一解 [3,4]");

    CHECK(la::nullspace({{1, 2, 3}}).dimension == 2, "nullspace 维数 2");
}

// ── 内核层:eigen ────────────────────────────────────────────────────────────

static void test_eigen() {
    // 特征值是复数（虚部为 0 表示实特征值）—— [[0,-1],[1,0]] 的 ±i 必须保留，
    // 所以这里比实部时同时确认虚部为 0。
    const auto near_c = [](const std::complex<double>& z, double want) {
        return near(z.real(), want, 1e-9) && near(z.imag(), 0.0, 1e-9);
    };
    const la::EigenvaluesResult ev = la::eigenvalues({{1, 2}, {2, 1}});
    CHECK((near_c(ev.values[0], -1.0) && near_c(ev.values[1], 3.0)) ||
              (near_c(ev.values[0], 3.0) && near_c(ev.values[1], -1.0)),
          "特征值 {-1, 3}");
    CHECK(!ev.has_complex, "实对称矩阵无复特征值");

    // 旋转矩阵的特征值是 ±i：必须如实给出虚部，不能塌成 0
    const la::EigenvaluesResult rot = la::eigenvalues({{0, -1}, {1, 0}});
    CHECK(rot.has_complex, "[[0,-1],[1,0]] 标记为有复特征值");
    {
        bool saw_pos_i = false, saw_neg_i = false;
        for (const auto& z : rot.values) {
            if (near(z.real(), 0.0, 1e-9) && near(z.imag(), 1.0, 1e-9)) saw_pos_i = true;
            if (near(z.real(), 0.0, 1e-9) && near(z.imag(), -1.0, 1e-9)) saw_neg_i = true;
        }
        CHECK(saw_pos_i && saw_neg_i, "[[0,-1],[1,0]] 特征值为 ±i");
    }
    // 复共轭对不能被当成重根
    {
        bool bogus_multiplicity = false;
        for (const auto& info : rot.with_multiplicity)
            if (info.multiplicity > 1) bogus_multiplicity = true;
        CHECK(!bogus_multiplicity, "±i 不应被报告为重根");
    }
    // 特征向量必须真的满足 A v = λ v
    {
        double worst = 0.0;
        for (const auto& p : la::eigenvectors({{0, -1}, {1, 0}}).eigenpairs) {
            const std::complex<double> v0 = p.eigenvector[0], v1 = p.eigenvector[1];
            const std::complex<double> av0 = -v1, av1 = v0;  // A = [[0,-1],[1,0]]
            worst = std::max(worst, std::abs(av0 - p.eigenvalue * v0));
            worst = std::max(worst, std::abs(av1 - p.eigenvalue * v1));
        }
        CHECK(worst < 1e-8, "旋转矩阵的 (λ, v) 满足 Av = λv");
    }

    CHECK(la::eigenvectors({{1, 2}, {2, 1}}).eigenpairs.size() >= 2,
          "特征向量 ≥ 2 个");

    const std::string cp = la::characteristic_polynomial({{1, 2}, {2, 1}});
    CHECK(!cp.empty() && cp.find("λ") != std::string::npos,
          "特征多项式含 λ");

    CHECK(la::is_diagonalizable({{1, 0}, {0, 2}}), "[[1,0],[0,2]] 可对角化");
    CHECK(la::diagonalize({{1, 0}, {0, 2}}).diagonalizable,
          "diagonalize([[1,0],[0,2]]) 可对角化");
}

// ── 分发层测试(JSON + C ABI)────────────────────────────────────────────────

static std::string call(const char* name, const char* args) {
    char buf[8192];
    const int n = math_call(name, args, buf, sizeof(buf));
    if (n < 0) return "<math_call 失败>";
    return std::string(buf, buf + n);
}

static void test_dispatch() {
    CHECK(function_exists("linear_combination"), "function_exists(linear_combination)");
    CHECK(function_exists("eigenvalues"), "function_exists(eigenvalues)");
    CHECK(function_exists("characteristic_polynomial"),
          "function_exists(characteristic_polynomial)");
    CHECK(function_exists("matrix_inverse"), "function_exists(matrix_inverse)");

    // vector_spaces
    CHECK(call("linear_combination", "{\"vectors\":[[1,0],[0,1]],\"coeffs\":[3,4]}") ==
              "{\"isError\":false,\"value\":[[3],[4]]}",
          "math_call linear_combination → [[3],[4]]");
    CHECK(call("is_linear_independent", "{\"vectors\":[[1,2],[2,4]]}") ==
              "{\"isError\":false,\"value\":false}",
          "math_call is_linear_independent(相关) → false");
    const std::string bs = call("basis", "{\"vectors\":[[1,0,0],[0,1,0],[1,1,0]]}");
    CHECK(bs.find("\"dimension\":2") != std::string::npos, "math_call basis 维数 2");

    // linear_transforms
    CHECK(call("linear_transform", "{\"matrix\":[[2,1],[0,3]],\"vector\":[1,2]}") ==
              "{\"isError\":false,\"value\":[[4],[6]]}",
          "math_call linear_transform → [[4],[6]]");
    const std::string rn = call("rank_nullity", "{\"matrix\":[[1,2,3],[4,5,6]]}");
    CHECK(rn.find("\"theorem_holds\":true") != std::string::npos,
          "math_call rank_nullity 定理成立");

    // inner_product
    CHECK(call("dot", "{\"u\":[1,2,3],\"v\":[4,5,6]}") ==
              "{\"isError\":false,\"value\":32}",
          "math_call dot = 32");
    const std::string ang = call("angle", "{\"u\":[1,0],\"v\":[0,1]}");
    CHECK(ang.find("\"degrees\":90") != std::string::npos, "math_call angle 90°");

    // quadratic_forms
    CHECK(call("quadratic_form", "{\"matrix\":[[1,0],[0,1]],\"x\":\"x,y\"}") ==
              "{\"isError\":false,\"value\":\"x**2 + y**2\"}",
          "math_call quadratic_form → x**2 + y**2");
    CHECK(call("is_positive_definite", "{\"matrix\":[[2,-1],[-1,2]]}") ==
              "{\"isError\":false,\"value\":true}",
          "math_call is_positive_definite → true");

    // linear_systems
    const std::string g = call("gaussian_elimination",
                               "{\"matrix\":[[1,2],[3,4]],\"b\":[5,6]}");
    CHECK(g.find("\"type\":\"unique\"") != std::string::npos,
          "math_call gaussian_elimination 唯一解");
    const std::string sol = call("lin_solve_linear_system",
                                 "{\"A\":[[1,0],[0,1]],\"b\":[3,4]}");
    CHECK(sol.find("\"solution\":[[3],[4]]") != std::string::npos,
          "math_call lin_solve → [[3],[4]]");
    const std::string inv = call("matrix_inverse", "{\"matrix\":[[2,0],[0,4]]}");
    CHECK(inv.find("\"isError\":false") != std::string::npos,
          "math_call matrix_inverse");

    // eigen
    const std::string evs = call("eigenvalues", "{\"matrix\":[[1,2],[2,1]]}");
    CHECK(evs.find("-1") != std::string::npos && evs.find("3") != std::string::npos,
          "math_call eigenvalues 含 -1 和 3");
    const std::string cp = call("characteristic_polynomial",
                                "{\"matrix\":[[1,2],[2,1]]}");
    CHECK(cp.find("\"isError\":false") != std::string::npos,
          "math_call characteristic_polynomial");
    CHECK(call("is_diagonalizable", "{\"matrix\":[[1,0],[0,2]]}") ==
              "{\"isError\":false,\"value\":true}",
          "math_call is_diagonalizable → true");
    const std::string diag = call("diagonalize", "{\"matrix\":[[1,0],[0,2]]}");
    CHECK(diag.find("\"diagonalizable\":true") != std::string::npos,
          "math_call diagonalize 可对角化");
}

int main() {
    std::system("chcp 65001 > nul");
    std::printf("===== linear_algebra 内核测试 =====\n");
    test_vector_spaces();
    test_linear_transforms();
    test_inner_product();
    test_quadratic_forms();
    test_linear_systems();
    test_eigen();
    std::printf("===== 分发层测试(JSON) =====\n");
    test_dispatch();

    std::printf("\n%d 项检查,%d 项失败\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
