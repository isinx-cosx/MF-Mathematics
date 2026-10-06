//! account.rs —— 用户系统桥（对照 C# `AccountBridge.cs` + `AccountApi.cs`）
//!
//! 这一层是"软件与服务器之间的那条线"，C# 注释里把纪律写得很好，照搬：
//!
//! ① **离线优先，绝不阻塞**：`info()` 只读内存/本地缓存、**从不等网络**（自检里有一项就是
//!    量它）。未登录、断网都不影响任何计算功能 —— 计算全在本地 C++ 引擎里。
//! ② **token 只在宿主**：DPAPI 密文落盘，页面只见 `loggedIn` / `username` 这类脱敏字段。
//! ③ **不合并失败**：站点的 `{detail}` 原样带给用户（"用户名或密码错误"），并区分
//!    unauthorized / ratelimit / http / network / timeout / aborted。
//! ④ **静默续期**（`ensure_fresh`）：临期前用 `/api/token/refresh` 换新 token，
//!    免得用户每 30 分钟被踢一次；续期失败**不弹错误**，只把状态标成需要重新登录。
//!
//! ⚠ 一条照搬的坑：**改了 baseUrl 或 remember 之后必须重新 Load**，否则"页面改了设置、
//! 宿主还在用旧值"（C# 注释里记着这个）。这里每次用 `cfg()` 从缓存取、`configure()` 落盘后
//! 立即刷新缓存。

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Mutex, OnceLock};

use base64::Engine;
use serde_json::{json, Map, Value};

use crate::{dpapi, pack, push, site, update};

/// 设置文件里的账号配置（字段名与 C# `AccountConfig` 的 camelCase 一致 —— 两个宿主共用同一份）
#[derive(Clone, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "camelCase", default)]
pub struct AccountConfig {
    pub base_url: String,
    pub timeout_sec: i64,
    pub remember: bool,
    pub auto_refresh: bool,
    /// DPAPI 密文（base64）。**绝不出现在任何返回给页面的 JSON 里**
    pub token_protected: String,
    pub username: String,
    pub email: String,
    pub balance: i64,
    pub has_ai_service: bool,
    pub role: i64,
    pub is_active: bool,
    pub session_expires_at: i64,
    pub profile_verified: bool,
    pub profile_checked_at: i64,
}

impl Default for AccountConfig {
    fn default() -> Self {
        AccountConfig {
            base_url: site::DEFAULT_BASE_URL.to_string(),
            timeout_sec: 20,
            remember: true,
            auto_refresh: true,
            token_protected: String::new(),
            username: String::new(),
            email: String::new(),
            balance: 0,
            has_ai_service: false,
            role: 0,
            is_active: false,
            session_expires_at: 0,
            profile_verified: false,
            profile_checked_at: 0,
        }
    }
}

impl AccountConfig {
    fn normalize(&mut self) {
        self.base_url = site::normalize_base_url(&self.base_url);
        if self.timeout_sec < 5 {
            self.timeout_sec = 20;
        }
        if self.timeout_sec > 120 {
            self.timeout_sec = 120;
        }
    }

    fn load() -> Self {
        match crate::sys::store_read_value("account") {
            Some(v) => {
                let mut c: AccountConfig =
                    serde_json::from_value(v).unwrap_or_default();
                c.normalize();
                c
            }
            None => AccountConfig::default(),
        }
    }

    fn save(&self) -> Result<(), String> {
        let text = serde_json::to_string_pretty(self).map_err(|e| e.to_string())?;
        let r = crate::sys::store_write("account", &text);
        let v: Value = serde_json::from_str(&r).unwrap_or(Value::Null);
        if v.get("ok").and_then(|b| b.as_bool()).unwrap_or(false) {
            Ok(())
        } else {
            Err(v.get("error").and_then(|s| s.as_str()).unwrap_or("写入配置失败").to_string())
        }
    }
}

/* ── 进程内状态 ─────────────────────────────────────────────────────────── */

