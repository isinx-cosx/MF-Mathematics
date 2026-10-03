// AccountBridge.cs — 用户系统桥（JS 侧：hostObjects.sync.account）
//
// 这一层是"软件与服务器之间的那条线"，所以把它的纪律写清楚：
//
// ① **离线优先，绝不阻塞**。所有网络调用都是异步 + 超时，界面永远先能画出来；
//    `Info()` 只读内存/本地缓存，从不等网络。**未登录、断网都不影响任何计算功能** ——
//    计算全部在本地 C++ 引擎里，这一层只负责身份与额度显示。
// ② **token 只在宿主**。DPAPI 密文落盘，页面只见 loggedIn / username 这类脱敏字段。
// ③ **不合并失败**。站点的 `{detail}` 原样带给用户（"用户名或密码错误"），并区分
//    unauthorized / ratelimit / network / timeout / aborted，界面据此给不同建议。
// ④ **静默续期**（EnsureFresh）：临期前用 /api/token/refresh 换新 token，免得用户
//    每 30 分钟被踢一次；续期失败不弹错误，只把状态标成需要重新登录。
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace MFMath.Host;

[ComVisible(true)]
public class AccountBridge
{
    private static readonly object Gate = new();
    private static AccountConfig? _config;
    private static string _memoryToken = "";        // DPAPI 不可用时只留内存（不写明文）
    private static volatile string _lastError = "";
    private static volatile string _lastErrorKind = "";
    private static volatile bool _offline;
    private static volatile string _busyOp = "";
    private static readonly CancellationTokenSource Life = new();

    private static AccountConfig Config
    {
        get { lock (Gate) return _config ??= AccountConfig.Load(); }
    }

    private static string J(string? s) => PushHub.Str(s);
    private static string B(bool v) => v ? "true" : "false";
    private static string Fail(string message, string kind = "config")
    {
        _lastError = message; _lastErrorKind = kind;
        return "{\"ok\":false,\"kind\":" + J(kind) + ",\"error\":" + J(message) + "}";
    }
    private static string Ok(string extra = "") => "{\"ok\":true" + (extra.Length > 0 ? "," + extra : "") + "}";

    /* ── 状态（脱敏）────────────────────────────────────────────────────── */

    public string Info()
    {
        var cfg = Config;
        bool hasToken = ResolveToken().Length > 0;
        long now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        var sb = new StringBuilder("{");
        sb.Append("\"baseUrl\":").Append(J(cfg.BaseUrl));
        sb.Append(",\"timeoutSec\":").Append(cfg.TimeoutSec);
        sb.Append(",\"remember\":").Append(B(cfg.Remember));
        sb.Append(",\"autoRefresh\":").Append(B(cfg.AutoRefresh));
        sb.Append(",\"loggedIn\":").Append(B(hasToken));
        sb.Append(",\"username\":").Append(J(cfg.Username));
        sb.Append(",\"email\":").Append(J(cfg.Email));
        sb.Append(",\"balance\":").Append(cfg.Balance);
        sb.Append(",\"hasAiService\":").Append(B(cfg.HasAiService));
        sb.Append(",\"role\":").Append(cfg.Role);
        sb.Append(",\"isActive\":").Append(B(cfg.IsActive));
        sb.Append(",\"sessionExpiresAt\":").Append(cfg.SessionExpiresAt);
        sb.Append(",\"sessionExpiresInSec\":").Append(cfg.SessionExpiresAt > 0
            ? Math.Max(0, (cfg.SessionExpiresAt - now) / 1000) : 0);
        // 断网时资料来自缓存 —— 明确标出来，不假装是刚校验过的
        sb.Append(",\"profileVerified\":").Append(B(cfg.ProfileVerified));
        sb.Append(",\"profileCheckedAt\":").Append(cfg.ProfileCheckedAt);
        sb.Append(",\"offline\":").Append(B(_offline));
        sb.Append(",\"dpapiAvailable\":").Append(B(DpapiAvailable()));
        sb.Append(",\"tokenSource\":").Append(J(_memoryToken.Length > 0 ? "memory"
            : cfg.TokenProtected.Length > 0 ? "dpapi" : "none"));
        sb.Append(",\"busy\":").Append(J(_busyOp));
        sb.Append(",\"lastError\":").Append(J(_lastError));
        sb.Append(",\"lastErrorKind\":").Append(J(_lastErrorKind));
        sb.Append(",\"configPath\":").Append(J(AccountConfig.FilePath));
        sb.Append(",\"configLoadFailed\":").Append(B(cfg.LoadFailed));
        sb.Append(",\"apiVersion\":").Append(J("v2 客户端契约：/api/login /api/token/refresh /api/me …"));
        sb.Append('}');
        return sb.ToString();
    }

