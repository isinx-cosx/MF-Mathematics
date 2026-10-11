# 引擎调用契约（CONTRACT）

> 本文说明怎么调用引擎：参数如何传、键名如何对齐、缺参数与类型不符会怎样、错误与「未实现」返回什么。
> 构建目标与 C ABI 导出见 [`README.md`](README.md)，各模块 action 清单见 [`MODULES.md`](MODULES.md)，输入层归一化与解析见 [`INPUT.md`](INPUT.md)，能力边界见 [`BOUNDARIES.md`](BOUNDARIES.md)。
> 本文的命令行实测结果直接反映前端通过宿主桥调用引擎时看到的行为。

## 1. 两个 C ABI

引擎对外只有两个 C ABI，声明在 [`../../MF_Mathematics/api.h`](../../MF_Mathematics/api.h)：

| C 符号 | 签名 | 说明 |
| --- | --- | --- |
| `function_exists` | `bool function_exists(const char* function_name)` | 名字存在返回 `true`；`nullptr` 返回 `false` |
| `math_call` | `int math_call(const char* name, const char* args_json, char* out_buffer, int out_size)` | 成功返回写入字节数（不含结尾 `'\0'`）；失败或缓冲不足返回 `-1` |

示例（在 `MF_Mathematics\build\bin\Release` 下执行 `probe_call.exe`）：

```text
math_call("diff_at", {"expr":"x^2","point":1})  →  {"isError":false,"value":2}
math_call("diff_at", {"expr":"x^2"})            →  {"isError":true,"value":"缺少必填参数 point（应为数字）。本次调用传入的参数键：expr"}
math_call("no_such_action_xyz", {})             →  {"isError":true,"value":"未找到函数: no_such_action_xyz"}
```

## 2. 参数与返回的信封

### 2.1 信封的两个键

`result_ok` / `result_err` 各构造一个二键对象（[`../../MF_Mathematics/api_helpers.h`](../../MF_Mathematics/api_helpers.h) 的 `result_ok` / `result_err`）。顶层键恰为 `isError` 与 `value`，没有第三个。

| 情形 | `isError` | `value` 的 JSON 类型 |
| --- | --- | --- |
| 正常结果 | `false` | 数字 / 字符串 / 数组 / 对象，由 action 决定 |
| 算不出来（非初等积分等） | `false` | 字符串 `"未实现"` |
| 参数缺失 / 类型不符 / 解析失败 | `true` | 字符串（中文原因） |
| 函数名不存在 | `true` | 字符串 `"未找到函数: <name>"` |

`isError:false` 不等于「这是你要的答案」：`"未实现"` 与 `0` 都是 `isError:false`。判「调用成功」看 `isError`，判「结果可用」还要看 `value` 是否是占位文本。

### 2.2 `math_call` 的返回值

| 返回 | 含义 |
| --- | --- |
| `> 0` | 写入的字节数，`out_buffer` 里是以 `'\0'` 结尾的完整 JSON |
| `-1` | 空指针 / `out_size <= 0` / 结果装不下（`result.size()+1 > out_size`） |
| 函数名不存在 | 不返回 `-1`，而是返回 `isError:true` 的信封 |

缓冲不足是调用方行为，与引擎自己的上限是两回事：`probe_call` 自带 4 MiB 缓冲（[`../../MF_Mathematics/tests/probe_call.cpp`](../../MF_Mathematics/tests/probe_call.cpp)），给它一个超过该容量的结果就会返回 `-1`；而超点数上限（如 `complex_grid` 的 `nx*ny > 400000`）是引擎在信封里返回中文报错。两者不能混为一类。

### 2.3 `args_json` 不是对象时

取值器的第一道判断是 `!args.is_object() || !args.has(key)`，于是非对象参数被归为「缺参数」，错误信息里会写「参数不是 JSON 对象」。参数 JSON 解析失败（如 `{"expr":` 这种截断输入）则抛 `std::runtime_error`（前缀 `"JSON 解析错误: "`，见 [`../../MF_Mathematics/json.hpp`](../../MF_Mathematics/json.hpp) 的 `err()`），被 `make_handler` 转成 `result_err`。

## 3. 键名契约

| 规则 | 行为 |
| --- | --- |
| 键名 = 参数名，逐字匹配，区分大小写 | 取值器一律 `args[key]` 直取 |
| 必填没传 | 「缺少必填参数」，并列出本次实际传入的键 |
| 可选没传 | 用引擎自己的缺省值 |
| 键名写错 | 按「没传」处理；必填的写错会报错并列出实际传的键 |
| 多余的键 | 被忽略，不报错 |

