#include <cstdio>
#include "calculus/integrals.h"
int main() {
    std::printf("∫√x        = %s\n", mf::calculus::integrate_indefinite("sqrt(x)", "x").c_str());
    std::printf("∫x·sin(x)  = %s\n", mf::calculus::integrate_indefinite("x*sin(x)", "x").c_str());
    std::printf("∫x·cos(x)  = %s\n", mf::calculus::integrate_indefinite("x*cos(x)", "x").c_str());
    std::printf("∫x·eˣ      = %s\n", mf::calculus::integrate_indefinite("x*exp(x)", "x").c_str());
    std::printf("∫1/x       = %s\n", mf::calculus::integrate_indefinite("1/x", "x").c_str());
    std::printf("∫x²·sin(x) = %s\n", mf::calculus::integrate_indefinite("x**2*sin(x)", "x").c_str());
    std::printf("∫sin(2x)   = %s\n", mf::calculus::integrate_indefinite("sin(2*x)", "x").c_str());
    std::printf("∫cos(2x)   = %s\n", mf::calculus::integrate_indefinite("cos(2*x)", "x").c_str());
    std::printf("∫1/(x+1)   = %s\n", mf::calculus::integrate_indefinite("1/(x+1)", "x").c_str());
    std::printf("∫1/x²      = %s\n", mf::calculus::integrate_indefinite("1/x**2", "x").c_str());
    return 0;
}
