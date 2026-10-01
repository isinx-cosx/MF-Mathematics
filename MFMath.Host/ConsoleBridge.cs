// ConsoleBridge.cs — 控制台桥（JS 侧：hostObjects.sync.con）
//
// 职责：把"跑一段用户代码"这件事放在宿主侧做（进程、文件、组件），而不是浏览器里。
//   · 组件管理：CPython（嵌入式）与 MinGW（A 档）都是**可选下载**的能力包，
//     装到 %LOCALAPPDATA%\MFMath\components\ 下（用户目录可写，不污染安装目录）
//   · 运行：把代码落成临时文件 → 起子进程 → 异步收 stdout/stderr → 轮询取回
//
// 为什么用"开始 + 轮询"而不是同步返回：
//   JS 走 hostObjects.sync 调用时页面会一直阻塞到方法返回；控制台可能跑几十秒，
//   同步返回会把界面锁死（窗口桥那边已经踩过一次死锁，见 WindowBridge 的注释）。
//   所以 Start 立即返回 runId，输出用 Poll 增量取。
//
// 与引擎的关系：Python 通过同目录的 mfmath.py（ctypes → mf_mathematics.dll）调引擎，
// C++ 侧则链接引擎的导入库；**计算始终由 C++ 引擎完成**，Python/C++ 只做编排。
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace MFMath.Host;

