// UpdateBridge.cs — 更新链（只提示 + 显示校验值 + 把下载交给浏览器）
//
// 本项目的既定取舍（已在 OPEN-ITEMS/决策里定下）：
//   **不自动下载、不执行安装包**。软件只做三件事：查版本、如实显示差异、把下载页交给浏览器。
//   理由：自动执行安装包等于给软件装了一条"下载并运行可执行文件"的通路；少一个通路少一片攻击面。
//
// 一条容易被忽略的真实陷阱（本轮特意处理）：
//   站点 `/api/version` 现在报的是 **1.2.0**（v1 的版本）。如果只判断"站点版本 ≠ 本机版本"，
//   v2 的软件会被提示"有新版 1.2.0"，然后把用户引去下载 **v1 安装包** —— 那是降级，不是更新。
//   所以这里比较的是**关系**（newer / same / older），只有站点确实更新时才提示"有新版本"，
//   站点更旧时如实说明"站点上的是 X（比当前版本旧）"并给出原因。
using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace MFMath.Host;

[ComVisible(true)]
public class UpdateBridge
{
    private static volatile string _lastError = "";
    private static long _lastCheckAt;
    private static string _lastResult = "";
    private static readonly CancellationTokenSource Life = new();

    private static string J(string? s) => PushHub.Str(s);
    private static string B(bool v) => v ? "true" : "false";
    private static string Fail(string message) => "{\"ok\":false,\"error\":" + J(message) + "}";

    /* ── 本机版本 ───────────────────────────────────────────────────────── */

    /// <summary>本机版本（程序集信息版本；csproj 里显式声明，不能靠默认的 1.0.0.0）</summary>
    public static string AppVersion()
    {
        try
        {
            var asm = Assembly.GetExecutingAssembly();
            string? info = asm.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion;
            if (!string.IsNullOrWhiteSpace(info))
            {
                // InformationalVersion 可能带 +<commit> 后缀，只取版本号部分
                int plus = info.IndexOf('+');
                return plus > 0 ? info.Substring(0, plus) : info;
            }
            return asm.GetName().Version?.ToString(3) ?? "0.0.0";
        }
        catch { return "0.0.0"; }
    }

    /// <summary>
    /// 版本比较：数字段逐段比（1.10.0 &gt; 1.9.9 —— 字符串比较会搞错这个），
    /// 带预发布后缀的（2.0.0-beta）视为**小于**同号正式版。
    /// 返回 &gt;0 表示 a 更新。
    /// </summary>
    public static int CompareVersions(string a, string b)
    {
        (int[] nums, string pre) Parse(string v)
        {
            string s = (v ?? "").Trim();
            string pre = "";
            int dash = s.IndexOf('-');
            if (dash >= 0) { pre = s.Substring(dash + 1); s = s.Substring(0, dash); }
            var parts = s.Split('.');
            var nums = new int[parts.Length];
            for (int i = 0; i < parts.Length; i++)
            {
                var digits = new StringBuilder();
                foreach (char c in parts[i]) { if (char.IsDigit(c)) digits.Append(c); else break; }
                nums[i] = digits.Length > 0 && int.TryParse(digits.ToString(), out int n) ? n : 0;
            }
            return (nums, pre);
        }

        var (na, pa) = Parse(a);
        var (nb, pb) = Parse(b);
        int len = Math.Max(na.Length, nb.Length);
        for (int i = 0; i < len; i++)
        {
            int x = i < na.Length ? na[i] : 0;
            int y = i < nb.Length ? nb[i] : 0;
            if (x != y) return x > y ? 1 : -1;
        }
        if (pa.Length == 0 && pb.Length == 0) return 0;
        if (pa.Length == 0) return 1;      // 正式版 > 预发布
        if (pb.Length == 0) return -1;
        return string.CompareOrdinal(pa, pb);
    }

    /* ── 状态 ───────────────────────────────────────────────────────────── */

    /// <summary>脱敏状态：本机版本、上次检查结果、下载地址（不含任何凭据）</summary>
    public string Info()
    {
        var sb = new StringBuilder("{");
        sb.Append("\"appVersion\":").Append(J(AppVersion()));
        sb.Append(",\"lastCheckAt\":").Append(_lastCheckAt);
        sb.Append(",\"lastError\":").Append(J(_lastError));
        sb.Append(",\"lastResult\":").Append(_lastResult.Length > 0 ? _lastResult : "null");
        sb.Append(",\"policy\":").Append(J("只提示与显示校验值；下载与安装都交给浏览器，软件不自动执行安装包"));
        sb.Append(",\"baseUrl\":").Append(J(AccountConfig.Load().BaseUrl));
        sb.Append('}');
        return sb.ToString();
    }

