cmake_minimum_required(VERSION 3.16)
project(mf_mathematics CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# DLL 与测试程序统一输出到 build/bin,保证运行时能找到 DLL。
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

# Eigen 头文件路径(编译命令的 -I)。默认取 vcpkg 安装位置,可 -DMF_EIGEN_INCLUDE_DIR=... 覆盖。
set(MF_EIGEN_INCLUDE_DIR
    "C:/Users/fsafsafsa/vcpkg/installed/x64-windows/include/eigen3"
    CACHE PATH "Eigen 头文件目录")

# SymEngine(符号计算)。默认取 vcpkg 安装位置,可 -DMF_SYMENGINE_ROOT=... 覆盖。
set(MF_SYMENGINE_ROOT
    "C:/Users/fsafsafsa/vcpkg/installed/x64-windows"
    CACHE PATH "SymEngine 安装根目录")

# ── mf_mathematics DLL ──────────────────────────────────────────────────────
add_library(mf_mathematics SHARED
    api.cpp
    registry.cpp
    introspect_api.cpp
    expr_api.cpp
    fractal_api.cpp
    symbolic_api.cpp
    plot_api.cpp
    number_theory/arithmetic_functions.cpp
    number_theory/core_algorithms.cpp
    number_theory/modular_arithmetic.cpp
    number_theory/prime_sieves.cpp
    number_theory/continued_fractions.cpp
    number_theory/zeta_interface.cpp
    number_theory/number_theory_api.cpp
    algebraic_topology/homology.cpp
    algebraic_topology/cohomology.cpp
    algebraic_topology/homotopy.cpp
    algebraic_topology/degree_fixedpoint.cpp
    algebraic_topology/persistent_homology.cpp
    algebraic_topology/at_api.cpp
    algebra/combinatorics.cpp
    algebra/number_theory.cpp
    algebra/analytic_geometry.cpp
    algebra/equation.cpp
    algebra/function.cpp
    algebra/expression.cpp
    algebra/inequality.cpp
    algebra/sequences.cpp
    algebra/algebra_api.cpp
    extras/extras.cpp
    extras/extras_api.cpp
    extras/analysis.cpp
    numerical/numerical_integration.cpp
    numerical/ode_solver.cpp
    numerical/interpolation.cpp
    numerical/error_stability.cpp
    numerical/optimization.cpp
    numerical/matrix_numerical.cpp
    numerical/numerical_api.cpp
    functional_analysis/normed_spaces.cpp
    functional_analysis/dual_spaces.cpp
    functional_analysis/linear_operators.cpp
    functional_analysis/spectral_theory.cpp
    functional_analysis/core_theorems.cpp
    functional_analysis/inner_product_spaces.cpp
    functional_analysis/fa_api.cpp
    calculus/derivatives.cpp
    calculus/integrals.cpp
    calculus/derivatives_app.cpp
    calculus/integrals_app.cpp
    calculus/series.cpp
    calculus/limits.cpp
    calculus/calculus_api.cpp
    real_analysis/differentiability.cpp
    real_analysis/sequence_limit.cpp
    real_analysis/real_numbers.cpp
    real_analysis/riemann_integral.cpp
    real_analysis/function_limit.cpp
    real_analysis/function_series.cpp
    real_analysis/real_analysis_api.cpp
    linear_algebra/vector_spaces.cpp
    linear_algebra/linear_transforms.cpp
    linear_algebra/inner_product.cpp
    linear_algebra/quadratic_forms.cpp
    linear_algebra/linear_systems.cpp
    linear_algebra/eigen.cpp
    linear_algebra/linear_algebra_api.cpp
    harmonic_analysis/fourier_series.cpp
    harmonic_analysis/fourier_transform.cpp
    harmonic_analysis/convolution.cpp
    harmonic_analysis/distributions.cpp
    harmonic_analysis/time_frequency.cpp
    harmonic_analysis/zeta_harmonic.cpp
    harmonic_analysis/harmonic_analysis_api.cpp
    measure_theory/set_systems.cpp
    measure_theory/measurable_functions.cpp
    measure_theory/measure_construction.cpp
    measure_theory/lebesgue_integral.cpp
    measure_theory/convergence_theorems.cpp
    measure_theory/probability_measure.cpp
    measure_theory/product_measure.cpp
    measure_theory/measure_theory_api.cpp
    probability/probability_space.cpp
    probability/random_variable.cpp
    probability/expectations.cpp
    probability/distributions.cpp
    probability/statistics.cpp
    probability/limits_theorems.cpp
    probability/hypothesis_test.cpp
    probability/nonparametric.cpp
    probability/anova.cpp
    probability/regression.cpp
    probability/time_series.cpp
    probability/probability_api.cpp
    complex_analysis/complex_integral.cpp
    complex_analysis/complex_topology.cpp
    complex_analysis/conformal.cpp
    complex_analysis/holomorphic.cpp
    complex_analysis/series.cpp
    complex_analysis/elementary_funcs.cpp
    complex_analysis/zeta.cpp
    complex_analysis/residue.cpp
    complex_analysis/complex_analysis_api.cpp
)
target_include_directories(mf_mathematics
    PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}
    PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/number_theory
    PRIVATE ${MF_EIGEN_INCLUDE_DIR}
)
target_link_libraries(mf_mathematics PRIVATE
    ${MF_SYMENGINE_ROOT}/lib/symengine.lib
    ${MF_SYMENGINE_ROOT}/lib/flint.lib
    ${MF_SYMENGINE_ROOT}/lib/gmp.lib
    ${MF_SYMENGINE_ROOT}/lib/mpfr.lib
)
target_compile_definitions(mf_mathematics PRIVATE MF_BUILD_DLL)

