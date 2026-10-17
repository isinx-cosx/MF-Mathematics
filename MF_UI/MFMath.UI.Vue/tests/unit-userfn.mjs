/**
 * unit-userfn.mjs —— 用户自定义函数（`f(x)=e^x`）的纯逻辑判据。
 *
 * 为什么不需要宿主：`plotMath.js` / `userFn.js` / `knownNames.js` 都不依赖引擎桥，
 * 是纯 ESM，node 直接就能跑。这条单测钉的是「展开算法」的四条正确性细节
 * （见 docs/PLAN-plot-user-functions.md §5）：
 *   ① 实参非原子要整体加括号   ② 括号要扫描配平
 *   ③ 标识符按整词匹配         ④ 循环定义要停下报错
 *
 * 跑法：node tests/unit-userfn.mjs
 */
import {
  parseExpr, resolveExpr, validate,
} from "../src/lib/plot/plotMath.js";
import {
  parseDefinition, collectDefs, expandCalls, findUndefinedCalls,
} from "../src/lib/plot/userFn.js";

let pass = 0;
let fail = 0;
function check(name, ok, detail = "") {
  if (ok) { pass++; console.log("  [OK]   " + name); }
  else { fail++; console.log("  [FAIL] " + name + (detail ? "   " + detail : "")); }
}
const j = (v) => JSON.stringify(v);

console.log("\n── ① parseDefinition：认得出定义、挡得住重定义内置名 ──");
{
  const d = parseDefinition("f(x)=x^2");
  check("f(x)=x^2 被认成定义", !!d && d.name === "f" && d.arg === "x" && d.body === "x^2", j(d));
  const bad = parseDefinition("sin(x)=x");
  check("重定义内置名报错", !!bad && !!bad.error, j(bad));
  check("多形参不当作定义（需要引擎级能力）", parseDefinition("f(x,y)=x+y") === null);
  check("普通等式不是定义", parseDefinition("y=x^2") === null);
  check("同形参同函数名报错", !!parseDefinition("f(f)=f^2")?.error);
}

console.log("\n── ② parseExpr：定义行进 definition 分支，参数不受形参污染 ──");
{
  const p = parseExpr("f(x)=e^x");
  check("来自 definition 类型", p.type === "definition", j({ type: p.type, body: p.body }));
  check("参数为空（e 是常量、x 是形参）", j(p.params) === "[]", j(p.params));
  check("带 fnName/argName 供渲染用", p.fnName === "f" && p.argName === "x", j({ f: p.fnName, a: p.argName }));
  const pa = parseExpr("f(x)=a*x^2");
  check("定义体里的自由参数进参数表", j(pa.params) === '["a"]', j(pa.params));
  // 回归：普通写法不能被误判成定义
  check("y=x^2 仍是 explicit", parseExpr("y=x^2").type === "explicit");
  check("x(x+1) 仍是 explicit（不是定义）", parseExpr("x(x+1)").type === "explicit");
  check("(cos t, sin t) 仍是参数方程", parseExpr("(cos t, sin t)").type === "parametric");
}

console.log("\n── ③ expandCalls：加括号 / 配平 / 整词 / 嵌套 ──");
{
  const defs = collectDefs(["f(x)=x^2", "g(x)=sin(x)", "h(a)=a+1"]);
  check("f(2) → (2^2)（2 是原子，不再套括号）", expandCalls("f(2)", defs).text === "(2^2)", expandCalls("f(2)", defs).text);
  const a1 = expandCalls("f(a+1)", defs).text;
  // 关键性质：代入后必须是 (a+1)^2，**不能**是 a+1^2（那等于 a+1，差得远）
  check("f(a+1) 实参整体加括号（不能是 a+1^2）", a1 === "((a+1)^2)", a1);
  const nest = expandCalls("f(g(x))", defs).text;
  check("f(g(x)) 嵌套展开且括号配平", /sin/.test(nest) && nest.startsWith("(("), nest);
  check("g(x)+1 只替换调用", expandCalls("g(x)+1", defs).text === "(sin(x))+1", expandCalls("g(x)+1", defs).text);
  check("af(x) 里的 a 不被当成形参", !/a\+1/.test(expandCalls("af(2)", { get: () => undefined, size: 1, has: () => false })?.text || ""));
  const cyc = collectDefs(["f(x)=f(x-1)"]);
  const r = expandCalls("f(3)", cyc);
  check("循环定义停下并报错（不卡死）", !!r.error && /层数过深/.test(r.error), j(r));
  check("未定义调用能被找出来", j(findUndefinedCalls("k(x)+1", defs)) === '["k"]', j(findUndefinedCalls("k(x)+1", defs)));
}

console.log("\n── ④ resolveExpr：送引擎前已展开；未定义则明确报错（不静默空白）──");
{
  const defs = collectDefs(["f(x)=x^2"]);
  const ok = resolveExpr("y=f(3)", defs);
  check("y=f(3) 展开后 body 里没有裸 f(", !/\bf\s*\(/.test(ok.body) && /\(3\^2\)/.test(ok.body), j(ok.body));
  const bad = resolveExpr("y=k(3)", defs);
  check("未定义函数 k → valid:false 且说清怎么定义",
    bad.valid === false && /未定义的函数 k/.test(bad.error), j({ v: bad.valid, e: bad.error }));
  const defRow = resolveExpr("f(x)=e^x", defs);
  check("定义行本身原样返回（不参与绘制）", defRow.type === "definition");
  check("没有定义时 resolveExpr 等价 parseExpr",
    j(resolveExpr("y=x^2")) === j(parseExpr("y=x^2")));
}

console.log("\n── ⑤ 回归：本地归一化不许动隐式乘法（1/2x 必须还是 1/(2x)）──");
{
  // plotMath.toEngineExpr 只做字面替换，不插 * —— 这条是历史教训，钉死它
  const { toEngineExpr } = await import("../src/lib/plot/plotMath.js");
  check("2x 不被插成 2*x", toEngineExpr("2x") === "2x", toEngineExpr("2x"));
  check("1/2x 不被插成 1/2*x", toEngineExpr("1/2x") === "1/2x", toEngineExpr("1/2x"));
  check("x(x+1) 不被插成 x*(x+1)", toEngineExpr("x(x+1)") === "x(x+1)", toEngineExpr("x(x+1)"));
  check("f(x) 在这一层原样保留（插号是引擎那边的事）", toEngineExpr("f(x)") === "f(x)", toEngineExpr("f(x)"));
  check("括号不匹配仍能报出来", validate("(x+1") === "括号不匹配");
  check("合法表达式 validate 返回 null", validate("(x+1)") === null);
}

console.log(`\n═══ 用户函数与解析：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|unit-userfn|${pass}|${fail}`);
process.exit(fail === 0 ? 0 : 1);
