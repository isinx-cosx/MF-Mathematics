using System;
using System.Text.Json;

namespace MFMath.Host;

/// <summary>
/// PushBridge —— 暴露给 JS 的 `push` host object（诊断 + 自测 + 手动发一条）。
///
/// 为什么要把"发消息"也暴露出去：推送是**单向旁路**，出问题时最难回答的一句话是
/// "到底是宿主没发，还是页面没收到"。有了这个桥，设置面板里点一下"发一条测试消息"，
/// 就能同时看到宿主侧计数（Sent/Seq）与页面侧计数（src/lib/push.js 的 received），
/// 两边一比即可定位。自动化测试也是靠它做端到端断言（tests/cdp-push.mjs）。
///
/// 它不是业务入口：真正的推送由 PushHub.Send 在安装进度、控制台运行等真实场景里发出。
/// </summary>
public class PushBridge
{
    /// <summary>通道状态：连接与否、收发计数、最后一条的主题与错误</summary>
    public string Info()
    {
        return "{" +
               "\"ready\":" + (PushHub.Ready ? "true" : "false") +
               ",\"sent\":" + PushHub.Sent +
               ",\"failed\":" + PushHub.Failed +
               ",\"seq\":" + PushHub.Seq +
               ",\"attachedMs\":" + PushHub.AttachedAtMs +
               ",\"lastTopic\":" + PushHub.Str(PushHub.LastTopic) +
               ",\"lastError\":" + PushHub.Str(PushHub.LastError) +
               ",\"hostVersion\":" + PushHub.Str("push/1 (PostWebMessageAsJson)") +
               "}";
    }

    /// <summary>
    /// 发一条消息回页面（JS → 宿主 → JS 的往返）。
    /// `payloadJson` 必须是合法 JSON 文本；空字符串按 null 处理。
    /// 返回 {ok, seq} 或 {ok:false, error}。
    /// </summary>
    public string Emit(string topic, string? payloadJson)
    {
        string t = (topic ?? "").Trim();
        if (t.Length == 0) return "{\"ok\":false,\"error\":\"topic 不能为空\"}";
        if (t.Length > 120) return "{\"ok\":false,\"error\":\"topic 过长（上限 120 字符）\"}";

        string? payload = null;
        if (!string.IsNullOrWhiteSpace(payloadJson))
        {
            try
            {
                using var _ = JsonDocument.Parse(payloadJson);
                payload = payloadJson;
            }
            catch (JsonException e)
            {
                return "{\"ok\":false,\"error\":" + PushHub.Str("payload 不是合法 JSON：" + e.Message) + "}";
            }
        }

        bool ok = PushHub.Send(t, payload);
        return "{\"ok\":" + (ok ? "true" : "false") +
               ",\"seq\":" + PushHub.Seq +
               (ok ? "" : ",\"error\":" + PushHub.Str(PushHub.LastError)) + "}";
    }

    /// <summary>轻量存活探测（不产生消息）</summary>
    public bool Ready() => PushHub.Ready;
}
