// AiBridge.cs — AI 助手桥（JS 侧：hostObjects.sync.ai）
//
// 分工（这次改动的核心）：
//   · **宿主 = 凭据 + 网络**。它保管密钥、发请求、把响应原始字节转回去。
//     它**不理解** SSE，也不理解 OpenAI 的分片语义 —— 那部分在 TS 里，
//     只有一份实现（MF_UI/MFMath.UI.Vue/src/lib/ai/{sse,client,collect}.ts，
//     移植自 MVS Agent 的 src/model/）。
//   · **页面 = 协议 + 组装 + 渲染**。SSE 分帧、usage 尾包、reasoning_content、
//     [DONE]、降级通知、消息组装与隐私开关，全在 TS 那一侧。
//   · **计算** 仍然全在 C++ 引擎：AI 只解释，结果区永远显示引擎值（有 CDP 断言守着）。
//
// 为什么密钥不放渲染进程：页面直连就得自己持有 API Key（localStorage / 内存），
// 而本项目已经有渲染进程注入面的现实案例（教程富文本清洗那个绕过）。
// 所以对外只有 hasKey / keySource / keyPersisted，密钥本身一步都不出宿主。
//
// 桥面：
//   Info() Configure(json) SetKey(key) ClearKey() Test()
//   Begin(json)  —— 带密钥发一次请求，字节经 ai.http / ai.raw / ai.rawEnd / ai.rawError 推回
//   Cancel(responseId) CancelAll() Busy() KeySource() SelfCheck()
using System;
using System.Collections.Concurrent;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace MFMath.Host;

[ComVisible(true)]
public class AiBridge
{
    private static readonly object ConfigLock = new();
    private static AiConfig? _config;

    /// <summary>DPAPI 不可用时的兜底：密钥只留在内存，重启后需要重填（**绝不写明文到磁盘**）</summary>
    private static string _memoryKey = "";

    private static volatile string _lastError = "";

    private static AiConfig Config
    {
        get
        {
            lock (ConfigLock)
            {
                return _config ??= AiConfig.Load();
            }
        }
    }

    /* ── JSON 小工具（与 PushHub/SettingsBridge 同风格）── */

    private static string J(string? s) => PushHub.Str(s);

    private static string B(bool v) => v ? "true" : "false";

    private static string Num(double v) => v.ToString("0.####", CultureInfo.InvariantCulture);

    private static string Fail(string message) => "{\"ok\":false,\"error\":" + J(message) + "}";

    /* ── 状态 ───────────────────────────────────────────────────────────── */

    /// <summary>
    /// 状态与**脱敏后的**配置。这里永远不会出现密钥本身——
    /// 只有 hasKey（有没有）、keySource（从哪来）、keyPersisted（有没有落盘）。
    /// </summary>
    public string Info()
    {
        var cfg = Config;
        bool dpapi = false;
        try { dpapi = AiDpapi.SelfTest(); } catch { }

        string keySource = !string.IsNullOrEmpty(_memoryKey) ? "memory"
                         : !string.IsNullOrEmpty(cfg.ApiKeyProtected) ? "dpapi"
                         : "none";

        var sb = new StringBuilder("{");
        sb.Append("\"enabled\":").Append(B(cfg.Enabled));
        sb.Append(",\"baseUrl\":").Append(J(cfg.BaseUrl));
        sb.Append(",\"model\":").Append(J(cfg.Model));
        sb.Append(",\"temperature\":").Append(Num(cfg.Temperature));
        sb.Append(",\"maxTokens\":").Append(cfg.MaxTokens);
        sb.Append(",\"includeUsage\":").Append(B(cfg.IncludeUsage));
        sb.Append(",\"timeoutSec\":").Append(cfg.TimeoutSec);
        sb.Append(",\"contextWindow\":").Append(cfg.ContextWindow);
        sb.Append(",\"historyTurns\":").Append(cfg.HistoryTurns);
        sb.Append(",\"sendExpr\":").Append(B(cfg.SendExpr));
        sb.Append(",\"sendResult\":").Append(B(cfg.SendResult));
        sb.Append(",\"sendHistory\":").Append(B(cfg.SendHistory));
        sb.Append(",\"sendCode\":").Append(B(cfg.SendCode));
        sb.Append(",\"hasKey\":").Append(B(keySource != "none"));
        sb.Append(",\"keySource\":").Append(J(keySource));
        sb.Append(",\"keyPersisted\":").Append(B(!string.IsNullOrEmpty(cfg.ApiKeyProtected)));
        sb.Append(",\"dpapiAvailable\":").Append(B(dpapi));
        sb.Append(",\"configLoadFailed\":").Append(B(cfg.KeyLoadFailed));
        sb.Append(",\"configPath\":").Append(J(AiConfig.FilePath));
        sb.Append(",\"configDir\":").Append(J(AiConfig.Dir));
        sb.Append(",\"lastError\":").Append(J(_lastError));
        sb.Append(",\"running\":" ).Append(AiRelay.RunningCount());
        sb.Append('}');
        return sb.ToString();
    }

