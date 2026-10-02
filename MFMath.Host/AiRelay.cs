// AiRelay.cs — 宿主中继：**带密钥发请求，把响应原始字节转回页面**
//
// 这里刻意**不理解 SSE**，也不理解 OpenAI 的分片语义。它只做四件事：
//   ① 校验调用方给的是**相对路径**（安全边界，见下）；
//   ② 用宿主自己保管的密钥加上 Authorization；
//   ③ 把响应头、响应体的原始字节（base64）依次推给页面；
//   ④ 取消 / 超时 / 把失败归类成"重试有没有意义"。
//
// 协议语义（SSE 分帧、usage 尾包、reasoning_content、[DONE]、降级通知）全在
// TS 那一份实现里：MF_UI/MFMath.UI.Vue/src/lib/ai/{sse,client,collect}.ts。
//
// ── 为什么把这条边界放在这里（而不是让页面直接 fetch）──
//   · **密钥**：页面直连就得自己持有 API Key，落点只能是 localStorage/内存。
//     本项目已经有渲染进程注入面的现实案例（教程富文本清洗那个绕过），
//     所以密钥一步都不该进渲染进程。页面对外只见 hasKey/keySource。
//   · **端点可配**：baseUrl 允许填自建/中转端点，这类不少不发 CORS 头
//     （本项目自己的假端点就是），宿主侧则对任何端点都成立。
//
// ── 安全边界（关键）──
// 中继天然是一个"替我发一次请求"的原语。如果允许页面传**绝对 URL**，
// 它就变成"把密钥发到任意地址"——页面里一段注入脚本就能把 key 骗走。
// 所以：
//   · 只接受以单个 `/` 开头的路径（`//host` 这种协议相对 URL 也拒绝）；
//   · 端点来自宿主自己的配置，页面无从指定；
//   · Authorization 由这里加，页面传的任何头都不会被转发。
//
// 事件话题：ai.http（状态行）· ai.raw（base64 字节块）· ai.rawEnd · ai.rawError
using System;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace MFMath.Host;

internal static class AiRelay
{
    /// <summary>
    /// 路径校验：必须是以单个 '/' 开头的相对路径。
    /// 这是防止"密钥被发到任意地址"的那道闸 —— 不要放宽它。
    /// </summary>
    public static bool ValidatePath(string? path, out string error)
    {
        error = "";
        if (string.IsNullOrWhiteSpace(path)) { error = "路径为空"; return false; }
        string p = path.Trim();
        if (p[0] != '/') { error = "只接受相对路径（如 /chat/completions）；不接收绝对地址"; return false; }
        if (p.Length > 1 && p[1] == '/') { error = "拒绝协议相对地址（//host）"; return false; }
        if (p.Contains("://", StringComparison.Ordinal)) { error = "路径里不允许出现协议头"; return false; }
        if (p.Contains("..", StringComparison.Ordinal)) { error = "路径里不允许出现 .."; return false; }
        if (p.Contains('\n') || p.Contains('\r')) { error = "路径里不允许换行"; return false; }
        return true;
    }

    /// <summary>
    /// 发起一次中继。返回 (ok, requestId, error, kind)。任何线程可调；
    /// 字节通过 PushHub 异步推出去。
    /// </summary>
    public static (bool ok, string requestId, string error, string kind) Begin(
        AiConfig cfg, string apiKey, string json, out string failure)
    {
        failure = "";
        string path = "/chat/completions";
        string bodyJson = "{}";

        try
        {
            using var doc = System.Text.Json.JsonDocument.Parse(json);
            var root = doc.RootElement;
            if (root.TryGetProperty("path", out var p) && p.ValueKind == System.Text.Json.JsonValueKind.String)
                path = p.GetString() ?? path;
            if (root.TryGetProperty("body", out var b))
                bodyJson = b.GetRawText();
        }
        catch (Exception e)
        {
            failure = "请求体解析失败：" + e.Message;
            return (false, "", failure, "config");
        }

        if (!ValidatePath(path, out string pathError))
        {
            failure = pathError;
            return (false, "", failure, "config");
        }

        string id = "r" + Interlocked.Increment(ref _seq);
        var turn = new RelayTurn { Id = id, Path = path };
        Turns[id] = turn;

        Task.Run(async () =>
        {
            // 超时与"用户取消"是两个 token：收尾时才能说清是谁取消的
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(cfg.TimeoutSec));
            try
            {
                await PumpAsync(cfg, apiKey, id, path, bodyJson, turn.Cts.Token, timeout.Token).ConfigureAwait(false);
            }
            catch (Exception e)
            {
                PushError(id, "protocol", e.GetType().Name + "：" + e.Message, 0);
            }
            finally
            {
                turn.State = "done";
            }
        });

