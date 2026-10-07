//! search.rs —— 联网搜索桥（对照 C# `SearchBridge.cs` + `SearchBackend.cs` + `SearchCache.cs`
//! + `SearchConfig.cs`，JS 侧是 `hostObjects.sync.search`）
//!
//! ## 为什么这件事在宿主里（与 AI 那条同源，C# 注释里的理由照搬）
//!   · **凭据**：Wolfram 的 App ID 只在宿主（DPAPI 密文），页面只见 `hasWolframKey`。
//!     如果页面能改后端端点，它就能把 App ID 发到任意地址 —— 和 AI 中继面对的是同一个问题，
//!     所以端点的测试/镜像覆盖只走环境变量 `MF_SEARCH_ENDPOINTS`，**不**从 `Configure` 暴露。
//!   · **网络**：页面跑在虚拟主机（`https://mfmath.local`）下，直连外部站点会撞 CORS；
//!     而 DDG 的 HTML 页也不允许跨源读。
//!   · **缓存与超时**：一处实现，且"断网 / 超时 / 被反爬 / 形状变了"要分类清楚。
//!
//! ## 数据流
//! 页面 `search.Start({query, engine?})` → **立即**返回 `{ok, requestId}`
//! → 宿主线程查缓存（键含引擎）→ 未命中就按引擎抓取 → 解析成纯文本结果
//! → `push` 推 `search.done{results, abstract, fromCache, cachedAt, elapsedMs}`
//!   或 `search.error{kind, status, message}`。
//!
//! **为什么必须异步**：宿主对象是**同步**调用，在这里把网络等完会把渲染进程冻住几秒
//! （控制台与 AI 那边都踩过这条）。所以 `Start` 只登记作业 + 起一条线程，结果一律经 push 回去。
//!
//! ## 桥面（与前端 `lib/search/bridge.js` 的 `call()` 调用点一一对应）
//! `Info() Configure(json) SetWolframKey(key) ClearWolframKey() Start(json) Cancel(id)
//!  CancelAll() Busy() OpenUrl(url) CacheStats() ClearCache() SelfCheck()`
//!
//! ## 三条与安全/健壮性有关的规矩（C# 的取舍，理由一并带上）
//!   ① **HTML 是不可信输入**：只从中抽文本（去标签、解实体、折叠空白、截断），
//!      绝不把标记原样交给界面 —— 界面那边也只用插值渲染。
//!   ② **结果 URL 只接受 http/https**：搜到的 `javascript:` / `data:` 一律丢弃；
//!      "打开结果"再经 `shellopen` 的同一道闸门（只放行 http/https）。
//!   ③ **失败分类要能指导下一步**：`config` / `network` / `http` / `parse` / `timeout` / `aborted`。
//!      UI 按类别给不同建议，而不是笼统一句"搜索失败"。
//!
//! ⚠ **不进渲染进程的东西**（本文件里逐处都写了这一点）：App ID 明文、DPAPI 密文、
//! 以及"用户搜了什么"这件事本身 —— 后者不写日志，免得诊断包把查询历史一起带走。

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, AtomicI64, Ordering};
use std::sync::{Arc, Mutex, MutexGuard, OnceLock};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use serde_json::{json, Map, Value};

use crate::{dpapi, http, logging, push, shellopen, site, sys};

/* ══════════════════════════════════════════════════════════════════════════
 * ① 端点（含环境变量覆盖，供测试与自建镜像用）
 *
 * **为什么覆盖只走环境变量**：页面能改 Wolfram 的端点 = 页面能把 App ID 发到任意地址。
 * 环境变量只有"启动宿主的那个人"能设（端到端用例、自建镜像都属于这一类）。
 * ══════════════════════════════════════════════════════════════════════════ */

const DEFAULT_DDG_HTML: &str = "https://html.duckduckgo.com/html";
const DEFAULT_DDG_IA: &str = "https://api.duckduckgo.com";
const DEFAULT_WOLFRAM: &str = "https://api.wolframalpha.com/v1/result";

/// 查询词上限：与 C# `SearchBackend.RunAsync` 的 500 一致（超长查询对端也是白费）
const MAX_QUERY_CHARS: usize = 500;

/// `MF_SEARCH_ENDPOINTS` 的解析结果（进程内只解析一次；配错了就当没配，用内置端点）
static OVERRIDES: OnceLock<HashMap<String, String>> = OnceLock::new();

fn overrides() -> &'static HashMap<String, String> {
    OVERRIDES.get_or_init(|| {
        // 键统一小写：C# 那份字典是 OrdinalIgnoreCase，这里等价实现
        let mut map: HashMap<String, String> = HashMap::new();
        let raw = std::env::var("MF_SEARCH_ENDPOINTS").unwrap_or_default();
        if !raw.trim().is_empty() {
            if let Ok(v) = serde_json::from_str::<Value>(&raw) {
                if let Some(obj) = v.as_object() {
                    for (k, val) in obj {
                        if let Some(s) = val.as_str() {
                            map.insert(k.to_ascii_lowercase(), s.to_string());
                        }
                    }
                }
            }
        }
        map
    })
}

fn endpoint(key: &str, fallback: &str) -> String {
    match overrides().get(&key.to_ascii_lowercase()) {
        Some(v) if !v.trim().is_empty() => v.trim().trim_end_matches('/').to_string(),
        _ => fallback.to_string(),
    }
}

pub fn ddg_html_endpoint() -> String {
    endpoint("ddgHtml", DEFAULT_DDG_HTML)
}
pub fn ddg_ia_endpoint() -> String {
    endpoint("ddgIa", DEFAULT_DDG_IA)
}
pub fn wolfram_endpoint() -> String {
    endpoint("wolfram", DEFAULT_WOLFRAM)
}

/* ══════════════════════════════════════════════════════════════════════════
 * ② 配置（`%LOCALAPPDATA%\MFMath\settings\search.json`）
 *
 * 与 AI / 账号同一条规矩：**凭据不进渲染进程**。Wolfram 的 App ID 存这里（DPAPI 密文），
 * 页面只见 `hasWolframKey`。其余字段（引擎、端点、超时、条数、缓存 TTL）页面本来就知道，
 * 但为了"一处真相"仍由宿主读写同一个文件 —— 设置面板与搜索页都从 `Info()` 取。
 *
 * ⚠ 读写走 `sys::store_write/read`（不是自己开文件）：那条路已经带上了
 *   `.bak` 备份 + 临时文件 + 原子替换，配置写一半崩掉不会留下半截 JSON。
 * ══════════════════════════════════════════════════════════════════════════ */

const CONFIG_STEM: &str = "search";

fn default_engine() -> String {
    "duckduckgo".to_string()
}
fn default_timeout_sec() -> i64 {
    15
}
fn default_result_count() -> i64 {
    8
}
fn default_cache_enabled() -> bool {
    true
}
fn default_cache_ttl_hours() -> i64 {
    24
}

/// 搜索配置。字段名与 C# `SearchConfig` 的 camelCase 一致 —— 迁移期两个宿主共用同一份文件。
#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SearchConfig {
    /// duckduckgo | wolfram | custom
    #[serde(default = "default_engine")]
    pub engine: String,
    /// 自定义端点（SearXNG 兼容的 JSON 接口根地址）
    #[serde(default)]
    pub custom_url: String,
    #[serde(default = "default_timeout_sec")]
    pub timeout_sec: i64,
    /// 每个来源最多取多少条（1–20）
    #[serde(default = "default_result_count")]
    pub result_count: i64,
    #[serde(default = "default_cache_enabled")]
    pub cache_enabled: bool,
    /// 缓存有效期（小时）。0 = 不过期
    #[serde(default = "default_cache_ttl_hours")]
    pub cache_ttl_hours: i64,
    /// DPAPI 密文（base64）。**绝不出现在任何返回给页面的 JSON 里**
    #[serde(default)]
    pub wolfram_key_protected: String,
    /// 配置文件坏掉时置位（**只报给界面，不落盘**）：坏文件按默认跑，但要如实说
    #[serde(skip)]
    pub load_failed: bool,
}

impl Default for SearchConfig {
    fn default() -> Self {
        SearchConfig {
            engine: default_engine(),
            custom_url: String::new(),
            timeout_sec: default_timeout_sec(),
            result_count: default_result_count(),
            cache_enabled: default_cache_enabled(),
            cache_ttl_hours: default_cache_ttl_hours(),
            wolfram_key_protected: String::new(),
            load_failed: false,
        }
    }
}

impl SearchConfig {
    /// 规范化（与 C# `SearchConfig.Normalize` 逐条一致）：
    /// 引擎只认三个；端点去尾斜杠；超时 3–120；条数 1–20（给 0 视为没配 → 8）；
    /// TTL 0–720 小时（0 = 不过期）。
    pub fn normalize(&mut self) {
        if !matches!(self.engine.as_str(), "duckduckgo" | "wolfram" | "custom") {
            self.engine = default_engine();
        }
        self.custom_url = self.custom_url.trim().trim_end_matches('/').to_string();
        if self.timeout_sec < 3 {
            self.timeout_sec = 3;
        }
        if self.timeout_sec > 120 {
            self.timeout_sec = 120;
        }
        if self.result_count < 1 {
            self.result_count = 8;
        }
        if self.result_count > 20 {
            self.result_count = 20;
        }
        if self.cache_ttl_hours < 0 {
            self.cache_ttl_hours = 0;
        }
        if self.cache_ttl_hours > 24 * 30 {
            self.cache_ttl_hours = 24 * 30;
        }
    }

