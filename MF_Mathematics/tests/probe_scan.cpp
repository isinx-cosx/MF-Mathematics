// probe_scan.cpp — 直接观测数值扫描的内部行为（诊断用，非回归）
//
// 用途：extrema_sym 的数值回退在某些区间上漏掉驻点（如 x·erf(x) 的 x=0
// 在 [-10,10] 上找不到、在 [-5,5] 上找得到），需要看清是采样、候选判定
// 还是三分细化哪一步出的问题。
#include <cstdio>
#include <string>

#include <symengine/basic.h>
#include <symengine/parser.h>
#include <symengine/printers.h>
#include <symengine/real_double.h>
#include <symengine/symbol.h>

#include <symengine/derivative.h>
#include "math_input.h"
#include "math_latex.h"
#include "special_numeric.h"
#include "symbolic_util.h"

int main() {
  std::system("chcp 65001 > nul");
  std::setvbuf(stdout, nullptr, _IONBF, 0);  // 崩溃时不丢缓冲输出

  // ── C. 输入规范化自检 ──────────────────────────────────────────────────────
  std::printf("== 输入规范化自检 ==\n");
  for (const char* raw : {"cosx", "2x", "x^2", "pi", "\xE2\x88\x9Ax", "|-3|",
                          "2\xC3\x97x", "\xCF\x80", "\\frac{1}{2}x",
                          "\\sqrt[3]{8}", "x^{2}"}) {
    const auto pr = mf::input::normalize(raw);
    std::printf("  [%s] -> [%s]", raw, pr.text.c_str());
    for (const auto& n : pr.notes) std::printf(" | %s", n.c_str());
    std::printf("\n");
  }
  std::fflush(stdout);
  // ── A. 特殊函数数值库自检 ──────────────────────────────────────────────────
  std::printf("\n== LaTeX 打印自检 ==\n");
  for (const char* raw : {"x^2+1", "2x", "sin(x)/cos(x)", "|-3|", "\\frac{1}{2}", "\\sqrt[3]{8}"}) {
    try {
      auto root = mf::expr::parse(raw);
      const std::string lx = mf::latex::expr_to_latex(root.get());
      std::printf("  %s  ->  %s\n", raw, lx.c_str());
      if (!lx.empty()) {
        std::printf("      字节:");
        for (unsigned char ch : lx) std::printf(" %02X", ch);
        std::printf("\n");
      }
    } catch (const std::exception& e) {
      std::printf("  %s  ->  解析失败: %s\n", raw, e.what());
    }
  }
  std::fflush(stdout);
  std::printf("== 特殊函数数值实现自检 ==\n");
  std::printf("  zeta(2)      = %.12f   (pi^2/6 = %.12f)\n", mf::num::zeta_real(2.0),
              3.14159265358979323846 * 3.14159265358979323846 / 6.0);
  std::printf("  zeta(-1)     = %.12f   (-1/12 = %.12f)\n", mf::num::zeta_real(-1.0), -1.0 / 12.0);
  std::printf("  zeta(0.5)    = %.12f   (-1.4603545088)\n", mf::num::zeta_real(0.5));
  std::printf("  gamma(0.5)   = %.12f   (sqrt(pi) = %.12f)\n", mf::num::gamma_real(0.5),
              std::sqrt(3.14159265358979323846));
  std::printf("  digamma(1)   = %.12f   (-euler = -0.5772156649)\n", mf::num::digamma_real(1.0));
  std::printf("  polygamma1(1.5)= %.12f  (pi^2/2-4 = %.12f)\n", mf::num::polygamma_real(1, 1.5),
              3.14159265358979323846 * 3.14159265358979323846 / 2.0 - 4.0);
  std::printf("  polygamma1(-0.5)= %.12f (pi^2/2+4 = %.12f)\n", mf::num::polygamma_real(1, -0.5),
              3.14159265358979323846 * 3.14159265358979323846 / 2.0 + 4.0);
  std::printf("  lambertw0(1) = %.12f   (0.5671432904)\n", mf::num::lambertw0_real(1.0));
  std::printf("  lambertw_m1(-0.1) = %.12f (-3.5771520639)\n", mf::num::lambertw_m1_real(-0.1));
  std::fflush(stdout);

  // ── B. zeta 的导数：Derivative 节点数值微分 ───────────────────────────────
  std::printf("\n== zeta 导数求值 ==\n");
  const auto z = SymEngine::parse("zeta(x)");
  SymEngine::map_basic_basic s05;
  s05[SymEngine::symbol("x")] = SymEngine::real_double(0.5);
  std::printf("  zeta(0.5)  = %.12f\n", mf::num::eval_double_ex(z, s05));
  std::fflush(stdout);

  const auto dz = SymEngine::diff(z, SymEngine::symbol("x"));
  std::printf("  d1 = %s\n", SymEngine::str(*dz).c_str());
  std::fflush(stdout);
  std::printf("  d1(0.5) = %.12f   (zeta'(0.5) = -3.9226461392)\n",
              mf::num::eval_double_ex(dz, s05));
  std::fflush(stdout);

  // 替换后再求值（这一步曾导致栈溢出，单独试以定位）
  std::printf("  替换后再求值 d1.subs(x=0.5) ...\n");
  std::fflush(stdout);
  try {
    const auto sub = dz->subs(s05);
    std::printf("    subs 成功: %s\n", SymEngine::str(*sub).c_str());
    std::fflush(stdout);
  } catch (...) {
    std::printf("    subs 抛异常\n");
    std::fflush(stdout);
  }

  const std::string expr = "2*x*E**(-x**2)/sqrt(pi) + erf(x)";
  const auto f = SymEngine::parse(expr);
  std::printf("\nf = %s\n\n", SymEngine::str(*f).c_str());

  // ① 单点求值是否正常
  for (double xv : {0.0, 1e-15, 0.0025, -0.0025, 0.5}) {
    SymEngine::map_basic_basic s;
    s[SymEngine::symbol("x")] = SymEngine::real_double(xv);
    const double v = mf::num::eval_double_ex(f, s);
    std::printf("  f(%g) = %.17g\n", xv, v);
  }
  std::printf("\n");

  // ② 不同区间下的扫描结果
  struct Case { double lo, hi; int steps; };
  const Case cases[] = {{-5, 5, 8000}, {-10, 10, 8000}, {-20, 20, 8000},
                        {-10, 10, 16000}, {-10, 10, 4000}};
  for (const auto& c : cases) {
    const auto sc = mf::symutil::numeric_roots_in_range(f, "x", c.lo, c.hi, c.steps, {});
    std::printf("  [%g,%g] steps=%d h=%.6g → 求值 %d/%d, 根 %zu 个:",
                c.lo, c.hi, c.steps, (c.hi - c.lo) / c.steps,
                sc.evaluated, sc.total, sc.roots.size());
    for (const auto& r : sc.roots) std::printf(" %.12g", r.x);
    std::printf("\n");
  }

  // ③ 手工验证"网格点正好踩在零点上"的邻域取值
  std::printf("\n  网格点附近（[-10,10], h=0.0025）:\n");
  const double h = 0.0025;
  for (int i = 3998; i <= 4002; ++i) {
    const double xc = -10.0 + i * h;
    SymEngine::map_basic_basic s;
    s[SymEngine::symbol("x")] = SymEngine::real_double(xc);
    std::printf("    i=%d x=%.17g f=%.17g\n", i, xc, mf::num::eval_double_ex(f, s));
  }

  // ④ 统计"|f| 局部极小"的候选点数量：若数量极大，就会把三分细化的
  //    次数上限耗尽，导致真正的零点候选拿不到细化机会。
  std::printf("\n  候选点统计（|f| 不高于左右相邻采样点）:\n");
  for (const auto& c : cases) {
    const double hh = (c.hi - c.lo) / c.steps;
    const auto val = [&](double xv) {
      SymEngine::map_basic_basic s;
      s[SymEngine::symbol("x")] = SymEngine::real_double(xv);
      return mf::num::eval_double_ex(f, s);
    };
    int cand = 0, near_zero = 0;
    for (int i = 0; i <= c.steps; ++i) {
      const double xc = c.lo + i * hh;
      const double av = std::fabs(val(xc));
      const double l = std::fabs(val(xc - hh));
      const double rr = std::fabs(val(xc + hh));
      if (av <= l && av <= rr) { ++cand; if (av <= 1e-9) ++near_zero; }
    }
    std::printf("    [%g,%g] steps=%d: 候选 %d 个，其中 |f|<=1e-9 的 %d 个\n",
                c.lo, c.hi, c.steps, cand, near_zero);
  }
  return 0;
}