static CFG: OnceLock<Mutex<AccountConfig>> = OnceLock::new();
static MEMORY_TOKEN: Mutex<String> = Mutex::new(String::new());
static LAST_ERROR: Mutex<String> = Mutex::new(String::new());
static LAST_ERROR_KIND: Mutex<String> = Mutex::new(String::new());
static OFFLINE: AtomicBool = AtomicBool::new(false);
static BUSY_OP: Mutex<String> = Mutex::new(String::new());

fn cfg_slot() -> &'static Mutex<AccountConfig> {
    CFG.get_or_init(|| Mutex::new(AccountConfig::load()))
}

fn cfg() -> AccountConfig {
    cfg_slot().lock().map(|c| c.clone()).unwrap_or_default()
}

fn with_cfg<R>(f: impl FnOnce(&mut AccountConfig) -> R) -> R {
    let mut g = cfg_slot().lock().unwrap_or_else(|e| e.into_inner());
    f(&mut g)
}

fn persist() {
    let c = cfg();
    let _ = c.save();
}

fn set_last_error(msg: &str, kind: &str) {
    if let Ok(mut g) = LAST_ERROR.lock() {
        *g = msg.to_string();
    }
    if let Ok(mut g) = LAST_ERROR_KIND.lock() {
        *g = kind.to_string();
    }
}
fn last_error() -> String {
    LAST_ERROR.lock().map(|g| g.clone()).unwrap_or_default()
}
fn last_error_kind() -> String {
    LAST_ERROR_KIND.lock().map(|g| g.clone()).unwrap_or_default()
}
fn busy() -> String {
    BUSY_OP.lock().map(|g| g.clone()).unwrap_or_default()
}
fn set_busy(op: &str) {
    if let Ok(mut g) = BUSY_OP.lock() {
        *g = op.to_string();
    }
}

