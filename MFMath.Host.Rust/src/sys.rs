//! sys.rs —— 设置面板用的宿主桥（JS 侧是 `hostObjects.sync.sys`）
//! 对照 C# `MFMath.Host/SettingsBridge.cs` 逐条实现：报路径、查文件在不在、
//! 读写设置 JSON、打开目录、导出诊断包。不含数学、不含窗口、不含进程。
//!
//! 三条安全/健壮性规则（C# 版注释里记的就是踩过的坑，这里一条不少）：
//!   ① **OpenPath 只允许打开白名单内的路径**（数据目录、应用目录、组件目录）。
//!      否则等于给渲染进程一个"打开任意路径"的原语，而设置面板是外部可扩展的。
//!   ② **读写设置 JSON 一律带 .bak**：覆盖前把旧文件复制成 .bak；解析失败时报错并
//!      **保留原文件不动**，避免"配置一坏全丢"。
//!   ③ **文件名单校验**：只允许 [a-z0-9_-]，杜绝用 "../" 跳出设置目录。

use std::fs;
use std::path::{Path, PathBuf};

use serde_json::json;

use crate::logging;

/// 引擎与运行时依赖的清单（顺序即 UI 上的显示顺序）
const ENGINE_DEPS: [&str; 6] = [
    "mf_mathematics.dll",
    "symengine-0.14.dll",
    "flint-24.dll",
    "gmp-10.dll",
    "mpfr-6.dll",
    "pthreadVC3.dll",
];

/* ── 路径 ───────────────────────────────────────────────────────────── */

fn data_dir() -> PathBuf {
    logging::data_dir()
}
fn settings_dir() -> PathBuf {
    data_dir().join("settings")
}
fn components_dir() -> PathBuf {
    data_dir().join("components")
}
fn exe_dir() -> PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()))
        .unwrap_or_else(|| PathBuf::from("."))
}

/* ── 校验 ───────────────────────────────────────────────────────────── */

/// 设置文件名合法性：只允许小写字母/数字/下划线/连字符，防目录穿越
fn valid_name(name: &str) -> bool {
    if name.trim().is_empty() || name.chars().count() > 40 {
        return false;
    }
    name.chars().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '_' || c == '-')
}

/// 路径是否落在允许打开的根目录内（含子目录）
fn under_allowed_root(path: &str) -> Result<(), String> {
    if path.trim().is_empty() {
        return Err("路径为空".into());
    }
    let abs = std::path::absolute(path).map_err(|e| format!("路径非法：{e}"))?;
    let abs_s = abs.to_string_lossy().to_ascii_lowercase();
    for root in [data_dir(), exe_dir(), components_dir()] {
        let Ok(rf) = std::path::absolute(&root) else { continue };
        let rf_s = rf.to_string_lossy().to_ascii_lowercase();
        if !rf_s.is_empty() && abs_s.starts_with(&rf_s) {
            return Ok(());
        }
    }
    Err("只允许打开数据目录或应用目录内的路径".into())
}

/* ── 基本信息 ───────────────────────────────────────────────────────── */

/// 宿主与运行环境信息（设置面板的"引擎"与"存储"两组都用它）
pub fn info() -> String {
    let component_base = std::env::var("__MF_COMPONENT_BASE").unwrap_or_default();
    json!({
        "dataDir": data_dir().to_string_lossy(),
        "settingsDir": settings_dir().to_string_lossy(),
        "appDir": exe_dir().to_string_lossy(),
        "hostVersion": format!("{} (Rust 宿主)", env!("CARGO_PKG_VERSION")),
        "runtime": "rust (wry / WebView2)",
        "os": logging::os_string(),
        "arch": std::env::consts::ARCH,
        "is64": cfg!(target_pointer_width = "64"),
        "componentBase": component_base,
    })
    .to_string()
}

/// 引擎产物清单：主 DLL 与 5 个运行时依赖在不在、多大
pub fn engine_report() -> String {
    let dir = exe_dir();
    let files: Vec<serde_json::Value> = ENGINE_DEPS
        .iter()
        .map(|name| {
            let p = dir.join(name);
            let md = fs::metadata(&p).ok();
            json!({
                "name": name,
                "present": md.is_some(),
                "bytes": md.as_ref().map(|m| m.len()).unwrap_or(0),
                "mtime": md
                    .as_ref()
                    .and_then(|m| m.modified().ok())
                    .map(logging::stamp_of)
                    .unwrap_or_default(),
            })
        })
        .collect();
    json!({ "dir": dir.to_string_lossy(), "files": files }).to_string()
}

/* ── 设置 JSON 存储 ─────────────────────────────────────────────────── */

