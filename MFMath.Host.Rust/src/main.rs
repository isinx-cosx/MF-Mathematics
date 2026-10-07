//! main.rs —— MFMath Rust 宿主（**Tauri v2**）
//!
//! 从 wry/tao 换到 Tauri：窗口由 Tauri 建（`create: false`，我们自己在 setup 里取 HWND 做
//! DWM/窗口操作），页面资产从 exe 同目录的 `wwwroot` 读、映射到 `https://mfmath.local/index.html`。
//!
//! **接缝形状（已定，别再改这一条）**：Tauri 没有 `AddHostObjectToScript`，
//! 但 Tauri 用的就是 WebView2 —— 我们直接走 `with_webview()` → `ICoreWebView2::AddHostObjectToScript`，
//! 把 `hostobject.rs` 的 COM 对象挂上去，于是前端那套
//! `window.chrome.webview.hostObjects.sync.<对象>.<方法>` **同步**调用原样可用（见 `hostobject.rs`）。
//! 这就是当初否掉"全异步 invoke"路线的原因：`mf.Dispatch` 在采样链/绘图网格里是热路径，
//! 必须同步返回字符串（详见 `docs/LINK-LAYER.md` §5 的历史记录）。
//!
//! ⚠ Tauri 的 `invoke` 命令层**已删**（原先的 `commands.rs`）：页面从 `mfmath.local` 调 `invoke`
//! 会被 Tauri 直接拒，而它想兜底的降级路也救不了 `mf`（`Dispatch` 要同步、`invoke` 只有 Promise）。
//!
//! 与 C# 宿主的对外行为保持逐条对齐：无边框窗口（标题栏由页面自绘）、尺寸 1240×820、
//! 最小 980×640、DWM 圆角/投影、`%LOCALAPPDATA%\MFMath` 数据目录、CDP 调试端口 9222。

// 必须是 GUI 子系统：Rust 的 bin target 在 Windows 上默认按**控制台**子系统链接，
// 会额外冒出一个空白控制台窗口（输出被重定向时它是空的、标题是 exe 全路径），
// 看起来就像"程序下面多了一个空窗口"。Tauri 官方模板只在 release 关，这里**无条件**关。
#![windows_subsystem = "windows"]

mod account;
mod console;   // ⚠ 文件名不能叫 con.rs：Windows 保留设备名，git 读不了它（见下方注释）
mod dpapi;
mod engine;
mod handlers;
mod hostobject;
mod http;
mod jobs;
mod logging;
mod pack;
mod push;
mod search;
mod selftest;
mod shellopen;
mod site;
mod sys;
mod update;
mod winbridge;

use raw_window_handle::HasWindowHandle;
use webview2_com::Microsoft::Web::WebView2::Win32::{
    COREWEBVIEW2_COLOR, COREWEBVIEW2_HOST_RESOURCE_ACCESS_KIND_ALLOW, ICoreWebView2_3,
    ICoreWebView2Controller2,
};
use windows::core::{Interface, PCWSTR};

use hostobject::{MethodSpec, RetKind};

/* ── 宿主对象的方法表 ────────────────────────────────────────────────────────
 *
 * 这张表有两个用途，必须**同时**正确，否则前端拿到的不是函数：
 *   ① `GetIDsOfNames` 按它给 dispid（下标 + 1）；
 *   ② `CreateDispTypeInfo` 按它造 ITypeInfo —— WebView2 的**同步**代理靠类型信息
 *      区分"方法/属性"；没有它，读 `mf.Dispatch` 会被当成取属性（返回一个字符串），
 *      于是 `mf.Dispatch is not a function`（README §四 S2 卡的就是这个）。
 *
 * 参数类型一律 VT_BSTR（前端宿主对象调用本来就只传字符串），返回类型见 RetKind。
 * 这里列出的方法必须与 handlers.rs 的 match 分支一一对应 —— 表里有、handlers 没有的，
 * 调用时会拿到"没有这个方法"的错误信封。
 */

