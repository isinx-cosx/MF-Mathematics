// WindowBridge.cs — 窗口控制桥（JS 顶栏 → WPF 窗口）
//
// 为什么要有它：窗口**不再由 WPF 画标题栏**（见 MainWindow.xaml 的说明），
// 顶部那条真正显示的是 JS UI，于是"拖动/最小化/最大化/关闭"必须能回调到 WPF。
// 这样做的直接好处是整条顶部区域跟随 JS 主题，不会再出现
// "JS 切了深色、顶部还是白的"这种两套外观。
//
// 与 MathBridge 分开注册（JS 里是 window.chrome.webview.hostObjects.sync.win），
// 因为数学能力与窗口外壳是两件事，混在一起会让"引擎桥"承担 UI 职责。
//
// 除了窗口控制，这里还放了**文件对话框**（保存/打开文本文件）：
// 网页侧无法直接读写任意路径，工作区"另存为/从文件打开"必须由宿主出面。
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;
using Microsoft.Win32;

namespace MFMath.Host;

[ComVisible(true)]
public class WindowBridge
{
    // 用系统消息发起拖动，而不是 WPF 的 DragMove()：
    //   · DragMove 不支持 Aero Snap（拖到屏幕边缘不会吸附）；
    //   · 最大化状态下拖拽时，原生行为会先还原窗口再跟随鼠标，
    //     手写状态机很难做对，交给系统最稳。
    private const int WM_NCLBUTTONDOWN = 0x00A1;
    private const int HTCAPTION = 0x0002;

    [DllImport("user32.dll")]
    private static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern bool ReleaseCapture();

    private readonly Window _window;

    public WindowBridge(Window window)
    {
        _window = window;
    }

    /// <summary>
    /// 把操作**投递**到 UI 线程后立即返回。
    ///
    /// 这里刻意不用 Dispatcher.Invoke（同步等待）：
    /// JS 通过 hostObjects.sync 调用本对象时，页面 JS 会一直阻塞到方法返回；
    /// 而"最大化"会改变窗口尺寸 → WebView2 要回调页面处理 resize，
    /// 页面却还卡在等待宿主返回 → 双方互等，直接死锁（实测把整个界面卡住）。
    /// 投递式调用在方法返回后才真正改窗口状态，页面不会持锁等待。
    /// </summary>
    private void Post(Action action)
    {
        _window.Dispatcher.BeginInvoke(new Action(() =>
        {
            try
            {
                action();
            }
            catch (Exception ex)
            {
                // 后台执行无法把异常抛回 JS；记到 stderr 便于排查（不静默）
                Console.Error.WriteLine("[WindowBridge] " + ex.Message);
            }
        }));
    }

    public void Minimize() => Post(() => _window.WindowState = WindowState.Minimized);

    public void ToggleMaximize() => Post(() =>
    {
        _window.WindowState = _window.WindowState == WindowState.Maximized
            ? WindowState.Normal
            : WindowState.Maximized;
    });

    public void Restore() => Post(() =>
    {
        if (_window.WindowState == WindowState.Minimized)
            _window.WindowState = WindowState.Normal;
    });

    /// <summary>只读查询：属性读取不会触发重排，可同步返回。</summary>
    public bool IsMaximized()
    {
        if (_window.Dispatcher.CheckAccess())
            return _window.WindowState == WindowState.Maximized;
        return _window.Dispatcher.Invoke(() => _window.WindowState == WindowState.Maximized);
    }

    public void Close() => Post(() => _window.Close());

    /// <summary>开始拖动窗口（JS 在顶栏空白处 mousedown 时调用）。</summary>
    public void StartDrag() => Post(() =>
    {
        var handle = new WindowInteropHelper(_window).Handle;
        if (handle == IntPtr.Zero) return;
        ReleaseCapture();
        SendMessage(handle, WM_NCLBUTTONDOWN, (IntPtr)HTCAPTION, IntPtr.Zero);
    });

    /// <summary>
    /// 用 JS 当前主题色设置窗口背景。
    /// 窗口背景只在"加载中/缩放/最大化动画"的瞬间可见，但那时露出的白色很扎眼，
    /// 所以让 JS 在切换主题时回设一次。
    /// </summary>
    public void SetChromeBackground(string color)
    {
        if (string.IsNullOrWhiteSpace(color)) return;
        Post(() =>
        {
            try
            {
                var c = (Color)ColorConverter.ConvertFromString(color.Trim());
                _window.Background = new SolidColorBrush(c);
            }
            catch (FormatException)
            {
                // 颜色串非法就保持原背景，不因为一次主题同步失败而改坏窗口
            }
        });
    }

    // ══════════════════════ 文件对话框（文本文件） ══════════════════════
    //
    // 为什么放在宿主：页面里既不能弹系统对话框，也不能写任意路径。
    // 工作区"另存为 / 从文件打开"（以及将来导出图片）都要走这里。
    //
    // 为什么这两个方法**同步**返回、不用 Post：它们要拿到用户的即时选择（确定/取消），
    // 投递式调用只能返回"已投递"。对话框是模态的，阻塞的只是这一次 JS 调用，
    // 不会像 ToggleMaximize 那样和 WebView 的 resize 回调互等。
    //
    // 自动化钩子：`path` 非空时**跳过对话框**直接读写该路径。
    // 只给测试脚本与命令行场景用；正常调用留空即走对话框。