    /// 从设置文件读；文件不存在用默认值（**离线也要能起来**）。
    /// 文件在但读不出来 → 默认值 + `load_failed`，让设置面板能说实话。
    fn load() -> Self {
        if !config_path().is_file() {
            return SearchConfig::default();
        }
        match sys::store_read_value(CONFIG_STEM) {
            Some(v) => match serde_json::from_value::<SearchConfig>(v) {
                Ok(mut c) => {
                    c.normalize();
                    c
                }
                Err(_) => {
                    let mut c = SearchConfig::default();
                    c.load_failed = true;
                    c
                }
            },
            None => {
                let mut c = SearchConfig::default();
                c.load_failed = true; // 坏文件按默认跑，并如实报给界面
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

/// `%LOCALAPPDATA%\MFMath\settings\search.json`（诊断导出会**跳过**它：里面有 App ID 密文）
fn config_path() -> PathBuf {
    logging::data_dir().join("settings").join("search.json")
}

static CFG: OnceLock<Mutex<SearchConfig>> = OnceLock::new();

fn cfg_slot() -> &'static Mutex<SearchConfig> {
    CFG.get_or_init(|| Mutex::new(SearchConfig::load()))
}

fn cfg() -> SearchConfig {
    cfg_slot().lock().map(|c| c.clone()).unwrap_or_default()
}

fn with_cfg<R>(f: impl FnOnce(&mut SearchConfig) -> R) -> R {
    let mut g = cfg_slot().lock().unwrap_or_else(|e| e.into_inner());
    f(&mut g)
}

fn now_ms() -> i64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_millis() as i64).unwrap_or(0)
}

/* ══════════════════════════════════════════════════════════════════════════
 * ③ 结果的形状
 * ══════════════════════════════════════════════════════════════════════════ */

/// 一条搜索结果（`source` 会显示在界面结果条上，说明它来自哪个后端）
#[derive(Clone, Serialize, Deserialize, Default)]
pub struct SearchResult {
    pub title: String,
    pub url: String,
    pub snippet: String,
    /// 这条结果来自哪个后端
    pub source: String,
}

/* ══════════════════════════════════════════════════════════════════════════
 * ④ 缓存（`%LOCALAPPDATA%\MFMath\search_cache.json`，与 C# 同路径同形状）
 *
 * 三条规矩，第一条是**修 v1 的缺陷**：
 *   ① **缓存键必须带引擎**。v1 只用查询词做键，于是"用 A 引擎搜过 x"会让"用 B 引擎搜 x"
 *      直接命中 A 的结果 —— 换了引擎却不生效，而且看不出来。
 *   ② **带 TTL**（v1 没有），过期即视为未命中；TTL 从配置读，0 表示不过期。
 *   ③ **有上限**（默认 200 条），按时间淘汰最旧的；原子落盘 —— 缓存文件坏了只丢缓存，
 *      不能连累搜索本身。
 *
 * 文件与 C# 是**同一个**（两个宿主共用），所以字段名与 JSON 形状必须逐字一致。
 * ══════════════════════════════════════════════════════════════════════════ */

const CACHE_MAX_ENTRIES: usize = 200;

#[derive(Clone, Serialize, Deserialize, Default)]
pub struct CacheEntry {
    /// 写入时刻（unix ms）
    #[serde(default)]
    pub at: i64,
    #[serde(default)]
    pub query: String,
    #[serde(default)]
    pub engine: String,
    /// JSON 里就叫 `abstract`（C# 的属性名），Rust 这边只能换个字段名
    #[serde(rename = "abstract", default)]
    pub abstract_text: String,
    #[serde(default)]
    pub results: Vec<SearchResult>,
}

fn cache_path() -> PathBuf {
    logging::data_dir().join("search_cache.json")
}

/// 规范化查询：去空白、折叠空格、小写 —— "x^2" 与 " X^2 " 应当命中同一条
fn normalize_query(query: &str) -> String {
    query.split_whitespace().collect::<Vec<_>>().join(" ").to_lowercase()
}

/// 缓存键：**引擎 + 规范化查询**（v1 只用了后半截，所以换引擎不生效）
fn cache_key(engine: &str, query: &str) -> String {
    format!("{engine}|{}", normalize_query(query))
}

static CACHE: Mutex<Option<HashMap<String, CacheEntry>>> = Mutex::new(None);

/// 取缓存表（首次调用时懒加载；**坏文件当空缓存**，绝不阻断搜索）
fn cache_lock() -> MutexGuard<'static, Option<HashMap<String, CacheEntry>>> {
    let mut g = CACHE.lock().unwrap_or_else(|e| e.into_inner());
    if g.is_none() {
        *g = Some(load_entries());
    }
    g
}

fn load_entries() -> HashMap<String, CacheEntry> {
    let mut map = HashMap::new();
    let Ok(text) = std::fs::read_to_string(cache_path()) else { return map };
    let list: Vec<CacheEntry> = serde_json::from_str(&text).unwrap_or_default();
    for e in list {
        // 没有引擎的条目无法参与"键含引擎"的约定，直接丢（C# 同样跳过）
        if e.engine.is_empty() {
            continue;
        }
        map.insert(cache_key(&e.engine, &e.query), e);
    }
    map
}

/// 命中判定：开关关着 / 没这条 / 过期（TTL > 0 且超龄）都算未命中
fn cache_get(engine: &str, query: &str, c: &SearchConfig) -> Option<CacheEntry> {
    if !c.cache_enabled {
        return None;
    }
    let g = cache_lock();
    let map = g.as_ref()?;
    let e = map.get(&cache_key(engine, query))?;
    if c.cache_ttl_hours > 0 {
        let age_hours = (now_ms() - e.at) as f64 / 3_600_000.0;
        if age_hours > c.cache_ttl_hours as f64 {
            return None; // 过期当未命中
        }
    }
    Some(e.clone())
}

/// 写一条缓存并落盘。**空结果不要写**（调用方判断）：下次还该再试一次。
fn cache_put(engine: &str, query: &str, abstract_text: &str, results: &[SearchResult]) {
    let mut g = cache_lock();
    let Some(map) = g.as_mut() else { return };
    map.insert(
        cache_key(engine, query),
        CacheEntry {
            at: now_ms(),
            query: query.to_string(),
            engine: engine.to_string(),
            abstract_text: abstract_text.to_string(),
            results: results.to_vec(),
        },
    );
    // 超上限就按时间淘汰最旧的（先算要淘汰几条，再删 —— 边删边比长度会算错）
    if map.len() > CACHE_MAX_ENTRIES {
        let over = map.len() - CACHE_MAX_ENTRIES;
        let mut by_age: Vec<(String, i64)> = map.iter().map(|(k, v)| (k.clone(), v.at)).collect();
        by_age.sort_by_key(|(_, at)| *at);
        for (k, _) in by_age.into_iter().take(over) {
            map.remove(&k);
        }
    }
    let mut list: Vec<CacheEntry> = map.values().cloned().collect();
    list.sort_by_key(|e| e.at);
    save_entries(&list);
}

/// 原子落盘（临时文件 + rename）。失败只丢缓存，不影响这次搜索。
/// Windows 上 `fs::rename` 走 `MoveFileEx(MOVEFILE_REPLACE_EXISTING)`：目标存在也能原子替换。
fn save_entries(list: &[CacheEntry]) {
    let path = cache_path();
    if let Some(dir) = path.parent() {
        let _ = std::fs::create_dir_all(dir);
    }
    let Ok(text) = serde_json::to_string(list) else { return };
    let tmp = PathBuf::from(format!("{}.tmp", path.display()));
    if std::fs::write(&tmp, text.as_bytes()).is_err() {
        return;
    }
    if std::fs::rename(&tmp, &path).is_err() {
        let _ = std::fs::remove_file(&tmp);
    }
}

fn cache_stats_value() -> Value {
    let g = cache_lock();
    let map = g.as_ref();
    let entries = map.map(|m| m.len()).unwrap_or(0);
    let newest = map.and_then(|m| m.values().map(|e| e.at).max()).unwrap_or(0);
    let bytes = std::fs::metadata(cache_path()).map(|m| m.len()).unwrap_or(0);
    json!({ "entries": entries, "bytes": bytes, "newest": newest })
}

/// `search.CacheStats()`（设置面板显示"当前 N 条 · N KB"）
pub fn cache_stats() -> String {
    cache_stats_value().to_string()
}

/// `search.ClearCache()`：内存与文件一起清；删不掉也把内存清了
pub fn clear_cache() -> String {
    let mut g = cache_lock();
    let n = g.as_ref().map(|m| m.len()).unwrap_or(0);
    *g = Some(HashMap::new());
    let _ = std::fs::remove_file(cache_path());
    json!({ "ok": true, "cleared": n }).to_string()
}

/* ══════════════════════════════════════════════════════════════════════════
 * ⑤ 文本清洗（HTML 是不可信输入）
 * ══════════════════════════════════════════════════════════════════════════ */

/// ASCII 大小写不敏感的子串查找（返回字节下标）。`needle` 必须是 ASCII。
///
/// 为什么手写而不是引入正则：C# 那三条模式都是"标签名 + 一个标记词 + 非贪婪文本"，
/// 用不上面向正则的能力；而多一个依赖就多一份"随版本编译不过"的风险。
/// 语义与 C# 的对应关系写在各调用点上。
fn find_ci(hay: &str, needle: &str, from: usize) -> Option<usize> {
    let h = hay.as_bytes();
    let n = needle.as_bytes();
    if n.is_empty() || h.len() < n.len() {
        return None;
    }
    let first = n[0].to_ascii_lowercase();
    let mut i = from;
    while i + n.len() <= h.len() {
        // UTF-8 的续字节与任何 ASCII 都不相等，所以逐字节比较不会切坏编码
        if h[i].to_ascii_lowercase() == first {
            let mut k = 1;
            while k < n.len() && h[i + k].to_ascii_lowercase() == n[k].to_ascii_lowercase() {
                k += 1;
            }
            if k == n.len() {
                return Some(i);
            }
        }
        i += 1;
    }
    None
}

