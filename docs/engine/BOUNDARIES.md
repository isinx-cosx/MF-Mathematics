# 引擎的能力边界

> 本文说明引擎如实承认的能力边界：哪些数学问题返回「未实现」、哪些能力界面选不到、哪些计算性能受限。
> 构建与 C ABI 见 [`README.md`](README.md)，调用契约见 [`CONTRACT.md`](CONTRACT.md)，模块清单见 [`MODULES.md`](MODULES.md)，测试资产见 [`TESTS.md`](TESTS.md)。
> 产品级「明确不做 / 推迟 / 尚未验证」见 [`../DESIGN-BOUNDARIES.md`](../DESIGN-BOUNDARIES.md)，本文不复制其条目。

## 1. 边界有三种

| 性质 | 表现 | 相关文档 |
| --- | --- | --- |
| 能力边界（设计选择的直接后果） | 数学上确实非初等 / 确实无解 → 如实拒绝，不硬凑 | [`../DESIGN.md`](../DESIGN.md) |
| 界面不可达 | 引擎有实现、学科页选不到 | 本文「界面不可达的功能」一节 |
| 性能受限 | 能用但慢，或受规模上限约束 | [`../HANG-OPTIMIZATION.md`](../HANG-OPTIMIZATION.md)、本文「性能受限的计算」一节 |

三类性质不同：能力边界改它需要改设计；界面不可达改它需要补入口或登记守卫；性能受限改它只需要有人优化。

## 2. 数学上如实拒绝的类

### 2.1 不定积分：非初等函数

判定点只有一处：`antiderivative()` 返回空指针就返回字面量 `"未实现"`（[`../../MF_Mathematics/calculus/integrals.cpp`](../../MF_Mathematics/calculus/integrals.cpp) 的 `integrate_indefinite`）。边界由规则命中与否决定，不是一张写死的黑名单。

| 输入 | 数学上为什么 |
| --- | --- |
| `x^x` | 无初等原函数 |
| `sin(x)/x` | Si(x)，非初等 |
| `exp(-x^2)` | 误差函数，非初等 |
| `1/log(x)` | li(x)，非初等 |
| `x^2*exp(-x^2)` | 同上族 |

反例：`tan(x)` 返回 `-log(cos(x)) + C`，`1/(1+x^4)` 返回四次式闭式。边界是「能算的越来越多」，不是「一律拒绝」。新增积分规则逐条配求导自证（对结果求导再与原式数值比对），见 [`TESTS.md`](TESTS.md)。

### 2.2 不定重积分 / 三重积分

内层积分失败就整条返回 `"未实现"`。通解形状与单变量不同：二重是 `H(x,y) + A(x) + B(y)`、三重是三层任意函数相加，这是数学上正确但用户容易误读的地方。

### 2.3 不定式极限

`calculus/limits.cpp` 对某几类形式兜底抛「不定式「<形式>」暂未实现该形式的求解（不猜结果）」。振荡型（如 `x*sin(1/x)` 在 0 处）被拒绝；而 `abs(x)/x` 在 0 处返回「极限不存在：左 -1、右 1（两侧不等）」，那是结论不是拒绝。判据是「确定形式给对值、不定式给对或如实拒绝」。

### 2.4 未识别的拓扑空间名

`fundamental_group {"space":"blahblah"}` 返回中文报错并列出可用写法，不给占位串。历史上曾返回 `π₁(<输入>)` 且 `isError:false`，现已改为报错并有回归断言。

### 2.5 拒绝形状不统一

同一个「算不出来」，引擎有三种外部形状：

| 形状 | 例子 |
| --- | --- |
| `isError:false` + 字面量 `"未实现"` | `integrate`、`integrate_double`、`integrate_triple` |
| `isError:true` + 中文文案 | `integrate_complex`（复符号积分失败）、`limit` 的不定式、未识别拓扑空间 |
| `isError:true` + 第三方英文原文 | `complex_eval` 对 `zeta(1+14.13i)` 返回 `Not Implemented` |

第三种形状来自 SymEngine 覆盖边界：`complex_numeric.h` 记录了 `zeta(2)` 能算、`zeta(1+14.13i)` 直接 `Not Implemented`，`gamma` 同理，`erf/erfc` 连实数都不支持。而复数绘图路径 `complex_grid` 接了引擎自己的复数求值，能画 ζ，于是「绘图能画、单点求值报英文错」——这是接口不一致，不是数学边界。

## 3. 界面不可达的功能

### 3.1 可达性守卫

守卫在 [`../../MF_UI/MFMath.UI.Vue/tools/check-ui.mjs`](../../MF_UI/MFMath.UI.Vue/tools/check-ui.mjs)，第 6 项。判据是：`ENGINE_MAP ∪ EXTRA_MAP` 里每个模式，要么在某页面的 `modes` 里，要么它的 `fn` 已被页面某个模式覆盖，要么已显式登记，否则报错。反向校验登记了却已可达的过时条目。当前状态：

