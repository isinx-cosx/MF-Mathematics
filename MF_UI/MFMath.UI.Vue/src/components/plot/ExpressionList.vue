<script setup>
/**
 * ExpressionList — Desmos 式表达式列表
 * 每行：[显示切换] [颜色圆点(点击改色)] [表达式输入] [删除]
 * 行为对齐 Desmos：
 *   · Enter 新建下一行；空行按 Backspace 删除
 *   · 点击行 → 高亮对应曲线
 *   · 解析失败 → 行内红点 + 提示文字
 *
 * 输入框是 MathLive 的 <math-field>：**数学直接排版在框内**（输入 \frac 当场变分数），
 * 而不是"文本框 + 下方预览"。另配符号面板插入 √ π 等难输字符。
 */
import { ref, nextTick, watch } from "vue";
import { ALL_COLORS } from "../../lib/plot/colors.js";
import MathField from "../math/MathField.vue";

const props = defineProps({
  modelValue: { type: Array, default: () => [] }, // [{id,text,color,visible,error}]
  activeId: { type: [String, Number], default: null },
});
const emit = defineEmits(["update:modelValue", "update:activeId", "add", "remove", "change"]);

/**
 * 本地影子副本：连续快速修改多行时，若每次都以 props.modelValue 为基准构造新数组，
 * 会因为 props 更新是异步的而互相覆盖（第一次的修改被第二次用旧 props 冲掉）。
 * 以同步更新的本地副本为准即可避免丢失。
 */
const local = ref(props.modelValue.map((r) => ({ ...r })));
watch(
  () => props.modelValue,
  (v) => { local.value = v; },
  { deep: true }
);

const paletteFor = ref(null);   // 打开调色板的行 id
const fieldRefs = ref({});      // rowId → MathField 组件实例
const focusedId = ref(null);    // 符号面板把符号插到哪一行

/**
 * 符号面板：插入的是 LaTeX，MathLive 会**就地排版**（#0 是占位符位置）。
 * 例如点分式 → 字段里立刻出现一个真正的分数结构，光标落在分子上。
 */
const SYMBOLS = [
  { label: "√", tip: "根号", latex: "\\sqrt{#0}" },
  { label: "x²", tip: "平方", latex: "^{2}" },
  { label: "xⁿ", tip: "幂", latex: "^{#0}" },
  { label: "a/b", tip: "分式", latex: "\\frac{#0}{#?}" },
  { label: "π", tip: "圆周率", latex: "\\pi" },
  { label: "e", tip: "自然对数底", latex: "e" },
  { label: "|x|", tip: "绝对值", latex: "\\left|#0\\right|" },
  { label: "sin", tip: "正弦", latex: "\\sin\\left(#0\\right)" },
  { label: "cos", tip: "余弦", latex: "\\cos\\left(#0\\right)" },
  { label: "tan", tip: "正切", latex: "\\tan\\left(#0\\right)" },
  { label: "ln", tip: "自然对数", latex: "\\ln\\left(#0\\right)" },
  { label: "lg", tip: "常用对数", latex: "\\lg\\left(#0\\right)" },
  { label: "eˣ", tip: "指数函数", latex: "e^{#0}" },
  { label: "≤", tip: "小于等于", latex: "\\le" },
  { label: "≥", tip: "大于等于", latex: "\\ge" },
  { label: "θ", tip: "极角 theta", latex: "\\theta" },
];

function update(id, patch) {
  local.value = local.value.map((r) => (r.id === id ? { ...r, ...patch } : r));
  emit("update:modelValue", local.value);
  emit("change");
}

// 输入与回车由 MathField 的事件接管（MathLive 自己处理光标与结构）

/** 把符号插入当前行光标处：交给 MathLive，排版会就地生效（#0 决定光标落点）。 */
function insertSymbol(sym) {
  const id = focusedId.value ?? (local.value[0] && local.value[0].id);
  const field = fieldRefs.value[id];
  if (field && typeof field.insertLatex === "function") {
    field.insertLatex(sym.latex);
  }
}

function toggleVisible(row) {
  update(row.id, { visible: !row.visible });
}

function openPalette(row, e) {
  e.stopPropagation();
  paletteFor.value = paletteFor.value === row.id ? null : row.id;
}

function pickColor(row, color, e) {
  e.stopPropagation();
  update(row.id, { color });
  paletteFor.value = null;
}

function setFieldRef(id, el) {
  if (el) fieldRefs.value[id] = el;
}

/** 供父组件在新增行后聚焦 */
function focusRow(id) {
  nextTick(() => fieldRefs.value[id]?.focus());
}
defineExpose({ focusRow });
</script>

