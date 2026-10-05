/**
 * 渲染进程的未捕获异常 → 宿主日志（P0）
 *
 * 为什么要有这个模块：
 *   宿主侧（C#）的异常已经有完整记录（`MFMath.Host/Log.cs` + `App.xaml.cs` 的三类处理器），
 *   但 **WebView2 里的 JS 异常宿主一条都看不到** —— 前端抛未捕获异常时，
 *   用户那边往往只是"点了没反应"或白屏，而 app.log 里毫无线索，只能靠猜。
 *   这里把前端捕获到的异常经 `hostObjects.sync.diag`（`LogBridge.cs`）写进**同一个** app.log，
 *   两边的时间线终于对得上。
 *
 * 覆盖面（三类，缺一不可）：
 *   · `error`（捕获阶段）—— 脚本错误 + 资源加载失败；
 *   · `unhandledrejection` —— Promise 里没人 catch 的异常（异步代码的主要漏点）；
 *   · **Vue 的 `app.config.errorHandler`** —— 组件渲染/生命周期里抛的错，Vue 默认只打 console，
 *     不接管的话连 `error` 事件都不会触发。
 *
 * 约束：**上报本身绝不能再抛**，也不能刷屏（去重 + 每次会话上限），
 * 浏览器里（没有宿主）就只留在控制台，不假装上报成功。
 */
const MAX_PER_SESSION = 50;
let sent = 0;
const seen = new Set();

function hostLog() {
  try {
    return window.chrome?.webview?.hostObjects?.sync?.diag ?? null;
  } catch {
    return null;
  }
}

/** 把任意形态的异常描述成一行可读文本（栈截断，避免一条日志几千字符） */
export function describeError(e) {
  try {
    if (e instanceof Error) {
      const stack = (e.stack || "").split("\n").slice(0, 6).join(" ⏎ ");
      return (e.name || "Error") + ": " + (e.message || "") + (stack ? " | " + stack : "");
    }
    if (typeof e === "string") return e;
    return JSON.stringify(e).slice(0, 500);
  } catch {
    return "(无法描述的异常)";
  }
}

function where() {
  try {
    return location.hash || location.pathname || "";
  } catch {
    return "";
  }
}

function report(kind, detail) {
  try {
    const text = `${kind} @${where()} — ${detail}`;
    if (seen.has(text) || sent >= MAX_PER_SESSION) return;
    seen.add(text);
    sent += 1;
    const h = hostLog();
    if (!h) return; // 浏览器里（没有宿主）就只留在控制台：不假装上报成功
    /* ⚠ 成员名必须与 C# **逐字一致（PascalCase）**：WebView2 宿主对象的属性是**大小写敏感**的。
     * 仓库里几处注释写成 `hostObjects.sync.mf.{dispatch,ready,version}`，那是错的 ——
     * 实际调用处是 `mf.Dispatch / mf.Ready / mf.Version`。
     * 而且**访问不存在的属性会直接抛 0x80070057**（不是返回 undefined），
     * 所以这里既不能靠 `typeof h.front === "function"` 试探、也没有回退余地：
     * 名字写错就会静默什么都不记 —— 这正是本模块第一次上线时的真实故障。 */
    h.Front("ERROR", text);
  } catch {
    // 上报失败绝不能再抛，否则会形成异常循环
  }
}

/** 在 main.js 里挂一次（传入 Vue app 以便接管组件错误） */
export function installErrorReporting(app) {
  try {
    window.addEventListener(
      "error",
      (ev) => {
        // 资源加载失败（img/script）没有 ev.error，但 target 上有 src/href
        if (ev && ev.target && ev.target !== window && (ev.target.src || ev.target.href)) {
          report("资源加载失败", String(ev.target.src || ev.target.href).slice(0, 300));
          return;
        }
        report("未捕获异常", describeError(ev?.error ?? ev?.message ?? "unknown"));
      },
      true, // 捕获阶段：资源错误不冒泡，必须用 capture
    );

    window.addEventListener("unhandledrejection", (ev) => {
      report("未处理的 Promise 异常", describeError(ev?.reason ?? "unknown"));
    });

    if (app && app.config) {
      app.config.errorHandler = (err, _instance, info) => {
        report("Vue 组件异常（" + (info || "?") + "）", describeError(err));
        // 保留默认可见性：控制台仍然要打出来，开发时才好定位
        console.error(err);
      };
    }
  } catch {
    // 挂钩失败也不能影响启动
  }
}
