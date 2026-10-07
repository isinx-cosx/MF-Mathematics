# 引擎的 12 个学科模块

> **本文只回答一个问题：引擎的 12 个学科模块各有什么、边界在哪。**
>
> 与同层其它文档的分工：
> - [`README.md`](README.md) —— 两个构建目标、C ABI 的机械语义、怎么构建（本文只讲**注册了什么**，不讲怎么注册）；
> - [`CONTRACT.md`](CONTRACT.md) —— args JSON 形状与**键名契约**、必填拒绝、"未实现"的返回形状（本文只给边界判据的**位置**，不复述键名）；
> - [`TESTS.md`](TESTS.md) —— 19 个可执行目标 / 16 个 CTest 用例的完整清单与守门断言（本文只标出每个模块对应哪条用例）；
> - [`BOUNDARIES.md`](BOUNDARIES.md) —— 跨模块的能力边界与 `NOT_EXPOSED` 口径（本文讲**模块内**的数值收口与显式拒绝）；
> - [`SYMBOLIC.md`](SYMBOLIC.md) —— 符号层（`symbolic_api.cpp` / `expr_api.cpp`）的 `RCP` 边界与化简择优（本文只把这 16 条 action 列进 §5.2）。

**证据基线**：2026-10-07 本机实测。产物 `MF_Mathematics/build/bin/Release/mf_mathematics.dll`
（LastWriteTime 2026-10-06 05:43:00）、`probe_call.exe`（05:43:03）。**产物不比源码旧**：
`MF_Mathematics/` 下（不含 `build/`）最新的源文件是 `tests/test_algebraic_topology.cpp`
（05:42:47），早于 DLL 的 05:43:00。`MF_Mathematics/build/` 不入 git，故每个数字都附复跑命令。

---

## 1. 本文是生成的，不是手抄的

**行数口径写死**为 `file.split('\n').length`，即**按 `\n` 切分**：含空行，且文件以换行结尾时多出 1 个空元素。
（不要用 `Get-Content | Measure-Object -Line` —— 它不数空行，`calculus` 会得到 4,093 而不是 4,330。）

**命令 A —— 每个模块有多少 action（权威归属）**

```powershell
node -e "const j=require('./MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json');const g={};for(const n of Object.keys(j)){const f=j[n].file;const d=f.includes('/')?f.split('/')[0]:'(根级) '+f;g[d]=(g[d]||0)+1;}console.log('total',Object.keys(j).length);for(const [d,c] of Object.entries(g).sort((a,b)=>b[1]-a[1]))console.log(String(c).padStart(4),d);"
```

实测（2026-10-07 10:40）：`total 424`，随后 13 行目录计数 + 5 行根级文件计数。

**命令 B —— 每个模块的文件数与行数（与 `CMakeLists.txt` 交叉）**

```powershell
node -e "const fs=require('fs');const E='MF_Mathematics';const M=['calculus','algebra','harmonic_analysis','probability','numerical','real_analysis','complex_analysis','measure_theory','linear_algebra','algebraic_topology','number_theory','functional_analysis'];const cm=fs.readFileSync(E+'/CMakeLists.txt','utf8');const L=new Set([...cm.matchAll(/^\s+((?:[a-z_]+\/)?[A-Za-z_0-9]+\.cpp)\s*$/gm)].map(m=>m[1]));const S=JSON.parse(fs.readFileSync('MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json','utf8'));const N=Object.keys(S);const ln=f=>fs.readFileSync(f,'utf8').split('\n').length;console.log('module\tcmakeCpp\tdiskCpp\tdiskH\tcppLines\thLines\tactions');for(const m of M){const a=fs.readdirSync(E+'/'+m);const c=a.filter(x=>x.endsWith('.cpp')),h=a.filter(x=>x.endsWith('.h'));const cc=c.filter(x=>L.has(m+'/'+x));console.log([m,cc.length,c.length,h.length,cc.reduce((s,x)=>s+ln(E+'/'+m+'/'+x),0),h.reduce((s,x)=>s+ln(E+'/'+m+'/'+x),0),N.filter(n=>S[n].file.startsWith(m+'/')).length].join('\t'));}"
```

**命令 C —— 盘上有、但不编译的引擎源（`diskCpp` 与 `cmakeCpp` 的差额）**

```powershell
node -e "const fs=require('fs'),p=require('path');const E='MF_Mathematics';const w=(d,o=[])=>{for(const e of fs.readdirSync(d,{withFileTypes:true})){if(e.name==='build')continue;const q=p.join(d,e.name);e.isDirectory()?w(q,o):o.push(q);}return o;};const all=w(E).filter(f=>f.endsWith('.cpp')&&!p.relative(E,f).startsWith('tests'+p.sep));const L=new Set([...fs.readFileSync(E+'/CMakeLists.txt','utf8').matchAll(/^\s+((?:[a-z_]+\/)?[A-Za-z_0-9]+\.cpp)\s*$/gm)].map(m=>m[1]));L.add('api.cpp');const nc=all.map(f=>p.relative(E,f).split(p.sep).join('/')).filter(r=>!L.has(r));console.log('盘上',all.length,'编译',L.size,'未编译',nc.length);nc.forEach(r=>console.log(' ',r));"
```

实测（10:48）：`盘上 110 编译 103 未编译 7` —— `demo/eigen_test.cpp`、`demo/main.cpp`、
`numerical/interpolation_core.cpp`、`numerical/matrix_core.cpp`、`numerical/numerical_core.cpp`、
`numerical/ode_core.cpp`、`numerical/optimization_core.cpp`。后 5 个在 `numerical` 模块目录里，
所以 §3 只有 `numerical` 一行的「`.cpp`」「`.cpp` 行」需要打折扣。

**命令 D —— 三个来源对账（函数集合必须逐字一致）**

```powershell
node MF_UI/MFMath.UI.Vue/tools/engine-signatures.mjs --check      # 源码 register_function ↔ 签名表
MF_Mathematics\build\bin\Release\probe_call.exe --list            # 运行时注册表 ↔ 签名表
cd MF_Mathematics\build; ctest -C Release --output-on-failure     # 16 条用例
```

| 检查 | 2026-10-07 实测结果 |
| --- | --- |
| `engine-signatures.mjs --check` | `源码 register_function 424 条 / 表 424 条`，`✓ 无漂移`，exit 0；另有 `提示（不判定失败）124 处` |
| `probe_call.exe --list` | `count` = **424**，`functions` 数组长度 424、无重复；与签名表的键**双向零差异** |
| `ctest -C Release` | **16/16 Passed**，`Total Test time (real) = 1.97 sec`（`build/Testing/Temporary/LastTest.log`：`Start testing: Oct 07 10:42`） |

---

## 2. 归属规则

