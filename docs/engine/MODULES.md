# 引擎的学科模块

> 本文按学科模块列出 `MF_Mathematics/` 的文件规模、注册的 action 数与能力边界。
> 构建目标与 C ABI 见 [`README.md`](README.md)，键名契约与参数类型见 [`CONTRACT.md`](CONTRACT.md)，能力边界见 [`BOUNDARIES.md`](BOUNDARIES.md)，测试资产见 [`TESTS.md`](TESTS.md)。
> action 数取自签名表，文件规模取自磁盘，两者独立，命令附于各节。

## 1. 统计口径

| 数字 | 来源 | 复跑命令 |
| --- | --- | --- |
| action 数 | `MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json`，取每条 `file` 字段第一段路径作为模块名 | 见「模块划分规则」一节 |
| 编译 `.cpp` | `CMakeLists.txt` 的 `add_library(mf_mathematics_core ...)` 源文件列表 | `Select-String -Path MF_Mathematics/CMakeLists.txt -Pattern '^\s+[A-Za-z0-9_/.]+\.cpp$'` |
| 行数 | 文件按 `\n` 切分后计数（含空行） | `node -e "console.log(require('fs').readFileSync(process.argv[1],'utf8').split('\n').length)" <file>` |

签名表是 action 数的权威源，其漂移由 `node tools/engine-signatures.mjs --check` 检查。

## 2. 模块划分规则

`file` 字段记录注册该 action 的 `*_api.cpp`，取 `file` 第一段路径得到模块名。424 个 action 的分解：

```powershell
node -e "const j=require('./MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json');const g={};for(const n of Object.keys(j)){const f=j[n].file;const d=f.includes('/')?f.split('/')[0]:'(root) '+f;g[d]=(g[d]||0)+1;}console.log(Object.keys(j).length);for(const [d,c] of Object.entries(g).sort((a,b)=>b[1]-a[1]))console.log(c,d);"
```

| 分组 | 数量 | 说明 |
| --- | --- | --- |
| 12 个学科模块 | 377 | 见「总表」与「模块逐个」两节 |
| `extras/` | 25 | 补齐件目录，见「extras 的 25 条」一节 |
| 引擎根目录 5 个 `*_api.cpp` | 22 | `expr_api.cpp` 9、`symbolic_api.cpp` 7、`plot_api.cpp` 4、`introspect_api.cpp` 1、`fractal_api.cpp` 1 |

根目录另有两个不注册 action 的文件：`registry.cpp`（注册表与分发）、`api.cpp`（C ABI 包装）。

## 3. 总表

「编译 `.cpp`」只数进入 `CMakeLists.txt` 编译列表的文件；「目录 `.cpp`」数目录内全部 `.cpp`；「`.h`」数目录内全部头文件（含 `.hpp`）。行数是编译 `.cpp` 行数与全部 `.h` 行数之和口径，下表中「`.cpp` 行」为编译单元行数，「`.h` 行」为目录内全部头文件行数。

| 模块 | 编译 `.cpp` | 目录 `.cpp` | `.h` | `.cpp` 行 | `.h` 行 | action | 注册文件（行数） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `calculus` | 7 | 7 | 6 | 4,330 | 285 | 35 | `calculus/calculus_api.cpp`（355） |
| `algebra` | 9 | 9 | 8 | 2,802 | 547 | 79 | `algebra/algebra_api.cpp`（627） |
| `harmonic_analysis` | 7 | 7 | 9 | 1,335 | 1,362 | 22 | `harmonic_analysis/harmonic_analysis_api.cpp`（319） |
| `probability` | 12 | 12 | 13 | 1,649 | 851 | 40 | `probability/probability_api.cpp`（554） |
| `numerical` | 7 | 12 | 12 | 992 | 999 | 25 | `numerical/numerical_api.cpp`（342） |
| `real_analysis` | 7 | 7 | 7 | 1,249 | 595 | 28 | `real_analysis/real_analysis_api.cpp`（288） |
| `complex_analysis` | 9 | 9 | 9 | 1,358 | 467 | 30 | `complex_analysis/complex_analysis_api.cpp`（401） |
| `measure_theory` | 8 | 8 | 8 | 1,230 | 547 | 24 | `measure_theory/measure_theory_api.cpp`（547） |
| `linear_algebra` | 7 | 7 | 7 | 1,226 | 453 | 32 | `linear_algebra/linear_algebra_api.cpp`（416） |
| `algebraic_topology` | 6 | 6 | 6 | 953 | 556 | 17 | `algebraic_topology/at_api.cpp`（316） |
| `number_theory` | 7 | 7 | 7 | 1,111 | 283 | 24 | `number_theory/number_theory_api.cpp`（299） |
| `functional_analysis` | 7 | 7 | 7 | 847 | 238 | 21 | `functional_analysis/fa_api.cpp`（298） |
| **合计** | 93 | 98 | 99 | 19,082 | 7,183 | 377 | — |

