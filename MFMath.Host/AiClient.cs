// AiClient.cs — OpenAI 兼容端点的流式客户端
//
// 一份适配器覆盖 DeepSeek / OpenAI / Moonshot / 硅基流动 / Ollama / vLLM —— 它们共用
// chat completions 的形状。**刻意不做 provider 注册表**：等真接了形状不同的第二家
// （比如 Anthropic 的 messages），抽象会自己浮出来；现在做只会做出一个没人用的空壳。
//
// 三条纪律（与 MVS Agent 的模型层一致，这里用 C# 落地）：
//   ① **流式是原语**：这个类只有 StreamAsync，阻塞式结果是它的派生（调用方自己收干）。
//   ② **能力缺失是可观测的降级**：有的端点不给 usage、有的不发 [DONE]、
//      有的把坏 JSON 塞进 data —— 这些都不是"崩"，而是 notice 事件。
//   ③ **错误是一等事件**：流吐了两百字之后连接断掉，不是抛异常的场合，而是
//      状态机里的一种正常终止；上层必须能区分"没开始"和"吐了一半"。
//
// 还有两个实测易踩点：
//   · `tool_call_delta` 的参数是**按 index 分组的 JSON 碎片**，拼完才可能合法；
//     第一版不做工具循环，但这里照常发事件（契约先留位，以后不用改这一层）。
//   · usage 尾包的 `choices` 是**空数组**，必须在取 choices[0] 之前处理。
using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace MFMath.Host;

internal enum AiEventKind { Text, Reasoning, ToolCall, Usage, Notice, Done, Error }

internal enum AiFinishReason { Stop, ToolCalls, Length, Aborted, Timeout, Error, Unknown }

internal sealed class AiStreamEvent
{
    public AiEventKind Kind;
    public string Text = "";          // Text / Reasoning / Notice.message / Error.message
    public string NoticeCode = "";
    public int ToolIndex;
    public string ToolId = "";
    public string ToolName = "";
    public string ToolArgsDelta = "";
    public int InputTokens;
    public int OutputTokens;
    public AiFinishReason Reason = AiFinishReason.Unknown;
    public string ErrorKind = "";     // config | network | http | protocol | timeout | aborted
    public int Status;
}

internal sealed class AiMessage
{
    public string Role { get; set; } = "user";
    public string Content { get; set; } = "";
}

internal sealed class AiRequest
{
    public List<AiMessage> Messages { get; set; } = new();
    public string? Model { get; set; }
    public double? Temperature { get; set; }
    public int? MaxTokens { get; set; }
}

internal static class AiClient
{
    // 单例 HttpClient：每请求 new 一个会把连接池打爆（TIME_WAIT 堆积），这是 .NET 的经典坑。
    // 超时不用 HttpClient.Timeout（它是"整个响应"的粗粒度上限，流式会被它提前掐断），
    // 改成每请求一个 CTS + CancelAfter（见 AiBridge）。
    private static readonly HttpClient Http = CreateClient();

    private static HttpClient CreateClient()
    {
        var handler = new SocketsHttpHandler
        {
            ConnectTimeout = TimeSpan.FromSeconds(20),
            PooledConnectionLifetime = TimeSpan.FromMinutes(5),
            AutomaticDecompression = DecompressionMethods.None,   // SSE 不压缩，别乱加 Accept-Encoding
        };
        var c = new HttpClient(handler) { Timeout = Timeout.InfiniteTimeSpan };
        c.DefaultRequestHeaders.TryAddWithoutValidation("Accept", "text/event-stream");
        c.DefaultRequestHeaders.TryAddWithoutValidation("User-Agent", "MFMath-Host/2.0");
        return c;
    }

    private static string JoinUrl(string baseUrl, string path)
        => baseUrl.TrimEnd('/') + path;

    private static StringContent BuildBody(AiConfig cfg, AiRequest req, bool stream)
    {
        var payload = new Dictionary<string, object?>
        {
            ["model"] = string.IsNullOrWhiteSpace(req.Model) ? cfg.Model : req.Model,
            ["messages"] = BuildMessages(req),
            ["temperature"] = req.Temperature ?? cfg.Temperature,
            ["max_tokens"] = req.MaxTokens ?? cfg.MaxTokens,
            ["stream"] = stream,
        };
        // include_usage 让 OpenAI/DeepSeek 在末尾多发一个 usage 尾包；
        // 部分兼容网关不认识这个字段，所以它是可关的（关掉就是 missing_usage 降级，不是错误）。
        if (stream && cfg.IncludeUsage)
            payload["stream_options"] = new Dictionary<string, object?> { ["include_usage"] = true };

        string json = JsonSerializer.Serialize(payload);
        return new StringContent(json, new UTF8Encoding(false), "application/json");
    }

