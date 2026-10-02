<script setup>
/**
 * AiPanel.vue — AI 助手面板（右侧抽屉，**非模态**）
 *
 * 为什么是抽屉而不是对话框：
 *   · 用户经常要一边看结果一边问 AI，模态窗会把界面挡住（而且本项目一贯要求不弹窗）；
 *   · 抽屉只占右侧一条，主界面仍可操作、可复制、可切页面。
 *
 * 渲染纪律（模型输出是不可信输入）：
 *   · 正文**绝不用 v-html**，也不拼 HTML 字符串；纯文本走插值，
 *     公式片段交给 MathLatex（KaTeX 在它内部安全渲染）；
 *   · 公式识别只做 $...$ / $$...$$ 的切分，识别不了就整段当纯文本显示。
 */
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import MathLatex from "../math/MathLatex.vue";
import {
  aiConfig, aiState, aiMessages, aiTestState, aiHosted,
  initAi, refreshAiConfig, aiTest, clearChat, contextBudget,
  currentContext, estimateMessagesTokens, splitMath,
  buildMessages, sendTurn, stopTurn,
} from "../../lib/ai/bridge.js";

const props = defineProps({ open: { type: Boolean, default: false } });
const emit = defineEmits(["close"]);

const route = useRoute();
const router = useRouter();

const draft = ref("");
const scroller = ref(null);
/** 用户往上翻的时候不要把他拽回底部 */
const pinned = ref(true);

onMounted(() => {
  initAi();
  refreshAiConfig();
});

watch(() => props.open, (v) => { if (v) { refreshAiConfig(); scrollToEnd(); } });

/* ── 公式切分：实现放在 bridge.js（唯一一份，且可离线断言）────────────── */
const asstSegments = computed(() => splitMath(aiState.value.stream));
const msgSegments = (m) => splitMath(m.content);

/* ── 发送 ─────────────────────────────────────────────────────────── */
function send() {
  const text = draft.value.trim();
  if (!text) return;
  draft.value = "";
  const r = sendTurn(text, { route: route.path });
  if (!r.ok) return;   // 错误已经进 aiState.error，由界面显示
  scrollToEnd();
}

function onKeydown(e) {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
}

function stop() { stopTurn(); }

/* ── 滚动 ─────────────────────────────────────────────────────────── */
function onScroll() {
  const el = scroller.value;
  if (!el) return;
  pinned.value = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
}
async function scrollToEnd() {
  if (!pinned.value) return;
  await nextTick();
  const el = scroller.value;
  if (el) el.scrollTop = el.scrollHeight;
}
watch(() => [aiState.value.stream.length, aiMessages.value.length, aiState.value.reasoning.length], scrollToEnd);

/* ── 上下文与预算 ─────────────────────────────────────────────────── */
const ctx = computed(() => currentContext(route.path));

/** 这一轮**实际会发**的内容（与 buildMessages 用同一份逻辑算，不另算一遍） */
const outgoing = computed(() => {
  const msgs = buildMessages({ userText: draft.value || "（待输入）", history: aiMessages.value, context: ctx.value, cfg: aiConfig.value });
  const tokens = estimateMessagesTokens(msgs);
  const budget = contextBudget(aiConfig.value);
  return {
    messages: msgs,
    tokens,
    budget,
    over: tokens > budget.budget,
    parts: [
      { label: "问题文本", on: true, always: true },
      { label: "当前表达式", on: aiConfig.value.sendExpr, has: !!ctx.value.expr },
      { label: "引擎结果", on: aiConfig.value.sendResult, has: !!ctx.value.result },
      { label: "控制台代码", on: aiConfig.value.sendCode, has: !!ctx.value.code },
      { label: "会话历史", on: aiConfig.value.sendHistory, has: aiMessages.value.length > 0 },
    ],
  };
});

const statusText = computed(() => {
  if (!aiHosted.value) return "浏览器预览：AI 只在 MFMath.exe 里可用";
  if (!aiConfig.value.enabled) return "AI 未启用";
  if (!aiConfig.value.hasKey) return "还没有 API Key";
  if (aiState.value.running) return "正在输出…";
  return aiConfig.value.model;
});

const testLine = computed(() => {
  const t = aiTestState.value;
  if (t.testing) return "正在测连接…";
  if (!t.result) return "";
  return t.result.ok
    ? `连接正常（HTTP ${t.result.status}，${t.result.ms} ms）`
    : `连接失败：${t.result.detail || "未知原因"}`;
});

function openSettings() {
  emit("close");
  router.push("/settings?group=ai");
}
</script>

