# 引擎调用契约（CONTRACT）

> **本文只回答一个问题：怎么调引擎 —— 参数怎么传、键名怎么对齐、缺参数会怎样、错误与未实现长什么样。**
>
> 与同层其它文档的分工：[`README.md`](README.md) 两个构建目标与"C ABI 恰好两个导出" · [`MODULES.md`](MODULES.md) 12 个学科模块逐个的 action 与能力 · [`INPUT.md`](INPUT.md) 输入层归一化与解析（含 `;` 的双语义） · [`BOUNDARIES.md`](BOUNDARIES.md) 能力边界与 `NOT_EXPOSED` 口径 · [`../link/README.md`](../link/README.md) 前端 ↔ 宿主的接缝（本文讲接缝**之下**那一层）。

**核对时间**：2026-10-07 · **核对产物**：`MF_Mathematics/build/bin/Release/probe_call.exe` + 同目录 `mf_mathematics.dll`（本机自省实测 `count=424`）；前端侧为 `MF_UI/MFMath.UI.Vue` 的 `node tools/check-ui.mjs`（exit 0）。
⚠ **一个前提没证实**：我没有重跑 `cmake --build … --config Release`，所以"该 DLL 与当前源码逐字一致"**未证实**。验证方式：按 [`README.md`](README.md) 重新构建后重跑 §7 的任意命令；输出与本文记录不同则以新构建为准。

## 1. 一页速查

引擎对外**只有两个 C ABI**（`MF_Mathematics/api.h:10`、`MF_Mathematics/api.h:18`）：

| C 符号 | 签名 | 说明 |
| --- | --- | --- |
| `function_exists` | `bool function_exists(const char* function_name)` | 名字存在返回 `true`；`nullptr` 返回 `false`（`api.cpp:10`） |
| `math_call` | `int math_call(const char* name, const char* args_json, char* out_buffer, int out_size)` | 成功返回写入字节数（**不含**结尾 `'\0'`）；失败或缓冲不足返回 `-1`（`api.h:17`） |

```
math_call("diff_at", "{\"expr\":\"x^2\",\"point\":1}", buf, size)  → {"isError":false,"value":2}
math_call("diff_at", "{\"expr\":\"x^2\"}", buf, size)
  → {"isError":true,"value":"缺少必填参数 point（应为数字）。本次调用传入的参数键：expr"}
math_call("no_such_action_xyz", "{}", buf, size)
  → {"isError":true,"value":"未找到函数: no_such_action_xyz"}
```

**四条一句话契约**（全文的浓缩）：`args` 是 JSON 对象、返回是 `{isError,value}`，且 `isError:false` 也可能是 `"未实现"`（§2.1）；键名逐字对齐，写错的键不报错而是**落到该参数缺省值**（§3.2 是一例用户可见的静默失效）；必填缺失由**调用点**负责拒绝（构造器只记账不抛，§5.3）；数组参数**整块写在一段里**（`x;[0,2]`，不是 `x;0;2`，§4.5）。

## 2. 参数是 JSON、返回也是 JSON 信封

### 2.1 信封的两个键，没有第三个

`result_ok` / `result_err` 各构造一个二键对象（`api_helpers.h:45-57`）。实测（`probe_call list_functions '{}'` 后取属性名）：顶层键恰为 `isError,value`。

| 情形 | `isError` | `value` 的 JSON 类型 |
| --- | --- | --- |
| 正常结果 | `false` | 数字 / 字符串 / 数组 / 对象，由 action 决定 |
| 算不出来（非初等积分等） | **`false`** | **字符串** `"未实现"`（§6.2） |
| 参数缺失 / 类型不符 / 解析失败 | `true` | 字符串（中文原因） |
| 函数名不存在 | `true` | 字符串 `"未找到函数: <name>"`（`registry.cpp:38`） |

⚠ **`isError:false` 不等于"这是你要的答案"**：`"未实现"` 与 `0` 都是 `isError:false`。判"调用成功"看 `isError`，判"结果可用"还要看 `value` 是不是占位文本。

### 2.2 `math_call` 的三个返回值

| 返回 | 含义 | 出处 / 实测 |
| --- | --- | --- |
| `> 0` | 写入的字节数，`out_buffer` 里是以 `'\0'` 结尾的完整 JSON | `api.cpp:23-24` |
| `-1` | 空指针 / `out_size <= 0` / **结果装不下**（`result.size()+1 > out_size`） | `api.cpp:16-19`、`api.cpp:22` |
| — | 函数名不存在**不**返回 `-1`，而是返回 `isError:true` 的信封 | `registry.cpp:37-39` |

缓冲不足是**真实会发生**的：`probe_call` 自带 4 MiB 缓冲（`tests/probe_call.cpp:33`），给它一个 600×600 的复网格就会被顶掉：

