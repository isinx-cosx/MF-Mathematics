//! ai.rs —— AI 助手桥 + SSE 中继（对照 C# `AiBridge.cs` / `AiClient.cs` / `AiConfig.cs` /
//! `AiRelay.cs`；JS 侧是 `hostObjects.sync.ai`）
//!
//! ## 分工（这次改动的核心，C# 注释里的取舍一条不落）
//!   · **宿主 = 凭据 + 网络**：它保管密钥、发请求、把响应**原始字节**转回去。
//!     它**不理解** SSE，也不理解 OpenAI 的分片语义 —— 那部分在 TS 里，只有一份实现
//!     （`MF_UI/MFMath.UI.Vue/src/lib/ai/{sse,client,collect}.ts`，移植自 MVS Agent 的 `src/model/`）。
//!   · **页面 = 协议 + 组装 + 渲染**：SSE 分帧、usage 尾包、reasoning_content、`[DONE]`、
//!     降级通知、消息组装与隐私开关，全在 TS 那一侧。
//!   · **计算** 仍然全在 C++ 引擎：AI 只解释，结果区永远显示引擎值（`tests/cdp-ai.mjs` 有断言守着）。
//!
//! 这样切的理由（C# `AiClient.cs` 文件头原话）：SSE 分帧与错误分类**只该有一份实现**。
//! 两边各写一套的后果正是"一直在线的界面和刚刷新的界面显示不同的东西"；而 TS 是允许的语言
//! —— 本项目的硬约束是"计算在 C++"，不是"界面只能写 JS"。
//!
//! ## 为什么密钥不放渲染进程
//! 页面直连就得自己持有 API Key（localStorage / 内存），而本项目已经有渲染进程注入面的
//! 现实案例（教程富文本清洗那个绕过）。所以对外只有 `hasKey` / `keySource` / `keyPersisted`，
//! **密钥本身一步都不出宿主** —— 连 `ai.json` 里放的都是 DPAPI 密文（见 `dpapi.rs`）。
//!
//! ## 安全边界：中继不是"替我发一次任意请求"的原语
//! 如果允许页面传**绝对 URL**，它就变成"把密钥发到任意地址"—— 页面里一段注入脚本就能把
//! key 骗走。所以 `validate_path` 只接受以单个 `/` 开头的路径（`//host` 这种协议相对地址、
//! 带 `..` 的穿越、带换行的注入一律拒绝）；端点来自宿主自己的配置（`ai.json` 的 `baseUrl`），
//! 页面**无从指定**；`Authorization` 由这里加，页面传的任何头都不会被转发。
//! ⚠ **不要**放宽这道闸门 —— `SelfCheck()` 里专门有一项在验它（拒绝绝对地址 / 协议相对地址 / `..`）。
//!
//! ## ⚠ 为什么**不**把端点交给 `site::normalize_base_url`
//! `site.rs` 的规范化在遇到不认识的值时会**退回内置站点**（`https://mf-vis-science.cn`）。
//! 那对账号/搜索是对的（端点是固定的），但对 AI 是**事故**：`baseUrl` 是用户自己填的，
//! 一旦填得怪一点，用户的 API Key 就会被发到我们自己的服务器上。
//! C# `AiClient.JoinUrl` 的规则只有一句 `baseUrl.TrimEnd('/') + path`，这里逐字照做，
//! 并且只在**错误文案**上复用 `site::detail_of` / `site::json_str`（纯函数，无副作用）。
//! 同理不用 `site::post`：它先查 `site::is_cancelled()`（那是账号/搜索共用的全局闸门，
//! 别人一次 CancelAll 之后 AI 会一路报"已取消"却根本没出网），而且它不流式。
//!
//! ## 流式增量怎么切分：宿主**不切**
//! SSE 的 `data:` 行、`[DONE]`、半行缓冲全是 TS 的事（`sse.ts` 里那份唯一的实现）。
//! 宿主只保证**字节顺序**与**完整性**：每读到一块就原样 base64 推一次（`ai.raw`），
//! **不做合并** —— 合并会让最后一个事件卡在缓冲里，界面看起来"卡住不动了"。
//! ⚠ C# 那段 `carry` 缓冲是**不可达的死代码**（它建了却从未被写入，`carry.Length` 恒为 0），
//! 所以这里直接实现"每块一推"：行为与 C# **实际跑出来**的一致，还少一段误导人的代码。
//!
//! ## 取消与超时：两个来源分开，收尾时才能说清是谁取消的
//!   · **取消** = 用户点"停止" / 窗口关闭（`Cancel` / `CancelAll` → 取消标记）；
//!   · **超时** = 整轮请求的墙钟上限（`timeoutSec`，默认 120 s，界面可调）。
//! blocking 的 reqwest **没有中断句柄**，所以这里的语义与 `jobs.rs` / `search.rs` 一致：
//! **"停止等待"而不是"假装杀干净"** —— 取消标记置位后，读循环在下一块数据到齐时收尾；
//! 而"卡死的读"由 reqwest blocking 自带的超时兜底：它的 `Client::timeout` 对响应体是
//! **逐次 read** 生效的（`blocking/response.rs:439` 每次 read 都 `wait::timeout(…, self.timeout)`），
//! 正好是这里需要的"读不动就别等死"。另外每收下一块再比一次总预算，把 C# 的
//! `CancellationTokenSource(TimeoutSec)` 那份**整轮**上限也保住。
//!
//! ## 断线 / 超时 / 非 200 的分类
//!   · **非 2xx 不是中继的错误**：状态行先经 `ai.http` 推回，字节照发 —— 由 TS 决定
//!     "这是 http 错误"（它要拿状态码与错误体拼文案，`client.ts` 的 `response.status` 分支）。
//!   · `timeout` 与 `aborted` 分开推；`network` 表示"流吐了一半之后连接被掐断"，
//!     **含义是"重试可能成功"**；`protocol` 留给"端点回了看不懂的东西"。
//!
//! ## 桥面（11 个方法，与前端 `lib/ai/{bridge.js,relay.ts}` 的调用点一一对应）
//! `Info() Busy() KeySource() Configure(json) SetKey(key) ClearKey() Test()
//!  Begin(json) Cancel(id) CancelAll() SelfCheck()`
//!
//! ⚠ **不进渲染进程的东西**：密钥明文、DPAPI 密文、以及"用户问了什么"
//! （prompt 与请求体一概不写日志；日志里只有"发往哪个 origin"）。

use std::io::Read;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, AtomicI64, Ordering};
use std::sync::{Arc, Mutex, OnceLock};
use std::time::{Duration, Instant};

use base64::engine::general_purpose::STANDARD as B64;
use base64::Engine;
use serde::{Deserialize, Serialize};
use serde_json::{json, Map, Value};

use crate::{dpapi, http, logging, push, site, sys};

