// analytic_geometry.h — 平面解析几何:两点间距离、中点、直线与圆方程。
//
// 直线/圆方程返回的字符串中,数字用 Python str(float) 风格格式化
// (整数值带 ".0",如 "1.0"),与 Python 的 f-string 对齐。

#pragma once

#include <string>

#include "../mf_export.h"

namespace mf::algebra {

struct Point {
    double x;
    double y;
};

// 两点间欧氏距离(四舍五入到 10 位小数)。
MF_API double distance(Point p1, Point p2);
// 两点中点。
MF_API Point midpoint(Point p1, Point p2);

// 两点式直线:斜率、各形式方程字符串。
struct LineFromPoints {
    std::string two_point;
    std::string point_slope;
    std::string slope_intercept;
    std::string general;
    double slope = 0.0;  // 垂直时为 +inf
};
MF_API LineFromPoints line_from_points(Point p1, Point p2);

// 斜截式 y = kx + b。
struct LineSlopeIntercept {
    std::string slope_intercept;
    std::string general;
    Point points[2];  // (0, b) 与 (1, k+b)
    double slope = 0.0;
    double y_intercept = 0.0;
};
MF_API LineSlopeIntercept line_from_slope_intercept(double k, double b);

// 点斜式 y - y₀ = k(x - x₀)。
struct LinePointSlope {
    std::string point_slope;
    std::string slope_intercept;
    std::string general;
    double slope = 0.0;
    Point point;
};
MF_API LinePointSlope line_from_point_slope(Point p, double k);

// 截距式 x/a + y/b = 1。a 或 b 为零抛 std::invalid_argument。
struct LineIntercepts {
    std::string intercept_form;
    std::string slope_intercept;
    std::string general;
    double x_intercept = 0.0;
    double y_intercept = 0.0;
    double slope = 0.0;
};
MF_API LineIntercepts line_from_intercepts(double a, double b);

// 一般式 Ax + By + C = 0。A、B 同时为零抛 std::invalid_argument。
struct LineGeneral {
    std::string general;
    double slope = 0.0;  // B == 0(垂直)时为 +inf
    std::string slope_intercept;
    bool has_x_intercept = false;
    double x_intercept = 0.0;
    bool has_y_intercept = false;
    double y_intercept = 0.0;
};
MF_API LineGeneral line_general(double A, double B, double C);

// 圆的标准方程 (x-h)² + (y-k)² = r²。r ≤ 0 抛 std::invalid_argument。
struct CircleStandard {
    std::string standard;
    std::string general;
    Point center;
    double radius = 0.0;
    double diameter = 0.0;
    double circumference = 0.0;
    double area = 0.0;
};
MF_API CircleStandard circle_standard(Point center, double r);

// 圆的一般方程 x²+y²+Dx+Ey+F=0 → 圆心半径。r² < 0 时 is_imaginary 置真。
struct CircleGeneral {
    bool is_imaginary = false;
    Point center;
    double radius = 0.0;
    double r_squared = 0.0;
    std::string standard;
    std::string general;
};
MF_API CircleGeneral circle_general(double D, double E, double F);

// ── 圆锥曲线（中心在原点，与圆的接口风格一致）─────────────────────────────
// 椭圆 x²/a² + y²/b² = 1（a > 0, b > 0）。焦点在长轴那一侧。
// a < b 时按"长轴在 y"处理：is_vertical 置真，foci/asymptote 等随之给出。
struct EllipseInfo {
    std::string standard;
    std::string general;
    double a = 0.0;
    double b = 0.0;
    double c = 0.0;             // 半焦距
    double eccentricity = 0.0;
    bool is_vertical = false;   // 长轴是否沿 y 轴
    double focus1_x = 0.0, focus1_y = 0.0;
    double focus2_x = 0.0, focus2_y = 0.0;
    double vertex_major = 0.0;  // 长半轴端点 (±a, 0) 或 (0, ±a)
    double vertex_minor = 0.0;
    std::string directrix;
    double area = 0.0;
};
MF_API EllipseInfo ellipse_standard(double a, double b);

// 双曲线 x²/a² - y²/b² = 1（a > 0, b > 0）。
struct HyperbolaInfo {
    std::string standard;
    std::string general;
    double a = 0.0;
    double b = 0.0;
    double c = 0.0;
    double eccentricity = 0.0;
    bool is_vertical = false;   // 焦点在 y 轴（y²/a² - x²/b² = 1）
    double focus1_x = 0.0, focus1_y = 0.0;
    double focus2_x = 0.0, focus2_y = 0.0;
    std::string asymptote1;
    std::string asymptote2;
    std::string directrix;
};
MF_API HyperbolaInfo hyperbola_standard(double a, double b);

// 抛物线：顶点在原点，p 为焦准距（焦点到准线的距离），p ≠ 0。
// axis: "x"（y² = 2px，开口向右/左）或 "y"（x² = 2py，开口向上/下）。
struct ParabolaInfo {
    std::string standard;
    std::string general;
    double p = 0.0;
    std::string axis;
    double focus_x = 0.0, focus_y = 0.0;
    std::string directrix;
    std::string opening;        // 右 / 左 / 上 / 下
    double latus_rectum = 0.0;  // 通径长度 = |2p|
};
MF_API ParabolaInfo parabola_standard(double p, const std::string& axis);

}  // namespace mf::algebra
