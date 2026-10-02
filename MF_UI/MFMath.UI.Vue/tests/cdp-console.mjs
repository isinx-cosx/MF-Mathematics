// 控制台验证：组件（可选下载）→ 写代码 → 跑 → 输出，且**C++ 在组件装好前不出现**
//
// 关键断言都对着真实行为：
//   · Python 侧调引擎拿到的值必须是引擎算的（不是 JS 或 Python 自己算的）
//   · 循环/条件/函数（设计方案里明确要支持的）必须能跑
//   · 引擎报错要走 stderr + 非零退出码，而不是被吞掉
//   · 语言下拉里 C++ 只在组件安装后出现（默认隐藏）
// 用法: node cdp-console.mjs   （宿主需带 --remote-debugging-port=9222 启动）
import { existsSync, writeFileSync, rmSync, readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { join } from "node:path";

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

const exceptions = [];
ws.addEventListener("message", (ev) => {
  let d; try { d = JSON.parse(ev.data); } catch { return; }
  if (d.method === "Runtime.exceptionThrown") {
    exceptions.push(String(d.params?.exceptionDetails?.exception?.description || d.params?.exceptionDetails?.text || "?"));
  }
});
await send("Runtime.enable");
await sleep(1200);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

/**
 * 写入代码。
 * 编辑区已换成 CodeMirror 6：它没有 textarea.value，必须走 EditorView.dispatch。
 * 组件把 EditorView 挂在编辑区根节点的 __mfEditor 上（见 CodeEditor.vue），
 * 拿不到就退回到 textarea（编辑器内核加载失败时的回退分支）。
 */
const setEditor = (code) => evalJs(`(function(){
  const host = document.querySelector('.console-wrap .editor');
  if (!host) return 'no-editor';
  if (host.__mfEditor) { host.__mfEditor.setDoc(${JSON.stringify(code)}); return 'cm'; }
  const ta = host.querySelector('textarea');
  if (ta) { ta.value = ${JSON.stringify(code)}; ta.dispatchEvent(new Event('input', { bubbles: true })); return 'ta'; }
  return 'no-editor';
})()`);
const getEditorText = () => evalJs(`(function(){
  const host = document.querySelector('.console-wrap .editor');
  if (!host) return '';
  if (host.__mfEditor) return host.__mfEditor.getDoc();
  const ta = host.querySelector('textarea');
  return ta ? ta.value : '';
})()`);
const clickRun = () => evalJs(`(function(){
  const b = [...document.querySelectorAll('.console-wrap .btn')].find((x) => /运行/.test(x.textContent));
  if (!b) return 'no-btn';
  if (b.disabled) return 'disabled';
  b.click(); return 'clicked';
})()`);
/** 等运行结束（退出码出现） */
const waitDone = async (timeoutMs = 40000) => {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    const st = await evalJs(`(function(){
      const b = document.querySelector('.console-wrap .badge');
      const o = document.querySelector('.console-wrap .out');
      const e = document.querySelectorAll('.console-wrap .out')[1];
      return { badge: b ? b.textContent.trim() : '', out: o ? o.textContent : '', err: e ? e.textContent : '' };
    })()`);
    if (st && /退出码/.test(st.badge)) return st;
    await sleep(300);
  }
  return null;
};

console.log("── 控制台：组件 / 语言 / 运行 ──");
await evalJs("location.hash = '#/'");
await sleep(900);

/* ══════════ 编辑器：CodeMirror 真的用上了，而且是**按需**加载的 ══════════
 *
 * 这一节刻意先于"跑代码"来验证，因为编辑器最容易出的问题不是"跑不起来"，而是：
 *   ① **悄悄退化成 textarea**（chunk 加载失败被 fallback 兜住）；
 *   ② **编辑器内核被静态 import 进主包**（懒加载白做，每个用户都白下一次）；
 *   ③ **语言包没分开**（写 Python 的用户也要下 C++ 语法包）。
 * 三种情况界面看起来都完全正常，只有断言能发现。
 *
 * 判定语言包身份用的是**内容指纹**（把 chunk 取回来找语法关键字），
 * 而不是文件名——两个语言包的入口都叫 index.js，打包出来都叫 index-<hash>.js，
 * 按名字区分一定会错（我第一版就是这么误判的）。 */
console.log("\n── 编辑器内核与按需加载 ──");

/** 已加载的 JS 资源（完整 URL，便于按内容判定） */
const resourcesFull = () => evalJs(`performance.getEntriesByType('resource')
  .map((r) => r.name).filter((n) => n.split('?')[0].endsWith('.js'))`);
const base = (u) => String(u).split('/').pop();
const editorChunks = (list) => (list || []).map(base).filter((n) => /^editor-.*\.js$/.test(n));

/** 把某个已加载的 chunk 取回来，看它的**内容**里有没有某个语法标记 */
const chunkHas = (url, needle) => evalJs(`(async () => {
  try {
    const t = await (await fetch(${JSON.stringify(url)})).text();
    return t.includes(${JSON.stringify(needle)});
  } catch (e) { return false; }
})()`);
/** 在一组 chunk 里找出"含某标记"的那个 */
async function findChunkByContent(urls, needle) {
  for (const u of urls) if (await chunkHas(u, needle)) return u;
  return null;
}

const atHome = await resourcesFull();
console.log("   首页已加载 chunk:", JSON.stringify(atHome.map(base)));
check("首页没有编辑器内核（说明它不在主包里）", editorChunks(atHome).length === 0,
  JSON.stringify(editorChunks(atHome)));