    private static List<Dictionary<string, string>> BuildMessages(AiRequest req)
    {
        var list = new List<Dictionary<string, string>>();
        foreach (var m in req.Messages)
        {
            string role = m.Role switch
            {
                "system" or "user" or "assistant" => m.Role,
                _ => "user",
            };
            list.Add(new Dictionary<string, string> { ["role"] = role, ["content"] = m.Content ?? "" });
        }
        return list;
    }

    /// <summary>
    /// 流式请求。所有事件（含错误与取消）都从 onEvent 出去，**这个方法自己不抛**。
    /// </summary>
    public static async Task StreamAsync(
        AiConfig cfg, string apiKey, AiRequest req,
        Action<AiStreamEvent> onEvent, CancellationToken userToken, CancellationToken timeoutToken)
    {
        // 两个 token 分开传，是为了在收尾时**说清是谁取消的**：
        // "你按了停止"与"超时了"在界面上是两件事，合并成一个 aborted 就分不出来了。
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(userToken, timeoutToken);
        var ct = linked.Token;
        if (string.IsNullOrWhiteSpace(cfg.BaseUrl)) { Emit(onEvent, Error("config", "未配置 API Base", 0)); return; }
        if (string.IsNullOrWhiteSpace(cfg.Model)) { Emit(onEvent, Error("config", "未指定模型", 0)); return; }
        if (string.IsNullOrWhiteSpace(apiKey)) { Emit(onEvent, Error("config", "没有 API Key", 0)); return; }

        bool sawUsage = false, sawDone = false, sawFinishReason = false;
        var finish = AiFinishReason.Unknown;
        bool gotAnyDelta = false;

        HttpResponseMessage? resp = null;
        try
        {
            using var httpReq = new HttpRequestMessage(HttpMethod.Post, JoinUrl(cfg.BaseUrl, "/chat/completions"))
            {
                Content = BuildBody(cfg, req, stream: true),
            };
            httpReq.Headers.TryAddWithoutValidation("Authorization", "Bearer " + apiKey);

            resp = await Http.SendAsync(httpReq, HttpCompletionOption.ResponseHeadersRead, ct)
                             .ConfigureAwait(false);

            if (!resp.IsSuccessStatusCode)
            {
                string detail = await ReadErrorBodyAsync(resp, ct).ConfigureAwait(false);
                Emit(onEvent, Error("http",
                    $"HTTP {(int)resp.StatusCode}{(string.IsNullOrEmpty(resp.ReasonPhrase) ? "" : " " + resp.ReasonPhrase)}"
                    + (string.IsNullOrEmpty(detail) ? "" : " — " + detail),
                    (int)resp.StatusCode));
                return;
            }

            await using var stream = await resp.Content.ReadAsStreamAsync(ct).ConfigureAwait(false);
            var parser = new AiSseParser();
            var decoder = Encoding.UTF8.GetDecoder();          // 有状态：多字节字符跨 chunk 不会被切坏
            var bytes = new byte[8192];
            var chars = new char[8192];

            while (true)
            {
                int read = await stream.ReadAsync(bytes.AsMemory(0, bytes.Length), ct).ConfigureAwait(false);
                if (read <= 0) break;
                int charCount = decoder.GetChars(bytes, 0, read, chars, 0);
                string chunk = new string(chars, 0, charCount);

                foreach (var sse in parser.Feed(chunk))
                {
                    bool stop = HandleEvent(sse, onEvent, ref sawUsage, ref sawDone, ref sawFinishReason,
                                            ref finish, ref gotAnyDelta);
                    if (stop) { sawDone = true; goto finished; }
                }
            }

            // 流正常结束：把没有空行收尾的最后一个事件也处理掉
            var tail = parser.Flush();
            if (tail.HasValue)
                HandleEvent(tail.Value, onEvent, ref sawUsage, ref sawDone, ref sawFinishReason, ref finish, ref gotAnyDelta);

        finished:
            if (!sawUsage)
                Emit(onEvent, Notice("missing_usage", "服务端未返回 usage，本轮 token 统计不可用（正常的兼容性降级）"));
            if (!sawDone && !sawFinishReason)
                Emit(onEvent, Notice("truncated_stream", "流既没有 [DONE] 也没有 finish_reason 就结束了"));
            Emit(onEvent, Done(finish == AiFinishReason.Unknown && gotAnyDelta ? AiFinishReason.Stop : finish));
        }
        catch (OperationCanceledException)
        {
            // 主动取消 / 超时都不是"异常"，是正常终止；两者要能区分开
            bool timeout = timeoutToken.IsCancellationRequested && !userToken.IsCancellationRequested;
            Emit(onEvent, Done(timeout ? AiFinishReason.Timeout : AiFinishReason.Aborted));
        }
        catch (System.IO.IOException e)
        {
            // **流吐了一半之后连接被掐断**走的是这里（socket 断 → ReadAsync 抛 IOException）。
            // 它必须与"协议错"分开：network 意味着重试有可能成功，
            // 而 protocol 是"端点回了看不懂的东西"——重试也一样。
            Emit(onEvent, Error("network", e.Message, 0));
        }
        catch (HttpRequestException e)
        {
            Emit(onEvent, Error("network", e.Message, 0));
        }
        catch (Exception e)
        {
            Emit(onEvent, Error("protocol", e.GetType().Name + ": " + e.Message, 0));
        }
        finally
        {
            resp?.Dispose();
        }
    }

