# 符号计算（SYMBOLIC）

> 本文说明符号计算层的组成与能力：依赖库、DLL 边界约束、化简 / 求导 / 积分 / 极限的实现与局限、排版输出。
> 与同层文档的分工：[`README.md`](README.md) 讲构建与测试入口；[`CONTRACT.md`](CONTRACT.md) 讲 args JSON 形状与键名契约；[`MODULES.md`](MODULES.md) 讲学科模块与 action 全表；[`NUMERIC.md`](NUMERIC.md) 讲数值容差与精度策略；[`BOUNDARIES.md`](BOUNDARIES.md) 讲能力边界。

## 1. 依赖库

| 库 | 版本依据 | 引入方式 | 定位命令 |
| --- | --- | --- | --- |
| SymEngine | DLL 名固定 `symengine-0.14.dll` | vcpkg，`MF_SYMENGINE_ROOT` 默认 `C:/Users/fsafsafsa/vcpkg/installed/x64-windows`，可用 `-DMF_SYMENGINE_ROOT=...` 覆盖 | `Select-String -Path MF_Mathematics/CMakeLists.txt -Pattern 'symengine-0.14.dll'` |
| flint / gmp / mpfr | DLL 名固定 `flint-24.dll`、`gmp-10.dll`、`mpfr-6.dll` | SymEngine 的运行时依赖，构建时随 `pthreadVC3.dll` 一并拷到输出目录 | `Select-String -Path MF_Mathematics/CMakeLists.txt -Pattern 'flint-24.dll'` |
| Eigen | 纯头文件 | 线性代数用，不属于符号层 | `Select-String -Path MF_Mathematics/CMakeLists.txt -Pattern 'MF_EIGEN_INCLUDE_DIR'` |

符号实现位于静态库 `mf_mathematics_core`；DLL 目标 `mf_mathematics` 只含 `api.cpp`。运行时 DLL 拷贝列表见 `CMakeLists.txt` 的 `POST_BUILD` 段。

## 2. DLL 边界约束

DLL 导出面是两个 `extern "C"` 函数：`function_exists`、`math_call`（`MF_Mathematics/api.h`）。

| 事实 | 定位命令 |
| --- | --- |
| 导出函数恰好两个 | `Select-String -Path MF_Mathematics/api.h -Pattern 'MF_API'` |
| 边界类型只有 `const char*` / `char*` / `int` / `bool` | `Get-Content MF_Mathematics/api.h` |
| 失败或缓冲不足统一返回 `-1` | `Get-Content MF_Mathematics/api.h` |

符号结果的直接后果是：所有结果必须以 JSON 可承载的形状（数字、字符串、数组、对象）离开引擎。配套机制是两类字符串数组转换与往返校验：

| 机制 | 作用 | 定位命令 |
| --- | --- | --- |
| `to_string_array` / `to_pretty_array` | `std::vector<std::string>` 与 JSON 数组互转 | `Select-String -Path MF_Mathematics/symbolic_api.cpp -Pattern 'to_pretty_array'` |
| 排版往返校验 | 排版串必须能 `parse` 回等价表达式才采用，否则保留原串 | `Select-String -Path MF_Mathematics/symbolic_api.cpp -Pattern 'to_pretty_array\|display'` |

往返校验存在的原因是 `solve_sym` 的解、`compare_expr` 的两侧等字段会被调用方回喂给引擎，排版一旦引入不可解析的写法，调用方会静默拿不到结果。

## 3. 文件组成与 action

| 文件 | 角色 | 关键符号 |
| --- | --- | --- |
| `MF_Mathematics/symbolic_util.h` | 符号判定工具（纯头文件） | `safe_solve`、`node_count`、`sign_definite`、`domain_constraints`、`numeric_roots_in_range`、`prove_equivalent`、`equation_realness`、`param_branches` |
| `MF_Mathematics/symbolic_api.cpp` | 符号 action 的注册与编排 | `register_all()` |
| `MF_Mathematics/symbolic_pretty.h` | 教科书记号文本排版 | `pretty_math`、`pretty_math_str`、`has_nonfinite` |
| `MF_Mathematics/math_latex.h` | LaTeX 输出（两个入口） | `expr_to_latex`、`symengine_to_latex` |
| `MF_Mathematics/calculus/integrals.cpp` | 自研符号积分 + 数值辛普森 + 反常积分 | `antiderivative`、`integrate_indefinite`、`improper_integral` |
| `MF_Mathematics/calculus/derivatives.cpp` | 求导 / 某点导数 / 隐函数 / 参数方程 | `diff`、`diff_at_str` |
| `MF_Mathematics/calculus/limits.cpp` | 极限：形式判定 + 分层策略 | `limit` |
| `MF_Mathematics/calculus/calculus_api.cpp` | 微积分模块 JSON 分发层 | `register_all()` |