/// 取标签里 `name="…"` 的属性值（C# 用 `href="(?<h>[^"]+)"`）
fn attr_value(tag: &str, name: &str) -> Option<String> {
    let needle = format!("{name}=\"");
    let at = find_ci(tag, &needle, 0)?;
    let from = at + needle.len();
    let end = tag[from..].find('"').map(|o| from + o)?;
    Some(tag[from..end].to_string())
}

/// 去掉 `<script>…</script>` / `<style>…</style>` 这类整块内容（连同里面的文本一起丢）
fn remove_block(s: &str, open: &str, close: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut pos = 0usize;
    loop {
        let Some(o) = find_ci(s, open, pos) else {
            out.push_str(&s[pos..]);
            break;
        };
        out.push_str(&s[pos..o]);
        out.push(' ');
        match find_ci(s, close, o) {
            Some(c) => pos = c + close.len(),
            None => {
                // 没有闭合标签：剩下的整段丢掉（C# 的 `.*?</script>` 也不匹配未闭合的那种）
                break;
            }
        }
    }
    out
}

/// 把所有 `<…>` 换成一个空格（C# 的 `<[^>]+>` → " "）
fn remove_tags(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut rest = s;
    while let Some(o) = rest.find('<') {
        out.push_str(&rest[..o]);
        match rest[o..].find('>') {
            Some(e) => {
                out.push(' ');
                rest = &rest[o + e + 1..];
            }
            None => break, // 未闭合的 '<'：原样留下
        }
    }
    out.push_str(rest);
    out
}

/// 折叠空白并去首尾（C# 的 `\s+` → " "）
fn collapse_ws(s: &str) -> String {
    s.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// 去标签、解实体、折叠空白。**不解析任何标记**，只留文本。
pub fn strip_tags(html: &str) -> String {
    if html.is_empty() {
        return String::new();
    }
    let s = remove_block(html, "<script", "</script>");
    let s = remove_block(&s, "<style", "</style>");
    let s = remove_tags(&s);
    // ⚠ 顺序与 C# 一致：**先去标签再解实体** —— 反过来的话 `&lt;b&gt;` 会被当成真标签删掉
    let s = html_decode(&s);
    collapse_ws(&s)
}

/// 截断（超长加省略号）。按**字符**数而不是字节数切，避免把一个码点切成两半。
pub fn clip(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        return s.to_string();
    }
    let mut out: String = s.chars().take(max).collect();
    out.push('…');
    out
}

/// 解 HTML 实体。**只做文本用途**：解出来的东西永远走插值渲染，不再当标记。
///
/// 与 C# `WebUtility.HtmlDecode` 的对齐情况（都实测过，不再靠猜）：
///   · 命名实体表现在是 **HTML4 全集 253 条**，且逐条由 .NET 的 `HtmlDecode` 取值生成
///     （见 `named_entity` 的注释）—— 不再有"子集漏掉某条"的问题；
///   · 命名与数字实体都**必须带分号**才解。这与 .NET 一致：实测 `&uuml`、`&#39`、`&#x27`
///     在 .NET 里同样不解，所以这里"见到就原样留着"是对齐，不是保守。
fn html_decode(s: &str) -> String {
    if !s.contains('&') {
        return s.to_string();
    }
    let mut out = String::with_capacity(s.len());
    let mut rest = s;
    while let Some(at) = rest.find('&') {
        out.push_str(&rest[..at]);
        let after = &rest[at..];
        // 实体最长也就 30 来个字符（&CounterClockwiseContourIntegral;），窗口给 34 个字符够
        let limit = after
            .char_indices()
            .take(34)
            .last()
            .map(|(i, c)| i + c.len_utf8())
            .unwrap_or(after.len());
        let window = &after[..limit];
        let decoded = window.find(';').and_then(|e| decode_entity(&window[1..e]));
        match decoded {
            Some((ch, consumed)) => {
                out.push(ch);
                rest = &after[consumed..];
            }
            None => {
                out.push('&');
                rest = &after[1..];
            }
        }
    }
    out.push_str(rest);
    out
}

/// 解一个实体名（不含 `&` 与 `;`）。返回 `(字符, 该实体在原文里占的字节数)`
fn decode_entity(body: &str) -> Option<(char, usize)> {
    let consumed = body.len() + 2; // & + body + ;
    if let Some(hex) = body.strip_prefix("#x").or_else(|| body.strip_prefix("#X")) {
        let v = u32::from_str_radix(hex, 16).ok()?;
        return Some((char::from_u32(v)?, consumed));
    }
    if let Some(dec) = body.strip_prefix('#') {
        let v: u32 = dec.parse().ok()?;
        return Some((char::from_u32(v)?, consumed));
    }
    named_entity(body).map(|c| (c, consumed))
}

/// 命名实体表：**HTML4 全集（253 条）**，取值方式见下。
///
/// 为什么是全集、而且必须"问 .NET 要"：C# 宿主用的是 `WebUtility.HtmlDecode`（.NET 的实体表），
/// 而真页面上的 `Z&uuml;rich`、`caf&eacute;`、`&hellip;` 都得解出来才不影响可读性。
/// 原先手写的 114 条子集在真站点上会漏 —— 而假端点夹具是纯 ASCII，**这套用例永远测不出来**。
/// 所以这里逐条由下面这一句产出，与 C# 宿主逐字一致：
///
/// ```text
/// [System.Net.WebUtility]::HtmlDecode("&uuml;")   ->  ü
/// ```
///
/// （`&apos;` 严格说不在 HTML4 里，但 .NET 会解，所以以 C# 为准一并收下。
/// 要增删就照上面这个办法重新生成，**别手抄** —— 手抄过一次，漏了 `&amp; &lt; &gt; &quot;`。）
///
/// 注：命名与数字实体都**必须带分号**才解。这一点也与 .NET 一致（实测 `&uuml`、`&#39`
/// 都不解），所以 `html_decode` 只认带分号的写法不是保守，而是对齐。
fn named_entity(name: &str) -> Option<char> {
    Some(match name {
        // ── 基础（XML/HTML 核心 —— .NET 也解 apos，所以以 C# 为准一并收下）
        "amp" => '&',
        "lt" => '<',
        "gt" => '>',
        "quot" => '"',
        "apos" => '\'',

        // ── Latin-1（西欧语言，真页面标题里常见：Z&uuml;rich / caf&eacute;）
        "nbsp" => '\u{a0}',
        "iexcl" => '¡',
        "cent" => '¢',
        "pound" => '£',
        "curren" => '¤',
        "yen" => '¥',
        "brvbar" => '¦',
        "sect" => '§',
        "uml" => '¨',
        "copy" => '©',
        "ordf" => 'ª',
        "laquo" => '«',
        "not" => '¬',
        "shy" => '\u{ad}',
        "reg" => '®',
        "macr" => '¯',
        "deg" => '°',
        "plusmn" => '±',
        "sup2" => '²',
        "sup3" => '³',
        "acute" => '´',
        "micro" => 'µ',
        "para" => '¶',
        "middot" => '·',
        "cedil" => '¸',
        "sup1" => '¹',
        "ordm" => 'º',
        "raquo" => '»',
        "frac14" => '¼',
        "frac12" => '½',
        "frac34" => '¾',
        "iquest" => '¿',
        "Agrave" => 'À',
        "Aacute" => 'Á',
        "Acirc" => 'Â',
        "Atilde" => 'Ã',
        "Auml" => 'Ä',
        "Aring" => 'Å',
        "AElig" => 'Æ',
        "Ccedil" => 'Ç',
        "Egrave" => 'È',
        "Eacute" => 'É',
        "Ecirc" => 'Ê',
        "Euml" => 'Ë',
        "Igrave" => 'Ì',
        "Iacute" => 'Í',
        "Icirc" => 'Î',
        "Iuml" => 'Ï',
        "ETH" => 'Ð',
        "Ntilde" => 'Ñ',
        "Ograve" => 'Ò',
        "Oacute" => 'Ó',
        "Ocirc" => 'Ô',
        "Otilde" => 'Õ',
        "Ouml" => 'Ö',
        "times" => '×',
        "Oslash" => 'Ø',
        "Ugrave" => 'Ù',
        "Uacute" => 'Ú',
        "Ucirc" => 'Û',
        "Uuml" => 'Ü',
        "Yacute" => 'Ý',
        "THORN" => 'Þ',
        "szlig" => 'ß',
        "agrave" => 'à',
        "aacute" => 'á',
        "acirc" => 'â',
        "atilde" => 'ã',
        "auml" => 'ä',
        "aring" => 'å',
        "aelig" => 'æ',
        "ccedil" => 'ç',
        "egrave" => 'è',
        "eacute" => 'é',
        "ecirc" => 'ê',
        "euml" => 'ë',
        "igrave" => 'ì',
        "iacute" => 'í',
        "icirc" => 'î',
        "iuml" => 'ï',
        "eth" => 'ð',
        "ntilde" => 'ñ',
        "ograve" => 'ò',
        "oacute" => 'ó',
        "ocirc" => 'ô',
        "otilde" => 'õ',
        "ouml" => 'ö',
        "divide" => '÷',
        "oslash" => 'ø',
        "ugrave" => 'ù',
        "uacute" => 'ú',
        "ucirc" => 'û',
        "uuml" => 'ü',
        "yacute" => 'ý',
        "thorn" => 'þ',
        "yuml" => 'ÿ',

        // ── 希腊字母与符号
        "fnof" => 'ƒ',
        "Alpha" => 'Α',
        "Beta" => 'Β',
        "Gamma" => 'Γ',
        "Delta" => 'Δ',
        "Epsilon" => 'Ε',
        "Zeta" => 'Ζ',
        "Eta" => 'Η',
        "Theta" => 'Θ',
        "Iota" => 'Ι',
        "Kappa" => 'Κ',
        "Lambda" => 'Λ',
        "Mu" => 'Μ',
        "Nu" => 'Ν',
        "Xi" => 'Ξ',
        "Omicron" => 'Ο',
        "Pi" => 'Π',
        "Rho" => 'Ρ',
        "Sigma" => 'Σ',
        "Tau" => 'Τ',
        "Upsilon" => 'Υ',
        "Phi" => 'Φ',
        "Chi" => 'Χ',
        "Psi" => 'Ψ',
        "Omega" => 'Ω',
        "alpha" => 'α',
        "beta" => 'β',
        "gamma" => 'γ',
        "delta" => 'δ',
        "epsilon" => 'ε',
        "zeta" => 'ζ',
        "eta" => 'η',
        "theta" => 'θ',
        "iota" => 'ι',
        "kappa" => 'κ',
        "lambda" => 'λ',
        "mu" => 'μ',
        "nu" => 'ν',
        "xi" => 'ξ',
        "omicron" => 'ο',
        "pi" => 'π',
        "rho" => 'ρ',
        "sigmaf" => 'ς',
        "sigma" => 'σ',
        "tau" => 'τ',
        "upsilon" => 'υ',
        "phi" => 'φ',
        "chi" => 'χ',
        "psi" => 'ψ',
        "omega" => 'ω',
        "thetasym" => 'ϑ',
        "upsih" => 'ϒ',
        "piv" => 'ϖ',

        // ── 排版与标点
        "OElig" => 'Œ',
        "oelig" => 'œ',
        "Scaron" => 'Š',
        "scaron" => 'š',
        "Yuml" => 'Ÿ',
        "circ" => 'ˆ',
        "tilde" => '˜',
        "ensp" => '\u{2002}',
        "emsp" => '\u{2003}',
        "thinsp" => '\u{2009}',
        "zwnj" => '\u{200c}',
        "zwj" => '\u{200d}',
        "lrm" => '\u{200e}',
        "rlm" => '\u{200f}',
        "ndash" => '–',
        "mdash" => '—',
        "lsquo" => '‘',
        "rsquo" => '’',
        "sbquo" => '‚',
        "ldquo" => '“',
        "rdquo" => '”',
        "bdquo" => '„',
        "dagger" => '†',
        "Dagger" => '‡',
        "permil" => '‰',
        "lsaquo" => '‹',
        "rsaquo" => '›',
        "euro" => '€',
        "bull" => '•',
        "hellip" => '…',
        "prime" => '′',
        "Prime" => '″',
        "oline" => '‾',
        "frasl" => '⁄',

        // ── 数学与集合
        "weierp" => '℘',
        "image" => 'ℑ',
        "real" => 'ℜ',
        "trade" => '™',
        "alefsym" => 'ℵ',
        "larr" => '←',
        "uarr" => '↑',
        "rarr" => '→',
        "darr" => '↓',
        "harr" => '↔',
        "crarr" => '↵',
        "lArr" => '⇐',
        "uArr" => '⇑',
        "rArr" => '⇒',
        "dArr" => '⇓',
        "hArr" => '⇔',
        "forall" => '∀',
        "part" => '∂',
        "exist" => '∃',
        "empty" => '∅',
        "nabla" => '∇',
        "isin" => '∈',
        "notin" => '∉',
        "ni" => '∋',
        "prod" => '∏',
        "sum" => '∑',
        "minus" => '−',
        "lowast" => '∗',
        "radic" => '√',
        "prop" => '∝',
        "infin" => '∞',
        "ang" => '∠',
        "and" => '∧',
        "or" => '∨',
        "cap" => '∩',
        "cup" => '∪',
        "int" => '∫',
        "there4" => '∴',
        "sim" => '∼',
        "cong" => '≅',
        "asymp" => '≈',
        "ne" => '≠',
        "equiv" => '≡',
        "le" => '≤',
        "ge" => '≥',
        "sub" => '⊂',
        "sup" => '⊃',
        "nsub" => '⊄',
        "sube" => '⊆',
        "supe" => '⊇',
        "oplus" => '⊕',
        "otimes" => '⊗',
        "perp" => '⊥',
        "sdot" => '⋅',
        "lceil" => '⌈',
        "rceil" => '⌉',
        "lfloor" => '⌊',
        "rfloor" => '⌋',
        "lang" => '〈',
        "rang" => '〉',
        "loz" => '◊',
        "spades" => '♠',
        "clubs" => '♣',
        "hearts" => '♥',
        "diams" => '♦',

        _ => return None,
    })
}

