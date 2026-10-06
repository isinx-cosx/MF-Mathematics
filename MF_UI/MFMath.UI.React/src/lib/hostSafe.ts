/**
 * hostSafe — 宿主调用的兜底与前端错误上报（React 版）
 *
 * 为什么需要：WebView2 的宿主对象（`chrome.webview.hostObjects.sync.*`）在页面
 * **首帧渲染时可能还没挂上**，此时访问不存在的成员会**抛 0x80070057**（不是返回 undefined）。
 * 如果这个异常发生在 React 首帧里，整个应用会渲染失败 —— 表现就是**白屏**，
 * 而且宿主日志里一条记录都没有（没有错误上报就没人知道发生了什么）。
 * Vue 版是把这些调用放在挂载之后/惰性求值，所以它遇不到；React 版必须显式兜底。
 */
export const HOST_LOG_PREFIX = "[前端] ";

/** 调用宿主能力，失败一律回退到 fallback，绝不把异常抛进渲染流程 */
export function safe<T>(fn: () => T, fallback: T): T {
  try {
    const v = fn();
    return v === undefined || v === null ? fallback : v;
  } catch {
    return fallback;
  }
}

/** 把一条前端错误送到宿主日志（有 diag 桥才送；没有就只留控制台） */
export function reportToHost(kind: string, message: string) {
  try {
    const w = window as unknown as {
      chrome?: { webview?: { hostObjects?: { sync?: Record<string, { Front?: (l: string, m: string) => void }> } } };
    };
    const diag = w.chrome?.webview?.hostObjects?.sync?.diag;
    // 成员名是 PascalCase 且大小写敏感（写 diag.front 会抛 0x80070057）
    if (diag && typeof diag.Front === "function") diag.Front(kind, message);
  } catch {
    /* 宿主不可用：忽略，控制台里已经有 */
  }
}

/**
 * 安装全局错误上报：window error / unhandledrejection。
 * 与 Vue 版 lib/diagnostics/errors.js 的行为对齐（去重 + 上限），保证
 * "界面白屏"这类问题在宿主日志里**一定**留下证据。
 */
export function installErrorReporting() {
  const seen = new Set<string>();
  const MAX = 50;

  const report = (kind: string, message: string) => {
    const text = String(message || "").slice(0, 500);
    const key = kind + "|" + text;
    if (seen.has(key) || seen.size >= MAX) return;
    seen.add(key);
    console.error(HOST_LOG_PREFIX + text);
    reportToHost(kind, text);
  };

  window.addEventListener("error", (e) => {
    const where = e.filename ? ` @${e.filename}:${e.lineno}` : "";
    report("ERROR", (e.message || "unknown error") + where);
  });
  window.addEventListener("unhandledrejection", (e) => {
    const r = (e as PromiseRejectionEvent).reason;
    report("REJECT", r && (r.stack || r.message) ? (r.stack || r.message) : String(r));
  });
}
