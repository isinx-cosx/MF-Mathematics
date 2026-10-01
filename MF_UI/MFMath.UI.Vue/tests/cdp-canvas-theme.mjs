// 绘图各画布是否跟随配色深浅（深色配色下不能还是白底）。
//
// 背景：
//   bridge.js:163-177 明确记录了这类历史事故——"数据的 theme 属性从来没有人传值，
//   画布永远走默认的 light"。桥里为此提供了 plotMode(explicit) 与 mf-appearance 广播。
//   但重写版把主题默认值写成了 "light"（SurfaceCanvas/VectorFieldCanvas/
//   GeometryCanvas/PlotCanvas 的 theme prop），而各视图**从不传** :theme，
//   于是 plotMode("light") 恒为 "light" → 切到深色配色，画布依然是白底。
//   原版是跟着主题走的（plot_colors.set_axes_theme(dark) 会切换轴/网格/背景色）。
//
// 判据（对 2D / 3D / 向量场 / 自由几何四个画布）：
//   统计"接近纯白"像素占比 whiteFrac。
//   浅色配色下背景是白的 → whiteFrac 高；
//   深色配色下背景变暗 → whiteFrac 必须显著下降。
//   修好前：两种配色下 whiteFrac 几乎不变（都是白底）。
//
// 用法: node tests/cdp-canvas-theme.mjs   （需宿主已带 --remote-debugging-port=9222 启动）
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
const send = (method, params, timeoutMs = 25000) => new Promise((resolve) => {
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
await send("Runtime.enable");
await sleep(1500);

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

/** 画布上"接近纯白"像素的占比 */
const whiteFrac = () => evalJs(`(function(){
  const cv = document.querySelector('canvas');
  if (!cv) return -1;
  const d = cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;
  let w = 0, n = 0;
  for (let i = 0; i < d.length; i += 4) {
    n++;
    if (d[i] > 225 && d[i+1] > 225 && d[i+2] > 225) w++;
  }
  return n ? w / n : -1;
})()`);

/** 用 localStorage + reload 切配色：不依赖外观弹窗的 DOM 结构 */
const setThemeAndReload = async (theme) => {
  await evalJs(`localStorage.setItem('mf_theme', ${JSON.stringify(theme)}); location.reload(); 'ok'`);
  await sleep(4500);
};
const gotoRoute = async (hash) => {
  await evalJs(`location.hash = ${JSON.stringify(hash)}; 'ok'`);
  await sleep(3000);
};

/** 3D 视图的投影缩放与 domain 无关（SurfaceCanvas scale = min(w,h)*0.22），
 *  默认 domain=5 时曲面铺满整个画布、背景一点都看不见 —— 那样就量不出底色。
 *  这里先把定义域滑块收到 1，让曲面缩小、露出背景，再量底色。 */
const shrink3D = async () => {
  await evalJs(`(function(){
    const r = document.querySelectorAll('input[type=range]')[0];
    if (!r) return 'no-range';
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setter.call(r, '1');
    r.dispatchEvent(new Event('input', { bubbles: true }));
    return 'ok';
  })()`);
  await sleep(1200);
};

const ROUTES = [
  { hash: "#/plot/2d", name: "2D 绘图 (PlotCanvas)" },
  { hash: "#/plot/3d", name: "3D 曲面 (SurfaceCanvas)", prep: shrink3D },
  { hash: "#/plot/vector", name: "向量场 (VectorFieldCanvas)" },
  { hash: "#/plot/geometry", name: "自由几何 (GeometryCanvas)" },
];

const measure = async () => {
  const out = {};
  for (const r of ROUTES) {
    await gotoRoute(r.hash);
    if (r.prep) await r.prep();
    out[r.hash] = await whiteFrac();
  }
  return out;
};

console.log("── 切到深色配色后，各画布是否变暗 ──");
await setThemeAndReload("glass-light");
const light = await measure();
console.log("   浅色配色 whiteFrac:", JSON.stringify(light));

await setThemeAndReload("neon-dark");
const dark = await measure();
console.log("   深色配色 whiteFrac:", JSON.stringify(dark));
console.log("   当前 data-mode:", await evalJs("document.documentElement.dataset.mode"));

for (const r of ROUTES) {
  const l = light[r.hash], d = dark[r.hash];
  check(`${r.name}：浅色下是浅底且深色下明显变暗`,
        l > 0.10 && d < 0.05 && d < l * 0.5,
        `light=${typeof l === "number" ? l.toFixed(3) : l} dark=${typeof d === "number" ? d.toFixed(3) : d}`);
}

// 收尾：恢复浅色配色，避免污染后续测试套件
await setThemeAndReload("glass-light");
const restored = await evalJs("document.documentElement.dataset.theme + '/' + document.documentElement.dataset.mode");
console.log("   已恢复配色:", restored);
check("收尾恢复为 glass-light/light", restored === "glass-light/light", restored);

console.log(`\n═══ 画布跟随配色验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|canvas-theme|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
