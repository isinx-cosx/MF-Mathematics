<script setup>
/**
 * AiGroup.vue — 设置 → AI
 *
 * 相比于 v1 的 12 项（provider / modelMap / localModel / cache …），这里收敛成 10 项，
 * 每一项都**真的接上了读写**：
 *   · provider 不做注册表：它就是几个预设按钮（点一下把 baseUrl + model 填好），
 *     因为 DeepSeek / OpenAI / Ollama / vLLM 共用同一份 chat completions 形状；
 *   · modelMap（"Sonnet" → 实际模型名）是 v1 的内部间接层，用户不需要知道，去掉；
 *   · localModel 由 provider=Ollama 预设覆盖（baseUrl 指 127.0.0.1:11434/v1）；
 *   · cache 改成"会话记录"（条数 + 清空），因为对话缓存反而会让回答过期。
 *
 * 密钥的那一栏把两件事分开说：「我的 key 在不在」和「它是不是明文躺在磁盘上」——
 * 只给一个打码字符串，用户没法判断自己该不该去改。打码值原样回传表示"没改密钥"。
 */
import { computed, onMounted, ref } from "vue";
import {
  aiConfig, aiTestState, aiHosted, aiMessages,
  refreshAiConfig, aiConfigure, aiSetKey, aiClearKey, aiSelfCheck, aiTest, clearChat,
} from "../../lib/ai/bridge.js";

const keyDraft = ref("");
const keyMsg = ref("");
const selfCheck = ref(null);
const saved = ref("");

function flash(msg) {
  saved.value = msg;
  setTimeout(() => { if (saved.value === msg) saved.value = ""; }, 2500);
}

function set(patch, label) {
  const r = aiConfigure(patch);
  if (r && r.ok) flash(label + " 已保存");
  else flash((r && r.error) || "保存失败");
}

onMounted(() => {
  refreshAiConfig();
  selfCheck.value = aiSelfCheck();
});

const cfg = aiConfig;

/** 引擎函数总数（工具能调多少个）—— 从工具层读，避免这里再写死一个数字 */
const toolCount = (() => {
  try { return window.__mfAi?.tools?.count?.() ?? 0; } catch { return 0; }
})();
const keyState = computed(() => {
  if (!cfg.value.hasKey) return "未配置";
  return cfg.value.keySource === "memory"
    ? "已配置（仅本次运行的内存里，未落盘）"
    : "已配置（DPAPI 密文落盘）";
});

const PRESETS = [
  { name: "DeepSeek", baseUrl: "https://api.deepseek.com/v1", model: "deepseek-chat" },
  { name: "OpenAI", baseUrl: "https://api.openai.com/v1", model: "gpt-4o-mini" },
  { name: "Ollama（本地）", baseUrl: "http://127.0.0.1:11434/v1", model: "qwen2.5:7b" },
];

function applyPreset(p) {
  aiConfigure({ baseUrl: p.baseUrl, model: p.model });
  flash("已填入 " + p.name + " 的端点与模型（密钥仍需自己填）");
}

function saveKey() {
  const k = keyDraft.value.trim();
  if (!k) { keyMsg.value = "先粘贴一个密钥"; return; }
  const r = aiSetKey(k);
  keyDraft.value = "";
  if (r && r.ok) keyMsg.value = r.warning || "密钥已保存";
  else keyMsg.value = (r && r.error) || "保存失败";
}

function dropKey() {
  const r = aiClearKey();
  keyMsg.value = r && r.ok ? "密钥已清除" : (r && r.error) || "清除失败";
}

const testLine = computed(() => {
  const t = aiTestState.value;
  if (t.testing) return "正在测连接…";
  if (!t.result) return "";
  return t.result.ok
    ? `连接正常：HTTP ${t.result.status}，${t.result.ms} ms，${t.result.detail || ""}`
    : `连接失败：HTTP ${t.result.status || "-"}，${t.result.detail || "未知原因"}`;
});
</script>