<template>
  <aside v-if="open" class="ai-panel" data-ai="panel" role="dialog" aria-label="AI 助手">
    <header class="ai-head">
      <span class="ai-title">AI 助手</span>
      <span class="ai-status" :class="{ warn: !aiConfig.enabled || !aiConfig.hasKey }" data-ai="status">{{ statusText }}</span>
      <button class="ai-x" data-ai="close" title="关闭" @click="emit('close')">✕</button>
    </header>

    <!-- 未就绪时把"为什么不能用"和"去哪里开"直接说出来，而不是给一个点不动的输入框 -->
    <div v-if="!aiHosted || !aiConfig.enabled || !aiConfig.hasKey" class="ai-blocked" data-ai="blocked">
      <p v-if="!aiHosted">浏览器预览里没有宿主桥。AI 的传输与密钥都在 MFMath.exe 里，所以这里不能用。</p>
      <p v-else-if="!aiConfig.enabled">AI 现在是关的。打开它并填一个 API Key 就能用。</p>
      <p v-else>还没有 API Key。密钥只存在宿主（DPAPI 加密），页面拿不到它。</p>
      <button class="btn btn-primary" data-ai="settings-link" @click="openSettings">去设置 → AI</button>
    </div>

    <div ref="scroller" class="ai-body" data-ai="msgs" @scroll="onScroll">
      <p v-if="!aiMessages.length && !aiState.stream" class="ai-empty">
        问点什么吧。计算仍然由 C++ 引擎完成 —— 我负责解释与思路。
      </p>

      <template v-for="(m, i) in aiMessages" :key="i">
        <div v-if="m.role === 'user'" class="ai-user">{{ m.content }}</div>
        <div v-else class="ai-asst" :data-ai="'msg-' + i">
          <!-- 思考过程跟着**这条消息**走（不是挂在面板底部）：它是这条回答的一部分，
               而且这样收尾时把它从实时缓冲搬进来，就不会出现"回答显示两次" -->
          <details v-if="m.reasoning" class="ai-reason" :data-ai="'reason-' + i">
            <summary>思考过程（{{ m.reasoning.length }} 字）</summary>
            <div class="ai-reason-body">{{ m.reasoning }}</div>
          </details>
          <template v-for="(s, j) in msgSegments(m)" :key="j">
            <MathLatex v-if="s.kind === 'math'" :latex="s.value" :display="s.display" :fallback="s.value" />
            <span v-else class="ai-text">{{ s.value }}</span>
          </template>
        </div>
      </template>

      <!-- 正在输出的这一轮：只在 running 时显示。
           收尾时内容会被并入上面的消息，这里随即消失 —— 不会和消息重复。 -->
      <details v-if="aiState.running && aiState.reasoning" class="ai-reason" data-ai="reasoning">
        <summary>思考过程（{{ aiState.reasoning.length }} 字）</summary>
        <div class="ai-reason-body">{{ aiState.reasoning }}</div>
      </details>

      <div v-if="aiState.running && aiState.stream" class="ai-asst ai-streaming" data-ai="stream">
        <template v-for="(s, j) in asstSegments" :key="j">
          <MathLatex v-if="s.kind === 'math'" :latex="s.value" :display="s.display" :fallback="s.value" />
          <span v-else class="ai-text">{{ s.value }}</span>
        </template>
        <span class="ai-caret">▌</span>
      </div>

      <p v-if="aiState.running && !aiState.stream && !aiState.reasoning" class="ai-waiting">正在连接模型…</p>

      <div v-if="aiState.notices.length" class="ai-notices" data-ai="notices">
        <p v-for="(n, i) in aiState.notices" :key="i">{{ n.message }}</p>
      </div>

      <div v-if="aiState.error" class="ai-error" data-ai="error">
        <p>{{ aiState.error.message }}</p>
        <p class="ai-error-kind">类别：{{ aiState.error.kind }}<span v-if="aiState.error.status"> · HTTP {{ aiState.error.status }}</span></p>
      </div>

      <p v-if="aiState.usage" class="ai-usage" data-ai="usage">
        本轮 token：输入 {{ aiState.usage.inputTokens }} / 输出 {{ aiState.usage.outputTokens }}
        <span v-if="aiState.doneReason && aiState.doneReason !== 'stop'"> · 结束原因：{{ aiState.doneReason }}</span>
      </p>
    </div>

    <div class="ai-compose">
      <textarea v-model="draft" data-ai="input" class="ai-input" rows="2"
                placeholder="Enter 发送，Shift+Enter 换行"
                @keydown="onKeydown" />
      <div class="ai-actions">
        <span class="ai-out" data-ai="outgoing" :class="{ over: outgoing.over }">
          将发送约 {{ outgoing.tokens }} token
          <span class="ai-out-parts">
            <template v-for="(p, i) in outgoing.parts" :key="i">
              <span v-if="p.always || p.has" :class="{ off: !p.on }">{{ p.label }}{{ p.on ? "" : "(关)" }}</span>
            </template>
          </span>
        </span>
        <button v-if="!aiState.running" class="btn btn-primary" data-ai="send"
                :disabled="!aiHosted || !aiConfig.enabled || !aiConfig.hasKey" @click="send">发送</button>
        <button v-else class="btn" data-ai="stop" @click="stop">停止</button>
        <button class="btn btn-ghost" data-ai="clear" title="清空这段对话" @click="clearChat">清空</button>
      </div>
      <div class="ai-foot">
        <button class="ai-link" data-ai="test" @click="aiTest">测试连接</button>
        <span v-if="testLine" class="ai-test-line" :data-ai="'test-' + (aiTestState.result?.ok ? 'ok' : 'fail')">{{ testLine }}</span>
        <span class="ai-spacer" />
        <span class="ai-window" :title="outgoing.budget.source">
          窗口 {{ outgoing.budget.window }} · {{ outgoing.budget.source.slice(0, 6) }}
        </span>
      </div>
    </div>
  </aside>