fn ok_with(extra: Value) -> String {
    match extra {
        Value::Null => json!({ "ok": true }).to_string(),
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

fn fail(msg: &str, kind: &str) -> String {
    set_last_error(msg, kind);
    json!({ "ok": false, "kind": kind, "error": msg }).to_string()
}

/* ── token 与脱敏 ───────────────────────────────────────────────────────── */

fn resolve_token() -> String {
    let mem = MEMORY_TOKEN.lock().map(|g| g.clone()).unwrap_or_default();
    if !mem.is_empty() {
        return mem;
    }
    let c = cfg();
    if c.token_protected.is_empty() {
        return String::new();
    }
    dpapi::unprotect(&c.token_protected).unwrap_or_default()
}

/// 存 token：DPAPI 可用就落盘密文，否则**只留内存**（绝不写明文）。返回 (是否落盘, 警告)
fn store_token(token: &str) -> (bool, String) {
    match dpapi::protect(token) {
        Some(blob) => {
            with_cfg(|c| c.token_protected = blob);
            if let Ok(mut g) = MEMORY_TOKEN.lock() {
                g.clear();
            }
            (true, String::new())
        }
        None => {
            if let Ok(mut g) = MEMORY_TOKEN.lock() {
                *g = token.to_string();
            }
            (
                false,
                "DPAPI 在本机不可用：登录状态只保留在本次运行的内存里（重启后需重新登录）。".to_string(),
            )
        }
    }
}

fn clear_token() {
    if let Ok(mut g) = MEMORY_TOKEN.lock() {
        g.clear();
    }
    with_cfg(|c| {
        c.token_protected.clear();
        c.session_expires_at = 0;
        c.profile_verified = false;
    });
}

fn push_changed(why: &str) {
    let env = json!({ "reason": why, "info": serde_json::from_str::<Value>(&info()).unwrap_or(Value::Null) });
    push::send("account.changed", &env.to_string());
}

/* ── Info（脱敏，绝不碰网络）────────────────────────────────────────────── */

pub fn info() -> String {
    let c = cfg();
    let has_token = !resolve_token().is_empty();
    let now = now_ms();
    json!({
        "baseUrl": c.base_url,
        "timeoutSec": c.timeout_sec,
        "remember": c.remember,
        "autoRefresh": c.auto_refresh,
        "loggedIn": has_token,
        "username": c.username,
        "email": c.email,
        "balance": c.balance,
        "hasAiService": c.has_ai_service,
        "role": c.role,
        "isActive": c.is_active,
        "sessionExpiresAt": c.session_expires_at,
        "sessionExpiresInSec": if c.session_expires_at > 0 { ((c.session_expires_at - now) / 1000).max(0) } else { 0 },
        // 断网时资料来自缓存 —— 明确标出来，不假装是刚校验过的
        "profileVerified": c.profile_verified,
        "profileCheckedAt": c.profile_checked_at,
        "offline": OFFLINE.load(Ordering::SeqCst),
        "dpapiAvailable": dpapi::selftest(),
        "tokenSource": if !MEMORY_TOKEN.lock().map(|g| g.clone()).unwrap_or_default().is_empty() {
            "memory"
        } else if !c.token_protected.is_empty() { "dpapi" } else { "none" },
        "busy": busy(),
        "lastError": last_error(),
        "lastErrorKind": last_error_kind(),
        "configPath": crate::logging::data_dir().join("settings/account.json").to_string_lossy(),
    })
    .to_string()
}

fn now_ms() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

/* ── 配置 ───────────────────────────────────────────────────────────────── */

pub fn configure(json_text: &str) -> String {
    let Ok(v) = serde_json::from_str::<Value>(json_text) else {
        return fail("配置解析失败：不是合法 JSON", "config");
    };
    let mut cur = cfg();
    let mut changed = false;
    if let Some(s) = v.get("baseUrl").and_then(|x| x.as_str()) {
        cur.base_url = s.to_string();
        changed = true;
    }
    if let Some(n) = v.get("timeoutSec").and_then(|x| x.as_i64()) {
        cur.timeout_sec = n;
        changed = true;
    }
    if let Some(b) = v.get("remember").and_then(|x| x.as_bool()) {
        cur.remember = b;
        changed = true;
    }
    if let Some(b) = v.get("autoRefresh").and_then(|x| x.as_bool()) {
        cur.auto_refresh = b;
        changed = true;
    }
    if !changed {
        return ok_with(json!({ "changed": 0 }));
    }
    cur.normalize();
    if let Err(e) = cur.save() {
        return fail(&format!("写入配置失败：{e}"), "config");
    }
    // 立刻刷新缓存（否则后续调用还在用旧站点地址）
    with_cfg(|c| *c = cur.clone());
    site::arm();
    ok_with(json!({ "changed": 1, "baseUrl": cur.base_url }))
}

/// 清掉本地登录状态（**不发网络请求**）
pub fn clear_local() -> String {
    clear_token();
    with_cfg(|c| {
        c.username.clear();
        c.email.clear();
        c.balance = 0;
        c.has_ai_service = false;
        c.role = 0;
        c.is_active = false;
        c.profile_checked_at = 0;
    });
    persist();
    push_changed("cleared");
    ok_with(Value::Null)
}

/* ── 资料 / JWT ─────────────────────────────────────────────────────────── */

/// 把 `/api/me` 的公开用户填进配置缓存
fn apply_profile(body: &str, c: &mut AccountConfig) -> bool {
    let Ok(u) = serde_json::from_str::<Value>(body) else { return false };
    if !u.is_object() {
        return false;
    }
    let s = |k: &str| u.get(k).and_then(|v| v.as_str()).unwrap_or("").to_string();
    let i = |k: &str| u.get(k).and_then(|v| v.as_i64()).unwrap_or(0);
    let b = |k: &str| u.get(k).and_then(|v| v.as_bool()).unwrap_or(false);
    c.username = s("username");
    c.email = s("email");
    c.balance = i("balance");
    c.has_ai_service = b("has_ai_service");
    // role: 站点给 0/1/2；也接受 true/false
    c.role = if u.get("role").and_then(|v| v.as_bool()) == Some(true) { 1 } else { i("role") };
    c.is_active = b("is_active");
    c.profile_verified = true;
    c.profile_checked_at = now_ms();
    !c.username.is_empty()
}

/// 解 JWT payload 里的 exp（**不校验签名**）。只用于决定何时静默续期。
pub fn jwt_exp(token: &str) -> Option<i64> {
    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() < 2 {
        return None;
    }
    let mut payload = parts[1].replace('-', "+").replace('_', "/");
    while payload.len() % 4 != 0 {
        payload.push('=');
    }
    let bytes = base64::engine::general_purpose::STANDARD.decode(payload).ok()?;
    let text = String::from_utf8(bytes).ok()?;
    let v: Value = serde_json::from_str(&text).ok()?;
    v.get("exp").and_then(|e| e.as_i64())
}

/// 到期时刻（unix ms）：优先 `expires_in`，退路是解 JWT 的 `exp`
fn expiry_from(body: &str, token: &str) -> i64 {
    let sec = serde_json::from_str::<Value>(body)
        .ok()
        .and_then(|v| v.get("expires_in").and_then(|e| e.as_i64()))
        .unwrap_or(0);
    if sec > 0 {
        return now_ms() + sec * 1000;
    }
    jwt_exp(token).map(|e| e * 1000).unwrap_or(0)
}

/// 登录历史 → 只取认识的字段透传给页面
pub fn normalize_history(body: &str, max: usize) -> String {
    let Ok(v) = serde_json::from_str::<Value>(body) else {
        return "[]".into();
    };
    let arr = if v.is_array() {
        v.as_array().cloned().unwrap_or_default()
    } else {
        v.get("items").and_then(|i| i.as_array()).cloned().unwrap_or_default()
    };
    let mut out = Vec::new();
    for it in arr.into_iter().take(max) {
        let s = |k: &str| it.get(k).and_then(|x| x.as_str()).unwrap_or("").to_string();
        let at = {
            let a = s("login_at");
            if a.is_empty() { s("at") } else { a }
        };
        let ua = {
            let u = s("user_agent");
            if u.chars().count() > 120 { u.chars().take(120).collect::<String>() + "…" } else { u }
        };
        out.push(json!({ "at": at, "ip": s("ip"), "ua": ua }));
    }
    Value::Array(out).to_string()
}

/* ── 请求结果的统一处理 ─────────────────────────────────────────────────── */

fn note_failure(call: &site::ApiCall, soft: bool) {
    let msg = if soft {
        format!("已登录，但没取到资料：{}", call.error)
    } else {
        call.error.clone()
    };
    set_last_error(&msg, call.kind);
    if call.kind == "network" || call.kind == "timeout" {
        OFFLINE.store(true, Ordering::SeqCst);
    } else if call.kind != "aborted" {
        OFFLINE.store(false, Ordering::SeqCst);
    }
}

fn form(fields: &[(&str, &str)]) -> String {
    fields
        .iter()
        .map(|(k, v)| format!("{}={}", urlencode(k), urlencode(v)))
        .collect::<Vec<_>>()
        .join("&")
}

fn urlencode(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for b in s.as_bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => out.push(*b as char),
            b' ' => out.push('+'),
            _ => out.push_str(&format!("%{b:02X}")),
        }
    }
    out
}

