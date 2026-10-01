<script setup>
/**
 * Plot3DView — 3D 曲面（对齐 Desmos 3D 交互）
 * 左：表达式 z = f(x, y) + 参数滑块 + 渲染选项
 * 右：曲面画布（拖拽旋转 / 滚轮缩放 / 重置视角）
 * 计算：网格值由 C++ 引擎 expr_eval_grid 求值（支持参数代入）
 */
import { ref, computed, watch, onMounted } from "vue";
import SurfaceCanvas from "../../components/plot/SurfaceCanvas.vue";
import ParamSlider from "../../components/plot/ParamSlider.vue";
import { parseExpr, validate, toEngineExpr } from "../../lib/plot/plotMath.js";
import { linspace } from "../../lib/plot/sampling.js";
import { engineCall, isHosted } from "../../lib/bridge.js";

const hosted = isHosted();
const canvasRef = ref(null);
const statusText = ref("就绪");

/* ── 表达式与参数 ── */
const exprInput = ref("sin(x)*cos(y)");
const exprError = ref(null);
const params = ref({});
const paramConfig = ref({});
const DEFAULT_CFG = { min: -10, max: 10, step: 0.1 };

/** 提取 z = f(x,y) 的函数体：
 *  支持 "z=..." / "f(x,y)=..." / 直接写表达式（隐含 z = ...） */
const surfaceBody = computed(() => {
  const t = exprInput.value.trim();
  if (!t) return "";
  let body = t;
  const m = t.match(/^[a-zA-Z_]\w*(\([^)]*\))?\s*=\s*(.+)$/);
  if (m) {
    const lhs = t.slice(0, t.indexOf("=")).trim();
    if (/^z$/i.test(lhs) || /^\w+\(/.test(lhs)) body = m[2];
    else return "";   // 非 z=f(x,y) 形式
  }
  return toEngineExpr(body);
});