<template>
  <div class="expr-list">
    <!-- 符号面板：点一下插入，省去手打 √ π ≤ 这些难输入的符号 -->
    <div class="symbol-bar">
      <button
        v-for="s in SYMBOLS"
        :key="s.label"
        class="symbol-btn"
        :title="s.tip"
        @click="insertSymbol(s)"
      >{{ s.label }}</button>
    </div>

    <div
      v-for="(row, i) in local"
      :key="row.id"
      class="expr-row"
      :class="{ active: row.id === activeId, hidden: !row.visible }"
      @click="emit('update:activeId', row.id)"
    >
      <!-- 行号 -->
      <span class="row-no">{{ i + 1 }}</span>

      <!-- 显示切换（点击圆点式图标，同 Desmos） -->
      <button class="vis-btn" :title="row.visible ? '隐藏' : '显示'" @click.stop="toggleVisible(row)">
        <span class="vis-ring" :class="{ off: !row.visible }" />
      </button>

      <!-- 颜色圆点（点击改色） -->
      <button class="color-dot" :style="{ background: row.color }" title="颜色" @click="openPalette(row, $event)" />
      <div v-if="paletteFor === row.id" class="palette" @click.stop>
        <button
          v-for="c in ALL_COLORS"
          :key="c"
          class="palette-swatch"
          :style="{ background: c }"
          :class="{ picked: c === row.color }"
          @click="pickColor(row, c, $event)"
        />
      </div>

      <!-- 表达式输入：MathLive 就地排版 -->
      <!-- data-tour 只标在第一行：教程里"函数输入框"指的是用户要输入的那一格，
           多行都标会让 querySelector 命中不确定。 -->
      <MathField
        :ref="(el) => setFieldRef(row.id, el)"
        :model-value="row.text"
        :data-tour="i === 0 ? 'plot_workspace.function_input' : undefined"
        placeholder="输入表达式，如 y=x^2 或 cosx"
        @update:model-value="(v) => update(row.id, { text: v })"
        @change="emit('change')"
        @focus="focusedId = row.id"
        @enter="emit('add', i)"
      />

      <!-- 删除（行 >1 时可用） -->
      <button
        v-if="local.length > 1"
        class="del-btn"
        title="删除"
        @click.stop="emit('remove', row.id)"
      >✕</button>


      <!-- 行内错误提示（对齐 Desmos：解析不了就明确提示） -->
      <div v-if="row.error" class="expr-error">{{ row.error }}</div>
    </div>

    <button class="add-row" data-tour="plot_workspace.add_function" @click="emit('add', local.length - 1)">＋ 添加表达式</button>
  </div>
</template>

<style scoped>
.expr-list { display: flex; flex-direction: column; gap: 6px; }

/* 符号面板：紧凑单行，可横向滚动 */
.symbol-bar {
  display: flex; flex-wrap: wrap; gap: 3px;
  padding-bottom: 2px;
}
.symbol-btn {
  min-width: 26px; height: 22px; padding: 0 5px;
  border: 1px solid var(--border); border-radius: 5px;
  background: var(--surface); color: var(--text-muted);
  cursor: pointer; font-size: 12px; line-height: 1;
  font-family: 'Cambria Math', 'Latin Modern Math', Georgia, serif;
}
.symbol-btn:hover { color: var(--accent); border-color: var(--accent); background: var(--accent-soft); box-shadow: var(--shadow-1); }
.symbol-btn:active { transform: translateY(1px); }

.expr-row {
  position: relative;
  display: grid;
  grid-template-columns: 16px 22px 18px 1fr auto;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  border-radius: var(--r-md);
  border: 1px solid transparent;
  background: var(--surface);
  transition: background .12s, border-color .12s;
}
.expr-row:hover { background: var(--surface-alt); box-shadow: var(--shadow-1); }
.expr-row.active { border-color: var(--accent); background: var(--accent-soft); }
/* 输入框的框体/字号/高度统一由 MathField.vue 决定（math-field.mathfield）。
 * 这里只保留"这一行自己的状态"：隐藏行淡出。
 * 曾经这里写死 height:30px + font-size:15px，
 * 比 MathLive 内部容器（内容自适应）矮，分数会被压到下一行。 */
.expr-row.hidden .expr-input { opacity: .45; text-decoration: line-through; }

.row-no {
  font-size: 11px;
  color: var(--text-subtle);
  text-align: right;
  user-select: none;
  font-variant-numeric: tabular-nums;
}

.vis-btn { background: none; border: none; padding: 0; cursor: pointer; display: grid; place-items: center; }
.vis-ring {
  width: 13px; height: 13px; border-radius: 50%;
  border: 2px solid var(--text-subtle);
  background: var(--accent);
  border-color: var(--accent);
}
.vis-ring.off { background: transparent; border-color: var(--text-subtle); }

.color-dot {
  width: 16px; height: 16px; border-radius: 50%;
  border: 2px solid rgba(0,0,0,.12); cursor: pointer; padding: 0;
}
.palette {
  position: absolute; top: 32px; left: 24px; z-index: 20;
  display: flex; gap: 4px; padding: 6px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r-md); box-shadow: var(--shadow);
}
.palette-swatch {
  width: 18px; height: 18px; border-radius: 50%;
  border: 2px solid transparent; cursor: pointer; padding: 0;
}
.palette-swatch.picked { border-color: var(--text); }

.del-btn {
  background: none; border: none; color: var(--text-subtle);
  cursor: pointer; font-size: 12px; padding: 2px 4px; opacity: 0;
}
.expr-row:hover .del-btn { opacity: 1; }
.del-btn:hover { color: var(--danger); }

/* 预览行：紧贴输入框下方，弱化成辅助信息 */
.expr-preview {
  grid-column: 3 / -1;
  display: flex; align-items: baseline; gap: 8px;
  padding: 1px 4px 2px;
  min-height: 18px;
  font-size: 12px;
  color: var(--text-muted);
  overflow-x: auto;
}
.preview-note { font-size: 11px; color: var(--text-subtle); white-space: nowrap; }
.preview-note code {
  font-family: 'Cascadia Code', Consolas, monospace;
  background: var(--surface-alt); border-radius: 3px; padding: 0 3px;
}

.expr-error {
  grid-column: 3 / -1;
  font-size: 11.5px; color: var(--danger);
  padding-left: 4px; margin-top: 2px;
}

.add-row {
  margin-top: 2px; height: 30px;
  border: 1px dashed var(--border); border-radius: 8px;
  background: transparent; color: var(--text-subtle);
  cursor: pointer; font-size: 12.5px;
}
.add-row:hover { color: var(--accent); border-color: var(--accent); }
</style>
