#include "integrals_app.h"

#include <cmath>

#include <symengine/basic.h>
#include <symengine/derivative.h>
#include <symengine/parser.h>
#include <symengine/printers.h>

#include "integrals.h"

namespace mf::calculus {

namespace {
// √(1 + (f')²) 的被积表达式。
std::string arc_integrand(const std::string& f, const std::string& var) {
    const auto d = SymEngine::diff(SymEngine::parse(f), SymEngine::symbol(var));
    return "sqrt(1 + (" + SymEngine::str(*d) + ")**2)";
}
}  // namespace

double area_between(const std::string& f, const std::string& g,
                    const std::string& var, double a, double b) {
    const std::string diff = "((" + f + ") - (" + g + "))**2";
    const std::string integrand = "sqrt(" + diff + ")";
    return integrate_numeric(integrand, var, a, b);
}

double volume_disk(const std::string& f, const std::string& var, double a,
                   double b) {
    const std::string integrand = "3.141592653589793*(" + f + ")**2";
    return integrate_numeric(integrand, var, a, b);
}

double volume_shell(const std::string& f, const std::string& var, double a,
                    double b) {
    const std::string integrand = "2*3.141592653589793*" + var + "*(" + f + ")";
    return integrate_numeric(integrand, var, a, b);
}

double arc_length(const std::string& f, const std::string& var, double a,
                  double b) {
    return integrate_numeric(arc_integrand(f, var), var, a, b);
}

}  // namespace mf::calculus
