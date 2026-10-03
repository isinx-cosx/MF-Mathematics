<script setup>
/**
 * StepViewer.vue — 分步显示的**渲染层**
 *
 * 它渲染的不是"模型写的步骤"，而是**这一轮里 AI 调引擎的记录**：
 *   第 N 步 · 中文动作名（来自引擎动作表）· 引擎函数 · 传入参数 · **引擎返回的完整值** · 耗时
 *
 * 为什么这样才是"分步显示"：本项目有硬约束"计算由 C++ 引擎完成"。所以每一步的数值必须是
 * 引擎算出来的事实，而不是模型的措辞。工具调用（`engine_call`）正好提供了这个事实来源；
 * 这里做的只是把它**按步骤排好给人看**。
 *
 * 两条显示纪律：
 *   ① 引擎返回值**完整显示**（工具块里给模型的是截断版，这里给人看的是完整的）；
 *   ② 失败的一步标红并保留 —— 不隐藏、不假装成功（宁可看到"这步没算出来"）。
 */
import { computed } from "vue";
import AiMarkdown from "./AiMarkdown.vue";

const props = defineProps({
  steps: { type: Array, default: () => [] },
  /** 这条回答的正文（模型措辞），放在步骤前后作为叙述 */
  prose: { type: String, default: "" },
  title: { type: String, default: "分步显示" },
});
const emit = defineEmits(["close"]);

const list = computed(() => props.steps || []);
const okCount = computed(() => list.value.filter((s) => s.ok).length);
const failCount = computed(() => list.value.length - okCount.value);

/** 参数显示：空对象显示成（无参数），其余紧凑 JSON */
function argsText(args) {
  if (!args || Object.keys(args).length === 0) return "（无参数）";
  try { return JSON.stringify(args); } catch { return String(args); }
}

/** 引擎返回值：完整、不截断（summary 里是 `fn(args) → value`，这里只取 value 部分） */
function valueText(s) {
  const s2 = String(s?.summary ?? "");
  const idx = s2.indexOf("→");
  return idx >= 0 ? s2.slice(idx + 1).trim() : s2;
}
</script>

<template>
  <div class="dialog-overlay" @click.self="emit('close')">
    <div class="dialog sv-dialog" data-steps="view" role="dialog" aria-label="分步显示">
      <div class="dialog-header">
        <span>{{ title }}<span v-if="list.length" class="sv-count"> · {{ list.length }} 步（成功 {{ okCount }}<span v-if="failCount"> · 失败 {{ failCount }}</span>）</span></span>
        <button class="dialog-close" data-steps="close" @click="emit('close')">✕</button>
      </div>

      <!-- 教程引导的目标：这一步的"内容区"（v1 的 step_viewer.content） -->
      <div class="dialog-body sv-body" data-tour="step_viewer.content">
        <p v-if="!list.length" class="sv-empty" data-steps="empty">
          这条回答里没有引擎步骤。让 AI 计算时（它只能通过 engine_call 拿数值）这里就会逐条列出来。
        </p>

        <template v-else>
          <p class="sv-lead" data-steps="lead">
            每一步都是**引擎算出来的**：模型提出要算什么，数值由本地 C++ 引擎给出。
            失败的步骤标红保留，不隐藏。
          </p>

          <ol class="sv-list">
            <li v-for="(s, i) in list" :key="i" class="sv-step" :class="{ bad: !s.ok }"
                :data-steps="'step-' + i">
              <div class="sv-head">
                <span class="sv-no">{{ i + 1 }}</span>
                <span class="sv-name">{{ s.summary && s.summary.includes("→") ? "" : "" }}</span>
                <code class="sv-fn" :data-steps="'fn-' + i">{{ s.fn || s.name }}</code>
                <span class="sv-ms">{{ s.ms }} ms</span>
                <span class="sv-state" :class="{ bad: !s.ok }">{{ s.ok ? "引擎已算出" : "失败" }}</span>
              </div>
              <div class="sv-args">参数：<code :data-steps="'args-' + i">{{ argsText(s.args) }}</code></div>
              <div class="sv-value">
                结果：<code :data-steps="'value-' + i">{{ valueText(s) }}</code>
              </div>
            </li>
          </ol>

          <section v-if="prose" class="sv-prose">
            <h4>AI 的说明</h4>
            <AiMarkdown :text="prose" />
          </section>
        </template>
      </div>

      <div class="dialog-footer">
        <button class="btn btn-primary" data-steps="ok" @click="emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sv-dialog { width: min(720px, 94vw); }
.sv-count { color: var(--muted); font-size: 12px; }
.sv-body { display: flex; flex-direction: column; gap: 10px; }
.sv-empty { margin: 0; font-size: 13px; color: var(--muted); line-height: 1.7; }
.sv-lead { margin: 0; font-size: 12px; color: var(--muted); line-height: 1.7; }
.sv-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.sv-step {
  border: 1px solid var(--border); border-left: 3px solid var(--accent, #5a82f0);
  border-radius: 8px; padding: 8px 10px;
}
.sv-step.bad { border-left-color: var(--danger, #d05a5a); }
.sv-head { display: flex; align-items: baseline; gap: 8px; }
.sv-no {
  width: 20px; height: 20px; flex: none; border-radius: 50%;
  background: var(--accent, #5a82f0); color: #fff; font-size: 11.5px;
  display: inline-flex; align-items: center; justify-content: center;
}
.sv-step.bad .sv-no { background: var(--danger, #d05a5a); }
.sv-fn { font-family: ui-monospace, Consolas, monospace; font-size: 12.5px; }
.sv-ms { font-size: 11px; color: var(--muted); }
.sv-state { margin-left: auto; font-size: 11px; color: var(--accent, #5a82f0); }
.sv-state.bad { color: var(--danger, #d05a5a); }
.sv-args, .sv-value { margin-top: 5px; font-size: 12px; color: var(--muted); }
.sv-args code, .sv-value code {
  font-family: ui-monospace, Consolas, monospace; font-size: 12px; color: var(--text);
  white-space: pre-wrap; word-break: break-word;
}
.sv-value code { color: var(--text); }
.sv-prose { border-top: 1px solid var(--border); padding-top: 10px; }
.sv-prose h4 { margin: 0 0 6px; font-size: 12px; color: var(--muted); font-weight: 600; }
</style>
