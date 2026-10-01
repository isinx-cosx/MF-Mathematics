// 13 个学科模式的**界面渲染**验证
//
// 为什么单独一套：audit-modes 是绕过界面直接调引擎的（每个模式一个独立进程），
// 它证明的是"参数构造 + 引擎行为"对；但每个模式的**界面**是否真的把结果画出来，
// 只有被 CDP 套件实际点到的那些才有证据。这个套件把 13 个视图都走一遍，
// 每个视图挑几个有样本的模式真的点一次"计算结果"。
//
// 核心断言（不是"页面没报错"这种弱检查）：
//   ① **界面的成败判定必须与引擎一致**——引擎说成功，界面不许显示错误；
//      引擎说报错，界面不许显示"已计算"。这一条专门抓"看着正常其实算错"。
//   ② 引擎给的是数值时，**那个数必须出现在界面上**（按数值比较，不按字符串）。
//   ③ 公式结果必须被 KaTeX 真正排版过（有 .katex 节点），而不是把 LaTeX 原文吐出来。
//   ④ 每个视图都要有模式接入引擎；一个都没接入 = 这个视图是空壳。
//
// 样本来自 fixtures/mode-samples.mjs（与 audit-modes 共用）。
// 这一点是踩过坑的：第一版用**视图级**样本去点该视图的第一个模式，
// 结果 6 个视图"失败"——查下来全是样本喂错了模式
// （"1,2,3" 能当条件数的输入吗？不能；伯努利分布的 p 更不能）。
//
// 关于"像素级"：这里做的像素级检查只有一项——整页截图不能是空白（空白页 PNG 极小）。
// 真正的视觉正确性靠 ①②③ 这些断言，而不是数像素颜色；把边界说清楚比堆一个
// 看起来唬人的像素断言更有价值。
//
// 用法: node cdp-modes-render.mjs   （宿主需带 --remote-debugging-port=9222 启动）
import { VIEW_CONFIGS } from "../src/lib/engine/viewConfigs.js";
import { ENGINE_MAP } from "../src/lib/engine/engineMap.js";
import { buildEngineArgs } from "../src/lib/engine/calcArgs.js";
import { VIEW_SAMPLE } from "./fixtures/view-samples.mjs";
import { MODE_SAMPLE } from "./fixtures/mode-samples.mjs";

/** 每个视图最多真的点几个模式（317 个全跑一遍要十几分钟，没必要） */
const MODES_PER_VIEW = 3;

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
await send("Page.enable");
await sleep(1200);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

/** 直接问引擎（走与界面同一条桥），用来做"界面 vs 引擎"的一致性对照 */
const engineTruth = (fn, args) => evalJs(`(function(){
  const mf = window.chrome?.webview?.hostObjects?.sync?.mf;
  if (!mf) return { isError: true, value: "无桥" };
  try { return JSON.parse(mf.Dispatch(${JSON.stringify(fn)}, ${JSON.stringify(JSON.stringify(args))})); }
  catch (e) { return { isError: true, value: String(e && e.message || e) }; }
})()`);

const viewInfo = () => evalJs(`(function(){
  const sel = document.querySelector('.cb-mode');
  const opts = sel ? [...sel.options].map(o => ({
    value: o.value, mapped: o.dataset.mapped === 'true', varDialog: o.dataset.varDialog === 'true',
    label: o.textContent.trim(),
  })) : [];
  return {
    isPlaceholder: !!document.querySelector('.placeholder-view'),
    title: document.querySelector('.ws-title')?.textContent.trim() || '',
    hasInput: !!document.querySelector('.cb-input'),
    hasCalc: !!document.querySelector('.cb-calc'),
    options: opts,
    mapped: opts.filter(o => o.mapped).length,
    total: opts.length,
    foot: [...document.querySelectorAll('.ws-foot span')].map(e => e.textContent.trim()).join(' | '),
  };
})()`);

