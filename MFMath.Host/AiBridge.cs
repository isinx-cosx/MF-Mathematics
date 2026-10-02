// AiBridge.cs — AI 助手桥（JS 侧：hostObjects.sync.ai）
//
// 为什么放在宿主而不是让页面直接 fetch：
//   ① **密钥不进渲染进程**。页面对外只看到"有没有密钥"，密钥只在宿主内存与
//      DPAPI 密文里；一旦让页面自己调端点，密钥就必须先出现在页面里。
//   ② 页面跑在虚拟主机 `https://mfmath.local` 下，直连外部端点会撞 CORS；
//      而且 `Authorization` 头这种东西不该由渲染进程持有。
//   ③ 流式要"边收边推"，宿主已经有推送通道（PushHub），正好是它的用武之地。
//
// 与页面的分工：
//   页面负责**组装消息**（系统提示、上下文、历史按隐私开关取舍）与**渲染**；
//   宿主负责**传输**（SSE 分帧、超时、取消、错误分类）与**密钥**。
//   所以 Start 的入参就是最终的 messages 数组 —— 宿主不猜哪些该发、哪些不该发，
//   但它也**不会**替页面去读历史或代码：那些内容根本不会经过宿主。
//
// 事件话题（都带 requestId，页面按 id 归并）：
//   ai.started · ai.delta · ai.reasoning · ai.toolcall · ai.usage · ai.notice
//   ai.done · ai.error · ai.test（连通性自检结果）
//
// 关于 ai.toolcall：第一版**不执行**任何工具调用（决策：先做对话+解释+上下文），
// 但事件照发、契约先留位 —— 以后加"AI 调度引擎"时不用改传输层，只需在页面侧接。
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace MFMath.Host;

[ComVisible(true)]
public class AiBridge
{
    /// <summary>增量合并窗口：40ms 或 64 字符，先到先发。</summary>
    private const int FlushMs = 40;
    private const int FlushChars = 64;

    private sealed class Turn
    {
        public string Id = "";
        public string Model = "";
        public long StartedMs;
        public int Chars;
        public volatile string State = "running";   // running | done | error
        public readonly CancellationTokenSource Cts = new();
        public readonly StringBuilder PendingText = new();
        public readonly StringBuilder PendingReasoning = new();
        public long LastFlushMs;
    }

    private static readonly ConcurrentDictionary<string, Turn> Turns = new();
    private static readonly object ConfigLock = new();
    private static AiConfig? _config;

    /// <summary>DPAPI 不可用时的兜底：密钥只留在内存，重启后需要重填（**绝不写明文到磁盘**）</summary>
    private static string _memoryKey = "";

    private static long _seq;
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

    /* ── JSON 小工具（与 PushHub/SettingsBridge 同风格：手拼，避免序列化器把字段名改掉）── */

