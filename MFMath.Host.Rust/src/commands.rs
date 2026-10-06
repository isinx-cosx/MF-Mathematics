//! commands.rs —— Tauri 命令层（替代 WebView2 的宿主对象注入）
//!
//! **为什么只用一个命令**：原先 10 个桥是通过 `AddHostObjectToScript` 注入的 COM 对象
//! （`window.chrome.webview.hostObjects.sync.<对象>.<方法>`）。Tauri 没有这条路，
//! 只有 `invoke(命令名, 参数)`。与其给 68 个方法各写一个 Tauri 命令，不如保留
//! **一个通用 `call(object, method, args)`** —— 它直接复用 handlers.rs 里那张
//! 已经跑通全量用例的注册表（`handlers::call`），前端也只需要在 lib/*/bridge.js
//! 那一层把"取宿主对象"换成"发一条 invoke"，调用点几乎不用动。
//!
//! 返回值统一是 JSON 字符串（与 WebView2 的同步桥**逐字一致**），这样前端
//! 那些 `parse(x)` 逻辑一行都不用改 —— 它们本来就在解析字符串。

use serde_json::{json, Value};

use crate::handlers::{self, Arg, Ret};

/// 把前端传来的值转成 handlers 认的实参。
/// 前端一直传的是字符串（`mf.Dispatch("expr_eval", '{"expr":…}')`），
/// 但通用命令也会被用来传数字/布尔（窗口尺寸之类），所以这里三种都收。
fn to_arg(v: &Value) -> Arg {
    match v {
        Value::String(s) => Arg::Str(s.clone()),
        Value::Number(n) => Arg::Num(n.as_f64().unwrap_or(0.0)),
        Value::Bool(b) => Arg::Bool(*b),
        Value::Null => Arg::None,
        // 对象/数组：按 JSON 文本传下去（引擎参数本来就是 JSON 文本）
        other => Arg::Str(other.to_string()),
    }
}

/// 通用桥调用：`invoke("call", { object, method, args })`
///
/// 返回 JSON 字符串（与宿主对象同步桥的返回**同一形状**）：
///   · 字符串类 → 原文
///   · 布尔类   → `"true"` / `"false"`
///   · void 类  → `null`
#[tauri::command]
pub fn call(object: String, method: String, args: Option<Vec<Value>>) -> Value {
    let argv: Vec<Arg> = args.unwrap_or_default().iter().map(to_arg).collect();
    match handlers::call(&object, &method, &argv) {
        Ret::Str(s) => json!(s),
        Ret::Bool(b) => json!(if b { "true" } else { "false" }),
        Ret::Empty => Value::Null,
    }
}

/// 宿主自述：给界面显示"跑在哪个壳里"，也方便端到端用例断言换壳成功。
#[tauri::command]
pub fn host_info() -> Value {
    json!({
        "host": "rust-tauri",
        "tauri": tauri::VERSION,
        "runtime": "WebView2 (Tauri v2)",
        "os": crate::logging::os_string(),
    })
}

/// 前端异常上报 → 宿主日志（对应原来的 `diag.Front`，改成命令没必要时可以走 call，
/// 但异常上报要在"桥本身可能坏了"的时候还能用，所以单独留一条命令）。
#[tauri::command]
pub fn front_log(level: String, message: String) {
    crate::logging::front(&level, &message);
}
