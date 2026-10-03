// SearchConfig.cs — 联网搜索的配置与落盘
//
// 与 AI 配置同一条规矩：**凭据不进渲染进程**。
// Wolfram 的 App ID 存在这里（DPAPI 密文），页面只见 hasWolframKey。
// 其余字段（引擎、自定义端点、超时、条数、缓存 TTL）页面本来就知道，但为了"一处真相"
// 还是由宿主读写同一个文件，页面通过 SearchBridge.Info/Configure 访问。
//
// 端点的**测试/镜像覆盖**走环境变量 MF_SEARCH_ENDPOINTS，**不**通过 Configure 暴露：
// 中继与搜索都遵守同一条安全边界 —— 如果页面能改 Wolfram 的端点，那它就能把 App ID
// 发到任意地址（和 AI 中继那条闸门面对的是同一个问题）。环境变量只有启动宿主的人能设。
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace MFMath.Host;

internal sealed class SearchConfig
{
    /// <summary>duckduckgo | wolfram | custom</summary>
    public string Engine { get; set; } = "duckduckgo";

    /// <summary>自定义端点（SearXNG 兼容的 JSON 接口根地址）</summary>
    public string CustomUrl { get; set; } = "";

    public int TimeoutSec { get; set; } = 15;

    /// <summary>每个来源最多取多少条（1–20）</summary>
    public int ResultCount { get; set; } = 8;

    public bool CacheEnabled { get; set; } = true;

    /// <summary>缓存有效期（小时）。0 = 不过期</summary>
    public int CacheTtlHours { get; set; } = 24;

    /// <summary>DPAPI 密文（base64）。**绝不出现在任何返回给页面的 JSON 里**。</summary>
    public string WolframKeyProtected { get; set; } = "";

    [JsonIgnore] public bool LoadFailed { get; set; }

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.Never,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        PropertyNameCaseInsensitive = true,
    };

    public static string Dir =>
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "MFMath", "settings");

    public static string FilePath => Path.Combine(Dir, "search.json");

    public static SearchConfig Load()
    {
        try
        {
            if (!File.Exists(FilePath)) return new SearchConfig();
            string text = File.ReadAllText(FilePath, Encoding.UTF8);
            return Normalize(JsonSerializer.Deserialize<SearchConfig>(text, JsonOpts) ?? new SearchConfig());
        }
        catch
        {
            var cfg = new SearchConfig();
            cfg.LoadFailed = true;      // 坏文件按默认跑，并如实报给界面
            return cfg;
        }
    }

    public static SearchConfig Normalize(SearchConfig c)
    {
        if (c.Engine != "duckduckgo" && c.Engine != "wolfram" && c.Engine != "custom") c.Engine = "duckduckgo";
        c.CustomUrl = (c.CustomUrl ?? "").Trim().TrimEnd('/');
        if (c.TimeoutSec < 3) c.TimeoutSec = 3;
        if (c.TimeoutSec > 120) c.TimeoutSec = 120;
        if (c.ResultCount < 1) c.ResultCount = 8;
        if (c.ResultCount > 20) c.ResultCount = 20;
        if (c.CacheTtlHours < 0) c.CacheTtlHours = 0;
        if (c.CacheTtlHours > 24 * 30) c.CacheTtlHours = 24 * 30;
        return c;
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
                try { File.Copy(FilePath, FilePath + ".bak", true); } catch { /* 备份失败不阻断 */ }
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

    /* ── 端点（含环境变量覆盖，供测试与自建镜像用）──────────────────────── */

    private static Dictionary<string, string>? _overrides;

    private static Dictionary<string, string> Overrides()
    {
        if (_overrides != null) return _overrides;
        var map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        try
        {
            string raw = Environment.GetEnvironmentVariable("MF_SEARCH_ENDPOINTS") ?? "";
            if (!string.IsNullOrWhiteSpace(raw))
            {
                using var doc = JsonDocument.Parse(raw);
                foreach (var p in doc.RootElement.EnumerateObject())
                    if (p.Value.ValueKind == JsonValueKind.String)
                        map[p.Name] = p.Value.GetString() ?? "";
            }
        }
        catch { /* 配错了就当没配，用内置端点 */ }
        return _overrides = map;
    }

    private static string Endpoint(string key, string fallback)
        => Overrides().TryGetValue(key, out var v) && !string.IsNullOrWhiteSpace(v) ? v.TrimEnd('/') : fallback;

    public static string DdgHtmlEndpoint => Endpoint("ddgHtml", "https://html.duckduckgo.com/html");
    public static string DdgIaEndpoint => Endpoint("ddgIa", "https://api.duckduckgo.com");
    public static string WolframEndpoint => Endpoint("wolfram", "https://api.wolframalpha.com/v1/result");
}
