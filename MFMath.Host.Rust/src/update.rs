//! update.rs —— 更新链（对照 C# `UpdateBridge.cs`）
//!
//! **本项目的既定取舍**（OPEN-ITEMS 里定下的，一条都不能松）：
//!   **不自动下载、不执行安装包**。软件只做三件事：查版本、如实显示差异、把下载页交给浏览器。
//!   理由：自动执行安装包等于给软件装了一条"下载并运行可执行文件"的通路；少一个通路少一片攻击面。
//!
//! **一条容易被忽略的真实陷阱**（C# 注释里特意记着，这里照搬）：
//!   站点 `/api/version` 可能报的是 **1.2.0**（v1 的版本）。如果只判断"站点版本 ≠ 本机版本"，
//!   v2 的软件会被提示"有新版 1.2.0"，然后把用户引去下载 **v1 安装包** —— 那是降级，不是更新。
//!   所以比较的是**关系**（newer / same / older），只有站点确实更新时才提示"有新版本"。
//!
//! ⚠ 还有一条踩过的坑（C# 注释里写着"本轮踩过"，非常值得照搬）：
//!   拼 JSON 时漏一个收尾括号 → JSON 不合法 → 页面侧 `parse()` 返回 null →
//!   表现成"宿主没有响应"。一个拼写错误被伪装成"桥不通"。所以这里**全部用 serde_json 拼**，
//!   不手写字符串。

use std::sync::atomic::{AtomicI64, Ordering};
use std::sync::Mutex;

use serde_json::{json, Map, Value};

use crate::{shellopen, site};

/// 本机版本：与 C# 的 `<Version>2.0.0</Version>` 对齐（**不是** 0.1.0，也不许是默认的 1.0.0.0）
pub fn app_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

fn now_ms() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

static LAST_ERROR: Mutex<String> = Mutex::new(String::new());
static LAST_RESULT: Mutex<String> = Mutex::new(String::new());
static LAST_CHECK_AT: AtomicI64 = AtomicI64::new(0);

fn set_err(s: &str) {
    if let Ok(mut g) = LAST_ERROR.lock() {
        *g = s.to_string();
    }
}
fn set_result(s: &str) {
    if let Ok(mut g) = LAST_RESULT.lock() {
        *g = s.to_string();
    }
}
fn get(m: &Mutex<String>) -> String {
    m.lock().map(|g| g.clone()).unwrap_or_default()
}

/// 版本比较：数字段逐段比（**1.10.0 > 1.9.9** —— 字符串比较会搞错这个），
/// 带预发布后缀的（2.0.0-beta）视为**小于**同号正式版。返回 >0 表示 a 更新。
pub fn compare_versions(a: &str, b: &str) -> i32 {
    fn parse(v: &str) -> (Vec<i32>, String) {
        let s = v.trim();
        let (num_part, pre) = match s.find('-') {
            Some(i) => (&s[..i], s[i + 1..].to_string()),
            None => (s, String::new()),
        };
        let nums = num_part
            .split('.')
            .map(|seg| {
                let digits: String = seg.chars().take_while(|c| c.is_ascii_digit()).collect();
                digits.parse::<i32>().unwrap_or(0)
            })
            .collect();
        (nums, pre)
    }
    let (na, pa) = parse(a);
    let (nb, pb) = parse(b);
    let len = na.len().max(nb.len());
    for i in 0..len {
        let x = *na.get(i).unwrap_or(&0);
        let y = *nb.get(i).unwrap_or(&0);
        if x != y {
            return if x > y { 1 } else { -1 };
        }
    }
    match (pa.is_empty(), pb.is_empty()) {
        (true, true) => 0,
        (true, false) => 1,  // 正式版 > 预发布
        (false, true) => -1,
        (false, false) => match pa.cmp(&pb) {
            std::cmp::Ordering::Less => -1,
            std::cmp::Ordering::Greater => 1,
            std::cmp::Ordering::Equal => 0,
        },
    }
}