/// `mf`：与 C# MathBridge 对齐，另加 Rust 侧的异步 job 通道四个方法
/// （`lib/bridge.js` 的 engineCallAsync 靠 DispatchJob 是否存在决定走异步还是退回同步）。
const MF_SPEC: &[MethodSpec] = &[
    MethodSpec { name: "Dispatch", params: &["name", "argsJson"], ret: RetKind::Str },
    MethodSpec { name: "Ready", params: &[], ret: RetKind::Bool },
    MethodSpec { name: "Version", params: &[], ret: RetKind::Str },
    MethodSpec { name: "FunctionExists", params: &["name"], ret: RetKind::Bool },
    MethodSpec { name: "DispatchJob", params: &["name", "argsJson"], ret: RetKind::Str },
    MethodSpec { name: "PollJob", params: &["jobId"], ret: RetKind::Str },
    MethodSpec { name: "CancelJob", params: &["jobId"], ret: RetKind::Str },
    MethodSpec { name: "JobStats", params: &[], ret: RetKind::Str },
    MethodSpec { name: "SolveSymbolic", params: &["expr", "var"], ret: RetKind::Str },
    MethodSpec { name: "DiscriminantSymbolic", params: &["expr", "var"], ret: RetKind::Str },
    MethodSpec { name: "FactorSymbolic", params: &["expr", "var"], ret: RetKind::Str },
    MethodSpec { name: "CompareExpr", params: &["a", "b"], ret: RetKind::Str },
    MethodSpec { name: "SimplifySymbolic", params: &["expr"], ret: RetKind::Str },
    MethodSpec { name: "ExtremaSymbolic", params: &["expr", "var"], ret: RetKind::Str },
    MethodSpec { name: "FreeSymbols", params: &["expr"], ret: RetKind::Str },
    MethodSpec { name: "Differentiate", params: &["expr", "var"], ret: RetKind::Str },
];

/// `sys`：设置面板（对照 C# SettingsBridge）
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

/// `diag`：前端异常入宿主日志（对照 C# LogBridge）
const DIAG_SPEC: &[MethodSpec] =
    &[MethodSpec { name: "Front", params: &["level", "message"], ret: RetKind::Empty }];

/// `win`：窗口操作 + 文件对话框（对照 C# WindowBridge，10 个方法一个不少）
const WIN_SPEC: &[MethodSpec] = &[
    MethodSpec { name: "Minimize", params: &[], ret: RetKind::Empty },
    MethodSpec { name: "ToggleMaximize", params: &[], ret: RetKind::Empty },
    MethodSpec { name: "IsMaximized", params: &[], ret: RetKind::Bool },
    MethodSpec { name: "Close", params: &[], ret: RetKind::Empty },
    MethodSpec { name: "StartDrag", params: &[], ret: RetKind::Empty },
    MethodSpec { name: "SetChromeBackground", params: &["color"], ret: RetKind::Empty },
    MethodSpec { name: "SaveTextFile", params: &["title", "defaultName", "filter", "content", "path"], ret: RetKind::Str },
    MethodSpec { name: "OpenTextFile", params: &["title", "filter", "path"], ret: RetKind::Str },
    MethodSpec { name: "SaveBinaryFile", params: &["title", "defaultName", "filter", "base64", "path"], ret: RetKind::Str },
];

/// `push`：宿主 → 页面 的推送通道（对照 C# PushHub/PushBridge）。
/// 页面侧就不必再问"是宿主没发还是我没收到"——`Info()` 给出宿主侧计数。
const PUSH_SPEC: &[MethodSpec] = &[
    MethodSpec { name: "Info", params: &[], ret: RetKind::Str },
    MethodSpec { name: "Emit", params: &["topic", "payloadJson"], ret: RetKind::Str },
    MethodSpec { name: "Ready", params: &[], ret: RetKind::Bool },
];

/// `update`：更新链（对照 C# UpdateBridge）。
/// 只有提示与"把下载交给浏览器"，**没有**任何自动下载/执行安装包的入口。
const UPDATE_SPEC: &[MethodSpec] = &[
    MethodSpec { name: "Info", params: &[], ret: RetKind::Str },
    MethodSpec { name: "Check", params: &[], ret: RetKind::Str },
    MethodSpec { name: "OpenDownloadPage", params: &["url"], ret: RetKind::Str },
    MethodSpec { name: "PreviewDownloadUrl", params: &["url"], ret: RetKind::Str },
    MethodSpec { name: "CancelAll", params: &[], ret: RetKind::Empty },
    MethodSpec { name: "SelfCheck", params: &[], ret: RetKind::Str },
];