「键名写错按没传处理」与「多余键被忽略」合起来是静默错值的来源：写错的键若恰好是可选参数，不会收到任何提示，只会拿到用缺省值算出来的结果。

### 3.1 表达式键与关键字键

`get_string` 按键名判断「这个参数是不是用户写的数学表达式」：命中 `is_expression_key`（[`../../MF_Mathematics/api_helpers.h`](../../MF_Mathematics/api_helpers.h)，共 21 个键名：`expr` `eq` `f` `g` `f_n` `func` `x_expr` `y_expr` `g_expr` `expr1` `expr2` `compare_expr` `seq` `seq_expr` `rule` `phi` `series` `body` `expression` `ex` `ey`）就先做隐式乘法 / LaTeX 归一化，否则原样取值。例如 `diff_at` 收到 `{"expr":"2x"}` 时，`2x` 被补成 `2*x`。

同一键在不同 action 里语义可能不同。`rule` 是典型：

| action | `rule` 的读法 | 取值器 |
| --- | --- | --- |
| `random_variable` | 关键字（如 `"identity"` / `"square"`），源码用 `==` 比较 | `get_keyword`（不归一化） |
| `recurrence_sequence` | 表达式（如 `"a[-1] + a[-2]"`） | `get_string`（归一化） |

凡源码拿参数跟字面量比较的，使用 `get_keyword` / `get_keyword_opt`；否则按表达式键统一归一化会把 `square` 补成 `s*q*u*a*r*e`，关键字分支永远匹配不上。

### 3.2 方程键

`get_equation` / `get_equation_opt` 先归一化、再按「左 = 右」整理成 `=0`。语义上是方程的函数（解方程、判别式、隐函数求导）收等号；其余函数收到等号时由 `friendly_parse_error` 给中文说明，而不是把 SymEngine 的 `Unknown token: '='` 原样抛出。

## 4. 参数类型

### 4.1 引擎侧：类型由取值器决定

取值器同时定义三件事：要什么 JSON 类型、缺键怎么办、类型不符报什么。

| 取值器 | 需要的 JSON 类型 | 缺键 |
| --- | --- | --- |
| `get_int` / `get_int_opt` | 整数（小数报错） | 抛「缺少必填参数」/ 返回缺省 |
| `get_int_bounded` / `get_int_opt_bounded` | 整数 + 闭区间上界 | 抛 / 返回缺省 |
| `get_double` / `get_double_opt` | 数字 | 抛 / 返回缺省 |
| `get_bool_opt` | JSON 布尔 | 返回缺省 |
| `get_string` / `get_string_opt` | 字符串（表达式键归一化） | 抛 / 返回缺省 |
| `get_keyword` / `get_keyword_opt` | 字符串（不归一化） | 抛 / 返回缺省 |
| `get_equation` / `get_equation_opt` | 字符串 + 等号整理 | 抛 / 返回缺省 |
| `get_string_or_number` | 字符串或数字（数字转串） | 抛 |
| `get_int_array` / `get_double_array` | JSON 数组（逐个转、逐个报下标） | 抛 |

类型不符与上界超出的报错示例：

```text
diff_at {"expr":123,"point":0}
  → 参数 expr 类型错误：应为字符串，实际收到整数。本次调用传入的参数键：expr, point
taylor_polynomial {"expr":"e^x","n":2.5}
  → 参数 n 类型错误：应为整数，实际收到数字。本次调用传入的参数键：expr, n
expr_eval_vars_batch {"expr":"x^2","xs":["a","b"]}
  → 数组参数 xs 的第 0 项不是数字（实际为字符串）
```

`get_int_bounded` 是防卡死收口：大量参数直接决定循环次数或分配尺寸（`n` / `n_terms` / `order` / `max_iter` / `resolution` / `width` / `height` / `n_points`），没有上限时用户填一个大数就等于让引擎去算一个跑不完的东西。越界时抛说明性错误，并解释为什么有上限。逐处上限见 [`MODULES.md`](MODULES.md) 与 [`../HANG-OPTIMIZATION.md`](../HANG-OPTIMIZATION.md)。

### 4.2 前端 `calcArgs.js`：类型是短词表

`ENGINE_MAP[mode].args` 的元素形状是 `{key, type, opt}`。`convertArg` 用 `switch` 把文本变成 JSON 值（[`../../MF_UI/MFMath.UI.Vue/src/lib/engine/calcArgs.js`](../../MF_UI/MFMath.UI.Vue/src/lib/engine/calcArgs.js)），`STRUCTURED` 列出必须真解析成数组/点的类型。按 415 个模式统计（命令见「怎么自己验证」一节）：