```powershell
# 工作目录 MF_Mathematics\build\bin\Release
.\probe_call.exe complex_grid '{"expr":"z^2","nx":600,"ny":600,"x0":-2,"x1":2,"y0":-2,"y1":2}'
# → exit=3，stderr：调用失败：缓冲区不足或参数非法（name=complex_grid）
```

而 `nx=700` 是被**引擎自己**的上限挡下的：`{"isError":true,"value":"网格点数 700×700 超过上限 400000，请降低分辨率（建议 ≤ 600×600）"}` —— **上限是产品行为，缓冲不足是调用方行为**，两者不能混为一类。Rust 宿主的应对是分级缓冲 4 MB → 16 MB → 64 MB（`MFMath.Host.Rust/src/engine.rs:24`、`:99-121`）：`n < 0` 就换更大缓冲重试，三级都不行才报"在 64 MB 缓冲下仍失败"。

### 2.3 `args_json` 不是对象时

`with_type_check` 的第一道判断是 `!args.is_object() || !args.has(key)`（`api_helpers.h:111`），于是非对象参数被归为"缺参数"：

```powershell
.\probe_call.exe diff_at 'null'    # …缺少必填参数 point（应为数字）。本次调用传入的参数键：（参数不是 JSON 对象）
.\probe_call.exe diff_at '"x^2"'   # 同上（键列表提示"参数不是 JSON 对象"）
.\probe_call.exe diff_at '[1,2]'   # 同上
```

**参数 JSON 解析失败**走另一条路：`make_handler` 里 `Value::parse` 抛 `std::runtime_error`（`json.hpp:287-290` 的 `err()`，前缀 `"JSON 解析错误: "`），被 `catch (const std::exception&)` 接住转成 `result_err`（`api_helpers.h:341-342`）：

```powershell
.\probe_call.exe diff_at '{"expr":'   # {"isError":true,"value":"JSON 解析错误: 未预期的字符 '"}
```

⚠ 上式尾部那个字符是**未转义的 NUL**（解析器在输入结束时 `peek()` 返回 `'\0'`，`json.hpp:294-296`）：消息合法但不可读，定位请换一个能给出可见字符的输入。

### 2.4 前端看到的是同一层

宿主同步桥 `MFMath.Host.Rust/src/engine.rs:94` 的 `call_json` **原样**返回引擎信封；宿主的错误信封由 `handlers.rs:42` 的 `err_envelope()` 手拼成同一形状（目的就是让前端一层 `parse()` 通吃）；前端在 `MF_UI/MFMath.UI.Vue/src/lib/bridge.js:131-132` 做 `mf.Dispatch(name, JSON.stringify(args))` → `JSON.parse`；异步 job 的 `result` 字段里装的又是一份信封原文（`bridge.js:217-219`）。所以本文的命令行实测结果，可以直接当作前端拿到的行为。

## 3. 键名契约

### 3.1 规则

1. **键名 = 参数名，逐字匹配，区分大小写**：取值器一律 `args[key]` 直取（`api_helpers.h:121-289`）。
2. **没传 ≠ 报错**：必填没传 → "缺少必填参数"（§5.1）；**可选**没传 → 用引擎自己的缺省（`get_*_opt`，`api_helpers.h:126-130`）。
3. **键名写错按"没传"处理**：必填的写错会报错并**列出你实际传的键**（`api_helpers.h:82-90` 的 `keys_of`）—— 这是专为排查拼写错误设计的：
   ```powershell
   .\probe_call.exe diff_at '{"expression":"x^2","point":1}'
   # {"isError":true,"value":"缺少必填参数 expr（应为字符串）。本次调用传入的参数键：expression, point"}
   ```
4. **多余的键被忽略**（不报错）：`.\probe_call.exe diff_at '{"expr":"x^2","point":3,"zzz":1}'` → `{"isError":false,"value":6}`。

> ⚠ 第 3、4 条合起来就是**静默错值**的温床：写错的键若**恰好是可选参数**，你不会收到任何提示，只会拿到用缺省值算出来的结果。

### 3.2 反面教材：`real_analysis` 一族只认 `interval`

引擎侧（`MF_Mathematics/real_analysis/real_analysis_api.cpp:34-44`）：

```cpp
void get_interval(const Value& args, double& a, double& b) {
    if (args.is_object() && args.has("interval") && args["interval"].is_array() &&
        args["interval"].size() == 2) { /* 取 a,b */ return; }
    a = 0.0; b = 1.0;   // ← 键不对、不是数组、或长度不是 2，都恒定落到这里
}
```

**实测（同一函数、不同键）**：

