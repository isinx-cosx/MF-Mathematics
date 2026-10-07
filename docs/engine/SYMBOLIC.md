# 符号层（SYMBOLIC）

> **本文只回答一个问题：符号层怎么组织 —— 用什么库、边界在哪、化简/求导/积分/极限怎么走？**
>
> 与同层其它文档的分工：
> - [`README.md`](README.md) —— 引擎的两个构建目标、C ABI 恰好两个导出、`/WHOLEARCHIVE` 守门、构建与测试入口；
> - [`CONTRACT.md`](CONTRACT.md) —— args JSON 的形状、**键名契约**、必填参数拒绝计算、`未实现` 的返回形状；
> - [`MODULES.md`](MODULES.md) —— 12 个学科模块的 action 全表（本文只点符号相关的那些）；
> - [`NUMERIC.md`](NUMERIC.md) —— `special_numeric` / `complex_numeric` 的容差与精度策略（本文只讲符号层**在哪一步**调用它）；
> - [`BOUNDARIES.md`](BOUNDARIES.md) —— 如实的能力边界与 `NOT_EXPOSED` 口径。

**结论时效**：以下数字是 **2026-10-07 10:41** 在现役产物上实测的。产物 `mf_mathematics.dll`
时间戳 2026/10/6 5:43:00，源码 `MF_Mathematics/calculus/integrals.cpp` 时间戳 2026/10/5 10:25:27
—— 产物新于源码，所以这轮实测对应当前源码。换一批产物就要重跑 §9 的命令。

---

## 1. 用什么库

| 库 | 版本 | 怎么进来 | 出处 |
| --- | --- | --- | --- |
| **SymEngine** | **0.14.0**（`SYMENGINE_VERSION "0.14.0"`；DLL 名 `symengine-0.14.dll`） | vcpkg；`MF_SYMENGINE_ROOT` 默认 `C:/Users/fsafsafsa/vcpkg/installed/x64-windows`，可用 `-DMF_SYMENGINE_ROOT=...` 覆盖 | `symengine_config.h`（`MF_SYMENGINE_ROOT/include/symengine/`）；`CMakeLists.txt:17-20`、`:156` |
| FLINT / GMP / MPFR | `flint-24` / `gmp-10` / `mpfr-6` | SymEngine 的运行时依赖，构建时一并拷到输出目录 | `CMakeLists.txt:156` |
| Eigen | — | 线性代数用，**不属于符号层** | `CMakeLists.txt:14` |

符号层的实现**全部在静态库 `mf_mathematics_core` 里**（`CMakeLists.txt:28-33` 逐个列出
`expr_api.cpp` / `symbolic_api.cpp` 等），DLL 目标 `mf_mathematics` 里只有 `api.cpp`（`CMakeLists.txt:167`）。

---

## 2. 边界：DLL 只暴露两个 C ABI 函数

这是 [`../DECISIONS.md`](../DECISIONS.md) 的 **D-001**，出处 [`../../README.md`](../../README.md):80 的架构图。

| 事实 | 证据 |
| --- | --- |
| 导出面**恰好两个** `extern "C"` 函数：`function_exists`、`math_call` | `api.h:10`、`api.h:18`；`api.cpp:9`、`api.cpp:14` |
| 边界上只有 `const char*` / `char*` / `int` / `bool` | `api.h:10-19`（逐字读签名） |
| **不暴露** `std::string` / `std::vector` / `SymEngine::RCP` | [`../../README.md`](../../README.md):80、[`../DECISIONS.md`](../DECISIONS.md) D-001（“跨编译器的 C++ ABI 是没有标准的”） |
| 域内头文件已不再使用 `MF_API`，`mf_export.h` 只服务 `api.h` | `CMakeLists.txt:24-27`、`mf_export.h:8-12` |
| 实测行数：`api.cpp` **27** 行、`api.h` **23** 行 | `(Get-Content MF_Mathematics/api.cpp).Count` → 27；`api.h` → 23 |

**代价（D-001 原文）：** ① 每次调用都要序列化/反序列化 JSON；② 错误只能靠字符串约定传递，
没有类型系统拦截；③ 自省能力弱，所以要靠 `count == 424` 守门（[`../DECISIONS.md`](../DECISIONS.md) D-003）。