```text
引擎模式可达性 ：映射 415 个 / 页面并集 391 个 / 取不到 0 个（已登记 0 个待补或无处安放）
```

复跑：

```powershell
cd MF_UI/MFMath.UI.Vue; node tools/check-ui.mjs
```

守卫初次运行时是 64 个「引擎有映射、页面选不到」的模式，现已清零。

### 3.2 重复命名模式

24 个「名字选不到、功能另有入口」的模式走 `DUPLICATE_NAME_GROUPS` 登记表。它们的 `fn` 都被页面上另一个名字覆盖，功能可达，缺的只是旧名字。这 24 个是命名冗余，不是功能缺口，与上文「可达性守卫」一节的功能缺口不是一回事。当前守卫打印：

```text
重名模式登记 ：已登记 24 个，未登记 0 个
```

### 3.3 守卫看不见的部分

可达性断言只遍历 `ENGINE_MAP ∪ EXTRA_MAP`（415 个模式名），而引擎注册表是 424 个 action。两者差 53 个 action 完全不在任何 `ENGINE_MAP` 条目里，守卫对它们不下一句断言。这 53 个里大部分是内部/画图通路（`expr_eval*`、`complex_grid`、`mandelbrot`、`sym_latex`、`to_engine_expr`、`prepare_expr`、`list_functions`），也夹着看着像用户能力的（`integrate_complex`、`real_integral`、`taylor_series`、`zeta_negative`、`is_harmonic`、`is_conformal`、`is_connected`、`matrix_multiply` 等）。函数工具箱以签名表为唯一数据源列出全部 424 个 action 并可调用，因此「学科页选不到」不等于「没有入口」。

差集复跑：

```powershell
cd MF_UI/MFMath.UI.Vue
node --input-type=module -e "
import fs from 'node:fs';
const sig = JSON.parse(fs.readFileSync('src/lib/ai/engine-signatures.json','utf8'));
const em = await import('./src/lib/engine/engineMap.js');
const extra = await import('./src/lib/engine/engineMapExtra.js');
const ALL = { ...em.ENGINE_MAP, ...extra.EXTRA_MAP };
const mapped = new Set(Object.values(ALL).map(v => v.fn));
const fns = Object.keys(sig);
console.log('action', fns.length, '已映射 fn', mapped.size, '未映射', fns.filter(f=>!mapped.has(f)).length);
console.log(fns.filter(f=>!mapped.has(f)).join(' '));
"
```

### 3.4 冻结的 Vue 绘图组

绘图组已整组迁到 React，6 个 Vue 绘图视图被裁定为冻结的回退资产。守卫 `check-ui.mjs` 用白名单加双向断言：目录里多一个文件要改白名单，任何人 import 它们就报错。当前打印：

```text
冻结的 Vue 绘图组 ：6/6 个文件在位，被 import 0 处
```

这是「前端有、不在构建图里」，与上文「可达性守卫」的「引擎有、界面选不到」不是一回事。

## 4. 性能受限的计算

参数决定循环次数或分配尺寸的动作走统一上界收口（[`../../MF_Mathematics/api_helpers.h`](../../MF_Mathematics/api_helpers.h) 的 `get_int_bounded` / `get_int_opt_bounded`），越界抛说明性错误。逐处上限与改前/改后对照见 [`../HANG-OPTIMIZATION.md`](../HANG-OPTIMIZATION.md)，本文不复制其数字。要点：

| 类别 | 处理 |
| --- | --- |
| 超点数 / 超项数 | 上界收口，越界返回中文报错 |
| 符号矩阵特征理论 | 12×12 上限 |
| 持续同调点云 | 三重循环 `O(n³)`，规模由输入决定，本轮未改算法 |

复现入口：

```powershell
python MF_Mathematics/tools/stress_scan.py --timeout 3 --kind base,big,hard,chain
python MF_Mathematics/tools/verify_hang_fixes.py 12
```

## 5. 怎么复查本文

```powershell
# ① 注册表 count
& MF_Mathematics/build/bin/Release/probe_call.exe list_functions '{}'   # value.count 应为 424

# ② 可达性守卫
cd MF_UI/MFMath.UI.Vue; node tools/check-ui.mjs                         # 应 exit 0

# ③ 「未实现」示例（在 MF_Mathematics\build\bin\Release 下）
.\probe_call.exe integrate '{"expr":"x^x","var":"x"}'
```

①③ 依赖 `build/bin/Release` 的构建产物；产物与当前源码逐字一致需先重新构建。