    /// <summary>当前是否有请求在跑（页面刷新后靠它决定要不要显示"正在输出"）</summary>
    public bool Busy() => AiRelay.Busy();

    /// <summary>密钥从哪来（供设置面板显示，不返回密钥内容）</summary>
    public string KeySource()
    {
        if (!string.IsNullOrEmpty(_memoryKey)) return "memory";
        if (!string.IsNullOrEmpty(Config.ApiKeyProtected)) return "dpapi";
        return "none";
    }

    /* ── 配置写入 ───────────────────────────────────────────────────────── */

    /// <summary>
    /// 更新非密钥配置。入参是**只含要改的字段**的 JSON（页面只发改动过的字段，
    /// 整份回传会把界面没显示的字段以默认值悄悄写回磁盘）。
    /// </summary>
    public string Configure(string json)
    {
        try
        {
            using var doc = System.Text.Json.JsonDocument.Parse(json);
            var root = doc.RootElement;
            var cfg = Config;
            bool changed = false;

            // 属性不能按 ref 传，所以先落到局部变量，最后统一写回
            bool enabled = cfg.Enabled, includeUsage = cfg.IncludeUsage,
                 sendExpr = cfg.SendExpr, sendResult = cfg.SendResult,
                 sendHistory = cfg.SendHistory, sendCode = cfg.SendCode;
            string baseUrl = cfg.BaseUrl, model = cfg.Model;
            int maxTokens = cfg.MaxTokens, timeoutSec = cfg.TimeoutSec, contextWindow = cfg.ContextWindow,
                historyTurns = cfg.HistoryTurns;
            double temperature = cfg.Temperature;

            bool TryBool(string name, ref bool target)
            {
                if (!root.TryGetProperty(name, out var e)) return false;
                if (e.ValueKind != System.Text.Json.JsonValueKind.True && e.ValueKind != System.Text.Json.JsonValueKind.False) return false;
                target = e.GetBoolean(); changed = true; return true;
            }
            bool TryStr(string name, ref string target)
            {
                if (!root.TryGetProperty(name, out var e) || e.ValueKind != System.Text.Json.JsonValueKind.String) return false;
                target = e.GetString() ?? ""; changed = true; return true;
            }
            bool TryInt(string name, ref int target)
            {
                if (!root.TryGetProperty(name, out var e) || e.ValueKind != System.Text.Json.JsonValueKind.Number) return false;
                target = e.GetInt32(); changed = true; return true;
            }
            bool TryDouble(string name, ref double target)
            {
                if (!root.TryGetProperty(name, out var e) || e.ValueKind != System.Text.Json.JsonValueKind.Number) return false;
                target = e.GetDouble(); changed = true; return true;
            }

            TryBool("enabled", ref enabled);
            TryStr("baseUrl", ref baseUrl);
            TryStr("model", ref model);
            TryDouble("temperature", ref temperature);
            TryInt("maxTokens", ref maxTokens);
            TryBool("includeUsage", ref includeUsage);
            TryInt("timeoutSec", ref timeoutSec);
            TryInt("contextWindow", ref contextWindow);
            TryInt("historyTurns", ref historyTurns);
            TryBool("sendExpr", ref sendExpr);
            TryBool("sendResult", ref sendResult);
            TryBool("sendHistory", ref sendHistory);
            TryBool("sendCode", ref sendCode);

            if (!changed) return "{\"ok\":true,\"changed\":0}";

            cfg.Enabled = enabled;
            cfg.BaseUrl = baseUrl;
            cfg.Model = model;
            cfg.Temperature = temperature;
            cfg.MaxTokens = maxTokens;
            cfg.IncludeUsage = includeUsage;
            cfg.TimeoutSec = timeoutSec;
            cfg.ContextWindow = contextWindow;
            cfg.HistoryTurns = historyTurns;
            cfg.SendExpr = sendExpr;
            cfg.SendResult = sendResult;
            cfg.SendHistory = sendHistory;
            cfg.SendCode = sendCode;

            AiConfig.Normalize(cfg);
            if (!cfg.Save(out string err)) return Fail("写入配置失败：" + err);
            lock (ConfigLock) _config = cfg;
            return "{\"ok\":true,\"changed\":1}";
        }
        catch (Exception e)
        {
            return Fail("配置解析失败：" + e.Message);
        }
    }