    private static bool DpapiAvailable()
    {
        try { return Dpapi.SelfTest(); } catch { return false; }
    }

    private static string ResolveToken()
    {
        if (_memoryToken.Length > 0) return _memoryToken;
        var cfg = Config;
        if (cfg.TokenProtected.Length == 0) return "";
        try { return Dpapi.Unprotect(cfg.TokenProtected) ?? ""; } catch { return ""; }
    }

    private static bool StoreToken(string token, out string warning)
    {
        warning = "";
        string? blob = null;
        try { blob = Dpapi.Protect(token); } catch { }
        if (blob == null)
        {
            _memoryToken = token;   // 只留内存：不写明文到磁盘
            warning = "DPAPI 在本机不可用：登录状态只保留在本次运行的内存里（重启后需重新登录）。";
            return false;
        }
        var cfg = Config;
        cfg.TokenProtected = blob;
        _memoryToken = "";
        return true;
    }

    private static void ClearToken()
    {
        _memoryToken = "";
        var cfg = Config;
        cfg.TokenProtected = "";
        cfg.SessionExpiresAt = 0;
        cfg.ProfileVerified = false;
    }

    private static void Persist()
    {
        try { Config.Save(out _); } catch { }
    }

    private static void PushChanged(string why)
    {
        PushHub.Send("account.changed", "{\"reason\":" + J(why) + ",\"info\":" + new AccountBridge().Info() + "}");
    }

    /* ── 配置 ───────────────────────────────────────────────────────────── */

    public string Configure(string json)
    {
        try
        {
            using var doc = System.Text.Json.JsonDocument.Parse(json);
            var root = doc.RootElement;
            var cfg = Config;
            bool changed = false;

            string baseUrl = cfg.BaseUrl; int timeoutSec = cfg.TimeoutSec;
            bool remember = cfg.Remember, autoRefresh = cfg.AutoRefresh;

            if (root.TryGetProperty("baseUrl", out var b) && b.ValueKind == System.Text.Json.JsonValueKind.String)
            { baseUrl = b.GetString() ?? ""; changed = true; }
            if (root.TryGetProperty("timeoutSec", out var t) && t.ValueKind == System.Text.Json.JsonValueKind.Number)
            { timeoutSec = t.GetInt32(); changed = true; }
            if (root.TryGetProperty("remember", out var r)
                && (r.ValueKind == System.Text.Json.JsonValueKind.True || r.ValueKind == System.Text.Json.JsonValueKind.False))
            { remember = r.GetBoolean(); changed = true; }
            if (root.TryGetProperty("autoRefresh", out var a)
                && (a.ValueKind == System.Text.Json.JsonValueKind.True || a.ValueKind == System.Text.Json.JsonValueKind.False))
            { autoRefresh = a.GetBoolean(); changed = true; }

            if (!changed) return Ok("\"changed\":0");

            cfg.BaseUrl = baseUrl; cfg.TimeoutSec = timeoutSec;
            cfg.Remember = remember; cfg.AutoRefresh = autoRefresh;
            AccountConfig.Normalize(cfg);
            if (!cfg.Save(out string err)) return Fail("写入配置失败：" + err);
            lock (Gate) _config = cfg;
            return Ok("\"changed\":1,\"baseUrl\":" + J(cfg.BaseUrl));
        }
        catch (Exception e) { return Fail("配置解析失败：" + e.Message); }
    }

