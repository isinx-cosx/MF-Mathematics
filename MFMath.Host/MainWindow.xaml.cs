using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using Microsoft.Web.WebView2.Core;

namespace MFMath.Host;

public partial class MainWindow : Window
{
    // ── 窗口圆角与投影（Windows 11 的 DWM 属性；Win10 上调用会失败，忽略即可）──
    private const int DWMWA_USE_IMMERSIVE_DARK_MODE = 20;   // Win10 1903+
    private const int DWMWA_WINDOW_CORNER_PREFERENCE = 33;  // Win11
    private const int DWMWA_NCRENDERING_POLICY = 2;
    private const int DWMWA_BORDER_COLOR = 34;              // Win11
    private const int DWMWCP_ROUND = 2;
    private const int DWMNCRP_ENABLED = 2;

    /// <summary>WebView2 的用户数据目录（构造时确定）。
    /// 之所以要存成字段：初始化失败时必须能把它写进日志/提示里 ——
    /// "目录不可写" 与 "有另一个进程占着它" 是两类最常见的原因，只说"WebView 失败"等于没说。</summary>
    private readonly string _webViewUserData = "";

    [DllImport("dwmapi.dll", PreserveSig = true)]
    private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int value, int size);

    public MainWindow()
    {
        InitializeComponent();

        // WebView2 的用户数据目录（缓存 / Local Storage / 登录态）必须显式指定。
        //
        // 不指定时它默认建在 **exe 旁边**（<exe名>.WebView2\），这在正式安装下有两个真问题：
        //   ① 正式安装是装到 %ProgramFiles%\MF-Mathematics\，普通用户对那里**没有写权限**，
        //      于是浏览器数据写不进去，WebView2 初始化可能直接失败（表现为白屏）；
        //   ② 那 100 MB 上下的数据长在安装目录里，卸载程序不会删（它只删自己装的文件），
        //      卸载后留下 199 个文件——这条是实测出来的（scripts\verify-installer.ps1）。
        // 放到 %LOCALAPPDATA%\MFMath\WebView2 就都解决了：用户一定有写权限，
        // 而且和组件缓存（components\）在同一处，卸载时按用户处理有统一说法。
        // 用户数据目录可以用 MF_WEBVIEW2_DIR 覆盖：多个宿主实例并行跑自动化测试时，
        // WebView2 不允许两个进程共用同一个用户数据目录，各给一个临时目录即可互不干扰。
        _webViewUserData = Environment.GetEnvironmentVariable("MF_WEBVIEW2_DIR") is { Length: > 0 } ov
            ? ov
            : Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "MFMath", "WebView2");
        // 这一步也会失败（目录被占用 / 无写权限 / 路径被写成了文件），
        // 而它失败时 WebView2 连初始化都不会开始 —— 同样必须留下记录，不能再静默。
        try
        {
            Directory.CreateDirectory(_webViewUserData);
        }
        catch (Exception e)
        {
            Log.Crash("WebView2 用户数据目录", e);
            Log.Error("无法创建 WebView2 用户数据目录：" + _webViewUserData + " → " + e.GetType().Name + ": " + e.Message);
            MessageBox.Show(
                "无法创建 WebView2 的用户数据目录，界面将无法加载。\n\n"
                + _webViewUserData + "\n\n" + e.GetType().Name + ": " + e.Message,
                "MF-Mathematics 界面无法加载", MessageBoxButton.OK, MessageBoxImage.Error);
            return;
        }
        // 写全名：这个类是 WPF 专用类型，在 Microsoft.Web.WebView2.Wpf 命名空间下
        Browser.CreationProperties = new Microsoft.Web.WebView2.Wpf.CoreWebView2CreationProperties
        {
            UserDataFolder = _webViewUserData,
        };

        Browser.CoreWebView2InitializationCompleted += OnWebViewReady;
        // 句柄一就绪就设置 DWM 圆角/投影，避免先闪一下直角
        SourceInitialized += OnSourceInitialized;

