// 验证第4轮收尾：行号、悬停曲线追踪、滑块设置与动画
// 用法: node cdp-plot-final.mjs
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
const moveMouse = async (x, y) => {
  await send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
  await sleep(120);
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
  await sleep(2500);
}

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

/* ── ① 表达式行号（P0）── */
console.log("── 行号显示 ──");
await setExprs(["y=x^2", "y=2*x+1", "y=sin(x)"]);
const rowNos = await evalJs(`[...document.querySelectorAll('.row-no')].map(e=>e.textContent.trim())`);
console.log("   行号:", JSON.stringify(rowNos));
check("多行显示行号 1,2,3", JSON.stringify(rowNos) === JSON.stringify(["1", "2", "3"]), JSON.stringify(rowNos));

/* ── ② 悬停曲线追踪（P3 增强）── */
console.log("\n── 悬停曲线显示点坐标 ──");
// 先清到单条曲线，便于定位
await setExprs(["y=x^2", ""]);
await sleep(1500);
const rect = await evalJs("(function(){const r=document.querySelector('canvas').getBoundingClientRect();return {x:r.left,y:r.top,w:r.width,h:r.height};})()");
const rangeTxt = await evalJs("document.querySelector('.side-status')?.textContent||''");
const mr = rangeTxt.match(/范围\s*\[([-\d.]+),\s*([-\d.]+)\]\s*×\s*\[([-\d.]+),\s*([-\d.]+)\]/);
const vr = mr ? { x0: +mr[1], x1: +mr[2], y0: +mr[3], y1: +mr[4] } : null;
console.log("   画布:", JSON.stringify(rect), "| 视图:", JSON.stringify(vr));

// 悬停在 y=x^2 上 x=1 处（世界坐标 → 屏幕）
const toScreen = (wx, wy) => ({
  x: rect.x + ((wx - vr.x0) / (vr.x1 - vr.x0)) * rect.w,
  y: rect.y + ((vr.y1 - wy) / (vr.y1 - vr.y0)) * rect.h,
});
// 先移到空白处，再移到曲线上
await moveMouse(rect.x + 20, rect.y + 20);
await sleep(400);
const beforePx = await evalJs(`(function(){
  const cv=document.querySelector('canvas'); const d=cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;
  let n=0; for(let i=0;i<d.length;i+=4) if(d[i]<80&&d[i+1]<80&&d[i+2]<80) n++;
  return n;
})()`);
const sp = toScreen(1.0, 1.0);   // y = x^2 上的点 (1, 1)
await moveMouse(sp.x, sp.y);
await sleep(700);
const afterPx = await evalJs(`(function(){
  const cv=document.querySelector('canvas'); const d=cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;
  let n=0; for(let i=0;i<d.length;i+=4) if(d[i]<80&&d[i+1]<80&&d[i+2]<80) n++;
  return n;
})()`);
console.log("   悬停前深色像素:", beforePx, "→ 悬停曲线上:", afterPx);
check("悬停曲线上出现追踪标记（深色像素增加）", afterPx > beforePx, `${beforePx} → ${afterPx}`);

/* ── ③ 滑块设置：范围/步长（P1）── */
console.log("\n── 滑块设置（范围 / 步长）──");
await setExprs(["y=a*x^2"]);
await sleep(1500);
const hasSettingsBtn = await evalJs(`!!document.querySelector('.param-row .icon-btn[title="滑块设置"]')`);
check("滑块带设置按钮", hasSettingsBtn === true, String(hasSettingsBtn));
const opened = await evalJs(`(function(){
  const b = document.querySelector('.param-row .icon-btn[title="滑块设置"]');
  if (!b) return 'no-btn'; b.click(); return 'clicked';
})()`);
await sleep(500);
const settingsHtml = await evalJs(`(function(){
  const s = document.querySelector('.param-settings');
  return s ? s.querySelectorAll('input').length : 0;
})()`);
console.log("   点击:", opened, "| 设置项 input 数:", settingsHtml);
check("设置面板展开（3 个输入：最小/最大/步长）", settingsHtml === 3, String(settingsHtml));

// 改最大值为 5
const changed = await evalJs(`(function(){
  const inputs = [...document.querySelectorAll('.param-settings input')];
  if (inputs.length < 2) return 'no-input';
  const setter = { call: (el, v) => { if (el && el.tagName === 'MATH-FIELD') { el.value = v; } else { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); } } };
  setter.call(inputs[1], '5');
  inputs[1].dispatchEvent(new Event('change', { bubbles: true }));
  return 'ok';
})()`);
await sleep(800);
const sliderMax = await evalJs(`document.querySelector('.param-slider')?.getAttribute('max')`);
console.log("   修改最大值:", changed, "→ 滑块 max =", sliderMax);
check("滑块范围已更新为 5", String(sliderMax) === "5", String(sliderMax));

/* ── ④ 滑块动画播放（P1）── */
console.log("\n── 滑块动画播放 ──");
const v0 = await evalJs(`document.querySelector('.param-val')?.textContent`);
const played = await evalJs(`(function(){
  const b = document.querySelector('.param-row .icon-btn[title="播放动画"]');
  if (!b) return 'no-play-btn'; b.click(); return 'clicked';
})()`);
await sleep(1600);
const v1 = await evalJs(`document.querySelector('.param-val')?.textContent`);
const playingState = await evalJs(`!!document.querySelector('.param-row .icon-btn[title="暂停动画"]')`);
console.log("   点击:", played, "| 值:", v0, "→", v1, "| 播放中:", playingState);
check("播放按钮可点击", played === "clicked", played);
check("动画推进参数值", v0 !== v1, `${v0} → ${v1}`);
check("播放中显示暂停按钮", playingState === true, String(playingState));

// 暂停
await evalJs(`document.querySelector('.param-row .icon-btn[title="暂停动画"]')?.click()`);
await sleep(400);
const paused = await evalJs(`!!document.querySelector('.param-row .icon-btn[title="播放动画"]')`);
check("可暂停动画", paused === true, String(paused));

/* ── ⑤ 无 JS 错误 ── */
const errs = await evalJs("window.__plotErrors || null");
console.log("\n   绘制错误:", JSON.stringify(errs));
check("绘制步骤无异常", !errs || errs.length === 0, JSON.stringify(errs));

console.log(`\n═══ 收尾验证：${pass} 通过 / ${fail} 失败 ═══`);
console.log(`RESULT|plot-final|${pass}|${fail}`);
ws.close();
process.exit(fail === 0 ? 0 : 1);