/* ══════════════════════════════════════════════════════════════════════════
 * ① 出参形状：**手拼 JSON**（保序）
 *
 * 为什么不用 `serde_json::json!`：本仓库没有开 `serde_json/preserve_order`
 * （Cargo.lock 里 serde_json 的依赖只有 itoa/memchr/serde/serde_core/zmij，没有 indexmap），
 * 于是 `serde_json::Map` 是 `BTreeMap` —— 键会被**按字典序重排**。
 * 而端到端用例断言的正是相邻形状：`"name":"中继路径闸门（拒绝绝对地址）","ok":true`
 * 与 `"hasKey":true` 这类；一旦重排就永远匹配不上。
 * C# 那边也是用 StringBuilder 手拼的（`PushHub.Str` + `Append`），这里与它保持一致。
 * 只对**推送负载**用 `json!`：前端是按属性名取的，顺序无所谓。
 * ══════════════════════════════════════════════════════════════════════════ */

/// 按 JSON 字符串规则转义并带引号（等价 C# 的 `PushHub.Str`）。
/// 交给 serde_json 做转义，省得自己维护一张转义表。
fn jstr(s: &str) -> String {
    Value::String(s.to_string()).to_string()
}

/// C# 的 `v.ToString("0.####", InvariantCulture)`：最多 4 位小数、无千分位、无科学计数
fn num_text(v: f64) -> String {
    let r = (v * 10_000.0).round() / 10_000.0;
    if r == 0.0 {
        // 顺手把 `-0` 归一成 `0`（C# 会打出 "-0"，那是它的小毛病，不值得照抄）
        return "0".to_string();
    }
    format!("{r}")
}

struct JsonOut {
    buf: String,
    first: bool,
}

impl JsonOut {
    fn new() -> Self {
        JsonOut { buf: String::from("{"), first: true }
    }
    fn key(&mut self, k: &str) {
        if !self.first {
            self.buf.push(',');
        }
        self.first = false;
        self.buf.push_str(&jstr(k));
        self.buf.push(':');
    }
    /// 字符串值
    fn s(&mut self, k: &str, v: &str) -> &mut Self {
        self.key(k);
        self.buf.push_str(&jstr(v));
        self
    }
    /// 已是 JSON 片段的值
    fn raw(&mut self, k: &str, v: &str) -> &mut Self {
        self.key(k);
        self.buf.push_str(v);
        self
    }
    fn b(&mut self, k: &str, v: bool) -> &mut Self {
        self.raw(k, if v { "true" } else { "false" })
    }
    fn i(&mut self, k: &str, v: i64) -> &mut Self {
        self.raw(k, &v.to_string())
    }
    fn f(&mut self, k: &str, v: f64) -> &mut Self {
        self.raw(k, &num_text(v))
    }
    fn done(mut self) -> String {
        self.buf.push('}');
        self.buf
    }
}

/// C# `AiBridge.Fail`
fn fail(message: &str) -> String {
    let mut o = JsonOut::new();
    o.b("ok", false).s("error", message);
    o.done()
}

/// `{"ok":false,"kind":…,"error":…}`（`Begin` 的失败信封，前端按 `kind` 决定怎么提示）
fn fail_kind(kind: &str, message: &str) -> String {
    let mut o = JsonOut::new();
    o.b("ok", false).s("kind", kind).s("error", message);
    o.done()
}

/// 让 `_lastError` 与返回信封同步（C# 在 `Begin` 失败时就是这么写的）。
fn last_error_fail_kind(kind: &str, message: &str) -> String {
    set_last_error(&format!("{kind}: {message}"));
    fail_kind(kind, message)
}

/// C# `AiClient.Truncate`：超长加省略号（按**字符**切，不切坏码点）
fn truncate(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        s.to_string()
    } else {
        format!("{}…", s.chars().take(max).collect::<String>())
    }
}

/* ══════════════════════════════════════════════════════════════════════════
 * ② 配置（`%LOCALAPPDATA%\MFMath\settings\ai.json`）
 *
 * 一处**故意与既有约定不同**的地方（C# `AiConfig.cs` 开头那段，照搬）：
 * 其他设置都是"页面写好 JSON → `sys.StoreWrite` 落盘"，因为那些内容页面本来就知道。
 * **AI 配置不能这样**：它包含 API Key，而 `StoreWrite` 的入参来自渲染进程 ——
 * 一旦这么走，密钥就必须先出现在页面里，与"密钥不进渲染进程"直接冲突。
 * 所以 AI 配置由**宿主自己**读写：页面只能拿到**脱敏视图** + 一个只写的 `SetKey`。
 *
 * 文件仍在 `%LOCALAPPDATA%\MFMath\settings\ai.json`（和别的设置文件同处一地，
 * 诊断包能一起带走 —— 但诊断导出会**跳过** ai.json，见 `sys.rs` 的凭据名单），
 * 里面的 `apiKeyProtected` 是 DPAPI 密文，页面就算用 `sys.StoreRead("ai")` 读到全文也解不开。
 * ⚠ 落盘走 `sys::store_write`（不是自己开文件）：那条路已经带上了 `.bak` 备份 + 临时文件
 * + 原子替换，配置写一半崩掉不会留下半截 JSON；字段名与 C# 逐字一致，迁移期两个宿主
 * 共用同一份文件。
 * ══════════════════════════════════════════════════════════════════════════ */

const CONFIG_STEM: &str = "ai";

/// DeepSeek 的官方端点（本地 Ollama 用 `http://127.0.0.1:11434/v1`）
const DEFAULT_BASE_URL: &str = "https://api.deepseek.com/v1";
const DEFAULT_MODEL: &str = "deepseek-chat";
const DEFAULT_TEMPERATURE: f64 = 0.6;
const DEFAULT_MAX_TOKENS: i64 = 2048;
const DEFAULT_TIMEOUT_SEC: i64 = 120;
const DEFAULT_HISTORY_TURNS: i64 = 6;

/// C# `AiClient.CreateClient` 里的 User-Agent，**逐字一致**。
/// 有些网关按 UA 做策略，迁移期两个宿主的行为要能对上，所以不省这一句。
const AI_UA: &str = "MFMath-Host/2.0";

fn def_base_url() -> String {
    DEFAULT_BASE_URL.to_string()
}
fn def_model() -> String {
    DEFAULT_MODEL.to_string()
}
fn def_temperature() -> f64 {
    DEFAULT_TEMPERATURE
}
fn def_max_tokens() -> i64 {
    DEFAULT_MAX_TOKENS
}
fn def_timeout_sec() -> i64 {
    DEFAULT_TIMEOUT_SEC
}
fn def_history_turns() -> i64 {
    DEFAULT_HISTORY_TURNS
}
/// 默认**开**的那几个开关（includeUsage / sendExpr / sendResult / toolsEnabled）
fn def_true() -> bool {
    true
}

