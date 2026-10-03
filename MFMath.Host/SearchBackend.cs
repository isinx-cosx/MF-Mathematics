// SearchBackend.cs — 三个搜索后端与它们的解析器（宿主侧，C#）
//
// 后端：
//   · duckduckgo —— 免密钥。**两个请求**：HTML 结果页（真的结果列表）+ Instant Answer
//     JSON（概念类查询的摘要，"什么是黎曼猜想"这种最有用）。IA 失败不影响结果页。
//   · wolfram    —— 短答案 API（`/v1/result` 返回纯文本），需要用户自备 App ID。
//   · custom     —— SearXNG 兼容的 JSON 接口（自建/自选实例）。
//
// 三条与安全/健壮性有关的规矩：
//   ① **HTML 是不可信输入**：只从中抽文本（去标签、解实体、折叠空白、截断），
//      绝不把标记原样交给界面 —— 界面那边也只用插值渲染。
//   ② **结果 URL 只接受 http/https**：搜到的 `javascript:` / `data:` 一律丢弃。
//   ③ 失败分类要能指导下一步：`config`（没配/没 key）、`network`（连不上）、
//      `http`（端点拒绝，例如 DDG 的反爬 202/403）、`parse`（端点回了不是我们要的形状）、
//      `timeout`、`aborted`。UI 按类别给不同的建议，而不是笼统一句"搜索失败"。
using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace MFMath.Host;

internal sealed class SearchResult
{
    public string Title { get; set; } = "";
    public string Url { get; set; } = "";
    public string Snippet { get; set; } = "";
    /// <summary>这条结果来自哪个后端（结果显示上会标注）</summary>
    public string Source { get; set; } = "";
}

internal sealed class SearchOutcome
{
    public bool Ok { get; set; }
    public string Engine { get; set; } = "";
    public string Abstract { get; set; } = "";
    public List<SearchResult> Results { get; set; } = new();
    public string ErrorKind { get; set; } = "";
    public string Error { get; set; } = "";
    public int Status { get; set; }
}

internal static class SearchBackend
{
    /// <summary>
    /// 搜索用的 HttpClient 是**独立一份**：它需要浏览器样式的 UA（DDG 的 HTML 页会挑 UA）
    /// 与 gzip 解压，而 AI 那条约定的头（`Accept: text/event-stream`）在这里是反效果。
    /// </summary>
    private static readonly HttpClient Http = CreateClient();
    private const string UserAgent =
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";

    private static HttpClient CreateClient()
    {
        var handler = new SocketsHttpHandler
        {
            ConnectTimeout = TimeSpan.FromSeconds(12),
            PooledConnectionLifetime = TimeSpan.FromMinutes(5),
            AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate,
        };
        var c = new HttpClient(handler) { Timeout = Timeout.InfiniteTimeSpan };
        c.DefaultRequestHeaders.TryAddWithoutValidation("User-Agent", UserAgent);
        c.DefaultRequestHeaders.TryAddWithoutValidation("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8");
        return c;
    }

    /* ── 入口 ───────────────────────────────────────────────────────────── */