**规则**：`engine-signatures.json` 每个键值对里有一个 `file` 字段，取它的**第一段路径**作为模块名。
`file` 的定义不由本文发明，它是 `MF_UI/MFMath.UI.Vue/tools/engine-signatures.mjs` 生成的。
⚠ 该脚本**正被并行会话修改**（`git status` 里是 ` M`），行号会漂，所以下面按**符号**引用、
括号里给 2026-10-07 10:50 核对时的行号：`apiFiles()`（:59-67）递归遍历 `MF_Mathematics/`、
**跳过 `build/` 与 `tests/`**、只收 `*_api.cpp` 与 `api.cpp`；`const rel = path.relative(ENGINE, file)`（:77）
就是 `file` 字段；`text.matchAll(/register_function\s*\(\s*"([^"]+)"/g)`（:79）按注册调用切块。
**所以 `file` 是"注册该 action 的那个 `*_api.cpp`"，不是"实现它的那个 `.cpp`"。**

**这个规则被独立验证过一次**（不是自证）：按各模块 `*_api.cpp` 里 `register_function("…")` 的**出现次数**
直接数一遍，与签名表按 `file` 分组的结果**在 12 个模块上逐条相等、两个方向都无差异**（见 §3 的
「`.cpp`」与「action」两列，以及 `CMakeLists.txt`:29-130 的编译列表）。

**归不上的 47 条分两类**（细则见 §5）：**`extras/` 目录 25 条** —— 它**不是 12 个学科模块之一**，
是"视图里未接入引擎的模式"的补齐件（`extras/extras_api.cpp`:1-4）；**引擎根目录 5 个 `*_api.cpp` 共 22 条** ——
`expr_api.cpp` 9 / `symbolic_api.cpp` 7 / `plot_api.cpp` 4 / `introspect_api.cpp` 1 / `fractal_api.cpp` 1，
它们是引擎内核与跨模块面，按学科切分不成立。**25 + 22 + 377 = 424**，其中 **377** 是 12 个模块的 action 总数。

---

## 3. 总表（12 行）

「`.cpp`」列只数**在 `CMakeLists.txt` 里被编译**的；「`.h`」列数**目录内全部** `.h`，
因为头文件是否被引用无法从 `CMakeLists.txt` 判定。行数口径见 §1。

| 模块 | `CMakeLists.txt` 行 | `.cpp` | `.h` | `.cpp` 行 | `.h` 行 | action | 注册文件（行数） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `calculus` | 74-80 | 7 | 6 | 4,330 | 285 | **35** | `calculus/calculus_api.cpp`（355） |
| `algebra` | 48-56 | 9 | 8 | 2,802 | 547 | **79** | `algebra/algebra_api.cpp`（627） |
| `harmonic_analysis` | 95-101 | 7 | 9 | 1,335 | 1,362 | **22** | `harmonic_analysis/harmonic_analysis_api.cpp`（319） |
| `probability` | 110-121 | 12 | 13 | 1,649 | 851 | **40** | `probability/probability_api.cpp`（554） |
| `numerical` | 60-66 | 7 ⚠ | 12 | 992 ⚠ | 999 | **25** | `numerical/numerical_api.cpp`（342） |
| `real_analysis` | 81-87 | 7 | 7 | 1,249 | 595 | **28** | `real_analysis/real_analysis_api.cpp`（288） |
| `complex_analysis` | 122-130 | 9 | 9 | 1,358 | 467 | **30** | `complex_analysis/complex_analysis_api.cpp`（401） |
| `measure_theory` | 102-109 | 8 | 8 | 1,230 | 547 | **24** | `measure_theory/measure_theory_api.cpp`（547） |
| `linear_algebra` | 88-94 | 7 | 7 | 1,226 | 453 | **32** | `linear_algebra/linear_algebra_api.cpp`（416） |
| `algebraic_topology` | 42-47 | 6 | 6 | 953 | 556 | **17** | `algebraic_topology/at_api.cpp`（316） |
| `number_theory` | 35-41 | 7 | 7 | 1,111 | 283 | **24** | `number_theory/number_theory_api.cpp`（299） |
| `functional_analysis` | 67-73 | 7 | 7 | 847 | 238 | **21** | `functional_analysis/fa_api.cpp`（298） |
| **合计** | — | **93** | **99** | **19,082** | **7,183** | **377** | — |

⚠ `numerical` 目录有 **5 个不编译的 `.cpp`**（盘上 12 个、编译 7 个，合计 **339 行**，§1 命令 C）。
该模块 `.cpp` 有两个口径：**编译单元 992 行**（总表采用）与**目录内全部 1,331 行**；
`.cpp` + `.h` 分别是 `1,991` 与 `2,330`。引用 §4.5 的数字时请一并引用这条。

---

## 4. 逐个模块

每节的「action 数出处」都是同一个规则：`engine-signatures.json` 里 `file` 字段等于该模块 `*_api.cpp` 的键数（§2）。
每节的「源」行给出注册文件行数与编译单元；每节的「CTest」行给出对应用例。
每节的「能力」段**逐条列出该模块的全部 action 名**（已用 §1 命令 A 的输出核对过：12 个模块全覆盖），
所以它可以直接当作"这个模块有哪些函数"的清单用；**边界段只列有明确判据的那些**，不是穷举。

### 4.1 `calculus`（微积分）

**源**：`calculus/calculus_api.cpp`（355 行）；编译 7 `.cpp` / 6 `.h`（`CMakeLists.txt`:74-80：
`derivatives.cpp`、`integrals.cpp`、`derivatives_app.cpp`、`integrals_app.cpp`、`series.cpp`、`limits.cpp` + API 层）；**action 数 35**，出处 = `file` == `calculus/calculus_api.cpp`。**CTest**：`limits`（`tests/test_limits.cpp`）、`calculus`（`tests/test_calculus.cpp`）。

**能力**：符号求导与微分（`diff`、`diff_at`、`parametric_diff`、`implicit_diff`、`differential`）；积分（`integrate`、`integrate_numeric`、`integrate_double`、`integrate_triple`、`integrate_complex`、`improper_integral`）；级数与幂级数（`series_convergence`、`series_sum`、`power_series`、`power_series_radius`、`taylor`）；极限（`limit`、`lhopital`）；几何应用（`arc_length`、`area_between`、`volume_disk`、`volume_shell`）；极值与单调性（`local_extrema`、`global_extrema`、`monotonicity`）；连续性/中值定理（`calc_is_continuous`、`calc_discontinuity_classify`、`calc_rolle_theorem`、`calc_lagrange_theorem`）；六种审敛法（`integral_test`、`direct_comparison_test`、`limit_comparison_test`、`p_series_test`、`leibniz_test`、`classify_and_test`）。

