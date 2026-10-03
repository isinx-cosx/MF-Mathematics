// AiConfig.cs — AI 配置的模型与落盘
//
// 一处**故意与既有约定不同**的地方，先写清楚：
//
// 其他设置（历史、工作区、计算与绘图偏好）都是"页面写好 JSON → sys.StoreWrite 落盘"，
// 因为那些内容页面本来就知道。**AI 配置不能这样**：它包含 API Key，而
// `sys.StoreWrite` 的入参来自渲染进程 —— 一旦这么走，密钥就必须先出现在页面里，
// 与"密钥不进渲染进程"直接冲突。
//
// 所以 AI 配置由**宿主自己**读写：页面只能通过 AiBridge 拿到**脱敏视图**
// （baseUrl / model / 有没有密钥），以及一个只写的 SetKey。文件仍在
// %LOCALAPPDATA%\MFMath\settings\ai.json（和别的设置文件同处一地，诊断包能一起带走），
// 但里面的 `apiKeyProtected` 是 DPAPI 密文，页面就算用 sys.StoreRead("ai") 读到全文也解不开。
using System;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace MFMath.Host;

internal sealed class AiConfig
{
    /// <summary>总开关。关闭时不发任何请求（界面上的 AI 入口仍然可见，只是点了会说明原因）</summary>
    public bool Enabled { get; set; }

    /// <summary>OpenAI 兼容端点。DeepSeek 用 https://api.deepseek.com/v1；本地 Ollama 用 http://127.0.0.1:11434/v1</summary>
    public string BaseUrl { get; set; } = "https://api.deepseek.com/v1";

    public string Model { get; set; } = "deepseek-chat";

    public double Temperature { get; set; } = 0.6;

    public int MaxTokens { get; set; } = 2048;

    /// <summary>请求 usage 尾包（stream_options.include_usage）。个别兼容网关会拒绝这个字段，关掉即可。</summary>
    public bool IncludeUsage { get; set; } = true;

    /// <summary>整轮请求的墙钟上限（秒）。超时按 error(timeout) 事件收尾，不留半死连接。</summary>
    public int TimeoutSec { get; set; } = 120;

    /// <summary>上下文窗口（token）。0 = 未知，按保守默认 32768 处理，并在界面上如实标注来源。</summary>
    public int ContextWindow { get; set; }

    /// <summary>
    /// 会话历史保留轮数（发给模型的上限）。这是一道**成本闸门**，
    /// 默认 6：够接着聊，又不至于每轮把整段对话重新计费。
    /// </summary>
    public int HistoryTurns { get; set; } = 6;

    /// <summary>
    /// 会把哪些内容发出去。**默认值就是隐私承诺**：
    /// 表达式与引擎结果默认开（否则 AI 看不到你在算什么，讲解质量很差），
    /// 历史与控制台代码默认关（那是用户的私人内容）。
    /// </summary>
    public bool SendExpr { get; set; } = true;
    public bool SendResult { get; set; } = true;
    public bool SendHistory { get; set; }

    /// <summary>控制台代码：默认关。那是用户的私人内容，只有明确打开才发。</summary>
    public bool SendCode { get; set; }

    /// <summary>
    /// 工具调用（function calling）：让 AI 能调本地 C++ 引擎真算。
    /// 默认**开** —— 计算必须发生在引擎里，而不是让模型心算。
    /// 关掉之后模型仍可回答，但数值只能靠它自己（那正是我们不想看到的）。
    /// 注意：工具结果要回传给模型，所以「发送引擎结果」关着时工具会被拒（见 lib/ai/tools.ts）。
    /// </summary>
    public bool ToolsEnabled { get; set; } = true;
    /// <summary>DPAPI 密文（base64）。**绝不出现在任何返回给页面的 JSON 里**。</summary>
    public string ApiKeyProtected { get; set; } = "";

    [JsonIgnore] public bool KeyLoadFailed { get; set; }

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.Never,
        // 文件名与字段名都用小驼峰：这是配置文件，用户可能会打开看，
        // 而且测试要断言"密钥以 apiKeyProtected 密文存在"——字段名不该由序列化器随手定成 PascalCase。
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        // 手改过大小写的文件也能读回来（配置文件是外部可编辑的）
        PropertyNameCaseInsensitive = true,
    };

    public static string Dir =>
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "MFMath", "settings");

    public static string FilePath => Path.Combine(Dir, "ai.json");

    public static AiConfig Load()
    {
        try
        {
            if (!File.Exists(FilePath)) return new AiConfig();
            string text = File.ReadAllText(FilePath, Encoding.UTF8);
            var cfg = JsonSerializer.Deserialize<AiConfig>(text, JsonOpts) ?? new AiConfig();
            return Normalize(cfg);
        }
        catch
        {
            // 配置坏了不能连累启动：按默认跑，并把"这份文件有问题"如实报给界面
            var cfg = new AiConfig();
            cfg.KeyLoadFailed = true;
            return cfg;
        }
    }

    /// <summary>把可疑取值收敛到安全范围（配置文件是外部可编辑的）</summary>
    public static AiConfig Normalize(AiConfig c)
    {
        if (string.IsNullOrWhiteSpace(c.BaseUrl)) c.BaseUrl = "https://api.deepseek.com/v1";
        c.BaseUrl = c.BaseUrl.Trim().TrimEnd('/');
        if (string.IsNullOrWhiteSpace(c.Model)) c.Model = "deepseek-chat";
        if (c.Temperature < 0 || c.Temperature > 2 || double.IsNaN(c.Temperature)) c.Temperature = 0.6;
        if (c.MaxTokens < 1) c.MaxTokens = 2048;
        if (c.MaxTokens > 32000) c.MaxTokens = 32000;
        if (c.TimeoutSec < 5) c.TimeoutSec = 5;
        if (c.TimeoutSec > 900) c.TimeoutSec = 900;
        if (c.ContextWindow < 0) c.ContextWindow = 0;
        if (c.ContextWindow > 4_000_000) c.ContextWindow = 4_000_000;
        if (c.HistoryTurns < 0) c.HistoryTurns = 0;
        if (c.HistoryTurns > 50) c.HistoryTurns = 50;
        return c;
    }

    /// <summary>原子落盘：先写 .tmp，再 File.Replace（同时留 .bak）。半途崩溃不会留下半截 JSON。</summary>
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
            else
            {
                File.Move(tmp, FilePath);
            }
            return true;
        }
        catch (Exception e)
        {
            error = e.Message;
            return false;
        }
    }
}
