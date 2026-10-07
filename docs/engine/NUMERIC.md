# 数值层怎么组织：特殊函数、复数、精度与容差策略

> **本文只回答一个问题：数值层怎么组织 —— 特殊函数、复数、精度与容差策略。**
>
> 与同层其它文档的分工：
> - [README.md](README.md) —— 两个构建目标、C ABI 恰好两个导出、构建与测试入口；
> - [SYMBOLIC.md](SYMBOLIC.md) —— 符号层：SymEngine/RCP 边界、化简/求导/积分/极限、pretty 与 LaTeX；
> - [INPUT.md](INPUT.md) —— 输入层：`math_input`/`parser_lib` 的归一化与解析；
> - [PLOT.md](PLOT.md) —— 采样与视口契约、`complex_grid` 字段的前端消费方式、分形迭代上限；
> - [TESTS.md](TESTS.md) —— 可执行目标 / CTest 用例怎么跑、怎么加一条。

本文所有数字都是 **2026-10-07 在本机 `MF_Mathematics/build/bin/Release`（产物时间 2026-10-06 05:43）上实测**，
每条都附可复跑命令。凡未实测的一律标「未证实」。

---

## 0. 三条纪律在数值层的落点

| 纪律 | 数值层的机制 | 出处 |
| --- | --- | --- |
| ① 不编造结果 | 算不出实数一律返回 `NaN`；网格里 `NaN` 单元格序列化成 JSON `null`，`ok`/`nan` 分别计数 | `special_numeric.h:16-17`、`plot_api.cpp:300-306`、`plot_api.cpp:323-324` |
| ② AI 不承担计算 | 复网格求值在引擎内完成（含 ζ/Γ/erf 的复数实现），前端只消费 `re`/`im` | `plot_api.cpp:18-19`、`plot_api.cpp:27` |
| ③ 留下「为什么」与「怎么证明」 | 数值实现自带契约测试；`test_complex_grid` 的 ①–⑥ 是硬断言，⑦ 用 `CHECK_KNOWN` 记录已知缺陷而**不**把错误行为固化成期望值 | `test_complex_grid.cpp:46-65`、`test_complex_grid.cpp:16-17` |

「不做静默降级」的两条具体表现：网格点数超限**报错**而不是悄悄降分辨率（`plot_api.cpp:238-240`）、
`unsupported` 非空表示「算不出来」而不是返回假值（`plot_api.cpp:331-332`）。

---

## 1. 数值层的文件与调用链

| 文件 | 职责 | action 数（实测） |
| --- | --- | --- |
| [`special_numeric.h`](../../MF_Mathematics/special_numeric.h) | 实值特殊函数（Γ/logΓ/ψ/ψ⁽ⁿ⁾/ζ/β/erf/erfc/W）+ `eval_double_ex` 增强求值 | 0（纯头文件，被别的模块调用） |
| [`complex_numeric.h`](../../MF_Mathematics/complex_numeric.h) | 复值表达式求值（`complex_grid` 的唯一数据来源） | 0（同上） |
| `MF_Mathematics/numerical/**` | 积分 / ODE / 插值 / 误差稳定性 / 优化 / 矩阵数值（Eigen） | 25（`numerical_api.cpp` 的 `register_function` 计数） |
| `MF_Mathematics/probability/**` | 概率统计：自带分布 CDF/分位数（不引 scipy） | 40（`probability_api.cpp`，同上） |
| `MF_Mathematics/plot_api.cpp` | `complex_grid` / `complex_eval` / `intersections` 等 | 4 |

两条调用链（数值层最需要记住的东西）：

```
complex_grid (plot_api.cpp:241)
   → mf::cnum::eval_node (complex_numeric.h:124)
       ├─ gamma / zeta / erf / erfc → 引擎自己的复数实现 (complex_numeric.h:211-214)
       └─ 其余初等函数              → SymEngine::eval_complex_double (complex_numeric.h:219,245,253)

符号表达式的数值回退 (symbolic_util.h:42, 1012)
   → mf::num::eval_double_ex (special_numeric.h:396)：三级递进，见 §3.2
```

第三个入口是 `probe_call.exe <action> <args_json>`：它只走 C ABI（`tests/probe_call.cpp:8-11`），
「探针观察到的与宿主/JS 调用方看到的是同一条路径」——本文所有实测都用它。

---

## 2. 第三方库：各自负责什么

| 库 | 引入处 | 源码里**直接**调用？ | 负责什么 |
| --- | --- | --- | --- |
| SymEngine | `CMakeLists.txt:139-140` | 是（`special_numeric.h:20-29`、`complex_numeric.h:29-35`、`plot_api.cpp:31-43`） | 表达式树、解析、`eval_double`/`eval_complex_double`、`diff`/`solve`/`subs`；即数值层的「原生求值」一级 |
| FLINT / GMP / MPFR | `CMakeLists.txt:141-143` | **否** | 仅作为 SymEngine 的传递依赖被链接；见下面的 grep 结论 |
| Eigen | `CMakeLists.txt:13-15`（`MF_EIGEN_INCLUDE_DIR`，默认 vcpkg）、`CMakeLists.txt:134` | 是（纯头文件） | 稠密矩阵与线性代数：`numerical/matrix_numerical.h:12`、`numerical/numerical_api.cpp:17`、`linear_algebra/*`、`functional_analysis/*`、`extras/*` |

