cmake_minimum_required(VERSION 3.20)
# CMake 4.x 移除了对旧 config 文件(<3.5)的支持，SymEngine 的 config 需要此兼容开关
set(CMAKE_POLICY_VERSION_MINIMUM 3.5)
project(symengine_demo CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(SymEngine CONFIG REQUIRED)

add_executable(demo main.cpp)
# SymEngine 的 config 把依赖(fint/mpfr/gmp)从 target 剥离，需链接 SYMENGINE_LIBRARIES
target_link_libraries(demo PRIVATE ${SYMENGINE_LIBRARIES})
if(MSVC)
    target_compile_options(demo PRIVATE /utf-8)
endif()

# Eigen 验证
find_package(Eigen3 CONFIG REQUIRED)
add_executable(eigen_test eigen_test.cpp)
target_link_libraries(eigen_test PRIVATE Eigen3::Eigen)
