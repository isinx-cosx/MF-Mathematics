#include <iostream>
#include <vector>
#include <stdexcept>
#include <cmath>
#include <algorithm>

double dot(const std::vector<double>& u, const std::vector<double>& v){
    double sum = 0;
    if (u.size() != v.size()) throw std::invalid_argument("向量维数不一致");;
    if (u.size() == 0 || v.size() == 0) throw std::invalid_argument("有一个向量为空！");
    for (size_t i = 0; i < u.size(); i++){
        sum += u[i] * v[i];
    }
    return sum;
}

double norm(const std::vector<double>& v) {
    return std::sqrt(dot(v, v));
}

double angle(const std::vector<double>& u, const std::vector<double>& v){
    double nu = norm(u);
    double nv = norm(v);
    double d = dot(u, v);
    if (nu < 1e-6 || nv <1e-6) throw std::invalid_argument("其中一个向量的模长为0");
    double cos = d / (nu * nv);
    cos = std::clamp(cos, -1.0, 1.0);
    return std::acos(cos);
}

// 测试辅助：断言两个 double 在容差内相等
bool check_close(const char* name, double got, double expect, double tol = 1e-9) {
    if (std::abs(got - expect) <= tol) {
        std::cout << "[PASS] " << name << " = " << got << std::endl;
        return true;
    }
    std::cout << "[FAIL] " << name << "：期望 " << expect << "，实际 " << got << std::endl;
    return false;
}

int main() {
    system("chcp 65001 > nul");
    double a = dot({1, 2, 3}, {4, 5, 6});
    double b = dot({1, -2, 3}, {-4, 5, -6});
    double c = dot({0, 0, 0}, {1, 2, 3});
    double d = dot({0.1, 0.2, 0.3}, {0.4, 0.5, 0.6});
    double e = dot({5}, {7});
    std::cout << a << std::endl;
    std::cout << b << std::endl;
    std::cout << c << std::endl;
    std::cout << d << std::endl;
    std::cout << e << std::endl;
    try {
        double f = dot({}, {});
        std::cout << f << std::endl;
    } catch (const std::exception& e) {
        std::cout << "错误: " << e.what() << std::endl;   // 打印"向量维数不一致"
    }
    try {
        double g = dot({6, 5}, {5});
        std::cout << g << std::endl;
    } catch (const std::exception& e) {
        std::cout << "错误: " << e.what() << std::endl;   // 打印"向量维数不一致"
    }

    // ── norm 测试 ──
    std::cout << "\n=== norm 测试 ===" << std::endl;
    check_close("norm({3,4}) = 5", norm({3, 4}), 5.0);
    check_close("norm({1,2,2}) = 3", norm({1, 2, 2}), 3.0);

    // ── angle 测试 ──
    std::cout << "=== angle 测试 ===" << std::endl;
    const double PI = std::acos(-1.0);   // 可移植地取 π
    check_close("angle((1,0),(0,1)) = π/2", angle({1, 0}, {0, 1}), PI / 2);
    check_close("angle((1,0),(1,0)) = 0",  angle({1, 0}, {1, 0}), 0.0);
    check_close("angle((1,0),(-1,0)) = π", angle({1, 0}, {-1, 0}), PI);

    return 0;
}