对符号层而言，这条边界的直接后果是：**所有符号结果必须以 JSON 可承载的形状出去**。
于是有了两件配套机制，它们不是可选的装饰：

| 机制 | 做什么 | 出处 |
| --- | --- | --- |
| `to_string_array` / `to_pretty_array` | `std::vector<std::string>` → JSON 数组；排版后再回喂 | `symbolic_api.cpp:94-121` |
| **排版往返校验** | 排版串必须能 `parse` 回**等价**表达式才采用，否则原样保留 | `symbolic_api.cpp:106-121`（数组）、`symbolic_api.cpp:370-377`（单值 `display()`） |

为什么要往返校验：这些字段会被调用方**回喂**给引擎（`solve_sym` 的解 → `complex_eval`；
`compare_expr` 的两侧）。排版一旦引入不可解析的写法，调用方就会静默拿不到结果
（`symbolic_api.cpp:100-105`）。§8 会给出一个**这条网没兜住**的实测反例。

> 特别注意：`display()` / `to_pretty_array()` 的兜底是“**退回 SymEngine 原生串**”，
> 不是“报错”。所以机器记号泄漏时，症状是**可读性变差或表达式非法**，而不是 `isError`。

---

## 3. 符号层的文件组成

| 文件 | 行数 | 角色 | 关键入口 |
| --- | --- | --- | --- |
| `MF_Mathematics/symbolic_util.h` | 1757 | 符号**判定**工具（纯头文件）：安全求解、节点数、可证明符号、定义域、数值求根回退、等价判定 | `safe_solve`(:371)、`node_count`(:509)、`sign_definite`(:807)、`domain_constraints`(:985)、`numeric_roots_in_range`(:1082)、`prove_equivalent`(:1420)、`equation_realness`(:1585) |
| `MF_Mathematics/symbolic_api.cpp` | 1370 | 符号 action 的注册与编排（**7 个** action，清单见下） | `register_all()`(:709) |
| `MF_Mathematics/symbolic_pretty.h` | 299 | 教科书记号排版 | `pretty_math`(:275)、`pretty_math_str`(:283)、`has_nonfinite`(:292) |
| `MF_Mathematics/math_latex.h` | 166 | LaTeX 输出（两个入口） | `expr_to_latex`(:94)、`symengine_to_latex`(:147) |
| `MF_Mathematics/expr_api.cpp` | 297 | 表达式求值与输入准备（**9 个** action，含 `sym_latex`） | `register_all()`(:103) |
| `MF_Mathematics/calculus/` —— `integrals.cpp`/`.h` **1390**/**66**、`derivatives.cpp`/`.h` **136**/**35**、`limits.cpp`/`.h` **1363**/**37**、`series.cpp`/`.h` **619**/**65**、`calculus_api.cpp` **354** | — | 积分（自研符号积分 + 辛普森 + 反常积分）、求导、极限、级数，以及它们的 JSON 分发层（**35 个** `register_function`） | `antiderivative`(integrals.cpp:459)、`integrate_indefinite`(:1047)、`diff`(derivatives.cpp:52)、`limit`(limits.cpp:1099)、`register_all()`(calculus_api.cpp:45) |

`symbolic_api.cpp` 注册的 **7** 个 action（数 `register_function(` 得 7 处）：
`free_symbols_of`(:713)、`solve_sym`(:725，走 **Decompose** 策略，另带 `realness`/`delta`/`generalSolution`)、
`discriminant_sym`(:760，先 `expand` 再取系数)、`factor_sym`(:845，走 **Strict**)、
`compare_expr`(:891，三态 `equal`/`not-equal`/`undetermined`)、`extrema_sym`(:954，含参极值 + 参数分类讨论)、
`simplify_sym`(:1272，多候选取最简)。

---

## 4. 化简怎么走

`simplify_sym` 不做“一次 `simplify` 就完事”，而是**生成一批候选、按节点数挑最简**
（`symbolic_api.cpp:1272-1364`）。并列时再比字符串长度，保证结果稳定可复现（:1337-1345）。

