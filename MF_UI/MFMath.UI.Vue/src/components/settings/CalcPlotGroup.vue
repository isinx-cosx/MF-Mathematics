<script setup>
/**
 * 设置 · 计算与绘图分组
 *
 * 这两项都是 v1 设置里有的、v2.0 一直缺的（`settings_dialog.py` 的"数值精度"与"绘图默认值"）。
 * 交互原则（与外观组一致）：**改了就生效，没有保存按钮，也不弹任何窗口**——
 * 精度改了下次排版就是新位数；范围改了下次进绘图页就是这个视野。
 * 非法输入（比如最大值小于最小值）在**行内**说明并退回自动，不弹提示框。
 */
import { computed, ref, watch } from "vue";
import { usePrefs } from "../../lib/settings/prefs.js";
import { fmtNum } from "../../lib/engine/resultFormat.js";

const {
  prefs, state, error, setDecimals, setPlotRange, resetPrefs,
  MIN_DECIMALS, MAX_DECIMALS, DEFAULT_DECIMALS,
} = usePrefs();

/** 量程输入用字符串中转：用户清空输入框时不能立刻被 Number("")=0 顶掉 */
const xMin = ref(prefs.value.plotXMin ?? "");
const xMax = ref(prefs.value.plotXMax ?? "");
const yMin = ref(prefs.value.plotYMin ?? "");
const yMax = ref(prefs.value.plotYMax ?? "");
const applied = ref(state.value.text);

watch(() => prefs.value, (p) => {
  xMin.value = p.plotXMin ?? "";
  xMax.value = p.plotXMax ?? "";
  yMin.value = p.plotYMin ?? "";
  yMax.value = p.plotYMax ?? "";
}, { deep: true });

function onDecimals(e) {
  setDecimals(e.target.value);
}

/** 每次输入就应用（不弹窗、不打断输入）；状态文字行内更新 */
function onRange() {
  const st = setPlotRange({ xMin: xMin.value, xMax: xMax.value, yMin: yMin.value, yMax: yMax.value });
  applied.value = st.text;
}

function doReset() {
  resetPrefs();
  applied.value = state.value.text;
}

/** 精度示例：拿 1/3 与 √2 当场显示，用户不必去别处试 */
const samples = computed(() => [
  { label: "1 ÷ 3", text: fmtNum(1 / 3) },
  { label: "√2", text: fmtNum(Math.SQRT2) },
]);
</script>

<template>
  <section>
    <div class="s-row" data-setting="calc.precision">
      <div class="s-label">
        <label>数值精度</label>
        <p class="s-hint">
          结果里小数保留几位（0–{{ MAX_DECIMALS }}）。默认 {{ DEFAULT_DECIMALS }} 位，与旧版一致；
          <b>改了就生效</b>，整数与科学计数法不受影响
        </p>
      </div>
      <div class="s-ctl wrap">
        <input class="s-num" type="number" :min="MIN_DECIMALS" :max="MAX_DECIMALS" step="1"
               :value="prefs.decimals" @input="onDecimals" aria-label="小数位数">
        <span class="s-hint">位小数</span>
        <span class="s-hint mono">
          示例：1÷3 = {{ samples[0].text }} ；√2 = {{ samples[1].text }}
        </span>
      </div>
    </div>

    <div class="s-row" data-setting="calc.plotRange">
      <div class="s-label">
        <label>绘图默认范围</label>
        <p class="s-hint">
          打开 2D 绘图页时的初始视野。四项都填才生效；留空 = 按画布宽高比自动（旧版行为）
        </p>
      </div>
      <div class="s-ctl wrap">
        <span class="s-hint">x</span>
        <input class="s-num" type="number" step="any" v-model="xMin" @input="onRange" aria-label="x 最小值">
        <span class="s-hint">~</span>
        <input class="s-num" type="number" step="any" v-model="xMax" @input="onRange" aria-label="x 最大值">
        <span class="s-hint" style="margin-left:8px">y</span>
        <input class="s-num" type="number" step="any" v-model="yMin" @input="onRange" aria-label="y 最小值">
        <span class="s-hint">~</span>
        <input class="s-num" type="number" step="any" v-model="yMax" @input="onRange" aria-label="y 最大值">
        <button class="s-btn" @click="doReset">恢复默认</button>
      </div>
    </div>

    <p class="s-hint" style="margin:2px 0 0">
      当前：{{ applied }}<template v-if="state.mode === 'invalid' || state.mode === 'partial'">
      </template> · 说明：范围只影响**新打开**的绘图页，已经拖动过的视野不会被改写
    </p>
    <p v-if="error" class="s-warn">{{ error }}</p>
  </section>
</template>

<style scoped>
.s-num {
  width: 84px; font: inherit; font-size: 12px; padding: 4px 7px;
  border: 1px solid var(--border, #d7dce5); border-radius: 6px;
  background: var(--surface, #fff); color: var(--text, #1f2937);
}
.s-num:focus { outline: none; border-color: var(--accent, #3b82f6); }
.s-ctl.wrap { flex-wrap: wrap; align-items: center; gap: 6px; }
</style>
