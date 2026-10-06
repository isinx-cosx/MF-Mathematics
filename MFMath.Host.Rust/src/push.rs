//! push.rs —— 宿主 → 页面 的**推送通道**（对照 C# `PushHub.cs` + `PushBridge.cs`）
//!
//! 为什么需要它（C# 版注释里的原话，这里同样成立）：在它之前，宿主与界面之间只有
//! "页面发起、一问一答"的同步桥与轮询两种办法；**宿主主动说话**（安装进度、控制台跑完、
//! AI 流式、搜索结束）只能靠轮询 —— 延迟固定、空转浪费。
//!
//! 机制：WebView2 的原生 `PostWebMessageAsJson`，页面侧收在 `chrome.webview` 的 message
//! 事件上（`src/lib/push.js`）。**前端一行都不用改** —— 这条路挂在 WebView2 上，
//! 不挂在某个框架上，所以换宿主时原样保留。
//!
//! ## 为什么发一条消息要绕这么大一圈（2026-10-07 三个坑，都实测过）
//!
//! **坑一：不能在同步宿主对象回调里直接 post。**
//! `push.Emit` 是同步宿主对象方法，调用期间浏览器/渲染进程正阻塞等我们的 `Invoke` 返回；
//! 此时再调回 `ICoreWebView2::PostWebMessageAsJson` 就是重入等待 ——
//! 现象：`Emit` 永不返回、页面随之失去响应（而且 stderr 与崩溃日志里一条都没有）。
//!
//! **坑二：`run_on_main_thread` 在主线程上调用等于没推迟。**
//! tauri-runtime-wry 的 `send_user_message`（`lib.rs:263`）有这么一段优化：
//! ```ignore
//! if current_thread().id() == self.main_thread_id { handle_user_message(...) }  // ← 就地执行
//! else { self.proxy.send_event(message) }                                        // ← 真正排队
//! ```
//! 我们在宿主对象回调里（就是主线程），所以它当场就把闭包跑了 —— 还是重入。
//! **从别的线程调**才会走 `send_event` 那条路，那才是"排到事件循环下一拍"。
//!
//! **坑三：也不能换个线程直接调 WebView2。**
//! `ICoreWebView2` 既不是 agile 对象、也没有注册 proxy/stub ——
//! 用 `CoMarshalInterThreadInterfaceInStream` 编组会直接失败
//!（实测 `REGDB_E_IIDNOTREG 0x80040155`："找不到 IID 的代理注册"），
//! 拿裸指针从别的线程调则是 UB：实测宿主**当场消失**。
//! 也试过 `SetTimer(hwnd, …, 1ms, proc)`（回调本该落在窗口线程上）：定时器挂上了、
//! `SetTimer` 也返回了非 0，但回调**一次都没被调用**（tao 的消息循环不保证送达）。
//!
//! **坑四（真正的元凶）：别把 `ICoreWebView2` 存成裸指针。**
//! 那个接口是在 `with_webview` 闭包里取到的，闭包一结束引用就被 Release 了 ——
//! 只留一个 `usize`，之后再用就是**悬垂指针**。症状与坑一/坑三**一模一样**：
//! 页面卡死，或者宿主干脆静默消失（stderr、崩溃日志、WER 转储里一条都没有）。
//! 所以 `CoreHandle` 会 AddRef 一份并持有到进程结束 —— 这个坑花的时间最多，别再踩。
//!
//! **所以：worker 线程 → `run_on_main_thread` → 主线程执行 post**（并用 CoreHandle 持有接口）。
//!   · `send` 只把信封塞进 channel，立刻返回，**永不阻塞**调用方；
//!   · 常驻 worker 收到后调 `run_on_main_thread` —— 从 worker 调才是真排队；
//!   · 闭包在事件循环下一拍落到主线程，那时我们的 `Invoke` 早已返回，post 自然通。
//!
//! 三条约束与 C# 版逐条一致：
//!   ① 只在 UI 线程碰 WebView2（由"worker 排队回主线程"保证）；
//!   ② 推送失败**绝不抛**给调用方：页面在导航、窗口在关闭都会失败，只记计数与最后一条错误；
//!   ③ 信封固定 `{topic, seq, ts, payload}`，`seq` 单调递增 —— 页面靠它发现丢消息。

