// integrals_app.h — 积分应用:曲线间面积、旋转体体积(圆盘/壳)、弧长。
#pragma once

#include <string>

#include "../mf_export.h"

namespace mf::calculus {

// 两曲线之间的面积 ∫|f-g| dx。
MF_API double area_between(const std::string& f, const std::string& g,
                           const std::string& var, double a, double b);

// 旋转体体积(圆盘法)V = π∫f² dx。
MF_API double volume_disk(const std::string& f, const std::string& var, double a,
                          double b);

// 旋转体体积(壳法)V = 2π∫x·f dx。
MF_API double volume_shell(const std::string& f, const std::string& var, double a,
                           double b);

// 曲线弧长 L = ∫√(1+f'²) dx。
MF_API double arc_length(const std::string& f, const std::string& var, double a,
                         double b);

}  // namespace mf::calculus
