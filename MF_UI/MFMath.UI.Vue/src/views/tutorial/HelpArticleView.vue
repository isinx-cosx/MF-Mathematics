<script setup>
/**
 * HelpArticleView — 单篇教程正文（替代 v1 `MF_Tutorial/help_browser.py` 的右侧正文）
 *
 * v1 的正文是 `_render_html` 拼出来的 HTML：概述 / 操作步骤 / 示例表 / FAQ，
 * 并且在步骤文本上只做 `<br> → " → "`、删 `<b>` 的降级，**其余标签原样泄漏**。
 * 这里结构一样，但把步骤文本按富文本渲染（经 targets.sanitizeTourHtml 清洗，
 * 教程 YAML 是外部可编辑文件，Web 环境下必须过一遍白名单）。
 *
 * 与 v1 的行为差异：
 *   · v1 只把 `last_tutorial` 写在帮助浏览器里，这里同样在打开正文时写（保持一致）；
 *   · v1 的"✓ 标记为已学"是正文底部的一个锚点链接，这里做成按钮，并且能取消；
 *   · **补上"开始这篇的引导"**（v1 硬编码只能引导 quick-start）。
 */
import { computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  getTutorial, isCompleted, markCompleted, markIncomplete, setLastTutorial,
  savedTourStep, initTutorials, storageError,
} from "../../lib/tutorial/store.js";
import { start } from "../../lib/tutorial/tour.js";
import { sanitizeTourHtml, PENDING } from "../../lib/tutorial/targets.js";

initTutorials();
const route = useRoute();
const router = useRouter();

const tutorial = computed(() => getTutorial(String(route.params.id || "")));
const stepHtml = (s) => sanitizeTourHtml(s.text);

onMounted(() => { if (tutorial.value) setLastTutorial(tutorial.value.id); });
watch(tutorial, (t) => { if (t) setLastTutorial(t.id); });

/** 该教程里有多少步的目标界面尚未实现（提前告知，避免用户走到一半才发现） */
const pendingSteps = computed(() => {
  const t = tutorial.value;
  if (!t) return [];
  return t.steps.filter((s) => Object.prototype.hasOwnProperty.call(PENDING, s.target));
});

function tour(resume = false) {
  const t = tutorial.value;
  if (!t) return;
  if (start(t.id, { resume })) router.push("/");
}
function toggleDone() {
  const t = tutorial.value;
  if (!t) return;
  if (isCompleted(t.id)) markIncomplete(t.id);
  else markCompleted(t.id);
}
function loadExample(ex) {
  // 复用示例库的跳转逻辑：这里只把参数带到示例库页（避免两处映射表各写一份）
  router.push({ path: "/examples", query: { q: ex.label } });
}
</script>

