using System;
using System.Threading.Tasks;
using System.Windows;

namespace MFMath.Host;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        Log.Info("启动；程序目录 " + AppContext.BaseDirectory);

        // ① WPF UI 线程的未处理异常（最常见的一类）
        DispatcherUnhandledException += (_, args) =>
        {
            string? path = Log.Crash("UI 线程", args.Exception);
            // 记录之后**让程序继续跑**：这是个工具型应用，用户可能刚算到一半；
            // 工作区有自动保存，随时可以重启，而"继续跑 + 告诉他日志在哪"比直接消失友好得多。
            args.Handled = true;
            Notify(args.Exception, path);
        };

        // ② 非 UI 线程的未处理异常：进程随后就会终止，能做的只有把现场完整留下来
        AppDomain.CurrentDomain.UnhandledException += (_, args) =>
        {
            if (args.ExceptionObject is Exception ex)
            {
                Log.Crash("非 UI 线程" + (args.IsTerminating ? "（致命）" : ""), ex);
            }
            else
            {
                Log.Crash("非 UI 线程",
                    new InvalidOperationException("非 Exception 的异常对象: " + args.ExceptionObject));
            }
        };

        // ③ 未观察的 Task 异常：.NET 默认会在 GC 时把进程终结掉。
        //    记下来并 SetObserved()，等于把这类"看不见的崩溃"变成"有记录但不致命"。
        TaskScheduler.UnobservedTaskException += (_, args) =>
        {
            Log.Crash("未观察的 Task 异常", args.Exception);
            args.SetObserved();
        };

        // 启动/退出各留一行：崩溃时间戳夹在这两行之间，一眼能定位是哪个阶段出的问题
        Exit += (_, _) => Log.Info("退出");
    }

    /// <summary>把"出错了、日志在哪"告诉用户 —— 一个不告诉用户日志位置的崩溃处理等于没有。</summary>
    private static void Notify(Exception ex, string? path)
    {
        try
        {
            string where = path is null
                ? "但崩溃日志**写入失败**（请检查磁盘权限）。"
                : "已写入崩溃日志：\n" + path
                  + "\n\n也可以在「设置 → 存储与数据 → 导出诊断包」里一并导出后发出来。";

            MessageBox.Show(
                "程序遇到了一个内部错误，已记录，且**没有**丢失你的工作区。\n\n"
                + ex.GetType().Name + ": " + ex.Message + "\n\n" + where,
                "MF-Mathematics 已记录一个错误",
                MessageBoxButton.OK, MessageBoxImage.Warning);
        }
        catch
        {
            // 连弹窗都失败就算了（例如崩溃发生在对话框还不可用的时机）
        }
    }
}