[ComVisible(true)]
public class ConsoleBridge
{
    // ── 路径 ──
    private static string AppDir => AppContext.BaseDirectory;
    private static string ComponentsRoot =>
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "MFMath", "components");
    private static string CacheDir => Path.Combine(ComponentsRoot, "cache");
    private static string ScratchRoot =>
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "MFMath", "console");

    // 组件清单：版本写在目录名里，便于将来并存/回滚
    private const string PythonVersion = "3.13.15";
    private const string PythonPayloadName = "python-3.13.15-embed-amd64.zip";
    private const string CppVersion = "16.1.0";
    private const string CppPayloadName = "mingw-16.1.0-x86_64-seh.zip";
    /// <summary>导入库用的 .def：引擎的 C ABI 就这两个入口，不依赖 gendef。</summary>
    private const string CppDefText = "LIBRARY mf_mathematics.dll\r\nEXPORTS\r\n    function_exists\r\n    math_call\r\n";

    // ── 组件包校验 ──
    // 组件包是几十 MB 的下载物，传输截断、被中间盒改写、放到一半的临时文件都很常见，
    // 而解压出错时给出的报错（"解压后没有 python.exe"）根本指不到真正的原因。
    // 所以安装前先对整包做一次 SHA-256。
    //
    // 想换一份自己构建的包时**不用改代码**：在被校验文件旁边放一个同名 .sha256
    // 文本文件（内容就是十六进制摘要，允许写成 "<hash>  <filename>" 的 sha256sum 格式），
    // 有旁文件就以旁文件为准。
    private const string PythonPayloadSha256 = "D1F04D990AEE1253D8569E8E5104E30FA9F5FA830899F14843448872D936A2CF";
    private const string CppPayloadSha256 = "64AAC3C5FDB16B5A18AE868EA477FE40C798A1581B5B335AB8F0E30A2A10B76B";
    /// <summary>组件包的标准大小：界面据此告诉用户"点安装要下多大的东西"</summary>
    private const long PythonPayloadBytes = 11009825;
    private const long CppPayloadBytes = 54084880;

    private static string PythonDir => Path.Combine(ComponentsRoot, "python-" + PythonVersion);
    private static string CppDir => Path.Combine(ComponentsRoot, "mingw-" + CppVersion);

    private const int MaxOutputBytes = 256 * 1024;   // 单流输出上限，防止刷屏把内存打爆
    private const int DefaultTimeoutSec = 60;
    private const int CompileTimeoutSec = 120;        // C++ 首次编译要跑 cc1plus + ld

    // ── 运行中的任务 ──
    private sealed class Run
    {
        public Process? Proc;
        public readonly StringBuilder Out = new();
        public readonly StringBuilder Err = new();
        // queued → running → done：Poll 必须能区分"还没起来"和"已结束"，
        // 否则客户端第一次轮询就以为跑完了（实测踩过）。
        public volatile string State = "queued";
        // C++ 比 Python 多一个「编译」阶段，界面要能说清是在编译还是在跑
        public volatile string Stage = "queued";   // queued | compiling | running | done
        public long CompileMs = -1;
        public int ExitCode = int.MinValue;
        public bool TimedOut;
        public long StartedMs;
        public string Language = "";
        public string Dir = "";
        public int TimedOutAfterSec;
    }

    private sealed class Job
    {
        public string State = "running";   // running | done | error
        public string Message = "";
        public int Percent;
    }

    private readonly ConcurrentDictionary<string, Run> _runs = new();
    private readonly ConcurrentDictionary<string, Job> _jobs = new();
    /// <summary>安装/下载任务的取消源：取消后保留 .part，下次能续传</summary>
    private readonly ConcurrentDictionary<string, CancellationTokenSource> _jobCancels = new();
    private int _seq;

    // ══════════════════════════ 组件状态 ══════════════════════════

    /// <summary>
    /// 组件状态（JSON）。JS 用它决定语言下拉里显示什么：
    /// C++ 在组件装好之前**不出现**在选项里（默认隐藏）。
    /// </summary>
    public string Components()
    {
        var sb = new StringBuilder();
        sb.Append("{\"engineDir\":").Append(Json(AppDir));
        sb.Append(",\"componentsRoot\":").Append(Json(ComponentsRoot));
        sb.Append(",\"downloadBase\":").Append(Json(ComponentDownload.BaseUrl));
        sb.Append(",\"python\":").Append(PythonStatus());
        sb.Append(",\"cpp\":").Append(CppStatus());
        sb.Append('}');
        return sb.ToString();
    }

    /// <summary>
    /// 换组件下载源。默认走官网；企业内网镜像或本地测试可以指到别处。
    /// 做成运行时可设，是免得为"换个镜像"重新编译。
    /// </summary>
    public string SetDownloadBase(string url)
    {
        ComponentDownload.SetBaseUrl(url);
        return "{\"base\":" + Json(ComponentDownload.BaseUrl) + "}";
    }

    /// <summary>
    /// 把「组件包还没下载」这件事准备好：先下载（带断点续传），再交给安装。
    /// 下载完成前不会碰组件目录，所以中途失败不会留下半装状态。
    /// </summary>
    private string EnsurePayload(string componentName, string fileName, string builtInSha, Job job,
                                 CancellationToken ct)
    {
        string? existing = FindPayload(fileName);
        if (existing != null) return existing;

        job.Message = "开始下载组件包…";
        job.Percent = 0;
        var r = ComponentDownload.Download(
            componentName, fileName, CacheDir,
            (pct, msg) => { job.Percent = pct * 9 / 10; job.Message = msg; },
            (line) => { job.Message = line; },
            ct);
        return r.Path;
    }

    /// <summary>缓存里已有的组件包大小（字节）。用于进度显示与"是否还需要下载"的判断。</summary>
    private static (bool available, long bytes, bool partial) PayloadState(string fileName)
    {
        string? p = FindPayload(fileName);
        if (p != null)
        {
            try { return (true, new FileInfo(p).Length, false); } catch { return (true, 0, false); }
        }
        // 半成品也算"有"：界面要能告诉用户"上次下到一半，点安装会接着下"
        string part = Path.Combine(CacheDir, fileName + ".part");
        if (File.Exists(part))
        {
            try { return (false, new FileInfo(part).Length, true); } catch { /* 忽略 */ }
        }
        return (false, 0, false);
    }

    private string PythonStatus()
    {
        string exe = Path.Combine(PythonDir, "python.exe");
        bool installed = File.Exists(exe) && File.Exists(Path.Combine(PythonDir, "mfmath.py"));
        long bytes = installed ? DirSize(PythonDir) : 0;
        var (payload, payloadBytes, partial) = PayloadState(PythonPayloadName);
        return "{\"installed\":" + (installed ? "true" : "false") +
               ",\"version\":" + Json(PythonVersion) +
               ",\"path\":" + Json(PythonDir) +
               ",\"bytes\":" + bytes +
               ",\"payloadAvailable\":" + (payload ? "true" : "false") +
               ",\"payloadBytes\":" + payloadBytes +
               ",\"payloadPartial\":" + (partial ? "true" : "false") +
               ",\"expectBytes\":" + PythonPayloadBytes +
               ",\"payloadName\":" + Json(PythonPayloadName) +
               ",\"warning\":" + Json(installed && !File.Exists(Path.Combine(PythonDir, "mfmath.py"))
                   ? "缺少 mfmath.py（引擎门面），请重新安装组件" : "") + "}";
    }

    private string CppStatus()
    {
        string gpp = Path.Combine(CppDir, "bin", "g++.exe");
        bool installed = File.Exists(gpp);
        long bytes = installed ? DirSize(CppDir) : 0;
        var (payload, payloadBytes, partial) = PayloadState(CppPayloadName);
        // 装好工具链还不够：导入库和门面头文件是"能调用引擎"的前提
        bool hasLib = File.Exists(Path.Combine(CppDir, "lib", "libmf_mathematics.a"));
        bool hasHeader = File.Exists(Path.Combine(CppDir, "include", "mfmath.hpp"));
        string warning = "";
        if (installed && (!hasLib || !hasHeader))
            warning = "C++ 组件不完整（缺导入库或门面头文件），请重新安装";
        else if (!installed)
            warning = "C++ 组件（MinGW A 档）未安装：装上后语言里会自动出现 C++";
        return "{\"installed\":" + (installed ? "true" : "false") +
               ",\"version\":" + Json(CppVersion) +
               ",\"path\":" + Json(CppDir) +
               ",\"bytes\":" + bytes +
               ",\"ready\":" + (installed && hasLib && hasHeader ? "true" : "false") +
               ",\"payloadAvailable\":" + (payload ? "true" : "false") +
               ",\"payloadBytes\":" + payloadBytes +
               ",\"payloadPartial\":" + (partial ? "true" : "false") +
               ",\"expectBytes\":" + CppPayloadBytes +
               ",\"payloadName\":" + Json(CppPayloadName) +
               ",\"warning\":" + Json(warning) + "}";
    }

    private static string? FindPayload(string fileName)
    {
        Directory.CreateDirectory(CacheDir);
        var candidates = new[]
        {
            Path.Combine(CacheDir, fileName),
            Path.Combine(AppDir, "components", fileName),
        };
        return candidates.FirstOrDefault(File.Exists);
    }

    /// <summary>
    /// 校验组件包完整性。当前返回期望的摘要（都是大写十六进制，不含空格）。
    /// 有同名 .sha256 旁文件时以旁文件为准，这样换自建包不必改代码。
    /// </summary>
    private static string ExpectedSha256(string payloadPath, string builtIn)
    {
        string side = payloadPath + ".sha256";
        if (File.Exists(side))
        {
            try
            {
                // 兼容 "hash" 与 "hash  filename" 两种写法
                string text = File.ReadAllText(side).Trim();
                string first = text.Split(new[] { ' ', '\t', '\r', '\n' },
                                          StringSplitOptions.RemoveEmptyEntries)[0];
                if (first.Length == 64) return first.ToUpperInvariant();
            }
            catch { /* 旁文件坏了就退回内置摘要 */ }
        }
        return builtIn;
    }

    private static string Sha256Of(string path)
    {
        using var sha = System.Security.Cryptography.SHA256.Create();
        using var fs = File.OpenRead(path);
        return Convert.ToHexString(sha.ComputeHash(fs));
    }

    /// <summary>校验失败就抛异常（消息里带上期望值与实际值，便于用户判断是哪种坏）。</summary>
    private static void VerifyPayload(string payloadPath, string builtIn, Job job)
    {
        string want = ExpectedSha256(payloadPath, builtIn);
        long bytes = new FileInfo(payloadPath).Length;
        job.Message = "校验组件包完整性（" + (bytes / 1024 / 1024) + " MB）…";
        job.Percent = 8;
        string actual = Sha256Of(payloadPath);
        if (actual != want)
            throw new InvalidOperationException(
                "组件包校验失败，可能没有下载完整或已损坏。\n" +
                "文件：" + payloadPath + "\n" +
                "期望 SHA-256：" + want + "\n" +
                "实际 SHA-256：" + actual + "\n" +
                "请删除该文件后重新下载。");
    }

    private static long DirSize(string dir)
    {
        try
        {
            return new DirectoryInfo(dir).EnumerateFiles("*", SearchOption.AllDirectories).Sum(f => f.Length);
        }
        catch
        {
            return 0;
        }
    }

    // ══════════════════════════ 安装 ══════════════════════════

    /// <summary>
    /// 开始安装组件（后台）。返回 jobId，用 InstallStatus 轮询。
    ///
    /// 组件包**不在**缓存里时会先联网下载（带断点续传），下完校验、再解压安装。
    /// 这也是「可选组件」能成立的前提：普通用户不需要知道缓存目录在哪。
    /// </summary>
    public string Install(string name)
    {
        string id = "job" + Interlocked.Increment(ref _seq);
        var job = new Job();
        _jobs[id] = job;
        var cts = new CancellationTokenSource();
        _jobCancels[id] = cts;
        string kind = (name ?? "").Trim().ToLowerInvariant();

        var th = new Thread(() =>
        {
            try
            {
                if (kind == "python") InstallPython(job, cts.Token);
                else if (kind == "cpp") InstallCpp(job, cts.Token);
                else
                {
                    job.State = "error";
                    job.Message = "未知组件：" + kind;
                }
            }
            catch (OperationCanceledException)
            {
                job.State = "error";
                job.Message = "已取消安装（已下载的部分保留着，下次接着下）";
            }
            catch (Exception ex)
            {
                job.State = "error";
                job.Message = ex.Message;
            }
            finally
            {
                _jobCancels.TryRemove(id, out _);
                cts.Dispose();
            }
        })
        { IsBackground = true, Name = "console-install-" + kind };
        th.Start();
        return id;
    }

    /// <summary>
    /// 卸载一个可选组件：删掉它的安装目录。
    ///
    /// 只接受 python / cpp 两个已知名字（不接受任意路径，避免变成"删目录"原语）。
    /// **不删 cache/**：那里面是下载好的组件包，重装时能省一次下载（几十 MB）。
    /// 如果控制台里还有进程在用该组件，删除会失败并把系统错误原样返回——
    /// 这比"假装卸掉了"好，用户能看懂"请先关闭控制台里的运行"。
    /// </summary>
    public string Uninstall(string name)
    {
        string kind = (name ?? "").Trim().ToLowerInvariant();
        string? dir = kind == "python" ? PythonDir : (kind == "cpp" ? CppDir : null);
        if (dir == null) return "{\"ok\":false,\"error\":" + Json("未知组件：" + kind) + "}";
        try
        {
            if (!Directory.Exists(dir)) return "{\"ok\":true,\"removed\":false,\"bytes\":0}";
            long bytes = DirSize(dir);
            Directory.Delete(dir, true);
            return "{\"ok\":true,\"removed\":true,\"bytes\":" + bytes + "}";
        }
        catch (Exception ex)
        {
            return "{\"ok\":false,\"error\":" + Json(ex.Message) + "}";
        }
    }

    /// <summary>取消一个正在进行的安装/下载（保留 .part，下次能续传）。</summary>
    public string CancelInstall(string jobId)
    {
        if (jobId != null && _jobCancels.TryGetValue(jobId, out var cts))
        {
            try { cts.Cancel(); } catch { /* 已取消 */ }
            return "{\"canceled\":true}";
        }
        return "{\"canceled\":false}";
    }

    private void InstallPython(Job job, CancellationToken ct)
    {
        job.Message = "查找组件包…";
        job.Percent = 5;
        string zip = EnsurePayload("python", PythonPayloadName, PythonPayloadSha256, job, ct);

        VerifyPayload(zip, PythonPayloadSha256, job);

        job.Message = "解压 CPython…";
        job.Percent = 60;
        string staging = PythonDir + ".staging";
        if (Directory.Exists(staging)) Directory.Delete(staging, true);
        Directory.CreateDirectory(staging);
        ZipFile.ExtractToDirectory(zip, staging, overwriteFiles: true);

        // 引擎门面：从应用目录拷进组件目录，保证 Python 侧能找到 mfmath.py
        string facadeSrc = Path.Combine(AppDir, "python", "mfmath.py");
        if (!File.Exists(facadeSrc))
            throw new InvalidOperationException("应用目录缺少 python\\mfmath.py（控制台无法调用引擎）");
        File.Copy(facadeSrc, Path.Combine(staging, "mfmath.py"), overwrite: true);

        if (!File.Exists(Path.Combine(staging, "python.exe")))
            throw new InvalidOperationException("解压后没有 python.exe，组件包可能不完整");

        job.Message = "替换为已安装版本…";
        job.Percent = 80;
        if (Directory.Exists(PythonDir)) Directory.Delete(PythonDir, true);
        Directory.Move(staging, PythonDir);

        job.Percent = 100;
        job.State = "done";
        job.Message = "CPython " + PythonVersion + " 已安装（" + (DirSize(PythonDir) / 1024 / 1024) + " MB）";
    }

    /// <summary>
    /// 装 MinGW A 档工具链，并把它变成"能调用引擎"的完整环境：
    ///   ① 解压工具链
    ///   ② 拷入门面头文件 mfmath.hpp / mfmath_autorun.hpp
    ///   ③ 现场生成 mf_mathematics.dll 的导入库（.def + dlltool）
    /// ③ 是关键：用户代码 #include "mfmath.hpp" 后正常链接即可，
    /// 计算全部落在引擎 DLL 里，和 Python 侧走的是同一个 C ABI。
    /// </summary>
    private void InstallCpp(Job job, CancellationToken ct)
    {
        job.Message = "查找组件包…";
        job.Percent = 3;
        string zip = EnsurePayload("mingw", CppPayloadName, CppPayloadSha256, job, ct);

        VerifyPayload(zip, CppPayloadSha256, job);

        job.Message = "解压 MinGW 工具链…";
        job.Percent = 20;
        string staging = CppDir + ".staging";
        if (Directory.Exists(staging)) Directory.Delete(staging, true);
        Directory.CreateDirectory(staging);
        ZipFile.ExtractToDirectory(zip, staging, overwriteFiles: true);
        FlattenSingleRoot(staging);

        string gpp = Path.Combine(staging, "bin", "g++.exe");
        if (!File.Exists(gpp))
            throw new InvalidOperationException("解压后没有 bin\\g++.exe，组件包可能不完整或布局不对");

        job.Message = "拷入门面头文件…";
        job.Percent = 40;
        string incDir = Path.Combine(staging, "include");
        Directory.CreateDirectory(incDir);
        foreach (var header in new[] { "mfmath.hpp", "mfmath_autorun.hpp" })
        {
            string src = Path.Combine(AppDir, "cpp", header);
            if (!File.Exists(src))
                throw new InvalidOperationException("应用目录缺少 cpp\\" + header + "（控制台无法调用引擎）");
            File.Copy(src, Path.Combine(incDir, header), overwrite: true);
        }

        job.Message = "生成引擎导入库…";
        job.Percent = 65;
        string libDir = Path.Combine(staging, "lib");
        Directory.CreateDirectory(libDir);
        string defPath = Path.Combine(libDir, "mf_mathematics.def");
        File.WriteAllText(defPath, CppDefText, new ASCIIEncoding());
        string importLib = Path.Combine(libDir, "libmf_mathematics.a");
        if (File.Exists(importLib)) File.Delete(importLib);

        string dlltool = Path.Combine(staging, "bin", "dlltool.exe");
        if (!File.Exists(dlltool))
            throw new InvalidOperationException("组件包里没有 bin\\dlltool.exe，无法生成导入库");
        string toolOut = RunTool(dlltool, "-d \"" + defPath + "\" -l \"" + importLib + "\" -k", libDir);
        if (!File.Exists(importLib))
            throw new InvalidOperationException("dlltool 没能生成 libmf_mathematics.a：" + toolOut);

        job.Message = "替换为已安装版本…";
        job.Percent = 90;
        if (Directory.Exists(CppDir)) Directory.Delete(CppDir, true);
        Directory.Move(staging, CppDir);

        job.Percent = 100;
        job.State = "done";
        job.Message = "MinGW " + CppVersion + " 已安装（" + (DirSize(CppDir) / 1024 / 1024) +
                      " MB），C++ 已出现在语言列表里";
    }

    /// <summary>同步跑一个工具并回收它的输出（安装阶段用，量很小）。</summary>
    private static string RunTool(string exe, string args, string workDir)
    {
        var psi = new ProcessStartInfo(exe, args)
        {
            WorkingDirectory = workDir,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        using var p = Process.Start(psi);
        if (p == null) throw new InvalidOperationException("无法启动 " + exe);
        string o = p.StandardOutput.ReadToEnd();
        string e = p.StandardError.ReadToEnd();
        p.WaitForExit(CompileTimeoutSec * 1000);
        return (o + e).Trim();
    }

    /// <summary>组件包若整体套了一层目录（mingw64/…），提到根上，省得处处要拼前缀。</summary>
    private static void FlattenSingleRoot(string dir)
    {
        if (File.Exists(Path.Combine(dir, "bin", "g++.exe"))) return;
        var subs = Directory.GetDirectories(dir);
        var files = Directory.GetFiles(dir);
        if (subs.Length != 1 || files.Length != 0) return;
        string inner = subs[0];
        if (!File.Exists(Path.Combine(inner, "bin", "g++.exe"))) return;
        foreach (var entry in Directory.GetFileSystemEntries(inner))
            Directory.Move(entry, Path.Combine(dir, Path.GetFileName(entry)));
        Directory.Delete(inner, true);
    }

    public string InstallStatus(string jobId)
    {
        if (jobId != null && _jobs.TryGetValue(jobId, out var job))
            return "{\"state\":" + Json(job.State) + ",\"message\":" + Json(job.Message) +
                   ",\"percent\":" + job.Percent + "}";
        return "{\"state\":\"unknown\",\"message\":\"没有这个任务\",\"percent\":0}";
    }

    // ══════════════════════════ 运行 ══════════════════════════

    private static int _scratchCleaned;
    /// <summary>
    /// 清掉上一次会话留下的控制台临时工程目录。
    ///
    /// 为什么放在宿主里做，而不是交给卸载程序：临时目录在 %LOCALAPPDATA% 下，
    /// 是**用户级**路径；管理员模式安装的卸载程序可能运行在另一个管理员账号下，
    /// 去删 {localappdata} 会删错人（Inno 编译时的 UsedUserAreasWarning 就是这件事）。
    /// 宿主自己清最准：它一定运行在真正使用它的那个用户下。
    ///
    /// 只清一次（每个进程），所以本次会话里报错信息中给出的 run&lt;n&gt;\main.py 路径
    /// 在会话期间一直有效。
    /// </summary>
    private static void CleanScratchOnce()
    {
        if (Interlocked.Exchange(ref _scratchCleaned, 1) != 0) return;
        try
        {
            if (Directory.Exists(ScratchRoot)) Directory.Delete(ScratchRoot, true);
        }
        catch { /* 有别的实例在用就跳过，不因为清理失败影响运行 */ }
    }

    /// <summary>开始运行一段代码，返回 runId。language: "python" | "cpp"</summary>
    public string Start(string language, string code, string stdin)
    {
        string id = "run" + Interlocked.Increment(ref _seq);
        var run = new Run { Language = language ?? "python", StartedMs = Environment.TickCount64 };
        _runs[id] = run;

        var th = new Thread(() => RunThread(id, run, code ?? "", stdin ?? ""))
        { IsBackground = true, Name = "console-" + id };
        th.Start();
        return id;
    }

    private void RunThread(string id, Run run, string code, string stdin)
    {
        try
        {
            CleanScratchOnce();
            Directory.CreateDirectory(ScratchRoot);
            string work = Path.Combine(ScratchRoot, id);
            if (Directory.Exists(work)) Directory.Delete(work, true);
            Directory.CreateDirectory(work);
            run.Dir = work;

            if (run.Language == "cpp") RunCpp(run, code, stdin, work);
            else RunPython(run, code, stdin, work);
        }
        catch (Exception ex)
        {
            Append(run.Err, "[宿主错误] " + ex.Message);
            run.ExitCode = -2;
        }
        finally
        {
            run.State = "done";
            run.Stage = "done";
        }
    }

    private void RunPython(Run run, string code, string stdin, string work)
    {
        string py = Path.Combine(PythonDir, "python.exe");
        if (!File.Exists(py))
        {
            run.Err.Append("CPython 组件未安装：请先在控制台里点「安装 Python 组件」。\n");
            run.ExitCode = -1;
            return;
        }
        string file = Path.Combine(work, "main.py");
        File.WriteAllText(file, code, new UTF8Encoding(false));

        // 引导脚本：解决"嵌入版 Python 处于 isolated 模式"这个坑。
        //
        // 嵌入式 CPython 带一个 python313._pth，等于强制在隔离模式下运行：
        //   · 环境变量 PYTHONPATH 被**完全忽略**（所以下面设了也白设）
        //   · 脚本所在目录不会进 sys.path[0]
        // 后果是用户不能 import 自己刚写的模块、也 import 不到 mfmath（除非它在
        // 组件目录里靠搜索路径撞上）。用一个显式引导文件把这些路径补回来，
        // 比去改组件里的 _pth 更稳（组件是官方发行的，改它会在升级时被覆盖）。
        string runner = Path.Combine(work, "_run.py");
        File.WriteAllText(runner, string.Join("\n", new[]
        {
            "import os, sys",
            "_d = os.path.dirname(os.path.abspath(__file__))",
            "for _p in (os.environ.get('MF_ENGINE_DIR') or '', sys.prefix, _d):",
            "    if _p and _p not in sys.path:",
            "        sys.path.insert(0, _p)",
            "# 以 __main__ 方式执行用户代码：traceback 里的文件名保持 main.py，行号可直接对上",
            "_f = os.path.join(_d, 'main.py')",
            "with open(_f, encoding='utf-8') as _h:",
            "    _src = _h.read()",
            "exec(compile(_src, 'main.py', 'exec'), {'__name__': '__main__', '__file__': _f})",
        }), new UTF8Encoding(false));

        // 让 Python 侧 ① 输出一律 UTF-8（中文不乱码）② 能找到引擎 DLL
        var env = new Dictionary<string, string>
        {
            ["PYTHONIOENCODING"] = "utf-8",
            ["PYTHONUTF8"] = "1",
            ["MF_ENGINE_DIR"] = AppDir,
            ["PYTHONPATH"] = PythonDir + Path.PathSeparator + AppDir,
        };
        run.Stage = "running";
        run.ExitCode = Exec(run, py, "-X utf8 \"" + runner + "\"", work, stdin, env, DefaultTimeoutSec);
    }

    /// <summary>
    /// C++：先编译再运行。编译用的工具链、门面头文件、引擎导入库都来自 C++ 组件。
    /// 编译器输出原样进 stderr（用户要靠它定位自己代码的问题），
    /// 编译失败就**不运行**，退出码沿用编译器的。
    /// </summary>
    private void RunCpp(Run run, string code, string stdin, string work)
    {
        string gpp = Path.Combine(CppDir, "bin", "g++.exe");
        if (!File.Exists(gpp))
        {
            run.Err.Append("C++ 组件（MinGW A 档）未安装：请先在控制台里点「安装 C++ 组件」。\n");
            run.ExitCode = -1;
            return;
        }
        string incDir = Path.Combine(CppDir, "include");
        string libDir = Path.Combine(CppDir, "lib");
        foreach (var need in new[]
                 {
                     Path.Combine(incDir, "mfmath.hpp"),
                     Path.Combine(incDir, "mfmath_autorun.hpp"),
                     Path.Combine(libDir, "libmf_mathematics.a"),
                 })
        {
            if (!File.Exists(need))
            {
                run.Err.Append("C++ 组件不完整，缺少 " + need + "：请重新安装 C++ 组件。\n");
                run.ExitCode = -1;
                return;
            }
        }

        File.WriteAllText(Path.Combine(work, "main.cpp"), code, new UTF8Encoding(false));

        string args =
            "-std=c++17 -O2 -static-libgcc -static-libstdc++ " +
            "-I\"" + incDir + "\" " +
            // 强制注入：让 stdout 边写边落管道，未捕获异常打断时前面的输出不会丢
            "-include \"" + Path.Combine(incDir, "mfmath_autorun.hpp") + "\" " +
            "main.cpp -L\"" + libDir + "\" -lmf_mathematics -o main.exe";

        run.Stage = "compiling";
        long t0 = Environment.TickCount64;
        int cc = Exec(run, gpp, args, work, "", null, CompileTimeoutSec);
        run.CompileMs = Environment.TickCount64 - t0;
        if (cc != 0)
        {
            run.Err.Insert(0, run.TimedOut
                ? "编译超时（超过 " + CompileTimeoutSec + " 秒已被终止）。\n"
                : "编译失败（编译器退出码 " + cc + "）：\n");
            run.ExitCode = cc;
            return;
        }

        string exe = Path.Combine(work, "main.exe");
        if (!File.Exists(exe))
        {
            run.Err.Append("编译器报告成功，但没有产出 main.exe。\n");
            run.ExitCode = -3;
            return;
        }

        run.Stage = "running";
        // 引擎 DLL 和它的依赖都在应用目录，放进 PATH 让 main.exe 找得到
        string path = Environment.GetEnvironmentVariable("PATH") ?? "";
        var env = new Dictionary<string, string> { ["PATH"] = AppDir + ";" + path };
        int code2 = Exec(run, exe, "", work, stdin, env, DefaultTimeoutSec);
        run.ExitCode = code2;

        if (code2 < 0 && !run.TimedOut)
            Append(run.Err,
                   "[宿主] 程序异常终止（退出码 " + code2 + "，0x" + ((uint)code2).ToString("X8") + "）。" +
                   "未捕获的 C++ 异常会让标准库直接 std::terminate 终止进程、不打任何说明，" +
                   "把可能抛异常的调用（mfm::call / mfm::num / mfm::text）包进 try/catch 才能看见原因。");
    }

    /// <summary>
    /// 跑一个子进程并回收输出。编译和运行共用一份逻辑：
    /// 都接管道、都限时、都能被 Stop 杀。
    /// </summary>
    private int Exec(Run run, string exe, string args, string work, string stdin,
                     IDictionary<string, string>? env, int timeoutSec)
    {
        var psi = new ProcessStartInfo(exe, args)
        {
            WorkingDirectory = work,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            RedirectStandardInput = !string.IsNullOrEmpty(stdin),
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        if (env != null)
            foreach (var kv in env) psi.Environment[kv.Key] = kv.Value;

        var proc = new Process { StartInfo = psi, EnableRaisingEvents = true };
        run.Proc = proc;
        proc.OutputDataReceived += (_, e) => Append(run.Out, e.Data);
        proc.ErrorDataReceived += (_, e) => Append(run.Err, e.Data);
        run.TimedOutAfterSec = timeoutSec;
        run.State = "running";
        proc.Start();
        proc.BeginOutputReadLine();
        proc.BeginErrorReadLine();
        if (!string.IsNullOrEmpty(stdin))
        {
            try { proc.StandardInput.Write(stdin); proc.StandardInput.Close(); }
            catch { /* 进程可能已退出，忽略 */ }
        }

        if (!proc.WaitForExit(timeoutSec * 1000))
        {
            run.TimedOut = true;
            try { proc.Kill(entireProcessTree: true); } catch { }
            proc.WaitForExit(3000);
        }
        int code = proc.HasExited ? proc.ExitCode : -1;
        run.Proc = null;
        return code;
    }

    private static void Append(StringBuilder sb, string? line)
    {
        if (line == null) return;
        lock (sb)
        {
            if (sb.Length > MaxOutputBytes) return;   // 到上限就丢，Poll 里会提示截断
            sb.Append(line).Append('\n');
        }
    }

    /// <summary>增量取回输出与状态（JSON）。</summary>
    public string Poll(string runId)
    {
        if (runId == null || !_runs.TryGetValue(runId, out var run))
            return "{\"state\":\"unknown\",\"running\":false,\"message\":\"没有这个运行\"}";
        string output, err;
        bool truncated;
        lock (run.Out) { output = run.Out.ToString(); truncated = run.Out.Length > MaxOutputBytes; }
        lock (run.Err) { err = run.Err.ToString(); }
        long elapsed = Environment.TickCount64 - run.StartedMs;
        bool done = run.State == "done";
        return "{\"state\":" + Json(run.State) +
               ",\"stage\":" + Json(run.Stage) +
               ",\"running\":" + (done ? "false" : "true") +
               ",\"exitCode\":" + (done ? run.ExitCode.ToString() : "null") +
               ",\"timedOut\":" + (run.TimedOut ? "true" : "false") +
               ",\"elapsedMs\":" + elapsed +
               ",\"compileMs\":" + (run.CompileMs >= 0 ? run.CompileMs.ToString() : "null") +
               ",\"stdout\":" + Json(output) +
               ",\"stderr\":" + Json(err) +
               ",\"truncated\":" + (truncated ? "true" : "false") + "}";
    }

    /// <summary>终止运行（连同子进程树）。</summary>
    public string Stop(string runId)
    {
        if (runId != null && _runs.TryGetValue(runId, out var run) && run.Proc != null)
        {
            try { run.Proc.Kill(entireProcessTree: true); } catch { }
            return "{\"stopped\":true}";
        }
        return "{\"stopped\":false}";
    }

    /// <summary>应用退出前清场：把还活着的子进程杀掉，别留孤儿进程。</summary>
    public string StopAll()
    {
        int n = 0;
        foreach (var kv in _runs)
        {
            if (kv.Value.Proc is { } p && !p.HasExited)
            {
                try { p.Kill(entireProcessTree: true); n++; } catch { }
            }
        }
        return "{\"killed\":" + n + "}";
    }

    // ── 极简 JSON 字符串转义（不引入序列化库：这里只有字符串字段）──
    private static string Json(string s)
    {
        var sb = new StringBuilder("\"");
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
                    if (c < 0x20) sb.Append("\\u").Append(((int)c).ToString("x4"));
                    else sb.Append(c);
                    break;
            }
        }
        return sb.Append('"').ToString();
    }
}