    /// <summary>保存文本到用户选定的文件。返回 {ok,path} / {canceled:true} / {ok:false,error}</summary>
    public string SaveTextFile(string title, string defaultName, string filter, string content, string path)
    {
        try
        {
            string target = path ?? "";
            if (target.Length == 0)
            {
                var dlg = new SaveFileDialog
                {
                    Title = string.IsNullOrWhiteSpace(title) ? "保存" : title,
                    FileName = string.IsNullOrWhiteSpace(defaultName) ? "workspace.mfws.json" : defaultName,
                    Filter = string.IsNullOrWhiteSpace(filter) ? "所有文件 (*.*)|*.*" : filter,
                    AddExtension = true,
                    OverwritePrompt = true,
                };
                bool? ok = _window.Dispatcher.CheckAccess() ? dlg.ShowDialog(_window)
                                                            : _window.Dispatcher.Invoke(() => dlg.ShowDialog(_window));
                if (ok != true) return "{\"canceled\":true}";
                target = dlg.FileName;
            }

            string dir = Path.GetDirectoryName(target) ?? "";
            if (dir.Length > 0) Directory.CreateDirectory(dir);
            // 不带 BOM：JSON 消费方（包括本应用自己）按 UTF-8 读，BOM 只会带来麻烦
            File.WriteAllText(target, content ?? "", new UTF8Encoding(false));
            return "{\"ok\":true,\"path\":" + Json(target) + ",\"bytes\":" + new FileInfo(target).Length + "}";
        }
        catch (Exception ex)
        {
            return "{\"ok\":false,\"error\":" + Json(ex.Message) + "}";
        }
    }

    /// <summary>从用户选定的文件读文本。返回 {ok,path,content} / {canceled:true} / {ok:false,error}</summary>
    public string OpenTextFile(string title, string filter, string path)
    {
        try
        {
            string target = path ?? "";
            if (target.Length == 0)
            {
                var dlg = new OpenFileDialog
                {
                    Title = string.IsNullOrWhiteSpace(title) ? "打开" : title,
                    Filter = string.IsNullOrWhiteSpace(filter) ? "所有文件 (*.*)|*.*" : filter,
                    CheckFileExists = true,
                };
                bool? ok = _window.Dispatcher.CheckAccess() ? dlg.ShowDialog(_window)
                                                            : _window.Dispatcher.Invoke(() => dlg.ShowDialog(_window));
                if (ok != true) return "{\"canceled\":true}";
                target = dlg.FileName;
            }

            if (!File.Exists(target)) return "{\"ok\":false,\"error\":" + Json("文件不存在：" + target) + "}";
            var info = new FileInfo(target);
            if (info.Length > 64L * 1024 * 1024)
                return "{\"ok\":false,\"error\":" + Json("文件过大（>64 MB），拒绝读取：" + target) + "}";
            string text = File.ReadAllText(target, Encoding.UTF8);
            return "{\"ok\":true,\"path\":" + Json(target) + ",\"content\":" + Json(text) + "}";
        }
        catch (Exception ex)
        {
            return "{\"ok\":false,\"error\":" + Json(ex.Message) + "}";
        }
    }

    private static string Json(string? s) => JsonSerializer.Serialize(s ?? "");

    /// <summary>
    /// 保存**二进制**内容到用户选定的文件（导出图片走这条：页面把 canvas 转成
    /// dataURL，去掉 `data:image/png;base64,` 前缀后传进来）。
    ///
    /// 为什么不在页面里直接下载：WebView2 里没有"另存为"，锚点 download 会落到
    /// 默认下载目录且不询问用户；而且这里要能拿到真实路径回显。
    /// 上限 64 MB：正常 2x 位图也就 3-5 MB，超过这个数说明调用方传错了东西。
    /// </summary>
    public string SaveBinaryFile(string title, string defaultName, string filter, string base64, string path)
    {
        try
        {
            string data = (base64 ?? "").Trim();
            int comma = data.IndexOf(',');
            if (data.StartsWith("data:", StringComparison.OrdinalIgnoreCase) && comma > 0)
                data = data.Substring(comma + 1);          // 允许直接把 dataURL 传进来
            if (data.Length == 0) return "{\"ok\":false,\"error\":" + Json("内容为空") + "}";

            byte[] bytes;
            try { bytes = Convert.FromBase64String(data); }
            catch (FormatException) { return "{\"ok\":false,\"error\":" + Json("base64 内容不合法") + "}"; }
            if (bytes.Length > 64L * 1024 * 1024)
                return "{\"ok\":false,\"error\":" + Json("内容过大（>64 MB），拒绝保存") + "}";

            string target = path ?? "";
            if (target.Length == 0)
            {
                var dlg = new SaveFileDialog
                {
                    Title = string.IsNullOrWhiteSpace(title) ? "保存" : title,
                    FileName = string.IsNullOrWhiteSpace(defaultName) ? "image.png" : defaultName,
                    Filter = string.IsNullOrWhiteSpace(filter) ? "所有文件 (*.*)|*.*" : filter,
                    AddExtension = true,
                    OverwritePrompt = true,
                };
                bool? ok = _window.Dispatcher.CheckAccess() ? dlg.ShowDialog(_window)
                                                            : _window.Dispatcher.Invoke(() => dlg.ShowDialog(_window));
                if (ok != true) return "{\"canceled\":true}";
                target = dlg.FileName;
            }

            string dir = Path.GetDirectoryName(target) ?? "";
            if (dir.Length > 0) Directory.CreateDirectory(dir);
            File.WriteAllBytes(target, bytes);
            return "{\"ok\":true,\"path\":" + Json(target) + ",\"bytes\":" + bytes.Length + "}";
        }
        catch (Exception ex)
        {
            return "{\"ok\":false,\"error\":" + Json(ex.Message) + "}";
        }
    }
}
