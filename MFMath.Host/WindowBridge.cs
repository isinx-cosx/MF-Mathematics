// WindowBridge.cs — 窗口控制桥（JS 顶栏 → WPF 窗口）
//
// 为什么要有它：窗口**不再由 WPF 画标题栏**（见 MainWindow.xaml 的说明），
// 顶部那条真正显示的是 JS UI，于是"拖动/最小化/最大化/关闭"必须能回调到 WPF。
// 这样做的直接好处是整条顶部区域跟随 JS 主题，不会再出现
// "JS 切了深色、顶部还是白的"这种两套外观。
//
// 与 MathBridge 分开注册（JS 里是 window.chrome.webview.hostObjects.sync.win），
// 因为数学能力与窗口外壳是两件事，混在一起会让"引擎桥"承担 UI 职责。
using System;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;

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
}