| 候选 `form` | 怎么产生 | 为什么需要 |
| --- | --- | --- |
| `原始形式` | 原表达式 | 有些形式化简反而变差 |
| `expand` | `SymEngine::expand` | `(x-a)^2-(x+a)^2` 的 `simplify` **原样返回**，只有 `expand` 给出 `-4*a*x`（:1269-1271） |
| `simplify` / `simplify(expand)` / `expand(simplify)` | 三种组合 | SymEngine 的化简不是单调的 |
| `expand(商的展开)` | `as_numer_denom` 后展开商 | 分子分母同乘同一因式时上面几条都化不掉（:1291-1300） |
| `三角恒等 sin²→1-cos²` | 显式替换 | **SymEngine::simplify 不做三角恒等**（:1302-1332） |
| `三角恒等 cos²→1-sin²` | 反向替换 | 同一自变量只取一个方向，否则两项互换会原地打转 |

选最简的单位是 `mf::symutil::node_count`（`symbolic_util.h:509`，**运算符数**，叶子算 1）。
实测（2026-10-07）：`simplify_sym {"expr":"(x-a)^2-(x+a)^2"}` → `chosen="expand"`、`simplified="-4*a*x"`；
`simplify_sym {"expr":"sin(x)^2+cos(x)^2"}` → `simplified="1"`。

`candidates` 数组会把每个候选连同 `ops` 一起回传（`symbolic_api.cpp:1347-1354`），
所以“为什么选它”是可核对的，不是黑箱。

---

## 5. 求导怎么走

| 层 | 实现 | 关键点 | 出处 |
| --- | --- | --- | --- |
| 表达式 → 导数 | `SymEngine::diff`，高阶则重复 `order` 次 | `order < 1` 抛 `invalid_argument` | `derivatives.cpp:40-57` |
| 某点导数 | 先代入，再用 `eval_double` | **整点用精确整数**（`integer((long long)point)`），否则 `real_double` | `derivatives.cpp:33-37`、`:59-72` |
| 含参数的某点导数 | `diff_at_str` | 代入后仍含自由符号 → 返回**符号文本**（如 `"4*a"`），不硬转 `double` | `derivatives.cpp:74-80`；action 侧 `calculus_api.cpp:54-66` |

为什么整点必须用整数：用 `real_double` 会把系数变成浮点，`d/dx(a*x^2)|x=2` 打印成 `4.0*a`、
`d/dx(k/x)|x=2` 打印成 `-0.25*k`；用整数代入手写得出 `4*a` 与 `-k/4`（`derivatives.cpp:28-32`）。

`calculus_api.cpp:59-65` 的判据是**整串**能否解析为数字（`used == s.size()`）：
`std::stod("4*a")` 只看前一位，绝不能当 4 用。

实测（2026-10-07）：`diff {"expr":"1/x"}` → `-1/x**2`；`diff {"expr":"sqrt(x)"}` → `(1/2)/sqrt(x)`；
`diff_at {"expr":"a*x^2","var":"x","point":2}` → `"4*a"`（前两条演示机器记号，第三条演示符号结果）。

> 注意 `diff` 的返回值来自 `SymEngine::str(*d)`（`derivatives.cpp:56`），**不经过**
> `pretty_math`。所以它的记号风格与 `simplify_sym` 不完全是同一套 —— 见 §8。

隐函数 / 参数方程求导：`implicit_diff` 用 dy/dx = −F_x/F_y，`F_y = 0` 返回 `"无法求解"`；
`parametric_diff` 用 (dy/dt)/(dx/dt)，`dx/dt = 0` 返回 `"无穷大（切线垂直）"`
（`derivatives.h:22-29`）。

---

## 6. 积分怎么走：18 条规则 + 求导自证

### 6.1 调用链

```
integrate（action，calculus_api.cpp:93）
  ├─ 有 a 与 b  → integrate_definite   → 符号 F(b)−F(a)；失败回退辛普森 n=1000（integrals.cpp:1143-1144）
  └─ 无 a / b   → integrate_indefinite → antiderivative；返回 null 时**返回 "未实现"**（integrals.cpp:1047-1052）
```

| 事实 | 出处 |
| --- | --- |
| `antiderivative` 无法积分时返回**空 `RCP`**（null），不抛异常 | `integrals.cpp:434-435`、:825 |
| 不定积分把 null 翻译成字面量 `"未实现"` | `integrals.cpp:1052` |
| 无理函数（非初等）也走同一条“如实拒绝”路径 | `integrals.cpp:1380`（`"未实现:无法符号积分该复函数"`） |
| 反常积分：无穷端按数量级分段（每 10 倍一段）求和并判收敛，发散抛 `invalid_argument` | `integrals.h:27-30` |
| 二/三重积分的数值回退是**嵌套**辛普森（内层边界可依赖外层变量） | `integrals.cpp:1286`、:1339 |