```text
string=328  double=215  int=128  double_array=67  matrix=60  string_or_number=48
vec=20  point=19  vector=7  int_array=7  ll_array=7  prob_table=6  bool=4  sig=4
point_cloud=3  pair_list=3  complex_obj=2  ll_matrix=2  double_list=2  matrix_list=1  string_array=2
```

合计 935 个参数条目，其中 440 个 `opt:true`。`convertArg` 未覆盖的类型条目为 0。

结构化类型的写法约定：

| 类型 | 文本写法 |
| --- | --- |
| `double_array` / `double_list` / `int_array` / `int_list` | 数字数组，容忍 `[]` `()` 逗号空格与中文逗号 |
| `point` | `[x,y]`，分组写法 `(1,2)` 取第一组 |
| `matrix` / `pair_list` / `point_cloud` / `ll_matrix` | `[[…],…]`，`1,2; 3,4` 也接受 |
| `prob_table` | `键=值; 键=值`，整串就是一张表 |
| `bool` | `"true"` / `"1"` / `"是"` |
| `string_array` | 按深度 0 的 `;` 切分 |

解析不出来时 `convertArg` 原样返回文本，让引擎抛它自己的中文参数错误，不在前端静默塞 0/1。

### 4.3 签名表 `engine-signatures.json`

[`../../MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json`](../../MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json) 有 424 条（与引擎注册数一致），由 `tools/engine-signatures.mjs` 从 `*_api.cpp` 源码提取。类型名出现的分布：

```text
string=322  number=242  int=133  ?=75  number[]=60  matrix=58  array=28
?bound=16  string|number=8  int[]=6  ?parse_omega=4  ?get_sig=4  equation=3  bool=3  ?get_keyword_opt=1
```

`?` 开头的类型共 100 条，是提取失败的降级类型，因此该工具不拿类型当判据。对账判据是单向的：函数集合不一致、源码读取的参数表里没有、源码按必填读而表写成可选，三类判失败；其余只作提示。

## 5. 缺参数会怎样

### 5.1 引擎侧：拒绝并说清

`throw_missing` / `throw_type` 的消息带三样东西：缺哪个键、应该是什么类型、本次实际传了哪些键。handler 注册时给过签名的还会追加「期望签名：」。

```text
uniform_continuity {}   → 缺少必填参数 expr（应为字符串）。本次调用传入的参数键：（无）
diff_at {"expr":"x^2"}  → 缺少必填参数 point（应为数字）。本次调用传入的参数键：expr
```

「期望签名」只对少数 handler 有：向 `make_handler` 传了非空签名字符串的调用点是 14 处，多数 action 的错误里没有这一段。

### 5.2 前端侧：拒绝发生在调用点

计算页 `CalcView` 缺必填参数时不调引擎，行内说清缺什么、怎么补。判断走记账通道而不是字符串匹配：构造器 `buildEngineArgs` 在必填参数拿不到值时把兜底值填进去并记账（`noteDefaulted`），调用点读 `report.defaulted` 决定是否拒绝。兜底值是 `0` / `[0,0]` / `[]` / `""`，在引擎眼里都是合法值，所以引擎不会替前端报错；拒绝必须由调用点完成。

## 6. 怎么自己验证

```powershell
# ① 在 MF_Mathematics\build\bin\Release 下
.\probe_call.exe list_functions '{}'      # isError:false，value.count = 424
.\probe_call.exe --has diff_at            # yes
.\probe_call.exe --has diff_at_typo       # no，exit 1

# ② 在 MF_UI\MFMath.UI.Vue 下：参数类型统计
node --input-type=module -e "const em=await import('./src/lib/engine/engineMap.js'); const M=em.ENGINE_MAP; const KNOWN=new Set(['double','int','bool','string_or_number','point','vec','vector','matrix','matrix_list','point_cloud','prob_table','complex_obj','ll_matrix','ll_array','ll_list','pair_list','sig','double_array','double_list','int_array','int_list','string_array','string']); let bad=0,tot=0,opt=0; for(const s of Object.values(M)) for(const a of (s.args||[])){tot++; if(a.opt)opt++; if(!KNOWN.has(a.type))bad++;} console.log('modes',Object.keys(M).length,'specs',Object.keys(em.ENGINE_VAR_SPECS).length,'args',tot,'opt',opt,'uncovered',bad,'fns',new Set(Object.values(M).map(s=>s.fn)).size);"
```

① 依赖 `build/bin/Release` 的构建产物；产物与当前源码逐字一致需先重新构建。
