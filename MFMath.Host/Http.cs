using System;
using System.Collections.Generic;

namespace MFMath.Host;

/// <summary>
/// 网络环境的**取证**辅助（只读，不改变任何行为）。
///
/// ════════════════════════════════════════════════════════════════════════
/// 这里曾经有过一个 `NoSystemProxy()` 扩展方法，把四处 HTTP 客户端改成直连 ——
/// 依据是"本机 PAC 指向一个已死的代理，所以 .NET 请求全挂"。
/// **那个归因是错的，已撤回**（代码里只留下这段记录，方法本身已删除）。
///
/// 实测 A/B（同一台机器、同一个 URL）：
///   Invoke-WebRequest                      → ✗ The SSL connection could not be established
///   Invoke-WebRequest -NoProxy（= 直连）    → ✗ 同样失败
///   → 加不加代理都一样，**与 PAC 无关**。
///
/// 后续二分（都在本机、都走真实验证）：
///   · Windows 根库**有** ISRG Root X1/X2（未过期）→ 信任不是原因；
///   · .NET 强制 TLS 1.2 / 1.3 / 两者 → **都失败** → 版本协商不是原因；
///   · `curl.exe`（同样走 Schannel）→ 也失败；**Node（OpenSSL）→ 200**；
///   · Schannel 对 microsoft.com / api.github.com / baidu.com → **全部 200**
///     → 本机 Schannel 本身是好的，**只对这个域名失败**；
///   · 失败时 <c>/var/log/nginx/error.log</c> **没有新增行**（行数 6 → 6）
///     → 请求**根本没到达服务器**，reset 发生在到达之前。
///   · 顺带更正一处误读：日志里的 `SSL routines::bad key share` 来自
///     **别的**客户端 IP（212.102.40.218 / 47.95.205.214），不是本机 ——
///     曾据此改过 nginx 的 `ssl_protocols`，实测无效后已撤回
///     （只保留"去掉已废弃的 TLSv1/1.1"这个真实改进）。
///
/// 结论（**最终，服务器侧抓包定案**）：
///   服务器端 tcpdump 同时录下两条连接，对比一目了然：
///     Schannel（.NET）：SYN → SYN-ACK → ACK → **In RST（本机自己发的）** → RST → P. len=444
///     OpenSSL（Node）  ：SYN → SYN-ACK → ACK → P. len=1612（ClientHello）→ ServerHello/证书 → 正常完成
///   服务器把 RST 记为 `In`（收到），**从未拒绝过**；同一个 IP、只把 SNI 从域名换成 IP 字面量
///   就成功（curl 用 `--resolve` 强制同一 IP 也失败，排除了"解析到别的 IP"）。
///   → 触发条件是 **SNI 里的域名**，拦截发生在本机，且只对部分进程生效。
///   本机存在沙箱的全量出站阻止规则（`codex_sandbox_offline_block_outbound`，
///   远端地址 0.0.0.0-126.255.255.255 / 128.0.0.0-255.255.255.255，Action=Block），
///   而 Node（测试与部署脚本用的运行时）可正常访问本站全部端点。
///   → **这是开发机沙箱的网络策略，既不是本项目代码，也不是服务器配置问题。**
///     当时一并更正的两条错误结论：①"PAC 导致"（A/B 已证伪）；
///     ②"服务器 TLS 与 Schannel 不兼容 / bad key share"（那些日志来自别的客户端 IP，
///     且 RST 方向证明是本机发的）。
///   **浏览器用户与普通用户机器不受影响**（Chromium 走 BoringSSL）。
///
/// ⚠ 因此**不要**再因为"某台机器连不上"就去关系统代理，也不要据此去改服务器 TLS：
/// 关掉代理会害到真正需要代理访问 AI 端点的用户（本产品用户大量属于这种情况），
/// 改服务器则是打错靶子（RST 根本不在服务器）。要改之前先做本文这种抓包/A-B。
/// ════════════════════════════════════════════════════════════════════════
/// </summary>
internal static class Http
{
    /// <summary>
    /// 描述系统里配了什么代理 —— **只写日志，不参与任何决策**。
    /// 目的是让"这台机器当时是什么网络环境"在 app.log 里有据可查，不必事后重猜。
    /// </summary>
    public static string DescribeSystemProxy()
    {
        try
        {
            using var key = Microsoft.Win32.Registry.CurrentUser.OpenSubKey(
                @"Software\Microsoft\Windows\CurrentVersion\Internet Settings");
            if (key is null) return "（读不到 Internet Settings）";

            var parts = new List<string>
            {
                "ProxyEnable=" + (key.GetValue("ProxyEnable")?.ToString() ?? "null"),
            };
            if (key.GetValue("ProxyServer") is { } server) parts.Add("ProxyServer=" + server);
            if (key.GetValue("AutoConfigURL") is { } pac) parts.Add("AutoConfigURL=" + pac);
            return string.Join("; ", parts);
        }
        catch (Exception e)
        {
            return "（读取失败: " + e.Message + "）";
        }
    }
}