await evalJs("location.hash = '#/tools/console'");
await sleep(2500);
const atConsole = await resourcesFull();
const newAtConsole = atConsole.filter((u) => !atHome.includes(u));
console.log("   进控制台新加载:", JSON.stringify(newAtConsole.map(base)));
check("进控制台才加载编辑器内核", editorChunks(newAtConsole).length >= 1,
  JSON.stringify(editorChunks(newAtConsole)));
// Python 是默认语言，所以它的语法包应当在这时就到位了。
// 指纹用不带引号的 "elif"：lezer 把关键字表拼成 "and,as,assert,...,elif,..."
// 这种逗号分隔的单个字符串，带引号反而匹配不到（第一版就是这么漏的）。
const pyCandidates = newAtConsole.filter((u) => !/^editor-/.test(base(u)));
const pyChunk = await findChunkByContent(pyCandidates, "elif");
console.log("   Python 语法包:", pyChunk ? base(pyChunk) : "（没找到）");
check("进控制台才加载 Python 语法包", !!pyChunk, pyChunk ? base(pyChunk) : "");

const ed = await evalJs(`(function(){
  const host = document.querySelector('.console-wrap .editor');
  if (!host) return null;
  const cm = host.querySelector('.cm-editor');
  return {
    hasHandle: !!host.__mfEditor,
    hasCmDom: !!cm,
    isFallback: host.parentElement.querySelector('.editor-ta') !== null,
    loading: !!host.parentElement.querySelector('.editor-loading'),
    gutterCells: host.querySelectorAll('.cm-lineNumbers .cm-gutterElement').length,
    tokenSpans: host.querySelectorAll('.cm-content .cm-line span').length,
    lines: host.querySelectorAll('.cm-content .cm-line').length,
  };
})()`);
console.log("   编辑器:", JSON.stringify(ed));
check("编辑区用的是 CodeMirror（不是退化后的 textarea）", !!ed?.hasHandle && !!ed?.hasCmDom, JSON.stringify(ed));
check("编辑器已完成加载（不在 loading 态）", ed?.loading === false, "");
check("有行号栏", (ed?.gutterCells || 0) >= 1, String(ed?.gutterCells));
check("载入示例后产生语法着色 token", (ed?.tokenSpans || 0) > 0, (ed?.tokenSpans || 0) + " 个 span");

// 切到 C++：只下载 C++ 语法包，且它与 Python 的不是同一个 chunk
const beforeCpp = atConsole.slice();
const hasCpp = (await evalJs("[...document.querySelectorAll('.console-wrap .input.lang option')].map(o=>o.value)")).includes("cpp");
if (hasCpp) {
  await evalJs(`(function(){
    const s=document.querySelector('.console-wrap .input.lang');
    s.value='cpp'; s.dispatchEvent(new Event('change',{bubbles:true})); return 1;})()`);
  await sleep(1200);
  const atCpp = await resourcesFull();
  const newForCpp = atCpp.filter((u) => !beforeCpp.includes(u));
  console.log("   切到 C++ 后新加载:", JSON.stringify(newForCpp.map(base)));
  const cppChunk = await findChunkByContent(newForCpp, "constexpr");
  console.log("   C++ 语法包:", cppChunk ? base(cppChunk) : "（没找到）");
  check("切到 C++ 才加载 C++ 语法包", !!cppChunk, cppChunk ? base(cppChunk) : "");
  check("两门语言用的是不同的 chunk", !!cppChunk && base(cppChunk) !== base(pyChunk),
    JSON.stringify({ py: base(pyChunk), cpp: cppChunk ? base(cppChunk) : null }));
  // 切回 Python：不应该再下载任何东西（已缓存）
  const beforeBack = atCpp.slice();
  await evalJs(`(function(){
    const s=document.querySelector('.console-wrap .input.lang');
    s.value='python'; s.dispatchEvent(new Event('change',{bubbles:true})); return 1;})()`);
  await sleep(900);
  const afterBack = await resourcesFull();
  check("切回 Python 不再重复下载（语言包有缓存）",
    afterBack.filter((u) => !beforeBack.includes(u)).length === 0,
    JSON.stringify(afterBack.filter((u) => !beforeBack.includes(u)).map(base)));
} else {
  check("（跳过 C++ 语法包检查：C++ 组件未安装）", true, "");
}

// 编辑器配色必须跟随外观（颜色取自 CSS 变量，不是硬编码）
const editorColors = () => evalJs(`(function(){
  const h = document.querySelector('.console-wrap .editor');
  const cm = h && h.querySelector('.cm-editor');
  if (!cm) return null;
  const cs = getComputedStyle(cm);
  return { bg: cs.backgroundColor, fg: cs.color };
})()`);
const lightCol = await editorColors();
await evalJs(`(function(){
  const b=[...document.querySelectorAll('.nav-btn')].find(x=>x.title==='切换主题'); b.click();
  return 1;})()`);
await sleep(300);
await evalJs(`(function(){
  const c=document.querySelector('.appearance-pop .tp-card[data-theme="terminal-dark"]'); if(c) c.click();
  return 1;})()`);
await sleep(600);
const darkCol = await editorColors();
console.log("   编辑器配色 浅色:", JSON.stringify(lightCol), "→ 深色:", JSON.stringify(darkCol));
check("编辑器配色跟随外观变化（没硬编码颜色）",
  !!lightCol && !!darkCol && lightCol.bg !== darkCol.bg, JSON.stringify({ light: lightCol, dark: darkCol }));