`symbolic_api.cpp` 注册 7 个 action，`calculus_api.cpp` 注册 35 个 action。计数命令：

```powershell
(Select-String -Path MF_Mathematics/symbolic_api.cpp -Pattern 'register_function\("' | Measure-Object).Count   # 7
(Select-String -Path MF_Mathematics/calculus/calculus_api.cpp -Pattern 'register_function\("' | Measure-Object).Count   # 35
```

`symbolic_api.cpp` 的 7 个 action：

| action | 作用 |
| --- | --- |
| `free_symbols_of` | 表达式的自由符号列表 |
| `solve_sym` | 精确解集合（含自由符号）+ 实根性，走 Decompose 策略 |
| `discriminant_sym` | 符号判别式 Δ = b²−4ac + 可证明的符号 |
| `factor_sym` | 符号因式分解 |
| `compare_expr` | 表达式等价判定，三态 `equal` / `not-equal` / `undetermined` |
| `extrema_sym` | 含参极值 + 参数分类讨论 |
| `simplify_sym` | 多候选取最简的精确化简 |

`calculus_api.cpp` 的 35 个 action 覆盖求导、积分、极限、级数、微积分应用题与级数判别法。

## 4. 化简

`simplify_sym` 不依赖单次 `SymEngine::simplify`，而是生成一批候选形式，按 `node_count`（节点数，叶子算 1）挑选最简；并列时按字符串长度取更短者，保证结果稳定。

| 候选 form | 产生方式 | 针对的情形 |
| --- | --- | --- |
| 原始形式 | 原表达式 | 有些形式化简反而变差 |
| `expand` | `SymEngine::expand` | `(x-a)^2-(x+a)^2` 的 simplify 原样返回，只有 expand 给出 `-4*a*x` |
| `simplify` / `simplify(expand)` / `expand(simplify)` | 三种组合 | SymEngine 的化简非单调 |
| `expand(商的展开)` | `as_numer_denom` 后展开商 | 分子分母同乘同一因式时前几种化不掉 |
| 三角恒等 `sin²→1-cos²` 与反向 | 显式替换 | `SymEngine::simplify` 不做三角恒等 |

`node_count` 定位：`Select-String -Path MF_Mathematics/symbolic_util.h -Pattern 'node_count'`。返回体含 `candidates` 数组，每个候选连同 `ops`（节点数）回传，选简依据可核对。

复跑：`MF_Mathematics\build\bin\Release\probe_call.exe simplify_sym '{"expr":"(x-a)^2-(x+a)^2"}'` 的 `chosen` 为 `expand`、`simplified` 为 `-4*a*x`。

## 5. 求导

| 能力 | 实现 | 关键行为 |
| --- | --- | --- |
| 表达式求导 | `SymEngine::diff`，高阶重复 `order` 次 | `order < 1` 抛异常；`order` 上限 1000（`get_int_opt_bounded`） |
| 某点导数 | 先代入再求值 | 整点用精确整数代入（`point_at`），否则用实数 |
| 含参数某点导数 | `diff_at_str` | 代入后仍含自由符号时返回符号文本（如 `4*a`），不硬转 `double` |

`diff_at` 的 JSON 分发在 `calculus_api.cpp`，判据是结果文本能否整串解析为数字（`stod` 的 `used == s.size()`），因此 `4*a` 不会被误当数值 `4`。

隐函数与参数方程求导：`implicit_diff` 用 dy/dx = −F_x/F_y，`F_y = 0` 返回“无法求解”；`parametric_diff` 用 (dy/dt)/(dx/dt)，`dx/dt = 0` 返回“无穷大（切线垂直）”。定位：`Select-String -Path MF_Mathematics/calculus/derivatives.cpp -Pattern 'implicit_diff|parametric_diff'`。

`diff` 的返回值来自 `SymEngine::str`，不经过 `pretty_math`，因此记号风格与 `simplify_sym` 不同（`**`、`(1/2)` 这类机器写法原样保留）。

## 6. 积分

