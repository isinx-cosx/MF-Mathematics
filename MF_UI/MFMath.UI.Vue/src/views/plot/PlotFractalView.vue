<script setup>
/**
 * PlotFractalView — Mandelbrot 分形
 *  · 迭代计数由 C++ 引擎 mandelbrot 计算（复平面窗口 + 分辨率 + 最大迭代）
 *  · 拖拽平移、滚轮缩放（以光标所在复数为不动点）
 *  · 多种配色方案；显示当前窗口与缩放倍数
 */
import { ref, computed, watch, onMounted, onBeforeUnmount } from "vue";
import { engineCall, isHosted } from "../../lib/bridge.js";
import { useRoute } from "vue-router";
import { exportCanvas } from "../../lib/plot/exportImage.js";

const hosted = isHosted();
const route = useRoute();
const canvas = ref(null);
let ctx = null;
let cssW = 0, cssH = 0, raf = 0;
let drag = null;

/** 复平面窗口。原版 plot/fractal/workspace.py:137-138 默认 x∈[-2,2]、y∈[-1.5,1.5]，
 *  且 origin="lower" 约定 y 向上（ymin 在屏幕下方）。 */
const DEFAULT_VIEW = { xmin: -2.0, xmax: 2.0, ymin: -1.5, ymax: 1.5 };
const view = ref({ ...DEFAULT_VIEW });
/** 原版默认迭代 256（下拉 [64,128,256,512,1024] 的第 3 项，workspace.py:135,173） */
const maxIter = ref(256);
const scheme = ref("classic");
const smooth = ref(true);
const statusText = ref("就绪");
const lastMs = ref(0);

/** 导出当前分形图为 PNG（2x、不透明底）；结果写进状态行 */
function exportImage() {
  const r = exportCanvas(canvas.value, { routePath: route.path, note: "分形" });
  statusText.value = r.ok
    ? `已导出图片：${r.path}（${r.width}×${r.height}）`
    : (r.canceled ? "已取消导出" : `导出失败：${r.error}`);
}
/** 渲染分辨率上限（保证交互流畅；越大越清晰） */
const maxSide = ref(560);

const SCHEMES = {
  classic: [
    [0, [0, 7, 100]],
    [0.16, [32, 107, 203]],
    [0.42, [237, 255, 255]],
    [0.6425, [255, 170, 0]],
    [0.8575, [0, 2, 0]],
    [1.0, [0, 7, 100]],
  ],
  sunset: [
    [0, [10, 10, 40]],
    [0.3, [120, 20, 90]],
    [0.6, [240, 120, 40]],
    [0.85, [255, 220, 120]],
    [1.0, [10, 10, 40]],
  ],
  mono: [
    [0, [0, 0, 0]],
    [1.0, [255, 255, 255]],
  ],
  ocean: [
    [0, [2, 20, 60]],
    [0.35, [20, 120, 180]],
    [0.7, [120, 220, 220]],
    [1.0, [2, 20, 60]],
  ],
};

function schemeColor(t) {
  const stops = SCHEMES[scheme.value] || SCHEMES.classic;
  const x = Math.max(0, Math.min(1, t));
  for (let i = 0; i + 1 < stops.length; i++) {
    const [t0, c0] = stops[i], [t1, c1] = stops[i + 1];
    if (x >= t0 && x <= t1) {
      const k = t1 === t0 ? 0 : (x - t0) / (t1 - t0);
      return [
        Math.round(c0[0] + (c1[0] - c0[0]) * k),
        Math.round(c0[1] + (c1[1] - c0[1]) * k),
        Math.round(c0[2] + (c1[2] - c0[2]) * k),
      ];
    }
  }
  return stops[stops.length - 1][1];
}

function scheduleDraw() {
  if (raf) return;
  raf = requestAnimationFrame(() => { raf = 0; render(); });
}

