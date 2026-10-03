// AccountApi.cs — 站点账号接口的客户端（宿主侧，C#）
//
// 契约来自站点现成的实现（Next.js 侧 src/app/api/*），**不是我们发明的**：
//   POST /api/login            表单 username, password[, remember] → {access_token, token_type, expires_in}
//   POST /api/token/refresh    表单（可带 remember）+ Bearer      → 同上（本轮为桌面端新增）
//   GET  /api/me               Bearer → {username, email, balance, has_ai_service, role, is_active}
//   POST /api/register         JSON {username, email, password, code?} → {msg}
//   POST /api/send-code        JSON {email} → {msg}
//   POST /api/verify-code      表单 username, code → {msg}
//   POST /api/resend-code      表单 username, email → {msg}
//   POST /api/change-password  表单 old_password, new_password + Bearer → {msg}
//   GET  /api/login-history    Bearer → {items:[…]}
//   POST /api/logout           Bearer → {msg}（把 jti 加入黑名单）
//
// 两条必须照做的约定：
//   ① **失败体是 `{detail}`**（站点注释里写明"桌面端依赖 detail"），不是 `{error}`。
//      好消息要原样带给用户（"用户名或密码错误""登录尝试次数过多，请 X 分 Y 秒后再试"）。
//   ② 请求一律由**宿主**发出：页面在虚拟主机下直连站点会撞 CORS，而且 token 不该进渲染进程。
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

internal sealed class AccountCall
{
    public bool Ok { get; set; }
    public int Status { get; set; }
    public string Body { get; set; } = "";
    /// <summary>unauthorized | ratelimit | http | network | timeout | aborted | parse</summary>
    public string ErrorKind { get; set; } = "";
    public string Error { get; set; } = "";
}

internal static class AccountApi
{
    private static readonly HttpClient Http = CreateClient();

    private static HttpClient CreateClient()
    {
        var handler = new SocketsHttpHandler
        {
            ConnectTimeout = TimeSpan.FromSeconds(12),
            PooledConnectionLifetime = TimeSpan.FromMinutes(5),
            AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate,
        };
        var c = new HttpClient(handler) { Timeout = Timeout.InfiniteTimeSpan };
        // 站点会把 UA 记进 login_history，写清楚是谁在登录，便于用户自查
        c.DefaultRequestHeaders.TryAddWithoutValidation("User-Agent", "MF-Mathematics/2.0 (Windows; desktop)");
        return c;
    }

    /* ── 三个动词 ───────────────────────────────────────────────────────── */

    public static Task<AccountCall> PostForm(string baseUrl, string path, Dictionary<string, string> fields,
                                             string? token, int timeoutSec, CancellationToken ct)
    {
        var body = new FormUrlEncodedContent(fields);
        return Send(baseUrl, path, HttpMethod.Post, body, token, timeoutSec, ct);
    }

    public static Task<AccountCall> PostJson(string baseUrl, string path, string json,
                                             string? token, int timeoutSec, CancellationToken ct)
    {
        var body = new StringContent(json, Encoding.UTF8, "application/json");
        return Send(baseUrl, path, HttpMethod.Post, body, token, timeoutSec, ct);
    }

    public static Task<AccountCall> Get(string baseUrl, string path, string? token, int timeoutSec, CancellationToken ct)
        => Send(baseUrl, path, HttpMethod.Get, null, token, timeoutSec, ct);