if(MSVC)
    # SymEngine/GMP/FLINT 头文件标记为外部,抑制其内部警告(/W4 之外)
    target_compile_options(mf_mathematics PRIVATE
        /utf-8 /W4 /external:W0 /external:I "${MF_SYMENGINE_ROOT}/include")
endif()

# 拷贝 SymEngine 运行时 DLL 到输出目录,保证测试运行时能找到。
if(WIN32)
    foreach(_dll symengine-0.14.dll flint-24.dll gmp-10.dll mpfr-6.dll pthreadVC3.dll)
        add_custom_command(TARGET mf_mathematics POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${MF_SYMENGINE_ROOT}/bin/${_dll}" $<TARGET_FILE_DIR:mf_mathematics>)
    endforeach()
endif()

if(MSVC)
    target_compile_options(mf_mathematics PRIVATE /utf-8 /W4)
endif()

# ── 测试 ────────────────────────────────────────────────────────────────────
enable_testing()

# 极限契约：确定形式必须给对；不定式要么给对、要么如实拒绝（不给假值）
add_executable(test_limits tests/test_limits.cpp)
target_link_libraries(test_limits PRIVATE mf_mathematics
    ${MF_SYMENGINE_ROOT}/lib/symengine.lib
    ${MF_SYMENGINE_ROOT}/lib/flint.lib
    ${MF_SYMENGINE_ROOT}/lib/gmp.lib
    ${MF_SYMENGINE_ROOT}/lib/mpfr.lib)
target_include_directories(test_limits PRIVATE ${CMAKE_CURRENT_SOURCE_DIR} ${MF_SYMENGINE_ROOT}/include)
if(MSVC)
    target_compile_options(test_limits PRIVATE /utf-8 /W4)
endif()
add_test(NAME limits COMMAND test_limits)

# 复网格契约：complex_grid 是复变函数可视化唯一的数据来源，钉住它的返回结构、
# 索引布局、null/nan 语义、unsupported 与点数上限（写法与 test_limits 一致：
# 库的链接是 PRIVATE，所以这里必须显式再链一次 symengine/flint/gmp/mpfr）
add_executable(test_complex_grid tests/test_complex_grid.cpp)
target_link_libraries(test_complex_grid PRIVATE mf_mathematics
    ${MF_SYMENGINE_ROOT}/lib/symengine.lib
    ${MF_SYMENGINE_ROOT}/lib/flint.lib
    ${MF_SYMENGINE_ROOT}/lib/gmp.lib
    ${MF_SYMENGINE_ROOT}/lib/mpfr.lib)
target_include_directories(test_complex_grid PRIVATE ${CMAKE_CURRENT_SOURCE_DIR} ${MF_SYMENGINE_ROOT}/include)
if(MSVC)
    target_compile_options(test_complex_grid PRIVATE /utf-8 /W4)
endif()
add_test(NAME complex_grid COMMAND test_complex_grid)

add_executable(test_number_theory tests/test_number_theory.cpp)
target_link_libraries(test_number_theory PRIVATE mf_mathematics)
target_include_directories(test_number_theory PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
if(MSVC)
    target_compile_options(test_number_theory PRIVATE /utf-8 /W4)
endif()
add_test(NAME number_theory COMMAND test_number_theory)

add_executable(test_algebraic_topology tests/test_algebraic_topology.cpp)
target_link_libraries(test_algebraic_topology PRIVATE mf_mathematics)
target_include_directories(test_algebraic_topology PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
if(MSVC)
    target_compile_options(test_algebraic_topology PRIVATE /utf-8 /W4)
endif()
add_test(NAME algebraic_topology COMMAND test_algebraic_topology)

add_executable(test_algebra tests/test_algebra.cpp)
target_link_libraries(test_algebra PRIVATE mf_mathematics)
target_include_directories(test_algebra PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
if(MSVC)
    target_compile_options(test_algebra PRIVATE /utf-8 /W4)
endif()
add_test(NAME algebra COMMAND test_algebra)

add_executable(test_numerical tests/test_numerical.cpp)
target_link_libraries(test_numerical PRIVATE mf_mathematics)
target_include_directories(test_numerical PRIVATE ${CMAKE_CURRENT_SOURCE_DIR} ${MF_EIGEN_INCLUDE_DIR})
if(MSVC)
    target_compile_options(test_numerical PRIVATE /utf-8 /W4)
endif()
add_test(NAME numerical COMMAND test_numerical)

add_executable(test_functional_analysis tests/test_functional_analysis.cpp)
target_link_libraries(test_functional_analysis PRIVATE mf_mathematics)
target_include_directories(test_functional_analysis PRIVATE ${CMAKE_CURRENT_SOURCE_DIR} ${MF_EIGEN_INCLUDE_DIR})
if(MSVC)
    target_compile_options(test_functional_analysis PRIVATE /utf-8 /W4)
endif()
add_test(NAME functional_analysis COMMAND test_functional_analysis)

add_executable(test_calculus tests/test_calculus.cpp)
target_link_libraries(test_calculus PRIVATE mf_mathematics)
target_include_directories(test_calculus PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
if(MSVC)
    target_compile_options(test_calculus PRIVATE /utf-8 /W4)
endif()
add_test(NAME calculus COMMAND test_calculus)

add_executable(test_real_analysis tests/test_real_analysis.cpp)
target_link_libraries(test_real_analysis PRIVATE mf_mathematics)
target_include_directories(test_real_analysis PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
if(MSVC)
    target_compile_options(test_real_analysis PRIVATE /utf-8 /W4)
endif()
add_test(NAME real_analysis COMMAND test_real_analysis)

add_executable(test_linear_algebra tests/test_linear_algebra.cpp)
target_link_libraries(test_linear_algebra PRIVATE mf_mathematics)
target_include_directories(test_linear_algebra PRIVATE ${CMAKE_CURRENT_SOURCE_DIR} ${MF_EIGEN_INCLUDE_DIR})
if(MSVC)
    target_compile_options(test_linear_algebra PRIVATE /utf-8 /W4 /external:W0 /external:I "${MF_EIGEN_INCLUDE_DIR}")
endif()
add_test(NAME linear_algebra COMMAND test_linear_algebra)

add_executable(test_harmonic_analysis tests/test_harmonic_analysis.cpp)
target_link_libraries(test_harmonic_analysis PRIVATE mf_mathematics)
target_include_directories(test_harmonic_analysis PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
if(MSVC)
    target_compile_options(test_harmonic_analysis PRIVATE /utf-8 /W4)
endif()
add_test(NAME harmonic_analysis COMMAND test_harmonic_analysis)

add_executable(test_measure_theory tests/test_measure_theory.cpp)
target_link_libraries(test_measure_theory PRIVATE mf_mathematics)
target_include_directories(test_measure_theory PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
if(MSVC)
    target_compile_options(test_measure_theory PRIVATE /utf-8 /W4)
endif()
add_test(NAME measure_theory COMMAND test_measure_theory)

add_executable(test_probability tests/test_probability.cpp)
target_link_libraries(test_probability PRIVATE mf_mathematics)
target_include_directories(test_probability PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
if(MSVC)
    target_compile_options(test_probability PRIVATE /utf-8 /W4)
endif()
add_test(NAME probability COMMAND test_probability)

add_executable(test_complex_analysis tests/test_complex_analysis.cpp)
target_link_libraries(test_complex_analysis PRIVATE mf_mathematics)
target_include_directories(test_complex_analysis PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
if(MSVC)
    target_compile_options(test_complex_analysis PRIVATE /utf-8 /W4)
endif()
add_test(NAME complex_analysis COMMAND test_complex_analysis)

# 符号 API 契约测试：钉住实际反馈过的缺陷（含参实根性、极值字段语义、
# 化简择优、因式分解根式归约、机器记号外泄、参数错误信息）
add_executable(test_symbolic_contract tests/test_symbolic_contract.cpp)
target_link_libraries(test_symbolic_contract PRIVATE mf_mathematics
    ${MF_SYMENGINE_ROOT}/lib/symengine.lib
    ${MF_SYMENGINE_ROOT}/lib/flint.lib
    ${MF_SYMENGINE_ROOT}/lib/gmp.lib
    ${MF_SYMENGINE_ROOT}/lib/mpfr.lib)
# 该套件直接包含 special_numeric.h 做数值实现自检，故需要 SymEngine 头文件
target_include_directories(test_symbolic_contract PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}
    ${MF_SYMENGINE_ROOT}/include)
if(MSVC)
    target_compile_options(test_symbolic_contract PRIVATE /utf-8 /W4
        /external:W0 /external:I "${MF_SYMENGINE_ROOT}/include")
endif()
add_test(NAME symbolic_contract COMMAND test_symbolic_contract)

add_executable(probe_bugs tests/probe_bugs.cpp)
target_link_libraries(probe_bugs PRIVATE mf_mathematics
    ${MF_SYMENGINE_ROOT}/lib/symengine.lib
    ${MF_SYMENGINE_ROOT}/lib/flint.lib
    ${MF_SYMENGINE_ROOT}/lib/gmp.lib
    ${MF_SYMENGINE_ROOT}/lib/mpfr.lib)
target_include_directories(probe_bugs PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}
    ${MF_SYMENGINE_ROOT}/include)
if(MSVC)
    target_compile_options(probe_bugs PRIVATE /utf-8 /W4
        /external:W0 /external:I "${MF_SYMENGINE_ROOT}/include")
endif()
add_test(NAME probe_bugs COMMAND probe_bugs)

# SymEngine::solve 安全性实测探针：在独立进程里试探各类方程，
# 用于确定 safe_solve 的超越函数黑名单能放宽到哪一步（崩溃点即证据）。
add_executable(probe_solve_safety tests/probe_solve_safety.cpp)
target_link_libraries(probe_solve_safety PRIVATE mf_mathematics
    ${MF_SYMENGINE_ROOT}/lib/symengine.lib
    ${MF_SYMENGINE_ROOT}/lib/flint.lib
    ${MF_SYMENGINE_ROOT}/lib/gmp.lib
    ${MF_SYMENGINE_ROOT}/lib/mpfr.lib)
target_include_directories(probe_solve_safety PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}
    ${MF_SYMENGINE_ROOT}/include)
if(MSVC)
    target_compile_options(probe_solve_safety PRIVATE /utf-8 /W4
        /external:W0 /external:I "${MF_SYMENGINE_ROOT}/include")
endif()

# 通用调用探针：不必启动宿主就能直接观察引擎对某组输入的真实返回，
# 用于核对字段语义、错误信息、记号外泄等「契约」层面的问题。
add_executable(probe_call tests/probe_call.cpp)
target_link_libraries(probe_call PRIVATE mf_mathematics)
target_include_directories(probe_call PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
if(MSVC)
    target_compile_options(probe_call PRIVATE /utf-8 /W4)
endif()

# 数值扫描内部行为诊断探针（非回归）
add_executable(probe_scan tests/probe_scan.cpp)
target_link_libraries(probe_scan PRIVATE mf_mathematics
    ${MF_SYMENGINE_ROOT}/lib/symengine.lib
    ${MF_SYMENGINE_ROOT}/lib/flint.lib
    ${MF_SYMENGINE_ROOT}/lib/gmp.lib
    ${MF_SYMENGINE_ROOT}/lib/mpfr.lib)
target_include_directories(probe_scan PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}
    ${MF_SYMENGINE_ROOT}/include)
if(MSVC)
    target_compile_options(probe_scan PRIVATE /utf-8 /W4
        /external:W0 /external:I "${MF_SYMENGINE_ROOT}/include")
endif()