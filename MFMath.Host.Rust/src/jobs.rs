//! jobs.rs —— 引擎"重活"的后台任务通道（异步）
//!
//! **为什么需要**：同步的 `mf.Dispatch` 会占住 WebView2 的 UI 线程，而引擎里确实有能跑到
//! 分钟级的动作 —— 分形 `mandelbrot`（分辨率 ≤1000 × 迭代 ≤1024 ≈ 1e9 次迭代）、
//! 复平面 `complex_grid`（resolution ≤1000 → 1e6 点）、`expr_eval_grid`（工具箱参数自由，
//! 2000×2000 = 4e6 点）、以及 `factor_integer` / `integrate_double` / `taylor_series`
//! 这类**没有上界**的符号运算。今天它们全在同步通道里，一跑就是"窗口白屏 + 系统判定未响应"。
//!
//! **设计（约束：不改引擎）**：
//!   · 一个常驻工作线程 + 任务队列，引擎调用**串行**执行。
//!     串行不是偷懒：引擎里除 `numerical/numerical_integration.cpp` 的一个 `thread_local`
//!     外**没有任何同步原语**，`math_call` 无锁（api.cpp 就是 dispatch + memcpy）；
//!     并发调用会踩 FLINT/SymEngine 的全局缓存，而这件事没人验证过。一次只跑一个重活也够用。
//!   · `DispatchJob` 入队即返回 jobId（界面立刻拿到，不再阻塞）；界面用 `PollJob` 轮询。
//!   · `CancelJob` 在当前实现里只能做到**停止等待 + 丢弃结果**：引擎没有取消钩子，
//!     工作线程会把它算完。要做到"真停"只能靠进程边界（把执行器换成 worker 子进程 + 杀进程，
//!     **引擎同样一行不用改**）—— 那是下一步。所以界面文案必须是"已取消等待"，不能写"已停止"。
//!   · 后来换成 Tauri 时这一层不用重写：它不依赖 WebView2，只依赖"谁能调引擎"。

use std::collections::{HashMap, VecDeque};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Condvar, Mutex, OnceLock};

use serde_json::json;

use crate::engine::Engine;

/// 一个后台任务的状态
#[derive(Clone)]
struct Job {
    id: String,
    name: String,
    args_json: String,
    /// queued | running | done | error | canceled
    state: &'static str,
    started_ms: u128,
    ms: u128,
    /// 引擎返回的 JSON 信封原文（`{"isError":…,"value":…}`），前端按原样解析
    result: String,
    /// 被取消过：结果回来也不再交付（但工作线程仍会跑完 —— 见模块注释）
    canceled: bool,
}

struct Queue {
    pending: VecDeque<Job>,
    jobs: HashMap<String, Job>,
    /// 当前正在跑的那个 job id（None = 空闲）
    running: Option<String>,
}

fn queue() -> &'static (Mutex<Queue>, Condvar) {
    static Q: OnceLock<(Mutex<Queue>, Condvar)> = OnceLock::new();
    Q.get_or_init(|| {
        (
            Mutex::new(Queue { pending: VecDeque::new(), jobs: HashMap::new(), running: None }),
            Condvar::new(),
        )
    })
}

static SEQ: AtomicU64 = AtomicU64::new(1);

fn exe_dir() -> std::path::PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()))
        .unwrap_or_else(|| std::path::PathBuf::from("."))
}

fn now_ms() -> u128 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0)
}

/// 启动常驻工作线程（幂等；main 启动时调一次）
pub fn start() {
    static STARTED: OnceLock<()> = OnceLock::new();
    STARTED.get_or_init(|| {
        let _ = std::thread::Builder::new()
            .name("mf-engine-jobs".into())
            .spawn(worker_loop);
    });
}

fn worker_loop() {
    let (lock, cv) = queue();
    loop {
        // 取下一个待跑任务（没有就睡，直到有人 notify）
        let mut job = {
            let mut q = match lock.lock() {
                Ok(g) => g,
                Err(_) => return,
            };
            loop {
                if let Some(j) = q.pending.pop_front() {
                    break j;
                }
                match cv.wait(q) {
                    Ok(g) => q = g,
                    Err(_) => return,
                }
            }
        };

        // 还在排队时就被取消：直接了结，不必再算
        if job.canceled {
            let (lock2, _) = queue();
            if let Ok(mut q) = lock2.lock() {
                job.state = "canceled";
                job.ms = 0;
                job.result = String::new();
                q.jobs.insert(job.id.clone(), job);
            }
            continue;
        }

        job.state = "running";
        job.started_ms = now_ms();
        {
            let (lock2, _) = queue();
            if let Ok(mut q) = lock2.lock() {
                q.running = Some(job.id.clone());
                q.jobs.insert(job.id.clone(), job.clone());
            }
        }

        // ⚠ 真正的引擎调用：可能跑很久，且**不可中断**（引擎没有取消钩子）
        let t0 = now_ms();
        let outcome = match Engine::shared(&exe_dir()) {
            Ok(e) => e.call_json(&job.name, &job.args_json),
            Err(msg) => Err(msg),
        };
        let ms = now_ms().saturating_sub(t0);

        let (lock3, cv3) = queue();
        if let Ok(mut q) = lock3.lock() {
            // 以表里的为准（期间可能被取消）
            let mut cur = q.jobs.get(&job.id).cloned().unwrap_or_else(|| job.clone());
            cur.ms = ms;
            if cur.canceled {
                cur.state = "canceled";
                cur.result = String::new();
            } else {
                match outcome {
                    Ok(text) => {
                        cur.state = "done";
                        cur.result = text;
                    }
                    Err(msg) => {
                        cur.state = "error";
                        cur.result = format!("{{\"isError\":true,\"value\":{}}}", json!(msg));
                    }
                }
            }
            q.jobs.insert(cur.id.clone(), cur);
            q.running = None;
        }
        cv3.notify_all();
    }
}