```powershell
.\probe_call.exe integral_mean_value '{"expr":"x","interval":[0,2]}'   # {"isError":false,"value":{"mean_value":1,"xi":1}}
.\probe_call.exe integral_mean_value '{"expr":"x","a":0,"b":2}'        # {"isError":false,"value":{"mean_value":0.5,"xi":0.5}}  ← 静默按 [0,1]
.\probe_call.exe integral_mean_value '{"expr":"x","interval":[5]}'     # 同 [0,1]（长度不是 2）
.\probe_call.exe integral_mean_value '{"expr":"x","interval":[0,2,9]}' # 同 [0,1]（长度不是 2）
```

第二种写法**不报错**：`a`/`b` 成了被忽略的多余键、`interval` 缺失 → `[0,1]`。这正是 [BUGS.md](../../MF_UI/BUGS.md) **B1**（P1，2026-10-07 已修）的成因：10 个 UI 模式的 `args` 要么声明成 `a`/`b`、要么根本没有区间参数，用户填了也不生效。修后前端统一引用一个片段（`engineMapExtra.js:26` 的 `const INTERVAL = { key: "interval", type: "double_array", opt: true };`），10 个模式逐个引用它（`engineMapExtra.js:176`、`:366-376`），并由自检守卫固定住：`node tools/check-ui.mjs` 打印"区间参数契约：10 个 handler / 命中模式 10 个 / 缺 interval 0 个"。

⚠ 该守卫**刻意不读引擎源码**，而是**写死**那 10 个 handler 名（`tools/check-ui.mjs:270-274`，理由见 `:265-267`）：**引擎新增走 `get_interval` 的 handler 时必须把它加进这个清单**，否则守卫不覆盖它。

### 3.3 表达式键 vs 关键字键：同名键在不同 action 里语义不同

`get_string` **按名字**判断"这个参数是不是用户写的数学表达式"：命中 `is_expression_key`（`api_helpers.h:27-36`，固定 20 个键名：`expr` `eq` `f` `g` `f_n` `func` `x_expr` `y_expr` `g_expr` `expr1` `expr2` `compare_expr` `seq` `seq_expr` `rule` `phi` `series` `body` `expression` `ex` `ey`）就先做隐式乘法 / LaTeX 归一化（`api_helpers.h:39-41`）。实测 `.\probe_call.exe diff_at '{"expr":"2x","point":1}'` → `{"isError":false,"value":2}`（`2x` 被补成 `2*x`）。

`rule` 在两张表里语义相反（`api_helpers.h:195-216`，以代码为准）：

| action | `rule` 的读法 | 实测 |
| --- | --- | --- |
| `random_variable` | **关键字**（`get_keyword`，不归一化），源码用 `==` 比较 | `{"rule":"square"}` 正常；`{"rule":"identity"}` 正常 |
| `recurrence_sequence` | **表达式**（`get_string`） | `{"rule":"a[-1]+a[-2]","n":5,"initial":[1,1]}` → `[1,1,2,3,5]` |

按名字统一归一化会把 `square` 补成 `s*q*u*a*r*e`，于是关键字分支永远匹配不上、落到 else 分支并把 `X(ω) = s*q*u*a*r*e` 当描述返回。**凡是源码里拿参数跟字面量比较的，都必须用 `get_keyword` / `get_keyword_opt`**（`api_helpers.h:206-216`）。

### 3.4 方程键：等号只对"语义上是方程"的键合法

`get_equation` / `get_equation_opt`（`api_helpers.h:227-244`）先归一化、再按课本的"左 = 右"整理成 `=0`；其它函数收到等号时由 `friendly_parse_error` 给中文说明（`api_helpers.h:318-329`）：

```powershell
.\probe_call.exe solve_quadratic '{"expr":"x^2-1=0"}'     # {"isError":false,"value":["1","-1"]}
.\probe_call.exe diff_at '{"expr":"x^2-1=0","point":1}'
# {"isError":true,"value":"表达式里出现了 '='，而这个函数只接受表达式。解方程 / 判别式 / 隐函数求导可以直接写 x^2+2x+1=0；其它函数请把等号右边移到左边（x^2+2x+1=0 → x^2+2x+1，引擎按 =0 处理）。原始信息：Unknown token: '='"}
```

## 4. 参数类型：三张表，表达方式各不相同

### 4.1 引擎侧：类型由"取值器"决定（唯一真相）

`api_helpers.h` 的每个取值器同时定义三件事：**要什么 JSON 类型 / 缺键怎么办 / 类型不符报什么**。