/// 列出已存在的设置文件（名字、大小、修改时间）；出错时返回 `{"error":…}`
/// —— 前端 io.js 明确按"不是数组"来识别这个错误分支。
pub fn store_list() -> String {
    let mut out: Vec<(String, u64, String)> = Vec::new();
    match fs::read_dir(settings_dir()) {
        Ok(rd) => {
            for e in rd.filter_map(|e| e.ok()) {
                let name = e.file_name().to_string_lossy().into_owned();
                if !name.to_ascii_lowercase().ends_with(".json") {
                    continue;
                }
                let md = e.metadata().ok();
                let bytes = md.as_ref().map(|m| m.len()).unwrap_or(0);
                let mtime = md
                    .as_ref()
                    .and_then(|m| m.modified().ok())
                    .map(logging::stamp_of)
                    .unwrap_or_default();
                let stem = name.trim_end_matches(".json").to_string();
                out.push((stem, bytes, mtime));
            }
        }
        Err(e) => {
            // 目录不存在是"还没有设置文件"，不是错误；其它 I/O 错误才报
            if e.kind() != std::io::ErrorKind::NotFound {
                return json!({ "error": e.to_string() }).to_string();
            }
        }
    }
    out.sort();
    let files: Vec<serde_json::Value> = out
        .into_iter()
        .map(|(name, bytes, mtime)| json!({ "name": name, "bytes": bytes, "mtime": mtime }))
        .collect();
    serde_json::Value::Array(files).to_string()
}