/// 脱敏状态：本机版本、上次检查结果、下载地址（不含任何凭据）
pub fn info() -> String {
    let cfg = site::SiteConfig::load();
    let last = get(&LAST_RESULT);
    json!({
        "appVersion": app_version(),
        "lastCheckAt": LAST_CHECK_AT.load(Ordering::SeqCst),
        "lastError": get(&LAST_ERROR),
        "lastResult": if last.is_empty() { Value::Null } else { Value::String(last) },
        "policy": "只提示与显示校验值；下载与安装都交给浏览器，软件不自动执行安装包",
        "baseUrl": cfg.base_url,
    })
    .to_string()
}

/// 查一次站点版本。返回
/// `{ok,current,latest,date,relation,hasUpdate,sha256,size,sha256Reason,downloadUrl,changelogUrl,note}`
/// 站点不通时 `ok=false` + `kind` + `error`（**不影响任何计算功能**）。
pub fn check() -> String {
    let cfg = site::SiteConfig::load();
    let call = site::get(&cfg.base_url, "/api/version", None, cfg.timeout_sec);
    if !call.ok {
        set_err(&call.error);
        return json!({ "ok": false, "kind": call.kind, "error": call.error }).to_string();
    }
    let parsed = parse_version_body(&call.body, &app_version());
    LAST_CHECK_AT.store(now_ms(), Ordering::SeqCst);
    set_err("");
    set_result(&parsed);
    parsed
}

/// 解析 `/api/version` 的信封（`{code,data:{…}}` 或平铺），并与本机版本比较。
/// 抽成独立函数是为了让 `account.SiteVersion` 复用同一份解析（一处实现）。
pub fn parse_version_body(body: &str, current: &str) -> String {
    let root: Value = match serde_json::from_str(body) {
        Ok(v) => site::unwrap_data(&v),
        Err(_) => {
            return json!({ "ok": false, "kind": "parse", "error": "版本接口返回的形状不认识" })
                .to_string();
        }
    };
    if !root.is_object() {
        return json!({ "ok": false, "kind": "parse", "error": "版本接口返回的形状不认识" })
            .to_string();
    }
    let s = |k: &str| root.get(k).and_then(|v| v.as_str()).unwrap_or("").to_string();
    let latest = s("latest");
    let date = s("date");
    let download = s("download_url");
    let changelog = s("changelog");
    let sha = s("sha256");
    let reason = s("sha256_reason");
    let size = root.get("size").and_then(|v| v.as_i64()).unwrap_or(0);

    let cmp = compare_versions(&latest, current);
    let relation = if cmp > 0 { "newer" } else if cmp < 0 { "older" } else { "same" };
    let has_update = relation == "newer";
    // 站点比本机旧时**不提示更新**，并把原因说清楚（否则用户会以为该下载那个包）
    let note = match relation {
        "newer" => "站点上有更新的版本。下载页会在浏览器里打开；本软件不会自动下载或运行安装包。",
        "same" => "已是最新版本。",
        "older" => "站点上的版本比本机旧（发布 v2.0 时需要把站点 src/lib/constants.ts 的 VERSION 改成 2.0.0）。",
        _ => "",
    };

    let mut out = Map::new();
    out.insert("ok".into(), json!(true));
    out.insert("current".into(), json!(current));
    out.insert("latest".into(), json!(latest));
    out.insert("date".into(), json!(date));
    out.insert("relation".into(), json!(relation));
    out.insert("hasUpdate".into(), json!(has_update));
    // 没给校验值时**如实说没有 + 原因**，绝不给空字符串让界面显示成"已校验"
    out.insert("sha256".into(), if sha.is_empty() { Value::Null } else { json!(sha) });
    out.insert(
        "sha256Reason".into(),
        if sha.is_empty() {
            json!(if reason.is_empty() { "站点没有提供校验值".to_string() } else { reason })
        } else {
            Value::Null
        },
    );
    out.insert("size".into(), if size > 0 { json!(size) } else { Value::Null });
    out.insert("downloadUrl".into(), json!(download));
    out.insert("changelogUrl".into(), json!(changelog));
    out.insert("note".into(), json!(note));
    Value::Object(out).to_string()
}