教科书边界解析：`"pi"` / `"π"` / `"oo"` / `"inf"` / `"∞"` / `"-oo"` 都认（`integrals.cpp:51-67`）。

### 6.2 规则表（自研，不调 SymEngine 的积分器）

`antiderivative` 的派发顺序（`integrals.cpp:459` 起）：`0` → 常数→`c·x` → 裸 `x`→`x²/2`
→ **Add 线性性** → **Mul**（提常数 / 特例闭式 / 分部积分）→ **Pow**（幂型、三角幂、根式、有理式）
→ 积分表（sin/cos/tan/sec/log/反三角）。

**新建的 18 条规则，每一条都在测试里配一条“求导自证”。**
“求导自证”= 对原函数求导，再与原被积函数**逐点数值比对**（`tests/test_calculus.cpp:29-60`）。

判据（逐字，`tests/test_calculus.cpp:55-57`）：

```cpp
if (!std::isfinite(a) || !std::isfinite(b)) return false;
const double den = (std::max)(1.0, std::abs(b));
if (std::abs(a - b) / den > 1e-9) return false;
```

即 **相对/绝对混合容差 1e-9**（分母取 `max(1, |f(x)|)`），在每个用例给定的 3 个点上逐一检查。

为什么必须“求导 + 数值比对”而不是比对字符串：原函数形式不唯一（`∫tan x` 写成 `−ln cos x`
还是 `ln sec x` 是同一个东西），比字符串只会误判；而规则写错时，字符串法同样会放过
（`tests/test_calculus.cpp:31-34`）。**注意：数值比对只说明“在这些点上一致”，
不构成全区间恒等的证明** —— 它是必要条件，不是充分条件。

| # | 被积函数 | 期望原函数 | 测试行 |
| --- | --- | --- | --- |
| 1 | `1/(1+x**2)` | `atan x` | `test_calculus.cpp:107` |
| 2 | `tan(x)` | `−ln cos x` | :109 |
| 3 | `x/(1+x**2)` | `½ln(1+x²)` | :111 |
| 4 | `1/(x*ln(x))` | `ln ln x` | :113 |
| 5 | `tan(x)**2` | `tan x − x` | :115 |
| 6 | `sec(x)` | `ln(sec x + tan x)` | :121 |
| 7 | `x*ln(x)` | `½x²ln x − ¼x²` | :123 |
| 8 | `exp(x)*sin(x)` | `eˣ(sin x − cos x)/2` | :125 |
| 9 | `exp(x)*cos(x)` | `eˣ(sin x + cos x)/2` | :127 |
| 10 | `atan(x)` | `x·atan x − ½ln(1+x²)` | :129 |
| 11 | `acos(x)` | `x·acos x − √(1−x²)` | :131 |
| 12 | `sin(x)**3` | `cos³x/3 − cos x` | :133 |
| 13 | `cos(x)**3` | `sin x − sin³x/3` | :135 |
| 14 | `sqrt(1-x**2)` | `(x√(1−x²) + asin x)/2` | :141 |
| 15 | `sqrt(1+x**2)` | `(x√(1+x²) + asinh x)/2` | :143 |
| 16 | `sec(x)**3` | `½(sec x·tan x + ln(sec x+tan x))` | :145 |
| 17 | `1/(1+x**4)` | 四次式闭式（分解 (x²±√2x+1)） | :147；闭式本体 `integrals.cpp:400-416` |
| 18 | `sqrt(x)*ln(x)` | `(2/3)x^{3/2}ln x − (4/9)x^{3/2}` | :149 |

“18”这个数是**数调用点**得到的：`Select-String -Path tests/test_calculus.cpp -Pattern 'antideriv_self_checks_out\('`
命中 19 行，其中 1 行是函数定义（`test_calculus.cpp:36`），**18 行是调用**。

### 6.3 这套自证抓到过一次真实错误

`∫cos³x` 的第一版把 `−sin³x/3` 写成了 `+sin³x/3`，被求导自证以 **maxrel=0.635** 当场抓出
（`tests/test_calculus.cpp:118-120`；同一条笔记在 `integrals.cpp:669-670`）。