/// `account`：用户系统（对照 C# AccountBridge）。token 只在宿主，页面只见脱敏字段。
const ACCOUNT_SPEC: &[MethodSpec] = &[
    MethodSpec { name: "Info", params: &[], ret: RetKind::Str },
    MethodSpec { name: "Configure", params: &["json"], ret: RetKind::Str },
    MethodSpec { name: "ClearLocal", params: &[], ret: RetKind::Str },
    MethodSpec { name: "Login", params: &["username", "password"], ret: RetKind::Str },
    MethodSpec { name: "LoginEx", params: &["json"], ret: RetKind::Str },
    MethodSpec { name: "Logout", params: &[], ret: RetKind::Str },
    MethodSpec { name: "RefreshProfile", params: &[], ret: RetKind::Str },
    MethodSpec { name: "RefreshToken", params: &[], ret: RetKind::Str },
    MethodSpec { name: "EnsureFresh", params: &["thresholdSec"], ret: RetKind::Bool },
    MethodSpec { name: "Register", params: &["json"], ret: RetKind::Str },
    MethodSpec { name: "SendCode", params: &["email"], ret: RetKind::Str },
    MethodSpec { name: "VerifyCode", params: &["username", "code"], ret: RetKind::Str },
    MethodSpec { name: "ResendCode", params: &["username", "email"], ret: RetKind::Str },
    MethodSpec { name: "ChangePassword", params: &["oldPassword", "newPassword"], ret: RetKind::Str },
    MethodSpec { name: "LoginHistory", params: &[], ret: RetKind::Str },
    MethodSpec { name: "SiteVersion", params: &[], ret: RetKind::Str },
    MethodSpec { name: "Busy", params: &[], ret: RetKind::Bool },
    MethodSpec { name: "CancelAll", params: &[], ret: RetKind::Empty },
    MethodSpec { name: "SelfCheck", params: &[], ret: RetKind::Str },
];

/// `search`：联网搜索（对照 C# `SearchBridge.cs`）。
/// App ID 只在宿主（DPAPI 密文），页面只见 hasWolframKey；结果经 push 推回
///（搜索是慢活，同步返回会把渲染进程冻住几秒）。
/// 方法名与参数个数照前端 `lib/search/bridge.js` 的 `call("XXX", …)` 调用点：
/// `Info Configure SetWolframKey ClearWolframKey SelfCheck CacheStats ClearCache
///  OpenUrl Start Cancel`（另补 C# 桥面里的 `CancelAll` / `Busy`）。
const SEARCH_SPEC: &[MethodSpec] = &[
    MethodSpec { name: "Info", params: &[], ret: RetKind::Str },
    MethodSpec { name: "Configure", params: &["json"], ret: RetKind::Str },
    MethodSpec { name: "SetWolframKey", params: &["key"], ret: RetKind::Str },
    MethodSpec { name: "ClearWolframKey", params: &[], ret: RetKind::Str },
    MethodSpec { name: "Start", params: &["json"], ret: RetKind::Str },
    MethodSpec { name: "Cancel", params: &["requestId"], ret: RetKind::Str },
    MethodSpec { name: "CancelAll", params: &[], ret: RetKind::Str },
    MethodSpec { name: "Busy", params: &[], ret: RetKind::Bool },
    MethodSpec { name: "OpenUrl", params: &["url"], ret: RetKind::Str },
    MethodSpec { name: "CacheStats", params: &[], ret: RetKind::Str },
    MethodSpec { name: "ClearCache", params: &[], ret: RetKind::Str },
    MethodSpec { name: "SelfCheck", params: &[], ret: RetKind::Str },
];

/// `con`：控制台 + 可选组件（对照 C# `ConsoleBridge.cs` + `ComponentDownload.cs`）。
///
/// ⚠ **模块文件叫 `console.rs`，但注册的宿主对象名必须是 `con`**（前端写的是
/// `hostObjects.sync.con`，那是契约）。改名不是因为命名偏好：Windows 把 `con` 当保留设备名，
/// `src/con.rs` 这种文件 **git 索引不了**（`git add` 直接报
/// `open("src/con.rs"): No such file or directory`，而文件明明在磁盘上），
/// 留着它等于这个桥永远进不了版本库。
/// 方法名与参数个数照前端 `lib/console/bridge.js` 的 `c.XXX(...)` 调用点：
/// `Components SetDownloadBase Install Uninstall CancelInstall InstallStatus
///  Start Poll Stop StopAll`（正好 10 个，C# 桥面也是这 10 个）。
///
/// ⚠ `Install` 与 `Start` 的返回是**裸 id 字符串**（`"job3"` / `"run4"`），不是 JSON ——
/// 前端写的是 `String(c.Install(name))`，用例也按裸字符串用。
const CON_SPEC: &[MethodSpec] = &[
    MethodSpec { name: "Components", params: &[], ret: RetKind::Str },
    MethodSpec { name: "SetDownloadBase", params: &["url"], ret: RetKind::Str },
    MethodSpec { name: "Install", params: &["name"], ret: RetKind::Str },
    MethodSpec { name: "Uninstall", params: &["name"], ret: RetKind::Str },
    MethodSpec { name: "CancelInstall", params: &["jobId"], ret: RetKind::Str },
    MethodSpec { name: "InstallStatus", params: &["jobId"], ret: RetKind::Str },
    MethodSpec { name: "Start", params: &["language", "code", "stdin"], ret: RetKind::Str },
    MethodSpec { name: "Poll", params: &["runId"], ret: RetKind::Str },
    MethodSpec { name: "Stop", params: &["runId"], ret: RetKind::Str },
    MethodSpec { name: "StopAll", params: &[], ret: RetKind::Str },
];