// 还原外观（后面的运行测试要在浅色下跑，也免得多主题影响别的断言）
await evalJs(`(function(){
  const c=document.querySelector('.appearance-pop .tp-card[data-theme="glass-light"]'); if(c) c.click();
  return 1;})()`);
await sleep(400);
await evalJs(`(function(){
  const p=document.querySelector('.appearance-pop'); if (p) p.querySelector('.ap-close').click();
  return 1;})()`);
await sleep(300);
check("外观已还原为默认", (await evalJs("document.documentElement.dataset.theme")) === "glass-light", "");

/* ══════════ 引擎函数名补全 ══════════
 *
 * 控制台的核心用法就是调引擎那 400 多个函数，用户不可能背下来；而 C++ 模式
 * （@codemirror/lang-cpp）的 languageData 里根本没有 autocomplete，一个候选都没有。
 * 候选来自引擎的 list_functions —— 它早就存在，之前一直没被调用过。
 *
 * 断言方式是**直接问编辑器状态**（languageDataAt('autocomplete') 取出各个补全源并调用），
 * 而不是靠"派发 Ctrl+Space 再看提示框"：后者依赖焦点与合成键盘事件，很容易假失败
 * （试过两轮：一次面板不弹、一次查询词为空只显示 Python 内置名）。
 * 直接调源能精确验证"引擎函数名确实作为候选项提供出来了"。 */
console.log("\n── 引擎函数名补全 ──");
await setEditor("expr_");
const acSrc = await evalJs(`(function(){
  const h = document.querySelector('.console-wrap .editor');
  const v = h && h.__mfEditor && h.__mfEditor.view;
  if (!v) return 'no-view';
  const pos = v.state.doc.length;
  const srcs = v.state.languageDataAt('autocomplete', pos);
  const fake = {
    state: v.state, pos, explicit: true,
    matchBefore(re) {
      const text = v.state.doc.sliceString(0, pos);
      const m = text.match(/[\\w:.>]*$/);
      return m ? { from: pos - m[0].length, to: pos, text: m[0] } : null;
    },
  };
  let best = null;
  for (const s of srcs) {
    try {
      const r = s(fake);
      const labels = r && r.options ? r.options.map((o) => o.label || o) : [];
      if (!best || labels.length > best.n) best = { n: labels.length, labels };
    } catch (e) { /* 某个源出错不影响其它源 */ }
  }
  return { srcCount: srcs.length, n: best ? best.n : 0,
           hit: best ? best.labels.filter((l) => /^expr_/.test(l)).slice(0, 4) : [] };
})()`);
console.log("   补全源:", JSON.stringify(acSrc));
check("编辑器注册了补全源", !!acSrc && acSrc.srcCount >= 1, JSON.stringify(acSrc));
check("候选里含引擎函数名（expr_ 开头）", !!acSrc && acSrc.hit.length >= 2, JSON.stringify(acSrc?.hit));
check("候选数量达到引擎函数表规模（≥100）", (acSrc?.n || 0) >= 100, String(acSrc?.n));

// 辅助检查：Ctrl+Space 确实能弹出面板（失败的合成键盘事件不代表功能坏，只记一行）
await evalJs(`(function(){
  const h = document.querySelector('.console-wrap .editor');
  const v = h && h.__mfEditor && h.__mfEditor.view;
  if (!v) return 0;
  v.dispatch({ selection: { anchor: v.state.doc.length } });
  v.focus();
  v.contentDOM.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', code: 'Space', ctrlKey: true, bubbles: true, cancelable: true }));
  return 1;})()`);
await sleep(800);
const ac = await evalJs(`(function(){
  const tip = document.querySelector('.cm-tooltip-autocomplete');
  if (!tip) return null;
  return { n: tip.querySelectorAll('li').length,
           first: [...tip.querySelectorAll('li')].slice(0, 5).map((li) => li.textContent.trim()) };
})()`);
console.log("   补全面板（Ctrl+Space，辅助）:", JSON.stringify(ac));
if (ac && ac.n > 0) {
  check("Ctrl+Space 弹出的面板里含引擎函数名",
    ac.first.some((t) => /expr_/.test(t)) || ac.n >= 20, JSON.stringify(ac.first));
} else {
  console.log("   （合成的 Ctrl+Space 没弹出面板——这条不计入失败，功能已由上面的补全源断言覆盖）");
}
await evalJs("document.activeElement && document.activeElement.blur()");
await evalJs("document.activeElement && document.activeElement.blur()");

/* ══════════ 清空输出 / 重置 ══════════
 * 原版有「重置」按钮；Vue 侧一直没有入口（只能靠"再运行一次"覆盖输出）。 */
console.log("\n── 清空输出 / 重置 ──");
await setEditor("import mfmath\nprint('要被清掉的一行')");
await clickRun();
const rClear = await waitDone();
check("先跑一次产生输出", !!rClear && /要被清掉的一行/.test(rClear.out || ""), "");
const btns = await evalJs(`[...document.querySelectorAll('.console-wrap .btn')].map((b) => b.textContent.trim())`);
check("有「清空输出」按钮", (btns || []).some((t) => /清空输出/.test(t)), (btns || []).join('/'));
check("有「重置」按钮", (btns || []).some((t) => /^重置$/.test(t)), (btns || []).join('/'));
await evalJs(`(function(){
  const b = [...document.querySelectorAll('.console-wrap .btn')].find((x) => /清空输出/.test(x.textContent));
  if (b) b.click(); return 1;})()`);
