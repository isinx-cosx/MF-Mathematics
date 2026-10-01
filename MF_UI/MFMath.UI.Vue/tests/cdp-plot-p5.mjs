// 验证 P5 自适应采样 + P2 极坐标网格
// 用法: node cdp-plot-p5.mjs
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
const send = (method, params, timeoutMs = 20000) => new Promise((resolve) => {
  const mid = ++id;
  const h = (ev) => {
    const d = JSON.parse(ev.data);
    if (d.id === mid) { clearTimeout(timer); ws.removeEventListener("message", h); resolve(d); }
  };
  // 超时保护：页面无响应时不让脚本永久挂起
  const timer = setTimeout(() => {
    ws.removeEventListener("message", h);
    resolve({ timeout: true, result: { result: { value: "[超时] 页面未在 " + timeoutMs + "ms 内响应" } } });
  }, timeoutMs);
  ws.addEventListener("message", h);
  ws.send(JSON.stringify({ id: mid, method, params }));
});
const evalJs = async (expr) => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return "[异常] " + (r.result.exceptionDetails.text || "");
  return r.result?.result?.value;
};
await send("Runtime.enable");
await sleep(1500);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

async function setExprs(texts) {
  await evalJs(`(function(){
    const cur = document.querySelectorAll('.expr-input').length;
    const need = ${texts.length} - cur;
    for (let k = 0; k < need; k++) document.querySelector('.add-row')?.click();
    return 'ok';
  })()`);
  await sleep(500);
  await evalJs(`(function(){
    // 输入框可能是 MathLive 的 <math-field>（数学就地排版）或普通 input，两种都支持：
    const setter = { call: (el, v) => { if (el && el.tagName === 'MATH-FIELD') { el.value = v; } else { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); } } };
    const texts = ${JSON.stringify(texts)};
    [...document.querySelectorAll('.expr-input')].forEach((inp, i) => {
      setter.call(inp, texts[i] || '');
      inp.dispatchEvent(new Event('input', { bubbles: true }));
    });
    return 'ok';
  })()`);
  await sleep(2200);
}

/** 读取采样点数（从状态栏）与画布像素统计。
 *
 *  · curve：与**第一条曲线的颜色**相近的像素数 —— 这是"曲线画得够不够密"的直接度量。
 *    之前用的是"深色像素(dark)"，那条断言其实**隐含依赖深色主题**：
 *    浅色主题下网格与坐标轴都不够暗，计数会从 >2000 掉到 ~1000 而误判失败。
 *    按曲线颜色统计与主题无关，才是在测本来想测的东西。
 *  · painted：非背景像素（网格 + 曲线），用于判断画布确实被重绘过。 */
const readState = () => evalJs(`(function(){
  const status = document.querySelector('.side-status')?.textContent || '';
  const m = status.match(/(\\d+)\\s*点/);
  const cv = document.querySelector('canvas');
  // 曲线颜色取自表达式行的颜色圆点
  let cr = 45, cg = 112, cb = 179;
  const dot = document.querySelector('.color-dot');
  if (dot) {
    const s = getComputedStyle(dot).backgroundColor || '';
    const p = s.match(/rgba?\\(([^)]+)\\)/);
    if (p) {
      const v = p[1].split(',').map(x => parseFloat(x));
      if (v.length >= 3) { cr = v[0]; cg = v[1]; cb = v[2]; }
    }
  }
  let dark = 0, painted = 0, curve = 0, total = 0;
  if (cv) {
    const ctx = cv.getContext('2d');
    const d = ctx.getImageData(0,0,cv.width,cv.height).data;
    total = d.length/4;
    // 背景取左上角像素，避免"浅色主题下白底被算成 painted"的偏差
    const br = d[0], bg = d[1], bb = d[2];
    for (let i=0;i<d.length;i+=4) {
      if (d[i]<80 && d[i+1]<80 && d[i+2]<80) dark++;
      if (!(Math.abs(d[i]-br)<6 && Math.abs(d[i+1]-bg)<6 && Math.abs(d[i+2]-bb)<6)) painted++;
      if (Math.abs(d[i]-cr)<50 && Math.abs(d[i+1]-cg)<50 && Math.abs(d[i+2]-cb)<50) curve++;
    }
  }
  return { status, points: m ? +m[1] : -1, dark, painted, curve, total };
})()`);

await evalJs("location.hash = '#/plot/2d'");
await sleep(1200);
// 重置到干净状态（清点 / 重置视图 / 只保留 1 行表达式），保证脚本可独立或连续运行
await evalJs(`(function(){
  // 清除已创建的点
  const clearBtn = [...document.querySelectorAll('.link-btn')].find(b => (b.textContent||'').includes('全部清除'));
  if (clearBtn) clearBtn.click();
  // 重置视图（缩放/平移归位）
  const resetBtn = document.querySelector('[title="重置视图"]');
  if (resetBtn) resetBtn.click();
  return 'ok';
})()`);
await sleep(500);
await evalJs(`(function(){
  let guard = 0;
  while (document.querySelectorAll('.expr-input').length > 1 && guard++ < 30) {
    const rows = [...document.querySelectorAll('.expr-row')];
    const del = rows.length ? rows[rows.length - 1].querySelector('.del-btn') : null;
    if (!del) break;
    del.click();
  }
  const setter = { call: (el, v) => { if (el && el.tagName === 'MATH-FIELD') { el.value = v; } else { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); } } };
  const first = document.querySelector('.expr-input');
  if (first) { setter.call(first, ''); first.dispatchEvent(new Event('input', { bubbles: true })); }
  return 'ok';
})()`);
await sleep(800);

