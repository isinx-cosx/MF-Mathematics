// 外观选择器验证：配色更多、能预览、四组维度各自生效、选择被记住
//
// 为什么单独一套：改版前的入口是「点一下就循环到下一套配色」，只有 4 套且看不出差别；
// 现在要证明的是"能挑"，而不只是"能换"。所以断言围绕：
//   · 面板里确实有 10 套配色卡，而且**每张卡的预览用的是那套主题的真实 CSS 变量**
//     （读 computedStyle 比较，不是看它写了什么 class）
//   · 圆角/疏密/字体能各自独立改，且改一个不动其它
//   · 跟随系统可勾选，勾上后配色变成与系统一致的深浅版本
//   · 选完关掉弹层，刷新后选择仍在（localStorage）
// 用法: node cdp-appearance.mjs   （宿主需带 --remote-debugging-port=9222 启动）
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

const openPanel = () => evalJs(`(function(){
  if (document.querySelector('.appearance-pop')) return 'already';
  const b = [...document.querySelectorAll('.nav-btn')].find((x) => x.title === '切换主题');
  if (!b) return 'no-btn';
  b.click(); return 'opened';
})()`);
const closePanel = () => evalJs(`(function(){
  const p = document.querySelector('.appearance-pop');
  if (!p) return 'closed';
  p.querySelector('.ap-close').click(); return 'closed';
})()`);
const attrsOf = () => evalJs(`(function(){
  const cs = getComputedStyle(document.documentElement);
  const bs = getComputedStyle(document.body);
  return {
    theme: document.documentElement.dataset.theme,
    mode: document.documentElement.dataset.mode,
    shape: document.documentElement.dataset.shape,
    density: document.documentElement.dataset.density,
    font: document.documentElement.dataset.font,
    bg: cs.getPropertyValue('--bg').trim(),
    rXl: cs.getPropertyValue('--r-xl').trim(),
    // 界面字体要读 body：font-family 是写在 body 上的，读 <html> 只会拿到浏览器默认值
    fontUi: bs.fontFamily,
    bodySize: bs.fontSize,
  };
})()`);

// 记录进入本套件前的外观，收尾时还原（各套件共用同一宿主实例）
const origin = await attrsOf();
console.log("── 外观选择器 ──");
console.log("   进入时:", JSON.stringify({ theme: origin.theme, shape: origin.shape, density: origin.density, font: origin.font }));

/* ── ① 入口不再是"点一下就切换"，而是弹出可挑的面板 ── */
await evalJs("location.hash = '#/'");
await sleep(500);
const beforeTheme = origin.theme;
check("入口能打开面板", (await openPanel()) === "opened");
await sleep(300);
const panel = await evalJs(`(function(){
  const p = document.querySelector('.appearance-pop');
  if (!p) return null;
  return {
    exists: true,
    cards: [...p.querySelectorAll('.tp-card')].map((c) => c.dataset.theme),
    labels: [...p.querySelectorAll('.tp-card .tp-name')].map((x) => x.textContent.trim()),
    shapes: [...p.querySelectorAll('.ap-row')][0] ? [...p.querySelectorAll('.ap-row')][0].querySelectorAll('.ap-seg').length : 0,
    rows: p.querySelectorAll('.ap-row').length,
    hasFollow: !!p.querySelector('.ap-follow input[type=checkbox]'),
    outside: (function(r){return {w:r.width,h:r.height,left:r.left,bottom:r.bottom};})(p.getBoundingClientRect()),
  };
})()`);
check("面板已出现", !!panel?.exists);
check("只是打开面板，没有顺手改掉配色",
  (await evalJs("document.documentElement.dataset.theme")) === beforeTheme, beforeTheme);
check("配色卡至少 8 套（改版前只有 4 套且看不出来）", (panel?.cards?.length || 0) >= 8,
  (panel?.cards?.length || 0) + " 套：" + (panel?.labels || []).join("/"));
check("浅色与深色都有多套可选",
  (panel?.cards || []).filter((c) => /light/.test(c)).length >= 4 &&
  (panel?.cards || []).filter((c) => /dark/.test(c)).length >= 4,
  "浅 " + (panel?.cards || []).filter((c) => /light/.test(c)).length +
  " / 深 " + (panel?.cards || []).filter((c) => /dark/.test(c)).length);