**边界**：
- **积不出来返回 `"未实现"`，不给近似值冒充** —— `calculus/integrals.cpp`:1052 `if (F.is_null()) return "未实现";`；`:1232`/`:1234`/`:1251`/`:1253`/`:1255` 是重积分各方向的同一处理。守它的是 `tests/test_calculus.cpp`:102（`∫x**x dx` 必须返回 `"未实现"`）与 `:140`（`e^{-x²}`/`1/ln x`/`x²e^{-x²}` 仍返回 `"未实现"` **是正确行为**）。
- **极限有硬预算，超了报错而不是挂住** —— `calculus/limits.cpp`:87-91 `kLimMaxDepth = 12`、`kLimMaxLhopital = 10`、`kLimMaxNormalize = 12`、`kLimMaxSteps = 3000`、`kLimBudgetMs = 1500.0`；`:139` 超预算抛 `std::domain_error("极限求解超出时间/步数预算…")`。
- **参数上界** —— `calculus/calculus_api.cpp`:280 抛 `求和上界 b 超出可计算范围 [-1000000, 1000000]`；`:50`/`:58` `order ≤ 1000`、`:241` `order ≤ 200`、`:311` `n ≤ 200`（均 `get_int_opt_bounded`，默认 1 / 1 / 3 / 5）。

### 4.2 `algebra`（代数）

**源**：`algebra/algebra_api.cpp`（627 行）；编译 9 `.cpp` / 8 `.h`（`CMakeLists.txt`:48-56：
`combinatorics.cpp`、`number_theory.cpp`、`analytic_geometry.cpp`、`equation.cpp`、`function.cpp`、`expression.cpp`、`inequality.cpp`、`sequences.cpp` + API 层）；**action 数 79**（12 个模块里最多），出处 = `file` == `algebra/algebra_api.cpp`。**CTest**：`algebra`（`tests/test_algebra.cpp`）。

**能力**：化简与因式分解（`simplify_polynomial`、`simplify_fraction`、`simplify_radical`、`expand_expression`、`common_denominator`、`fraction_operations`、`rationalize_denominator`、`like_radicals`、`radical_operations`、`factor` 及 `factor_common`/`factor_cross`/`factor_difference_squares`/`factor_group`/`factor_perfect_square`）；方程与不等式（`solve_linear`、`solve_quadratic`、`solve_fractional`、`solve_irrational`、`solve_linear_inequality`、`solve_quadratic_inequality`、`solve_inequality_system`、`alg_solve_linear_system`、`discriminant`、`vieta_theorem`）；数列（`arithmetic_sequence`、`geometric_sequence`、`recurrence_sequence`、`sequence_term`、`arithmetic_sum`、`geometric_sum`）；计数（`permutation`、`combination`、`binomial_expand`、`binomial_term`、`addition_principle`、`multiplication_principle`）；解析几何（`line_from_points`/`line_from_slope_intercept`/`line_from_point_slope`/`line_from_intercepts`、`line_general`、`slope_intercept`、`circle_standard`/`circle_general`、`parabola_standard`、`ellipse_standard`、`hyperbola_standard`、`distance`、`distance_on_number_line`、`midpoint`、`inverse_proportional`）；函数性质（`domain`、`range_estimate`、`power_function`、`exponential_function`、`log_function`、`linear_function`、`quadratic_function`、`abs_value`、`ratio`、`quadratic_extrema`、`max_min_initial`、`correspondence_rule`）；三角（`trig_basic_identities`、`trig_periodicity`、`sine_cosine_tangent`）；运算律与记数（`commutative_law`、`associative_law`、`distributive_law`、`significant_figures`、`to_scientific_notation`、`percentage`、`percentage_change`）；证明与不等式性质（`arithmetic_proof`、`geometric_proof`、`am_gm_inequality`、`comb_identities`、`inequality_properties`）。

**边界**：
- **因式分解必须自证，不成立就退回展开式** —— `algebra/expression.cpp`:45-47 写明三道校验（真实次数、逐项系数比对、渲染成字符串再解析回来校验一次）；`:127` `if (!factorization_holds(cand, e)) return {};`；`:379` `if (out.empty()) return expanded;`。规模上界 `:49` `kMaxPolyDeg = 32`、`:50` `kCoefLimit = 100000`。
- **只有部分函数/运算符被支持** —— `algebra/function.cpp`:366 `不支持 '<func>',仅支持 sin, cos, tan`（`tests/test_algebra.cpp`:260 钉住 `trig_periodicity 不支持 cot → 抛异常`）；`algebra/number_theory.cpp`:65、`:79` `不支持的运算符 '<op>',仅支持 '+' 和 '*'`；`algebra/sequences.cpp`:91 抛 `递推规则引用了超出初始值历史范围的项`。
- **溢出如实报错** —— `combinatorics.cpp`:53 排列数、`:77` 组合数、`number_theory.cpp`:108 比例化简，都是 `throw std::overflow_error(...)`。
- **参数上界（8 处，全在必填参数上）** —— `algebra_api.cpp`:88/91 `n ≤ 1,000,000`、`:102`/`:107` `n ≤ 1,000`（二项式指数）、`:579`/`:593`/`:600`/`:614` `n ≤ 100,000`（项数）。

### 4.3 `harmonic_analysis`（调和分析）

**源**：`harmonic_analysis/harmonic_analysis_api.cpp`（319 行）；编译 7 `.cpp` / 9 `.h`（`CMakeLists.txt`:95-101：
`fourier_series.cpp`、`fourier_transform.cpp`、`convolution.cpp`、`distributions.cpp`、`time_frequency.cpp`、`zeta_harmonic.cpp` + API 层）；**action 数 22**，出处 = `file` == `harmonic_analysis/harmonic_analysis_api.cpp`。**CTest**：`harmonic_analysis`（`tests/test_harmonic_analysis.cpp`）。

**能力**：傅里叶级数与变换（`fourier_series`、`fourier_coeff`、`complex_fourier_coeff`、`fourier_transform`、`inverse_fourier_transform`、`ft_constant`、`ft_delta`、`ft_of_gaussian`）；卷积（`convolution`、`convolution_theorem`、`gaussian_blur`）；时频（`stft`、`wavelet_transform`、`low_pass_filter`）；广义函数（`delta_distribution`、`tempered_distribution`）；定理级检查（`plancherel_theorem`、`uncertainty_principle`、`orthogonality_check`、`poisson_summation`）；θ 函数与 ζ 函数方程（`theta_function`、`functional_equation_demo`）。

**边界**：
- **`.h` 行数（1,362）比 `.cpp`（1,335）还多**，因为实现主要落在三个内部头里：`ha_numeric.h` 577 行、`ha_rational_ft.h` 373 行、`ha_internal.h` 166 行（合计 1,116 行）。不要把"`.h` 看起来少"当成"实现少"。
- **高斯核长度硬上限** —— `harmonic_analysis/convolution.cpp`:106 抛 `sigma 过大：高斯核长度会超过 1000001`；`:51` 另把时域圆卷积输入压到 4096。
- **STFT 窗口零填充上限 / 小波白名单** —— `time_frequency.cpp`:137 抛 `窗口长度过大：零填充到 2 的幂后超过上限。请减小窗口。`；`:190` 抛 `不支持的小波类型`。
- **参数上界** —— `harmonic_analysis_api.cpp`:92/118 `n ≤ 100,000`（必填）、`:102` `n_terms ≤ 200`（必填）、`:244` `window_size ∈ [2, 65536]`（必填）、`:245` `hop_size ∈ [0, 65536]`、`:278` `n_terms ≤ 200`（默认 50）、`:292` `n_terms ≤ 200`（默认 100）。

