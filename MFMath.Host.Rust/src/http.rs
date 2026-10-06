//! http.rs —— 共享 HTTP 客户端（`search` / `account` / `update` / `ai` 都用它）
//!
//! ## 为什么是 rustls 而不是 Schannel
//!
//! README §三 定的就是这个（"reqwest 一律用 rustls"）。**但当时的理由被推翻了**，
//! 这里如实记下更正（C# `Http.cs` 里有一整篇取证记录）：
//!
//! 曾经以为"本机 Schannel 坏、所以 .NET 请求全挂"，据此改过代理、改过服务器 TLS。
//! 服务器端 tcpdump 定案：两条连接对比 ——
//!   · Schannel（.NET）：SYN → SYN-ACK → ACK → **In RST（本机自己发的）** → RST
//!   · OpenSSL（Node）：正常完成握手
//! RST 方向证明**是本机发的**，服务器从未拒绝；触发条件是 SNI 里的域名。
//! 真凶是**本机开发沙箱的全量出站阻止规则**，只对部分进程生效 —— 既不是本项目代码，
//! 也不是服务器配置。**浏览器用户与普通用户机器不受影响**（Chromium 走 BoringSSL）。
//!
//! 所以用 rustls 的理由不是"Schannel 坏了"，而是：**不依赖系统 TLS 配置**、
//! 行为与 Chromium 那条链一致、跨机器可复现。仍然是对的选择，只是理由要说对。
//! ⚠ 并且：**不要**因为"某台机器连不上"去关系统代理 —— 那会害到真正需要代理访问
//! AI 端点的用户（本产品用户大量属于这类）。
//!
//! ## 用法约定
//!
//! · 一律用 `blocking` 客户端 + **自己起线程**：宿主对象是同步调用，绝不能在 UI 线程上
//!   等网络；各桥统一的形状是"派活 → 立刻返回 id → 结果通过 push 推回页面"
//!   （`search.Start`/`account.Login` 就是这么设计的）。
//! · 超时一律**显式**给（默认 30 s）：默认的"永远等"会让界面看起来卡死。

use std::time::Duration;

/// 共享客户端（内部有连接池，构造一次即可）
static CLIENT: std::sync::OnceLock<reqwest::blocking::Client> = std::sync::OnceLock::new();

/// 搜索用的浏览器 UA —— 与 C# `SearchBackend.UserAgent` **逐字一致**。
///
/// ⚠ 为什么必须带它：DuckDuckGo 的 HTML 端点对非常规 UA 很不友好（反爬页或直接 403）。
/// C# 一直发的是这句 Chrome UA，而假端点不挑 UA —— **这个差异在本机测不出来**，
/// 只会在用户机器上表现为"搜索没结果"。所以宁可多养一个客户端，也不省这一句。
pub const BROWSER_UA: &str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";

/// 走浏览器 UA 的客户端（只有搜索用它）。**每次新建**，理由同 `client_with_timeout`：
/// 搜索的超时是用户可配的，缓存一个固定超时的客户端迟早会用错超时。
pub fn client_with_timeout_ua(timeout_secs: i64, ua: Option<&str>) -> reqwest::blocking::Client {
    build_with_ua(if timeout_secs <= 0 { 30 } else { timeout_secs }, ua)
}

/// 装一次 rustls 的加密后端。
///
/// 为什么需要它：`Cargo.toml` 里 reqwest 用的是 `rustls-no-provider` —— 默认后端
/// aws-lc-sys 要现场编一大堆 C，本机实测直接编不过（cl.exe D8050「命令行太长」）。
/// 换成 ring 之后就必须**自己**把 provider 装成进程默认，否则第一次发请求会 panic。
pub fn ensure_crypto() {
    static ONCE: std::sync::OnceLock<()> = std::sync::OnceLock::new();
    ONCE.get_or_init(|| {
        if rustls::crypto::ring::default_provider().install_default().is_err() {
            // 已经装过（tauri 或别的依赖先装了）—— 不是错误
        }
    });
}

/// 取共享客户端；`timeout_secs` 为 0 或负数时用 30 s 兜底
pub fn client(timeout_secs: i64) -> &'static reqwest::blocking::Client {
    // OnceLock 里只能放一个，所以超时取"第一次用到的那次" —— 各桥各自的超时差异由
    // `client_with_timeout` 承担，共享的那个只服务默认值（绝大多数调用）
    let _ = timeout_secs;
    CLIENT.get_or_init(|| build(30))
}