    /// <summary>
    /// 设置 API Key。**只写不读**：页面拿不到它。
    /// DPAPI 可用就落盘（密文）；不可用则只留在内存，并明确告诉调用方"重启后要重填"。
    /// </summary>
    public string SetKey(string key)
    {
        if (string.IsNullOrWhiteSpace(key)) return Fail("密钥为空");
        string trimmed = key.Trim();

        string? blob = null;
        try { blob = AiDpapi.Protect(trimmed); } catch { }

        if (blob == null)
        {
            _memoryKey = trimmed;
            return "{\"ok\":true,\"persisted\":false,\"warning\":" +
                   J("DPAPI 在本机不可用：密钥只保留在本次运行的内存里（重启后需要重新填写）。" +
                     "不会把明文写到磁盘上。") + "}";
        }

        var cfg = Config;
        cfg.ApiKeyProtected = blob;
        if (!cfg.Save(out string err)) return Fail("密钥已加密但写入配置失败：" + err);
        lock (ConfigLock) _config = cfg;
        _memoryKey = "";
        return "{\"ok\":true,\"persisted\":true}";
    }

    public string ClearKey()
    {
        _memoryKey = "";
        var cfg = Config;
        cfg.ApiKeyProtected = "";
        if (!cfg.Save(out string err)) return Fail("清除密钥失败：" + err);
        lock (ConfigLock) _config = cfg;
        return "{\"ok\":true}";
    }

    private static string ResolveKey()
    {
        if (!string.IsNullOrEmpty(_memoryKey)) return _memoryKey;
        var cfg = Config;
        if (string.IsNullOrEmpty(cfg.ApiKeyProtected)) return "";
        try { return AiDpapi.Unprotect(cfg.ApiKeyProtected) ?? ""; }
        catch { return ""; }
    }

    /* ── 连通性自检 ─────────────────────────────────────────────────────── */