### 4.4 `probability`（概率统计）

**源**：`probability/probability_api.cpp`（554 行）；编译 12 `.cpp` / 13 `.h`（`CMakeLists.txt`:110-121：
`probability_space.cpp`、`random_variable.cpp`、`expectations.cpp`、`distributions.cpp`、`statistics.cpp`、`limits_theorems.cpp`、`hypothesis_test.cpp`、`nonparametric.cpp`、`anova.cpp`、`regression.cpp`、`time_series.cpp` + API 层）；**action 数 40**，出处 = `file` == `probability/probability_api.cpp`。**CTest**：`probability`（`tests/test_probability.cpp`）。

**能力**：概率与条件概率（`conditional_probability`、`total_probability`、`bayes_theorem`、`is_independent`）；分布（`normal`、`binomial`、`poisson`、`exponential`、`uniform`、`bernoulli` 及 `pmf`/`pdf`/`distribution_function`）；数字特征（`expectation_rv`、`prob_expectation`、`variance`、`covariance`、`correlation_coefficient`、`sample_mean`、`sample_variance`）；极限定理（`law_of_large_numbers`、`central_limit_theorem`）；估计（`mle`、`moment_estimate`、`confidence_interval`）；参数检验（`z_test`、`t_test`、`chi_square_test`、`p_value`）；非参数检验（`mann_whitney_u`、`wilcoxon_signed_rank`、`kruskal_wallis`）；方差分析（`one_way_anova`、`two_way_anova`）；回归与时间序列（`linear_regression`、`predict`、`residuals`、`moving_average`、`exp_smoothing`、`linear_trend`）。

**边界**：
- **三对近似同名的 action 分属三个模块** —— `bernoulli`（伯努利**分布**）在本模块，`bernoulli_number`（伯努利**数**）在 `number_theory/number_theory_api.cpp`，`binomial`（二项分布）在本模块而 `binomial_expand`/`binomial_term` 在 `algebra`。
- **只拒绝空输入，其余交给下游** —— `probability/probability_api.cpp`:45 注释写明"只拒绝空输入 —— 空数组传到下游统计函数里会变成非法下标访问"。这是**刻意的**边界选择：引擎不为统计方法做适用性预判。
- **零方差样本单独处理** —— `probability/hypothesis_test.cpp`:49 "零方差样本：t 无定义。均值恰为 mu0 → 无法拒绝；否则 → 显著"；`tests/test_probability.cpp`:157/160 钉住 `z_test`/`t_test` 的 `reject_H0` 字段语义。
- **参数上界** —— `probability_api.cpp`:288 `n ≤ 1,000,000`（试验次数）、`:359`/`:369`/`:383` `n ≤ 1,000,000`（样本数，三个检验都是必填）、`:519` `window ≤ 1,000,000`（默认 3）、`:537` `forecast_steps ≤ 1,000,000`（默认 3）。

### 4.5 `numerical`（数值分析）

**源**：`numerical/numerical_api.cpp`（342 行）；编译 7 `.cpp` / 12 `.h`（`CMakeLists.txt`:60-66：
`numerical_integration.cpp`、`ode_solver.cpp`、`interpolation.cpp`、`error_stability.cpp`、`optimization.cpp`、`matrix_numerical.cpp` + API 层）；**目录内另有 5 个不编译的 `.cpp`**（§3 ⚠、§6.1）；**action 数 25**，出处 = `file` == `numerical/numerical_api.cpp`。**CTest**：`numerical`（`tests/test_numerical.cpp`）。

**能力**：数值积分与微分（`trapezoidal_rule`、`simpson_rule`、`gauss_quadrature`、`numerical_derivative`、`optimal_step`）；ODE（`euler_method`、`implicit_euler`、`rk4`、`is_stable`、`stiff_detector`、`phase_portrait`）；插值（`lagrange_interpolation`、`newton_interpolation`、`cubic_spline`）；误差（`truncation_error`、`rounding_error_estimate`、`condition_number`）；迭代法（`jacobi_iteration`、`gauss_seidel`、`conjugate_gradient`、`lu_decomposition`、`qr_algorithm`、`power_method`）；优化（`gradient_descent`）；拟合（`least_squares_fit`）。

**边界**：
- **公式阶数白名单** —— `numerical/numerical_integration.cpp`:41 `throw std::invalid_argument("高斯求积目前仅支持 n=2,3,4")`；`:21`/`:27` 子区间数 `n ≤ 0` 直接拒绝。
- **插值的前置条件逐条拒绝** —— `numerical/interpolation.cpp`:38 `x 值中存在重复点,牛顿插值要求各点 x 坐标互不相同`；`:46` `三次样条至少需要 4 个点`；`interpolation_core.h`:69 另有 `n < 2` 的结点下限。
- **奇异/不收敛显式拒绝而不是给近似解** —— 迭代法里有 `矩阵奇异或需要行交换: 主元接近零`、`对角元素含零,无法直接使用雅可比迭代`、`pᵀAp 接近零,矩阵可能非正定或不满足收敛条件`。
- **本模块参数上界最密（13 处）** —— `numerical_api.cpp`:253 `n ≤ 1,000,000`（必填，采样点数）、`:145`/`:149`/`:153` `n ≤ 10,000,000`、`:192` `n_trajectories ≤ 100`、`:193` `resolution ≤ 200`、`:235` `degree ≤ 20`，以及 6 处 `max_iter ≤ 100,000`（`:268`、`:293`、`:303`、`:313`、`:320`、`:332`）。

### 4.6 `real_analysis`（实分析）

**源**：`real_analysis/real_analysis_api.cpp`（288 行）；编译 7 `.cpp` / 7 `.h`（`CMakeLists.txt`:81-87：
`differentiability.cpp`、`sequence_limit.cpp`、`real_numbers.cpp`、`riemann_integral.cpp`、`function_limit.cpp`、`function_series.cpp` + API 层）；**action 数 28**，出处 = `file` == `real_analysis/real_analysis_api.cpp`。**CTest**：`real_analysis`（`tests/test_real_analysis.cpp`）。

**能力**：实数完备性（`supremum`、`infimum`、`dedekind_cut`、`archimedean_property`）；序列（`sequence_limit`、`sequence_convergence`、`cauchy_criterion`）；函数极限与连续（`limit_epsilon_delta`、`real_is_continuous`、`real_discontinuity_classify`、`uniform_continuity`、`intermediate_value`、`extreme_value`）；可导性（`derivative_definition`、`is_differentiable`、`real_rolle_theorem`、`real_lagrange_theorem`）；Riemann 积分（`darboux_sum`、`riemann_integrable`、`fundamental_theorem`、`integral_mean_value`）；函数列与函数项级数（`pointwise_convergence`、`uniform_convergence`、`weierstrass_m_test`、`termwise_differentiation`、`termwise_integration`、`taylor_polynomial`、`taylor_remainder`）。