/// 单独造一个客户端（需要非默认超时/代理时用）
pub fn client_with_timeout(timeout_secs: i64) -> reqwest::blocking::Client {
    build(if timeout_secs <= 0 { 30 } else { timeout_secs })
}

fn build(timeout_secs: i64) -> reqwest::blocking::Client {
    build_with_ua(timeout_secs, None)
}

/// `ua: None` = 宿主自己的 UA（`MF-Mathematics/<版本>`）；`Some(s)` = 指定 UA（搜索用浏览器 UA）
fn build_with_ua(timeout_secs: i64, ua: Option<&str>) -> reqwest::blocking::Client {
    ensure_crypto();
    reqwest::blocking::Client::builder()
        // 跟随系统代理：产品用户里大量需要代理才能访问 AI 端点（见文件头的告诫）
        .timeout(Duration::from_secs(timeout_secs as u64))
        .user_agent(match ua {
            Some(s) => s.to_string(),
            None => concat!("MF-Mathematics/", env!("CARGO_PKG_VERSION")).to_string(),
        })
        // 重定向交给 reqwest，但限制次数：站点契约里不该出现长链跳转
        .redirect(reqwest::redirect::Policy::limited(5))
        .build()
        .unwrap_or_else(|_| reqwest::blocking::Client::new())
}

/// 这个站点/端点属于"本机回环"吗？
/// 用途：**只**给诊断文案用（"查询会发往哪个站点"这类说明），不作任何放行判断。
pub fn is_loopback(url: &str) -> bool {
    let u = url.to_ascii_lowercase();
    u.contains("://127.0.0.1") || u.contains("://localhost") || u.contains("://[::1]")
}

/// 只保留 scheme://host[:port]，用于界面/日志里说明"发往哪里"（**不泄漏路径与查询串**）
pub fn origin_of(url: &str) -> String {
    match reqwest::Url::parse(url) {
        Ok(u) => {
            let host = u.host_str().unwrap_or("");
            match u.port() {
                Some(p) => format!("{}://{}:{}", u.scheme(), host, p),
                None => format!("{}://{}", u.scheme(), host),
            }
        }
        Err(_) => String::new(),
    }
}

/// 系统里配了什么代理 —— **只写日志，不参与任何决策**（对照 C# `Http.DescribeSystemProxy`）。
/// 目的是让"这台机器当时是什么网络环境"在 app.log 里有据可查，不必事后重猜。
pub fn describe_system_proxy() -> String {
    use windows::Win32::System::Registry::{HKEY_CURRENT_USER, RRF_RT_REG_DWORD, RRF_RT_REG_SZ, RegGetValueW};
    use windows::core::w;

    fn read_dword(name: windows::core::PCWSTR) -> Option<u32> {
        let mut v: u32 = 0;
        let mut cb = std::mem::size_of::<u32>() as u32;
        // SAFETY: 只读当前用户的 Internet Settings；缓冲区大小由 cb 给出
        let rc = unsafe {
            RegGetValueW(
                HKEY_CURRENT_USER,
                w!("Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings"),
                name,
                RRF_RT_REG_DWORD,
                None,
                Some(&mut v as *mut u32 as *mut core::ffi::c_void),
                Some(&mut cb),
            )
        };
        (rc == windows::Win32::Foundation::ERROR_SUCCESS).then_some(v)
    }

    fn read_str(name: windows::core::PCWSTR) -> Option<String> {
        let mut buf = [0u16; 512];
        let mut cb = (buf.len() * 2) as u32;
        // SAFETY: 同上
        let rc = unsafe {
            RegGetValueW(
                HKEY_CURRENT_USER,
                w!("Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings"),
                name,
                RRF_RT_REG_SZ,
                None,
                Some(buf.as_mut_ptr() as *mut core::ffi::c_void),
                Some(&mut cb),
            )
        };
        if rc != windows::Win32::Foundation::ERROR_SUCCESS {
            return None;
        }
        let n = buf.iter().position(|c| *c == 0).unwrap_or(buf.len());
        Some(String::from_utf16_lossy(&buf[..n]))
    }

    let mut parts = vec![match read_dword(w!("ProxyEnable")) {
        Some(v) => format!("ProxyEnable={v}"),
        None => "ProxyEnable=null".into(),
    }];
    if let Some(s) = read_str(w!("ProxyServer")) {
        parts.push(format!("ProxyServer={s}"));
    }
    if let Some(s) = read_str(w!("AutoConfigURL")) {
        parts.push(format!("AutoConfigURL={s}"));
    }
    parts.join("; ")
}