#if DEBUG
        // 开发模式：指向 Vite dev server（需先在 MFMath.UI.Vue 下 npm run dev，支持热更新）
        Browser.Source = new Uri("http://127.0.0.1:5173/");
#else
        // 发布模式：先用 about:blank 触发 WebView2 初始化，Ready 后再映射虚拟主机导航
        Browser.Source = new Uri("about:blank");
#endif
    }

    /// <summary>
    /// 无边框窗口默认是**直角且没有投影**（WindowStyle=None 会丢掉 DWM 的边框渲染），
    /// 于是窗口看起来像一块贴死的方块，跟 UI 内的圆角面板不搭。
    /// 这里用 DWM 属性补回：
    ///   · DWMWA_WINDOW_CORNER_PREFERENCE = ROUND  → Windows 11 的原生圆角
    ///   · DWMWA_NCRENDERING_POLICY = ENABLED      → 让 DWM 重新绘制投影
    /// 两项都是 Win11 才有的属性，在 Win10 上返回非 0，静默忽略即可——
    /// 圆角会缺失，但 UI 内部的圆角面板仍然成立，不会出现布局问题。
    /// </summary>
    private void OnSourceInitialized(object? sender, EventArgs e)
    {
        var hwnd = new WindowInteropHelper(this).Handle;
        if (hwnd == IntPtr.Zero) return;

        int round = DWMWCP_ROUND;
        DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ref round, sizeof(int));

        int nc = DWMNCRP_ENABLED;
        DwmSetWindowAttribute(hwnd, DWMWA_NCRENDERING_POLICY, ref nc, sizeof(int));
    }

    private void OnWebViewReady(object? sender, CoreWebView2InitializationCompletedEventArgs e)
    {
        /* ⚠ 原实现只有一句 `if (!e.IsSuccess) return;` —— 初始化失败被**静默吞掉**：
         * 用户看到"窗口一片空白、日志里一行都没有"，而 WebView2 的真实原因
         * （Runtime 缺失 / 用户数据目录不可写或损坏 / WebView2Loader.dll 位数不符 /
         *   有另一个 MFMath·msedgewebview2 进程占着同一个用户数据目录）
         * 全在 e.InitializationException 里。这里再不记，就等于把唯一的线索扔掉。 */
        if (!e.IsSuccess)
        {
            Exception ex = e.InitializationException
                           ?? new InvalidOperationException("WebView2 初始化失败（未提供异常对象）");
            string? crashPath = Log.Crash("WebView2 初始化", ex);
            Log.Error("WebView2 初始化失败；用户数据目录 " + _webViewUserData
                      + "；" + ex.GetType().Name + ": " + ex.Message);
            try
            {
                MessageBox.Show(
                    "WebView2 初始化失败，界面无法加载。\n\n"
                    + ex.GetType().Name + ": " + ex.Message
                    + "\n\n用户数据目录：\n" + _webViewUserData
                    + "\n\n崩溃日志：" + (crashPath ?? "写入失败（请检查磁盘权限）")
                    + "\n\n常见原因：\n"
                    + "① 有另一个 MFMath.exe / msedgewebview2.exe 占着同一个用户数据目录"
                    + "（WebView2 不允许两个进程共用）：把进程全部结束后重开；\n"
                    + "② 该目录不可写或已损坏（可改名或删除后重启，数据目录会重建）；\n"
                    + "③ 缺 WebView2 Runtime，或 WebView2Loader.dll 与进程位数不符。",
                    "MF-Mathematics 界面无法加载", MessageBoxButton.OK, MessageBoxImage.Error);
            }
            catch { /* 连弹窗都失败就算了（例如窗口还不可用） */ }
            return;
        }
        // 成功也记一行：这样"日志里有没有这一行"就能直接区分
        // 「WebView 起来了但页面空」和「WebView 根本没起来」——这两类问题的排查方向完全不同。
        Log.Info("WebView2 就绪：" + Browser.CoreWebView2.Environment.BrowserVersionString
                 + "；用户数据目录 " + _webViewUserData);

        // 引擎桥（数学计算）、窗口桥（外壳控制）、控制台桥（跑用户代码）、设置桥（文件与系统信息）
        // 分开注册：JS 侧分别是 hostObjects.sync.mf / .win / .con / .sys。
        Browser.CoreWebView2.AddHostObjectToScript("mf", new MathBridge());
        Browser.CoreWebView2.AddHostObjectToScript("win", new WindowBridge(this));
        // 前端日志桥（hostObjects.sync.diag）：把渲染进程里捕获到的 JS 异常
        // 写进宿主的 app.log。没有它，WebView2 里的异常宿主一条都看不到，
        // 用户遇到的就是"点了没反应"且日志空白。
        Browser.CoreWebView2.AddHostObjectToScript("diag", new LogBridge());
        ConsoleBridge console = new ConsoleBridge();
        Browser.CoreWebView2.AddHostObjectToScript("con", console);
        // 设置面板：报路径、查依赖 DLL 在不在、读写设置 JSON、打开目录、导出诊断包。
        // 放独立桥是因为它只做"文件与系统信息"，不含数学/窗口/进程，加设置项也不会撑大另外三个。
        Browser.CoreWebView2.AddHostObjectToScript("sys", new SettingsBridge());
        // 推送通道（宿主 → 页面）：挂上 CoreWebView2 后，任何线程都能
        // PushHub.Send(topic, payload) 主动给界面发消息（组件安装进度、控制台运行结束…）。
        // 暴露给 JS 的 `push` 桥只用于诊断与自测，业务消息不经过它。
        PushHub.Attach(Browser.CoreWebView2);
        Browser.CoreWebView2.AddHostObjectToScript("push", new PushBridge());
        // AI 助手：密钥只留在宿主（DPAPI 密文），流式经推送通道回页面。
        // 放独立桥是因为它只做"传输 + 密钥"：页面负责组装消息与渲染，宿主不猜内容。
        AiBridge ai = new AiBridge();
        Browser.CoreWebView2.AddHostObjectToScript("ai", ai);
        // 联网搜索：凭据（Wolfram App ID）与网络都在宿主，结果经推送通道回页面。
        // 与 AI 同源的理由：页面直连会撞 CORS，而 App ID 不该进渲染进程。
        SearchBridge search = new SearchBridge();
        Browser.CoreWebView2.AddHostObjectToScript("search", search);
        // 用户系统：与站点（https://mf-vis-science.cn）的账号接口对接。
        // token 只存宿主（DPAPI 密文）；**未登录/断网都不影响任何计算功能**（计算全在本地引擎）。
        AccountBridge account = new AccountBridge();
        Browser.CoreWebView2.AddHostObjectToScript("account", account);
        // 更新链：只查版本、显示校验值、把下载页交给浏览器。
        // **不自动下载、不执行安装包** —— 少一条"下载并运行可执行文件"的通路。
        UpdateBridge update = new UpdateBridge();
        Browser.CoreWebView2.AddHostObjectToScript("update", update);
        // 关窗时把控制台里还活着的子进程带走，不留孤儿；在跑的 AI / 搜索请求也一并取消
        // （否则后台 Task 会拽着一个 HTTP 连接，窗口关了但进程不退出）
        Closed += (_, _) =>
        {
            try { console.StopAll(); } catch { }
            try { ai.CancelAll(); } catch { }
            try { search.CancelAll(); } catch { }
            try { account.CancelAll(); } catch { }
            try { update.CancelAll(); } catch { }
            PushHub.Detach();
        };

#if !DEBUG
        // 发布模式：wwwroot = Vue 构建产物拷贝
        // ESM 脚本经 file:// 会被 CORS 拦截，因此映射虚拟主机 mfmath.local → wwwroot
        string uiDir = Path.Combine(AppContext.BaseDirectory, "wwwroot");
        Browser.CoreWebView2.SetVirtualHostNameToFolderMapping(
            "mfmath.local", uiDir, CoreWebView2HostResourceAccessKind.Allow);
        Browser.Source = new Uri("https://mfmath.local/index.html");
#endif
    }
}