function resize() {
  const el = canvas.value;
  if (!el) return;
  cssW = el.clientWidth; cssH = el.clientHeight;
  if (cssW <= 0 || cssH <= 0) return;
  const dpr = window.devicePixelRatio || 1;
  el.width = Math.round(cssW * dpr);
  el.height = Math.round(cssH * dpr);
  scheduleDraw();
}

/** 引擎计算 + 图像渲染 */
function render() {
  if (!ctx) return;
  if (cssW <= 0) { const el = canvas.value; cssW = el?.clientWidth || 0; cssH = el?.clientHeight || 0; }
  if (cssW <= 0 || cssH <= 0) return;
  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  if (!hosted) {
    ctx.fillStyle = "#0a0f1c";
    ctx.fillRect(0, 0, cssW, cssH);
    ctx.fillStyle = "#94a3b8";
    ctx.font = "13px -apple-system, Segoe UI, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("浏览器预览：无引擎桥，分形不渲染", cssW / 2, cssH / 2);
    statusText.value = "浏览器预览：无引擎桥";
    return;
  }

  // 采样分辨率（保持宽高比，限制最长边）
  const scale = Math.min(1, maxSide.value / Math.max(cssW, cssH));
  const w = Math.max(32, Math.round(cssW * scale));
  const h = Math.max(32, Math.round(cssH * scale));
  const v = view.value;

  const t0 = performance.now();
  const r = engineCall("mandelbrot", {
    xmin: v.xmin, xmax: v.xmax, ymin: v.ymin, ymax: v.ymax,
    width: w, height: h, max_iter: maxIter.value,
  });
  const dt = performance.now() - t0;
  lastMs.value = dt;

  if (!r || r.isError || !Array.isArray(r.value) || r.value.length !== w * h) {
    ctx.fillStyle = "#0a0f1c";
    ctx.fillRect(0, 0, cssW, cssH);
    ctx.fillStyle = "#f87171";
    ctx.font = "13px -apple-system, Segoe UI, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("引擎分形计算失败", cssW / 2, cssH / 2);
    statusText.value = r && r.isError ? String(r.value).slice(0, 80) : "分形计算失败";
    return;
  }

  // 生成图像（引擎返回行主序：第 0 行对应 ymin）
  const off = document.createElement("canvas");
  off.width = w; off.height = h;
  const octx = off.getContext("2d");
  const img = octx.createImageData(w, h);
  const data = img.data;
  const iters = r.value;
  const mi = maxIter.value;
  for (let i = 0; i < w * h; i++) {
    // 引擎行主序：第 0 行 = ymin（数学下方，见 MF_Mathematics/fractal_api.cpp:30-31）。
    // canvas 第 0 行在屏幕顶部，所以必须按 (h-1-row) 取行，才能让 y 轴朝上——
    // 原版 workspace.py:242 用 imshow(..., origin="lower")，是同一个约定。
    // 之前直接取 iters[i]，图像被上下镜像，与滚轮/拖拽的 y 约定相反。
    const row = (i / w) | 0, col = i % w;
    const it = iters[(h - 1 - row) * w + col];
    const idx = i * 4;
    if (it >= mi) {
      data[idx] = 12; data[idx + 1] = 12; data[idx + 2] = 20; data[idx + 3] = 255;
    } else if (smooth.value) {
      // 平滑着色：用迭代数做连续映射，减少色带
      const t = Math.pow(it / mi, 0.45);
      const [cr, cg, cb] = schemeColor(t);
      data[idx] = cr; data[idx + 1] = cg; data[idx + 2] = cb; data[idx + 3] = 255;
    } else {
      const [cr, cg, cb] = schemeColor(it / mi);
      data[idx] = cr; data[idx + 1] = cg; data[idx + 2] = cb; data[idx + 3] = 255;
    }
  }
  octx.putImageData(img, 0, 0);
  // 图像已在上面按 (h-1-row) 翻转成"y 向上"（与原版 origin="lower" 一致）
  ctx.drawImage(off, 0, 0, w, h, 0, 0, cssW, cssH);

  // 信息叠加
  ctx.fillStyle = "rgba(0,0,0,.45)";
  ctx.fillRect(0, 0, cssW, 22);
  ctx.fillStyle = "#e2e8f0";
  ctx.font = "11.5px -apple-system, Segoe UI, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  const zoom = (DEFAULT_VIEW.xmax - DEFAULT_VIEW.xmin) / Math.max(1e-12, v.xmax - v.xmin);
  ctx.fillText(
    `中心 ${((v.xmin + v.xmax) / 2).toFixed(6)} ${((v.ymin + v.ymax) / 2) >= 0 ? "+" : "-"} ${Math.abs((v.ymin + v.ymax) / 2).toFixed(6)}i` +
    ` · 缩放 ${zoom.toFixed(1)}× · 迭代 ${mi} · ${w}×${h} · ${dt.toFixed(0)}ms`,
    8, 11
  );
  statusText.value = `引擎 mandelbrot ${w}×${h} · ${dt.toFixed(0)} ms`;
}