/// 要注册的宿主对象。**加一个桥 = 这里加一行 + handlers.rs 加一个分支**，
/// COM 那一层（hostobject.rs）一行都不用动。
const HOST_OBJECTS: &[(&str, &[MethodSpec])] = &[
    ("mf", MF_SPEC),
    ("sys", SYS_SPEC),
    ("diag", DIAG_SPEC),
    ("win", WIN_SPEC),
    ("push", PUSH_SPEC),
    ("update", UPDATE_SPEC),
    ("account", ACCOUNT_SPEC),
    ("search", SEARCH_SPEC),
    ("con", CON_SPEC),
];

/// 同时写 stderr 与 app.log。
/// GUI 子系统下 stdout 不再连终端，所以启动信息不能只靠 println!（重定向时 stderr 仍可见）。
fn note(msg: &str) {
    println!("[rust-host] {msg}");
    logging::info(msg);
}

/// WebView2 用户数据目录。
/// `MF_WEBVIEW2_DIR` 优先（**与 C# 宿主同名开关**，用于"多个宿主实例不能共用同一数据目录"
/// 以及受限上下文里指到可写目录），默认 `%LOCALAPPDATA%\MFMath\webview2`（与 C# 同默认值）。
fn webview_data_dir() -> std::path::PathBuf {
    std::env::var("MF_WEBVIEW2_DIR")
        .ok()
        .filter(|s| !s.trim().is_empty())
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| logging::data_dir().join("webview2"))
}

/// 数据目录锁文件的句柄：**必须活到进程结束** —— 句柄一丢，占用就释放了。
static INSTANCE_GUARD: std::sync::OnceLock<std::fs::File> = std::sync::OnceLock::new();

/// 单实例闸门的结果。**三种情况必须分开**（2026-10-07 踩过一次）：
/// 把"我写不进去"错报成"被别人占着"，会让一个本可启动的宿主硬性起不来，
/// 而且给出的是一个**错误的原因**。
enum DirLock {
    /// 拿到了占用权（句柄必须活到进程结束）
    Held(std::fs::File),
    /// 确实被另一个实例占着（`ERROR_SHARING_VIOLATION`）→ 值得硬性失败并说清是谁
    Busy(String),
    /// 目录不可写等**其它**原因（`ERROR_ACCESS_DENIED` 等）→ **不阻止启动**：
    /// 从工作区内的 `target\debug` 启动就会这样（本机沙箱不允许工作区内进程写工作区外），
    /// 那时宿主仍然能起，只是设置/日志写不进去 —— 别把这种情形变成"启动失败"。
    Unavailable(String),
}

