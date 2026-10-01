#include "conformal.h"

#include <cctype>
#include <cmath>
#include <stdexcept>

#include "ca_internal.h"

namespace mf::complex_analysis {

namespace {
using mf::complex_analysis::detail::kPi;

// 将独立虚数单位 i/I 归一为 SymEngine 的 I。
std::string normalize_i(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    for (std::size_t i = 0; i < s.size(); ++i) {
        const char c = s[i];
        if (c == 'I' || c == 'i') {
            const bool prev_alpha =
                i > 0 && (std::isalnum((unsigned char)s[i - 1]) || s[i - 1] == '_');
            const bool next_alpha =
                i + 1 < s.size() &&
                (std::isalnum((unsigned char)s[i + 1]) || s[i + 1] == '_');
            if (!prev_alpha && !next_alpha) {
                out += 'I';
                continue;
            }
        }
        out += c;
    }
    return out;
}

std::complex<double> eval_complex_norm(const std::string& func,
                                       std::complex<double> z) {
    return detail::eval_complex(normalize_i(func), z);
}
}  // namespace

ConformalResult is_conformal(const std::string& func, std::complex<double> z) {
    ConformalResult r;
    r.derivative = detail::eval_diff_complex(normalize_i(func), z);
    r.is_conformal = std::abs(r.derivative) > 1e-15;
    return r;
}

std::string riemann_mapping(const std::string& region) {
    std::string key = region;
    for (char& c : key) {
        if (c == ' ') c = '_';
        c = (char)::tolower((unsigned char)c);
    }
    if (key == "unit_disk") return "f(z) = z";
    if (key == "upper_half_plane")
        return "f(z) = (z - I)/(z + I)（Cayley 变换）";
    if (key == "right_half_plane") return "f(z) = (z - 1)/(z + 1)";
    if (key == "slit_disk") return "f(z) = (√z + 1)²/(√z - 1)²";
    if (key == "first_quadrant") return "f(z) = z² → Cayley 变换";
    throw std::invalid_argument("不支持的区域: " + region);
}

std::vector<BoundarySample> boundary_correspondence(const std::string& func,
                                                    const std::string& region) {
    std::string rl = region;
    for (char& c : rl) c = (char)::tolower((unsigned char)c);
    const bool upper = rl.find("upper") != std::string::npos &&
                       rl.find("half") != std::string::npos;
    std::vector<BoundarySample> samples;
    if (upper) {
        for (int k = 0; k < 10; ++k) {
            const double t = -5.0 + 10.0 * k / 9.0;
            BoundarySample s;
            s.z = {t, 0.0};
            s.w = eval_complex_norm(func, s.z);
            samples.push_back(s);
        }
        for (int k = 0; k < 10; ++k) {
            const double th = kPi * k / 9.0;
            BoundarySample s;
            s.z = 10.0 * std::complex<double>(std::cos(th), std::sin(th));
            s.w = eval_complex_norm(func, s.z);
            samples.push_back(s);
        }
    } else {
        for (int k = 0; k < 16; ++k) {
            const double th = 2.0 * kPi * k / 16;
            BoundarySample s;
            s.z = std::complex<double>(std::cos(th), std::sin(th));
            s.w = eval_complex_norm(func, s.z);
            samples.push_back(s);
        }
    }
    return samples;
}

}  // namespace mf::complex_analysis
