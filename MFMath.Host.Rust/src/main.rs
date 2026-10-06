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
mod logging;
mod sys;

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

use hostobject::{MethodSpec, RetKind};

/// `mf` 桥的方法表：**这既是 GetIDsOfNames/Invoke 的依据，也是 ITypeInfo 的依据**
/// （WebView2 靠类型信息区分"方法/属性"，缺了它 `mf.Dispatch` 会被当属性读成字符串）。
/// 前四个是前端 `lib/bridge.js` 真正会调的；后面八个是 C# `MathBridge` 的具名符号封装 ——
/// 前端不走它们，但项目自带的端到端用例直接调（cdp-plot-extrema-domain 等），
/// 而且它们是 C# 宿主的公开 API：少了就是宿主能力缩水。
const MF_SPEC: &[MethodSpec] = &[
    MethodSpec { name: "Dispatch", params: &["name", "argsJson"], ret: RetKind::Str },
    MethodSpec { name: "Ready", params: &[], ret: RetKind::Bool },
    MethodSpec { name: "Version", params: &[], ret: RetKind::Str },
    MethodSpec { name: "FunctionExists", params: &["name"], ret: RetKind::Bool },
    // ↓ C# MathBridge 的薄包装（参数默认值也照抄：var 缺省 "x"）
    MethodSpec { name: "SolveSymbolic", params: &["expr", "var"], ret: RetKind::Str },
    MethodSpec { name: "DiscriminantSymbolic", params: &["expr", "var"], ret: RetKind::Str },
    MethodSpec { name: "FactorSymbolic", params: &["expr", "var"], ret: RetKind::Str },
    MethodSpec { name: "CompareExpr", params: &["a", "b"], ret: RetKind::Str },
    MethodSpec { name: "SimplifySymbolic", params: &["expr"], ret: RetKind::Str },
    MethodSpec { name: "ExtremaSymbolic", params: &["expr", "var"], ret: RetKind::Str },
    MethodSpec { name: "FreeSymbols", params: &["expr"], ret: RetKind::Str },
    MethodSpec { name: "Differentiate", params: &["expr", "var"], ret: RetKind::Str },
];

/// `sys` 桥（设置面板）：对照 C# `SettingsBridge.cs` 的 8 个公开方法，一个不少。
/// 返回都是 JSON 字符串（前端 `lib/settings/bridge.js` 自己 parse）。
const SYS_SPEC: &[MethodSpec] = &[
    MethodSpec { name: "Info", params: &[], ret: RetKind::Str },
    MethodSpec { name: "EngineReport", params: &[], ret: RetKind::Str },
    MethodSpec { name: "StoreList", params: &[], ret: RetKind::Str },
    MethodSpec { name: "StoreRead", params: &["name"], ret: RetKind::Str },
    MethodSpec { name: "StoreWrite", params: &["name", "json"], ret: RetKind::Str },
    MethodSpec { name: "StoreDelete", params: &["name"], ret: RetKind::Str },
    MethodSpec { name: "OpenPath", params: &["path"], ret: RetKind::Str },
    MethodSpec { name: "ExportDiagnostics", params: &[], ret: RetKind::Str },
];

/// `diag` 桥（前端异常 → 宿主日志）：对照 C# `LogBridge.cs`，只有一件事、一个方法。
const DIAG_SPEC: &[MethodSpec] = &[MethodSpec { name: "Front", params: &["level", "message"], ret: RetKind::Empty }];

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
        // ① 完整崩溃记录（环境 + 异常 + app.log 尾部），单文件即可复盘
        if let Some(p) = logging::crash("启动失败", &msg) {
            eprintln!("[rust-host] 崩溃记录：{p}");
        }
        // ② 同目录再放一份：双击启动时 stderr 看不到，这一份是留给用户的最近线索
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

    // WebView2 的用户数据目录：与 C# 宿主同名开关 MF_WEBVIEW2_DIR。
    // 为什么必须有：C# 版那段注释写得很清楚 —— 多个宿主实例不能共用同一个数据目录；
    // 另外在受限上下文里 %LOCALAPPDATA% 不可写时，指到可写目录是唯一的出路。
    let mut web_context = match std::env::var("MF_WEBVIEW2_DIR") {
        Ok(d) if !d.trim().is_empty() => {
            let p = PathBuf::from(d.trim());
            let _ = std::fs::create_dir_all(&p);
            println!("[rust-host] WebView2 用户数据目录：{}", p.display());
            wry::WebContext::new(Some(p))
        }
        _ => wry::WebContext::new(None),
    };
    // 让出一份 'static：单窗口宿主里数据目录要活到进程结束
    let web_context: &'static mut wry::WebContext = Box::leak(Box::new(web_context));

    // 与 C# Release 版同样的浏览器参数（wry 的默认值要自己带上，见其文档）
    let webview = WebViewBuilder::new_with_web_context(web_context)
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
    //    方法表 + 由它造出的 ITypeInfo 都在 hostobject.rs
    //    一个通用 IDispatch 服务所有桥：加一个桥 = 这里加一行 + handlers.rs 加一个分支
    hostobject::register(&core, "mf", MF_SPEC)?;
    hostobject::register(&core, "sys", SYS_SPEC)?;
    hostobject::register(&core, "diag", DIAG_SPEC)?;

    // ③ 导航（与 C# 的发布模式一致）
    unsafe { core.Navigate(w!("https://mfmath.local/index.html"))? };
    println!("[rust-host] WebView2 就绪；宿主对象 mf / sys / diag 已注册；CDP 端口 9222");

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