/// 同一个 WebView2 数据目录**只能有一个实例**在用（WebView2 对该目录是独占的，
/// 第二个实例会以 `HRESULT(0x800700AA)`＝"请求的资源在使用中"收场）。
///
/// 为什么要自己先判一次：那个错误码**看不出是谁占着**，用户（和我）只能靠猜。
/// 实测踩过：并行跑用例时另起一个宿主，另一个正常启动的实例就报这个码（2026-10-07）。
///
/// 做法是**独占共享模式**打开数据目录里的一个锁文件（`share_mode(0)`）：
///   · 第二个实例 `open` 会拿到 `ERROR_SHARING_VIOLATION`，我们在建窗口**之前**就能明确报错；
///   · Windows 在进程退出（含崩溃、被杀）时释放句柄，所以**不会留下"假占用"** ——
///     这正是"看文件在不在"的做法不能用的原因；
///   · 锁文件里写着持有者的 pid，报错时能直接说清是谁占着。
/// 返回的 `File` 必须活到进程结束（调用方存进 static）。
fn lock_webview_dir(dir: &std::path::Path) -> DirLock {
    use std::io::Write;
    use std::os::windows::fs::OpenOptionsExt;
    if let Err(e) = std::fs::create_dir_all(dir) {
        return DirLock::Unavailable(format!("建数据目录 {} 失败：{e}", dir.display()));
    }
    let lock = dir.join(".mf-instance");
    match std::fs::OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        // 只共享"读"：这样下一个实例**能读出**锁文件里的 pid 写进报错信息，
        // 但它要的是写权限（read+write），拿不到 —— 仍然必然共享冲突。
        .share_mode(1 /* FILE_SHARE_READ */)
        .open(&lock)
    {
        Ok(mut f) => {
            // 记账：谁占着这个目录（报错时给下一个实例看）
            let _ = f.set_len(0);
            let _ = f.write_all(format!("pid={}\n", std::process::id()).as_bytes());
            DirLock::Held(f)
        }
        Err(e) => {
            // ERROR_SHARING_VIOLATION(32) = 真的有人占着；其余（多为 ERROR_ACCESS_DENIED=5，
            // 例如从工作区内的 target\debug 启动）是**本进程写不进去**，不是别人占着。
            let code = e.raw_os_error().unwrap_or(0);
            if code != 32 {
                return DirLock::Unavailable(format!(
                    "打不开锁文件 {}：{e}（os error {code}）。\
                     若你是从工作区内的 target\\debug 启动的，本机沙箱不允许它写工作区外 —— \
                     把 exe 连同 DLL/wwwroot 拷到工作区外再跑。",
                    lock.display()
                ));
            }
            let holder = std::fs::read_to_string(&lock)
                .ok()
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
                .unwrap_or_else(|| "（读不到持有者信息）".to_string());
            DirLock::Busy(format!(
                "WebView2 数据目录正被另一个实例占用：{}（{holder}）\n原始错误：{e}",
                dir.display()
            ))
        }
    }
}

/// 宿主 exe 所在目录（引擎 DLL、wwwroot 都按它找）
fn exe_dir() -> std::path::PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()))
        .unwrap_or_else(|| std::path::PathBuf::from("."))
}

/// UI 目录：**与 C# 宿主读同一份**（README §六 的原话："Release 的 `wwwroot` 是
/// `MF_UI/MFMath.UI.Vue/dist` 的拷贝，Rust 宿主读同一份"）。
///
/// 为什么不直接用 Tauri 的 `frontendDist`（把 dist 嵌进 exe）：那样页面 URL 会变成
/// `http://tauri.localhost/`，而 47 个 CDP 用例、C# 宿主、以及"改了前端只要重拷 dist"
/// 这条工作流，全都以 `https://mfmath.local/` 为准。嵌进去的资产仍然保留，只是当兜底 ——
/// 没有 `wwwroot` 时（比如直接跑 `cargo run` 没同步过 UI）仍然能起来。
fn wwwroot_dir() -> std::path::PathBuf {
    std::env::var("MF_WWWROOT")
        .ok()
        .filter(|s| !s.trim().is_empty())
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| exe_dir().join("wwwroot"))
}

/// 虚拟主机名与首页地址（与 C# 宿主逐字一致：`MainWindow.xaml.cs:187-192`）
const UI_HOST: &str = "mfmath.local";
const UI_URL: &str = "https://mfmath.local/index.html";

/// WebView2 起不来时的**可读**收场：日志 + 崩溃文件 + 一个不阻塞过久的提示框。
///
/// 为什么不能让它走到 Tauri 的 panic：宿主是 GUI 子系统，双击运行时 stderr 没人看得到，
/// 用户只会觉得"点了没反应"，而日志里一行都没有（C# 宿主 commit 7bc5632 修的就是这个）。
fn fail_with_reason(stage: &str, err: &str) -> ! {
    let hint = if err.contains("0x800700AA") {
        "\n\n提示：这个错误码是「请求的资源在使用中」。\n\
         启动前已经查过同目录实例（见日志里的「WebView2 数据目录占用」），所以这次多半是\n\
         **上一次异常退出残留的 WebView2 子进程**还占着数据目录：结束掉 `msedgewebview2.exe`，\n\
         或用环境变量 MF_WEBVIEW2_DIR 指到别的目录再试。"
    } else {
        ""
    };
    let detail = format!(
        "{stage} 失败\n{err}{hint}\n\nexe     : {}\n数据目录: {}",
        exe_dir().display(),
        webview_data_dir().display()
    );
    eprintln!("[rust-host] {detail}");
    logging::error(&detail);
    let crash = logging::crash(stage, &detail).unwrap_or_else(|| "（崩溃文件写不出来）".into());

    // 提示框放在线程里 + 最多等 20 秒：用户能看到原因，自动化跑批也不会被永久挂住
    let text = format!("MF-Mathematics 启动失败\n\n{err}{hint}\n\n崩溃记录：{crash}");
    let (tx, rx) = std::sync::mpsc::channel::<()>();
    let _ = std::thread::Builder::new().name("mf-alert".into()).spawn(move || {
        use windows::core::HSTRING;
        use windows::Win32::UI::WindowsAndMessaging::{MessageBoxW, MB_ICONERROR, MB_OK};
        unsafe {
            let _ = MessageBoxW(
                None,
                &HSTRING::from(text),
                &HSTRING::from("MF-Mathematics 启动失败"),
                MB_OK | MB_ICONERROR,
            );
        }
        let _ = tx.send(());
    });
    let _ = rx.recv_timeout(std::time::Duration::from_secs(20));
    std::process::exit(1);
}

