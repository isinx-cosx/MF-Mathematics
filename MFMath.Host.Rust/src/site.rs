//! site.rs —— **站点契约**的公共层（`account` / `update` / `search` 共用）
//!
//! 三件事在这里只实现一份：
//!   · **站点地址与超时的来源**：设置文件 `account.json`（与 C# `AccountConfig` 同样的
//!     默认值 `https://mf-vis-science.cn` / 20 s 与同样的规范化）；
//!   · **带错误分类的请求**：`kind` 取 `unauthorized`/`ratelimit`/`http`/`timeout`/`aborted`/
//!     `network`，与 C# `AccountApi.Send` 逐条对应 —— 界面靠它给出"下一步怎么办"，
//!     所以分类不能合并成一句"请求失败"；
//!   · **失败原因的取法**：优先站点约定的 `{detail}`，其次 `{msg}`，最后截断原文。
//!
//! ⚠ 站点地址的规范化不是洁癖：这个值决定 token 被发到哪儿。能塞进 `https://evil@host`
//! 之类就麻烦了，所以 `?`/`#`/`@` 一律退回默认站点（与 C# 同一套判断）。

use std::sync::atomic::{AtomicBool, Ordering};

use serde_json::Value;

use crate::http;

/// 生产站点（与 C# `AccountConfig.BaseUrl` 默认值一致）
pub const DEFAULT_BASE_URL: &str = "https://mf-vis-science.cn";

/// 全局取消标记：`CancelAll` 置位，新的请求不再发起；**已在飞的那一个不会被强杀**
/// （blocking 客户端没有中断句柄）—— 语义与 jobs.rs 的"停止等待"一致，文案也要照此写。
static CANCELLED: AtomicBool = AtomicBool::new(false);

pub fn cancel_all() {
    CANCELLED.store(true, Ordering::SeqCst);
}

pub fn arm() {
    CANCELLED.store(false, Ordering::SeqCst);
}

pub fn is_cancelled() -> bool {
    CANCELLED.load(Ordering::SeqCst)
}

/// 站点配置（`account.json` 里的 `baseUrl` / `timeoutSec`）
#[derive(Clone)]
pub struct SiteConfig {
    pub base_url: String,
    pub timeout_sec: i64,
}

impl SiteConfig {
    /// 从设置文件读；文件不存在/坏掉都用默认值（**离线也要能起来**）
    pub fn load() -> Self {
        let raw = crate::sys::store_read_value("account");
        let base = raw
            .as_ref()
            .and_then(|v| v.get("baseUrl"))
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let timeout = raw
            .as_ref()
            .and_then(|v| v.get("timeoutSec"))
            .and_then(|v| v.as_i64())
            .unwrap_or(20);
        SiteConfig {
            base_url: normalize_base_url(base),
            timeout_sec: if (5..=120).contains(&timeout) { timeout } else { 20 },
        }
    }

}

/// 站点地址规范化：只接受 http/https，且不能带查询串/片段/用户信息
pub fn normalize_base_url(url: &str) -> String {
    let s = url.trim();
    if s.is_empty() {
        return DEFAULT_BASE_URL.to_string();
    }
    let lower = s.to_ascii_lowercase();
    if !lower.starts_with("http://") && !lower.starts_with("https://") {
        return DEFAULT_BASE_URL.to_string();
    }
    let s = s.trim_end_matches('/');
    if s.contains('?') || s.contains('#') || s.contains('@') {
        return DEFAULT_BASE_URL.to_string();
    }
    s.to_string()
}

/// 一次请求的结果（与 C# `AccountCall` 同形）
pub struct ApiCall {
    pub ok: bool,
    pub body: String,
    pub kind: &'static str,
    pub error: String,
    /// HTTP 状态码（0 = 没到服务器：网络/超时/取消）。
    /// 搜索要拿它区分语义（如 Wolfram 的 501 = 没理解查询），所以不能只留错误文案。
    pub status: i32,
}

impl ApiCall {
    fn ok(status: i32, body: String) -> Self {
        ApiCall { ok: true, body, kind: "", error: String::new(), status }
    }
    fn err(status: i32, body: String, kind: &'static str, error: String) -> Self {
        ApiCall { ok: false, body, kind, error, status }
    }
}

/// GET 一个站内路径（宿主自己的 UA）
pub fn get(base_url: &str, path: &str, token: Option<&str>, timeout_sec: i64) -> ApiCall {
    get_ua(base_url, path, token, timeout_sec, None)
}