/* ── 登录 / 登出 / 续期 ─────────────────────────────────────────────────── */

pub fn login(username: &str, password: &str) -> String {
    login_ex(&json!({ "username": username, "password": password }).to_string())
}

pub fn login_ex(json_text: &str) -> String {
    let Ok(v) = serde_json::from_str::<Value>(json_text) else {
        return fail("请求解析失败：不是合法 JSON", "config");
    };
    let username = v.get("username").and_then(|x| x.as_str()).unwrap_or("").trim().to_string();
    let password = v.get("password").and_then(|x| x.as_str()).unwrap_or("").to_string();
    let remember = v.get("remember").and_then(|x| x.as_bool());
    if username.is_empty() {
        return fail("用户名不能为空", "config");
    }
    if password.is_empty() {
        return fail("密码不能为空", "config");
    }

    let c = cfg();
    let rem = remember.unwrap_or(c.remember);
    set_busy("login");
    let mut fields = vec![("username", username.as_str()), ("password", password.as_str())];
    if rem {
        fields.push(("remember", "1"));
    }
    let call = site::post(
        &c.base_url,
        "/api/login",
        "application/x-www-form-urlencoded",
        form(&fields),
        None,
        c.timeout_sec,
    );
    if !call.ok {
        note_failure(&call, false);
        set_busy("");
        return fail(&call.error, call.kind);
    }
    let token = site::json_str(&call.body, "access_token");
    if token.is_empty() {
        set_busy("");
        return fail("服务器没有返回 access_token（契约不符）", "parse");
    }
    let (persisted, warning) = store_token(&token);
    let expires = expiry_from(&call.body, &token);
    with_cfg(|cf| {
        cf.session_expires_at = expires;
        cf.remember = rem;
    });

    // 登录成功后立刻取一次资料（失败**不回滚登录**：token 是有效的）
    let me = site::get(&c.base_url, "/api/me", Some(&token), c.timeout_sec);
    if me.ok {
        let mut cur = cfg();
        apply_profile(&me.body, &mut cur);
        with_cfg(|cf| {
            cf.username = cur.username.clone();
            cf.email = cur.email.clone();
            cf.balance = cur.balance;
            cf.has_ai_service = cur.has_ai_service;
            cf.role = cur.role;
            cf.is_active = cur.is_active;
            cf.profile_verified = true;
            cf.profile_checked_at = cur.profile_checked_at;
        });
    } else {
        with_cfg(|cf| cf.profile_verified = false);
        note_failure(&me, true);
    }
    persist();
    OFFLINE.store(false, Ordering::SeqCst);
    set_last_error("", "");
    if !persisted {
        set_last_error(&warning, "dpapi");
    }
    push_changed("login");
    set_busy("");
    let cur = cfg();
    ok_with(json!({
        "username": if cur.username.is_empty() { username } else { cur.username },
        "remember": rem,
        "sessionExpiresAt": cur.session_expires_at,
        "warning": if persisted { String::new() } else { warning },
    }))
}