`numerical` 的「目录 `.cpp`」为 12 而「编译 `.cpp`」为 7，差额 5 个文件不参与编译，见「numerical（数值分析）」一节。

行数复跑（按模块目录与编译列表）：

```powershell
node -e "
const fs=require('fs');
const cmake=fs.readFileSync('MF_Mathematics/CMakeLists.txt','utf8');
const compiled=cmake.split('\n').filter(l=>/^\s+[A-Za-z0-9_\/.]+\.cpp$/.test(l)).map(l=>l.trim());
function L(p){try{return fs.readFileSync(p,'utf8').split('\n').length}catch(e){return 0}}
const mods=['calculus','algebra','harmonic_analysis','probability','numerical','real_analysis','complex_analysis','measure_theory','linear_algebra','algebraic_topology','number_theory','functional_analysis'];
for(const m of mods){const dir='MF_Mathematics/'+m;const hs=fs.readdirSync(dir).filter(f=>f.endsWith('.h')||f.endsWith('.hpp'));const cpp=compiled.filter(c=>c.startsWith(m+'/'));let cl=0,hl=0;for(const c of cpp)cl+=L('MF_Mathematics/'+c);for(const h of hs)hl+=L(dir+'/'+h);console.log(m,'cppLines='+cl,'hLines='+hl,'compiledCpp='+cpp.length,'h='+hs.length);}
"
```

## 4. 模块逐个

### 4.1 `calculus`（微积分）

**源**：`calculus/calculus_api.cpp`（355 行），编译 7 `.cpp` / 6 `.h`，CTest：`calculus`、`limits`。action 数 35。

**能力**：求导与微分（`diff`、`diff_at`、`parametric_diff`、`implicit_diff`、`differential`）；积分（`integrate`、`integrate_numeric`、`integrate_double`、`integrate_triple`、`integrate_complex`、`improper_integral`）；级数（`series_convergence`、`series_sum`、`power_series`、`power_series_radius`、`taylor`）；极限（`limit`、`lhopital`）；几何应用（`arc_length`、`area_between`、`volume_disk`、`volume_shell`）；极值与单调（`local_extrema`、`global_extrema`、`monotonicity`）；连续与中值定理（`calc_is_continuous`、`calc_discontinuity_classify`、`calc_rolle_theorem`、`calc_lagrange_theorem`）；六种审敛（`integral_test`、`direct_comparison_test`、`limit_comparison_test`、`p_series_test`、`leibniz_test`、`classify_and_test`）。

**边界**：无法符号积分返回字面量 `"未实现"`，不给近似值；定积分符号失败回退数值辛普森。极限求解有硬预算，常量在 `calculus/limits.cpp`：

```powershell
Select-String -Path MF_Mathematics/calculus/limits.cpp -Pattern 'kLimMax'
```

### 4.2 `algebra`（代数）

**源**：`algebra/algebra_api.cpp`（627 行），编译 9 `.cpp` / 8 `.h`，CTest：`algebra`。action 数 79，为 12 个模块中最多。