use std::sync::atomic::{AtomicI64, AtomicU64, Ordering};
use std::sync::mpsc::{channel, Receiver, Sender};
use std::sync::{Mutex, OnceLock};

use serde_json::{json, Value};
use tauri::AppHandle;
use webview2_com::Microsoft::Web::WebView2::Win32::ICoreWebView2;
use windows::core::HSTRING;

/// 核心对象的**持有者**。
///
/// ⚠ 不能用裸指针存：`ICoreWebView2` 是在 `with_webview` 闭包里取到的，那个引用在闭包
/// 结束时就被 Release 了；只留一个 `usize` 指针，之后再用就是**悬垂指针** ——
/// 症状是宿主**静默消失**（stderr、崩溃日志、WER 转储里一条都没有，最难查的那种）。
/// 所以这里 clone 一份（AddRef）并让 `OnceLock` 持有到进程结束。
struct CoreHandle(ICoreWebView2);
// SAFETY: 只在主线程上使用（worker 会把 post 排回主线程，见文件头），且持有到进程结束
unsafe impl Send for CoreHandle {}
unsafe impl Sync for CoreHandle {}

static CORE: OnceLock<CoreHandle> = OnceLock::new();

/// 事件循环把手：worker 用它把 post 排回主线程（**必须从 worker 线程调**，见坑二）
static APP: OnceLock<AppHandle> = OnceLock::new();

/// 待发队列（`send` 只往这里丢，立刻返回）
static TX: OnceLock<Sender<String>> = OnceLock::new();

static SEQ: AtomicU64 = AtomicU64::new(0);
static SENT: AtomicU64 = AtomicU64::new(0);
static FAILED: AtomicU64 = AtomicU64::new(0);
static ATTACHED_MS: AtomicI64 = AtomicI64::new(0);
static LAST_TOPIC: Mutex<String> = Mutex::new(String::new());
static LAST_ERROR: Mutex<String> = Mutex::new(String::new());

fn now_ms() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

fn set_last(slot: &Mutex<String>, v: String) {
    if let Ok(mut g) = slot.lock() {
        *g = v;
    }
}

fn get_last(slot: &Mutex<String>) -> String {
    slot.lock().map(|g| g.clone()).unwrap_or_default()
}

/// 在（主线程上、WebView2 就绪之后）挂上通道，并起一个常驻 worker。
pub fn attach(app: &AppHandle, core: &ICoreWebView2) {
    let _ = CORE.set(CoreHandle(core.clone())); // clone = AddRef；随 OnceLock 活到进程结束
    let _ = APP.set(app.clone());
    ATTACHED_MS.store(now_ms(), Ordering::SeqCst);

    let (tx, rx) = channel::<String>();
    match std::thread::Builder::new().name("mf-push".into()).spawn(move || worker(rx)) {
        Ok(_) => {
            let _ = TX.set(tx);
        }
        Err(e) => set_last(&LAST_ERROR, format!("推送 worker 起不来：{e}")),
    }
}

/// 常驻 worker：把每条消息**排回主线程**再发。
/// 关键点：这里不是主线程，所以 `run_on_main_thread` 会真的排队（见文件头坑二）。
fn worker(rx: Receiver<String>) {
    while let Ok(env) = rx.recv() {
        let Some(app) = APP.get().cloned() else { continue };
        if app.run_on_main_thread(move || post(&env)).is_err() {
            FAILED.fetch_add(1, Ordering::SeqCst);
            set_last(&LAST_ERROR, "事件循环已退出，推送无法排队".into());
        }
    }
}