/// 派一个后台任务：入队即返回 `{"ok":true,"jobId":…}`（不等引擎）
pub fn dispatch_job(name: &str, args_json: &str) -> String {
    let id = format!("e-{}", SEQ.fetch_add(1, Ordering::Relaxed));
    let job = Job {
        id: id.clone(),
        name: name.to_string(),
        args_json: args_json.to_string(),
        state: "queued",
        started_ms: now_ms(),
        ms: 0,
        result: String::new(),
        canceled: false,
    };
    let (lock, cv) = queue();
    match lock.lock() {
        Ok(mut q) => {
            q.jobs.insert(id.clone(), job.clone());
            q.pending.push_back(job);
            cv.notify_all();
            json!({ "ok": true, "jobId": id }).to_string()
        }
        Err(e) => json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}

/// 查状态：`{"ok":true,"jobId":…,"state":…,"ms":…,"elapsedMs":…,"result":<引擎信封>}`
/// 还在排队/运行中时 `result` 为空串，界面继续轮询即可。
pub fn poll_job(id: &str) -> String {
    let (lock, _) = queue();
    let q = match lock.lock() {
        Ok(g) => g,
        Err(e) => return json!({ "ok": false, "error": e.to_string() }).to_string(),
    };
    match q.jobs.get(id) {
        None => json!({ "ok": false, "error": "未知的任务 id" }).to_string(),
        Some(j) => json!({
            "ok": true,
            "jobId": j.id,
            "name": j.name,
            "state": j.state,
            "ms": j.ms,
            "elapsedMs": now_ms().saturating_sub(j.started_ms),
            "result": j.result,
        })
        .to_string(),
    }
}

/// 取消：排队中的直接作废；正在跑的**只能**标记为"不再等待"（引擎会算完，见模块注释）
pub fn cancel_job(id: &str) -> String {
    let (lock, cv) = queue();
    let mut q = match lock.lock() {
        Ok(g) => g,
        Err(e) => return json!({ "ok": false, "error": e.to_string() }).to_string(),
    };
    // 排队中 → 直接从队列移除并作废
    if let Some(pos) = q.pending.iter().position(|j| j.id == id) {
        q.pending.remove(pos);
        if let Some(mut j) = q.jobs.get(id).cloned() {
            j.state = "canceled";
            j.canceled = true;
            q.jobs.insert(id.to_string(), j);
        }
        drop(q);
        cv.notify_all();
        return json!({ "ok": true, "state": "canceled", "note": "尚未开始，已作废" }).to_string();
    }
    // 正在跑 → 标记；结果回来时会被丢弃
    match q.jobs.get_mut(id) {
        None => json!({ "ok": false, "error": "未知的任务 id" }).to_string(),
        Some(j) => {
            j.canceled = true;
            let running = j.state == "running";
            json!({
                "ok": true,
                "state": if running { "running" } else { j.state },
                "note": if running {
                    "已停止等待；引擎不支持中途停止，它会把这一步算完后丢弃结果"
                } else {
                    "已作废"
                },
            })
            .to_string()
        }
    }
}

/// 供自检/诊断：排队几个、谁在跑
pub fn stats() -> String {
    let (lock, _) = queue();
    match lock.lock() {
        Ok(q) => json!({
            "pending": q.pending.len(),
            "running": q.running,
            "total": q.jobs.len(),
        })
        .to_string(),
        Err(e) => json!({ "error": e.to_string() }).to_string(),
    }
}

/* ── 无头自检：`mfmath-host-rust.exe --selftest-jobs` ────────────────────
 *
 * **不依赖 WebView2**，所以受限环境下也能验（这正是它的用处：宿主在沙箱里起不来的
 * 时候，通道逻辑仍然可以被验证）。验的是派活 → 串行排队 → 轮询 → 完成 →
 * 取消（排队中 / 运行中）这几条语义。 */

fn poll_json(id: &str) -> serde_json::Value {
    serde_json::from_str(&poll_job(id)).unwrap_or_else(|_| json!({}))
}

fn wait_final(id: &str, timeout_ms: u64) -> serde_json::Value {
    let t0 = std::time::Instant::now();
    loop {
        let st = poll_json(id);
        match st["state"].as_str() {
            Some("done") | Some("error") | Some("canceled") => return st,
            _ => {}
        }
        if t0.elapsed().as_millis() as u64 > timeout_ms {
            return st;
        }
        std::thread::sleep(std::time::Duration::from_millis(50));
    }
}

fn selftest_line(ok: bool, name: &str, detail: String) -> (bool, String) {
    (ok, format!("{} {:<30} {}", if ok { "[PASS]" } else { "[FAIL]" }, name, detail))
}

pub fn selftest() {
    start();
    let mut ok = true;
    let mut out: Vec<String> = Vec::new();
    let heavy = "{\"xmin\":-2.2,\"xmax\":0.8,\"ymin\":-1.2,\"ymax\":1.2,\"width\":600,\"height\":600,\"max_iter\":256}";
    let light = "{\"xmin\":-2.2,\"xmax\":0.8,\"ymin\":-1.2,\"ymax\":1.2,\"width\":64,\"height\":64,\"max_iter\":16}";
    let jid = |s: &str| serde_json::from_str::<serde_json::Value>(s).unwrap_or_else(|_| json!({}))["jobId"]
        .as_str()
        .unwrap_or("")
        .to_string();

    // ① 小活：派 → 等 → 结果是引擎信封且数值正确
    let id1 = jid(&dispatch_job("expr_eval", "{\"expr\":\"x^2\",\"x\":3}"));
    let st1 = wait_final(&id1, 20_000);
    let inner: serde_json::Value =
        serde_json::from_str(st1["result"].as_str().unwrap_or("{}")).unwrap_or_else(|_| json!({}));
    let good = st1["state"] == "done"
        && inner["value"].as_f64().map(|v| (v - 9.0).abs() < 1e-9).unwrap_or(false);
    let (o, l) = selftest_line(good, "小活：完成且结果正确", format!("state={} result={}", st1["state"], st1["result"]));
    ok &= o;
    out.push(l);

    // ② 重活 + 串行：第二个必须还在排队（引擎调用串行化）
    let id2 = jid(&dispatch_job("mandelbrot", heavy));
    let id3 = jid(&dispatch_job("mandelbrot", light));
    std::thread::sleep(std::time::Duration::from_millis(200));
    let s2 = poll_json(&id2);
    let s3 = poll_json(&id3);
    let (o, l) = selftest_line(
        s2["state"] == "running" && s3["state"] == "queued",
        "重活在跑、第二个排队（串行）",
        format!("job2={} job3={}", s2["state"], s3["state"]),
    );
    ok &= o;
    out.push(l);

    // ③ 取消"排队中"的任务：立刻作废，不必等它开跑
    let c3: serde_json::Value = serde_json::from_str(&cancel_job(&id3)).unwrap_or_else(|_| json!({}));
    let (o, l) = selftest_line(
        c3["state"] == "canceled" && c3["note"].as_str().unwrap_or("").contains("作废"),
        "取消排队中的任务",
        format!("{}", c3),
    );
    ok &= o;
    out.push(l);

    // ④ 重活跑完：结果点数 = w*h（说明引擎真的算完了）
    let s2f = wait_final(&id2, 120_000);
    let pts = serde_json::from_str::<serde_json::Value>(s2f["result"].as_str().unwrap_or("{}"))
        .ok()
        .and_then(|v| v["value"].as_array().map(|a| a.len()))
        .unwrap_or(0);
    let (o, l) = selftest_line(
        s2f["state"] == "done" && pts == 600 * 600,
        "重活完成、点数正确",
        format!("state={} pts={} ms={}", s2f["state"], pts, s2f["ms"]),
    );
    ok &= o;
    out.push(l);

    // ⑤ 取消"运行中"的任务：状态如实说明"停止等待"，且结果不再交付
    let id4 = jid(&dispatch_job("mandelbrot", heavy));
    std::thread::sleep(std::time::Duration::from_millis(250));
    let c4: serde_json::Value = serde_json::from_str(&cancel_job(&id4)).unwrap_or_else(|_| json!({}));
    let s4 = wait_final(&id4, 120_000);
    let (o, l) = selftest_line(
        c4["note"].as_str().unwrap_or("").contains("停止等待")
            && s4["state"] == "canceled"
            && s4["result"].as_str().unwrap_or("").is_empty(),
        "取消运行中的任务（如实说明 + 丢弃结果）",
        format!("note={} final={}", c4["note"], s4["state"]),
    );
    ok &= o;
    out.push(l);

    println!("{}", out.join("\n"));
    println!("stats: {}", stats());
    println!("RESULT|selftest-jobs|{}|{}", if ok { "PASS" } else { "FAIL" }, out.len());
    std::process::exit(if ok { 0 } else { 1 });
}