/* ── ① 平滑函数：自适应采样不应过度加密（点数接近初始 300）── */
console.log("── 自适应采样：平滑函数（y=x^2）──");
await setExprs(["y=x^2"]);
let st = await readState();
console.log("   状态:", st.status);
console.log("   采样点数:", st.points);
check("平滑函数采样成功", st.points > 0, st.status);
const smoothPts = st.points;
check("平滑函数点数不过度膨胀（< 900）", st.points < 900, String(st.points));

/* ── ② 高频振荡函数：自适应应显著加密（Desmos 画质关键）── */
console.log("\n── 自适应采样：高频函数（y=sin(20x)）──");
await setExprs(["y=sin(20*x)"]);
st = await readState();
console.log("   状态:", st.status);
console.log("   采样点数:", st.points, "（平滑函数为", smoothPts, "）");
check("高频函数采样成功", st.points > 0, st.status);
check("高频函数点数显著多于平滑函数（自适应加密生效）",
  st.points > smoothPts * 1.3, `${st.points} vs ${smoothPts}`);

/* ── ③ 高曲率处加密的可视化证据：曲线像素密度 ── */
console.log("\n── 曲线质量（像素）──");
const highFreq = st;
// 与主题无关的判据：统计"曲线颜色"的像素数
check("高频曲线绘制充分（曲线颜色像素 > 3000）", highFreq.curve > 3000, "curve=" + highFreq.curve + " painted=" + highFreq.painted);

/* ── ④ 极坐标网格切换（Desmos 投影模式）── */
console.log("\n── 极坐标网格切换 ──");
await setExprs(["r=2*cos(3*theta)"]);
const beforePolar = await readState();
// 点击极坐标网格按钮
const clicked = await evalJs(`(function(){
  const btns = [...document.querySelectorAll('.vc-btn')];
  const b = btns.find(x => (x.getAttribute('title')||'').includes('极坐标网格'));
  if (!b) return 'not-found';
  b.click(); return 'clicked';
})()`);
await sleep(1200);
const afterPolar = await readState();
const btnState = await evalJs(`(function(){
  const btns = [...document.querySelectorAll('.vc-btn')];
  const b = btns.find(x => (x.getAttribute('title')||'').includes('直角网格'));
  return { found: !!b, active: btns.filter(x=>x.classList.contains('on')).length };
})()`);
console.log("   点击结果:", clicked, "| 按钮已切换:", JSON.stringify(btnState));
console.log("   切换前深色像素:", beforePolar.dark, "→ 切换后:", afterPolar.dark);
check("极坐标网格按钮可点击", clicked === "clicked", clicked);
check("切换后画布重绘（网格变化）", beforePolar.dark !== afterPolar.dark, `${beforePolar.dark} → ${afterPolar.dark}`);
check("按钮进入激活态", btnState.active >= 1, JSON.stringify(btnState));

/* ── ⑤ 网格显示/隐藏开关 ── */
console.log("\n── 网格显示开关 ──");
const beforeHide = await readState();
const hideClicked = await evalJs(`(function(){
  const btns = [...document.querySelectorAll('.vc-btn')];
  const b = btns.find(x => (x.getAttribute('title')||'').includes('隐藏网格'));
  if (!b) return 'not-found';
  b.click(); return 'clicked';
})()`);
await sleep(1000);
const afterHide = await readState();
console.log("   点击:", hideClicked, "| 隐藏前非白像素:", beforeHide.painted, "→ 隐藏后:", afterHide.painted);
check("网格开关可点击", hideClicked === "clicked", hideClicked);
check("隐藏网格后浅色网格像素消失（非白像素减少）",
  afterHide.painted < beforeHide.painted, `${beforeHide.painted} → ${afterHide.painted}`);
// 隐藏网格只应影响网格像素；曲线像素数应基本不变。
// （原来比较"深色像素"，而浅色主题下那主要是网格线本身，测的不是曲线。）
check("隐藏网格后曲线仍在（曲线像素基本不变）",
  Math.abs(afterHide.curve - beforeHide.curve) <= Math.max(50, beforeHide.curve * 0.05),
  `${beforeHide.curve} → ${afterHide.curve}`);

/* ── ⑥ 恢复直角网格 + 显示网格 ── */
await evalJs(`(function(){
  const btns = [...document.querySelectorAll('.vc-btn')];
  btns.find(x => (x.getAttribute('title')||'').includes('直角网格'))?.click();
  return 'ok';
})()`);
await sleep(500);
await evalJs(`(function(){
  const btns = [...document.querySelectorAll('.vc-btn')];
  btns.find(x => (x.getAttribute('title')||'').includes('显示网格'))?.click();
  return 'ok';
})()`);
await sleep(1000);
const restored = await readState();
console.log("   恢复后状态:", restored.status);
check("可恢复直角网格与网格显示", restored.dark > 0, String(restored.dark));

console.log(`\n═══ P5/P2 验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|plot-p5|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
