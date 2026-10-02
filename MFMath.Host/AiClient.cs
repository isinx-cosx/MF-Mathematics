// AiClient.cs — 宿主侧与端点打交道的最小公共件 + 连通性测试
//
// 这里**不再有流式客户端**。原来那套 C# SSE 分帧 / OpenAI 分片解析已经删掉，
// 全部搬到 TS（MF_UI/.../src/lib/ai/{sse,client,collect}.ts，移植自 MVS Agent）。
// 宿主只做两件事，都在 AiRelay.cs：
//   · 用自己保管的密钥发这个请求；
//   · 把响应原始字节转回页面。
//
// 这样做的理由（也是这次改动的原因）：
//   · SSE 分帧、OpenAI 的碎包语义、错误分类**只该有一份实现**。
//     两边各写一套的后果，正是 MVS Agent README 里那句「两份实现不一致 =
//     一直在线的界面和刚刷新的界面显示不同的东西」；
//   · TS 是允许的语言 —— 这个项目的硬约束是"计算在 C++"，不是"界面只能写 JS"。
//     协议这种纯逻辑放在 TS 里，还能脱离宿主做离线单元测试（tests/unit-sse.mjs）。
//
// 这里留下的是"必须贴着 Windows/.NET 才成立"的部分：HttpClient、JSON 拼装、
// 超时、以及在宿主侧算错误分类（哪种失败重试可能有意义）。
using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace MFMath.Host;

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
    // 改成每请求一个 CTS（见 AiRelay）。
    private static readonly HttpClient Http = CreateClient();

    /// <summary>共享实例：AiRelay 与连通性测试都必须复用同一个连接池</summary>
    internal static HttpClient Shared => Http;

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

    internal static string JoinUrl(string baseUrl, string path)
        => baseUrl.TrimEnd('/') + path;

    internal static StringContent BuildBody(AiRequest req, string model)
    {
        var payload = new Dictionary<string, object?>
        {
            ["model"] = string.IsNullOrWhiteSpace(req.Model) ? model : req.Model,
            ["messages"] = BuildMessages(req),
            ["stream"] = false,
        };
        if (req.Temperature.HasValue) payload["temperature"] = req.Temperature.Value;
        if (req.MaxTokens.HasValue) payload["max_tokens"] = req.MaxTokens.Value;

        string json = JsonSerializer.Serialize(payload);
        return new StringContent(json, new UTF8Encoding(false), "application/json");
    }

    internal static List<Dictionary<string, string>> BuildMessages(AiRequest req)
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

    internal static async Task<string> ReadErrorBodyAsync(HttpResponseMessage resp, CancellationToken ct)
    {
        try
        {
            string text = await resp.Content.ReadAsStringAsync(ct).ConfigureAwait(false);
            return Truncate(text.Trim(), 400);
        }
        catch { return ""; }
    }

    internal static string Truncate(string s, int max)
        => string.IsNullOrEmpty(s) || s.Length <= max ? s : s.Substring(0, max) + "…";

    /// <summary>
    /// 连通性测试：非流式、max_tokens=1。返回 (ok, status, ms, detail)。
    /// 它不解析 SSE，所以留在宿主侧不构成"第二套实现"；结果经推送话题 ai.test 回页面。
    /// </summary>
    public static async Task<(bool ok, int status, long ms, string detail)> TestAsync(
        AiConfig cfg, string apiKey, CancellationToken ct)
    {
        var sw = System.Diagnostics.Stopwatch.StartNew();
        try
        {
            using var req = new HttpRequestMessage(HttpMethod.Post, JoinUrl(cfg.BaseUrl, "/chat/completions"))
            {
                Content = BuildBody(new AiRequest
                {
                    Messages = new List<AiMessage> { new() { Role = "user", Content = "ping" } },
                    MaxTokens = 1,
                }, cfg.Model),
            };
            req.Headers.TryAddWithoutValidation("Authorization", "Bearer " + apiKey);

            using var resp = await Http.SendAsync(req, ct).ConfigureAwait(false);
            sw.Stop();
            if (!resp.IsSuccessStatusCode)
            {
                string detail = await ReadErrorBodyAsync(resp, ct).ConfigureAwait(false);
                return (false, (int)resp.StatusCode, sw.ElapsedMilliseconds, Truncate(detail, 300));
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