/* ── 交互：拖拽平移 + 点击缩放（对齐原版 workspace.py:256-286）──
 *
 * 原版的三种鼠标操作：
 *   · 左键单击：w = 跨度/3，新窗口 = (点击点 ∓ w) → 新跨度 = 2/3 旧跨度 = **放大 1.5×**，
 *     点击处成为新中心（workspace.py:266-270）。原版注释写"左键缩放"，倍率就是 1.5×。
 *   · 右键单击：w = 跨度×0.5，新窗口 = (点击点 ∓ w) → 新跨度 = 2w = **原跨度**，
 *     即"把窗口重定中心到点击处、不改变缩放"（workspace.py:271-275）。原版那行注释写的
 *     是"右键缩小"，但按代码算并没有缩放 —— 这里按代码的实际行为对齐，不按注释。
 *   · 双击：重置视图（workspace.py:259-265）。
 * 拖拽平移是 Vue 额外加的（原版状态栏宣称支持，但没实现），保留，且只在"真的移动过"时平移，
 * 不动才算单击缩放。
 */
function fractionAt(e) {
  const rect = canvas.value.getBoundingClientRect();
  return [(e.clientX - rect.left) / Math.max(cssW, 1), (e.clientY - rect.top) / Math.max(cssH, 1)];
}
/** 屏幕比例 → 复坐标（屏幕上方 = ymax，与原版的 origin="lower" 一致） */
function complexAt(fx, fy) {
  const v = view.value;
  return [v.xmin + fx * (v.xmax - v.xmin), v.ymax - fy * (v.ymax - v.ymin)];
}
/** 以 (cx, cy) 为中心、跨度乘以 factor */
function setViewAround(cx, cy, factor) {
  const v = view.value;
  const hw = (v.xmax - v.xmin) * factor / 2;
  const hh = (v.ymax - v.ymin) * factor / 2;
  view.value = { xmin: cx - hw, xmax: cx + hw, ymin: cy - hh, ymax: cy + hh };
  scheduleDraw();
}

function onMouseDown(e) {
  const [fx, fy] = fractionAt(e);
  if (e.button === 2) {
    // 原版 workspace.py:271-275：右键把窗口中心挪到点击处，跨度不变
    const [cx, cy] = complexAt(fx, fy);
    setViewAround(cx, cy, 1);
    return;
  }
  if (e.button !== 0) return;
  drag = { x: e.clientX, y: e.clientY, v: { ...view.value }, fx, fy, moved: false };
  canvas.value.style.cursor = "grabbing";
}
function onMouseMove(e) {
  if (!drag) return;
  if (Math.abs(e.clientX - drag.x) > 2 || Math.abs(e.clientY - drag.y) > 2) drag.moved = true;
  const dx = (e.clientX - drag.x) / Math.max(cssW, 1) * (drag.v.xmax - drag.v.xmin);
  const dy = (e.clientY - drag.y) / Math.max(cssH, 1) * (drag.v.ymax - drag.v.ymin);
  view.value = {
    xmin: drag.v.xmin - dx, xmax: drag.v.xmax - dx,
    ymin: drag.v.ymin + dy, ymax: drag.v.ymax + dy,   // 屏幕向下 → 复平面 y 增大
  };
  scheduleDraw();
}
function onMouseUp() {
  const d = drag;
  drag = null;
  if (canvas.value) canvas.value.style.cursor = "grab";
  if (d && !d.moved) {
    // 单击（没拖动过）→ 原版左键行为：以点击处为中心放大 1.5×
    const [cx, cy] = complexAt(d.fx, d.fy);
    setViewAround(cx, cy, 2 / 3);
  }
}