    /// <summary>清掉本地登录状态（不发网络请求）。用户在设置里"退出并清除本机凭据"用这个</summary>
    public string ClearLocal()
    {
        ClearToken();
        var cfg = Config;
        cfg.Username = ""; cfg.Email = ""; cfg.Balance = 0; cfg.HasAiService = false; cfg.Role = 0;
        cfg.IsActive = false; cfg.ProfileCheckedAt = 0;
        Persist();
        PushChanged("cleared");
        return Ok();
    }

    /* ── 登录 / 登出 / 续期 ─────────────────────────────────────────────── */

    /// <summary>登录。入参 <code>{"username":"…","password":"…","remember":true}</code></summary>
    public string Login(string username, string password)
        => LoginEx("{\"username\":" + J(username) + ",\"password\":" + J(password) + "}");

    public string LoginEx(string json)
    {
        string username = "", password = "";
        bool? remember = null;
        try
        {
            using var doc = System.Text.Json.JsonDocument.Parse(json);
            var root = doc.RootElement;
            if (root.TryGetProperty("username", out var u) && u.ValueKind == System.Text.Json.JsonValueKind.String)
                username = (u.GetString() ?? "").Trim();
            if (root.TryGetProperty("password", out var p) && p.ValueKind == System.Text.Json.JsonValueKind.String)
                password = p.GetString() ?? "";
            if (root.TryGetProperty("remember", out var r)
                && (r.ValueKind == System.Text.Json.JsonValueKind.True || r.ValueKind == System.Text.Json.JsonValueKind.False))
                remember = r.GetBoolean();
        }
        catch (Exception e) { return Fail("请求解析失败：" + e.Message); }

        if (username.Length == 0) return Fail("用户名不能为空");
        if (password.Length == 0) return Fail("密码不能为空");

        var cfg = Config;
        bool rem = remember ?? cfg.Remember;
        var fields = new Dictionary<string, string> { ["username"] = username, ["password"] = password };
        if (rem) fields["remember"] = "1";

        _busyOp = "login";
        try
        {
            var call = AccountApi.PostForm(cfg.BaseUrl, "/api/login", fields, null, cfg.TimeoutSec, Life.Token)
                                  .GetAwaiter().GetResult();
            if (!call.Ok)
            {
                NoteFailure(call);
                return Fail(call.Error, call.ErrorKind);
            }
            string token = AccountApi.JsonStr(call.Body, "access_token");
            if (token.Length == 0) return Fail("服务器没有返回 access_token（契约不符）", "parse");

            bool persisted = StoreToken(token, out string warning);
            cfg.SessionExpiresAt = ExpiryFrom(call.Body, token);
            cfg.Remember = rem;              // 记住用户的选择，续期时保持一致

            // 登录成功后立刻取一次资料（这一步失败不回滚登录：token 是有效的）
            var me = AccountApi.Get(cfg.BaseUrl, "/api/me", token, cfg.TimeoutSec, Life.Token).GetAwaiter().GetResult();
            if (me.Ok) AccountApi.ApplyProfile(me.Body, cfg);
            else { cfg.ProfileVerified = false; NoteFailure(me, soft: true); }

            Persist();
            _offline = false;
            _lastError = ""; _lastErrorKind = "";
            if (!persisted) { _lastError = warning; _lastErrorKind = "dpapi"; }
            PushChanged("login");
            return Ok("\"username\":" + J(cfg.Username.Length > 0 ? cfg.Username : username)
                + ",\"remember\":" + B(rem)
                + ",\"sessionExpiresAt\":" + cfg.SessionExpiresAt
                + ",\"warning\":" + J(persisted ? "" : warning));
        }
        catch (Exception e) { return Fail(e.GetType().Name + "：" + e.Message, "unknown"); }
        finally { _busyOp = ""; }
    }

