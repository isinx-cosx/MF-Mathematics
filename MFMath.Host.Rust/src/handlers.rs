//! handlers.rs —— `(宿主对象, 方法名) → 处理函数` 的注册表
//!
//! 这是"一个通用 IDispatch 服务 10 个桥"的落点：新增一个桥 = 在这里加一个 `match` 分支，
//! COM 那一层（hostobject.rs）一行都不用动。
//!
//! `mf`（引擎桥）：四个走前端的通用方法（`lib/bridge.js` 只用 Dispatch / Ready /
//! Version / FunctionExists）+ C# `MathBridge` 的八个具名符号封装（见 SYMBOLIC_ALIASES）。

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
    let mut out = String::from("{\"isError\":true,\"value\":");
    push_json_str(&mut out, msg);
    out.push('}');
    out
}

/// 按 JSON 字符串规则转义并**带引号**追加（手拼 JSON 用；不引第三方库）
fn push_json_str(out: &mut String, s: &str) {
    out.push('"');
    for ch in s.chars() {
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
    out.push('"');
}

/// C# `MathBridge` 的具名符号封装 → 引擎 action（以及参数的默认值）。
/// 全是**薄包装**：把位置参数拼成 JSON 后走同一条 Dispatch 通路，返回信封逐字一致。
/// 前端不走这些名字，但项目自带的端到端用例直接调，而且它们是 C# 宿主的公开 API。
const SYMBOLIC_ALIASES: &[(&str, &str, &[&str])] = &[
    ("SolveSymbolic", "solve_sym", &["expr", "var"]),
    ("DiscriminantSymbolic", "discriminant_sym", &["expr", "var"]),
    ("FactorSymbolic", "factor_sym", &["expr", "var"]),
    ("CompareExpr", "compare_expr", &["a", "b"]),
    ("SimplifySymbolic", "simplify_sym", &["expr"]),
    ("ExtremaSymbolic", "extrema_sym", &["expr", "var"]),
    ("FreeSymbols", "free_symbols_of", &["expr"]),
    ("Differentiate", "diff", &["expr", "var"]),
];

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
        // C# 的具名符号封装：名字 → (action, 参数名)
        other => {
            if let Some((_, action, params)) = SYMBOLIC_ALIASES.iter().find(|(n, _, _)| *n == other) {
                alias_call(action, params, args)
            } else {
                Ret::Str(err_envelope(&format!("mf 没有这个方法：{other}")))
            }
        }
    }
}

/// 具名封装的共同实现：位置参数 → JSON（缺省 `var` 补 "x"，与 C# 默认参数一致），
/// 然后走与 `Dispatch` 完全相同的引擎调用与错误信封。
fn alias_call(action: &str, params: &[&str], args: &[Arg]) -> Ret {
    let mut json = String::from("{");
    for (i, p) in params.iter().enumerate() {
        if i > 0 {
            json.push(',');
        }
        push_json_str(&mut json, p);
        json.push(':');
        match args.get(i) {
            // 数值/布尔按字面量给（引擎侧自己解析），字符串按 JSON 字符串给
            Some(Arg::Num(n)) => json.push_str(&n.to_string()),
            Some(Arg::Bool(b)) => json.push_str(if *b { "true" } else { "false" }),
            Some(Arg::Str(s)) => push_json_str(&mut json, s),
            // 缺省：var 默认 "x"（C# 的默认参数），其余给空串
            _ => push_json_str(&mut json, if *p == "var" { "x" } else { "" }),
        }
    }
    json.push('}');

    match engine() {
        Ok(e) => match e.call_json(action, &json) {
            Ok(j) => Ret::Str(j),
            Err(msg) => Ret::Str(err_envelope(&msg)),
        },
        Err(msg) => Ret::Str(err_envelope(&msg)),
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