/** 滚轮缩放：以光标处的复数为不动点 */
function onWheel(e) {
  e.preventDefault();
  const rect = canvas.value.getBoundingClientRect();
  const fx = (e.clientX - rect.left) / Math.max(cssW, 1);
  const fy = (e.clientY - rect.top) / Math.max(cssH, 1);
  const v = view.value;
  const cx = v.xmin + fx * (v.xmax - v.xmin);
  const cy = v.ymax - fy * (v.ymax - v.ymin);   // 屏幕 y 向下 → 复平面 y 减小
  const factor = e.deltaY < 0 ? 0.55 : 1.8;
  let nw = (v.xmax - v.xmin) * factor;
  let nh = (v.ymax - v.ymin) * factor;
  nw = Math.max(1e-13, Math.min(8, nw));
  nh = Math.max(1e-13, Math.min(8, nh));
  view.value = {
    xmin: cx - fx * nw, xmax: cx + (1 - fx) * nw,
    ymin: cy - (1 - fy) * nh, ymax: cy + fy * nh,
  };
  scheduleDraw();
}

function resetView() {
  view.value = { ...DEFAULT_VIEW };
  scheduleDraw();
}

/** 缩放到已知的兴趣区域 */
const REGIONS = [
  { name: "全景", v: { ...DEFAULT_VIEW } },
  { name: "海马谷", v: { xmin: -0.8, xmax: -0.72, ymin: 0.06, ymax: 0.12 } },
  { name: "象谷", v: { xmin: -0.76, xmax: -0.74, ymin: 0.1, ymax: 0.115 } },
  { name: "螺旋", v: { xmin: -1.79, xmax: -1.77, ymin: 0.0, ymax: 0.015 } },
  { name: "迷你集", v: { xmin: -1.768, xmax: -1.766, ymin: 0.0015, ymax: 0.0035 } },
];
function gotoRegion(r) {
  view.value = { ...r.v };
  scheduleDraw();
}

let ro = null;
onMounted(() => {
  ctx = canvas.value.getContext("2d");
  canvas.value.style.cursor = "grab";
  resize();
  if (window.ResizeObserver) { ro = new ResizeObserver(resize); ro.observe(canvas.value); }
});
onBeforeUnmount(() => { if (ro) ro.disconnect(); cancelAnimationFrame(raf); });

watch([maxIter, scheme, smooth, maxSide], scheduleDraw);
watch(() => [view.value.xmin, view.value.xmax, view.value.ymin, view.value.ymax], scheduleDraw);
</script>

