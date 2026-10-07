# 输入层：归一化与解析

> **本文只回答一个问题：输入层怎么把用户输入变成引擎能吃的参数（归一化与解析）？**
>
> 与同层其它文档的分工：
> - [CONTRACT.md](CONTRACT.md) —— args JSON 形状与**键名契约**；本文到"引擎收到什么键"为止，键名对不对由它管；
> - [MODULES.md](MODULES.md) —— 12 个学科模块与 424 个 action 的清单；本文只讲参数是怎么被组出来的；
> - [SYMBOLIC.md](SYMBOLIC.md) —— 归一化之后的符号层（SymEngine）；本文只到"归一化串交给两条解析路径"这一层；
> - [TESTS.md](TESTS.md) —— 19 个可执行目标与 CTest 用例；本文 §8 只列能直接复跑本文结论的那几条；
> - [../ui/ENGINE-BINDING.md](../ui/ENGINE-BINDING.md) —— 前端 `ENGINE_MAP` / `calcArgs` 的接线与可达性守门；本文讲的是它内部的两段职责划分。

**核对时间**：2026-10-07 10:46 · **核对方式**：`probe_call.exe`（`MF_Mathematics\build\bin\Release\`，本次已存在的 Release 产物）直调引擎 + Node v26.3.1 直调前端构造器（**没有起宿主、没有跑 CDP**，见 §10）。

---

## 1. 这一层由哪些文件构成

| 文件 | 行数 | 职责（一句话） | 关键位置 |
| --- | --- | --- | --- |
| [`math_input.h`](../../MF_Mathematics/math_input.h) | 1027 | **字符级归一化**：全角 / Unicode 数学符号 / LaTeX → 引擎语法；隐式乘法显式化；`√`、`\|…\|` 改写成函数；科学计数法展开 | `normalize` :267、`implicit_multiplication` :785 |
| [`parser_lib.h`](../../MF_Mathematics/parser_lib.h) | 702 | **表达式解析与求值**（递归下降 + 数值微分）；`parse()` 是唯一入口，内部先归一化 | `parse` :459、`Parser` :157 |
| [`api_helpers.h`](../../MF_Mathematics/api_helpers.h) | 358 | **按参数键决定要不要归一化**（`is_expression_key` 白名单），以及参数类型错误的中文文案 | `is_expression_key` :27、`get_string` :181 |
| [`expr_api.cpp`](../../MF_Mathematics/expr_api.cpp) | 297 | 把归一化/解析暴露成引擎 action：`to_engine_expr`、`prepare_expr`、`expr_eval*` | :237、:252 |
| [`calcArgs.js`](../../MF_UI/MFMath.UI.Vue/src/lib/engine/calcArgs.js) | 454 | **前端唯一构造 args 的地方**：分段 → 选参数 → 按类型转换 JSON | `splitSegments` :60、`buildEngineArgs` :262 |
| [`engineMapExtra.js`](../../MF_UI/MFMath.UI.Vue/src/lib/engine/engineMapExtra.js) | 533 | 模式声明（`fn` + `args` 键名/类型/必填性）+ 弹窗字段默认值 | :328、:500-509 |
| [`plotMath.js`](../../MF_UI/MFMath.UI.Vue/src/lib/plot/plotMath.js) | 246 | 绘图侧本地归一化：**只做全角与 `× ÷ −` 的字面替换**，不做语义改写 | `toEngineExpr` :40 |
| [`prepare.js`](../../MF_UI/MFMath.UI.Vue/src/lib/plot/prepare.js) | 97 | 绘图侧调引擎 `prepare_expr` / `to_engine_expr`，并决定"哪一段才归一化" | :65-98 |

```powershell
# 行数与规模（本节数字的复跑方式）
node -e "['MF_Mathematics/math_input.h','MF_Mathematics/parser_lib.h','MF_Mathematics/expr_api.cpp','MF_Mathematics/api_helpers.h','MF_UI/MFMath.UI.Vue/src/lib/engine/calcArgs.js'].forEach(f=>console.log(require('fs').readFileSync(f,'utf8').split('\n').length-1,f))"
node --input-type=module -e "import {ENGINE_MAP,ENGINE_VAR_SPECS} from './MF_UI/MFMath.UI.Vue/src/lib/engine/engineMap.js'; console.log(Object.keys(ENGINE_MAP).length, Object.keys(ENGINE_VAR_SPECS).length)"
& 'MF_Mathematics\build\bin\Release\probe_call.exe' --list   # count = 424
```

上面三条命令的实测输出：`ENGINE_MAP` **415** 个模式、`ENGINE_VAR_SPECS` **139** 个条目；`list_functions` 的 `count` **424**（与 [AGENTS.md](../../AGENTS.md) §2 的判据 424 一致）。

---

## 2. 一次计算里，谁负责哪一段

| 阶段 | 谁做 | 位置 | 输入 → 输出 |
| --- | --- | --- | --- |
| ① 分段 | 前端 | `splitSegments`，calcArgs.js:60 | `"x^2-4; -2; 2"` → `["x^2-4","-2","2"]` |
| ② 选参数 | 前端 | `pickTextArg`，calcArgs.js:242 | 段 → `args` 的键（"第一段是那条表达式"） |
| ③ 类型转换 | 前端 | `convertArg`，calcArgs.js:160 | 文本 → JSON 值（数组 / 对象 / 点 / 数 / 串） |
| ④ 传参 | 前端→引擎 | 宿主桥，args 是 JSON 对象 | `{expr:"2*x", a:-2, b:2}` |
| ⑤ 按键决定是否归一化 | 引擎 | `get_string`，api_helpers.h:181 + `is_expression_key` :27 | `expr` 键 → 归一化；`method` 键 → 原样 |
| ⑥ 归一化 | 引擎 | `normalize`，math_input.h:267 | `"2x"` → `"2*x"`，并给出 `notes` |
| ⑦ 解析 | 引擎 | `parse`，parser_lib.h:459 | 规范化串 → `ExprNode` 树 |
| ⑧ 求值 | 引擎 | `eval` / `apply_function`，parser_lib.h:552/473 | 树 + 变量 → 数值或中文错误 |

**这条分界线的判据（不要越界）**：

- 前端**不做数学语义改写**。`calcArgs.js:33-35` 的 `toEngineExpr` 现在是恒等函数（`return String(s)`），注释写明"语法归一化只发生在引擎里一处"；绘图侧 `plotMath.js:40-46` 只替换全角与 `× ÷ −` 三个符号，`plotMath.js:31-38` 记录了曾经因为本地插 `*` 与替换 `π` 造成的事故。
- 引擎**不做分段**。`;` 是纯前端约定：把 `x>1; x<3` 交给引擎，实测 `prepare_expr` 返回 `ok:false`、`error:"表达式后存在多余字符 (位置 1)"`（`expr_eval` 同）。也就是说**引擎从头到尾不认识 `;`**。
- 引擎**按参数键**决定是否归一化，而不是按"看起来像不像数学"。白名单在 `api_helpers.h:27-36`（`expr`/`eq`/`f`/`g`/`func`/`seq`/`rule`/`body`… 21 个键）。

---

## 3. 前端负责的那一段：`args` 的构造

### 3.1 分段规则（`;` 的第一种语义）

`splitSegments`（calcArgs.js:60-74）：

| 规则 | 实现位置 | 实测 |
| --- | --- | --- |
| 深度 0 的 `;` 或换行 → 分段 | :67 | `"x^2-4; -2; 2"` → `["x^2-4","-2","2"]` |
| `(` `[` `{` 内部的分号**不**分段 | :65-66 | `"f(a;b);c"` → `["f(a;b)","c"]`；`"[[1,2];[3,4]]"` → 一段 |
| 只去掉**末尾**空段；中间空段保留 | :72 | `"x;"` → `["x"]`；`"x;;y"` → `["x","","y"]`；`"x;\ny"` → `["x","","y"]`（⚠ 用户在 `;` 后按一次回车就会多出一个空段） |
| 每段 `trim()` | :71 | `" -2 "` → `"-2"` |
| 空串 → `[""]`（长度 1） | :70-73 | `splitSegments("")` → `[""]`（与 calcArgs.js:358-362 的注释说法不符，见 §9 债 2） |

### 3.2 六步分配（自动映射路径）

`buildEngineArgs`（calcArgs.js:262-336）按下面的顺序消费段落与弹窗字段：

| 步 | 做什么 | 位置 |
| --- | --- | --- |
| ① | 第一段给"那条表达式"参数（`pickTextArg(spec.args,{skipWholeString:true})`：先找必填 `string`，再找非 `string_array`/`complex_obj` 的参数） | :276-291 |
| ② | 剩下的段整组交给 `string_array` 参数（`join(";")` 后由 `convertArg` 再切） | :293-298 |
| ③ | 其余**必填**参数按声明顺序吃段；没段可得就记账 `missingRequired` | :300-305 |
| ④ | 还有剩段 → 补给**可选**参数（如 `"x^2-4; -2; 2"`） | :307-312 |
| ⑤ | 仍缺的必填参数 → 弹窗字段（跳过"（输入框）"类字段）→ 再不行按类型兜底并记账 | :314-327 |
| ⑥ | 其余可选参数 → 弹窗字段；**没有就整个键省略**，让引擎用默认值 | :329-334 |

> ⚠ 顺序不能按"声明顺序一把梭"：`定积分` 的 `args` 是 `[var(opt), a(opt), b(opt), expr(必填)]`，若按声明顺序给第一段，用户写的被积函数会被当成积分变量。所以 ① 先挑必填表达式参数（calcArgs.js:272-275 的注释，实测 `buildEngineArgs("定积分","x^2")` → `{expr:"x^2",var:"x",a:0,b:1}`）。

### 3.3 类型转换（`convertArg`，calcArgs.js:160-190）

| 声明的 type | 转成什么 | 位置 |
| --- | --- | --- |
| `double` / `int` / `bool` | 数 / 截断整数 / 布尔（`true`/`1`/`是`） | :163-165 |
| `string_or_number` | 纯数字字面量 → 数；否则原样串 | :166 |
| `point` | 取第一个 `(…)` 组的前两个数 | :167、:149-153 |
| `matrix` / `matrix_list` / `point_cloud` / `ll_matrix` / `pair_list` | 二维数组（`JSON` → `;` 分行 → 逗号分词三级兜底） | :169-181、:89-115 |
| `prob_table` | `{键: 数}`（`/[;,]\s*/` 分词 + `=` 取值） | :172、:136-146 |
| `complex_obj` | `{维数: [[顶点…]]}` | :173、:122-134 |
| `sig` / `double_array` / `int_array` / `double_list` / `int_list` | 数字数组 | :184-186 |
| `string_array` | **整串再分段** | :187 |
| 其它 | 原样串 | :188 |

两条**必须记住**的设计（都是踩过坑之后写的）：

- 解析不出来时**原样返回文本**，让引擎抛它自己的中文参数错误（:156-159）；静默塞 `0/1` 才是难查的失败。
- 必填参数拿不到值时走 `fallbackOf`（:200-207）**并记账**（`noteDefaulted` :218-221）；这些兜底值在引擎眼里都是合法值，所以调用点必须自己拦 —— `CalcView.vue:288-299` 就是这么做的（缺参数就不调引擎）。详见 [../../MF_UI/BUGS.md](../../MF_UI/BUGS.md) B4。

### 3.4 弹窗路径（`buildEngineArgsFromValues`，calcArgs.js:352-443）

弹窗第一个格子是输入框的镜像，因此**同样可以写 `;` 分段**（:354-357）。与自动映射路径的三处差异：

| 差异 | 位置 | 说明 |
| --- | --- | --- |
| 先按 `seg` 推进 `ui`（弹窗字段要跳过几格） | :402 | 段填过的参数不能再被字段填一次 |
| 概率表整串吃掉时 `ui` 必须回 0 | :368-372、:379-386 | 表没有"填掉若干个参数"，回 0 才对得上 |
| 输入框空时用**第 0 格自己的默认值** | :409-426 | 如乘积测度第 0 格默认 `lebesgue`；空了才走兜底 |

---

## 4. 引擎负责的那一段：归一化（`math_input.h`）

`normalize` 的处理顺序**有语义后果**，不能换（:264-266 的说明）：

| # | 步骤 | 位置 | 为什么要这个顺序 |
| --- | --- | --- | --- |
| 0 | 展开 `\operatorname{}` 等包装命令；丢掉 `\left \right \, \; \! \quad` | :141-171、:269-284 | 包装命令可能嵌在 `\frac{}` 的参数里，参数是整段取出的 |
| 1 | LaTeX 命令 → 引擎语法（`\frac{a}{b}`→`((a)/(b))`、`\sqrt[n]{x}`→`((x)^(1/(n)))`、`\sin^{-1}`→`asin`、`\cdot`→`*`…）；剩余 `{}` 当圆括号 | :286-442 | 先还原 LaTeX，花括号才能当分组用 |
| 2 | 字符映射：全角 ASCII（U+FF01..FF5E）→ 半角；`× · ⋅ ÷ −`；上标 `² ³ ¹ ⁰ ⁴…⁹`；`≤ ≥ ≠ ≡`；`π Π θ`；`∛`；`∞`→`oo`；`√`→`sqrt` | :444-478、:77-120 | 全部记录进 `notes` |
| 3 | 压缩空白（连续空白→一个空格，去首尾） | :480-497 | 只为好读，不改语义 |
| 3.5 | 科学计数法 → 十进制字面量 | :499-508、:188-259 | `1e-9` 若留到第 4 步会被读成 `e−9 ≈ −6.28`（**不报错的错答案**） |
| 3.6 | `√x`→`sqrt(x)`、`\|x\|`→`abs(x)` | :510-519、:569-615 | 引擎自己的解析器认得 `√` 与 `\|…\|`，SymEngine 不认 → 同一串"绘图能画、求导报 syntax error" |
| 4 | 隐式乘法显式化：函数名补括号、连写标识符切分、因子间补 `*`、`/` 后连写因子整体作分母 | :521-532、:785-968 | SymEngine 只认显式 `*` |
| 兜底 | 输出里出现"裸函数名"→ **明确报错**，不猜 | :737-755 | `sin x`、`8x sin x` 里的 `sin` 曾经被 SymEngine 当变量 |

**实测对照表**（`probe_call.exe to_engine_expr`，见 §8 的复跑方式）：

| 输入 | 归一化结果 | 备注 |
| --- | --- | --- |
| `2x` | `2*x` | |
| `sin x` | `sin(x)` | 函数名一律补全括号 |
| `sinxcosx` | `sin(x)*cos(x)` | 连写按"最长函数名前缀 + 单字母变量"切 |
| `sin2x` | `sin(2*x)` | |
| `1/2x` | `1/(2*x)` | 教材分数条写法；`expr_eval_vars` 在 x=4 得 **0.125** |
| `1/2(x+1)` | `1/(2*(x+1))` | x=4 得 **0.1** |
| `1/2π` | `1/(2*pi)` | |
| `x^2y` | `x^2*y` | 幂之后紧跟因子 |
| `x**2` | `x^2` | `**` 与 `^` 合并成一个算符 |
| `\frac{1}{2}x` | `((1)/(2))*x` | |
| `\sqrt[3]{x}` | `((x)^(1/(3)))` | |
| `\sin^{-1} x` | `asin(x)` | 反函数整体识别，不是 `(sin x)⁻¹` |
| `√2` | `sqrt(2)` | |
| `\|x\|` | `abs(x)` | |
| `∞` | `oo` | 引擎与 SymEngine 都认 `oo` |
| `πx` | `pi*x` | x=2 时 `expr_eval_vars` = 2π = **6.283185307179586** |
| `x²+θ` | `x^2+theta` | |
| `（x＋1）` | `(x+1)` | 全角 |
| `1e-9` | `0.000000001` | 纯字符串平移，不经过 double |
| `x+sin` | **isError**：`函数 sin 后面缺少自变量（写 sin x 或 sin(x)）` | 报错而不是猜 |

归一化的改写类别会通过 `notes` 交给界面（`math_input.h:14-15`），`expr_api.cpp:237-247` 的 `to_engine_expr` 与 :252-273 的 `prepare_expr` 把它返回给前端；`prepare.js:4-11` 用它做实时预览（"你输入的被这样理解了"）。注意 `expr_api.cpp:34-55` 的 `raw_expr_arg`：这两个接口必须绕开 `get_string` 的归一化（api_helpers.h:184），否则 `changed`/`input` 恒为空/等于结果。

---

## 5. 引擎负责的那一段：解析（`parser_lib.h`）

| 事实 | 位置 | 说明 |
| --- | --- | --- |
| `parse()` 是**所有解析路径的唯一入口** | :459-469 | 归一化在这里做，调用方不必各自预处理 |
| 归一化结果必须存进具名变量 | :463-466 | `Parser` 持有 `const std::string&`；传 `normalize(s).text` 的临时对象会悬垂（实测表现为"空表达式"） |
| 递归下降 + 深度上限 512 | :170-193 | 五万层括号能把 C 栈打穿（SEH，`catch(...)` 抓不到，进程直接消失） |
| 幂算符 `**` 与 `^` 同义 | :270-283 | |
| 后缀 `!` → `factorial` | :285-296 | `expr_eval("5!")` = **120**（同处 :473-484 限制非负整数、n ≤ 170） |
| `\|x\|` 与 `√x` 在解析层也认 | :308-326 | `√` 的首字节判定必须转 `unsigned char`（:319-322 记录了符号扩展漏判） |
| 常量：`pi`/`PI`、`e`、`oo`/`inf`/`infinity` | :142-152 | |
| 函数别名归一：`tg`→`tan`、`ctg`→`cot`、`ln`→`log`、`lg`→`log10`、`arcsin`→`asin` | :90-129 | |
| 归一化认得、求值器没实现的函数（`gamma`/`zeta`/`erf`…） | :408-425 | 只在**后随括号**时拦下并报"不支持该函数"，裸用当变量，不误伤 |
| 求值期如实报错（定义域、除零、NaN） | :493-509、:527-542、:570-572；expr_api.cpp:96-101 | `asin` 越界、`ln` ≤ 0、`sqrt` 负数都报中文原因 |

**解析层不认识的字符**：`,`、`;`、`>`、`<`、`=` 都不是表达式语法，会落到 `throw_err("表达式后存在多余字符")`（:166）。唯一的例外是**方程**：`normalize_equation_arg`（api_helpers.h:227-232）先做字符归一化，再用 `equation_to_zero`（math_input.h:993-1025）把 `左 = 右` 整理成 `(左) - (右)`；`is_equation`（:980-991）把 `==`/`<=`/`>=`/`!=` 里的等号排除在方程之外。只有语义上就是方程的函数才该走 `get_equation`（api_helpers.h:218-225）。

`prepare_expr` 会把"规范化串 + 校验结果 + LaTeX"一次返回（expr_api.cpp:252-273），所以界面能在用户按键时就知道这串能不能解析。

---

## 6. `;` 的两种互斥语义（本文重点）

### 6.1 同一个字符，四处不同的读法

| 谁 | 位置 | 判据 | `;` 在这个语境里是 | 深度敏感 |
| --- | --- | --- | --- | --- |
| `splitSegments` | calcArgs.js:60-74（切分在 :67） | `c === ";" \|\| c === "\n"` | **多参数分隔符** | **是**（`([{` 计数） |
| `probTableOf` | calcArgs.js:136-146（切分在 :138） | `/[;,]\s*/` | **概率表项分隔符** | 否 |
| `matrixOf` | calcArgs.js:89-101（切分在 :97） | `/[;\n]/` | 矩阵**行**分隔符 | 否（只在单段内部生效） |
| `complexObjOf` | calcArgs.js:122-134（切分在 :126） | 按竖线或 `;` 切分（正则见该行） | 复形单元分隔符 | 否 |
| `prepare.js` 的绘图归一化 | prepare.js:80、:94 | `key.split(";")` | 参数分段（**只归一化第一段**） | 否 |
| 引擎 | —— | 无 | **完全不认识 `;`** | —— |

实测（Node 直调 `calcArgs.js`）：

```
splitSegments('1,2; 3,4')            => ["1,2","3,4"]        ← 语义 A：被切成两段
convertArg('matrix','1,2; 3,4')      => [[1,2],[3,4]]        ← 语义 C：这里是"行分隔"
convertArg('prob_table','A=1, B=2')  => {"A":1,"B":2}        ← 语义 B：逗号也算表项分隔
convertArg('complex_obj','3:1,2|4:3')=> {"3":[[1,2]],"4":[[3]]}
```

即：**同一串文本，先被语义 A 切一次，剩下的片段又可能被 B/C/D 再切一次**。这就是冲突的来源。

### 6.2 曾经造成什么后果（修复前）

概率四模式的参数是 `prob_table`。修复前 `convertArg` 的 `prob_table` 分支**只拿到一段**，而产品自带的默认示例恰好是用 `;` 写的表：

```
engineMapExtra.js:500  「条件概率」第 0 格默认值 = "A_and_B=0.2; B=0.5"
engineMapExtra.js:501  「独立性」  第 0 格默认值 = "A_and_B=0.12; A=0.3; B=0.4"
```

于是"打开弹窗、什么都不改、直接点计算"就走进冲突：整串先按语义 A 切成两段，只有第一段进了 `P`。我复跑了那个关键一步（当前代码里 `convertArg` 的行为没变，变的只是调用它的地方）：

```powershell
node --input-type=module -e "import {convertArg} from './MF_UI/MFMath.UI.Vue/src/lib/engine/calcArgs.js'; console.log(JSON.stringify(convertArg('prob_table','A_and_B=0.2')))"
# => {"A_and_B":0.2}          ← B=0.5 整条丢失
```

[../../MF_UI/BUGS.md](../../MF_UI/BUGS.md) B2① 记录了修复前的完整形状（`{"P":{"A_and_B":0.2},"A":"B=0.5","B":"A"}`：表丢一半、`A` 被塞进字符串 `"B=0.5"`、`B` 变成 `"A"`）。我把这个形状**直接喂给引擎**，得到的是报错而不是错值：

| 传给引擎的 args | 引擎返回 |
| --- | --- |
| `{"P":{"A_and_B":0.2},"A":"B=0.5","B":"A"}` → `conditional_probability` | `isError:true`，`"缺少 P(B) 的值"`（probability_api.cpp:130） |
| `{"events":{"A1":0.5,"A2":0.5},"P":{},"condition":"B"}` → `total_probability` | `isError:true`，`"缺少条件概率 P(B\|A1)"`（probability_api.cpp:161） |

> 口径更正：[../../MF_UI/BUGS.md](../../MF_UI/BUGS.md) B2 的现象写成"得到的是错的结果"；按引擎实测，这四个默认示例的形状都是**报错**（文案如上），不是静默错值。归类见 §9 债 4。

B2 还有第二个独立成因：`全概率公式`/`贝叶斯公式` 的弹窗第 2 格原本是"完备事件组（逗号分隔）"，却被赋给声明为 `prob_table` 的 `P`，`probTableOf("A1,A2")` 找不到 `=` → `P` 恒为 `{}`（engineMapExtra.js:502-507 的注释记录了这段）。

### 6.3 现在怎么收口

| # | 措施 | 位置 | 判据 |
| --- | --- | --- | --- |
| 1 | `prob_table` 参数**整串 join 回去**（`segments.join(";")`），不让语义 A 先切 | calcArgs.js:284-291（自动映射）、:375-387（弹窗） | `textArg.type === "prob_table"` |
| 2 | 概率表吃掉整串时**不推进弹窗字段游标**（`tableTookAll` → `ui = 0`） | :368-372、:402 | 否则字段队列整体错位一格 |
| 3 | `string_array` 用**剩余所有段** join（对称做法） | :293-298、:187 | 修复 B2③：`x>1; x<3` 不再只剩第一条 |
| 4 | `pickTextArg` 的 `skipWholeString` 分支**不退回 `args[0]`** | :242-252 | 唯一参数是 `string_array` 时（`解不等式/组`）整串才不会被交给"只吃第一段"的逻辑 |
| 5 | 弹窗字段与 args **语义对齐**成"两张分开的表" | engineMapExtra.js:502-509 | 先验表 → `events`，条件概率表 → `P` |
| 6 | 自检守卫「**概率表契约**」用**弹窗自带默认值**跑真构造器，断言每个 `prob_table` 参数非空 | tools/check-ui.mjs:298-319 | 守卫已**验证会失败**（BUGS.md §0.1 B2 行） |

收口后的实测（Node 直调构造器）：

| 模式 | 弹窗默认值 | 构造出的 args |
| --- | --- | --- |
| 条件概率 | `["A_and_B=0.2; B=0.5","A","B"]` | `{"P":{"A_and_B":0.2,"B":0.5},"A":"A","B":"B"}` |
| 独立性 | `["A_and_B=0.12; A=0.3; B=0.4","A","B"]` | `{"P":{"A_and_B":0.12,"A":0.3,"B":0.4},"A":"A","B":"B"}` |
| 全概率公式 | `["A1=0.5; A2=0.5","B\|A1=0.1; B\|A2=0.2","B"]` | `{"events":{"A1":0.5,"A2":0.5},"P":{"B\|A1":0.1,"B\|A2":0.2},"condition":"B"}` |
| 贝叶斯公式 | 同上 | `{…,"evidence":"B"}` |

把这些 args 直接送进引擎（`probe_call.exe`）：

| 引擎 action | 返回 | 手算核对 |
| --- | --- | --- |
| `conditional_probability` | `0.4` | 0.2 / 0.5 ✓ |
| `is_independent` | `true` | 0.12 = 0.3 × 0.4 ✓ |
| `total_probability` | `0.15000000000000002` | 0.5×0.1 + 0.5×0.2 ✓ |
| `bayes_theorem` | `{"A1":0.3333333333333333,"A2":0.6666666666666666}` | (0.5×0.1)/0.15、0.1/0.15 ✓ |

**结论**：`;` 的双语义冲突是在**前端**收口的（表类参数先 join、字符串数组整组给），引擎侧一行没改 —— 因为引擎根本不认识 `;`。这也是为什么收口只能靠"哪个 type 该吃掉整串"这张约定表，而不是靠引擎容错。

### 6.4 仍然没收口的一条

`engineMapExtra.js:328-332` 把概率四模式的参数**全部**声明成 `opt:true`，而引擎签名表说它们全是必填：

| action | `engine-signatures.json` 的 `required` / `optional` | `engineMapExtra.js` 的声明 |
| --- | --- | --- |
| `conditional_probability` | `["A","B","P"]` / `[]` | 三个都 `opt:true`（:328） |
| `is_independent` | `["A","B","P"]` / `[]` | 三个都 `opt:true`（:329） |
| `total_probability` | `["condition","events","P"]` / `[]` | 三个都 `opt:true`（:331） |
| `bayes_theorem` | `["evidence","events","P"]` / `[]` | 三个都 `opt:true`（:332） |

后果有两个，都还没修：

1. `pickTextArg` 因此选不到"必填 `string`"，只能退到"第一个不是 `string_array`/`complex_obj` 的参数"（calcArgs.js:246-250）—— 现在是靠这条兜底规则歪打正着地选中了 `P`/`events`，不是靠 `opt` 的正确性。
2. `opt:true` 让这些参数不会进入 `report.defaulted`，于是 B4 的"缺必填参数就拒绝计算"（CalcView.vue:288-299）对它们**不生效**：用户把概率表清空，界面不会拦，一路交给引擎报"缺少条件概率 P(B|A1)"。这不违反"不编造结果"（引擎确实报了错），但少了前置提示。[../../MF_UI/BUGS.md](../../MF_UI/BUGS.md) B2 的"建议修法"已经点名要对齐 `opt` 与引擎 `required`，至今未做。

---

## 7. 归一化会吃掉什么（写输入时要知道的边界）

| 现象 | 实测 | 位置 |
| --- | --- | --- |
| **纯小写多字母标识符会被拆成字母乘积** | `to_engine_expr("xy")` → `x*y`；`("ab")` → `a*b`；`("lebesgue")` → `l*e*b*e*s*g*u*e` | math_input.h:680-730（切词）；:697-703 只对"含大写或数字"的整词放行 |
| 含大写或数字的整词保留 | `("XA")` → `XA`；`("x2")` → `x2`（未变） | 同上 |
| 关键词参数**绝不能**被归一化 | `product_measure` 传 `mu:"lebesgue"` → `2`；传 `mu:"l*e*b*e*s*g*u*e"` → `isError:"值不是数字"` | `is_expression_key` 白名单 api_helpers.h:27-36；`get_keyword` :195-216 |
| 同一键名在不同 action 里语义不同 | `random_variable` 的 `rule` 是关键词（`"square"` 实测正常）；`recurrence_sequence` 的 `rule` 才是表达式 | api_helpers.h:195-205 |
| 绘图侧只归一化**第一段** | `"x^2; 1; 1e-6; central"` 只处理第一段，后面原样透传 | prepare.js:68-94 |
| 围道这类"带括号的关键词"要原样传 | `cauchy_theorem` 传 `contour:"circle(0+0i,1)"` → 正常出结果；传拆开后的 `"c*i*r*c*l*e*(0+0*i,1)"` → `isError:"无法解析 contour: …"` | 见 §9 债 3 |

---

## 8. 可复跑的验证命令

| 想验什么 | 命令 | 期望 |
| --- | --- | --- |
| 引擎函数总数 | `& 'MF_Mathematics\build\bin\Release\probe_call.exe' --list` | `count` = **424** |
| 归一化 | `& …\probe_call.exe to_engine_expr '@<json文件>'` | 见 §4 对照表 |
| 解析 + LaTeX + notes | `& …\probe_call.exe prepare_expr '@<json文件>'` | `{input,normalized,changed,notes,ok,latex}` |
| 归一化的**语义不变性** | `node MF_UI/MFMath.UI.Vue/tests/cdp-expr-normalize.mjs`（**需宿主 + `--remote-debugging-port=9222`**） | 界面侧的 `__mfToEngineExpr` 必须不改字面、且归一化前后同值（用例 :59-101；结果 `RESULT\|cdp-expr-normalize\|26\|0` 记于 [../../MF_UI/BUGS.md](../../MF_UI/BUGS.md) §0.2） |
| 全 415 模式的参数构造 + 真引擎 | `node MF_UI/MFMath.UI.Vue/tests/audit-modes.mjs` | `RESULT\|audit-modes\|393\|0`（BUGS.md §0.2；不需宿主，每模式一个 `probe_call` 进程） |
| 前端构造器逐条复算 | `node --input-type=module -e "import {buildEngineArgs} from './MF_UI/MFMath.UI.Vue/src/lib/engine/calcArgs.js'; console.log(JSON.stringify(buildEngineArgs('条件概率','A_and_B=0.2; B=0.5')))"` | `{"P":{"A_and_B":0.2,"B":0.5},"A":"A","B":"B"}` |
| 概率表契约守卫 | `npm run check --prefix MF_UI/MFMath.UI.Vue` → check-ui 的「概率表契约」行（判据见 tools/check-ui.mjs:298-319） | 本轮**没跑** `npm run check`；我按同一判据用 Node 复算（弹窗自带默认值 → 真构造器），得 **4 个模式 / 空表 0 个** |

⚠ **一个探针陷阱**：`probe_call` 的 JSON 走命令行 argv，非 ASCII 会在进程边界被按 ANSI 转码（实测命令行传 `{"expr":"√2"}`，到达引擎时已是 `¡Ì2`，结果 `changed:false`）。测非 ASCII 必须写成 UTF-8 文件再用 `@路径`（`probe_call.cpp:65-84` 的读文件分支就是为这个加的）。

---

## 9. 已知的文档债

| # | 位置 | 注释/文档说 | 代码/实测做 |
| --- | --- | --- | --- |
| 1 | math_input.h:549（判据实现在 :960-961） | `数字与数字之间（"2 3" 视为笔误，不做乘法）` | 确实不补 `*`，但两个数字字面量因此**被粘连成一个数**：`to_engine_expr("2 3")` → `23`、`("12 34")` → `1234`、`("2.5 3")` → `2.53`、`("1 2+3")` → `12+3`；`expr_eval("2 3")` = **23**。路径是 :961 不补 `*` + 第 ⑤ 步直接拼串（:950-965）→ 无分隔符即合并。⚠ 这是**静默错值**，不是报错，与"不编造结果"的纪律相冲突；BUGS.md / OPEN-ITEMS.md 里均无登记（`grep 笔误` 只命中源码注释） |
| 2 | calcArgs.js:358-362 | "`splitSegments("")` 返回的是**空数组**，于是 `segments.length === 1 && segments[0] === ""` 恒为 false" | 实测 `splitSegments("")` → `[""]`（长度 1、`[0] === ""`）：判据"恒为 false"不成立。`boxText.trim() === ""`（:363）这个**结论**是对的，理由写错了 |
| 3 | engineMapExtra.js:491-494 | "走输入框时，整串会经引擎的 `to_engine_expr` 补隐式乘号 → `circle(0+0i,1)` 被拆成 `c*i*r*c*l*e*(0+0*i,1)`" | 现在前端不做这个改写（calcArgs.js:33-35 恒等；绘图侧按段处理，prepare.js:80-94），且 `contour` 不在 `is_expression_key` 白名单里。实测引擎对 `contour:"circle(0+0i,1)"` 正常出结果，只有**已经拆开**的串才报 `无法解析 contour`。该注释描述的是 2026-09 之前的行为 |
| 4 | MF_UI/BUGS.md B2 | 概率四模式"弹窗自带的默认示例直接点计算就是错的"、"得到的是错的结果" | 按引擎实测是**报错**（`缺少 P(B) 的值` / `缺少条件概率 P(B\|A1)`），不是静默错值。措辞不精确，结论（必须修）不受影响 |
| 5 | calcArgs.js:307-312 vs :329-334 | ④"剩余段补给可选参数"、⑥"其余可选参数 → 弹窗字段" | 自动映射路径里，④ 吃掉的段**不会**跳过 ⑥ 的字段队列：`buildEngineArgs("定积分","x^2; 0; 1")` → `{"expr":"x^2","var":"0","a":1,"b":"x"}`（`b` 拿到了本该给"积分变量"的默认值 `"x"`），而弹窗路径同一输入 → `b:1`。两条路径对同一输入不一致。**当前界面够不到自动映射那条**（`needsVarDialog("定积分")` 为真 → CalcView.vue:276 走弹窗），所以分类是"构件级缺陷、界面不可达"，未登记在 BUGS.md |
| 6 | MF_UI/BUGS.md:380-382 | 建议"把 `opt` 与引擎 `required` 对齐" | engineMapExtra.js:328-332 仍是三个 `opt:true`（引擎签名 required 全含），后果见 §6.4 |
| 7 | parser_lib.h:7 | "支持 …函数 sin cos tan sqrt log exp" | `apply_function`（:473-549）实现的远不止这 6 个（含反三角、双曲、`floor/ceil/round/sign/factorial` 等）。列举行过时，不影响行为 |
| 8 | math_input.h:550 | "`xy` 这种连写（引擎把多字母标识符当作一个变量名，**维持原样**）" | 实测**不保留**：`to_engine_expr("xy")` → `x*y`、`("ab")` → `a*b`。切词逻辑（:680-730）只对"含大写或数字"的整词早退放行（:697-703）；含大写/数字的确实保留（`XA`、`x2` 未变）。所以用户**不能**把 `ab`、`lebesgue` 这类纯小写多字母名当变量/关键词交给归一化 |

---

## 10. 未证实 / 本轮没做的验证

| 项 | 状态 | 要怎么才能证实 |
| --- | --- | --- |
| 宿主机上的真实表现（CDP 端到端） | **未跑**。本轮宿主未启动，所有"实测"都是 `probe_call.exe` 直调引擎 + Node 直调前端构造器 | 起宿主后跑 `tests/run-all.ps1 -NoLaunch`（判据见 [../../MFMath.Host.Rust/docs/ACCEPTANCE.md](../../MFMath.Host.Rust/docs/ACCEPTANCE.md)），重点看 `cdp-expr-normalize` / `cdp-modes-render` / `audit-modes` |
| §9 债 1（`2 3` → `23`）在界面上是否可达 | **未验证**。构件级确定（引擎实测），但没在 UI 上点过 | 计算页输入框写 `2 3` 点计算，看结果是 23 还是报错 |
| SymEngine 路径对全部 415 模式的归一化覆盖 | **未做全量**。只抽验了 `simplify_sym`（`2x+2x`→`4*x`、`\frac{1}{2}x + x`→`(3/2)*x`、`\sqrt{x^2}`→`sqrt(x**2)`）与 `solve_quadratic`（`x^2-4`→`["2","-2"]`） | 跑 `audit-modes`（它同时覆盖符号与数值 action），或对 `symbolic_*` 家族逐个 `probe_call` |
| §9 债 5 是否还影响其它模式 | **未穷举**。只定位到 `定积分` 这一例（可选参数排在必填之前 + 有弹窗字段 + 用户多写段） | 用 `engineMapExtra.js`/`engineMap.js` 扫"含 opt 参数且含 VAR_SPECS"的模式，逐个比 `buildEngineArgs` 与 `buildEngineArgsFromValues` 的输出 |
| `notes` 在界面上的逐条呈现 | **未验证**。只核到 `prepare_expr` 会返回 `notes`、`prepare.js:26-41` 会接收 | 起宿主看 2D 绘图页输入 `cosx` 时的提示行 |