/// 登出：先通知服务器拉黑 token，再清本地。**服务器不通也照样清本地**（否则断网就退不出去）
pub fn logout() -> String {
    let c = cfg();
    let token = resolve_token();
    let mut server_note = String::new();
    if !token.is_empty() {
        let call = site::post(
            &c.base_url,
            "/api/logout",
            "application/x-www-form-urlencoded",
            String::new(),
            Some(&token),
            c.timeout_sec,
        );
        if !call.ok && call.kind == "network" {
            server_note = "（服务器暂时联系不上，已在本机退出；下次联网时该 token 仍在有效期内，可到站点改密码强制失效）".into();
        }
    }
    clear_token();
    persist();
    push_changed("logout");
    ok_with(json!({ "serverNote": server_note }))
}

/// 用当前 token 取资料（同时校验它还有效）
pub fn refresh_profile() -> String {
    let c = cfg();
    let token = resolve_token();
    if token.is_empty() {
        return fail("尚未登录", "unauthorized");
    }
    let me = site::get(&c.base_url, "/api/me", Some(&token), c.timeout_sec);
    if !me.ok {
        note_failure(&me, false);
        if me.kind == "unauthorized" {
            clear_token();
            persist();
            push_changed("expired");
        } else {
            with_cfg(|cf| cf.profile_verified = false);
            persist();
        }
        return fail(&me.error, me.kind);
    }
    let mut cur = cfg();
    apply_profile(&me.body, &mut cur);
    with_cfg(|cf| {
        cf.username = cur.username.clone();
        cf.email = cur.email.clone();
        cf.balance = cur.balance;
        cf.has_ai_service = cur.has_ai_service;
        cf.role = cur.role;
        cf.is_active = cur.is_active;
        cf.profile_verified = true;
        cf.profile_checked_at = cur.profile_checked_at;
    });
    persist();
    OFFLINE.store(false, Ordering::SeqCst);
    set_last_error("", "");
    push_changed("profile");
    ok_with(json!({ "username": cur.username }))
}