    private static string J(string? s)
    {
        if (s == null) return "null";
        var sb = new StringBuilder(s.Length + 2);
        sb.Append('"');
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
                    if (c < ' ') sb.Append("\\u").Append(((int)c).ToString("x4"));
                    else sb.Append(c);
                    break;
            }
        }
        return sb.Append('"').ToString();
    }

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
        sb.Append(",\"running\":").Append(RunningJson());
        sb.Append('}');
        return sb.ToString();
    }

    private static string RunningJson()
    {
        var sb = new StringBuilder("[");
        bool first = true;
        foreach (var kv in Turns)
        {
            var t = kv.Value;
            if (t.State != "running") continue;
            if (!first) sb.Append(',');
            first = false;
            sb.Append("{\"requestId\":").Append(J(t.Id))
              .Append(",\"model\":").Append(J(t.Model))
              .Append(",\"chars\":").Append(t.Chars)
              .Append(",\"elapsedMs\":").Append(Environment.TickCount64 - t.StartedMs)
              .Append('}');
        }
        return sb.Append(']').ToString();
    }

    /// <summary>当前是否有请求在跑（页面刷新后靠它决定要不要显示"正在输出"）</summary>
    public bool Busy()
    {
        foreach (var kv in Turns) if (kv.Value.State == "running") return true;
        return false;
    }

    /// <summary>密钥从哪来（供设置面板显示"，不返回密钥内容）</summary>
    public string KeySource()
    {
        if (!string.IsNullOrEmpty(_memoryKey)) return "memory";
        if (!string.IsNullOrEmpty(Config.ApiKeyProtected)) return "dpapi";
        return "none";
    }

    /* ── 配置写入 ───────────────────────────────────────────────────────── */

    /// <summary>
    /// 更新非密钥配置。入参是**只含要改的字段**的 JSON（页面只发改动过的字段，
    /// 整份回传会把界面没显示的字段以默认值悄悄写回磁盘）。返回 {"ok":true} 或 {"ok":false,"error":...}。
    /// </summary>
    public string Configure(string json)
    {
        try
        {
            using var doc = System.Text.Json.JsonDocument.Parse(json);
            var root = doc.RootElement;
            var cfg = Config;
            bool changed = false;

            // 属性不能按 ref 传，所以先落到局部变量，最后统一写回。
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

    /* ── 对话 ───────────────────────────────────────────────────────────── */

    /// <summary>
    /// 开始一轮对话。入参：
    /// <code>{"messages":[{"role":"system","content":"..."},{"role":"user","content":"..."}],
    ///        "model":"deepseek-chat","temperature":0.6,"maxTokens":2048}</code>
    /// 立即返回 {"ok":true,"requestId":"ai1"}；内容与状态全部走推送话题。
    /// </summary>
    public string Start(string json)
    {
        var cfg = Config;
        if (!cfg.Enabled) return Fail("AI 未启用（设置 → AI 里打开）");

        string key = ResolveKey();
        if (string.IsNullOrEmpty(key))
            return Fail(cfg.ApiKeyProtected.Length > 0
                ? "密钥无法解密（可能换了 Windows 用户或文件被改动），请重新填写"
                : "还没有配置 API Key");

        AiRequest req;
        try { req = ParseRequest(json); }
        catch (Exception e) { return Fail("请求解析失败：" + e.Message); }

        if (req.Messages.Count == 0) return Fail("消息为空");

        foreach (var kv in Turns)
            if (kv.Value.State == "running") return Fail("已有一轮对话在输出，请先停止它");

        string id = "ai" + Interlocked.Increment(ref _seq);
        var turn = new Turn
        {
            Id = id,
            Model = string.IsNullOrWhiteSpace(req.Model) ? cfg.Model : req.Model!,
            StartedMs = Environment.TickCount64,
            LastFlushMs = Environment.TickCount64,
        };
        Turns[id] = turn;

        PushHub.Send("ai.started", "{\"requestId\":" + J(id) + ",\"model\":" + J(turn.Model)
                                 + ",\"startedAt\":" + DateTimeOffset.Now.ToUnixTimeMilliseconds() + "}");

        Task.Run(async () =>
        {
            // 超时与"用户取消"是**两个** token：收尾时才能说清是"你按了停止"还是"超时了"
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(cfg.TimeoutSec));
            try
            {
                await AiClient.StreamAsync(cfg, key, req, ev => OnEvent(turn, ev), turn.Cts.Token, timeout.Token)
                              .ConfigureAwait(false);
            }
            catch (Exception e)
            {
                // StreamAsync 自己不抛；真抛了也当成一条 error 事件，绝不让后台线程静默死掉
                PushError(turn, "unknown", e.Message, 0);
            }
            finally
            {
                Flush(turn, force: true);
                turn.State = turn.State == "error" ? "error" : "done";
            }
        });

        return "{\"ok\":true,\"requestId\":" + J(id) + "}";
    }

    /// <summary>停止一轮输出（页面点"停止"、或窗口关闭时调用）</summary>
    public string Cancel(string requestId)
    {
        if (Turns.TryGetValue(requestId ?? "", out var turn))
        {
            try { turn.Cts.Cancel(); } catch { }
            return "{\"ok\":true}";
        }
        return "{\"ok\":false,\"error\":\"没有这个请求\"}";
    }

    public string CancelAll()
    {
        int n = 0;
        foreach (var kv in Turns)
        {
            if (kv.Value.State != "running") continue;
            try { kv.Value.Cts.Cancel(); n++; } catch { }
        }
        return "{\"ok\":true,\"cancelled\":" + n + "}";
    }

    /* ── 事件 → 推送 ────────────────────────────────────────────────────── */

    private static AiRequest ParseRequest(string json)
    {
        using var doc = System.Text.Json.JsonDocument.Parse(json);
        var root = doc.RootElement;
        var req = new AiRequest();

        if (root.TryGetProperty("model", out var modelEl) && modelEl.ValueKind == System.Text.Json.JsonValueKind.String)
            req.Model = modelEl.GetString();
        if (root.TryGetProperty("temperature", out var tempEl) && tempEl.ValueKind == System.Text.Json.JsonValueKind.Number)
            req.Temperature = tempEl.GetDouble();
        if (root.TryGetProperty("maxTokens", out var maxEl) && maxEl.ValueKind == System.Text.Json.JsonValueKind.Number)
            req.MaxTokens = maxEl.GetInt32();

        if (root.TryGetProperty("messages", out var msgs) && msgs.ValueKind == System.Text.Json.JsonValueKind.Array)
        {
            foreach (var item in msgs.EnumerateArray())
            {
                if (item.ValueKind != System.Text.Json.JsonValueKind.Object) continue;
                var msg = new AiMessage();
                if (item.TryGetProperty("role", out var r) && r.ValueKind == System.Text.Json.JsonValueKind.String)
                    msg.Role = r.GetString() ?? "user";
                if (item.TryGetProperty("content", out var c))
                {
                    if (c.ValueKind == System.Text.Json.JsonValueKind.String) msg.Content = c.GetString() ?? "";
                    // 富内容数组第一版不支持：宁可明确报错，也不要悄悄丢首段
                    else if (c.ValueKind == System.Text.Json.JsonValueKind.Array)
                        throw new NotSupportedException("content 暂只支持字符串");
                }
                req.Messages.Add(msg);
            }
        }
        return req;
    }

    private void OnEvent(Turn turn, AiStreamEvent ev)
    {
        switch (ev.Kind)
        {
            case AiEventKind.Text:
                turn.Chars += ev.Text.Length;
                lock (turn.PendingText) turn.PendingText.Append(ev.Text);
                Flush(turn, force: false);
                break;

            case AiEventKind.Reasoning:
                lock (turn.PendingReasoning) turn.PendingReasoning.Append(ev.Text);
                Flush(turn, force: false);
                break;

            case AiEventKind.ToolCall:
                // 第一版不执行工具调用，但事件照发（契约留位：以后接"AI 调度引擎"不用改传输层）
                PushHub.Send("ai.toolcall", "{\"requestId\":" + J(turn.Id)
                    + ",\"index\":" + ev.ToolIndex
                    + ",\"id\":" + J(ev.ToolId)
                    + ",\"name\":" + J(ev.ToolName)
                    + ",\"argsDelta\":" + J(ev.ToolArgsDelta) + "}");
                break;

            case AiEventKind.Usage:
                Flush(turn, force: true);
                PushHub.Send("ai.usage", "{\"requestId\":" + J(turn.Id)
                    + ",\"inputTokens\":" + ev.InputTokens
                    + ",\"outputTokens\":" + ev.OutputTokens + "}");
                break;

            case AiEventKind.Notice:
                Flush(turn, force: true);
                PushHub.Send("ai.notice", "{\"requestId\":" + J(turn.Id)
                    + ",\"code\":" + J(ev.NoticeCode)
                    + ",\"message\":" + J(ev.Text) + "}");
                break;

            case AiEventKind.Error:
                Flush(turn, force: true);
                turn.State = "error";
                PushError(turn, ev.ErrorKind, ev.Text, ev.Status);
                break;

            case AiEventKind.Done:
                Flush(turn, force: true);
                PushHub.Send("ai.done", "{\"requestId\":" + J(turn.Id)
                    + ",\"reason\":" + J(ReasonName(ev.Reason))
                    + ",\"chars\":" + turn.Chars
                    + ",\"elapsedMs\":" + (Environment.TickCount64 - turn.StartedMs) + "}");
                if (turn.State == "running") turn.State = "done";
                break;
        }
    }

    private static string ReasonName(AiFinishReason r) => r switch
    {
        AiFinishReason.Stop => "stop",
        AiFinishReason.ToolCalls => "tool_calls",
        AiFinishReason.Length => "length",
        AiFinishReason.Aborted => "aborted",
        AiFinishReason.Timeout => "timeout",
        AiFinishReason.Error => "error",
        _ => "unknown",
    };

    private void PushError(Turn turn, string kind, string message, int status)
    {
        _lastError = kind + ": " + message;
        PushHub.Send("ai.error", "{\"requestId\":" + J(turn.Id)
            + ",\"kind\":" + J(kind)
            + ",\"status\":" + status
            + ",\"message\":" + J(message) + "}");
    }

    /// <summary>
    /// 增量合并：攒够 64 字符、或过了 40ms 就发一次；force=true（usage/notice/done/error/收尾）一定发。
    /// 一个字符一条推送会把 WebView2 的消息通道打满（长回复时界面会明显发涩），
    /// 而攒太久又会让人以为"没反应了"，所以两个阈值都要有。
    /// </summary>
    private static void Flush(Turn turn, bool force)
    {
        int pendingText, pendingReasoning;
        lock (turn.PendingText) pendingText = turn.PendingText.Length;
        lock (turn.PendingReasoning) pendingReasoning = turn.PendingReasoning.Length;
        if (pendingText == 0 && pendingReasoning == 0) return;

        long now = Environment.TickCount64;
        if (!force && pendingText + pendingReasoning < FlushChars && now - turn.LastFlushMs < FlushMs)
            return;   // 内容留在缓冲里，等下一个增量或下一个时间片

        string text, reasoning;
        lock (turn.PendingText)
        {
            text = turn.PendingText.ToString();
            turn.PendingText.Clear();
        }
        lock (turn.PendingReasoning)
        {
            reasoning = turn.PendingReasoning.ToString();
            turn.PendingReasoning.Clear();
        }

        if (text.Length > 0)
        {
            // 单条推送最多带 4KB
            const int maxChunk = 4096;
            for (int i = 0; i < text.Length; i += maxChunk)
            {
                string part = text.Substring(i, Math.Min(maxChunk, text.Length - i));
                PushHub.Send("ai.delta", "{\"requestId\":" + J(turn.Id) + ",\"text\":" + J(part) + "}");
            }
        }
        if (reasoning.Length > 0)
        {
            PushHub.Send("ai.reasoning", "{\"requestId\":" + J(turn.Id) + ",\"text\":" + J(reasoning) + "}");
        }
        turn.LastFlushMs = now;
    }

    /* ── 自检（设置面板的"AI"组要有一行能跑的自检）───────────────────────── */

    /// <summary>
    /// 三项自检：DPAPI 能不能用、SSE 分帧在**任意切分**下是否一致、配置目录可写。
    /// 分帧那一项用的是内置样本，不联网 —— 自检不该依赖网络。
    /// </summary>
    public string SelfCheck()
    {
        var sb = new StringBuilder("{\"ok\":true,\"checks\":[");
        bool all = true;

        // ① DPAPI —— **不可用不算失败**：那是降级（密钥只留内存），不是故障。
        //    所以它单独报 ok，但不参与 ok_all。
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

        // ② SSE 分帧：同一份样本按 1/2/3/5/17/64 字节切，结果必须完全一致
        const string sample = "data: {\"a\":1}\n\ndata: two\r\n\r\n: ping\ndata: three\n\n";
        var baseline = ParseSample(sample, sample.Length);
        bool framingOk = baseline.Count == 3
                         && baseline[0].Data == "{\"a\":1}"
                         && baseline[1].Data == "two"
                         && baseline[2].Data == "three";
        string framingDetail = framingOk ? "3 个事件，基线正确" : "基线不正确（" + baseline.Count + " 个事件）";
        foreach (int size in new[] { 1, 2, 3, 5, 17, 64 })
        {
            var sliced = ParseSample(sample, size);
            if (sliced.Count != baseline.Count)
            {
                framingOk = false;
                framingDetail = "按 " + size + " 字节切分后事件数不同（" + sliced.Count + "/" + baseline.Count + "）";
                break;
            }
            for (int i = 0; i < sliced.Count; i++)
            {
                if (sliced[i].Data != baseline[i].Data)
                {
                    framingOk = false;
                    framingDetail = "按 " + size + " 字节切分后第 " + (i + 1) + " 个事件内容不同";
                    break;
                }
            }
            if (!framingOk) break;
        }
        if (framingOk) framingDetail = "1/2/3/5/17/64 字节切分下结果一致";
        all &= framingOk;
        sb.Append(",{\"name\":\"SSE 分帧（任意切分一致）\",\"ok\":").Append(B(framingOk))
          .Append(",\"detail\":").Append(J(framingDetail)).Append('}');

        // ③ 配置目录可写
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

    private static List<AiSseEvent> ParseSample(string text, int chunkSize)
    {
        var parser = new AiSseParser();
        var events = new List<AiSseEvent>();
        var bytes = Encoding.UTF8.GetBytes(text);
        for (int i = 0; i < bytes.Length; i += chunkSize)
        {
            int len = Math.Min(chunkSize, bytes.Length - i);
            // 这里刻意用**无状态**方式解码：样本是 ASCII，精确模拟"按字节切"
            events.AddRange(parser.Feed(Encoding.UTF8.GetString(bytes, i, len)));
        }
        var tail = parser.Flush();
        if (tail.HasValue) events.Add(tail.Value);
        return events;
    }
}
