// fractal_api.cpp — 分形计算注册（Mandelbrot 迭代，纯 C++）
#include "registry.hpp"
#include "api_helpers.h"
#include "json.hpp"

#include <vector>

namespace {

using mf::json::Value;
using mf::api::make_handler;
using mf::api::get_double_opt;
using mf::api::get_int_opt;
using mf::api::to_int_array;

void register_all() {
  using mf::registry::register_function;

  // Mandelbrot 集：返回 width*height 个迭代次数（行优先）
  register_function("mandelbrot", make_handler([](const Value& args) {
    const double xmin = get_double_opt(args, "xmin", -2.0);
    const double xmax = get_double_opt(args, "xmax", 1.0);
    const double ymin = get_double_opt(args, "ymin", -1.5);
    const double ymax = get_double_opt(args, "ymax", 1.5);
    const int w = static_cast<int>(get_int_opt(args, "width", 800));
    const int h = static_cast<int>(get_int_opt(args, "height", 600));
    const int max_iter = static_cast<int>(get_int_opt(args, "max_iter", 100));

    std::vector<long long> iters(static_cast<size_t>(w) * h);
    for (int py = 0; py < h; py++) {
      const double c_im = ymin + (ymax - ymin) * py / h;
      for (int px = 0; px < w; px++) {
        const double c_re = xmin + (xmax - xmin) * px / w;
        double z_re = 0.0, z_im = 0.0;
        int iter = 0;
        while (iter < max_iter && z_re * z_re + z_im * z_im <= 4.0) {
          const double nz_re = z_re * z_re - z_im * z_im + c_re;
          const double nz_im = 2.0 * z_re * z_im + c_im;
          z_re = nz_re;
          z_im = nz_im;
          iter++;
        }
        iters[static_cast<size_t>(py) * w + px] = iter;
      }
    }
    return to_int_array(iters);
  }));
}

struct Registrar { Registrar() { register_all(); } };
const Registrar g_fractal_registrar;

}  // namespace
