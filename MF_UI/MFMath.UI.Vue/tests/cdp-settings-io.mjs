// cdp-settings-io.mjs — 设置备份：导出 / 导入（换机迁移）
//
// 这一项最重要的一条不是"能导出"，而是**凭据不进备份、导入也不清凭据**：
// 写错的话用户会静默失去 API Key / 登录状态，而且很难查。所以断言围绕它展开。
//
// 走宿主的**自动化路径钩子**（SaveTextFile/OpenTextFile 的 path 参数非空则跳过原生对话框），
// 所以在用例里能跑完整链路，又不会弹出文件选择框。
import { readFileSync, existsSync, unlinkSync } from "node:fs";
import path from "node:path";
import { tmpdir } from "node:os";

const FILE = path.join(tmpdir(), "mfmath-settings-io-test.json");
if (existsSync(FILE)) unlinkSync(FILE);
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
const send = (method, params, timeoutMs = 40000) => new Promise((resolve) => {
  const mid = ++id;
  const h = (ev) => { const d = JSON.parse(ev.data); if (d.id === mid) { clearTimeout(timer); ws.removeEventListener("message", h); resolve(d); } };
  const timer = setTimeout(() => { ws.removeEventListener("message", h); resolve({ timeout: true, result: { result: { value: "[超时]" } } }); }, timeoutMs);
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
async function waitTrue(expr, ms = 12000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { if (await evalJs(expr) === true) return true; await sleep(150); }
  return false;
}

let ready = false;
for (let i = 0; i < 40; i++) {
  if (await evalJs(`typeof window.__mfSettingsIo === "object" && window.__mfSettingsIo !== null`) === true) { ready = true; break; }
  if (i === 12) await evalJs(`location.reload()`);
  await sleep(1000);
}
if (!ready) { console.error("页面未就绪：等不到 window.__mfSettingsIo"); try { ws.close(); } catch { /* 忽略 */ } process.exit(1); }

// 准备：一个探针设置文件（含一个**像凭据的**字段，用来验证字段级剥离）+ 一个外观偏好
await evalJs(`window.chrome.webview.hostObjects.sync.sys.StoreWrite("io-probe", JSON.stringify({ marker: "A", keep: { n: 1 }, apiKeyProtected: "SHOULD-NOT-APPEAR" }))`);
await evalJs(`localStorage.setItem("mf_theme", "dark")`);
await sleep(300);

console.log("=== ① 打包：内容与「不含凭据」===");
const built = String(await evalJs(`JSON.stringify(window.__mfSettingsIo.build())`));
const bundle = (() => { try { return JSON.parse(built).bundle; } catch { return null; } })();
check("打包成功", !!bundle, built.slice(0, 120));
check("包格式带 app / kind / version", bundle?.app === "MF-Mathematics" && bundle?.kind === "settings-bundle" && bundle?.version === 1,
  JSON.stringify({ app: bundle?.app, kind: bundle?.kind, version: bundle?.version }));
check("包含探针设置文件", !!bundle?.files?.["io-probe"], Object.keys(bundle?.files || {}).join(","));
check("**凭据文件被整份排除**（ai / account / search）",
  JSON.stringify(bundle?.excluded || []) === '["ai","account","search"]', JSON.stringify(bundle?.excluded));
check("包里没有 ai / account / search 三份文件",
  !bundle?.files?.ai && !bundle?.files?.account && !bundle?.files?.search, Object.keys(bundle?.files || {}).join(","));
check("**像凭据的字段被剥掉并记录**",
  !JSON.stringify(bundle).includes("SHOULD-NOT-APPEAR") && JSON.stringify(bundle?.stripped || []).includes("io-probe.apiKeyProtected"),
  JSON.stringify(bundle?.stripped || []));
check("普通字段保留（marker=A）", bundle?.files?.["io-probe"]?.marker === "A");
check("带上外观偏好（mf_ 前缀）", bundle?.prefs?.mf_theme === "dark", JSON.stringify(bundle?.prefs || {}).slice(0, 80));
// ⚠ 检查"包里有没有凭据"必须看**字段名**，不能拿整包文本做正则：
// `stripped` 数组本身就是"被剥掉的字段名"清单（那是刻意记录的），拿全文匹配会把自己人打了。
const secretKeys = (() => {
  const bad = [];
  const walk = (v, path0) => {
    if (Array.isArray(v)) return v.forEach((x, i) => walk(x, `${path0}[${i}]`));
    if (!v || typeof v !== "object") return;
    for (const [k, val] of Object.entries(v)) {
      if (/(protected|password|passwd|secret|token|api[-_]?key)/i.test(k)) bad.push(path0 ? `${path0}.${k}` : k);
      walk(val, path0 ? `${path0}.${k}` : k);
    }
  };
  walk(bundle?.files || {}, "");
  return bad;
})();
check("**设置文件里没有任何凭据字段**（按字段名递归检查，而不是看全文）",
  secretKeys.length === 0, JSON.stringify(secretKeys));
check("被剥掉的字段被记录在案（可追溯）", JSON.stringify(bundle?.stripped || []).includes("io-probe.apiKeyProtected"), JSON.stringify(bundle?.stripped || []));

console.log("=== ② 导出到文件（走宿主自动化钩子，不弹对话框）===");
const exp = String(await evalJs(`JSON.stringify(window.__mfSettingsIo.exportToFile(${JSON.stringify(FILE)}))`));
check("导出成功并给出路径与字节数", /"ok":true/.test(exp) && exp.includes("mfmath-settings-io-test.json"), exp.slice(0, 140));
check("文件真的写到磁盘了", existsSync(FILE), FILE);
const onDisk = existsSync(FILE) ? readFileSync(FILE, "utf8") : "";
check("磁盘上的内容与内存包一致（可解析且格式正确）", (() => { try { return JSON.parse(onDisk).kind === "settings-bundle"; } catch { return false; } })());
check("**磁盘上的备份里也没有凭据字段**（同样是看字段名）", (() => {
  try {
    const f = JSON.parse(onDisk).files || {};
    const bad = [];
    const walk = (v) => {
      if (Array.isArray(v)) return v.forEach(walk);
      if (!v || typeof v !== "object") return;
      for (const [k, val] of Object.entries(v)) {
        if (/(protected|password|passwd|secret|token|api[-_]?key)/i.test(k)) bad.push(k);
        walk(val);
      }
    };
    walk(f);
    return bad.length === 0;
  } catch { return false; }
})());
check("哨兵值没有出现在磁盘上", !onDisk.includes("SHOULD-NOT-APPEAR"));

console.log("=== ③ 导入：round-trip 覆盖 ===");
await evalJs(`window.chrome.webview.hostObjects.sync.sys.StoreWrite("io-probe", JSON.stringify({ marker: "B" }))`);
await evalJs(`localStorage.setItem("mf_theme", "light")`);
await sleep(250);
const imp = String(await evalJs(`JSON.stringify(window.__mfSettingsIo.importFromFile(${JSON.stringify(FILE)}))`));
check("导入成功并报告写入了多少", /"ok":true/.test(imp) && /"files":\d+/.test(imp), imp.slice(0, 140));
check("导入后**说明要重启**（设置与外观都在启动时读取，不假装即时生效）", /"needsRestart":true/.test(imp));
const back = String(await evalJs(`(() => { const r = JSON.parse(window.chrome.webview.hostObjects.sync.sys.StoreRead("io-probe")); return r.json; })()`));
check("设置文件被恢复成备份里的内容（marker 回到 A）", /"marker":"A"/.test(back) && !/"marker":"B"/.test(back), back.slice(0, 80));
check("外观偏好也被恢复（mf_theme 回到 dark）", (await evalJs(`localStorage.getItem("mf_theme")`)) === "dark");

console.log("=== ④ 坏包一律拒绝，且**不部分写入** ===");
const beforeProbe = String(await evalJs(`(() => { const r = JSON.parse(window.chrome.webview.hostObjects.sync.sys.StoreRead("io-probe")); return r.json; })()`));
const bad1 = String(await evalJs(`JSON.stringify(window.__mfSettingsIo.apply("这不是 JSON"))`));
check("非 JSON → 可读原因", /"ok":false/.test(bad1) && /合法的 JSON/.test(bad1), bad1.slice(0, 90));
const bad2 = String(await evalJs(`JSON.stringify(window.__mfSettingsIo.apply({ app: "MF-Mathematics", kind: "别的", version: 1 }))`));
check("kind 不对 → 说明类型不对", /"ok":false/.test(bad2) && /类型不对/.test(bad2), bad2.slice(0, 90));
const bad3 = String(await evalJs(`JSON.stringify(window.__mfSettingsIo.apply({ app: "MF-Mathematics", kind: "settings-bundle", version: 99, files: { "io-probe": { marker: "X" } } }))`));
check("来自更新版本的包 → 让用户先更新（拒绝）", /"ok":false/.test(bad3) && /先更新软件/.test(bad3), bad3.slice(0, 100));
const afterProbe = String(await evalJs(`(() => { const r = JSON.parse(window.chrome.webview.hostObjects.sync.sys.StoreRead("io-probe")); return r.json; })()`));
check("**被拒绝的导入没有改动任何文件**", beforeProbe === afterProbe, afterProbe.slice(0, 70));

console.log("=== ⑤ 导入不会清掉凭据（关键性质）===");
const beforeAi = String(await evalJs(`(() => { const r = JSON.parse(window.chrome.webview.hostObjects.sync.sys.StoreRead("ai")); return JSON.stringify({ ok: r.ok, exists: r.exists !== false, json: r.json || "" }); })()`));
// 手造一个**故意带凭据文件**的包：applyBundle 必须跳过它（否则会覆盖用户现在的密钥）
const evil = JSON.stringify({
  app: "MF-Mathematics", kind: "settings-bundle", version: 1,
  files: { ai: { apiKeyProtected: "EVIL" }, account: { tokenProtected: "EVIL" }, "io-probe": { marker: "C" } },
});
const evilRes = String(await evalJs(`JSON.stringify(window.__mfSettingsIo.apply(${JSON.stringify(evil)}))`));
check("含有凭据文件的包：那两份被跳过（并报告跳过）",
  /"ok":true/.test(evilRes) && /"skipped"/.test(evilRes) && /ai/.test(evilRes), evilRes.slice(0, 140));
const afterAi = String(await evalJs(`(() => { const r = JSON.parse(window.chrome.webview.hostObjects.sync.sys.StoreRead("ai")); return JSON.stringify({ ok: r.ok, exists: r.exists !== false, json: r.json || "" }); })()`));
check("**ai.json 内容未被改动**（导入不会清掉/覆盖密钥）", beforeAi === afterAi);
check("包里的其它文件照常写入（io-probe 变成 C）",
  /"marker":"C"/.test(String(await evalJs(`(() => { const r = JSON.parse(window.chrome.webview.hostObjects.sync.sys.StoreRead("io-probe")); return r.json; })()`))));

console.log("=== ⑥ 界面：存储与数据里的按钮（不再是'待实现'）===");
await evalJs(`location.hash = "#/settings?group=storage"`);
check("存储与数据分组可达", await waitTrue(`!!document.querySelector('[data-setting="storage.io"]')`, 10000));
check("有导出按钮", (await evalJs(`!!document.querySelector('[data-io=export]')`)) === true);
check("有导入按钮", (await evalJs(`!!document.querySelector('[data-io=import]')`)) === true);
check("**这一页不再有「待实现」标签**",
  (await evalJs(`document.querySelectorAll('[data-setting^="storage."] .pending-tag').length`)) === 0);
check("写清了备份范围与「不含密钥」",
  await evalJs(`(() => { const t = document.querySelector('[data-io=scope]').textContent; return /不含密钥/.test(t) && /重启后/.test(t); })()`) === true);
check("导入有二次确认", (await evalJs(`(() => {
  const b = document.querySelector('[data-io=import]'); b.click();
  return new Promise((r) => setTimeout(() => {
    const c = !!document.querySelector('[data-io=confirm]');
    const cancel = [...document.querySelectorAll('.s-btn')].find((x) => x.textContent.trim() === '取消');
    if (cancel) cancel.click();
    r(c);
  }, 250));
})()`)) === true);

// 收尾：删掉探针文件与用例造出来的设置，别污染用户环境
await evalJs(`window.chrome.webview.hostObjects.sync.sys.StoreDelete("io-probe")`);
await evalJs(`localStorage.removeItem("mf_theme")`);
if (existsSync(FILE)) unlinkSync(FILE);

console.log(`RESULT|cdp-settings-io|${pass}|${fail}`);
try { ws.close(); } catch { /* 忽略 */ }
process.exit(fail === 0 ? 0 : 1);