</template>

<style scoped>
/* 非模态抽屉：只占右侧一条，主界面照旧可点。
   pointer-events 只在自己身上，绝不放一个全屏遮罩（那会变成模态）。 */
.ai-panel {
  position: fixed;
  top: 0; right: 0; bottom: 0;
  width: 420px;
  max-width: 92vw;
  display: flex;
  flex-direction: column;
  background: var(--panel, var(--bg));
  border-left: 1px solid var(--border);
  box-shadow: -12px 0 32px rgba(0, 0, 0, .18);
  z-index: 60;
}
.ai-head {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
}
.ai-title { font-weight: 600; }
.ai-status { color: var(--muted); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ai-status.warn { color: var(--warn, #c77); }
.ai-x { margin-left: auto; background: none; border: 0; color: var(--muted); cursor: pointer; font-size: 14px; }

.ai-blocked { padding: 12px; display: flex; flex-direction: column; gap: 8px; border-bottom: 1px solid var(--border); }
.ai-blocked p { margin: 0; color: var(--muted); font-size: 12.5px; line-height: 1.6; }

.ai-body { flex: 1; overflow: auto; padding: 12px; display: flex; flex-direction: column; gap: 10px; }
.ai-empty { color: var(--muted); font-size: 12.5px; }
.ai-user {
  align-self: flex-end; max-width: 88%;
  background: var(--accent-soft, rgba(90, 130, 240, .14));
  border-radius: 10px; padding: 8px 10px; white-space: pre-wrap; word-break: break-word;
}
.ai-asst { font-size: 13.5px; line-height: 1.7; white-space: pre-wrap; word-break: break-word; }
.ai-text { white-space: pre-wrap; }
.ai-caret { animation: ai-blink 1s step-start infinite; }
@keyframes ai-blink { 50% { opacity: 0; } }
.ai-waiting { color: var(--muted); font-size: 12.5px; }
.ai-reason { font-size: 12.5px; color: var(--muted); border-left: 2px solid var(--border); padding-left: 8px; }
.ai-reason-body { white-space: pre-wrap; margin-top: 6px; }
.ai-notices { font-size: 12px; color: var(--muted); }
.ai-notices p { margin: 2px 0; }
.ai-error {
  font-size: 12.5px; color: var(--danger, #d05a5a);
  border: 1px solid var(--danger, #d05a5a); border-radius: 8px; padding: 8px;
}
.ai-error p { margin: 0; }
.ai-error-kind { color: var(--muted); margin-top: 4px !important; }
.ai-usage { font-size: 11.5px; color: var(--muted); margin: 0; }

.ai-compose { border-top: 1px solid var(--border); padding: 10px 12px 8px; display: flex; flex-direction: column; gap: 6px; }
.ai-input {
  width: 100%; resize: vertical; min-height: 44px;
  background: var(--bg); color: var(--text);
  border: 1px solid var(--border); border-radius: 8px; padding: 8px;
  font: inherit; font-size: 13px;
}
.ai-actions { display: flex; align-items: center; gap: 8px; }
.ai-out { font-size: 11.5px; color: var(--muted); display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.ai-out.over { color: var(--warn, #c77); }
.ai-out-parts { display: inline-flex; gap: 4px; }
.ai-out-parts span { border: 1px solid var(--border); border-radius: 4px; padding: 0 4px; }
.ai-out-parts span.off { opacity: .45; text-decoration: line-through; }
.ai-actions .btn { margin-left: auto; }
.ai-foot { display: flex; align-items: center; gap: 8px; font-size: 11.5px; color: var(--muted); }
.ai-link { background: none; border: 0; color: var(--accent, #5a82f0); cursor: pointer; padding: 0; font-size: 11.5px; }
.ai-spacer { flex: 1; }
.ai-window { cursor: help; }
</style>
