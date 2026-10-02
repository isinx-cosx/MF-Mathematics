/**
 * push.js — C#→JS 推送通道（页面侧）
 *
 * 宿主侧：MFMath.Host/PushHub.cs（`CoreWebView2.PostWebMessageAsJson`）
 *        暴露给 JS 的诊断桥：`push`（hostObjects.sync.push）
 *
 * 信封固定为：`{ topic, seq, ts, payload }`
 *   · topic   主题字符串，页面按主题订阅（`component.install` / `console.run` …）
 *   · seq     宿主侧单调递增序号。**丢消息能看出来**：seq 不连续即说明中间丢了
 *   · ts      宿主发出的毫秒时间戳
 *   · payload 主题自己的数据（JSON 对象或 null）
 *
 * 为什么不用"每个主题一个回调"的黑盒：推送是**旁路**，它失败不能影响业务。
 * 所以这里所有订阅都是"通知一下，收到了什么自己再决定要不要去拉数据"，
 * 而权威数据仍在同步桥（`InstallStatus` / `Poll`）里 —— 推送负责"及时"，
 * 一次同步调用负责"正确"。这个分工在下面 ComponentsGroup / ConsoleView 里都能看到。
 *
 * 无宿主（浏览器预览）时全部降级为 no-op，界面照旧可用。
 */
import { ref } from "vue";

/** 页面侧状态：最常被界面用来显示"推送通道：已连接 / 收到 N 条" */
export const pushState = ref({
  available: false,   // 事件监听已挂上
  received: 0,        // 收到的消息条数
  lastTopic: "",
  lastTs: 0,
  lastSeq: 0,
  gaps: 0,            // seq 不连续的次数（丢消息）
});

const MAX_LOG = 50;
const log = [];
const handlers = new Set();
let inited = false;

function hostObj() {
  try {
    return window.chrome?.webview?.hostObjects?.sync?.push ?? null;
  } catch {
    return null;
  }
}

/** 宿主是否提供了 `push` 桥（在这个前提下推送才可能到） */
export function isPushHosted() {
  return hostObj() !== null;
}

function parse(text, fallback = null) {
  if (text == null) return fallback;
  if (typeof text === "object") return text;
  try { return JSON.parse(String(text)); } catch { return fallback; }
}

/** 通道诊断：宿主侧计数 + 页面侧计数（两边一比就知道卡在哪一段） */
export function pushInfo() {
  const c = hostObj();
  let host = null;
  try { host = c ? parse(c.Info()) : null; } catch { host = { error: "Info() 调用失败" }; }
  return {
    host,
    page: {
      available: pushState.value.available,
      received: pushState.value.received,
      lastTopic: pushState.value.lastTopic,
      lastTs: pushState.value.lastTs,
      lastSeq: pushState.value.lastSeq,
      gaps: pushState.value.gaps,
      handlers: handlers.size,
    },
  };
}

/**
 * 订阅推送。两种写法：
 *   onPush(handler)              —— 所有主题
 *   onPush("component.install", handler) —— 只这一个主题
 * 返回取消订阅的函数。
 */
export function onPush(topicOrHandler, maybeHandler) {
  const topic = typeof topicOrHandler === "string" ? topicOrHandler : null;
  const fn = typeof topicOrHandler === "function" ? topicOrHandler : maybeHandler;
  if (typeof fn !== "function") return () => {};
  const entry = { topic, fn };
  handlers.add(entry);
  return () => handlers.delete(entry);
}

function dispatch(env) {
  const prev = pushState.value;
  const seq = typeof env.seq === "number" ? env.seq : 0;
  const gap = prev.lastSeq > 0 && seq > 0 && seq !== prev.lastSeq + 1;
  pushState.value = {
    available: true,
    received: prev.received + 1,
    lastTopic: String(env.topic || ""),
    lastTs: typeof env.ts === "number" ? env.ts : Date.now(),
    lastSeq: seq || prev.lastSeq,
    gaps: prev.gaps + (gap ? 1 : 0),
  };
  log.push(env);
  if (log.length > MAX_LOG) log.shift();
  for (const h of [...handlers]) {
    if (h.topic && h.topic !== env.topic) continue;
    try { h.fn(env); } catch (e) {
      // 订阅方出错不能影响其它订阅方，更不能影响推送本身
      console.error("[push] 处理 " + env.topic + " 失败：", e);
    }
  }
}

/** 挂上监听（App 启动时调一次；重复调用无副作用） */
export function initPush() {
  if (inited) return pushState.value.available;
  const wv = (() => { try { return window.chrome?.webview ?? null; } catch { return null; } })();
  if (!wv || typeof wv.addEventListener !== "function") return false;
  wv.addEventListener("message", (ev) => {
    const env = parse(ev?.data);
    // 不是推送信封就不管（WebView2 的 message 通道将来也可能有别的 sender）
    if (!env || typeof env.topic !== "string") return;
    dispatch(env);
  });
  inited = true;
  pushState.value = { ...pushState.value, available: true, lastTopic: pushState.value.lastTopic };
  // 测试与排障用的钩子：CDP 里够不着模块作用域，只能从这里读
  try {
    window.__mfPush = {
      info: pushInfo,
      state: () => pushState.value,
      log: () => log.slice(),
      on: onPush,
      emit: emit,
    };
  } catch { /* 忽略 */ }
  return true;
}

/**
 * 让宿主发一条消息回来（JS → 宿主 → JS 往返）。**只用于自测/诊断**，
 * 业务消息由宿主在真实事件里主动发出。
 * @returns {{ok:boolean, seq?:number, error?:string}}
 */
export function emit(topic, payload = null) {
  const c = hostObj();
  if (!c) return { ok: false, error: "无宿主：推送通道只在 MFMath.exe 里可用" };
  try {
    return parse(c.Emit(String(topic || ""), payload == null ? "" : JSON.stringify(payload)), { ok: false, error: "返回无法解析" });
  } catch (e) {
    return { ok: false, error: String(e?.message || e) };
  }
}

/** 最近收到的消息（诊断面板与测试用） */
export function pushLog() {
  return log.slice();
}
