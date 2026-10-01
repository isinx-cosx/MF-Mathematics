#include "product_measure.h"

#include <cmath>
#include <exception>
#include <limits>
#include <string>

#include "../calculus/integrals.h"

namespace mf::measure_theory {

namespace {

// 一次迭代积分的求值结果。
//
// 被积函数在积分区域上无界/不绝对可积时,积分层会**如实拒绝求值**(抛 domain_error,
// 见 calculus/integrals.cpp 的有界性检查)。对 Fubini 判定来说这不是"调用失败",而是
// 一条关键信息,所以要记录下来交给调用方,而不是让它穿出去变成一个错误。
struct IteratedValue {
    double value = std::numeric_limits<double>::quiet_NaN();
    bool evaluable = false;
    std::string why;
};

IteratedValue eval_iterated(const std::string& expr, const std::string& outer,
                            const std::string& inner, const std::string& o_lo,
                            const std::string& o_hi, const std::string& i_lo,
                            const std::string& i_hi) {
    IteratedValue r;
    try {
        const double v =
            mf::calculus::integrate_double(expr, outer, inner, o_lo, o_hi, i_lo, i_hi);
        if (std::isfinite(v)) {
            r.value = v;
            r.evaluable = true;
        } else {
            r.why = "迭代积分在数值上不收敛(求值返回非有限值)";
        }
    } catch (const std::exception& e) {
        r.why = e.what();
    } catch (...) {
        r.why = "迭代积分求值抛出未知异常";
    }
    return r;
}

}  // namespace

double product_measure(double mu_factor, double nu_factor, double ax, double bx,
                       double ay, double by) {
    return mu_factor * std::abs(bx - ax) * nu_factor * std::abs(by - ay);
}

FubiniResult fubini_theorem(const std::string& expr, double xa, double xb,
                            double ya, double yb) {
    FubiniResult r;
    const auto sx = [](double v) { return std::to_string(v); };
    // 先 x 后 y:外层 y 在 [ya,yb],内层 x 在 [xa,xb]。
    const IteratedValue xy =
        eval_iterated(expr, "y", "x", sx(ya), sx(yb), sx(xa), sx(xb));
    // 先 y 后 x:外层 x 在 [xa,xb],内层 y 在 [ya,yb]。
    const IteratedValue yx =
        eval_iterated(expr, "x", "y", sx(xa), sx(xb), sx(ya), sx(yb));

    r.xy_order = xy.value;   // 求不出来时保持 NaN(序列化为 null)
    r.yx_order = yx.value;
    r.difference = std::abs(xy.value - yx.value);   // NaN 会传播
    r.fubini_holds = r.difference < 1e-6;           // 与 NaN 比较为 false

    if (xy.evaluable && yx.evaluable) {
        r.iterated_integrals_evaluated = true;
        r.note = r.fubini_holds
                     ? "两个迭代积分都可求值且相等,判定 Fubini 成立"
                     : "两个迭代积分都可求值但不相等,判定 Fubini 失效";
        return r;
    }

    // 迭代积分求不出来 —— 这本身就是结论,不是调用失败:
    // f 在积分区域上无界/不绝对可积 ⇒ Fubini 定理「f 绝对可积」的前提不满足 ⇒
    // 定理不适用,两个迭代积分不必相等,故判定 Fubini 失效。
    // 经典例子:(x-y)/(x+y)^3 在 [0,1]² 上两个迭代积分分别为 +0.5 与 -0.5。
    r.iterated_integrals_evaluated = false;
    r.fubini_holds = false;
    const std::string& why = xy.evaluable ? yx.why : xy.why;
    r.note = "被积函数在积分区域上无界/不绝对可积(迭代积分无法求值):Fubini 定理"
             "「f 绝对可积」的前提不满足,定理不适用,两个迭代积分不必相等 ⇒ 判定 "
             "Fubini 失效(定性结论,不是调用失败)。积分层原始信息: " + why;
    return r;
}

}  // namespace mf::measure_theory