await sleep(400);
const cleared = await evalJs(`(document.querySelector('.console-wrap .out')||{}).textContent || ''`);
check("清空后输出框里没有刚才那行", !/要被清掉的一行/.test(cleared), JSON.stringify(cleared.slice(0, 40)));

/* ══════════ 会话态：每次运行都是新进程（页面必须说清） ══════════
 * 原版 PyQt 是同进程持久命名空间（a=5 之后下一次能算 a*2）；Vue 走子进程，跨运行零状态。
 * 另外嵌入版 CPython 处于 isolated 模式，默认不会把脚本目录放进 sys.path，
 * 靠宿主的 _run.py 引导补回来——这里顺带验证那条路径。 */
console.log("\n── 会话态与 sys.path ──");
const hint = await evalJs(`(document.querySelector('.console-wrap .hint')||{}).textContent || ''`);
check("页面明确写了「每次运行都是新进程」", /新进程/.test(hint), hint.slice(0, 40));
await setEditor("import sys\nprint('PATH0', sys.path[0][-12:])\nimport mfmath\nprint('OK')");
await clickRun();
const rPath = await waitDone();
console.log("   输出:", JSON.stringify((rPath?.out || "").trim().slice(0, 120)));
check("脚本目录已进 sys.path 且能 import mfmath",
  /PATH0/.test(rPath?.out || "") && /OK/.test(rPath?.out || ""), (rPath?.out || "").slice(0, 60));

console.log("\n── 控制台：组件 / 语言 / 运行 ──");

const shell = await evalJs(`(function(){
  const wrap = document.querySelector('.console-wrap');
  const opts = [...document.querySelectorAll('.console-wrap .input.lang option')].map((o) => o.value);
  const comps = [...document.querySelectorAll('.console-wrap .comp-row')].map((r) => r.textContent.replace(/\\s+/g, ' ').trim());
  return {
    isPlaceholder: /占位|开发中/.test(document.body.textContent.slice(0, 4000)) && !wrap,
    hasWrap: !!wrap,
    title: (document.querySelector('.console-wrap .ws-title') || {}).textContent || '',
    hasEditor: !!document.querySelector('.console-wrap .editor'),
    hasRun: !!document.querySelector('.console-wrap .btn'),
    languages: opts,
    comps,
  };
})()`);
console.log("   语言:", JSON.stringify(shell.languages), "| 组件行:", JSON.stringify(shell.comps));
check("这一页不再是占位视图", shell.hasWrap && !shell.isPlaceholder, shell.title);
check("有代码编辑框", shell.hasEditor);
check("有运行按钮", shell.hasRun);
check("语言里有 Python", shell.languages.includes("python"), shell.languages.join(","));
check("C++ 组件未装 → 语言里不出现 C++（默认隐藏）",
  shell.languages.includes("cpp") === /已安装/.test((shell.comps[1] || "")), shell.languages.join(","));

// 若 Python 未装，先装（组件包应已在缓存目录；没有则明确报错而不是静默跳过）
const pyInstalled = /已安装/.test(shell.comps[0] || "");
if (!pyInstalled) {
  console.log("   Python 未安装 → 触发安装…");
  const payloadReady = !/缺少组件包/.test(shell.comps[0] || "");
  check("Python 组件包可用（缓存目录或应用目录）", payloadReady,
    payloadReady ? "" : "把 python-3.13.15-embed-amd64.zip 放到 %LOCALAPPDATA%\\MFMath\\components\\cache\\");
  await evalJs(`(function(){
    const btn = [...document.querySelectorAll('.console-wrap .comp-row .btn')][0];
    if (btn && !btn.disabled) btn.click();
  })()`);
  for (let i = 0; i < 40 && !/已安装/.test(await evalJs("document.querySelectorAll('.console-wrap .comp-row')[0].textContent") || ""); i++) await sleep(500);
  const now = await evalJs("document.querySelectorAll('.console-wrap .comp-row')[0].textContent.replace(/\\s+/g,' ')");
  console.log("   安装后:", now);
  check("安装后 Python 显示已安装", /已安装/.test(now || ""), String(now));
}

console.log("\n── 跑默认示例（引擎求值 / 求导 / 极限）──");
await setEditor([
  "import mfmath",
  "print('x^2 在 x=3 处 =', mfmath.call('expr_eval', expr='x^2', x=3))",
  "print('d/dx (x e^x) =', mfmath.call('diff', expr='xe^x', var='x'))",
  "print('lim (1+1/x)^x =', mfmath.call('limit', expr='(1+1/x)^x', var='x', point='oo'))",
].join("\n"));
check("写入代码生效（CodeMirror 或回退 textarea）",
  ["cm", "ta"].includes(await setEditor("import mfmath\nprint('ok')")),
  await setEditor("import mfmath\nprint('ok')"));
await setEditor([
  "import mfmath",
  "print('x^2 在 x=3 处 =', mfmath.call('expr_eval', expr='x^2', x=3))",
  "print('d/dx (x e^x) =', mfmath.call('diff', expr='xe^x', var='x'))",
  "print('lim (1+1/x)^x =', mfmath.call('limit', expr='(1+1/x)^x', var='x', point='oo'))",
].join("\n"));
const clicked = await clickRun();
const r1 = await waitDone();
console.log("   ", clicked, "|", r1 ? r1.badge.replace(/\s+/g, " ") : "超时");
console.log("    输出:", JSON.stringify((r1?.out || "").trim().slice(0, 200)));
check("运行完成且退出码 0", !!r1 && /退出码 0/.test(r1.badge), r1 ? r1.badge : "");
check("引擎求值结果正确（9）", /=\s*9/.test(r1?.out || ""), "");
check("引擎求导结果正确", /exp\(x\)/.test(r1?.out || ""), "");
check("引擎极限结果正确（e）", /2\.718281828/.test(r1?.out || ""), "");

