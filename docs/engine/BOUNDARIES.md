# 引擎的能力边界

> **本文只回答一个问题：引擎如实承认的能力边界有哪些？**
>
> 与同层其它文档的分工：
> - [README.md](README.md) —— 引擎怎么构建、恰好两个 C ABI 导出、`/WHOLEARCHIVE` 守门；
> - [CONTRACT.md](CONTRACT.md) —— args JSON 形状与键名契约，含"未实现"的返回形状；
> - [MODULES.md](MODULES.md) —— 12 个学科模块逐个的 action 与能力（由签名表生成）；
> - [TESTS.md](TESTS.md) —— 引擎的测试目标与判据怎么加；
> - [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) —— 产品级"明确不做 / 推迟 / 尚未验证"（本文只写引擎侧，且**不复制**它的条目与数字）。

**核对时间**：2026-10-07（本机）。正文里带命令的输出都是**本机真跑出来的**；凡是没验证过的，逐字写"未证实"并给出验法。

---

## 0. "边界"有三种，混着写就会读成免责声明

| 性质 | 表现 | 口径在哪 | 本文 |
| --- | --- | --- | --- |
| **能力边界**（设计选择的直接后果） | 数学上确实不是初等函数 / 确实无解 → 如实拒绝，不硬凑 | [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) §3、[../DESIGN.md](../DESIGN.md) §2 ②（`:41-56`） | §1 |
| **曾经是缺陷**：引擎有实现、学科页选不到 | 现已清零，且有构建期守卫双向校验 | [../../MF_UI/BUGS.md](../../MF_UI/BUGS.md) B10、[../DECISIONS.md](../DECISIONS.md) D-012 | §2 |
| **已知未优化**：能用但慢 | 有人愿意优化就优化，不是欠债 | [../HANG-OPTIMIZATION.md](../HANG-OPTIMIZATION.md) §4（`:163-170`） | §3（**只给指针**） |

**本文不写**：① "明确不做 / 推迟" —— 见 [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) §1/§2 与 [../OPEN-ITEMS.md](../OPEN-ITEMS.md) §5；② "尚未验证" —— 见 [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) §5；③ i18n 覆盖面、AI 的回答语言 —— 是**产品边界**，不是引擎边界（同文 §3 末两行）。把这三类混进"引擎边界"，读者会把"没验过"当成"没有"。

---

## 1. 数学上如实返回"未实现"的类

### 1.1 不定积分：非初等函数（5 条，实测）

判定点只有一处：`antiderivative()` 返回空指针就返回字面量 `"未实现"` —— `MF_Mathematics/calculus/integrals.cpp:1051-1052`。所以边界是**规则命中与否**决定的，不是一张写死的黑名单。

```powershell
$p = "MF_Mathematics\build\bin\Release\probe_call.exe"
& $p integrate '{"expr":"x**x","var":"x"}'
```

| 输入 | 引擎返回（本机实测） | 数学上为什么 |
| --- | --- | --- |
| `x**x` | `{"isError":false,"value":"未实现"}` | 无初等原函数 |
| `sin(x)/x` | `{"isError":false,"value":"未实现"}` | Si(x)，非初等 |
| `exp(-x**2)` | `{"isError":false,"value":"未实现"}` | 误差函数，非初等 |
| `1/log(x)` | `{"isError":false,"value":"未实现"}` | li(x)，非初等 |
| `x**2*exp(-x**2)` | `{"isError":false,"value":"未实现"}` | 同上族 |

这 5 条与代码里的注释互相印证（**不是照抄注释，是两边都核过**）：`MF_Mathematics/tests/test_calculus.cpp:138-140` 写"26 个教科书积分里只剩非初等的那 5 条仍返回"未实现""，`:102-103` 用 `x**x` 守这条底线。

**边界是"能算的越来越多"，不是"一律拒绝"**——同一次实测的反例（在同一批规则里，命中就给闭式）：

| 输入 | 引擎返回（本机实测） |
| --- | --- |
| `tan(x)` | `{"isError":false,"value":"-log(cos(x)) + C"}` |
| `1/(1+x**4)` | `{"isError":false,"value":"(1/8)*sqrt(2)*log(...) + (1/4)*sqrt(2)*atan(-1 + sqrt(2)*x) + ... + C"}` |

`test_calculus.cpp:105-149` 里这批规则逐条配了**求导自证**（`antideriv_self_checks_out`），`:119-120` 记录了它当场抓出过一次符号写反。