**能力**：化简与因式分解（`simplify_polynomial`、`simplify_fraction`、`simplify_radical`、`expand_expression`、`common_denominator`、`fraction_operations`、`rationalize_denominator`、`like_radicals`、`radical_operations`、`factor` 及其变体）；方程与不等式（`solve_linear`、`solve_quadratic`、`solve_fractional`、`solve_irrational`、`solve_linear_inequality`、`solve_quadratic_inequality`、`solve_inequality_system`、`alg_solve_linear_system`、`discriminant`、`vieta_theorem`）；数列（`arithmetic_sequence`、`geometric_sequence`、`recurrence_sequence`、`sequence_term`、`arithmetic_sum`、`geometric_sum`）；计数（`permutation`、`combination`、`binomial_expand`、`binomial_term`、`addition_principle`、`multiplication_principle`）；解析几何（直线、圆、抛物线、椭圆、双曲线、距离、中点）；函数性质与三角；运算律与记数；证明与不等式性质。

**边界**：因式分解须自证成立，否则退回展开式，常量 `kMaxPolyDeg`、`kCoefLimit` 在 `expression.cpp`。函数名白名单仅 `sin/cos/tan`，运算符白名单仅 `+`/`*`。排列数、组合数、比例化简溢出抛 `overflow_error`。

### 4.3 `harmonic_analysis`（调和分析）

**源**：`harmonic_analysis/harmonic_analysis_api.cpp`（319 行），编译 7 `.cpp` / 9 `.h`，CTest：`harmonic_analysis`。action 数 22。

**能力**：傅里叶级数与变换（`fourier_series`、`fourier_coeff`、`complex_fourier_coeff`、`fourier_transform`、`inverse_fourier_transform`、`ft_constant`、`ft_delta`、`ft_of_gaussian`）；卷积（`convolution`、`convolution_theorem`、`gaussian_blur`）；时频（`stft`、`wavelet_transform`、`low_pass_filter`）；广义函数（`delta_distribution`、`tempered_distribution`）；定理检查（`plancherel_theorem`、`uncertainty_principle`、`orthogonality_check`、`poisson_summation`）；θ 函数与函数方程（`theta_function`、`functional_equation_demo`）。

**边界**：`.h` 行数（1,362）超过 `.cpp`（1,335），实现主要落在 `ha_numeric.h`、`ha_rational_ft.h`、`ha_internal.h`。高斯核 sigma 上界：核长度超过 1000001 即抛错。时域圆卷积输入压到 4096。STFT 窗口零填充有上限、小波类型走白名单。

### 4.4 `probability`（概率统计）

**源**：`probability/probability_api.cpp`（554 行），编译 12 `.cpp` / 13 `.h`，CTest：`probability`。action 数 40。

**能力**：条件概率（`conditional_probability`、`total_probability`、`bayes_theorem`、`is_independent`）；分布（`normal`、`binomial`、`poisson`、`exponential`、`uniform`、`bernoulli`、`pmf`、`pdf`、`distribution_function`）；数字特征（`expectation_rv`、`prob_expectation`、`variance`、`covariance`、`correlation_coefficient`、`sample_mean`、`sample_variance`）；极限定理（`law_of_large_numbers`、`central_limit_theorem`）；估计（`mle`、`moment_estimate`、`confidence_interval`）；参数与非参数检验（`z_test`、`t_test`、`chi_square_test`、`p_value`、`mann_whitney_u`、`wilcoxon_signed_rank`、`kruskal_wallis`）；方差分析（`one_way_anova`、`two_way_anova`）；回归与时间序列（`linear_regression`、`predict`、`residuals`、`moving_average`、`exp_smoothing`、`linear_trend`）。

**边界**：只拒绝空输入，其余交给下游统计函数。零方差样本单独处理。近似同名 action 分属不同模块：`bernoulli`（分布）在本模块，`bernoulli_number`（数）在 `number_theory`；`binomial`（分布）在本模块，`binomial_expand`/`binomial_term` 在 `algebra`。

### 4.5 `numerical`（数值分析）

**源**：`numerical/numerical_api.cpp`（342 行），编译 7 `.cpp` / 12 `.h`，CTest：`numerical`。action 数 25。

**能力**：数值积分与微分（`trapezoidal_rule`、`simpson_rule`、`gauss_quadrature`、`numerical_derivative`、`optimal_step`）；ODE（`euler_method`、`implicit_euler`、`rk4`、`is_stable`、`stiff_detector`、`phase_portrait`）；插值（`lagrange_interpolation`、`newton_interpolation`、`cubic_spline`）；误差（`truncation_error`、`rounding_error_estimate`、`condition_number`）；迭代法（`jacobi_iteration`、`gauss_seidel`、`conjugate_gradient`、`lu_decomposition`、`qr_algorithm`、`power_method`）；优化与拟合（`gradient_descent`、`least_squares_fit`）。