**边界**：
- **"原函数未实现"向上传播成"这条判据不可用"，而不是变成 0** —— `real_analysis/riemann_integral.cpp`:118 `if (r.antiderivative == "未实现") {`。
- **`limit` 不在本模块** —— 本模块只有 `limit_epsilon_delta`（ε-δ 定义级）；一符号式的极限求解在 `calculus/limits.cpp`（action `limit`、`lhopital`）。**两处不共用同一份实现**，比对二者结果时不要当成一个东西。
- **`.h` 里最大的是 `ra_internal.h`（348 行）** —— 本模块 `.h` 合计 595 行，一半以上在这个内部头里。
- **参数上界** —— `real_analysis_api.cpp`:63/69 `n ≤ 100`（默认 3）、`:115` `max_n ≤ 100,000`（默认 1000）、`:266`/`:274` `n_terms ≤ 200`（默认 10 / 5）。

### 4.7 `complex_analysis`（复分析）

**源**：`complex_analysis/complex_analysis_api.cpp`（401 行）；编译 9 `.cpp` / 9 `.h`（`CMakeLists.txt`:122-130：
`complex_integral.cpp`、`complex_topology.cpp`、`conformal.cpp`、`holomorphic.cpp`、`series.cpp`、`elementary_funcs.cpp`、`zeta.cpp`、`residue.cpp` + API 层）；**action 数 30**，出处 = `file` == `complex_analysis/complex_analysis_api.cpp`。**CTest**：`complex_grid`（`tests/test_complex_grid.cpp`）、`complex_analysis`（`tests/test_complex_analysis.cpp`）。

**能力**：解析性（`is_holomorphic`、`cauchy_riemann`、`is_harmonic`）；复积分与三大定理（`contour_integral`、`cauchy_theorem`、`cauchy_integral_formula`、`derivative_formula`、`residue`、`residue_theorem`、`real_integral`）；级数（`taylor_series`、`laurent_series`、`zeta_series`）；奇点与幅角（`singularity_classify`、`pole_order`、`argument_principle`、`rouche_theorem`）；ζ 函数（`analytic_continuation_zeta`、`functional_equation_zeta`、`nontrivial_zeros`）；共形与拓扑（`is_conformal`、`mobius_transform`、`boundary_correspondence`、`riemann_mapping`、`is_open`、`is_connected`、`is_domain`）；初等复函数（`exp_complex`、`log_complex`、`sqrt_complex`）。

**边界**：
- **ζ 的负整数点有明确可算范围** —— `complex_analysis/zeta.cpp`:26-30 抛 `超出可算范围（负整数点要求 |Re s| ≤ 500）`，并说明该点由伯努利数 `B_{n+1}` 给出；上限与 `number_theory` 的 `bernoulli_number`（`number_theory_api.cpp`:286/289 `n ≤ 500`）**刻意保持一致**。
- **极点/本性奇点处不做泰勒展开** —— `complex_analysis/series.cpp`:110 注释："极点 / 本性奇点处不存在泰勒展开,必须明确拒绝"。
- **共形映射的区域是白名单** —— `complex_analysis/conformal.cpp`:61 `throw std::invalid_argument("不支持的区域: " + region)`。
- **`zeros_and_poles` 不在本模块** —— 它在 `extras/extras_api.cpp`（§5.1）。
- **参数上界** —— `complex_analysis_api.cpp`:172 `n ≤ 100`（**必填**，阶数）、`:138`/`:158`/`:173` `n_points ≤ 10,000`（默认 1000）、`:284` `n ≤ 200`（默认 6）、`:290` `n ≤ 200`（默认 5）、`:326` `n_terms ≤ 1,000,000`（默认 1000）。

### 4.8 `measure_theory`（测度论）

**源**：`measure_theory/measure_theory_api.cpp`（547 行）；编译 8 `.cpp` / 8 `.h`（`CMakeLists.txt`:102-109：
`set_systems.cpp`、`measurable_functions.cpp`、`measure_construction.cpp`、`lebesgue_integral.cpp`、`convergence_theorems.cpp`、`probability_measure.cpp`、`product_measure.cpp` + API 层）；**action 数 24**，出处 = `file` == `measure_theory/measure_theory_api.cpp`。**CTest**：`measure_theory`（`tests/test_measure_theory.cpp`）。

**能力**：σ-代数（`is_sigma_algebra`、`generate_sigma_algebra`、`borel_sigma_algebra`）；测度构造（`outer_measure`、`caratheodory_measurable`、`lebesgue_measure`、`measure_properties`、`product_measure`）；可测函数与逼近（`is_measurable`、`simple_function`、`step_function_approx`）；积分（`integral_simple`、`integral_nonnegative`、`integral_general`、`integral_zero_set_independent`）；收敛定理（`monotone_convergence`、`fatou_lemma`、`dominated_convergence`）；Fubini（`fubini_theorem`）；概率测度（`probability_space`、`random_variable`、`meas_expectation`、`conditional_expectation`、`independence_check`）。

**边界**：
- **生成 σ-代数有组合爆炸上界** —— `measure_theory/set_systems.cpp`:118 抛"生成元过多（上限 200）"，并写明代价：生成开区间是 `O(N²)`、再生成 σ-代数是 `O(N³)`；`:67` 说明另一种情形"不如明确拒绝"（否则会把中间产物当成"生成的 σ-代数"）。
- **样本空间上限** —— `measure_theory_api.cpp`:146 抛"样本空间过大（上限 2000）：后续要枚举子集/σ-代数"。
- **不绝对可积就拒绝求值** —— `measure_theory/product_measure.cpp`:16 "被积函数在积分区域上无界/不绝对可积时,积分层会**如实拒绝求值**(抛 domain_error)"。
- **参数上界只有 1 处** —— `measure_theory_api.cpp`:261 `n ≤ 100,000`（**必填**，阶梯数）。这是本模块**唯一**一处 `get_int_bounded` 收口，所以"本模块参数无上界"这句话**既不成立也不可反推**，需逐 action 核（§7 第 1 条）。

### 4.9 `linear_algebra`（线性代数）

**源**：`linear_algebra/linear_algebra_api.cpp`（416 行）；编译 7 `.cpp` / 7 `.h`（`CMakeLists.txt`:88-94：
`vector_spaces.cpp`、`linear_transforms.cpp`、`inner_product.cpp`、`quadratic_forms.cpp`、`linear_systems.cpp`、`eigen.cpp` + API 层）；**action 数 32**，出处 = `file` == `linear_algebra/linear_algebra_api.cpp`。**CTest**：`linear_algebra`（`tests/test_linear_algebra.cpp`）。

