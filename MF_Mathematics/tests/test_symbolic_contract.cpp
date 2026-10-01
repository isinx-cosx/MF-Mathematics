// test_symbolic_contract.cpp — 符号 API 的「契约」回归测试
//
// 这些用例全部来自实际反馈的缺陷，逐条钉住，防止回退：
//   #1 intersections 含参时 real 判错（曾把 Δ=a²+4>0 的两个实交点标成虚根）
//   #2 extrema_sym 分支里 value 的语义歧义（曾是二阶导值，却被当成极值）
//   #3 simplify_sym 的 simplified 比 expanded 还差（化简路径没生效）
//   #4 factor_sym("x^2-a^2") 给出 sqrt(a**2) 而不是 (x+a)(x-a)
//   #5 机器记号外泄（a**(-1)、zoo、I）
//   #6 compare_expr 参数错误信息不友好（要试错三轮）
//   #7 过期引擎 DLL（构建产物与本文件同目录的探针一起核对时间戳，见 sync-engine.ps1）
//
// 全部通过公开的 C ABI（math_call）调用，与 C#/JS 调用方走同一条路径，
// 因此这些断言直接描述对外行为，而不是内部实现。
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "api.h"
#include "special_numeric.h"

namespace {

int g_checks = 0;
int g_failures = 0;

#define CHECK(cond, msg)                      \
  do {                                        \
    ++g_checks;                               \
    if (!(cond)) {                            \
      ++g_failures;                           \
      std::printf("[FAIL] %s\n", msg);        \
    }                                         \
  } while (0)

/** 调用引擎，返回 {isError, value} 的原始 JSON。 */
std::string call(const std::string& name, const std::string& args) {
  std::vector<char> buf(1 << 20);
  const int n = math_call(name.c_str(), args.c_str(), buf.data(),
                          static_cast<int>(buf.size()));
  if (n < 0) return "{\"isError\":true,\"value\":\"调用失败\"}";
  return std::string(buf.data(), static_cast<std::size_t>(n));
}

/** 极简 JSON 取值：在文本里找 "key": 之后的值（够用于契约断言，避免引入解析器）。 */
bool has(const std::string& json, const std::string& needle) {
  return json.find(needle) != std::string::npos;
}

/**
 * 在**某个参数分支对象内部**查找片段。
 * 序列化后的字段按字典序排列（assume/exists/f2_value/f_value/kind/note），
 * 因此不能假设 "assume" 与 "kind" 相邻；同时一个表达式可能有多个驻点、
 * 每个驻点都带同名分支，所以要遍历所有匹配而不是只看第一个。
 */
bool branch_has(const std::string& json, const std::string& assume,
                const std::string& needle) {
  const std::string key = "\"assume\":\"" + assume + "\"";
  std::size_t p = json.find(key);
  while (p != std::string::npos) {
    const std::size_t close = json.find('}', p);
    if (close == std::string::npos) return false;
    const std::size_t hit = json.find(needle, p);
    if (hit != std::string::npos && hit < close) return true;
    p = json.find(key, close);
  }
  return false;
}

// ── #1 含参交点的实根性 ─────────────────────────────────────────────────────

void test_intersections_realness() {
  // x² = a·x + 1 → Δ = a² + 4 恒正 → 对任意实参数都有两个实交点
  const std::string r = call("intersections", "{\"expr1\":\"x^2\",\"expr2\":\"a*x+1\"}");
  CHECK(has(r, "\"delta\":\"4 + a**2\""), "#1 判别式应为 4 + a**2");
  CHECK(!has(r, "\"real\":false"), "#1 恒正判别式下不得出现 real=false");
  CHECK(has(r, "\"realness\":\"real\""), "#1 总体实根性应为 real");
  CHECK(has(r, "\"deltaSign\":\"positive\""), "#1 Δ 符号应为 positive");

  // x² = -a → Δ = -4a 符号依赖 a → 必须标为 conditional，且 real 不出结论（null）
  const std::string c = call("intersections", "{\"expr1\":\"x^2\",\"expr2\":\"-a\"}");
  CHECK(has(c, "\"realness\":\"conditional\""), "#1 Δ 变号时应为 conditional");
  CHECK(has(c, "\"real\":null"), "#1 无法判定时 real 必须是 null（不是 false）");

  // 纯数值且无实根：仍要过滤掉复数解（不能因为改造而放行）
  // x² = -1 的符号解为 ±i，两根都是复根 → skippedComplex 应为 2
  const std::string n = call("intersections", "{\"expr1\":\"x^2\",\"expr2\":\"-1\"}");
  CHECK(has(n, "\"skippedComplex\":2"), "#1 纯数值复数解仍应被过滤（±i 共 2 个）");
  CHECK(has(n, "\"realness\":\"complex\""), "#1 x²=-1 的实根性应为 complex");
  CHECK(has(n, "\"count\":0"), "#1 复根不得出现在 points 里");
}

// ── #2 极值字段语义 ─────────────────────────────────────────────────────────

void test_extrema_field_semantics() {
  // f = a·x³ - x，在 a>0 分支：x₀ = -1/√(3a)，f(x₀) = 2√3/(9√a)，f''(x₀) = -2√3·√a
  const std::string r = call("extrema_sym", "{\"expr\":\"a*x^3-x\"}");
  CHECK(has(r, "\"f_value\""), "#2 分支必须给出 f_value（极值本身）");
  CHECK(has(r, "\"f2_value\""), "#2 二阶导值应命名为 f2_value（不再叫 value）");
  // 旧实现的分支形如 {"assume":"a>0","value":"-6",...}，这里断言该形状已消失
  CHECK(!has(r, "\"assume\":\"a>0\",\"value\""), "#2 分支内的歧义字段 value 必须消失");
  CHECK(has(r, "\"valueFieldNote\""), "#2 应附带字段语义说明");
  // a>0 时 f(x₀) = 2√3/9（a=1），f''(x₀) = -2√3（a=1）——两者必须不同
  CHECK(has(r, "\"f_value\":\"(2/9)*sqrt(3)\""), "#2 a>0 分支 f_value = (2/9)√3");
  CHECK(has(r, "\"f2_value\":\"-2*sqrt(3)\""), "#2 a>0 分支 f2_value = -2√3");
  CHECK(has(r, "\"kind\":\"maximum\""), "#2 f''<0 → 极大");
}

// ── #3 化简 ─────────────────────────────────────────────────────────────────

void test_simplify_chooses_best() {
  // (x-a)² - (x+a)² = -4ax：SymEngine::simplify 原样返回，expand 才对
  const std::string r = call("simplify_sym", "{\"expr\":\"(x-a)^2-(x+a)^2\"}");
  CHECK(has(r, "\"simplified\":\"-4*a*x\""), "#3 应选中最简形式 -4*a*x");
  CHECK(has(r, "\"chosen\":\"expand\""), "#3 chosen 应说明来自 expand");
  CHECK(has(r, "\"candidates\""), "#3 应给出候选清单以便核对");

  // 三角恒等：SymEngine::simplify 本身不做三角恒等，靠显式候选补上
  const std::string t = call("simplify_sym", "{\"expr\":\"sin(x)^2+cos(x)^2\"}");
  CHECK(has(t, "\"simplified\":\"1\""), "#3 sin²+cos² 应化为 1");
  CHECK(has(t, "三角恒等"), "#3 chosen 应说明来自三角恒等候选");
}

// ── #4 因式分解 ─────────────────────────────────────────────────────────────

void test_factor_sym_radicals() {
  const std::string r = call("factor_sym", "{\"expr\":\"x^2-a^2\"}");
  CHECK(has(r, "\"factored\":\"(x + a)*(x - a)\""), "#4 x²-a² → (x + a)*(x - a)");
  CHECK(!has(r, "sqrt(a**2)"), "#4 不得残留 sqrt(a**2)");

  // 归约只在数学等价时采用：x²-2 的根是真根式，不能"化简"成整数
  const std::string s = call("factor_sym", "{\"expr\":\"x^2-2\"}");
  CHECK(has(s, "sqrt(2)"), "#4 x²-2 的根应保留 sqrt(2)");

  // 奇次幂不是完全平方：a³ 的开方不能被"化简"成 a**(3/2)
  const std::string c = call("factor_sym", "{\"expr\":\"x^2-a^3\"}");
  CHECK(!has(c, "a**(3/2)"), "#4 不得把 a³ 误判为完全平方");
}

// ── #5 记号 ─────────────────────────────────────────────────────────────────

void test_no_machine_notation() {
  const std::string r = call("extrema_sym", "{\"expr\":\"a*x^3-x\"}");
  CHECK(!has(r, "**(-1)"), "#5 输出中不得出现负指数 **(-1)");
  CHECK(!has(r, "**(-1/2)"), "#5 输出中不得出现负指数 **(-1/2)");
  CHECK(!has(r, "zoo"), "#5 不得外泄 zoo（复无穷）");
  CHECK(!has(r, "sqrt(3)*sqrt(a**(-1))"), "#5 不得外泄嵌套负指数根式");

  const std::string s = call("solve_sym", "{\"expr\":\"z^2+1\",\"var\":\"z\"}");
  // 虚数单位必须保持 I：这些字符串会被回喂给 complex_eval，SymEngine 只认 I
  CHECK(has(s, "I"), "#5 虚数单位应保持 I（可被引擎重新解析）");
  CHECK(!has(s, "\"solutions\":[\"i\""), "#5 不得把 I 排版成 i（会破坏往返解析）");

  const std::string f = call("simplify_sym", "{\"expr\":\"1/x\"}");
  CHECK(has(f, "\"simplified\":\"1/x\""), "#5 1/x 应写作分式而非 x**(-1)");
}

// ── #6 参数错误信息 ─────────────────────────────────────────────────────────

void test_arg_error_messages() {
  // 缺参数 b：一次就要说清缺什么、要什么类型、期望签名
  const std::string r = call("compare_expr", "{\"a\":\"1\"}");
  CHECK(has(r, "\"isError\":true"), "#6 缺参数应报错");
  CHECK(has(r, "缺少必填参数 b"), "#6 应点名缺失参数");
  CHECK(has(r, "应为字符串"), "#6 应说明期望类型");
  CHECK(has(r, "期望签名"), "#6 应给出期望签名");
  CHECK(has(r, "本次调用传入的参数键：a"), "#6 应回显实际传入的键");

  // 类型错：a 是数字而非字符串，要指出实际类型
  const std::string t = call("compare_expr", "{\"a\":1,\"b\":\"1\"}");
  CHECK(has(t, "类型错误"), "#6 类型不符应明确报类型错误");
  CHECK(has(t, "实际收到整数"), "#6 应报出实际收到的类型");
}

// ── 自省 ────────────────────────────────────────────────────────────────────

void test_introspection() {
  const std::string r = call("list_functions", "{}");
  CHECK(has(r, "\"count\":"), "list_functions 应返回数量");
  CHECK(has(r, "\"compare_expr\""), "list_functions 应含 compare_expr");
  CHECK(has(r, "\"intersections\""), "list_functions 应含 intersections");
  CHECK(function_exists("list_functions"), "C ABI 应能查到 list_functions");
}

// ── 定义域：导数零点存在 ≠ 它是极值点 ──────────────────────────────────────
//
// ln 是高考导数题最高频的形态（a·x−ln x、x−a·ln x、x²−a·ln x）。定义域 x>0
// 没纳入判定时，会给出"看似合理但错"的答案：按 f'' 符号报出根本不存在的极值点。

void test_extrema_domain() {
  // f = a·x − ln x（x>0），f'=0 的根 x=1/a
  const std::string r = call("extrema_sym", "{\"expr\":\"a*x-ln(x)\"}");
  CHECK(has(r, "\"domain\""), "#8 应给出定义域约束");
  CHECK(has(r, "x > 0"), "#8 应识别出 log 的真数约束 x>0");
  CHECK(branch_has(r, "a>0", "\"exists\":true"), "#8 a>0 时驻点 x=1/a 有效");
  CHECK(branch_has(r, "a>0", "\"kind\":\"minimum\""), "#8 a>0 时为极小值");
  // a=0：1/a 无定义 → 没有极值点（旧版报 degenerate）
  CHECK(branch_has(r, "a=0", "\"exists\":false"), "#8 a=0 分支驻点不存在");
  CHECK(branch_has(r, "a=0", "\"kind\":\"no-critical-point\""),
        "#8 a=0 时应为「无极值点」（驻点 1/a 无定义）");
  // a<0：x=1/a<0 不在定义域内 → 没有极值点（旧版报 minimum）
  CHECK(branch_has(r, "a<0", "\"exists\":false"), "#8 a<0 分支驻点无效");
  CHECK(branch_has(r, "a<0", "\"kind\":\"outside-domain\""),
        "#8 a<0 时应为「驻点在定义域外」");
  CHECK(!branch_has(r, "a<0", "\"kind\":\"minimum\""),
        "#8 a<0 不得再报极小值");

  // f = ln x − a·x：a<0 同样不得报极大值
  const std::string r2 = call("extrema_sym", "{\"expr\":\"ln(x)-a*x\"}");
  CHECK(branch_has(r2, "a=0", "\"kind\":\"no-critical-point\""),
        "#8 ln x−a·x 的 a=0 分支应为「无极值点」");
  CHECK(!branch_has(r2, "a<0", "\"kind\":\"maximum\""),
        "#8 ln x−a·x 的 a<0 不得报极大值");
  CHECK(branch_has(r2, "a>0", "\"kind\":\"maximum\""),
        "#8 ln x−a·x 的 a>0 分支为极大值");

  // f = x − a·ln x：a=0 时 f′≡1≠0，既无驻点、x=0 也在定义域外。
  // 引擎按更根本的原因（残差复核：驻点不满足 f′=0）给出结论；
  // 关键性质是**不得报出极值**，而不是具体归到哪一类无效原因。
  const std::string r3 = call("extrema_sym", "{\"expr\":\"x-a*ln(x)\"}");
  CHECK(branch_has(r3, "a=0", "\"exists\":false"), "#8 x−a·ln x 的 a=0 分支不得给出驻点");
  CHECK(!branch_has(r3, "a=0", "\"kind\":\"minimum\"") &&
        !branch_has(r3, "a=0", "\"kind\":\"maximum\""),
        "#8 x−a·ln x 的 a=0 分支不得报极值");
  CHECK(branch_has(r3, "a>0", "\"kind\":\"minimum\""),
        "#8 x−a·ln x 的 a>0 分支为极小值");
  CHECK(!branch_has(r3, "a<0", "\"kind\":\"maximum\""),
        "#8 x−a·ln x 的 a<0 不得报极大值");

  // f = x² − a·ln x：f''(x₀)=4 不含 a，但驻点 ±√(a/2) 依赖 a
  //   旧版因"只看 f2 判定是否需要分支"而给出 branches: [] 且把负根也报成极小值
  const std::string r4 = call("extrema_sym", "{\"expr\":\"x^2-a*ln(x)\"}");
  CHECK(has(r4, "\"branches\""), "#8 x²−a·ln x 必须给出参数分支");
  CHECK(!has(r4, "\"branches\":[]"), "#8 分支数组不得为空");
  CHECK(branch_has(r4, "a>0", "\"kind\":\"outside-domain\""),
        "#8 x²−a·ln x 的负根分支应为「驻点在定义域外」");
  CHECK(branch_has(r4, "a>0", "\"kind\":\"minimum\""),
        "#8 x²−a·ln x 的正根分支为极小值");
  CHECK(branch_has(r4, "a<0", "\"kind\":\"no-critical-point\""),
        "#8 x²−a·ln x 在 a<0 时驻点非实 → 无极值点");

  // 无定义域约束时的行为必须保持不变（不得因这次改动而误报 outside-domain）
  const std::string r5 = call("extrema_sym", "{\"expr\":\"x^3-3*a*x\"}");
  CHECK(has(r5, "\"domain\":[]"), "#8 多项式应无定义域约束");
  CHECK(branch_has(r5, "a>0", "\"exists\":true"), "#8 多项式分支不受影响");
  CHECK(branch_has(r5, "a>0", "\"kind\":\"maximum\""), "#8 x³−3ax 的 a>0 分支为极大值");
  // 注意：valueFieldNote 里本身会提到 outside-domain，故只能匹配字段值形式
  CHECK(!has(r5, "\"kind\":\"outside-domain\""),
        "#8 无定义域约束时不得出现 outside-domain");

  // 分母约束：1/x 要求 x≠0
  const std::string r6 = call("extrema_sym", "{\"expr\":\"x+a/x\"}");
  CHECK(has(r6, "≠ 0"), "#8 应识别出分母约束 x≠0");

  // 残差复核：SymEngine::solve 偶尔给出未化简/只在个别参数下成立的根，
  // 必须复核 f'(x₀)=0，否则会凭空报出驻点及其极值类型。
  //   f = a·x + atan(x)，真实驻点 ±√(−(1+a)/a)，求解器返回的表达式在
  //   a = −1 时恰好正确、a = −2 时不成立 → 必须在分支内多值取样才能暴露。
  const std::string r7 = call("extrema_sym", "{\"expr\":\"a*x+atan(x)\"}");
  CHECK(branch_has(r7, "a>0", "\"kind\":\"no-critical-point\""),
        "#8 a·x+atan(x) 在 a>0 时 f′>0 恒成立 → 无极值点");
  CHECK(!branch_has(r7, "a<0", "\"kind\":\"minimum\"") &&
        !branch_has(r7, "a<0", "\"kind\":\"maximum\""),
        "#8 a·x+atan(x) 在 a<0 不得报极值（结论随 a 细分而变）");
  CHECK(branch_has(r7, "a<0", "\"uniform\":false") ||
        branch_has(r7, "a<0", "\"kind\":\"conditional-within-branch\"") ||
        branch_has(r7, "a<0", "\"kind\":\"solver-unreliable\""),
        "#8 a<0 内结论不唯一时应显式标注，而不是二选一");

  // f = a/x − x：a=0 时 f′ = −1 ≠ 0，求解器仍返回 ±√(−a) → 必须判为不可信
  const std::string r8 = call("extrema_sym", "{\"expr\":\"a/x-x\"}");
  CHECK(branch_has(r8, "a=0", "\"exists\":false"), "#8 a/x−x 的 a=0 分支不得给出驻点");
  CHECK(branch_has(r8, "a<0", "\"exists\":true"), "#8 a/x−x 的 a<0 分支驻点有效");
}

// ── 求解可达性：换元降次与数值回退 ─────────────────────────────────────────
//
// SymEngine::solve 对含 sqrt/tan/exp 的方程会栈溢出或静默返回空集，
// 于是这三类高频形态原本一律报错。现在按三级策略处理，且**每一级都如实标注**：
//   ① symbolic          多项式/有理式/log/atan
//   ② substitution-*    换元 t=√g、t=tan g（仍是精确解）
//   ③ numeric           数值扫描（正确但非精确，必须可辨认）

void test_solve_reachability() {
  // ① 换元 t=√x：a·√x − x 的驻点是 x = a²/4
  const std::string sq = call("extrema_sym", "{\"expr\":\"a*sqrt(x)-x\"}");
  // 单根式现在由更强的"根式消元"处理（也能给出 a²/4），换元作为其后续手段
  CHECK(has(sq, "\"solveMethod\":\"substitution-sqrt\"") ||
        has(sq, "\"solveMethod\":\"elimination-radical\""),
        "#9 √ 形态应走换元/消元而非数值");
  CHECK(has(sq, "a**2"), "#9 换元后应给出精确驻点 a²/4");
  CHECK(!has(sq, "\"solveMethod\":\"numeric\""), "#9 不该退化成数值");

  // ② 换元 t=tan x：a·x + tan x 的驻点是 atan(±√(−(1+a)))
  const std::string tn = call("extrema_sym", "{\"expr\":\"a*x+tan(x)\"}");
  CHECK(has(tn, "\"solveMethod\":\"substitution-tan\""), "#9 tan 形态应走换元降次");
  CHECK(has(tn, "atan("), "#9 换元后应给出 atan 形式的精确驻点");

  // ③ 数值回退：exp 形态无法换元，但可数值求驻点
  const std::string nm = call("extrema_sym", "{\"expr\":\"exp(x)-2*x\"}");
  CHECK(has(nm, "\"solveMethod\":\"numeric\""), "#9 exp 形态应回退为数值");
  CHECK(has(nm, "0.693147"), "#9 exp(x)-2x 的驻点应为 ln2");
  CHECK(has(nm, "\"solveNote\""), "#9 数值结果必须附带说明（非精确解）");

  // ④ 相切零点（f′ 只在一点触碰 0、不变号）也要能找到
  const std::string tg = call("extrema_sym", "{\"expr\":\"sinh(x)-x\"}");
  CHECK(has(tg, "\"solveMethod\":\"numeric\""), "#9 sinh(x)−x 应回退为数值");
  CHECK(has(tg, "\"critical_points\":[\"0\"]"), "#9 sinh(x)−x 的驻点应为 0（相切零点）");

  // ⑤ 不能因为"数值很小"就把整段采样点都当成根
  //    （x·eˣ 在负半轴整段都极小，曾一度产出 8001 个假根）
  const std::string xe = call("extrema_sym", "{\"expr\":\"x*exp(x)\"}");
  CHECK(has(xe, "\"critical_points\":[\"-1\"]"), "#9 x·eˣ 只应在 x = −1 有驻点");

  // ⑥ f′ 恒不为 0 时应报告"未发现驻点"而不是伪造结论
  const std::string no = call("extrema_sym", "{\"expr\":\"1/x\"}");
  CHECK(has(no, "\"critical_points\":[]"), "#9 1/x 不应给出驻点");
  CHECK(has(no, "\"solveMethod\":\"numeric\""), "#9 并说明结论来自数值扫描");
  CHECK(has(no, "不是完备判定"), "#9 数值扫描的局限必须写明");

  // ⑦ 特殊函数的定义域约束必须体现在领域模型里
  //    （补上 Γ/ψ 的双精度求值后 gamma 已可求解，见 ⑪ 的用例）
  const std::string gm = call("extrema_sym", "{\"expr\":\"gamma(x)\"}");
  CHECK(has(gm, "\"domain\""), "#9 应给出 Gamma 的定义域约束");
  CHECK(has(gm, "∉ {0,−1,−2,…}"), "#9 Gamma 应排除 0 与负整数");

  // ⑧ 多根式：隔离-平方逐次消元（√x+√(1−x) 的驻点是 x = 1/2）
  const std::string mr = call("extrema_sym", "{\"expr\":\"sqrt(x)+sqrt(1-x)\"}");
  CHECK(has(mr, "\"solveMethod\":\"elimination-radical\""), "#9 多根式应走消元");
  CHECK(has(mr, "\"critical_points\":[\"1/2\"]"), "#9 √x+√(1−x) 的驻点应为 1/2");

  // ⑨ 扫描区间可配置：同一函数在不同区间下的结论应一致
  const std::string rg = call("extrema_sym", "{\"expr\":\"x*erf(x)\",\"xmin\":-1,\"xmax\":1}");
  CHECK(has(rg, "\"critical_points\":[\"0\""), "#9 自定义区间下应有驻点 0");
  const std::string bad = call("extrema_sym", "{\"expr\":\"x\",\"xmin\":5,\"xmax\":1}");
  CHECK(has(bad, "xmax 必须大于 xmin"), "#9 区间非法应明确报错");

  // ⑩ 参数代入：含参且导数非有理时，给出参数值即可数值求解
  const std::string pv = call("extrema_sym", "{\"expr\":\"a*x+exp(x)\",\"vars\":{\"a\":-3}}");
  CHECK(has(pv, "\"solveMethod\":\"numeric\""), "#9 代参后应能数值求解");
  CHECK(has(pv, "1.098612"), "#9 a=-3 时驻点应为 ln 3");

  // ⑪ 特殊函数：SymEngine 的 eval_double 不支持 Γ/ψ，靠增强求值补上
  const std::string gm2 = call("extrema_sym", "{\"expr\":\"gamma(x)\"}");
  CHECK(has(gm2, "\"solveMethod\":\"numeric\""), "#9 Γ 应能数值求值");
  CHECK(has(gm2, "1.461632"), "#9 Γ 的极小点应在 x ≈ 1.46163");
  CHECK(has(gm2, "\"kind\":\"minimum\""), "#9 Γ 在该点应为极小值（而非 no-real-value）");

  // ⑫ 原有精确路径不受影响
  const std::string ok = call("extrema_sym", "{\"expr\":\"a*x-ln(x)\"}");
  CHECK(has(ok, "\"solveMethod\":\"symbolic\""), "#9 有理导数应仍走精确符号求解");
}


// ── 特殊函数数值实现 ────────────────────────────────────────────────────────
//
// SymEngine 的 eval_double 对 Γ/ψ/ζ/W 没有实现，这些函数一度"一个采样点都算不出来"。
// 补上后必须逐条对已知值核验——数值实现最容易出现"看起来对"的偏差，
// 尤其是 ζ 在 0<s<1 的抵消误差、ψ⁽ⁿ⁾ 在负半轴的递推、W₋₁ 的分支。

void test_special_numeric() {
  const double pi = 3.14159265358979323846;
  const auto near = [](double a, double b, double tol) {
    return std::fabs(a - b) <= tol;
  };

  CHECK(near(mf::num::zeta_real(2.0), pi * pi / 6.0, 1e-12), "#10 zeta(2) = pi^2/6");
  CHECK(near(mf::num::zeta_real(-1.0), -1.0 / 12.0, 1e-12), "#10 zeta(-1) = -1/12");
  CHECK(near(mf::num::zeta_real(0.0), -0.5, 1e-12), "#10 zeta(0) = -1/2");
  // 0<s<1 曾因函数方程自我递归而爆栈（1-s 仍落在 (0,1)），这里钉住
  CHECK(near(mf::num::zeta_real(0.5), -1.4603545088, 1e-9), "#10 zeta(0.5) = -1.4603545088");
  CHECK(std::isnan(mf::num::zeta_real(1.0)), "#10 zeta(1) 极点应不可求值");

  CHECK(near(mf::num::gamma_real(0.5), std::sqrt(pi), 1e-12), "#10 Gamma(1/2) = sqrt(pi)");
  CHECK(near(mf::num::gamma_real(5.0), 24.0, 1e-9), "#10 Gamma(5) = 24");
  CHECK(std::isnan(mf::num::gamma_real(-2.0)), "#10 Gamma(-2) 极点应不可求值");
  CHECK(near(mf::num::gamma_real(-0.5), -2.0 * std::sqrt(pi), 1e-9),
        "#10 Gamma(-1/2) = -2sqrt(pi)");

  CHECK(near(mf::num::digamma_real(1.0), -0.5772156649015329, 1e-12), "#10 psi(1) = -gamma");
  CHECK(near(mf::num::polygamma_real(1, 1.5), pi * pi / 2.0 - 4.0, 1e-10),
        "#10 psi'(3/2) = pi^2/2 - 4");
  // 负半轴走递推（此前直接返回 NaN）
  CHECK(near(mf::num::polygamma_real(1, -0.5), pi * pi / 2.0 + 4.0, 1e-10),
        "#10 psi'(-1/2) = pi^2/2 + 4");
  CHECK(near(mf::num::polygamma_real(1, 0.5), pi * pi / 2.0, 1e-10), "#10 psi'(1/2) = pi^2/2");

  CHECK(near(mf::num::lambertw0_real(1.0), 0.5671432904097838, 1e-12),
        "#10 W0(1) = 0.5671432904");
  CHECK(near(mf::num::lambertw_m1_real(-0.1), -3.5771520639572972, 1e-9),
        "#10 W-1(-0.1) = -3.5771520640");
  CHECK(std::isnan(mf::num::lambertw_m1_real(0.1)), "#10 W-1 在 x>0 上无实值");
  CHECK(std::isnan(mf::num::lambertw0_real(-1.0)), "#10 W0 在 x<-1/e 上无实值");
}

// ── 求解可达性（第二轮）：不求值导数、负半轴 psi、多分支 W ─────────────────

void test_special_function_solving() {
  // zeta'(x) 在 SymEngine 里是不求值的 Derivative 节点；必须在**替换前**做数值微分，
  // 因为替换会把求导变量换成常数（Subs(Derivative(...), (x), (0.5))）。
  const std::string z = call("extrema_sym", "{\"expr\":\"zeta(x)\"}");
  CHECK(has(z, "\"solveMethod\":\"numeric\""), "#11 zeta 应能数值求解");
  CHECK(has(z, "-2.717"), "#11 zeta 在平凡零点之间应有极值点（-2.717...）");
  CHECK(has(z, "-19.403"), "#11 且应覆盖到区间左端附近的极值点");

  // psi^(n) 在负半轴可求值 -> 定义域内不再"整段算不出来"
  const std::string pg = call("extrema_sym", "{\"expr\":\"polygamma(1,x)\"}");
  CHECK(has(pg, "\"solveMethod\":\"numeric\""), "#11 psi' 应能数值求值");
  CHECK(has(pg, "\"critical_points\":[]"), "#11 psi'(x) 在定义域内恒正 -> 无极值点");
  CHECK(has(pg, "最小值为"), "#11 无根时应报告区间内 |f'| 的最小值供判断");

  // W0 严格递增 -> 无极值点
  const std::string w = call("extrema_sym", "{\"expr\":\"lambertw(x)\"}");
  CHECK(has(w, "\"critical_points\":[]"), "#11 W0 严格递增 -> 无极值点");
}


// ── 自变量取值不得静默默认为 0 ──────────────────────────────────────────────
//
// expr_eval_vars 旧实现只认键 "x" 且缺省取 0.0，于是 {"values":[2]} 这类写法
// 被忽略、含自变量却漏传取值时也照样算出结果——返回一个"看起来正常"的错值。
// 现在：取值必须有来源；只有表达式确实不含该变量时才允许缺省。

void test_eval_vars_no_silent_default() {
  // values 数组必须生效（曾返回 a*0=0）
  const std::string v1 = call("expr_eval_vars", "{\"expr\":\"a*x\",\"vars\":{\"a\":3},\"values\":[2]}");
  CHECK(has(v1, "\"value\":6"), "#12 values 数组应作为自变量取值（a*x, a=3, x=2 → 6）");
  // 兼容写法：与自变量同名的键
  const std::string v2 = call("expr_eval_vars",
                              "{\"expr\":\"a*x\",\"vars\":{\"a\":3},\"var\":\"x\",\"x\":2}");
  CHECK(has(v2, "\"value\":6"), "#12 同名键应作为自变量取值");
  const std::string v3 = call("expr_eval_vars",
                              "{\"expr\":\"a*t\",\"vars\":{\"a\":3},\"var\":\"t\",\"t\":2}");
  CHECK(has(v3, "\"value\":6"), "#12 var=t 时键 t 应生效");
  // 含自变量却漏传 → 必须报错，不得按 0 代入
  const std::string v4 = call("expr_eval_vars", "{\"expr\":\"a*x\",\"vars\":{\"a\":3}}");
  CHECK(has(v4, "\"isError\":true"), "#12 含自变量却漏传取值应报错");
  CHECK(has(v4, "未提供自变量 x 的值"), "#12 报错要点明缺哪个自变量");
  CHECK(!has(v4, "\"value\":0"), "#12 绝不能静默返回按 0 代入的结果");
  // 表达式不含该变量时，缺省 0 无害，不应报错
  const std::string v5 = call("expr_eval_vars", "{\"expr\":\"a*2\",\"vars\":{\"a\":3}}");
  CHECK(has(v5, "\"value\":6"), "#12 不含自变量时缺省不应报错");
}


// ── 课本写法输入 ────────────────────────────────────────────────────────────
//
// 旧解析器只认程序员语法：cosx、2x、x^2、pi、√x、|x|、lnx 全部失败
// （2x/x^2 报"多余字符"，cosx 被当成未定义变量）。这里把每一类都钉住，
// 防止将来回到"只认 ** 不认 ^"的状态。

void test_textbook_notation() {
  // 函数名后无括号、无空格（用户报的那一类）
  CHECK(has(call("expr_eval", "{\"expr\":\"cosx\",\"x\":1}"), "0.5403023"), "#13 cosx → cos(x)");
  CHECK(has(call("expr_eval", "{\"expr\":\"sinx\",\"x\":1}"), "0.8414709"), "#13 sinx → sin(x)");
  CHECK(has(call("expr_eval", "{\"expr\":\"lnx\",\"x\":2}"), "0.6931471"), "#13 lnx → ln(x)");
  CHECK(has(call("expr_eval", "{\"expr\":\"ctgx\",\"x\":1}"), "0.6420926"), "#13 ctgx → cot(x)（教材别名）");
  CHECK(has(call("expr_eval", "{\"expr\":\"arcsinx\",\"x\":0.5}"), "0.5235987"),
        "#13 arcsinx → asin(x)");
  CHECK(has(call("expr_eval", "{\"expr\":\"sin2x\",\"x\":0.5}"), "0.8414709"), "#13 sin2x → sin(2x)");
  CHECK(has(call("expr_eval", "{\"expr\":\"sin^2x\",\"x\":1}"), "0.7080734"),
        "#13 sin^2x → (sin x)²（教材记法）");
  CHECK(has(call("expr_eval", "{\"expr\":\"sin x\",\"x\":1}"), "0.8414709"),
        "#13 函数名与实参之间有空格也可以");

  // 隐式乘法与幂
  CHECK(has(call("expr_eval", "{\"expr\":\"2x\",\"x\":3}"), "\"value\":6"), "#13 2x → 2*x");
  CHECK(has(call("expr_eval", "{\"expr\":\"(x+1)(x-1)\",\"x\":3}"), "\"value\":8"),
        "#13 (x+1)(x-1) → 乘法");
  CHECK(has(call("expr_eval", "{\"expr\":\"x^2\",\"x\":3}"), "\"value\":9"), "#13 ^ 与 ** 等价");
  CHECK(has(call("expr_eval", "{\"expr\":\"x**2\",\"x\":3}"), "\"value\":9"), "#13 ** 仍然可用");

  // 连写字母＝单字母相乘（用户报：xe 被当成变量名）
  CHECK(has(call("expr_eval", "{\"expr\":\"xe\",\"x\":2}"), "5.4365636"),
        "#13 xe → x·e（e 是自然常数，不是变量名 xe）");
  CHECK(has(call("prepare_expr", "{\"expr\":\"xy\"}"), "\"normalized\":\"x*y\""),
        "#13 xy → x*y（规范化结果里已经是显式乘法）");
  CHECK(has(call("diff", "{\"expr\":\"xe^x - ax + b\",\"var\":\"x\"}"), "exp(x)"),
        "#13 d/dx(xe^x−ax+b) 必须含 exp(x)（曾输出 xe**x*log(xe)）");
  CHECK(!has(call("diff", "{\"expr\":\"xe^x - ax + b\",\"var\":\"x\"}"), "log(xe)"),
        "#13 且不得再把 xe 当整体");
  // 但不能把已知名字拆坏
  CHECK(has(call("expr_eval", "{\"expr\":\"pi\",\"x\":1}"), "3.1415926"), "#13 pi 仍是圆周率");
  CHECK(has(call("diff", "{\"expr\":\"theta*x\",\"var\":\"theta\"}"), "\"value\":\"x\""),
        "#13 theta 仍是单个变量名（不被拆成 t*h*e*t*a）");
  CHECK(has(call("expr_eval", "{\"expr\":\"oo\",\"x\":1}"), "isError"),
        "#13 oo 不会被拆成 o*o");
  CHECK(has(call("expr_eval", "{\"expr\":\"2 - 3\",\"x\":1}"), "\"value\":-1"),
        "#13 减号不会被当成隐式乘法的负因子");

  // 常量与 Unicode
  CHECK(has(call("expr_eval", "{\"expr\":\"pi\",\"x\":1}"), "3.1415926"), "#13 pi 是圆周率");
  CHECK(has(call("expr_eval", "{\"expr\":\"2pi\",\"x\":1}"), "6.2831853"), "#13 2pi → 2π");
  CHECK(has(call("expr_eval", "{\"expr\":\"e\",\"x\":1}"), "2.7182818"), "#13 e 是自然对数底");
  CHECK(has(call("expr_eval", "{\"expr\":\"e^x\",\"x\":1}"), "2.7182818"), "#13 e^x");
  // √ 是 UTF-8 多字节：char 有符号时与 0xE2 直接比较会失配，这里钉住
  {
    const std::string sq = std::string("{\"expr\":\"\\u221A4\",\"x\":1}");
    CHECK(has(call("expr_eval", sq), "\"value\":2"), "#13 √4 → sqrt(4)");
    const std::string sq2 = std::string("{\"expr\":\"3\\u221Ax\",\"x\":4}");
    CHECK(has(call("expr_eval", sq2), "\"value\":6"), "#13 3√x → 3*sqrt(x)");
  }
  CHECK(has(call("expr_eval", "{\"expr\":\"|-3|\",\"x\":1}"), "\"value\":3"), "#13 |x| 绝对值");
  CHECK(has(call("expr_eval", "{\"expr\":\"2|x|\",\"x\":3}"), "\"value\":6"),
        "#13 2|x| 隐式乘法与绝对值共存");
  CHECK(has(call("expr_eval", "{\"expr\":\"x\\u00B2\",\"x\":3}"), "\"value\":9"),
        "#13 x² 上标字符 → x^2");

  // 全角字符（中文输入法下极易带出来）
  CHECK(has(call("expr_eval", "{\"expr\":\"\\uFF082x\\uFF09\",\"x\":3}"), "\"value\":6"),
        "#13 全角括号/字母可解析");

  // LaTeX 输入
  CHECK(has(call("prepare_expr", "{\"expr\":\"\\\\frac{1}{2}\"}"),
            "\\frac{1}{2}"),
        "#13 \\frac{1}{2} 可用且回显为分数");
  CHECK(has(call("prepare_expr", "{\"expr\":\"\\\\sqrt{x}\"}"), "\\\\sqrt{x}"),
        "#13 \\sqrt{x} 可用");
  CHECK(has(call("prepare_expr", "{\"expr\":\"x^2+1\"}"), "x^{2} + 1"),
        "#13 LaTeX 预览形状正确（曾经因读错 op 字段整段丢失）");
  CHECK(has(call("prepare_expr", "{\"expr\":\"2x\"}"), "2 \\\\cdot x"),
        "#13 隐式乘法在预览里显示为 \\cdot");

  // 未知写法要如实报错，不能静默给错值
  CHECK(has(call("expr_eval", "{\"expr\":\"foobar\",\"x\":1}"), "isError"),
        "#13 未知标识符应报错");
  CHECK(has(call("expr_eval", "{\"expr\":\"sin(\",\"x\":1}"), "isError"),
        "#13 括号不匹配应报错");
}

}  // namespace

int main() {
  std::system("chcp 65001 > nul");
  std::printf("===== 符号 API 契约测试 =====\n");

  test_intersections_realness();
  test_extrema_field_semantics();
  test_simplify_chooses_best();
  test_factor_sym_radicals();
  test_no_machine_notation();
  test_arg_error_messages();
  test_introspection();
  test_extrema_domain();
  test_solve_reachability();
  test_special_numeric();
  test_special_function_solving();
  test_eval_vars_no_silent_default();
  test_textbook_notation();

  std::printf("\n%d 项检查,%d 项失败\n", g_checks, g_failures);
  return g_failures == 0 ? 0 : 1;
}