    public static async Task<SearchOutcome> RunAsync(
        SearchConfig cfg, string wolframKey, string query, CancellationToken ct)
    {
        string q = (query ?? "").Trim();
        if (q.Length == 0) return Err("config", "查询为空");
        if (q.Length > 500) q = q.Substring(0, 500);

        try
        {
            return cfg.Engine switch
            {
                "wolfram" => await WolframAsync(cfg, wolframKey, q, ct).ConfigureAwait(false),
                "custom" => await SearxngAsync(cfg, q, ct).ConfigureAwait(false),
                _ => await DuckDuckGoAsync(cfg, q, ct).ConfigureAwait(false),
            };
        }
        // ⚠ 取消/超时**必须原样穿出去**：只有让它冒到 SearchBridge，那边才能区分
        // "你按了停止"（aborted）与"超过设定的时间"（timeout）—— 两者在界面上给的建议不同。
        // 两个坑都在这里堵住（实测各踩一次）：
        //   ① 早先这里 `catch (OperationCanceledException)` 直接返回 Err("aborted")，
        //      于是"慢速 + 短超时"被报成"已取消"；
        //   ② 去掉那个 catch 之后，HttpClient 抛的是 **TaskCanceledException**（OCE 的子类），
        //      它掉进了下面的泛型 catch，被归成 "parse"（"形状不对"）—— 更离谱。
        // 所以显式 rethrow，并且这一条必须排在泛型 catch 之前。
        catch (OperationCanceledException) { throw; }
        catch (IOException e) { return Err("network", e.Message); }
        catch (HttpRequestException e) { return Err("network", e.Message); }
        catch (Exception e) { return Err("parse", e.GetType().Name + "：" + e.Message); }
    }

    private static SearchOutcome Err(string kind, string message, int status = 0)
        => new() { Ok = false, ErrorKind = kind, Error = message, Status = status };

    private static async Task<string> GetStringAsync(string url, CancellationToken ct)
    {
        using var resp = await Http.GetAsync(url, HttpCompletionOption.ResponseContentRead, ct).ConfigureAwait(false);
        string body = await resp.Content.ReadAsStringAsync(ct).ConfigureAwait(false);
        if (!resp.IsSuccessStatusCode)
        {
            string hint = (int)resp.StatusCode switch
            {
                202 or 403 => "（端点拒绝了这次请求，可能是反爬限制；可换自定义端点）",
                429 => "（请求太频繁，稍后再试）",
                _ => "",
            };
            throw new HttpStatusException((int)resp.StatusCode, $"HTTP {(int)resp.StatusCode} {resp.ReasonPhrase}{hint}", body);
        }
        return body;
    }

    private sealed class HttpStatusException : Exception
    {
        public int Status { get; }
        public string Body { get; }
        public HttpStatusException(int status, string message, string body) : base(message)
        { Status = status; Body = body; }
    }

    /* ── DuckDuckGo ─────────────────────────────────────────────────────── */

    private static async Task<SearchOutcome> DuckDuckGoAsync(SearchConfig cfg, string q, CancellationToken ct)
    {
        var outcome = new SearchOutcome { Ok = true, Engine = "duckduckgo" };

        // ① Instant Answer：概念类摘要。**尽力而为** —— 它挂了不该影响结果列表。
        //    但取消/超时要原样抛出去：那是"整次搜索"的状态，不是"这一路拿不到摘要"。
        try
        {
            string iaUrl = SearchConfig.DdgIaEndpoint + "/?q=" + Uri.EscapeDataString(q)
                         + "&format=json&no_html=1&skip_disambig=1&no_redirect=1";
            outcome.Abstract = ParseDdgAbstract(await GetStringAsync(iaUrl, ct).ConfigureAwait(false));
        }
        catch (OperationCanceledException) { throw; }
        catch { /* 其它失败忽略：结果页才是主体 */ }

        // ② HTML 结果页
        string url = SearchConfig.DdgHtmlEndpoint + "/?q=" + Uri.EscapeDataString(q) + "&kl=wt-wt";
        string html;
        try
        {
            html = await GetStringAsync(url, ct).ConfigureAwait(false);
        }
        catch (HttpStatusException e)
        {
            // 结果页被拒时，如果 IA 有摘要就还算成功（至少给了点东西）
            if (!string.IsNullOrEmpty(outcome.Abstract)) return outcome;
            return Err("http", e.Message, e.Status);
        }

        outcome.Results = ParseDdgHtml(html, cfg.ResultCount);
        if (outcome.Results.Count == 0 && string.IsNullOrEmpty(outcome.Abstract))
        {
            // 形状不像结果页（改版/被拦截）与"确实没有结果"要分开说
            if (html.Length < 2000 && html.IndexOf("result__a", StringComparison.Ordinal) < 0)
                return Err("parse", "DuckDuckGo 返回的页面里没有结果块（可能改版或被拦截），可改用自定义端点");
        }
        return outcome;
    }

