<script setup>
/**
 * SettingsView — 设置面板**容器**
 *
 * 它是一个容器而不是一个页面：分组会随功能进度陆续填内容。
 * 分三批（按依赖）：
 *   第一批（现在就有）：外观 / 引擎 / 组件 / 存储与数据
 *   第二批（P1 后）：搜索、历史与工作区管理
 *   第三批（P2/P3/P5 后）：AI、更新
 * 未实现的分组**不隐藏、不留空白**，而是显式列出"将提供什么 + 依赖什么"，
 * 且这些项也进搜索索引 —— 否则用户搜"API Key"搜不到，会以为软件没这功能。
 *
 * 布局用"左侧分类导航 + 右侧内容"而不是标签页：分组有 7 个，标签页会挤。
 * 顶部搜索做的是**跳到具体某一项**（不是筛掉其它分组）：命中后切到该分组、
 * 滚到该行并短暂高亮。设置项一多，"按名字找"比"按分组翻"快得多。
 */
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { GROUPS, itemsOf, searchItems, groupById } from "../../lib/settings/catalog.js";
import AppearanceGroup from "../../components/settings/AppearanceGroup.vue";
import CalcPlotGroup from "../../components/settings/CalcPlotGroup.vue";
import EngineGroup from "../../components/settings/EngineGroup.vue";
import ComponentsGroup from "../../components/settings/ComponentsGroup.vue";
import StorageGroup from "../../components/settings/StorageGroup.vue";
import PlaceholderGroup from "../../components/settings/PlaceholderGroup.vue";

const active = ref("appearance");
const query = ref("");
const highlightId = ref("");
const contentEl = ref(null);

const route = useRoute();
// 支持 /settings?group=search 这种深链：搜索占位面板的「看设置里的搜索项」要用它，
// 否则用户点进来落在"外观"，还得自己找一遍。
//
// 必须**同时**监听 query 变化，而不是只在 onMounted 里读一次：
// 用户已经停在设置页时再点一次深链（或从别的分组跳过来）不会重新挂载组件，
// 只读 onMounted 就会出现"点了没反应"。自动化测试正是这么抓到的。
function applyGroupFromQuery(g) {
  const id = String(g || "");
  if (id && groupById(id)) active.value = id;
}
applyGroupFromQuery(route.query.group);
onMounted(() => applyGroupFromQuery(route.query.group));
watch(() => route.query.group, applyGroupFromQuery);

const group = computed(() => groupById(active.value));
const pendingGroups = new Set(GROUPS.filter((g) => g.status === "pending").map((g) => g.id));
const results = computed(() => searchItems(query.value));

/** 每个分组的"已完成 / 总数"，让进度一眼可见 */
function countOf(gid) {
  const items = itemsOf(gid);
  const ready = items.filter((i) => i.status === "ready").length;
  return { ready, total: items.length };
}

function jump(item) {
  active.value = item.group;
  query.value = "";
  nextTick(() => {
    const box = contentEl.value;
    const el = box?.querySelector(`[data-setting="${item.id}"]`);
    if (!el) return;
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    highlightId.value = item.id;
    setTimeout(() => { if (highlightId.value === item.id) highlightId.value = ""; }, 1800);
  });
}
</script>

<template>
  <div class="view-body set-body">
    <aside class="set-nav">
      <div class="set-search-wrap">
        <input v-model="query" class="set-search" type="search" placeholder="搜索设置项（如 密钥 / 缓存 / DLL）" />
        <ul v-if="query.trim() && results.length" class="set-results">
          <li v-for="it in results" :key="it.id" @click="jump(it)">
            <span class="r-label">{{ it.label }}</span>
            <span class="r-group">{{ groupById(it.group)?.label }}</span>
          </li>
        </ul>
        <p v-else-if="query.trim()" class="set-noresult">没有匹配的设置项</p>
      </div>

      <ul class="set-groups">
        <!-- data-tour：教程里"设置 → AI 配置"这类步骤原本没有目标（v1 的
             settings_dialog.ai_tab / appearance_tab 全库都没有 setObjectName）。
             这里给对应分组挂上引导目标，那两个步骤就不再是"目标不存在"。 -->
        <li v-for="g in GROUPS" :key="g.id" :class="{ on: active === g.id }"
            :data-tour="g.id === 'appearance' ? 'settings_dialog.appearance_tab' : (g.id === 'ai' ? 'settings_dialog.ai_tab' : undefined)"
            @click="active = g.id">
          <span class="g-label">{{ g.label }}</span>
          <span class="g-count" :class="{ done: !pendingGroups.has(g.id) && countOf(g.id).ready === countOf(g.id).total }">
            {{ countOf(g.id).ready }}/{{ countOf(g.id).total }}
          </span>
        </li>
      </ul>

      <p class="set-tip">
        带 <b>?</b> 的分组尚未接入，点开可看到"将提供什么、依赖什么"。
      </p>
    </aside>

    <section ref="contentEl" class="set-content" :class="{ 'has-flash': highlightId }">
      <header class="set-head">
        <h2 class="set-title">{{ group?.label }}</h2>
        <p v-if="group?.note" class="set-note">{{ group.note }}</p>
        <p v-else-if="group?.depends" class="set-note">依赖：{{ group.depends }}</p>
      </header>

      <div :class="{ flash: highlightId === 'appearance' }">
        <AppearanceGroup v-if="active === 'appearance'" />
        <CalcPlotGroup v-else-if="active === 'calc'" />
        <EngineGroup v-else-if="active === 'engine'" />
        <ComponentsGroup v-else-if="active === 'components'" />
        <StorageGroup v-else-if="active === 'storage'" />
        <PlaceholderGroup v-else :group="group" :items="itemsOf(active)" />
      </div>
    </section>
  </div>