console.log("\n── 循环 / 条件 / 函数（设计方案要求支持）──");
await setEditor([
  "import mfmath",
  "def f(x): return mfmath.call('expr_eval', expr='x^2-4', x=x)",
  "hits = 0",
  "for i in range(-30, 31):",
  "    if abs(f(i/10)) < 0.5:",
  "        hits += 1",
  "print('接近零的点数 =', hits)",
  "print('列表推导 =', [k*k for k in range(5)])",
].join("\n"));
await clickRun();
const r2 = await waitDone();
console.log("    输出:", JSON.stringify((r2?.out || "").trim().slice(0, 160)));
check("循环+条件+函数能跑（退出码 0）", !!r2 && /退出码 0/.test(r2.badge), r2 ? r2.badge : "");
check("循环里反复调引擎成功", /接近零的点数 =\s*\d+/.test(r2?.out || ""), "");
check("列表推导正常", /\[0, 1, 4, 9, 16\]/.test(r2?.out || ""), "");

/* ══════════════ 组件包完整性校验 ══════════════
 *
 * 组件包是几十 MB 的下载物，截断/被改写都很常见，而解压出错时的报错
 * （"解压后没有 python.exe"）根本指不到真正原因，所以宿主在解压前先校验 SHA-256。
 *
 * 这里**不动真正的组件包**（那会把环境搞坏）：只放一个内容为 64 个 0 的
 * .sha256 旁文件，让期望摘要与实际不符，从而走到失败分支；
 * 然后删掉旁文件再装一次，证明"同一个包在摘要对的时候能装成功"——
 * 否则断言"校验失败"只能说明校验逻辑永远在报错。 */
console.log("\n── 组件包完整性校验（SHA-256）──");
const cacheDir = join(process.env.LOCALAPPDATA || "", "MFMath", "components", "cache");
const pyZip = join(cacheDir, "python-3.13.15-embed-amd64.zip");
const pySide = pyZip + ".sha256";
let sidecarWritten = false;

const hostInstall = (name) => evalJs(`(function(){
  const c = window.chrome?.webview?.hostObjects?.sync?.con;
  if (!c) return null;
  return String(c.Install(${JSON.stringify(name)}));
})()`);
const hostInstallStatus = (jobId) => evalJs(`(function(){
  const c = window.chrome?.webview?.hostObjects?.sync?.con;
  if (!c) return null;
  return String(c.InstallStatus(${JSON.stringify(jobId)}));
})()`);
const waitJob = async (jobId, timeoutMs = 120000) => {
  const t0 = Date.now();
  let last = null;
  while (Date.now() - t0 < timeoutMs) {
    const raw = await hostInstallStatus(jobId);
    try { last = JSON.parse(raw); } catch { last = { state: "?", message: String(raw) }; }
    if (last.state !== "running") return last;
    await sleep(400);
  }
  return last;
};

if (!existsSync(pyZip)) {
  check("Python 组件包在位（校验用例需要它）", false, pyZip);
} else {
  // 期望摘要取"这个包**真实**的摘要"，而不是"删掉旁文件让它落到代码里写死的摘要"：
  // 本机自建的组件包（带 sympy/numpy/scipy，见 MFMath.Host/tools/build-python-component.ps1）
  // 与内置摘要本来就不同，删旁文件等于**故意**造一次校验失败，测不出"摘要对时能装成功"。
  const realHash = createHash("sha256").update(readFileSync(pyZip)).digest("hex").toUpperCase();
  const hadSidecar = existsSync(pySide);
  const origSidecar = hadSidecar ? readFileSync(pySide, "utf8") : null;

  writeFileSync(pySide, "0".repeat(64) + "\n", "utf8");
  sidecarWritten = true;
  const badJob = await hostInstall("python");
  const badRes = await waitJob(badJob);
  console.log("   坏摘要结果:", JSON.stringify(badRes).slice(0, 220));
  check("摘要不符时安装被拒绝", badRes?.state === "error", badRes?.state);
  check("报错说明是校验失败（而不是解压失败）", /校验失败/.test(badRes?.message || ""), "");
  check("报错里给出期望与实际摘要", /期望 SHA-256/.test(badRes?.message || "") && /实际 SHA-256/.test(badRes?.message || ""), "");
  check("校验失败时没有留下半装状态", !existsSync(join(cacheDir, "..", "python-3.13.15.staging")), "");
  // 报错必须点名是哪个文件，否则用户不知道该重下什么
  check("报错里带上出问题的文件名", /python-3\.13\.15-embed-amd64\.zip/.test(badRes?.message || ""), "");

  // 写回真实摘要 → 同一个包必须能装成功（证明不是恒报错）
  writeFileSync(pySide, realHash + "\n", "utf8");
  const goodJob = await hostInstall("python");
  const goodRes = await waitJob(goodJob);
  console.log("   正确摘要结果:", JSON.stringify(goodRes).slice(0, 160));
  check("摘要正确时同一个包装得成功（证明不是恒报错）", goodRes?.state === "done", goodRes?.state);

  // 还原：把旁文件写成"与当前缓存包一致"的状态。
  //
  // 为什么不是"本来没有就删掉"：本机缓存里的包可能是**自建包**（带 sympy/numpy/scipy，
  // 见 MFMath.Host/tools/build-python-component.ps1），它与代码里写死的官方摘要**不同**。
  // 把旁文件删掉，等于让宿主退回到内置摘要 → 之后每次安装都会"校验失败"，
  // 而这正是本测试后面那两条续传用例失败的原因（实测踩过）。
  // 所以这里保留/写入真实摘要：对官方包它等于内置摘要（无害），对自建包它是**必需**的。
  const officialZip = pyZip + ".official";
  const isOfficial = existsSync(officialZip)
    ? createHash("sha256").update(readFileSync(officialZip)).digest("hex").toUpperCase() === realHash
    : false;
  if (hadSidecar || !isOfficial) {
    writeFileSync(pySide, realHash + "\n", "utf8");
    if (!hadSidecar) console.log("   注：缓存里是自建组件包，已保留 .sha256 旁文件（否则安装会因摘要不符失败）");
  } else {
    rmSync(pySide, { force: true });
  }
  sidecarWritten = false;
}