    /// <summary>处理一个 SSE 事件。返回 true 表示遇到 [DONE]，应当收尾。</summary>
    private static bool HandleEvent(
        AiSseEvent sse, Action<AiStreamEvent> onEvent,
        ref bool sawUsage, ref bool sawDone, ref bool sawFinishReason,
        ref AiFinishReason finish, ref bool gotAnyDelta)
    {
        if (sse.Data == "[DONE]") { sawDone = true; return true; }

        JsonDocument doc;
        try { doc = JsonDocument.Parse(sse.Data); }
        catch
        {
            Emit(onEvent, Notice("bad_sse_data", "无法解析的 SSE data：" + Truncate(sse.Data, 200)));
            return false;
        }

        using (doc)
        {
            var root = doc.RootElement;

            // usage 尾包：choices 是空数组，必须先处理它
            if (root.TryGetProperty("usage", out var usage) && usage.ValueKind == JsonValueKind.Object)
            {
                sawUsage = true;
                Emit(onEvent, new AiStreamEvent
                {
                    Kind = AiEventKind.Usage,
                    InputTokens = GetInt(usage, "prompt_tokens"),
                    OutputTokens = GetInt(usage, "completion_tokens"),
                });
            }

            if (!root.TryGetProperty("choices", out var choices) || choices.ValueKind != JsonValueKind.Array
                || choices.GetArrayLength() == 0)
                return false;

            var choice = choices[0];
            if (choice.TryGetProperty("delta", out var delta) && delta.ValueKind == JsonValueKind.Object)
            {
                // DeepSeek 用 reasoning_content，部分端点用 reasoning
                string reasoning = GetString(delta, "reasoning_content");
                if (reasoning.Length == 0) reasoning = GetString(delta, "reasoning");
                if (reasoning.Length > 0)
                {
                    gotAnyDelta = true;
                    Emit(onEvent, new AiStreamEvent { Kind = AiEventKind.Reasoning, Text = reasoning });
                }

                string content = GetString(delta, "content");
                if (content.Length > 0)
                {
                    gotAnyDelta = true;
                    Emit(onEvent, new AiStreamEvent { Kind = AiEventKind.Text, Text = content });
                }

                if (delta.TryGetProperty("tool_calls", out var calls) && calls.ValueKind == JsonValueKind.Array)
                {
                    foreach (var call in calls.EnumerateArray())
                    {
                        if (!call.TryGetProperty("index", out var idx) || idx.ValueKind != JsonValueKind.Number)
                            continue;
                        var ev = new AiStreamEvent { Kind = AiEventKind.ToolCall, ToolIndex = idx.GetInt32() };
                        if (call.TryGetProperty("id", out var id) && id.ValueKind == JsonValueKind.String)
                            ev.ToolId = id.GetString() ?? "";
                        if (call.TryGetProperty("function", out var fn) && fn.ValueKind == JsonValueKind.Object)
                        {
                            ev.ToolName = GetString(fn, "name");
                            ev.ToolArgsDelta = GetString(fn, "arguments");
                        }
                        Emit(onEvent, ev);
                    }
                }
            }

            if (choice.TryGetProperty("finish_reason", out var fr) && fr.ValueKind == JsonValueKind.String)
            {
                sawFinishReason = true;
                finish = MapFinishReason(fr.GetString());
            }
        }
        return false;
    }

