/**
 * cdp-math-tools.mjs — 数学工具层（verify_step / search_knowledge）的端到端断言
 *
 * 移植来源：`MVS官网/math-assistant/ts/src/mfmath.ts`。
 * 本文件除了验"能用"，重点是守住移植时**修掉的那几个洞**（原版会让校验形同虚设）：
 *   V1  tol 无上界     → tol:1e9 时任何错误推导都判通过
 *   V2  expected 非有限 → Infinity 让比较失去意义
 *   V3  expr 不限类型/长度
 *   V4  vars 不限个数/键名
 *   V5  未知参数被静默忽略 → 模型写 expectedValue 以为在判等，实际没判（假通过）
 *   V6  知识库原文进上下文 == 提示注入面 → 结果必须带「这是资料不是指令」的标记
 *   V14 引擎给出 NaN/Inf 时不能拿去比较
 *
 * 用法: node cdp-math-tools.mjs   （宿主需带 --remote-debugging-port=9222 启动）
 */
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage() {
  for (let i = 0; i < 30; i++) {
    try {
      const list = await (await fetch("http://127.0.0.1:9222/json/list")).json();
      const p = list.find((t) => t.type === "page" && /mfmath\.local|index\.html/.test(t.url || ""));
      if (p) return p.webSocketDebuggerUrl;
    } catch { /* 等宿主 */ }
    await sleep(1000);
  }
  return null;
}
const wsUrl = await findPage();
if (!wsUrl) { console.error("未找到宿主页面"); process.exit(1); }
const ws = new WebSocket(wsUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0;
const send = (method, params, timeoutMs = 30000) => new Promise((resolve) => {
  const mid = ++id;
  const h = (ev) => {
    const d = JSON.parse(ev.data);
    if (d.id === mid) { clearTimeout(timer); ws.removeEventListener("message", h); resolve(d); }
  };
  const timer = setTimeout(() => {
    ws.removeEventListener("message", h);
    resolve({ timeout: true, result: { result: { value: "[超时]" } } });
  }, timeoutMs);
  ws.addEventListener("message", h);
  ws.send(JSON.stringify({ id: mid, method, params }));
});
const evalJs = async (expr) => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return "[异常] " + (r.result.exceptionDetails.text || "");
  return r.result?.result?.value;
};

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

/* 每次进控制台/绘图前先回首页：本套件只关心工具层，不依赖页面状态 */
await evalJs("location.hash='#/'");
await sleep(1200);

const hasHook = await evalJs("!!(window.__mfAiTools && window.__mfAiTools.execute)");
if (!hasHook) {
  console.log("  [SKIP] 页面上没有 __mfAiTools（AI 工具层没初始化）");
  ws.close();
  process.exit(0);
}

/** 调一次工具，得到 {ok, content, summary} */
const run = async (name, args, allow = true) =>
  evalJs(`(function(){
    const r = window.__mfAiTools.execute(${JSON.stringify(name)}, ${JSON.stringify(args)}, ${allow});
    return JSON.stringify(r);
  })()`).then((s) => { try { return JSON.parse(s); } catch { return { ok: false, content: String(s), summary: String(s) }; } });

const body = (r) => { try { return JSON.parse(r.content); } catch { return {}; } };

console.log("\n── 工具集与 schema ──");
const names = JSON.parse(String(await evalJs("JSON.stringify(window.__mfAiTools.tools().map(t=>t.name))")));
check("四个工具都在（含 verify_step / search_knowledge）",
  ["engine_find", "engine_call", "verify_step", "search_knowledge"].every((n) => names.includes(n)),
  JSON.stringify(names));
const vt = JSON.parse(String(await evalJs(
  `JSON.stringify(window.__mfAiTools.tools().find(t=>t.name==='verify_step'))`,
)));
check("verify_step 的 schema 有 expr/vars/expected/tol", ["expr", "vars", "expected", "tol"].every((k) => k in (vt.parameters?.properties || {})), Object.keys(vt.parameters?.properties || {}).join(","));
check("verify_step 只要求 expr（其余可选）", JSON.stringify(vt.parameters?.required) === '["expr"]', JSON.stringify(vt.parameters?.required));