/// AI 配置。字段名与 C# `AiConfig` 的 camelCase 一致 —— 迁移期两个宿主共用同一份文件。
#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AiConfig {
    /// 总开关。关闭时不发任何请求（界面上的 AI 入口仍然可见，只是点了会说明原因）
    #[serde(default, alias = "Enabled")]
    pub enabled: bool,

    /// OpenAI 兼容端点（DeepSeek / OpenAI / Moonshot / 硅基流动 / Ollama / vLLM 共用形状）。
    /// ⚠ 用户可配 = "密钥会发到哪儿"这个闸门在这里，见文件头那段说明。
    #[serde(default = "def_base_url", alias = "BaseUrl")]
    pub base_url: String,

    #[serde(default = "def_model", alias = "Model")]
    pub model: String,

    #[serde(default = "def_temperature", alias = "Temperature")]
    pub temperature: f64,

    #[serde(default = "def_max_tokens", alias = "MaxTokens")]
    pub max_tokens: i64,

    /// 请求 usage 尾包（`stream_options.include_usage`）。
    /// 个别兼容网关会拒绝这个字段，关掉即可 —— 缺失不是错误，TS 会降级成 missing_usage 通知。
    #[serde(default = "def_true", alias = "IncludeUsage")]
    pub include_usage: bool,

    /// 整轮请求的墙钟上限（秒）。超时按 error(timeout) 事件收尾，不留半死连接。
    #[serde(default = "def_timeout_sec", alias = "TimeoutSec")]
    pub timeout_sec: i64,

    /// 上下文窗口（token）。0 = 未知，按保守默认 32768 处理，并在界面上如实标注来源
    /// （这一段估算在 `bridge.js` 的 `contextBudget` 里，宿主只负责把它存下来）。
    #[serde(default, alias = "ContextWindow")]
    pub context_window: i64,

    /// 会话历史保留轮数（发给模型的上限）。这是一道**成本闸门**：
    /// 默认 6 —— 够接着聊，又不至于每轮把整段对话重新计费。
    /// ⚠ 语义是"最多带 N 轮"，**0 = 一条历史都不带**（不是"带全部"）。
    #[serde(default = "def_history_turns", alias = "HistoryTurns")]
    pub history_turns: i64,

    /// 会把哪些内容发出去。**默认值就是隐私承诺**：
    /// 表达式与引擎结果默认开（否则 AI 看不到你在算什么，讲解质量很差），
    /// 历史与控制台代码默认关（那是用户的私人内容）。
    #[serde(default = "def_true", alias = "SendExpr")]
    pub send_expr: bool,
    #[serde(default = "def_true", alias = "SendResult")]
    pub send_result: bool,
    #[serde(default, alias = "SendHistory")]
    pub send_history: bool,

    /// 控制台代码：默认关。那是用户的私人内容，只有明确打开才发。
    #[serde(default, alias = "SendCode")]
    pub send_code: bool,

    /// 工具调用（function calling）：让 AI 能调本地 C++ 引擎真算。
    /// 默认**开** —— 计算必须发生在引擎里，而不是让模型心算。
    /// 关掉之后模型仍可回答，但数值只能靠它自己（那正是我们不想看到的）。
    /// 注意：工具结果要回传给模型，所以「发送引擎结果」关着时工具会被拒（见 `lib/ai/tools.ts`）。
    ///
    /// ⚠ 这个字段以前界面发它、宿主既不读也不返回 —— 于是 `refreshAiConfig` 的
    /// `{...DEFAULT_CFG, ...info}` 合并让它恒为 true，用户关掉后看到"已保存"、实际关不掉。
    /// 现在读写都通了。
    #[serde(default = "def_true", alias = "ToolsEnabled")]
    pub tools_enabled: bool,

    /// DPAPI 密文（base64）。**绝不出现在任何返回给页面的 JSON 里**。
    #[serde(default, alias = "ApiKeyProtected")]
    pub api_key_protected: String,

    /// 配置文件坏掉时置位（**只报给界面，不落盘**）：坏文件按默认跑，但要如实说
    #[serde(skip)]
    pub load_failed: bool,
}

impl Default for AiConfig {
    fn default() -> Self {
        AiConfig {
            enabled: false,
            base_url: def_base_url(),
            model: def_model(),
            temperature: def_temperature(),
            max_tokens: def_max_tokens(),
            include_usage: true,
            timeout_sec: def_timeout_sec(),
            context_window: 0,
            history_turns: def_history_turns(),
            send_expr: true,
            send_result: true,
            send_history: false,
            send_code: false,
            tools_enabled: true,
            api_key_protected: String::new(),
            load_failed: false,
        }
    }
}

impl AiConfig {
    /// 把可疑取值收敛到安全范围（配置文件是外部可编辑的）。逐条对照 C# `AiConfig.Normalize`。
    pub fn normalize(&mut self) {
        if self.base_url.trim().is_empty() {
            self.base_url = def_base_url();
        }
        self.base_url = self.base_url.trim().trim_end_matches('/').to_string();
        if self.model.trim().is_empty() {
            self.model = def_model();
        }
        // `!(0.0 <= t <= 2.0)` 把 NaN 也一并收进来（与 C# 的 `double.IsNaN` 判据等价）
        if !(self.temperature >= 0.0 && self.temperature <= 2.0) {
            self.temperature = DEFAULT_TEMPERATURE;
        }
        if self.max_tokens < 1 {
            self.max_tokens = DEFAULT_MAX_TOKENS;
        }
        if self.max_tokens > 32_000 {
            self.max_tokens = 32_000;
        }
        if self.timeout_sec < 5 {
            self.timeout_sec = 5;
        }
        if self.timeout_sec > 900 {
            self.timeout_sec = 900;
        }
        if self.context_window < 0 {
            self.context_window = 0;
        }
        if self.context_window > 4_000_000 {
            self.context_window = 4_000_000;
        }
        if self.history_turns < 0 {
            self.history_turns = 0;
        }
        if self.history_turns > 50 {
            self.history_turns = 50;
        }
    }

    /// 从设置文件读；文件不存在用默认值（**离线也要能起来**）。
    /// 文件在但读不出来 → 默认值 + `load_failed`，让设置面板能说实话。
    fn load() -> Self {
        if !config_path().is_file() {
            return AiConfig::default();
        }
        match sys::store_read_value(CONFIG_STEM) {
            Some(v) => match serde_json::from_value::<AiConfig>(v) {
                Ok(mut c) => {
                    c.normalize();
                    c
                }
                Err(_) => {
                    // 配置坏了不能连累启动：按默认跑，并把"这份文件有问题"如实报给界面
                    let mut c = AiConfig::default();
                    c.load_failed = true;
                    c
                }
            },
            None => {
                let mut c = AiConfig::default();
                c.load_failed = true;
                c
            }
        }
    }