    /// <summary>从 DDG 的 HTML 结果页抽结果。**只抽文本**，URL 只接受 http/https。</summary>
    internal static List<SearchResult> ParseDdgHtml(string html, int max)
    {
        var list = new List<SearchResult>();
        if (string.IsNullOrEmpty(html)) return list;

        var titles = Regex.Matches(html,
            "<a(?<tag>[^>]*result__a[^>]*)>(?<text>.*?)</a>",
            RegexOptions.Singleline | RegexOptions.IgnoreCase);
        var snippets = Regex.Matches(html,
            "<(a|div)(?<tag>[^>]*result__snippet[^>]*)>(?<text>.*?)</\\1>",
            RegexOptions.Singleline | RegexOptions.IgnoreCase);

        for (int i = 0; i < titles.Count && list.Count < max; i++)
        {
            var m = titles[i];
            string href = "";
            var hm = Regex.Match(m.Groups["tag"].Value, "href=\"(?<h>[^\"]+)\"", RegexOptions.IgnoreCase);
            if (hm.Success) href = WebUtility.HtmlDecode(hm.Groups["h"].Value);
            href = RealUrl(href);
            if (!IsHttpUrl(href)) continue;   // javascript:/data: 一律丢弃

            string title = StripTags(m.Groups["text"].Value);
            if (title.Length == 0) continue;

            string snippet = i < snippets.Count ? StripTags(snippets[i].Groups["text"].Value) : "";
            list.Add(new SearchResult
            {
                Title = Clip(title, 200),
                Url = href,
                Snippet = Clip(snippet, 400),
                Source = "DuckDuckGo",
            });
        }
        return list;
    }

    /// <summary>DDG 的结果链接会包一层跳转（`//duckduckgo.com/l/?uddg=…`），把真实地址解出来</summary>
    internal static string RealUrl(string href)
    {
        string h = (href ?? "").Trim();
        if (h.StartsWith("//", StringComparison.Ordinal)) h = "https:" + h;
        var m = Regex.Match(h, "[?&]uddg=(?<u>[^&]+)", RegexOptions.IgnoreCase);
        if (m.Success) { try { return Uri.UnescapeDataString(m.Groups["u"].Value); } catch { return h; } }
        return h;
    }

    internal static bool IsHttpUrl(string url)
        => !string.IsNullOrWhiteSpace(url)
           && (url.StartsWith("http://", StringComparison.OrdinalIgnoreCase)
               || url.StartsWith("https://", StringComparison.OrdinalIgnoreCase));

    internal static string ParseDdgAbstract(string json)
    {
        try
        {
            using var doc = JsonDocument.Parse(json);
            var root = doc.RootElement;
            foreach (var name in new[] { "AbstractText", "Answer", "Definition" })
            {
                if (root.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String)
                {
                    string s = StripTags(v.GetString() ?? "");
                    if (s.Length > 0) return Clip(s, 600);
                }
            }
        }
        catch { /* 摘要拿不到就算了 */ }
        return "";
    }

    /* ── Wolfram Alpha（自备 App ID）──────────────────────────────────── */

    private static async Task<SearchOutcome> WolframAsync(SearchConfig cfg, string key, string q, CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(key))
            return Err("config", "Wolfram 需要 App ID：去「设置 → 搜索」填一个，或改用 DuckDuckGo / 自定义端点");

