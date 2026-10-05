// test_algebraic_topology.cpp — algebraic_topology(homology/cohomology)测试。
//
// 期望值取自 Python 版各模块 self_test() 的断言,并补充复形路径用例。

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <string>
#include <vector>

#include "api.h"
#include "algebraic_topology/cohomology.h"
#include "algebraic_topology/degree_fixedpoint.h"
#include "algebraic_topology/homology.h"
#include "algebraic_topology/homotopy.h"
#include "algebraic_topology/persistent_homology.h"

namespace at = mf::algebraic_topology;

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

static bool near(double a, double b, double tol) {
    return std::abs(a - b) <= tol;
}

// ── 内核层:内部辅助修复回归 ────────────────────────────────────────────────

static void test_internal() {
    // boundary_matrix 应内部归一化单形顺序,乱序输入与排序输入结果一致
    const auto sorted =
        at::detail::boundary_matrix({{0, 1, 2}}, {{0, 1}, {0, 2}, {1, 2}});
    const auto unsorted =
        at::detail::boundary_matrix({{2, 1, 0}}, {{1, 0}, {2, 0}, {2, 1}});
    CHECK(sorted == unsorted, "boundary_matrix 乱序输入归一化后一致");

    // 非 ±1 整数矩阵的秩(溢出检测路径)
    CHECK_EQ(at::detail::integer_rank({{2, 0}, {0, 3}}), 2LL,
             "rank([[2,0],[0,3]]) == 2");
    CHECK_EQ(at::detail::integer_rank({{1, 1}, {1, 1}}), 1LL,
             "rank([[1,1],[1,1]]) == 1");
    CHECK_EQ(at::detail::integer_rank({{3, 6, 9}, {1, 2, 3}}), 1LL,
             "rank 线性相关 == 1");
}

// ── 内核层:空间查表 ─────────────────────────────────────────────────────────

static void test_space_lookup() {
    CHECK_EQ(at::homology_group("S1", 0).betti, 1LL, "H0(S1) β=1");
    CHECK_EQ(at::homology_group("S1", 1).betti, 1LL, "H1(S1) β=1");
    CHECK_EQ(at::homology_group("T2", 1).betti, 2LL, "H1(T2) β=2");
    CHECK_EQ(at::homology_group("S2", 2).betti, 1LL, "H2(S2) β=1");

    const at::HomologyGroup rp2 = at::homology_group("RP2", 1);
    CHECK_EQ(rp2.betti, 0LL, "H1(RP2) β=0");
    CHECK(rp2.torsion == std::vector<long long>{2}, "H1(RP2) 挠 [2]");
    CHECK(rp2.group == "Z_2", "H1(RP2) = Z_2");

    const at::HomologyGroup k = at::homology_group("K", 1);
    CHECK_EQ(k.betti, 1LL, "H1(K) β=1");
    CHECK(k.torsion == std::vector<long long>{2}, "H1(K) 挠 [2]");

    CHECK(at::betti_numbers("T2") == std::vector<long long>({1, 2, 1}),
          "β(T2) == [1,2,1]");
    CHECK(at::betti_numbers("S2") == std::vector<long long>({1, 0, 1}),
          "β(S2) == [1,0,1]");

    CHECK_EQ(at::euler_characteristic("S2"), 2LL, "χ(S2) == 2");
    CHECK_EQ(at::euler_characteristic("T2"), 0LL, "χ(T2) == 0");
    CHECK_EQ(at::euler_characteristic("S1"), 0LL, "χ(S1) == 0");
}

// ── 内核层:单纯复形路径 ─────────────────────────────────────────────────────

