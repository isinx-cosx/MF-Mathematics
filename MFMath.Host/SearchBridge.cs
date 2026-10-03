// SearchBridge.cs — 联网搜索桥（JS 侧：hostObjects.sync.search）
//
// 为什么放在宿主（与 AI 那条同源）：
//   · **凭据**：Wolfram 的 App ID 只在宿主（DPAPI 密文），页面只见 hasWolframKey。
//     如果页面能改后端端点，它就能把 App ID 发到任意地址 —— 和 AI 中继面对的是同一个问题，
//     所以端点的测试/镜像覆盖走环境变量（MF_SEARCH_ENDPOINTS），**不**从页面暴露。
//   · **网络**：页面跑在虚拟主机下，直连外部站点会撞 CORS；而 DDG 的 HTML 页也不允许跨源读。
//   · **缓存与超时**：一处实现，且断网/超时/被反爬要分类清楚（见 SearchBackend 的注释）。
//
// 数据流：
//   页面 search.Start({query, engine?}) → 立即返回 {ok, requestId}
//   → 宿主查缓存（键含引擎）→ 未命中就按引擎抓取 → 解析成纯文本结果
//   → PushHub 推 search.done{results, abstract, fromCache, elapsedMs} 或 search.error{kind,...}
//
// 桥面：
//   Info() Configure(json) SetWolframKey(key) ClearWolframKey()
//   Start(json) Cancel(id) CancelAll() Busy()
//   OpenUrl(url) CacheStats() ClearCache() SelfCheck()
using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace MFMath.Host;

[ComVisible(true)]
public class SearchBridge
{
    private sealed class Job
    {
        public string Id = "";
        public string Query = "";
        public string Engine = "";
        public volatile string State = "running";   // running | done | error
        public readonly CancellationTokenSource Cts = new();
    }

    private static readonly ConcurrentDictionary<string, Job> Jobs = new();
    private static readonly object ConfigLock = new();
    private static SearchConfig? _config;
    private static string _memoryKey = "";          // DPAPI 不可用时的兜底（只留内存，不写明文）
    private static long _seq;
    private static volatile string _lastError = "";

    private static SearchConfig Config
    {
        get { lock (ConfigLock) return _config ??= SearchConfig.Load(); }
    }

    private static string J(string? s) => PushHub.Str(s);
    private static string B(bool v) => v ? "true" : "false";
    private static string Fail(string message) => "{\"ok\":false,\"error\":" + J(message) + "}";

    /* ── 状态 ───────────────────────────────────────────────────────────── */

    /// <summary>脱敏状态：**永远不返回 App ID 本身**，只说有没有、从哪来。</summary>
    public string Info()
    {
        var cfg = Config;
        bool dpapi = false;
        try { dpapi = Dpapi.SelfTest(); } catch { }

        string keySource = !string.IsNullOrEmpty(_memoryKey) ? "memory"
                         : !string.IsNullOrEmpty(cfg.WolframKeyProtected) ? "dpapi"
                         : "none";

        var sb = new StringBuilder("{");
        sb.Append("\"engine\":").Append(J(cfg.Engine));
        sb.Append(",\"customUrl\":").Append(J(cfg.CustomUrl));
        sb.Append(",\"timeoutSec\":").Append(cfg.TimeoutSec);
        sb.Append(",\"resultCount\":").Append(cfg.ResultCount);
        sb.Append(",\"cacheEnabled\":").Append(B(cfg.CacheEnabled));
        sb.Append(",\"cacheTtlHours\":").Append(cfg.CacheTtlHours);
        sb.Append(",\"hasWolframKey\":").Append(B(keySource != "none"));
        sb.Append(",\"wolframKeySource\":").Append(J(keySource));
        sb.Append(",\"dpapiAvailable\":").Append(B(dpapi));
        sb.Append(",\"configLoadFailed\":").Append(B(cfg.LoadFailed));
        sb.Append(",\"configPath\":").Append(J(SearchConfig.FilePath));
        sb.Append(",\"lastError\":").Append(J(_lastError));
        sb.Append(",\"running\":").Append(Running());
        // 面板上要**明说查询会发往哪个站点**（隐私说明不是装饰）
        sb.Append(",\"endpoint\":").Append(J(EndpointOf(cfg)));
        // 生效端点（不是凭据，公开地址）：设置面板与端到端用例都靠它确认"到底发去哪儿"。
        // 覆盖只走环境变量 MF_SEARCH_ENDPOINTS —— 页面能改端点就等于能把 App ID 发到任意地址。
        sb.Append(",\"endpoints\":{")
          .Append("\"ddgHtml\":").Append(J(SearchConfig.DdgHtmlEndpoint))
          .Append(",\"ddgIa\":").Append(J(SearchConfig.DdgIaEndpoint))
          .Append(",\"wolfram\":").Append(J(SearchConfig.WolframEndpoint))
          .Append('}');
        sb.Append(",\"cache\":").Append(SearchCache.Stats());
        sb.Append('}');
        return sb.ToString();
    }

