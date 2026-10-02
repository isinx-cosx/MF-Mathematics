<!--
  PlotComplexView.vue — 复平面绘图（复变函数可视化）

  【这是一次重做】上一版把"复变函数可视化"做成了"多项式求根标点"（解方程 → 在复平面
  画根、单位圆、共轭点），与原版（MF_UI/plot/complex/workspace.py）完全不是一个功能。
  本版按原版对齐：输入 f(z)，五种绘制模式。

  与原版逐条对应（原版 → 本版）：
    相位图        H=(arg+π)/2π, S=1, V=clip(mag/max, 0.3, 1)          → 同
    3D 模长曲面   mag 按 99 分位截断, viridis, elev=30 azim=-60        → 同（2D 画布等距投影）
    向量场式      采样间隔 nx//40, U=mag·cos(arg), V=mag·sin(arg),
                  按 arg 上 hsv 配色, alpha=.8, 等比例坐标轴            → 同
    HSV 域着色    V=log1p(mag)/log1p(max)                              → 同
    共形映射网格  21 条水平 + 21 条垂直网格线各 400 点，映射到 w 平面，
                  水平线蓝、垂直线红，等比例坐标轴                     → 同
    范围/分辨率   默认 x,y ∈ [-5,5]、分辨率 200（可调 50~1000）        → 同
    自然输入      e^z、sinz、|z| 等                                    → 同（交给引擎的归一化）

  与原版的两点**有意不同**（都是架构决定的，不是偷工）：
    ① 计算全在 C++ 引擎里（complex_grid），JS 只上色/画图。
       原版用 sympy/numpy/mpmath 现算，新架构必须走引擎——这也是本项目的一贯约束。
    ② 原版用 QMessageBox 模态弹窗警告"范围过大/分辨率过高"；这里改成面板内联提示，
       因为模态弹窗会打断输入，而且拖滑块时反复弹窗很烦。
-->
<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from "vue";
import { engineCall, isHosted, plotMode, onAppearanceChange } from "../../lib/bridge.js";
import { gridFor } from "../../lib/plot/colors.js";
import { useRoute } from "vue-router";
import { exportCanvas } from "../../lib/plot/exportImage.js";

const hosted = isHosted();
const route = useRoute();
const canvas = ref(null);
const theme = ref(plotMode());
const statusText = ref("等待输入函数");

/** 导出当前复平面图为 PNG（2x、不透明底）；结果写进面板里的状态行 */
function exportImage() {
  const r = exportCanvas(canvas.value, { routePath: route.path, note: "复平面" });
  statusText.value = r.ok
    ? `已导出图片：${r.path}（${r.width}×${r.height}）`
    : (r.canceled ? "已取消导出" : `导出失败：${r.error}`);
}

/* ── 参数（默认值与原版一致）── */
const funcExpr = ref("");
const mode = ref(0);
const xMin = ref(-5), xMax = ref(5), yMin = ref(-5), yMax = ref(5);
const resolution = ref(200);
const busy = ref(false);

const MODES = [
  { id: 0, name: "相位图", hint: "辐角上色（色相=辐角，明度=模长）" },
  { id: 1, name: "3D 模长曲面", hint: "z 平面上的 |f(z)| 曲面" },
  { id: 2, name: "向量场式", hint: "每点的 f(z) 当成一个箭头" },
  { id: 3, name: "HSV 域着色", hint: "辐角=色相，模长取对数当明度" },
  { id: 4, name: "共形映射网格", hint: "z 平面网格在 w=f(z) 下怎么变形" },
];

/** 原版会弹窗提醒的阈值，这里做内联提示 */
const rangeWarn = computed(() => Math.max(xMax.value - xMin.value, yMax.value - yMin.value) > 100);
const resWarn = computed(() => resolution.value > 600);
const gridPoints = computed(() => resolution.value * resolution.value);

const hasResult = ref(false);
/* 数据缓存：模式切换时不重新问引擎（同一份网格数据，五种画法都用它） */
let grid = null;        // { re, im, nx, ny, ... }
let confLines = null;   // 共形映射用：{ h: {...}, v: {...} }

