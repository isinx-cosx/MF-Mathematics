/**
 * ai/bridge.js — AI 助手（宿主桥 + 流式状态 + 消息组装）
 *
 * 分工（刻意如此）：
 *   · **宿主** 负责传输与密钥：SSE 分帧、超时、取消、错误分类，密钥只在宿主内存与
 *     DPAPI 密文里（见 MFMath.Host/AiBridge.cs）。页面**拿不到密钥**。
 *   · **页面** 负责组装消息与渲染：系统提示、上下文、历史按隐私开关取舍，
 *     以及把增量渲染到面板上。
 *
 * 事件话题（宿主经 PushHub 推来，都带 requestId）：
 *   ai.started · ai.delta · ai.reasoning · ai.toolcall · ai.usage · ai.notice
 *   ai.done · ai.error · ai.test
 *
 * 三条纪律（照搬 MVS Agent 的模型层，这里落在 UI 侧）：
 *   ① 流式是原语：状态里存的是**增量累加**的 text/reasoning，不是最终字符串；
 *   ② 能力缺失是可观测的降级：缺 usage、流被截断都进 notices，不算失败；
 *   ③ 错误是一等事件：error/done 都带原因，"没开始"和"吐了一半"必须能区分。
 *
 * 无宿主（浏览器预览）时全部降级：面板照旧能开，但会在顶部明说"只在 MFMath.exe 里可用"。
 */
import { computed, ref } from "vue";
import { onPush } from "../push.js";
import { getPage } from "../workspace/store.js";

/* ── 宿主桥 ──────────────────────────────────────────────────────────── */

function hostObj() {
  try {
    return window.chrome?.webview?.hostObjects?.sync?.ai ?? null;
  } catch {
    return null;
  }
}

/** 宿主是否提供 `ai` 桥 */
export function isAiHosted() {
  return hostObj() !== null;
}

function parse(text, fallback = null) {
  if (text == null) return fallback;
  if (typeof text === "object") return text;
  try { return JSON.parse(String(text)); } catch { return fallback; }
}

function call(method, ...args) {
  const c = hostObj();
  if (!c || typeof c[method] !== "function") return null;
  try { return parse(c[method](...args)); } catch (e) { return { ok: false, error: String(e?.message || e) }; }
}

/* ── 配置状态 ────────────────────────────────────────────────────────── */

const DEFAULT_CFG = {
  enabled: false,
  baseUrl: "https://api.deepseek.com/v1",
  model: "deepseek-chat",
  temperature: 0.6,
  maxTokens: 2048,
  includeUsage: true,
  timeoutSec: 120,
  contextWindow: 0,
  historyTurns: 6,
  sendExpr: true,
  sendResult: true,
  sendHistory: false,
  sendCode: false,
  hasKey: false,
  keySource: "none",
  keyPersisted: false,
  dpapiAvailable: false,
  configPath: "",
  lastError: "",
};

/** 脱敏后的配置（永远不含密钥本身） */
export const aiConfig = ref({ ...DEFAULT_CFG });
export const aiHosted = ref(false);

/** 刷新宿主侧状态。面板打开、设置改动后都要调一次。 */
export function refreshAiConfig() {
  aiHosted.value = isAiHosted();
  const info = call("Info");
  if (info && typeof info === "object" && "enabled" in info) {
    aiConfig.value = { ...DEFAULT_CFG, ...info };
  }
  return aiConfig.value;
}

/** 只发改动过的字段：整份回传会把界面没显示的字段以默认值悄悄写回磁盘 */
export function aiConfigure(patch) {
  const keys = Object.keys(patch || {});
  if (!keys.length) return { ok: true, changed: 0 };
  const res = call("Configure", JSON.stringify(patch));
  refreshAiConfig();
  return res || { ok: false, error: "无宿主：AI 配置只在 MFMath.exe 里可改" };
}

export function aiSetKey(key) {
  const res = call("SetKey", String(key || ""));
  refreshAiConfig();
  return res || { ok: false, error: "无宿主" };
}

export function aiClearKey() {
  const res = call("ClearKey");
  refreshAiConfig();
  return res || { ok: false, error: "无宿主" };
}

export function aiSelfCheck() {
  return call("SelfCheck") || { ok: false, error: "无宿主" };
}

