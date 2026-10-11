# 输入层（INPUT）

> 本文说明输入层怎么把用户输入变成引擎能吃的参数：归一化与解析规则，以及前端参数构造。
> 与同层文档的分工：[`CONTRACT.md`](CONTRACT.md) 讲 args JSON 形状与键名契约；[`MODULES.md`](MODULES.md) 讲模块与 action 清单；[`SYMBOLIC.md`](SYMBOLIC.md) 讲归一化之后的符号层；[`../ui/ENGINE-BINDING.md`](../ui/ENGINE-BINDING.md) 讲前端 `ENGINE_MAP` / `calcArgs` 的接线。

## 1. 这一层由哪些文件构成

| 文件 | 职责 | 关键符号 |
| --- | --- | --- |
| `MF_Mathematics/math_input.h` | 字符级归一化：全角 / Unicode 数学符号 / LaTeX → 引擎语法；隐式乘法显式化；`√`、`|…|` 改写成函数；科学计数法展开 | `normalize`、`implicit_multiplication`、`equation_to_zero` |
| `MF_Mathematics/parser_lib.h` | 表达式解析与求值（递归下降 + 数值微分）；`parse()` 是唯一入口，内部先归一化 | `parse`、`eval`、`apply_function` |
| `MF_Mathematics/api_helpers.h` | 按参数键决定要不要归一化（`is_expression_key` 白名单），参数类型错误的中文文案 | `is_expression_key`、`get_string`、`get_keyword` |
| `MF_Mathematics/expr_api.cpp` | 把归一化/解析暴露成引擎 action | `to_engine_expr`、`prepare_expr`、`expr_eval*` |
| `MF_UI/MFMath.UI.Vue/src/lib/engine/calcArgs.js` | 前端构造 args 的唯一位置：分段 → 选参数 → 按类型转换 JSON | `splitSegments`、`buildEngineArgs`、`convertArg` |
| `MF_UI/MFMath.UI.React/src/plot/usePlotSampling.ts` | 绘图侧采样：调用 `expr_eval_vars_batch` / `expr_eval_grid` | `sampleAll` |

## 2. 一次计算里，谁负责哪一段

| 阶段 | 谁做 | 位置 | 输入 → 输出 |
| --- | --- | --- | --- |
| ① 分段 | 前端 | `splitSegments`（calcArgs.js） | `"x^2-4; -2; 2"` → `["x^2-4","-2","2"]` |
| ② 选参数 | 前端 | `pickTextArg`（calcArgs.js） | 段 → `args` 的键 |
| ③ 类型转换 | 前端 | `convertArg`（calcArgs.js） | 文本 → JSON 值 |
| ④ 传参 | 前端→引擎 | 宿主桥 | `{expr:"2*x", a:-2, b:2}` |
| ⑤ 按键决定是否归一化 | 引擎 | `get_string` + `is_expression_key`（api_helpers.h） | `expr` 键 → 归一化；`method` 键 → 原样 |
| ⑥ 归一化 | 引擎 | `normalize`（math_input.h） | `"2x"` → `"2*x"` |
| ⑦ 解析 | 引擎 | `parse`（parser_lib.h） | 规范化串 → `ExprNode` 树 |
| ⑧ 求值 | 引擎 | `eval`（parser_lib.h） | 树 + 变量 → 数值或中文错误 |

这条分界线的判据：

- 前端不做数学语义改写。`calcArgs.js` 的 `toEngineExpr` 是恒等函数（`return String(s)`）；语法归一化只发生在引擎一处。
- 引擎不做分段。`;` 是纯前端约定，引擎从头到尾不认识 `;`。
- 引擎按参数键决定是否归一化，而不是按「看起来像不像数学」。白名单在 `api_helpers.h` 的 `is_expression_key`（`expr`/`eq`/`f`/`g`/`func`/`seq`/`rule`/`body`/`series`/`expression` 等 21 个键）。

## 3. 前端负责的那一段：`args` 的构造

### 3.1 分段规则（`splitSegments`）

| 规则 | 说明 |
| --- | --- |
| 深度 0 的 `;` 或换行 → 分段 | `"x^2-4; -2; 2"` → `["x^2-4","-2","2"]` |
| `(` `[` `{` 内部的分号不分段 | `"f(a;b);c"` → `["f(a;b)","c"]` |
| 只去掉末尾空段；中间空段保留 | `"x;"` → `["x"]`；`"x;;y"` → `["x","","y"]` |
| 每段 `trim()` | `" -2 "` → `"-2"` |

### 3.2 六步分配（`buildEngineArgs` 自动映射路径）