    /// <summary>
    /// 测连接。**异步**：同步 host object 调用会阻塞渲染进程，一次 TLS+推理往返可能几秒，
    /// 界面会被冻住。所以这里立即返回，结果用 ai.test 推回去。
    /// </summary>
    public string Test()
    {
        string key = ResolveKey();
        if (string.IsNullOrEmpty(key)) return Fail("没有 API Key（先在下面填一个）");
        if (!Config.Enabled) return Fail("AI 未启用（先打开上面的开关）");

        var cfg = Config;
        Task.Run(async () =>
        {
            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(Math.Min(30, cfg.TimeoutSec)));
            var (ok, status, ms, detail) = await AiClient.TestAsync(cfg, key, cts.Token).ConfigureAwait(false);
            var sb = new StringBuilder("{");
            sb.Append("\"ok\":").Append(B(ok));
            sb.Append(",\"status\":").Append(status);
            sb.Append(",\"ms\":").Append(ms);
            sb.Append(",\"model\":").Append(J(cfg.Model));
            sb.Append(",\"detail\":").Append(J(detail));
            sb.Append('}');
            PushHub.Send("ai.test", sb.ToString());
        });
        return "{\"ok\":true,\"testing\":true}";
    }

    /* ── 中继（对话就走这里）──────────────────────────────────────────── */

    /// <summary>
    /// 带密钥发一次请求，响应字节经推送转回页面。
    /// 入参：<code>{"path":"/chat/completions","body":{...OpenAI 请求体...}}</code>
    /// 返回 <code>{"ok":true,"requestId":"r1"}</code>；
    /// 页面随后会收到 ai.http / ai.raw* 话题，由 TS 侧的 client.ts 解析成模型事件。
    /// </summary>
    public string Begin(string json)
    {
        var cfg = Config;
        if (!cfg.Enabled) return Fail("AI 未启用（设置 → AI 里打开）");

        string key = ResolveKey();
        if (string.IsNullOrEmpty(key))
            return "{\"ok\":false,\"kind\":\"config\",\"error\":" + J(
                cfg.ApiKeyProtected.Length > 0
                    ? "密钥无法解密（可能换了 Windows 用户或文件被改动），请重新填写"
                    : "还没有配置 API Key") + "}";

        if (AiRelay.Busy())
            return "{\"ok\":false,\"kind\":\"busy\",\"error\":" + J("已有一轮对话在输出，请先停止它") + "}";

        var (ok, id, error, kind) = AiRelay.Begin(cfg, key, json, out string failure);
        if (!ok)
        {
            _lastError = kind + ": " + (failure.Length > 0 ? failure : error);
            return "{\"ok\":false,\"kind\":" + J(kind) + ",\"error\":" + J(failure.Length > 0 ? failure : error) + "}";
        }
        return "{\"ok\":true,\"requestId\":" + J(id) + "}";
    }

    /// <summary>停止一轮输出（页面点"停止"、或窗口关闭时调用）</summary>
    public string Cancel(string requestId)
        => AiRelay.Cancel(requestId) ? "{\"ok\":true}" : "{\"ok\":false,\"error\":\"没有这个请求\"}";

    public string CancelAll() => "{\"ok\":true,\"cancelled\":" + AiRelay.CancelAll() + "}";

    /* ── 自检（设置面板的"AI"组要有一行能跑的自检）───────────────────────── */

    /// <summary>
    /// 四项自检，**都不联网**：
    ///   ① DPAPI 能不能用（不可用是降级，不算失败——密钥只留内存）；
    ///   ② 中继的路径闸门：相对路径放行，绝对地址 / 协议相对地址 / `..` 一律拒绝；
    ///   ③ 字节经 base64 转手无损（响应体就是这么过推送的）；
    ///   ④ 配置目录可写。
    /// </summary>
    public string SelfCheck()
    {
        var sb = new StringBuilder("{\"ok\":true,\"checks\":[");
        bool all = true;

        // ① DPAPI —— 不可用不算失败（降级），所以不参与 ok_all
        bool dpapi = false;
        string dpapiDetail;
        try
        {
            dpapi = AiDpapi.SelfTest();
            dpapiDetail = dpapi ? "可用：密钥以当前用户范围加密后落盘" : "不可用：密钥只留在内存（不写明文）";
        }
        catch (Exception e) { dpapiDetail = "异常：" + e.Message; }
        sb.Append("{\"name\":\"密钥保护（DPAPI）\",\"ok\":").Append(B(dpapi))
          .Append(",\"detail\":").Append(J(dpapiDetail)).Append('}');

        // ② 中继路径闸门
        bool allowOk = AiRelay.ValidatePath("/chat/completions", out _);
        bool denyAbsolute = !AiRelay.ValidatePath("https://evil.example/v1/chat/completions", out _);
        bool denyProtoRelative = !AiRelay.ValidatePath("//evil.example/v1", out _);
        bool denyDotDot = !AiRelay.ValidatePath("/../../etc", out _);
        bool gateOk = allowOk && denyAbsolute && denyProtoRelative && denyDotDot;
        all &= gateOk;
        sb.Append(",{\"name\":\"中继路径闸门（拒绝绝对地址）\",\"ok\":").Append(B(gateOk))
          .Append(",\"detail\":").Append(J(gateOk
              ? "相对路径放行；绝对地址 / 协议相对地址 / .. 一律拒绝"
              : "闸门判定不正确，存在把密钥发到任意地址的风险")).Append('}');

        // ③ base64 往返
        bool b64 = AiRelay.Base64RoundTrip();
        all &= b64;
        sb.Append(",{\"name\":\"响应字节转手无损（base64）\",\"ok\":").Append(B(b64))
          .Append(",\"detail\":").Append(J(b64 ? "含 0x00/0xFF/中文的探针往返一致" : "往返不一致")).Append('}');

        // ④ 配置目录可写
        bool writable;
        string writeDetail;
        try
        {
            System.IO.Directory.CreateDirectory(AiConfig.Dir);
            string probe = System.IO.Path.Combine(AiConfig.Dir, "ai.selftest.tmp");
            System.IO.File.WriteAllText(probe, "ok");
            System.IO.File.Delete(probe);
            writable = true;
            writeDetail = AiConfig.Dir;
        }
        catch (Exception e)
        {
            writable = false;
            writeDetail = e.Message;
        }
        all &= writable;
        sb.Append(",{\"name\":\"配置目录可写\",\"ok\":").Append(B(writable))
          .Append(",\"detail\":").Append(J(writeDetail)).Append('}');

        sb.Append("],\"ok_all\":").Append(B(all)).Append('}');
        return sb.ToString();
    }
}
