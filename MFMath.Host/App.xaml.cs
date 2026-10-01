using System.IO;
using System.Windows;
using System.Windows.Threading;

namespace MFMath.Host;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        DispatcherUnhandledException += (_, args) =>
        {
            try
            {
                File.AppendAllText(
                    Path.Combine(AppContext.BaseDirectory, "crash.log"),
                    $"[{DateTime.Now:HH:mm:ss}] {args.Exception}\n");
            }
            catch { /* 日志失败忽略 */ }
        };
    }
}
