//! shellopen.rs —— 用系统默认程序打开链接（**唯一实现**，带协议闸门）
//!
//! 为什么要抽出来：搜索的"打开结果"、更新的"打开下载页"都要它，而它带一条**安全闸门** ——
//! 只放行 http/https。闸门写两份就迟早有一份被改坏，而且改坏的那份不会有人注意。
//!
//! 不放行其它协议的理由（C# `ShellOpen.cs` 的原话）：`file:`、`ms-settings:`、各种自定义
//! 协议都能用系统处理程序**启动本机程序** —— 那已经不是"打开链接"，而是"用任意协议启动
//! 程序"的原语。搜索结果与下载地址都是外部内容，不能让它们碰到这个能力。
//!
//! ⚠ 判定用**真正的 URL 解析**而不是 `starts_with("https://")`：后者会放过
//! `javascript:location='https://x'` 这种混进来的串。

use windows::core::{HSTRING, PCWSTR};
use windows::Win32::UI::Shell::ShellExecuteW;
use windows::Win32::UI::WindowsAndMessaging::SW_SHOWNORMAL;

/// 只接受 http/https；返回是否放行
pub fn is_allowed(url: &str) -> bool {
    let u = url.trim();
    if u.is_empty() {
        return false;
    }
    match reqwest::Url::parse(u) {
        Ok(parsed) => matches!(parsed.scheme(), "http" | "https"),
        Err(_) => false,
    }
}

/// 放行则用系统默认浏览器打开
pub fn open(url: &str) -> Result<(), String> {
    if !is_allowed(url) {
        return Err("只允许打开 http/https 链接".into());
    }
    let op = HSTRING::from("open");
    let file = HSTRING::from(url.trim());
    // SAFETY: 三个字符串都是本函数栈上的 HSTRING，活得比调用久；hwnd 传 None 表示无属主窗口
    let r = unsafe {
        ShellExecuteW(
            None,
            PCWSTR(op.as_ptr()),
            PCWSTR(file.as_ptr()),
            PCWSTR::null(),
            PCWSTR::null(),
            SW_SHOWNORMAL,
        )
    };
    // ShellExecuteW 的约定：返回值 > 32 才算成功
    let code = r.0 as isize;
    if code > 32 {
        Ok(())
    } else {
        Err(format!("打开失败（ShellExecute 返回 {code}）"))
    }
}