static void test_complex_path() {
    // 填充三角形:(0,1,2) → 7 个单形,顶点 {0,1,2} 共 3 个。
    const at::SimplicialComplexResult tri =
        at::build_simplicial_complex({{0, 1, 2}});
    CHECK_EQ(tri.num_vertices, 3LL, "三角形顶点数 3");
    CHECK_EQ(tri.num_simplices, 7LL, "三角形补全后 7 个单形");
    CHECK_EQ(tri.max_dimension, 2LL, "三角形最高维 2");

    // 实心三角形(盘)同调:H0=Z,H1=0,χ=1
    CHECK_EQ(at::homology_group(tri.complex, 0).betti, 1LL, "盘 H0 β=1");
    CHECK_EQ(at::homology_group(tri.complex, 1).betti, 0LL, "盘 H1 β=0");
    CHECK_EQ(at::euler_characteristic(tri.complex), 1LL, "盘 χ=1");

    // 三角形边界(圆 S1):H0=Z,H1=Z,χ=0
    const at::SimplicialComplexResult circle =
        at::build_simplicial_complex({{0, 1}, {0, 2}, {1, 2}});
    CHECK_EQ(at::homology_group(circle.complex, 0).betti, 1LL, "圆 H0 β=1");
    CHECK_EQ(at::homology_group(circle.complex, 1).betti, 1LL, "圆 H1 β=1");
    CHECK_EQ(at::euler_characteristic(circle.complex), 0LL, "圆 χ=0");

    // 两个分离点:β0 = 2
    const at::SimplicialComplexResult two_pts =
        at::build_simplicial_complex({{0}, {1}});
    CHECK_EQ(at::homology_group(two_pts.complex, 0).betti, 2LL, "两点 H0 β=2");

    // 带两个三角形的复形(两个相连三角形),最大维 2
    const at::SimplicialComplexResult two_tri =
        at::build_simplicial_complex({{0, 1, 2}, {0, 1, 3}});
    CHECK_EQ(two_tri.num_vertices, 4LL, "双三角形顶点数 4");
    CHECK_EQ(two_tri.max_dimension, 2LL, "双三角形最高维 2");
    // 三角形拼成的菱形(两个三角形共享边)是一个盘:χ = 1
    CHECK_EQ(at::euler_characteristic(two_tri.complex), 1LL, "双三角形 χ=1");
}

// ── 内核层:上同调与庞加莱对偶 ───────────────────────────────────────────────

static void test_cohomology() {
    CHECK_EQ(at::cohomology_group("S1", 1).betti, 1LL, "H1(S1) β=1");
    CHECK_EQ(at::cohomology_group("T2", 2).betti, 1LL, "H2(T2) β=1");

    at::PoincareDuality pd1 = at::poincare_duality("S2", 1);
    CHECK(pd1.duality_holds, "S2 庞加莱对偶 k=1 成立");
    at::PoincareDuality pd2 = at::poincare_duality("T2", 0);
    CHECK(pd2.duality_holds, "T2 庞加莱对偶 k=0 成立");
    CHECK_EQ(pd2.dimension, 2LL, "T2 维数 2");
}

// ── 内核层:同伦与不动点 ─────────────────────────────────────────────────────

static void test_homotopy() {
    CHECK(at::fundamental_group("S1") == "Z", "π1(S1) = Z");
    CHECK(at::fundamental_group("Sn", 2) == "0", "π1(S2) = 0");
    CHECK(at::fundamental_group("T2") == "Z×Z", "π1(T2) = Z×Z");
    CHECK(at::fundamental_group("RP2") == "Z_2", "π1(RP2) = Z_2");
    CHECK(at::fundamental_group("Sn", 0) == "π₁(Sn)", "π1(S0) 占位符(对齐 Python)");
    CHECK(at::fundamental_group("WEDGE_5", 1) == "F_5",
          "wedge_5 → F_5(从名字解析)");
    CHECK(at::fundamental_group("WEDGEN", 3) == "F_3",
          "WEDGEN → F_n(回退 n 参数)");
    CHECK(at::is_simply_connected("Sn", 2), "S2 单连通");
    CHECK(!at::is_simply_connected("S1"), "S1 非单连通");
    const at::PathHomotopy ph = at::path_homotopy("S1");
    CHECK(ph.space == "S1" && ph.fundamental_group == "Z",
          "path_homotopy(S1) π1 = Z");

    // 英文别名：circle/torus/disk 这类最自然的写法要给出**真答案**。
    // 以前它们落到"未知空间"分支、把占位串 π₁(circle) 当结果返回（isError:false）。
    CHECK(at::fundamental_group("circle") == "Z", "π1(circle) = Z（英文别名）");
    CHECK(at::fundamental_group("torus") == "Z×Z", "π1(torus) = Z×Z（英文别名）");
    CHECK(at::fundamental_group("disk") == "0", "π1(disk) = 0（可缩）");
    CHECK(!at::is_simply_connected("circle"), "circle 非单连通（经别名 → S1）");
    // 未识别的空间必须**如实报错**，不能返回占位串当答案。
    bool threw = false;
    try {
        at::fundamental_group("blahblah");
    } catch (const std::exception&) {
        threw = true;
    }
    CHECK(threw, "未知空间如实报错（不再返回 π₁(输入) 占位串）");
}