/* ══════════ 组件下载：断点续传必须真的续，而不是从头下 ══════════
 *
 * 为什么这条重要：54 MB 的 MinGW 包走一遍网络，中途断线几乎必然发生。
 * 如果"续传"其实是从 0 重来，用户会看到进度条一次次跳回 0，却永远装不上。
 *
 * 怎么证明是**真续传**而不是假装：预先把真实 zip 的前 N 字节写成 .part，
 * 然后起一个**本地**带 Range 的 HTTP 服务当下载源，把宿主的下载地址指过去。
 * 装完之后检查服务端收到的请求头里有没有 `Range: bytes=<N>-`——
 * 这是服务端视角的证据，比看宿主自己的日志可信。
 *
 * 服务端返回 206 是前提；顺带也验证"服务端忽略 Range 时必须退化成从头写"，
 * 否则会把整个文件追加到旧内容后面，得到一个长度翻倍、哈希对不上的怪文件。 */
console.log("\n── 组件下载：断点续传 ──");
{
  const { createServer } = await import("node:http");
  const { readFileSync, copyFileSync, statSync, existsSync: ex, rmSync: rm } = await import("node:fs");

  const realZip = join(cacheDir, "python-3.13.15-embed-amd64.zip");
  const partFile = realZip + ".part";
  const backup = realZip + ".testbak";
  const RESUME_AT = 4 * 1024 * 1024;          // 预置前 4 MB
  const requests = [];
  let ignoreRange = false;                    // 用来验证"服务端不支持续传"的退化分支

  // 本地服务的源文件用**备份**（真实包要改名挪走，否则宿主会直接复用缓存、根本不联网）
  const sourcePath = backup;

  const server = createServer((req, res) => {
    requests.push({ url: req.url, range: req.headers.range || "" });
    if (!ex(sourcePath)) { res.writeHead(404); res.end("no file"); return; }
    const total = statSync(sourcePath).size;
    const m = /bytes=(\d+)-(\d*)/.exec(req.headers.range || "");
    if (m && !ignoreRange) {
      const start = Number(m[1]);
      const end = m[2] ? Number(m[2]) : total - 1;
      if (start >= total || end < start) {
        res.writeHead(416, { "Content-Range": `bytes */${total}`, "Accept-Ranges": "bytes" });
        res.end();
        return;
      }
      res.writeHead(206, {
        "Content-Type": "application/octet-stream",
        "Content-Range": `bytes ${start}-${end}/${total}`,
        "Content-Length": String(end - start + 1),
        "Accept-Ranges": "bytes",
      });
      res.end(readFileSync(sourcePath).subarray(start, end + 1));
      return;
    }
    res.writeHead(200, {
      "Content-Type": "application/octet-stream",
      "Content-Length": String(total),
      "Accept-Ranges": "bytes",
    });
    res.end(readFileSync(sourcePath));
  });
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const port = server.address().port;
  const setBase = (u) => evalJs(`(function(){
    const c = window.chrome?.webview?.hostObjects?.sync?.con;
    return c ? String(c.SetDownloadBase(${JSON.stringify(u)})) : null;
  })()`);

  try {
    copyFileSync(realZip, backup);                       // 保命备份（同时作为本地服务的源）
    rm(realZip, { force: true });
    // 预置半成品：前 4 MB 的**真实**字节（模拟"上次下到一半断了"）
    const head = readFileSync(backup).subarray(0, RESUME_AT);
    const { writeFileSync } = await import("node:fs");
    writeFileSync(partFile, head);
    console.log(`   预置 .part = ${RESUME_AT} 字节；下载源 = http://127.0.0.1:${port}`);

    await setBase(`http://127.0.0.1:${port}`);
    const jobId = await hostInstall("python");
    const res = await waitJob(jobId, 180000);
    console.log("   结果:", JSON.stringify(res).slice(0, 140));
    console.log("   服务端收到的请求:", JSON.stringify(requests.map((r) => r.range || "(无 Range)")));

    check("带半成品时安装成功", res?.state === "done", res?.state + " " + String(res?.message).slice(0, 60));
    const ranged = requests.find((r) => r.range === `bytes=${RESUME_AT}-`);
    check(`服务端确实收到了 Range: bytes=${RESUME_AT}-（真续传）`, !!ranged,
      JSON.stringify(requests.map((r) => r.range)));
    // 续传后文件必须与原件逐字节相同（宿主自己也会校验 SHA-256，这里再独立算一遍）
    const { createHash } = await import("node:crypto");
    const h = (p) => createHash("sha256").update(readFileSync(p)).digest("hex").toUpperCase();
    check("续传拼出的文件 SHA-256 与原件一致", h(realZip) === h(backup),
      `${h(realZip).slice(0, 16)}… vs ${h(backup).slice(0, 16)}…`);
    check("下载完成后 .part 已被清理（不会和新文件并存）", !ex(partFile), "");

    // 服务端忽略 Range 的退化分支：必须从头写，不能追加
    requests.length = 0;
    ignoreRange = true;
    rm(realZip, { force: true });
    writeFileSync(partFile, head);                       // 再放一个 4 MB 半成品
    const job2 = await hostInstall("python");
    const res2 = await waitJob(job2, 180000);
    const h2 = ex(realZip) ? h(realZip) : "";
    console.log("   忽略 Range 时:", JSON.stringify(res2).slice(0, 100),
      "| 请求:", JSON.stringify(requests.map((r) => r.range || "(无 Range)")));
    check("服务端不支持续传时仍能装成功", res2?.state === "done", res2?.state);
    check("不支持续传时结果文件仍然正确（没把新内容追加到旧的后面）",
      h2 === h(backup), `${h2.slice(0, 16)}…`);
    ignoreRange = false;
  } finally {
    // 无论成败都要把环境还原干净：删 .part、恢复真实包、把下载源指回官网
    try { rm(partFile, { force: true }); } catch { /* 忽略 */ }
    try { if (ex(backup) && !ex(realZip)) copyFileSync(backup, realZip); } catch { /* 忽略 */ }
    try { rm(backup, { force: true }); } catch { /* 忽略 */ }
    await setBase("");
    server.close();
  }
}