### 1.2 不定重积分 / 三重积分：内层不成就整条返回"未实现"

| 输入 | 引擎返回（本机实测） | 代码位置 |
| --- | --- | --- |
| `integrate_double {"expr":"sin(x*y)","x":"x","y":"y"}` | `{"isError":false,"value":"未实现"}` | `integrals.cpp:1232`（内层对 y 失败） |
| `integrate_triple {"expr":"exp(-z**2)","x":"x","y":"y","z":"z"}` | `{"isError":false,"value":"未实现"}` | `integrals.cpp:1251-1255` |

**通解形状与单变量不同**：二重是 `H(x,y) + A(x) + B(y)`、三重是三层任意函数相加（`integrals.cpp:1218-1224`、`:1256-1258`）。这是数学上正确、但**用户容易误读**的地方（会以为和单变量一样"只差一个常数"）。端到端断言在 `MF_Mathematics/tests/test_calculus.cpp:421-422`（只断言"含未实现"，不编造）。

### 1.3 复数定积分：走**抛错**而不是返回字符串

| 输入 | 引擎返回（本机实测） |
| --- | --- |
| `integrate_complex {"expr":"z**2","var":"z","a":"0","b":"1"}` | `{"isError":false,"value":[0.3333333333333333,0]}` |
| `integrate_complex {"expr":"z**z","var":"z","a":"0","b":"1"}` | `{"isError":true,"value":"未实现:无法符号积分该复函数"}` |
| `integrate_complex {"expr":"1/z","var":"z","a":"0","b":"1"}` | `{"isError":true,"value":"Not Implemented"}` |

前两行的分界在 `integrals.cpp:1378-1380`：`antiderivative` 为空就 `throw std::invalid_argument`。**第三行是第三种形状**（详见 §1.6）：`log(0)` 求值失败时抛上来的是第三方库的英文原文，不是本项目的文案。

### 1.4 不定式极限：拒绝对某几类形式求解

`calculus/limits.cpp:1084` 兜底抛 `不定式「<形式>」暂未实现该形式的求解（不猜结果）`。本机实测两个真实输入：

| 输入 | 引擎返回（本机实测） |
| --- | --- |
| `limit {"expr":"x*sin(1/x)","var":"x","point":0}` | `{"isError":true,"value":"不定式「三角函数在 ∞（振荡）」暂未实现该形式的求解（不猜结果）"}` |
| `limit {"expr":"sin(1/x)","var":"x","point":0}` | 同上 |

⚠ **这两条要分清**：`x·sin(1/x) → 0` 其实**是存在的**（夹逼），引擎是"知道该拒绝"而不是"知道答案为 0"。这是**有意的保守**：宁可不给，也不给一个没有证明支撑的数。对照组 `limit {"expr":"abs(x)/x","var":"x","point":0}` 返回 `极限不存在：左 -1.000000、右 1.000000（两侧不等）`（`limits.cpp:1055`）——那是**结论**，不是拒绝；而 `(1+x)^(1/x)`、`x^x` 在 0 处都正常返回（本机实测 `2.718281828459045`、`1`）。

判据侧见 `MF_Mathematics/tests/test_limits.cpp:59`：期望的是"如实拒绝（不定式暂未实现 / 极限不存在）——重点是**不能给错值**"。

### 1.5 未识别的拓扑空间名：报错，不给占位串

| 输入 | 引擎返回（本机实测） |
| --- | --- |
| `fundamental_group {"space":"blahblah"}` | `{"isError":true,"value":"不认识的拓扑空间「blahblah」。可用写法：S1/S2/S3…、T2、RP2、K 或 KLEIN、FIG8、D2/D3…、POINT、RN、WEDGE5；也接受英文名 circle / sphere / torus / disk / ball / figure8 / mobius。"}` |
| `fundamental_group {"space":"circle"}` | `{"isError":false,"value":"Z"}` |
| `fundamental_group {"space":"torus"}` | `{"isError":false,"value":"Z×Z"}` |

`algebraic_topology/homotopy.cpp:76-87` 是这条的落点，`:78-79` 记录了它**曾经**返回 `π₁(<输入>)` 且 `isError:false`（用户会以为那就是答案）。回归断言：`MF_Mathematics/tests/test_algebraic_topology.cpp:158-165`；同一文件 `:167-174` 还锁住"别名表必须整组一致"（历史上 `fundamental_group("circle")` 与 `homology_group("circle",1)` 给出过互相矛盾的结论）。

