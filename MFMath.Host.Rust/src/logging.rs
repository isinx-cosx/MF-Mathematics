//! logging.rs —— 宿主日志与崩溃记录（对照 已移除的 C# 宿主的 Log.cs）
//!
//! 为什么要有它：宿主侧异常、**以及 WebView2 里的 JS 异常**（经 `diag` 桥转发）都要落到
//! **同一个** app.log，两边的时间线才对得上；而"设置 → 导出诊断包"要能把日志尾部一起带走。
//!
//! 策略（与 C# 版逐条一致）：
//!   · 日志写 `%LOCALAPPDATA%\MFMath\logs`（一定可写），单文件 2 MB 轮转成 app.1.log；
//!   · 崩溃另写 `crash-*.log`：环境 + 异常 + 最近的 app.log 尾部，单文件即可复盘；
//!   · **不联网上报**：数学工具的用户不该因为一次崩溃就被上传任何东西；
//!   · 日志本身永远不许影响主流程 —— 所有写入失败都静默返回。

use std::fs::{self, File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use windows::Win32::System::SystemInformation::GetLocalTime;

const MAX_BYTES: u64 = 2 * 1024 * 1024; // 单个 app.log 上限 2 MB
const KEEP_CRASH_FILES: usize = 20; // 崩溃日志只留最近 20 个
const CRASH_TAIL_LINES: usize = 200; // 崩溃日志里附带多少行 app.log 尾部
const TAIL_CHUNK: u64 = 256 * 1024; // 读尾部时最多读这么多字节，避免把内存吃满

static GATE: Mutex<()> = Mutex::new(());

/* ── 路径 ───────────────────────────────────────────────────────────── */

pub fn local_app_data() -> PathBuf {
    std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

/// 用户数据根目录：与 WebView2 用户数据、组件缓存同处一地，卸载时说法统一
pub fn data_dir() -> PathBuf {
    local_app_data().join("MFMath")
}

/// 日志目录（一定可写；诊断导出与"日志在哪"提示都用它）
pub fn dir() -> PathBuf {
    data_dir().join("logs")
}

fn app_log_path() -> PathBuf {
    dir().join("app.log")
}

/* ── 时间（本地时区；Rust 标准库不做日期格式化，用 Win32 GetLocalTime）──── */

/// `(年, 月, 日, 时, 分, 秒, 毫秒)`
pub fn local_parts() -> (u16, u16, u16, u16, u16, u16, u16) {
    // SAFETY: GetLocalTime 只写它自己的输出结构，无前置条件
    let st = unsafe { GetLocalTime() };
    (st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond, st.wMilliseconds)
}

/// `yyyy-MM-dd HH:mm:ss.SSS`（与 C# 日志行格式一致）
pub fn stamp_full() -> String {
    let (y, mo, d, h, mi, s, ms) = local_parts();
    format!("{y:04}-{mo:02}-{d:02} {h:02}:{mi:02}:{s:02}.{ms:03}")
}

/// 把文件的修改时间按**本地时区**格式化成 `yyyy-MM-dd HH:mm`。
/// Rust 标准库只给 UTC 时间戳，所以自己算一次当前本地偏移再用民用历算法换算。
pub fn stamp_of(t: std::time::SystemTime) -> String {
    let secs = t
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let local = secs + local_offset_secs();
    let days = local.div_euclid(86_400);
    let rem = local.rem_euclid(86_400);
    let (y, mo, d) = civil_from_days(days);
    format!("{y:04}-{mo:02}-{d:02} {:02}:{:02}", rem / 3600, (rem % 3600) / 60)
}

/// 当前本地时区偏移（秒）。用"本地民用时间 - UTC 时间戳"反推，夏令时也自然带上。
fn local_offset_secs() -> i64 {
    let (y, mo, d, h, mi, s, _) = local_parts();
    let local_secs = days_from_civil(y as i64, mo as i64, d as i64) * 86_400
        + h as i64 * 3600
        + mi as i64 * 60
        + s as i64;
    let utc_secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    local_secs - utc_secs
}

/// 民用历 → 距 1970-01-01 的天数（Howard Hinnant 的算法，无分支特判闰年）
fn days_from_civil(y: i64, m: i64, d: i64) -> i64 {
    let y = if m <= 2 { y - 1 } else { y };
    let era = if y >= 0 { y } else { y - 399 } / 400;
    let yoe = y - era * 400; // [0, 399]
    let mp = (m + 9) % 12; // 3 月为 0
    let doy = (153 * mp + 2) / 5 + d - 1; // [0, 365]
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy; // [0, 146096]
    era * 146_097 + doe - 719_468
}

/// 距 1970-01-01 的天数 → 民用历 (年, 月, 日)
fn civil_from_days(z: i64) -> (i64, i64, i64) {
    let z = z + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = z - era * 146_097; // [0, 146096]
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365; // [0, 399]
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100); // [0, 365]
    let mp = (5 * doy + 2) / 153; // [0, 11]
    let d = doy - (153 * mp + 2) / 5 + 1; // [1, 31]
    let m = if mp < 10 { mp + 3 } else { mp - 9 }; // [1, 12]
    (if m <= 2 { y + 1 } else { y }, m, d)
}

/// `yyyyMMdd-HHmmss`（崩溃日志与诊断包文件名用）
pub fn stamp_compact() -> String {
    let (y, mo, d, h, mi, s, _) = local_parts();
    format!("{y:04}{mo:02}{d:02}-{h:02}{mi:02}{s:02}")
}

/// 系统版本串（诚实报告）。
/// `GetVersionExW` 在没有应用清单时会谎报 6.2，所以直接调 ntdll 的 `RtlGetVersion`
/// —— windows crate 没导出它，就自己 `LoadLibraryW` + `GetProcAddress`（与引擎 FFI 同一套写法）。
pub fn os_string() -> String {
    use std::env::consts::ARCH;
    if let Some((major, minor, build)) = rtl_get_version() {
        return format!("Windows {major}.{minor}.{build} ({ARCH})");
    }
    format!("Windows ({ARCH})")
}

#[repr(C)]
struct OsVersionInfoW {
    size: u32,
    major: u32,
    minor: u32,
    build: u32,
    platform: u32,
    csd: [u16; 128],
}

fn rtl_get_version() -> Option<(u32, u32, u32)> {
    use windows::core::{s, w};
    use windows::Win32::System::LibraryLoader::{GetProcAddress, LoadLibraryW};
    // SAFETY: 只取一个导出函数的地址并按 NTAPI 约定调用；结构按 OSVERSIONINFOW 布局手写
    unsafe {
        let lib = LoadLibraryW(w!("ntdll.dll")).ok()?;
        let proc = GetProcAddress(lib, s!("RtlGetVersion"))?;
        let f: unsafe extern "system" fn(*mut OsVersionInfoW) -> i32 = std::mem::transmute(proc);
        let mut vi = OsVersionInfoW {
            size: std::mem::size_of::<OsVersionInfoW>() as u32,
            major: 0,
            minor: 0,
            build: 0,
            platform: 0,
            csd: [0; 128],
        };
        if f(&mut vi) == 0 && vi.major > 0 {
            Some((vi.major, vi.minor, vi.build))
        } else {
            None
        }
    }
}

/* ── 写日志 ─────────────────────────────────────────────────────────── */

pub fn info(msg: &str) {
    write_line("INFO ", msg);
}
pub fn warn(msg: &str) {
    write_line("WARN ", msg);
}
pub fn error(msg: &str) {
    write_line("ERROR", msg);
}

/// 装一个 panic 钩子：**任何** panic 都要留下崩溃文件。
///
/// 为什么必须有它：宿主是 GUI 子系统（`#![windows_subsystem = "windows"]`），
/// **双击运行时 stderr 根本没人看得到**；而 Tauri 在 setup 失败时是**直接 panic** 的
/// （`tauri-2.12.1/src/app.rs:1444`：`Failed to setup app: …`）。
/// 两者叠在一起，用户看到的就是"窗口没出来、日志里一行都没有"—— 本轮实测
/// WebView2 撞车（`0x800700AA`）时正是这个现象，只能靠猜。
///
/// 钩子里做三件事：写 `crash-*.log`（含 backtrace 与最近日志尾部）、把同一句话写进
/// app.log、再把默认钩子跑一遍（重定向时 stderr 仍可见）。
pub fn install_panic_hook() {
    static ONCE: std::sync::Once = std::sync::Once::new();
    ONCE.call_once(|| {
        let default = std::panic::take_hook();
        std::panic::set_hook(Box::new(move |info| {
            let payload = info
                .payload()
                .downcast_ref::<&str>()
                .map(|s| (*s).to_string())
                .or_else(|| info.payload().downcast_ref::<String>().cloned())
                .unwrap_or_else(|| "（无法描述的 panic）".to_string());
            let loc = info
                .location()
                .map(|l| format!("{}:{}:{}", l.file(), l.line(), l.column()))
                .unwrap_or_else(|| "（位置未知）".into());
            // force_capture：不依赖 RUST_BACKTRACE，用户机器上也能拿到栈
            let bt = std::backtrace::Backtrace::force_capture();
            let detail = format!("panic @ {loc}\n{payload}\n\n== backtrace ==\n{bt}");
            error(&format!("panic @ {loc}：{payload}"));
            if let Some(p) = crash("panic", &detail) {
                eprintln!("[rust-host] 崩溃记录：{p}");
            } else {
                eprintln!("[rust-host] panic（崩溃文件写不出来，日志目录不可写？）：{detail}");
            }
            default(info);
        }));
    });
}

/// `diag.Front(level, msg)` 的落点：前端异常写进同一个 app.log（前缀标明来源）
pub fn front(level: &str, message: &str) {
    let text = format!("[前端] {message}");
    match level.trim().to_ascii_uppercase().as_str() {
        "WARN" => warn(&text),
        "INFO" => info(&text),
        _ => error(&text),
    }
}

fn write_line(level: &str, msg: &str) {
    // 日志失败绝不能影响主流程
    let Ok(_guard) = GATE.lock() else { return };
    let _ = fs::create_dir_all(dir());
    rotate();
    if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(app_log_path()) {
        let _ = f.write_all(format!("[{}] [{}] {}\r\n", stamp_full(), level, msg).as_bytes());
    }
}

/// 只保留一代历史（app.1.log），避免无限增长
fn rotate() {
    let p = app_log_path();
    let Ok(md) = fs::metadata(&p) else { return };
    if md.len() < MAX_BYTES {
        return;
    }
    let prev = dir().join("app.1.log");
    let _ = fs::remove_file(&prev);
    let _ = fs::rename(&p, &prev);
}

/* ── 崩溃记录 ───────────────────────────────────────────────────────── */

/// 记录一次崩溃，返回崩溃日志的完整路径（写失败返回 None）
pub fn crash(source: &str, detail: &str) -> Option<String> {
    let _guard = GATE.lock().ok()?;
    fs::create_dir_all(dir()).ok()?;
    let path = dir().join(format!("crash-{}.log", stamp_compact()));
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()))
        .unwrap_or_else(|| PathBuf::from("."));

    let mut s = String::new();
    s.push_str("MF-Mathematics 崩溃记录\r\n");
    s.push_str(&format!("时间    : {}\r\n", stamp_full()));
    s.push_str(&format!("来源    : {source}\r\n"));
    s.push_str(&format!("版本    : {}\r\n", env!("CARGO_PKG_VERSION")));
    s.push_str(&format!("系统    : {} / Rust 宿主 (Tauri v2)\r\n", os_string()));
    s.push_str(&format!("程序目录: {}\r\n", exe_dir.display()));
    s.push_str(&format!("日志目录: {}\r\n\r\n", dir().display()));
    s.push_str("== 异常 ==\r\n");
    s.push_str(detail);
    s.push_str("\r\n\r\n");
    s.push_str(&format!("== 最近日志（app.log 尾部 {CRASH_TAIL_LINES} 行）==\r\n"));
    s.push_str(&tail(&app_log_path(), CRASH_TAIL_LINES));
    fs::write(&path, s.as_bytes()).ok()?;
    prune_crashes();
    Some(path.to_string_lossy().into_owned())
}

