<script setup>
/**
 * ReactPlotView.vue —— 把 React 版绘图页**嵌进 Vue 外壳**（React-in-Vue）
 *
 * 为什么这样接，而不是把整个 UI 换成 React：
 *   React 版目前是**迁移外壳**（`MFMath.UI.React/src/App.tsx` 的 MIGRATED_PLOTS 只有
 *   `/plot/2d` 与 `/plot/polar`，其余页面显示"还没迁移到 React"占位）。
 *   本轮的边界是**绘图组整组归 React、其余页面仍留 Vue** ——
 *   直接换成 React 外壳会让计算页/设置/教程/控制台集体变占位，那是迁移的终点。
 *
 * 逻辑层是**同一份**：React 侧源码写的是 `@shared/plot/*`、`@shared/bridge.js`，
 * 由 vite.config.js 的别名指到本工程的 `src/lib` —— 同一个模块实例，
 * 所以 plotMath 的注入钩子、引擎桥（hostObjects.sync.mf）都共享，不会出现两套算法漂移。
 * 样式同样是**抽取值 Vue 版**（tools/extract-styles.mjs），不是重写。
 *
 * 页面按路由 meta.reactPage（见 src/router/index.js 的 REACT_PAGES）动态加载：
 * 每页各自一个分块，进哪页下哪页的代码。
 *
 * ⚠ 换页必须**重挂**：React 页里的模式/状态是 useState 初值，只改 prop 不会生效；
 *   而且不卸载的话 ResizeObserver / 采样循环会在离开后继续跑。
 */
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { useRoute } from "vue-router";
import { createElement } from "react";
import { createRoot } from "react-dom/client";

/** 页面键 → React 组件加载器（与 router/index.js 的 REACT_PAGES 对应） */
const LOADERS = {
  "2d": () => import("../../../../MFMath.UI.React/src/plot/PlotPage"),
  "polar": () => import("../../../../MFMath.UI.React/src/plot/PlotPage"),
  "vector": () => import("../../../../MFMath.UI.React/src/plot/PlotVectorPage"),
  "fractal": () => import("../../../../MFMath.UI.React/src/plot/PlotFractalPage"),
  "3d": () => import("../../../../MFMath.UI.React/src/plot/Plot3DPage"),
  "complex": () => import("../../../../MFMath.UI.React/src/plot/PlotComplexPage"),
  "geometry": () => import("../../../../MFMath.UI.React/src/plot/PlotGeometryPage"),
};

const route = useRoute();
/** 当前页键：以 meta.reactPage 为准；老路由（只有 meta.grid）退回 2d/polar */
const pageKey = () => route.meta?.reactPage || (route.meta?.grid === "polar" ? "polar" : "2d");

const host = ref(null);
const loading = shallowRef(false);
let root = null;
let disposed = false;
/** 挂载序号：异步加载期间又切了页，旧的那次不该再挂 */
let seq = 0;

async function mount(key) {
  if (!host.value) return;
  const my = ++seq;
  if (root) {
    // 先卸载：React 的 ResizeObserver / 采样循环必须收尾，否则换页后还在跑
    root.unmount();
    root = null;
  }
  loading.value = true;
  const loader = LOADERS[key] || LOADERS["2d"];
  let mod = null;
  try {
    mod = await loader();
  } catch (e) {
    loading.value = false;
    console.error("[react-plot] 页面加载失败", key, e);
    return;
  }
  loading.value = false;
  if (disposed || my !== seq || !host.value) return;   // 已卸载或已被更新的那次取代
  /* 2d / polar 也**必须**传 routePath（BUGS.md B14/B15）：工作区按 `route.path` 分页存
   * （`/plot/2d` 与 `/plot/polar` 各一份），导出图片的默认文件名与提示也用它。
   * 以前这两条只传 gridMode，于是 2D/极坐标页既存不进工作区，导出也不写"导到哪了"。
   * 其余页本来就在传 routePath。 */
  const props = key === "2d" || key === "polar"
    ? { gridMode: key === "polar" ? "polar" : "rect", routePath: route.path }
    : { routePath: route.path };
  root = createRoot(host.value);
  root.render(createElement(mod.default, props));
}

onMounted(() => mount(pageKey()));
watch(() => route.fullPath, () => {
  if (route.meta?.reactPage || route.path.startsWith("/plot/")) mount(pageKey());
});
onBeforeUnmount(() => {
  disposed = true;
  seq++;
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
/* React 各页的根节点用的是 height:100%（.desmos-layout / .vf-layout / …），
 * 所以这里必须给出确定高度，否则画布列会塌成 0。 */
.react-plot-host {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
</style>