const setBlock = (expr, mode) => evalJs(`(function(){
  const inp = document.querySelector('.cb-input');
  if (!inp) return 'no-input';
  if (inp.tagName === 'MATH-FIELD') inp.value = ${JSON.stringify(expr)};
  else Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(inp, ${JSON.stringify(expr)});
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  if (${JSON.stringify(mode)}) {
    const sel = document.querySelector('.cb-mode');
    if (![...sel.options].some(o => o.value === ${JSON.stringify(mode)})) return 'no-mode';
    Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set.call(sel, ${JSON.stringify(mode)});
    sel.dispatchEvent(new Event('change', { bubbles: true }));
  }
  return 'ok';
})()`);

const clickCalc = () => evalJs(`(function(){
  const b = document.querySelector('.cb-calc'); if (!b) return 'no-btn'; b.click(); return 'clicked';
})()`);

/**
 * 等一次计算"落地"。
 * 注意：错误**不一定**走 .cb-error —— 引擎级错误是显示在结果弹窗里的
 * （第一版只找 .cb-ok/.cb-error，于是把"弹窗里已经写了错误"误判成超时）。
 */
const waitOutcome = async (timeoutMs = 15000) => {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    const s = await evalJs(`(function(){
      const dlg = document.querySelector('.dialog');
      const res = dlg ? (dlg.querySelector('.dialog-result')?.textContent.trim() || '') : '';
      return {
        inlineOk: !!(document.querySelector('.cb-ok')),
        inlineErr: (document.querySelector('.cb-error')?.textContent.trim() || ''),
        dialog: !!dlg,
        dialogResult: res,
        computing: /计算中/.test(document.querySelector('.cb-calc')?.textContent || ''),
      };
    })()`);
    if (s && (s.inlineOk || s.inlineErr || (s.dialog && s.dialogResult))) return s;
    await sleep(250);
  }
  return null;
};

const readDialog = () => evalJs(`(function(){
  const dlg = document.querySelector('.dialog');
  if (!dlg) return null;
  const resEl = dlg.querySelector('.dialog-result');
  return {
    header: dlg.querySelector('.dialog-header')?.textContent.trim() || '',
    text: resEl ? resEl.textContent.trim().slice(0, 300) : '',
    katex: resEl ? resEl.querySelectorAll('.katex').length : 0,
    tex: resEl ? [...resEl.querySelectorAll('[data-tex]')].map(e => e.getAttribute('data-tex')).join(' ') : '',
  };
})()`);
const closeDialog = async () => {
  await evalJs("document.querySelector('.dialog-close')?.click()");
  await sleep(200);
};

/** 从任意文本里抓出所有数值，用来做"引擎给的数必须出现在界面上"的比较 */
function numbersIn(text) {
  const out = [];
  const re = /-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?/g;
  let m;
  while ((m = re.exec(String(text))) !== null) out.push(Number(m[0]));
  return out.filter((n) => Number.isFinite(n));
}
const approxIn = (text, v) => numbersIn(text).some((n) => {
  if (n === v) return true;
  const scale = Math.max(1, Math.abs(v));
  return Math.abs(n - v) / scale < 1e-6;
});
/** 界面判定为"出错"的两种形态：行内 .cb-error，或弹窗里以「错误」开头的说明 */
const uiSaysError = (outcome, dialogText) =>
  !!outcome.inlineErr || /^\s*错误/.test(dialogText || "");

const views = Object.keys(VIEW_CONFIGS);
console.log(`── 13 个学科模式的界面渲染 ──`);
console.log(`   视图数: ${views.length}，每个视图最多真跑 ${MODES_PER_VIEW} 个模式\n`);