这个数**可以复算**。符号写反时，求导结果与原式之差为：

```
d/dx[sin x + sin³x/3] − cos³x = cos x + sin²x·cos x − cos³x = 2·cos x·sin²x
```

在用例给定的点 `{0.3, 0.7, -0.6}`（`test_calculus.cpp:135`）上按 §6.2 的判据算：

| x | 差 | `den = max(1,|cos³x|)` | 比值 |
| --- | --- | --- | --- |
| 0.3 | 0.166863 | 1.000000 | 0.166863 |
| 0.7 | **0.634844** | 1.000000 | **0.634844** |
| −0.6 | 0.526269 | 1.000000 | 0.526269 |

复算命令（pwsh，2026-10-07 实跑）：

```powershell
foreach($x in 0.3,0.7,-0.6){ $c=[math]::Cos($x); $s=[math]::Sin($x); $d=2*$c*$s*$s
  "{0}`t{1:F6}`t{2:F6}" -f $x,$d,($d/[math]::Max(1.0,[math]::Abs([math]::Pow($c,3)))) }
```

最大值 0.634844 出现在 x = 0.7，远大于容差 1e-9 —— 与注释里的 0.635 一致（四舍五入到 3 位）。
**必须说清的是**：测试本身**不打印** `maxrel` 这个数（它只在失败时打印用例名，见 `test_calculus.cpp:65-72`），
所以 0.635 是“注释里的说法 + 本次复算”两处对上，不是测试输出里的字段。

现在的实现（`integrals.cpp:659-681`）逐字保留了“减”：

```cpp
// ∫cos³u = (+sin u − sin³u/3)/m   ← 注意是**减** sin³u/3
const auto cube = is_sin ? p3 : SymEngine::neg(p3);
```

实测（2026-10-07）：

```
probe_call.exe integrate {"expr":"cos(x)**3"}  → "(-1/3)*sin(x)**3 + sin(x) + C"     ← 减号在位
probe_call.exe integrate {"expr":"x**x"}       → "未实现"                            ← 非初等，如实拒绝
```

“不编造结果”这条纪律在积分层的落点就是：**非初等就返回 `未实现`**。
`tests/test_calculus.cpp:100-103` 特意把守这条底线的样本从 `∫tan x`（现已实现）换成了 `x**x`。

---

## 7. 极限怎么走

极限不是“代进去看看”，而是**先做结构化形式判定，再走分层策略**
（`limits.cpp:68-84` 的 L1–L5）。原实现的症结正是缺 L1：它用“分子/分母是否有限”猜形式，
于是 `dv = +∞` 被当成 `dv → 0`，把 `lim 1/x (x→∞)` 算成 `∞`；
`nv = dv = ∞` 直接抛“极限发散”，把 `(2x+1)/(x−1) (x→∞)` 本该是 2 报成错（`limits.cpp:81-84`）。

| 层 | 做法 | 出处 |
| --- | --- | --- |
| **L1 形式判定** | 结构化判定该点的形式，**不用 ε**；拿不准一律判 `Indet` | `limits.cpp:72` |
| **L2 确定形式** | `Finite` / `Zero` / `∞`（符号确定）→ 直接代入 | `limits.cpp:73` |
| **L3 ∞ 兜底** | `x = 1/t`（`t→0±`）；代数式的商/差先在 ∞ 上用系数比 / 阶比较 | `limits.cpp:74` |
| **L4 不定式** | `0/0`、`∞/∞` → 洛必达（每轮**重新分类**）；`1^∞`/`0^0`/`∞^0` → `exp(g·log f)`；`0·∞` → `A/(1/B)` 或 `B/(1/A)` 两种都试；`∞−∞` → 通分 / 共轭有理化 / 阶比较 | `limits.cpp:75-78`、`:664-714` |
| **L5 诚实** | 解不出就抛异常并说明**是哪种形式、为什么**，绝不给看着像结果的错值 | `limits.cpp:79`、`:1084` |

硬上限（防止单次调用把页面拖死）：递归深度 12、洛必达轮数 10、归一化 12、策略步数 3000、
**墙钟预算 1500 ms**（`limits.cpp:87-91`）。洛必达出现重复的分子分母对时判为不收敛并报错，
不做猜测（`limits.cpp:676`）。超越函数展开用 20 阶泰勒（`limits.cpp:1161`、`:1179`）。

