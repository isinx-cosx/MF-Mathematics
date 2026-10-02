// AiSse.cs — SSE 分帧（纯函数，不碰网络，可单独测）
//
// 这一层的全部难点只有一句：**一个 TCP chunk 不等于一个 SSE 事件。**
// `data: {...}` 可能被切成两半跨 chunk，一个 chunk 里也可能塞了三个事件；
// 直接对每个 chunk 做 JSON.Parse 是最常见的崩法。
//
// 除了缓冲跨 chunk，还有四个容易漏的规范细节（都会在真实端点上偶发）：
//   ① 行分隔符有 \n / \r\n / \r 三种；**末尾孤立的 \r 必须留到下一个 chunk**
//      ——因为那可能是被切断的 CRLF 的前半截；
//   ② `data:` 后面**只去掉一个空格**，多余的空格属于数据；
//   ③ 以冒号开头的是注释（常用于心跳保活），必须跳过；
//   ④ 一个块里多个 `data:` 行要按规范用 \n 连接。
// 另外 `[DONE]` 不是 JSON：调用方必须在 JSON.Parse 之前把它拦掉（见 AiClient）。
//
// 多字节 UTF-8 跨 chunk 由调用方用**有状态的 Decoder** 处理（Encoding.UTF8.GetDecoder()），
// 这里只处理已经解码成字符的文本。
using System;
using System.Collections.Generic;
using System.Text;

namespace MFMath.Host;

/// <summary>一个 SSE 事件：event 名（可为空）与 data（多行用 \n 连接后的结果）</summary>
internal readonly struct AiSseEvent
{
    public readonly string Name;
    public readonly string Data;
    public AiSseEvent(string name, string data) { Name = name; Data = data; }
}

internal sealed class AiSseParser
{
    private readonly StringBuilder _buffer = new();

    /// <summary>行尾归一化。末尾孤立的 \r 保留不动，等下一个 chunk 拼上再说。</summary>
    internal static string NormalizeNewlines(string buffer)
    {
        string crlf = buffer.Replace("\r\n", "\n");
        if (crlf.EndsWith("\r", StringComparison.Ordinal))
            return crlf.Substring(0, crlf.Length - 1).Replace("\r", "\n") + "\r";
        return crlf.Replace("\r", "\n");
    }

    /// <summary>解析一个事件块（已被空行分隔）。返回 null 表示块里没有任何有效字段。</summary>
    internal static AiSseEvent? ParseBlock(string block)
    {
        string name = "";
        var dataLines = new List<string>();

        foreach (string rawLine in block.Split('\n'))
        {
            string line = rawLine;
            if (line.Length == 0) continue;
            if (line[0] == ':') continue;              // 注释 / 心跳

            int colon = line.IndexOf(':');
            string field = colon < 0 ? line : line.Substring(0, colon);
            string value = colon < 0 ? "" : line.Substring(colon + 1);
            if (value.StartsWith(" ", StringComparison.Ordinal)) value = value.Substring(1);  // 只去一个空格

            if (field == "event") name = value;
            else if (field == "data") dataLines.Add(value);
        }

        if (dataLines.Count == 0 && name.Length == 0) return null;
        return new AiSseEvent(name, string.Join("\n", dataLines));
    }

    /// <summary>喂一段新到的文本，吐出这次能完整切出来的事件。</summary>
    public List<AiSseEvent> Feed(string chunk)
    {
        var result = new List<AiSseEvent>();
        if (!string.IsNullOrEmpty(chunk)) _buffer.Append(chunk);

        string normalized = NormalizeNewlines(_buffer.ToString());
        _buffer.Clear();
        _buffer.Append(normalized);

        string text = _buffer.ToString();
        int cursor = 0;
        while (true)
        {
            int boundary = text.IndexOf("\n\n", cursor, StringComparison.Ordinal);
            if (boundary < 0) break;
            var ev = ParseBlock(text.Substring(cursor, boundary - cursor));
            if (ev.HasValue) result.Add(ev.Value);
            cursor = boundary + 2;
        }
        if (cursor > 0)
        {
            _buffer.Clear();
            _buffer.Append(text.Substring(cursor));
        }
        return result;
    }

    /// <summary>流结束时调用：末尾没有空行收尾的最后一个事件仍要发出去。</summary>
    public AiSseEvent? Flush()
    {
        string remaining = NormalizeNewlines(_buffer.ToString());
        _buffer.Clear();
        if (remaining.Length == 0) return null;
        return ParseBlock(remaining);
    }
}
