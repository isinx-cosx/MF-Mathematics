using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;

namespace MFMath.Host;

/// <summary>
/// 宿主日志与崩溃记录（D3）。
///
/// **为什么要重做**：原先只有 App.xaml.cs 里一个 DispatcherUnhandledException 处理器，
/// 把异常 append 到 <c>AppContext.BaseDirectory\crash.log</c>。两处硬伤让它基本等于没有：
///   ① 只覆盖 WPF **UI 线程** —— 非 UI 线程异常、Task 未观察异常、引擎 DLL 加载失败全都抓不到；
///   ② 安装目录（Program Files 或部署目录）通常**不可写**，写失败又被 <c>catch { }</c> 吞掉 →
///      多数机器上崩溃之后什么都没留下。
///
/// **现在的策略**：
///   · 日志写到 <c>%LOCALAPPDATA%\MFMath\logs</c>（一定可写），带大小轮转，不会无限增长；
///   · 崩溃另写 <c>crash-*.log</c>：环境 + **完整异常链** + 最近的 app.log 尾部 —— 单文件即可复盘；
///   · 崩溃日志纳入「设置 → 导出诊断包」，用户点一下就能把它发出来，不必去翻目录；
///   · **不联网上报**：数学工具的用户不该因为一次崩溃就被上传任何东西。
///
/// 日志本身永远不许影响主流程：所有写入都包在 try/catch 里，失败即静默返回。
/// </summary>
internal static class Log
{
    private const long MaxBytes = 2 * 1024 * 1024;   // 单个 app.log 上限 2 MB
    private const int KeepCrashFiles = 20;           // 崩溃日志只留最近 20 个
    private const int CrashTailLines = 200;          // 崩溃日志里附带多少行 app.log 尾部

    private static readonly object Gate = new();

    /// <summary>日志目录（一定可写；诊断导出与"日志在哪"提示都用它）</summary>
    public static string Dir { get; } = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "MFMath", "logs");

    private static string AppLogPath => Path.Combine(Dir, "app.log");

    public static void Info(string msg) => Write("INFO ", msg);
    public static void Warn(string msg) => Write("WARN ", msg);
    public static void Error(string msg) => Write("ERROR", msg);

    private static void Write(string level, string msg)
    {
        try
        {
            lock (Gate)
            {
                Directory.CreateDirectory(Dir);
                Rotate();
                File.AppendAllText(
                    AppLogPath,
                    $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff}] [{level}] {msg}{Environment.NewLine}",
                    new UTF8Encoding(false));
            }
        }
        catch
        {
            // 日志失败绝不能影响主流程
        }
    }

    /// <summary>只保留一代历史（app.1.log），避免无限增长</summary>
    private static void Rotate()
    {
        try
        {
            var fi = new FileInfo(AppLogPath);
            if (!fi.Exists || fi.Length < MaxBytes) return;
            string prev = Path.Combine(Dir, "app.1.log");
            File.Delete(prev);
            File.Move(AppLogPath, prev);
        }
        catch
        {
            // 轮转失败不影响后续 append（大不了文件大一点）
        }
    }

    /// <summary>
    /// 记录一次崩溃，返回崩溃日志的完整路径（写失败返回 null）。
    /// </summary>
    public static string? Crash(string source, Exception ex)
    {
        try
        {
            lock (Gate)
            {
                Directory.CreateDirectory(Dir);
                string path = Path.Combine(Dir, "crash-" + DateTime.Now.ToString("yyyyMMdd-HHmmss", CultureInfo.InvariantCulture) + ".log");

                var sb = new StringBuilder();
                sb.AppendLine("MF-Mathematics 崩溃记录");
                sb.AppendLine("时间    : " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture));
                sb.AppendLine("来源    : " + source);
                sb.AppendLine("版本    : " + AppVersion());
                sb.AppendLine("系统    : " + Environment.OSVersion
                              + " / .NET " + Environment.Version
                              + " / " + (Environment.Is64BitProcess ? "x64" : "x86"));
                sb.AppendLine("程序目录: " + AppContext.BaseDirectory);
                sb.AppendLine("日志目录: " + Dir);
                sb.AppendLine();

                sb.AppendLine("== 异常链 ==");
                int depth = 0;
                for (Exception? e = ex; e is not null && depth < 10; e = e.InnerException, depth++)
                {
                    sb.AppendLine("-- [" + depth + "] " + e.GetType().FullName + ": " + e.Message);
                    if (e is AggregateException agg)
                    {
                        foreach (Exception inner in agg.InnerExceptions)
                            sb.AppendLine("     · 聚合成员 " + inner.GetType().Name + ": " + inner.Message);
                    }
                    sb.AppendLine(e.StackTrace);
                    sb.AppendLine();
                }

                sb.AppendLine("== 最近日志（app.log 尾部 " + CrashTailLines + " 行）==");
                sb.AppendLine(Tail(AppLogPath, CrashTailLines));

                File.WriteAllText(path, sb.ToString(), new UTF8Encoding(false));
                PruneCrashes();
                return path;
            }
        }
        catch
        {
            return null;
        }
    }

    /// <summary>读文件尾部若干行（文件很大时只读尾部 256 KB，避免把内存吃满）</summary>
    public static string Tail(string path, int lines)
    {
        try
        {
            if (!File.Exists(path)) return "(无日志)";
            const int chunk = 256 * 1024;
            using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
            long start = Math.Max(0, fs.Length - chunk);
            fs.Seek(start, SeekOrigin.Begin);
            byte[] buf = new byte[fs.Length - start];
            int read = fs.Read(buf, 0, buf.Length);
            string text = Encoding.UTF8.GetString(buf, 0, read);
            var all = text.Replace("\r\n", "\n").Split('\n');
            return string.Join(Environment.NewLine, all.Skip(Math.Max(0, all.Length - lines)));
        }
        catch (Exception e)
        {
            return "(读取日志失败: " + e.Message + ")";
        }
    }

    private static void PruneCrashes()
    {
        try
        {
            var files = new DirectoryInfo(Dir).GetFiles("crash-*.log")
                .OrderByDescending(f => f.Name)
                .Skip(KeepCrashFiles);
            foreach (var f in files)
            {
                try { f.Delete(); } catch { }
            }
        }
        catch
        {
            // 清理失败无所谓
        }
    }

    private static string AppVersion()
    {
        try
        {
            Assembly asm = Assembly.GetEntryAssembly() ?? Assembly.GetExecutingAssembly();
            return asm.GetName().Version?.ToString() ?? "(未知)";
        }
        catch
        {
            return "(未知)";
        }
    }
}