实测（2026-10-07）：

```
probe_call.exe limit {"expr":"sin(x)/x","point":0}                → 1
probe_call.exe limit {"expr":"(2*x+1)/(x-1)","point":"oo"}        → 2     ← L1 修好后的那个回归
```

`calculus_api.cpp:179-186` 把 `±∞` 结果转成字符串 `"oo"` / `"-oo"`：JSON 没有 `inf` 字面量，
直接给 `Value(inf)` 会被序列化成 `null`，与“算不出”无法区分。`power_series_radius` 同理（`:313-321`）。

---

## 8. pretty 打印与 LaTeX 输出的分工

**两条出口，输入类型不同，用途不同，不能互相替代。**

| 出口 | 函数 | 输入 | 产出 | 谁在用 |
| --- | --- | --- | --- | --- |
| **教科书记号（文本）** | `pretty_math`（`symbolic_pretty.h:275`）/ `pretty_math_str`（`:283`） | `RCP<const Basic>` / `std::string` | 无负指数的文本（`a**(-1)`→`1/a`、`x**(1/2)`→`sqrt(x)`、`zoo`→`无定义（复无穷）`） | 符号 action 的 `solutions` / `simplified` / `delta` / `f_value` … |
| **LaTeX（给 KaTeX）** | `expr_to_latex` `math_latex.h:94` | `mf::expr::ExprNode*`（**绘图/输入侧的表达式树**） | `\frac{}{}`、`\sqrt{}`、`\left(\right)` | `prepare_expr` 的 `latex` 字段（`expr_api.cpp:266`） |
| **LaTeX（给结果）** | `symengine_to_latex` `math_latex.h:147` | `RCP<const Basic>` | 走 `SymEngine::LatexPrinter` | `sym_latex` action（`expr_api.cpp:277-291`） |

为什么要两个 LaTeX 入口：绘图路径用的是 `mf::expr` 的表达式树，而 SymEngine 的 `LatexPrinter`
只认识自己的 `Basic`。两者都要能出 LaTeX，才能让“输入框下方实时显示解析结果”覆盖全部输入
（`math_latex.h:7-9`）。

`math_latex.h` 明确声明自己输出的是**展示用** LaTeX：不保证能被 LaTeX 引擎原样编译
（不处理宏包、不做 `\operatorname*`），目标是被 **KaTeX** 正确渲染（`math_latex.h:11-12`）。

实测（2026-10-07）：

```
probe_call.exe sym_latex {"expr":"1/x"}  → {"latex":"x^{-1}","ok":true}
```

即 `sym_latex` **不经过** `pretty_math`，直接给 SymEngine 的 LaTeX —— 所以是 `x^{-1}` 而不是
`\frac{1}{x}`。这是设计上的分工，不是缺陷；但要知道“同一个 `1/x`，文本出口是 `1/x`，
LaTeX 出口是 `x^{-1}`”。

`pretty_math` 的三条**必须**记住的性质：

1. **它只做书写重排，不做化简**（`symbolic_pretty.h:271-274`）。`**` 仍然保留：`a**2` 是
   `pow_str` 的正常输出（`symbolic_pretty.h:112-134`）；它去掉的是**负**指数。
2. **括号的正确性与数值正确性是同一件事**。打印器不改运算顺序，和式出现在乘法/除法/幂的
   因子位置就必须补括号，否则重解析出来是另一个表达式：
   `(x+2)*(x+3)` 曾打成 `2 + x*3 + x`；`(x+1)/(x+2)` 曾打成 `1 + x/2 + x`（`symbolic_pretty.h:22-29`）。
   分母是**乘积**时整体加括号，判据是**因子个数**而不是“串里有没有 `*`”（`:253-257`）。
3. **虚数单位保持 `I`，绝不排版成 `i`**（`symbolic_pretty.h:178-182`）。SymEngine 的解析器只认 `I`，
   写成 `i` 会被当成自由变量，复根整批消失。`test_symbolic_contract.cpp:149-152` 钉住这条。

### 8.1 排版往返校验的实测边界（这条网没兜住的地方）

`display()`（`symbolic_api.cpp:370-377`）与 `to_pretty_array()`（`:106-121`）的策略是
“排版 → 重解析 → 比对，不等价就**退回原串**”。实测暴露出两个后果：