fn main() {
    // 最先装 panic 钩子：GUI 子系统下 stderr 没人看得到，panic 必须留下崩溃文件
    logging::install_panic_hook();

    // 无头自检：只验后台任务通道，不需要 WebView2（受限环境里也能跑）
    if std::env::args().any(|a| a == "--selftest-jobs") {
        jobs::selftest();
        return;
    }

    // 无头自检：共享件（DPAPI / sha256 / zip / HTTP 环境）。
    // `--selftest-common --unprotect <base64>` 用来验"另一侧写的密文能不能解开"。
    if std::env::args().any(|a| a == "--selftest-common") {
        let args: Vec<String> = std::env::args().collect();
        let ext = args
            .iter()
            .position(|a| a == "--unprotect")
            .and_then(|i| args.get(i + 1))
            .map(|s| s.as_str());
        selftest::run(ext);
    }

    // 异步 job 通道的常驻工作线程：先起好，界面第一次派活就没有额外延迟
    jobs::start();

    // 端到端用例靠 CDP 驱动界面。WebView2 用这个环境变量追加浏览器参数 ——
    // 换到 Tauri 后依然有效（Tauri 底下还是 WebView2），所以测试链路不用改。
    // SAFETY: 单线程启动阶段、Tauri 初始化之前设置；没有并发读者
    unsafe {
        if std::env::var_os("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS").is_none() {
            std::env::set_var("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--remote-debugging-port=9222");
        }
    }

    note(&format!("引擎自检：{}", handlers::engine_selfcheck()));

    let run = tauri::Builder::default()
        .setup(|app| {
            /* 窗口**手工创建**，而不是让 Tauri 按配置建（所以 tauri.conf.json 里是 `create: false`）。
             *
             * 为什么非得这样：Tauri 在 Windows 上会强制给 WebView2 一个数据目录 ——
             * `tauri-2.12.1/src/manager/webview.rs:559-576`：
             *     if data_directory.is_none() { data_directory = app_local_data_dir() }
             *     if !dir.exists() { create_dir_all(dir)? }      ← 失败就是 "os error 5 拒绝访问"
             * 而 `app_local_data_dir()` 走的是 **known-folder API（SHGetKnownFolderPath）**，
             * **不读 LOCALAPPDATA 环境变量** —— 所以"重定向 LOCALAPPDATA"对它无效，
             * 在受限上下文里就必然撞上 access denied，连窗口都建不出来。
             * Tauri 那句注释 "but we do respect user-specification" 正是留的口子：
             * 我们自己指定数据目录，它就用我们的。 */
            let data_dir = webview_data_dir();
            let _ = std::fs::create_dir_all(&data_dir);
            /* 同目录单实例闸门（见 lock_webview_dir 的注释）：**在建窗口之前**判定，
             * 否则只会拿到一个看不出原因的 0x800700AA。句柄存进 static，活到进程结束。 */
            match lock_webview_dir(&data_dir) {
                DirLock::Held(guard) => {
                    let _ = INSTANCE_GUARD.set(guard);
                }
                DirLock::Busy(msg) => fail_with_reason("WebView2 数据目录占用", &msg),
                /* 写不进去（例如从工作区内的 target\debug 启动）**不阻止启动** ——
                 * 那只影响单实例检查，宿主本身还能跑（只是设置/日志落不了盘）。 */
                DirLock::Unavailable(msg) => note(&format!("跳过单实例检查：{msg}")),
            }

            /* UI 从哪来：优先 exe 同目录的 `wwwroot`（= dist 的拷贝，与 C# 宿主同一份），
             * 没有才退回 Tauri 嵌进 exe 的那份资产。
             *
             * 走 wwwroot 时窗口先开在 `about:blank`：映射虚拟主机与注册宿主对象都在
             * `with_webview` 里做，做完**由我们自己** `Navigate` 到首页 —— 顺序完全确定，
             * 不依赖"注册消息是否跑在页面首帧之前"。 */
            let wwwroot = wwwroot_dir();
            let use_folder = wwwroot.join("index.html").is_file();
            if use_folder {
                note(&format!("UI 目录：{}（虚拟主机 {UI_HOST}）", wwwroot.display()));
            } else {
                note(&format!(
                    "UI 目录 {} 里没有 index.html，改用 Tauri 内嵌资产（页面 URL 会是 tauri.localhost）",
                    wwwroot.display()
                ));
            }

            let start_url = if use_folder {
                tauri::WebviewUrl::External("about:blank".parse()?)
            } else {
                tauri::WebviewUrl::default()
            };
            let win = tauri::WebviewWindowBuilder::new(app, "main", start_url)
                .title("MF-Mathematics")
                .inner_size(1240.0, 820.0)
                .min_inner_size(980.0, 640.0)
                .decorations(false)
                /* ⚠ 先**不显示**。为什么：`about:blank` 的底色是**纯白**，窗口一建出来就露给用户 ——
                 * 实测 0.2 / 0.45 / 0.8 秒三帧都是一整块白窗口（到 1.3 秒才出界面），
                 * 看起来就是"一个空白的、WinForm 味的老式窗口"，很丑。
                 * 显示时机见下面的 on_page_load：**应用页面加载完成**才露出来。 */
                .visible(false)
                .on_page_load(|w, payload| {
                    if matches!(payload.event(), tauri::webview::PageLoadEvent::Finished) {
                        // about:blank 那一轮不算（它只是我们"先注册桥、再导航"用的占位页）
                        if !payload.url().as_str().starts_with("about:") {
                            let _ = w.show();
                        }
                    }
                })
                .data_directory(data_dir.clone())
                .build();
            let win = match win {
                Ok(w) => w,
                Err(e) => fail_with_reason("WebView2 窗口创建", &format!("{e}")),
            };
            note(&format!("WebView2 用户数据目录：{}", data_dir.display()));

            /* 兜底：万一页面永远加载不完（wwwroot 缺文件、虚拟主机映射失败…），窗口不能一直藏着 ——
             * 那样用户会以为程序根本没启动。6 秒后强行显示。 */
            {
                let w = win.clone();
                let _ = std::thread::Builder::new().name("mf-show-watchdog".into()).spawn(move || {
                    std::thread::sleep(std::time::Duration::from_secs(6));
                    if !w.is_visible().unwrap_or(true) {
                        let _ = w.show();
                        logging::warn("页面 6 秒仍未加载完成，先把窗口显示出来（否则看起来像没启动）");
                    }
                });
            }

            /* 宿主对象（同步桥）：这是换壳时唯一真正取舍过的接缝。
             *
             * 取 ICoreWebView2 的路子：Tauri 把底层 WebView2 控制器交出来
             * （`PlatformWebview::controller()` → `ICoreWebView2Controller`），
             * 再由它拿 `ICoreWebView2` —— `AddHostObjectToScript` 与
             * `PostWebMessageAsJson`（推送通道）都在这个接口上。
             *
             * `with_webview` 只是往事件循环**投递**一条消息（tauri-runtime-wry
             * `lib.rs:1552` → `send_user_message`，不阻塞），闭包在主线程上执行。
             * 闭包要求 `Send + 'static`，所以 `&App` 不能直接捕进来 —— 克隆一个 AppHandle。 */
            let app_handle = app.handle().clone();
            win.with_webview(move |pw| {
                let controller = pw.controller();

                /* WebView2 自己的默认底色：不设就是**纯白**。跟浅色主题的 `--bg`（#eef2f9）对齐，
                 * 这样即便有一帧露出底色，看起来也是应用自己的颜色而不是刺眼的白。
                 * （窗口本身等到页面加载完才显示，这里只是双保险。） */
                if let Ok(c2) = controller.cast::<ICoreWebView2Controller2>() {
                    let bg = COREWEBVIEW2_COLOR { A: 255, R: 0xEE, G: 0xF2, B: 0xF9 };
                    // SAFETY: 只写入一个 4 字节的颜色结构
                    if let Err(e) = unsafe { c2.SetDefaultBackgroundColor(bg) } {
                        note(&format!("设置 WebView2 默认底色失败（不影响功能）：{e}"));
                    }
                }

                let core = match unsafe { controller.CoreWebView2() } {
                    Ok(c) => c,
                    Err(e) => {
                        note(&format!("取 CoreWebView2 失败，宿主对象未注册：{e}"));
                        return;
                    }
                };

                // ① 虚拟主机映射（只有 C# 宿主那条 wwwroot 路线才需要）
                let mut url_w: Vec<u16> = Vec::new();
                if use_folder {
                    let host_w: Vec<u16> = UI_HOST.encode_utf16().chain(std::iter::once(0)).collect();
                    let folder_w: Vec<u16> =
                        wwwroot.to_string_lossy().encode_utf16().chain(std::iter::once(0)).collect();
                    match core.cast::<ICoreWebView2_3>() {
                        Ok(wv3) => unsafe {
                            match wv3.SetVirtualHostNameToFolderMapping(
                                PCWSTR(host_w.as_ptr()),
                                PCWSTR(folder_w.as_ptr()),
                                COREWEBVIEW2_HOST_RESOURCE_ACCESS_KIND_ALLOW,
                            ) {
                                Ok(()) => note(&format!("虚拟主机 {UI_HOST} → {}", wwwroot.display())),
                                Err(e) => note(&format!("虚拟主机映射失败：{e}")),
                            }
                        },
                        Err(e) => note(&format!("拿不到 ICoreWebView2_3，无法映射虚拟主机：{e}")),
                    }
                    url_w = UI_URL.encode_utf16().chain(std::iter::once(0)).collect();
                }

                // ② 宿主对象：10 个桥共用一份 COM 实现（hostobject.rs）
                for (name, spec) in HOST_OBJECTS {
                    match hostobject::register(&core, name, spec) {
                        Ok(()) => note(&format!("宿主对象 {name} 已注册（{} 个方法）", spec.len())),
                        Err(e) => note(&format!("宿主对象 {name} 注册失败：{e}")),
                    }
                }

                // ③ 推送通道挂上同一个核心对象（页面侧的监听是 chrome.webview 的 message 事件）
                push::attach(&app_handle, &core);

                // ③ 一切就绪后再导航（顺序确定，不存在"页面先跑、桥后到"的竞态）
                if !url_w.is_empty() {
                    match unsafe { core.Navigate(PCWSTR(url_w.as_ptr())) } {
                        Ok(()) => note(&format!("导航到 {UI_URL}")),
                        Err(e) => note(&format!("导航失败：{e}")),
                    }
                }
            })?;

            // 主窗口句柄交给 `win` 桥（最小化/最大化/关闭/拖拽/背景色），并补 DWM 圆角/投影
            match win.window_handle() {
                Ok(h) => {
                    if let raw_window_handle::RawWindowHandle::Win32(w) = h.as_raw() {
                        let hwnd = w.hwnd.get() as isize;
                        winbridge::set_hwnd(hwnd);
                        /* 无边框窗口自己补 DWM 的圆角与投影。
                         * ⚠ 这里曾经有个 bug：`apply_dwm_chrome` 把 DWMNCRENDERINGPOLICY 传成了
                         * 1（= DISABLED，注释却写 ENABLED），结果 DWM 不再渲染非客户区，
                         * Windows 退回经典边框 —— 看起来就是"底部多出一个 WinForm 味的老式窗框"。
                         * 已改成 2（= ENABLED），详见 winbridge.rs 的注释。 */
                        winbridge::apply_dwm_chrome(hwnd);
                    }
                }
                Err(e) => note(&format!("取窗口句柄失败（win 桥的窗口操作会不可用）：{e}")),
            }
            /* ⚠ 这里**没有** `.invoke_handler(...)`：三条 Tauri 命令（`call` / `host_info` /
             * `front_log`）已随 `commands.rs` 一起删掉。理由（实测过，不是理论）：
             *   · 页面从 `mfmath.local` 这个 origin 调 `invoke` 会被 Tauri 直接拒
             *     （`call not allowed. Plugin not found`），所以它们**永远不会成功**；
             *   · 它们想兜底的场景是"wwwroot 缺失、页面退回 `tauri.localhost`"，
             *     但那条路救不了 `mf` —— `Dispatch` 必须**同步**返回，而 `invoke` 只有 Promise；
             *   · `front_log` 那条独立路径的功能已由宿主对象 `diag.Front` 承担（异常上报仍可用）。
             * 前端 `lib/bridge.js` 里的 `tauriInvoke()` 探测保持原样：它在 C# 宿主下本来就返回 null，
             * 留着无害（那是两个宿主共用的那一层）。 */
            note("Tauri WebView2 就绪；宿主对象 9 个（含 diag）；CDP 端口 9222");
            Ok(())
        })
        .run(tauri::generate_context!());

    if let Err(e) = run {
        let msg = format!("{e:#}");
        eprintln!("[rust-host] 运行失败：{msg}");
        if let Some(p) = logging::crash("运行失败", &msg) {
            eprintln!("[rust-host] 崩溃记录：{p}");
        }
        std::process::exit(1);
    }
}
