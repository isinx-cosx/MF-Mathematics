<script setup>
/**
 * MathLatex — 用 KaTeX 渲染引擎给出的 LaTeX。
 *
 * 渲染失败或没有 LaTeX 时**退回纯文本**，绝不显示空白：
 * 表达式显示不出来比显示得不好看严重得多。
 */
import { computed } from "vue";
import katex from "katex";

const props = defineProps({
  latex: { type: String, default: "" },
  fallback: { type: String, default: "" },
  display: { type: Boolean, default: false },
});

/** 真正送进 KaTeX 的源码（去空白） */
const src = computed(() => (props.latex || "").trim());

const html = computed(() => {
  if (!src.value) return "";
  try {
    return katex.renderToString(src.value, {
      throwOnError: false,   // 语法可疑也尽量渲染，而不是整块消失
      displayMode: props.display,
      output: "html",
      strict: false,
    });
  } catch {
    return "";
  }
});
</script>

<template>
  <!-- data-tex 保留原始 LaTeX：KaTeX 把公式拆成一堆 span，
       文字内容再也读不回原式，调试与测试都需要这个出口 -->
  <span v-if="html" class="math-latex" :data-tex="src" v-html="html" />
  <span v-else class="math-plain">{{ fallback }}</span>
</template>

<style scoped>
.math-latex { display: inline-block; line-height: 1.2; }
/* KaTeX 默认字号偏大，这里跟随父级上下文 */
.math-latex :deep(.katex) { font-size: 1.02em; }
.math-plain {
  font-family: 'Cambria Math', 'Latin Modern Math', Georgia, serif;
  color: inherit;
  white-space: pre-wrap;
}
</style>