static void test_degree_fixedpoint() {
    CHECK_EQ(at::mapping_degree(1).antipodal_degree, 1LL, "S1 对径映射度 1");
    CHECK_EQ(at::mapping_degree(2).antipodal_degree, -1LL, "S2 对径映射度 -1");
    CHECK_EQ(at::mapping_degree(2).identity_degree, 1LL, "deg(id) = 1");
    CHECK(at::brouwer_fixed_point_theorem("D2").holds, "布劳威尔 D2 成立");
    CHECK_EQ(at::brouwer_fixed_point_theorem("D3").dimension, 3LL, "D3 维数 3");
    CHECK(!at::hairy_ball_theorem(2).nonzero_vector_field_exists,
          "S2 毛球:无非零向量场");
    CHECK(at::hairy_ball_theorem(3).nonzero_vector_field_exists,
          "S3 有非零向量场");
    CHECK_EQ(at::hairy_ball_theorem(2).euler_characteristic, 2LL, "χ(S2)=2");
}

static void test_conceptual() {
    const at::BoundaryOperator bo = at::boundary_operator(2);
    CHECK(bo.dimension == 2 && !bo.formula.empty(), "boundary_operator(2) 有公式");
    const at::CupProduct cp = at::cup_product();
    CHECK(cp.operation == "cup_product" &&
              cp.mapping == "H^p × H^q → H^{p+q}",
          "cup_product 结果");
}

// ── 内核层:持续同调 ─────────────────────────────────────────────────────────

static void test_persistent_homology() {
    // 两点 {0},{1},max_scale=1:1 次合并 (0,1) + 1 个幸存 (0,1)
    const std::vector<std::vector<double>> pts2 = {{0.0}, {1.0}};
    const at::FiltrationResult f2 = at::filtration(pts2, 1.0);
    CHECK_EQ(f2.n_points, 2LL, "filtration 2 点");
    CHECK_EQ(f2.ambient_dim, 1LL, "filtration ambient=1");
    CHECK_EQ(static_cast<long long>(f2.birth_death_0.size()), 2LL,
             "filtration 2 点 bd0 2 对");

    const at::PersistenceDiagramResult pd0 = at::persistence_diagram(pts2, 0, 1.0);
    CHECK_EQ(pd0.num_pairs, 2LL, "pd0 2 点 2 对");
    CHECK(near(pd0.pairs[0].persistence, 1.0, 1e-9), "pd0 持久性 1.0");
    // significant 阈值可配置:默认 0.1 → 全显著;ratio 2.0 → 全不显著
    CHECK_EQ(pd0.significant_pairs, 2LL, "pd0 显著对 2(默认阈值 0.1)");
    const at::PersistenceDiagramResult pd0_strict =
        at::persistence_diagram(pts2, 0, 1.0, 2.0);
    CHECK_EQ(pd0_strict.significant_pairs, 0LL, "pd0 显著对 0(阈值 2.0)");

    // 3 个共线点 {0},{1},{2},max_scale=1:三角形最大边 2>1 → dim1 无三角形
    const std::vector<std::vector<double>> pts3 = {{0.0}, {1.0}, {2.0}};
    const at::PersistenceDiagramResult pd1 = at::persistence_diagram(pts3, 1, 1.0);
    CHECK_EQ(pd1.num_pairs, 0LL, "pd1 共线点无三角形 → 0 对");

    // 2D 三角形,max_scale=2:dim1 有 1 个三角形对
    const std::vector<std::vector<double>> tri = {{0, 0}, {1, 0}, {0, 1}};
    const at::PersistenceDiagramResult pd1b = at::persistence_diagram(tri, 1, 2.0);
    CHECK_EQ(pd1b.num_pairs, 1LL, "2D 三角形 dim1 1 对");
    CHECK(near(pd1b.pairs[0].birth, 1.41421356237, 1e-6), "三角形 birth = 最长边 √2");

    // 条形码
    const at::BarcodeResult br = at::barcode_plot(pts2, 0, 1.0);
    CHECK_EQ(br.num_bars, 2LL, "barcode 2 条");
    CHECK(br.barcodes[0].bar_length == br.barcodes[0].persistence,
          "bar_length = persistence");
}