    private static async Task<AccountCall> Send(string baseUrl, string path, HttpMethod method,
        HttpContent? body, string? token, int timeoutSec, CancellationToken ct)
    {
        string url = AccountConfig.NormalizeBaseUrl(baseUrl) + path;
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(timeoutSec));
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(timeout.Token, ct);
        try
        {
            using var req = new HttpRequestMessage(method, url);
            if (body != null) req.Content = body;
            if (!string.IsNullOrEmpty(token))
                req.Headers.TryAddWithoutValidation("Authorization", "Bearer " + token);

            using var resp = await Http.SendAsync(req, HttpCompletionOption.ResponseContentRead, linked.Token)
                                       .ConfigureAwait(false);
            string text = await resp.Content.ReadAsStringAsync(linked.Token).ConfigureAwait(false);
            int status = (int)resp.StatusCode;

            if (resp.IsSuccessStatusCode) return new AccountCall { Ok = true, Status = status, Body = text };

            string kind = status switch
            {
                401 or 403 => "unauthorized",
                429 => "ratelimit",
                _ => "http",
            };
            return new AccountCall { Ok = false, Status = status, Body = text, ErrorKind = kind, Error = Detail(text, status) };
        }
        catch (OperationCanceledException)
        {
            bool isTimeout = timeout.IsCancellationRequested && !ct.IsCancellationRequested;
            return new AccountCall
            {
                Ok = false,
                ErrorKind = isTimeout ? "timeout" : "aborted",
                Error = isTimeout ? $"超过 {timeoutSec} 秒没有响应" : "已取消",
            };
        }
        catch (HttpRequestException e)
        {
            return new AccountCall { Ok = false, ErrorKind = "network", Error = FriendlyNetwork(e) };
        }
        catch (IOException e)
        {
            return new AccountCall { Ok = false, ErrorKind = "network", Error = e.Message };
        }
    }

    private static string FriendlyNetwork(HttpRequestException e)
    {
        string msg = e.Message;
        if (e.InnerException is System.Net.Sockets.SocketException se)
        {
            msg = se.SocketErrorCode switch
            {
                System.Net.Sockets.SocketError.HostNotFound => "找不到服务器地址（检查网络或站点地址）",
                System.Net.Sockets.SocketError.ConnectionRefused => "服务器拒绝连接（地址/端口不对，或服务没起）",
                System.Net.Sockets.SocketError.TimedOut => "连接超时",
                _ => se.Message,
            };
        }
        return msg;
    }

    /* ── 响应解析 ───────────────────────────────────────────────────────── */

    /// <summary>失败信息：优先 `{detail}`（站点约定），其次 `{msg}`，最后退回截断的原文</summary>
    public static string Detail(string body, int status)
    {
        string d = JsonStr(body, "detail");
        if (d.Length > 0) return d;
        string m = JsonStr(body, "msg");
        if (m.Length > 0) return m;
        string trimmed = (body ?? "").Trim();
        if (trimmed.Length == 0) return status == 0 ? "请求失败" : $"HTTP {status}";
        return trimmed.Length <= 200 ? trimmed : trimmed.Substring(0, 200) + "…";
    }

    public static string JsonStr(string body, string name)
    {
        try
        {
            using var doc = JsonDocument.Parse(body ?? "");
            if (doc.RootElement.ValueKind == JsonValueKind.Object
                && doc.RootElement.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String)
                return v.GetString() ?? "";
        }
        catch { /* 不是 JSON 就当没有 */ }
        return "";
    }

    /// <summary>
    /// 解 JWT payload 里的 exp（**不校验签名**）。只用它来决定"什么时候该静默续期"；
    /// 真正的校验在服务器上，客户端猜错了也只会多一次 401，不会因此获得任何权限。
    /// </summary>
    public static long? JwtExp(string token)
    {
        try
        {
            string[] parts = (token ?? "").Split('.');
            if (parts.Length < 2) return null;
            string payload = parts[1].Replace('-', '+').Replace('_', '/');
            while (payload.Length % 4 != 0) payload += "=";
            string json = Encoding.UTF8.GetString(Convert.FromBase64String(payload));
            using var doc = JsonDocument.Parse(json);
            if (doc.RootElement.TryGetProperty("exp", out var exp) && exp.TryGetInt64(out long seconds))
                return seconds;
        }
        catch { /* 形状不对就当不知道 */ }
        return null;
    }

    private static string Str(JsonElement obj, string name)
        => obj.TryGetProperty(name, out var v)
           && (v.ValueKind == JsonValueKind.String) ? (v.GetString() ?? "") : "";
    private static int IntOf(JsonElement obj, string name)
        => obj.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.Number && v.TryGetInt32(out int i) ? i : 0;
    private static bool BoolOf(JsonElement obj, string name)
        => obj.TryGetProperty(name, out var v) && (v.ValueKind == JsonValueKind.True || v.ValueKind == JsonValueKind.False) && v.GetBoolean();

    /// <summary>把 /api/me 的公开用户填进配置缓存</summary>
    public static bool ApplyProfile(string body, AccountConfig cfg)
    {
        try
        {
            using var doc = JsonDocument.Parse(body ?? "");
            var u = doc.RootElement;
            if (u.ValueKind != JsonValueKind.Object) return false;
            cfg.Username = Str(u, "username");
            cfg.Email = Str(u, "email");
            cfg.Balance = IntOf(u, "balance");
            cfg.HasAiService = BoolOf(u, "has_ai_service");
            // role: 站点给的是 0/1/2（2 = 超级管理员）；这里也接受 true/false
            if (u.TryGetProperty("role", out var role) && role.ValueKind == JsonValueKind.True) cfg.Role = 1;
            else cfg.Role = IntOf(u, "role");
            cfg.IsActive = BoolOf(u, "is_active");
            cfg.ProfileVerified = true;
            cfg.ProfileCheckedAt = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            return cfg.Username.Length > 0;
        }
        catch { return false; }
    }

    /// <summary>登录历史 → 直接透传给页面（只取我们认识的字段，别把整包 JSON 塞给界面）</summary>
    public static string NormalizeHistory(string body, int max = 20)
    {
        var sb = new StringBuilder("[");
        try
        {
            using var doc = JsonDocument.Parse(body ?? "");
            JsonElement arr;
            if (doc.RootElement.ValueKind == JsonValueKind.Array) arr = doc.RootElement;
            else if (!doc.RootElement.TryGetProperty("items", out arr)) return "[]";

            int n = 0;
            foreach (var it in arr.EnumerateArray())
            {
                if (n >= max) break;
                if (n > 0) sb.Append(',');
                sb.Append("{\"at\":").Append(PushHub.Str(Str(it, "login_at") is { Length: > 0 } at ? at : Str(it, "at")))
                  .Append(",\"ip\":").Append(PushHub.Str(Str(it, "ip")))
                  .Append(",\"ua\":").Append(PushHub.Str(Clip(Str(it, "user_agent"), 120)))
                  .Append('}');
                n++;
            }
        }
        catch { return "[]"; }
        return sb.Append(']').ToString();
    }

    private static string Clip(string s, int max)
        => string.IsNullOrEmpty(s) || s.Length <= max ? (s ?? "") : s.Substring(0, max) + "…";
}
