<script setup>
import { labelOf } from "../../lib/engine/resultModel.js";
/**
 * ResultValue — 按 resultModel 的节点树渲染结果。
 *
 * 数学节点交给 KaTeX（MathLatex），元信息/中文说明原样显示；
 * 矩阵用表格、对象用键值行、一维数组用逗号分隔。
 * 类名沿用旧实现的 res-table / res-obj / res-row / res-key / res-val，
 * 既有选择器与测试不用改。
 */
import MathLatex from "../math/MathLatex.vue";

defineProps({
  /** toResultNodes() 的结果 */
  nodes: { type: Array, default: () => [] },
});
</script>

<template>
  <template v-for="(n, i) in nodes" :key="i">
    <span v-if="n.k === 'num'" class="rv-num">{{ n.text }}</span>
    <span v-else-if="n.k === 'bool'" class="rv-bool">{{ n.text }}</span>
    <span v-else-if="n.k === 'text'" class="rv-text">{{ n.text }}</span>
    <MathLatex v-else-if="n.k === 'math'" class="rv-math" :latex="n.latex" :fallback="n.text" />
    <span v-else-if="n.k === 'list'" class="res-list">
      <template v-for="(it, j) in n.items" :key="j">
        <span v-if="j" class="rv-sep">, </span>
        <ResultValue :nodes="it" />
      </template>
    </span>
    <table v-else-if="n.k === 'table'" class="res-table">
      <tbody>
        <tr v-for="(row, r) in n.rows" :key="r">
          <td v-for="(cell, c) in row" :key="c"><ResultValue :nodes="cell" /></td>
        </tr>
      </tbody>
    </table>
    <div v-else-if="n.k === 'obj'" class="res-obj">
      <div v-for="(row, r) in n.rows" :key="r" class="res-row">
        <span class="res-key">{{ labelOf(row.key) }}</span>
        <span class="res-val"><ResultValue :nodes="row.value" /></span>
      </div>
    </div>
  </template>
</template>

<style scoped>
.rv-num, .rv-bool, .rv-text { font-family: 'Cambria Math', 'Latin Modern Math', Georgia, serif; }
.rv-bool { font-weight: 600; }
.rv-sep { color: var(--text-subtle); }

.res-list { display: inline; }

.res-table {
  border-collapse: collapse;
  font-size: 0.85em;
}
.res-table td {
  border: 1px solid var(--border);
  padding: 3px 10px;
  text-align: right;
}
.res-obj { display: flex; flex-direction: column; gap: 4px; }
.res-row { display: flex; gap: 10px; align-items: baseline; }
.res-key {
  min-width: 96px;
  color: var(--text-muted);
  font-size: 0.72em;
  font-family: 'Cascadia Code', Consolas, monospace;
}
.res-val { color: var(--text); }
</style>