    /* ── 检查 ───────────────────────────────────────────────────────────── */

    /// <summary>
    /// 查一次站点版本。返回
    /// <code>{ok, current, latest, date, relation, hasUpdate, sha256, size, sha256Reason, downloadUrl, changelogUrl, note}</code>
    /// 站点不通时 ok=false + error（**不影响任何计算功能**）。
    /// </summary>
    public string Check()
    {
        var cfg = AccountConfig.Load();
        var call = AccountApi.Get(cfg.BaseUrl, "/api/version", null, cfg.TimeoutSec, Life.Token)
                             .GetAwaiter().GetResult();
        if (!call.Ok)
        {
            _lastError = call.Error;
            return "{\"ok\":false,\"kind\":" + J(call.ErrorKind) + ",\"error\":" + J(call.Error) + "}";
        }

        string current = AppVersion();
        var parsed = ParseVersionBody(call.Body, current);
        _lastCheckAt = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        _lastError = "";
        _lastResult = parsed;
        return parsed;
    }

    /// <summary>
    /// 解析 `/api/version` 的信封（{code,data:{…}} 或平铺），并与本机版本比较。
    /// 抽成静态方法是为了让 AccountBridge.SiteVersion 复用同一份解析（一处实现）。
    /// </summary>
    public static string ParseVersionBody(string body, string current)
    {
        string latest = "", date = "", download = "", changelog = "", sha = "", reason = "";
        long size = 0;
        try
        {
            using var doc = JsonDocument.Parse(body);
            var root = doc.RootElement;
            if (root.TryGetProperty("data", out var data) && data.ValueKind == JsonValueKind.Object) root = data;
            string raw = root.GetRawText();
            latest = AccountApi.JsonStr(raw, "latest");
            date = AccountApi.JsonStr(raw, "date");
            download = AccountApi.JsonStr(raw, "download_url");
            changelog = AccountApi.JsonStr(raw, "changelog");
            sha = AccountApi.JsonStr(raw, "sha256");
            reason = AccountApi.JsonStr(raw, "sha256_reason");
            if (root.TryGetProperty("size", out var sz) && sz.ValueKind == JsonValueKind.Number && sz.TryGetInt64(out long n)) size = n;
        }
        catch
        {
            return "{\"ok\":false,\"kind\":\"parse\",\"error\":\"版本接口返回的形状不认识\"}";
        }

        int cmp = CompareVersions(latest, current);
        string relation = cmp > 0 ? "newer" : cmp < 0 ? "older" : "same";
        bool hasUpdate = relation == "newer";
        // 站点比本机旧时**不提示更新**，并且把原因说清楚（否则用户会以为该下载那个包）
        string note = relation switch
        {
            "newer" => "站点上有更新的版本。下载页会在浏览器里打开；本软件不会自动下载或运行安装包。",
            "same" => "已是最新版本。",
            "older" => "站点上的版本比本机旧（发布 v2.0 时需要把站点 src/lib/constants.ts 的 VERSION 改成 2.0.0）。",
            _ => "",
        };

        var sb = new StringBuilder("{");
        sb.Append("\"ok\":true");
        sb.Append(",\"current\":").Append(PushHub.Str(current));
        sb.Append(",\"latest\":").Append(PushHub.Str(latest));
        sb.Append(",\"date\":").Append(PushHub.Str(date));
        sb.Append(",\"relation\":").Append(PushHub.Str(relation));
        sb.Append(",\"hasUpdate\":").Append(hasUpdate ? "true" : "false");
        // 没给校验值时**如实说没有 + 原因**，绝不给个空字符串让界面显示成"已校验"
        sb.Append(",\"sha256\":").Append(sha.Length > 0 ? PushHub.Str(sha) : "null");
        sb.Append(",\"sha256Reason\":").Append(sha.Length > 0 ? "null" : PushHub.Str(reason.Length > 0 ? reason : "站点没有提供校验值"));
        sb.Append(",\"size\":").Append(size > 0 ? size.ToString() : "null");
        sb.Append(",\"downloadUrl\":").Append(PushHub.Str(download));
        sb.Append(",\"changelogUrl\":").Append(PushHub.Str(changelog));
        sb.Append(",\"note\":").Append(PushHub.Str(note));
        // ⚠ 别漏这个收尾括号：漏了的话 JSON 不合法，而页面侧的 parse() 失败会返回 null，
        // 于是表现成"宿主没有响应" —— 一个 JSON 拼写错误被伪装成"桥不通"，非常难查（本轮踩过）。
        sb.Append('}');
        return sb.ToString();
    }