// ── 分发层测试(JSON + C ABI)────────────────────────────────────────────────

static std::string call(const char* name, const char* args) {
    char buf[8192];
    const int n = math_call(name, args, buf, sizeof(buf));
    if (n < 0) return "<math_call 失败>";
    return std::string(buf, buf + n);
}

static void test_dispatch() {
    CHECK(function_exists("homology_group"), "function_exists(homology_group)");
    CHECK(function_exists("simplicial_complex"), "function_exists(simplicial_complex)");

    CHECK(call("homology_group", "{\"space\":\"T2\",\"n\":1}") ==
              "{\"isError\":false,\"value\":{\"betti\":2,\"group\":\"Z^2\",\"torsion\":[]}}",
          "math_call homology_group(T2,1) == betti 2");
    CHECK(call("homology_group", "{\"space\":\"RP2\",\"n\":1}") ==
              "{\"isError\":false,\"value\":{\"betti\":0,\"group\":\"Z_2\",\"torsion\":[2]}}",
          "math_call homology_group(RP2,1) == Z_2");
    CHECK(call("betti_numbers", "{\"space\":\"T2\"}") ==
              "{\"isError\":false,\"value\":[1,2,1]}",
          "math_call betti_numbers(T2) == [1,2,1]");
    CHECK(call("euler_characteristic", "{\"space\":\"S2\"}") ==
              "{\"isError\":false,\"value\":2}",
          "math_call euler_characteristic(S2) == 2");
    CHECK(call("cohomology_group", "{\"space\":\"S1\",\"n\":1}") ==
              "{\"isError\":false,\"value\":{\"betti\":1,\"group\":\"Z\",\"torsion\":[]}}",
          "math_call cohomology_group(S1,1) == Z");
    CHECK(call("poincare_duality", "{\"manifold\":\"S2\",\"k\":1}") ==
              "{\"isError\":false,\"value\":{\"co_betti\":0,\"dimension\":2,"
              "\"duality_holds\":true,\"hom_betti\":0,\"manifold\":\"S2\"}}",
          "math_call poincare_duality(S2,1) 成立");

    // 复形 JSON 输入:三角形边界(圆)的 H1
    const std::string circle_json =
        "{\"complex\":{\"0\":[[0],[1],[2]],\"1\":[[0,1],[0,2],[1,2]]},\"n\":1}";
    CHECK(call("homology_group", circle_json.c_str()) ==
              "{\"isError\":false,\"value\":{\"betti\":1,\"group\":\"Z\",\"torsion\":[]}}",
          "math_call homology_group(complex 圆,1) == Z");

    // simplicial_complex 构建 + 统计
    CHECK(call("simplicial_complex", "{\"simplices\":[[0,1,2],[0,1,3]]}") ==
              "{\"isError\":false,\"value\":{\"complex\":{\"0\":[[0],[1],[2],[3]],"
              "\"1\":[[0,1],[0,2],[0,3],[1,2],[1,3]],\"2\":[[0,1,2],[0,1,3]]},"
              "\"max_dimension\":2,\"num_simplices\":11,\"num_vertices\":4}}",
          "math_call simplicial_complex(双三角形)");

    // 错误路径:未知空间
    const std::string unknown = call("homology_group", "{\"space\":\"XX\",\"n\":0}");
    CHECK(unknown.find("\"isError\":true") != std::string::npos, "未知空间 → isError");

    // 批次 B:同伦/不动点/概念函数
    CHECK(call("fundamental_group", "{\"space\":\"T2\"}") ==
              "{\"isError\":false,\"value\":\"Z×Z\"}",
          "math_call fundamental_group(T2) == Z×Z");
    CHECK(call("is_simply_connected", "{\"space\":\"Sn\",\"n\":2}") ==
              "{\"isError\":false,\"value\":true}",
          "math_call is_simply_connected(Sn,2) == true");
    CHECK(call("mapping_degree", "{\"sphere_dim\":2}") ==
              "{\"isError\":false,\"value\":{\"antipodal_degree\":-1,"
              "\"identity_degree\":1,\"sphere_dim\":2}}",
          "math_call mapping_degree(2) == 对径度 -1");
    CHECK(call("hairy_ball_theorem", "{\"sphere_dim\":2}") ==
              "{\"isError\":false,\"value\":{\"euler_characteristic\":2,"
              "\"nonzero_vector_field_exists\":false,\"sphere_dim\":2}}",
          "math_call hairy_ball_theorem(2) == S2 无非零场");
    CHECK(call("brouwer_fixed_point_theorem", "{\"space\":\"D2\"}") ==
              "{\"isError\":false,\"value\":{\"dimension\":2,\"holds\":true}}",
          "math_call brouwer(D2) 成立");
    CHECK(call("boundary_operator", "{\"dimension\":2}").find("formula") !=
              std::string::npos,
          "math_call boundary_operator(2) 有公式");
    CHECK(call("cup_product", "{}") ==
              "{\"isError\":false,\"value\":{\"mapping\":\"H^p × H^q → H^{p+q}\","
              "\"operation\":\"cup_product\"}}",
          "math_call cup_product 结果");

    // 批次 C:持续同调(浮点值,做结构性检查)
    const std::string filt =
        call("filtration", "{\"point_cloud\":[[0],[1]],\"max_scale\":1.0}");
    CHECK(filt.find("\"isError\":false") != std::string::npos &&
              filt.find("\"n_points\":2") != std::string::npos,
          "math_call filtration 2 点");
    const std::string pdc =
        call("persistence_diagram",
             "{\"point_cloud\":[[0],[1]],\"dim\":0,\"max_scale\":1.0}");
    CHECK(pdc.find("\"isError\":false") != std::string::npos &&
              pdc.find("\"num_pairs\":2") != std::string::npos,
          "math_call persistence_diagram 2 对");
    const std::string barc =
        call("barcode_plot", "{\"point_cloud\":[[0],[1]],\"dim\":0}");
    CHECK(barc.find("\"isError\":false") != std::string::npos &&
              barc.find("\"num_bars\":2") != std::string::npos,
          "math_call barcode_plot 2 条");
}

int main() {
    std::system("chcp 65001 > nul");
    std::printf("===== algebraic_topology 内核测试 =====\n");
    test_internal();
    test_space_lookup();
    test_complex_path();
    test_cohomology();
    test_homotopy();
    test_degree_fixedpoint();
    test_conceptual();
    test_persistent_homology();
    std::printf("===== 分发层测试(JSON) =====\n");
    test_dispatch();

    std::printf("\n%d 项检查,%d 项失败\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