**能力**：向量空间（`is_vector_space`、`subspace_span`、`basis`、`dimension`、`is_linear_independent`、`linear_combination`、`kernel`、`image`、`nullspace`、`rank`、`rank_nullity`）；线性变换与矩阵（`linear_transform`、`matrix_representation`、`matrix_inverse`）；线性方程组（`lin_solve_linear_system`、`gaussian_elimination`）；内积空间（`dot`、`norm`、`angle`、`lin_gram_schmidt`、`lin_is_orthogonal`、`orthogonal_projection`）；特征理论（`eigenvalues`、`eigenvectors`、`characteristic_polynomial`、`diagonalize`、`is_diagonalizable`）；二次型（`quadratic_form`、`standard_form`、`is_positive_definite`、`is_negative_definite`、`is_indefinite`）。

**边界**：
- **符号路线与数值路线分开限流（本模块最重要的边界）** —— `linear_algebra/linear_algebra_api.cpp`:63-70 说明：特征多项式 / 特征值 / 对角化走 **SymEngine 符号**路线，代价随阶数迅速增长，"20×20 整数矩阵实测 >10 s 不返回"；因此 `:75-78` 用 `get_matrix_symbolic` 卡在上限 **12×12**，错误文案点名"本动作是符号计算（行列式/化简），上限 12×12；阶数更高请改用数值特征值"。**数值类动作（矩阵乘法、高斯消元、数值行列式）不走这里，不受 12×12 限制。**
- **本模块没有一处 `get_int_bounded`** —— 规模限制全部通过"矩阵维度"这一条路径实现（`get_matrix_symbolic`），而不是通过整数参数收口（§4.8 的同款提示同样适用）。
- **`matrix_multiply` 不在本模块** —— 它在 `extras/extras_api.cpp`（§5.1）。

### 4.10 `algebraic_topology`（代数拓扑）

**源**：`algebraic_topology/at_api.cpp`（316 行）；编译 6 `.cpp` / 6 `.h`（`CMakeLists.txt`:42-47：
`homology.cpp`、`cohomology.cpp`、`homotopy.cpp`、`degree_fixedpoint.cpp`、`persistent_homology.cpp` + API 层）；**action 数 17**（12 个模块里最少），出处 = `file` == `algebraic_topology/at_api.cpp`。**CTest**：`algebraic_topology`（`tests/test_algebraic_topology.cpp`）。

**能力**：单纯复形与链复形（`simplicial_complex`、`boundary_operator`、`filtration`）；同调与上同调（`homology_group`、`betti_numbers`、`euler_characteristic`、`cohomology_group`、`cup_product`、`poincare_duality`）；同伦（`fundamental_group`、`path_homotopy`、`is_simply_connected`）；映射度与不动点（`mapping_degree`、`brouwer_fixed_point_theorem`、`hairy_ball_theorem`）；持续同调（`persistence_diagram`、`barcode_plot`）。

**边界**：
- **维数收口是本模块的主要闸门** —— `at_api.cpp`:152/241 `max_dim ≤ 20`（默认 -1 / 2）、`:138`/`:145` `n ≤ 100`（**必填**，维数 n）、`:198` `sphere_dim ≤ 1000`、`:215` `sphere_dim ≤ 100`、`:223` `dimension ≤ 1000`。
- **复形参数用 JSON 对象表达（本模块特有的形状约定）** —— `at_api.cpp`:6-8 给出两种写法：`{"complex": {"2": [[0,1,2],[0,1,3]], "1": [[0,1],...], "0": [[0],[1],...]}}` 或 `{"space": "T2", "n": 1}`。
- **同模块内结论不能自相矛盾** —— `tests/test_algebraic_topology.cpp`:171 记录了这条纪律的由来："同一导航分组内对同一输入给出互相矛盾的结论，比不支持还糟"。
- **`.h` 里最大的是 `at_internal.h`（333 行）** —— 本模块 `.h` 合计 556 行，一半以上在这里。

### 4.11 `number_theory`（数论）

**源**：`number_theory/number_theory_api.cpp`（299 行）；编译 7 `.cpp` / 7 `.h`（`CMakeLists.txt`:35-41：
`arithmetic_functions.cpp`、`core_algorithms.cpp`、`modular_arithmetic.cpp`、`prime_sieves.cpp`、`continued_fractions.cpp`、`zeta_interface.cpp` + API 层）；**action 数 24**，出处 = `file` == `number_theory/number_theory_api.cpp`。**CTest**：`number_theory`（`tests/test_number_theory.cpp`）。

**能力**：初等数论（`gcd`、`extended_gcd`、`is_prime`、`prime_factors`、`divisor_count`、`divisor_sum`、`euler_phi`、`mobius`、`mobius_prefix`）；同余（`mod_pow`、`mod_inverse`、`crt`、`discrete_log`、`primitive_root`）；筛法（`eratosthenes`、`segmented_sieve`）；连分数（`continued_fraction`、`convergents`、`best_rational_approximation`）；ζ 与 L 函数接口（`bernoulli_number`、`euler_product`、`zeta_dirichlet_series`、`zeta_negative`、`dirichlet_l_function`）。

**边界**：
- **整数上界最全（17 处），动机是"别把界面卡住"** —— `number_theory_api.cpp`:60 注释写明动机、`:66-69` 是统一错误文案；实际落点：`:136`/`:139`/`:142`/`:145`/`:225` `n ≤ 10^15`、`:181` `p ≤ 10^9`、`:186` `p ≤ 10^12`、`:191` `n ≤ 10^8`（筛法）、`:194` `n ≤ 10^9`、`:197` `segment_size ∈ [1, 10^7]`（默认 100,000）、`:239` `n_terms ≤ 10^5`（默认 20）、`:256` `max_denom ≤ 10^9`（默认 10^6）、`:267` `prime_limit ≤ 10^7`（默认 100）、`:271`/`:275` `n_terms ≤ 10^6`、`:286`/`:289` `n ≤ 500`（伯努利数阶 / ζ 阶）。
- **连分数有迭代安全上限** —— `continued_fractions.cpp`:124 `for (int iter = 0; iter < 100; ++iter)`（注释 `// 安全上限`）。
- **与复分析的 ζ 共用 500 这个界** —— `number_theory_api.cpp`:286/289 与 `complex_analysis/zeta.cpp`:26-30 双侧一致（§4.7 已引）。
- **`zeta_interface.cpp`:15** `素数上限必须 ≥2`（输入校验，不是性能收口）。
- **注意 `algebra/number_theory.cpp` 是另一个东西** —— 文件与头都叫 `number_theory`，但它在 `algebra` 命名空间下、负责运算律与比例（§4.2）。**两者不是同一模块。**

### 4.12 `functional_analysis`（泛函分析）