### 1.6 边界的**形状不统一**——这是本文最该被看到的一张表

同一个"算不出来"，引擎有三种外部形状。做前端/宿主错误处理的人必须知道这三种都存在：

| 形状 | 例子 | 出处 | 用户看到什么 |
| --- | --- | --- | --- |
| `isError:false` + 字面量 `"未实现"` | `integrate`, `integrate_double`, `integrate_triple` | `integrals.cpp:1052`、`:1232`、`:1251-1255` | 一个**看起来像结果**的字符串 |
| `isError:true` + 中文文案 | `integrate_complex`、`limit` 的不定式、未识别拓扑空间 | `integrals.cpp:1380`、`limits.cpp:1084`、`homotopy.cpp:83-87` | 一条错误 |
| `isError:true` + **第三方英文原文** | `complex_eval {"expr":"zeta(1+14.13*i)"}` → `复数求值失败：Not Implemented`；`gamma(1+i)` 同 | `extras/extras.cpp:49-61`；`api_helpers.h:341-342` 只翻译"`=` 用错函数"那一类 | 一句英文的 `Not Implemented` |

**前两种形状的差异是否会让用户误读，未证实。** 静态证据只到这一步：UI 里**没有任何一处**引用字面量 `未实现`（`MF_UI/MFMath.UI.Vue/src` 与 `MF_UI/MFMath.UI.React/src` 全量检索命中 0 处，命中的全是教程/设置的"尚未实现"文案）；`src/lib/engine/resultModel.js:150,157,181` 会把含中文的字符串当**纯文本**渲染，即与普通结果同款样式。要证实"用户是否看得出这不是结果"，需要在真宿主里跑一次并截图——**本文不替它背书**。

**第三种形状的另一半是一处不对称（本机实测，值得单记）**：`complex_grid {"expr":"zeta(z)",…}` 返回 `{"isError":false,…,"ok":9,"unsupported":""}` ——**复数绘图路径能算 ζ**，因为 `plot_api.cpp:27,296` 接的是引擎自己的复数求值 `complex_numeric.h`（该头文件 `:8-10` 记录了 SymEngine 的覆盖边界：`zeta(2)` 能算、`zeta(1+14.13i)` 直接 `Not Implemented`；`gamma` 同理；`erf/erfc` 连实数都不支持）。而同一个数学能力在 `complex_eval` 这个 action 上没有接，于是"绘图能画、单点求值报英文错"。这是**接口不一致**，不是数学边界。

### 1.7 为什么"拒绝"是设计选择，而不是没做

- **错误的原函数比"未实现"危险得多**：用户看到"未实现"会换条路；看到一个错的闭式解，他会拿它去算别的东西（[../DESIGN.md](../DESIGN.md) `:52-53`）。
- **代价被明确写下来了**：用户会觉得"这软件连这个都不会"——这是**有意的取舍**（同文 `:55-56`）。
- **改它的门槛是"改设计"，不是"补功能"**：[../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) `:115` 写明能力边界"不动门槛"；要改先改 [../DESIGN.md](../DESIGN.md) §2 ② 与 [../DECISIONS.md](../DECISIONS.md)。
- **它对应的接口纪律**："AI 不承担计算、引擎不编造"——[../DECISIONS.md](../DECISIONS.md) D-002（前端不承担任何计算）+ [../DESIGN.md](../DESIGN.md) §2 ②。

### 1.8 边界内的一个**刻意例外**：S⁰

`fundamental_group {"space":"S0"}` 返回 `{"isError":false,"value":"π₁(S0)"}`（本机实测）——**这是一个占位串**，而本项目最想避免的就是占位串。`homotopy.cpp:81-82` 写明了理由：S⁰ 非道路连通，本就**没有基本群可言**，所以那是"如实说明"而不是"不知道"，引擎测试也明确要求（对齐 Python）。判据：**占位串服务于"问题本身不成立"，不服务于"我还不会算"**。写在这里，是因为它是"边界"最容易被误读成"退步"的一处。

---

## 2. 引擎有实现、学科页选不到的模式

### 2.1 `NOT_EXPOSED` 的口径与双向校验（给行号）

