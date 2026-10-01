<script setup>
/**
 * 设置 · 占位分组（AI / 搜索 / 更新）
 *
 * 设计取舍：**不隐藏、也不留空白**。用户需要知道"这个功能存在，但还没做，依赖什么"。
 * 每个待实现项都从 catalog 里取（单一真相源），所以：
 *   · 占位内容与将来的真实实现共用同一份清单，做完一项就把该行的 status 改成 ready；
 *   · 顶部搜索能搜到这些项，并且点进去会落到这里（而不是"搜不到 = 不存在"）。
 *
 * 为什么不做成"点一下就报错"的假控件：那正是 v1 的老毛病——顶栏的"搜索/历史"是
 * 无事件绑定的死按钮，用户点了没反应也查不到原因。
 */
const props = defineProps({
  group: { type: Object, required: true },
  items: { type: Array, default: () => [] },
});
</script>

<template>
  <section>
    <div class="ph-head">
      <h3 class="ph-title">{{ group.label }} 配置</h3>
      <p class="ph-sub">该功能将在后续版本提供。</p>
      <p class="ph-dep">当前状态：未接入（依赖 {{ group.depends || "后续阶段" }}）</p>
    </div>

    <div class="ph-list">
      <div v-for="it in items" :key="it.id" class="s-row" :data-setting="it.id">
        <div class="s-label">
          <label>{{ it.label }}</label>
          <p class="s-hint">等待对应功能落地后开放；界面位置与字段名已经预留</p>
        </div>
        <div class="s-ctl"><span class="pending-tag">待实现</span></div>
      </div>
    </div>

    <p class="ph-note">
      这一组不做成"点了报错"的假控件：v1 顶栏的「搜索 / 历史」就是无事件绑定的死按钮，
      点了没反应也查不到原因。这里显式说明状态与依赖，功能就绪后同一位置直接可用。
    </p>
  </section>
</template>

<style scoped>
.ph-head { border-left: 3px solid var(--accent, #3b82f6); padding-left: 10px; margin-bottom: 12px; }
.ph-title { margin: 0; font-size: 14px; }
.ph-sub { margin: 4px 0 2px; font-size: 13px; }
.ph-dep { margin: 0; font-size: 12px; color: var(--text-subtle, #64748b); }
.ph-list { margin-top: 6px; }
.pending-tag {
  font-size: 11.5px; padding: 2px 8px; border-radius: 999px;
  border: 1px dashed var(--border); color: var(--text-subtle, #94a3b8);
}
.ph-note {
  margin-top: 14px; padding: 8px 10px; font-size: 12px; border-radius: 8px;
  background: var(--surface-alt); color: var(--text-subtle, #64748b);
}
</style>
