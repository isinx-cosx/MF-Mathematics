// 一次性探针：隐式乘法支持情况（通过 prepare_expr 看引擎到底解析成什么）
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { PROBE, requirePath } from "./engine-paths.mjs";

/* 树外路径统一由 engine-paths.mjs 解析（BUGS.md B8）——这里原来写死的是
 * `Desktop/cppcshap` 那棵**另一棵树**里的 probe_call.exe。 */
requirePath(PROBE, "引擎探针 probe_call.exe（probe-implicit 用它直接看引擎的解析结果）", "MF_PROBE_EXE");
const tmp = path.join(os.tmpdir(), "implicit.json");

const cases = [
  // 基础：数字 × 变量/函数/括号
  "2x", "2 x", "2π", "2pi", "3sin(x)", "2sinx", "2sqrt(x)", "2|x|", "2(x+1)", "2 x^2",
  // 括号 × 括号 / 括号 × 函数
  "(x+1)(x-1)", "(x+1)(x+2)(x+3)", "(x+1)sin(x)", "sin(x)(x+1)", "(x+1)sqrt(x)",
  // 变量 × 括号/函数/根式
  "x(x+1)", "x sin(x)", "xsin(x)", "xsqrt(x)", "xy", "xyz", "x|x|",
  // 函数 × 函数
  "sin(x)cos(x)", "sinx cosx", "sinxcosx", "e^x cos(x)",
  // 指数/根式相连
  "2e^x", "e^x(x+1)", "sqrt(x)y", "√x y", "x^2y", "2^x y",
  // 分数相连
  "1/2x", "1/2 x", "(1/2)x", "x/2y", "1/(2x)",
  // LaTeX 风格
  "\\frac{1}{2}x", "\\frac{1}{2}\\sqrt{x}", "2\\pi", "\\sin x\\cos x", "(x+1)(x-1)",
  // 数字 × 数字（应当拒绝或按小数处理）
  "2 3", "2.5x", "2(3)",
  // 常见写法
  "2x^2+3x-1", "sin2x", "cos2x", "tan3x", "ln2x", "e2x",
];

function call(fn, args) {
  fs.writeFileSync(tmp, JSON.stringify(args), "utf8");
  try {
    return JSON.parse(execFileSync(PROBE, [fn, `@${tmp}`], { encoding: "utf8", timeout: 10000 }));
  } catch (e) {
    return { isError: true, value: "进程异常: " + (e.status ?? e.message) };
  }
}

let ok = 0, bad = 0;
for (const c of cases) {
  const r = call("prepare_expr", { expr: c });
  if (r.isError) {
    bad++;
    console.log(`  [失败] ${JSON.stringify(c).padEnd(24)} ${String(r.value).slice(0, 80)}`);
    continue;
  }
  const v = r.value;
  if (!v.ok) {
    bad++;
    console.log(`  [失败] ${JSON.stringify(c).padEnd(24)} ${String(v.error || "").slice(0, 80)}`);
    continue;
  }
  // 再看它解析成什么（用 sym_latex 反查规范化结果）
  const l = call("sym_latex", { expr: v.normalized });
  const norm = v.normalized;
  const latex = l.isError ? "?" : (l.value.latex || l.value.error || "");
  ok++;
  console.log(`  [通过] ${JSON.stringify(c).padEnd(24)} → ${String(norm).padEnd(22)} latex=${latex}`);
}
console.log(`\n通过 ${ok} / 失败 ${bad}（共 ${cases.length}）`);
