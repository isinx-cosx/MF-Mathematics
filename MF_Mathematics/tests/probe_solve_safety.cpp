// probe_solve_safety.cpp — 实证 SymEngine::solve 对各类方程是否安全
//
// 背景：safe_solve 用"字符串里是否含超越函数名"来拦截求解请求，因为实测
// sin(20*x) 的驻点方程会让 SymEngine 求解器**栈溢出**（0xC00000FD，进程级
// 故障，无法用异常捕获）。这个黑名单过于粗暴：它连带挡掉了 exp / sqrt /
// asin 等一大类其驻点方程其实可解的函数，使新加的定义域分析根本走不到。
//
// 本探针把每条用例做成**可单独执行**的（probe_solve_safety <序号>），
// 由外部逐条起独立进程运行。这样某条崩溃只会影响它自己，退出码即证据，
// 据此决定黑名单能放宽到哪一步——只放宽有实测证据的形式，不靠推测。
//
// 用法：
//   probe_solve_safety           列出全部用例
//   probe_solve_safety <序号>     只跑第 <序号> 条，返回码 0=成功，其它=异常/崩溃
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include <symengine/basic.h>
#include <symengine/parser.h>
#include <symengine/printers.h>
#include <symengine/sets.h>
#include <symengine/solve.h>
#include <symengine/symbol.h>

namespace {

struct Case {
  const char* label;
  const char* eq;
  const char* note;
};

// 顺序无关：外部逐条执行，崩溃不会带走其它用例
const std::vector<Case>& cases() {
  static const std::vector<Case> kCases = {
      // ① 基线：多项式 / 有理式（已知安全）
      {"poly", "3*x**2 - 3*a", "多项式 —— 基线"},
      {"rational", "-1 + a/x", "有理式 —— 基线（ln 形态的驻点方程也是这一类）"},

      // ② exp 混合：x·e^x 这类高频形态
      {"exp_mul", "(1 + x)*exp(x)", "多项式×exp 的驻点方程"},
      {"exp_lin", "exp(x) - 2", "指数方程"},

      // ③ 根式：sqrt(x) - a·x 这类
      {"sqrt_lin", "1/2*a/sqrt(x) - 1", "含 sqrt 的有理式"},
      {"sqrt_poly", "-(1/2)/sqrt(x) + 2*x", "含 sqrt 的多项式"},

      // ④ 反三角
      {"asin", "1/sqrt(1 - x**2) + a", "asin 的导数方程"},
      {"acos", "-1/sqrt(1 - x**2) + a", "acos 的导数方程"},
      {"atan", "1/(1 + x**2) + a", "atan 的导数方程（有理式，预期安全）"},

      // ⑤ 底数与指数都含变量
      {"pow_var", "x**x*(1 + log(x))", "x^x 的驻点方程"},

      // ⑥ 双曲
      {"sinh", "cosh(x) - a", "双曲函数（预期同三角）"},

      // ⑦ 三角：已知崩溃，放最后
      {"trig_tan", "1 + tan(x)**2", "tan 的导数方程"},
      {"trig_sin", "cos(x) - 1/2", "简单三角方程"},
      {"trig_cos20", "20*cos(20*x)", "已确认栈溢出（历史事故）"},
  };
  return kCases;
}

void run(std::size_t i) {
  const Case& c = cases()[i];
  std::printf("[try ] %s   <%s>   %s\n", c.label, c.eq, c.note);
  std::fflush(stdout);
  try {
    const auto sol =
        SymEngine::solve(SymEngine::parse(c.eq), SymEngine::symbol("x"));
    std::printf("[ ok ] %s   -> %s\n", c.label, SymEngine::str(*sol).c_str());
  } catch (const std::exception& e) {
    std::printf("[throw] %s   -> %s\n", c.label, e.what());
  }
  std::fflush(stdout);
}

}  // namespace

int main(int argc, char** argv) {
  std::system("chcp 65001 > nul");

  if (argc < 2) {
    std::printf("===== SymEngine::solve 安全性实测用例 =====\n");
    const auto& cs = cases();
    for (std::size_t i = 0; i < cs.size(); ++i)
      std::printf("  %2zu  %-14s %s\n", i, cs[i].label, cs[i].note);
    std::printf("\n逐条执行：probe_solve_safety <序号>\n");
    return 0;
  }

  const std::size_t idx = static_cast<std::size_t>(std::atoi(argv[1]));
  if (idx >= cases().size()) {
    std::fprintf(stderr, "序号越界（0..%zu）\n", cases().size() - 1);
    return 2;
  }
  run(idx);
  return 0;
}