/// 结果 URL 的闸门：只接受 http/https。
/// `shellopen::is_allowed` 做的是**真正的 URL 解析**，所以 `javascript:location='https://x'`
/// 这种混进来的串也挡得住（`starts_with` 那种写法挡不住）。
pub fn is_http_url(url: &str) -> bool {
    shellopen::is_allowed(url)
}

/// 百分号解码（`uddg=` 参数用）。解出非 UTF-8 就返回 None，由调用方退回原串。
fn percent_decode(s: &str) -> Option<String> {
    let b = s.as_bytes();
    let mut out: Vec<u8> = Vec::with_capacity(b.len());
    let mut i = 0usize;
    while i < b.len() {
        if b[i] == b'%' && i + 2 < b.len() {
            let hi = (b[i + 1] as char).to_digit(16);
            let lo = (b[i + 2] as char).to_digit(16);
            if let (Some(hi), Some(lo)) = (hi, lo) {
                out.push((hi * 16 + lo) as u8);
                i += 3;
                continue;
            }
        }
        out.push(b[i]);
        i += 1;
    }
    String::from_utf8(out).ok()
}

/// 百分号编码。**空格编成 `%20` 而不是 `+`**：与 C# 的 `Uri.EscapeDataString` 一致，
/// 也让同一份拼接能安全地用在路径与查询串两处。
fn urlencode(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for b in s.as_bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(*b as char)
            }
            _ => out.push_str(&format!("%{b:02X}")),
        }
    }
    out
}

/* ══════════════════════════════════════════════════════════════════════════
 * ⑥ 解析器（最容易随对方改版而碎的一层，所以每一处"闸门"都写明为什么）
 * ══════════════════════════════════════════════════════════════════════════ */

/// DDG 的结果链接会包一层跳转（`//duckduckgo.com/l/?uddg=…`），把真实地址解出来。
/// 只在 `?`/`&` 之后认 `uddg=`（否则链接里随便一段文字都可能被当成跳转参数）。
pub fn real_url(href: &str) -> String {
    let mut h = href.trim().to_string();
    if h.starts_with("//") {
        h = format!("https:{h}");
    }
    let mut from = 0usize;
    while let Some(at) = find_ci(&h, "uddg=", from) {
        let preceded = at > 0 && matches!(h.as_bytes()[at - 1], b'?' | b'&');
        if preceded {
            let start = at + 5;
            let end = h[start..].find('&').map(|o| start + o).unwrap_or(h.len());
            let raw = &h[start..end];
            // C# 的 Uri.UnescapeDataString：解不出来就退回原串（宁可打不开，也不给错地址）
            return percent_decode(raw).unwrap_or(h);
        }
        from = at + 5;
    }
    h
}

/// 扫出「打开标签里含 marker 的那些元素」：返回 `(标签体, 元素文本)`。
///
/// 对应 C# 的两条正则：
///   · 标题 `<a(?<tag>[^>]*result__a[^>]*)>(?<text>.*?)</a>`
///   · 摘要 `<(a|div)(?<tag>[^>]*result__snippet[^>]*)>(?<text>.*?)</\1>`
/// `[^>]*` = "标签里不能有 `>`"，也就是"读到第一个 `>` 为止"；`.*?` + Singleline = "读到最近的
/// 闭合标签为止"。所以这里的扫描与那两条正则**是同一套语义**。
///
/// ⚠ `allow_div` **必须照 C# 分开**：标题那条正则写的是 `<a…`，只认 `<a>`；
/// 只有摘要那条是 `<(a|div)…`。这不是细节洁癖 —— 真页面里 `<div class="result__a">`
/// 这种写法一旦出现，放宽的那一侧就会多抓一条（甚至错抓整块容器）。
///
/// ⚠ 至于"要不要干脆用 `regex` crate 把那两条模式原样搬过来"：**不划算**。
/// C# 摘要那条用了反引用 `</\1>`（要求开闭标签同名），而 `regex` crate 不支持反引用，
/// 搬过来只能退化成 `</(?:a|div)>`，反而比现在这段扫描更松。所以这里保持手写扫描
///（它本来就已经做到"开闭标签配对"），只在 `allow_div` 这一处按 C# 收紧。
///
/// ⚠ `cap` 是**扫描上限**而不是结果上限：C# 会一直扫到 `list.Count == max` 为止，
/// 中间被丢掉的（坏协议链接、空标题）不占名额。这里给 `max` 留 8 倍余量，够用又不至于
/// 在畸形页面上扫出一大堆字符串。
fn scan_tag_texts(html: &str, marker: &str, cap: usize, allow_div: bool) -> Vec<(String, String)> {
    let mut out: Vec<(String, String)> = Vec::new();
    let mut pos = 0usize;
    while out.len() < cap {
        // 同时找 `<a` 与 `<div`，取更靠前的那个（DDG 的结果块两种都出现过；标题只认前者）
        let head_div = if allow_div { find_ci(html, "<div", pos) } else { None };
        let (start, close) = match (find_ci(html, "<a", pos), head_div) {
            (None, None) => break,
            (Some(x), None) => (x, "</a>"),
            (None, Some(y)) => (y, "</div>"),
            (Some(x), Some(y)) => {
                if x <= y {
                    (x, "</a>")
                } else {
                    (y, "</div>")
                }
            }
        };
        let Some(tag_end) = html[start..].find('>').map(|o| start + o) else { break };
        let tag = &html[start..tag_end];
        if find_ci(tag, marker, 0).is_none() {
            pos = tag_end + 1;
            continue;
        }
        let from = tag_end + 1;
        let Some(close_at) = find_ci(html, close, from) else { break };
        // 非贪婪：**最近**的闭合标签。嵌套的 div 也就跟着停在第一个 `</div>`
        out.push((tag.to_string(), html[from..close_at].to_string()));
        pos = close_at + close.len();
    }
    out
}