    fn save(&self) -> Result<(), String> {
        let text = serde_json::to_string_pretty(self).map_err(|e| e.to_string())?;
        let r = sys::store_write(CONFIG_STEM, &text);
        let v: Value = serde_json::from_str(&r).unwrap_or(Value::Null);
        if v.get("ok").and_then(|b| b.as_bool()).unwrap_or(false) {
            Ok(())
        } else {
            Err(v.get("error").and_then(|s| s.as_str()).unwrap_or("写入配置失败").to_string())
        }
    }
}

/// `%LOCALAPPDATA%\MFMath\settings`（与 `sys.rs` 的 `settings_dir` 同一处）
fn config_dir() -> PathBuf {
    logging::data_dir().join("settings")
}

/// `%LOCALAPPDATA%\MFMath\settings\ai.json`
fn config_path() -> PathBuf {
    config_dir().join("ai.json")
}

static CFG: OnceLock<Mutex<AiConfig>> = OnceLock::new();

fn cfg_slot() -> &'static Mutex<AiConfig> {
    CFG.get_or_init(|| Mutex::new(AiConfig::load()))
}

fn cfg() -> AiConfig {
    cfg_slot().lock().map(|c| c.clone()).unwrap_or_default()
}

fn with_cfg<R>(f: impl FnOnce(&mut AiConfig) -> R) -> R {
    let mut g = cfg_slot().lock().unwrap_or_else(|e| e.into_inner());
    f(&mut g)
}

/* ══════════════════════════════════════════════════════════════════════════
 * ③ 密钥与进程内状态
 * ══════════════════════════════════════════════════════════════════════════ */

/// DPAPI 不可用时的兜底：密钥只留在内存，重启后需要重填（**绝不写明文到磁盘**）
static MEMORY_KEY: Mutex<String> = Mutex::new(String::new());
static LAST_ERROR: Mutex<String> = Mutex::new(String::new());

fn set_last_error(s: &str) {
    if let Ok(mut g) = LAST_ERROR.lock() {
        *g = s.to_string();
    }
}

fn last_error() -> String {
    LAST_ERROR.lock().map(|g| g.clone()).unwrap_or_default()
}

fn memory_key() -> String {
    MEMORY_KEY.lock().map(|g| g.clone()).unwrap_or_default()
}

/// 密钥从哪来（供设置面板显示，**不返回密钥内容**）
pub fn key_source() -> &'static str {
    if !memory_key().is_empty() {
        "memory"
    } else if !cfg().api_key_protected.is_empty() {
        "dpapi"
    } else {
        "none"
    }
}

/// 取明文密钥：内存优先，其次解 DPAPI 密文（换了 Windows 用户/文件被改都会解不出来）
fn resolve_key() -> String {
    let mem = memory_key();
    if !mem.is_empty() {
        return mem;
    }
    let c = cfg();
    if c.api_key_protected.is_empty() {
        return String::new();
    }
    dpapi::unprotect(&c.api_key_protected).unwrap_or_default()
}

/* ══════════════════════════════════════════════════════════════════════════
 * ④ 中继的作业表
 *
 * 一个"作业"= 一次 `Begin` 起的流。C# 用 `ConcurrentDictionary<string, RelayTurn>`，
 * 这里用 `Mutex<Vec<Turn>>` + `Arc<AtomicBool>`（与 `search.rs` 同一套写法）。
 *
 * ⚠ 与 C# 的一处有意差异：C# 的 `Turns` **只增不减**（一次会话里每个请求都留一条），
 * 这是内存泄漏；`relay.ts` 里那个 MAX_ORPHANS 注释记的就是同一类问题。
 * 这里保留最近 `MAX_TURNS` 条（**运行中的一条都不丢**），足够让"流结束后前端补的那次
 * `ai.Cancel(id)`"仍能命中，又不会无限增长。
 * ══════════════════════════════════════════════════════════════════════════ */

struct Turn {
    id: String,
    /// 这一轮的取消标记（用户点停止 / 窗口关闭）
    cancelled: Arc<AtomicBool>,
    running: AtomicBool,
}

const MAX_TURNS: usize = 64;

static TURNS: Mutex<Vec<Turn>> = Mutex::new(Vec::new());
static SEQ: AtomicI64 = AtomicI64::new(0);

fn running_count() -> usize {
    TURNS.lock().map(|g| g.iter().filter(|t| t.running.load(Ordering::SeqCst)).count()).unwrap_or(0)
}

fn register_turn(id: &str, cancelled: Arc<AtomicBool>) {
    let mut g = TURNS.lock().unwrap_or_else(|e| e.into_inner());
    g.push(Turn { id: id.to_string(), cancelled, running: AtomicBool::new(true) });
    if g.len() > MAX_TURNS {
        // 先丢"已结束里最旧的"，运行中的一个都不动（边删边比长度会算错，先算再删）
        let over = g.len() - MAX_TURNS;
        let mut dropped = 0usize;
        let mut kept: Vec<Turn> = Vec::with_capacity(g.len());
        for t in g.drain(..) {
            if dropped < over && !t.running.load(Ordering::SeqCst) {
                dropped += 1;
                continue;
            }
            kept.push(t);
        }
        *g = kept;
    }
}

fn finish_turn(id: &str) {
    let mut g = TURNS.lock().unwrap_or_else(|e| e.into_inner());
    for t in g.iter_mut() {
        if t.id == id {
            t.running.store(false, Ordering::SeqCst);
            break;
        }
    }
}

/* ══════════════════════════════════════════════════════════════════════════
 * ⑤ 路径闸门（防"密钥被发到任意地址"的那道闸）
 * ══════════════════════════════════════════════════════════════════════════ */

/// 路径校验：必须是以单个 `/` 开头的相对路径。**不要放宽它**。
/// 逐条对照 C# `AiRelay.ValidatePath`（含判定顺序与文案）。
pub fn validate_path(path: &str) -> Result<(), String> {
    if path.trim().is_empty() {
        return Err("路径为空".into());
    }
    let p = path.trim();
    if !p.starts_with('/') {
        return Err("只接受相对路径（如 /chat/completions）；不接收绝对地址".into());
    }
    if p.len() > 1 && p.as_bytes()[1] == b'/' {
        return Err("拒绝协议相对地址（//host）".into());
    }
    if p.contains("://") {
        return Err("路径里不允许出现协议头".into());
    }
    if p.contains("..") {
        return Err("路径里不允许出现 ..".into());
    }
    if p.contains('\n') || p.contains('\r') {
        return Err("路径里不允许换行".into());
    }
    Ok(())
}

/// 端点拼接：与 C# `AiClient.JoinUrl` 逐字一致（`baseUrl.TrimEnd('/') + path`）。
/// **不做**站点默认地址兜底 —— 见文件头那段说明（那会把密钥发到不相干的地方）。
fn join_url(base_url: &str, path: &str) -> String {
    format!("{}{}", base_url.trim_end_matches('/'), path)
}

/// 自检用：字节经 base64 转手是否无损（响应体就是这么过推送的）
fn base64_round_trip() -> bool {
    const PROBE: [u8; 11] = [0, 1, 2, 127, 128, 255, 10, 13, 0xE4, 0xB8, 0xAD];
    matches!(B64.decode(B64.encode(PROBE)), Ok(v) if v == PROBE)
}

