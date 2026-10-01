<script setup>
/**
 * MultiVarDialog — 多参数输入弹窗（对应 Python multi_var_dialog / 旧版 showMultiVarDialog）
 * 引擎 handler 的参数提取顺序 ≠ 语义顺序，因此这里只负责"收集用户填写的值"，
 * 参数分配交由 lib/engine/calcArgs.js 的 buildEngineArgsFromValues 处理。
 */
import { ref, onMounted, onBeforeUnmount, nextTick } from "vue";
import { escapeHtml } from "../../lib/engine/resultFormat.js";

const props = defineProps({
  mode: { type: String, required: true },
  /** 字段定义 [[标签, 默认值], ...] */
  fields: { type: Array, default: () => [] },
  /** 输入框中的表达式（预填第一个字段） */
  firstValue: { type: String, default: "" },
});
const emit = defineEmits(["confirm", "cancel"]);

const values = ref([]);
const inputs = ref([]);

onMounted(() => {
  values.value = props.fields.map(([label, def], i) =>
    i === 0 && props.firstValue ? props.firstValue : (def ?? "")
  );
  nextTick(() => {
    const first = inputs.value[0];
    if (first) { first.focus(); first.select(); }
  });
});

function confirm() {
  emit("confirm", values.value.map((v) => String(v ?? "").trim()));
}

function onKeydown(e) {
  if (e.key === "Enter") { e.preventDefault(); confirm(); }
  else if (e.key === "Escape") { e.preventDefault(); emit("cancel"); }
}

// Esc/Enter 挂在 window 上，而不是内层 div 的 @keydown。
// 挂在 div 上时，用户一旦点到遮罩空白处（焦点移出该 div）就再也关不掉这个弹窗——
// 原版是 QDialog，Esc 永远有效。这里对齐 ResultDialog 的做法（见其 :62-66）。
onMounted(() => window.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));
</script>

<template>
  <!-- 点遮罩不关闭：多次填参数时鼠标经常划过外部，一不小心对话框就没了（用户反馈）。
       关闭方式：右上角 ✕ / 取消按钮 / Esc。 -->
  <div class="dialog-overlay">
    <div class="dialog">
      <div class="dialog-header">
        <span>输入参数 — {{ mode }}</span>
        <button class="dialog-close" @click="emit('cancel')">✕</button>
      </div>
      <div class="dialog-body">
        <div v-for="(f, i) in fields" :key="i" class="mvar-group">
          <label class="mvar-label">{{ f[0] }}</label>
          <input
            :ref="(el) => (inputs[i] = el)"
            v-model="values[i]"
            class="input mono"
            spellcheck="false"
          />
        </div>
        <div class="mvar-actions">
          <button class="btn btn-ghost" @click="emit('cancel')">取消</button>
          <button class="btn btn-primary" @click="confirm">计算</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mvar-group { display: flex; flex-direction: column; gap: 4px; margin-bottom: 10px; }
.mvar-label { font-size: 12px; color: var(--text-muted); }
.mvar-actions {
  display: flex; justify-content: flex-end; gap: 8px;
  padding-top: 12px; margin-top: 4px;
  border-top: 1px solid var(--border);
}
</style>