    /// <summary>
    /// 把下载页交给浏览器。
    ///
    /// ⚠ 这里有个**必须区分两种情况**的坑（本轮被用例逼出来的）：
    /// 一开始我把"不是 http(s) 开头"的一律当相对路径，拼到站点地址上去 ——
    /// 于是 `javascript:alert(1)` 被拼成了 `http://站点/javascript:alert(1)`，
    /// 协议闸门形同虚设（它已经是个合法的 http URL 了）。所以现在：
    ///   · 带协议的（`^scheme:`）→ 直接过 ShellOpen 的闸门，只放行 http/https；
    ///   · 不带协议的 → 才当站内相对路径，并且拒绝 `//host`、`..`、`\`、`:`、空白 —— 
    ///     否则相对路径本身就是一个"跳到别处"的口子。
    /// </summary>
    public string OpenDownloadPage(string url)
    {
        var (ok, absolute, reason) = ResolveDownloadUrl(url);
        if (!ok) return Fail(reason);
        var (opened, err) = ShellOpen.Url(absolute);
        return opened ? "{\"ok\":true,\"opened\":" + J(absolute) + "}" : Fail(err);
    }

    /// <summary>
    /// **只算出"将会打开的地址"，不真的打开。**
    /// 两个用处：① 界面上先给用户看"将打开：<url>"（而不是点下去才知道去哪儿）；
    /// ② 让"相对路径拼接 + 协议闸门"这条逻辑能被端到端断言，而不必在测试里真弹一个浏览器。
    /// 返回 (是否放行, 绝对地址, 拒绝原因)。
    /// </summary>
    public (bool ok, string url, string reason) ResolveDownloadUrl(string url)
    {
        string raw = (url ?? "").Trim();
        if (raw.Length == 0) return (false, "", "没有下载地址");

        // 带协议的 —— 一律过闸门（javascript:/file:/ms-* 在这里就被拒）
        if (System.Text.RegularExpressions.Regex.IsMatch(raw, "^[a-zA-Z][a-zA-Z0-9+.\\-]*:"))
            return ShellOpen.IsAllowed(raw) ? (true, raw, "") : (false, "", "只允许打开 http/https 链接");

        // 不带协议的 —— 才当站内相对路径（判断与自检共用 LooksRelativeSafe）
        if (!LooksRelativeSafe(raw))
            return (false, "", "只接受站点内的相对路径（不允许 //host、..、\\、: 或空白）");
        string pathPart = raw.StartsWith("/", StringComparison.Ordinal) ? raw : "/" + raw;
        return (true, AccountConfig.Load().BaseUrl.TrimEnd('/') + pathPart, "");
    }

    /// <summary>给界面用：把"将打开的地址"作为纯查询返回（不打开、不改状态）</summary>
    public string PreviewDownloadUrl(string url)
    {
        var (ok, absolute, reason) = ResolveDownloadUrl(url);
        return ok
            ? "{\"ok\":true,\"url\":" + J(absolute) + "}"
            : "{\"ok\":false,\"reason\":" + J(reason) + "}";
    }

    public void CancelAll() { try { Life.Cancel(); } catch { } }

    /* ── 自检（不联网）──────────────────────────────────────────────────── */

