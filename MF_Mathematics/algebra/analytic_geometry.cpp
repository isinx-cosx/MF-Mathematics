#include "analytic_geometry.h"

#include <charconv>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>

namespace mf::algebra {

namespace {

const double kPi = 3.14159265358979323846;

// Python str(float) 风格:最短往返表示,整数值补 ".0"(如 2.0 → "2.0")。
std::string fmt(double d) {
    if (d != d) return "nan";
    if (d == std::numeric_limits<double>::infinity()) return "inf";
    if (d == -std::numeric_limits<double>::infinity()) return "-inf";
    char buf[40];
    const auto res = std::to_chars(buf, buf + sizeof(buf), d,
                                   std::chars_format::general);
    std::string s(buf, res.ptr);
    if (s.find('.') == std::string::npos && s.find('e') == std::string::npos &&
        s.find('E') == std::string::npos) {
        s += ".0";
    }
    return s;
}

// 有符号形式的常数项:"+ 3.0" 或 "- 3.0"
std::string signed_const(double b) {
    return b >= 0 ? "+ " + fmt(b) : "- " + fmt(std::abs(b));
}

std::string slope_intercept_str(double k, double b) {
    return b >= 0 ? "y = " + fmt(k) + "x + " + fmt(b)
                  : "y = " + fmt(k) + "x - " + fmt(std::abs(b));
}

std::string general_str(double k, double b) {
    return b >= 0 ? fmt(k) + "x - y + " + fmt(b) + " = 0"
                  : fmt(k) + "x - y - " + fmt(std::abs(b)) + " = 0";
}

}  // namespace

double distance(Point p1, Point p2) {
    const double dx = p2.x - p1.x;
    const double dy = p2.y - p1.y;
    return std::round(std::sqrt(dx * dx + dy * dy) * 1e10) / 1e10;
}

Point midpoint(Point p1, Point p2) {
    return {(p1.x + p2.x) / 2.0, (p1.y + p2.y) / 2.0};
}

LineFromPoints line_from_points(Point p1, Point p2) {
    LineFromPoints res;
    res.two_point = "(y - " + fmt(p1.y) + ")/(x - " + fmt(p1.x) + ") = (" +
                    fmt(p2.y) + " - " + fmt(p1.y) + ")/(" + fmt(p2.x) + " - " +
                    fmt(p1.x) + ")";
    if (p1.x == p2.x) {
        res.slope = std::numeric_limits<double>::infinity();
        res.point_slope = "不存在（垂直于x轴）";
        res.slope_intercept = "不存在（垂直于x轴）";
        res.general = "x - " + fmt(p1.x) + " = 0  或  x = " + fmt(p1.x);
    } else {
        const double k = (p2.y - p1.y) / (p2.x - p1.x);
        const double b = p1.y - k * p1.x;
        res.slope = k;
        res.point_slope =
            "y - " + fmt(p1.y) + " = " + fmt(k) + "(x - " + fmt(p1.x) + ")";
        res.slope_intercept = slope_intercept_str(k, b);
        res.general = general_str(k, b);
    }
    return res;
}

LineSlopeIntercept line_from_slope_intercept(double k, double b) {
    LineSlopeIntercept res;
    res.slope = k;
    res.y_intercept = b;
    res.slope_intercept = slope_intercept_str(k, b);
    res.general = general_str(k, b);
    res.points[0] = {0.0, b};
    res.points[1] = {1.0, k + b};
    return res;
}

LinePointSlope line_from_point_slope(Point p, double k) {
    LinePointSlope res;
    const double b = p.y - k * p.x;
    res.point_slope = "y - " + fmt(p.y) + " = " + fmt(k) + "(x - " + fmt(p.x) + ")";
    res.slope_intercept = "y = " + fmt(k) + "x " + signed_const(b);
    res.general = fmt(k) + "x - y " + signed_const(b) + " = 0";
    res.slope = k;
    res.point = p;
    return res;
}

LineIntercepts line_from_intercepts(double a, double b) {
    if (a == 0.0 || b == 0.0) throw std::invalid_argument("截距不能为零");
    LineIntercepts res;
    const double k = -b / a;
    res.intercept_form = "x/" + fmt(a) + " + y/" + fmt(b) + " = 1";
    res.slope_intercept = slope_intercept_str(k, b);
    res.general = "(" + fmt(b) + ")x + (" + fmt(a) + ")y - " + fmt(a * b) + " = 0";
    res.x_intercept = a;
    res.y_intercept = b;
    res.slope = k;
    return res;
}

LineGeneral line_general(double A, double B, double C) {
    if (A == 0.0 && B == 0.0)
        throw std::invalid_argument("A 和 B 不能同时为 0");
    LineGeneral res;
    res.general = fmt(A) + "x + " + fmt(B) + "y + " + fmt(C) + " = 0";
    if (B != 0.0) {
        const double k = -A / B;
        const double b = -C / B;
        res.slope = k;
        res.slope_intercept = slope_intercept_str(k, b);
    } else {
        res.slope = std::numeric_limits<double>::infinity();
        res.slope_intercept =
            "x = " + fmt(std::round(-C / A * 1e4) / 1e4);
    }
    res.has_x_intercept = (A != 0.0);
    res.x_intercept = A != 0.0 ? -C / A : 0.0;
    res.has_y_intercept = (B != 0.0);
    res.y_intercept = B != 0.0 ? -C / B : 0.0;
    return res;
}

CircleStandard circle_standard(Point center, double r) {
    if (r <= 0.0) throw std::invalid_argument("半径必须大于 0");
    CircleStandard res;
    const double h = center.x;
    const double k = center.y;
    res.standard =
        "(x - " + fmt(h) + ")² + (y - " + fmt(k) + ")² = " + fmt(r) + "²";
    const double D = -2 * h;
    const double E = -2 * k;
    const double F = h * h + k * k - r * r;
    res.general =
        "x² + y² + " + fmt(D) + "x + " + fmt(E) + "y + " + fmt(F) + " = 0";
    res.center = center;
    res.radius = r;
    res.diameter = 2 * r;
    res.circumference = 2 * kPi * r;
    res.area = kPi * r * r;
    return res;
}

CircleGeneral circle_general(double D, double E, double F) {
    CircleGeneral res;
    const double h = -D / 2;
    const double k = -E / 2;
    const double r2 = (D * D + E * E - 4 * F) / 4;
    res.center = {h, k};
    res.r_squared = r2;
    res.general =
        "x² + y² + " + fmt(D) + "x + " + fmt(E) + "y + " + fmt(F) + " = 0";
    if (r2 < 0) {
        res.is_imaginary = true;
        res.standard = "(x + " + fmt(D) + "/2)² + (y + " + fmt(E) + "/2)² = " + fmt(r2);
        return res;
    }
    res.radius = std::sqrt(r2);
    res.standard = "(x + " + fmt(D) + "/2)² + (y + " + fmt(E) + "/2)² = " + fmt(res.radius) + "²";
    return res;
}

/* ── 圆锥曲线 ──────────────────────────────────────────────────────────────
 * 都取标准位置（中心/顶点在原点），与 circle_standard 一样给出标准式、一般式与
 * 焦点/准线/离心率等几何量。a、b 的次序不影响结果：哪边大哪边就是长（实）轴。
 */

EllipseInfo ellipse_standard(double a, double b) {
    if (a <= 0.0 || b <= 0.0) throw std::invalid_argument("椭圆参数 a、b 必须大于 0");
    EllipseInfo res;
    res.is_vertical = b > a;
    res.a = std::max(a, b);   // 长半轴
    res.b = std::min(a, b);   // 短半轴
    const double A2 = a * a, B2 = b * b;
    // c 必须用**长半轴/短半轴**算，不能用输入的 a、b：
    // 传 a=3, b=5（竖椭圆）时 A2-B2 < 0，会被 max(0,…) 截成 c=0、e=0、准线 "±inf"，
    // 而标准椭圆 a=5, b=3 却算得对 —— 同一图形因书写顺序不同给出两种答案。
    res.c = std::sqrt(std::max(0.0, res.a * res.a - res.b * res.b));
    res.eccentricity = res.c / res.a;
    res.vertex_major = res.a;
    res.vertex_minor = res.b;
    res.area = kPi * res.a * res.b;

    // 标准式写在输入的 a、b 上（x²/a² + y²/b² = 1），保序，便于和题目对照
    res.standard = "x²/" + fmt(a * a) + " + y²/" + fmt(b * b) + " = 1";
    res.general = fmt(B2) + "x² + " + fmt(A2) + "y² - " + fmt(A2 * B2) + " = 0";

    if (res.is_vertical) {          // 长轴沿 y → 焦点在 (0, ±c)
        res.focus1_x = 0.0; res.focus1_y = res.c;
        res.focus2_x = 0.0; res.focus2_y = -res.c;
        res.directrix = "y = ±" + fmt(res.a / res.eccentricity);
    } else {                        // 长轴沿 x → 焦点在 (±c, 0)
        res.focus1_x = res.c; res.focus1_y = 0.0;
        res.focus2_x = -res.c; res.focus2_y = 0.0;
        res.directrix = "x = ±" + fmt(res.a / res.eccentricity);
    }
    return res;
}

HyperbolaInfo hyperbola_standard(double a, double b) {
    if (a <= 0.0 || b <= 0.0) throw std::invalid_argument("双曲线参数 a、b 必须大于 0");
    HyperbolaInfo res;
    // 约定：x²/a² - y²/b² = 1 为"横轴在 x"；若传入顺序相反则视为竖轴
    res.is_vertical = false;
    res.a = a;
    res.b = b;
    res.c = std::sqrt(a * a + b * b);
    res.eccentricity = res.c / a;
    res.standard = "x²/" + fmt(a * a) + " - y²/" + fmt(b * b) + " = 1";
    res.general = fmt(b * b) + "x² - " + fmt(a * a) + "y² - " + fmt(a * a * b * b) + " = 0";
    res.focus1_x = res.c; res.focus1_y = 0.0;
    res.focus2_x = -res.c; res.focus2_y = 0.0;
    const double k = b / a;   // 渐近线 y = ±(b/a)x
    res.asymptote1 = "y = " + fmt(k) + "x";
    res.asymptote2 = "y = -" + fmt(k) + "x";
    res.directrix = "x = ±" + fmt(a * a / res.c);
    return res;
}

ParabolaInfo parabola_standard(double p, const std::string& axis) {
    if (p == 0.0) throw std::invalid_argument("抛物线参数 p 不能为 0");
    ParabolaInfo res;
    res.p = p;
    res.axis = (axis == "y" || axis == "Y") ? "y" : "x";
    res.latus_rectum = std::fabs(2 * p);
    // 焦点在对称轴上，离顶点 p/2；准线在另一侧
    if (res.axis == "x") {
        res.standard = "y² = " + fmt(2 * p) + "x";
        res.general = "y² - " + fmt(2 * p) + "x = 0";
        res.focus_x = p / 2; res.focus_y = 0.0;
        res.directrix = "x = " + fmt(-p / 2);
        res.opening = p > 0 ? "右" : "左";
    } else {
        res.standard = "x² = " + fmt(2 * p) + "y";
        res.general = "x² - " + fmt(2 * p) + "y = 0";
        res.focus_x = 0.0; res.focus_y = p / 2;
        res.directrix = "y = " + fmt(-p / 2);
        res.opening = p > 0 ? "上" : "下";
    }
    return res;
}

}  // namespace mf::algebra