    private static AiFinishReason MapFinishReason(string? raw) => raw switch
    {
        "stop" => AiFinishReason.Stop,
        "tool_calls" => AiFinishReason.ToolCalls,
        "length" => AiFinishReason.Length,
        _ => AiFinishReason.Unknown,
    };

    private static int GetInt(JsonElement obj, string name)
        => obj.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.Number ? v.GetInt32() : 0;

    private static string GetString(JsonElement obj, string name)
        => obj.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? (v.GetString() ?? "") : "";

    private static async Task<string> ReadErrorBodyAsync(HttpResponseMessage resp, CancellationToken ct)
    {
        try
        {
            string text = await resp.Content.ReadAsStringAsync(ct).ConfigureAwait(false);
            return Truncate(text.Trim(), 400);
        }
        catch { return ""; }
    }

    private static string Truncate(string s, int max)
        => string.IsNullOrEmpty(s) || s.Length <= max ? s : s.Substring(0, max) + "…";

    private static void Emit(Action<AiStreamEvent> onEvent, AiStreamEvent ev)
    {
        try { onEvent(ev); } catch { /* 下游（推送）失败不能反过来打断流 */ }
    }

    private static AiStreamEvent Notice(string code, string message)
        => new() { Kind = AiEventKind.Notice, NoticeCode = code, Text = message };

    private static AiStreamEvent Done(AiFinishReason reason)
        => new() { Kind = AiEventKind.Done, Reason = reason };

    private static AiStreamEvent Error(string kind, string message, int status)
        => new() { Kind = AiEventKind.Error, ErrorKind = kind, Text = message, Status = status };

    /// <summary>连通用测试：非流式、max_tokens=1。返回 (ok, status, ms, detail)。</summary>
    public static async Task<(bool ok, int status, long ms, string detail)> TestAsync(
        AiConfig cfg, string apiKey, CancellationToken ct)
    {
        var sw = System.Diagnostics.Stopwatch.StartNew();
        try
        {
            using var req = new HttpRequestMessage(HttpMethod.Post, JoinUrl(cfg.BaseUrl, "/chat/completions"))
            {
                Content = BuildBody(cfg, new AiRequest
                {
                    Messages = new List<AiMessage> { new() { Role = "user", Content = "ping" } },
                    MaxTokens = 1,
                }, stream: false),
            };
            req.Headers.TryAddWithoutValidation("Authorization", "Bearer " + apiKey);

            using var resp = await Http.SendAsync(req, ct).ConfigureAwait(false);
            sw.Stop();
            if (!resp.IsSuccessStatusCode)
            {
                string detail = await ReadErrorBodyAsync(resp, ct).ConfigureAwait(false);
                return (false, (int)resp.StatusCode, sw.ElapsedMilliseconds,
                        Truncate(detail, 300));
            }

            string body = await resp.Content.ReadAsStringAsync(ct).ConfigureAwait(false);
            string model = "";
            try
            {
                using var doc = JsonDocument.Parse(body);
                if (doc.RootElement.TryGetProperty("model", out var m) && m.ValueKind == JsonValueKind.String)
                    model = m.GetString() ?? "";
            }
            catch { /* 形状不认识也不影响"通了"这个结论 */ }
            return (true, (int)resp.StatusCode, sw.ElapsedMilliseconds,
                    model.Length > 0 ? "模型：" + model : "端点已响应");
        }
        catch (OperationCanceledException)
        {
            sw.Stop();
            return (false, 0, sw.ElapsedMilliseconds, "已取消或超时");
        }
        catch (Exception e)
        {
            sw.Stop();
            return (false, 0, sw.ElapsedMilliseconds, e.GetType().Name + "：" + e.Message);
        }
    }
}
