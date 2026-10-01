<script setup>
/**
 * TutorialCatalogView — 教程目录（替代 v1 帮助浏览器左侧的树 + 筛选）
 *
 * 能力对齐 v1 的 help_browser：
 *   · 分类分组、难度标签（v1 算了 diff_tag 但没拼进标签，这里显示出来）
 *   · 进度 "已学 x/y · %"
 *   · 点击进入正文
 * 并补上 v1 没有的：
 *   · **从任意一篇启动引导**（v1 的 _open_guided_walkthrough 硬编码 start("quick-start")，
 *     帮助文档与示例库里没有任何"开始这篇教程的引导"入口）
 *   · 继续上次未走完的引导
 *   · 进度写入失败时明确提示（v1 写失败只 logger.debug，用户丢进度无感）
 */
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import {
  TUTORIALS, CATEGORY_META, isCompleted, isStale, progress,
  savedTourStep, storageError, resetAllProgress, initTutorials,
} from "../../lib/tutorial/store.js";
import { start } from "../../lib/tutorial/tour.js";

initTutorials();
const router = useRouter();

const cat = ref("");
const diff = ref("");
const confirmingReset = ref(false);

const CATS = computed(() => {
  const ids = [...new Set(TUTORIALS.map((t) => t.category))];
  return [{ id: "", label: "全部分类" }, ...ids.map((id) => ({ id, label: `${CATEGORY_META[id]?.icon || ""} ${CATEGORY_META[id]?.label || id}` }))];
});
const DIFFS = [
  { id: "", label: "全部难度" },
  { id: "beginner", label: "🔵 入门" },
  { id: "intermediate", label: "🟡 进阶" },
  { id: "advanced", label: "🟣 高级" },
];

const list = computed(() =>
  TUTORIALS.filter((t) => (!cat.value || t.category === cat.value) && (!diff.value || t.difficulty === diff.value))
);

function open(t) { router.push(`/tutorial/${t.id}`); }
function tour(t) { const ok = start(t.id); if (ok) router.push("/"); }
function resumeTour(t) { const ok = start(t.id, { resume: true }); if (ok) router.push("/"); }
function reset() {
  resetAllProgress();
  confirmingReset.value = false;
}
</script>

<template>
  <div class="view-body" data-tour="tutorial.catalog">
    <header class="tc-head">
      <div>
        <h2 class="tc-title">使用教程</h2>
        <p class="tc-sub">
          共 {{ TUTORIALS.length }} 篇 · 已学 {{ progress.done }}/{{ progress.total }} · {{ progress.percent }}%
          <span v-if="progress.done" class="tc-bar"><i :style="{ width: progress.percent + '%' }" /></span>
        </p>
      </div>
      <div class="tc-filters">
        <select v-model="cat" class="tc-select">
          <option v-for="c in CATS" :key="c.id" :value="c.id">{{ c.label }}</option>
        </select>
        <select v-model="diff" class="tc-select">
          <option v-for="d in DIFFS" :key="d.id" :value="d.id">{{ d.label }}</option>
        </select>
        <button v-if="!confirmingReset" class="btn btn-ghost" title="清空所有已学标记与引导进度" @click="confirmingReset = true">重置进度</button>
        <span v-else class="tc-confirm">
          确定重置？<button class="btn btn-ghost" @click="reset">确定</button>
          <button class="btn btn-ghost" @click="confirmingReset = false">取消</button>
        </span>
      </div>
    </header>

    <p v-if="storageError" class="tc-warn">进度存储异常：{{ storageError }}</p>

    <div class="tc-grid">
      <article v-for="t in list" :key="t.id" class="tc-card" :class="{ done: isCompleted(t.id) }">
        <div class="tc-card-head">
          <span class="tc-icon">{{ t.categoryIcon }}</span>
          <h3 class="tc-name">{{ t.title }}</h3>
          <span v-if="isCompleted(t.id)" class="tc-done" title="已学完">✅</span>
        </div>
        <p class="tc-meta">
          <span>{{ t.difficultyIcon }} {{ t.difficultyLabel }}</span>
          <span v-if="t.duration"> · ⏱ {{ t.duration }}</span>
          <span> · {{ t.steps.length }} 步 / {{ t.examples.length }} 示例</span>
          <span v-if="t.faq.length"> · {{ t.faq.length }} 问答</span>
        </p>
        <p class="tc-summary">{{ t.summary }}</p>
        <p v-if="isStale(t.id)" class="tc-stale">教程内容已更新，先前的"已学"标记已失效（步骤/示例有改动）</p>
        <div class="tc-actions">
          <button class="btn btn-primary" @click="tour(t)">开始引导</button>
          <button v-if="savedTourStep(t.id) !== null" class="btn" @click="resumeTour(t)">
            继续引导（第 {{ savedTourStep(t.id) + 1 }} 步）
          </button>
          <button class="btn btn-ghost" @click="open(t)">阅读</button>
        </div>
      </article>
    </div>

    <p v-if="!list.length" class="tc-empty">这个条件下没有教程。</p>
  </div>
</template>

<style scoped>
.tc-head { display: flex; align-items: flex-start; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.tc-title { margin: 0; font-size: 17px; }
.tc-sub { margin: 4px 0 0; font-size: 12px; color: var(--text-subtle, #64748b); display: flex; align-items: center; gap: 8px; }
.tc-bar { display: inline-block; width: 120px; height: 4px; border-radius: 2px; background: var(--surface-alt); overflow: hidden; }
.tc-bar i { display: block; height: 100%; background: var(--accent, #3b82f6); }
.tc-filters { margin-left: auto; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.tc-select {
  font: inherit; font-size: 12px; padding: 4px 8px;
  border: 1px solid var(--border); border-radius: var(--r-sm, 6px);
  background: var(--surface); color: var(--text);
}
.tc-confirm { font-size: 12px; display: flex; align-items: center; gap: 4px; }
.tc-warn {
  margin: 0 0 12px; padding: 8px 11px; font-size: 12.5px; border-radius: 8px;
  background: color-mix(in srgb, #ef4444 12%, transparent);
  border: 1px solid color-mix(in srgb, #ef4444 40%, transparent);
}
.tc-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.tc-card {
  padding: 12px 14px; border: 1px solid var(--border); border-radius: var(--r-md, 10px);
  background: var(--surface);
}
.tc-card.done { border-color: color-mix(in srgb, #10b981 45%, var(--border)); }
.tc-card-head { display: flex; align-items: center; gap: 7px; }
.tc-icon { font-size: 15px; }
.tc-name { margin: 0; font-size: 13.5px; }
.tc-done { margin-left: auto; }
.tc-meta { margin: 6px 0 0; font-size: 11.5px; color: var(--text-subtle, #64748b); }
.tc-summary { margin: 7px 0 0; font-size: 12.5px; line-height: 1.65; }
.tc-stale { margin: 7px 0 0; font-size: 11.5px; color: #b45309; }
.tc-actions { display: flex; gap: 6px; margin-top: 11px; flex-wrap: wrap; }
.tc-empty { font-size: 13px; color: var(--text-subtle, #94a3b8); }
</style>