| 取值器 | 需要的 JSON 类型 | 缺键 | 出处 |
| --- | --- | --- | --- |
| `get_int` / `get_int_opt` | 整数（**小数报错**） | 抛"缺少必填参数" / 返回 `def` | `api_helpers.h:121-130` |
| `get_int_bounded` / `get_int_opt_bounded` | 整数 + **闭区间上界** | 抛 / 返回 `def` | `api_helpers.h:143-163` |
| `get_double` / `get_double_opt` | 数字 | 抛 / 返回 `def` | `api_helpers.h:165-174` |
| `get_bool_opt` | **只能是 JSON 布尔** | 返回 `def` | `api_helpers.h:176-179` |
| `get_string` / `get_string_opt` | 字符串（表达式键会归一化） | 抛 / 返回 `def` | `api_helpers.h:181-193` |
| `get_keyword` / `get_keyword_opt` | 字符串（**不**归一化） | 抛 / 返回 `def` | `api_helpers.h:206-216` |
| `get_equation` / `get_equation_opt` | 字符串 + 等号整理 | 抛 / 返回 `def` | `api_helpers.h:234-244` |
| `get_string_or_number` | 字符串**或**数字（数字转成串） | 抛 | `api_helpers.h:247-255` |
| `get_int_array` / `get_double_array` | **JSON 数组**（逐个转、逐个报下标） | 抛"缺少必填参数（应为…数组）" | `api_helpers.h:257-289` |

```powershell
.\probe_call.exe diff_at '{"expr":123,"point":0}'
# {"isError":true,"value":"参数 expr 类型错误：应为字符串，实际收到整数。本次调用传入的参数键：expr, point"}
.\probe_call.exe taylor_polynomial '{"expr":"e^x","n":2.5}'
# {"isError":true,"value":"参数 n 类型错误：应为整数，实际收到数字。本次调用传入的参数键：expr, n"}
.\probe_call.exe expr_eval_vars_batch '{"expr":"x^2","xs":["a","b"]}'
# {"isError":true,"value":"数组参数 xs 的第 0 项不是数字（实际为字符串）"}
.\probe_call.exe taylor_polynomial '{"expr":"e^x","n":1000}'    # 上界参数另有一套文案（api_helpers.h:143-156）
# {"isError":true,"value":"项数 超出可计算范围 [-9223372036854775807, 100]：收到 1000。上限是为了避免单次计算卡住界面——这类参数直接决定循环次数或分配大小，代价随它迅速增长；需要更大规模请分批做。"}
```

> ⚠ **`get_bool_opt` 是这条规则之外的一个洞**：它没走 `with_type_check`（对照 `api_helpers.h:111` 与 `:176-179`），类型错时抛的是 `json.hpp:113` 的裸消息，**没有键名、没有期望类型、没有键列表**：
> ```powershell
> .\probe_call.exe simplicial_complex '{"simplices":[[0,1]],"maximal":1}'       # {"isError":true,"value":"值不是布尔"}
> .\probe_call.exe simplicial_complex '{"simplices":[[0,1]],"maximal":"true"}'  # 同上
> .\probe_call.exe simplicial_complex '{"simplices":[[0,1]],"maximal":true}'    # {"isError":false,…}
> ```
> 参数类错误"一次说清缺什么、要什么类型、实际收到什么"的承诺（`api_helpers.h:59-64`）**对 bool 参数不成立**。

### 4.2 前端 `calcArgs.js`：类型是自造的短词表

`ENGINE_MAP[mode].args` 的元素形状是 `{key, type, opt}`（`engineMap.js:3`）。`convertArg` 用一张 `switch` 把文本变成 JSON 值（`calcArgs.js:160-190`），`STRUCTURED` 列出"必须真解析成数组/点"的类型（`calcArgs.js:53-57`）。对 415 个模式逐个统计 `args` 条目（复跑命令见 §7 ③）：

```
string=328  double=215  int=128  double_array=67  matrix=60  string_or_number=48
vec=20  point=19  vector=7  int_array=7  ll_array=7  prob_table=6  bool=4  sig=4
point_cloud=3  pair_list=3  complex_obj=2  ll_matrix=2  double_list=2  matrix_list=1  string_array=1
```

合计 **934** 个参数条目，其中 **440** 个 `opt:true`；**`convertArg` 未覆盖的类型条目 = 0**。几处必须知道的语义：