**边界**：高斯求积阶数白名单仅 `n=2,3,4`。插值前置条件逐条拒绝（x 有重复点、三次样条至少 4 点）。目录内另有 5 个不编译的 `.cpp`（`interpolation_core.cpp`、`matrix_core.cpp`、`numerical_core.cpp`、`ode_core.cpp`、`optimization_core.cpp`），各自含 `PYBIND11_MODULE`，不在编译列表中：

```powershell
Select-String -Path MF_Mathematics/numerical/*_core.cpp -Pattern 'PYBIND11_MODULE'
```

### 4.6 `real_analysis`（实分析）

**源**：`real_analysis/real_analysis_api.cpp`（288 行），编译 7 `.cpp` / 7 `.h`，CTest：`real_analysis`。action 数 28。

**能力**：实数完备性（`supremum`、`infimum`、`dedekind_cut`、`archimedean_property`）；序列（`sequence_limit`、`sequence_convergence`、`cauchy_criterion`）；函数极限与连续（`limit_epsilon_delta`、`real_is_continuous`、`real_discontinuity_classify`、`uniform_continuity`、`intermediate_value`、`extreme_value`）；可导性（`derivative_definition`、`is_differentiable`、`real_rolle_theorem`、`real_lagrange_theorem`）；Riemann 积分（`darboux_sum`、`riemann_integrable`、`fundamental_theorem`、`integral_mean_value`）；函数列与函数项级数（`pointwise_convergence`、`uniform_convergence`、`weierstrass_m_test`、`termwise_differentiation`、`termwise_integration`、`taylor_polynomial`、`taylor_remainder`）。

**边界**：原函数为 `"未实现"` 时向上传播为「判据不可用」，不折算为 0。`limit` 不在本模块；符号极限求解 `limit`/`lhopital` 在 `calculus/limits.cpp`，两者不共用实现。本模块区间类 handler 只读 `interval` 键（见 [`CONTRACT.md`](CONTRACT.md) 的键名契约与 [`BOUNDARIES.md`](BOUNDARIES.md) 的区间契约守卫）。

### 4.7 `complex_analysis`（复分析）

**源**：`complex_analysis/complex_analysis_api.cpp`（401 行），编译 9 `.cpp` / 9 `.h`，CTest：`complex_grid`、`complex_analysis`。action 数 30。

**能力**：解析性（`is_holomorphic`、`cauchy_riemann`、`is_harmonic`）；复积分与定理（`contour_integral`、`cauchy_theorem`、`cauchy_integral_formula`、`derivative_formula`、`residue`、`residue_theorem`、`real_integral`）；级数（`taylor_series`、`laurent_series`、`zeta_series`）；奇点与幅角（`singularity_classify`、`pole_order`、`argument_principle`、`rouche_theorem`）；ζ 函数（`analytic_continuation_zeta`、`functional_equation_zeta`、`nontrivial_zeros`）；共形与拓扑（`is_conformal`、`mobius_transform`、`boundary_correspondence`、`riemann_mapping`、`is_open`、`is_connected`、`is_domain`）；初等复函数（`exp_complex`、`log_complex`、`sqrt_complex`）。

**边界**：ζ 的负整数点要求 `|Re s| ≤ 500`，该点由伯努利数给出，上限与 `number_theory` 的 `bernoulli_number` 一致。极点/本性奇点处不做泰勒展开，明确拒绝。共形映射区域走白名单。

### 4.8 `measure_theory`（测度论）

**源**：`measure_theory/measure_theory_api.cpp`（547 行），编译 8 `.cpp` / 8 `.h`，CTest：`measure_theory`。action 数 24。