check("圆角 / 疏密 / 字体三行都在", (panel?.rows || 0) >= 3, (panel?.rows || 0) + " 行");
check("有「跟随系统」开关", !!panel?.hasFollow);
// #sidebar 是 overflow:hidden，面板必须没被裁掉
check("面板没被侧栏的 overflow:hidden 裁掉",
  !!panel && panel.outside.w > 200 && panel.outside.h > 200,
  panel ? Math.round(panel.outside.w) + "×" + Math.round(panel.outside.h) : "");

/* ── ② 预览卡必须用各自主题的真实变量渲染（不是一张静态图 / 不是同一个颜色） */
const previews = await evalJs(`(function(){
  return [...document.querySelectorAll('.appearance-pop .tp-card')].map((c) => {
    const cs = getComputedStyle(c);
    return { id: c.dataset.theme, bg: cs.backgroundColor, text: cs.color,
             card: cs.getPropertyValue('--surface').trim() };
  });
})()`);
const uniqBg = new Set((previews || []).map((p) => p.bg));
console.log("   预览卡底色:", (previews || []).map((p) => p.id + "=" + p.bg).slice(0, 4).join("  ") + " …");
check("每张预览卡渲染出各自的配色（颜色互不相同）", uniqBg.size >= 8, uniqBg.size + " 种底色");

/* ── ③ 挑一套配色：只有它变，其它三个维度不许跟着动 ── */
const pick = (id) => evalJs(`(function(){
  const c = document.querySelector('.appearance-pop .tp-card[data-theme="${id}"]');
  if (!c) return 'no-card';
  c.click(); return 'picked';})()`);
await pick("paper-light");
await sleep(400);
const afterTheme = await attrsOf();
check("点卡片即应用该配色", afterTheme.theme === "paper-light", afterTheme.theme);
check("配色真的换成了米黄纸感底", afterTheme.bg === "#f5efe1", afterTheme.bg);
check("换配色不改圆角", afterTheme.rXl === origin.rXl, origin.rXl + " → " + afterTheme.rXl);
check("换配色不改密度", afterTheme.density === origin.density, afterTheme.density);
check("换配色不改字体", afterTheme.font === origin.font, afterTheme.font);
check("换配色不改字号", afterTheme.bodySize === origin.bodySize, origin.bodySize + " → " + afterTheme.bodySize);

// 深色配色的 data-mode 要跟着变（画布靠它决定深浅）
const darkCard = (panel?.cards || []).find((c) => /dark/.test(c)) || "glass-dark";
await pick(darkCard);
await sleep(400);
const afterDark = await attrsOf();
check("切到深色配色时 data-mode 变 dark", afterDark.mode === "dark", afterDark.mode);
await pick("paper-light");
await sleep(300);
check("切回浅色配色时 data-mode 变 light", (await attrsOf()).mode === "light", "");

/* ── ④ 圆角 / 疏密 / 字体各自独立生效 ── */
await evalJs(`(function(){
  const rows=[...document.querySelectorAll('.appearance-pop .ap-row')];
  const b=[...rows[0].querySelectorAll('.ap-seg')].find(x=>/极简/.test(x.textContent)); b.click(); return 1;})()`);
await sleep(300);
const afterShape = await attrsOf();
check("圆角预设生效（data-shape=flat）", afterShape.shape === "flat", afterShape.shape);
check("圆角变量真的变小了", parseFloat(afterShape.rXl) < parseFloat(origin.rXl),
  origin.rXl + " → " + afterShape.rXl);
check("改圆角不动配色", afterShape.theme === "paper-light", afterShape.theme);

await evalJs(`(function(){
  const rows=[...document.querySelectorAll('.appearance-pop .ap-row')];
  const b=[...rows[1].querySelectorAll('.ap-seg')].find(x=>/紧凑/.test(x.textContent)); b.click(); return 1;})()`);
await sleep(300);
const afterDensity = await attrsOf();
check("疏密预设生效（data-density=compact）", afterDensity.density === "compact", afterDensity.density);
check("紧凑确实把字号压小了", parseFloat(afterDensity.bodySize) < parseFloat(origin.bodySize),
  origin.bodySize + " → " + afterDensity.bodySize);
check("改疏密不动圆角", afterDensity.shape === "flat", afterDensity.shape);

