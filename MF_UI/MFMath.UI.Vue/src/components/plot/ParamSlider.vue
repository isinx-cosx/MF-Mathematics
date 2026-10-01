<script setup>
/**
 * ParamSlider — 参数滑块（对齐 Desmos）
 *  · 表达式含自由参数（如 y=a*x+b 的 a、b）时自动出现
 *  · 拖动实时重绘；数值框可精确输入
 *  · 齿轮展开设置：最小/最大值、步长（Desmos 的滑块设置）
 *  · 播放按钮：自动往返动画（Desmos 的滑块动画）
 */
import { computed, ref, onBeforeUnmount } from "vue";

const props = defineProps({
  name: { type: String, required: true },
  value: { type: Number, required: true },
  min: { type: Number, default: -10 },
  max: { type: Number, default: 10 },
  step: { type: Number, default: 0.1 },
});
const emit = defineEmits(["update:value", "update:config"]);

const editing = ref(false);
const draft = ref("");
const showSettings = ref(false);
const playing = ref(false);
/** 动画速度（每秒变化量，按范围自适应） */
const SPEEDS = [0.25, 0.5, 1];
const speedIdx = ref(1);

let rafId = 0;
let lastTs = 0;
let dir = 1;

const display = computed(() => {
  const v = props.value;
  if (!isFinite(v)) return "—";
  const a = Math.abs(v);
  if (a !== 0 && (a < 1e-4 || a >= 1e5)) return v.toExponential(2);
  return String(Math.round(v * 1e6) / 1e6);
});

const sliderValue = computed(() => Math.min(Math.max(props.value, props.min), props.max));

function onSlide(e) {
  emit("update:value", Number(e.target.value));
}

function startEdit() {
  draft.value = display.value;
  editing.value = true;
}

function commit() {
  const v = Number(draft.value);
  if (isFinite(v)) emit("update:value", v);
  editing.value = false;
}

/** 设置项：写入 config（父组件据此更新 min/max/step） */
function setConfig(patch) {
  emit("update:config", { min: props.min, max: props.max, step: props.step, ...patch });
}

/** 播放/暂停自动动画：值在 [min,max] 间往返 */
function togglePlay() {
  if (playing.value) { stopAnim(); return; }
  playing.value = true;
  lastTs = 0;
  const span = Math.max(1e-9, props.max - props.min);
  const perSecond = span * SPEEDS[speedIdx.value] * 0.35;   // 每秒走过的区间比例
  const tick = (ts) => {
    if (!playing.value) return;
    if (!lastTs) lastTs = ts;
    const dt = Math.min(0.1, (ts - lastTs) / 1000);
    lastTs = ts;
    let v = props.value + dir * perSecond * dt;
    if (v > props.max) { v = props.max; dir = -1; }
    if (v < props.min) { v = props.min; dir = 1; }
    emit("update:value", v);
    rafId = requestAnimationFrame(tick);
  };
  rafId = requestAnimationFrame(tick);
}

function stopAnim() {
  playing.value = false;
  if (rafId) cancelAnimationFrame(rafId);
  rafId = 0;
}

function cycleSpeed() {
  speedIdx.value = (speedIdx.value + 1) % SPEEDS.length;
}

onBeforeUnmount(stopAnim);
</script>

<template>
  <div class="param-block" data-tour="plot_workspace.sliders">
    <div class="param-row">
      <span class="param-name">{{ name }}</span>
      <input
        class="param-slider"
        type="range"
        :min="min"
        :max="max"
        :step="step"
        :value="sliderValue"
        @input="onSlide"
      />
      <input
        v-if="editing"
        class="param-val-input"
        :value="draft"
        @input="draft = $event.target.value"
        @blur="commit"
        @keydown.enter="commit"
        @keydown.esc="editing = false"
        autofocus
      />
      <button v-else class="param-val" @click="startEdit">{{ display }}</button>
      <button class="icon-btn" :title="playing ? '暂停动画' : '播放动画'" @click="togglePlay">
        {{ playing ? "❚❚" : "▶" }}
      </button>
      <button class="icon-btn" title="滑块设置" @click="showSettings = !showSettings">⚙</button>
    </div>

    <!-- 滑块设置（对齐 Desmos：最小值 / 最大值 / 步长 / 动画速度）-->
    <div v-if="showSettings" class="param-settings">
      <label>最小 <input class="set-input" type="number" :value="min" @change="setConfig({ min: Number($event.target.value) })" /></label>
      <label>最大 <input class="set-input" type="number" :value="max" @change="setConfig({ max: Number($event.target.value) })" /></label>
      <label>步长 <input class="set-input" type="number" :value="step" min="0" @change="setConfig({ step: Math.abs(Number($event.target.value)) || 0.1 })" /></label>
      <label class="speed-row">
        速度
        <button class="speed-btn" @click="cycleSpeed">{{ SPEEDS[speedIdx] }}×</button>
      </label>
    </div>
  </div>
</template>

<style scoped>
.param-block { display: flex; flex-direction: column; }
.param-row {
  display: grid;
  grid-template-columns: 18px 1fr 58px 22px 22px;
  align-items: center;
  gap: 5px;
  padding: 3px 6px;
}
.param-name {
  font-family: 'Cambria Math', Georgia, serif;
  font-style: italic;
  font-size: 15px;
  color: var(--text);
}
.param-slider { width: 100%; accent-color: var(--accent); cursor: pointer; }
.param-val {
  height: 24px; padding: 0 6px; text-align: center;
  border: 1px solid var(--border); border-radius: 6px;
  background: var(--surface); color: var(--text);
  font-family: 'Cascadia Code', Consolas, monospace; font-size: 12px;
  cursor: text;
}
.param-val:hover { border-color: var(--accent); }
.param-val-input {
  height: 24px; width: 58px; padding: 0 6px;
  border: 1px solid var(--accent); border-radius: 6px;
  background: var(--surface); color: var(--text);
  font-family: 'Cascadia Code', Consolas, monospace; font-size: 12px;
  outline: none;
}
.icon-btn {
  width: 22px; height: 22px; padding: 0;
  border: 1px solid var(--border); border-radius: 5px;
  background: var(--surface); color: var(--text-muted);
  font-size: 9px; cursor: pointer; line-height: 1;
}
.icon-btn:hover { color: var(--accent); border-color: var(--accent); }

.param-settings {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 4px 8px;
  padding: 6px 8px 8px;
  margin: 0 6px 4px;
  border-radius: 8px;
  background: var(--surface-alt);
  font-size: 11.5px;
  color: var(--text-muted);
}
.param-settings label { display: flex; align-items: center; justify-content: space-between; gap: 4px; }
.set-input {
  width: 62px; height: 22px; padding: 0 5px;
  border: 1px solid var(--border); border-radius: 5px;
  background: var(--surface); color: var(--text);
  font-family: 'Cascadia Code', Consolas, monospace; font-size: 11.5px;
  outline: none;
}
.set-input:focus { border-color: var(--accent); }
.speed-row { justify-content: space-between; }
.speed-btn {
  height: 22px; padding: 0 8px;
  border: 1px solid var(--border); border-radius: 5px;
  background: var(--surface); color: var(--text);
  font-size: 11.5px; cursor: pointer;
}
.speed-btn:hover { border-color: var(--accent); color: var(--accent); }
</style>