积分内核是自研符号积分器，不调用 SymEngine 的积分器。`antiderivative` 无法积分时返回空 `RCP`，`integrate_indefinite` 把它翻译为字面量 `"未实现"`，不编造结果。

### 6.1 调用链

```
integrate（calculus_api.cpp）
  ├─ 给 a 与 b → integrate_definite：符号 F(b)−F(a)；失败回退辛普森 n=1000
  └─ 未给 a/b → integrate_indefinite：antiderivative；返回 null 时返回 "未实现"
```

| 事实 | 定位命令 |
| --- | --- |
| `antiderivative` 无法积分返回空 `RCP`，不抛异常 | `Select-String -Path MF_Mathematics/calculus/integrals.cpp -Pattern 'RCP<const Basic> antiderivative'` |
| 不定积分把 null 翻译成 `"未实现"` | `Select-String -Path MF_Mathematics/calculus/integrals.cpp -Pattern '未实现'` |
| 反常积分无穷端按数量级分段求和并判收敛，发散抛异常 | `Select-String -Path MF_Mathematics/calculus/integrals.cpp -Pattern 'improper_pos'` |
| 二 / 三重积分的数值回退是嵌套辛普森（内层边界可依赖外层变量） | `Select-String -Path MF_Mathematics/calculus/integrals.cpp -Pattern 'integrate_double\|integrate_triple'` |

边界解析 `parse_bound` 认 `"pi"` / `"π"` / `"oo"` / `"inf"` / `"∞"` / `"-oo"`。

### 6.2 派发顺序与求导自证

`antiderivative` 的派发顺序：常数 → `c·x` → 裸 `x` → `x²/2` → Add 线性性 → Mul（提常数 / 特例闭式 / 分部积分）→ Pow（幂型、三角幂、根式、有理式）→ 积分表（sin / cos / tan / sec / log / 反三角）。

配了「求导自证」的规则是 18 条。求导自证 = 对原函数求导，再与原被积函数在给定点上逐点数值比对，判据是相对 / 绝对混合容差 `1e-9`（分母取 `max(1, |f(x)|)`）。

| 被积函数 | 期望原函数 |
| --- | --- |
| `1/(1+x**2)` | `atan x` |
| `tan(x)` | `−ln cos x` |
| `x/(1+x**2)` | `½ln(1+x²)` |
| `1/(x*ln(x))` | `ln ln x` |
| `tan(x)**2` | `tan x − x` |
| `sec(x)` | `ln(sec x + tan x)` |
| `x*ln(x)` | `½x²ln x − ¼x²` |
| `exp(x)*sin(x)` | `eˣ(sin x − cos x)/2` |
| `exp(x)*cos(x)` | `eˣ(sin x + cos x)/2` |
| `atan(x)` | `x·atan x − ½ln(1+x²)` |
| `acos(x)` | `x·acos x − √(1−x²)` |
| `sin(x)**3` | `cos³x/3 − cos x` |
| `cos(x)**3` | `sin x − sin³x/3` |
| `sqrt(1-x**2)` | `(x√(1−x²) + asin x)/2` |
| `sqrt(1+x**2)` | `(x√(1+x²) + asinh x)/2` |
| `sec(x)**3` | `½(sec x·tan x + ln(sec x+tan x))` |
| `1/(1+x**4)` | 四次式闭式（`antideriv_one_plus_x4`） |
| `sqrt(x)*ln(x)` | `(2/3)x^{3/2}ln x − (4/9)x^{3/2}` |

「18」的核对命令：

```powershell
(Select-String -Path MF_Mathematics/tests/test_calculus.cpp -Pattern 'antideriv_self_checks_out\(' | Measure-Object).Count   # 19，其中 1 处是函数定义，18 处是调用
```

非初等积分（如 `x^x`）走「如实拒绝」路径，返回 `"未实现"`，与 `test_calculus.cpp` 中 `x**x` 的断言一致。

### 6.3 未验证的部分

| 事项 | 现状 | 验证方法 |
| --- | --- | --- |
| 符号积分规则总数 | 确证的是「配了求导自证的调用点 = 18」；`integrals.cpp` 中还有未配独立自证的分支（如 `asin` 闭式、一般 `1/(c+u²)`、`1/(u·ln u)`） | 逐分支列出 `return RCP<const Basic>()` 之前的成功路径，并给每条补一个 `antideriv_self_checks_out` 调用点 |

## 7. 极限

极限先做结构化形式判定，再走分层策略（`limits.cpp`）。