    private static string EndpointOf(SearchConfig cfg) => cfg.Engine switch
    {
        "wolfram" => "api.wolframalpha.com（会带上你的 App ID）",
        "custom" => string.IsNullOrWhiteSpace(cfg.CustomUrl) ? "（自定义端点未填）" : cfg.CustomUrl,
        _ => "html.duckduckgo.com + api.duckduckgo.com（免密钥）",
    };

    private static int Running()
    {
        int n = 0;
        foreach (var kv in Jobs) if (kv.Value.State == "running") n++;
        return n;
    }

    public bool Busy() => Running() > 0;

    /* ── 配置 ───────────────────────────────────────────────────────────── */

    public string Configure(string json)
    {
        try
        {
            using var doc = System.Text.Json.JsonDocument.Parse(json);
            var root = doc.RootElement;
            var cfg = Config;
            bool changed = false;

            string engine = cfg.Engine, customUrl = cfg.CustomUrl;
            int timeoutSec = cfg.TimeoutSec, resultCount = cfg.ResultCount, ttl = cfg.CacheTtlHours;
            bool cacheEnabled = cfg.CacheEnabled;

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
            bool TryBool(string name, ref bool target)
            {
                if (!root.TryGetProperty(name, out var e)) return false;
                if (e.ValueKind != System.Text.Json.JsonValueKind.True && e.ValueKind != System.Text.Json.JsonValueKind.False) return false;
                target = e.GetBoolean(); changed = true; return true;
            }

            TryStr("engine", ref engine);
            TryStr("customUrl", ref customUrl);
            TryInt("timeoutSec", ref timeoutSec);
            TryInt("resultCount", ref resultCount);
            TryBool("cacheEnabled", ref cacheEnabled);
            TryInt("cacheTtlHours", ref ttl);

            if (!changed) return "{\"ok\":true,\"changed\":0}";

            cfg.Engine = engine;
            cfg.CustomUrl = customUrl;
            cfg.TimeoutSec = timeoutSec;
            cfg.ResultCount = resultCount;
            cfg.CacheEnabled = cacheEnabled;
            cfg.CacheTtlHours = ttl;

            SearchConfig.Normalize(cfg);
            if (!cfg.Save(out string err)) return Fail("写入配置失败：" + err);
            lock (ConfigLock) _config = cfg;
            return "{\"ok\":true,\"changed\":1}";
        }
        catch (Exception e) { return Fail("配置解析失败：" + e.Message); }
    }

    /// <summary>设置 Wolfram App ID。**只写不读**（同 AI 密钥那条规矩）。</summary>
    public string SetWolframKey(string key)
    {
        if (string.IsNullOrWhiteSpace(key)) return Fail("App ID 为空");
        string trimmed = key.Trim();

        string? blob = null;
        try { blob = Dpapi.Protect(trimmed); } catch { }
        if (blob == null)
        {
            _memoryKey = trimmed;
            return "{\"ok\":true,\"persisted\":false,\"warning\":" +
                   J("DPAPI 在本机不可用：App ID 只保留在本次运行的内存里（重启后需重填），不会写明文到磁盘。") + "}";
        }

        var cfg = Config;
        cfg.WolframKeyProtected = blob;
        if (!cfg.Save(out string err)) return Fail("已加密但写入配置失败：" + err);
        lock (ConfigLock) _config = cfg;
        _memoryKey = "";
        return "{\"ok\":true,\"persisted\":true}";
    }

