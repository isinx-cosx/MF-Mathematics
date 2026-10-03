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
import { HostRelayClient } from "./client.ts";
import { collect, parseToolArgs } from "./collect.ts";
import { isRelayHosted, relayCancelAll } from "./relay.ts";
import { parseInline } from "./markdown.ts";
import { AI_TOOLS, executeTool, initAiToolsHook, ENGINE_FN_COUNT } from "./tools.ts";

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
  // 工具调用：让 AI 能调本地 C++ 引擎真算（默认开 —— 计算必须发生在引擎里）
  toolsEnabled: true,
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

/* ── 会话落盘：只落最终消息，不落增量 ────────────────────────────────── */

const CHAT_STORE = "ai-chat";
const MAX_MESSAGES = 40;
/** 思考过程跟着消息一起存，但要有上限：它是过程，不是结论，别把日志撑爆 */
const MAX_REASONING = 8000;

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
        .map((m) => (typeof m.reasoning === "string" && m.reasoning
          ? { role: m.role, content: m.content, reasoning: m.reasoning }
          : { role: m.role, content: m.content }))
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
  initTestWatch();
}

/**
 * 只订阅连通性自检结果。
 *
 * ⚠ 对话本身**不再走推送话题**：SSE 分帧、OpenAI 分片语义、错误分类都搬到了
 * TS 那一层（`client.ts` 直接消费宿主转回来的原始字节），所以增量是把
 * `client.stream()` 的事件喂进 `collect({ onEvent })` 得来的 —— 一份实现。
 * 之前那套 `ai.started/delta/reasoning/usage/notice/done/error` 话题连同
 * 宿主侧的 C# 流式客户端一起删掉了（宿主现在只转发字节）。
 */