/* ══════════════════════════════════════════════════════════════════════════
 * ⑥ 推送（ai.http · ai.raw · ai.rawEnd · ai.rawError · ai.test）
 *
 * 这些负载是按属性名取的，用 `json!` 就行（顺序无关）。
 * ⚠ 所有推送都**绝不**包含密钥、prompt 或响应正文的明文 —— 正文只以 base64 走。
 * ══════════════════════════════════════════════════════════════════════════ */

/// 状态行先推：TS 那边要靠它区分 2xx 与错误体（`relay.ts` 会等这条才继续）
fn push_http(id: &str, status: i32, status_text: &str) {
    let payload = json!({ "requestId": id, "status": status, "statusText": status_text });
    push::send("ai.http", &payload.to_string());
}

fn push_chunk(id: &str, chunk: &[u8]) {
    let payload = json!({ "requestId": id, "b64": B64.encode(chunk) });
    push::send("ai.raw", &payload.to_string());
}

fn push_raw_end(id: &str, bytes: u64) {
    let payload = json!({ "requestId": id, "bytes": bytes });
    push::send("ai.rawEnd", &payload.to_string());
}

fn push_error(id: &str, kind: &str, message: &str) {
    let payload = json!({ "requestId": id, "kind": kind, "status": 0, "message": message });
    push::send("ai.rawError", &payload.to_string());
}

/* ══════════════════════════════════════════════════════════════════════════
 * ⑦ 中继本体
 * ══════════════════════════════════════════════════════════════════════════ */