| 命令（2026-10-07 实跑） | 输出 | 判定 |
| --- | --- | --- |
| `solve_sym {"expr":"x^2+(1/a)*x+1"}` | `"delta":"-4 + a**(-2)"`、`solutions` 含 `a**(-1)` | **产品缺陷**：机器记号外泄（兜底网把它退回了原生串） |
| `discriminant_sym {"expr":"x^2+(1/a)*x+1"}` | `"b":"1/a"`、`"delta":"-4 + 1/a**2"` | 同一个 Δ，这里排版成功 —— 两个 action 对同一对象的记号不一致 |
| `simplify_sym {"expr":"(1/2)*x^(-1)"}` | `"simplified":"(1/2)*/x"` | **产品缺陷**：输出的是**非法表达式**（悬空 `*`），且 `simplify_sym` 未走往返校验（`symbolic_api.cpp:1357` 直接调 `pretty_math`） |

根因（读代码定位）：`pretty_math` 的 `Mul` 分支在“**所有因子都进了分母、而数值系数不是 ±1**”时，
`num_part = head + num_body`（`symbolic_pretty.h:249`）会以 `coef_prefix` 结尾的 `*`（`:170`
返回 `"-(1/2)*"` 这种带 `*` 的前缀）作为最终分子串，于是拼出 `(1/2)*/x`；系数为 1 时不受影响
（`coef_prefix` 返回空串，`:250` 兜底成 `"1"`），所以只测 `1/x` 的用例 `#5`
（`test_symbolic_contract.cpp:154-155`）抓不到它。

⚠ 这两个是**代码缺陷**，不是文档债；本文把它们放在这里是因为它们**同时**证伪了
`symbolic_api.cpp:17` 的注释（见 §11）。本文件不修代码。

---

## 9. 怎么复跑

以下命令全部在仓库根目录执行（2026-10-07 十时实跑）。

```powershell
# 1) 积分规则与求导自证（含 §6.3 那 18 条）
& '.\MF_Mathematics\build\bin\Release\test_calculus.exe'
#   → 最后一行 "106 项检查,0 项失败"

# 2) 符号 API 契约（含 #1..#7 七类回归）
& '.\MF_Mathematics\build\bin\Release\test_symbolic_contract.exe'
#   → "167 项检查,0 项失败"

# 3) 注册表守门（D-003）
& '.\MF_Mathematics\build\bin\Release\probe_call.exe' list_functions '{}'
#   → value.count == 424

# 4) 单个 action 的现形
& '.\MF_Mathematics\build\bin\Release\probe_call.exe' diff '{"expr":"1/x"}'
& '.\MF_Mathematics\build\bin\Release\probe_call.exe' integrate '{"expr":"cos(x)**3"}'
& '.\MF_Mathematics\build\bin\Release\probe_call.exe' simplify_sym '{"expr":"1/0"}'
```

注意事项（[`../../AGENTS.md`](../../AGENTS.md) §4）：

- 跑之前设 `$env:TEMP="$repo\.tmp-build"; $env:TMP=$env:TEMP`；
- `test_calculus` 与 `test_symbolic_contract` 都**显式再链一次** `symengine.lib`（`CMakeLists.txt:277-278`、`:341-342`），
  因为内核库的链接是 `PRIVATE`。改这两个用例时别忘了；
- 产物**必须新于源码**，否则你验的是旧 DLL。用 §文首那种时间戳比对，或跑 `sync-engine.ps1`
  （`test_symbolic_contract.cpp:10` 的 `#7` 就是守这条的）。

`ctest` 里这两个用例的名字是 `calculus` 与 `symbolic_contract`（`CMakeLists.txt:288`、`:353`）。

---

## 10. 未证实

按“不确定就不写”的规矩，以下几条**本文不给结论**：

