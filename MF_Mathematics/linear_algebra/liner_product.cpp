#include <iostream>
#include <vector>
#include <stdexcept>
#include <cmath>
#include <algorithm>

double dot_c(std::vector<double> u, std::vector<double> v, int n){
    double sum = 0;
    for (int i = 0; i < n; i++) sum += u[i] * v[i];
    return sum;
}

double norm_c(std::vector<double> u, int n){
    return std::sqrt(dot_c(u, u, n));
}

double angle_c(std::vector<double> u, std::vector<double>  v, int n){
    double nu = norm_c(u, n);
    double nv = norm_c(v, n);
    double d = dot_c(u, v, n);
    if (nu < 1e-15 || nv < 1e-15) {
        return NAN;
    }
    double cos = d / (nu * nv);
    cos = std::clamp(cos, -1.0, 1.0);
    return std::acos(cos);
}
