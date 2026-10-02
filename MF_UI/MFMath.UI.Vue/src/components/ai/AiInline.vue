<script setup>
/**
 * AiInline — 行内 token 的渲染（递归）
 *
 * 全程只用模板插值，**没有一处 v-html、没有一处拼 HTML 字符串**：
 * 模型输出里就算写了 `<img onerror=…>`，它也会作为**文本**被插值转义后显示出来。
 * 这是"不做净化器也安全"的原因 —— 结构上不存在注入面。
 */
import MathLatex from "../math/MathLatex.vue";

defineProps({ tokens: { type: Array, default: () => [] } });

function copy(text) {
  try { navigator.clipboard?.writeText(String(text || "")); } catch { /* 忽略 */ }
}
</script>

<template>
  <!-- 用自身文件名递归：Vue 允许 SFC 隐式引用自己 -->
  <template v-for="(t, i) in tokens" :key="i">
    <strong v-if="t.type === 'strong'"><AiInline :tokens="t.content" /></strong>
    <em v-else-if="t.type === 'em'"><AiInline :tokens="t.content" /></em>
    <s v-else-if="t.type === 'strike'"><AiInline :tokens="t.content" /></s>
    <code v-else-if="t.type === 'code'" class="md-code">{{ t.text }}</code>
    <MathLatex v-else-if="t.type === 'math'" :latex="t.tex" :display="t.display" :fallback="t.tex" />
    <!-- 链接：安全协议才做成可点的，但**不导航**（导航会把整个应用带走），点了复制 -->
    <a v-else-if="t.type === 'link' && t.safe" class="md-link" :href="t.href"
       :title="'点击复制：' + t.href" @click.prevent="copy(t.href)">
      <AiInline :tokens="t.content" /><span class="md-url">{{ t.href }}</span>
    </a>
    <span v-else-if="t.type === 'link'" class="md-link-unsafe" :title="'不安全的链接协议，仅显示：' + t.href">
      <AiInline :tokens="t.content" /><span class="md-url">{{ t.href }}</span>
    </span>
    <span v-else class="md-text">{{ t.text }}</span>
  </template>
</template>

<style scoped>
.md-text { white-space: pre-wrap; }
.md-code {
  font-family: ui-monospace, Consolas, monospace;
  font-size: .92em; padding: 1px 4px; border-radius: 4px;
  background: var(--code-bg, rgba(127, 127, 127, .16));
}
.md-link { color: var(--accent, #5a82f0); cursor: pointer; text-decoration: none; }
.md-link:hover { text-decoration: underline; }
.md-link-unsafe { color: var(--muted); text-decoration: line-through; cursor: help; }
.md-url {
  font-size: .82em; color: var(--muted); margin-left: 4px;
  word-break: break-all; text-decoration: none;
}
</style>
