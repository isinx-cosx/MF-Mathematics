<script setup>
/**
 * PlotVectorView — 向量场
 * 输入 dx = P(x,y)、dy = Q(x,y) → 网格箭头（引擎双网格求值）
 * 控制：网格密度、箭头比例、归一化、按模长着色、参数滑块
 */
import { ref, computed, watch, onMounted } from "vue";
import VectorFieldCanvas from "../../components/plot/VectorFieldCanvas.vue";
import ParamSlider from "../../components/plot/ParamSlider.vue";
import { toEngineExpr, validate } from "../../lib/plot/plotMath.js";
import { linspace } from "../../lib/plot/sampling.js";
import { engineCall, isHosted } from "../../lib/bridge.js";
import { useRoute } from "vue-router";
import { exportCanvas } from "../../lib/plot/exportImage.js";

const hosted = isHosted();
const route = useRoute();
const canvasRef = ref(null);
const statusText = ref("就绪");

/** 导出当前画布为 PNG（2x、不透明底），结果写进状态栏 */
function exportImage() {
  const r = exportCanvas(canvasRef.value?.canvasEl?.(), { routePath: route.path, note: "向量场" });
  statusText.value = r.ok
    ? `已导出图片：${r.path}（${r.width}×${r.height}）`
    : (r.canceled ? "已取消导出" : `导出失败：${r.error}`);
}

/* ── 两个分量表达式 ── */
const dxInput = ref("-y");
const dyInput = ref("x");
const dxError = ref(null);
const dyError = ref(null);

/** 去掉 "dx=" / "P=" 之类前缀，取函数体 */
function bodyOf(text) {
  const t = String(text || "").trim();
  if (!t) return "";
  const m = t.match(/^[a-zA-Z_]\w*\s*=\s*(.+)$/);
  return toEngineExpr(m ? m[1] : t);
}
const dxBody = computed(() => bodyOf(dxInput.value));
const dyBody = computed(() => bodyOf(dyInput.value));

/* ── 参数（两个分量合并） ── */
const KNOWN = new Set(["pi", "e", "sin", "cos", "tan", "exp", "log", "sqrt", "abs", "sinh", "cosh", "tanh",
                       "asin", "acos", "atan", "floor", "ceil", "round", "sign", "pow", "cbrt", "log2", "log10"]);