「引擎源码里不直接调用 FLINT/GMP/MPFR」是 grep 结论：

```powershell
Get-ChildItem MF_Mathematics -Recurse -Include *.h,*.cpp | Select-String -Pattern 'mpfr|gmp|flint'
# 实测：0 处源码命中，全部命中在 CMakeLists.txt（构建脚本）
```

因此「MPFR 提供高精度计算」这类说法在本引擎**不成立**（未证实；要证实需找到一处直接调用 `mpfr_*` 的源码）。
运行时版本由 DLL 名固定：`symengine-0.14.dll`、`flint-24.dll`、`gmp-10.dll`、`mpfr-6.dll`（`CMakeLists.txt:156`）。

---

## 3. 实值特殊函数（`special_numeric.h`）

存在的理由（`special_numeric.h:1-17`）：SymEngine 的 `eval_double` 没有 Γ/PolyGamma/Zeta/Beta/LambertW，
含这些函数的导数**一个采样点都算不出来**。本文件补上，并且算不出实数**一律返回 `NaN`**（不抛异常、不返回错值），
让调用方沿用统一的「NaN = 该点不可求值」判断；能直接用标准库的就用（`erf`/`erfc` → `special_numeric.h:281-282`）。

| 函数 | 实现要点（以代码为准） | 极点 / 域外 → NaN | 出处 |
| --- | --- | --- | --- |
| `gamma_real` | `x>0` 走 `exp(lgamma(x))`；`x<0` 非整数走反射公式 `π/(sin πx·Γ(1−x))` | 非正整数；`\|sin πx\|<1e-300` | `special_numeric.h:44-54` |
| `loggamma_real` | `lgamma` | `x ≤ 0` 或非有限 | `special_numeric.h:57-60` |
| `digamma_real` | 递推抬到 `y ≥ 8` 再用渐近展开（系数 `1/12,1/120,1/252,1/240,1/132`） | 非正整数 | `special_numeric.h:63-85` |
| `hurwitz_zeta` | 直接和 `n_terms` 项（默认 16）+ Euler–Maclaurin 尾部，`kB[6]` 到 `B₁₂` | `a ≤ 0`；`\|s−1\|<1e-14` | `special_numeric.h:89-112` |
| `zeta_real` | 四分支见下 | `s=1`（`1e-14` 判据） | `special_numeric.h:126-144` |
| `polygamma_real` | `ψ⁽ⁿ⁾(x)=ψ⁽ⁿ⁾(x+1)−(−1)ⁿn!/x^{n+1}` 逐次右移，再用 `(−1)^{n+1}n!ζ(n+1,y)` | 非正整数；右移 `guard > 1000000` | `special_numeric.h:152-177` |
| `beta_real` | `Γ(a)Γ(b)/Γ(a+b)` | 任一 Γ 非有限或 `Γ(a+b)==0` | `special_numeric.h:180-185` |
| `lambertw0_real` | 牛顿迭代解 `w·eʷ=x`，≤100 次，`\|Δw\|<1e-16` 停 | `x < −1/e−1e-15` | `special_numeric.h:188-204` |
| `lambertw_m1_real` | 两种渐近初值（`x>−0.1` 用 `ln(−x)` 展开，否则分支点展开），≤200 次 | `x ≥ 0`；`\|x+1/e\|<1e-12` 返回 −1 | `special_numeric.h:211-236` |

`zeta_real` 的分支（注释与代码一致，`special_numeric.h:114-125`）：

| 区间 | 做法 | 出处 |
| --- | --- | --- |
| `s ≥ 1` | Euler–Maclaurin，直接和 16 项 | `special_numeric.h:131` |
| `s == 0` | 直接返回 `−0.5`（函数方程在此失效） | `special_numeric.h:130` |
| `0 < s < 1` | 仍用 Euler–Maclaurin，项数 `n = 200/(s+0.1)`，夹到 `[64, 200000]` | `special_numeric.h:134-136` |
| `s < 0` | 函数方程降到 `1−s ≥ 1` | `special_numeric.h:139-143` |

**为什么 `0<s<1` 不套函数方程**：那样 `1−s` 仍落在 `(0,1)`，`ζ(0.5) → ζ(0.5)` 无限递归爆栈
（`special_numeric.h:122-124`；回归断言 `test_symbolic_contract.cpp:370`）。

### 3.1 容差常量与实测

精度判据在 `test_symbolic_contract.cpp:361-394`（该套件直接 `#include "special_numeric.h"` 做自检，
需要 SymEngine 头的原因见 `CMakeLists.txt:346`），判据是**绝对误差** `|a−b| ≤ tol`（`test_symbolic_contract.cpp:363-365`）：

