<script setup>
/**
 * PlaceholderView — 占位视图（功能迁移中的模式）
 * props.name 由路由 meta 传入；迁移完成后该路由指向真实组件
 */
import { computed } from "vue";
const props = defineProps({ name: { type: String, default: "" } });
const viewName = computed(() => props.name || "此模式");
</script>

<template>
  <div class="view-body">
    <div class="placeholder-view">
      <span class="placeholder-icon">◌</span>
      <span class="placeholder-title">{{ viewName }}</span>
      <span class="placeholder-desc">该模式正由旧版 MFMath.UI 迁移到 Vue，暂未接入</span>
    </div>
  </div>
</template>