const themeVars = () => {
  const cs = getComputedStyle(document.documentElement);
  const v = (n) => cs.getPropertyValue(n).trim();
  return {
    bg: v("--plot-bg") || v("--surface-alt"),
    text: v("--text"),
    muted: v("--text-muted"),
    subtle: v("--text-subtle"),
    border: v("--border"),
    accent: v("--accent"),
  };
};

/* ── 与原版同一套着色公式 ─────────────────────────────────────────────── */
/** hsv → rgb，h,s,v ∈ [0,1] */
function hsv2rgb(h, s, v) {
  h = ((h % 1) + 1) % 1;
  const i = Math.floor(h * 6);
  const f = h * 6 - i;
  const p = v * (1 - s), q = v * (1 - f * s), t = v * (1 - (1 - f) * s);
  let r, g, b;
  switch (i % 6) {
    case 0: r = v; g = t; b = p; break;
    case 1: r = q; g = v; b = p; break;
    case 2: r = p; g = v; b = t; break;
    case 3: r = p; g = q; b = v; break;
    case 4: r = t; g = p; b = v; break;
    default: r = v; g = p; b = q; break;
  }
  return [r * 255, g * 255, b * 255];
}
/** viridis 近似（原版 3D 曲面用的 cmap）。取 9 个锚点线性插值。 */
const VIRIDIS = [
  [68, 1, 84], [72, 40, 120], [62, 74, 137], [49, 104, 142], [38, 130, 142],
  [31, 158, 137], [53, 183, 121], [109, 205, 89], [180, 222, 44], [253, 231, 37],
];
function viridis(t) {
  t = Math.max(0, Math.min(1, t));
  const x = t * (VIRIDIS.length - 1);
  const i = Math.floor(x), f = x - i;
  const a = VIRIDIS[i], b = VIRIDIS[Math.min(i + 1, VIRIDIS.length - 1)];
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
}