console.log("\n── 引擎报错必须显性（stderr + 非零退出码）──");
await setEditor([
  "import mfmath",
  "mfmath.call('diff', expr='sin(', var='x')",
  "print('不该走到这一行')",
].join("\n"));
await clickRun();
const r3 = await waitDone();
console.log("   ", r3 ? r3.badge.replace(/\s+/g, " ") : "超时", "| stderr:", JSON.stringify((r3?.err || "").slice(0, 120)));
check("引擎错误导致非零退出码", !!r3 && !/退出码 0/.test(r3.badge), r3 ? r3.badge : "");
check("错误信息出现在 stderr", /EngineError|syntax error/.test(r3?.err || ""), "");
check("出错后没有继续执行", !/不该走到这一行/.test(r3?.out || ""), "");

/* ══════════════ C++：组件 → 编译 → 运行 → 调引擎 ══════════════
 *
 * 这条链最值得验证的是**计算确实走 C++ 引擎 DLL**，而不是什么替代实现：
 *   · 用户代码里没有任何数学，只有 mfm::num/mfm::text 打给引擎的调用
 *   · 结果与 Python 侧同一个 C ABI 拿到的一致
 *   · 编译失败要原样给出编译器诊断，且**不运行**（不能拿旧 exe 凑数）
 *   · 未捕获异常时 aborted 前的输出不能丢（靠 -include mfmath_autorun.hpp 的行冲刷） */
const compRow = async (i) =>
  evalJs(`(function(){const r=document.querySelectorAll('.console-wrap .comp-row')[${i}];
    return r ? r.textContent.replace(/\\s+/g,' ').trim() : '';})()`);

console.log("\n── C++ 组件（MinGW A 档）──");
let cppRow = await compRow(1);
console.log("   组件行:", JSON.stringify(cppRow));
if (!/已安装/.test(cppRow)) {
  const payloadOk = !/缺少组件包/.test(cppRow);
  check("MinGW 组件包可用", payloadOk,
    payloadOk ? "" : "把 mingw-16.1.0-x86_64-seh.zip 放到 %LOCALAPPDATA%\\MFMath\\components\\cache\\");
  if (payloadOk) {
    console.log("   触发安装（解压约 225 MB，需要一会儿）…");
    await evalJs(`(function(){
      const rows=[...document.querySelectorAll('.console-wrap .comp-row')];
      const btn = rows[1] && rows[1].querySelector('.btn');
      if (btn && !btn.disabled) btn.click();
      return 1;})()`);
    for (let i = 0; i < 240; i++) {
      const st = await evalJs(`(function(){
        const p=document.querySelector('.console-wrap .progress-txt');
        return p ? p.textContent.trim() : '';})()`);
      if (i % 12 === 0 && st) console.log("     ", st);
      cppRow = await compRow(1);
      if (/已安装/.test(cppRow) || /失败|错误/.test(st)) break;
      await sleep(500);
    }
  }
}
cppRow = await compRow(1);
console.log("   安装后:", JSON.stringify(cppRow));
check("C++ 组件显示已安装", /已安装/.test(cppRow), cppRow);

// 装好后语言下拉里必须自动出现 C++
const langs2 = await evalJs("[...document.querySelectorAll('.console-wrap .input.lang option')].map(o=>o.value)");
console.log("   语言:", JSON.stringify(langs2));
check("装好后 C++ 出现在语言里", langs2.includes("cpp"), langs2.join(","));

// 切到 C++
await evalJs(`(function(){
  const s=document.querySelector('.console-wrap .input.lang');
  s.value='cpp'; s.dispatchEvent(new Event('change',{bubbles:true})); return 1;})()`);
await sleep(400);