| 断言 | 容差 | 出处 |
| --- | --- | --- |
| `zeta_real(2)=π²/6`、`zeta_real(−1)=−1/12`、`zeta_real(0)=−0.5`、`gamma_real(0.5)=√π`、`digamma_real(1)`、`lambertw0_real(1)` | `1e-12` | `test_symbolic_contract.cpp:367-369,374,380,388` |
| `zeta_real(0.5)=−1.4603545088`、`gamma_real(5)`、`gamma_real(−0.5)`、`lambertw_m1_real(−0.1)` | `1e-9` | `test_symbolic_contract.cpp:371,375,377,390` |
| `polygamma_real(1, 0.5/1.5/−0.5)` | `1e-10` | `test_symbolic_contract.cpp:381,384,386` |
| 极点必须 `isnan`：`zeta_real(1)`、`gamma_real(−2)`、`lambertw_m1_real(0.1)`、`lambertw0_real(−1)` | 硬断言 | `test_symbolic_contract.cpp:372,376,392,393` |

本轮实测：`test_symbolic_contract.exe` = **167 项检查，0 项失败**；`test_numerical.exe` = **47 项检查，0 项失败**。

### 3.2 三级递进求值 `eval_double_ex`

`special_numeric.h:389-395` 写明三级，代码即此（`special_numeric.h:396-432`），任何一级成功即返回：

1. **原生**：`subs` 后直接 `eval_double`（`special_numeric.h:403-409`）。
2. **不求值导数**：必须在替换**之前**做（替换会把求导变量换成常数，变成「对 0.5 求导」）。
   中心差分 `(f(x₀+h)−f(x₀−h))/(2h)`，二阶用三点公式；只支持同一符号的 1/2 阶；
   `h = (1e-6 或 1e-4)·max(1,|x₀|)`；`depth > 3` 放弃（`special_numeric.h:311-364`）。
3. **特殊函数数值化**：自底向上把「实参已是数值」的 Γ/ψ/ζ/W 等节点换成 `RealDouble` 再交给 `eval_double`
   （`special_numeric.h:370-387`）。

递归深度上限 `depth > 6` 直接返回 NaN（`special_numeric.h:400`）。

---

## 4. 复数层（`complex_numeric.h`）

### 4.1 为什么自己写

`complex_numeric.h:3-12` 记录的实测事实：SymEngine 的 `eval_complex_double` 只覆盖初等函数——
`zeta(2)` 能算但 `zeta(1+14.13i)` 报 `Not Implemented`，`gamma(0.5)` 能算但 `gamma(1+i)` 同样不行，
`erf`/`erfc` 连实数都不支持。所以 ζ/Γ/erf/erfc 必须自己实现。

### 4.2 求值器的组织方式

| 设计点 | 代码 | 为什么 |
| --- | --- | --- |
| 数值叶子与常数（π、e、欧拉常数）交给 SymEngine | `complex_numeric.h:131-139` | 省得自己维护常数表 |
| 函数**按名字**分派，不按类 | `complex_numeric.h:201-214` + `fn_name_cached`（`complex_numeric.h:60-67`） | `is_a<FunctionSymbol>` 对 `Sin/Log/Zeta` 编译能过但运行时恒 false；按类漏一个会**静默算错**，按名字漏了会明确报「不支持」 |
| 名字只在整棵树算一次（指针→名字缓存） | `complex_numeric.h:51-57` | 网格求值期间是同一棵树，`str()` 不便宜 |
| 整数幂走快速幂连乘（`\|e\| ≤ 64`） | `complex_numeric.h:161-181` | `z^2` 比 `pow(z,2.0)` 准且快 |
| 算不出来 → NaN + `unsupported` | `complex_numeric.h:19-20`、`plot_api.cpp:331-332` | 绝不返回看起来正常的错值 |
| 递归深度上限 200 | `complex_numeric.h:127` | 表达式深得离谱别爆栈 |
| 两参数 `Zeta(s,a)` 只在 `a=1` 可用 | `complex_numeric.h:226-235` | 其余 Hurwitz ζ 没实现，明确报出来而非拿 `a=1` 糊弄 |

### 4.3 复数 ζ / Γ / erf 的实际实现

| 函数 | 实现 | 出处 |
| --- | --- | --- |
| `zeta_complex` | 极点判据 `\|s−1\|<1e-12` → NaN，其余转 `analytic_continuation_zeta` | `complex_numeric.h:108-111` |
| `analytic_continuation_zeta` | 非正整数（`\|Im s\|<1e-12` 且 `round(Re s) ≤ 0`）→ 伯努利数 `ζ(−n)=−B_{n+1}/(n+1)`，`n>500` **抛异常**；`Re s ≥ 0` → Euler–Maclaurin；`Re s < 0` → 函数方程 | `zeta.cpp:17-62` |
| E-M 求和 | `N = ceil(0.8\|s\|)+8` 夹到 `[16, 4000000]`；尾部在**最小项**处截断（渐近级数发散）；停止判据 `1e-19·scale` | `ca_internal.h:155-202` |
| `gamma_complex` | Lanczos，`g=7`、9 个系数 `c[0..8]`；`Re z<0.5` 走反射公式；非正整数**抛异常** | `ca_internal.h:61-82` |
| `erf_complex` | `\|z\|>4` 用渐近展开（先按 `erf(−z)=−erf(z)` 折到右半平面），项开始变大就停；否则泰勒级数（≤250 项，`\|t\|<1e-20` 停） | `complex_numeric.h:79-103` |
| `erfc_complex` | `1 − erf_complex(z)` | `complex_numeric.h:105` |