/* ── 打开下载页 ─────────────────────────────────────────────────────────── */

/// 给它是不是"带协议"的判断（`^[a-zA-Z][a-zA-Z0-9+.\-]*:`）
fn has_scheme(s: &str) -> bool {
    let mut it = s.chars();
    match it.next() {
        Some(c) if c.is_ascii_alphabetic() => {}
        _ => return false,
    }
    for c in it {
        if c == ':' {
            return true;
        }
        if !(c.is_ascii_alphanumeric() || c == '+' || c == '.' || c == '-') {
            return false;
        }
    }
    false
}

/// 与 `open_download_page` 里"相对路径"分支同一套判断（抽出来是为了让自检覆盖它）。
///
/// 为什么必须能单独验：拼接逻辑曾经把 `javascript:alert(1)` 拼成合法的 http URL
/// 从而让协议闸门形同虚设（C# 注释里记着这个 bug）。
pub fn looks_relative_safe(raw: &str) -> bool {
    let s = raw.trim();
    if s.is_empty() {
        return false;
    }
    if has_scheme(s) {
        return false;
    }
    if s.starts_with("//") {
        return false;
    }
    if s.chars().any(|c| c.is_whitespace()) {
        return false;
    }
    if s.contains('\\') || s.contains("..") || s.contains(':') {
        return false;
    }
    true
}

/// 只算出"将会打开的地址"，不真的打开。返回 `(是否放行, 绝对地址, 拒绝原因)`
pub fn resolve_download_url(url: &str) -> (bool, String, String) {
    let raw = url.trim();
    if raw.is_empty() {
        return (false, String::new(), "没有下载地址".into());
    }
    // 带协议的 —— 一律过闸门（javascript:/file:/ms-* 在这里就被拒）
    if has_scheme(raw) {
        return if shellopen::is_allowed(raw) {
            (true, raw.to_string(), String::new())
        } else {
            (false, String::new(), "只允许打开 http/https 链接".into())
        };
    }
    // 不带协议的 —— 才当站内相对路径
    if !looks_relative_safe(raw) {
        return (
            false,
            String::new(),
            "只接受站点内的相对路径（不允许 //host、..、\\、: 或空白）".into(),
        );
    }
    let cfg = site::SiteConfig::load();
    let path = if raw.starts_with('/') { raw.to_string() } else { format!("/{raw}") };
    (true, format!("{}{}", cfg.base_url.trim_end_matches('/'), path), String::new())
}

/// 把下载页交给浏览器
pub fn open_download_page(url: &str) -> String {
    let (ok, absolute, reason) = resolve_download_url(url);
    if !ok {
        return json!({ "ok": false, "error": reason }).to_string();
    }
    match shellopen::open(&absolute) {
        Ok(()) => json!({ "ok": true, "opened": absolute }).to_string(),
        Err(e) => json!({ "ok": false, "error": e }).to_string(),
    }
}

/// 给界面用：把"将打开的地址"作为纯查询返回（不打开、不改状态）
pub fn preview_download_url(url: &str) -> String {
    let (ok, absolute, reason) = resolve_download_url(url);
    if ok {
        json!({ "ok": true, "url": absolute }).to_string()
    } else {
        json!({ "ok": false, "reason": reason }).to_string()
    }
}

pub fn cancel_all() {
    site::cancel_all();
}

/* ── 自检（不联网）──────────────────────────────────────────────────────── */