<template>
  <div class="ag">
    <p v-if="!aiHosted" class="ag-warn" data-setting="ai.enabled">
      浏览器预览里没有宿主桥：AI 的传输与密钥都在 MFMath.exe 中，这里只能看不能改。
    </p>

    <!-- ① 启用 -->
    <section class="row" data-setting="ai.enabled">
      <div class="lab">
        <span>启用 AI</span>
        <small>关掉之后顶栏的 AI 面板仍可打开，但会告诉你为什么不能用</small>
      </div>
      <div class="ctl">
        <label class="sw">
          <input type="checkbox" data-ai-set="enabled" :checked="cfg.enabled"
                 @change="set({ enabled: $event.target.checked }, '启用状态')" />
          <span>{{ cfg.enabled ? "已启用" : "已关闭" }}</span>
        </label>
      </div>
    </section>

    <!-- ② 端点（provider 就是预设按钮） -->
    <section class="row" data-setting="ai.baseUrl">
      <div class="lab">
        <span>API Base</span>
        <small>任何 OpenAI 兼容端点都行：DeepSeek / OpenAI / Ollama / vLLM</small>
      </div>
      <div class="ctl col">
        <div class="presets">
          <button v-for="p in PRESETS" :key="p.name" class="chip" :data-ai-preset="p.name"
                  @click="applyPreset(p)">{{ p.name }}</button>
        </div>
        <input class="inp mono" data-ai-set="baseUrl" :value="cfg.baseUrl"
               @change="set({ baseUrl: $event.target.value }, '端点')" />
      </div>
    </section>

    <!-- ③ 模型 -->
    <section class="row" data-setting="ai.model">
      <div class="lab">
        <span>默认模型</span>
        <small>写模型名即可（如 deepseek-chat / deepseek-reasoner）</small>
      </div>
      <div class="ctl">
        <input class="inp mono" data-ai-set="model" :value="cfg.model"
               @change="set({ model: $event.target.value }, '模型')" />
      </div>
    </section>

    <!-- ④ 模型参数 -->
    <section class="row" data-setting="ai.modelParams">
      <div class="lab">
        <span>模型参数</span>
        <small>温度越低越保守；最大输出长度决定单次回复上限</small>
      </div>
      <div class="ctl col">
        <label class="inline">
          温度
          <input class="inp num" type="number" step="0.1" min="0" max="2" data-ai-set="temperature"
                 :value="cfg.temperature" @change="set({ temperature: Number($event.target.value) }, '温度')" />
        </label>
        <label class="inline">
          最大输出
          <input class="inp num" type="number" min="1" max="32000" step="64" data-ai-set="maxTokens"
                 :value="cfg.maxTokens" @change="set({ maxTokens: Number($event.target.value) }, '最大输出')" />
          token
        </label>
        <label class="sw">
          <input type="checkbox" data-ai-set="includeUsage" :checked="cfg.includeUsage"
                 @change="set({ includeUsage: $event.target.checked }, 'usage 尾包')" />
          <span>请求 usage 尾包（有的兼容网关会拒绝这个字段，那就关掉）</span>
        </label>
        <label class="inline">
          整轮超时
          <input class="inp num" type="number" min="5" max="900" step="5" data-ai-set="timeoutSec"
                 :value="cfg.timeoutSec" @change="set({ timeoutSec: Number($event.target.value) }, '超时')" />
          秒
        </label>
      </div>
    </section>

    <!-- ⑤ 密钥：只说"在不在"和"是不是明文"，不问内容 -->
    <section class="row" data-setting="ai.apiKey">
      <div class="lab">
        <span>API Key</span>
        <small>只写不读：密钥存在宿主侧，页面拿不到它（这就是它不落 localStorage 的原因）</small>
      </div>
      <div class="ctl col">
        <p class="state" data-ai="key-state">
          {{ keyState }}
          <span v-if="!cfg.dpapiAvailable" class="warn">· 本机 DPAPI 不可用，密钥只留内存（不写明文）</span>
        </p>
        <div class="inline">
          <input class="inp mono" type="password" placeholder="粘贴新密钥（留空表示不改）"
                 data-ai-set="apiKey" v-model="keyDraft" @keydown.enter="saveKey" />
          <button class="btn" data-ai="save-key" @click="saveKey">保存密钥</button>
          <button class="btn btn-ghost" data-ai="clear-key" @click="dropKey">清除</button>
        </div>
        <p v-if="keyMsg" class="note" data-ai="key-msg">{{ keyMsg }}</p>
      </div>
    </section>

    <!-- ⑥ 上下文与历史 -->
    <section class="row" data-setting="ai.context">
      <div class="lab">
        <span>上下文与历史</span>
        <small>窗口只用来判断"离装不下还有多远"；不填就按 32k 保守估计</small>
      </div>
      <div class="ctl col">
        <label class="inline">
          会话历史保留
          <input class="inp num" type="number" min="0" max="50" data-ai-set="historyTurns"
                 :value="cfg.historyTurns" @change="set({ historyTurns: Number($event.target.value) }, '历史轮数')" />
          轮
        </label>
        <label class="inline">
          上下文窗口
          <input class="inp num" type="number" min="0" max="4000000" step="1024" data-ai-set="contextWindow"
                 :value="cfg.contextWindow" @change="set({ contextWindow: Number($event.target.value) }, '上下文窗口')" />
          token（0 = 未知）
        </label>
      </div>
    </section>

    <!-- ⑦ 工具调用：让 AI 调引擎算，而不是自己心算 -->
    <section class="row" data-setting="ai.tools">
      <div class="lab">
        <span>工具调用</span>
        <small>让 AI 直接调本地 C++ 引擎做真实计算（推荐开启）</small>
      </div>
      <div class="ctl col">
        <label class="sw">
          <input type="checkbox" data-ai-set="toolsEnabled" :checked="cfg.toolsEnabled"
                 @change="set({ toolsEnabled: $event.target.checked }, '工具调用')" />
          <span>允许 AI 调用引擎计算（共 {{ toolCount }} 个引擎函数，查一个调一个）</span>
        </label>
        <p class="hint">
          开着的时候：模型只能通过 <code>engine_call</code> 拿到数值，每一步都是引擎算出来的；
          它负责讲思路与措辞，不负责算术。关掉之后它仍能回答，但数值只能靠它自己 —— 那正是本项要避免的。
          <br />
          边界：工具**只能碰引擎**（碰不到能写文件、起进程的那些桥），参数按引擎的动作表校验，
          一轮对话里最多调用 4 轮。工具结果要回传给模型，所以「引擎算出的结果」关着时会被拒。
        </p>
      </div>
    </section>

    <!-- ⑧ 隐私：会发什么，逐项可关 -->
    <section class="row" data-setting="ai.privacy">
      <div class="lab">
        <span>会发送什么</span>
        <small>只有你点发送时才发；这里关掉的内容不会离开这台机器</small>
      </div>
      <div class="ctl col">
        <label class="sw"><input type="checkbox" disabled checked /><span>你的问题文本（必需）</span></label>
        <label class="sw">
          <input type="checkbox" data-ai-set="sendExpr" :checked="cfg.sendExpr"
                 @change="set({ sendExpr: $event.target.checked }, '发送当前表达式')" />
          <span>当前表达式（默认开：否则 AI 看不到你在算什么）</span>
        </label>
        <label class="sw">
          <input type="checkbox" data-ai-set="sendResult" :checked="cfg.sendResult"
                 @change="set({ sendResult: $event.target.checked }, '发送引擎结果')" />
          <span>引擎算出的结果（默认开，且明确告诉模型"以此为准"）</span>
        </label>
        <label class="sw">
          <input type="checkbox" data-ai-set="sendHistory" :checked="cfg.sendHistory"
                 @change="set({ sendHistory: $event.target.checked }, '发送会话历史')" />
          <span>会话历史（默认关）</span>
        </label>
        <label class="sw">
          <input type="checkbox" data-ai-set="sendCode" :checked="cfg.sendCode"
                 @change="set({ sendCode: $event.target.checked }, '发送控制台代码')" />
          <span>控制台代码（默认关：那是你的私人内容）</span>
        </label>
      </div>
    </section>

    <!-- ⑧ 测试连接 -->
    <section class="row" data-setting="ai.test">
      <div class="lab">
        <span>测试连接</span>
        <small>发一条最大 1 token 的请求，只验证"能不能通"，不消耗多少额度</small>
      </div>
      <div class="ctl col">
        <div class="inline">
          <button class="btn" data-ai="test" :disabled="!aiHosted || !cfg.enabled || !cfg.hasKey"
                  @click="aiTest">测试</button>
          <span v-if="testLine" class="note" data-ai="test-line">{{ testLine }}</span>
        </div>
      </div>
    </section>

    <!-- ⑨ 自检 -->
    <section class="row" data-setting="ai.selftest">
      <div class="lab">
        <span>自检</span>
        <small>密钥保护、SSE 分帧（任意切分一致）、配置目录可写 —— 不联网</small>
      </div>
      <div class="ctl col">
        <button class="btn" data-ai="selfcheck" @click="selfCheck = aiSelfCheck()">重新自检</button>
        <ul class="checks" data-ai="selfcheck-list">
          <li v-for="(c, i) in (selfCheck?.checks || [])" :key="i" :class="{ bad: !c.ok }">
            <span class="dot">{{ c.ok ? "✔" : "✗" }}</span>
            <span class="ck-name">{{ c.name }}</span>
            <span class="ck-detail">{{ c.detail }}</span>
          </li>
        </ul>
      </div>
    </section>

    <!-- ⑩ 会话记录 -->
    <section class="row" data-setting="ai.chat">
      <div class="lab">
        <span>会话记录</span>
        <small>只保存最终消息（不保存增量），落 %LOCALAPPDATA%\MFMath\settings\ai-chat.json</small>
      </div>
      <div class="ctl col">
        <p class="state" data-ai="chat-count">当前 {{ aiMessages.length }} 条消息</p>
        <button class="btn btn-ghost" data-ai="clear-chat" @click="clearChat()">清空对话</button>
      </div>
    </section>

    <p v-if="saved" class="ag-saved" data-ai="saved">{{ saved }}</p>
  </div>