</template>

<style scoped>
.set-body { display: flex; gap: 16px; align-items: flex-start; }

/* ── 左侧分组导航 ── */
.set-nav { flex: none; width: 190px; position: sticky; top: 0; }
.set-search-wrap { position: relative; margin-bottom: 10px; }
.set-search {
  width: 100%; font: inherit; font-size: 12px; padding: 6px 9px;
  border: 1px solid var(--border); border-radius: var(--r-sm, 6px);
  background: var(--surface); color: var(--text);
}
.set-results {
  position: absolute; left: 0; right: 0; top: calc(100% + 4px); z-index: 30;
  margin: 0; padding: 4px; list-style: none; max-height: 300px; overflow: auto;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r-sm, 6px); box-shadow: var(--shadow-3, 0 10px 30px rgba(0,0,0,.18));
}
.set-results li { display: flex; gap: 8px; align-items: baseline; padding: 5px 7px; border-radius: 5px; cursor: pointer; }
.set-results li:hover { background: var(--surface-alt); }
.r-label { font-size: 12.5px; }
.r-group { margin-left: auto; font-size: 11px; color: var(--text-subtle, #94a3b8); }
.set-noresult { margin: 6px 0 0; font-size: 11.5px; color: var(--text-subtle, #94a3b8); }

.set-groups { margin: 0; padding: 0; list-style: none; }
.set-groups li {
  display: flex; align-items: center; gap: 7px; padding: 6px 9px; margin-bottom: 2px;
  border-radius: var(--r-sm, 6px); cursor: pointer; font-size: 13px;
}
.set-groups li:hover { background: var(--surface-alt); }
.set-groups li.on { background: var(--accent-soft, #e0ecff); color: var(--accent, #2563eb); font-weight: 600; }
.g-count { margin-left: auto; font-size: 11px; color: var(--text-subtle, #94a3b8); }
.g-count.done { color: #10b981; }
.set-tip { margin: 12px 0 0; font-size: 11.5px; line-height: 1.6; color: var(--text-subtle, #94a3b8); }

/* ── 右侧内容 ── */
.set-content { flex: 1; min-width: 0; }
.set-head { margin-bottom: 14px; }
.set-title { margin: 0; font-size: 17px; }
.set-note { margin: 4px 0 0; font-size: 12px; color: var(--text-subtle, #64748b); }
.flash { animation: set-flash 1.6s ease-out; }
@keyframes set-flash {
  0% { background: var(--accent-soft, #e0ecff); }
  100% { background: transparent; }
}

/* 分组行由各子组件渲染，但行样式是共用的，放这里统一（子组件用 data-setting 定位） */
:deep(.s-row) {
  display: flex; gap: 16px; align-items: flex-start;
  padding: 10px 0; border-bottom: 1px solid var(--border);
}
:deep(.s-row.col) { flex-direction: column; gap: 8px; }
:deep(.s-row:last-child) { border-bottom: none; }
:deep(.s-label) { flex: none; width: 260px; }
:deep(.s-label label) { font-size: 13px; font-weight: 600; }
:deep(.s-hint) { margin: 3px 0 0; font-size: 11.5px; line-height: 1.6; color: var(--text-subtle, #64748b); }
:deep(.s-ctl) { flex: 1; min-width: 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
:deep(.s-ctl.wrap) { flex-direction: column; align-items: stretch; }
:deep(.s-ctl.seg button) {
  font: inherit; font-size: 12.5px; padding: 5px 12px; cursor: pointer;
  border: 1px solid var(--border); background: var(--surface);
  color: var(--text); border-radius: var(--r-sm, 6px);
}
:deep(.s-ctl.seg button.on) { background: var(--accent); border-color: var(--accent); color: #fff; }
:deep(.s-btn) {
  font: inherit; font-size: 12.5px; padding: 5px 12px; cursor: pointer;
  border: 1px solid var(--border); border-radius: var(--r-sm, 6px);
  background: var(--surface); color: var(--text);
}
:deep(.s-btn:hover:not(:disabled)) { border-color: var(--accent); }
:deep(.s-btn:disabled) { opacity: .5; cursor: default; }
:deep(.s-btn.primary) { background: var(--accent); border-color: var(--accent); color: #fff; }
:deep(.s-input) {
  font: inherit; font-size: 12.5px; padding: 5px 9px;
  border: 1px solid var(--border); border-radius: var(--r-sm, 6px);
  background: var(--surface); color: var(--text);
}
:deep(.s-input.wide) { width: 320px; }
:deep(.s-warn) {
  margin: 10px 0; padding: 8px 11px; font-size: 12.5px; border-radius: 8px;
  background: color-mix(in srgb, #f59e0b 14%, transparent);
  border: 1px solid color-mix(in srgb, #f59e0b 40%, transparent);
}
:deep(.mono) { font-family: Consolas, 'Cascadia Mono', monospace; font-size: 12px; }
</style>