**能力**：σ-代数（`is_sigma_algebra`、`generate_sigma_algebra`、`borel_sigma_algebra`）；测度构造（`outer_measure`、`caratheodory_measurable`、`lebesgue_measure`、`measure_properties`、`product_measure`）；可测函数与逼近（`is_measurable`、`simple_function`、`step_function_approx`）；积分（`integral_simple`、`integral_nonnegative`、`integral_general`、`integral_zero_set_independent`）；收敛定理（`monotone_convergence`、`fatou_lemma`、`dominated_convergence`）；Fubini（`fubini_theorem`）；概率测度（`probability_space`、`random_variable`、`meas_expectation`、`conditional_expectation`、`independence_check`）。

**边界**：生成 σ-代数有组合爆炸上界（生成元上限 200，代价 `O(N²)`/`O(N³)`）。样本空间上限 2000。被积函数不绝对可积时拒绝求值，不满足 Fubini 前提。

### 4.9 `linear_algebra`（线性代数）

**源**：`linear_algebra/linear_algebra_api.cpp`（416 行），编译 7 `.cpp` / 7 `.h`，CTest：`linear_algebra`。action 数 32。

**能力**：向量空间（`is_vector_space`、`subspace_span`、`basis`、`dimension`、`is_linear_independent`、`linear_combination`、`kernel`、`image`、`nullspace`、`rank`、`rank_nullity`）；线性变换与矩阵（`linear_transform`、`matrix_representation`、`matrix_inverse`）；线性方程组（`lin_solve_linear_system`、`gaussian_elimination`）；内积空间（`dot`、`norm`、`angle`、`lin_gram_schmidt`、`lin_is_orthogonal`、`orthogonal_projection`）；特征理论（`eigenvalues`、`eigenvectors`、`characteristic_polynomial`、`diagonalize`、`is_diagonalizable`）；二次型（`quadratic_form`、`standard_form`、`is_positive_definite`、`is_negative_definite`、`is_indefinite`）。

**边界**：符号矩阵动作（特征值、特征向量、特征多项式、对角化、可对角化）走 `get_matrix_symbolic`，上限 12×12；数值类动作不受此限。本模块没有 `get_int_bounded` 收口，规模闸门全部通过矩阵维度实现。

### 4.10 `algebraic_topology`（代数拓扑）

**源**：`algebraic_topology/at_api.cpp`（316 行），编译 6 `.cpp` / 6 `.h`，CTest：`algebraic_topology`。action 数 17，为 12 个模块中最少。

**能力**：单纯复形与链复形（`simplicial_complex`、`boundary_operator`、`filtration`）；同调与上同调（`homology_group`、`betti_numbers`、`euler_characteristic`、`cohomology_group`、`cup_product`、`poincare_duality`）；同伦（`fundamental_group`、`path_homotopy`、`is_simply_connected`）；映射度与不动点（`mapping_degree`、`brouwer_fixed_point_theorem`、`hairy_ball_theorem`）；持续同调（`persistence_diagram`、`barcode_plot`）。

**边界**：维数收口（`max_dim ≤ 20`、`n ≤ 100`、`sphere_dim ≤ 1000` 等）。复形参数用 JSON 对象表达（`{"complex": {"2": [[0,1,2],...], ...}}`）或已知空间名（`{"space": "T2", "n": 1}`）。

### 4.11 `number_theory`（数论）

**源**：`number_theory/number_theory_api.cpp`（299 行），编译 7 `.cpp` / 7 `.h`，CTest：`number_theory`。action 数 24。

**能力**：初等数论（`gcd`、`extended_gcd`、`is_prime`、`prime_factors`、`divisor_count`、`divisor_sum`、`euler_phi`、`mobius`、`mobius_prefix`）；同余（`mod_pow`、`mod_inverse`、`crt`、`discrete_log`、`primitive_root`）；筛法（`eratosthenes`、`segmented_sieve`）；连分数（`continued_fraction`、`convergents`、`best_rational_approximation`）；ζ 与 L 函数接口（`bernoulli_number`、`euler_product`、`zeta_dirichlet_series`、`zeta_negative`、`dirichlet_l_function`）。

**边界**：整数上界最密（17 处），模块自带 `get_int_bounded`。连分数迭代有安全上限 100。ζ 的 500 上界与 `complex_analysis/zeta.cpp` 一致。`algebra/number_theory.cpp` 是 `algebra` 目录下的文件，负责运算律与比例化简，与 `number_theory/` 目录无关系。

