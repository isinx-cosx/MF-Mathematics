<script setup>
/**
 * AiMarkdown — 助手正文的块级渲染
 *
 * 解析在 lib/ai/markdown.ts（token 树），这里只负责把 token 摆成 DOM。
 * **没有 v-html**：模型写的 HTML 会以文本形式转义显示 —— 这是刻意的，
 * 见 markdown.ts 顶部关于"为什么不引 marked + DOMPurify"的说明。
 */
import { computed } from "vue";
import AiInline from "./AiInline.vue";
import { parseMarkdown } from "../../lib/ai/markdown.ts";

const props = defineProps({ text: { type: String, default: "" } });
const blocks = computed(() => parseMarkdown(props.text));
</script>

<template>
  <div class="md" data-ai="markdown">
    <template v-for="(b, i) in blocks" :key="i">
      <h3 v-if="b.type === 'h'" class="md-h" :class="'lv' + b.level"><AiInline :tokens="b.content" /></h3>
      <p v-else-if="b.type === 'p'" class="md-p"><AiInline :tokens="b.content" /></p>
      <ul v-else-if="b.type === 'ul'" class="md-ul">
        <li v-for="(it, j) in b.items" :key="j" :style="{ marginLeft: it.depth * 14 + 'px' }">
          <AiInline :tokens="it.content" />
        </li>
      </ul>
      <ol v-else-if="b.type === 'ol'" class="md-ol">
        <li v-for="(it, j) in b.items" :key="j" :value="Number(it.n)"
            :style="{ marginLeft: it.depth * 14 + 'px' }">
          <AiInline :tokens="it.content" />
        </li>
      </ol>
      <pre v-else-if="b.type === 'code'" class="md-pre" :data-lang="b.lang"><code>{{ b.text }}</code></pre>
      <blockquote v-else-if="b.type === 'quote'" class="md-quote"><AiInline :tokens="b.content" /></blockquote>
      <hr v-else-if="b.type === 'hr'" class="md-hr" />
      <table v-else-if="b.type === 'table'" class="md-table">
        <thead>
          <tr>
            <th v-for="(c, j) in b.head" :key="j" :style="{ textAlign: b.align[j] || 'left' }">
              <AiInline :tokens="c" />
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, r) in b.rows" :key="r">
            <td v-for="(c, j) in row" :key="j" :style="{ textAlign: b.align[j] || 'left' }">
              <AiInline :tokens="c" />
            </td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>

<style scoped>
.md { display: flex; flex-direction: column; gap: 8px; }
.md-p { margin: 0; }
.md-h { margin: 2px 0 0; font-size: 14px; }
.md-h.lv1 { font-size: 16px; }
.md-h.lv2 { font-size: 15px; }
.md-ul, .md-ol { margin: 0; padding-left: 20px; display: flex; flex-direction: column; gap: 3px; }
.md-pre {
  margin: 0; padding: 8px 10px; overflow: auto;
  background: var(--code-bg, rgba(127, 127, 127, .12));
  border-radius: 6px; font-size: 12px; line-height: 1.55;
}
.md-pre code { font-family: ui-monospace, Consolas, monospace; white-space: pre; }
.md-quote {
  margin: 0; padding: 2px 0 2px 10px; color: var(--muted);
  border-left: 2px solid var(--border);
}
.md-hr { border: 0; border-top: 1px solid var(--border); margin: 4px 0; width: 100%; }
.md-table { border-collapse: collapse; font-size: 12.5px; }
.md-table th, .md-table td { border: 1px solid var(--border); padding: 3px 7px; }
.md-table th { background: var(--code-bg, rgba(127, 127, 127, .10)); font-weight: 600; }
</style>