守卫在 `MF_UI/MFMath.UI.Vue/tools/check-ui.mjs`，第 6 项：

| 行号 | 内容 |
| --- | --- |
| `:200-212` | 该项的说明：为什么会藏住（用例 `setBlock` 找不到模式只 `return 'no-mode'`，调用方不看返回值，最后表现成一条看不懂的断言失败） |
| `:202` | "实测发现：**64 个**模式在 ENGINE_MAP/EXTRA_MAP 里有完整映射、引擎也实现并有测试，但…一个都没挂" |
| `:213-226` | `NOT_EXPOSED_GROUPS` —— **现已为空数组**；`:214` 注明"本项自检第一次跑时是 64 个"，`:216-222` 记下最后离开这个名单的三条（柯西定理 / 辐角原理 / Rouche 定理、空间完备性）与各自的修法 |
| `:227-228` | `NOT_EXPOSED = new Map(...)` |
| `:230-241` | **正向**：`ENGINE_MAP ∪ EXTRA_MAP` 里每个模式，要么在某页面的 `modes` 里，要么它的 `fn` 已被页面某个模式覆盖，要么已登记，否则报错 |
| `:242-251` | **反向**：登记了却已经可达 / 登记了却不在 ENGINE_MAP 里 → 报"过时条目，请删除" |
| `:252-255` | 打印一行汇总 |

口径的**精确措辞**在 `:210-211`：判据是"模式名可选到 **或** 它的 `fn` 已被**页面上的**某个模式覆盖（同一个 action 换个名字挂在页面上，不算缺口）"，其余必须显式登记。

### 2.2 64 → 0：怎么复算这个数字

`64` 是**历史数字**，**不能**从当前代码复跑（当前跑到的是 0）。它有两处相互独立的证据，都能复跑：

```powershell
# ① 守卫自己的说明（行号见上表）
Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern '64 个'
# ② 清零那一次提交：提交信息 + 该提交里 viewConfigs.js 的注释（"共 64 个"）
git show 1eef596 --stat
git show 1eef596:MF_UI/MFMath.UI.Vue/src/lib/engine/viewConfigs.js | Select-String -Pattern '64 个'
```

`1eef596` 的提交信息原文是"二、引擎模式可达性：64 个'引擎有映射、页面选不到' → **0**"，并注明"该守卫第一次跑就抓到我误登记的 4 个别名"——即**反向校验当场生效过**。当前状态（本机实测，退出码 0）：

```
引擎模式可达性      ：映射 415 个 / 页面并集 391 个 / 取不到 0 个（已登记 0 个待补或无处安放）
```

跑法：`cd MF_UI/MFMath.UI.Vue; node tools/check-ui.mjs`（`npm run check:ui` = `build-tutorials.mjs && check-ui.mjs && check-examples.mjs`，见 `package.json`）。

### 2.3 24 个"名字选不到、功能另有入口"：**另一档**，不是缺口

判据收紧后新暴露的一批，走另一张登记表 `DUPLICATE_NAME_GROUPS`（`check-ui.mjs:330-346`；正向 `:395-399`、反向 `:400-406`、打印 `:408`）。它们**不是** 64 那一类：

- 这 24 个的 `fn` **都**已被页面上的另一个名字覆盖 ⇒ **功能是可达的，缺的只是"这个旧名字"**（`check-ui.mjs:326-328`；逐个对应表见 [../../MF_UI/BUGS.md](../../MF_UI/BUGS.md) `:785-800`）。
- 本机实测那一行：`重名模式登记        ：已登记 24 个，未登记 0 个`。
- 唯一**不只是重名**的一条是 `解不等式组`：它的 `args` 是**空的**，而页面上同 `fn` 的 `解不等式/组` 声明了 `ineqs` —— 即便挂出来也构造不出参数，`check-ui.mjs:339-342` 建议直接删。
- 该守卫的"验证过会失败"：把「化简」从登记表里去掉 → 报错 exit 1（[../../MF_UI/BUGS.md](../../MF_UI/BUGS.md) `:776`）。

**结论口径**：§2.2 的 64 是**功能缺口**（引擎有、界面全无入口），§2.3 的 24 是**命名冗余**。把两者写成"24 项能力缺失"是错的，[../../MF_UI/BUGS.md](../../MF_UI/BUGS.md) `:779-783` 专门更正过这一点。

### 2.4 ⚠ 这个守卫**看不见**什么：口径的边界