**异常如何收口**：`gamma_complex` 在极点抛 `std::invalid_argument`（`ca_internal.h:68-70`），
`analytic_continuation_zeta` 在 `|Re s|>500` 的负整数点抛异常（`zeta.cpp:27-31`）；`complex_grid` 的求值循环
用 `try/catch` 兜住并转成 NaN（`plot_api.cpp:295-299`），于是这些点在网格里表现为 `null` + `nan` 计数，
而不会让异常穿过 C ABI。

### 4.4 实测精度（参考实现：mpmath 1.3.0，`mp.dps=40`）

命令模板（实部 `x0=x1`、虚部 `y0=y1`，`nx=ny=1` 是契约里的单点路径）：

```powershell
cd MF_Mathematics\build\bin\Release
.\probe_call.exe complex_grid '{"expr":"zeta(z)","x0":1,"x1":1,"y0":14.13,"y1":14.13,"nx":1,"ny":1,"digits":17}'
python -c "import mpmath as mp; mp.mp.dps=40; print(mp.nstr(mp.zeta(mp.mpc(1,14.13)),30))"
```

| 求值点 | 引擎（`digits=17`） | mpmath 参考 | 实测绝对偏差 |
| --- | --- | --- | --- |
| `zeta(1+14.13i)` | `0.324034139679685 + 0.03688287636366447i` | `0.32403413967968510673 + 0.036882876363664284926i` | 实部 ≈1e-16，虚部 ≈1.9e-16 |
| `zeta(0.5)` | `−1.4603545088095866` | `−1.4603545088095868129` | ≈1.9e-16 |
| `zeta(1+200i)` | `2.595909063070131 − 1.0525862652278348i` | `2.5959090630701371637 − 1.0525862652278352469i` | 实部 ≈6.2e-15，虚部 ≈4.4e-16 |
| `zeta(0.5+200i)` | `4.590577374969065 − 3.1894012475790965i` | `4.5905773749690526592 − 3.1894012475791441342i` | 实部 ≈1.2e-14，虚部 ≈4.8e-14 |
| `zeta(1+1000i)` | `0.9409368682928737 + 0.045226652072131925i` | `0.9409368682927533108 + 0.04522665207209509909i` | 实部 ≈1.2e-13，虚部 ≈3.7e-14 |
| `zeta(2+10000i)` | `0.9223155399003716 − 0.25836255532533037i` | `0.9223155399002110740 − 0.2583625553253814177i` | 实部 ≈1.6e-13，虚部 ≈5.1e-14 |
| `zeta(−1−100i)`（函数方程支） | `75.62350395748253 − 3.1275873739625895i` | `75.623503957491138779 − 3.1275873739493605857i` | 实部 ≈8.6e-12，虚部 ≈1.3e-11 |

结论：临界带 / 右半平面在 `|Im s|` 到 10⁴ 量级上保住约 1e-13 **相对**精度；负半平面走函数方程那一支
绝对偏差约 1e-11。`ca_internal.h:154` 的「从 |Im s|=0 到 200 以上都能保住 double 精度」按实测只在相对精度意义上成立。
另外三条同命令实测：`zeta(1)` → `null` + `nan=1`；`zeta(−600)` → `null`（超 ±500 抛异常被兜住）；
`zeta(−3) = 0.008333333333333326 = 1/120`。

### 4.5 `erf` / `erfc` 的实测精度与一个确切缺陷

| 求值点 | 引擎 | mpmath | 实测偏差 |
| --- | --- | --- | --- |
| `erf(1+i)`（泰勒支） | `1.3161512816979477 + 0.1904534692378347i` | `1.3161512816979476449 + 0.1904534692378346863i` | ≈4e-16 / 1.6e-17 |
| `erf(3+2i)`（`\|z\|=3.606`，泰勒支） | `0.9989632788567173 − 1.1546724151463507e-05i` | `0.9989632788568172689 − 1.15467243792906034e-05i` | ≈1.0e-13 / 2.3e-13 |
| `erf(2.8+2.8i)`（`\|z\|=3.96`，泰勒支） | `1.1062967417740792 − 0.09434928182314187i` | `1.1062967417631329930 − 0.0943492818327122476i` | ≈1.1e-11 / 9.6e-12 |
| `erf(4)`（`\|z\|=4` 仍走泰勒支） | `0.9999999845869657` | `0.9999999845827420997` | ≈4.2e-12 |
| `erf(4.01)`（渐近支） | `0.9999999858030595` | `0.9999999858030605786` | ≈1.1e-15 |
| `erf(5+i)`（渐近支） | `1.0000000000029599 − 2.8460183820706642e-12i` | `1.0000000000029597765 − 2.8460183820855939e-12i` | ≈1.2e-16 / 1.5e-23 |
| `erf(6+3i)`（渐近支） | `0.9999999999999496 − 1.4870834637192685e-13i` | `0.9999999999999496059 − 1.4870834637192687e-13i` | ≈5.4e-17 / 3.6e-25 |

即：`|z| ≲ 2` 与 `|z| > 4` 两支都接近双精度；**精度衰减发生在阈值附近**（`|z| = 3.96 ~ 4` 降到 1e-11 ~ 1e-12），
这是级数在切换点附近的条件数问题，不是用错了公式。

**确切缺陷（产品缺陷，2026-10-07 实测）**：`erfc(z) = 1 − erf(z)`（`complex_numeric.h:105`）在大 `|z|` 时被相消吃光：

