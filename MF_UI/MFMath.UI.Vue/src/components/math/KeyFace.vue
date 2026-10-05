<script setup>
/**
 * KeyFace — 数学键盘的**键面**（排版逻辑在 lib/math/keyFace.js，构建期自检跑同一套逻辑）。
 *
 * 为什么键面需要排版：模板类键的键面本身就是 LaTeX（`\frac{▢}{▢}`、`∫_{▢}^{▢}`…）。
 * 以前直接把 LaTeX 源码当文字画出来，用户看到一串反斜杠和花括号，等于一排看不懂的键。
 *
 * 两类键面走两条路：
 *   · 需要排版的（模板、`I_n`、`0_{m×n}`）→ KaTeX，失败自动退回文本；
 *   · 其余 100 多个（`∫` `sin` `α` `A⁻¹`）→ **保持原来的纯文字**，连字体都不变，
 *     免得为了修 10 个键把另外 109 个键的观感也改掉。
 */
import { computed } from "vue";
import { keyFaceInfo } from "../../lib/math/keyFace.js";
import MathLatex from "./MathLatex.vue";

const props = defineProps({
  /** 键面原字样（可能含 ▢ 占位符） */
  label: { type: String, default: "" },
});

const info = computed(() => keyFaceInfo(props.label));
</script>

<template>
  <MathLatex v-if="info.tex" :latex="info.tex" :fallback="info.text" />
  <span v-else class="face-plain">{{ info.text }}</span>
</template>

<style scoped>
.face-plain { white-space: nowrap; }
</style>