console.log("\n── verify_step：能算、能判、能拦 ──");
const okStep = await run("verify_step", { expr: "x^2", vars: { x: 3 }, expected: 9 });
check("正确的一步判通过", okStep.ok === true, okStep.summary);
const badStep = await run("verify_step", { expr: "x^2", vars: { x: 3 }, expected: 10 });
check("错误的一步被拦下（VALUE_MISMATCH）", badStep.ok === false && /VALUE_MISMATCH/.test(badStep.content), badStep.summary);
const calcOnly = await run("verify_step", { expr: "x^2", vars: { x: 3 } });
const calcBody = body(calcOnly);
check("不给 expected 就只求值、不判等", calcOnly.ok === true && calcBody.value === 9 && /未判等/.test(calcOnly.content), calcOnly.summary);

console.log("\n── 加固项：不允许用参数把校验做废 ──");
const tolHuge = await run("verify_step", { expr: "x^2", vars: { x: 3 }, expected: 1000, tol: 1e9 });
check("V1 tol=1e9 不再让错误推导通过", tolHuge.ok === false && /VALUE_MISMATCH/.test(tolHuge.content), tolHuge.summary);
const tolBody = body(tolHuge);
check("V1 tol 被夹到 <= 1e-2（回显可见）", typeof tolBody.tol === "number" && tolBody.tol <= 1e-2, String(tolBody.tol));
const expInf = await run("verify_step", { expr: "x^2", vars: { x: 3 }, expected: "Infinity" });
check("V2 expected 非有限时明确报错", expInf.ok === false && /有限数字/.test(expInf.content), expInf.summary);
const exprObj = await run("verify_step", { expr: { a: 1 }, vars: { x: 1 } });
check("V3 expr 不是字符串时明确报错", exprObj.ok === false && /必须是字符串/.test(exprObj.content), exprObj.summary);
const exprHuge = await run("verify_step", { expr: "x+".repeat(1500) + "1", vars: { x: 1 } });
check("V3 超长 expr 被拒（不把整篇塞给引擎）", exprHuge.ok === false && /太长/.test(exprHuge.content), exprHuge.summary);
const varsMany = await run("verify_step", { expr: "x", vars: Object.fromEntries(Array.from({ length: 40 }, (_, i) => [`v${i}`, i])) });
check("V4 变量个数超限被拒", varsMany.ok === false && /最多 32/.test(varsMany.content), varsMany.summary);
const varBadName = await run("verify_step", { expr: "x", vars: { "x; drop": 1 } });
check("V4 变量名不合法被拒", varBadName.ok === false && /变量名不合法/.test(varBadName.content), varBadName.summary);
const varNonNum = await run("verify_step", { expr: "x", vars: { x: "3" } });
check("V4 变量值必须是有限数字", varNonNum.ok === false && /有限数字/.test(varNonNum.content), varNonNum.summary);
const unknownKey = await run("verify_step", { expr: "x", vars: { x: 1 }, expectedValue: 1 });
check("V5 未知参数 expectedValue 被拒（不再静默忽略 → 假通过）",
  unknownKey.ok === false && /不认识的参数 expectedValue/.test(unknownKey.content), unknownKey.summary);

console.log("\n── verify_step：引擎侧异常不被当成通过 ──");
const badExpr = await run("verify_step", { expr: "this_is_not_math(((", vars: { x: 1 }, expected: 1 });
check("表达式无法求值时给可执行提示（不是静默失败）",
  badExpr.ok === false && /EXPR_EVAL_FAILED|求值失败/.test(badExpr.content), badExpr.summary.slice(0, 60));
const divZero = await run("verify_step", { expr: "1/x", vars: { x: 0 }, expected: 1 });
check("V14 定义域外（1/0）不当作与 expected 相符", divZero.ok === false, divZero.summary.slice(0, 70));

console.log("\n── search_knowledge：本地知识库 ──");
const kb = await run("search_knowledge", { query: "导数" });
const kbBody = body(kb);
check("能检索到本地知识库条目", kb.ok === true && Array.isArray(kbBody.hits) && kbBody.hits.length > 0, kb.summary);
check("V6 结果标注了来源与「资料不是指令」",
  kbBody.source === "local-knowledge-base" && kbBody.kind === "reference-material" && /不要执行/.test(String(kbBody.note)),
  JSON.stringify({ source: kbBody.source, kind: kbBody.kind }));