/** 把 nx×ny 的网格按逐点着色画成底图（等价于原版 imshow(origin="lower")） */
function paintGrid(ctx, g, colorAt, W, H, box) {
  const img = ctx.createImageData(g.nx, g.ny);
  const d = img.data;
  for (let j = 0; j < g.ny; ++j) {
    // origin="lower"：网格第 0 行在下方，而 canvas 第 0 行在上方 → 行序翻转
    const src = (g.ny - 1 - j) * g.nx;
    for (let i = 0; i < g.nx; ++i) {
      const k = src + i;
      const rgb = colorAt(k);
      const o = (j * g.nx + i) * 4;
      d[o] = rgb[0]; d[o + 1] = rgb[1]; d[o + 2] = rgb[2]; d[o + 3] = 255;
    }
  }
  // 用离屏 canvas 放大到目标区域：保持 imshow 的"最近邻、块状"观感
  const off = document.createElement("canvas");
  off.width = g.nx; off.height = g.ny;
  off.getContext("2d").putImageData(img, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(off, box.x, box.y, box.w, box.h);
  ctx.imageSmoothingEnabled = true;
}

/* ── 取数：全部来自引擎 ─────────────────────────────────────────────── */
async function fetchGrid() {
  const n = Math.max(2, Math.min(1000, Math.round(resolution.value)));
  const r = engineCall("complex_grid", {
    expr: funcExpr.value,
    x0: xMin.value, x1: xMax.value, y0: yMin.value, y1: yMax.value,
    nx: n, ny: n,
  });
  if (!r) { throw new Error("桥不可用"); }
  if (r.isError) { throw new Error(String(r.value)); }
  const v = r.value || {};
  if (v.unsupported) {
    // 引擎明确说了哪个函数算不了 → 直接把它抛给用户，别画一张空白图让人猜
    throw new Error(String(v.unsupported));
  }
  return {
    re: v.re, im: v.im, nx: v.nx, ny: v.ny,
    maxMag: v.maxMag || 0, nan: v.nan || 0, ok: v.ok || 0,
  };
}

/** 共形映射：水平线（ny=21 行，每行 nx=400 点）与垂直线（nx=21 列，每列 ny=400 点） */
async function fetchConformalGrids() {
  const N = 400, L = 21;
  const mk = (nx, ny) => {
    const r = engineCall("complex_grid", {
      expr: funcExpr.value, x0: xMin.value, x1: xMax.value, y0: yMin.value, y1: yMax.value, nx, ny,
    });
    if (!r || r.isError) throw new Error(r ? String(r.value) : "桥不可用");
    const v = r.value || {};
    if (v.unsupported) throw new Error(String(v.unsupported));
    return { re: v.re, im: v.im, nx: v.nx, ny: v.ny };
  };
  confLines = { h: mk(N, L), v: mk(L, N) };
}

/* ── 绘制 ────────────────────────────────────────────────────────────── */
let raf = 0;
function scheduleDraw() { cancelAnimationFrame(raf); raf = requestAnimationFrame(draw); }

function draw() {
  const el = canvas.value;
  if (!el) return;
  const W = el.clientWidth, H = el.clientHeight;
  if (W <= 0 || H <= 0) return;
  const dpr = window.devicePixelRatio || 1;
  if (el.width !== Math.round(W * dpr) || el.height !== Math.round(H * dpr)) {
    el.width = Math.round(W * dpr); el.height = Math.round(H * dpr);
  }
  const ctx = el.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const C = themeVars();
  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, W, H);

  if (!grid) {
    ctx.fillStyle = C.subtle;
    ctx.font = "13px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("等待输入函数", W / 2, H / 2);
    return;
  }

  const pad = { l: 46, r: 14, t: 14, b: 30 };
  const box = { x: pad.l, y: pad.t, w: Math.max(10, W - pad.l - pad.r), h: Math.max(10, H - pad.t - pad.b) };
  const g = grid;

  if (mode.value === 1) { draw3D(ctx, g, box, C); drawAxes(ctx, box, C, { x: "Re(z)", y: "Im(z)" }); return; }
  if (mode.value === 4) { drawConformal(ctx, box, C); return; }

  // mag / arg 每点算一次
  const n = g.nx * g.ny;
  const mag = new Float64Array(n), arg = new Float64Array(n);
  for (let k = 0; k < n; ++k) {
    const re = g.re[k], im = g.im[k];
    if (re === null || im === null) { mag[k] = NaN; arg[k] = NaN; continue; }
    mag[k] = Math.hypot(re, im);
    arg[k] = Math.atan2(im, re);
  }
  const maxMag = g.maxMag > 0 ? g.maxMag : 1;

  if (mode.value === 0 || mode.value === 3) {
    // 相位图：V = clip(mag/max, 0.3, 1)
    // HSV 域着色：V = log1p(mag)/log1p(max)（原版两者的区别就在这一行）
    const logMax = Math.log1p(maxMag);
    paintGrid(ctx, g, (k) => {
      if (Number.isNaN(mag[k])) return [C.bg === "#ffffff" ? 255 : 24, C.bg === "#ffffff" ? 255 : 24, C.bg === "#ffffff" ? 255 : 24];
      const Hh = (arg[k] + Math.PI) / (2 * Math.PI);
      let V;
      if (mode.value === 0) V = Math.max(0.3, Math.min(1, mag[k] / (maxMag + 1e-10)));
      else V = Math.max(0, Math.min(1, Math.log1p(mag[k]) / (logMax + 1e-9)));
      return hsv2rgb(Hh, 1, V);
    }, W, H, box);
    drawAxes(ctx, box, C, { x: "Re(z)", y: "Im(z)" });
    return;
  }

  // 向量场式：采样间隔 nx//40（原版同）
  ctx.save();
  ctx.beginPath(); ctx.rect(box.x, box.y, box.w, box.h); ctx.clip();
  const skip = Math.max(1, Math.floor(g.nx / 40));
  const sx = (i) => box.x + (i / Math.max(1, g.nx - 1)) * box.w;
  const sy = (j) => box.y + box.h - (j / Math.max(1, g.ny - 1)) * box.h;   // y 向上
  // 箭头长度按最大模长归一，避免整屏糊成一片
  const scale = maxMag > 0 ? 1 / maxMag : 1;
  ctx.globalAlpha = 0.8;                       // 原版 alpha=0.8
  for (let j = 0; j < g.ny; j += skip) {
    for (let i = 0; i < g.nx; i += skip) {
      const k = j * g.nx + i;
      if (Number.isNaN(mag[k])) continue;
      const u = mag[k] * Math.cos(arg[k]) * scale;
      const v = mag[k] * Math.sin(arg[k]) * scale;
      const len = Math.hypot(u, v);
      if (len < 1e-6) continue;
      const x = sx(i), y = sy(j);
      const ex = x + u * box.w * 0.42, ey = y - v * box.h * 0.42;
      const rgb = hsv2rgb((arg[k] + Math.PI) / (2 * Math.PI), 1, 0.95);
      ctx.strokeStyle = `rgb(${rgb[0] | 0},${rgb[1] | 0},${rgb[2] | 0})`;
      ctx.fillStyle = ctx.strokeStyle;
      ctx.lineWidth = 1.1;
      ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(ex, ey); ctx.stroke();
      const a = Math.atan2(ey - y, ex - x);
      const hl = 5;
      ctx.beginPath();
      ctx.moveTo(ex, ey);
      ctx.lineTo(ex - hl * Math.cos(a - 0.4), ey - hl * Math.sin(a - 0.4));
      ctx.lineTo(ex - hl * Math.cos(a + 0.4), ey - hl * Math.sin(a + 0.4));
      ctx.closePath(); ctx.fill();
    }
  }
  ctx.globalAlpha = 1;
  ctx.restore();
  // 原版向量场是等比例坐标轴（aspect equal）
  drawAxes(ctx, box, C, { x: "Re(z)", y: "Im(z)" }, true);
}

