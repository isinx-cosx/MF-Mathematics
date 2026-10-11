# 数值层（NUMERIC）

> 本文说明数值层怎么组织：特殊函数与复数实现、精度与容差设定、密集求值类操作的规模上限。
> 与同层文档的分工：[`SYMBOLIC.md`](SYMBOLIC.md) 讲符号层；[`INPUT.md`](INPUT.md) 讲输入归一化与解析；[`PLOT.md`](PLOT.md) 讲绘图接口与采样；[`TESTS.md`](TESTS.md) 讲可执行目标与 CTest 用例。

## 1. 数值层的文件与职责

| 文件 | 职责 | action 数 |
| --- | --- | --- |
| `MF_Mathematics/special_numeric.h` | 实值特殊函数（Γ/logΓ/ψ/ψ⁽ⁿ⁾/ζ/β/erf/erfc/W）+ `eval_double_ex` 增强求值 | 0（纯头文件，被别的模块调用） |
| `MF_Mathematics/complex_numeric.h` | 复值表达式求值（`complex_grid` 的数据来源） | 0（同上） |
| `MF_Mathematics/numerical/**` | 积分 / ODE / 插值 / 误差稳定性 / 优化 / 矩阵数值（Eigen） | 25 |
| `MF_Mathematics/probability/**` | 概率统计：自带分布 CDF/分位数（不引 scipy） | 40 |
| `MF_Mathematics/plot_api.cpp` | `complex_grid` / `complex_eval` / `intersections` 等 | 4 |

`numerical` 与 `probability` 的 action 计数命令：

```powershell
(Select-String -Path MF_Mathematics/numerical/numerical_api.cpp -Pattern 'register_function\("' | Measure-Object).Count       # 25
(Select-String -Path MF_Mathematics/probability/probability_api.cpp -Pattern 'register_function\("' | Measure-Object).Count   # 40
```

两条调用链：

```
complex_grid (plot_api.cpp)
   → mf::cnum::eval_node (complex_numeric.h)
       ├─ gamma / zeta / erf / erfc → 引擎自己的复数实现
       └─ 其余初等函数              → SymEngine::eval_complex_double

符号表达式的数值回退 (symbolic_util.h)
   → mf::num::eval_double_ex (special_numeric.h)：三级递进，见 §3.2
```

`probe_call.exe <action> <args_json>` 走 C ABI，与宿主 / JS 调用方看到的同一条路径。

## 2. 第三方库分工

| 库 | 引入处 | 源码直接调用？ | 负责什么 |
| --- | --- | --- | --- |
| SymEngine | `CMakeLists.txt` | 是 | 表达式树、解析、`eval_double`/`eval_complex_double`、`diff`/`solve`/`subs` |
| FLINT / GMP / MPFR | `CMakeLists.txt` | 否 | 仅作为 SymEngine 的传递依赖被链接 |
| Eigen | `CMakeLists.txt`（`MF_EIGEN_INCLUDE_DIR`） | 是（纯头文件） | 稠密矩阵与线性代数 |

「引擎源码不直接调用 FLINT/GMP/MPFR」的核对：

```powershell
Get-ChildItem MF_Mathematics -Recurse -Include *.h,*.cpp | Select-String -Pattern 'mpfr|gmp|flint'
# 命中全部在 CMakeLists.txt（构建脚本），源码 0 处
```

因此「MPFR 提供高精度计算」这类说法在本引擎不成立；要证实需找到一处直接调用 `mpfr_*` 的源码。

## 3. 实值特殊函数（`special_numeric.h`）

存在的理由：SymEngine 的 `eval_double` 没有 Γ/PolyGamma/Zeta/Beta/LambertW，含这些函数的导数一个采样点都算不出来。本文件补上，算不出实数一律返回 `NaN`（不抛异常、不返回错值），让调用方沿用「NaN = 该点不可求值」的统一判断；能直接用标准库的优先用标准库（`erf`/`erfc`）。