### 4.12 `functional_analysis`（泛函分析）

**源**：`functional_analysis/fa_api.cpp`（298 行），编译 7 `.cpp` / 7 `.h`，CTest：`functional_analysis`。action 数 21。

**能力**：赋范空间（`lp_norm`、`is_banach`、`space_completeness_check`）；内积空间（`inner_product`、`is_hilbert`、`funct_gram_schmidt`、`funct_is_orthogonal`）；有界算子（`is_bounded`、`operator_norm`、`kernel_dimension`、`linear_functional_eval`）；对偶与三大定理（`dual_space_basis`、`hahn_banach_extension`、`is_reflexive`、`open_mapping`、`uniform_boundedness`、`closed_graph`）；谱（`spectrum_approx`、`spectrum_classify`、`spectral_theorem`）；收敛（`weak_convergence`）。

**边界**：空矩阵 0×0 当场拒绝。范数阶数走白名单。6 个算子性质 action 在 `extras/`（见「extras 的 25 条」一节）。

## 5. 学科模块之外

### 5.1 `extras/` 的 25 条

`extras/` 是独立目录，不是 12 个学科模块之一。其设计原则：能给出确定结论的给结论，只能数值求解的标注数值结果与扫描区间，方法不适用时返回原因。

| 主题 | 落在 `extras/` 的 action | 条数 |
| --- | --- | --- |
| 曲线分析（属 `calculus` 范畴） | `calc_asymptotes`、`calc_cauchy_mvt`、`calc_concavity`、`calc_curvature`、`calc_inflection` | 5 |
| 级数与无穷乘积 | `absolute_convergence`、`product_sequence`、`infinite_product`、`dirichlet_eta` | 4 |
| 微分方程（属 `numerical` 范畴） | `ode_first_order`、`ode_constant_coefficients`、`ode_linear_system`、`first_order_linear_pde`、`classify_second_order_pde` | 5 |
| 线性代数 | `matrix_multiply` | 1 |
| 泛函分析 | `adjoint_operator`、`is_compact_operator`、`is_self_adjoint`、`riesz_representation`、`spectral_radius`、`fredholm_alternative` | 6 |
| 复分析 | `complex_argument`、`complex_conjugate`、`complex_modulus`、`zeros_and_poles` | 4 |

`extras/` 目录规模：`analysis.cpp` 1,825 行、`extras.cpp` 182 行、`extras_api.cpp` 310 行；头 `analysis.h` 135 行、`extras.h` 63 行。

### 5.2 根目录的 22 条

根目录 5 个 `*_api.cpp` 不按学科切分，共 22 个 action：

| 文件 | action 数 | 内容 | CTest |
| --- | --- | --- | --- |
| `expr_api.cpp` | 9 | `prepare_expr`、`expr_eval`、`expr_eval2`、`expr_eval_vars`、`expr_eval_batch`、`expr_eval_vars_batch`、`expr_eval_grid`、`to_engine_expr`、`sym_latex` | 无专属用例 |
| `symbolic_api.cpp` | 7 | `simplify_sym`、`factor_sym`、`solve_sym`、`compare_expr`、`discriminant_sym`、`extrema_sym`、`free_symbols_of` | `symbolic_contract` |
| `plot_api.cpp` | 4 | `complex_grid`、`complex_eval`、`complex_eval_many`、`intersections` | `complex_grid` |
| `introspect_api.cpp` | 1 | `list_functions` | 间接（`count == 424` 断言） |
| `fractal_api.cpp` | 1 | `mandelbrot` | 无专属用例 |

两条影响返回值形状的跨模块上界：

- `complex_grid` 点数上限 400,000（`plot_api.cpp`），`expr_eval_grid` 对齐到同一值（`expr_api.cpp`）。
- `mandelbrot` 的点数上限是 4,000,000（`fractal_api.cpp`），因为分形结果不逐点回传。

符号层 `expr_api.cpp` / `symbolic_api.cpp` 的细节见 [`SYMBOLIC.md`](SYMBOLIC.md)，采样与视口层 `plot_api.cpp` / `fractal_api.cpp` 见 [`PLOT.md`](PLOT.md)。
