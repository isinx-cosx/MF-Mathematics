using System;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Threading;

namespace MFMath.Host;

/// <summary>
/// 可选组件的下载器（CPython / MinGW 工具链）。
///
/// 为什么需要它：组件包是 11 MB / 54 MB，不可能塞进安装包让所有人先下。
/// 之前只能手工把 zip 丢到缓存目录，普通用户做不到，所以"可选组件"实际上等于没提供。
///
/// 三个必须做对的地方（都是实测踩出来的）：
///
///   ① **断点续传**。54 MB 走一遍网络，中途断线几乎必然发生；从 0 重来对用户是灾难。
///      这里把已下载的部分留在 <c>&lt;文件名&gt;.part</c>，下次带
///      <c>Range: bytes=&lt;已下载&gt;-</c> 接着下，服务端返回 206 就追加。
///      服务端**不支持** Range（返回 200 全量）时必须退化成从头写，否则会把整个文件
///      追加到旧内容后面，得到一个长度翻倍、哈希对不上的怪文件。
///
///   ② **校验后才认账**。下载完先比 SHA-256，对不上就当失败、保留 .part 供续传，
///      绝不让半个包进到解压流程（否则报错会指到"解压后没有 python.exe"这种误导性地方）。
///
///   ③ **失败要能续**。网络错误/超时不算致命：保留 .part、把原因说清楚，
///      用户下次点"安装"就从断点接着走，而不是从零开始。
/// </summary>
internal static class ComponentDownload
{
    /// <summary>默认走官网；企业内网/离线镜像可以用 SetDownloadBase 或环境变量改。</summary>
    public const string DefaultBaseUrl = "https://mf-vis-science.cn";

    private static string _baseUrl = ResolveInitialBase();

    private static string ResolveInitialBase()
    {
        string? env = Environment.GetEnvironmentVariable("MF_COMPONENT_BASE");
        return string.IsNullOrWhiteSpace(env) ? DefaultBaseUrl : env.TrimEnd('/');
    }

    public static string BaseUrl => _baseUrl;

    public static void SetBaseUrl(string? url)
    {
        if (string.IsNullOrWhiteSpace(url)) { _baseUrl = ResolveInitialBase(); return; }
        _baseUrl = url.Trim().TrimEnd('/');
    }

    public static string UrlFor(string name) => _baseUrl + "/download/component/" + name;

    private static readonly HttpClient Http = CreateClient();

    private static HttpClient CreateClient()
    {
        var handler = new SocketsHttpHandler
        {
            // 缺文件时站点会 302 到 GitHub Release，必须允许跟随重定向
            AllowAutoRedirect = true,
            MaxAutomaticRedirections = 5,
            ConnectTimeout = TimeSpan.FromSeconds(20),
        };
        var c = new HttpClient(handler)
        {
            // 单个请求不设短超时：54 MB 慢网可能要好几分钟，靠读流的超时兜底即可
            Timeout = Timeout.InfiniteTimeSpan,
        };
        c.DefaultRequestHeaders.UserAgent.ParseAdd("MFMath-Host/1.0 (+https://mf-vis-science.cn)");
        return c;
    }

    public sealed class Result
    {
        public string Path = "";
        public long Bytes;
        public bool Resumed;         // 这次是否续传
        public long ResumedFrom;
    }