function initTestWatch() {
  onPush((env) => {
    if (String(env?.topic || "") !== "ai.test") return;
    aiTestState.value = { testing: false, result: env.payload || {} };
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

/* ── 正文切分（适配层）：公式/文本压平，供测试与旧调用方使用 ──────────── */

/**
 * 把一行正文压平成 `[{kind:"text"|"math", value, display}]`。
 *
 * 真正的解析在 `markdown.ts`（行内 token 树，含粗体/代码/链接），
 * 这里只是**适配层**：把树压平。刻意不在这里再写一份公式识别 ——
 * 「`$...$` 里不像公式就当占位符文本」这条规矩只能有一个实现。
 */
export function splitMath(text) {
  const flat = [];
  const walk = (tokens) => {
    for (const t of tokens) {
      if (t.type === "math") flat.push({ kind: "math", value: t.tex, display: t.display });
      else if (t.type === "text") flat.push({ kind: "text", value: t.text });
      else if (t.type === "code") flat.push({ kind: "text", value: "`" + t.text + "`" });
      else if (Array.isArray(t.content)) walk(t.content);
    }
  };
  walk(parseInline(text));
  return flat.length ? flat : [{ kind: "text", value: String(text || "") }];
}

/* ── 发送 / 停止（走 TS 客户端；宿主只负责带密钥发请求与转发字节）───────── */

let controller = null;   // 当前这一轮的 AbortController

/**
 * 发一轮。**立即返回**（不等回复），流式增量由 onEvent 写进 aiState。
 *
 * 支持**工具循环**：模型可以调 `engine_call` 让本地 C++ 引擎真算，拿回结果再继续讲。
 *   ① 轮次有上限（MAX_TOOL_ROUNDS）：模型抽风反复调工具时会被截断并给出说明，而不是无限烧钱；
 *   ② 工具只能碰引擎（见 lib/ai/tools.ts），碰不到能写文件/起进程的桥；
 *   ③ 「发送引擎结果」关着时工具会被拒（结果要回传给模型 = 把引擎结果发出去）；
 *   ④ 停止按钮在任何一轮都能中断（abort + 取消宿主侧连接）。
 * @returns {{ok:boolean, error?:string}}
 */
export const MAX_TOOL_ROUNDS = 4;

export function sendTurn(userText, { route = "", history = aiMessages.value, context = null, autoSteps = false } = {}) {
  const text = String(userText || "").trim();
  if (!text) return { ok: false, error: "先说点什么" };

  const cfg = aiConfig.value;
  if (!cfg.enabled) return { ok: false, error: "AI 未启用：去「设置 → AI」打开开关" };
  if (!cfg.hasKey) return { ok: false, error: "还没有 API Key：去「设置 → AI」填一个" };
  if (aiState.value.running) return { ok: false, error: "已有一轮在输出，先停止它" };
  if (!isRelayHosted()) return { ok: false, error: "无宿主：AI 只在 MFMath.exe 里可用" };

  const ctx = context ?? currentContext(route);
  const messages = buildMessages({ userText: text, history, context: ctx, cfg });
  const toolsOn = cfg.toolsEnabled !== false;          // 默认开：让计算发生在引擎里
  const allowResults = cfg.sendResult !== false;       // 隐私开关，工具结果的发送要和它一致

  // 先落到会话里（用户那条），这样即使请求失败也能看到自己说过什么
  aiMessages.value = [...aiMessages.value, { role: "user", content: text }].slice(-MAX_MESSAGES);

  aiState.value = {
    running: true, requestId: "", model: cfg.model, stream: "", reasoning: "",
    notices: [], usage: null, error: null, doneReason: "", startedAt: Date.now(),
    toolCalls: [], rounds: 0,
  };

  controller = new AbortController();
  const client = new HostRelayClient({ includeUsage: cfg.includeUsage !== false });

  // 工具循环。不 await：调用方（面板）要立刻恢复响应，增量靠回调推进。
  (async () => {
    const convo = [...messages];
    const toolRecords = [];
    let textAll = "";
    let reasoningAll = "";
    let lastReason = "";
    let error = null;

    for (let round = 0; ; round++) {
      const out = await collect(client.stream({
        model: cfg.model,
        messages: convo,
        temperature: Number(cfg.temperature),
        maxTokens: Number(cfg.maxTokens),
        tools: toolsOn ? AI_TOOLS : undefined,
        signal: controller.signal,
      }), {
        onEvent: (ev) => {
          const s = aiState.value;
          switch (ev.type) {
            case "text_delta":
              aiState.value = { ...s, stream: s.stream + ev.text };
              break;
            case "reasoning_delta":
              aiState.value = { ...s, reasoning: s.reasoning + ev.text };
              break;
            case "usage":
              aiState.value = { ...s, usage: ev.usage };
              break;
            case "notice":
              aiState.value = { ...s, notices: [...s.notices, ev.notice] };
              break;
            case "error":
              aiState.value = { ...s, error: ev.error };
              break;
            default:
              break;   // tool_call_delta：按 index 累积在 collect 里，这里等收尾统一处理
          }
        },
      });

      textAll += out.text || "";
      reasoningAll += out.reasoning || "";
      lastReason = out.finishReason;
      if (out.error) { error = out.error; break; }

      const calls = out.toolCalls || [];
      if (!toolsOn || calls.length === 0) break;

      if (round >= MAX_TOOL_ROUNDS - 1) {
        // 到顶了：如实说明，而不是继续烧
        aiState.value = {
          ...aiState.value,
          notices: [...aiState.value.notices, {
            kind: "tool_round_limit",
            message: `工具调用已达上限（${MAX_TOOL_ROUNDS} 轮），停止继续调用。`,
          }],
        };
        break;
      }

      aiState.value = { ...aiState.value, rounds: round + 1 };
      // 助手这一轮（可能带正文 + 工具调用）要进上下文，否则下一轮模型不知道自己要过什么
      convo.push({
        role: "assistant",
        content: out.text || "",
        toolCalls: calls.map((c) => ({ id: c.id, name: c.name, argsJson: c.argsJson })),
      });

      for (const call of calls) {
        let args = {};
        try {
          const parsed = parseToolArgs(call);
          args = parsed && typeof parsed === "object" ? parsed : {};
        } catch (e) {
          // 参数碎片拼不成 JSON（流被截断/模型抽风）：当成一次失败的工具调用回给模型
          const rec = {
            name: call.name || "(未命名)", ok: false,
            content: `{"ok":false,"error":${JSON.stringify(String(e?.message || e))}}`,
            summary: "参数不是合法 JSON", ms: 0,
          };
          toolRecords.push(rec);
          aiState.value = { ...aiState.value, toolCalls: [...toolRecords] };
          convo.push({ role: "tool", toolCallId: call.id, content: rec.content });
          continue;
        }
        const rec = executeTool(call.name, args, allowResults);
        toolRecords.push(rec);
        aiState.value = { ...aiState.value, toolCalls: [...toolRecords] };
        convo.push({ role: "tool", toolCallId: call.id, content: rec.content });
      }
      // 这一轮的正文已经"说完了"，把它从实时缓冲移进已定稿的部分，
      // 免得下一轮的增量接在旧文字后面显示成一个畸形段落
      aiState.value = { ...aiState.value, stream: "", reasoning: "" };
    }

    return { text: textAll, reasoning: reasoningAll, finishReason: lastReason, error, toolRecords };
  })().then((r) => {
    // 收尾：把这一轮的正文与思考过程**并入会话**，然后清掉实时缓冲。
    //
    // ⚠ 这里必须清 stream / reasoning —— 上一版没清，于是同一段回答被渲染两次：
    // 一次来自消息列表（最终文本），一次来自还留在 aiState 里的"流式块"。
    // 症状很显眼但根因很蠢：running 只是"还在跑"的标志，它不是"这段文本属于谁"的归属。
    const finalText = r.text;
    const reasoning = (r.reasoning || "").slice(0, MAX_REASONING);
    aiState.value = {
      ...aiState.value, running: false,
      doneReason: r.error ? "error" : r.finishReason,
      stream: "", reasoning: "",
    };
    if (finalText.trim() || reasoning.trim() || r.toolRecords.length) {
      const msg = { role: "assistant", content: finalText };
      if (reasoning) msg.reasoning = reasoning;
      // 工具调用记录跟着消息走（面板据此渲染"这一步调了引擎、结果是什么"）
      if (r.toolRecords.length) msg.toolCalls = r.toolRecords;
      // 这一轮是"查看步骤"发起的：收尾后自动把步骤弹出来（用户点那个按钮就是想看步骤）
      if (autoSteps && r.toolRecords.length) {
        aiStepsFor.value = { steps: r.toolRecords, prose: finalText };
      }
      aiMessages.value = [...aiMessages.value, msg].slice(-MAX_MESSAGES);
      persistChat();
    }
  }).catch((e) => {
    // 用户按了停止：不是错误，别弹红字
    if (controller?.signal?.aborted) {
      aiState.value = { ...aiState.value, running: false, doneReason: "aborted", stream: "", reasoning: "" };
      return;
    }
    aiState.value = {
      ...aiState.value,
      running: false,
      error: { kind: "unknown", status: 0, message: String(e?.message || e) },
    };
  }).finally(() => {
    controller = null;
  });

  return { ok: true };
}

/** 停止当前这一轮：先取消宿主侧连接，再 abort 本地迭代 */
export function stopTurn() {
  if (!aiState.value.running) return { ok: false, error: "当前没有在输出的请求" };
  try { controller?.abort(); } catch { /* 忽略 */ }
  relayCancelAll();
  aiState.value = { ...aiState.value, running: false, doneReason: "aborted" };
  return { ok: true };
}

/* ── 由别处发起的"分步讲解"（计算页的结果对话框点「查看步骤」）──────────────
 * 为什么要有这条通道：分步显示的内容**只能来自 AI 调引擎的记录** —— 引擎信封里没有 steps
 * 字段，自己编步骤就等于伪造推导。所以"查看步骤"的正确做法是：把这道题交给 AI，让它逐步调
 * 引擎，每一步的数值都由引擎给出。
 *
 * 通路：计算页 requestAiTurn(prompt, {autoSteps}) → App 打开面板 → 面板取走请求并自动发送
 * → 收尾后若这一轮带着引擎步骤，面板自动弹出 StepViewer。
 * 用 ref 而不是事件总线：只有一处消费（面板），取一次即清，免得下次打开面板又重放一遍。
 */
export const aiRequest = ref(null);
export const aiStepsFor = ref(null);

export function requestAiTurn(text, { autoSteps = false } = {}) {
  const t = String(text || "").trim();
  if (!t) return { ok: false, error: "没有内容" };
  aiRequest.value = { text: t, autoSteps: !!autoSteps, at: Date.now() };
  return { ok: true };
}

/** 面板取走请求（取一次即清空） */
export function takeAiRequest() {
  const r = aiRequest.value;
  aiRequest.value = null;
  return r;
}

/** 面板关掉步骤弹层后清空 */
export function clearAiSteps() { aiStepsFor.value = null; }

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
      requestTurn: requestAiTurn,
      takeRequest: takeAiRequest,
      steps: () => aiStepsFor.value,
      clearSteps: clearAiSteps,
      stop: stopTurn,
      clear: clearChat,
      build: (opts) => buildMessages(opts || {}),
      splitMath,
      tokens: estimateTokens,
      budget: contextBudget,
      context: currentContext,
      hosted: isAiHosted,
      // 工具：引擎目录规模、单个函数/校验/执行（"只能调引擎"这条边界也靠它断言）
      tools: {
        count: () => ENGINE_FN_COUNT,
        schemas: () => AI_TOOLS,
        execute: executeTool,
        maxRounds: () => MAX_TOOL_ROUNDS,
      },
    };
  } catch { /* 忽略 */ }
  initAiToolsHook();
}