| 输入 | 引擎返回 | mpmath 参考 | 相对偏差 |
| --- | --- | --- | --- |
| `erfc(1)` | `0.15729920705028522` | `0.1572992070502851307` | ≈5.7e-16（无相消，正常） |
| `erfc(5)` | `1.5374368445009168e-12` | `1.5374597944280348502e-12` | ≈1.5e-5 |
| `erfc(10)` | `0`（`ok=1`，**不是** `null`） | `2.088487583762544757e-45` | 100%（有效数字全丢） |
| `erfc(27)` | `0` | `5.237048923789255685e-319` | 100% |

复跑：`.\probe_call.exe complex_grid '{"expr":"erfc(z)","x0":10,"x1":10,"y0":0,"y1":0,"nx":1,"ny":1,"digits":17}'`。
测试只钉了 `erfc(1)`（`test_complex_grid.cpp:358`，容差 `1e-9`），这条缺陷**没有回归保护**。
按纪律 ①/③ 它属于「产品缺陷」而不是「算不出来」——引擎返回 `0` 且 `ok=1`，前端会把它当真值画出来。

---

## 5. 容差与精度策略

### 5.1 三种容差口径，别混用

| 判据 | 定义 | 用在哪 | 出处 |
| --- | --- | --- | --- |
| 绝对容差 | `\|a−b\| ≤ tol` | `test_numerical.cpp` 全部、`test_symbolic_contract.cpp` 的特殊函数自检 | `test_numerical.cpp:38`、`test_symbolic_contract.cpp:363-365` |
| 相对容差（带 1 下限） | `\|a−b\| ≤ tol·max(1,\|b\|)` | `test_complex_grid.cpp` 全部；`NaN` 参与比较一律失败 | `test_complex_grid.cpp:71-74` |
| 引擎内部停止判据 | 迭代增量 / 余项与量级之比 | `optimal_step_impl`、概率层连分数、迭代解法 | `numerical_core.h:135-157`、`prob_internal.h:121-122` |

⚠ 第二种口径有**固有弱点**：`b ≈ 0` 时它退化成绝对容差 `tol`。本套件里没有 `b ≈ 0` 的期望值，所以未造成误判；
但若照 §4.5 给 `erfc(10)` 加一条期望值，用这个 helper 会**通过**
（`|0 − 2.088e-45| ≤ 1e-9·max(1, 2.088e-45)` 成立）。要钉「应当极小但不为 0」的量，必须用分母取 `|b|` 的相对误差。
本仓库别处是否已有这种写法，本文未证实。

### 5.2 `complex_grid` 的容差常量（`test_complex_grid.cpp`，本轮全部通过）

| 检验对象 | 容差 | 出处 |
| --- | --- | --- |
| `z^2`/`exp`/`e^z`/`sin`/`cos`/`tan` @ `1+i`（参考 = C++ 标准库 `<complex>`）、`1/(1+z)` @ `i` | `1e-12` | `test_complex_grid.cpp:274-285,327` |
| `log(−1) = iπ`（缺省 `digits=7` 已截成 7 位有效数字）；实部必须**恰好** 0 | `1e-6`；`==0.0` | `test_complex_grid.cpp:287-300` |
| `sqrt(−1) = i` | `1e-12`，并额外断言 `\|Re\| ≤ 1e-15` | `test_complex_grid.cpp:302-311` |
| `abs(3+4i) = 5`、`\|z\| = 5` | `==5.0`（硬相等） | `test_complex_grid.cpp:320,335` |
| 实值特殊函数 `zeta(2)/zeta(3)/zeta(−1)/gamma(0.5)/erf(1)/erfc(1)/gamma(z)zeta(z)`（`digits=17`） | `1e-9` | `test_complex_grid.cpp:349-361` |
| 复值特殊函数 `gamma(1+i)`/`gamma(i)`/`erf(1+i)`（`digits=17`） | `1e-9` | `test_complex_grid.cpp:368-373` |
| 域外点/极点必须 `null` 且计入 `nan`（`1/z` 中心、`exp(1000)`、`log(0)`、`gamma(−3)`） | 硬断言 | `test_complex_grid.cpp:381-446` |
| 行优先索引 `index=j*nx+i` 与坐标一致（`z`、`2*z+I`、`var=t`）；`nx=1`/`ny=1` 只取**起点值** | `1e-12`；`1e-15` | `test_complex_grid.cpp:411,467,487,506,527-542` |
| 点数上限 400000（`701×701`、`400×1001` 必须报错且文案含 `400000`） | 硬断言 | `test_complex_grid.cpp:628-655` |

为什么特殊函数用 `1e-9` 而不是 `1e-12`：ζ 的 `0<s<1` 抵消区与 E-M 尾部截断比初等函数差几个量级。
历史原因记在 `test_complex_grid.cpp:344-352`：旧实现用截断级数 10000 项给 `zeta(2)=1.644834`，尾巴误差 ≈`1/N`≈1e-4。

### 5.3 `numerical` 包的容差常量（`test_numerical.cpp`）

