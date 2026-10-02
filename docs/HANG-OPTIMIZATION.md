# 会卡住的算法：实测、定位与优化

> 起因：不做前端"数学守卫"（提交前预判），而是**直接找出会卡住的算法并优化**。
> 这份文档只写有证据的结论：每条风险都是**真跑出来**的，每个修复都有改前/改后对照。
> 自动生成的逐条对照见 [`hang-fix-verification.md`](hang-fix-verification.md)。

## 0. 怎么找的（两把工具，互补）

| 工具 | 作用 | 用法 |
| --- | --- | --- |
| `MF_Mathematics/tools/stress_scan.py` | **广度**：从 `engineMap.js` 的参数 schema 为每个动作生成 base/big/huge/hard/chain 五档病态输入，**每个用例跑在独立子进程里带墙钟超时**，挂住就杀掉并精确定位 | `python MF_Mathematics/tools/stress_scan.py --timeout 3 --kind base,big,hard,chain` |
| `MF_Mathematics/tools/verify_hang_fixes.py` | **深度**：针对已定位的风险点，用真实病态参数逐个复核，判定 REJECTED / OK / HANG / CRASH，并生成对照报告 | `python MF_Mathematics/tools/verify_hang_fixes.py 12` |

第一轮广度扫描：**1113 个用例、15 个挂住**（3s 超时），另有一批"能算完但 3–11 秒"的。
把超时放宽到 20s 分类后：`bernoulli_number` / `fourier_series` / `poisson_summation` 是**真回不来**，
`taylor` / `power_series`（11s）、`integral_test`（3–10s）、`termwise_integration`（5.6s）、
`integral_nonnegative`（0.5–3.9s）是"慢到用户以为死了"。

同时做了一遍**只读静态审计**（递归/循环上界/按用户给的整数分配），补齐了广度扫描覆盖不到的动作
（`mandelbrot`、`expr_eval_grid`、`stft`、解析器深嵌套等）——这些不是 UI 映射表里的动作，
扫描器生成不出它们的参数。

## 1. 三类根因（不是"数学太难"，都是工程问题）

### 1.1 重复解析：同一个表达式被 parse 了上百万次

`calculus/series.cpp` 的 `eval_n(expr, var, n)` 每次调用都 `SymEngine::parse(expr)`。
单次无所谓，但 `integral_test` 的旧实现是：

```cpp
for (long long n = 1; n <= 100000; ++n)  { ... eval_n(...) ... }   // 10 万次
for (long long n = 100001; n <= 1000000; ++n) { ... eval_n(...) ... }  // 90 万次
```

**100 万次解析**。`1/n²` 这种最简单的式子要 1.0 秒，复杂式子 3–10 秒。
`series_sum` 的无穷和分支同样是 100 万次。

**修复**：
- 新增 `SeriesEvaluator`：**构造时解析一次**，之后每次只做整数代换 + 求值；
  `factorial(n)` 的字符串预处理也移到构造期。
- `integral_test` 改成**积分判别法**的真实语义：在 `[1e5, 1e6]` 上按几何节点做梯形积分
  （65 个点，跨两个数量级），阈值与原实现一致（尾部量级 < 0.1 视为收敛），
  并额外用 `|a|` 的同一积分做量级检查，避免震荡项相消骗过判据。
- `series_sum` 的无穷分支：部分和算到 2000 项，尾项按通项自身的衰减规律解析估计
  （几何衰减 → `a_N·r/(1−r)`；幂型衰减 → 先由 `a(N)/a(2N)` 估出 `p`，再用
  `a_N·N/(p−1) + a_N/2`，即积分 + Euler–Maclaurin 一阶项）。

**效果**：`integral_test` 基准 **1022 ms → 51 ms**；病态被积函数 3–10 s → 50 ms；
`series_sum` 的 `1/n²` 仍精确到 1e-7（C++ 测试要求 1.644934 ± 1e-3）。

### 1.2 重复求值：同一批样本点被算了 1000 遍

`measure_theory/lebesgue_integral.cpp` 的分层逼近里，采样点 `t = a + (b−a)·s/samples`
**不依赖外层层号 k**，却被写在内层循环里：

```cpp
for (int k = 0; k < 1000; ++k)
    for (int s = 0; s < 500; ++s)
        const double v = eval_double_str(expr, t);   // 50 万次，其中 499500 次是白算的
```

**修复**：500 个点求值一次，再按层计数（结果数学上完全等价）。
**效果**：基准 `x²` **543 ms → 49 ms**；`1/(sin(x)−0.5)` 3.9 s → 拒绝（见 1.3）。

### 1.3 用户给的一个整数直接当循环上界/分配尺寸（40 处）

这是最大的一类。例子（都是真跑出来的）：