    /// <summary>登出：先通知服务器把 token 拉黑，再清本地。**服务器不通也照样清本地**（否则断网就退不出去）</summary>
    public string Logout()
    {
        var cfg = Config;
        string token = ResolveToken();
        string serverNote = "";
        if (token.Length > 0)
        {
            var call = AccountApi.PostForm(cfg.BaseUrl, "/api/logout", new Dictionary<string, string>(), token, cfg.TimeoutSec, Life.Token)
                                  .GetAwaiter().GetResult();
            if (!call.Ok && call.ErrorKind == "network")
                serverNote = "（服务器暂时联系不上，已在本机退出；下次联网时该 token 仍在有效期内，可到站点改密码强制失效）";
        }
        ClearToken();
        Persist();
        PushChanged("logout");
        return Ok("\"serverNote\":" + J(serverNote));
    }

    /// <summary>用当前 token 取资料（校验是否还有效）</summary>
    public string RefreshProfile()
    {
        var cfg = Config;
        string token = ResolveToken();
        if (token.Length == 0) return Fail("尚未登录", "unauthorized");

        var me = AccountApi.Get(cfg.BaseUrl, "/api/me", token, cfg.TimeoutSec, Life.Token).GetAwaiter().GetResult();
        if (!me.Ok)
        {
            NoteFailure(me);
            if (me.ErrorKind == "unauthorized") { ClearToken(); Persist(); PushChanged("expired"); }
            else { cfg.ProfileVerified = false; Persist(); }
            return Fail(me.Error, me.ErrorKind);
        }
        AccountApi.ApplyProfile(me.Body, cfg);
        Persist();
        _offline = false; _lastError = ""; _lastErrorKind = "";
        PushChanged("profile");
        return Ok("\"username\":" + J(cfg.Username));
    }

    /// <summary>静默续期：临期前换一枚新 token。失败不抛错，只把状态标成需要重新登录</summary>
    public string RefreshToken()
    {
        var cfg = Config;
        string token = ResolveToken();
        if (token.Length == 0) return Fail("尚未登录", "unauthorized");

        var fields = new Dictionary<string, string>();
        if (cfg.Remember) fields["remember"] = "1";
        var call = AccountApi.PostForm(cfg.BaseUrl, "/api/token/refresh", fields, token, cfg.TimeoutSec, Life.Token)
                             .GetAwaiter().GetResult();
        if (!call.Ok)
        {
            NoteFailure(call);
            if (call.ErrorKind == "unauthorized") { ClearToken(); Persist(); PushChanged("expired"); }
            return Fail(call.Error, call.ErrorKind);
        }
        string fresh = AccountApi.JsonStr(call.Body, "access_token");
        if (fresh.Length == 0) return Fail("续期响应里没有 access_token（契约不符）", "parse");
        StoreToken(fresh, out _);
        cfg.SessionExpiresAt = ExpiryFrom(call.Body, fresh);
        Persist();
        PushChanged("refreshed");
        return Ok("\"sessionExpiresAt\":" + cfg.SessionExpiresAt);
    }

    /// <summary>
    /// 临期自动续期（界面在打开时/每次账号操作前调一次即可，调用方不必自己算时间）。
    /// 剩余不足阈值才动手；失败也只是返回 false，不影响任何计算功能。
    /// </summary>
    public bool EnsureFresh(int thresholdSec = 300)
    {
        var cfg = Config;
        if (!cfg.AutoRefresh || ResolveToken().Length == 0) return false;
        long now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        if (cfg.SessionExpiresAt <= 0) return false;
        if (cfg.SessionExpiresAt - now > thresholdSec * 1000L) return true;
        string r = RefreshToken();
        return r.StartsWith("{\"ok\":true", StringComparison.Ordinal);
    }

    private static long ExpiryFrom(string body, string token)
    {
        int sec = 0;
        try
        {
            using var doc = System.Text.Json.JsonDocument.Parse(body);
            if (doc.RootElement.TryGetProperty("expires_in", out var e) && e.ValueKind == System.Text.Json.JsonValueKind.Number)
                sec = e.GetInt32();
        }
        catch { /* 拿不到 expires_in */ }
        if (sec > 0) return DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() + sec * 1000L;
        long? exp = AccountApi.JwtExp(token);          // 退路：解 JWT 的 exp
        return exp.HasValue ? exp.Value * 1000L : 0;
    }