| 检验对象 | 容差 | 出处 |
| --- | --- | --- |
| 积分：梯形 / 辛普森 / 高斯（`n=3`） | `0.001` / `0.0001` / `0.0001` | `test_numerical.cpp:52,54,56` |
| 数值微分 `(x³)'@2`；ODE：欧拉 / 隐式欧拉 / RK4 的 `y(1)≈e` | `0.001`；`0.5` / `0.5` / `0.001` | `test_numerical.cpp:58,67,71,69` |
| 插值（拉格朗日 / 牛顿 / 三次样条取值）、LU 重构 `L·U≈A` | `1e-10` | `test_numerical.cpp:86,91,98,133` |
| 迭代解法（雅可比 / 高斯赛德尔 / 共轭梯度）**内部** `tol`；幂法 / QR **内部** `tol` | `1e-6`，`max_iter=100`；`1e-8`，`max_iter=1000` | `test_numerical.cpp:141,143,150,156,161` |
| 条件数 `1/x`、病态 `1/(x−1)`；舍入误差界 `rounding_error_estimate(16)` | `0.01`、`>100`；`1e-16 ± 1e-30` | `test_numerical.cpp:110,112,116` |
| 梯度下降 `x_min`；符号微分 `d(x^(2+0))`/`d(x^x)`/`d((x^x)^x)` | `0.01`；`1e-9`/`1e-6`/`0.1` | `test_numerical.cpp:120-124,169-182` |
| JSON 分发层（走 `math_call`，数值同上） | `0.001`/`0.0001`/`0.01` | `test_numerical.cpp:203-252` |

本轮实测：`test_complex_grid.exe` = **153 项检查，0 项失败**，加 `--strict` 同样 **0 项失败、0 项已知缺陷**
（`--strict` 会把 `CHECK_KNOWN` 计入失败，见 `test_complex_grid.cpp:19-21,717-720`）；`test_numerical.exe` = **47 项检查，0 项失败**。

### 5.4 引擎内部的步长与停止判据（算法参数，不是测试容差）

| 参数 | 值 | 出处 |
| --- | --- | --- |
| 机器 eps | `2.220446049250313e-16` | `numerical_core.h:13` |
| 数值微分默认步长 `h` | `1e-6` | `numerical_integration.h:23`、`numerical_api.cpp:157` |
| 最优步长 `h*` | 中心差分 `(3·eps·\|f\|/\|f'''\|)^{1/3}`；单侧 `(2·eps·\|f\|/\|f''\|)^{1/2}`；高阶导数消失时退到 `eps^{1/3}·max(1,\|x\|)` / `eps^{1/2}·max(1,\|x\|)`；夹到 `[1e-12, 0.1]` | `numerical_core.h:135-157`（`h*` 只取决于 `\|f\|` 与高阶导数幅值的**比值**） |
| 高阶导数探针 | 步长阶梯 `{1e-1…1e-6}`，下限 `100·eps·max(1,\|x\|)`，取 6 个估计的**中位数**，低于噪声水位的丢弃 | `numerical_core.h:90-129` |
| `condition_number` | 差分 `eps` 默认 `1e-8`；`\|f(x)\|<1e-15` → `+inf` | `error_stability.h:11`、`numerical_api.cpp:245`、`error_stability.cpp:72` |
| `truncation_error` | `\|true_value\| > 1e-15` 时用真值，否则用第 `n+1` 项差 | `error_stability.cpp:80` |
| `is_stable` | 输入相对扰动 `1e-8`，结果相对差 `< 1e-4` 判稳定（判据写在函数里，API 不可调） | `error_stability.cpp:89-96` |
| 梯度下降 | `tol` 默认 `1e-6`；无解析导数时中心差分 `h_fd = 1e-6` | `numerical_api.cpp:268`、`optimization_core.h:36,51` |
| 迭代线代解法 / 特征值 | `tol` 默认 `1e-6`（线代）/ `1e-8`（幂法、QR），`max_iter` 默认 `1000` | `numerical_api.cpp:292,319,331` |
| 概率层连分数与级数 | `maxit=200`、`eps=3e-14`、`tiny=1e-300` | `prob_internal.h:119-122,164-198` |
| 正态 / t 分位数 | Acklam 有理逼近 + **两次**牛顿修正（`prob_internal.h:75` 声称 ≈1e-9）；t 用牛顿迭代 ≤80 次，停判 `\|step\|<1e-12·(1+\|t\|)`，`\|t\|>1e15` 发散保护 | `prob_internal.h:76-114,223-237` |

### 5.5 概率层自带分布的实测精度（无 scipy，`prob_internal.h` 自实现）

`prob_internal.h:3-4` 写明它替代 `scipy.stats`。实测 `p_value`（参数键名见 `probability_api.cpp:404-408`）：

| 调用 | 引擎返回 | mpmath 参考 | 实测偏差 |
| --- | --- | --- | --- |
| `p_value(1.96,"normal",df=1,"two-sided")` | `0.049995790296440745` | `0.0499957902964408724256…` | ≈1.3e-16 |
| `p_value(3.0,"t",df=4,"two-sided")` | `0.03994196807171879` | `0.039941968071718827275…` | ≈3.7e-17 |
| `p_value(5,"chi2",df=2,"greater")` | `0.08208499862389884` | `0.082084998623898795169…` | ≈4.5e-17 |