/** 3D 模长曲面：等距投影 + 画家算法（不需要引入 3D 库） */
function draw3D(ctx, g, box, C) {
  const n = g.nx * g.ny;
  const mag = new Float64Array(n);
  let maxMag = 0;
  for (let k = 0; k < n; ++k) {
    const re = g.re[k], im = g.im[k];
    const m = (re === null || im === null) ? NaN : Math.hypot(re, im);
    mag[k] = m;
    if (Number.isFinite(m) && m > maxMag) maxMag = m;
  }
  // 原版：mag 按 99 分位截断（否则靠近极点的尖峰把整个曲面压平）
  const sorted = Array.from(mag).filter(Number.isFinite).sort((a, b) => a - b);
  const p99 = sorted.length ? sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.99))] : 1;
  const zTop = Math.max(p99, 1e-9);

  const elev = 30 * Math.PI / 180, azim = -60 * Math.PI / 180;
  const cx = box.x + box.w / 2, cy = box.y + box.h / 2;
  const span = Math.min(box.w, box.h) * 0.42;
  const proj = (px, py, pz) => {
    // px,py ∈ [-1,1]（z 平面坐标归一化），pz ∈ [0,1]（模长）
    const ca = Math.cos(azim), sa = Math.sin(azim);
    const X = px * ca - py * sa;
    const Y = px * sa + py * ca;
    const ce = Math.cos(elev), se = Math.sin(elev);
    return [cx + X * span, cy - (Y * span * se - pz * span * 0.7 * ce)];
  };
  const step = Math.max(1, Math.floor(g.nx / 160));   // 600×600 时别画 36 万个四边形
  const quads = [];
  for (let j = 0; j + step < g.ny; j += step) {
    for (let i = 0; i + step < g.nx; i += step) {
      const p = [
        [i, j], [i + step, j], [i + step, j + step], [i, j + step],
      ].map(([ii, jj]) => {
        const k = jj * g.nx + ii;
        const px = (ii / (g.nx - 1)) * 2 - 1;
        const py = (jj / (g.ny - 1)) * 2 - 1;
        const m = Number.isFinite(mag[k]) ? Math.min(mag[k], zTop) : 0;
        return { xyz: proj(px, py, m / zTop), m };
      });
      const depth = (p[0].xyz[1] + p[2].xyz[1]) / 2;   // 画家算法：先远后近
      quads.push({ p, depth, avg: (p[0].m + p[1].m + p[2].m + p[3].m) / 4 });
    }
  }
  quads.sort((a, b) => a.depth - b.depth);
  ctx.save();
  ctx.beginPath(); ctx.rect(box.x, box.y, box.w, box.h); ctx.clip();   // 曲面不出画布
  for (const q of quads) {
    const rgb = viridis(q.avg / zTop);
    ctx.fillStyle = `rgba(${rgb[0] | 0},${rgb[1] | 0},${rgb[2] | 0},0.9)`;   // 原版 alpha=0.9
    ctx.beginPath();
    ctx.moveTo(q.p[0].xyz[0], q.p[0].xyz[1]);
    for (let t = 1; t < 4; ++t) ctx.lineTo(q.p[t].xyz[0], q.p[t].xyz[1]);
    ctx.closePath();
    ctx.fill();
  }
  ctx.restore();
  ctx.fillStyle = C.muted;
  ctx.font = "11px system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText("|f(z)| 曲面（按 99 分位截断，越高越亮）", box.x + 4, box.y + 12);
}