    /// <summary>
    /// 五项自检，**都不联网**：版本比较（含 1.10.0 &gt; 1.9.9 这个字符串比较会错的例子）、
    /// 信封解析 + 关系判定、站点更旧时不提示更新、校验值缺失如实说明、打开链接的协议闸门。
    /// </summary>
    public string SelfCheck()
    {
        var sb = new StringBuilder("{\"ok\":true,\"checks\":[");
        bool all = true;

        // ① 版本比较
        bool cmpOk = CompareVersions("1.10.0", "1.9.9") > 0
                  && CompareVersions("2.0.0", "2.0.0") == 0
                  && CompareVersions("1.2.0", "2.0.0") < 0
                  && CompareVersions("2.0.0-beta.1", "2.0.0") < 0
                  && CompareVersions("2.0.1", "2.0.0") > 0;
        all &= cmpOk;
        sb.Append("{\"name\":\"版本比较\",\"ok\":").Append(B(cmpOk))
          .Append(",\"detail\":").Append(J(cmpOk
              ? "逐段比数字（1.10.0 > 1.9.9，字符串比较会搞错）；预发布小于同号正式版"
              : "版本比较结果不符合预期")).Append('}');

        // ② 信封解析（站点是 {code,data,msg}）
        string body = "{\"code\":0,\"data\":{\"latest\":\"9.9.9\",\"date\":\"2026-01-01\",\"download_url\":\"/download\",\"sha256\":\"" + new string('a', 64) + "\",\"size\":123}" + ",\"msg\":\"success\"}";
        string parsed = ParseVersionBody(body, "2.0.0");
        bool parseOk = parsed.Contains("\"latest\":\"9.9.9\"") && parsed.Contains("\"relation\":\"newer\"")
                       && parsed.Contains("\"hasUpdate\":true") && parsed.Contains("\"size\":123");
        all &= parseOk;
        sb.Append(",{\"name\":\"版本信封解析 + 关系判定\",\"ok\":").Append(B(parseOk))
          .Append(",\"detail\":").Append(J(parseOk ? "取 data 里的字段，算出 newer / hasUpdate" : "解析结果不符合预期")).Append('}');

        // ③ 站点更旧时**不**提示更新（本轮最重要的一条：否则 v2 用户会被引去下载 v1 包）
        string older = ParseVersionBody("{\"data\":{\"latest\":\"1.2.0\",\"download_url\":\"/download\"}}", "2.0.0");
        bool olderOk = older.Contains("\"relation\":\"older\"") && older.Contains("\"hasUpdate\":false")
                       && older.Contains("比本机旧");
        all &= olderOk;
        sb.Append(",{\"name\":\"站点更旧时不提示更新\",\"ok\":").Append(B(olderOk))
          .Append(",\"detail\":").Append(J(olderOk
              ? "站点报 1.2.0、本机 2.0.0 时判定为 older 并说明原因（避免把用户引去下载 v1 安装包）"
              : "更旧场景的判定不符合预期")).Append('}');

        // ④ 校验值缺失时如实说明
        string noSha = ParseVersionBody("{\"data\":{\"latest\":\"9.9.9\",\"sha256_reason\":\"服务器上还没有安装包文件\"}}", "2.0.0");
        bool shaOk = noSha.Contains("\"sha256\":null") && noSha.Contains("服务器上还没有安装包文件");
        all &= shaOk;
        sb.Append(",{\"name\":\"校验值缺失时如实说明\",\"ok\":").Append(B(shaOk))
          .Append(",\"detail\":").Append(J(shaOk ? "返回 null 并带上站点的原因，不编造也不留空白" : "缺失场景处理不符合预期")).Append('}');

        // ⑤ 打开链接只放行 http(s)，且**带协议的输入不会被当成相对路径**（本轮修的那个 bug）
        bool urlOk = ShellOpen.IsAllowed("https://mf-vis-science.cn/download")
                  && ShellOpen.IsAllowed("http://127.0.0.1:8000/download")
                  && !ShellOpen.IsAllowed("javascript:alert(1)")
                  && !ShellOpen.IsAllowed("file:///C:/Windows/System32/cmd.exe")
                  && !ShellOpen.IsAllowed("ms-settings:")
                  && !ShellOpen.IsAllowed("")
                  // 关键回归：这几个必须被"相对路径"分支直接拒掉（而不是拼成 http 后放行）
                  && !LooksRelativeSafe("javascript:alert(1)")
                  && !LooksRelativeSafe("file:///C:/Windows/System32/cmd.exe")
                  && !LooksRelativeSafe("//evil.example/x")
                  && LooksRelativeSafe("/download")
                  && LooksRelativeSafe("download")
                  && !LooksRelativeSafe("/a/../b");
        all &= urlOk;
        sb.Append(",{\"name\":\"打开下载页只放行 http/https\",\"ok\":").Append(B(urlOk))
          .Append(",\"detail\":").Append(J(urlOk
              ? "javascript: / file: / ms-* 一律拒绝；带协议的输入不会被当成相对路径去拼接（否则闸门形同虚设）"
              : "协议闸门判定不正确")).Append('}');

        sb.Append("],\"ok_all\":").Append(B(all)).Append('}');
        return sb.ToString();
    }

    /// <summary>
    /// 与 OpenDownloadPage 里"相对路径"分支同一套判断（抽出来是为了让它能被自检覆盖）。
    /// 为什么必须能单独验：拼接逻辑曾经把 `javascript:` 拼成合法 http URL 从而绕过闸门。
    /// </summary>
    internal static bool LooksRelativeSafe(string raw)
    {
        string s = (raw ?? "").Trim();
        if (s.Length == 0) return false;
        if (System.Text.RegularExpressions.Regex.IsMatch(s, "^[a-zA-Z][a-zA-Z0-9+.\\-]*:")) return false;
        if (s.StartsWith("//", StringComparison.Ordinal)) return false;
        foreach (char c in s) if (char.IsWhiteSpace(c)) return false;
        if (s.Contains('\\') || s.Contains("..") || s.Contains(':')) return false;
        return true;
    }
}