    private static void NoteFailure(AccountCall call, bool soft = false)
    {
        _lastError = call.Error; _lastErrorKind = call.ErrorKind;
        if (call.ErrorKind == "network" || call.ErrorKind == "timeout") _offline = true;
        else if (call.ErrorKind != "aborted") _offline = false;
        if (soft) { _lastError = "已登录，但没取到资料：" + call.Error; }
    }

    /* ── 注册与邮箱验证（未登录时可用）──────────────────────────────────── */

    /// <summary>注册。入参 <code>{"username","email","password","code"?}</code> —— code 可省略，
    /// 省略时站点会创建未激活用户并发邮件验证码（与网站注册完全一致）</summary>
    public string Register(string json)
    {
        var cfg = Config;
        var call = AccountApi.PostJson(cfg.BaseUrl, "/api/register", json, null, cfg.TimeoutSec, Life.Token)
                             .GetAwaiter().GetResult();
        if (!call.Ok) { NoteFailure(call); return Fail(call.Error, call.ErrorKind); }
        _lastError = ""; _lastErrorKind = ""; _offline = false;
        return Ok("\"msg\":" + J(AccountApi.JsonStr(call.Body, "msg")));
    }

    public string SendCode(string email)
    {
        var cfg = Config;
        string json = "{\"email\":" + J((email ?? "").Trim()) + "}";
        var call = AccountApi.PostJson(cfg.BaseUrl, "/api/send-code", json, null, cfg.TimeoutSec, Life.Token)
                             .GetAwaiter().GetResult();
        if (!call.Ok) { NoteFailure(call); return Fail(call.Error, call.ErrorKind); }
        _offline = false;
        return Ok("\"msg\":" + J(AccountApi.JsonStr(call.Body, "msg")));
    }

    public string VerifyCode(string username, string code)
    {
        var cfg = Config;
        var fields = new Dictionary<string, string> { ["username"] = (username ?? "").Trim(), ["code"] = (code ?? "").Trim() };
        var call = AccountApi.PostForm(cfg.BaseUrl, "/api/verify-code", fields, null, cfg.TimeoutSec, Life.Token)
                             .GetAwaiter().GetResult();
        if (!call.Ok) { NoteFailure(call); return Fail(call.Error, call.ErrorKind); }
        _offline = false;
        return Ok("\"msg\":" + J(AccountApi.JsonStr(call.Body, "msg")));
    }

    public string ResendCode(string username, string email)
    {
        var cfg = Config;
        var fields = new Dictionary<string, string> { ["username"] = (username ?? "").Trim(), ["email"] = (email ?? "").Trim() };
        var call = AccountApi.PostForm(cfg.BaseUrl, "/api/resend-code", fields, null, cfg.TimeoutSec, Life.Token)
                             .GetAwaiter().GetResult();
        if (!call.Ok) { NoteFailure(call); return Fail(call.Error, call.ErrorKind); }
        _offline = false;
        return Ok("\"msg\":" + J(AccountApi.JsonStr(call.Body, "msg")));
    }

    /* ── 需要登录的操作 ─────────────────────────────────────────────────── */

    public string ChangePassword(string oldPassword, string newPassword)
    {
        var cfg = Config;
        string token = ResolveToken();
        if (token.Length == 0) return Fail("尚未登录", "unauthorized");

        var fields = new Dictionary<string, string> { ["old_password"] = oldPassword ?? "", ["new_password"] = newPassword ?? "" };
        var call = AccountApi.PostForm(cfg.BaseUrl, "/api/change-password", fields, token, cfg.TimeoutSec, Life.Token)
                             .GetAwaiter().GetResult();
        if (!call.Ok) { NoteFailure(call); return Fail(call.Error, call.ErrorKind); }
        _offline = false;
        // 站点改密码不会废止已发出去的 token（它们在有效期内仍可用）——如实告诉用户
        return Ok("\"msg\":" + J(AccountApi.JsonStr(call.Body, "msg"))
            + ",\"note\":" + J("改密码不会让已登录的会话立刻失效；要立刻踢掉，可在站点上登出或等 token 到期。"));
    }