/// blocking 的 `Read` 出错时，超时是这样包进来的：
/// `io::Error::new(ErrorKind::Other, reqwest::Error{ kind: Decode, source: TimedOut })`
/// （`blocking/response.rs:441` → `error.rs:192`）。
/// 所以先看 io 的 kind，再把内层 downcast 回 `reqwest::Error` 问 `is_timeout()`。
fn io_is_timeout(e: &std::io::Error) -> bool {
    if e.kind() == std::io::ErrorKind::TimedOut {
        return true;
    }
    let Some(inner) = e.get_ref() else { return false };
    let inner: &(dyn std::error::Error + 'static) = inner;
    matches!(inner.downcast_ref::<reqwest::Error>(), Some(re) if re.is_timeout())
}

/// "本轮超过设定的超时时间"（与 C# 同一句文案，界面直接显示）
const TIMEOUT_MESSAGE: &str = "本轮超过设定的超时时间（可在设置 → AI 里调整）";

/// 发起一次中继：带宿主的密钥请求，把响应**原始字节**依次推回页面。
///
/// 形状与 C# `AiRelay.PumpAsync` 逐条对齐：
///   ① 发请求（`Authorization` 在这里加）→ ② 收到头就推 `ai.http`
///   → ③ 每读到一块推 `ai.raw`（base64，**不分帧**）→ ④ 读到 EOF 推 `ai.rawEnd`
///   任何失败路径推 `ai.rawError`，**不推** `ai.rawEnd`（TS 靠这个区分"正常结束"与"出事"）。
fn pump(c: &AiConfig, api_key: &str, id: &str, path: &str, body: &str, cancelled: &AtomicBool) {
    let url = join_url(&c.base_url, path);

    /* 只记"发往哪个来源"（scheme://host，不含路径与查询串），**不记 prompt / 请求体**：
     * 后者属于用户，不该被诊断包带走。这一行是给"密钥到底会被发去哪儿"留证据的。 */
    logging::info(&format!("ai.Begin {id} origin={} path={path}", http::origin_of(&url)));

    /* ⚠ 客户端要**活到读循环结束**：blocking 的 `Response` 读体时用的就是它带来的那份
     * 超时（逐次 read 生效），把它提前 drop 掉虽然不会立刻出错，但读循环依赖的是
     * `Response` 自己持有的副本 —— 为了不让后来改这块的人踩坑，这里显式绑定住。 */
    let client = http::client_with_timeout_ua(c.timeout_sec, Some(AI_UA));
    let req = client
        .post(&url)
        .header("Content-Type", "application/json")
        .header("Accept", "text/event-stream")
        /* ⚠ C# 的原话是「SSE 不压缩，别乱加 Accept-Encoding」（`DecompressionMethods.None`），
         * 这里必须显式做同一件事：本仓库给 reqwest 开了 gzip/brotli，reqwest 会在请求头里
         * **没有** `Accept-Encoding` 时自动补一个 `gzip`（tower-http 的
         * `decompression/service.rs:116` 判的是 `Entry::Vacant`），于是端点可能**压着**
         * 这条流发 —— 压缩层要攒够一块才吐，增量推送就会顿住，界面看起来"卡住不动了"。
         * 写死 `identity` 正好把自动补头挡在外面。
         * 万一端点仍然压着发：reqwest 的解压层会透明解开，不会把 gzip 字节直接丢给 TS。 */
        .header("Accept-Encoding", "identity")
        .header("Authorization", format!("Bearer {api_key}"))
        .body(body.to_string());

    let mut resp = match req.send() {
        Ok(r) => r,
        Err(e) => {
            // 连接都没起来：状态行不存在，TS 那边靠 rawError 唤醒等待者（`relay.ts` 的 onAbort 同理）
            let kind = if e.is_timeout() { "timeout" } else { "network" };
            let msg = if kind == "timeout" { TIMEOUT_MESSAGE.to_string() } else { e.to_string() };
            push_error(id, kind, &msg);
            return;
        }
    };

    let status = resp.status().as_u16() as i32;
    let status_text = resp.status().canonical_reason().unwrap_or("");
    push_http(id, status, status_text);

    let started = Instant::now();
    let budget = Duration::from_secs(c.timeout_sec.max(1) as u64);
    let mut buf = vec![0u8; 16 * 1024];
    let mut bytes: u64 = 0;

    loop {
        // 取消在**每一块之间**生效（blocking 客户端没有中断句柄，见文件头"取消与超时"）
        if cancelled.load(Ordering::SeqCst) {
            push_error(id, "aborted", "已取消");
            return;
        }
        match resp.read(&mut buf) {
            Ok(0) => break, // EOF：响应体读完了
            Ok(n) => {
                // 字节按原样转出去（base64），**不做任何分帧**：分帧是 TS 的事，
                // 宿主只保证字节顺序与完整性。每块一推 —— 合并会让最后一个事件卡在缓冲里。
                push_chunk(id, &buf[..n]);
                bytes += n as u64;
                // C# 的 `CancellationTokenSource(TimeoutSec)` 是"整轮"上限；
                // 这里每收一块比一次，把那份语义保住（卡死的读另有逐次超时兜底）。
                if started.elapsed() >= budget {
                    push_error(id, "timeout", TIMEOUT_MESSAGE);
                    return;
                }
            }
            Err(e) => {
                if cancelled.load(Ordering::SeqCst) {
                    push_error(id, "aborted", "已取消");
                } else if io_is_timeout(&e) || started.elapsed() >= budget {
                    push_error(id, "timeout", TIMEOUT_MESSAGE);
                } else {
                    // 流吐了一半之后连接被掐断走这里。与"协议错"分开：
                    // network 意味着**重试可能成功**，protocol 是"端点回了看不懂的东西"。
                    push_error(id, "network", &e.to_string());
                }
                return;
            }
        }
    }

    push_raw_end(id, bytes);
}

/* ══════════════════════════════════════════════════════════════════════════
 * ⑧ 桥面
 * ══════════════════════════════════════════════════════════════════════════ */

/// `ai.Info()`：状态与**脱敏后的**配置。
/// 这里永远不会出现密钥本身 —— 只有 hasKey（有没有）、keySource（从哪来）、
/// keyPersisted（有没有落盘）。字段顺序与 C# 一致（便于两边对照排查）。
pub fn info() -> String {
    let c = cfg();
    let dpapi_ok = dpapi::selftest();
    let src = key_source();
    let mut o = JsonOut::new();
    o.b("enabled", c.enabled)
        .s("baseUrl", &c.base_url)
        .s("model", &c.model)
        .f("temperature", c.temperature)
        .i("maxTokens", c.max_tokens)
        .b("includeUsage", c.include_usage)
        .i("timeoutSec", c.timeout_sec)
        .i("contextWindow", c.context_window)
        .i("historyTurns", c.history_turns)
        .b("sendExpr", c.send_expr)
        .b("sendResult", c.send_result)
        .b("sendHistory", c.send_history)
        .b("sendCode", c.send_code)
        .b("toolsEnabled", c.tools_enabled)
        .b("hasKey", src != "none")
        .s("keySource", src)
        .b("keyPersisted", !c.api_key_protected.is_empty())
        .b("dpapiAvailable", dpapi_ok)
        .b("configLoadFailed", c.load_failed)
        .s("configPath", &config_path().to_string_lossy())
        .s("configDir", &config_dir().to_string_lossy())
        .s("lastError", &last_error())
        // 页面刷新后靠它决定要不要显示"正在输出"（`bridge.js` 的 refreshAiConfig 读它）
        .i("running", running_count() as i64);
    o.done()
}

/// 当前是否有请求在跑（`relay.ts` 的 relayBusy 用它）
pub fn is_busy() -> bool {
    running_count() > 0
}

/* ── Configure ──────────────────────────────────────────────────────────── */

/// 只在"字段存在且类型对得上"时才算改动 —— 对应 C# 那四个局部函数 TryBool/TryStr/TryInt/TryDouble。
/// 用宏而不是闭包：闭包没法同时可变借用 `cur` 与 `changed`。
macro_rules! set_bool {
    ($root:expr, $name:literal, $cur:expr, $changed:expr, $field:ident) => {
        if let Some(x) = $root.get($name).and_then(|v| v.as_bool()) {
            $cur.$field = x;
            $changed = true;
        }
    };
}
macro_rules! set_str {
    ($root:expr, $name:literal, $cur:expr, $changed:expr, $field:ident) => {
        if let Some(x) = $root.get($name).and_then(|v| v.as_str()) {
            $cur.$field = x.to_string();
            $changed = true;
        }
    };
}
macro_rules! set_int {
    ($root:expr, $name:literal, $cur:expr, $changed:expr, $field:ident) => {
        match take_int($root, $name) {
            // C# 的 `e.GetInt32()` 遇到非整数会抛，被外层 try 接住 → 整次配置失败。
            // 这里照做：宁可报错，也不静默改一个用户没要的值。
            Err(e) => return fail(&format!("配置解析失败：{e}")),
            Ok(Some(n)) => {
                $cur.$field = n;
                $changed = true;
            }
            Ok(None) => {}
        }
    };
}
macro_rules! set_float {
    ($root:expr, $name:literal, $cur:expr, $changed:expr, $field:ident) => {
        if let Some(x) = $root.get($name).and_then(|v| v.as_f64()) {
            $cur.$field = x;
            $changed = true;
        }
    };
}

fn take_int(root: &Map<String, Value>, name: &str) -> Result<Option<i64>, String> {
    match root.get(name) {
        None => Ok(None),
        // 是数字但不是整数（或超出 i64）：与 C# 的 GetInt32 一样报错
        Some(v) if v.is_number() => v.as_i64().map(Some).ok_or_else(|| format!("字段 {name} 不是整数")),
        // 类型不对就当没给（与 C# 的 TryInt 一致）
        Some(_) => Ok(None),
    }
}

/// 更新非密钥配置。入参是**只含要改的字段**的 JSON（页面只发改动过的字段，
/// 整份回传会把界面没显示的字段以默认值悄悄写回磁盘）。
pub fn configure(json_text: &str) -> String {
    let v: Value = match serde_json::from_str(json_text) {
        Ok(v) => v,
        Err(e) => return fail(&format!("配置解析失败：{e}")),
    };
    // C# 的 `root.TryGetProperty` 在顶层不是对象时会抛 → 被接住 → "配置解析失败"。照做。
    let Some(root) = v.as_object() else {
        return fail("配置解析失败：顶级不是一个 JSON 对象");
    };

    let mut cur = cfg();
    let mut changed = false;

    // 顺序与 C# 一致（其中 toolsEnabled 是此前被漏掉、现在补上的那一个）
    set_bool!(root, "enabled", cur, changed, enabled);
    set_str!(root, "baseUrl", cur, changed, base_url);
    set_str!(root, "model", cur, changed, model);
    set_float!(root, "temperature", cur, changed, temperature);
    set_int!(root, "maxTokens", cur, changed, max_tokens);
    set_bool!(root, "includeUsage", cur, changed, include_usage);
    set_int!(root, "timeoutSec", cur, changed, timeout_sec);
    set_int!(root, "contextWindow", cur, changed, context_window);
    set_int!(root, "historyTurns", cur, changed, history_turns);
    set_bool!(root, "sendExpr", cur, changed, send_expr);
    set_bool!(root, "sendResult", cur, changed, send_result);
    set_bool!(root, "sendHistory", cur, changed, send_history);
    set_bool!(root, "sendCode", cur, changed, send_code);
    set_bool!(root, "toolsEnabled", cur, changed, tools_enabled);

    if !changed {
        let mut o = JsonOut::new();
        o.b("ok", true).i("changed", 0);
        return o.done();
    }

    cur.normalize();
    if let Err(e) = cur.save() {
        return fail(&format!("写入配置失败：{e}"));
    }
    // 立刻刷新内存里的那份（否则下一轮请求还在用旧端点/旧超时）
    with_cfg(|c| *c = cur);
    let mut o = JsonOut::new();
    o.b("ok", true).i("changed", 1);
    o.done()
}

/* ── SetKey / ClearKey ──────────────────────────────────────────────────── */

/// 设置 API Key。**只写不读**：页面拿不到它。
/// DPAPI 可用就落盘（密文）；不可用则**只留在内存**，并明确告诉调用方"重启后要重填"
/// —— 绝不降级成明文落盘（见 `dpapi.rs` 的三条纪律）。
pub fn set_key(key: &str) -> String {
    if key.trim().is_empty() {
        return fail("密钥为空");
    }
    let trimmed = key.trim().to_string();

    match dpapi::protect(&trimmed) {
        Some(blob) => {
            let mut cur = cfg();
            cur.api_key_protected = blob;
            if let Err(e) = cur.save() {
                // ⚠ 这里是**有意**与 C# 的一处差异：C# 先把自己缓存的那份对象改了再 Save，
                // 失败时内存里仍然留着新密文（而 `_memoryKey` 是空的），于是"保存失败"
                // 之后密钥却已经生效了一半。Rust 这边只在落盘成功后才提交内存，
                // 失败就是失败，语义干净。
                return fail(&format!("密钥已加密但写入配置失败：{e}"));
            }
            with_cfg(|c| *c = cur);
            if let Ok(mut g) = MEMORY_KEY.lock() {
                g.clear();
            }
            let mut o = JsonOut::new();
            o.b("ok", true).b("persisted", true);
            o.done()
        }
        None => {
            if let Ok(mut g) = MEMORY_KEY.lock() {
                *g = trimmed;
            }
            let mut o = JsonOut::new();
            o.b("ok", true).b("persisted", false).s(
                "warning",
                "DPAPI 在本机不可用：密钥只保留在本次运行的内存里（重启后需要重新填写）。不会把明文写到磁盘上。",
            );
            o.done()
        }
    }
}

/// 清掉密钥（内存与密文一起清）
pub fn clear_key() -> String {
    if let Ok(mut g) = MEMORY_KEY.lock() {
        g.clear();
    }
    let mut cur = cfg();
    cur.api_key_protected.clear();
    if let Err(e) = cur.save() {
        return fail(&format!("清除密钥失败：{e}"));
    }
    with_cfg(|c| *c = cur);
    let mut o = JsonOut::new();
    o.b("ok", true);
    o.done()
}

/* ── Test（连通性自检）──────────────────────────────────────────────────── */

/// 端点的错误文案（C# 是 `e.GetType().Name + "：" + e.Message`；这里保留"名称：消息"这个
/// 形状，名称换成能看懂的中文分类 —— 面板上直接显示这句，英文类型名对用户没有意义）。
fn reqwest_error_text(e: &reqwest::Error) -> String {
    let kind = if e.is_connect() {
        "连接失败"
    } else if e.is_body() || e.is_decode() {
        "响应读取失败"
    } else {
        "请求失败"
    };
    format!("{kind}：{e}")
}

/// 一次连通性测试：非流式、`max_tokens=1`。返回 `(ok, status, ms, detail)`。
///
/// 它**不解析 SSE**，所以留在宿主侧不构成"第二套实现"；结果经推送话题 `ai.test` 回页面。
/// 超时用 `min(30, timeoutSec)`（C# 也是这个上限，探测不值得等满 900 秒）。
fn test_once(c: &AiConfig, api_key: &str, timeout_sec: i64) -> (bool, i32, i64, String) {
    let started = Instant::now();
    let url = join_url(&c.base_url, "/chat/completions");
    // 形状照 C# `AiClient.BuildBody`：只要 model / messages / stream，外加 max_tokens=1
    let body = json!({
        "model": c.model,
        "messages": [{ "role": "user", "content": "ping" }],
        "stream": false,
        "max_tokens": 1,
    })
    .to_string();

    let client = http::client_with_timeout_ua(timeout_sec, Some(AI_UA));
    let resp = client
        .post(&url)
        .header("Content-Type", "application/json")
        // 与中继那条同源：C# 关掉了自动解压，这里也别让 reqwest 自动补 Accept-Encoding
        .header("Accept-Encoding", "identity")
        .header("Authorization", format!("Bearer {api_key}"))
        .body(body)
        .send();

    let resp = match resp {
        Ok(r) => r,
        Err(e) => {
            let ms = started.elapsed().as_millis() as i64;
            return if e.is_timeout() { (false, 0, ms, "已取消或超时".into()) } else { (false, 0, ms, reqwest_error_text(&e)) };
        }
    };

    let status = resp.status().as_u16() as i32;
    let text = match resp.text() {
        Ok(t) => t,
        Err(e) => {
            let ms = started.elapsed().as_millis() as i64;
            return if e.is_timeout() { (false, 0, ms, "已取消或超时".into()) } else { (false, 0, ms, reqwest_error_text(&e)) };
        }
    };
    let ms = started.elapsed().as_millis() as i64;

    if !(200..300).contains(&status) {
        // C# 读错误体后截断到 400，再在 Test 里截到 300 —— 净效果就是 300
        return (false, status, ms, truncate(text.trim(), 300));
    }

    // 形状不认识也不影响"通了"这个结论（C# 注释原话）
    let model = site::json_str(&text, "model");
    let detail = if model.is_empty() { "端点已响应".to_string() } else { format!("模型：{model}") };
    (true, status, ms, detail)
}

/// 测连接。**异步**：同步宿主对象调用会阻塞渲染进程，一次 TLS + 推理往返可能几秒，
/// 界面会被冻住。所以这里立即返回，结果用 `ai.test` 推回去。
pub fn test() -> String {
    let key = resolve_key();
    if key.is_empty() {
        return fail("没有 API Key（先在下面填一个）");
    }
    let c = cfg();
    if !c.enabled {
        return fail("AI 未启用（先打开上面的开关）");
    }

    let secs = c.timeout_sec.min(30).max(1);
    let owned = c.clone();
    let spawned = std::thread::Builder::new().name("mf-ai-test".into()).spawn(move || {
        let (ok, status, ms, detail) = test_once(&owned, &key, secs);
        let payload = json!({
            "ok": ok,
            "status": status,
            "ms": ms,
            // 回的是**这次实际用的** model（供面板显示"刚才用的是哪个模型"）
            "model": owned.model,
            "detail": detail,
        });
        push::send("ai.test", &payload.to_string());
    });
    if let Err(e) = spawned {
        return fail(&format!("起不了连通性测试线程：{e}"));
    }

    let mut o = JsonOut::new();
    o.b("ok", true).b("testing", true);
    o.done()
}

/* ── Begin / Cancel / CancelAll ─────────────────────────────────────────── */

/// 带密钥发一次请求，响应字节经推送转回页面。
/// 入参：`{"path":"/chat/completions","body":{…OpenAI 请求体…}}`
/// 返回 `{"ok":true,"requestId":"r1"}`；
/// 页面随后会收到 `ai.http` / `ai.raw*` 话题，由 TS 侧的 `client.ts` 解析成模型事件。
pub fn begin(json_text: &str) -> String {
    let c = cfg();
    if !c.enabled {
        return fail("AI 未启用（设置 → AI 里打开）");
    }

    let key = resolve_key();
    if key.is_empty() {
        // 有密文却解不开 = 换了 Windows 用户/文件被改：这句文案要能让用户知道该重填
        let msg = if !c.api_key_protected.is_empty() {
            "密钥无法解密（可能换了 Windows 用户或文件被改动），请重新填写"
        } else {
            "还没有配置 API Key"
        };
        return fail_kind("config", msg);
    }

    if is_busy() {
        // 单飞：同一时间只允许一轮。TS 那边也有同样的守卫，这里是第二道。
        return fail_kind("busy", "已有一轮对话在输出，请先停止它");
    }

    // 入参解析（C# 在 `AiRelay.Begin` 里做，失败同样归到 config 类）
    let v: Value = match serde_json::from_str(json_text) {
        Ok(v) => v,
        Err(e) => return last_error_fail_kind("config", &format!("请求体解析失败：{e}")),
    };
    let Some(root) = v.as_object() else {
        return last_error_fail_kind("config", "请求体解析失败：顶级不是一个 JSON 对象");
    };
    let path = root.get("path").and_then(|x| x.as_str()).unwrap_or("/chat/completions").to_string();
    // ⚠ serde 的 `Value::to_string()` 会把 body **重新序列化**（键序变成字典序），
    // C# 的 `GetRawText()` 给的是原文切片。语义完全一致、端点看不出来（它本来就按 JSON 解析），
    // 但如果你在假端点里逐字节比对过请求体，这里是唯一会对不上的地方。
    let body = root.get("body").map(|b| b.to_string()).unwrap_or_else(|| "{}".to_string());

    if let Err(e) = validate_path(&path) {
        return last_error_fail_kind("config", &e);
    }

    let id = format!("r{}", SEQ.fetch_add(1, Ordering::SeqCst) + 1);
    let cancelled = Arc::new(AtomicBool::new(false));
    register_turn(&id, cancelled.clone());

    let turn_id = id.clone();
    let cfg_snapshot = c.clone();
    let spawned = std::thread::Builder::new()
        .name(format!("mf-ai-{turn_id}"))
        .spawn(move || {
            pump(&cfg_snapshot, &key, &turn_id, &path, &body, &cancelled);
            finish_turn(&turn_id);
        });

    if let Err(e) = spawned {
        finish_turn(&id);
        return last_error_fail_kind("network", &format!("起不了中继线程：{e}"));
    }

    let mut o = JsonOut::new();
    o.b("ok", true).s("requestId", &id);
    o.done()
}

/// 停止一轮输出（页面点"停止"、或窗口关闭时调用）。
/// ⚠ 只是**置取消标记**：真正收尾在读循环的下一块数据处（见文件头"取消与超时"）。
pub fn cancel(request_id: &str) -> String {
    let g = TURNS.lock().unwrap_or_else(|e| e.into_inner());
    match g.iter().find(|t| t.id == request_id) {
        Some(t) => {
            t.cancelled.store(true, Ordering::SeqCst);
            let mut o = JsonOut::new();
            o.b("ok", true);
            o.done()
        }
        None => fail("没有这个请求"),
    }
}

/// 取消所有在跑的中继，返回取消了几条
pub fn cancel_all() -> String {
    let g = TURNS.lock().unwrap_or_else(|e| e.into_inner());
    let mut n = 0i64;
    for t in g.iter() {
        if !t.running.load(Ordering::SeqCst) {
            continue;
        }
        t.cancelled.store(true, Ordering::SeqCst);
        n += 1;
    }
    let mut o = JsonOut::new();
    o.b("ok", true).i("cancelled", n);
    o.done()
}

/* ── SelfCheck（设置面板的"AI"组要有一行能跑的自检）──────────────────────── */

fn check_json(name: &str, ok: bool, detail: &str) -> String {
    let mut o = JsonOut::new();
    o.s("name", name).b("ok", ok).s("detail", detail);
    o.done()
}

/// 四项自检，**都不联网**：
///   ① DPAPI 能不能用（不可用是降级，不算失败 —— 密钥只留内存）；
///   ② 中继的路径闸门：相对路径放行，绝对地址 / 协议相对地址 / `..` 一律拒绝；
///   ③ 字节经 base64 转手无损（响应体就是这么过推送的）；
///   ④ 配置目录可写。
pub fn self_check() -> String {
    let mut checks: Vec<String> = Vec::new();
    let mut all = true;

    // ① DPAPI —— 不可用**不算失败**（降级），所以不参与 ok_all
    let dpapi_ok = dpapi::selftest();
    checks.push(check_json(
        "密钥保护（DPAPI）",
        dpapi_ok,
        if dpapi_ok {
            "可用：密钥以当前用户范围加密后落盘"
        } else {
            "不可用：密钥只留在内存（不写明文）"
        },
    ));

    // ② 中继路径闸门
    let allow_ok = validate_path("/chat/completions").is_ok();
    let deny_absolute = validate_path("https://evil.example/v1/chat/completions").is_err();
    let deny_proto_relative = validate_path("//evil.example/v1").is_err();
    let deny_dot_dot = validate_path("/../../etc").is_err();
    let gate_ok = allow_ok && deny_absolute && deny_proto_relative && deny_dot_dot;
    all &= gate_ok;
    checks.push(check_json(
        "中继路径闸门（拒绝绝对地址）",
        gate_ok,
        if gate_ok {
            "相对路径放行；绝对地址 / 协议相对地址 / .. 一律拒绝"
        } else {
            "闸门判定不正确，存在把密钥发到任意地址的风险"
        },
    ));

    // ③ base64 往返（含 0x00/0xFF/中文的一个字节探针）
    let b64_ok = base64_round_trip();
    all &= b64_ok;
    checks.push(check_json(
        "响应字节转手无损（base64）",
        b64_ok,
        if b64_ok { "含 0x00/0xFF/中文的探针往返一致" } else { "往返不一致" },
    ));

    // ④ 配置目录可写
    let dir = config_dir();
    let probe = dir.join("ai.selftest.tmp");
    let write_result = std::fs::create_dir_all(&dir)
        .map_err(|e| e.to_string())
        .and_then(|_| std::fs::write(&probe, b"ok").map_err(|e| e.to_string()))
        .and_then(|_| std::fs::remove_file(&probe).map_err(|e| e.to_string()));
    let (writable, write_detail) = match write_result {
        Ok(()) => (true, dir.to_string_lossy().to_string()),
        Err(e) => (false, e),
    };
    all &= writable;
    checks.push(check_json("配置目录可写", writable, &write_detail));

    let mut o = JsonOut::new();
    o.b("ok", true).raw("checks", &format!("[{}]", checks.join(","))).b("ok_all", all);
    o.done()
}