</template>

<style scoped>
.ag { display: flex; flex-direction: column; gap: 2px; }
.row { display: flex; gap: 16px; padding: 12px 4px; border-bottom: 1px solid var(--border); align-items: flex-start; }
.lab { width: 190px; flex: none; display: flex; flex-direction: column; gap: 3px; }
.lab span { font-size: 13.5px; }
.lab small { color: var(--muted); font-size: 11.5px; line-height: 1.5; }
.ctl { flex: 1; min-width: 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ctl.col { flex-direction: column; align-items: stretch; gap: 7px; }
.inline { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--muted); }
.inp {
  background: var(--bg); color: var(--text); border: 1px solid var(--border);
  border-radius: 6px; padding: 5px 7px; font-size: 12.5px; min-width: 0; flex: 1;
}
.inp.num { max-width: 96px; flex: none; }
.mono { font-family: ui-monospace, Consolas, monospace; }
.sw { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--muted); }
.presets { display: flex; gap: 6px; flex-wrap: wrap; }
.chip { background: none; border: 1px solid var(--border); color: var(--muted); border-radius: 999px; padding: 2px 9px; font-size: 11.5px; cursor: pointer; }
.chip:hover { color: var(--text); border-color: var(--accent, #5a82f0); }
.state { margin: 0; font-size: 12.5px; color: var(--text); }
.state .warn, .warn { color: var(--warn, #c77); }
.note { margin: 0; font-size: 11.5px; color: var(--muted); }
.checks { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.checks li { display: flex; gap: 6px; font-size: 11.5px; color: var(--muted); }
.checks li.bad { color: var(--danger, #d05a5a); }
.ck-name { color: var(--text); flex: none; }
.ck-detail { overflow: hidden; text-overflow: ellipsis; }
.ag-saved { position: sticky; bottom: 0; margin: 0; padding: 6px 4px; font-size: 11.5px; color: var(--accent, #5a82f0); }
</style>
