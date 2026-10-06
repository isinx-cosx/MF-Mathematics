<script setup>
/**
 * ReactPlotView.vue —— 把 React 版的 2D 绘图页**嵌进 Vue 外壳**（React-in-Vue）
 *
 * 为什么这样接，而不是把整个 UI 换成 React：
 *   React 版目前是**迁移外壳**（`MFMath.UI.React/src/App.tsx` 的 MIGRATED_PLOTS 只有
 *   `/plot/2d` 与 `/plot/polar`，其余 25 个页面显示"还没迁移到 React"占位）。
 *   直接换成 React 外壳会让计算页/设置/教程/控制台集体变占位 —— 那是迁移的终点，不是这一步。
 *   所以这一步只把这两个绘图页换成 React，外壳仍是 Vue。
 *
 * 逻辑层是**同一份**：React 侧源码写的是 `@shared/plot/*`、`@shared/bridge.js`，
 * 由 vite.config.js 的别名指到本工程的 `src/lib` —— 同一个模块实例，
 * 所以 plotMath 的注入钩子、引擎桥（hostObjects.sync.mf）都共享，不会出现两套算法漂移。
 *
 * ⚠ 切换 2D ↔ 极坐标必须**重挂**：PlotPage 里 `mode` 是 useState 初值，
 *   只改 prop 不会生效（Vue 版是 watch 后改 ref，React 版没做这个分支）。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { createElement } from "react";
import { createRoot } from "react-dom/client";
import PlotPage from "../../../../MFMath.UI.React/src/plot/PlotPage";

const route = useRoute();
/** 与 Vue 版一致：两个绘图入口共用同一页，靠路由 meta.grid 区分直角/极坐标 */
const mode = computed(() => (route.meta?.grid === "polar" ? "polar" : "rect"));

const host = ref(null);
let root = null;

function mount(m) {
  if (!host.value) return;
  if (root) {
    // 先卸载：React 的 ResizeObserver / 采样循环必须收尾，否则换页后还在跑
    root.unmount();
    root = null;
  }
  root = createRoot(host.value);
  root.render(createElement(PlotPage, { gridMode: m }));
}

onMounted(() => mount(mode.value));
watch(mode, (m) => mount(m));
onBeforeUnmount(() => {
  if (root) {
    root.unmount();
    root = null;
  }
});
</script>

<template>
  <div ref="host" class="react-plot-host" data-react-plot></div>
</template>

<style scoped>
/* React 根节点 .desmos-layout 用的是 height:100%，所以这里必须给出确定高度 */
.react-plot-host {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
</style>