| 事项 | 现状 | 怎么才能证实 |
| --- | --- | --- |
| “自研积分规则”的**总数** | 只有“配了求导自证的**调用点** = 18”是确证的。`integrals.cpp` 里还有**没有**独立 self-check 的分支，例如 `asin` 闭式（`:805-822`）、一般的 `1/(c+u²)` 与 `1/(u·ln u)`（`:715-725`） | 逐分支列出 `return RCP<const Basic>()` 之前的成功路径，并给每条补一个 `antideriv_self_checks_out` 调用点 |
| `pretty_math` 与 `SymEngine::str` 在**全部**输入上的差异 | 只实测了若干样本（见 §8.1）。`symbolic_pretty.h:3-4` 说 `str()` 会把负指数写成 `a**(-1)`，本次实测**未复现**：`diff {"expr":"1/x"}` → `-1/x**2`、`diff {"expr":"sqrt(x)"}` → `(1/2)/sqrt(x)` | 用一个属性测试遍历 `str()` 与 `pretty_math()` 的输出集合，或读该版本 SymEngine 的 printer 实现 |
| §8.1 两个缺陷的**影响面** | 不知道前端 / AI 工具表是否真的消费 `simplified`、`delta` 字段，因此不知道用户是否已经看到 `(1/2)*/x` | 沿 `MF_UI/` 搜 `simplified` / `delta` 的读取点（跨 Vue 与 React 两个工程一起搜，见 `AGENTS.md` §5 第 2 条），再用 CDP 用例复现 |
| 参数分支 `assume` 的**完备性** | `param_branches` 只按正/零/负三分（`symbolic_util.h:1257-1275`），`extrema_sym` 用代表值 `{1,3}` / `{-1,-2}` 采样（`symbolic_api.cpp:333-354`）。代码自称“分支预览而非完备证明”（`:941-942`） | 构造 `a·x+atan(x)` 那类分支内不唯一的输入，逐步细分参数范围并核对结论 |
| 极限的 1500 ms 墙钟预算在慢机器上是否足够 | 只见到常量定义（`limits.cpp:91`） | 在目标机器上跑 `test_limits.exe` 并计时 |
| 级数模块的判据与容差 | 只核对了入口（§3） | 属于 [`NUMERIC.md`](NUMERIC.md) 与该模块自身文档的范围；本文不越界下结论 |

---

## 11. 已知的文档债

| # | 位置 | 注释/旧文档说 | 代码/实测做 | 处置 |
| --- | --- | --- | --- | --- |
| 1 | `symbolic_api.cpp:17` | “输出统一用 `pretty_math()` 排版（教科书记号），**不再外泄 `a**(-1)` 这类机器记号**” | `solve_sym {"expr":"x^2+(1/a)*x+1"}` 实测返回 `"delta":"-4 + a**(-2)"`、`solutions` 含 `a**(-1)`；`simplify_sym {"expr":"(1/2)*x^(-1)"}` 返回非法的 `"(1/2)*/x"` | 待修：`pretty_math` 的 `Mul` 分支在“分子为空 + 分数系数”时不应输出悬空 `*`（`symbolic_pretty.h:170`、`:246-251`）；并把 `symbolic_api.cpp:1357` 也接入往返校验 |
| 2 | `tests/test_symbolic_contract.cpp:144-147` | `#5 输出中不得出现负指数 **(-1)` | 该断言只对 **`extrema_sym` 一个响应**做检查（`:143`=在 `r` 上查）；`solve_sym` 的泄漏因此不被抓 | 用例判据**覆盖不全**（不是“产品已无缺陷”）。待补：对 `solve_sym` / `discriminant_sym` / `simplify_sym` 的响应同样断言 |
| 3 | `docs/DECISIONS.md:46` | “`api.cpp` 只有 **22** 行；`api.h` **18** 行” | 实测 `(Get-Content MF_Mathematics/api.cpp).Count` = **27**；`api.h` = **23** | 待更新（D-001 的“现状”字段） |
| 4 | `MF_Mathematics/calculus/integrals.h:3` | 规则清单写作“多项式规则 ∫xⁿ、积分表(sin/cos/eˣ/1/x/ln)、线性性、分部积分(简单)” | 实际已含三角幂（`tan²`/`sin³`/`cos³`/`sec³`）、`sec`、`atan`/`acos`/`asin`、`√(1±x²)`、`1/(1+x⁴)`、`√x·ln x` 等 18 条（§6.2） | 待更新（枚举不完整，不影响行为） |
| 5 | `symbolic_pretty.h:3-4` | “`SymEngine::str()` 输出的是机器记号，负指数写成 `a**(-1)`” | 本次实测**未复现**该写法：`diff {"expr":"1/x"}` → `-1/x**2`、`diff {"expr":"sqrt(x)"}` → `(1/2)/sqrt(x)`（见 §10） | 待复核后再改，**不要**据注释改代码 |