| 写法 | 转成什么 | 出处 |
| --- | --- | --- |
| `double_array` / `double_list` / `int_array` / `int_list` | 数字数组（容忍 `[]` `()` 逗号空格与中文逗号）；int 系再逐个 `Math.trunc` | `calcArgs.js:77-86`、`:185-186` |
| `point` | `[x,y]`（分组写法 `(1,2)` 取第一组，最多 2 个） | `calcArgs.js:149-153` |
| `matrix` / `pair_list` / `point_cloud` / `ll_matrix` | `[[…],…]`；`1,2; 3,4` 也接受 | `calcArgs.js:88-101` |
| `prob_table` | `"键=值; 键=值"` → 对象；**整串就是一张表** | `calcArgs.js:136-146`、`:285-287` |
| `bool` | `s === "true" \|\| s === "1" \|\| s === "是"` | `calcArgs.js:165` |
| `string_array` | **按深度 0 的 `;` 切分**（括号里的 `;` 不算分隔） | `calcArgs.js:59-74`、`:187` |
| 其它（含拼错的类型名） | 落到 `default: toEngineExpr(s)` → **字符串** | `calcArgs.js:188` |

> ⚠ `default` 那条静默兜底是**有意保留**的：解析不出来就按原样交给引擎，让引擎抛它自己的中文参数错误（`calcArgs.js:155-159`）。**在这里塞 0/1 才是真正难查的失败。**

### 4.3 签名表 `engine-signatures.json`：类型是"刮"出来的

`MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json` 有 **424** 条（与引擎注册数一致），由 `tools/engine-signatures.mjs` 从 `*_api.cpp` 源码刮出，类型名来自 `TYPE_OF`（`engine-signatures.mjs:40-53`）。实际出现过的类型（实测统计）：

```
? | ?bound | ?get_keyword_opt | ?get_sig | ?parse_omega
array | bool | equation | int | int[] | matrix | number | number[] | string | string|number
```

两条必须知道：① **降级类型共 100 个条目**（`?` 75、`?bound` 16、`?get_sig` 4、`?parse_omega` 4、`?get_keyword_opt` 1）—— 当年刮取失败的遗留，所以工具**不拿类型当判据**（`engine-signatures.mjs:21-23`）。② 对账判据是**单向**的（`engine-signatures.mjs:136-147`）：只判"函数集合不一致""源码明确读取的参数表里没有""源码按必填读、表里写成可选"，**表里多出来的参数、类型差异、表里必填而源码只见 `_opt` 一律只作提示**。复跑：`node tools/engine-signatures.mjs --check`（有漂移 exit 1，已在 `npm run check` 里）。

### 4.4 ⚠ 三张表的接缝：函数工具箱少了两类转换

函数工具箱（`views/tools/ToolboxView.vue`）不做 `convertArg`，它按签名表的类型名自己分流（`ToolboxView.vue:128-141`）：数值型走 `NUMERIC = {number,int,integer,float,double,real}`（`:66`）→ `Number(raw)`；结构化走 `STRUCT = /^(matrix|array|object|list|vector|tuple|sets|data|pmf_data)$/i`（`:68`）→ `JSON.parse(raw)`；**其余一律 `args[p.key] = raw`（字符串）**。而签名表里出现过、两类都不匹配的有 **66 个数组类型条目**（`int[]` / `number[]`）+ **3 个 `bool` 条目**，引擎侧却分别是 `get_int_array` / `get_double_array`（要求 `is_array()`）与 `get_bool_opt`（要求 JSON 布尔）：

```powershell
.\probe_call.exe expr_eval_vars_batch '{"expr":"x^2","xs":"1,2"}'
# {"isError":true,"value":"缺少必填参数 xs（应为数字数组）。本次调用传入的参数键：expr, xs"}   ← 字符串不行
.\probe_call.exe simplicial_complex '{"simplices":[[0,1]],"maximal":"true"}'   # {"isError":true,"value":"值不是布尔"}
```

**分类**：这是**产品缺陷**（工具箱对这两类参数不可用），**静态可证 + 引擎侧已实测**；UI 侧我没做端到端，**未证实**用户真会撞到。验证方式：宿主里打开函数工具箱、选 `expr_eval_vars_batch`、在 `xs` 里填 `[1,2]` 点调用，看是否得到上面那句"缺少必填参数"。

### 4.5 数组参数怎么给：**一个参数 = 一段**

`;` 在深度 0 处切段（`calcArgs.js:59-74`），**一段喂一个参数**（`calcArgs.js:262-336`），所以数组参数必须**整块写在一段里**（`node --input-type=module` 下实测）：

```js
buildEngineArgs('平均值','x;[0,2]')   // {"expr":"x","interval":[0,2]}   ✅
buildEngineArgs('平均值','x;0,2')     // {"expr":"x","interval":[0,2]}   ✅（逗号不是分段符）
buildEngineArgs('平均值','x;0;2')     // {"expr":"x","interval":[0]}     ❌ 第二段被丢弃 → 引擎静默按 [0,1]
```

`平均值` 的弹窗字段默认值是 `"0,1"`（`engineMapExtra.js:402`），等于引擎自己的缺省，所以**不改弹窗直接点计算的结果与修复前逐字一致**（`engineMapExtra.js:361`）。

