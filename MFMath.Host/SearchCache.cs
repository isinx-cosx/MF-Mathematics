// SearchCache.cs — 搜索结果的本地缓存
//
// 三条规矩，第一条是**修 v1 的缺陷**：
//   ① **缓存键必须带引擎**。v1 只用查询词做键，于是"用 A 引擎搜过 x"会让"用 B 引擎搜 x"
//      直接命中 A 的结果 —— 换了引擎却不生效，而且看不出来。
//   ② **带 TTL**，过期即视为未命中（v1 没有）。TTL 从配置读，0 表示不过期。
//   ③ **有上限**，按时间淘汰最旧的（默认 200 条），并且原子落盘 ——
//      缓存文件坏了只丢缓存，不能连累搜索本身。
//
// 文件：%LOCALAPPDATA%\MFMath\search_cache.json（和别的数据同处一地，诊断包能一起带走）
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace MFMath.Host;

internal sealed class SearchCacheEntry
{
    public long At { get; set; }
    public string Query { get; set; } = "";
    public string Engine { get; set; } = "";
    public string Abstract { get; set; } = "";
    public List<SearchResult> Results { get; set; } = new();
}

internal static class SearchCache
{
    private const int MaxEntries = 200;
    private static readonly object Gate = new();
    private static Dictionary<string, SearchCacheEntry>? _entries;
    private static bool _dirty;

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        WriteIndented = false,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        PropertyNameCaseInsensitive = true,
    };

    private static string FilePath => Path.Combine(SearchConfig.Dir, "..", "search_cache.json");

    /** 规范化查询：去空白、折叠空格、小写 —— "x^2" 与 " X^2 " 应当命中同一条 */
    private static string Normalize(string query)
        => string.Join(" ", (query ?? "").Trim().ToLowerInvariant().Split(' ', StringSplitOptions.RemoveEmptyEntries));

    private static string Key(string engine, string query) => engine + "|" + Normalize(query);

    private static Dictionary<string, SearchCacheEntry> Entries()
    {
        if (_entries != null) return _entries;
        try
        {
            string p = Path.GetFullPath(FilePath);
            if (File.Exists(p))
            {
                string text = File.ReadAllText(p, Encoding.UTF8);
                var list = JsonSerializer.Deserialize<List<SearchCacheEntry>>(text, JsonOpts) ?? new List<SearchCacheEntry>();
                var map = new Dictionary<string, SearchCacheEntry>(StringComparer.Ordinal);
                foreach (var e in list)
                {
                    if (e == null || string.IsNullOrEmpty(e.Engine)) continue;
                    map[Key(e.Engine, e.Query)] = e;
                }
                return _entries = map;
            }
        }
        catch { /* 坏文件：当空缓存，不阻断搜索 */ }
        return _entries = new Dictionary<string, SearchCacheEntry>(StringComparer.Ordinal);
    }

    public static (bool hit, SearchCacheEntry? entry) Get(string engine, string query, SearchConfig cfg)
    {
        if (!cfg.CacheEnabled) return (false, null);
        lock (Gate)
        {
            if (!Entries().TryGetValue(Key(engine, query), out var e) || e == null) return (false, null);
            if (cfg.CacheTtlHours > 0)
            {
                double ageHours = (DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() - e.At) / 3600000.0;
                if (ageHours > cfg.CacheTtlHours) return (false, null);   // 过期当未命中
            }
            return (true, e);
        }
    }

    public static void Put(string engine, string query, string @abstract, List<SearchResult> results)
    {
        lock (Gate)
        {
            var map = Entries();
            map[Key(engine, query)] = new SearchCacheEntry
            {
                At = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                Query = query,
                Engine = engine,
                Abstract = @abstract ?? "",
                Results = results ?? new List<SearchResult>(),
            };
            // 超上限就按时间淘汰最旧的
            if (map.Count > MaxEntries)
            {
                foreach (var k in map.OrderBy(kv => kv.Value.At).Take(map.Count - MaxEntries).Select(kv => kv.Key).ToList())
                    map.Remove(k);
            }
            _dirty = true;
            Save();
        }
    }

    /// <summary>原子落盘（临时文件 + File.Replace）。失败只丢缓存，不影响这次搜索。</summary>
    private static void Save()
    {
        if (!_dirty) return;
        try
        {
            string p = Path.GetFullPath(FilePath);
            Directory.CreateDirectory(Path.GetDirectoryName(p)!);
            string json = JsonSerializer.Serialize(Entries().Values.OrderBy(e => e.At).ToList(), JsonOpts);
            string tmp = p + ".tmp";
            File.WriteAllText(tmp, json, new UTF8Encoding(false));
            if (File.Exists(p)) File.Replace(tmp, p, null, true);
            else File.Move(tmp, p);
            _dirty = false;
        }
        catch { /* 忽略：下次仍可重试 */ }
    }

    public static string Stats()
    {
        lock (Gate)
        {
            var map = Entries();
            long bytes = 0;
            try { var fi = new FileInfo(Path.GetFullPath(FilePath)); if (fi.Exists) bytes = fi.Length; } catch { }
            long newest = map.Count == 0 ? 0 : map.Values.Max(e => e.At);
            return "{\"entries\":" + map.Count + ",\"bytes\":" + bytes + ",\"newest\":" + newest + "}";
        }
    }

    public static string Clear()
    {
        lock (Gate)
        {
            int n = Entries().Count;
            _entries = new Dictionary<string, SearchCacheEntry>(StringComparer.Ordinal);
            _dirty = true;
            try
            {
                string p = Path.GetFullPath(FilePath);
                if (File.Exists(p)) File.Delete(p);
            }
            catch { /* 删不掉也把内存清了 */ }
            return "{\"ok\":true,\"cleared\":" + n + "}";
        }
    }
}