fn prune_crashes() {
    let Ok(rd) = fs::read_dir(dir()) else { return };
    let mut names: Vec<String> = rd
        .filter_map(|e| e.ok())
        .filter_map(|e| e.file_name().into_string().ok())
        .filter(|n| n.starts_with("crash-") && n.ends_with(".log"))
        .collect();
    names.sort_by(|a, b| b.cmp(a)); // 新的在前
    for n in names.into_iter().skip(KEEP_CRASH_FILES) {
        let _ = fs::remove_file(dir().join(n));
    }
}

/* ── 读文件尾部 ─────────────────────────────────────────────────────── */

/// 读文件尾部若干行（文件很大时只读尾部 256 KB）；读不到时返回 `(无日志)`，
/// 与 C# 版同文案，前端/诊断包里的表现一致。
pub fn tail(path: &Path, lines: usize) -> String {
    let text = match read_tail_bytes(path, TAIL_CHUNK) {
        Ok(t) => t,
        Err(e) => return format!("(读取日志失败: {e})"),
    };
    if text.is_empty() && !path.exists() {
        return "(无日志)".to_string();
    }
    let normalized = text.replace("\r\n", "\n");
    let all: Vec<&str> = normalized.split('\n').collect();
    let skip = all.len().saturating_sub(lines);
    all[skip..].join("\r\n")
}

fn read_tail_bytes(path: &Path, chunk: u64) -> Result<String, std::io::Error> {
    let mut f = File::open(path)?;
    let len = f.metadata()?.len();
    let start = len.saturating_sub(chunk);
    f.seek(SeekFrom::Start(start))?;
    let mut buf = Vec::new();
    f.read_to_end(&mut buf)?;
    Ok(String::from_utf8_lossy(&buf).into_owned())
}