/// 静默续期：临期前换一枚新 token。失败不抛错，只把状态标成需要重新登录
pub fn refresh_token() -> String {
    let c = cfg();
    let token = resolve_token();
    if token.is_empty() {
        return fail("尚未登录", "unauthorized");
    }
    let body = if c.remember { "remember=1".to_string() } else { String::new() };
    let call = site::post(
        &c.base_url,
        "/api/token/refresh",
        "application/x-www-form-urlencoded",
        body,
        Some(&token),
        c.timeout_sec,
    );
    if !call.ok {
        note_failure(&call, false);
        if call.kind == "unauthorized" {
            clear_token();
            persist();
            push_changed("expired");
        }
        return fail(&call.error, call.kind);
    }
    let fresh = site::json_str(&call.body, "access_token");
    if fresh.is_empty() {
        return fail("续期响应里没有 access_token（契约不符）", "parse");
    }
    let _ = store_token(&fresh);
    let exp = expiry_from(&call.body, &fresh);
    with_cfg(|cf| cf.session_expires_at = exp);
    persist();
    push_changed("refreshed");
    ok_with(json!({ "sessionExpiresAt": exp }))
}

/// 临期自动续期（界面在打开时/每次账号操作前调一次即可）。
/// 剩余不足阈值才动手；失败只是返回 false，不影响任何计算功能。
pub fn ensure_fresh(threshold_sec: i64) -> bool {
    let c = cfg();
    if !c.auto_refresh || resolve_token().is_empty() {
        return false;
    }
    if c.session_expires_at <= 0 {
        return false;
    }
    if c.session_expires_at - now_ms() > threshold_sec * 1000 {
        return true;
    }
    refresh_token().starts_with("{\"ok\":true")
}

/* ── 注册与邮箱验证（未登录时可用）──────────────────────────────────────── */

pub fn register(json_text: &str) -> String {
    let c = cfg();
    let call = site::post(&c.base_url, "/api/register", "application/json", json_text.to_string(), None, c.timeout_sec);
    if !call.ok {
        note_failure(&call, false);
        return fail(&call.error, call.kind);
    }
    set_last_error("", "");
    OFFLINE.store(false, Ordering::SeqCst);
    ok_with(json!({ "msg": site::json_str(&call.body, "msg") }))
}

pub fn send_code(email: &str) -> String {
    let c = cfg();
    let body = json!({ "email": email.trim() }).to_string();
    let call = site::post(&c.base_url, "/api/send-code", "application/json", body, None, c.timeout_sec);
    if !call.ok {
        note_failure(&call, false);
        return fail(&call.error, call.kind);
    }
    OFFLINE.store(false, Ordering::SeqCst);
    ok_with(json!({ "msg": site::json_str(&call.body, "msg") }))
}

pub fn verify_code(username: &str, code: &str) -> String {
    let c = cfg();
    let call = site::post(
        &c.base_url,
        "/api/verify-code",
        "application/x-www-form-urlencoded",
        form(&[("username", username.trim()), ("code", code.trim())]),
        None,
        c.timeout_sec,
    );
    if !call.ok {
        note_failure(&call, false);
        return fail(&call.error, call.kind);
    }
    OFFLINE.store(false, Ordering::SeqCst);
    ok_with(json!({ "msg": site::json_str(&call.body, "msg") }))
}

pub fn resend_code(username: &str, email: &str) -> String {
    let c = cfg();
    let call = site::post(
        &c.base_url,
        "/api/resend-code",
        "application/x-www-form-urlencoded",
        form(&[("username", username.trim()), ("email", email.trim())]),
        None,
        c.timeout_sec,
    );
    if !call.ok {
        note_failure(&call, false);
        return fail(&call.error, call.kind);
    }
    OFFLINE.store(false, Ordering::SeqCst);
    ok_with(json!({ "msg": site::json_str(&call.body, "msg") }))
}

