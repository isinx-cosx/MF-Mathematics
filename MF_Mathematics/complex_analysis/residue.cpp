#include "residue.h"

#include <cmath>
#include <complex>
#include <limits>
#include <stdexcept>
#include <string>

#include <symengine/basic.h>
#include <symengine/functions.h>
#include <symengine/integer.h>
#include <symengine/parser.h>
#include <symengine/simplify.h>
#include <symengine/solve.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

#include "ca_internal.h"
#include "series.h"

namespace mf::complex_analysis {

namespace {
using mf::complex_analysis::detail::kPi;
using mf::complex_analysis::detail::eval_complex;

// RCP 表达式在复点的值。
std::complex<double> eval_rcp(const SymEngine::RCP<const SymEngine::Basic>& g,
                              std::complex<double> z) {
    const auto zs = SymEngine::symbol("z");
    const auto sub = g->subs({{zs, SymEngine::complex_double(z)}});
    return SymEngine::eval_complex_double(*sub);
}

// m 阶极点的留数公式(符号)。g 在 z0 处若为 0/0(未化简)返回 ok=false。
bool residue_pole_symbolic(const std::string& func, std::complex<double> z0,
                           long long m, std::complex<double>& out) {
    const auto zs = SymEngine::symbol("z");
    auto g = SymEngine::parse(func);
    g = SymEngine::mul(
        g, SymEngine::pow(SymEngine::sub(zs, SymEngine::complex_double(z0)),
                          SymEngine::integer(m)));
    g = SymEngine::simplify(g);
    for (long long i = 0; i < m - 1; ++i) g = SymEngine::diff(g, zs);
    // 检查 g 在 z0 处分母是否为零(0/0 或未消去极点)。
    try {
        SymEngine::RCP<const SymEngine::Basic> num, den;
        SymEngine::as_numer_denom(g, outArg(num), outArg(den));
        if (std::abs(eval_rcp(den, z0)) < 1e-9) return false;
        const std::complex<double> val = eval_rcp(num, z0) / eval_rcp(den, z0);
        if (!(std::isfinite(val.real()) && std::isfinite(val.imag()))) return false;
        double fact = 1.0;
        for (long long i = 2; i <= m - 1; ++i) fact *= (double)i;
        out = val / fact;
        return true;
    } catch (...) {
        return false;
    }
}

// 留数 = 1/(2πi) ∮ f dz(小圆围道,仅含 z0 一个奇点)。
std::complex<double> residue_contour(const std::string& func,
                                     std::complex<double> z0) {
    const double r = 0.25;
    const auto f = [&](double t) {
        const std::complex<double> z_t =
            z0 + r * std::complex<double>(std::cos(t), std::sin(t));
        const std::complex<double> dz =
            r * std::complex<double>(-std::sin(t), std::cos(t));
        return eval_complex(func, z_t) * dz;
    };
    const std::complex<double> integral =
        detail::simpson_c(f, 0.0, 2.0 * kPi, 2000);
    return integral / (2.0 * kPi * std::complex<double>(0.0, 1.0));
}

// 复围道积分 1/(2πi) ∮ f'/f dz → Z-P。
long long argument_principle_num(const std::string& func,
                                 std::complex<double> center, double radius) {
    const auto fp = [&](double t) {
        const std::complex<double> z_t =
            center + radius * std::complex<double>(std::cos(t), std::sin(t));
        const std::complex<double> dz =
            radius * std::complex<double>(-std::sin(t), std::cos(t));
        const std::complex<double> fz = eval_complex(func, z_t);
        if (std::abs(fz) > 1e-15)
            return detail::eval_diff_complex(func, z_t) / fz * dz;
        return std::complex<double>(0.0, 0.0);
    };
    const std::complex<double> zp =
        detail::simpson_c(fp, 0.0, 2.0 * kPi, 2000) /
        (2.0 * kPi * std::complex<double>(0.0, 1.0));
    return (long long)std::llround(zp.real());
}
}  // namespace

std::complex<double> residue(const std::string& func, std::complex<double> z0) {
    const long long m = pole_order(func, z0);
    if (m <= 0) {
        // 正则点:留数恒为 0。若 f(z0) 无法判定(0/0 垃圾值),回退围道积分。
        try {
            const std::complex<double> v = eval_complex(func, z0);
            if (std::isfinite(v.real()) && std::isfinite(v.imag()) &&
                std::abs(v) < 1e6)
                return {0.0, 0.0};
        } catch (...) {
        }
        return residue_contour(func, z0);
    }
    std::complex<double> sym;
    if (residue_pole_symbolic(func, z0, m, sym)) return sym;
    return residue_contour(func, z0);
}

std::complex<double> residue_theorem(
    const std::string& func,
    const std::vector<std::complex<double>>& singularities) {
    std::complex<double> total(0.0, 0.0);
    for (const auto& zk : singularities) total += residue(func, zk);
    return 2.0 * kPi * std::complex<double>(0.0, 1.0) * total;
}

double real_integral(const std::string& func, double a, double b) {
    const bool full_line =
        a == -std::numeric_limits<double>::infinity() &&
        b == std::numeric_limits<double>::infinity();
    if (!full_line) {
        // 有限区间:数值积分(复变量 x 上的实函数)。
        const auto x = SymEngine::symbol("x");
        const auto e = SymEngine::parse(func);
        auto f = [&](double t) {
            const auto sub = e->subs({{x, SymEngine::real_double(t)}});
            return SymEngine::eval_double(*sub);
        };
        const double h = (b - a) / 2000;
        double s = f(a) + f(b);
        for (int i = 1; i < 2000; ++i) {
            const double t = a + i * h;
            s += (i % 2 == 1) ? 4.0 * f(t) : 2.0 * f(t);
        }
        return s * h / 3.0;
    }
    // 全实轴:复化 x → z,求上半平面极点留数和。
    const auto xs = SymEngine::symbol("x");
    const auto zs = SymEngine::symbol("z");
    const std::string func_z = SymEngine::str(
        *SymEngine::parse(func)->subs({{xs, zs}}));
    SymEngine::RCP<const SymEngine::Basic> num, den;
    SymEngine::as_numer_denom(SymEngine::parse(func_z), outArg(num), outArg(den));
    const auto roots = SymEngine::solve(den, zs);
    if (!SymEngine::is_a<SymEngine::FiniteSet>(*roots))
        throw std::invalid_argument("无法求解分母零点");
    const auto& fs = SymEngine::down_cast<const SymEngine::FiniteSet&>(*roots);
    std::complex<double> total(0.0, 0.0);
    for (const auto& rt : fs.get_args()) {
        const std::complex<double> zk =
            SymEngine::eval_complex_double(*rt);
        if (zk.imag() > 1e-9) total += residue(func_z, zk);
    }
    const std::complex<double> result =
        2.0 * kPi * std::complex<double>(0.0, 1.0) * total;
    // 实值被积函数沿上半平面围道的积分为实数(虚部数值舍入)。
    return result.real();
}

long long argument_principle(const std::string& func,
                             std::complex<double> center, double radius) {
    return argument_principle_num(func, center, radius);
}

RoucheResult rouche_theorem(const std::string& f, const std::string& g,
                            std::complex<double> center, double radius) {
    RoucheResult r;
    double max_ratio = 0.0;
    r.condition_holds = true;
    for (int i = 0; i < 1000; ++i) {
        const double th = 2.0 * kPi * i / 1000;
        const std::complex<double> z_pt =
            center + radius * std::complex<double>(std::cos(th), std::sin(th));
        const double fv = std::abs(eval_complex(f, z_pt));
        const double gv = std::abs(eval_complex(g, z_pt));
        const double ratio = fv > 1e-15 ? gv / fv
                                        : std::numeric_limits<double>::infinity();
        max_ratio = std::max(max_ratio, ratio);
        if (gv >= fv) r.condition_holds = false;
    }
    r.max_ratio = max_ratio;
    r.zeros_f = argument_principle_num(f, center, radius);
    r.zeros_fg = argument_principle_num("(" + f + ") + (" + g + ")", center, radius);
    return r;
}

}  // namespace mf::complex_analysis