## 5. 缺参数会怎样

### 5.1 引擎侧：拒绝并说清（这是设计）

`throw_missing` / `throw_type` 的消息带三样东西：**缺哪个键 / 应该是什么类型 / 本次实际传了哪些键**（`api_helpers.h:92-105`）；handler 注册时给过签名的还会追加"期望签名："（`api_helpers.h:337-340`）。

```powershell
.\probe_call.exe uniform_continuity '{}'   # …缺少必填参数 expr（应为字符串）。本次调用传入的参数键：（无）
.\probe_call.exe diff_at '{"expr":"x^2"}'  # …缺少必填参数 point（应为数字）。本次调用传入的参数键：expr
.\probe_call.exe to_engine_expr '{}'       # …（无）。期望签名：{expr: string}
.\probe_call.exe diff '{}'                 # …（无）      ← 没有"期望签名"
```

⚠ **"期望签名"只对少数 handler 有**：向 `make_handler` 传了签名字符串的调用点共 **12 处**（`Select-String -Path MF_Mathematics/**/*_api.cpp -Pattern '^\s*\}\s*,\s*"'`），所以多数 action 的错误里没有这一段。

### 5.2 前端侧的三种不同处置

| 调用点 | 缺必填参数时的行为 | 出处 |
| --- | --- | --- |
| 计算页 CalcView | **不调引擎**，行内说清缺什么、怎么补 | `CalcView.vue:291-299`、`:360-369` |
| 函数工具箱 ToolboxView | 空字段**一律不发**（含必填）→ 由引擎报"缺少必填参数" | `ToolboxView.vue:131` |
| 绘图页 React | 直接 `engineCall`，错误进 `nextErr` / 页内状态行 | `usePlotSampling.ts:60`、`Plot3DPage.tsx:158`、`PlotFractalPage.tsx:186` |

`CalcView` 的判据走**记账通道**而不是字符串匹配（`CalcView.vue:291-299`）：

```js
const report = { defaulted: [] };
const args = buildEngineArgs(mode, expr, report);
const missing = missingRequiredText(report, mode);
if (missing) { patchBlock(block.id, { computing: false, error: missing }); return; }
```

`report.defaulted` 由 `noteDefaulted` 在**必填参数拿不到值**时填充（`calcArgs.js:218-221`、`:318-327`、`:428-435`）。

### 5.3 必须说清的一个细节：兜底**仍在**，拒绝发生在调用点

`buildEngineArgs` **依然**会产出 `0` / `[0,0]` / `[]` 这些兜底值，只是同时记账。实测：`buildEngineArgs('某点导数','x^2', r)` → `{"expr":"x^2","point":0}`，且 `r.defaulted = [{"key":"point","type":"double","value":0}]`。

这就是 [BUGS.md](../../MF_UI/BUGS.md) **B4** 的完整形状（原文 `BUGS.md:450-505`，修复记录 `BUGS.md:141`）：**前半是"消除静默"（builder 记账），后半是"拒绝计算"（CalcView 不调引擎）**。两个直接后果：直接 import `calcArgs.js` 的**测试代码**（`tests/audit-modes.mjs:39`、`tests/cdp-modes-render.mjs:241`）仍会拿到兜底值，**必须自己传 `report` 并检查**；**新写的调用点**也必须自己传 `report`，否则 B4 会在新路径上复现。

B4 的清单要打折看：探针按 **415 个模式**查出 32 个"必填被兜底"，其中**只有 10 个是页面模式**（会真正被 UI 与套件点到），样本已按这 10 条补齐并用真引擎验过（`BUGS.md:491-496`、`CalcView.vue:356-358`）。

## 6. 错误与"未实现"长什么样

### 6.1 错误的三条来源（决定消息质量）

`make_handler` 有三层 `catch`（`api_helpers.h:331-356`）：

| 层级 | 捕获 | 消息形状 | 实测 |
| --- | --- | --- | --- |
| 参数类 | `arg_error`（`api_helpers.h:66-68`） | 中文 + 期望类型 + 键列表（+可选签名） | §5.1 四条 |
| 其它 `std::exception` | SymEngine / 自研代码抛出 | **原文**，只对含 `=` 的 token 错误做改写 | `"积分下限须小于上限"`（`integrals.cpp:1068`）、`"Unknown token: '='"` → 中文（`api_helpers.h:318-329`） |
| 非 `std` 异常 | `throw 42;` / `throw "..."` | 固定中文"引擎内部错误…" | `api_helpers.h:343-354` |