/// **在主线程上**执行（由 worker 排队过来）：这时宿主对象回调早已返回，可以安全 post
fn post(env: &str) {
    let Some(core) = CORE.get() else { return };
    // SAFETY: 主线程 + 接口被 OnceLock 持有到进程结束（见 CoreHandle 的注释）
    match unsafe { core.0.PostWebMessageAsJson(&HSTRING::from(env)) } {
        Ok(()) => {
            SENT.fetch_add(1, Ordering::SeqCst);
        }
        Err(e) => {
            // 页面在导航中 / 窗口在关闭：正常情况，记下来即可
            FAILED.fetch_add(1, Ordering::SeqCst);
            set_last(&LAST_ERROR, e.to_string());
        }
    }
}

/// 通道是否已挂上（`push.Ready` 与 `Info().ready` 都看它）
pub fn ready() -> bool {
    CORE.get().is_some() && APP.get().is_some() && TX.get().is_some()
}

/// 发一条推送。`payload_json` 必须是合法 JSON 文本（空串 = 没有负载）。
/// 返回是否已**排进队列**（不是"已送达"）—— 真正的 post 在主线程的下一拍。
pub fn send(topic: &str, payload_json: &str) -> bool {
    let Some(tx) = TX.get() else {
        FAILED.fetch_add(1, Ordering::SeqCst);
        set_last(&LAST_ERROR, "推送通道未连接（WebView2 尚未就绪或窗口已关闭）".into());
        return false;
    };

    let payload: Value = if payload_json.trim().is_empty() {
        Value::Null
    } else {
        serde_json::from_str(payload_json).unwrap_or(Value::Null)
    };
    let seq = SEQ.fetch_add(1, Ordering::SeqCst) + 1;
    let env = json!({ "topic": topic, "seq": seq, "ts": now_ms(), "payload": payload }).to_string();
    set_last(&LAST_TOPIC, topic.to_string());

    if tx.send(env).is_err() {
        FAILED.fetch_add(1, Ordering::SeqCst);
        set_last(&LAST_ERROR, "推送 worker 已退出".into());
        return false;
    }
    true
}

/// `push.Info()`：通道状态（宿主侧计数 + 最后一条的主题与错误）
pub fn info() -> String {
    json!({
        "ready": ready(),
        "sent": SENT.load(Ordering::SeqCst),
        "failed": FAILED.load(Ordering::SeqCst),
        "seq": SEQ.load(Ordering::SeqCst),
        "attachedMs": ATTACHED_MS.load(Ordering::SeqCst),
        "lastTopic": get_last(&LAST_TOPIC),
        "lastError": get_last(&LAST_ERROR),
        "hostVersion": "push/1 (PostWebMessageAsJson · Rust)",
    })
    .to_string()
}

/// `push.Emit(topic, payloadJson)`：JS → 宿主 → JS 的往返（自测/诊断用）。
/// 校验与 C# 版一致：topic 非空且 ≤120 字符；payload 必须是合法 JSON。
pub fn emit(topic: &str, payload_json: &str) -> String {
    let t = topic.trim();
    if t.is_empty() {
        return json!({ "ok": false, "error": "topic 不能为空" }).to_string();
    }
    if t.chars().count() > 120 {
        return json!({ "ok": false, "error": "topic 过长（上限 120 字符）" }).to_string();
    }
    let payload = payload_json.trim();
    if !payload.is_empty() {
        if let Err(e) = serde_json::from_str::<Value>(payload) {
            return json!({ "ok": false, "error": format!("payload 不是合法 JSON：{e}") }).to_string();
        }
    }
    let ok = send(t, payload);
    if ok {
        json!({ "ok": true, "seq": SEQ.load(Ordering::SeqCst) }).to_string()
    } else {
        json!({ "ok": false, "seq": SEQ.load(Ordering::SeqCst), "error": get_last(&LAST_ERROR) }).to_string()
    }
}