/// 读设置文件：`{"ok":true,"json":"…"}` / `{"ok":true,"exists":false}` /
/// `{"ok":false,"corrupt":true,"error":"…"}`。**解析失败保留原文件**。
pub fn store_read(name: &str) -> String {
    if !valid_name(name) {
        return json!({ "ok": false, "error": "非法的设置文件名" }).to_string();
    }
    let p = settings_dir().join(format!("{name}.json"));
    if !p.exists() {
        return json!({ "ok": true, "json": "", "exists": false }).to_string();
    }
    match fs::read_to_string(&p) {
        Ok(text) => {
            if let Err(e) = serde_json::from_str::<serde_json::Value>(&text) {
                return json!({ "ok": false, "corrupt": true, "error": format!("JSON 解析失败：{e}") }).to_string();
            }
            json!({ "ok": true, "exists": true, "json": text }).to_string()
        }
        Err(e) => json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}

/// 写设置文件：先校验 JSON，再备份旧文件，最后**原子替换**（临时文件 + rename）。
/// 半途崩溃也不会留下半截 JSON —— v1 的工作区保存就是直接 open(path,"w")，
/// 写一半崩溃后下次读必然 JSONDecodeError。
pub fn store_write(name: &str, body: &str) -> String {
    if !valid_name(name) {
        return json!({ "ok": false, "error": "非法的设置文件名" }).to_string();
    }
    if body.trim().is_empty() {
        return json!({ "ok": false, "error": "内容为空" }).to_string();
    }
    if let Err(e) = serde_json::from_str::<serde_json::Value>(body) {
        return json!({ "ok": false, "error": e.to_string() }).to_string();
    }
    let dir = settings_dir();
    if let Err(e) = fs::create_dir_all(&dir) {
        return json!({ "ok": false, "error": e.to_string() }).to_string();
    }
    let p = dir.join(format!("{name}.json"));
    let tmp = dir.join(format!("{name}.json.tmp"));
    if let Err(e) = fs::write(&tmp, body.as_bytes()) {
        return json!({ "ok": false, "error": e.to_string() }).to_string();
    }
    if p.exists() {
        // 备份失败不阻断写入（与 C# 一致）
        let _ = fs::copy(&p, dir.join(format!("{name}.json.bak")));
    }
    // Windows 上 fs::rename 走 MoveFileEx(MOVEFILE_REPLACE_EXISTING)：目标存在也能原子替换
    match fs::rename(&tmp, &p) {
        Ok(()) => json!({ "ok": true }).to_string(),
        Err(e) => {
            let _ = fs::remove_file(&tmp);
            json!({ "ok": false, "error": e.to_string() }).to_string()
        }
    }
}

pub fn store_delete(name: &str) -> String {
    if !valid_name(name) {
        return json!({ "ok": false, "error": "非法的设置文件名" }).to_string();
    }
    let p = settings_dir().join(format!("{name}.json"));
    match fs::remove_file(&p) {
        Ok(()) => json!({ "ok": true }).to_string(),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => json!({ "ok": true }).to_string(),
        Err(e) => json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}

/* ── 打开目录 / 诊断包 ──────────────────────────────────────────────── */

/// 在资源管理器里打开路径（白名单内的目录或文件）
pub fn open_path(path: &str) -> String {
    if let Err(reason) = under_allowed_root(path) {
        return json!({ "ok": false, "error": reason }).to_string();
    }
    let p = Path::new(path);
    let res = if p.is_dir() {
        std::process::Command::new("explorer.exe").arg(path).spawn().map(|_| ())
    } else if p.is_file() {
        std::process::Command::new("explorer.exe")
            .arg(format!("/select,{path}"))
            .spawn()
            .map(|_| ())
    } else {
        return json!({ "ok": false, "error": "路径不存在" }).to_string();
    };
    match res {
        Ok(()) => json!({ "ok": true }).to_string(),
        Err(e) => json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}

/// 导出诊断包：版本、路径、引擎产物清单、设置文件（**跳过凭据文件**）+ 日志尾部，
/// 写到数据目录并返回文件路径，方便让用户直接发给支持。
pub fn export_diagnostics() -> String {
    let dir = data_dir();
    if let Err(e) = fs::create_dir_all(&dir) {
        return json!({ "ok": false, "error": e.to_string() }).to_string();
    }
    let path = dir.join(format!("diagnostics-{}.txt", logging::stamp_compact()));

    let mut s = String::new();
    s.push_str("MF-Mathematics 诊断包\r\n");
    s.push_str(&format!("生成时间: {}\r\n\r\n", logging::stamp_full()));
    s.push_str("== 宿主与环境 ==\r\n");
    s.push_str(&info());
    s.push_str("\r\n\r\n== 引擎产物 ==\r\n");
    s.push_str(&engine_report());
    s.push_str("\r\n\r\n== 设置文件 ==\r\n");
    s.push_str(&store_list());
    s.push_str("\r\n\r\n");

    /* ⚠ 凭据文件名是 ai.json / account.json / search.json —— **一个都不含 "secret"**。
     * 原先只按"文件名含 secret"跳，等于没跳：API Key、登录态、Wolfram App ID 的密文
     * 都会被打进诊断包，而界面对用户写的是"不含密钥文件"。名单与前端
     * lib/settings/io.js 的 CREDENTIAL_FILES 保持一致；"secret" 那条保留作兜底。 */
    const CREDENTIAL_STEMS: [&str; 3] = ["ai", "account", "search"];
    if let Ok(rd) = fs::read_dir(settings_dir()) {
        let mut names: Vec<String> = rd
            .filter_map(|e| e.ok())
            .map(|e| e.file_name().to_string_lossy().into_owned())
            .filter(|n| n.to_ascii_lowercase().ends_with(".json"))
            .collect();
        names.sort();
        for n in names {
            let stem = n.trim_end_matches(".json");
            if n.to_ascii_lowercase().contains("secret") {
                continue;
            }
            if CREDENTIAL_STEMS.iter().any(|c| c.eq_ignore_ascii_case(stem)) {
                continue;
            }
            s.push_str(&format!("-- {n} --\r\n"));
            match fs::read_to_string(settings_dir().join(&n)) {
                Ok(t) => s.push_str(&t),
                Err(e) => s.push_str(&format!("(读取失败: {e})")),
            }
            s.push_str("\r\n\r\n");
        }
    }

    // 崩溃排查最需要的就是这两段：最近日志 + 最近一次崩溃的完整现场
    s.push_str("== 宿主日志（app.log 尾部）==\r\n");
    s.push_str(&format!("日志目录: {}\r\n", logging::dir().display()));
    s.push_str(&logging::tail(&logging::dir().join("app.log"), 200));
    s.push_str("\r\n\r\n== 最近的崩溃记录 ==\r\n");
    s.push_str(&newest_crash_text());
    s.push_str("\r\n");

    match fs::write(&path, s.as_bytes()) {
        Ok(()) => json!({ "ok": true, "path": path.to_string_lossy() }).to_string(),
        Err(e) => json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}

fn newest_crash_text() -> String {
    let Ok(rd) = fs::read_dir(logging::dir()) else { return "(无)".into() };
    let mut names: Vec<String> = rd
        .filter_map(|e| e.ok())
        .map(|e| e.file_name().to_string_lossy().into_owned())
        .filter(|n| n.starts_with("crash-") && n.ends_with(".log"))
        .collect();
    names.sort_by(|a, b| b.cmp(a)); // 文件名即时间戳，倒序取最新
    match names.first() {
        None => "(无)".to_string(),
        Some(n) => match fs::read_to_string(logging::dir().join(n)) {
            Ok(t) => format!("-- {n} --\r\n{t}"),
            Err(e) => format!("(读取崩溃记录失败: {e})"),
        },
    }
}