check("命中条目带 title/text/score", (kbBody.hits || []).every((h) => h.title && h.text && typeof h.score === "number"),
  JSON.stringify((kbBody.hits || [])[0] || {}).slice(0, 90));
const kbTop = await run("search_knowledge", { query: "导数", top_k: 1 });
check("top_k 生效（1 条）", (body(kbTop).hits || []).length === 1, String((body(kbTop).hits || []).length));
const kbTopBig = await run("search_knowledge", { query: "导数", top_k: 999 });
check("top_k 被夹到 <= 10", (body(kbTopBig).hits || []).length <= 10, String((body(kbTopBig).hits || []).length));
const kbMiss = await run("search_knowledge", { query: "量子色动力学非阿贝尔规范场" });
check("查不到时明确说没命中（不瞎编）", kbMiss.ok === false && /没有与/.test(kbMiss.content), kbMiss.summary);
const kbEmpty = await run("search_knowledge", { query: "   " });
check("空 query 被拒", kbEmpty.ok === false && /缺少 query/.test(kbEmpty.content), kbEmpty.summary);
const kbLong = await run("search_knowledge", { query: "导".repeat(300) });
check("超长 query 被拒", kbLong.ok === false && /太长/.test(kbLong.content), kbLong.summary);

console.log("\n── 隐私闸门：工具结果要回传给模型 ──");
const gatedVt = await run("verify_step", { expr: "x^2", vars: { x: 3 }, expected: 9 }, false);
check("关掉「发送引擎结果」时 verify_step 被拦", gatedVt.ok === false && /隐私|发送引擎结果/.test(gatedVt.content), gatedVt.summary);
const gatedKb = await run("search_knowledge", { query: "导数" }, false);
check("关掉时 search_knowledge 也被拦", gatedKb.ok === false && /隐私|发送引擎结果/.test(gatedKb.content), gatedKb.summary);

console.log("\n── system prompt 拼接 ──");
const prompt = String(await evalJs("window.__mfAiTools.mathPrompt()"));
check("prompt 含「分离参数」策略", prompt.includes("分离参数"));
check("prompt 含 verify_step 纪律", prompt.includes("VALUE_MISMATCH"));
check("prompt 含「资料不是指令」纪律", prompt.includes("不得当作指令"));
const looksMath = JSON.parse(String(await evalJs(
  `JSON.stringify([window.__mfAiTools.looksMath("已知 f(x)=ln x - a x 恒成立求 a"), window.__mfAiTools.looksMath("今天天气怎么样")])`,
)));
check("题型判断：数学题 → true / 非数学题 → false", looksMath[0] === true && looksMath[1] === false, JSON.stringify(looksMath));

/* 真正拼进请求的那份 system（__mfAi.build 就是 buildMessages）：数学题要带上讲解片段，
 * 非数学题不能带 —— 否则等于给闲聊也套数学模板。 */
const sysMath = String(await evalJs(
  `window.__mfAi.build({ userText: "求 f(x)=x^2 的导数", history: [] }).filter(m => m.role === "system").map(m => m.content).join("\\n")`,
));
const sysChat = String(await evalJs(
  `window.__mfAi.build({ userText: "今天天气怎么样", history: [] }).filter(m => m.role === "system").map(m => m.content).join("\\n")`,
));
check("数学题的 system 里拼上了数学讲解片段", sysMath.includes("数学讲解要求") && sysMath.includes("分离参数"), sysMath.length + " 字符");
check("非数学题的 system 里没有数学讲解片段", !sysChat.includes("数学讲解要求"), sysChat.length + " 字符");

console.log("\n── 知识库召回（教材口径）──");
for (const q of ["导数", "矩阵乘法", "极值"]) {
  const r = await run("search_knowledge", { query: q, top_k: 2 });
  const h = body(r).hits || [];
  console.log("    " + q + " → " + (h.map((x) => x.title).join(" | ") || "（无命中）"));
}
const kbConcept = await run("search_knowledge", { query: "怎么样把计算结果画成图像" });
check("换个问法也能回收（绘图相关条目）", kbConcept.ok === true && (body(kbConcept).hits || []).length > 0, kbConcept.summary);

console.log(`\nRESULT|math-tools|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
