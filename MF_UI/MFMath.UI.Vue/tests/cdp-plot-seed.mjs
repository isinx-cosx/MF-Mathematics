/**
 * cdp-plot-seed.mjs — 示例任务库「加载到工作区」→ 各绘图页能不能真的接住
 *
 * 背景（BUGS.md 记录的那条）：示例库对绘图示例调了 `setPending({expr, mode})` 后跳路由，
 * 但**长期没有任何绘图页消费它** —— 表达式被静默丢掉，用户只看到默认内容。
 *
 * 现在按页面主输入分工接线，本文件逐页验：
 *   2D 绘图 → PlotPage 表达式行        （`sin(x)`）
 *   3D 绘图 → 曲面表达式                （`x^2 - y^2`）
 *   复平面  → 复变函数                  （`z^2`）
 *   向量场  → dx / dy 两个分量          （`F(x,y)=[-y, x]` 拆开）
 * 并断言：接不了的示例**不当成成功**（页面要么用上、要么明确说明），不静默吞掉。
 *
 * 用法: node cdp-plot-seed.mjs   （宿主需带 --remote-debugging-port=9222 启动）
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

/** 进示例库，点「加载到工作区」于匹配的卡片；返回点了哪张 */
async function loadExample(re) {
  await evalJs("location.hash='#/examples'");
  await sleep(1800);
  const clicked = await evalJs(`(function(){
    const cards = [...document.querySelectorAll('.ex-item, .ex-card')];
    const t = cards.find((c) => ${re}.test(c.textContent || ''));
    if (!t) return '';
    const b = [...t.querySelectorAll('button')].find((x) => /加载/.test(x.textContent || ''));
    if (!b) return '';
    b.click();
    return (t.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 40);
  })()`);
  await sleep(3200);
  return String(clicked);
}

/** 读页面上所有可见输入框的值 */
const inputValues = () => evalJs(`JSON.stringify(
  [...document.querySelectorAll('input.input, .expr-input')]
    .map((e) => String(e.value !== undefined ? e.value : e.textContent || '').trim())
    .filter((v) => v !== '')
)`).then((s) => { try { return JSON.parse(String(s)); } catch { return []; } });

const statusText = () => evalJs(`(document.querySelector('.status, .side-status') || {}).textContent || ''`);

console.log("\n── 2D 绘图 ──");
let used = await loadExample("/模式：2D 绘图/");
check("点到了「2D 函数图像」类示例", !!used, used);
check("跳到 /plot/2d", (await evalJs("location.hash")) === "#/plot/2d", String(await evalJs("location.hash")));
let vals = await inputValues();
check("表达式进了 2D 表达式行", vals.some((v) => /sin/.test(v)), JSON.stringify(vals));
check("引擎确实按示例采样了", /引擎采样\s*1\s*条曲线/.test(String(await statusText())), String(await statusText()).slice(0, 60));

console.log("\n── 3D 绘图 ──");
used = await loadExample("/模式：3D 绘图/");
check("点到了 3D 类示例", !!used, used);
check("跳到 /plot/3d", (await evalJs("location.hash")) === "#/plot/3d", String(await evalJs("location.hash")));
vals = await inputValues();
check("表达式进了 3D 曲面输入框（不是默认 sin(x)*cos(y) 被顶掉）",
  vals.some((v) => /x\^2\s*-\s*y\^2|sqrt/.test(v)), JSON.stringify(vals));

console.log("\n── 复平面 ──");
used = await loadExample("/模式：复数着色/");
check("点到了复数类示例", !!used, used);
check("跳到 /plot/complex", (await evalJs("location.hash")) === "#/plot/complex", String(await evalJs("location.hash")));
vals = await inputValues();
check("复变函数进了输入框（z^2 / exp(z)）", vals.some((v) => /z\^2|exp\(z\)/.test(v)), JSON.stringify(vals));

console.log("\n── 向量场 ──");
used = await loadExample("/模式：向量场/");
check("点到了向量场示例", !!used, used);
check("跳到 /plot/vector", (await evalJs("location.hash")) === "#/plot/vector", String(await evalJs("location.hash")));
vals = await inputValues();
check("两个分量都被拆出来填好（-y / x 或 2x / 2y）",
  vals.some((v) => /^-y$|^2\*?x$|^2x$/.test(v)) && vals.some((v) => /^x$|^2\*?y$|^2y$/.test(v)),
  JSON.stringify(vals));

console.log("\n── 覆盖度：示例库里的绘图类示例都必须落在「已接线」的页上 ──");
/* 直接读数据源（不是读页面）：绘图类示例的 mode 只有这四类，且都对应上面验过的页。
 * 将来谁加了「几何/分形」的示例，这条会红 —— 提醒他把那两页也接上（否则又是静默丢弃）。 */
const { readFileSync } = await import("node:fs");
const { join, dirname } = await import("node:path");
const { fileURLToPath } = await import("node:url");
const DATA = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "tutorials", "tutorials.json");
const tut = JSON.parse(readFileSync(DATA, "utf8"));
const plotModes = new Set();
for (const t of tut.tutorials || []) {
  for (const e of t.examples || []) {
    if (e && /绘图|着色|向量场|几何|分形|极坐标|3D|2D/.test(String(e.mode || ""))) plotModes.add(String(e.mode));
  }
}
const SEEDED_MODES = ["2D 绘图", "3D 绘图", "复数着色", "向量场"];
console.log("    示例库里的绘图类 mode: " + JSON.stringify([...plotModes]));
check("绘图类示例的 mode 都在已接线的四类里",
  [...plotModes].every((m) => SEEDED_MODES.includes(m)), JSON.stringify([...plotModes]));
check("没有把示例路由到自由几何 / 分形（那两页本来就没有表达式可接）",
  ![...plotModes].some((m) => /几何|分形/.test(m)), JSON.stringify([...plotModes]));

console.log(`\nRESULT|plot-seed|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