/// 从 DDG 的 HTML 结果页抽结果。**只抽文本**，URL 只接受 http/https。
pub fn parse_ddg_html(html: &str, max: usize) -> Vec<SearchResult> {
    let mut list = Vec::new();
    if html.is_empty() || max == 0 {
        return list;
    }
    let cap = max.saturating_mul(8).saturating_add(32);
    let titles = scan_tag_texts(html, "result__a", cap, false);   // C#: 标题只认 <a>
    let snippets = scan_tag_texts(html, "result__snippet", cap, true); // C#: 摘要认 <a> 或 <div>

    for (i, (tag, text)) in titles.iter().enumerate() {
        if list.len() >= max {
            break;
        }
        let href = attr_value(tag, "href").map(|h| html_decode(&h)).unwrap_or_default();
        let href = real_url(&href);
        if !is_http_url(&href) {
            continue; // javascript:/data: 一律丢弃
        }
        let title = strip_tags(text);
        if title.is_empty() {
            continue;
        }
        // 摘要按下标配对（C# 也是 `snippets[i]`）：DDG 的结果页是一标题一摘要交替的
        let snippet = snippets.get(i).map(|(_, t)| strip_tags(t)).unwrap_or_default();
        list.push(SearchResult {
            title: clip(&title, 200),
            url: href,
            snippet: clip(&snippet, 400),
            source: "DuckDuckGo".to_string(),
        });
    }
    list
}

/// DDG 的 Instant Answer：概念类查询的摘要（"什么是黎曼猜想"这种最有用）。
/// 依次认 `AbstractText` / `Answer` / `Definition`；拿不到就返回空串（**不是错误**）。
pub fn parse_ddg_abstract(json_text: &str) -> String {
    let Ok(v) = serde_json::from_str::<Value>(json_text) else { return String::new() };
    for name in ["AbstractText", "Answer", "Definition"] {
        if let Some(s) = v.get(name).and_then(|x| x.as_str()) {
            let t = strip_tags(s);
            if !t.is_empty() {
                return clip(&t, 600);
            }
        }
    }
    String::new()
}

/// 自定义端点（SearXNG 兼容 JSON）。不是 JSON / 没有 `results` 数组 → Err，由调用方归类为 `parse`。
pub fn parse_searxng(json_text: &str, max: usize) -> Result<Vec<SearchResult>, String> {
    let v: Value = serde_json::from_str(json_text).map_err(|e| e.to_string())?;
    let arr = v
        .get("results")
        .and_then(|x| x.as_array())
        .ok_or_else(|| "没有 results 数组".to_string())?;
    let mut list = Vec::new();
    for item in arr {
        if list.len() >= max {
            break;
        }
        let s = |k: &str| item.get(k).and_then(|x| x.as_str()).unwrap_or("").to_string();
        let url = s("url");
        if !is_http_url(&url) {
            continue; // 非 http(s) 的 url 一律丢弃
        }
        let engine = s("engine");
        list.push(SearchResult {
            title: clip(&strip_tags(&s("title")), 200),
            url,
            snippet: clip(&strip_tags(&s("content")), 400),
            source: if engine.is_empty() { "自定义".to_string() } else { engine },
        });
    }
    Ok(list)
}

/* ══════════════════════════════════════════════════════════════════════════
 * ⑦ 三个后端
 *
 *   · duckduckgo —— 免密钥。**两个请求**：HTML 结果页（真的结果列表）+ Instant Answer
 *     JSON（概念类摘要）。IA 失败不影响结果页。
 *   · wolfram    —— 短答案 API（`/v1/result` 返回纯文本），需要用户自备 App ID。
 *   · custom     —— SearXNG 兼容的 JSON 接口（自建/自选实例）。
 *
 * 请求本身**复用 site.rs** 的 `get()`：它已经把失败分成
 * `unauthorized / ratelimit / http / timeout / aborted / network`，并带"下一步怎么办"的文案。
 * 这里只做一层**语义翻译**（见 `kind_of`），不再重写一遍分类。
 * ⚠ 因此请求头是共享客户端那份（`MF-Mathematics/<版本>`），而不是 C# 搜索专用的浏览器 UA ——
 *   这是有意的取舍：宁可复用一处分类，也不为了 UA 再养一份 HTTP 栈（见交付说明）。
 * ══════════════════════════════════════════════════════════════════════════ */

struct Outcome {
    ok: bool,
    engine: String,
    abstract_text: String,
    results: Vec<SearchResult>,
    error_kind: String,
    error: String,
    status: i32,
}

impl Outcome {
    fn success(engine: &str) -> Self {
        Outcome {
            ok: true,
            engine: engine.to_string(),
            abstract_text: String::new(),
            results: Vec::new(),
            error_kind: String::new(),
            error: String::new(),
            status: 0,
        }
    }

    fn failure(engine: &str, kind: &str, message: String, status: i32) -> Self {
        Outcome {
            ok: false,
            engine: engine.to_string(),
            abstract_text: String::new(),
            results: Vec::new(),
            error_kind: kind.to_string(),
            error: message,
            status,
        }
    }
}

/// 整次搜索共享一份超时预算。
///
/// C# 是一个 `CancellationTokenSource(TimeoutSec)` 覆盖"先 IA 再 HTML"两路请求；
/// 若给每个请求各算一次超时，DDG 那条最坏会等 2×超时，用户看到的分类也就不是他设的那个数。
fn remaining_budget(timeout_sec: i64, started: Instant) -> i64 {
    let used = started.elapsed().as_secs() as i64;
    timeout_sec - used
}

fn timeout_message(timeout_sec: i64) -> String {
    format!("超过 {timeout_sec} 秒没有返回（可在设置 → 搜索里调大）")
}

fn aborted(engine: &str) -> Outcome {
    Outcome::failure(engine, "aborted", "已取消".to_string(), 0)
}

/// 把 `site.rs` 的分类翻成搜索桥的分类。
/// 两套 kind 的含义其实一致，只有两点要说明：
///   · `unauthorized`（401/403）在搜索里**不能**一律叫"没登录"：对 DDG/SearXNG 而言那是
///     "端点拒绝/被反爬"，所以并进 `http`；Wolfram 那条另有单独判断（→ `config`）。
///   · `ratelimit`（429）对界面来说是同一类建议："稍后再试/换个端点"，同样并进 `http`。
fn kind_of(call: &site::ApiCall) -> &'static str {
    match call.kind {
        "timeout" => "timeout",
        "aborted" => "aborted",
        "unauthorized" | "ratelimit" | "http" => "http",
        _ => "network",
    }
}

/// 失败的 HTTP 文案：`HTTP <状态>` + 状态码专属提示 + 站点给的原因（`site::detail_of` 取过）。
fn http_message(call: &site::ApiCall) -> String {
    let status = call.status;
    let hint = match status {
        202 | 403 => "（端点拒绝了这次请求，可能是反爬限制；可换自定义端点）",
        429 => "（请求太频繁，稍后再试）",
        _ => "",
    };
    let detail = call.error.trim();
    if status <= 0 {
        // 没有状态码 = 连接层失败：直接用 site.rs 那句"下一步怎么办"
        return detail.to_string();
    }
    if detail.is_empty() || detail == format!("HTTP {status}") {
        format!("HTTP {status}{hint}")
    } else {
        format!("HTTP {status}{hint}：{detail}")
    }
}

fn failure_from(engine: &str, call: &site::ApiCall, timeout_sec: i64) -> Outcome {
    let kind = kind_of(call);
    let message = match kind {
        "timeout" => timeout_message(timeout_sec),
        "aborted" => "已取消".to_string(),
        "network" => call.error.clone(),
        _ => http_message(call),
    };
    Outcome::failure(engine, kind, message, call.status)
}

/// 自定义端点的闸门。
///
/// **为什么不能省**：`site::get()` 会对 base URL 做规范化，遇到不认识的值会**退回站点默认地址**
/// —— 那意味着查询词会被发到完全不相干的服务器上去（隐私事故，不是功能问题）。
/// 所以这里先自己挡一道：只接受 http/https，且不许带查询串/片段/用户信息。
fn custom_url_ok(url: &str) -> bool {
    let s = url.trim();
    let lower = s.to_ascii_lowercase();
    (lower.starts_with("http://") || lower.starts_with("https://"))
        && !s.contains('?')
        && !s.contains('#')
        && !s.contains('@')
}

/// 按引擎跑一次搜索。`cancel` 是**这一路搜索自己的**取消标记（不是 site.rs 那个全局闸门）。
fn run(c: &SearchConfig, key: &str, query: &str, cancel: &AtomicBool) -> Outcome {
    let mut q = query.trim().to_string();
    if q.is_empty() {
        return Outcome::failure(&c.engine, "config", "查询为空".to_string(), 0);
    }
    if q.chars().count() > MAX_QUERY_CHARS {
        q = q.chars().take(MAX_QUERY_CHARS).collect();
    }
    match c.engine.as_str() {
        "wolfram" => wolfram(c, key, &q, cancel),
        "custom" => searxng(c, &q, cancel),
        _ => duckduckgo(c, &q, cancel),
    }
}

