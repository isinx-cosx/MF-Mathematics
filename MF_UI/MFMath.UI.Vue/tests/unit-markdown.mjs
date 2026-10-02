// 离线单测：markdown 解析（不需要宿主）。重点在"递归不会把自己卡死"与"注入面为零"。
import { parseMarkdown, parseInline } from "../src/lib/ai/markdown.ts";

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};
const flat = (tokens) => tokens.map((t) => (t.type === "text" ? t.text : t.type === "math" ? `$${t.tex}$` : `[${t.type}]`)).join("");

console.log("=== 行内 ===");
check("粗体", flat(parseInline("a **b** c")) === "a [strong] c");
check("斜体与删除线", flat(parseInline("a *b* ~~c~~")) === "a [em] [strike]");
check("行内代码", flat(parseInline("用 `x=1` 试试")) === "用 [code] 试试");
check("公式", flat(parseInline("取 $x^2$ 的导数")) === "取 $x^2$ 的导数");
check("占位符不当公式", flat(parseInline("行内 $...$ 与 $$...$$")) === "行内 $...$ 与 $$...$$");
check("嵌套粗体里带公式", flat(parseInline("**$x$**")) === "[strong]");

console.log("=== 递归压力（共用正则对象会导致死循环，这条就是那次 bug 的回归）===");
const t0 = Date.now();
const stress = parseInline("**粗** *斜* `码` [链](https://e.com) ~~删~~ ".repeat(200));
const ms = Date.now() - t0;
check("200 组行内记号能在 1 秒内解析完（不死循环）", ms < 1000, `${ms} ms，${stress.length} 个 token`);
const deep = parseInline("**".repeat(60) + "x" + "**".repeat(60));
check("极端嵌套也不卡死", deep.length > 0);

console.log("=== 块级 ===");
const md = parseMarkdown([
  "# 标题", "", "**粗** 文本", "", "- 甲", "- 乙", "", "1. 一", "2. 二", "",
  "| 量 | 值 |", "| --- | ---: |", "| $x$ | 1 |", "",
  "```python", "print('$不解析$')", "```", "", "> 引用", "", "---", "",
  "<img src=x onerror=alert(1)>",
].join("\n"));
const kinds = md.map((b) => b.type).join(",");
check("块类型顺序正确", kinds === "h,p,ul,ol,table,code,quote,hr,p", kinds);
const code = md.find((b) => b.type === "code");
check("代码块内容原样（含 $ 不解析）", code.text === "print('$不解析$')" && code.lang === "python", code.text);
const table = md.find((b) => b.type === "table");
check("表格表头与对齐", table.head.length === 2 && table.align[1] === "right", JSON.stringify(table.align));
check("表格单元里允许公式", table.head[0].some((t) => t.type === "math") || table.rows[0][0].some((t) => t.type === "math"));
const last = md[md.length - 1];
check("HTML 原样当文本（不会被当成结构）", last.type === "p" && last.content.every((t) => t.type === "text"), JSON.stringify(last).slice(0, 80));

console.log("=== 危险链接 ===");
check("javascript: 链接标 unsafe", parseInline("[坏](javascript:alert(1))")[0].safe === false);
check("data: 链接标 unsafe", parseInline("[坏](data:text/html,x)")[0].safe === false);
check("https 链接安全", parseInline("[好](https://example.com)")[0].safe === true);
check("图片不生成图片 token（只留文字+地址）", flat(parseInline("![图](https://e.com/a.png)")).includes("[code]"));
check("裸 img 标签只是文本", parseInline("<img src=x onerror=alert(1)>")[0].type === "text");

console.log(`RESULT|unit-markdown|${pass}|${fail}`);
process.exit(fail === 0 ? 0 : 1);