第三层存在的理由是**安全**而非友好：非 std 异常穿过 `extern "C"` 边界是未定义行为，表现为**整个宿主进程被终止**（`api_helpers.h:345-347`）。⚠ 但 `catch(...)` **抓不到访问违例 / 栈溢出**（`api_helpers.h:348-350`）—— 这类 SEH 直接杀进程，`probe_bugs` / `probe_solve_safety` 那套"崩溃点即证据"的探针语义不受影响。

### 6.2 "未实现"：`isError:false` + 字符串 `"未实现"`

这是"不编造结果"的落地方式：**算不出来就说算不出来，且不算"错误"**。返回字面量 `"未实现"` 的位置：`integrate_indefinite`（`integrals.cpp:1051-1052`、`calculus/integrals.h:14`）、`integrate_double_indefinite`（`integrals.cpp:1232-1234`）、`integrate_triple_indefinite`（`integrals.cpp:1251-1255`）。

```powershell
.\probe_call.exe integrate '{"expr":"e^(-x^2)"}'   # {"isError":false,"value":"未实现"}
.\probe_call.exe integrate '{"expr":"1/ln(x)"}'    # {"isError":false,"value":"未实现"}
.\probe_call.exe integrate '{"expr":"x^x"}'        # {"isError":false,"value":"未实现"}
.\probe_call.exe integrate_double '{"expr":"x^x*y","x":"x","y":"y"}'   # {"isError":false,"value":"未实现"}
```

**定积分**是另一条路：符号失败**回退数值**（`integrals.h:18`），所以不返回 `"未实现"`：

```powershell
.\probe_call.exe integrate '{"expr":"e^(-x^2)","a":"0","b":"1"}'   # {"isError":false,"value":0.746824132812436}
.\probe_call.exe integrate '{"expr":"sin(x)","a":"0","b":"pi"}'    # {"isError":false,"value":2}
```

**定/不定由键的存在决定**（不是另设开关）：`a` 与 `b` **同时**存在才是定积分（`calculus_api.cpp:93-100`）。`integrate_double` 同一套约定：四个边界键（`xa`,`xb`,`ya`,`yb`）齐了才定，否则不定 —— **缺边界不再静默按 `[0,1]` 算**（`calculus_api.cpp:112-131`，注释与代码一致）。

### 6.3 "未实现" 与 "错误" 的对照

| | 未实现 | 错误 |
| --- | --- | --- |
| `isError` | `false` | `true` |
| `value` 类型 | 字符串（`"未实现"`）或对象 | 字符串 |
| 典型触发 | 非初等原函数（`x^x`、`e^(-x^2)`、`1/ln(x)`） | 缺参数、类型不符、JSON 错、函数名不存在 |
| 前端是否特判 | **没有** —— 在前端引擎消费代码里 `grep 未实现` 零命中（`MFMath.UI.Vue/src`、`MFMath.UI.React/src` 都搜过），它作为普通结果值显示 | 各处按 `isError` 分支 |

⚠ 所以**"界面上看到 `未实现`"是正确行为，不是 bug**；把它当成空结果或 0 才是 bug。

### 6.4 机器话外泄：一例实测

```powershell
.\probe_call.exe integrate_complex '{"expr":"e^(-z^2)","a":"0","b":"1"}'
# {"isError":true,"value":"Symbol cannot be evaluated."}
```

`integrals.cpp:1367` 的注释写"失败抛'未实现'"，`:1380` 也确有 `throw std::invalid_argument("未实现:无法符号积分该复函数")`，但**实测没走到那一句** —— 用户看到的是 SymEngine 的英文原文。`friendly_parse_error` 只改写含 `=` 的 token 错误（`api_helpers.h:318-322`），兜不住这类消息。**分类**：产品缺陷（消息质量），**已实测**；未证实的是它能否从 UI 走到（需先确认哪个 UI 模式映射到 `integrate_complex`）。

### 6.5 宿主层叠加：信封之上还有一层，词表**不是**同一套

引擎信封只有 `isError` / `value`，**没有 `kind`**。宿主在它之上另立一套：同步派发失败是 `{"isError":true,"value":"原因"}`（`handlers.rs:42` 的 `err_envelope()`，与已废弃的 C# 版逐字一致，目的就是让前端一层 `parse()` 通吃）；派发异步任务返回 `{"ok":true,"jobId":"job3"}` / `{"ok":false,"error":"…"}`（`jobs.rs:183-185`）；轮询返回 `{"ok":true,"jobId":…,"state":…,"ms":…,"elapsedMs":…,"result":<引擎信封原文>}`（`jobs.rs:189-206`）。而**失败分类词表**（`kind`）只属于账号 / 搜索 / 更新这些网络对象（`account` 8 类、`search` 6 类、`update` 走 site 层）—— 见 [`../link/FEATURES.md`](../link/FEATURES.md) §6.4。