    public string LoginHistory()
    {
        var cfg = Config;
        string token = ResolveToken();
        if (token.Length == 0) return Fail("尚未登录", "unauthorized");
        var call = AccountApi.Get(cfg.BaseUrl, "/api/login-history", token, cfg.TimeoutSec, Life.Token)
                             .GetAwaiter().GetResult();
        if (!call.Ok) { NoteFailure(call); return Fail(call.Error, call.ErrorKind); }
        _offline = false;
        return Ok("\"items\":" + AccountApi.NormalizeHistory(call.Body));
    }

    /// <summary>站点版本/下载信息（更新链的前置；这里只做只读查询）</summary>
    public string SiteVersion()
    {
        var cfg = Config;
        var call = AccountApi.Get(cfg.BaseUrl, "/api/version", null, cfg.TimeoutSec, Life.Token)
                             .GetAwaiter().GetResult();
        if (!call.Ok) { NoteFailure(call); return Fail(call.Error, call.ErrorKind); }
        _offline = false;
        // 解析与比较都复用 UpdateBridge（一处实现）：这里只把结果包成账号页要的形状
        string parsed = UpdateBridge.ParseVersionBody(call.Body, UpdateBridge.AppVersion());
        if (!parsed.StartsWith("{\"ok\":true", StringComparison.Ordinal)) return parsed;
        using var doc = System.Text.Json.JsonDocument.Parse(parsed);
        var r = doc.RootElement;
        string g(string k) => r.TryGetProperty(k, out var v) && v.ValueKind == System.Text.Json.JsonValueKind.String ? (v.GetString() ?? "") : "";
        return Ok("\"latest\":" + J(g("latest")) + ",\"date\":" + J(g("date"))
            + ",\"downloadUrl\":" + J(g("downloadUrl"))
            + ",\"hasUpdate\":" + (r.TryGetProperty("hasUpdate", out var hu) && hu.ValueKind == System.Text.Json.JsonValueKind.True ? "true" : "false")
            + ",\"relation\":" + J(g("relation")));
    }

    public bool Busy() => _busyOp.Length > 0;

    public void CancelAll()
    {
        try { Life.Cancel(); } catch { }
    }

    /* ── 自检（不联网）──────────────────────────────────────────────────── */