| 函数 | 实现要点 | 极点 / 域外 → NaN |
| --- | --- | --- |
| `gamma_real` | `x>0` 走 `exp(lgamma(x))`；`x<0` 非整数走反射公式 | 非正整数；`|sin πx|<1e-300` |
| `loggamma_real` | `lgamma` | `x ≤ 0` 或非有限 |
| `digamma_real` | 递推抬到 `y ≥ 8` 再用渐近展开 | 非正整数 |
| `hurwitz_zeta` | 直接和 `n_terms` 项（默认 16）+ Euler–Maclaurin 尾部 | `a ≤ 0`；`|s−1|<1e-14` |
| `zeta_real` | 四分支，见下表 | `s=1`（`1e-14` 判据） |
| `polygamma_real` | 逐次右移，再用 `(−1)^{n+1}n!ζ(n+1,y)` | 非正整数；右移 `guard > 1000000` |
| `beta_real` | `Γ(a)Γ(b)/Γ(a+b)` | 任一 Γ 非有限或 `Γ(a+b)==0` |
| `lambertw0_real` | 牛顿迭代解 `w·eʷ=x`，≤100 次 | `x < −1/e−1e-15` |
| `lambertw_m1_real` | 两种渐近初值，≤200 次 | `x ≥ 0` |

`zeta_real` 的分支（定位 `Select-String -Path MF_Mathematics/special_numeric.h -Pattern 'zeta_real'`）：

| 区间 | 做法 |
| --- | --- |
| `s ≥ 1` | Euler–Maclaurin，直接和 16 项 |
| `s == 0` | 直接返回 `−0.5` |
| `0 < s < 1` | Euler–Maclaurin，项数 `n = 200/(s+0.1)`，夹到 `[64, 200000]` |
| `s < 0` | 函数方程降到 `1−s ≥ 1` |

`0<s<1` 不套函数方程的原因是 `1−s` 仍落在 `(0,1)`，会无限递归。

### 3.1 容差常量

精度判据在 `test_symbolic_contract.cpp`，判据是绝对误差 `|a−b| ≤ tol`：

| 断言 | 容差 |
| --- | --- |
| `zeta_real(2)`、`zeta_real(−1)`、`zeta_real(0)`、`gamma_real(0.5)`、`digamma_real(1)`、`lambertw0_real(1)` | `1e-12` |
| `zeta_real(0.5)`、`gamma_real(5)`、`gamma_real(−0.5)`、`lambertw_m1_real(−0.1)` | `1e-9` |
| `polygamma_real(1, 0.5/1.5/−0.5)` | `1e-10` |
| 极点必须 `isnan`（`zeta_real(1)`、`gamma_real(−2)` 等） | 硬断言 |

### 3.2 三级递进求值 `eval_double_ex`

`eval_double_ex`（`special_numeric.h`）三级，任何一级成功即返回：

1. **原生**：`subs` 后直接 `eval_double`。
2. **不求值导数**：在替换之前做（替换会把求导变量换成常数）。中心差分 `(f(x₀+h)−f(x₀−h))/(2h)`，二阶用三点公式；只支持同一符号的 1/2 阶；`h = (1e-6 或 1e-4)·max(1,|x₀|)`。
3. **特殊函数数值化**：自底向上把「实参已是数值」的 Γ/ψ/ζ/W 等节点换成 `RealDouble` 再交给 `eval_double`。

递归深度上限 `depth > 6` 直接返回 NaN。

## 4. 复数层（`complex_numeric.h`）

### 4.1 为什么自己写

SymEngine 的 `eval_complex_double` 只覆盖初等函数：`zeta(1+14.13i)`、`gamma(1+i)` 均报 `Not Implemented`，`erf`/`erfc` 连实数都不支持。因此 ζ/Γ/erf/erfc 需要自己实现。

### 4.2 求值器组织方式

| 设计点 | 说明 |
| --- | --- |
| 数值叶子与常数（π、e、欧拉常数）交给 SymEngine | 省去维护常数表 |
| 函数按名字分派，不按类 | `is_a<FunctionSymbol>` 对 `Sin/Log/Zeta` 运行时恒 false；按类漏一个会静默算错，按名字漏了会明确报「不支持」 |
| 名字只在整棵树算一次（指针 → 名字缓存） | `str()` 不便宜 |
| 整数幂走快速幂连乘（`|e| ≤ 64`） | `z^2` 比 `pow(z,2.0)` 准且快 |
| 算不出来 → NaN + `unsupported` | 不返回看起来正常的错值 |
| 递归深度上限 200 | 避免深表达式爆栈 |
| 两参数 `Zeta(s,a)` 只在 `a=1` 可用 | 其余 Hurwitz ζ 未实现，明确报出 |