    public string ClearWolframKey()
    {
        _memoryKey = "";
        var cfg = Config;
        cfg.WolframKeyProtected = "";
        if (!cfg.Save(out string err)) return Fail("清除失败：" + err);
        lock (ConfigLock) _config = cfg;
        return "{\"ok\":true}";
    }

    private static string ResolveKey()
    {
        if (!string.IsNullOrEmpty(_memoryKey)) return _memoryKey;
        var cfg = Config;
        if (string.IsNullOrEmpty(cfg.WolframKeyProtected)) return "";
        try { return Dpapi.Unprotect(cfg.WolframKeyProtected) ?? ""; } catch { return ""; }
    }

    /* ── 搜索 ───────────────────────────────────────────────────────────── */

    /// <summary>
    /// 发起一次搜索，**立即返回**；结果经 PushHub 推回去（同步 host object 调用会把渲染进程
    /// 冻住几秒，控制台与 AI 那边都踩过这条）。
    /// 入参：<code>{"query":"…","engine":"duckduckgo|wolfram|custom","noCache":false}</code>
    /// </summary>
    public string Start(string json)
    {
        string query = "", engine = "";
        bool noCache = false;
        try
        {
            using var doc = System.Text.Json.JsonDocument.Parse(json);
            var root = doc.RootElement;
            if (root.TryGetProperty("query", out var q) && q.ValueKind == System.Text.Json.JsonValueKind.String)
                query = (q.GetString() ?? "").Trim();
            if (root.TryGetProperty("engine", out var e) && e.ValueKind == System.Text.Json.JsonValueKind.String)
                engine = e.GetString() ?? "";
            if (root.TryGetProperty("noCache", out var nc) &&
                (nc.ValueKind == System.Text.Json.JsonValueKind.True || nc.ValueKind == System.Text.Json.JsonValueKind.False))
                noCache = nc.GetBoolean();
        }
        catch (Exception e) { return Fail("请求解析失败：" + e.Message); }

        if (query.Length == 0) return Fail("查询为空");

        var cfg = Config;
        if (string.IsNullOrWhiteSpace(engine)) engine = cfg.Engine;
        if (engine != "duckduckgo" && engine != "wolfram" && engine != "custom") engine = "duckduckgo";

        string id = "s" + Interlocked.Increment(ref _seq);
        var job = new Job { Id = id, Query = query, Engine = engine };
        Jobs[id] = job;

        string key = ResolveKey();
        Task.Run(async () =>
        {
            var sw = Stopwatch.StartNew();
            try
            {
                // ① 缓存（键含引擎；命中就完全不出网）
                if (!noCache && cfg.CacheEnabled)
                {
                    var (hit, entry) = SearchCache.Get(engine, query, cfg);
                    if (hit && entry != null)
                    {
                        PushDone(id, engine, entry.Results, entry.Abstract, true, sw.ElapsedMilliseconds, entry.At);
                        job.State = "done";
                        return;
                    }
                }

                // ② 抓取。超时与"用户取消"分开：收尾时才能说清是谁取消的
                using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(cfg.TimeoutSec));
                using var linked = CancellationTokenSource.CreateLinkedTokenSource(timeout.Token, job.Cts.Token);

                SearchOutcome outcome;
                try
                {
                    outcome = await SearchBackend.RunAsync(cfg, key, query, linked.Token).ConfigureAwait(false);
                }
                catch (OperationCanceledException)
                {
                    bool isTimeout = timeout.IsCancellationRequested && !job.Cts.IsCancellationRequested;
                    PushError(id, isTimeout ? "timeout" : "aborted",
                              isTimeout ? $"超过 {cfg.TimeoutSec} 秒没有返回（可在设置 → 搜索里调大）" : "已取消", 0);
                    job.State = "error";
                    return;
                }

                if (!outcome.Ok)
                {
                    PushError(id, outcome.ErrorKind, outcome.Error, outcome.Status);
                    job.State = "error";
                    return;
                }

                // ③ 有结果才写缓存（空结果不缓存：下次还该再试一次）
                if (cfg.CacheEnabled && (outcome.Results.Count > 0 || !string.IsNullOrEmpty(outcome.Abstract)))
                    SearchCache.Put(engine, query, outcome.Abstract, outcome.Results);

                PushDone(id, engine, outcome.Results, outcome.Abstract, false, sw.ElapsedMilliseconds, 0);
                job.State = "done";
            }
            catch (Exception e)
            {
                _lastError = "unknown: " + e.Message;
                PushError(id, "unknown", e.GetType().Name + "：" + e.Message, 0);
                job.State = "error";
            }
        });