/** 共形映射：z 平面网格 → w 平面 */
function drawConformal(ctx, box, C) {
  const lines = confLines;
  if (!lines) return;
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  const scan = (G) => {
    for (let k = 0; k < G.re.length; ++k) {
      const re = G.re[k], im = G.im[k];
      if (re === null || im === null) continue;
      if (re < x0) x0 = re; if (re > x1) x1 = re;
      if (im < y0) y0 = im; if (im > y1) y1 = im;
    }
  };
  scan(lines.h); scan(lines.v);
  if (!Number.isFinite(x0) || x1 <= x0) { x0 = -1; x1 = 1; }
  if (!Number.isFinite(y0) || y1 <= y0) { y0 = -1; y1 = 1; }
  const sx = (v) => box.x + ((v - x0) / (x1 - x0)) * box.w;
  const sy = (v) => box.y + box.h - ((v - y0) / (y1 - y0)) * box.h;

  ctx.save();
  ctx.beginPath(); ctx.rect(box.x, box.y, box.w, box.h); ctx.clip();
  ctx.lineWidth = 0.9;
  // 水平线（y=const）：蓝；原版 #3b82f6 / alpha .4
  ctx.strokeStyle = "rgba(59,130,246,0.55)";
  for (let j = 0; j < lines.h.ny; ++j) {
    ctx.beginPath();
    let started = false;
    for (let i = 0; i < lines.h.nx; ++i) {
      const k = j * lines.h.nx + i;
      const re = lines.h.re[k], im = lines.h.im[k];
      if (re === null || im === null) { started = false; continue; }
      const X = sx(re), Y = sy(im);
      if (!started) { ctx.moveTo(X, Y); started = true; } else ctx.lineTo(X, Y);
    }
    ctx.stroke();
  }
  // 垂直线（x=const）：红；原版 #ef4444
  ctx.strokeStyle = "rgba(239,68,68,0.55)";
  for (let i = 0; i < lines.v.nx; ++i) {
    ctx.beginPath();
    let started = false;
    for (let j = 0; j < lines.v.ny; ++j) {
      const k = j * lines.v.nx + i;
      const re = lines.v.re[k], im = lines.v.im[k];
      if (re === null || im === null) { started = false; continue; }
      const X = sx(re), Y = sy(im);
      if (!started) { ctx.moveTo(X, Y); started = true; } else ctx.lineTo(X, Y);
    }
    ctx.stroke();
  }
  ctx.restore();
  drawAxes(ctx, box, C, { x: "Re(w)", y: "Im(w)" }, true);
  ctx.fillStyle = C.muted;
  ctx.font = "11px system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(`w = ${funcExpr.value}`, box.x + 4, box.y + 12);
}