        return (true, id, "", "");
    }

    private static long _seq;
    private static readonly System.Collections.Concurrent.ConcurrentDictionary<string, RelayTurn> Turns = new();

    internal sealed class RelayTurn
    {
        public string Id = "";
        public string Path = "";
        public volatile string State = "running";
        public readonly CancellationTokenSource Cts = new();
    }

    internal static bool Busy()
    {
        foreach (var kv in Turns) if (kv.Value.State == "running") return true;
        return false;
    }

    internal static int CancelAll()
    {
        int n = 0;
        foreach (var kv in Turns)
        {
            if (kv.Value.State != "running") continue;
            try { kv.Value.Cts.Cancel(); n++; } catch { }
        }
        return n;
    }

    internal static bool Cancel(string requestId)
    {
        if (Turns.TryGetValue(requestId ?? "", out var turn))
        {
            try { turn.Cts.Cancel(); } catch { }
            return true;
        }
        return false;
    }

    internal static int RunningCount()
    {
        int n = 0;
        foreach (var kv in Turns) if (kv.Value.State == "running") n++;
        return n;
    }

    private static async Task PumpAsync(
        AiConfig cfg, string apiKey, string id, string path, string bodyJson,
        CancellationToken userToken, CancellationToken timeoutToken)
    {
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(userToken, timeoutToken);
        var ct = linked.Token;

        HttpResponseMessage? resp = null;
        long bytes = 0;
        try
        {
            using var req = new HttpRequestMessage(HttpMethod.Post, AiClient.JoinUrl(cfg.BaseUrl, path))
            {
                Content = new StringContent(bodyJson, new UTF8Encoding(false), "application/json"),
            };
            req.Headers.TryAddWithoutValidation("Authorization", "Bearer " + apiKey);
            req.Headers.TryAddWithoutValidation("Accept", "text/event-stream");

            resp = await AiClient.Shared.SendAsync(req, HttpCompletionOption.ResponseHeadersRead, ct)
                                  .ConfigureAwait(false);

            // 状态行先推：TS 那边要靠它区分 2xx 与错误体
            PushHub.Send("ai.http", "{\"requestId\":" + PushHub.Str(id)
                + ",\"status\":" + (int)resp.StatusCode
                + ",\"statusText\":" + PushHub.Str(resp.ReasonPhrase ?? "") + "}");

            await using var stream = await resp.Content.ReadAsStreamAsync(ct).ConfigureAwait(false);
            var buffer = new byte[16 * 1024];
            var carry = new MemoryStream();

            while (true)
            {
                int read = await stream.ReadAsync(buffer.AsMemory(0, buffer.Length), ct).ConfigureAwait(false);
                if (read <= 0) break;

                // 字节按原样转出去（base64），**不做任何分帧**：
                // 分帧是 TS 那边的事，宿主只需要保证字节顺序与完整性。
                // 每个读取块推一次：SSE 的块很小（几百字节），为了延迟不做合并 ——
                // 合并会让最后一个事件卡在缓冲里，界面看起来"卡住不动了"。
                if (carry.Length > 0)
                {
                    carry.Write(buffer, 0, read);
                    var all = carry.ToArray();
                    carry.SetLength(0);
                    PushChunk(id, all);
                    bytes += all.Length;
                }
                else
                {
                    var chunk = new byte[read];
                    Array.Copy(buffer, chunk, read);
                    PushChunk(id, chunk);
                    bytes += read;
                }
            }

            PushHub.Send("ai.rawEnd", "{\"requestId\":" + PushHub.Str(id) + ",\"bytes\":" + bytes + "}");
        }
        catch (OperationCanceledException)
        {
            bool timeout = timeoutToken.IsCancellationRequested && !userToken.IsCancellationRequested;
            PushError(id, timeout ? "timeout" : "aborted",
                      timeout ? "本轮超过设定的超时时间（可在设置 → AI 里调整）" : "已取消", 0);
        }
        catch (IOException e)
        {
            // 流吐了一半之后连接被掐断走这里。与"协议错"分开：
            // network 意味着重试可能成功，protocol 是"端点回了看不懂的东西"。
            PushError(id, "network", e.Message, 0);
        }
        catch (HttpRequestException e)
        {
            PushError(id, "network", e.Message, 0);
        }
        finally
        {
            resp?.Dispose();
        }
    }

    private static void PushChunk(string id, byte[] chunk)
    {
        PushHub.Send("ai.raw", "{\"requestId\":" + PushHub.Str(id)
            + ",\"b64\":" + PushHub.Str(Convert.ToBase64String(chunk)) + "}");
    }

    private static void PushError(string id, string kind, string message, int status)
    {
        PushHub.Send("ai.rawError", "{\"requestId\":" + PushHub.Str(id)
            + ",\"kind\":" + PushHub.Str(kind)
            + ",\"status\":" + status
            + ",\"message\":" + PushHub.Str(message) + "}");
    }

    /// <summary>自检用：base64 往返是否无损（字节经推送转手就靠它）</summary>
    public static bool Base64RoundTrip()
    {
        var probe = new byte[] { 0, 1, 2, 127, 128, 255, 10, 13, 0xE4, 0xB8, 0xAD };
        var back = Convert.FromBase64String(Convert.ToBase64String(probe));
        if (back.Length != probe.Length) return false;
        for (int i = 0; i < probe.Length; i++) if (back[i] != probe[i]) return false;
        return true;
    }
}