const paramNames = computed(() => {
  const out = new Set();
  for (const body of [dxBody.value, dyBody.value]) {
    const re = /[a-zA-Z_][a-zA-Z0-9_]*/g;
    let m;
    while ((m = re.exec(body)) !== null) {
      const name = m[0];
      if (/^\s*\(/.test(body.slice(m.index + name.length))) continue;
      if (KNOWN.has(name) || name === "x" || name === "y") continue;
      out.add(name);
    }
  }
  return [...out].sort();
});

const params = ref({});
const paramConfig = ref({});
const DEFAULT_CFG = { min: -10, max: 10, step: 0.1 };
watch(paramNames, (names) => {
  const next = { ...params.value }, cfg = { ...paramConfig.value };
  let changed = false;
  for (const n of names) {
    if (!(n in next)) { next[n] = 1; changed = true; }
    if (!(n in cfg)) { cfg[n] = { ...DEFAULT_CFG }; changed = true; }
  }
  for (const k of Object.keys(next)) if (!names.includes(k)) { delete next[k]; changed = true; }
  for (const k of Object.keys(cfg)) if (!names.includes(k)) { delete cfg[k]; changed = true; }
  if (changed) { params.value = next; paramConfig.value = cfg; }
}, { immediate: true });

function updateParamConfig(name, c) {
  const min = Math.min(c.min, c.max - 1e-9);
  const max = Math.max(c.max, min + 1e-9);
  paramConfig.value = { ...paramConfig.value, [name]: { min, max, step: c.step } };
  const v = params.value[name];
  if (typeof v === "number") {
    const clamped = Math.min(Math.max(v, min), max);
    if (clamped !== v) params.value = { ...params.value, [name]: clamped };
  }
}

/* ── 视图与选项 ── */
const view = ref({ x0: -5, y0: -5, x1: 5, y1: 5 });
const density = ref(21);          // 每轴箭头数
// 原版 vector_field/workspace.py:185 的 quiver 用单位方向向量 (U/M, V/M) + 颜色编码模长，
// 即"等长箭头"是原版默认行为；此前默认 false（长度随模长伸缩）与原版不符。
const normalize = ref(true);
const colorByMagnitude = ref(true);
const showGrid = ref(true);
const arrowScale = ref(0);        // 0 = 自动

/* ── 采样（引擎双网格） ── */
const field = ref(null);
function sampleField() {
  if (!hosted) { statusText.value = "浏览器预览：无引擎桥"; return; }
  const v = view.value;
  const n = density.value;
  const xs = linspace(v.x0, v.x1, n);
  const ys = linspace(v.y0, v.y1, n);
  const need = n * n;
  const rdx = engineCall("expr_eval_grid", { expr: dxBody.value, xs, ys, vars: params.value });
  const rdy = engineCall("expr_eval_grid", { expr: dyBody.value, xs, ys, vars: params.value });
  if (rdx && !rdx.isError && rdy && !rdy.isError &&
      Array.isArray(rdx.value) && Array.isArray(rdy.value) &&
      rdx.value.length === need && rdy.value.length === need) {
    field.value = { xs, ys, dx: rdx.value, dy: rdy.value };
    let finite = 0;
    for (let i = 0; i < need; i++) {
      if (isFinite(rdx.value[i]) && isFinite(rdy.value[i])) finite++;
    }
    statusText.value = `引擎向量场 ${n}×${n} · 有效箭头 ${finite}`;
    dxError.value = null; dyError.value = null;
  } else {
    field.value = null;
    dxError.value = rdx && rdx.isError ? String(rdx.value).slice(0, 80) : null;
    dyError.value = rdy && rdy.isError ? String(rdy.value).slice(0, 80) : null;
    statusText.value = "求值失败";
  }
}

watch([dxBody, dyBody, params, density, () => [view.value.x0, view.value.x1, view.value.y0, view.value.y1]],
      () => sampleField(), { deep: true });

function validateInputs() {
  dxError.value = validate(dxInput.value);
  dyError.value = validate(dyInput.value);
}
watch([dxInput, dyInput], validateInputs);

/* 预设（便于快速体验常见场） */
const PRESETS = [
  { name: "旋转场", dx: "-y", dy: "x" },
  { name: "径向源", dx: "x", dy: "y" },
  { name: "鞍点", dx: "x", dy: "-y" },
  { name: "涡旋衰减", dx: "-y/(x^2+y^2+1)", dy: "x/(x^2+y^2+1)" },
  { name: "重力场", dx: "-x/(x^2+y^2)^1.5", dy: "-y/(x^2+y^2)^1.5" },
];
function applyPreset(p) {
  dxInput.value = p.dx;
  dyInput.value = p.dy;
}

function resetView() {
  view.value = { x0: -5, y0: -5, x1: 5, y1: 5 };
  sampleField();
}

onMounted(() => requestAnimationFrame(() => sampleField()));
</script>

<template>
  <div class="vf-layout">
    <aside class="vf-side">
      <div class="field">
        <label>dx / dt = P(x, y)</label>
        <input v-model="dxInput" class="input mono" spellcheck="false" placeholder="-y" />
        <div v-if="dxError" class="err">{{ dxError }}</div>
      </div>
      <div class="field">
        <label>dy / dt = Q(x, y)</label>
        <input v-model="dyInput" class="input mono" spellcheck="false" placeholder="x" />
        <div v-if="dyError" class="err">{{ dyError }}</div>
      </div>

      <div class="field">
        <label>快速预设</label>
        <div class="presets">
          <button v-for="p in PRESETS" :key="p.name" class="preset-btn" @click="applyPreset(p)">
            {{ p.name }}
          </button>
        </div>
      </div>

      <div class="field">
        <label>网格密度 {{ density }}×{{ density }}</label>
        <input v-model.number="density" class="slider" type="range" min="7" max="41" step="2" />
      </div>

      <div class="field">
        <label>箭头长度 {{ arrowScale === 0 ? "自动" : arrowScale.toFixed(1) + "×" }}</label>
        <input v-model.number="arrowScale" class="slider" type="range" min="0" max="1.5" step="0.1" />
      </div>

      <div class="field opts">
        <label class="chk"><input v-model="normalize" type="checkbox" /> 归一化（等长）</label>
        <label class="chk"><input v-model="colorByMagnitude" type="checkbox" /> 按模长着色</label>
        <label class="chk"><input v-model="showGrid" type="checkbox" /> 显示网格</label>
      </div>

      <div v-if="paramNames.length" class="slider-box">
        <div class="slider-title">参数</div>
        <ParamSlider
          v-for="n in paramNames"
          :key="n"
          :name="n"
          :value="params[n] ?? 1"
          :min="paramConfig[n]?.min ?? -10"
          :max="paramConfig[n]?.max ?? 10"
          :step="paramConfig[n]?.step ?? 0.1"
          @update:value="(val) => (params = { ...params, [n]: val })"
          @update:config="(c) => updateParamConfig(n, c)"
        />
      </div>

      <div class="status">{{ statusText }}</div>
    </aside>

    <div class="vf-main">
      <VectorFieldCanvas
        ref="canvasRef"
        v-model:view="view"
        :field="field"
        :normalize="normalize"
        :color-by-magnitude="colorByMagnitude"
        :show-grid="showGrid"
        :arrow-scale="arrowScale"
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
.vf-layout {
  display: grid;
  grid-template-columns: minmax(0, 300px) minmax(160px, 1fr);
  grid-template-rows: minmax(0, 1fr);
  height: 100%;
  min-height: 520px;
}
@media (max-width: 760px) {
  .vf-layout { grid-template-columns: minmax(0, 1fr); grid-template-rows: auto minmax(220px, 1fr); min-height: 320px; }
  .vf-side { max-height: 34vh; border-right: none; border-bottom: 1px solid var(--border); }
}
.vf-side {
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
.err { font-size: 11.5px; color: var(--danger); }
.presets { display: flex; flex-wrap: wrap; gap: 4px; }
.preset-btn {
  padding: 3px 8px; border: 1px solid var(--border); border-radius: 6px;
  background: var(--surface); color: var(--text-muted); font-size: 11.5px; cursor: pointer;
}
.preset-btn:hover { border-color: var(--accent); color: var(--accent); }
.slider-box { padding: 8px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); }
.slider-title { font-size: 11.5px; color: var(--text-subtle); margin-bottom: 4px; }
.status { margin-top: auto; font-size: 11.5px; color: var(--text-subtle); }
.vf-main { position: relative; min-width: 0; min-height: 0; }
.view-controls { position: absolute; top: 12px; right: 12px; }
.vc-btn {
  width: 32px; height: 32px; border: 1px solid var(--border); border-radius: 8px;
  background: var(--glass); backdrop-filter: blur(8px); color: var(--text);
  font-size: 15px; cursor: pointer;
}
.vc-btn:hover { background: var(--surface); border-color: var(--accent); color: var(--accent); }
</style>