let ranModes = 0;
for (const key of views) {
  const cfg = VIEW_CONFIGS[key];
  console.log(`【${key}】${cfg.title || ""}`);

  await evalJs(`location.hash = '#/calc/${key}'`);
  await sleep(900);
  const info = await viewInfo();
  check(`  ${key}: 已渲染真实视图（不是占位页）`, !info?.isPlaceholder && !!info?.title, info?.title || "");
  check(`  ${key}: 有输入框与计算按钮`, !!info?.hasInput && !!info?.hasCalc, "");
  check(`  ${key}: 至少有一个模式接入了引擎`, (info?.mapped || 0) >= 1,
    `已接入 ${info?.mapped}/${info?.total}`);

  // 挑样本：只挑 fixtures 里有按模式样本的（视图级样本对第一个模式往往牛头不对马嘴）
  const candidates = (info?.options || [])
    .filter((o) => o.mapped && Object.prototype.hasOwnProperty.call(MODE_SAMPLE, o.value))
    .filter((o) => !o.varDialog)                 // 参数弹窗是另一个套件的事
    .slice(0, MODES_PER_VIEW);
  if (!candidates.length) {
    // 全都没样本就退回视图级样本跑第一个已接入模式，至少证明这条路能走通
    const fallback = (info?.options || []).find((o) => o.mapped);
    if (fallback) candidates.push({ ...fallback, __fallbackSample: VIEW_SAMPLE[key] ?? "" });
  }

  for (const target of candidates) {
    ranModes++;
    const sample = target.__fallbackSample !== undefined
      ? target.__fallbackSample
      : MODE_SAMPLE[target.value];
    const setRes = await setBlock(sample, target.value);
    if (setRes !== "ok") {
      check(`  ${key}/${target.value}: 能写入表达式`, false, String(setRes));
      continue;
    }
    await clickCalc();
    const outcome = await waitOutcome();
    if (!outcome) {
      check(`  ${key}/${target.value}: 计算在 15 秒内落地`, false,
        "既没出现'已计算/错误'行，也没弹出结果弹窗");
      continue;
    }
    const dlg = await readDialog();
    const dialogText = dlg?.text || "";
    const uiErr = uiSaysError(outcome, dialogText);

    // ① 界面成败 vs 引擎成败 —— 本节核心
    const args = buildEngineArgs(target.value, sample) || {};
    const fnName = ENGINE_MAP[target.value]?.fn || null;
    const truth = fnName ? await engineTruth(fnName, args) : null;
    if (!truth) {
      check(`  ${key}/${target.value}: 能定位到引擎函数名（用于对照）`, false, "ENGINE_MAP 里没有 fn");
    } else {
      check(`  ${key}/${target.value}: 界面成败与引擎一致（引擎${truth.isError ? "报错" : "成功"}）`,
        !!truth.isError === uiErr,
        `界面: ${uiErr ? "错误" : "已计算"} | 引擎: ${truth.isError ? "错误 " + String(truth.value).slice(0, 30) : "成功"}`);
    }

    if (uiErr) {
      // 引擎确实报错时，界面给出可读错误是正确行为
      console.log(`     界面显示错误：${(outcome.inlineErr || dialogText).slice(0, 70)}`);
    } else {
      // ② 引擎给数值时，那个数必须出现在界面上
      if (truth && typeof truth.value === "number") {
        const hay = `${dialogText} ${dlg?.tex || ""}`;
        check(`  ${key}/${target.value}: 引擎的数值 ${truth.value} 出现在界面上`,
          approxIn(hay, truth.value), `界面: ${dialogText.slice(0, 70)}`);
      }
      // ③ 公式必须被真正排版（KaTeX 节点），而不是把 LaTeX 原文吐出来
      check(`  ${key}/${target.value}: 结果弹窗有内容`,
        (dlg?.text || dlg?.tex || "").length > 0, (dlg?.text || "").slice(0, 60));
      const looksTex = /\\\\|\$|\\frac|\\sqrt/.test(dialogText);
      check(`  ${key}/${target.value}: 公式已排版（或本来就是纯文本结果）`,
        (dlg?.katex || 0) > 0 || !looksTex, `katex=${dlg?.katex}`);
    }

    await closeDialog();
  }

  // 整页截图不能是空白（空白页的 PNG 极小）
  const shot = await send("Page.captureScreenshot", { format: "png" });
  const bytes = shot?.result?.data ? Math.floor(shot.result.data.length * 0.75) : 0;
  check(`  ${key}: 页面确实绘制了内容（截图非空白）`, bytes > 8000, `${bytes} 字节`);
}

/* 收尾：回到首页，别把其它套件留在某个计算页上 */
await evalJs("location.hash = '#/'");
await sleep(400);
check("实际跑过的模式数达到预期（每视图 ≥2）", ranModes >= views.length * 2, `${ranModes} 个`);
check("全程没有 JS 异常", exceptions.length === 0, exceptions.slice(0, 2).join(" | "));

console.log(`\n═══ 模式渲染验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|cdp-modes-render|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
