// AccountConfig.cs — 账号配置与本地会话落盘
//
// 与 AI / 搜索同一条规矩：**凭据不进渲染进程**。
// token 是 DPAPI 密文存在这里，页面只见 loggedIn / username 这类脱敏字段。
//
// 另一条同样重要的规矩：**离线不阻塞**。这个文件里缓存了"上次登录时的资料"，
// 断网时界面照样能显示"上次是 xxx 登录"，但会标成 unverified —— 不假装是刚校验过的。
using System;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace MFMath.Host;

internal sealed class AccountConfig
{
    /// <summary>站点地址。默认生产站点；自建部署可以改（测试也靠它指到本地假服务器）</summary>
    public string BaseUrl { get; set; } = "https://mf-vis-science.cn";

    public int TimeoutSec { get; set; } = 20;

    /// <summary>桌面默认「记住我」（换 30 天长 token）。可在设置里关掉</summary>
    public bool Remember { get; set; } = true;

    /// <summary>临期前静默续期（见 AccountBridge.EnsureFreshAsync）</summary>
    public bool AutoRefresh { get; set; } = true;

    /// <summary>DPAPI 密文（base64）。**绝不出现在任何返回给页面的 JSON 里**</summary>
    public string TokenProtected { get; set; } = "";

    // ↓ 资料缓存：断网时界面靠它显示上次的状态（会标 unverified）
    public string Username { get; set; } = "";
    public string Email { get; set; } = "";
    public int Balance { get; set; }
    public bool HasAiService { get; set; }
    public int Role { get; set; }
    public bool IsActive { get; set; }

    /// <summary>会话到期时刻（unix 毫秒，据登录/续期响应的 expires_in 推算）</summary>
    public long SessionExpiresAt { get; set; }

    /// <summary>上次资料是否**真的**从服务器取到过（断网时为 false）</summary>
    public bool ProfileVerified { get; set; }
    public long ProfileCheckedAt { get; set; }

    [JsonIgnore] public bool LoadFailed { get; set; }

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        PropertyNameCaseInsensitive = true,
    };

    public static string Dir => SearchConfig.Dir;                       // %LOCALAPPDATA%\MFMath\settings
    public static string FilePath => Path.Combine(Dir, "account.json");

    public static AccountConfig Load()
    {
        try
        {
            if (!File.Exists(FilePath)) return new AccountConfig();
            string text = File.ReadAllText(FilePath, Encoding.UTF8);
            return Normalize(JsonSerializer.Deserialize<AccountConfig>(text, JsonOpts) ?? new AccountConfig());
        }
        catch
        {
            var cfg = new AccountConfig();
            cfg.LoadFailed = true;
            return cfg;
        }
    }

    public static AccountConfig Normalize(AccountConfig c)
    {
        c.BaseUrl = NormalizeBaseUrl(c.BaseUrl);
        if (c.TimeoutSec < 5) c.TimeoutSec = 20;
        if (c.TimeoutSec > 120) c.TimeoutSec = 120;
        return c;
    }

    /// <summary>
    /// 站点地址只接受 http/https，且不能带查询串/片段/用户信息。
    /// 这不是洁癖：这个值决定 token 被发到哪儿，能塞 `https://evil@host` 之类就麻烦了。
    /// </summary>
    public static string NormalizeBaseUrl(string url)
    {
        string s = (url ?? "").Trim();
        if (s.Length == 0) return "https://mf-vis-science.cn";
        if (!s.StartsWith("http://", StringComparison.OrdinalIgnoreCase)
            && !s.StartsWith("https://", StringComparison.OrdinalIgnoreCase))
            return "https://mf-vis-science.cn";
        s = s.TrimEnd('/');
        if (s.Contains('?') || s.Contains('#') || s.Contains('@')) return "https://mf-vis-science.cn";
        return s;
    }

    public bool Save(out string error)
    {
        error = "";
        try
        {
            Directory.CreateDirectory(Dir);
            string json = JsonSerializer.Serialize(this, JsonOpts);
            string tmp = FilePath + ".tmp";
            File.WriteAllText(tmp, json, new UTF8Encoding(false));
            if (File.Exists(FilePath))
            {
                try { File.Copy(FilePath, FilePath + ".bak", true); } catch { }
                File.Replace(tmp, FilePath, null, true);
            }
            else File.Move(tmp, FilePath);
            return true;
        }
        catch (Exception e)
        {
            error = e.Message;
            return false;
        }
    }
}