/* ── 连通性测试 ──────────────────────────────────────────────────────── */

export const aiTestState = ref({ testing: false, result: null });

export function aiTest() {
  const res = call("Test");
  if (!res || res.ok === false) {
    aiTestState.value = { testing: false, result: { ok: false, detail: res?.error || "无宿主" } };
    return res;
  }
  aiTestState.value = { testing: true, result: null };
  return { ok: true };
}

/* ── 流式会话状态 ────────────────────────────────────────────────────── */

/**
 * 一轮对话的状态。
 * `messages` 是**已经完成的**轮次（落盘只落它，不落增量——增量会把日志撑爆），
 * `stream` 是当前正在增长的文本。
 */
export const aiState = ref({
  running: false,
  requestId: "",
  model: "",
  stream: "",
  reasoning: "",
  notices: [],
  usage: null,
  error: null,
  doneReason: "",
  startedAt: 0,
});

/** 会话消息（只存最终结果：user / assistant 文本） */
export const aiMessages = ref([]);

const CHAT_STORE = "ai-chat";
const MAX_MESSAGES = 40;

/** 会话落盘：只落最终消息，不落增量。刷新后能接着聊，且日志不会被 token 撑爆。 */
function persistChat() {
  const c = (() => { try { return window.chrome?.webview?.hostObjects?.sync?.sys ?? null; } catch { return null; } })();
  if (!c || typeof c.StoreWrite !== "function") return;
  try {
    c.StoreWrite(CHAT_STORE, JSON.stringify({
      version: 1,
      updatedAt: Date.now(),
      messages: aiMessages.value.slice(-MAX_MESSAGES),
    }));
  } catch { /* 落盘失败不影响对话 */ }
}