/** 坐标轴与刻度（等比例的视图按数据范围标，否则按 z 平面范围） */
function drawAxes(ctx, box, C, labels, equalAspect = false) {
  const g = grid;
  const x0 = equalAspect && confLines ? null : xMin.value;
  ctx.strokeStyle = C.border;
  ctx.fillStyle = C.muted;
  ctx.font = "11px system-ui, sans-serif";
  ctx.lineWidth = 1;
  const ticks = 8;
  for (let t = 0; t <= ticks; ++t) {
    const fx = box.x + (t / ticks) * box.w;
    const fy = box.y + (t / ticks) * box.h;
    ctx.beginPath(); ctx.moveTo(fx, box.y); ctx.lineTo(fx, box.y + box.h);
    ctx.globalAlpha = 0.16; ctx.stroke(); ctx.globalAlpha = 1;
    ctx.beginPath(); ctx.moveTo(box.x, fy); ctx.lineTo(box.x + box.w, fy);
    ctx.globalAlpha = 0.16; ctx.stroke(); ctx.globalAlpha = 1;
  }
  ctx.strokeStyle = C.border;
  ctx.strokeRect(box.x, box.y, box.w, box.h);
  ctx.textAlign = "center";
  if (x0 !== null && g) {
    for (let t = 0; t <= 4; ++t) {
      const v = xMin.value + ((xMax.value - xMin.value) * t) / 4;
      ctx.fillText(v.toFixed(2), box.x + (t / 4) * box.w, box.y + box.h + 14);
    }
    ctx.textAlign = "right";
    for (let t = 0; t <= 4; ++t) {
      const v = yMin.value + ((yMax.value - yMin.value) * t) / 4;
      ctx.fillText(v.toFixed(2), box.x - 6, box.y + box.h - (t / 4) * box.h + 4);
    }
  }
  ctx.textAlign = "right";
  ctx.fillStyle = C.subtle;
  ctx.font = "11px system-ui, sans-serif";
  ctx.fillText(labels.x, box.x + box.w, box.y + box.h + 14);
  ctx.textAlign = "left";
  ctx.fillText(labels.y, box.x, box.y - 3);
}

/* ── 动作 ────────────────────────────────────────────────────────────── */
/** 这组参数对应的数据指纹：表达式/范围/分辨率没变就复用已取回的网格，不重复过桥 */
const dataKey = () =>
  `${funcExpr.value}|${xMin.value}|${xMax.value}|${yMin.value}|${yMax.value}|${resolution.value}`;
let gridKey = "";

async function apply() {
  const raw = funcExpr.value.trim();
  if (!raw) { grid = null; confLines = null; gridKey = ""; hasResult.value = false; statusText.value = "就绪"; scheduleDraw(); return; }
  if (!hosted) { statusText.value = "浏览器预览：无引擎桥，无法计算"; return; }
  const key = dataKey();
  const reuse = grid && gridKey === key;
  busy.value = true;
  statusText.value = "计算中…";
  await nextTick();
  const t0 = performance.now();
  try {
    // 五模式共用同一块网格；共形映射另外取两组线数据（它的坐标在 w 平面，网格数据用不上）
    if (!reuse) {
      grid = await fetchGrid();
      confLines = null;
      gridKey = key;
    }
    if (mode.value === 4 && !confLines) await fetchConformalGrids();
    hasResult.value = true;
    const ms = Math.round(performance.now() - t0);
    // 复用缓存时耗时会很小——如实写出来，别让人以为"切模式也要重算一遍"
    statusText.value = `已绘制：${raw} ｜ ${MODES[mode.value].name} ｜ ${grid.nx}×${grid.ny}，${ms} ms${reuse ? "（复用已算好的网格）" : ""}`;
    scheduleDraw();
  } catch (e) {
    grid = null; confLines = null; gridKey = "";
    hasResult.value = false;
    statusText.value = String(e?.message || e);
    scheduleDraw();
  } finally {
    busy.value = false;
  }
}

/**
 * 切模式：**始终**走 apply()。
 * 之前只在"共形映射"时才 apply，导致切到其它模式后状态栏还写着上一个模式名——
 * 而画面其实已经换了（测试就是靠像素差异发现"画对了但状态没更新"的）。
 * apply() 内部按 dataKey 复用网格，所以这里不会重复问引擎。
 */
function setMode(id) {
  const changed = mode.value !== id;
  mode.value = id;
  if (changed && hasResult.value) apply();
  else scheduleDraw();
}