**源**：`functional_analysis/fa_api.cpp`（298 行）；编译 7 `.cpp` / 7 `.h`（`CMakeLists.txt`:67-73：
`normed_spaces.cpp`、`dual_spaces.cpp`、`linear_operators.cpp`、`spectral_theory.cpp`、`core_theorems.cpp`、`inner_product_spaces.cpp` + API 层）；**action 数 21**，出处 = `file` == `functional_analysis/fa_api.cpp`。**CTest**：`functional_analysis`（`tests/test_functional_analysis.cpp`）。

**能力**：赋范空间（`lp_norm`、`is_banach`、`space_completeness_check`）；内积空间（`inner_product`、`is_hilbert`、`funct_gram_schmidt`、`funct_is_orthogonal`）；有界算子（`is_bounded`、`operator_norm`、`kernel_dimension`、`linear_functional_eval`）；对偶与三大定理（`dual_space_basis`、`hahn_banach_extension`、`is_reflexive`、`open_mapping`、`uniform_boundedness`、`closed_graph`）；谱（`spectrum_approx`、`spectrum_classify`、`spectral_theorem`）；收敛（`weak_convergence`）。

**边界**：
- **空矩阵必须当场拒绝（防进程级崩溃）** —— `functional_analysis/fa_api.cpp`:43 注释记录了实测原因："0×0 传进 Eigen 会直接访问违规（实测 exit=0xC0000005）"。这是 `0xC0000005` 访问违规，所以这条拒绝不是风格问题。
- **范数阶数白名单** —— `functional_analysis/linear_operators.cpp`:26 `throw std::invalid_argument("不支持的范数阶数: " + p)`。
- **算子性质类 action 有 6 个落在 `extras`** —— `is_compact_operator`、`is_self_adjoint`、`adjoint_operator`、`riesz_representation`、`spectral_radius`、`fredholm_alternative` 全在 `extras/extras_api.cpp`。查这几个概念时要走 extras，不要在本模块里找（§5.1）。
- **参数上界只有 1 处** —— `fa_api.cpp`:266 `n_points ≤ 1,000,000`（默认 1000）。这是本模块唯一一处 `get_int_bounded` 收口。

---

## 5. 归不到 12 个模块的 47 条

### 5.1 `extras/` 的 25 条

`extras` 有独立目录与独立注册文件，但**不是 12 个学科模块之一**。`extras/extras_api.cpp`:1-4 自述其存在理由：
这批函数是"被『视图里未接入引擎的模式』逼出来的补齐件"，集中在一处便于看出"为了哪些模式补了什么"，
且不去改动已经很大的各模块 API 文件。它按**主题**打散了本应属于其它模块的 action，这是最容易查错的一处：

| 主题上像属于 | 实际在 `extras` 的 action | 条数 |
| --- | --- | --- |
| `calculus`（曲线分析） | `calc_asymptotes`、`calc_cauchy_mvt`、`calc_concavity`、`calc_curvature`、`calc_inflection` | 5 |
| `calculus` / `number_theory`（级数与无穷乘积） | `absolute_convergence`、`product_sequence`、`infinite_product`、`dirichlet_eta` | 4 |
| `numerical`（微分方程） | `ode_first_order`、`ode_constant_coefficients`、`ode_linear_system`、`first_order_linear_pde`、`classify_second_order_pde` | 5 |
| `linear_algebra` | `matrix_multiply` | 1 |
| `functional_analysis` | `adjoint_operator`、`is_compact_operator`、`is_self_adjoint`、`riesz_representation`、`spectral_radius`、`fredholm_alternative` | 6 |
| `complex_analysis` | `complex_argument`、`complex_conjugate`、`complex_modulus`、`zeros_and_poles` | 4 |

`extras/analysis.cpp`（1,825 行）是该目录最大的实现文件；`extras/analysis.h`:13-16 写明设计原则：
能给确定结论的给结论；只能数值求解的**明确标注数值结果与扫描区间**；方法不适用时返回**为什么不适用**。

⚠ 上表的"主题上像属于"是**本文按 action 名做的人工归类，不是引擎里的一种映射**。引擎侧只有"注册在哪个文件"
这一个事实，没有第二份"A 属于 B 模块"的登记。故上表可用于查错、**不可引用为契约**；要验证就用 §1 命令 A 看 `file` 字段。

### 5.2 引擎根目录 5 个 `*_api.cpp` 的 22 条

| 文件 | action 数 | 内容 | CTest 覆盖 |
| --- | --- | --- | --- |
| `expr_api.cpp` | 9 | `prepare_expr`、`expr_eval`、`expr_eval2`、`expr_eval_vars`、`expr_eval_batch`、`expr_eval_vars_batch`、`expr_eval_grid`、`to_engine_expr`、`sym_latex` | 无专属用例 |
| `symbolic_api.cpp` | 7 | `simplify_sym`、`factor_sym`、`solve_sym`、`compare_expr`、`discriminant_sym`、`extrema_sym`、`free_symbols_of` | `symbolic_contract`（`tests/test_symbolic_contract.cpp`） |
| `plot_api.cpp` | 4 | `complex_grid`、`complex_eval`、`complex_eval_many`、`intersections` | `complex_grid`（`tests/test_complex_grid.cpp`） |
| `introspect_api.cpp` | 1 | `list_functions` | 间接：`README.md` §5 的 `count == 424` 断言 |
| `fractal_api.cpp` | 1 | `mandelbrot` | 无专属用例 |

这 5 个文件不按学科切分：`expr_api.cpp` / `symbolic_api.cpp` 是**符号层**（见 [`SYMBOLIC.md`](SYMBOLIC.md)），
`plot_api.cpp` / `fractal_api.cpp` 是**采样与视口层**（见 [`PLOT.md`](PLOT.md)），`introspect_api.cpp` 是**自省面**。
**"12 个学科模块"这个划分对它们不适用** —— 硬塞进去会产生一个错的模块表。

两条跨模块面的硬上界（影响所有模块的返回值形状）：

- `plot_api.cpp`:256 抛"超过上限 400000，请降低分辨率（建议 ≤ 600×600）"；`:238-239` 给出代价估算（400k 点 × 2 个数 ≈ 9.6 MB，超过桥的缓冲）。`tests/test_complex_grid.cpp`:628-652 双向钉住它（701×701 = 491,401 报错；400×1001 = 400,400 也报错）。
- `expr_api.cpp`:144-148 把 `expr_eval_grid` 的上限**对齐到同一个 400,000**；`fractal_api.cpp`:32-37 是另一套（上限 4,000,000，因为分形结果不逐点回传）。

---

## 6. 已知的文档债

### 6.1 `numerical` 目录里 5 个 v1 Python 胶水层仍在盘中（且不计入编译）