| 步 | 做什么 |
| --- | --- |
| ① | 第一段给「那条表达式」参数（`pickTextArg`：先找必填 `string`，再找非 `string_array`/`complex_obj` 的参数） |
| ② | 剩下的段整组交给 `string_array` 参数 |
| ③ | 其余必填参数按声明顺序吃段；没段可得就记账 `missingRequired` |
| ④ | 还有剩段补给可选参数 |
| ⑤ | 仍缺的必填参数 → 弹窗字段 → 再不行按类型兜底并记账 |
| ⑥ | 其余可选参数 → 弹窗字段；没有就整个键省略，让引擎用默认值 |

### 3.3 类型转换（`convertArg`）

| 声明的 type | 转成什么 |
| --- | --- |
| `double` / `int` / `bool` | 数 / 截断整数 / 布尔 |
| `string_or_number` | 纯数字字面量 → 数；否则原样串 |
| `point` | 取第一个 `(…)` 组的前两个数 |
| `matrix` / `matrix_list` / `point_cloud` / `ll_matrix` / `pair_list` | 二维数组（JSON → 分号分行 → 逗号分词三级兜底） |
| `prob_table` | `{键: 数}`（`/[;,]\s*/` 分词 + `=` 取值） |
| `complex_obj` | `{维数: [[顶点…]]}` |
| `sig` / `double_array` / `int_array` / `double_list` / `int_list` | 数字数组 |
| `string_array` | 整串再分段 |
| 其它 | 原样串 |

两条设计：解析不出来时原样返回文本，让引擎抛它自己的中文参数错误；必填参数拿不到值时走 `fallbackOf` 并记账（`noteDefaulted`），调用点据此拦截。

## 4. 引擎负责的那一段：归一化（`math_input.h`）

`normalize` 的处理顺序有语义后果：

| 步 | 步骤 | 位置 |
| --- | --- | --- |
| 0 | 展开 `\operatorname{}` 等包装命令；丢掉 `\left \right \, \; \! \quad` | `unwrap_wrapper_commands` |
| 1 | LaTeX 命令 → 引擎语法（`\frac{a}{b}`→`((a)/(b))`、`\sqrt[n]{x}`→`((x)^(1/(n)))`、`\sin^{-1}`→`asin`）；剩余 `{}` 当圆括号 | `normalize` |
| 2 | 字符映射：全角 ASCII → 半角；`× · ⋅ ÷ −`；上标 `² ³ ¹ ⁰ ⁴…⁹`；`≤ ≥ ≠ ≡`；`π Π θ`；`∛`；`∞`→`oo`；`√`→`sqrt` | `map_codepoint` |
| 3 | 压缩空白 | `normalize` |
| 3.5 | 科学计数法 → 十进制字面量 | `scientific_notation_to_decimal` |
| 3.6 | `√x`→`sqrt(x)`、`|x|`→`abs(x)` | `sqrt_fences_to_function`、`abs_fences_to_function` |
| 4 | 隐式乘法显式化：函数名补括号、连写标识符切分、因子间补 `*`、`/` 后连写因子整体作分母 | `implicit_multiplication` |
| 兜底 | 输出里出现「裸函数名」→ 明确报错，不猜 | `require_calls_have_parens` |

关键设计：科学计数法必须在隐式乘法之前改写，否则 `1e-9` 会被读成 `1*e-9` = e − 9 ≈ −6.28（不报错的错答案）。

实测对照表（`probe_call.exe to_engine_expr`）：

| 输入 | 归一化结果 |
| --- | --- |
| `2x` | `2*x` |
| `sin x` | `sin(x)` |
| `sinxcosx` | `sin(x)*cos(x)` |
| `sin2x` | `sin(2*x)` |
| `1/2x` | `1/(2*x)` |
| `1/2(x+1)` | `1/(2*(x+1))` |
| `x^2y` | `x^2*y` |
| `x**2` | `x^2` |
| `\frac{1}{2}x` | `((1)/(2))*x` |
| `\sin^{-1} x` | `asin(x)` |
| `√2` | `sqrt(2)` |
| `|x|` | `abs(x)` |
| `∞` | `oo` |
| `πx` | `pi*x` |
| `（x＋1）` | `(x+1)` |
| `1e-9` | `0.000000001` |
| `x+sin` | 报错（函数 sin 后面缺少自变量） |

归一化的改写类别通过 `notes` 交给界面；`to_engine_expr` 与 `prepare_expr` 把它返回给前端。这两个接口用 `raw_expr_arg` 绕开 `get_string` 的归一化，否则 `changed`/`input` 恒为空或等于结果。

## 5. 引擎负责的那一段：解析（`parser_lib.h`）

