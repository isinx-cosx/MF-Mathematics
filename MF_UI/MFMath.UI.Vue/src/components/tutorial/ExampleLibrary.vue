<script setup>
/**
 * ExampleLibrary — 示例任务库（替代 v1 `MF_Tutorial/example_library.py`）
 *
 * 内容来源与 v1 一致：教程的 `examples` 字段，按教程顺序串联（没有独立数据源）。
 *
 * 修掉 v1 两处：
 *   ① v1 用 `tutorial.category` 做筛选（不是示例自身字段），示例只能跟着所属教程
 *      分类出现 —— 这里保留同样的筛选语义（数据本身没有示例级分类），但在界面上
 *      标明"按所属教程分类"，不含糊；
 *   ② v1 点「加载到工作区」时，mode 只映射了 14 个计算子模式里的 4 个，
 *      匹配不到就静默不切换。这里用 lib/workspace/pendingInput.js 的完整映射表，
 *      并且**匹配不到就明说理由**（含"该功能尚未实现"）。
 */
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import { TUTORIALS, CATEGORY_META } from "../../lib/tutorial/store.js";
import { setPending, routeForMode } from "../../lib/workspace/pendingInput.js";

const router = useRouter();

const CATS = [
  { id: "", label: "全部" },
  { id: "calculation", label: "计算" },
  { id: "plot", label: "绘图" },
  { id: "ai", label: "AI" },
  { id: "tools", label: "工具" },
  { id: "settings", label: "设置" },
];
const cat = ref("");
const query = ref("");
const hint = ref("");
let hintTimer = 0;

const items = computed(() => {
  const q = query.value.trim().toLowerCase();
  const out = [];
  for (const t of TUTORIALS) {
    if (cat.value && t.category !== cat.value) continue;
    for (const e of t.examples) {
      if (q && !(`${e.label} ${e.expr} ${e.mode} ${e.description}`.toLowerCase().includes(q))) continue;
      out.push({ ...e, tutorialId: t.id, tutorialTitle: t.title, category: t.category });
    }
  }
  return out;
});

function flash(msg) {
  hint.value = msg;
  clearTimeout(hintTimer);
  hintTimer = setTimeout(() => { hint.value = ""; }, 4200);
}

function load(ex) {
  const info = routeForMode(ex.mode);
  if (!info.ok) {
    flash(`无法加载「${ex.label}」：${info.reason}`);
    return;
  }
  setPending({ expr: ex.expr, operation: ex.operation, label: ex.label, from: "example" });
  router.push(info.route);
}

async function copy(ex) {
  try {
    await navigator.clipboard.writeText(ex.expr || ex.label);
    flash(`已复制：${(ex.expr || ex.label).slice(0, 40)}`);
  } catch {
    flash("复制失败（剪贴板不可用）");
  }
}
</script>

<template>
  <div class="view-body">
    <header class="ex-head">
      <div>
        <h2 class="ex-title">示例任务库</h2>
        <p class="ex-sub">共 {{ items.length }} 个示例 · 点「加载到工作区」会切到对应界面并填入表达式</p>
      </div>
      <input v-model="query" class="ex-search" type="search" placeholder="搜索示例（名称 / 表达式 / 模式）" />
    </header>

    <div class="ex-tabs">
      <button v-for="c in CATS" :key="c.id" class="ex-tab" :class="{ on: cat === c.id }" @click="cat = c.id">
        {{ c.id ? (CATEGORY_META[c.id]?.icon || "") + " " : "" }}{{ c.label }}
      </button>
    </div>

    <p v-if="hint" class="ex-hint">{{ hint }}</p>

    <div v-if="items.length" class="ex-grid">
      <article v-for="ex in items" :key="ex.tutorialId + '-' + ex.index" class="ex-card">
        <h3 class="ex-label">{{ ex.label }}</h3>
        <p v-if="ex.expr" class="ex-expr">{{ ex.expr }}</p>
        <p class="ex-meta">
          <span v-if="ex.mode">模式：{{ ex.mode }}</span>
          <span v-if="ex.operation"> · 操作：{{ ex.operation }}</span>
        </p>
        <p v-if="ex.description" class="ex-desc">{{ ex.description }}</p>
        <p class="ex-from">来自：{{ ex.tutorialTitle }}</p>
        <div class="ex-actions">
          <button class="btn btn-primary" @click="load(ex)">加载到工作区 →</button>
          <button class="btn btn-ghost" @click="copy(ex)">复制</button>
        </div>
      </article>
    </div>
    <p v-else class="ex-empty">这个条件下没有示例任务。</p>
  </div>
</template>

<style scoped>
.ex-head { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 10px; }
.ex-title { margin: 0; font-size: 17px; }
.ex-sub { margin: 4px 0 0; font-size: 12px; color: var(--text-subtle, #64748b); }
.ex-search {
  margin-left: auto; font: inherit; font-size: 12px; padding: 5px 10px; width: 240px;
  border: 1px solid var(--border); border-radius: var(--r-sm, 6px);
  background: var(--surface); color: var(--text);
}
.ex-tabs { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
.ex-tab {
  font: inherit; font-size: 12px; padding: 4px 11px; cursor: pointer;
  border: 1px solid var(--border); border-radius: 999px;
  background: var(--surface); color: var(--text-subtle, #475569);
}
.ex-tab.on { background: var(--accent); border-color: var(--accent); color: #fff; }
.ex-hint {
  margin: 0 0 12px; padding: 8px 11px; font-size: 12.5px; border-radius: 8px;
  background: color-mix(in srgb, #ef4444 12%, transparent);
  border: 1px solid color-mix(in srgb, #ef4444 40%, transparent);
}
.ex-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.ex-card {
  padding: 12px 14px; border: 1px solid var(--border); border-radius: var(--r-md, 10px);
  background: var(--surface);
}
.ex-card:hover { border-color: var(--accent); }
.ex-label { margin: 0 0 6px; font-size: 13.5px; }
.ex-expr {
  margin: 0 0 6px; font-family: 'Cambria Math', 'Latin Modern Math', Consolas, monospace;
  font-size: 14px; color: var(--accent, #6366f1); word-break: break-all;
}
.ex-meta { margin: 0; font-size: 12px; color: var(--text-subtle, #64748b); }
.ex-desc { margin: 6px 0 0; font-size: 12.5px; line-height: 1.6; }
.ex-from { margin: 8px 0 0; font-size: 11.5px; color: var(--text-subtle, #94a3b8); }
.ex-actions { display: flex; gap: 6px; margin-top: 10px; }
.ex-empty { font-size: 13px; color: var(--text-subtle, #94a3b8); }
</style>