| 动作 | 输入 | 旧行为 |
| --- | --- | --- |
| `bernoulli_number` | `n=100000` | O(n²) 大有理数递推，>20 s 不返回 |
| `series_sum` | `b=100000000` | 逐项求值 1 亿次 |
| `taylor` / `power_series` | `order=10000` | 每次系数从头求导（O(n²) 次符号求导），11 s |
| `fourier_series` | `n_terms=10000` | 每项 2 次 2000 点辛普森，8.3 s |
| `termwise_integration` | `n_terms=1000000` | 逐项累加进越来越大的符号表达式 |
| `eratosthenes` | `n=1e10` | 按 n 分配 1.25 GB 位图 |
| `discrete_log` | `p≈1e18` | BSGS 先建 1e9 项的哈希表 |
| `euler_phi` / `prime_factors` | `n≈1e18` | 试除法跑到 √n ≈ 1.5e9 |
| `mandelbrot` | `100000×100000` | 8e10 个元素的迭代数组 |
| `expr_eval_grid` | 两个 4000 长数组 | 1.6e7 个点，逐点求值 + 逐点序列化 JSON |
| `step_function_approx` | `n=1e9` | 循环 1e9 次 |

**修复**：在 `api_helpers.h` 里加了统一的**带上界取参** `get_int_bounded /
get_int_opt_bounded`（越界时抛出说明性错误，并解释"为什么有上限"），然后按一份
逐行规则表把 **82 处**调用收口（脚本 `tools/apply_int_caps.py` 保留备查，
每一处都指定了上限与面向用户的参数名）。上限的取法：先看算法代价，
再确认准确性套件里的既有取值都在范围内。

**效果**：全部变成 **50–150 ms 的明确报错**，例如
`伯努利数阶 n 超出可计算范围 [0, 500]：收到 100000。上限是为了避免单次计算卡住界面……`

### 1.4 另外三类（静态审计 + 针对性复核）

| 问题 | 位置 | 机制 | 修复 |
| --- | --- | --- | --- |
| **可证明的死循环** | `ha_internal.h` 新增 `fft_grid_size`，替换 `time_frequency.cpp` / `fourier_transform.cpp` / `convolution.cpp` 四处 | `int n = 1; while (n < n_points) n <<= 1;` —— `n_points > 2³⁰` 时左移**有符号溢出**成负数→再移成 0，而 `0<<1` 恒为 0，循环条件永远成立 | 改 `long long` + 显式上限（2²⁰；`convolution_theorem` 另压到 4096，因为它要在时域做 O(n²) 圆卷积） |
| **进程级崩溃：整数除零** | `time_frequency.cpp` 的 `stft` | `window_size=1` → 汉宁窗除以 0、`hop_size=window_size/2=0` → `(n-window_size)/hop_size` 是整数除零，x86 抛 #DE，MSVC 的 `catch(...)` **抓不到**（SEH），整个宿主进程直接消失 | 入口校验 `window_size ≥ 2`、`hop_size ≥ 1` |
| **进程级崩溃：栈溢出** | `parser_lib.h` | 递归下降解析器（`parse_expr → term → factor → unary → power → postfix → primary → parse_expr`）没有深度计数，5 万层括号（几 KB 字符串）打穿 C 栈；同样是 SEH，抓不住 | 在 `parse_expr` 入口加 RAII 深度计数，上限 512 层，超出给"请拆成几步计算" |

还有一处**先崩溃后定位**的：`gaussian_blur` 的高斯核长由 `sigma` 决定，
`(int)(2*ceil(3σ))+1` 在 `σ=1e9` 时整数溢出成一个非法尺寸 → 直接爆内存；已改为按 double 判上限。

## 2. 顺手做掉的算法优化

`generate_sigma_algebra`：成员判定原来每次线性扫描 |σ| 个集合，而并集枚举本身是
O(|σ|²) → 整体 O(|σ|³)。12 个生成元（|σ|=4096）实测 **9.7 秒**。
改成有序集合做索引后 O(|σ|² log |σ|)，同样输入 **1.76 秒**（5.5×）。

`plot_api.cpp` 的 `complex_grid` 早就有点数上限（400000），而 `expr_eval_grid` 没有 ——
本次按同一数值补齐（同项目内已有正确做法，只是漏了这一处）。

## 3. 验证

**广度扫描**（1113 个病态用例，3s 超时）：修复前 **挂住 15**、最慢 10.4s；
修复后 **挂住 0 / 崩溃 0**，最慢 199ms。

**逐条复核**（`verify_hang_fixes.py`，44 个真实病态输入，每个独立子进程 + 12s 超时）：

```
status counts: {'REJECTED': 40, 'OK': 4}      # 0 HANG, 0 CRASH
```

**C++ 单元测试**：15 个可执行文件、**1128 项检查 0 项失败**
（algebra 136、algebraic_topology 89、calculus 85、complex_analysis 49、
complex_grid 153、functional_analysis 43、harmonic_analysis 34、limits 47、
linear_algebra 61、measure_theory 49、number_theory 53、numerical 47、
probability 63、real_analysis 52、symbolic_contract 167）。

**准确性套件**（v1 树 `tests/accuracy`，独立参考实现 mpmath/sympy/numpy/scipy 对拍）：
**2180 通过 / 0 失败 / 0 跳过，action 覆盖 424/424**。

