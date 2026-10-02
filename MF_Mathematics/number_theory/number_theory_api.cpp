// number_theory_api.cpp — number_theory 包的 JSON 分发层。
//
// 将 24 个 action 注册进全局注册表:解析 JSON 参数 → 调用干净内核 →
// 序列化结果。加载本编译单元(DLL 或可执行文件)时通过静态对象自动注册。
//
// 结果约定:
//   标量            → {"isError":false,"value": <数字/bool>}
//   列表            → {"isError":false,"value": [ ... ]}
//   精确分数        → {"isError":false,"value": [分子, 分母]}
//   溢出降级浮点    → {"isError":false,"value": {"isApprox":true,"approx": <浮点>}}
//   出错            → {"isError":true,"value": "<错误消息>"}

#include "registry.hpp"
#include "json.hpp"

#include "arithmetic_functions.h"
#include "core_algorithms.h"
#include "modular_arithmetic.h"
#include "prime_sieves.h"
#include "continued_fractions.h"
#include "zeta_interface.h"

#include <cstdint>
#include <string>
#include <vector>

namespace {

using mf::json::Value;
using namespace mf::number_theory;  // 引入内核函数/结构

// ── 结果与参数辅助 ──────────────────────────────────────────────────────────

Value result_ok(Value v) {
    Value obj = Value::make_object();
    obj.set("isError", Value(false));
    obj.set("value", std::move(v));
    return obj;
}

Value result_err(const std::string& msg) {
    Value obj = Value::make_object();
    obj.set("isError", Value(true));
    obj.set("value", Value(msg));
    return obj;
}

long long get_int(const Value& args, const char* key) {
    if (!args.is_object() || !args.has(key))
        throw std::invalid_argument(std::string("缺少参数 ") + key);
    return args[key].as_int();
}

long long get_int_opt(const Value& args, const char* key, long long def) {
    if (!args.is_object() || !args.has(key)) return def;
    return args[key].as_int();
}

// 带上界的整数参数：这些参数直接决定循环次数/分配大小（试除法 ~√n、筛法、BSGS），
// 没有上限时一个大数就能让界面卡死。语义与 api_helpers.h 里的同名助手一致。
long long get_int_bounded(const Value& args, const char* key, long long lo, long long hi,
                          const char* what) {
    const long long v = get_int(args, key);
    if (v < lo || v > hi) {
        const std::string name = (what && *what) ? what : key;
        std::string msg = name + " 超出可计算范围 [" + std::to_string(lo) + ", " +
                          std::to_string(hi) + "]：收到 " + std::to_string(v);
        if (v > hi)
            msg += "。上限是为了避免单次计算卡住界面——这类参数直接决定循环次数"
                   "或分配大小，代价随它迅速增长；需要更大规模请分批做。";
        throw std::invalid_argument(msg);
    }
    return v;
}

long long get_int_opt_bounded(const Value& args, const char* key, long long def,
                              long long lo, long long hi, const char* what) {
    if (!args.is_object() || !args.has(key)) return def;
    return get_int_bounded(args, key, lo, hi, what);
}

double get_double(const Value& args, const char* key) {
    if (!args.is_object() || !args.has(key))
        throw std::invalid_argument(std::string("缺少参数 ") + key);
    return args[key].as_double();
}

std::vector<long long> get_int_array(const Value& args, const char* key) {
    if (!args.is_object() || !args.has(key) || !args[key].is_array())
        throw std::invalid_argument(std::string("缺少数组参数 ") + key);
    const Value& arr = args[key];
    std::vector<long long> out;
    for (std::size_t i = 0; i < arr.size(); ++i) out.push_back(arr.at(i).as_int());
    return out;
}

Value to_int_array(const std::vector<long long>& v) {
    Value arr = Value::make_array();
    for (long long x : v) arr.push_back(Value(x));
    return arr;
}

// 通用包装:解析 → 执行内核 → 序列化;任何异常转成 {"isError":true}
template <typename Fn>
mf::registry::Handler make_handler(Fn&& fn) {
    return [fn](const std::string& args_json) -> std::string {
        try {
            const Value args = Value::parse(args_json);
            return result_ok(fn(args)).to_string();
        } catch (const std::exception& e) {
            return result_err(e.what()).to_string();
        }
    };
}

// ── 精确分数 / 降级浮点 → JSON ──────────────────────────────────────────────

Value rational_to_value(const BernoulliResult& r) {
    if (r.is_approx) {
        Value obj = Value::make_object();
        obj.set("isApprox", Value(true));
        obj.set("approx", Value(r.approx));
        return obj;
    }
    Value arr = Value::make_array();
    arr.push_back(Value(r.num));
    arr.push_back(Value(r.den));
    return arr;
}

void register_all() {
    using mf::registry::register_function;

    // ── arithmetic_functions ──────────────────────────────────────────────
    register_function("euler_phi", make_handler([](const Value& args) {
        return Value(euler_phi(get_int_bounded(args, "n", -9223372036854775807, 1000000000000000, "n")));
    }));
    register_function("divisor_count", make_handler([](const Value& args) {
        return Value(divisor_count(get_int_bounded(args, "n", -9223372036854775807, 1000000000000000, "n")));
    }));
    register_function("divisor_sum", make_handler([](const Value& args) {
        return Value(divisor_sum(get_int_bounded(args, "n", -9223372036854775807, 1000000000000000, "n")));
    }));
    register_function("mobius", make_handler([](const Value& args) {
        return Value(mobius(get_int_bounded(args, "n", -9223372036854775807, 1000000000000000, "n")));
    }));
    register_function("mobius_prefix", make_handler([](const Value& args) {
        // 核心自己就有 n ≤ 1e7 的守卫（算术函数里那条），文案也是它给的；
        // 这里再加一层助手只会把文案换掉、并挡住套件里 2e7 那个用例的原始报错。
        return Value(mobius_prefix(get_int(args, "n")));
    }));

    // ── core_algorithms ────────────────────────────────────────────────────
    register_function("gcd", make_handler([](const Value& args) {
        return Value(gcd(get_int(args, "a"), get_int(args, "b")));
    }));
    register_function("extended_gcd", make_handler([](const Value& args) {
        const auto eg = extended_gcd(get_int(args, "a"), get_int(args, "b"));
        Value arr = Value::make_array();
        arr.push_back(Value(eg.g));
        arr.push_back(Value(eg.x));
        arr.push_back(Value(eg.y));
        return arr;
    }));
    register_function("mod_inverse", make_handler([](const Value& args) {
        return Value(mod_inverse(get_int(args, "a"), get_int(args, "m")));
    }));
    register_function("mod_pow", make_handler([](const Value& args) {
        return Value(mod_pow(get_int(args, "base"),
                             get_int(args, "exp"),
                             get_int(args, "mod")));
    }));

    // ── modular_arithmetic ─────────────────────────────────────────────────
    register_function("crt", make_handler([](const Value& args) {
        const auto residues = get_int_array(args, "residues");
        const auto moduli = get_int_array(args, "moduli");
        return Value(crt(residues, moduli));
    }));
    register_function("primitive_root", make_handler([](const Value& args) {
        return Value(primitive_root(get_int_bounded(args, "p", -9223372036854775807, 1000000000, "p")));
    }));
    register_function("discrete_log", make_handler([](const Value& args) {
        return Value(discrete_log(get_int(args, "g"),
                                  get_int(args, "h"),
                                  get_int_bounded(args, "p", -9223372036854775807, 1000000000000, "p")));
    }));

    // ── prime_sieves ───────────────────────────────────────────────────────
    register_function("eratosthenes", make_handler([](const Value& args) {
        return to_int_array(eratosthenes(get_int_bounded(args, "n", -9223372036854775807, 100000000, "n（筛法上限）")));
    }));
    register_function("segmented_sieve", make_handler([](const Value& args) {
        const long long n = get_int_bounded(args, "n", -9223372036854775807, 1000000000, "n");
        // 段长本身可以是任意小值（套件就用 13 来验分段正确性），真正决定代价的是
        // **段数**：每段都要用小素数筛一遍。所以这里限的是 n/seg，而不是把段长抬起来。
        const long long seg = get_int_opt_bounded(args, "segment_size", 100000, 1, 10000000, "segment_size");
        const long long segments = n / seg + 1;
        if (segments > 2000000)
            throw std::invalid_argument("分段筛的段数过多：" + std::to_string(segments) +
                                        " 段（n=" + std::to_string(n) + " / segment_size=" +
                                        std::to_string(seg) + "），上限 2000000。" +
                                        "请增大 segment_size 或减小 n。");
        const auto primes = segmented_sieve(n, seg);
        if (primes.size() > 50000) {
            Value obj = Value::make_object();
            obj.set("count", Value(static_cast<long long>(primes.size())));
            Value sample = Value::make_array();
            for (std::size_t i = 0; i < primes.size() && i < 20; ++i)
                sample.push_back(Value(primes[i]));
            sample.push_back(Value("..."));
            const std::size_t tail_start =
                primes.size() > 20 ? primes.size() - 20 : 0;
            for (std::size_t i = tail_start; i < primes.size(); ++i)
                sample.push_back(Value(primes[i]));
            obj.set("sample", std::move(sample));
            return obj;
        }
        return to_int_array(primes);
    }));
    register_function("is_prime", make_handler([](const Value& args) {
        return Value(is_prime(get_int(args, "n")));
    }));
    register_function("prime_factors", make_handler([](const Value& args) {
        const auto factors = prime_factors(get_int_bounded(args, "n", -9223372036854775807, 1000000000000000, "n"));
        Value arr = Value::make_array();
        for (const auto& [p, e] : factors) {
            Value pair = Value::make_array();
            pair.push_back(Value(p));
            pair.push_back(Value(e));
            arr.push_back(std::move(pair));
        }
        return arr;
    }));

    // ── continued_fractions ────────────────────────────────────────────────
    register_function("continued_fraction", make_handler([](const Value& args) {
        return to_int_array(continued_fraction(
            get_double(args, "x"), get_int_opt_bounded(args, "n_terms", 20, -9223372036854775807, 100000, "连分数项数")));
    }));
    register_function("convergents", make_handler([](const Value& args) {
        const auto convs = convergents(get_int_array(args, "frac"));
        Value arr = Value::make_array();
        for (const auto& c : convs) {
            Value v = Value::make_array();
            v.push_back(Value(c.p));
            v.push_back(Value(c.q));
            v.push_back(Value(c.approx));
            arr.push_back(std::move(v));
        }
        return arr;
    }));
    register_function("best_rational_approximation",
                      make_handler([](const Value& args) {
        const auto r = best_rational_approximation(
            get_double(args, "x"), get_int_opt_bounded(args, "max_denom", 1000000, -9223372036854775807, 1000000000, "分母上限"));
        Value v = Value::make_array();
        v.push_back(Value(r.p));
        v.push_back(Value(r.q));
        v.push_back(Value(r.approx));
        return v;
    }));

    // ── zeta_interface ─────────────────────────────────────────────────────
    register_function("euler_product", make_handler([](const Value& args) {
        return Value(euler_product(
            get_double(args, "s"), get_int_opt_bounded(args, "prime_limit", 100, -9223372036854775807, 10000000, "素数上限")));
    }));
    register_function("zeta_dirichlet_series", make_handler([](const Value& args) {
        return Value(zeta_dirichlet_series(
            get_double(args, "s"), get_int_opt_bounded(args, "n_terms", 10000, -9223372036854775807, 1000000, "级数项数")));
    }));
    register_function("dirichlet_l_function", make_handler([](const Value& args) {
        const double s = get_double(args, "s");
        const long long nt = get_int_opt_bounded(args, "n_terms", 1000, -9223372036854775807, 1000000, "级数项数");
        const long long cond = get_int_opt(args, "conductor", 4);
        std::vector<long long> chi;
        const std::vector<long long>* chi_ptr = nullptr;
        if (args.has("chi") && args["chi"].is_array()) {
            chi = get_int_array(args, "chi");
            chi_ptr = &chi;
        }
        return Value(dirichlet_l_function(s, chi_ptr, nt, cond));
    }));
    register_function("bernoulli_number", make_handler([](const Value& args) {
        return rational_to_value(bernoulli_number(get_int_bounded(args, "n", -9223372036854775807, 500, "伯努利数阶 n")));
    }));
    register_function("zeta_negative", make_handler([](const Value& args) {
        return rational_to_value(zeta_negative(get_int_bounded(args, "n", -9223372036854775807, 500, "ζ 自变量的阶 n")));
    }));
}

struct Registrar {
    Registrar() { register_all(); }
};
const Registrar g_number_theory_registrar;

}  // namespace