/// 五项自检，**都不联网**：版本比较（含 `1.10.0 > 1.9.9` 这个字符串比较会错的例子）、
/// 信封解析 + 关系判定、站点更旧时不提示更新、校验值缺失如实说明、打开链接的协议闸门。
pub fn self_check() -> String {
    let mut checks: Vec<Value> = Vec::new();
    let mut all = true;
    let mut push = |name: &str, ok: bool, detail: &str, checks: &mut Vec<Value>| {
        checks.push(json!({ "name": name, "ok": ok, "detail": detail }));
    };

    // ① 版本比较
    let cmp_ok = compare_versions("1.10.0", "1.9.9") > 0
        && compare_versions("2.0.0", "2.0.0") == 0
        && compare_versions("1.2.0", "2.0.0") < 0
        && compare_versions("2.0.0-beta.1", "2.0.0") < 0
        && compare_versions("2.0.1", "2.0.0") > 0;
    all &= cmp_ok;
    push(
        "版本比较",
        cmp_ok,
        if cmp_ok {
            "逐段比数字（1.10.0 > 1.9.9，字符串比较会搞错）；预发布小于同号正式版"
        } else {
            "版本比较结果不符合预期"
        },
        &mut checks,
    );

    // ② 信封解析（站点是 {code,data,msg}）
    let body = format!(
        "{{\"code\":0,\"data\":{{\"latest\":\"9.9.9\",\"date\":\"2026-01-01\",\"download_url\":\"/download\",\"sha256\":\"{}\",\"size\":123}},\"msg\":\"success\"}}",
        "a".repeat(64)
    );
    let parsed = parse_version_body(&body, "2.0.0");
    let parse_ok = parsed.contains("\"latest\":\"9.9.9\"")
        && parsed.contains("\"relation\":\"newer\"")
        && parsed.contains("\"hasUpdate\":true")
        && parsed.contains("\"size\":123");
    all &= parse_ok;
    push(
        "版本信封解析 + 关系判定",
        parse_ok,
        if parse_ok { "取 data 里的字段，算出 newer / hasUpdate" } else { "解析结果不符合预期" },
        &mut checks,
    );

    // ③ 站点更旧时**不**提示更新（最重要的一条：否则 v2 用户会被引去下载 v1 包）
    let older = parse_version_body("{\"data\":{\"latest\":\"1.2.0\",\"download_url\":\"/download\"}}", "2.0.0");
    let older_ok = older.contains("\"relation\":\"older\"")
        && older.contains("\"hasUpdate\":false")
        && older.contains("比本机旧");
    all &= older_ok;
    push(
        "站点更旧时不提示更新",
        older_ok,
        if older_ok {
            "站点报 1.2.0、本机 2.0.0 时判定为 older 并说明原因（避免把用户引去下载 v1 安装包）"
        } else {
            "更旧场景的判定不符合预期"
        },
        &mut checks,
    );

    // ④ 校验值缺失时如实说明
    let no_sha = parse_version_body(
        "{\"data\":{\"latest\":\"9.9.9\",\"sha256_reason\":\"服务器上还没有安装包文件\"}}",
        "2.0.0",
    );
    let sha_ok = no_sha.contains("\"sha256\":null") && no_sha.contains("服务器上还没有安装包文件");
    all &= sha_ok;
    push(
        "校验值缺失时如实说明",
        sha_ok,
        if sha_ok { "返回 null 并带上站点的原因，不编造也不留空白" } else { "缺失场景处理不符合预期" },
        &mut checks,
    );

    // ⑤ 打开链接只放行 http(s)，且**带协议的输入不会被当成相对路径**（C# 修过的那个 bug）
    let url_ok = shellopen::is_allowed("https://mf-vis-science.cn/download")
        && shellopen::is_allowed("http://127.0.0.1:8000/download")
        && !shellopen::is_allowed("javascript:alert(1)")
        && !shellopen::is_allowed("file:///C:/Windows/System32/cmd.exe")
        && !shellopen::is_allowed("ms-settings:")
        && !shellopen::is_allowed("")
        && !looks_relative_safe("javascript:alert(1)")
        && !looks_relative_safe("file:///C:/Windows/System32/cmd.exe")
        && !looks_relative_safe("//evil.example/x")
        && looks_relative_safe("/download")
        && looks_relative_safe("download")
        && !looks_relative_safe("/a/../b");
    all &= url_ok;
    push(
        "打开下载页只放行 http/https",
        url_ok,
        if url_ok {
            "javascript: / file: / ms-* 一律拒绝；带协议的输入不会被当成相对路径去拼接（否则闸门形同虚设）"
        } else {
            "协议闸门判定不正确"
        },
        &mut checks,
    );

    json!({ "ok": true, "checks": checks, "ok_all": all }).to_string()
}