/** 自由参数（除 x、y 外的标识符） */
const paramNames = computed(() => {
  const body = surfaceBody.value;
  if (!body) return [];
  const KNOWN = new Set(["pi", "e", "sin", "cos", "tan", "exp", "log", "sqrt", "abs", "sinh", "cosh", "tanh",
                         "asin", "acos", "atan", "floor", "ceil", "round", "sign", "pow", "cbrt", "log2", "log10"]);
  const out = new Set();
  const re = /[a-zA-Z_][a-zA-Z0-9_]*/g;
  let m;
  while ((m = re.exec(body)) !== null) {
    const name = m[0];
    const after = body.slice(m.index + name.length);
    if (/^\s*\(/.test(after)) continue;     // 函数调用
    if (KNOWN.has(name)) continue;
    if (name === "x" || name === "y") continue;
    out.add(name);
  }
  return [...out].sort();
});

watch(paramNames, (names) => {
  const next = { ...params.value };
  const cfg = { ...paramConfig.value };
  let changed = false;
  for (const n of names) {
    if (!(n in next)) { next[n] = 1; changed = true; }
    if (!(n in cfg)) { cfg[n] = { ...DEFAULT_CFG }; changed = true; }
  }
  for (const k of Object.keys(next)) if (!names.includes(k)) { delete next[k]; changed = true; }
  for (const k of Object.keys(cfg)) if (!names.includes(k)) { delete cfg[k]; changed = true; }
  if (changed) { params.value = next; paramConfig.value = cfg; }
}, { immediate: true });

function updateParamConfig(name, conf) {
  const min = Math.min(conf.min, conf.max - 1e-9);
  const max = Math.max(conf.max, min + 1e-9);
  paramConfig.value = { ...paramConfig.value, [name]: { min, max, step: conf.step } };
  const v = params.value[name];
  if (typeof v === "number") {
    const clamped = Math.min(Math.max(v, min), max);
    if (clamped !== v) params.value = { ...params.value, [name]: clamped };
  }
}

/* ── 视角与渲染选项 ── */
// pitch 就是仰角：默认取原版 view_init(elev=25) 的 25°=0.4363 rad（此前是 0.6 rad≈34.4°）。
// yaw 是绕 z 的方位角，Vue 的旋转方向与 matplotlib 的 azim 定义不同，未强行对齐。
const view = ref({ yaw: -0.6, pitch: 0.4363, zoom: 1 });
const showSurface = ref(true);
const showWireframe = ref(false);
const gridN = ref(48);          // 网格密度（每轴）
const domain = ref(5);          // x,y ∈ [-domain, domain]

/* ── 网格采样（引擎） ── */
const grid = ref(null);
function sampleSurface() {
  const body = surfaceBody.value;
  if (!body) { grid.value = null; statusText.value = "请输入 z = f(x, y)"; return; }
  if (!hosted) { statusText.value = "浏览器预览：无引擎桥，曲面不绘制"; return; }
  const n = gridN.value;
  const xs = linspace(-domain.value, domain.value, n);
  const ys = linspace(-domain.value, domain.value, n);
  const r = engineCall("expr_eval_grid", { expr: body, xs, ys, vars: params.value });
  if (r && !r.isError && Array.isArray(r.value) && r.value.length === n * n) {
    grid.value = { xs, ys, values: r.value };
    let finite = 0;
    for (const v of r.value) if (typeof v === "number" && isFinite(v)) finite++;
    statusText.value = `引擎网格 ${n}×${n} = ${finite} 个有效值`;
    exprError.value = null;
  } else {
    grid.value = null;
    exprError.value = r && r.isError ? String(r.value).slice(0, 90) : "网格求值失败";
    statusText.value = "求值失败";
  }
}

watch([surfaceBody, params, gridN, domain], () => { sampleSurface(); }, { deep: true });

function validateInput() {
  exprError.value = validate(exprInput.value);
}
watch(exprInput, validateInput);

function resetView() {
  canvasRef.value?.resetView();
}

onMounted(() => {
  requestAnimationFrame(() => sampleSurface());
});
</script>

<template>
  <div class="plot3d-layout">
    <aside class="plot3d-side">
      <div class="field">
        <label>曲面表达式</label>
        <input
          v-model="exprInput"
          class="input mono"
          spellcheck="false"
          placeholder="z = sin(x)*cos(y)"
        />
        <div v-if="exprError" class="err">{{ exprError }}</div>
      </div>

      <div class="field">
        <label>定义域 x,y ∈ [-{{ domain }}, {{ domain }}]</label>
        <input v-model.number="domain" class="slider" type="range" min="1" max="20" step="0.5" />
      </div>

      <div class="field">
        <label>网格密度 {{ gridN }}×{{ gridN }}</label>
        <input v-model.number="gridN" class="slider" type="range" min="16" max="96" step="4" />
      </div>

      <div class="field opts">
        <label class="chk"><input v-model="showSurface" type="checkbox" /> 曲面填充</label>
        <label class="chk"><input v-model="showWireframe" type="checkbox" /> 线框叠加</label>
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

    <div class="plot3d-main">
      <SurfaceCanvas
        ref="canvasRef"
        v-model:view="view"
        :grid="grid"
        :show-surface="showSurface"
        :show-wireframe="showWireframe"
      />
      <div class="view-controls">
        <button class="vc-btn" title="重置视角" @click="resetView">⟲</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.plot3d-layout { display: grid; grid-template-columns: 300px 1fr; height: 100%; min-height: 520px; }
.plot3d-side {
  display: flex; flex-direction: column; gap: 12px;
  padding: 12px; border-right: 1px solid var(--border);
  background: var(--surface-alt); overflow-y: auto;
}
.field { display: flex; flex-direction: column; gap: 5px; }
.field > label { font-size: 11.5px; color: var(--text-muted); }
.slider { width: 100%; accent-color: var(--accent); }
.opts { flex-direction: row; gap: 14px; }
.chk { display: flex; align-items: center; gap: 5px; font-size: 12px; color: var(--text); }
.err { font-size: 11.5px; color: var(--danger); }
.slider-box {
  padding: 8px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface);
}
.slider-title { font-size: 11.5px; color: var(--text-subtle); margin-bottom: 4px; }
.status { margin-top: auto; font-size: 11.5px; color: var(--text-subtle); }
.plot3d-main { position: relative; min-width: 0; }
.view-controls { position: absolute; top: 12px; right: 12px; display: flex; flex-direction: column; gap: 4px; }
.vc-btn {
  width: 32px; height: 32px; border: 1px solid var(--border); border-radius: 8px;
  background: var(--glass); backdrop-filter: blur(8px); color: var(--text);
  font-size: 15px; cursor: pointer;
}
.vc-btn:hover { background: var(--surface); border-color: var(--accent); color: var(--accent); }
</style>