<template>
  <div class="frac-layout">
    <aside class="frac-side">
      <div class="field">
        <label>最大迭代次数 {{ maxIter }}</label>
        <!-- 原版迭代档位 [64,128,256,512,1024]（workspace.py:172）；这里保留连续滑块，
             但上限对齐到原版最大值 1024，默认 256 与原版一致 -->
        <input v-model.number="maxIter" class="slider" type="range" min="30" max="1024" step="10" />
      </div>
      <div class="field">
        <label>渲染分辨率 {{ maxSide }} px（越长越慢）</label>
        <input v-model.number="maxSide" class="slider" type="range" min="240" max="1200" step="40" />
      </div>
      <div class="field">
        <label>配色方案</label>
        <select v-model="scheme" class="select">
          <option value="classic">经典（蓝白橙）</option>
          <option value="sunset">日落</option>
          <option value="ocean">海洋</option>
          <option value="mono">黑白</option>
        </select>
      </div>
      <div class="field opts">
        <label class="chk"><input v-model="smooth" type="checkbox" /> 平滑着色</label>
      </div>

      <div class="field">
        <label>兴趣区域</label>
        <div class="regions">
          <button v-for="r in REGIONS" :key="r.name" class="region-btn" @click="gotoRegion(r)">{{ r.name }}</button>
        </div>
      </div>

      <div class="field hints">
        <div>左键单击：以点击处为中心放大 1.5×</div>
        <div>右键单击：把窗口中心挪到点击处（不改变缩放）</div>
        <div>拖拽：平移复平面　双击 / ⟲：重置视图</div>
        <div>滚轮：以光标处为中心缩放</div>
        <div>提示：迭代次数越高，边界细节越丰富</div>
      </div>

      <div class="status">{{ statusText }}</div>
    </aside>

    <div class="frac-main">
      <canvas
        ref="canvas"
        class="frac-canvas"
        @mousedown="onMouseDown"
        @mousemove="onMouseMove"
        @mouseup="onMouseUp"
        @mouseleave="onMouseUp"
        @dblclick="resetView"
        @contextmenu.prevent
        @wheel="onWheel"
      />
      <div class="view-controls">
        <button class="vc-btn" title="重置视图" @click="resetView">⟲</button>
        <button class="vc-btn" title="导出图片（PNG，2 倍像素）" @click="exportImage">⤓</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 两列都必须能压缩、行高必须受容器约束（与 PlotView.vue 同款问题）：
 * 写死 `300px 1fr` 时窗口一窄画布列就被算成 0px，整幅图"消失"。 */
.frac-layout {
  display: grid;
  grid-template-columns: minmax(0, 300px) minmax(160px, 1fr);
  grid-template-rows: minmax(0, 1fr);
  height: 100%;
  min-height: 520px;
}
@media (max-width: 760px) {
  .frac-layout { grid-template-columns: minmax(0, 1fr); grid-template-rows: auto minmax(220px, 1fr); min-height: 320px; }
  .frac-side { max-height: 34vh; border-right: none; border-bottom: 1px solid var(--border); }
}
.frac-side {
  display: flex; flex-direction: column; gap: 12px;
  padding: 12px; border-right: 1px solid var(--border);
  background: var(--surface-alt); overflow-y: auto;
  min-width: 0; min-height: 0;
}
.field { display: flex; flex-direction: column; gap: 5px; }
.field > label { font-size: 11.5px; color: var(--text-muted); }
.slider { width: 100%; accent-color: var(--accent); }
.opts { gap: 6px; }
.chk { display: flex; align-items: center; gap: 5px; font-size: 12px; color: var(--text); }
.regions { display: flex; flex-wrap: wrap; gap: 4px; }
.region-btn {
  padding: 3px 8px; border: 1px solid var(--border); border-radius: 6px;
  background: var(--surface); color: var(--text-muted); font-size: 11.5px; cursor: pointer;
}
.region-btn:hover { border-color: var(--accent); color: var(--accent); }
.hints { font-size: 11.5px; color: var(--text-subtle); gap: 3px; }
.status { margin-top: auto; font-size: 11.5px; color: var(--text-subtle); }
.frac-main { position: relative; min-width: 0; min-height: 0; }
.frac-canvas { display: block; width: 100%; height: 100%; touch-action: none; }
.view-controls { position: absolute; top: 32px; right: 12px; }
.vc-btn {
  width: 32px; height: 32px; border: 1px solid var(--border); border-radius: 8px;
  background: var(--glass); backdrop-filter: blur(8px); color: var(--text);
  font-size: 15px; cursor: pointer;
}
.vc-btn:hover { background: var(--surface); border-color: var(--accent); color: var(--accent); }
</style>
