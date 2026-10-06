//! handlers.rs —— `(宿主对象, 方法名) → 处理函数` 的注册表
//!
//! 这是"一个通用 IDispatch 服务 10 个桥"的落点：新增一个桥 = 在这里加一个 `match` 分支，
//! COM 那一层（hostobject.rs）一行都不用动。
//!
//! 当前 spike 只实现 `mf`（引擎桥），且只实现前端**真正会调**的四个方法
//! （`lib/bridge.js` 只用 Dispatch / Ready / Version / FunctionExists；
//! C# 版 `MathBridge` 里另外 7 个符号封装方法前端从未调用，故不迁移）。

use std::sync::OnceLock;

use crate::engine::Engine;

/// 从 JS 传进来的实参
pub enum Arg {
    Str(String),
    Num(f64),
    Bool(bool),
    None,
}

/// 回给 JS 的值（其余类型等用到再加，**不预留**）
pub enum Ret {
    Str(String),
    Bool(bool),
    Empty,
}

/// 引擎所在目录 = 宿主 exe 同目录（与 C# 的 AppContext.BaseDirectory 同义）
fn exe_dir() -> std::path::PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()))
        .unwrap_or_else(|| std::path::PathBuf::from("."))
}

fn engine() -> Result<&'static Engine, String> {
    Engine::shared(&exe_dir())
}

/// 与 C# `MathBridge.Dispatch` 的异常信封逐字一致，前端 `parse()` 那层才不用区分实现
fn err_envelope(msg: &str) -> String {
    // 手拼 JSON：这里的 msg 来自引擎/我们自己的固定文案，仍按 JSON 规则转义
    let mut out = String::from("{\"isError\":true,\"value\":\"");
    for ch in msg.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push_str("\"}");
    out
}

fn arg_str(args: &[Arg], i: usize) -> Option<&str> {
    match args.get(i) {
        Some(Arg::Str(s)) => Some(s.as_str()),
        _ => None,
    }
}

pub fn call(object: &str, method: &str, args: &[Arg]) -> Ret {
    match object {
        "mf" => mf(method, args),
        other => Ret::Str(err_envelope(&format!("未知宿主对象：{other}"))),
    }
}

fn mf(method: &str, args: &[Arg]) -> Ret {
    match method {
        "Ready" => Ret::Bool(true),
        "Version" => Ret::Str("mf_mathematics (Rust 宿主 · wry/WebView2)".to_string()),
        // 通用透传：与 C# 版一样，引擎新增 action 不需要改宿主
        "Dispatch" => {
            let Some(fn_name) = arg_str(args, 0) else {
                return Ret::Str(err_envelope("Dispatch 缺少函数名"));
            };
            let args_json = arg_str(args, 1).unwrap_or("{}");
            match engine() {
                Ok(e) => match e.call_json(fn_name, args_json) {
                    Ok(json) => Ret::Str(json),
                    Err(msg) => Ret::Str(err_envelope(&msg)),
                },
                Err(msg) => Ret::Str(err_envelope(&msg)),
            }
        }
        "FunctionExists" => match arg_str(args, 0) {
            Some(name) => match engine() {
                Ok(e) => Ret::Bool(e.exists(name)),
                Err(_) => Ret::Bool(false),
            },
            None => Ret::Bool(false),
        },
        other => Ret::Str(err_envelope(&format!("mf 没有这个方法：{other}"))),
    }
}

/// 供 main 打印一句自检（引擎在不在、注册了多少 action）
pub fn engine_selfcheck() -> String {
    match engine() {
        Ok(e) => match e.call_json("list_functions", "{}") {
            Ok(json) => {
                let count = json
                    .split("\"count\":")
                    .nth(1)
                    .and_then(|s| s.split(|c: char| !c.is_ascii_digit()).next())
                    .unwrap_or("?")
                    .to_string();
                format!("引擎已加载，list_functions.count = {count}")
            }
            Err(msg) => format!("引擎已加载但调用失败：{msg}"),
        },
        Err(msg) => format!("引擎未加载：{msg}"),
    }
}

static _UNUSED: OnceLock<()> = OnceLock::new();