| 层 | 做法 |
| --- | --- |
| L1 形式判定 | 结构化判定该点的形式，不用 ε；拿不准一律判 `Indet` |
| L2 确定形式 | Finite / Zero / ∞（符号确定）→ 直接代入 |
| L3 ∞ 兜底 | `x = 1/t`（t→0±）；代数式的商 / 差先在 ∞ 上用系数比 / 阶比较 |
| L4 不定式 | `0/0`、`∞/∞` → 洛必达（每轮重新分类）；`1^∞`/`0^0`/`∞^0` → `exp(g·log f)`；`0·∞` → 两种恒等改写；`∞−∞` → 通分 / 共轭有理化 / 阶比较 |
| L5 诚实 | 解不出就抛异常并说明形式与原因 |

硬上限（`limits.cpp` 的常量，定位 `Select-String -Path MF_Mathematics/calculus/limits.cpp -Pattern 'kLimMaxDepth|kLimMaxLhopital|kLimMaxNormalize|kLimMaxSteps|kLimBudgetMs'`）：递归深度 12、洛必达轮数 10、归一化 12、策略步数 3000、墙钟预算 1500 ms。

`±∞` 结果转成字符串 `"oo"` / `"-oo"`（`calculus_api.cpp` 的 `limit` 分发），因为 JSON 无 `inf` 字面量。输入允许课本方程写法（`x^2+2x+1=0` 与 `x^2+2x+1` 等价，都按 =0 求解），由 `get_equation` 与 `equation_to_zero` 整理。

## 8. 排版输出

符号结果有两条独立出口：教科书记号文本（`pretty_math`）与 LaTeX（`math_latex.h`），输入类型不同。

| 出口 | 入口 | 输入 | 产出 |
| --- | --- | --- | --- |
| 教科书记号文本 | `pretty_math` / `pretty_math_str` | `RCP<const Basic>` / 字符串 | 无负指数的文本：`a**(-1)`→`1/a`、`x**(1/2)`→`sqrt(x)`、`zoo`→`无定义（复无穷）` |
| LaTeX（绘图侧） | `expr_to_latex` | `mf::expr::ExprNode*` 表达式树 | `\frac{}{}`、`\sqrt{}`、`\left(\right)` |
| LaTeX（符号侧） | `symengine_to_latex` | `RCP<const Basic>` | 走 SymEngine 的 `LatexPrinter` |

两个 LaTeX 入口并存的原因是绘图路径用 `mf::expr` 的表达式树，SymEngine 的 `LatexPrinter` 只认识 `Basic`。`math_latex.h` 声明输出是展示用 LaTeX，目标是 KaTeX 渲染，不保证能被 LaTeX 引擎原样编译。

`pretty_math` 的性质：

1. 只做书写重排，不做化简；`**` 仍保留（`a**2` 是正常输出），去掉的是负指数。
2. 括号正确性与数值正确性相关：和式出现在乘法 / 除法 / 幂的因子位置时必须补括号，否则重解析出的是另一个表达式；分母是乘积时按因子个数整体加括号。
3. 虚数单位保持 `I`，不排成 `i`（SymEngine 解析器只认 `I`，写成 `i` 会被当自由变量）。

往返校验（`display`、`to_pretty_array`）把「排版 → 重解析 → 比对，不等价则退回原串」作为安全网。`simplify_sym` 的 `simplified` / `expanded` 字段直接调用 `pretty_math`，不经过该校验。

## 9. 复跑

以下命令在仓库根目录执行（`MF_Mathematics/build/` 已构建时）：

```powershell
& '.\MF_Mathematics\build\bin\Release\test_calculus.exe'          # 积分规则与求导自证
& '.\MF_Mathematics\build\bin\Release\test_symbolic_contract.exe' # 符号 API 契约
& '.\MF_Mathematics\build\bin\Release\probe_call.exe' list_functions '{}'   # value.count 应为 424

& '.\MF_Mathematics\build\bin\Release\probe_call.exe' simplify_sym '{"expr":"(x-a)^2-(x+a)^2"}'
& '.\MF_Mathematics\build\bin\Release\probe_call.exe' integrate '{"expr":"cos(x)**3"}'
& '.\MF_Mathematics\build\bin\Release\probe_call.exe' limit '{"expr":"sin(x)/x","point":0}'
```

`test_calculus` 与 `test_symbolic_contract` 两个 CTest 用例的名字是 `calculus` 与 `symbolic_contract`（见 [`TESTS.md`](TESTS.md)）。
