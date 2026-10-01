#include "series.h"

#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

#include <symengine/basic.h>
#include <symengine/complex_double.h>
#include <symengine/constants.h>
#include <symengine/functions.h>
#include <symengine/integer.h>
#include <symengine/parser.h>
#include <symengine/real_double.h>
#include <symengine/simplify.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

#include "ca_internal.h"
#include "residue.h"

namespace mf::complex_analysis {

namespace {
using mf::complex_analysis::detail::kPi;
using mf::complex_analysis::detail::eval_complex;

// 泰勒系数 c_k = f^{(k)}(z0)/k!(符号计算,精确有理数)。
std::string coeff_at(const std::string& func, std::complex<double> z0,
                     long long k) {
    try {
        const auto zs = SymEngine::symbol("z");
        auto d = SymEngine::parse(func);
        for (long long i = 0; i < k; ++i) d = SymEngine::diff(d, zs);
        if (k > 0) d = SymEngine::div(d, SymEngine::factorial((unsigned long)k));
        SymEngine::RCP<const SymEngine::Basic> point;
        if (std::abs(z0.imag()) < 1e-12 && std::abs(z0.real() - std::round(z0.real())) < 1e-12)
            point = SymEngine::integer((long long)std::round(z0.real()));
        else if (std::abs(z0.imag()) < 1e-12)
            point = SymEngine::real_double(z0.real());
        else
            point = SymEngine::complex_double(z0);
        const auto sub = d->subs({{zs, point}});
        return SymEngine::str(*SymEngine::simplify(sub));
    } catch (...) {
        return "0";
    }
}

// 系数串是否需要整体加括号。
// SymEngine 把复数系数打印成 "a + b*I"/"a - b*I" 这类**含加减号**的形式。
// 若直接与幂拼成 power*coeff,加减号后面的部分就脱离乘法、退化成独立的
// 常数项 —— 输出的表达式在数学上是错的(这就是本条缺陷)。
bool needs_parens(const std::string& c) {
    // SymEngine 的加法打印形式带空格:"0.5 + 0.5*I"。
    if (c.find(' ') != std::string::npos) return true;
    // 无空格写法 a±b;跳过 "3.06e-17" 这类指数记号里的符号。
    for (std::size_t i = 1; i < c.size(); ++i) {
        if ((c[i] == '+' || c[i] == '-') && c[i - 1] != 'e' && c[i - 1] != 'E')
            return true;
    }
    return false;
}

// 单项格式化:系数 coeff × (z-center)^k。
// center 为空串 ⇒ 以 0 为中心,幂写作 z**k;否则中心点已代入数值。
std::string format_term(const std::string& coeff, long long k,
                        const std::string& center) {
    if (coeff == "0" || coeff == "0.0") return "";
    if (k == 0) return coeff;  // 常数项本身就是完整的加数,无需加括号
    std::string power;
    if (center.empty()) {
        power = (k == 1) ? "z" : "z**" + std::to_string(k);
    } else {
        power = (k == 1) ? "(z - " + center + ")"
                         : "(z - " + center + ")**" + std::to_string(k);
    }
    if (coeff == "1") return power;
    if (coeff == "-1") return "-" + power;
    if (needs_parens(coeff)) return power + "*(" + coeff + ")";
    const std::size_t pos = coeff.find('/');
    if (pos != std::string::npos) {
        const std::string num = coeff.substr(0, pos);
        const std::string den = coeff.substr(pos + 1);
        if (num == "1") return power + "/" + den;
        if (num == "-1") return "-" + power + "/" + den;
        return power + "*" + num + "/" + den;
    }
    return power + "*" + coeff;
}

// 展开中心必须**代入数值**(此前硬编码字面量 "z0",输出不是 z 的函数;
// 同文件的 format_z0() 本来就是对的,laurent_series 已在用)。
std::string format_z0(std::complex<double> z0) {
    if (std::abs(z0.imag()) < 1e-12) return std::to_string(z0.real());
    if (std::abs(z0.real()) < 1e-12) return std::to_string(z0.imag()) + "*I";
    return std::to_string(z0.real()) + "+" + std::to_string(z0.imag()) + "*I";
}

// 系数串是否已经退化成 SymEngine 的复无穷 / 非数。
bool is_degenerate_coeff(const std::string& c) {
    return c.find("zoo") != std::string::npos ||
           c.find("nan") != std::string::npos ||
           c.find("inf") != std::string::npos;
}
}  // namespace

std::string taylor_series(const std::string& func, std::complex<double> z0,
                          long long n) {
    // 极点 / 本性奇点处不存在泰勒展开,必须明确拒绝:
    // 此前 "1/z" @ z0=0 会返回 "zoo + z*zoo + ..."(sympy 的复无穷)。
    const SingularityResult cls = singularity_classify(func, z0);
    if (cls.classification == "pole" || cls.classification == "essential") {
        throw std::invalid_argument(
            "taylor_series: " + func + " 在 z0 处" +
            (cls.classification == "pole" ? "为极点" : "为本性奇点") +
            ",不存在泰勒展开");
    }
    const std::string center =
        (std::abs(z0) < 1e-12) ? std::string() : format_z0(z0);
    std::string out;
    for (long long k = 0; k <= n; ++k) {
        const std::string coeff = coeff_at(func, z0, k);
        if (is_degenerate_coeff(coeff)) {
            throw std::invalid_argument(
                "taylor_series: " + func + " 在 z0 处的泰勒系数不收敛");
        }
        const std::string term = format_term(coeff, k, center);
        if (term.empty()) continue;
        if (!out.empty()) out += (term[0] == '-') ? " - " : " + ";
        out += (term[0] == '-') ? term.substr(1) : term;
    }
    return out.empty() ? "0" : out;
}

std::string laurent_series(const std::string& func, std::complex<double> z0,
                           long long n) {
    const SingularityResult cls = singularity_classify(func, z0);
    const long long m = (cls.classification == "pole") ? cls.pole_order : 1;
    const std::string base = "(z - " + format_z0(z0) + ")";
    const auto fmt_cx = [](std::complex<double> v) -> std::string {
        const double re = v.real(), im = v.imag();
        if (std::abs(im) < 1e-8) return std::to_string(re);
        if (std::abs(re) < 1e-8) return std::to_string(im) + "*I";
        return std::to_string(re) + (im < 0 ? "" : "+") + std::to_string(im) + "*I";
    };
    // 洛朗系数 a_e = Res[ f/(z-z0)^{e+1} ](e ≥ 0)或 Res[ f·(z-z0)^{-e-1} ](e < 0)。
    // 数值围道留数法,避免 SymEngine 不约 (z-z0) 因子导致的 0/0/NaN。
    std::string out;
    for (long long e = -m; e <= n; ++e) {
        std::string integrand;
        if (e >= 0) {
            integrand = func + "/" + base + "**" + std::to_string(e + 1);
        } else if (e == -1) {
            integrand = func;
        } else {
            integrand = func + "*" + base + "**" + std::to_string(-e - 1);
        }
        std::complex<double> a{0.0, 0.0};
        try {
            a = residue(integrand, z0);
        } catch (...) {
        }
        if (std::abs(a) < 1e-8) continue;
        std::string term;
        if (e < 0) {
            const std::string den =
                (e == -1) ? base : base + "**" + std::to_string(-e);
            term = fmt_cx(a) + "/" + den;
        } else if (e == 0) {
            term = fmt_cx(a);
        } else {
            term = fmt_cx(a) + "*" + base + "**" + std::to_string(e);
        }
        if (!out.empty()) out += " + ";
        out += term;
    }
    return out.empty() ? "0" : out;
}

SingularityResult singularity_classify(const std::string& func,
                                       std::complex<double> z0) {
    SingularityResult r;
    // 直接求值:若有限且量级合理 → 正则点(避免 1/0 的垃圾大值)。
    try {
        const std::complex<double> v = eval_complex(func, z0);
        if (std::isfinite(v.real()) && std::isfinite(v.imag()) &&
            std::abs(v) < 1e6) {
            r.classification = "regular";
            return r;
        }
    } catch (...) {
    }

    // 逐层采样 max|f|,按 log-log 斜率估计极点阶数。
    const double epsilons[3] = {1e-2, 1e-4, 1e-6};
    double max_abs[3] = {0.0, 0.0, 0.0};
    for (int ei = 0; ei < 3; ++ei) {
        for (int k = 0; k < 8; ++k) {
            const double a = 2.0 * kPi * k / 8;
            const std::complex<double> z =
                z0 + epsilons[ei] * std::complex<double>(std::cos(a), std::sin(a));
            try {
                const std::complex<double> v = eval_complex(func, z);
                const double av = std::abs(v);
                if (!(std::isfinite(av))) {
                    r.classification = "essential";
                    return r;
                }
                max_abs[ei] = std::max(max_abs[ei], av);
            } catch (...) {
                r.classification = "essential";
                return r;
            }
        }
    }

    // 无显著增长 → 可去奇点(按相对增长判定,避免弱极点被绝对阈值误判)。
    if (max_abs[2] < 10.0 * max_abs[0] + 1.0) {
        r.classification = "removable";
        return r;
    }
    // log-log 斜率(极点阶数估计)。
    const double slope =
        std::log(max_abs[2] / max_abs[0]) / std::log(epsilons[0] / epsilons[2]);
    const double slope12 =
        std::log(max_abs[1] / max_abs[0]) / std::log(epsilons[0] / epsilons[1]);
    if (std::abs(slope - slope12) > 0.3) {
        r.classification = "essential";
        return r;
    }
    r.classification = "pole";
    r.pole_order = (long long)std::lround(slope);
    if (r.pole_order < 1) {
        r.classification = "essential";
        r.pole_order = 0;
    }
    return r;
}

long long pole_order(const std::string& func, std::complex<double> z0) {
    const SingularityResult cls = singularity_classify(func, z0);
    return (cls.classification == "pole") ? cls.pole_order : 0;
}

}  // namespace mf::complex_analysis