console.log("\n── C++ 示例：求值 / 求导 / 极限 ──");
await setEditor([
  '#include "mfmath.hpp"',
  '#include <iostream>',
  'int main() {',
  '    std::cout << "x^2 在 x=3 处 = " << mfm::num("expr_eval", {{"expr", "x^2"}, {"x", 3}}) << "\\n";',
  '    std::cout << "d/dx (x e^x) = " << mfm::text("diff", {{"expr", "xe^x"}, {"var", "x"}}) << "\\n";',
  '    std::cout << "lim (1+1/x)^x = "',
  '              << mfm::text("limit", {{"expr", "(1+1/x)^x"}, {"var", "x"}, {"point", "oo"}}) << "\\n";',
  '    std::cout << "引擎函数总数 = " << mfm::functions().size() << "\\n";',
  '    return 0;',
  '}',
].join("\n"));
const cr = await clickRun();
const r4 = await waitDone(90000);
console.log("   ", cr, "|", r4 ? r4.badge.replace(/\s+/g, " ") : "超时");
console.log("    输出:", JSON.stringify((r4?.out || "").trim().slice(0, 260)));
if (r4?.err) console.log("    stderr:", JSON.stringify(r4.err.slice(0, 300)));
check("C++ 编译并运行成功（退出码 0）", !!r4 && /退出码 0/.test(r4.badge), r4 ? r4.badge : "");
check("C++ 侧引擎求值正确（9）", /=\s*9\b/.test(r4?.out || ""), "");
check("C++ 侧引擎求导正确", /exp\(x\)/.test(r4?.out || ""), "");
check("C++ 侧引擎极限正确（e）", /2\.718281828/.test(r4?.out || ""), "");
// 不写死具体数字：引擎每次加函数这个数就变（这次加 complex_grid 就从 423 变 424，
// 旧断言 423 直接把这条卡挂了）。改成"能拿到一张可观的函数表"即可。
check("C++ 侧能看到引擎函数表", /引擎函数总数 = \d{3,}/.test(r4?.out || ""),
  (r4?.out || "").match(/引擎函数总数 = \d+/)?.[0] || "");

// 编译阶段必须真的被报告出来（不允许"点一下就说跑完了"）。
// 注意要选**右边那根** bar：左边编辑区也有一根 .bar，按 class 直接取会取错。
const stageInfo = await evalJs(`(function(){
  const b=[...document.querySelectorAll('.console-wrap .bar')].find(x=>x.querySelector('.badge'));
  return b ? b.textContent.replace(/\\s+/g,' ').trim() : '';})()`);
console.log("   状态栏:", JSON.stringify(stageInfo));
check("状态栏报告了编译耗时", /编译\s*\d+\s*ms/.test(stageInfo || ""), String(stageInfo));

console.log("\n── C++ 编译失败：给编译器诊断且不运行 ──");
await setEditor([
  '#include "mfmath.hpp"',
  '#include <iostream>',
  'int main() {',
  '    std::cout << "这一行不该出现\\n";',
  '    mfm::num("expr_eval", {{"expr", "x^2"}, {"x", }});   // 语法错误',
  '    return 0;',
  '}',
].join("\n"));
await clickRun();
const r5 = await waitDone(90000);
console.log("   ", r5 ? r5.badge.replace(/\s+/g, " ") : "超时");
console.log("    stderr:", JSON.stringify((r5?.err || "").slice(0, 220)));
check("编译失败 → 非零退出码", !!r5 && !/退出码 0/.test(r5.badge), r5 ? r5.badge : "");
check("给出编译失败说明", /编译失败/.test(r5?.err || ""), "");
check("带编译器原始诊断（含行号）", /main\.cpp:\d+/.test(r5?.err || ""), "");
check("编译失败时不运行程序", !/这一行不该出现/.test(r5?.out || ""), "");

console.log("\n── C++ 未捕获异常：abort 前的输出不能丢 ──");
await setEditor([
  '#include <iostream>',
  'int main() {',
  '    std::cout << "异常之前的第一行\\n";',
  '    throw std::runtime_error("故意不捕获");',
  '    return 0;',
  '}',
].join("\n"));
await clickRun();
const r6 = await waitDone(90000);
console.log("   ", r6 ? r6.badge.replace(/\s+/g, " ") : "超时", "| out:", JSON.stringify((r6?.out || "").trim()));
check("异常导致非零退出码", !!r6 && !/退出码 0/.test(r6.badge), r6 ? r6.badge : "");
check("abort 之前的输出没丢", /异常之前的第一行/.test(r6?.out || ""), "");
check("stderr 有 terminate 说明", /terminate/.test(r6?.err || ""), "");
check("提示了 try/catch 这条线索", /try\/catch/.test(r6?.err || ""), "");

// 收尾：切回 Python，免得后面的套件以为控制台停在 C++
await evalJs(`(function(){
  const s=document.querySelector('.console-wrap .input.lang');
  if (s) { s.value='python'; s.dispatchEvent(new Event('change',{bubbles:true})); }
  return 1;})()`);

// 兜底：万一中途抛异常，别把那个"坏摘要"旁文件留在缓存目录里，
// 否则之后所有 Python 组件安装都会被它挡住。
if (sidecarWritten) { try { rmSync(pySide, { force: true }); } catch { /* 忽略 */ } }

check("全程没有 JS 异常", exceptions.length === 0, exceptions.slice(0, 2).join(" | "));

console.log(`\n═══ 控制台验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|cdp-console|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
