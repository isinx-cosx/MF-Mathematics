// 复平面绘图验证（对应 MF_UI/plot/complex/workspace.py 的原版功能）
//
// 【重做后的新套件，替代旧的 cdp-plot-complex】旧版检验的是"多项式求根标点"，
// 而那个功能已经按原版换成了复变函数可视化，旧断言整体失效，所以整份重写。
// 本套件验证原版的五种模式：相位图 / 3D 模长曲面 / 向量场式 / HSV 域着色 / 共形映射网格。
//
// 断言不只看"画出来了"，而是对着**数学上应有的样子**：
//   · 相位图：色相 = 辐角。f(z)=z² 在 z=1 处 arg=0，在 z=i 处 arg=π，
//     两处色相必须差得远——只检查"有颜色"抓不出相位算错。
//   · HSV 与相位图必须给出**不同**的像素（两者差别只在明度用 mag/max 还是 log1p）
//   · 共形映射：w 平面里既要有水平线的蓝，也要有垂直线的红
//   · 原版明确支持的 zeta/gamma/erf 必须能画，不是空白
//   · 算不了的函数必须**明确报出来**，不能画一张空白图让人以为函数就是这样
//
// 用法: node cdp-complex-modes.mjs   （宿主需带 --remote-debugging-port=9222 启动）
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
const send = (method, params, timeoutMs = 60000) => new Promise((resolve) => {
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
await sleep(1000);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

/* ── 页面操作 ── */
const setExpr = (v) => evalJs(`(function(){
  const i = document.querySelector('.plot-side .input.mono');
  if (!i) return 'no-input';
  Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(i, ${JSON.stringify(v)});
  i.dispatchEvent(new Event('input', { bubbles: true }));
  return 'ok';
})()`);
const clickApply = () => evalJs(`(function(){
  const b = [...document.querySelectorAll('.plot-side .btn')].find((x) => /应用/.test(x.textContent));
  if (!b) return 'no-btn'; if (b.disabled) return 'disabled'; b.click(); return 'clicked';
})()`);
const pickMode = (name) => evalJs(`(function(){
  const b = [...document.querySelectorAll('.plot-side .mode-btn')].find((x) => x.textContent.trim() === ${JSON.stringify(name)});
  if (!b) return 'no-mode'; b.click(); return 'picked';
})()`);
const waitSettled = async (timeoutMs = 60000) => {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    const s = await evalJs(`(function(){
      const st=(document.querySelector('.plot-side .status')||{}).textContent||'';
      const b=[...document.querySelectorAll('.plot-side .btn')].find(x=>/应用|计算中/.test(x.textContent));
      return { st, busy: b ? /计算中/.test(b.textContent) : false };
    })()`);
    if (s && !s.busy && !/计算中/.test(s.st || "")) return s.st;
    await sleep(300);
  }
  return null;
};
/** 画布像素统计：颜色数、蓝/红像素数、指定相对位置的颜色与色相 */
const probe = (points = []) => evalJs(`(function(){
  const c = document.querySelector('.complex-canvas');
  if (!c) return null;
  const ctx = c.getContext('2d');
  const { width: W, height: H } = c;
  const d = ctx.getImageData(0, 0, W, H).data;
  const uniq = new Set();
  let blue = 0, red = 0;
  for (let i = 0; i < d.length; i += 4) {
    const r = d[i], g = d[i + 1], b = d[i + 2];
    uniq.add((r >> 3) + ',' + (g >> 3) + ',' + (b >> 3));
    if (b > r + 40 && b > g + 20) blue++;
    if (r > g + 60 && r > b + 60) red++;
  }
  const hue = (rgb) => {
    const [r, g, b] = rgb.map((v) => v / 255);
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b), dd = mx - mn;
    if (dd < 1e-6) return -1;
    let h;
    if (mx === r) h = ((g - b) / dd) % 6; else if (mx === g) h = (b - r) / dd + 2; else h = (r - g) / dd + 4;
    return ((h * 60) + 360) % 360;
  };
  const px = ${JSON.stringify(points)}.map(([fx, fy]) => {
    const x = Math.round(fx * (W - 1)), y = Math.round(fy * (H - 1));
    const o = (y * W + x) * 4;
    const rgb = [d[o], d[o + 1], d[o + 2]];
    return { rgb, hue: Math.round(hue(rgb)) };
  });
  return { W, H, uniq: uniq.size, blue, red, px };
})()`);
const hueGap = (a, b) => {
  if (a < 0 || b < 0) return 0;
  const d = Math.abs(a - b);
  return Math.min(d, 360 - d);
};

console.log("── 复平面绘图：五模式 ──");
await evalJs("location.hash = '#/'");
await sleep(500);
await evalJs("location.hash = '#/plot/complex'");
await sleep(1500);

const shell = await evalJs(`(function(){
  const modes = [...document.querySelectorAll('.plot-side .mode-btn')].map((b) => b.textContent.trim());
  return {
    title: (document.querySelector('.plot-side .ws-title')||{}).textContent||'',
    hasInput: !!document.querySelector('.plot-side .input.mono'),
    modes,
    canvas: !!document.querySelector('.complex-canvas'),
    nums: document.querySelectorAll('.plot-side .input.num').length,
  };
})()`);
console.log("   模式:", JSON.stringify(shell.modes));
check("是复变函数可视化视图（原版功能，不是求根标点）", /复数/.test(shell.title) && shell.hasInput, shell.title);
check("五种模式齐全", shell.modes.length === 5 &&
  ["相位图", "3D 模长曲面", "向量场式", "HSV 域着色", "共形映射网格"].every((n) => shell.modes.includes(n)),
  shell.modes.join("/"));
check("有绘图范围与分辨率输入", shell.nums >= 5, shell.nums + " 个");
check("有画布", shell.canvas);

/* ── ① 相位图：色相 = 辐角 ── */
console.log("\n── ① 相位图（f(z)=z^2）──");
await setExpr("z^2");
await clickApply();
let st = await waitSettled();
console.log("   状态:", JSON.stringify(String(st).slice(0, 90)));
let p = await probe([[0.82, 0.5], [0.5, 0.10]]);
console.log("   像素:", JSON.stringify(p?.px));
check("计算完成并报告了模式与耗时", /已绘制/.test(String(st)) && /相位图/.test(String(st)), String(st).slice(0, 80));
check("画布不是空白（颜色数 > 80）", (p?.uniq || 0) > 80, String(p?.uniq));
const hueRight = p?.px?.[0]?.hue ?? -1;
const hueTop = p?.px?.[1]?.hue ?? -1;
check("右中与上中的色相明显不同（对应 arg=0 与 arg=π）", hueGap(hueRight, hueTop) > 90,
  `右 ${hueRight}° vs 上 ${hueTop}° 差 ${hueGap(hueRight, hueTop)}°`);

/* ── ② HSV 域着色必须与相位图不同 ── */
console.log("\n── ② HSV 域着色 vs 相位图 ──");
const phaseRgb = JSON.stringify(p?.px?.[0]?.rgb);
await pickMode("HSV 域着色");
await sleep(1200);
st = await waitSettled(40000);
const p2 = await probe([[0.82, 0.5]]);
check("切到 HSV 域着色会重新计算并重绘", /已绘制/.test(String(st)) && /HSV/.test(String(st)), String(st).slice(0, 70));
check("HSV 与相位图的像素不同（明度公式确实不一样）",
  JSON.stringify(p2?.px?.[0]?.rgb) !== phaseRgb, `相位图 ${phaseRgb} vs HSV ${JSON.stringify(p2?.px?.[0]?.rgb)}`);

/* ── ③ 向量场式 ── */
console.log("\n── ③ 向量场式 ──");
await pickMode("向量场式");
await sleep(1500);
st = await waitSettled(40000);
const p3 = await probe();
console.log("   状态:", JSON.stringify(String(st).slice(0, 80)), "颜色数:", p3?.uniq);
check("向量场画出来了", /已绘制/.test(String(st)) && (p3?.uniq || 0) > 20, String(p3?.uniq));
check("箭头带辐角色相（不是整屏一个色）", (p3?.uniq || 0) > 40, String(p3?.uniq));

/* ── ④ 3D 模长曲面 ── */
console.log("\n── ④ 3D 模长曲面 ──");
await pickMode("3D 模长曲面");
await sleep(1500);
st = await waitSettled(60000);
const p4 = await probe();
console.log("   状态:", JSON.stringify(String(st).slice(0, 80)), "颜色数:", p4?.uniq);
check("3D 曲面画出来了", /已绘制/.test(String(st)) && /3D/.test(String(st)), String(st).slice(0, 70));
check("曲面有颜色层次（viridis 渐变）", (p4?.uniq || 0) > 60, String(p4?.uniq));

/* ── ⑤ 共形映射网格 ── */
console.log("\n── ⑤ 共形映射网格 ──");
await pickMode("共形映射网格");
await sleep(2500);
st = await waitSettled(90000);
const p5 = await probe();
console.log("   状态:", JSON.stringify(String(st).slice(0, 90)));
console.log("   蓝像素:", p5?.blue, " 红像素:", p5?.red);
check("共形映射画出来了", /已绘制/.test(String(st)) && /共形/.test(String(st)), String(st).slice(0, 70));
check("有水平线的蓝与垂直线的红（原版配色）", (p5?.blue || 0) > 200 && (p5?.red || 0) > 200,
  `蓝 ${p5?.blue} / 红 ${p5?.red}`);

/* ── ⑥ 原版支持的特殊函数 ── */
console.log("\n── ⑥ 特殊函数 zeta / gamma / erf（原版明确支持）──");
for (const [fn, label] of [["zeta(z)", "zeta"], ["gamma(z)", "gamma"], ["erf(z)", "erf"]]) {
  await pickMode("HSV 域着色");
  await sleep(300);
  await setExpr(fn);
  await clickApply();
  const s = await waitSettled(180000);
  const pz = await probe();
  console.log(`   ${fn}: ${JSON.stringify(String(s).slice(0, 70))}  颜色数 ${pz?.uniq}`);
  check(`${label}(z) 能画出来`, /已绘制/.test(String(s)) && (pz?.uniq || 0) > 60, String(s).slice(0, 60));
}

/* ── ⑦ 算不了的函数必须明确报错 ── */
console.log("\n── ⑦ 不支持的函数要明确报出来 ──");
await setExpr("besselj(0,z)");
await clickApply();
const sErr = await waitSettled(30000);
console.log("   状态:", JSON.stringify(String(sErr).slice(0, 100)));
check("不支持的函数给出可读错误（不是空白图）",
  !/已绘制/.test(String(sErr)) && String(sErr).trim().length > 0, String(sErr).slice(0, 80));

/* ── ⑧ 范围提示 ── */
console.log("\n── ⑧ 范围提示 ──");
await setExpr("z^2");
await evalJs(`(function(){
  const i=[...document.querySelectorAll('.plot-side .input.num')];
  const set=(el,v)=>{Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set.call(el,String(v));
    el.dispatchEvent(new Event('input',{bubbles:true}));};
  set(i[0],-200); set(i[1],200);
  return 1;})()`);
await sleep(500);
check("范围超过 100 时给出提示", (await evalJs("!!document.querySelector('.plot-side .warn')")) === true, "");

await evalJs("location.hash = '#/'");
await sleep(400);
check("全程没有 JS 异常", exceptions.length === 0, exceptions.slice(0, 2).join(" | "));

console.log(`\n═══ 复平面绘图验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|cdp-complex-modes|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