`check-ui.mjs` 的可达性断言只遍历 `ENGINE_MAP ∪ EXTRA_MAP`（`:231`、`:391`）——即 **415 个模式名**。引擎的注册表是 **424 个 action**（本机实测：`probe_call.exe list_functions` 的 `count` 为 `424`；同一数字也是构建守门值，[../DESIGN.md](../DESIGN.md) `:48-50`）。

于是有一批 action **完全不在任何 `ENGINE_MAP` 条目里**，`NOT_EXPOSED` 的机制对它们**一个断言都不下**。本机实测的差集：

```powershell
cd MF_UI/MFMath.UI.Vue
node --input-type=module -e "
import fs from 'node:fs';
const sig = JSON.parse(fs.readFileSync('src/lib/ai/engine-signatures.json','utf8'));
const em = await import('./src/lib/engine/engineMap.js');
const extra = await import('./src/lib/engine/engineMapExtra.js');
const ALL = { ...em.ENGINE_MAP, ...extra.EXTRA_MAP };
const mapped = new Set(Object.values(ALL).map(v => v.fn));
const fns = Object.keys(sig.functions);
console.log('action', fns.length, '已映射 fn', mapped.size, '未映射', fns.filter(f=>!mapped.has(f)).length);
console.log(fns.filter(f=>!mapped.has(f)).join(' '));
"
```

实测输出：`action 424 已映射 fn 371 未映射 53`。这 53 个里**大部分是内部/画图通路**（`expr_eval*`、`complex_grid`、`mandelbrot`、`sym_latex`、`to_engine_expr`、`prepare_expr`、`list_functions` …），但也夹着**看着像用户能力**的：`integrate_complex`、`real_integral`、`taylor_series`、`zeta_negative`、`is_harmonic`、`is_conformal`、`is_connected`、`matrix_multiply` 等。

**但"学科页选不到"≠"没有入口"**：函数工具箱以 `src/lib/ai/engine-signatures.json` 为**唯一数据源**，把全部 424 个 action 列出来并可直接调用（`MF_UI/MFMath.UI.Vue/src/views/tools/ToolboxView.vue:3`、`:10-11`、`:22`、`:46`；[../../MF_UI/BUGS.md](../../MF_UI/BUGS.md) `:764` 以 `matrix_multiply` 举过这个例子）。

**未证实**：这 53 个 action 是否**逐个**能在工具箱里调用成功、返回有意义的结果，我没有验证（要验就得在真宿主里逐个点，或对 `probe_call.exe <fn>` 逐个喂合法参数）。所以本文只说"工具箱**列出**了它们"，不说"它们都能用"。

### 2.5 相关但不同类：冻结的 Vue 绘图组

不是"引擎有、界面选不到"，而是"**前端有、不在构建图里**"：6 个 Vue 绘图视图被裁定为**冻结的回退资产**，`check-ui.mjs:356-359` 是白名单、`:365-388` 双向断言（目录里多一个文件要改白名单；**任何人 import 它们就报错**），`:407` 打印"`6/6 个文件在位，被 import 0 处`"（本机实测一致）。它属于 [../DECISIONS.md](../DECISIONS.md) D-005；本文列它只为**划清界线**——"点不到"的两种成因（口径没接上 / 代码被冻结）不是一回事。

---

## 3. 慢的地方：只给指针

**本节不复制任何数字**——那份清单有自己的维护者、判据与验证记录，复制就会有两份真相。

- 已知仍未优化的算法：持续同调 `O(n³)`、符号矩阵 > 12×12、`roots_in_disc` 密集求值、`expand((x+1)^10000000)` 等 —— 见 [../HANG-OPTIMIZATION.md](../HANG-OPTIMIZATION.md) **§4**（`:163-170`）。
- 逐条改前/改后对照：`docs/hang-fix-verification.md`（[../HANG-OPTIMIZATION.md](../HANG-OPTIMIZATION.md) `:5` 指向它）。
- 产品侧的同一份指针：[../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) §4（`:77-85`，同样只给指针）。
- **性质**：这一节是"能用但慢"，与 §1 的"算不出来"、§2 的"点不到"**都不是一回事**；改动它不需要改设计，只需要有人愿意优化。

复现入口（原文 §5 `:173-189` 有完整版）：`python MF_Mathematics/tools/stress_scan.py --timeout 3 --kind base,big,hard,chain` 与 `python MF_Mathematics/tools/verify_hang_fixes.py 12`。