<template>
  <div class="view-body">
    <template v-if="tutorial">
      <header class="ha-head">
        <button class="btn btn-ghost" @click="router.push('/tutorial')">← 教程目录</button>
        <div class="ha-actions">
          <button class="btn btn-primary" @click="tour(false)">开始引导</button>
          <button v-if="savedTourStep(tutorial.id) !== null" class="btn" @click="tour(true)">
            继续引导（第 {{ savedTourStep(tutorial.id) + 1 }} 步）
          </button>
          <button class="btn" :class="{ done: isCompleted(tutorial.id) }" @click="toggleDone">
            {{ isCompleted(tutorial.id) ? "✓ 已学（点击取消）" : "标记为已学" }}
          </button>
        </div>
      </header>

      <h1 class="ha-title">{{ tutorial.title }}</h1>
      <p class="ha-meta">
        {{ tutorial.difficultyIcon }} {{ tutorial.difficultyLabel }} ·
        <span v-if="tutorial.duration">⏱ {{ tutorial.duration }} · </span>
        {{ tutorial.categoryIcon }} {{ tutorial.categoryLabel }} ·
        {{ tutorial.steps.length }} 步 / {{ tutorial.examples.length }} 示例
        <span v-if="isCompleted(tutorial.id)"> · ✅ 已完成</span>
      </p>

      <p v-if="storageError" class="ha-warn">进度存储异常：{{ storageError }}</p>

      <p v-if="pendingSteps.length" class="ha-warn soft">
        这篇里有 <b>{{ pendingSteps.length }}</b> 步的目标界面尚未实现（引导时会在该步明确提示并允许跳过，
        不会像旧版那样静默跳过还标成已完成）。
      </p>

      <h3 class="ha-h3">概述</h3>
      <p class="ha-summary">{{ tutorial.summary }}</p>

      <template v-if="tutorial.steps.length">
        <h3 class="ha-h3">操作步骤</h3>
        <ol class="ha-steps">
          <li v-for="s in tutorial.steps" :key="s.index" class="ha-step">
            <span class="ha-step-no">{{ s.index }}</span>
            <div class="ha-step-body">
              <div class="ha-step-text" v-html="stepHtml(s)" />
              <p class="ha-step-target">
                目标：<code>{{ s.target }}</code>
                <span v-if="PENDING[s.target]" class="ha-pending">（{{ PENDING[s.target] }}）</span>
              </p>
            </div>
          </li>
        </ol>
      </template>

      <template v-if="tutorial.examples.length">
        <h3 class="ha-h3">示例任务</h3>
        <table class="ha-table">
          <thead><tr><th>名称</th><th>表达式</th><th>模式</th><th /></tr></thead>
          <tbody>
            <tr v-for="e in tutorial.examples" :key="e.index">
              <td>{{ e.label }}</td>
              <td class="ha-mono">{{ e.expr || "—" }}</td>
              <td>{{ e.mode || "—" }}</td>
              <td><button class="btn btn-ghost" @click="loadExample(e)">去示例库</button></td>
            </tr>
          </tbody>
        </table>
      </template>

      <template v-if="tutorial.faq.length">
        <h3 class="ha-h3">常见问题</h3>
        <details v-for="(f, i) in tutorial.faq" :key="i" class="ha-faq">
          <summary>{{ f.q }}</summary>
          <p>{{ f.a }}</p>
        </details>
      </template>
    </template>

    <div v-else class="ha-missing">
      <p>找不到教程「{{ route.params.id }}」。</p>
      <button class="btn" @click="router.push('/tutorial')">返回教程目录</button>
    </div>
  </div>
</template>

<style scoped>
.ha-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.ha-actions { margin-left: auto; display: flex; gap: 6px; flex-wrap: wrap; }
.ha-actions .btn.done { border-color: #10b981; color: #10b981; }
.ha-title { margin: 6px 0 6px; font-size: 20px; }
.ha-meta { margin: 0 0 12px; font-size: 12px; color: var(--text-subtle, #64748b); }
.ha-warn {
  margin: 0 0 12px; padding: 8px 11px; font-size: 12.5px; border-radius: 8px;
  background: color-mix(in srgb, #f59e0b 14%, transparent);
  border: 1px solid color-mix(in srgb, #f59e0b 40%, transparent);
}
.ha-warn.soft { background: color-mix(in srgb, #64748b 10%, transparent); border-color: var(--border); }
.ha-h3 { margin: 18px 0 8px; font-size: 14px; }
.ha-summary { margin: 0; font-size: 13px; line-height: 1.8; }
.ha-steps { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 10px; }
.ha-step { display: flex; gap: 10px; }
.ha-step-no {
  flex: none; width: 22px; height: 22px; border-radius: 50%;
  display: grid; place-items: center; font-size: 12px;
  background: var(--accent-soft, #e0ecff); color: var(--accent, #2563eb);
}
.ha-step-body { min-width: 0; }
.ha-step-text { font-size: 13px; line-height: 1.75; }
.ha-step-text :deep(b) { font-weight: 600; }
.ha-step-target { margin: 4px 0 0; font-size: 11.5px; color: var(--text-subtle, #94a3b8); }
.ha-pending { color: #b45309; }
.ha-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.ha-table th, .ha-table td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); }
.ha-mono { font-family: 'Cambria Math', Consolas, monospace; }
.ha-faq { margin-bottom: 6px; font-size: 13px; }
.ha-faq summary { cursor: pointer; }
.ha-faq p { margin: 6px 0 10px 16px; line-height: 1.7; color: var(--text-subtle, #475569); }
.ha-missing { font-size: 13px; }
</style>