onMounted(() => {
  scheduleDraw();
  const off = onAppearanceChange(() => { theme.value = plotMode(); scheduleDraw(); });
  onBeforeUnmount(() => off());
  const ro = window.ResizeObserver ? new ResizeObserver(scheduleDraw) : null;
  if (ro && canvas.value) ro.observe(canvas.value);
  onBeforeUnmount(() => ro?.disconnect());
});
watch([xMin, xMax, yMin, yMax, resolution], () => { if (hasResult.value) scheduleDraw(); });
</script>

<template>
  <div class="view-body">
    <div class="plot-layout">
      <aside class="plot-side">
        <div class="ws-title">复数模式</div>
        <div class="ws-desc">复变函数可视化 · 计算由 C++ 引擎完成</div>

        <label class="lbl">f(z) =</label>
        <input v-model="funcExpr" class="input mono" placeholder="e^z、sin(z)、zeta(z)、gamma(z)、erf(z)…"
               @keydown.enter="apply()" />
        <button class="btn btn-primary" :disabled="busy || !hosted" @click="apply()">
          {{ busy ? "计算中…" : "应用" }}
        </button>

        <div class="sep"></div>

        <label class="lbl">绘制模式</label>
        <button v-for="m in MODES" :key="m.id" class="btn mode-btn" :class="{ on: mode === m.id }"
                :title="m.hint" @click="setMode(m.id)">{{ m.name }}</button>

        <div class="sep"></div>

        <label class="lbl">绘图范围</label>
        <div class="row"><span class="tag">x:</span>
          <input v-model.number="xMin" type="number" step="0.5" class="input num" />
          <span class="tag">~</span>
          <input v-model.number="xMax" type="number" step="0.5" class="input num" /></div>
        <div class="row"><span class="tag">y:</span>
          <input v-model.number="yMin" type="number" step="0.5" class="input num" />
          <span class="tag">~</span>
          <input v-model.number="yMax" type="number" step="0.5" class="input num" /></div>

        <div class="row"><span class="tag">分辨率:</span>
          <input v-model.number="resolution" type="number" min="50" max="1000" step="10" class="input num" />
          <span class="tag">{{ gridPoints.toLocaleString() }} 点</span></div>

        <p v-if="rangeWarn" class="warn">范围跨度超过 100，点数多时会明显变慢。</p>
        <p v-if="resWarn" class="warn">分辨率超过 600，计算可能需要十几秒。</p>

        <button class="btn" :disabled="busy || !hosted" @click="apply()">重绘</button>
        <button class="btn" :disabled="busy" title="把当前复平面图导出成 PNG（2 倍像素）" @click="exportImage">导出图片</button>
        <p class="status">{{ statusText }}</p>
      </aside>

      <div class="plot-main">
        <canvas ref="canvas" class="complex-canvas"></canvas>
      </div>
    </div>
  </div>
</template>

<style scoped>
.plot-layout { display: flex; gap: 14px; align-items: stretch; height: 100%; }
.plot-side { width: 260px; flex-shrink: 0; display: flex; flex-direction: column; gap: 6px; }
.plot-main { flex: 1; min-width: 0; display: flex; }
.complex-canvas {
  flex: 1; min-height: 420px; display: block;
  background: var(--surface-alt);
  border: 1px solid var(--border); border-radius: var(--r-md);
}
.lbl { font-size: 12.5px; color: var(--text-muted); margin-top: 4px; }
.sep { height: 1px; background: var(--border); margin: 8px 0; }
.row { display: flex; align-items: center; gap: 5px; }
.tag { font-size: 11.5px; color: var(--text-subtle); white-space: nowrap; }
.num { width: 66px; height: 28px; padding: 0 6px; }
.mode-btn { text-align: left; height: 30px; }
.mode-btn.on { background: var(--accent-soft); color: var(--accent); border-color: var(--accent); font-weight: 700; }
.warn { font-size: 11.5px; color: var(--danger); background: var(--danger-soft); border-radius: var(--r-sm); padding: 5px 7px; }
.status { font-size: 11.5px; color: var(--text-subtle); margin-top: 6px; line-height: 1.5; word-break: break-all; }
</style>