fn duckduckgo(c: &SearchConfig, q: &str, cancel: &AtomicBool) -> Outcome {
    let engine = "duckduckgo";
    let started = Instant::now();
    let mut outcome = Outcome::success(engine);

    /* ① Instant Answer：概念类摘要。**尽力而为** —— 它挂了不该影响结果列表。
     *    但取消/超时要原样抛出去：那是"整次搜索"的状态，不是"这一路拿不到摘要"。 */
    if cancel.load(Ordering::SeqCst) {
        return aborted(engine);
    }
    let left = remaining_budget(c.timeout_sec, started);
    if left <= 0 {
        return Outcome::failure(engine, "timeout", timeout_message(c.timeout_sec), 0);
    }
    let ia_path = format!(
        "/?q={}&format=json&no_html=1&skip_disambig=1&no_redirect=1",
        urlencode(q)
    );
    let call = site::get_ua(&ddg_ia_endpoint(), &ia_path, None, left, Some(crate::http::BROWSER_UA));
    if !call.ok {
        match call.kind {
            "timeout" | "aborted" => return failure_from(engine, &call, c.timeout_sec),
            _ => { /* 其它失败忽略：结果页才是主体 */ }
        }
    } else {
        outcome.abstract_text = parse_ddg_abstract(&call.body);
    }

    // ② HTML 结果页
    if cancel.load(Ordering::SeqCst) {
        return aborted(engine);
    }
    let left = remaining_budget(c.timeout_sec, started);
    if left <= 0 {
        return Outcome::failure(engine, "timeout", timeout_message(c.timeout_sec), 0);
    }
    let html_path = format!("/?q={}&kl=wt-wt", urlencode(q));
    let call = site::get_ua(&ddg_html_endpoint(), &html_path, None, left, Some(crate::http::BROWSER_UA));
    if !call.ok {
        // 结果页被拒时，如果 IA 有摘要就还算成功（至少给了点东西）
        if !outcome.abstract_text.is_empty() {
            return outcome;
        }
        return failure_from(engine, &call, c.timeout_sec);
    }

    outcome.results = parse_ddg_html(&call.body, c.result_count.max(1) as usize);
    if outcome.results.is_empty() && outcome.abstract_text.is_empty() {
        // "形状不像结果页"（改版/被拦截）与"确实没有结果"要分开说：前者该换端点，后者不是错误。
        // 判据与 C# 一致：页面短得不像结果页 **且** 连一个结果块的类名都没有。
        if call.body.len() < 2000 && !call.body.contains("result__a") {
            return Outcome::failure(
                engine,
                "parse",
                "DuckDuckGo 返回的页面里没有结果块（可能改版或被拦截），可改用自定义端点".to_string(),
                0,
            );
        }
    }
    outcome
}

fn wolfram(c: &SearchConfig, key: &str, q: &str, cancel: &AtomicBool) -> Outcome {
    let engine = "wolfram";
    if key.trim().is_empty() {
        return Outcome::failure(
            engine,
            "config",
            "Wolfram 需要 App ID：去「设置 → 搜索」填一个，或改用 DuckDuckGo / 自定义端点".to_string(),
            0,
        );
    }
    if cancel.load(Ordering::SeqCst) {
        return aborted(engine);
    }

    // ⚠ App ID 只在这里拼进 URL，且只发给"宿主自己认定的"那个端点（环境变量覆盖只有启动者能设）
    let path = format!("?appid={}&i={}", urlencode(key.trim()), urlencode(q));
    let call = site::get_ua(&wolfram_endpoint(), &path, None, c.timeout_sec, Some(crate::http::BROWSER_UA));
    if !call.ok {
        return match call.status {
            401 | 403 => Outcome::failure(
                engine,
                "config",
                format!("App ID 无效或被拒绝（HTTP {}）", call.status),
                call.status,
            ),
            501 => Outcome::failure(
                engine,
                "config",
                "Wolfram 没有理解这个查询（它返回 501）".to_string(),
                call.status,
            ),
            _ => failure_from(engine, &call, c.timeout_sec),
        };
    }

    let mut outcome = Outcome::success(engine);
    // `/v1/result` 回的就是一段纯文本；仍然过一遍 strip_tags —— 谁也不能保证它永远不带标记
    let answer = clip(strip_tags(&call.body).trim(), 1000);
    if !answer.is_empty() {
        outcome.abstract_text = answer.clone();
        outcome.results.push(SearchResult {
            title: "Wolfram Alpha 简答".to_string(),
            url: format!("https://www.wolframalpha.com/input?i={}", urlencode(q)),
            snippet: answer,
            source: "Wolfram Alpha".to_string(),
        });
    }
    outcome
}

fn searxng(c: &SearchConfig, q: &str, cancel: &AtomicBool) -> Outcome {
    let engine = "custom";
    if c.custom_url.trim().is_empty() {
        return Outcome::failure(
            engine,
            "config",
            "自定义端点还没填（需要一个 SearXNG 之类的 JSON 接口）".to_string(),
            0,
        );
    }
    if !custom_url_ok(&c.custom_url) {
        return Outcome::failure(
            engine,
            "config",
            // ⚠ 这里**刻意比 C# 严**（C# 只有"空就报错"），而且是有意的：
            //   基址是 `origin + 可选路径前缀`，我们再往后拼 `/search?q=…&format=json`
            //   （与 C# 的 `CustomUrl + "/search?q=…"` 逐字一致）。所以基址里带 `?` 会拼成
            //   `https://x/?a=1/search?q=…` —— C# 会照拼、然后以一个莫名其妙的错误收场，
            //   我们在这里直接说清"该怎么填"。`#` 之后的内容 HTTP 客户端根本不会发；
            //   `@` 能塞用户信息/伪装主机（`https://evil@real`），一律拒。
            "自定义端点要填成「站点前缀」：http/https、不能带查询串/片段/用户信息\
             （本软件会在它后面拼 /search?q=…&format=json）".to_string(),
            0,
        );
    }
    if cancel.load(Ordering::SeqCst) {
        return aborted(engine);
    }

    let path = format!("/search?q={}&format=json", urlencode(q));
    // ⚠ 用 get_verbatim 而不是 site::get_ua：后者会过 normalize_base_url，
    // 而它对坏值的处理是**退回内置站点** —— 那等于把用户的查询词发到我们自己的服务器上。
    let call = site::get_verbatim(&c.custom_url, &path, c.timeout_sec, Some(crate::http::BROWSER_UA));
    if !call.ok {
        return failure_from(engine, &call, c.timeout_sec);
    }

    match parse_searxng(&call.body, c.result_count.max(1) as usize) {
        Ok(results) => {
            let mut outcome = Outcome::success(engine);
            outcome.results = results;
            outcome
        }
        Err(_) => Outcome::failure(
            engine,
            "parse",
            "自定义端点没有返回 SearXNG 形状的 JSON（很多实例默认关闭 format=json）".to_string(),
            0,
        ),
    }
}

/* ══════════════════════════════════════════════════════════════════════════
 * ⑧ 作业与进程内状态
 *
 * **为什么作业表里不存查询词**：那样诊断包、崩溃现场里就会多一份"用户搜过什么"的记录。
 * 这里只留取消标记与运行状态 —— 够用，且少一处隐私面。
 * ══════════════════════════════════════════════════════════════════════════ */

struct Job {
    id: String,
    /// 这一路搜索自己的取消标记（不碰 `site.rs` 那个全局闸门，见 `start()` 的说明）
    cancelled: Arc<AtomicBool>,
    running: bool,
}

/// 同时保留的作业数上限：`Jobs` 只增不减会慢慢攒住已经结束的条目
const MAX_JOBS: usize = 64;

static JOBS: Mutex<Vec<Job>> = Mutex::new(Vec::new());
static SEQ: AtomicI64 = AtomicI64::new(0);
/// DPAPI 不可用时的兜底（**只留内存，不写明文**）
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

fn running() -> usize {
    JOBS.lock().map(|g| g.iter().filter(|j| j.running).count()).unwrap_or(0)
}

fn finish_job(id: &str) {
    let mut g = JOBS.lock().unwrap_or_else(|e| e.into_inner());
    for j in g.iter_mut() {
        if j.id == id {
            j.running = false;
            break;
        }
    }
}

fn push_done(
    id: &str,
    engine: &str,
    results: &[SearchResult],
    abstract_text: &str,
    from_cache: bool,
    elapsed_ms: i64,
    cached_at: i64,
) {
    let payload = json!({
        "requestId": id,
        "engine": engine,
        "fromCache": from_cache,
        "cachedAt": cached_at,
        "elapsedMs": elapsed_ms,
        "abstract": abstract_text,
        "results": results,
    });
    push::send("search.done", &payload.to_string());
}

fn push_error(id: &str, kind: &str, message: &str, status: i32) {
    set_last_error(&format!("{kind}: {message}"));
    let payload = json!({
        "requestId": id,
        "kind": kind,
        "status": status,
        "message": message,
    });
    push::send("search.error", &payload.to_string());
}