复跑：`.\probe_call.exe p_value '{"test_statistic":1.96,"dist":"normal","df":1,"alternative":"two-sided"}'`；
参考值用 mpmath 的 `mp.ncdf` / `mp.betainc(...,regularized=True)` / `mp.gammainc`。
`test_probability.cpp` 的判据远宽于此：多数是绝对容差 `0.01`（`test_probability.cpp:157,160,165,209-217`），
秩检验 `1e-9`（`test_probability.cpp:175`），只有少数几处 `1e-12`（`test_probability.cpp:61-66,114`）。
即**实测精度（1e-16）比测试判据（1e-2）严得多**——测试钉的是「量级与结论正确」，不是数值精度。

---

## 6. 密集求值类操作的规模上界从哪来

统一收口点是 `api_helpers.h:143-156` 的 `get_int_bounded`：凡**直接决定分配尺寸或循环次数**的参数都必须给显式上下界，
越界抛中文错误，文案里写明「上限是为了避免单次计算卡住界面——这类参数直接决定循环次数或分配大小」
（`api_helpers.h:135-153`）。逐个 action 的具体数值见下表。

| 操作 | 上界 | 越界行为 | 出处 |
| --- | --- | --- | --- |
| `complex_grid` | `nx*ny > 400000` | 报错，文案含「超过上限 400000，请降低分辨率（建议 ≤ 600×600）」 | `plot_api.cpp:253-256` |
| `trapezoidal_rule` / `simpson_rule` 的 `n` | `≤ 10000000`（`n ≤ 0` 也报错） | 报错 | `numerical_api.cpp:145,149`、`numerical_integration.cpp:21,27` |
| `gauss_quadrature` 的 `n` | API 声明 `≤ 10000000`，**实现只接受 2/3/4** | 报错「高斯求积目前仅支持 n=2,3,4」 | `numerical_api.cpp:153` vs `numerical_integration.cpp:40-41`；用例 `test_numerical.cpp:237-238` |
| `truncation_error` 的 `n`；`least_squares_fit` 的 `degree` | `≤ 1000000`；`≤ 20` | 报错 | `numerical_api.cpp:253,235` |
| `phase_portrait` | `resolution ≤ 200`、`n_trajectories ≤ 100` | 报错 | `numerical_api.cpp:192-193` |
| 迭代线代解法 / 特征值 | `max_iter ≤ 100000` | 报错 | `numerical_api.cpp:268,293,303,313,320,332` |
| 复数围道积分 / 级数项数（复数分析模块） | `n_points ≤ 10000`、级数项数 `≤ 200` | 报错 | `complex_analysis/complex_analysis_api.cpp:138,284` |
| 泛函分析采样 | `n_points ≤ 1000000` | 报错 | `functional_analysis/fa_api.cpp:266` |

「400000 从哪来」有明确的工程理由而不是拍脑袋：JSON 里每个数约 12 字节，400k 点 ×2 个数 ≈ 9.6 MB，
超过这个量桥的缓冲就顶不住（`plot_api.cpp:238-240`）。上界的作用范围也就到「一次响应」为止——
`complex_grid` 一次返回整块网格而不是让前端逐点过桥（`plot_api.cpp:235-236`）。

**一个确切没有上界的地方（2026-10-07 实测）**：三个 ODE 求解器的步数由 `double` 参数算出，不经过 `get_int_bounded`——

`n_steps = max(1, ceil((t_end − t0) / h))`（`ode_solver.cpp:16-19`），唯一的校验是 `h > 0`（`ode_solver.cpp:26,46,70`）；
`numerical_api.cpp:166-180` 对 `t0/y0/t_end/h` 全用 `get_double`/`get_double_opt`，没有界。返回体随步数线性增长：

| `t_end` / `h` | 步数 | 结果 | 输出字节数 | 耗时 |
| --- | --- | --- | --- | --- |
| `10 / 1e-4` | 100000 | `exit=0` | 2,890,232 | 274 ms |
| `100 / 1e-4` | 1000000 | `exit=3`（`probe_call` 的 4 MiB 缓冲不足，`probe_call.cpp:33`） | — | 1594 ms |

复跑：`.\probe_call.exe euler_method '{"f":"y","t0":0,"y0":1,"t_end":100,"h":1e-4}'`。
失败分类：这是**产品侧的规模上界缺口**（不是环境没准备好，也不是用例判据错）——
`math_call` 缓冲不足返回 −1 是 C ABI 既定契约，但引擎没有在计算前拒绝过大的步数。
「极端参数（如 `t_end=1e9, h=1e-9`）会不会把宿主拖死」本文**未实测**（有意不测：这类输入的目的就是耗尽内存）；
要验证就单独在一台可牺牲的机器上跑，并盯住进程 RSS。

---

## 7. 复现本文全部数字

