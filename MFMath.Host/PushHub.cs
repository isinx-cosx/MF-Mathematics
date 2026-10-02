using System;
using System.Threading;
using System.Windows.Threading;
using Microsoft.Web.WebView2.Core;

namespace MFMath.Host;

/// <summary>
/// PushHub —— C# → JS 的**推送通道**（宿主主动把消息发给页面）。
///
/// 为什么需要它：在此之前宿主与界面之间只有两条路：
///   · 同步 host object 调用（JS 调 C#，一问一答）—— 页面发起，宿主不能主动说话；
///   · 轮询（`InstallStatus` / `Poll` 每 400ms 一次）—— 能拿到进度，但延迟固定、空转浪费。
/// AI 的流式输出、更新下载进度、长任务阶段变化都需要"宿主主动推"，轮询做不了。
///
/// 机制：`CoreWebView2.PostWebMessageAsJson`（WebView2 原生），JS 侧收在
/// `window.chrome.webview` 的 message 事件上（见 src/lib/push.js）。
///
/// 三个必须遵守的约束：
///   ① **PostWebMessageAsJson 只能在 UI 线程调用** —— 安装/运行都在后台线程，
///      所以这里存一个 Dispatcher，跨线程时 BeginInvoke 回 UI 线程再发；
///   ② **不能抛异常给调用方** —— 推送是"尽力而为"的旁路：页面还没加载完、
///      窗口正在关闭都会失败，这时只记计数与最后一条错误，绝不打断业务逻辑；
///   ③ **信封固定** —— `{topic, seq, ts, payload}`，`seq` 单调递增，便于页面
///      发现丢消息（只关心"变了没有"的场景更简单，见 src/lib/push.js 的说明）。
/// </summary>
public static class PushHub
{
    private static CoreWebView2? _core;
    private static Dispatcher? _ui;
    private static long _seq;
    private static long _sent;
    private static long _failed;
    private static long _attachedAtMs;
    private static volatile string _lastTopic = "";
    private static volatile string _lastError = "";

    public static bool Ready => _core != null;
    public static long Sent => Interlocked.Read(ref _sent);
    public static long Failed => Interlocked.Read(ref _failed);
    public static long Seq => Interlocked.Read(ref _seq);
    public static long AttachedAtMs => Interlocked.Read(ref _attachedAtMs);
    public static string LastTopic => _lastTopic;
    public static string LastError => _lastError;

    /// <summary>在 UI 线程（WebView2 就绪回调里）挂上核心对象</summary>
    public static void Attach(CoreWebView2 core)
    {
        _core = core;
        _ui = Dispatcher.CurrentDispatcher;
        Interlocked.Exchange(ref _attachedAtMs, Environment.TickCount64);
    }

    public static void Detach()
    {
        _core = null;
        _ui = null;
    }

    /// <summary>
    /// 发一条推送。`payloadJson` 必须是**合法的 JSON**（对象/数组/字符串都行），
    /// 传 null 表示没有负载。返回是否已交给 WebView2。
    /// 任何线程都可以调。
    /// </summary>
    public static bool Send(string topic, string? payloadJson = null)
    {
        var core = _core;
        if (core == null)
        {
            Interlocked.Increment(ref _failed);
            _lastError = "推送通道未连接（WebView2 尚未就绪或窗口已关闭）";
            return false;
        }

        long seq = Interlocked.Increment(ref _seq);
        string msg = "{\"topic\":" + Str(topic) +
                     ",\"seq\":" + seq +
                     ",\"ts\":" + DateTimeOffset.Now.ToUnixTimeMilliseconds() +
                     ",\"payload\":" + (string.IsNullOrWhiteSpace(payloadJson) ? "null" : payloadJson) +
                     "}";
        _lastTopic = topic ?? "";

        var ui = _ui;
        if (ui != null && !ui.CheckAccess())
        {
            // 后台线程（安装、运行 Python/C++）走这里：排到 UI 线程再发
            try
            {
                ui.BeginInvoke(new Action(() => Post(core, msg)));
                return true;
            }
            catch (Exception ex)
            {
                Interlocked.Increment(ref _failed);
                _lastError = ex.Message;
                return false;
            }
        }
        return Post(core, msg);
    }

    private static bool Post(CoreWebView2 core, string msg)
    {
        try
        {
            core.PostWebMessageAsJson(msg);
            Interlocked.Increment(ref _sent);
            return true;
        }
        catch (Exception ex)
        {
            // 页面在导航中 / 窗口在关闭时会失败，属正常：记下来即可，不抛
            Interlocked.Increment(ref _failed);
            _lastError = ex.Message;
            return false;
        }
    }

    /// <summary>JSON 字符串字面量（推送里的 topic 与诊断信息都要转义）</summary>
    internal static string Str(string? s)
    {
        if (s == null) return "null";
        var sb = new System.Text.StringBuilder(s.Length + 2);
        sb.Append('"');
        foreach (char c in s)
        {
            switch (c)
            {
                case '"': sb.Append("\\\""); break;
                case '\\': sb.Append("\\\\"); break;
                case '\n': sb.Append("\\n"); break;
                case '\r': sb.Append("\\r"); break;
                case '\t': sb.Append("\\t"); break;
                default:
                    if (c < ' ') sb.Append("\\u").Append(((int)c).ToString("x4"));
                    else sb.Append(c);
                    break;
            }
        }
        sb.Append('"');
        return sb.ToString();
    }
}
