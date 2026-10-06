//! main.rs —— MFMath Rust 宿主（spike）
//!
//! 目标（S1 + S2）：窗口 + WebView2 加载 `wwwroot`（虚拟主机 `mfmath.local`，
//! 与 C# 宿主完全一致）+ 注册**同步**宿主对象 `mf`，使前端那 45 处
//! `window.chrome.webview.hostObjects.sync.*` **一行都不用改**。
//!
//! 与 C# 宿主的对应关系：
//!   MainWindow.xaml.cs 的 `SetVirtualHostNameToFolderMapping` + `AddHostObjectToScript`
//!   → 本文件同样的两步；`MathBridge.Dispatch` → handlers.rs 的 `mf`。

// 这是一个 FFI / COM vtable 层：hostobject.rs 里每个 `unsafe extern "system"` 函数体
// 本质上全是 unsafe 操作。edition 2024 要求逐块标注，这里统一关闭 —— 但**不安全边界
// 仍然是有意的**：vtable 的槽位顺序、VARIANT 的联合字段、BSTR 的所有权都按 COM 规则手写。
#![allow(unsafe_op_in_unsafe_fn)]

mod engine;
mod handlers;
mod hostobject;

use std::path::PathBuf;

use tao::dpi::LogicalSize;
use tao::event::{Event, WindowEvent};
use tao::event_loop::{ControlFlow, EventLoopBuilder};
use tao::window::WindowBuilder;
use webview2_com::Microsoft::Web::WebView2::Win32::{
    COREWEBVIEW2_HOST_RESOURCE_ACCESS_KIND_ALLOW, ICoreWebView2_3,
};
use windows::core::{w, Interface, PCWSTR};
use wry::{WebViewBuilder, WebViewBuilderExtWindows, WebViewExtWindows};

/// 前端 `lib/bridge.js` 实际会调用的方法（C# 版 MathBridge 的另外 7 个符号封装前端从未调用）
const MF_METHODS: &[&str] = &["Dispatch", "Ready", "Version", "FunctionExists"];

fn exe_dir() -> PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()))
        .unwrap_or_else(|| PathBuf::from("."))
}

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

/// 启动失败的**留痕**包装。
///
/// 为什么需要它：窗口是在 `event_loop.run()` 才被显示的，所以 `register()` / 导航
/// 一旦失败，用户看到的就是"双击没反应/打不开"，**没有任何信息**。
/// 这与 C# 宿主那次"WebView2 初始化失败被 `if (!e.IsSuccess) return;` 吞掉、
/// 只剩白屏"是同一类问题 —— 失败必须留下可读的证据。
/// 这里同时写 stderr 和 exe 同目录的 `rust-host-error.log`（前者在双击时看不到）。
fn main() {
    if let Err(e) = run() {
        let msg = format!("{e:#}");
        eprintln!("[rust-host] 启动失败：{msg}");
        let _ = std::fs::write(
            exe_dir().join("rust-host-error.log"),
            format!("MFMath Rust 宿主启动失败：\n{msg}\n"),
        );
    }
}

fn run() -> anyhow::Result<()> {
    let event_loop = EventLoopBuilder::new().build();

    let dir = exe_dir();
    let wwwroot = dir.join("wwwroot");
    println!("[rust-host] 程序目录：{}", dir.display());
    println!("[rust-host] {}", handlers::engine_selfcheck());
    if !wwwroot.is_dir() {
        eprintln!(
            "[rust-host] 警告：{} 不存在 —— 前端资源要放到这里\n\
             [rust-host]   Release 值：npm run build 后从 MF_UI/MFMath.UI.Vue/dist 拷过来",
            wwwroot.display()
        );
    }

    let window = WindowBuilder::new()
        .with_title("MF-Mathematics")
        .with_inner_size(LogicalSize::new(1280.0, 840.0))
        .build(&event_loop)?;

    // 与 C# Release 版同样的浏览器参数（wry 的默认值要自己带上，见其文档）
    let webview = WebViewBuilder::new()
        .with_url("about:blank")
        .with_additional_browser_args(
            "--disable-features=msWebOOUI,msPdfOOUI,msSmartScreenProtection \
             --autoplay-policy=no-user-gesture-required \
             --remote-debugging-port=9222",
        )
        .build(&window)?;

    let core = webview.webview();

    // ① 虚拟主机映射：https://mfmath.local/index.html → wwwroot（前端用的是相对资源路径）
    let wv3: ICoreWebView2_3 = core.cast()?;
    let host_w = wide("mfmath.local");
    let folder_w = wide(&wwwroot.to_string_lossy());
    unsafe {
        wv3.SetVirtualHostNameToFolderMapping(
            PCWSTR(host_w.as_ptr()),
            PCWSTR(folder_w.as_ptr()),
            COREWEBVIEW2_HOST_RESOURCE_ACCESS_KIND_ALLOW,
        )?;
    }

    // ② 同步宿主对象：前端 window.chrome.webview.hostObjects.sync.mf.*
    hostobject::register(&core, "mf", MF_METHODS)?;

    // ③ 导航（与 C# 的发布模式一致）
    unsafe { core.Navigate(w!("https://mfmath.local/index.html"))? };
    println!("[rust-host] WebView2 就绪；宿主对象 mf 已注册；CDP 端口 9222");

    event_loop.run(move |event, _, control_flow| {
        *control_flow = ControlFlow::Wait;
        if let Event::WindowEvent {
            event: WindowEvent::CloseRequested,
            ..
        } = event
        {
            *control_flow = ControlFlow::Exit;
        }
        let _keep = &webview; // WebView 必须活到事件循环结束
    });
}