```powershell
cmake --build MF_Mathematics/build --config Release        # 产物落在 build/bin/Release
cd MF_Mathematics\build\bin\Release
.\test_complex_grid.exe            # 期望 153 项检查，0 项失败
.\test_complex_grid.exe --strict   # 期望同样 0 项失败（KNOWN-BUG 计入失败后仍全绿）
.\test_numerical.exe               # 期望 47 项检查，0 项失败
.\test_symbolic_contract.exe       # 期望 167 项检查，0 项失败（含 §3.1 的特殊函数自检）
.\probe_call.exe complex_grid '{"expr":"zeta(z)","x0":1,"x1":1,"y0":14.13,"y1":14.13,"nx":1,"ny":1,"digits":17}'
.\probe_call.exe complex_grid '{"expr":"erfc(z)","x0":10,"x1":10,"y0":0,"y1":0,"nx":1,"ny":1,"digits":17}'
.\probe_call.exe p_value '{"test_statistic":1.96,"dist":"normal","df":1,"alternative":"two-sided"}'
.\probe_call.exe --list            # value.count 应为 424
python -c "import mpmath as mp; mp.mp.dps=40; print(mp.nstr(mp.zeta(mp.mpc(1,14.13)),30))"
```

`digits` 的语义（`plot_api.cpp:250,273-287`）：缺省 **7 位有效数字**，`digits ≤ 0` 或 `> 17` 时**原样返回**（不截断）；
`round_to` 先把 `v == 0.0` 单独返回 0，再按 `10^(digits−1−floor(log10|v|))` 定标取整。
所以 `digits` 是**显示/传输精度**，不是计算精度——计算始终是双精度，`digits` 只影响序列化。
`minMag` 忽略 `< 1e-12` 的模长（`plot_api.cpp:311`），`maxMag`/`minMag` 在无有效值时都回落成 `0.0`（`plot_api.cpp:329-330`）。

---

## 已知的文档债

1. **`test_complex_grid.cpp:658-665` 与 `plot_api.cpp:276-282` 描述的缺陷已被修好，两处注释都过期。**
   注释说：`round_to` 在 `digits ≥ 10` 时把精确 0 写成 JSON `null`，而 `nan` 计数不增加，前端无法区分「0」与「极点」。
   代码实际做：`plot_api.cpp:283` 有 `if (v == 0.0) return 0.0;`，精确 0 **不会**进入 `pow` 分支。
   实测 2026-10-07：`test_complex_grid.exe --strict` = 153 项检查、0 项失败、**0 项已知缺陷**——
   即 ⑦ 节（`test_complex_grid.cpp:666-713`）现在是空转的，`--strict` 不再证明任何缺陷存在。
   `plot_api.cpp:282` 那句「边界实测：digits≤9 正常，10~17 坏」与代码不符。
2. **`complex_numeric.h:76-77` 的精度声称与实测不符。**
   注释说「`|z| ≤ 4` 约 1e-15，`|z|` 更大时约 1e-8」。实测（§4.5）：`|z|≤2` 与 `|z|≥4.01` 都在 1e-16 ~ 1e-15；
   **最差的地方反而是阈值附近**（`erf(4)` ≈4.2e-12、`erf(2.8+2.8i)` ≈1.1e-11）。两级说法都不成立，且没提阈值处的退化。
3. **`complex_numeric.h:107` 对 `zeta_complex` 的算法描述与代码不符。**
   注释说「整数与非正整数用伯努利数、**Re>1 用级数**、其余 Euler–Maclaurin」。代码只做两件事：
   极点判据后转 `analytic_continuation_zeta`（`complex_numeric.h:109-110`），而它按 `s.real() >= 0.0` → Euler–Maclaurin、
   否则函数方程（`zeta.cpp:55-61`）——`zeta_series` 在这条路径上**不可达**。
4. **`MF_Mathematics/probability/stats_dist.h` 是死代码，且与 `prob_internal.h` 重复。**
   grep 全仓库 `stats_dist`：只有它自己第 1 行的注释命中，**没有任何文件 `#include` 它**。
   它的 `betacf`/`betainc`/`t_cdf`/`t_quantile` 与现役的 `prob_internal.h:119-237` 是同一套算法的两份拷贝，
   并且已有实质差异：`stats_dist.h:61` 用 `std::log1p(-x)`，`prob_internal.h:157` 用 `std::log(1.0 - x)`（后者在 `x→1` 时更差）。
   因此 `stats_dist.h:5`、`stats_dist.h:78` 的「精度 ~1e-12」描述的是**不被调用的代码**。
5. **`numerical/error_stability.h:15-16` 的措辞与代码判据不一致。**
   头文件说「`true_value` **非零**时返回 `|近似−真值|`」，代码判的是 `std::abs(true_value) > 1e-15`（`error_stability.cpp:80`）；
   头文件 `error_stability.h:10-11` 说「`f(x)≈0` 时返回 `+inf`」，代码判的是 `|f(x)| < 1e-15`（`error_stability.cpp:72`）。
6. **`numerical/numerical_api.cpp:3` 的 action 计数过期。** 文件头注释说「注册 19 个 action …
   matrix_numerical(Eigen)的 6 个 action 稍后追加」；实际 `register_function` 调用 **25 次**
   （5 积分 + 5 ODE + 4 插值 + 4 误差 + 1 优化 + 6 矩阵），「稍后追加」已经发生、注释没跟上。
7. **`numerical_api.cpp:153` 给 `gauss_quadrature` 的 `n` 声明 `≤ 10000000`，实现只接受 2/3/4。**
   这不是静默降级（实现明确报错，`numerical_integration.cpp:40-41`，用例 `test_numerical.cpp:237-238`），
   但 API 给出的可接受区间对调用方是误导的：`n=5` 会先通过上界检查、再被实现拒绝。