### 4.3 复数 ζ / Γ / erf 的实现

| 函数 | 实现 |
| --- | --- |
| `zeta_complex` | 极点判据 `|s−1|<1e-12` → NaN，其余转 `analytic_continuation_zeta` |
| `analytic_continuation_zeta` | 负整数用伯努利数；`Re s ≥ 0` → Euler–Maclaurin；`Re s < 0` → 函数方程 |
| `gamma_complex` | Lanczos（`g=7`、9 个系数）；`Re z<0.5` 走反射公式；非正整数抛异常 |
| `erf_complex` | `|z|>4` 用渐近展开（先折到右半平面，项开始变大就停）；否则泰勒级数（≤250 项） |
| `erfc_complex` | `1 − erf_complex(z)` |

异常收口：`gamma_complex` 在极点抛 `std::invalid_argument`，`complex_grid` 的求值循环用 `try/catch` 兜住并转成 NaN，这些点在网格里表现为 `null` + `nan` 计数，异常不穿过 C ABI。

定位：`Select-String -Path MF_Mathematics/complex_numeric.h -Pattern 'zeta_complex|erf_complex|gamma_complex'`；`Select-String -Path MF_Mathematics/complex_analysis/ca_internal.h -Pattern 'gamma_complex'`。

### 4.4 已确证的缺陷

`erfc(z) = 1 − erf(z)`（`complex_numeric.h`）在大 `|z|` 时被相消吃光：`erfc(5)` 相对偏差约 `1.5e-5`，`erfc(10)` 返回 `0` 且 `ok=1`（真值约 `2.09e-45`），`erfc(27)` 同样返回 `0`。测试只钉了 `erfc(1)`，这条缺陷没有回归保护。复跑：

```powershell
MF_Mathematics\build\bin\Release\probe_call.exe complex_grid '{"expr":"erfc(z)","x0":10,"x1":10,"y0":0,"y1":0,"nx":1,"ny":1,"digits":17}'
```

引擎返回 `0` 且 `ok=1`，前端会把它当真值绘制，属于产品缺陷而不是「算不出来」。

## 5. 容差与精度策略

### 5.1 三种容差口径

| 判据 | 定义 | 用在哪 |
| --- | --- | --- |
| 绝对容差 | `|a−b| ≤ tol` | `test_numerical.cpp` 全部、`test_symbolic_contract.cpp` 的特殊函数自检 |
| 相对容差（带 1 下限） | `|a−b| ≤ tol·max(1,|b|)` | `test_complex_grid.cpp` 全部；NaN 参与比较一律失败 |
| 引擎内部停止判据 | 迭代增量 / 余项与量级之比 | `optimal_step_impl`、概率层连分数、迭代解法 |

### 5.2 `numerical` 包的容差与上界（`test_numerical.cpp`）

| 检验对象 | 容差 |
| --- | --- |
| 积分：梯形 / 辛普森 / 高斯（`n=3`） | `0.001` / `0.0001` / `0.0001` |
| 数值微分 `(x³)'@2`；ODE 的 `y(1)≈e` | `0.001`；`0.5` / `0.5` / `0.001` |
| 插值、LU 重构 `L·U≈A` | `1e-10` |
| 迭代解法内部 `tol`；幂法 / QR 内部 `tol` | `1e-6`；`1e-8` |

### 5.3 引擎内部的步长与停止判据

| 参数 | 值 |
| --- | --- |
| 机器 eps | `2.220446049250313e-16`（`numerical_core.h`） |
| 数值微分默认步长 `h` | `1e-6` |
| 最优步长 `h*` | 中心差分 `(3·eps·|f|/|f'''|)^{1/3}`；单侧 `(2·eps·|f|/|f''|)^{1/2}`；夹到 `[1e-12, 0.1]` |
| `condition_number` | 差分 `eps` 默认 `1e-8`；`|f(x)|<1e-15` → `+inf` |
| `truncation_error` | `|true_value| > 1e-15` 时用真值，否则用第 `n+1` 项差 |
| `is_stable` | 输入相对扰动 `1e-8`，结果相对差 `< 1e-4` 判稳定 |
| 梯度下降 | `tol` 默认 `1e-6`；无解析导数时中心差分 `h_fd = 1e-6` |
| 迭代线代 / 特征值 | `tol` 默认 `1e-6`（线代）/ `1e-8`（幂法、QR），`max_iter` 默认 `1000` |
| 概率层连分数与级数 | `maxit=200`、`eps=3e-14`、`tiny=1e-300` |
| 正态 / t 分位数 | Acklam 有理逼近 + 两次牛顿修正；t 用牛顿迭代 ≤80 次，停判 `|step|<1e-12·(1+|t|)` |