/* ── 需要登录的操作 ─────────────────────────────────────────────────────── */

pub fn change_password(old_password: &str, new_password: &str) -> String {
    let c = cfg();
    let token = resolve_token();
    if token.is_empty() {
        return fail("尚未登录", "unauthorized");
    }
    let call = site::post(
        &c.base_url,
        "/api/change-password",
        "application/x-www-form-urlencoded",
        form(&[("old_password", old_password), ("new_password", new_password)]),
        Some(&token),
        c.timeout_sec,
    );
    if !call.ok {
        note_failure(&call, false);
        return fail(&call.error, call.kind);
    }
    OFFLINE.store(false, Ordering::SeqCst);
    // 站点改密码不会立刻废止已发出的 token —— 如实告诉用户，别让人以为已经踢掉了
    ok_with(json!({
        "msg": site::json_str(&call.body, "msg"),
        "note": "改密码不会让已登录的会话立刻失效；要立刻踢掉，可在站点上登出或等 token 到期。",
    }))
}

pub fn login_history() -> String {
    let c = cfg();
    let token = resolve_token();
    if token.is_empty() {
        return fail("尚未登录", "unauthorized");
    }
    let call = site::get(&c.base_url, "/api/login-history", Some(&token), c.timeout_sec);
    if !call.ok {
        note_failure(&call, false);
        return fail(&call.error, call.kind);
    }
    OFFLINE.store(false, Ordering::SeqCst);
    let items: Value = serde_json::from_str(&normalize_history(&call.body, 20)).unwrap_or(json!([]));
    ok_with(json!({ "items": items }))
}

/// 站点版本/下载信息（更新链的前置；解析与比较**复用 update**，一处实现）
pub fn site_version() -> String {
    let c = cfg();
    let call = site::get(&c.base_url, "/api/version", None, c.timeout_sec);
    if !call.ok {
        note_failure(&call, false);
        return fail(&call.error, call.kind);
    }
    OFFLINE.store(false, Ordering::SeqCst);
    let parsed: Value = serde_json::from_str(&update::parse_version_body(&call.body, &update::app_version()))
        .unwrap_or(Value::Null);
    if parsed.get("ok").and_then(|b| b.as_bool()) != Some(true) {
        return parsed.to_string();
    }
    let g = |k: &str| parsed.get(k).cloned().unwrap_or(Value::Null);
    ok_with(json!({
        "latest": g("latest"),
        "date": g("date"),
        "downloadUrl": g("downloadUrl"),
        "hasUpdate": parsed.get("hasUpdate").and_then(|b| b.as_bool()).unwrap_or(false),
        "relation": g("relation"),
    }))
}

pub fn is_busy() -> bool {
    !busy().is_empty()
}

pub fn cancel_all() {
    site::cancel_all();
}

/* ── 自检（不联网）──────────────────────────────────────────────────────── */

