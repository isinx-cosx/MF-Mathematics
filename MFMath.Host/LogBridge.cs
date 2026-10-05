namespace MFMath.Host;

/// <summary>
/// 渲染进程 → 宿主日志的桥（注册为 <c>window.chrome.webview.hostObjects.sync.diag</c>）。
///
/// **为什么需要它**：宿主侧（C#）的异常本来就有完整记录（见 <see cref="Log"/> 与 App.xaml.cs），
/// 但 **WebView2 里的 JS 异常宿主完全看不到** —— 前端抛一个未捕获异常，用户那边可能只是
/// "点了没反应"或白屏，而 app.log 里一条线索都没有，于是只能靠猜。
/// 这个桥把前端捕获到的异常写进**同一个** app.log，两边终于对得上时间线。
///
/// 只做一件事：把一行文本写进日志。不做上报、不联网、不做任何决策。
/// </summary>
public class LogBridge
{
    /// <summary>JS 调用：hostObjects.sync.diag.front(level, message)</summary>
    public void Front(string level, string message)
    {
        string text = "[前端] " + (message ?? "");
        switch ((level ?? "").Trim().ToUpperInvariant())
        {
            case "WARN":
                Log.Warn(text);
                break;
            case "INFO":
                Log.Info(text);
                break;
            default:
                Log.Error(text);
                break;
        }
    }
}