function loadChat() {
  const c = (() => { try { return window.chrome?.webview?.hostObjects?.sync?.sys ?? null; } catch { return null; } })();
  if (!c || typeof c.StoreRead !== "function") return;
  try {
    const r = parse(c.StoreRead(CHAT_STORE));
    if (!r || !r.ok || !r.json) return;
    const obj = JSON.parse(r.json);
    if (obj && Array.isArray(obj.messages)) {
      aiMessages.value = obj.messages
        .filter((m) => m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string")
        .slice(-MAX_MESSAGES);
    }
  } catch { /* 坏文件不静默覆盖，只是这次读不到 */ }
}

export function clearChat() {
  aiMessages.value = [];
  aiState.value = { ...aiState.value, stream: "", reasoning: "", notices: [], error: null, usage: null, doneReason: "" };
  persistChat();
}

/* ── 推送订阅 ────────────────────────────────────────────────────────── */

let inited = false;

/** 挂上推送订阅（App 启动时调一次，幂等） */
export function initAi() {
  if (inited) return;
  inited = true;
  loadChat();

  onPush((env) => {
    const p = env?.payload || {};
    const topic = String(env?.topic || "");
    if (!topic.startsWith("ai.")) return;

    if (topic === "ai.test") {
      aiTestState.value = { testing: false, result: p };
      return;
    }

    // ⚠ ai.started 必须**先于**"旧请求过滤"处理。
    // 过滤的作用是防止上一轮的迟到增量污染新回复，而 started 本身就是"新一轮开始"，
    // 拿它去和旧 requestId 比会被自己挡掉——实测症状很隐蔽：
    // JS 侧 requestId 永远停在上上轮，stop() 停了个不存在的 id，
    // 宿主那一轮还在跑，于是下一次发送被宿主的单飞检查拒绝（"已有一轮在输出"）。
    if (topic === "ai.started") {
      aiState.value = {
        running: true,
        requestId: String(p.requestId || ""),
        model: String(p.model || ""),
        stream: "",
        reasoning: "",
        notices: [],
        usage: null,
        error: null,
        doneReason: "",
        startedAt: typeof p.startedAt === "number" ? p.startedAt : Date.now(),
      };
      return;
    }

    // 其余话题只认当前这一轮
    if (p.requestId && aiState.value.requestId && p.requestId !== aiState.value.requestId) return;

    switch (topic) {
      case "ai.delta":
        aiState.value = { ...aiState.value, stream: aiState.value.stream + String(p.text || "") };
        break;

      case "ai.reasoning":
        aiState.value = { ...aiState.value, reasoning: aiState.value.reasoning + String(p.text || "") };
        break;

      case "ai.usage":
        aiState.value = { ...aiState.value, usage: { inputTokens: p.inputTokens || 0, outputTokens: p.outputTokens || 0 } };
        break;

      case "ai.notice":
        aiState.value = {
          ...aiState.value,
          notices: [...aiState.value.notices, { code: String(p.code || ""), message: String(p.message || "") }],
        };
        break;

      case "ai.error":
        aiState.value = {
          ...aiState.value,
          running: false,
          error: { kind: String(p.kind || ""), status: Number(p.status || 0), message: String(p.message || "") },
        };
        break;

      case "ai.done": {
        const text = aiState.value.stream;
        const reason = String(p.reason || "");
        aiState.value = { ...aiState.value, running: false, doneReason: reason };
        if (text.trim()) {
          aiMessages.value = [...aiMessages.value, { role: "assistant", content: text }].slice(-MAX_MESSAGES);
          persistChat();
        }
        break;
      }

      default:
        break;   // ai.toolcall：第一版不执行工具，契约留位
    }
  });
}

/* ── 消息组装（隐私开关在这里生效）────────────────────────────────────── */

const SYSTEM_PROMPT = [
  "你是 MF-Mathematics 的数学助手。",
  "硬规矩：所有计算由 C++ 引擎完成，你只做解释、讲解与思路梳理。",
  "· 需要具体数值或符号结果时，请说明这一步应由引擎计算，不要自行给一个可能出错的数值；",
  "· 如果用户给了引擎已经算出的结果，以它为准，不要改写成你自己算的值；",
  "· 公式用 LaTeX：行内 $...$，独立成行用 $$...$$；",
  "· 不确定就直说，不要编造。",
].join("\n");

/** 从当前页面的工作区载荷里取上下文（只有打开对应开关才会被送出去） */
export function currentContext(route) {
  const p = getPage(route || "");
  const ctx = { page: route || "", expr: "", result: "", code: "", lang: "" };
  if (!p || typeof p !== "object") return ctx;

  if (p.kind === "calc" && Array.isArray(p.blocks)) {
    const last = p.blocks[p.blocks.length - 1];
    if (last) {
      ctx.expr = String(last.expr || "");
      ctx.result = String(last.result || "");
      ctx.mode = String(last.mode || "");
    }
  } else if (p.kind === "plot" && Array.isArray(p.expressions)) {
    ctx.expr = p.expressions.map((e) => String(e?.text ?? e ?? "")).filter(Boolean).join(" ; ");
  } else if (p.kind === "console") {
    ctx.lang = String(p.lang || "");
    ctx.code = String(p.code || "");
  }
  return ctx;
}

/**
 * 组装将要发给模型的消息数组。**返回的就是唯一真相**：
 * 面板上的"将发送约 N token / 包含哪些内容"直接用它算，不另算一遍。
 */
export function buildMessages({ userText, history = [], context = null, cfg = aiConfig.value }) {
  const out = [{ role: "system", content: SYSTEM_PROMPT }];

  const lines = [];
  if (context) {
    if (cfg.sendExpr && context.expr) lines.push("当前表达式：" + context.expr);
    if (cfg.sendResult && context.result) lines.push("引擎已算出的结果：" + context.result + "（以此为准）");
    if (context.mode) lines.push("当前模式：" + context.mode);
    if (cfg.sendCode && context.code) lines.push("控制台代码（" + (context.lang || "") + "）：\n" + context.code);
  }
  if (lines.length) out.push({ role: "system", content: "用户当前的工作现场：\n" + lines.join("\n") });

  // 历史：只在开关打开时带上，且**只带最近 N 轮**（成本闸门）。
  // 注意 historyTurns=0 的语义是"一条历史都不带"，不是"带全部"——
  // 这里刻意不写 slice(-keep)，那在 keep=0 时会退化成 slice(0)（正好相反）。
  if (cfg.sendHistory && history.length) {
    const keep = Math.max(0, (Number(cfg.historyTurns) || 0) * 2);
    if (keep > 0) {
      for (const m of history.slice(-keep)) {
        out.push({ role: m.role === "assistant" ? "assistant" : "user", content: String(m.content || "") });
      }
    }
  }

  out.push({ role: "user", content: String(userText || "") });
  return out;
}

/* ── token 估算（用途只有一个：显示"这轮大概要花多少"）───────────────── */

const CJK = [[0x3000, 0x303f], [0x3040, 0x30ff], [0x3400, 0x4dbf], [0x4e00, 0x9fff], [0xf900, 0xfaff], [0xff00, 0xffef]];

function isCjk(code) {
  for (const [a, b] of CJK) if (code >= a && code <= b) return true;
  return false;
}

/**
 * 按字符分类加权估算：ASCII 约 3.5 字符 1 token、CJK 约 1 字符 1 token。
 * **这是估算，不是分词**，误差方向偏保守（宁可高估）——它只用来决定"该不该提醒用户太长"。
 */
export function estimateTokens(text) {
  let ascii = 0, cjk = 0, other = 0;
  for (const ch of String(text || "")) {
    const c = ch.codePointAt(0) ?? 0;
    if (c < 0x80) ascii += 1;
    else if (isCjk(c)) cjk += 1;
    else other += 1;
  }
  return Math.ceil(ascii / 3.5 + cjk * 1.05 + other * 0.7);
}

export function estimateMessagesTokens(messages) {
  let total = 0;
  for (const m of messages || []) total += 6 + estimateTokens(m.content);
  return total;
}

/** 上下文窗口：声明值优先，否则保守默认 32k，并**如实标注来源** */
export function contextBudget(cfg = aiConfig.value) {
  const declared = Number(cfg.contextWindow) || 0;
  const window = declared > 0 ? declared : 32768;
  return {
    window,
    source: declared > 0 ? "你声明的值" : "保守默认（未声明，且多数兼容端点不返回上下文长度）",
    budget: Math.max(1024, window - (Number(cfg.maxTokens) || 2048)),
  };
}

/* ── 发送 / 停止 ─────────────────────────────────────────────────────── */

/** @returns {{ok:boolean, error?:string, requestId?:string}} */
export function sendTurn(userText, { route = "", history = aiMessages.value, context = null } = {}) {
  const text = String(userText || "").trim();
  if (!text) return { ok: false, error: "先说点什么" };

  const cfg = aiConfig.value;
  if (!cfg.enabled) return { ok: false, error: "AI 未启用：去「设置 → AI」打开开关" };
  if (!cfg.hasKey) return { ok: false, error: "还没有 API Key：去「设置 → AI」填一个" };

  const ctx = context ?? currentContext(route);
  const messages = buildMessages({ userText: text, history, context: ctx, cfg });

  // 先落到会话里（用户那条），这样即使请求失败也能看到自己说过什么
  aiMessages.value = [...aiMessages.value, { role: "user", content: text }].slice(-MAX_MESSAGES);

  const res = call("Start", JSON.stringify({ messages }));
  if (!res || res.ok === false) {
    const err = res?.error || "无宿主：AI 只在 MFMath.exe 里可用";
    aiState.value = { ...aiState.value, running: false, error: { kind: "config", status: 0, message: err } };
    return { ok: false, error: err };
  }
  persistChat();
  return res;
}

export function stopTurn() {
  const id = aiState.value.requestId;
  if (!id) return { ok: false, error: "当前没有在输出的请求" };
  return call("Cancel", id) || { ok: false, error: "无宿主" };
}

export const aiBusy = computed(() => aiState.value.running);

/** 测试/排障钩子：CDP 里够不到模块作用域 */
export function initAiHook() {
  try {
    window.__mfAi = {
      info: () => aiConfig.value,
      state: () => aiState.value,
      messages: () => aiMessages.value,
      refresh: refreshAiConfig,
      configure: aiConfigure,
      setKey: aiSetKey,
      clearKey: aiClearKey,
      selfCheck: aiSelfCheck,
      test: aiTest,
      send: (text, opts) => sendTurn(text, opts || {}),
      stop: stopTurn,
      clear: clearChat,
      build: (opts) => buildMessages(opts || {}),
      tokens: estimateTokens,
      budget: contextBudget,
      context: currentContext,
      hosted: isAiHosted,
    };
  } catch { /* 忽略 */ }
}