### 3.1 收口时踩的坑（值得记：**上限归引擎，下限归核心**）

第一版把 82 处取参统一换成 `get_int_bounded(lo, hi)`，**下限也一起收了**。
准确性套件立刻报出 21 处失败——全是把**合法输入**挡在门外：

| 被误挡的合法输入 | 为什么合法 |
| --- | --- |
| `is_prime(6917529027641081853)`（6.9e18 素数） | 素性判定本来就快（实测毫秒级），1e12 上限纯属多余 |
| `prime_factors(1000036000099)` | 1e12 出头的半素数，试除法 √n≈1e6，本来就该算得出 |
| `fourier_coeff(n=0)` / `complex_fourier_coeff(n=-1)` | `a₀` 与 `c₋₁` 是**正常系数**，n 本来就可正可负可零 |
| `mapping_degree(sphere_dim=-1)`、`boundary_operator(dimension=-1)` | 负维数是"定义域外输入"，核心返回结果而不是报错 |
| `eratosthenes(0/1)`、`discrete_log(p=1)`、`euler_phi(-6)`、`mobius_prefix(2e7)` | 小/负/偏大的取值都有核心自己的语义与文案 |
| `trapezoidal_rule(n=0)`、`simpson_rule(n=-3)`、`taylor_polynomial(n=-1)` | 核心会给出"n 必须为正整数"这类**具体**报错 |

第二版的规则：**统一助手只管上限（防卡死），下限交还给每个动作自己的校验**；
只有"越界会崩溃/无意义分配"的三个键保留下限（`segment_size ≥ 1` 防除零、
`window_size ≥ 2` 防 stft 除零、`hop_size ≥ 0` 防帧索引倒退）。
改完 21 → 0 失败。

这条经验的通用形式：**统一入口校验只能收紧"资源上限"，不能收紧"定义域"**——
定义域是各动作的数学语义，换一层报错就等于把语义判断从核心挪到了外框，
既容易误挡合法输入，也会把可操作的报错文案变成一句"超出范围"。

### 3.2 第三轮：每项都要做一次数值积分的动作

修完上面仍有两处挂住：`fourier_series` / `poisson_summation` 取
`n_terms=1000` 且 `f=(x+1)^80`。原因是**每个系数**都要做 2 次 2000 点辛普森积分，
1000 项就是 400 万次求值——不是解析问题（表达式只解析一次），是纯粹的求值次数。
把这类动作的项数上限从 2000 收到 **200**（套件里最大用 50，余量充足），
`termwise_integration` 的 2.0s 也一并降到 0.4s 以下。

## 4. 已知仍未优化（有证据、但本轮没动）

| 位置 | 现象 | 为什么先不动 |
| --- | --- | --- |
| `algebraic_topology/persistent_homology.cpp` | 三重循环枚举 2-单形，点云 2000 点时 O(n³)≈1.3e9 | 需要改算法（Vietoris–Rips 的邻居剪枝），不是加上限就能解决的；已确认点云规模由输入决定，前端默认很小 |
| `linear_algebra/eigen.cpp` 等符号矩阵动作 | 12×12 以上符号特征值/特征多项式 | 已加 12×12 上限（快速拒绝）；真要支持更大规模需要数值路线 |
| `extras/analysis.cpp` 的 `roots_in_disc` / `poly_roots` | 迭代次数有界，但每轮在 ≤60 次多项式上密集求值 | 静态审计标注"没实测"，本轮没有对应的病态输入证据 |
| `SymEngine::expand` 对内建大整幂是否有内部保护 | `expand((x+1)^10000000)` 按定义要产出 1e7 项 | 实现体在预编译 DLL 里，无法静态确认；本轮没构造出"用户可达且真的卡住"的路径 |

## 5. 复现方式

```powershell
$V2 = "…\Multifunctional-Mathematics-v2.0"
# 广度扫描（找新的会卡住的动作；huge 档会放大到 1e7，建议先跑 base,big,hard,chain）
python "$V2\MF_Mathematics\tools\stress_scan.py" --timeout 3 --kind base,big,hard,chain
# 已定位风险点的逐条复核（并重新生成 hang-fix-verification.md）
python "$V2\MF_Mathematics\tools\verify_hang_fixes.py" 12
# C++ 单元测试
cmake --build "$V2\MF_Mathematics\build" --config Release --parallel
Get-ChildItem "$V2\MF_Mathematics\build\bin\Release\test_*.exe" | % { & $_.FullName }
# 准确性套件（在 v1 树里跑；harness.py 的 ENGINE_DLL 已指向 v2 的构建产物）
cd "…\Multifunctional-Mathematics\MF_Mathematics\tests\accuracy"; python run_accuracy.py
```

一次性收口脚本（保留备查，动手前都先看过 dry 结果）：
`tools/apply_int_caps.py`（82 处加上限）、`tools/fix_cap_regressions.py`（修回误挡的合法输入）、
`tools/relax_lower_bounds.py`（把下限交还核心）。