| 文件 | 行数 | 注释自称 | 事实 |
| --- | --- | --- | --- |
| `numerical/numerical_core.cpp` | 84 | `// numerical_binding.cpp — Python 胶水层`（:1） | 文件名是 `numerical_core.cpp`，注释里是另一个名字 |
| `numerical/interpolation_core.cpp` | 40 | `// interpolation_core.cpp — Python 胶水层`（:1） | 名称一致 |
| `numerical/matrix_core.cpp` | 81 | `// matrix_core.cpp — Python 胶水层`（:1） | 名称一致 |
| `numerical/ode_core.cpp` | 53 | 首行直接是 `#include <pybind11/pybind11.h>` | 无模块注释 |
| `numerical/optimization_core.cpp` | 81 | `// optimization_core.cpp — Python 胶水层`（:1） | 名称一致 |

行数口径同 §3（`split('\n').length`）；五者合计 **339 行**，与 §3 ⚠ 的差额对上。

**为什么是债**：这 5 个 `.cpp` **不在 `CMakeLists.txt`:60-66 的编译列表里**（§1 命令 C 已复跑），
但它们的同名 `.h` 里放着**真正在用的内联实现** —— `numerical_core.h` 被 `numerical_integration.cpp`:9 引用
且通篇是 `inline` 函数（`:16` `trapezoidal`、`:26` `simpson`、`:38` `gauss_quad`、`:63` `derivative`…）；
`interpolation_core.h` 被 `interpolation.cpp`:10 引用；而 `matrix_core.h`（313 行）、`ode_core.h`（49 行）、
`optimization_core.h`（71 行）**除各自的胶水层 `.cpp` 外没有任何文件引用** —— 这三个头是死代码，
合计 **433 行**，却计入 §3 的 `.h` 行数。

**处置建议**：删掉这 5 个 `.cpp` 与 3 个死头（它们不属于任何构建目标）。**在删之前**，
任何统计 `numerical` 规模的说法都必须注明口径 —— 这正是 §3 ⚠ 与 §4.5 存在的原因。

### 6.2 `algebra_api.cpp` 与 `at_api.cpp` 的头部注释少报 action 数

| 位置 | 注释说 | 代码做 |
| --- | --- | --- |
| `algebra/algebra_api.cpp`:1 | `algebra 包(combinatorics + number_theory)JSON 分发层` | 该文件 `#include` 了 8 个子模块头（`:9-16`），实际注册 **79** 个 action |
| `algebra/algebra_api.cpp`:3 | `注册 17 个 action。analytic_geometry 的函数稍后追加到本文件。` | 实际 **79** 个；"稍后追加"已经发生，但这句话没更新 |
| `algebraic_topology/at_api.cpp`:1 | `algebraic_topology 包(homology/cohomology)JSON 分发层` | 该文件 `#include` 了 `homotopy.h`、`degree_fixedpoint.h`、`persistent_homology.h`（`:16-18`），注释漏了这三块 |
| `algebraic_topology/at_api.cpp`:3 | `注册 6 个 action:simplicial_complex / homology_group / … / poincare_duality` | 实际 **17** 个 |

**为什么是债**：`numerical_api.cpp`:3 是**正确**的写法（"注册 19 个 action … 6 个稍后追加"，19 + 6 = 25 = 实测值），
上面两处的注释会让读者少算 62 个 action（79 − 17）与 11 个 action（17 − 6）。按 `AGENTS.md` §5 **以代码为准**：
action 数一律用 §1 命令 A/B 现算。

### 6.3 `engine-signatures.json` 的两个已知局限（引用本文数字时必须带上）

这两条**不是本文发现的**，是仓库里已登记的，此处引用以免读者把本文当成引擎契约的权威源：

1. **该表的参数提取是单向下界，不是完整契约。** `MF_UI/BUGS.md`:970-974 写着"`engine-signatures.json` **不能当『引擎契约的权威』用**：该表**系统性遗漏通过 helper / lambda 读取的参数**"，并给了两个实例：`product_measure` 表里 `params={A,B}`，而 `measure_theory_api.cpp`:505-514 用 lambda 直接读 `mu`/`nu`；`integral_mean_value` 表里 `params={expr}`，而实际读 `interval`。同处还指出 `required` 是**多分支并集**而非真必填。生成器自己在同一脚本的「对账」注释块里也写明判据是单向的（2026-10-07 10:50 核对时在 `engine-signatures.mjs`:145-156）。**因此本文只用它数 action 个数与归属，不用它断言"某 action 的参数就是这些"，也不据它判"UI 少传了必填参数"。**
2. **`interval` 这个键在 12 个 handler 里被读，而表里可能对不上。** `MF_UI/BUGS.md`:335 把它登记为待改进项（应在生成逻辑里提取 helper 读取的键）。相关参数形状问题归 [`CONTRACT.md`](CONTRACT.md)。

### 6.4 本文自身的时限

§3/§4 的数字绑定在 **2026-10-06 05:43 构建的产物**上（§1 命令 A–C 走**源码**，命令 D 的 `probe_call` 走**运行时 DLL**）。
引擎源码一改，`diskCpp`/`cppLines` 列立刻过期；`action` 列则会先被 `engine-signatures.mjs --check` 拦下
（它是 `npm run check` 的一道闸门）。**读到这里时请先跑一遍 §1 命令 D。**

---

## 7. 未证实项（写明怎么才能验证）

| # | 未证实的事 | 为什么没证 | 怎么验证 |
| --- | --- | --- | --- |
| 1 | 各模块是否**所有**参数都没有"运行时长"上界 | 本文只扫了 `get_int_bounded` / `get_int_opt_bounded` 两种助手（§4 各节「参数上界」段）。引擎里还有域内自定义收口（如 `linear_algebra_api.cpp`:71 `get_matrix_symbolic`、`calculus/limits.cpp`:87-91 的预算常量），本文无法保证扫全 | 以 `MF_Mathematics` 为根 grep `throw` 与 `上限`，逐个 action 对应到 handler；或对每个 action 用 `probe_call.exe <名字> <超界参数>` 实测返回 |
| 2 | §5.1 那张"主题上像属于"的对照表是否与维护者意图一致 | 引擎侧**没有**第二份模块归属登记，本文的分类是按 action 名做的人工归类 | 问维护者；或看 `MF_UI/MFMath.UI.Vue/src/lib/router/nav.js` 的导航分组是否与本文一致（导航分组是另一套划分，**未证实**它与 §5.1 相同） |
| 3 | `demo/eigen_test.cpp`、`demo/main.cpp` 是否还有用 | 二者不在 `CMakeLists.txt`，本文只报告"不编译"这一事实 | `git log -- MF_Mathematics/demo/`；或全树 grep 是否有人引用 `demo` |
| 4 | 16 条 CTest 用例是否覆盖 §4 每个模块的**全部** action | 用例是模块级的（每模块 1 条，`calculus`/`complex_analysis` 各 2 条），是否逐 action 断言**未统计** | 见 [`TESTS.md`](TESTS.md)；或统计 `tests/*.cpp` 里 `CHECK` 覆盖到的 action 名集合，与 §1 命令 A 的输出取差集 |
