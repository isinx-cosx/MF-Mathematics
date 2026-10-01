<script setup>
/**
 * ResultDialog — 结果对话框（对应 Python ResultDialog / 旧版 showResultDialog）
 *
 * 输出**用 KaTeX 排版**，与输入框的 MathLive 对齐：
 *   · 上下文（用户输入的那条表达式）→ 引擎 sym_latex → KaTeX
 *   · 结果值 → resultModel 判定"哪段是数学"，数学交给 KaTeX，元信息原文显示
 * 旧实现是把 `^2` 换成 `<sup>` 的 ASCII 近似（3*x<sup>2</sup>），
 * 分数、根式、绝对值都表达不出来，所以这里换成真排版。
 */
import { computed, onMounted, onBeforeUnmount } from "vue";
import ResultValue from "./ResultValue.vue";
import MathLatex from "../math/MathLatex.vue";
import { toResultNodes, textLatex, labelOf } from "../../lib/engine/resultModel.js";
import { fmtNum } from "../../lib/engine/resultFormat.js";
import { prepareExpr } from "../../lib/plot/prepare.js";

const props = defineProps({
  mode: { type: String, default: "" },
  expr: { type: String, default: "" },
  /** 引擎返回的 {isError, value}；null 表示未接入 */
  result: { type: Object, default: null },
  /** 原始 JSON（供复制/调试） */
  rawJson: { type: String, default: "" },
});
const emit = defineEmits(["close", "steps"]);

/** 三种状态：缺引擎 / 引擎报错 / 正常结果 */
const state = computed(() => {
  if (!props.result) return { k: "missing", text: "（计算功能待接入引擎）" };
  if (props.result.isError) return { k: "error", text: String(props.result.value) };
  return { k: "ok", text: "" };
});

const nodes = computed(() => (state.value.k === "ok" ? toResultNodes(props.result.value) : []));

/**
 * 上下文用 prepare_expr 的 LaTeX：它保留**用户书写的顺序**（x^2-4 → x^{2} - 4），
 * 而 sym_latex 走 SymEngine 打印器，会重排成规范形式（-4 + x^2）——
 * 这一栏的语义是"你要算的是这个"，重排会让人以为输入变了。
 */
const contextLatex = computed(() => {
  const e = String(props.expr || "").trim();
  if (!e) return "";
  const p = prepareExpr(e);
  if (p.ok && p.latex) return p.latex;
  return textLatex(e);
});

/**
 * 复制结果：给**可读文本**，不是包装 JSON。
 *
 * 之前复制的是 props.rawJson，用户粘出来是
 *   {"isError": false, "value": {"delta": 1, "solutions": ["2","3"]}}
 * 这种机器格式，贴到别处根本没法看。现在按结果类型给人类可读的文本：
 * 数值原样；对象排成 "键 = 值" 多行；数组逗号连接。原始 JSON 仍可通过
 * 「复制原始 JSON」单独取（调试用）。
 */
function resultAsText() {
  const v = props.result?.value;
  if (v === null || v === undefined) return "";
  if (typeof v === "number") return fmtNum(v);
  if (typeof v === "string") return v;
  if (Array.isArray(v)) return v.map((x) => (typeof x === "object" ? JSON.stringify(x) : String(x))).join(", ");
  if (typeof v === "object") {
    return Object.entries(v)
      .map(([k, x]) => `${labelOf(k)} = ${typeof x === "object" && x !== null ? JSON.stringify(x) : String(x)}`)
      .join("\n");
  }
  return String(v);
}

async function copyResult() {
  const text = resultAsText();
  if (!text) return;
  try { await navigator.clipboard.writeText(text); } catch { /* 剪贴板不可用时忽略 */ }
}

/** 原始 JSON（调试出口）：用户明确要"机器格式"时才用 */
async function copyRawJson() {
  try { await navigator.clipboard.writeText(props.rawJson || ""); } catch { /* 忽略 */ }
}

/**
 * 关闭方式：右上角 ✕、底部「关闭」、Esc。
 *
 * 曾经点遮罩（对话框外部）就会关闭，用户抱怨"点周围就没了，很麻烦"——
 * 看结果时经常要顺手把鼠标移出去，一不小心结果就消失了，还得重算一遍。
 * 现在遮罩点击不再关闭；键盘用户走 Esc，鼠标用户走 ✕/关闭按钮。
 */
function onKeydown(e) {
  if (e.key === "Escape") { e.preventDefault(); emit("close"); }
}
onMounted(() => window.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));
</script>

<template>
  <div class="dialog-overlay">
    <div class="dialog">
      <div class="dialog-header">
        <!-- 出错时标题要说"错误"：恒为"计算结果 — xxx"会让用户以为算完了（原版就是这么分的） -->
        <span>{{ state.k === "error" ? "错误" : "计算结果" }} — {{ mode }}</span>
        <button class="dialog-close" @click="emit('close')">✕</button>
      </div>
      <div class="dialog-body">
        <!-- 上下文同样按数学排版；引擎解析不了就退回原文 -->
        <div class="dialog-context">
          <MathLatex v-if="contextLatex" :latex="contextLatex" :fallback="expr" />
          <span v-else>{{ expr || "（空表达式）" }}</span>
        </div>
        <div class="dialog-result" :class="{ 'is-error': state.k === 'error' }">
          <span v-if="state.k === 'error'" class="rv-error">错误：{{ state.text }}</span>
          <span v-else-if="state.k === 'missing'" class="rv-empty">{{ state.text }}</span>
          <ResultValue v-else :nodes="nodes" />
        </div>
      </div>
      <div class="dialog-footer">
        <button class="btn btn-ghost" data-tour="result_dialog.steps_button" @click="emit('steps')">查看步骤</button>
        <button v-if="rawJson" class="btn btn-ghost" title="复制可读的数学文本" @click="copyResult">复制结果</button>
        <button v-if="rawJson" class="btn btn-ghost" title="复制引擎原始 JSON（调试用）" @click="copyRawJson">复制 JSON</button>
        <button class="btn btn-primary" @click="emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 覆盖 theme.css 的等宽 13px/16px —— 结果现在是排版出来的数学，不是 ASCII 文本 */
.dialog-context {
  font-family: inherit;
  font-size: 15px;
  color: var(--text);
}
.dialog-result {
  font-family: inherit;
  font-size: 20px;
  font-weight: 500;
  line-height: 1.5;
}
.dialog-result.is-error { border-left: 3px solid var(--danger); padding-left: 10px; }
.rv-error { color: var(--danger); font-size: 14px; font-weight: 400; }
.rv-empty { color: var(--text-subtle); font-size: 14px; font-weight: 400; }
</style>