**不要用宿主那套词表解释引擎错误**：引擎没有 `kind`；异步 job 的 `result` 字段里装的**才是**引擎信封（`bridge.js:217-219`）。取消语义也只在宿主层（引擎没有取消钩子，`CancelJob` 是"停止等待 + 丢弃结果"）：见 [`../link/JOBS-PUSH.md`](../link/JOBS-PUSH.md) 与 `bridge.js:156-158`、`:192-198` 的同一句说明。

## 7. 怎么自己验证（可复跑）

① ② ④ 在 `MF_Mathematics\build\bin\Release` 下执行；③ ⑤ 在 `MF_UI\MFMath.UI.Vue` 下执行。

| # | 命令 | 期望 |
| --- | --- | --- |
| ① | `.\probe_call.exe list_functions '{}'` | `isError:false`，`value.count` = **424** |
| ② | `.\probe_call.exe --has diff_at` | 打印 `yes`；`--has diff_at_typo` 打印 `no` 且 exit 1 |
| ③ | 见下方一行 | `ENGINE_MAP` **415** 键 / `ENGINE_VAR_SPECS` **139** 键 / args 条目 **934**（opt **440**）/ 未覆盖类型 **0** / 去重 fn **371** |
| ④ | `.\probe_call.exe integral_mean_value '{"expr":"x","a":0,"b":2}'` 与 `…'{"expr":"x","interval":[0,2]}'` | 前者 `mean_value:0.5`（静默 `[0,1]`）、后者 `1` —— 键名契约的对照实验 |
| ⑤ | `node tools/check-ui.mjs` | exit 0；打印"区间参数契约：10 个 handler / 命中模式 10 个 / 缺 interval 0 个"、"概率表契约：4 个模式 / 空表 0 个"、"样本 fixture：287 个键 / 重复键 0 个"、"端到端用例：cdp-* 48 个，已登记 48 个" |

③ 的完整一行（§4.2 的统计数字由它产出）：

```powershell
node --input-type=module -e "const em=await import('./src/lib/engine/engineMap.js'); const M=em.ENGINE_MAP; const KNOWN=new Set(['double','int','bool','string_or_number','point','vec','vector','matrix','matrix_list','point_cloud','prob_table','complex_obj','ll_matrix','ll_array','ll_list','pair_list','sig','double_array','double_list','int_array','int_list','string_array','string']); let bad=0,tot=0,opt=0; for(const s of Object.values(M)) for(const a of (s.args||[])){tot++; if(a.opt)opt++; if(!KNOWN.has(a.type))bad++;} console.log('modes',Object.keys(M).length,'specs',Object.keys(em.ENGINE_VAR_SPECS).length,'args',tot,'opt',opt,'uncovered',bad,'fns',new Set(Object.values(M).map(s=>s.fn)).size);"
```

⚠ 跑 ⑤ 前确认没有别的会话在驱动同一棵树（[`../../AGENTS.md`](../../AGENTS.md) §4）。⑤ 不需要宿主所以不受并发影响；**但 ① ② ④ 依赖 `build/bin/Release` 的构建产物** —— 见文首那条"未证实"。

## 8. 已知的文档债

| # | 位置 | 注释/旧文档说 X | 代码做 Y | 证据 |
| --- | --- | --- | --- | --- |
| 1 | `MF_Mathematics/introspect_api.cpp:6` | 前端映射表"如 Vue 的 `ENGINE_MAP`，**324 条**" | `ENGINE_MAP` 实际 **415** 键 | §7 ③ 的命令；`engineMap.js:9` 也写"实际 415" |
| 2 | `MF_UI/MFMath.UI.Vue/src/views/tools/ToolboxView.vue:134-137` | "结构化参数要真值而不是它的字符串" | `STRUCT` 正则（`:68`）不含 `int[]` / `number[]` / `bool`，这 **66+3** 个参数条目落到字符串分支 | §4.4；引擎侧实测见该节 |
| 3 | `MF_Mathematics/calculus/integrals.cpp:1367` | "失败抛'未实现'" | 实测 `integrate_complex('e^(-z^2)',0,1)` 返回英文 `"Symbol cannot be evaluated."`，`:1380` 那句没被触发 | §6.4 |
| 4 | `MF_Mathematics/api_helpers.h:59-64` | "一次说清：缺什么、要什么类型、实际收到什么、本函数收到了哪些键" | `get_bool_opt`（`:176-179`）绕开 `with_type_check`，bool 类型错时只有裸消息 `"值不是布尔"` | §4.1 末的实测块 |

**本文没有收录的相邻债**（不属本文范围）：`docs/` 里仍把已废弃的 .NET 宿主写成现役实现的 6 份文档 —— 见 [`../PROJECT-BOARD.md`](../PROJECT-BOARD.md) §3 **R7**。