定位：`Select-String -Path MF_Mathematics/numerical/numerical_core.h -Pattern 'kMachineEps'`；`Select-String -Path MF_Mathematics/probability/prob_internal.h -Pattern 'maxit|eps|tiny'`。

## 6. 密集求值类操作的规模上界

统一收口点是 `api_helpers.h` 的 `get_int_bounded`：凡直接决定分配尺寸或循环次数的参数都给显式上下界，越界抛中文错误。

| 操作 | 上界 | 越界行为 |
| --- | --- | --- |
| `complex_grid` | `nx*ny ≤ 400000` | 报错，文案含「超过上限 400000」 |
| `trapezoidal_rule` / `simpson_rule` 的 `n` | `≤ 10000000` | 报错（`n ≤ 0` 也报错） |
| `gauss_quadrature` 的 `n` | API 声明 `≤ 10000000`，实现只接受 2/3/4 | 报错「高斯求积目前仅支持 n=2,3,4」 |
| `truncation_error` 的 `n` | `≤ 1000000` | 报错 |
| `least_squares_fit` 的 `degree` | `≤ 20` | 报错 |
| `phase_portrait` | `resolution ≤ 200`、`n_trajectories ≤ 100` | 报错 |
| 迭代线代解法 / 特征值 | `max_iter ≤ 100000` | 报错 |
| `mandelbrot` | `width/height ≤ 4000`、`max_iter ≤ 100000`、`width×height ≤ 4000000` | 报错 |

`complex_grid` 的 400000 上限的工程理由：JSON 里每个数约 12 字节，400k 点 × 2 个数 ≈ 9.6 MB，超过这个量桥的缓冲顶不住（`plot_api.cpp` 注释）。

一个确切没有上界的地方：三个 ODE 求解器的步数由 `n_steps = max(1, ceil((t_end − t0) / h))` 算出，不经过 `get_int_bounded`（`MF_Mathematics/numerical/ode_solver.cpp`），唯一的校验是 `h > 0`。返回体随步数线性增长；`euler_method` 在 `t_end=100, h=1e-4` 时产生 1000000 步，超出 `probe_call` 的 4 MiB 缓冲（返回 `-1`）。这是产品侧的规模上界缺口：引擎没有在计算前拒绝过大的步数。

定位：`Select-String -Path MF_Mathematics/numerical/ode_solver.cpp -Pattern 'n_steps'`；`Select-String -Path MF_Mathematics/numerical/numerical_api.cpp -Pattern 'euler_method|rk4|implicit_euler'`。

## 7. 复现本文全部数字

```powershell
cmake --build MF_Mathematics/build --config Release
cd MF_Mathematics\build\bin\Release
.\test_complex_grid.exe            # 复网格契约
.\test_numerical.exe               # numerical 包
.\test_symbolic_contract.exe       # 含特殊函数自检
.\probe_call.exe complex_grid '{"expr":"zeta(z)","x0":1,"x1":1,"y0":14.13,"y1":14.13,"nx":1,"ny":1,"digits":17}'
.\probe_call.exe complex_grid '{"expr":"erfc(z)","x0":10,"x1":10,"y0":0,"y1":0,"nx":1,"ny":1,"digits":17}'
.\probe_call.exe p_value '{"test_statistic":1.96,"dist":"normal","df":1,"alternative":"two-sided"}'
.\probe_call.exe --list            # value.count 应为 424
```

`digits` 的语义（`plot_api.cpp`）：缺省 7 位有效数字，`digits ≤ 0` 或 `> 17` 时原样返回（不截断）。`digits` 是显示/传输精度，不是计算精度——计算始终是双精度，`digits` 只影响序列化。