/// 一次搜索的完整流程（在**自己的线程**上跑）。形状与 C# 的 `Task.Run` 逐条对齐：
/// ① 查缓存（命中就完全不出网）→ ② 抓取 → ③ **有结果才**写缓存 → 推 `search.done`。
fn run_job(id: &str, query: &str, engine: &str, cancel: &Arc<AtomicBool>, no_cache: bool) {
    let sw = Instant::now();
    let c = cfg(); // 用"开始那一刻"的配置快照：中途改设置不该影响这一路
    let key = resolve_key();

    // ① 缓存（键含引擎；命中就完全不出网）
    if !no_cache && c.cache_enabled {
        if let Some(entry) = cache_get(engine, query, &c) {
            push_done(
                id,
                engine,
                &entry.results,
                &entry.abstract_text,
                true,
                sw.elapsed().as_millis() as i64,
                entry.at,
            );
            finish_job(id);
            return;
        }
    }

    // ② 抓取。超时与"用户取消"分开：收尾时才能说清是谁取消的
    let outcome = run(&c, &key, query, cancel);

    // ⚠ 取消要**先于**"拿到了什么"判断：用户按下停止之后回来的响应**不再采用**
    //   （blocking 客户端没有中断句柄，能做的到这一步；与 jobs.rs 的"停止等待"同一套说法）
    if cancel.load(Ordering::SeqCst) {
        push_error(id, "aborted", "已取消", 0);
        finish_job(id);
        return;
    }
    if !outcome.ok {
        let (kind, message) = if outcome.error_kind == "aborted" {
            ("aborted".to_string(), "已取消".to_string())
        } else {
            (outcome.error_kind.clone(), outcome.error.clone())
        };
        push_error(id, &kind, &message, outcome.status);
        finish_job(id);
        return;
    }

    // ③ 有结果才写缓存（空结果不缓存：下次还该再试一次）
    if c.cache_enabled && (!outcome.results.is_empty() || !outcome.abstract_text.is_empty()) {
        cache_put(engine, query, &outcome.abstract_text, &outcome.results);
    }

    push_done(
        id,
        &outcome.engine, // 用"实际跑过的那条后端"回报（与请求参数一致，但以结果为准）
        &outcome.results,
        &outcome.abstract_text,
        false,
        sw.elapsed().as_millis() as i64,
        0,
    );
    finish_job(id);
}

/* ══════════════════════════════════════════════════════════════════════════
 * ⑨ 桥面
 * ══════════════════════════════════════════════════════════════════════════ */

fn fail(message: &str) -> String {
    json!({ "ok": false, "error": message }).to_string()
}

fn ok_with(extra: Value) -> String {
    match extra {
        Value::Object(m) => {
            let mut out = Map::new();
            out.insert("ok".into(), json!(true));
            for (k, v) in m {
                out.insert(k, v);
            }
            Value::Object(out).to_string()
        }
        _ => json!({ "ok": true }).to_string(),
    }
}

/// 面板上要**明说查询会发往哪个站点**（隐私说明不是装饰）。
///
/// ⚠ 这里是有意**写死**的说明文字（C# 也是）：如果它跟着 `MF_SEARCH_ENDPOINTS` 变成
/// "http://127.0.0.1:8792"，那真实用户看到的就不再是"我要把查询发给谁"，
/// 而用例断言的"隐私行写明发往哪里"也就失去意义了。生效端点另有 `endpoints` 字段可查。
fn endpoint_of(c: &SearchConfig) -> String {
    match c.engine.as_str() {
        "wolfram" => "api.wolframalpha.com（会带上你的 App ID）".to_string(),
        "custom" => {
            if c.custom_url.trim().is_empty() {
                "（自定义端点未填）".to_string()
            } else {
                c.custom_url.clone()
            }
        }
        _ => "html.duckduckgo.com + api.duckduckgo.com（免密钥）".to_string(),
    }
}

/// 生效端点的**来源**（scheme://host，不含路径与查询串）——只写进 app.log，
/// 用来回答"这台机器当时把查询发去哪儿了"。
fn endpoint_origin(c: &SearchConfig) -> String {
    match c.engine.as_str() {
        "wolfram" => http::origin_of(&wolfram_endpoint()),
        "custom" => http::origin_of(&c.custom_url),
        _ => format!(
            "{} + {}",
            http::origin_of(&ddg_html_endpoint()),
            http::origin_of(&ddg_ia_endpoint())
        ),
    }
}

fn resolve_key() -> String {
    let mem = memory_key();
    if !mem.is_empty() {
        return mem;
    }
    let c = cfg();
    if c.wolfram_key_protected.is_empty() {
        return String::new();
    }
    dpapi::unprotect(&c.wolfram_key_protected).unwrap_or_default()
}

fn key_source() -> &'static str {
    if !memory_key().is_empty() {
        "memory"
    } else if !cfg().wolfram_key_protected.is_empty() {
        "dpapi"
    } else {
        "none"
    }
}

/// 脱敏状态：**永远不返回 App ID 本身**，只说有没有、从哪来。
pub fn info() -> String {
    let c = cfg();
    let src = key_source();
    json!({
        "engine": c.engine,
        "customUrl": c.custom_url,
        "timeoutSec": c.timeout_sec,
        "resultCount": c.result_count,
        "cacheEnabled": c.cache_enabled,
        "cacheTtlHours": c.cache_ttl_hours,
        "hasWolframKey": src != "none",
        "wolframKeySource": src,
        "dpapiAvailable": dpapi::selftest(),
        "configLoadFailed": c.load_failed,
        "configPath": config_path().to_string_lossy(),
        "lastError": last_error(),
        "running": running(),
        // 面板上要明说查询会发往哪个站点（隐私说明不是装饰）
        "endpoint": endpoint_of(&c),
        // 生效端点（不是凭据，公开地址）：设置面板与端到端用例都靠它确认"到底发去哪儿"。
        // 覆盖只走环境变量 MF_SEARCH_ENDPOINTS —— 页面能改端点就等于能把 App ID 发到任意地址。
        "endpoints": {
            "ddgHtml": ddg_html_endpoint(),
            "ddgIa": ddg_ia_endpoint(),
            "wolfram": wolfram_endpoint(),
        },
        "cache": cache_stats_value(),
    })
    .to_string()
}

/// 改配置。只认类型对得上的字段（字符串/数字/布尔），一个都没给就 `changed:0`。
pub fn configure(json_text: &str) -> String {
    let Ok(v) = serde_json::from_str::<Value>(json_text) else {
        return fail("配置解析失败：不是合法 JSON");
    };
    let mut cur = cfg();
    let mut changed = false;
    if let Some(s) = v.get("engine").and_then(|x| x.as_str()) {
        cur.engine = s.to_string();
        changed = true;
    }
    if let Some(s) = v.get("customUrl").and_then(|x| x.as_str()) {
        cur.custom_url = s.to_string();
        changed = true;
    }
    if let Some(n) = v.get("timeoutSec").and_then(|x| x.as_i64()) {
        cur.timeout_sec = n;
        changed = true;
    }
    if let Some(n) = v.get("resultCount").and_then(|x| x.as_i64()) {
        cur.result_count = n;
        changed = true;
    }
    if let Some(b) = v.get("cacheEnabled").and_then(|x| x.as_bool()) {
        cur.cache_enabled = b;
        changed = true;
    }
    if let Some(n) = v.get("cacheTtlHours").and_then(|x| x.as_i64()) {
        cur.cache_ttl_hours = n;
        changed = true;
    }
    if !changed {
        return ok_with(json!({ "changed": 0 }));
    }
    cur.normalize();
    if let Err(e) = cur.save() {
        return fail(&format!("写入配置失败：{e}"));
    }
    // 立刻刷新内存里的那份（否则后面的搜索还在用旧引擎/旧端点）
    with_cfg(|c| *c = cur.clone());
    ok_with(json!({ "changed": 1 }))
}

/// 设置 Wolfram App ID。**只写不读**（同 AI 密钥那条规矩）。
pub fn set_wolfram_key(key: &str) -> String {
    if key.trim().is_empty() {
        return fail("App ID 为空");
    }
    let trimmed = key.trim().to_string();

    match dpapi::protect(&trimmed) {
        Some(blob) => {
            let mut cur = cfg();
            cur.wolfram_key_protected = blob;
            if let Err(e) = cur.save() {
                return fail(&format!("已加密但写入配置失败：{e}"));
            }
            with_cfg(|c| *c = cur);
            if let Ok(mut g) = MEMORY_KEY.lock() {
                g.clear();
            }
            ok_with(json!({ "persisted": true }))
        }
        None => {
            // ⚠ DPAPI 不可用时**绝不降级成明文落盘**：只留内存，并明确告诉用户重启后要重填
            if let Ok(mut g) = MEMORY_KEY.lock() {
                *g = trimmed;
            }
            ok_with(json!({
                "persisted": false,
                "warning": "DPAPI 在本机不可用：App ID 只保留在本次运行的内存里（重启后需重填），不会写明文到磁盘。",
            }))
        }
    }
}

/// 清掉 App ID（内存与密文一起清）
pub fn clear_wolfram_key() -> String {
    if let Ok(mut g) = MEMORY_KEY.lock() {
        g.clear();
    }
    let mut cur = cfg();
    cur.wolfram_key_protected.clear();
    if let Err(e) = cur.save() {
        return fail(&format!("清除失败：{e}"));
    }
    with_cfg(|c| *c = cur);
    ok_with(Value::Null)
}