/// GET 一个站内路径，并**指定 User-Agent**（搜索专用：DDG 挑 UA，见 `http::BROWSER_UA`）。
/// 其余行为与 `get` 完全一致 —— 尤其是错误分类，别在这里分叉。
pub fn get_ua(base_url: &str, path: &str, token: Option<&str>, timeout_sec: i64, ua: Option<&str>) -> ApiCall {
    if is_cancelled() {
        return ApiCall::err(0, String::new(), "aborted", "已取消".into());
    }
    let url = format!("{}{}", normalize_base_url(base_url).trim_end_matches('/'), path);
    let client = http::client_with_timeout_ua(timeout_sec, ua);
    let mut req = client.get(&url);
    if let Some(t) = token.filter(|t| !t.is_empty()) {
        req = req.header("Authorization", format!("Bearer {t}"));
    }
    finish(req.send())
}

/// POST（`content_type` 为 `application/json` 或 `application/x-www-form-urlencoded`）
pub fn post(
    base_url: &str,
    path: &str,
    content_type: &str,
    body: String,
    token: Option<&str>,
    timeout_sec: i64,
) -> ApiCall {
    if is_cancelled() {
        return ApiCall::err(0, String::new(), "aborted", "已取消".into());
    }
    let url = format!("{}{}", normalize_base_url(base_url).trim_end_matches('/'), path);
    let client = http::client_with_timeout(timeout_sec);
    let mut req = client.post(&url).header("Content-Type", content_type).body(body);
    if let Some(t) = token.filter(|t| !t.is_empty()) {
        req = req.header("Authorization", format!("Bearer {t}"));
    }
    finish(req.send())
}

fn finish(sent: Result<reqwest::blocking::Response, reqwest::Error>) -> ApiCall {
    let resp = match sent {
        Ok(r) => r,
        Err(e) => {
            let (kind, msg) = classify(&e);
            return ApiCall::err(0, String::new(), kind, msg);
        }
    };
    let status = resp.status().as_u16() as i32;
    let body = resp.text().unwrap_or_default();
    if (200..300).contains(&status) {
        return ApiCall::ok(status, body);
    }
    let kind = match status {
        401 | 403 => "unauthorized",
        429 => "ratelimit",
        _ => "http",
    };
    let detail = detail_of(&body, status);
    ApiCall::err(status, body, kind, detail)
}

/// 把 reqwest 的错误翻成"下一步怎么办"能用的分类与文案
fn classify(e: &reqwest::Error) -> (&'static str, String) {
    if e.is_timeout() {
        return ("timeout", format!("超过 {} 秒没有响应", 0).replace(" 0 ", " "));
    }
    if e.is_connect() {
        // 连接层面失败：把最常见的原因说清楚，而不是丢一句英文
        let s = e.to_string();
        let hint = if s.contains("refused") || s.contains("os error 10061") {
            "服务器拒绝连接（地址/端口不对，或服务没起）"
        } else if s.contains("dns") || s.contains("Name or service not known") || s.contains("11001") {
            "找不到服务器地址（检查网络或站点地址）"
        } else if s.contains("10060") {
            "连接超时"
        } else {
            "连不上服务器"
        };
        return ("network", hint.to_string());
    }
    ("network", e.to_string())
}

/// 失败信息：优先 `{detail}`（站点约定），其次 `{msg}`，最后退回截断的原文
pub fn detail_of(body: &str, status: i32) -> String {
    let v: Option<Value> = serde_json::from_str(body).ok();
    if let Some(v) = &v {
        for k in ["detail", "msg", "message", "error"] {
            if let Some(s) = v.get(k).and_then(|x| x.as_str()) {
                if !s.trim().is_empty() {
                    return s.to_string();
                }
            }
        }
    }
    let t = body.trim();
    if t.is_empty() {
        return if status == 0 { "请求失败".into() } else { format!("HTTP {status}") };
    }
    t.chars().take(200).collect()
}

/// 从（可能带信封的）JSON 文本里取一个字符串字段
pub fn json_str(body: &str, key: &str) -> String {
    serde_json::from_str::<Value>(body)
        .ok()
        .and_then(|v| v.get(key).and_then(|x| x.as_str()).map(|s| s.to_string()))
        .unwrap_or_default()
}

/// 取站点信封里的 `data`（站点是 `{code,data,msg}`；平铺结构则原样返回）
pub fn unwrap_data(v: &Value) -> Value {
    match v.get("data") {
        Some(d) if d.is_object() => d.clone(),
        _ => v.clone(),
    }
}