        return "{\"ok\":true,\"requestId\":" + J(id) + ",\"engine\":" + J(engine) + "}";
    }

    public string Cancel(string requestId)
    {
        if (Jobs.TryGetValue(requestId ?? "", out var job))
        {
            try { job.Cts.Cancel(); } catch { }
            return "{\"ok\":true}";
        }
        return "{\"ok\":false,\"error\":\"没有这个请求\"}";
    }

    public string CancelAll()
    {
        int n = 0;
        foreach (var kv in Jobs)
        {
            if (kv.Value.State != "running") continue;
            try { kv.Value.Cts.Cancel(); n++; } catch { }
        }
        return "{\"ok\":true,\"cancelled\":" + n + "}";
    }

    private static void PushDone(string id, string engine, System.Collections.Generic.List<SearchResult> results,
                                 string @abstract, bool fromCache, long elapsedMs, long cachedAt)
    {
        var sb = new StringBuilder("{\"requestId\":").Append(J(id));
        sb.Append(",\"engine\":").Append(J(engine));
        sb.Append(",\"fromCache\":").Append(B(fromCache));
        sb.Append(",\"cachedAt\":").Append(cachedAt);
        sb.Append(",\"elapsedMs\":").Append(elapsedMs);
        sb.Append(",\"abstract\":").Append(J(@abstract ?? ""));
        sb.Append(",\"results\":[");
        for (int i = 0; i < results.Count; i++)
        {
            var r = results[i];
            if (i > 0) sb.Append(',');
            sb.Append("{\"title\":").Append(J(r.Title))
              .Append(",\"url\":").Append(J(r.Url))
              .Append(",\"snippet\":").Append(J(r.Snippet))
              .Append(",\"source\":").Append(J(r.Source)).Append('}');
        }
        sb.Append("]}");
        PushHub.Send("search.done", sb.ToString());
    }

    private static void PushError(string id, string kind, string message, int status)
    {
        _lastError = kind + ": " + message;
        PushHub.Send("search.error", "{\"requestId\":" + J(id)
            + ",\"kind\":" + J(kind)
            + ",\"status\":" + status
            + ",\"message\":" + J(message) + "}");
    }

    /* ── 打开结果（搜索结果的自然动作）──────────────────────────────────── */

    /// <summary>
    /// 用系统默认浏览器打开一个链接。**只放行 http/https** —— 否则这就成了
    /// "用任意协议启动本机程序"的原语（`file:`、`ms-*:`、自定义协议都能被利用）。
    /// </summary>
    public string OpenUrl(string url)
    {
        // 闸门与实现都在 ShellOpen 里（更新链也用同一份）；这里只做转发，避免两处各写一份
        var (ok, err) = ShellOpen.Url(url);
        return ok ? "{\"ok\":true}" : Fail(err);
    }

    /* ── 缓存 ───────────────────────────────────────────────────────────── */

    public string CacheStats() => SearchCache.Stats();

    public string ClearCache() => SearchCache.Clear();

    /* ── 自检（不联网）──────────────────────────────────────────────────── */

    /// <summary>
    /// 五项自检，**都不联网**：解析器拿内置样本跑（DDG HTML / DDG IA / SearXNG JSON /
    /// Wolfram 纯文本）、缓存键含引擎、OpenUrl 协议闸门。解析器是最容易随对方改版而碎的一层，
    /// 所以它必须能在不联网的情况下被验。
    /// </summary>
    public string SelfCheck()
    {
        var sb = new StringBuilder("{\"ok\":true,\"checks\":[");
        bool all = true;

        // ① DDG HTML 解析
        const string ddgHtml = "<html><body>"
            + "<a rel=\"nofollow\" class=\"result__a\" href=\"//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fx&amp;rut=1\">示例 <b>标题</b></a>"
            + "<a class=\"result__snippet\" href=\"x\">示例 <b>摘要</b> 文本</a>"
            + "<a class=\"result__a\" href=\"javascript:alert(1)\">坏链接</a>"
            + "</body></html>";
        var parsed = SearchBackend.ParseDdgHtml(ddgHtml, 8);
        bool ddgOk = parsed.Count == 1
                     && parsed[0].Url == "https://example.com/x"
                     && parsed[0].Title == "示例 标题"
                     && parsed[0].Snippet == "示例 摘要 文本";
        all &= ddgOk;
        sb.Append("{\"name\":\"DuckDuckGo 结果解析\",\"ok\":").Append(B(ddgOk))
          .Append(",\"detail\":").Append(J(ddgOk
              ? "跳转链接还原 + 去标签 + 丢弃 javascript: 链接 都正确"
              : "内置样本解析不符合预期")).Append('}');

        // ② DDG Instant Answer 摘要
        bool iaOk = SearchBackend.ParseDdgAbstract("{\"AbstractText\":\"<b>黎曼猜想</b>是关于 ζ 函数零点的猜想。\"}")
                    == "黎曼猜想 是关于 ζ 函数零点的猜想。";
        all &= iaOk;
        sb.Append(",{\"name\":\"Instant Answer 摘要解析\",\"ok\":").Append(B(iaOk))
          .Append(",\"detail\":").Append(J(iaOk ? "取 AbstractText 并去标签" : "摘要解析不符合预期")).Append('}');

        // ③ SearXNG JSON 解析
        const string searx = "{\"results\":[{\"title\":\"甲\",\"url\":\"https://a.example\",\"content\":\"内容\",\"engine\":\"google\"}"
            + ",{\"title\":\"坏\",\"url\":\"data:text/html,x\",\"content\":\"\",\"engine\":\"\"}]}";
        bool sxOk = false;
        try
        {
            var r = SearchBackend.ParseSearxng(searx, 8);
            sxOk = r.Count == 1 && r[0].Title == "甲" && r[0].Url == "https://a.example";
        }
        catch { sxOk = false; }
        all &= sxOk;
        sb.Append(",{\"name\":\"SearXNG JSON 解析\",\"ok\":").Append(B(sxOk))
          .Append(",\"detail\":").Append(J(sxOk ? "取 results 并丢弃非 http(s) 的 url" : "解析不符合预期")).Append('}');

        // ④ 缓存键必须含引擎（v1 的缺陷：换引擎仍然命中旧结果）
        bool keyOk;
        try
        {
            SearchCache.Put("__selftest_a__", "x", "", new System.Collections.Generic.List<SearchResult>
                { new() { Title = "t", Url = "https://e.com" } });
            var cfgA = SearchConfig.Normalize(new SearchConfig { CacheEnabled = true, CacheTtlHours = 24 });
            var (hitA, _) = SearchCache.Get("__selftest_a__", "x", cfgA);
            var (hitB, _) = SearchCache.Get("__selftest_b__", "x", cfgA);   // 换了引擎
            var (missC, _) = SearchCache.Get("__selftest_a__", "y", cfgA);  // 换了查询
            keyOk = hitA && !hitB && !missC;
        }
        catch { keyOk = false; }
        all &= keyOk;
        sb.Append(",{\"name\":\"缓存键含引擎 + TTL\",\"ok\":").Append(B(keyOk))
          .Append(",\"detail\":").Append(J(keyOk
              ? "同引擎同查询命中；换引擎或换查询都不命中（v1 只用查询词做键，换了引擎不生效）"
              : "缓存键或命中判定不符合预期")).Append('}');

        // ⑤ OpenUrl 只放行 http(s)
        bool urlOk = SearchBackend.IsHttpUrl("https://example.com")
                     && SearchBackend.IsHttpUrl("http://example.com")
                     && !SearchBackend.IsHttpUrl("javascript:alert(1)")
                     && !SearchBackend.IsHttpUrl("file:///C:/Windows/System32/cmd.exe")
                     && !SearchBackend.IsHttpUrl("ms-settings:")
                     && !SearchBackend.IsHttpUrl("");
        all &= urlOk;
        sb.Append(",{\"name\":\"打开链接只放行 http/https\",\"ok\":").Append(B(urlOk))
          .Append(",\"detail\":").Append(J(urlOk
              ? "javascript: / file: / ms-* 一律拒绝（否则成了用任意协议启动本机程序的原语）"
              : "协议闸门判定不正确")).Append('}');

        sb.Append("],\"ok_all\":").Append(B(all)).Append('}');
        return sb.ToString();
    }
}
