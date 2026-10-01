// resultModel 单元测试 —— 不依赖宿主窗口，用假桥替换引擎调用
//
// 为什么单独做一个：结果渲染器的三条分支（矩阵 / 一维数组 / 对象嵌套）
// **从界面点不出来**——引擎的高斯消元返回 {rank, free_vars, type} 而不是矩阵。
// 但这些分支必须可靠，因为任何模块将来返回矩阵都会走它们。
//
// 假桥模拟真实引擎的两条实测行为（都验过）：
//   · sym_latex("该分支内结论不唯一：极大值") → ok:true、latex 原样返回中文
//     —— 所以"引擎接受了"不等于"这是数学"，必须有独立的中文闸门
//   · sym_latex 对含 '=' 的输入报 "Unknown token: '='"
//     —— 所以等式要由 equationLatex 拆开两边分别转
//
// 用法: node unit-result-model.mjs
const calls = [];

globalThis.window = {
  chrome: {
    webview: {
      hostObjects: {
        sync: {
          mf: {
            Dispatch(fn, argsJson) {
              const a = JSON.parse(argsJson);
              calls.push({ fn, expr: a.expr });
              if (fn === "sym_latex") {
                const e = String(a.expr ?? "");
                if (e.includes("=")) return JSON.stringify({ isError: false, value: { ok: false, error: "Unknown token: '='" } });
                if (/[\u4e00-\u9fff]/.test(e)) return JSON.stringify({ isError: false, value: { ok: true, latex: e } }); // 真实引擎就是这样
                if (!/^[\x20-\x7E]+$/.test(e)) return JSON.stringify({ isError: false, value: { ok: false, error: "syntax error" } }); // ≠ 之类
                // 其余一律接受 —— 真实引擎连 "symbolic" 都会接受，挡住它的责任在 isMathText
                return JSON.stringify({ isError: false, value: { ok: true, latex: "L<" + e + ">" } });
              }
              return JSON.stringify({ isError: true, value: "假桥只实现 sym_latex" });
            },
          },
        },
      },
    },
  },
};

const { toResultNodes, isMathText, PLAIN_KEYS } = await import("../src/lib/engine/resultModel.js");

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};
const kinds = (nodes) => nodes.map((n) => n.k).join(",");

/* ── ① 判定：什么算数学 ── */
console.log("── 数学 / 文字的判定 ──");
check("表达式算数学", isMathText("(x + 2)*(x - 2)"), "");
check("等式算数学（由 equationLatex 处理）", isMathText("y=2*x+1"), "");
check("纯字母不算数学（'symbolic' 不能排成 s·y·m·b·o·l·i·c）", !isMathText("symbolic"), "");
check("中文说明不算数学", !isMathText("该分支内结论不唯一：极大值"), "");
check("含中文与等号的混合文本不算数学", !isMathText("移项得 x=2"), "");
check("中文标点也要挡住", !isMathText("最小值（a>0）"), "");
check("带减号的英文取值不算数学（two-sided 会被引擎读成 two - sided）", !isMathText("two-sided"), "");
check("带数字的减法仍算数学", isMathText("x-1"), "");
check("元信息字段名直接排除（即使内容是数学样式）", !isMathText("x>0", "solveNote"), "");
check("PLAIN_KEYS 覆盖引擎实际使用的字段名", PLAIN_KEYS.has("solveMethod") && PLAIN_KEYS.has("kind") && PLAIN_KEYS.has("steps"), "");

/* ── ② 标量 ── */
console.log("\n── 标量 ──");
check("字符串表达式 → math 节点", kinds(toResultNodes("(x + 2)*(x - 2)")) === "math", kinds(toResultNodes("(x + 2)*(x - 2)")));
const eq = toResultNodes("y=2*x+1");
check("等式两侧分别转 LaTeX 再拼回", eq[0].k === "math" && eq[0].latex === "L<y> = L<2*x+1>", JSON.stringify(eq[0]));
check("数字 → num 节点", kinds(toResultNodes(3.5)) === "num", JSON.stringify(toResultNodes(3.5)));
check("布尔 → 真/假", toResultNodes(true)[0].text === "真" && toResultNodes(false)[0].text === "假", "");
check("null → 空", toResultNodes(null)[0].text === "（空）", "");

/* ── ③ 对象（含元信息与数学混排）── */
console.log("\n── 对象 ──");
const obj = toResultNodes({
  den: "x*(1 + x)",
  rank: 2,
  type: "infinite",
  solveMethod: "substitution-sqrt",
  note: "该分支内结论不唯一：极大值",
});
const o = obj[0];
check("对象 → obj 节点，字段顺序保留", o.k === "obj" && o.rows.map((r) => r.key).join(",") === "den,rank,type,solveMethod,note", o.k);
const val = (k) => o.rows.find((r) => r.key === k).value;
check("数学字段 den → math", kinds(val("den")) === "math", JSON.stringify(val("den")));
check("数字字段 rank → num", kinds(val("rank")) === "num", JSON.stringify(val("rank")));
check("元信息 solveMethod → text（不被排成数学）", kinds(val("solveMethod")) === "text", JSON.stringify(val("solveMethod")));
check("中文 note → text（哪怕引擎会原样返回它）", kinds(val("note")) === "text", JSON.stringify(val("note")));
check("普通英文短词 type → text", kinds(val("type")) === "text", JSON.stringify(val("type")));

/* ── ④ 矩阵 / 一维数组（界面点不到，只能在这里钉住）── */
console.log("\n── 矩阵 / 一维数组 ──");
const mtx = toResultNodes([[1, 2], [3, 4]]);
check("数组的数组 → table", mtx[0].k === "table", mtx[0].k);
check("矩阵是 2×2", mtx[0].rows.length === 2 && mtx[0].rows[0].length === 2, JSON.stringify(mtx[0].rows.length));
check("单元格是 num 节点", mtx[0].rows[0][0][0].k === "num" && mtx[0].rows[1][1][0].text === "4", JSON.stringify(mtx[0].rows[1][1]));
const vec = toResultNodes([1, 2, 3]);
check("一维数组 → list", vec[0].k === "list" && vec[0].items.length === 3, vec[0].k);
check("空数组 → 空", toResultNodes([])[0].text === "（空）", "");
const nested = toResultNodes({ pts: [[1, 2], [3, 4]] });
check("对象里的矩阵保持 table 结构", nested[0].rows[0].value[0].k === "table", nested[0].rows[0].value[0].k);
const mixedVec = toResultNodes(["x^2", "无解"]);
check("数组里逐个元素判定（数学/文字混排）", kinds(mixedVec[0].items[0]) === "math" && kinds(mixedVec[0].items[1]) === "text",
  JSON.stringify(mixedVec[0].items.map((n) => n[0].k)));

/* ── ⑤ 假桥确实被用到了（否则上面全是假绿）── */
console.log("\n── 桥调用 ──");
check("确实问了引擎（数学判定不是纯正则猜的）", calls.length > 0, calls.length + " 次调用");
check("等式两边都问了引擎", calls.filter((c) => c.fn === "sym_latex" && (c.expr === "y" || c.expr === "2*x+1")).length === 2,
  JSON.stringify(calls.map((c) => c.expr)));

console.log(`\n═══ resultModel 单元测试：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|unit-result-model|${pass}|${fail}`);
process.exit(fail === 0 ? 0 : 1);