pub fn self_check() -> String {
    let mut checks: Vec<Value> = Vec::new();
    let mut all = true;
    let add = |name: &str, ok: bool, detail: String, checks: &mut Vec<Value>| {
        checks.push(json!({ "name": name, "ok": ok, "detail": detail }));
    };

    // ① 站点地址闸门
    let url_ok = site::normalize_base_url("https://mf-vis-science.cn") == "https://mf-vis-science.cn"
        && site::normalize_base_url("https://mf-vis-science.cn/") == "https://mf-vis-science.cn"
        && site::normalize_base_url("http://127.0.0.1:8795") == "http://127.0.0.1:8795"
        && site::normalize_base_url("javascript:alert(1)") == site::DEFAULT_BASE_URL
        && site::normalize_base_url("file:///C:/Windows") == site::DEFAULT_BASE_URL
        && site::normalize_base_url("https://evil@host") == site::DEFAULT_BASE_URL
        && !site::normalize_base_url("https://x.cn/?a=1").contains('?');
    all &= url_ok;
    add(
        "站点地址闸门",
        url_ok,
        if url_ok {
            "只接受 http/https、去尾斜杠、拒绝查询串/片段/用户信息（这个值决定 token 发往哪儿）".into()
        } else {
            "地址归一化不符合预期".into()
        },
        &mut checks,
    );

    // ② 失败体 {detail} 解析
    let detail_ok = site::detail_of("{\"detail\":\"用户名或密码错误\"}", 400) == "用户名或密码错误"
        && site::detail_of("{\"msg\":\"已成功登出\"}", 200) == "已成功登出"
        && site::detail_of("", 500) == "HTTP 500";
    all &= detail_ok;
    add(
        "失败体 {detail} 解析",
        detail_ok,
        if detail_ok {
            "优先 detail、其次 msg、最后退回 HTTP 状态码（站点的错误形状原样带给用户）".into()
        } else {
            "错误体解析不符合预期".into()
        },
        &mut checks,
    );

    // ③ JWT exp 解析（只用于排期；签名由服务器校验）
    let payload = base64::engine::general_purpose::STANDARD.encode("{\"sub\":\"u\",\"exp\":2000000000}");
    let sample = format!("eyJhbGciOiJIUzI1NiJ9.{}.sig", payload.trim_end_matches('='));
    let exp_ok = jwt_exp(&sample) == Some(2_000_000_000) && jwt_exp("garbage").is_none();
    all &= exp_ok;
    add(
        "JWT exp 解析",
        exp_ok,
        if exp_ok {
            "能算出到期时间用于静默续期；**不校验签名**（那是服务器的事，猜错只会多一次 401）".into()
        } else {
            "exp 解析不符合预期".into()
        },
        &mut checks,
    );

    // ④ 登录历史归一化
    let hist = normalize_history(
        "{\"items\":[{\"ip\":\"1.2.3.4\",\"user_agent\":\"UA\",\"login_at\":\"2026-01-01T00:00:00Z\"}]}",
        20,
    );
    let hist_ok = hist.contains("1.2.3.4") && hist.contains("2026-01-01") && !hist.contains("password");
    all &= hist_ok;
    add(
        "登录历史归一化",
        hist_ok,
        if hist_ok { "取 ip / user_agent / login_at".into() } else { "归一化不符合预期".into() },
        &mut checks,
    );

    // ⑤ 脱敏视图里没有 token
    let info_text = info();
    let token_now = resolve_token();
    let redact_ok = !info_text.contains("access_token")
        && !info_text.contains("tokenProtected")
        && (token_now.is_empty() || !info_text.contains(&token_now));
    all &= redact_ok;
    add(
        "脱敏视图不含 token",
        redact_ok,
        if redact_ok {
            "Info() 只有 loggedIn/tokenSource 这类标志，token 本体不出宿主".into()
        } else {
            "脱敏视图里出现了 token 或字段名".into()
        },
        &mut checks,
    );

    // ⑥ 离线不阻塞：Info() 不依赖网络
    let t0 = std::time::Instant::now();
    let _ = info();
    let ms = t0.elapsed().as_millis();
    let fast_ok = ms < 50;
    all &= fast_ok;
    add(
        "Info() 不碰网络（离线也能画界面）",
        fast_ok,
        if fast_ok {
            format!("读本地状态用了 {ms} ms；断网时界面照常显示上次的资料并标注 unverified")
        } else {
            format!("Info() 用了 {ms} ms，像是碰了网络")
        },
        &mut checks,
    );

    // ⑦ sha256 工具（更新链显示校验值要用；顺手在这里钉一下）
    let sha_ok = pack::sha256_eq(
        &pack::sha256_bytes(b"abc"),
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    );
    all &= sha_ok;
    add("sha256 工具", sha_ok, "校验值显示与比较".into(), &mut checks);

    json!({ "ok": true, "checks": checks, "ok_all": all }).to_string()
}