| 事实 | 说明 |
| --- | --- |
| `parse()` 是所有解析路径的唯一入口 | 归一化在这里做，调用方不必各自预处理 |
| 递归下降 + 深度上限 512 | 深嵌套会把 C 栈打穿 |
| 幂算符 `**` 与 `^` 同义 | |
| 后缀 `!` → `factorial` | 限制非负整数、n ≤ 170 |
| 常量：`pi`/`PI`、`e`、`oo`/`inf`/`infinity` | |
| 函数别名归一：`tg`→`tan`、`ctg`→`cot`、`ln`→`log`、`lg`→`log10`、`arcsin`→`asin` | |
| 归一化认得、求值器没实现的函数（`gamma`/`zeta`/`erf`…） | 只在后随括号时拦下并报「不支持该函数」 |
| 求值期如实报错（定义域、除零、NaN） | `asin` 越界、`ln` ≤ 0、`sqrt` 负数都报中文原因 |

解析层不认识的字符（`,`、`;`、`>`、`<`、`=`）不是表达式语法，会落到「表达式后存在多余字符」。唯一的例外是方程：`get_equation`（api_helpers.h）先做字符归一化，再用 `equation_to_zero`（math_input.h）把 `左 = 右` 整理成 `(左) - (右)`；`is_equation` 把 `==`/`<=`/`>=`/`!=` 里的等号排除在方程之外。

`prepare_expr` 把「规范化串 + 校验结果 + LaTeX」一次返回，界面能在用户按键时就知道这串能不能解析。

## 6. `;` 的双重语义

`;` 是前端约定，引擎不认。同一串文本先被 `splitSegments` 按参数分隔切一次，剩下的片段又可能被 `matrixOf`/`probTableOf`/`complexObjOf` 再切一次。

| 谁 | 判据 | `;` 在这个语境里是 | 深度敏感 |
| --- | --- | --- | --- |
| `splitSegments` | `c === ";" || c === "\n"` | 多参数分隔符 | 是（`([{` 计数） |
| `probTableOf` | `/[;,]\s*/` | 概率表项分隔符 | 否 |
| `matrixOf` | `/[;\n]/` | 矩阵行分隔符 | 否（只在单段内部生效） |
| `complexObjOf` | 按竖线或 `;` 切分 | 复形单元分隔符 | 否 |

收口方式：`prob_table` 参数整串 join 回去（`segments.join(";")`），不让 `splitSegments` 先切；`string_array` 用剩余所有段 join。概率四模式（条件概率 / 独立性 / 全概率 / 贝叶斯）的弹窗默认值用 `;` 写表，构造器据此产出 `{"P":{"A_and_B":0.2,"B":0.5},"A":"A","B":"B"}` 这类正确形状。

## 7. 归一化会吃掉什么

| 现象 | 说明 |
| --- | --- |
| 纯小写多字母标识符会被拆成字母乘积 | `xy` → `x*y`、`lebesgue` → `l*e*b*e*s*g*u*e` |
| 含大写或数字的整词保留 | `XA`、`x2` 未变 |
| 关键词参数不能被归一化 | `product_measure` 传 `mu:"lebesgue"` → 正确；传 `mu:"l*e*b*e*s*g*u*e"` → 报「值不是数字」 |
| 同一键名在不同 action 里语义不同 | `random_variable` 的 `rule` 是关键词；`recurrence_sequence` 的 `rule` 是表达式 |
| 围道这类「带括号的关键词」要原样传 | `cauchy_theorem` 传 `contour:"circle(0+0i,1)"` → 正常；拆开后的串报「无法解析 contour」 |

因此含纯小写多字母的变量名 / 关键词不能交给归一化，必须走 `get_keyword` 或白名单之外的键。

## 8. 可复跑的验证命令

| 想验什么 | 命令 | 期望 |
| --- | --- | --- |
| 引擎函数总数 | `& 'MF_Mathematics\build\bin\Release\probe_call.exe' --list` | `count` = 424 |
| 归一化 | `& …\probe_call.exe to_engine_expr '{"expr":"2x"}'` | 见 §4 对照表 |
| 解析 + LaTeX + notes | `& …\probe_call.exe prepare_expr '{"expr":"cosx"}'` | `{input,normalized,changed,notes,ok,latex}` |
| 前端构造器 | `node --input-type=module -e "import {buildEngineArgs} from './MF_UI/MFMath.UI.Vue/src/lib/engine/calcArgs.js'; console.log(JSON.stringify(buildEngineArgs('条件概率','A_and_B=0.2; B=0.5')))"` | `{"P":{"A_and_B":0.2,"B":0.5},"A":"A","B":"B"}` |

一个探针陷阱：`probe_call` 的 JSON 走命令行 argv，非 ASCII 会在进程边界被按 ANSI 转码。测非 ASCII 必须写成 UTF-8 文件再用 `@路径`（`probe_call.cpp` 的读文件分支）。