await evalJs(`(function(){
  const rows=[...document.querySelectorAll('.appearance-pop .ap-row')];
  const b=[...rows[2].querySelectorAll('.ap-seg')].find(x=>/等宽/.test(x.textContent)); b.click(); return 1;})()`);
await sleep(300);
const afterFont = await attrsOf();
check("字体预设生效（data-font=mono）", afterFont.font === "mono", afterFont.font);
check("界面字体真的换成了等宽", /cascadia|consolas/i.test(afterFont.fontUi), afterFont.fontUi);
check("改字体不动配色与圆角",
  afterFont.theme === "paper-light" && afterFont.shape === "flat", afterFont.theme + "/" + afterFont.shape);

/* ── ⑤ 跟随系统：勾上后配色应与系统深浅一致 ── */
await evalJs(`(function(){
  const cb=document.querySelector('.appearance-pop .ap-follow input');
  cb.checked = true; cb.dispatchEvent(new Event('change',{bubbles:true})); return 1;})()`);
await sleep(400);
const sysDark = await evalJs("window.matchMedia('(prefers-color-scheme: dark)').matches");
const followed = await attrsOf();
console.log("   系统深色 =", sysDark, "→ 跟随后的玩法:", followed.theme, "mode =", followed.mode);
check("勾选跟随系统后配色与系统深浅一致",
  followed.mode === (sysDark ? "dark" : "light"), followed.theme);
await evalJs(`(function(){
  const cb=document.querySelector('.appearance-pop .ap-follow input');
  cb.checked = false; cb.dispatchEvent(new Event('change',{bubbles:true})); return 1;})()`);
await sleep(300);

/* ── ⑥ 关面板的两种方式（不靠点遮罩误关） + 选择被记住 ── */
await evalJs("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))");
await sleep(250);
check("按 Esc 能关面板", (await evalJs("!!document.querySelector('.appearance-pop')")) === false);
await evalJs("document.body.click()");
await sleep(200);
check("面板关掉后配色保持不变（没有副作用）",
  (await evalJs("document.documentElement.dataset.theme")) === "paper-light");

await openPanel();
await sleep(250);
await evalJs(`(function(){
  const t=[...document.querySelectorAll('.topbar-title')][0];
  t.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true})); return 1;})()`);
await sleep(250);
check("点面板外面能关（不用遮罩）", (await evalJs("!!document.querySelector('.appearance-pop')")) === false);

const saved = await evalJs(`(function(){
  return { theme: localStorage.getItem('mf_theme'), shape: localStorage.getItem('mf_shape'),
           density: localStorage.getItem('mf_density'), font: localStorage.getItem('mf_font') };})()`);
check("选择写进了 localStorage", saved?.theme === "paper-light" && saved?.shape === "flat" &&
  saved?.density === "compact" && saved?.font === "mono", JSON.stringify(saved));

/* ── 收尾：还原成进入本套件之前的外观 ── */
await evalJs(`(function(){
  const el = document.documentElement;
  el.dataset.theme = ${JSON.stringify(origin.theme)};
  el.dataset.mode = ${JSON.stringify(origin.mode || "light")};
  el.dataset.shape = ${JSON.stringify(origin.shape)};
  el.dataset.density = ${JSON.stringify(origin.density)};
  el.dataset.font = ${JSON.stringify(origin.font)};
  try { localStorage.setItem('mf_theme', ${JSON.stringify(origin.theme)});
        localStorage.setItem('mf_shape', ${JSON.stringify(origin.shape)});
        localStorage.setItem('mf_density', ${JSON.stringify(origin.density)});
        localStorage.setItem('mf_font', ${JSON.stringify(origin.font)});
        localStorage.setItem('mf_theme_follow', '0'); } catch (e) {}
  // 让画布也按还原后的外观重绘（画布不听 CSS，只认这个广播）
  document.dispatchEvent(new CustomEvent('mf-appearance'));
  return 1;})()`);
await sleep(300);
const restored = await attrsOf();
check("收尾还原成功（后续套件不受影响）",
  restored.theme === origin.theme && restored.shape === origin.shape &&
  restored.density === origin.density && restored.font === origin.font,
  restored.theme + "/" + restored.shape + "/" + restored.density + "/" + restored.font);

check("全程没有 JS 异常", exceptions.length === 0, exceptions.slice(0, 2).join(" | "));

console.log(`\n═══ 外观选择器验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|cdp-appearance|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
