// ShellOpen.cs — 用系统默认程序打开链接（唯一实现）
//
// 为什么要抽出来：搜索的"打开结果"、更新的"打开下载页"都需要它，而它带一条**安全闸门** ——
// 只放行 http/https。闸门写两份就迟早会有一份被改坏（而且改坏的那份不会有人注意），
// 所以这里只留一份，两个桥都调它。
//
// 不放行其它协议的理由：`file:`、`ms-settings:`、各种自定义协议都能用系统处理程序启动本机
// 程序 —— 那已经不是"打开链接"，而是"用任意协议启动程序"的原语。搜索结果与下载地址都是
// 外部内容，不能让它们碰到这个能力。
using System;
using System.Diagnostics;

namespace MFMath.Host;

internal static class ShellOpen
{
    /// <summary>只接受 http/https；返回是否放行</summary>
    public static bool IsAllowed(string url)
    {
        string u = (url ?? "").Trim();
        if (u.Length == 0) return false;
        // 用一个真正的 Uri 解析，而不是 StartsWith：后者会放过 "javascript:..." 里
        // 混进来的 "https://"（例如 "javascript:location='https://x'"）。
        if (!Uri.TryCreate(u, UriKind.Absolute, out var uri)) return false;
        return uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps;
    }

    /// <summary>放行则用系统默认浏览器打开；返回 (ok, error)</summary>
    public static (bool ok, string error) Url(string url)
    {
        if (!IsAllowed(url)) return (false, "只允许打开 http/https 链接");
        try
        {
            Process.Start(new ProcessStartInfo { FileName = (url ?? "").Trim(), UseShellExecute = true });
            return (true, "");
        }
        catch (Exception e)
        {
            return (false, "打开失败：" + e.Message);
        }
    }
}
