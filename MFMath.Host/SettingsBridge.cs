using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;

namespace MFMath.Host;

/// <summary>
/// 设置面板用的宿主桥（JS 侧是 hostObjects.sync.sys）。
///
/// 为什么单独一个桥、而不是塞进 MathBridge/WindowBridge/ConsoleBridge：
/// 这个桥只做"文件与系统信息"这一件事——报路径、查文件在不在、读写设置 JSON、
/// 打开目录、导出诊断包。它不含数学、不含窗口、不含进程，职责清楚，
/// 将来加设置项也不会把另外三个桥撑大。
///
/// 三条安全/健壮性规则（都是踩过或看得见的坑）：
///   ① **OpenPath 只允许打开白名单内的路径**（数据目录、应用目录、组件目录）。
///      否则它就等于给渲染进程一个"打开任意路径"的原语，而设置面板是外部可扩展的。
///   ② **读写设置 JSON 一律带 .bak**：覆盖前把旧文件复制成 .bak；解析失败时
///      报错并**保留原文件不动**（不清空、不覆盖），避免"配置一坏全丢"。
///   ③ **文件名单校验**：只允许 [a-z0-9_-]，杜绝用 "../" 跳出设置目录。
/// </summary>
[ComVisible(true)]
public class SettingsBridge
{
    private static readonly string LocalAppData =
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);

    /// <summary>用户数据根目录：与 WebView2 用户数据、组件缓存同处一地，卸载时说法统一。</summary>
    private static string DataDir => Path.Combine(LocalAppData, "MFMath");

    /// <summary>设置文件目录。</summary>
    private static string SettingsDir => Path.Combine(DataDir, "settings");

    /// <summary>引擎与运行时依赖的清单（顺序即 UI 上的显示顺序）。</summary>
    private static readonly string[] EngineDeps =
    {
        "mf_mathematics.dll", "symengine-0.14.dll", "flint-24.dll",
        "gmp-10.dll", "mpfr-6.dll", "pthreadVC3.dll",
    };

    private static string Json(string s)
    {
        var sb = new StringBuilder("\"");
        foreach (char c in s ?? "")
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

    /// <summary>设置文件名合法性：只允许小写字母/数字/下划线/连字符，防目录穿越。</summary>
    private static bool ValidName(string name)
    {
        if (string.IsNullOrWhiteSpace(name) || name.Length > 40) return false;
        foreach (char c in name)
        {
            bool ok = (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || c == '-';
            if (!ok) return false;
        }
        return true;
    }

    /// <summary>路径是否落在允许打开的根目录内（含子目录）。</summary>
    private static bool UnderAllowedRoot(string path, out string reason)
    {
        reason = "";
        if (string.IsNullOrWhiteSpace(path)) { reason = "路径为空"; return false; }

        string full;
        try { full = Path.GetFullPath(path); }
        catch (Exception e) { reason = "路径非法：" + e.Message; return false; }

        var roots = new List<string> { DataDir, AppContext.BaseDirectory };
        try { roots.Add(Path.Combine(DataDir, "components")); } catch { /* 忽略 */ }
        // 组件目录由 ConsoleBridge 决定，这里按约定的同名字段再算一份，避免互相依赖
        roots.Add(Path.Combine(DataDir, "components"));

        foreach (var r in roots.Distinct())
        {
            if (string.IsNullOrEmpty(r)) continue;
            string rf = Path.GetFullPath(r);
            if (full.StartsWith(rf, StringComparison.OrdinalIgnoreCase)) return true;
        }
        reason = "只允许打开数据目录或应用目录内的路径";
        return false;
    }

    /* ── 基本信息 ─────────────────────────────────────────────────────── */

    /// <summary>宿主与运行环境信息（设置面板的"引擎"与"存储"两组都用它）。</summary>
    public string Info()
    {
        string hostVersion = "unknown";
        try
        {
            var asm = Assembly.GetExecutingAssembly();
            hostVersion = asm.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion
                          ?? asm.GetName().Version?.ToString() ?? "unknown";
        }
        catch { /* 拿不到就保持 unknown，不影响其它字段 */ }

        var sb = new StringBuilder("{");
        sb.Append("\"dataDir\":").Append(Json(DataDir));
        sb.Append(",\"settingsDir\":").Append(Json(SettingsDir));
        sb.Append(",\"appDir\":").Append(Json(AppContext.BaseDirectory));
        sb.Append(",\"hostVersion\":").Append(Json(hostVersion));
        sb.Append(",\"runtime\":").Append(Json(Environment.Version.ToString()));
        sb.Append(",\"os\":").Append(Json(Environment.OSVersion.VersionString));
        sb.Append(",\"arch\":").Append(Json(RuntimeInformation.OSArchitecture.ToString()));
        sb.Append(",\"is64\":").Append(Environment.Is64BitProcess ? "true" : "false");
        sb.Append(",\"componentBase\":").Append(Json(
            Environment.GetEnvironmentVariable("__MF_COMPONENT_BASE") ?? ""));
        sb.Append('}');
        return sb.ToString();
    }

    /// <summary>引擎产物清单：主 DLL 与 5 个运行时依赖在不在、多大。</summary>
    public string EngineReport()
    {
        string dir = AppContext.BaseDirectory;
        var sb = new StringBuilder("{");
        sb.Append("\"dir\":").Append(Json(dir));
        sb.Append(",\"files\":[");
        for (int i = 0; i < EngineDeps.Length; i++)
        {
            string name = EngineDeps[i];
            string p = Path.Combine(dir, name);
            bool exists = File.Exists(p);
            long bytes = 0;
            string mtime = "";
            if (exists)
            {
                try
                {
                    var fi = new FileInfo(p);
                    bytes = fi.Length;
                    mtime = fi.LastWriteTime.ToString("yyyy-MM-dd HH:mm", CultureInfo.InvariantCulture);
                }
                catch { /* 读不到大小就当 0，前面 exists 已为真 */ }
            }
            if (i > 0) sb.Append(',');
            sb.Append("{\"name\":").Append(Json(name))
              .Append(",\"present\":").Append(exists ? "true" : "false")
              .Append(",\"bytes\":").Append(bytes)
              .Append(",\"mtime\":").Append(Json(mtime))
              .Append('}');
        }
        sb.Append("]}");
        return sb.ToString();
    }

    /* ── 设置 JSON 存储 ───────────────────────────────────────────────── */

    /// <summary>列出已存在的设置文件（名字、大小、修改时间）。</summary>
    public string StoreList()
    {
        var sb = new StringBuilder("[");
        try
        {
            if (Directory.Exists(SettingsDir))
            {
                bool first = true;
                foreach (var f in Directory.EnumerateFiles(SettingsDir, "*.json").OrderBy(x => x))
                {
                    var fi = new FileInfo(f);
                    if (!first) sb.Append(',');
                    first = false;
                    sb.Append("{\"name\":").Append(Json(Path.GetFileNameWithoutExtension(f)))
                      .Append(",\"bytes\":").Append(fi.Length)
                      .Append(",\"mtime\":").Append(Json(fi.LastWriteTime.ToString("yyyy-MM-dd HH:mm", CultureInfo.InvariantCulture)))
                      .Append('}');
                }
            }
        }
        catch (Exception e)
        {
            return "{\"error\":" + Json(e.Message) + "}";
        }
        return sb.Append(']').ToString();
    }

    /// <summary>
    /// 读设置文件。返回 {"ok":true,"json":"..."} 或 {"ok":false,"error":"...","corrupt":true}。
    /// **解析失败时保留原文件**：调用方据此提示用户，且下一次写入会先把坏文件备份成 .bak。
    /// </summary>
    public string StoreRead(string name)
    {
        if (!ValidName(name)) return "{\"ok\":false,\"error\":\"非法的设置文件名\"}";
        string p = Path.Combine(SettingsDir, name + ".json");
        if (!File.Exists(p)) return "{\"ok\":true,\"json\":\"\",\"exists\":false}";
        try
        {
            string text = File.ReadAllText(p, Encoding.UTF8);
            using var _ = JsonDocument.Parse(text);   // 只校验，不解释
            return "{\"ok\":true,\"exists\":true,\"json\":" + Json(text) + "}";
        }
        catch (JsonException e)
        {
            return "{\"ok\":false,\"corrupt\":true,\"error\":" + Json("JSON 解析失败：" + e.Message) + "}";
        }
        catch (Exception e)
        {
            return "{\"ok\":false,\"error\":" + Json(e.Message) + "}";
        }
    }

    /// <summary>
    /// 写设置文件：先校验 JSON，再备份旧文件，最后**原子替换**（临时文件 + File.Replace）。
    /// 这样半途崩溃也不会留下半截 JSON —— v1 的工作区保存就是直接 open(path,"w")，
    /// 写一半崩溃后下次读必然 JSONDecodeError。
    /// </summary>
    public string StoreWrite(string name, string json)
    {
        if (!ValidName(name)) return "{\"ok\":false,\"error\":\"非法的设置文件名\"}";
        if (string.IsNullOrWhiteSpace(json)) return "{\"ok\":false,\"error\":\"内容为空\"}";
        try
        {
            using var _ = JsonDocument.Parse(json);
            Directory.CreateDirectory(SettingsDir);
            string p = Path.Combine(SettingsDir, name + ".json");
            string tmp = p + ".tmp";
            File.WriteAllText(tmp, json, new UTF8Encoding(false));
            if (File.Exists(p))
            {
                string bak = p + ".bak";
                try { File.Copy(p, bak, true); } catch { /* 备份失败不阻断写入 */ }
                File.Replace(tmp, p, null, true);
            }
            else
            {
                File.Move(tmp, p);
            }
            return "{\"ok\":true}";
        }
        catch (Exception e)
        {
            return "{\"ok\":false,\"error\":" + Json(e.Message) + "}";
        }
    }

    public string StoreDelete(string name)
    {
        if (!ValidName(name)) return "{\"ok\":false,\"error\":\"非法的设置文件名\"}";
        try
        {
            string p = Path.Combine(SettingsDir, name + ".json");
            if (File.Exists(p)) File.Delete(p);
            return "{\"ok\":true}";
        }
        catch (Exception e)
        {
            return "{\"ok\":false,\"error\":" + Json(e.Message) + "}";
        }
    }

    /* ── 打开目录 / 诊断包 ───────────────────────────────────────────── */

    /// <summary>在资源管理器里打开路径（白名单内的目录或文件）。</summary>
    public string OpenPath(string path)
    {
        if (!UnderAllowedRoot(path, out string reason))
            return "{\"ok\":false,\"error\":" + Json(reason) + "}";
        try
        {
            if (Directory.Exists(path))
            {
                Process.Start(new ProcessStartInfo { FileName = path, UseShellExecute = true });
                return "{\"ok\":true}";
            }
            if (File.Exists(path))
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = "explorer.exe",
                    Arguments = "/select,\"" + path + "\"",
                    UseShellExecute = true,
                });
                return "{\"ok\":true}";
            }
            return "{\"ok\":false,\"error\":\"路径不存在\"}";
        }
        catch (Exception e)
        {
            return "{\"ok\":false,\"error\":" + Json(e.Message) + "}";
        }
    }

    /// <summary>
    /// 导出诊断包：版本、路径、引擎产物清单、设置文件（**跳过含 secret 的文件**）
    /// 写到数据目录并返回文件路径，方便让用户直接发给支持。
    /// </summary>
    public string ExportDiagnostics()
    {
        try
        {
            Directory.CreateDirectory(DataDir);
            string p = Path.Combine(
                DataDir,
                "diagnostics-" + DateTime.Now.ToString("yyyyMMdd-HHmmss", CultureInfo.InvariantCulture) + ".txt");

            var sb = new StringBuilder();
            sb.AppendLine("MF-Mathematics 诊断包");
            sb.AppendLine("生成时间: " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture));
            sb.AppendLine();
            sb.AppendLine("== 宿主与环境 ==");
            sb.AppendLine(Info());
            sb.AppendLine();
            sb.AppendLine("== 引擎产物 ==");
            sb.AppendLine(EngineReport());
            sb.AppendLine();
            sb.AppendLine("== 设置文件 ==");
            sb.AppendLine(StoreList());
            sb.AppendLine();
            if (Directory.Exists(SettingsDir))
            {
                // ⚠ 凭据文件名是 ai.json / account.json / search.json —— **一个都不含 "secret"**。
                // 原先只按"文件名含 secret"跳，等于没跳：API Key、登录态、Wolfram App ID 的
                // 密文都会被打进诊断包，而界面（StorageGroup.vue）对用户写的是"不含密钥文件"。
                // 名单与前端 lib/settings/io.js 的 CREDENTIAL_FILES 保持一致；
                // "secret" 那条保留，作为将来新增文件名的兜底。
                var credentialFiles = new[] { "ai", "account", "search" };
                foreach (var f in Directory.EnumerateFiles(SettingsDir, "*.json").OrderBy(x => x))
                {
                    string n = Path.GetFileName(f);
                    string stem = Path.GetFileNameWithoutExtension(n);
                    if (n.Contains("secret", StringComparison.OrdinalIgnoreCase)) continue;
                    if (Array.Exists(credentialFiles,
                            x => string.Equals(x, stem, StringComparison.OrdinalIgnoreCase))) continue;
                    sb.AppendLine("-- " + n + " --");
                    try { sb.AppendLine(File.ReadAllText(f, Encoding.UTF8)); }
                    catch (Exception e) { sb.AppendLine("(读取失败: " + e.Message + ")"); }
                    sb.AppendLine();
                }
            }
            sb.AppendLine();
            // 崩溃排查最需要的就是这两段：最近日志 + 最近一次崩溃的完整现场。
            // 崩溃日志本身就是"单文件可复盘"的（环境 + 异常链 + 日志尾部），
            // 所以这里只带最近一个，不把 20 个都塞进诊断包。
            sb.AppendLine("== 宿主日志（app.log 尾部）==");
            sb.AppendLine("日志目录: " + Log.Dir);
            sb.AppendLine(Log.Tail(Path.Combine(Log.Dir, "app.log"), 200));
            sb.AppendLine();
            sb.AppendLine("== 最近的崩溃记录 ==");
            try
            {
                string? newest = Directory.Exists(Log.Dir)
                    ? Directory.EnumerateFiles(Log.Dir, "crash-*.log")
                        .OrderByDescending(x => Path.GetFileName(x), StringComparer.Ordinal)
                        .FirstOrDefault()
                    : null;
                if (newest is null) sb.AppendLine("(无)");
                else
                {
                    sb.AppendLine("-- " + Path.GetFileName(newest) + " --");
                    sb.AppendLine(File.ReadAllText(newest, Encoding.UTF8));
                }
            }
            catch (Exception e)
            {
                sb.AppendLine("(读取崩溃记录失败: " + e.Message + ")");
            }
            sb.AppendLine();
            File.WriteAllText(p, sb.ToString(), new UTF8Encoding(false));
            return "{\"ok\":true,\"path\":" + Json(p) + "}";
        }
        catch (Exception e)
        {
            return "{\"ok\":false,\"error\":" + Json(e.Message) + "}";
        }
    }
}