---

## 4. 怎么复查本文

```powershell
$V2 = "<...>\Multifunctional-Mathematics-v2.0"
# ① §1 的全部实测样例（返回 JSON 里的 isError / value）
& "$V2\MF_Mathematics\build\bin\Release\probe_call.exe" list_functions   # count 应为 424
& "$V2\MF_Mathematics\build\bin\Release\probe_call.exe" integrate '{"expr":"x**x","var":"x"}'

# ② §2 的守卫与它当前打印的那几行（应 exit 0）
cd "$V2\MF_UI\MFMath.UI.Vue"; node tools/check-ui.mjs

# ③ §2.2 的历史数字 64（只能从提交取证，当前代码里查不到）
git -C $V2 show 1eef596:MF_UI/MFMath.UI.Vue/src/lib/engine/viewConfigs.js | Select-String '64 个'

# ④ §2.4 的差集（424 vs 371 vs 53）
#    脚本见 §2.4 正文
```

**本文的判据口径**（与 [../../AGENTS.md](../../AGENTS.md) §5 一致）：跑输出了就写"实测 + 命令"；只读了代码就写"静态 + `文件:行`"；没验的一律写"未证实"并给出验法。**任何在并发窗口里得到的失败数字都不作数**——跑端到端前先确认没有别的会话在驱动同一个页面（[../../MF_UI/BUGS.md](../../MF_UI/BUGS.md) `:196-198`）。

---

## 已知的文档债

> 规矩同 [../../AGENTS.md](../../AGENTS.md) §5：**与代码不符的注释/旧文档要记在这里，注明 `文件:行`**。下面每条都附了复跑命令。

| # | 位置 | 文档/注释说 | 代码实际做 | 复跑方式 |
| --- | --- | --- | --- | --- |
| 1 | `MF_UI/MFMath.UI.Vue/tools/check-ui.mjs:203` | "viewConfigs 的 **13 个**页面模式表" | 当前 `VIEW_CONFIGS` 有 **14** 个键；清零那次提交 `1eef596` 里也已经是 14 | `node -e "import('./src/lib/engine/viewConfigs.js').then(m=>console.log(Object.keys(m.VIEW_CONFIGS).length))"`（在 `MF_UI/MFMath.UI.Vue` 下）；历史值：`git show 1eef596:MF_UI/MFMath.UI.Vue/src/lib/engine/viewConfigs.js \| Select-String '^  "[a-z-]+": \{'` 计 14 |
| 2 | [../DECISIONS.md](../DECISIONS.md) `:187` | "另有 24 个**参数表悬空**的模式名字单独登记（`:324`）" | 那 24 个是**重名模式**（`fn` 已被页面覆盖），登记表在 `check-ui.mjs:330`；真正"参数表悬空"的是另一回事：2 个 `ENGINE_VAR_SPECS` 键（`数值微分`、`矩阵乘法`，[../../MF_UI/BUGS.md](../../MF_UI/BUGS.md) `:760-764`） | `Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern 'DUPLICATE_NAME_GROUPS = '` → 330 |
| 3 | [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) `:72` | "415 个模式名 + **184 个**参数弹窗字段" | 模式名 415 对得上；弹窗字段这一项 `check-ui.mjs` 现在打印 **186 条唯一标签**（口径是否同一，我**没证实**） | `node tools/check-ui.mjs` → `i18n 弹窗字段 ：186 条唯一标签`；历史值见提交 `2e95d8e`（"184 条唯一标签"） |
| 4 | `MF_Mathematics/api_helpers.h:311-329` | 注释标题是"把 SymEngine 的机器话错误换成可操作的中文" | 实际只翻译"把 `=` 写进了不接受 `=` 的函数"这一种；其它异常**原样透传**，于是用户会看到英文的 `Not Implemented`（§1.6 第三行，本机实测） | `& probe_call.exe complex_eval '{"expr":"zeta(1+14.13*i)"}'` |

**另有一条口径提醒（不是债，是容易读错）**：`check-ui.mjs:202` 与 `:214` 的 `64` 是**历史**数字，当前实测为 0；引它时必须写成"首次跑时 64、现已 0"，否则会让人以为现在还有 64 个点不到的模式（[../DECISIONS.md](../DECISIONS.md) D-012 `:186` 就是这么写的）。