/// 发起一次搜索，**立即返回**（结果经 push 推回去）。
/// 入参：`{"query":"…","engine":"duckduckgo|wolfram|custom","noCache":false}`
pub fn start(json_text: &str) -> String {
    let Ok(v) = serde_json::from_str::<Value>(json_text) else {
        return fail("请求解析失败：不是合法 JSON");
    };
    let query = v.get("query").and_then(|x| x.as_str()).unwrap_or("").trim().to_string();
    let engine_arg = v.get("engine").and_then(|x| x.as_str()).unwrap_or("").to_string();
    let no_cache = v.get("noCache").and_then(|x| x.as_bool()).unwrap_or(false);

    if query.is_empty() {
        return fail("查询为空");
    }

    let c = cfg();
    let engine = if engine_arg.trim().is_empty() { c.engine.clone() } else { engine_arg };
    let engine = if matches!(engine.as_str(), "duckduckgo" | "wolfram" | "custom") {
        engine
    } else {
        "duckduckgo".to_string()
    };

    let id = format!("s{}", SEQ.fetch_add(1, Ordering::SeqCst) + 1);
    let cancelled = Arc::new(AtomicBool::new(false));
    {
        let mut jobs = JOBS.lock().unwrap_or_else(|e| e.into_inner());
        jobs.push(Job { id: id.clone(), cancelled: cancelled.clone(), running: true });
        // 只留最近 64 个：先把"已结束里最旧的"丢掉，运行中的一个都不动
        if jobs.len() > MAX_JOBS {
            let over = jobs.len() - MAX_JOBS;
            let mut dropped = 0usize;
            let mut kept: Vec<Job> = Vec::with_capacity(jobs.len());
            for j in jobs.drain(..) {
                if dropped < over && !j.running {
                    dropped += 1;
                    continue;
                }
                kept.push(j);
            }
            *jobs = kept;
        }
    }

    /* site.rs 的取消标记是**三个桥共用**的一个全局闸门（账号的 CancelAll 会置位）。
     * 用户按的这次是"搜索"，理应把闸门复位 —— 否则账号侧一次 CancelAll 之后，
     * 搜索会一路报"已取消"却根本没出网（那种"点了没反应"最难查）。
     * 搜索自己那一路的取消走 `cancelled`，**不动**这个全局标记。 */
    site::arm();

    // 只记"发往哪个来源"，**不记查询词**：查询词属于用户，不该被诊断包带走
    logging::info(&format!("search.Start {} engine={engine} origin={}", id, endpoint_origin(&c)));

    let job_id = id.clone();
    let query2 = query.clone();
    let engine2 = engine.clone();
    let cancel2 = cancelled.clone();
    let spawned = std::thread::Builder::new()
        .name(format!("mf-search-{job_id}"))
        .spawn(move || run_job(&job_id, &query2, &engine2, &cancel2, no_cache));

    if let Err(e) = spawned {
        finish_job(&id);
        return fail(&format!("起不了搜索线程：{e}"));
    }

    json!({ "ok": true, "requestId": id, "engine": engine }).to_string()
}

pub fn cancel(request_id: &str) -> String {
    let jobs = JOBS.lock().unwrap_or_else(|e| e.into_inner());
    match jobs.iter().find(|j| j.id == request_id) {
        Some(j) => {
            j.cancelled.store(true, Ordering::SeqCst);
            ok_with(Value::Null)
        }
        None => fail("没有这个请求"),
    }
}

/// 取消所有在跑的搜索。**已在飞的那一个不会被强杀**（blocking 客户端没有中断句柄），
/// 效果是"回来的响应不再采用、后续请求不再发起"——文案与 `jobs.rs` 的停止语义一致。
pub fn cancel_all() -> String {
    let jobs = JOBS.lock().unwrap_or_else(|e| e.into_inner());
    let mut n = 0;
    for j in jobs.iter() {
        if !j.running {
            continue;
        }
        j.cancelled.store(true, Ordering::SeqCst);
        n += 1;
    }
    ok_with(json!({ "cancelled": n }))
}

pub fn is_busy() -> bool {
    running() > 0
}

/// 用系统默认浏览器打开一个链接。**闸门在 `shellopen`**（只放行 http/https）：
/// 否则这就成了"用任意协议启动本机程序"的原语（`file:`、`ms-*:`、自定义协议都能被利用）。
pub fn open_url(url: &str) -> String {
    match shellopen::open(url) {
        Ok(()) => ok_with(Value::Null),
        Err(e) => fail(&e),
    }
}

/* ══════════════════════════════════════════════════════════════════════════
 * ⑩ 自检（**不联网**）
 *
 * 五项：解析器拿内置样本跑（DDG HTML / DDG IA / SearXNG JSON）、缓存键含引擎 + TTL、
 * OpenUrl 协议闸门。解析器是最容易随对方改版而碎的一层，所以它必须能在不联网的情况下被验。
 * ══════════════════════════════════════════════════════════════════════════ */

pub fn self_check() -> String {
    let mut checks: Vec<Value> = Vec::new();
    let mut all = true;
    let add = |checks: &mut Vec<Value>, name: &str, ok: bool, detail: String| {
        checks.push(json!({ "name": name, "ok": ok, "detail": detail }));
    };

    // ① DDG HTML 解析（跳转链接还原 + 去标签 + **解实体** + 标题只认 <a> + 丢弃 javascript: 链接）
    //
    // ⚠ 实体这几条是**补上去的**：假端点夹具是纯 ASCII，`cdp-search` 那 55 项**一条实体都不覆盖**，
    // 而真页面上 `Z&uuml;rich`、`caf&eacute;`、`&hellip;` 到处都是 —— 实体表缺条目时，
    // 整套用例照样全绿。所以把"解 Latin-1/排版符号"与"缺分号不解"钉在这里。
    const DDG_HTML: &str = "<html><body>\
        <a rel=\"nofollow\" class=\"result__a\" href=\"//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fx&amp;rut=1\">示例 <b>标题</b></a>\
        <a class=\"result__snippet\" href=\"x\">示例 <b>摘要</b> 文本</a>\
        <a class=\"result__a\" href=\"https://example.com/z\">Z&uuml;rich &hellip; caf&eacute;</a>\
        <a class=\"result__snippet\" href=\"x\">缺分号的实体 caf&eacute 原样留着</a>\
        <div class=\"result__a\" href=\"https://evil.example/d\">不该被当成标题</div>\
        <a class=\"result__a\" href=\"javascript:alert(1)\">坏链接</a>\
        </body></html>";
    let parsed = parse_ddg_html(DDG_HTML, 8);
    let ddg_ok = parsed.len() == 2
        && parsed[0].url == "https://example.com/x"
        && parsed[0].title == "示例 标题"
        && parsed[0].snippet == "示例 摘要 文本"
        // 实体表：Latin-1 与排版符号都要解出来（`Z&uuml;rich &hellip; caf&eacute;` → `Zürich … café`）
        && parsed[1].title == "Zürich … café"
        // 缺分号的写法**不解**（与 .NET 的 HtmlDecode 实测一致：`&uuml`、`&#39`、`&#x27` 都不解）
        && parsed[1].snippet == "缺分号的实体 caf&eacute 原样留着"
        // 标题只认 `<a>`（C# 那条正则就是 `<a…`）：`<div class="result__a">` 不能被抓成一条结果
        && !parsed.iter().any(|r| r.title.contains("不该被当成标题"));
    all &= ddg_ok;
    add(
        &mut checks,
        "DuckDuckGo 结果解析",
        ddg_ok,
        if ddg_ok {
            "跳转链接还原 + 去标签 + 解实体（含缺分号不解）+ 标题只认 <a> + 丢弃 javascript: 链接 都正确"
                .to_string()
        } else {
            format!("内置样本解析不符合预期：{} 条 {:?}", parsed.len(), parsed.iter().map(|r| &r.title).collect::<Vec<_>>())
        },
    );

    // ② DDG Instant Answer 摘要
    let ia = parse_ddg_abstract("{\"AbstractText\":\"<b>黎曼猜想</b>是关于 ζ 函数零点的猜想。\"}");
    let ia_ok = ia == "黎曼猜想 是关于 ζ 函数零点的猜想。";
    all &= ia_ok;
    add(
        &mut checks,
        "Instant Answer 摘要解析",
        ia_ok,
        if ia_ok { "取 AbstractText 并去标签".to_string() } else { "摘要解析不符合预期".to_string() },
    );

    // ③ SearXNG JSON 解析
    const SEARX: &str = "{\"results\":[{\"title\":\"甲\",\"url\":\"https://a.example\",\"content\":\"内容\",\"engine\":\"google\"}\
        ,{\"title\":\"坏\",\"url\":\"data:text/html,x\",\"content\":\"\",\"engine\":\"\"}]}";
    let sx_ok = match parse_searxng(SEARX, 8) {
        Ok(r) => r.len() == 1 && r[0].title == "甲" && r[0].url == "https://a.example",
        Err(_) => false,
    };
    all &= sx_ok;
    add(
        &mut checks,
        "SearXNG JSON 解析",
        sx_ok,
        if sx_ok { "取 results 并丢弃非 http(s) 的 url".to_string() } else { "解析不符合预期".to_string() },
    );

    // ④ 缓存键必须含引擎（v1 的缺陷：换引擎仍然命中旧结果）
    let key_ok = {
        cache_put(
            "__selftest_a__",
            "x",
            "",
            &[SearchResult {
                title: "t".to_string(),
                url: "https://e.com".to_string(),
                ..Default::default()
            }],
        );
        let mut c = SearchConfig { cache_enabled: true, cache_ttl_hours: 24, ..Default::default() };
        c.normalize();
        let hit_a = cache_get("__selftest_a__", "x", &c).is_some();
        let hit_b = cache_get("__selftest_b__", "x", &c).is_some(); // 换了引擎
        let miss_c = cache_get("__selftest_a__", "y", &c).is_some(); // 换了查询
        hit_a && !hit_b && !miss_c
    };
    all &= key_ok;
    add(
        &mut checks,
        "缓存键含引擎 + TTL",
        key_ok,
        if key_ok {
            "同引擎同查询命中；换引擎或换查询都不命中（v1 只用查询词做键，换了引擎不生效）".to_string()
        } else {
            "缓存键或命中判定不符合预期".to_string()
        },
    );

    // ⑤ OpenUrl 只放行 http(s)
    let url_ok = is_http_url("https://example.com")
        && is_http_url("http://example.com")
        && !is_http_url("javascript:alert(1)")
        && !is_http_url("file:///C:/Windows/System32/cmd.exe")
        && !is_http_url("ms-settings:")
        && !is_http_url("");
    all &= url_ok;
    add(
        &mut checks,
        "打开链接只放行 http/https",
        url_ok,
        if url_ok {
            "javascript: / file: / ms-* 一律拒绝（否则成了用任意协议启动本机程序的原语）".to_string()
        } else {
            "协议闸门判定不正确".to_string()
        },
    );

    json!({ "ok": true, "checks": checks, "ok_all": all }).to_string()
}