    /// <summary>
    /// 六项自检，**都不联网**：站点地址闸门、表单编码、`{detail}` 解析、JWT exp 解析、
    /// 登录历史归一化、以及"脱敏视图里没有 token"。契约解析与地址闸门是最容易悄悄坏掉的两层。
    /// </summary>
    public string SelfCheck()
    {
        var sb = new StringBuilder("{\"ok\":true,\"checks\":[");
        bool all = true;

        // ① 站点地址闸门
        bool urlOk = AccountConfig.NormalizeBaseUrl("https://mf-vis-science.cn") == "https://mf-vis-science.cn"
                  && AccountConfig.NormalizeBaseUrl("https://mf-vis-science.cn/") == "https://mf-vis-science.cn"
                  && AccountConfig.NormalizeBaseUrl("http://127.0.0.1:8795") == "http://127.0.0.1:8795"
                  && AccountConfig.NormalizeBaseUrl("javascript:alert(1)") == "https://mf-vis-science.cn"
                  && AccountConfig.NormalizeBaseUrl("file:///C:/Windows") == "https://mf-vis-science.cn"
                  && AccountConfig.NormalizeBaseUrl("https://evil@host") == "https://mf-vis-science.cn"
                  && !AccountConfig.NormalizeBaseUrl("https://x.cn/?a=1").Contains('?');
        all &= urlOk;
        sb.Append("{\"name\":\"站点地址闸门\",\"ok\":").Append(B(urlOk))
          .Append(",\"detail\":").Append(J(urlOk
              ? "只接受 http/https、去尾斜杠、拒绝查询串/片段/用户信息（这个值决定 token 发往哪儿）"
              : "地址归一化不符合预期")).Append('}');

        // ② 失败体 {detail} 解析（站点约定：桌面端依赖 detail）
        bool detailOk = AccountApi.Detail("{\"detail\":\"用户名或密码错误\"}", 400) == "用户名或密码错误"
                     && AccountApi.Detail("{\"msg\":\"已成功登出\"}", 200) == "已成功登出"
                     && AccountApi.Detail("", 500) == "HTTP 500";
        all &= detailOk;
        sb.Append(",{\"name\":\"失败体 {detail} 解析\",\"ok\":").Append(B(detailOk))
          .Append(",\"detail\":").Append(J(detailOk
              ? "优先 detail、其次 msg、最后退回 HTTP 状态码（站点的错误形状原样带给用户）"
              : "错误体解析不符合预期")).Append('}');

        // ③ JWT exp 解析（只用于排期；签名由服务器校验）
        string sample = "eyJhbGciOiJIUzI1NiJ9." +
            Convert.ToBase64String(Encoding.UTF8.GetBytes("{\"sub\":\"u\",\"exp\":2000000000}"))
                .TrimEnd('=').Replace('+', '-').Replace('/', '_') + ".sig";
        bool expOk = AccountApi.JwtExp(sample) == 2000000000L && AccountApi.JwtExp("garbage") == null;
        all &= expOk;
        sb.Append(",{\"name\":\"JWT exp 解析\",\"ok\":").Append(B(expOk))
          .Append(",\"detail\":").Append(J(expOk
              ? "能算出到期时间用于静默续期；**不校验签名**（那是服务器的事，猜错只会多一次 401）"
              : "exp 解析不符合预期")).Append('}');

        // ④ 登录历史归一化（只透传认识的字段）
        string hist = AccountApi.NormalizeHistory("{\"items\":[{\"ip\":\"1.2.3.4\",\"user_agent\":\"UA\",\"login_at\":\"2026-01-01T00:00:00Z\"}]}");
        bool histOk = hist.Contains("1.2.3.4") && hist.Contains("2026-01-01") && !hist.Contains("password");
        all &= histOk;
        sb.Append(",{\"name\":\"登录历史归一化\",\"ok\":").Append(B(histOk))
          .Append(",\"detail\":").Append(J(histOk ? "取 ip / user_agent / login_at" : "归一化不符合预期")).Append('}');

        // ⑤ 脱敏视图里没有 token
        var cfg = Config;
        string info = Info();
        string tokenNow = ResolveToken();
        bool redactOk = !info.Contains("access_token") && !info.Contains("tokenProtected")
                     && (tokenNow.Length == 0 || !info.Contains(tokenNow));
        all &= redactOk;
        sb.Append(",{\"name\":\"脱敏视图不含 token\",\"ok\":").Append(B(redactOk))
          .Append(",\"detail\":").Append(J(redactOk
              ? "Info() 只有 loggedIn/tokenSource 这类标志，token 本体不出宿主"
              : "脱敏视图里出现了 token 或字段名")).Append('}');

        // ⑥ 离线不阻塞：Info() 不依赖网络
        var sw = System.Diagnostics.Stopwatch.StartNew();
        Info();
        sw.Stop();
        bool fastOk = sw.ElapsedMilliseconds < 50;
        all &= fastOk;
        sb.Append(",{\"name\":\"Info() 不碰网络（离线也能画界面）\",\"ok\":").Append(B(fastOk))
          .Append(",\"detail\":").Append(J(fastOk
              ? $"读本地状态用了 {sw.ElapsedMilliseconds} ms；断网时界面照常显示上次的资料并标注 unverified"
              : $"Info() 用了 {sw.ElapsedMilliseconds} ms，像是碰了网络")).Append('}');

        sb.Append("],\"ok_all\":").Append(B(all)).Append('}');
        return sb.ToString();
    }
}