        string url = SearchConfig.WolframEndpoint
                   + "?appid=" + Uri.EscapeDataString(key)
                   + "&i=" + Uri.EscapeDataString(q);
        string body;
        try
        {
            body = await GetStringAsync(url, ct).ConfigureAwait(false);
        }
        catch (HttpStatusException e)
        {
            string msg = e.Status switch
            {
                401 or 403 => "App ID 无效或被拒绝（HTTP " + e.Status + "）",
                501 => "Wolfram 没有理解这个查询（它返回 501）",
                _ => e.Message,
            };
            return Err(e.Status is 401 or 403 or 501 ? "config" : "http", msg, e.Status);
        }

        var outcome = new SearchOutcome { Ok = true, Engine = "wolfram" };
        string answer = Clip(StripTags(body).Trim(), 1000);
        if (answer.Length > 0)
        {
            outcome.Abstract = answer;
            outcome.Results.Add(new SearchResult
            {
                Title = "Wolfram Alpha 简答",
                Url = "https://www.wolframalpha.com/input?i=" + Uri.EscapeDataString(q),
                Snippet = answer,
                Source = "Wolfram Alpha",
            });
        }
        return outcome;
    }

    /* ── 自定义端点（SearXNG 兼容 JSON）────────────────────────────────── */

    private static async Task<SearchOutcome> SearxngAsync(SearchConfig cfg, string q, CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(cfg.CustomUrl))
            return Err("config", "自定义端点还没填（需要一个 SearXNG 之类的 JSON 接口）");

        string url = cfg.CustomUrl + "/search?q=" + Uri.EscapeDataString(q) + "&format=json";
        string body;
        try
        {
            body = await GetStringAsync(url, ct).ConfigureAwait(false);
        }
        catch (HttpStatusException e)
        {
            return Err("http", e.Message, e.Status);
        }

        var outcome = new SearchOutcome { Ok = true, Engine = "custom" };
        try
        {
            outcome.Results = ParseSearxng(body, cfg.ResultCount);
        }
        catch
        {
            return Err("parse", "自定义端点没有返回 SearXNG 形状的 JSON（很多实例默认关闭 format=json）");
        }
        return outcome;
    }

    internal static List<SearchResult> ParseSearxng(string json, int max)
    {
        var list = new List<SearchResult>();
        using var doc = JsonDocument.Parse(json);          // 不是 JSON 就抛，由调用方归类为 parse
        if (!doc.RootElement.TryGetProperty("results", out var arr) || arr.ValueKind != JsonValueKind.Array)
            throw new InvalidOperationException("没有 results 数组");

        foreach (var item in arr.EnumerateArray())
        {
            if (list.Count >= max) break;
            string title = GetStr(item, "title");
            string url = GetStr(item, "url");
            string content = GetStr(item, "content");
            if (!IsHttpUrl(url)) continue;
            list.Add(new SearchResult
            {
                Title = Clip(StripTags(title), 200),
                Url = url,
                Snippet = Clip(StripTags(content), 400),
                Source = GetStr(item, "engine") is { Length: > 0 } eng ? eng : "自定义",
            });
        }
        return list;
    }

    private static string GetStr(JsonElement obj, string name)
        => obj.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? (v.GetString() ?? "") : "";

    /* ── 文本清洗（HTML 是不可信输入）──────────────────────────────────── */

    /// <summary>去标签、解实体、折叠空白。**不解析任何标记**，只留文本。</summary>
    internal static string StripTags(string html)
    {
        if (string.IsNullOrEmpty(html)) return "";
        string s = Regex.Replace(html, "<script[^>]*>.*?</script>", " ", RegexOptions.Singleline | RegexOptions.IgnoreCase);
        s = Regex.Replace(s, "<style[^>]*>.*?</style>", " ", RegexOptions.Singleline | RegexOptions.IgnoreCase);
        s = Regex.Replace(s, "<[^>]+>", " ");
        s = WebUtility.HtmlDecode(s);
        s = Regex.Replace(s, "\\s+", " ");
        return s.Trim();
    }

    internal static string Clip(string s, int max)
        => string.IsNullOrEmpty(s) || s.Length <= max ? (s ?? "") : s.Substring(0, max) + "…";
}
