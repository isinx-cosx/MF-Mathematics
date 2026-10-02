// quadratic_forms.h — 二次型与正定性:二次型、标准形、正/负定、不定。
#pragma once

#include <string>
#include <vector>

#include "la_internal.h"

namespace mf::linear_algebra {

// 二次型 x^T·A·x 的展开表达式。x 为逗号分隔变量名(空则自动 x0,x1,...)。
std::string quadratic_form(const std::vector<std::vector<double>>& matrix,
                                  const std::string& x);

// 正交变换化为标准形 λ₁y₁²+...+λₙyₙ²。
struct StandardFormResult {
    std::string standard_form;
    std::vector<double> eigenvalues;
    Matrix orthogonal_matrix;
};
StandardFormResult standard_form(
    const std::vector<std::vector<double>>& matrix);

// 顺序主子式全正 → 正定。
bool is_positive_definite(
    const std::vector<std::vector<double>>& matrix);

// 负定:奇阶主子式 < 0,偶阶 > 0。
bool is_negative_definite(
    const std::vector<std::vector<double>>& matrix);

// 不定:同时有正、负特征值。
bool is_indefinite(const std::vector<std::vector<double>>& matrix);

}  // namespace mf::linear_algebra