    /// <summary>
    /// 下载组件包到 <paramref name="cacheDir"/>，文件名 <paramref name="fileName"/>。
    /// 已存在同名完整文件时直接复用（不再联网）。
    /// </summary>
    /// <param name="progress">进度回调：百分比、给用户看的一句话</param>
    /// <param name="log">细节日志（每行会进安装任务的消息，便于出问题时报出来）</param>
    public static Result Download(string componentName, string fileName, string cacheDir,
                                  Action<int, string> progress, Action<string> log,
                                  CancellationToken ct)
    {
        Directory.CreateDirectory(cacheDir);
        string finalPath = Path.Combine(cacheDir, fileName);
        string partPath = finalPath + ".part";

        if (File.Exists(finalPath) && new FileInfo(finalPath).Length > 0)
        {
            log("缓存里已有 " + fileName + "，跳过下载");
            return new Result { Path = finalPath, Bytes = new FileInfo(finalPath).Length };
        }

        string url = UrlFor(componentName);
        var result = new Result { Path = finalPath };
        Exception? lastError = null;

        // 最多 3 轮：每轮都从 .part 的当前长度接着下，所以"重试"就是"续传"
        for (int attempt = 1; attempt <= 3; attempt++)
        {
            ct.ThrowIfCancellationRequested();
            long have = File.Exists(partPath) ? new FileInfo(partPath).Length : 0;
            try
            {
                using var req = new HttpRequestMessage(HttpMethod.Get, url);
                if (have > 0) req.Headers.Range = new RangeHeaderValue(have, null);

                using var resp = Http.Send(req, HttpCompletionOption.ResponseHeadersRead, ct);
                long total = resp.Content.Headers.ContentLength is long len
                    ? (resp.StatusCode == System.Net.HttpStatusCode.PartialContent ? len + have : len)
                    : -1;

                if (resp.StatusCode == System.Net.HttpStatusCode.RequestedRangeNotSatisfiable)
                {
                    // 服务端说这个范围不合法：多半是 .part 比真实文件还大（换过包/写坏了）
                    log("服务端拒绝了续传范围（416），删掉半成品重新下载");
                    TryDelete(partPath);
                    have = 0;
                    continue;
                }
                if (!resp.IsSuccessStatusCode)
                    throw new HttpRequestException("下载失败：HTTP " + (int)resp.StatusCode + " " + resp.ReasonPhrase);

                bool resumed = resp.StatusCode == System.Net.HttpStatusCode.PartialContent && have > 0;
                if (!resumed && have > 0)
                {
                    // 服务端忽略了 Range（返回 200 全量）：必须从头写，绝不能追加
                    log("服务端不支持断点续传（返回 200 全量），已丢弃已下载的 " + have + " 字节重新开始");
                    have = 0;
                }
                result.Resumed = resumed;
                result.ResumedFrom = have;

                FileMode mode = resumed ? FileMode.Append : FileMode.Create;
                using (var fs = new FileStream(partPath, mode, FileAccess.Write, FileShare.None, 1 << 16))
                using (var src = resp.Content.ReadAsStream(ct))
                {
                    var buf = new byte[1 << 17];   // 128 KB
                    long done = have;
                    int n;
                    int lastPct = -1;
                    while ((n = src.Read(buf, 0, buf.Length)) > 0)
                    {
                        ct.ThrowIfCancellationRequested();
                        fs.Write(buf, 0, n);
                        done += n;
                        int pct = total > 0 ? (int)(done * 90 / total) : 0;   // 下载占 0~90%
                        if (pct != lastPct)
                        {
                            lastPct = pct;
                            progress(pct, string.Format("下载 {0}：{1}/{2} MB{3}",
                                componentName,
                                done / 1048576,
                                total > 0 ? (total / 1048576).ToString() : "?",
                                resumed ? "（续传）" : ""));
                        }
                    }
                    fs.Flush(true);
                    result.Bytes = done;
                }

                if (total > 0 && result.Bytes != total)
                    throw new IOException(string.Format(
                        "下载不完整：期望 {0} 字节，实际 {1} 字节（已保留断点，下次会接着下）", total, result.Bytes));

                File.Move(partPath, finalPath, overwrite: true);
                result.Path = finalPath;
                return result;
            }
            catch (OperationCanceledException) when (ct.IsCancellationRequested)
            {
                throw;
            }
            catch (Exception ex)
            {
                lastError = ex;
                long kept = File.Exists(partPath) ? new FileInfo(partPath).Length : 0;
                if (attempt < 3)
                {
                    log("第 " + attempt + " 次下载中断（" + ex.Message + "），已保留 " + kept + " 字节，准备续传");
                    Thread.Sleep(800 * attempt);
                }
                else
                {
                    log("第 " + attempt + " 次下载失败（" + ex.Message + "），已保留 " + kept + " 字节");
                }
            }
        }

        throw new InvalidOperationException(
            "组件下载失败：" + (lastError?.Message ?? "未知原因") + "\n" +
            "下载地址：" + url + "\n" +
            "已保留断点文件：" + partPath + "（下次点「安装」会接着下）\n" +
            "如果这台机器不能访问外网，也可以手工把 " + fileName + " 放到 " + cacheDir + " 后再点安装。");
    }

    private static void TryDelete(string path)
    {
        try { if (File.Exists(path)) File.Delete(path); } catch { /* 忽略 */ }
    }
}
