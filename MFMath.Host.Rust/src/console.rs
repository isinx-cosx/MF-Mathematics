//! con.rs —— 控制台桥（JS 侧：`hostObjects.sync.con`）
//!
//! 对照实现：已移除的 C# 宿主的 ConsoleBridge.cs（899 行）+ `ComponentDownload.cs`（207 行）。
//! 逐条搬运，**包括注释里记下来的那些坑**；与 C# 的有意差异集中列在本文件末尾。
//!
//! 职责：把"跑一段用户代码"这件事放在宿主侧做（进程、文件、组件），而不是浏览器里。
//!   · 组件管理：CPython（嵌入式）与 MinGW（A 档）都是**可选下载**的能力包，
//!     装到 `%LOCALAPPDATA%\MFMath\components\` 下（用户目录可写，不污染安装目录）
//!   · 运行：把代码落成临时文件 → 起子进程 → 异步收 stdout/stderr → 轮询取回
//!
//! 为什么用"开始 + 轮询"而不是同步返回：
//!   JS 走 `hostObjects.sync` 调用时页面会一直阻塞到方法返回；控制台可能跑几十秒，
//!   同步返回会把界面锁死（窗口桥那边已经踩过一次死锁，见 `WindowBridge` 的注释）。
//!   所以 `Start` 立即返回 runId，输出用 `Poll` 增量取。
//!
//! 与引擎的关系：Python 通过同目录的 `mfmath.py`（ctypes → mf_mathematics.dll）调引擎，
//! C++ 侧则链接引擎的导入库；**计算始终由 C++ 引擎完成**，Python/C++ 只做编排。
//!
//! 桥面（10 个方法，参数个数照前端 `lib/console/bridge.js` 的调用点，返回形状照 C#）：
//!   `Components()`                    -> JSON 字符串
//!   `SetDownloadBase(url)`            -> JSON 字符串
//!   `Install(name)`                   -> **裸 id 字符串**（不是 JSON）
//!   `Uninstall(name)`                 -> JSON 字符串
//!   `CancelInstall(jobId)`            -> JSON 字符串
//!   `InstallStatus(jobId)`            -> JSON 字符串
//!   `Start(language, code, stdin)`    -> **裸 id 字符串**（不是 JSON）
//!   `Poll(runId)`                     -> JSON 字符串
//!   `Stop(runId)`                     -> JSON 字符串
//!   `StopAll()`                       -> JSON 字符串

use std::collections::HashMap;
use std::io::{BufRead, Read, Write};
use std::os::windows::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex, MutexGuard, OnceLock};
use std::time::{Duration, Instant};

use serde_json::{json, Value};

/* ══════════════════════════ 常量（与 C# 逐字一致） ══════════════════════════ */

// 组件清单：版本写在目录名里，便于将来并存/回滚
const PYTHON_VERSION: &str = "3.13.15";
const PYTHON_PAYLOAD_NAME: &str = "python-3.13.15-embed-amd64.zip";
const CPP_VERSION: &str = "16.1.0";
const CPP_PAYLOAD_NAME: &str = "mingw-16.1.0-x86_64-seh.zip";

/// 导入库用的 .def：引擎的 C ABI 就这两个入口，不依赖 gendef。
const CPP_DEF_TEXT: &str = "LIBRARY mf_mathematics.dll\r\nEXPORTS\r\n    function_exists\r\n    math_call\r\n";

// ── 组件包校验 ──
// 组件包是几十 MB 的下载物，传输截断、被中间盒改写、放到一半的临时文件都很常见，
// 而解压出错时给出的报错（"解压后没有 python.exe"）根本指不到真正的原因。
// 所以安装前先对整包做一次 SHA-256。
//
// 想换一份自己构建的包时**不用改代码**：在被校验文件旁边放一个同名 `.sha256`
// 文本文件（内容就是十六进制摘要，允许写成 "<hash>  <filename>" 的 sha256sum 格式），
// 有旁文件就以旁文件为准。
const PYTHON_PAYLOAD_SHA256: &str = "D1F04D990AEE1253D8569E8E5104E30FA9F5FA830899F14843448872D936A2CF";
const CPP_PAYLOAD_SHA256: &str = "64AAC3C5FDB16B5A18AE868EA477FE40C798A1581B5B335AB8F0E30A2A10B76B";

/// 组件包的标准大小：界面据此告诉用户"点安装要下多大的东西"
const PYTHON_PAYLOAD_BYTES: i64 = 11_009_825;
const CPP_PAYLOAD_BYTES: i64 = 54_084_880;

/// 单流输出上限，防止刷屏把内存打爆（C# `MaxOutputBytes`）
const MAX_OUTPUT_BYTES: usize = 256 * 1024;
const DEFAULT_TIMEOUT_SEC: u64 = 60;
/// C++ 首次编译要跑 cc1plus + ld
const COMPILE_TIMEOUT_SEC: u64 = 120;

/// 组件包下载的**整体**超时（Rust 侧新增，见文件末尾"有意差异"③）。
/// C# 那边是 `Timeout.InfiniteTimeSpan` + `ConnectTimeout=20s`；reqwest 的 blocking
/// 客户端没有"只限连接"的旋钮，所以这里给一个"慢网也够用、卡死也能收场"的上限。
const DOWNLOAD_TIMEOUT_SEC: u64 = 1800;

/// 组件下载源的默认站点（与 C# `ComponentDownload.DefaultBaseUrl` 一致）
const DEFAULT_BASE_URL: &str = "https://mf-vis-science.cn";

/// 下载组件包时的 UA（与 C# 逐字一致）
const DOWNLOAD_UA: &str = "MFMath-Host/1.0 (+https://mf-vis-science.cn)";

/// CreateProcess 的 CREATE_NO_WINDOW：GUI 宿主起子进程时不要弹控制台黑框
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

/* ══════════════════════════ 路径 ══════════════════════════ */

/// 宿主 exe 所在目录（与 C# 的 `AppContext.BaseDirectory` 同义）
fn app_dir() -> PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()))
        .unwrap_or_else(|| PathBuf::from("."))
}

/// `%LOCALAPPDATA%\MFMath`（与 `logging::data_dir` 同一处：两个宿主共用这个根）
fn data_dir() -> PathBuf {
    crate::logging::data_dir()
}

/// `%LOCALAPPDATA%\MFMath\components`
fn components_root() -> PathBuf {
    data_dir().join("components")
}

/// 下载缓存（组件包放这儿，重装时省一次几十 MB 的下载）
fn cache_dir() -> PathBuf {
    components_root().join("cache")
}

/// 控制台临时工程根目录（每次运行一个 `run<n>\` 子目录）
fn scratch_root() -> PathBuf {
    data_dir().join("console")
}

fn python_dir() -> PathBuf {
    components_root().join(format!("python-{PYTHON_VERSION}"))
}

fn cpp_dir() -> PathBuf {
    components_root().join(format!("mingw-{CPP_VERSION}"))
}

/// `<目录>.staging`：安装的暂存目录（成功路径是 rename 到正式目录，失败/取消才需要清）
fn staging_of(dir: &Path) -> PathBuf {
    let mut s = dir.as_os_str().to_os_string();
    s.push(".staging");
    PathBuf::from(s)
}

/* ══════════════════════════ 小工具 ══════════════════════════ */

/// 取锁；中毒（某个线程 panic 过）也照样拿到底层数据 —— 控制台/安装在 panic 之后
/// 仍然要能用，宿主**不能**因为一次 panic 就永久失去这个桥。
fn guard<T>(m: &Mutex<T>) -> MutexGuard<'_, T> {
    m.lock().unwrap_or_else(|e| e.into_inner())
}

/* ══════════════════════════ 下载源 ══════════════════════════ */

static BASE_URL: OnceLock<Mutex<String>> = OnceLock::new();

/// 初始下载源：环境变量覆盖（企业内网镜像 / 本地测试），否则官网。
///
/// C# 读的是 `MF_COMPONENT_BASE`；Rust 侧先读 `__MF_COMPONENT_BASE`
///（本宿主 `sys.rs` 已经在用的名字，见那里的 `componentBase`），再退到 C# 的名字。
/// 两个都认，是**有意的超集**：换宿主不用改环境变量，也不需要用户改脚本。
fn resolve_initial_base() -> String {
    for key in ["__MF_COMPONENT_BASE", "MF_COMPONENT_BASE"] {
        if let Ok(v) = std::env::var(key) {
            if !v.trim().is_empty() {
                return v.trim_end_matches('/').to_string();
            }
        }
    }
    DEFAULT_BASE_URL.to_string()
}

fn base_cell() -> &'static Mutex<String> {
    BASE_URL.get_or_init(|| Mutex::new(resolve_initial_base()))
}

fn base_url() -> String {
    guard(base_cell()).clone()
}

/// 换组件下载源。默认走官网；企业内网镜像或本地测试可以指到别处。
/// 做成运行时可设，是免得为"换个镜像"重新编译。
///
/// ⚠ **闸门问题（有意不加，理由如下）**：C# 的 `SetBaseUrl` 只做
/// `Trim().TrimEnd('/')`，没有任何 scheme/host 白名单。这里照搬，因为：
///   ① 这不是"把用户数据发到任意地址"那类接口 —— 它只决定**从哪里拉组件包**，
///      而拉回来的东西要过 SHA-256（内置摘要，或包旁边用户自己放的 `.sha256` 旁文件）
///      才能进入解压流程，恶意地址无法借此注入代码；
///   ② 本机端到端用例正是用 `http://127.0.0.1:<port>` 的本地镜像验"断点续传真的续"
///      （`tests/cdp-console.mjs`），加 https/域名白名单会直接把这条用例打死；
///   ③ 两个宿主的对外行为要逐字一致，否则"同一个界面、同一个设置"在两边表现不同。
/// 唯一保留的收紧是**空值回落到默认站点/环境变量**（与 C# 一致），不留空基址。
pub fn set_download_base(url: &str) -> String {
    let next = if url.trim().is_empty() {
        resolve_initial_base()
    } else {
        url.trim().trim_end_matches('/').to_string()
    };
    *guard(base_cell()) = next.clone();
    json!({ "base": next }).to_string()
}

/* ══════════════════════════ 组件状态 ══════════════════════════ */

/// 某组件包当前在不在（缓存目录或应用目录），多大，是不是半成品。
fn payload_state(file_name: &str) -> (bool, u64, bool) {
    if let Some(p) = find_payload(file_name) {
        return (true, std::fs::metadata(&p).map(|m| m.len()).unwrap_or(0), false);
    }
    // 半成品也算"有"：界面要能告诉用户"上次下到一半，点安装会接着下"
    let part = cache_dir().join(format!("{file_name}.part"));
    if part.is_file() {
        // 读不到就当 0 —— 只是显示用，不该因此报错
        return (false, std::fs::metadata(&part).map(|m| m.len()).unwrap_or(0), true);
    }
    (false, 0, false)
}

fn find_payload(file_name: &str) -> Option<PathBuf> {
    let _ = std::fs::create_dir_all(cache_dir());
    let candidates = [cache_dir().join(file_name), app_dir().join("components").join(file_name)];
    candidates.into_iter().find(|p| p.is_file())
}

/// 目录体积（递归求和；读不到就算 0 —— 只是显示用）
fn dir_size(dir: &Path) -> u64 {
    let mut total = 0u64;
    let mut stack = vec![dir.to_path_buf()];
    while let Some(d) = stack.pop() {
        let Ok(rd) = std::fs::read_dir(&d) else { continue };
        for e in rd.flatten() {
            let Ok(md) = e.metadata() else { continue };
            if md.is_dir() {
                stack.push(e.path());
            } else {
                total += md.len();
            }
        }
    }
    total
}

fn python_status() -> Value {
    let dir = python_dir();
    let installed = dir.join("python.exe").is_file() && dir.join("mfmath.py").is_file();
    let bytes = if installed { dir_size(&dir) } else { 0 };
    let (payload, payload_bytes, partial) = payload_state(PYTHON_PAYLOAD_NAME);
    // ⚠ 与 C# 逐字一致：`installed` 已经要求 mfmath.py 存在，所以这条 warning 在 C# 里
    // 本来就是**死分支**。这里照搬不删，为的是两个宿主吐出的 JSON 形状完全一致 ——
    // 前端只读字段名，不会因为一个永远为空的字段而分叉。
    let warning = if installed && !dir.join("mfmath.py").is_file() {
        "缺少 mfmath.py（引擎门面），请重新安装组件"
    } else {
        ""
    };
    json!({
        "installed": installed,
        "version": PYTHON_VERSION,
        "path": dir.to_string_lossy(),
        "bytes": bytes,
        "payloadAvailable": payload,
        "payloadBytes": payload_bytes,
        "payloadPartial": partial,
        "expectBytes": PYTHON_PAYLOAD_BYTES,
        "payloadName": PYTHON_PAYLOAD_NAME,
        "warning": warning,
    })
}

fn cpp_status() -> Value {
    let dir = cpp_dir();
    let gpp = dir.join("bin").join("g++.exe");
    let installed = gpp.is_file();
    let bytes = if installed { dir_size(&dir) } else { 0 };
    let (payload, payload_bytes, partial) = payload_state(CPP_PAYLOAD_NAME);
    // 装好工具链还不够：导入库和门面头文件是"能调用引擎"的前提
    let has_lib = dir.join("lib").join("libmf_mathematics.a").is_file();
    let has_header = dir.join("include").join("mfmath.hpp").is_file();
    let warning = if installed && (!has_lib || !has_header) {
        "C++ 组件不完整（缺导入库或门面头文件），请重新安装"
    } else if !installed {
        "C++ 组件（MinGW A 档）未安装：装上后语言里会自动出现 C++"
    } else {
        ""
    };
    json!({
        "installed": installed,
        "version": CPP_VERSION,
        "path": dir.to_string_lossy(),
        "bytes": bytes,
        "ready": installed && has_lib && has_header,
        "payloadAvailable": payload,
        "payloadBytes": payload_bytes,
        "payloadPartial": partial,
        "expectBytes": CPP_PAYLOAD_BYTES,
        "payloadName": CPP_PAYLOAD_NAME,
        "warning": warning,
    })
}

/// 组件状态（JSON）。JS 用它决定语言下拉里显示什么：
/// C++ 在组件装好之前**不出现**在选项里（默认隐藏）。
pub fn components() -> String {
    json!({
        "engineDir": app_dir().to_string_lossy(),
        "componentsRoot": components_root().to_string_lossy(),
        "downloadBase": base_url(),
        "python": python_status(),
        "cpp": cpp_status(),
    })
    .to_string()
}

/* ══════════════════════════ 安装作业 ══════════════════════════ */

#[derive(Clone)]
struct JobState {
    /// running | done | error
    state: String,
    message: String,
    percent: i32,
}

type JobArc = Arc<Mutex<JobState>>;

static JOBS: OnceLock<Mutex<HashMap<String, JobArc>>> = OnceLock::new();
static JOB_CANCELS: OnceLock<Mutex<HashMap<String, Arc<AtomicBool>>>> = OnceLock::new();
static SEQ: AtomicU64 = AtomicU64::new(1);

fn jobs() -> &'static Mutex<HashMap<String, JobArc>> {
    JOBS.get_or_init(|| Mutex::new(HashMap::new()))
}

fn job_cancels() -> &'static Mutex<HashMap<String, Arc<AtomicBool>>> {
    JOB_CANCELS.get_or_init(|| Mutex::new(HashMap::new()))
}

/// 一次安装失败的两种收场：用户取消 / 真出错
enum InstallFail {
    Cancelled,
    Failed(String),
}

/// `pack::unzip_to` 之类的公共件返回 `Err(String)`，直接用 `?` 转进来
impl From<String> for InstallFail {
    fn from(s: String) -> Self {
        InstallFail::Failed(s)
    }
}

fn job_snapshot(job: &JobArc) -> JobState {
    guard(job).clone()
}

fn job_set(job: &JobArc, percent: Option<i32>, message: Option<&str>) {
    let mut j = guard(job);
    if let Some(p) = percent {
        j.percent = p;
    }
    if let Some(m) = message {
        j.message = m.to_string();
    }
}

/// 把一次安装作业的状态推给界面（topic = `component.install`）
fn push_job(kind: &str, job_id: &str, job: &JobState) {
    let payload = json!({
        "kind": kind,
        "jobId": job_id,
        "state": job.state,
        "percent": job.percent,
        "message": job.message,
    })
    .to_string();
    crate::push::send("component.install", &payload);
}

/// 开始安装组件（后台）。返回 jobId，用 `InstallStatus` 轮询。
///
/// 组件包**不在**缓存里时会先联网下载（带断点续传），下完校验、再解压安装。
/// 这也是「可选组件」能成立的前提：普通用户不需要知道缓存目录在哪。
pub fn install(name: &str) -> String {
    let id = format!("job{}", SEQ.fetch_add(1, Ordering::Relaxed));
    let job: JobArc = Arc::new(Mutex::new(JobState {
        // ⚠ 初值必须是 "running"：前端与实际用例的 `waitJob` 都是
        // "state !== running 就算终态"，用一个 "queued" 初值会让第一次轮询就以为装完了
        //（C# 注释里记的就是这个坑）。
        state: "running".to_string(),
        message: String::new(),
        percent: 0,
    }));
    let cancel = Arc::new(AtomicBool::new(false));

    guard(jobs()).insert(id.clone(), job.clone());
    guard(job_cancels()).insert(id.clone(), cancel.clone());

    let kind = name.trim().to_lowercase();

    // ── 安装线程 ──
    {
        let (job, cancel, id, kind) = (job.clone(), cancel.clone(), id.clone(), kind.clone());
        let _ = std::thread::Builder::new()
            .name(format!("console-install-{kind}"))
            .spawn(move || {
                let outcome = match kind.as_str() {
                    "python" => install_python(&job, &cancel),
                    "cpp" => install_cpp(&job, &cancel),
                    other => Err(InstallFail::Failed(format!("未知组件：{other}"))),
                };
                {
                    let mut j = guard(&job);
                    match outcome {
                        // 成功路径已经在 install_* 里把 state/message 写好了
                        Ok(()) => {}
                        Err(InstallFail::Cancelled) => {
                            j.state = "error".into();
                            j.message = "已取消安装（已下载的部分保留着，下次接着下）".into();
                        }
                        Err(InstallFail::Failed(m)) => {
                            j.state = "error".into();
                            j.message = m;
                        }
                    }
                }
                guard(job_cancels()).remove(&id);
                // 失败/取消时清掉解压用的暂存目录：留着它既占空间，也会让
                // "校验失败时没有留下半装状态" 这条不变量失效（自动化测试正是这么抓到的）。
                clean_staging(&kind);
            });
    }

    // ── 进度推送线程 ──
    // 安装过程有 25 处 job.Message / job.Percent 赋值，逐个加推送既啰嗦又容易漏；
    // 这里用一个**观察线程**每 200ms 采样一次，只在"百分比或文案或状态变了"时推一条，
    // 结束时推最后一条再退出。界面因此不必再 400ms 轮询（轮询作为无推送时的兜底保留）。
    {
        let (job, id, kind) = (job.clone(), id.clone(), kind.clone());
        let _ = std::thread::Builder::new()
            .name(format!("push-job-{kind}"))
            .spawn(move || {
                let mut last = job_snapshot(&job);
                push_job(&kind, &id, &last);
                loop {
                    std::thread::sleep(Duration::from_millis(200));
                    let now = job_snapshot(&job);
                    if now.percent != last.percent || now.message != last.message || now.state != last.state {
                        last = now.clone();
                        push_job(&kind, &id, &now);
                    }
                    if now.state == "done" || now.state == "error" {
                        break;
                    }
                }
            });
    }

    id
}

/// 删掉安装过程的暂存目录（`<组件目录>.staging`）。
/// 只在失败/取消时有意义：成功路径是 `rename(staging → 正式目录)`，暂存目录已经不存在。
/// 下载缓存里的 `.part` **不动** —— 那是断点续传的凭据，与暂存目录是两回事。
fn clean_staging(kind: &str) {
    let dir = match kind {
        "python" => python_dir(),
        "cpp" => cpp_dir(),
        _ => return,
    };
    let s = staging_of(&dir);
    if s.exists() {
        // 清理失败不应掩盖真正的错误
        let _ = std::fs::remove_dir_all(&s);
    }
}

/// 卸载一个可选组件：删掉它的安装目录。
///
/// 只接受 python / cpp 两个已知名字（不接受任意路径，避免变成"删目录"原语）。
/// **不删 cache/**：那里面是下载好的组件包，重装时能省一次下载（几十 MB）。
/// 如果控制台里还有进程在用该组件，删除会失败并把系统错误原样返回——
/// 这比"假装卸掉了"好，用户能看懂"请先关闭控制台里的运行"。
pub fn uninstall(name: &str) -> String {
    let kind = name.trim().to_lowercase();
    let dir = match kind.as_str() {
        "python" => python_dir(),
        "cpp" => cpp_dir(),
        _ => return json!({ "ok": false, "error": format!("未知组件：{kind}") }).to_string(),
    };
    if !dir.exists() {
        return json!({ "ok": true, "removed": false, "bytes": 0 }).to_string();
    }
    let bytes = dir_size(&dir);
    match std::fs::remove_dir_all(&dir) {
        Ok(()) => json!({ "ok": true, "removed": true, "bytes": bytes }).to_string(),
        Err(e) => json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}

/// 取消一个正在进行的安装/下载（保留 .part，下次能续传）。
pub fn cancel_install(job_id: &str) -> String {
    let cell = guard(job_cancels()).get(job_id).cloned();
    match cell {
        Some(flag) => {
            flag.store(true, Ordering::SeqCst);
            json!({ "canceled": true }).to_string()
        }
        None => json!({ "canceled": false }).to_string(),
    }
}

pub fn install_status(job_id: &str) -> String {
    let job = guard(jobs()).get(job_id).cloned();
    match job {
        Some(j) => {
            let s = job_snapshot(&j);
            json!({ "state": s.state, "message": s.message, "percent": s.percent }).to_string()
        }
        None => json!({ "state": "unknown", "message": "没有这个任务", "percent": 0 }).to_string(),
    }
}

/* ══════════════════════════ 组件下载器 ══════════════════════════ */
//
// 三个必须做对的地方（都是 C# 实测踩出来的，原样搬过来）：
//
//   ① **断点续传**。54 MB 走一遍网络，中途断线几乎必然发生；从 0 重来对用户是灾难。
//      这里把已下载的部分留在 `<文件名>.part`，下次带 `Range: bytes=<已下载>-` 接着下，
//      服务端返回 206 就追加。服务端**不支持** Range（返回 200 全量）时必须退化成从头写，
//      否则会把整个文件追加到旧内容后面，得到一个长度翻倍、哈希对不上的怪文件。
//
//   ② **校验后才认账**。下载完先比 SHA-256，对不上就当失败、保留 .part 供续传，
//      绝不让半个包进到解压流程（否则报错会指到"解压后没有 python.exe"这种误导性地方）。
//
//   ③ **失败要能续**。网络错误/超时不算致命：保留 .part、把原因说清楚，
//      用户下次点"安装"就从断点接着走，而不是从零开始。

/// 一次下载尝试的结局
enum Attempt {
    Done,
    /// 服务端说这个范围不合法（多半是 .part 比真实文件还大）
    RangeRejected,
    Cancelled,
    Failed(String),
}

/// 下载组件包到 `cache_dir`，文件名 `file_name`。
/// 已存在同名完整文件时直接复用（不再联网）。
fn download(
    component: &str,
    file_name: &str,
    cache_dir: &Path,
    job: &JobArc,
    cancel: &AtomicBool,
) -> Result<PathBuf, InstallFail> {
    std::fs::create_dir_all(cache_dir).map_err(|e| InstallFail::Failed(format!("建缓存目录失败：{e}")))?;
    let final_path = cache_dir.join(file_name);
    let part_path = cache_dir.join(format!("{file_name}.part"));

    let existing = std::fs::metadata(&final_path).map(|m| m.len()).unwrap_or(0);
    if final_path.is_file() && existing > 0 {
        job_set(job, None, Some(&format!("缓存里已有 {file_name}，跳过下载")));
        return Ok(final_path);
    }

    let url = format!("{}/download/component/{}", base_url(), component);
    if cancel.load(Ordering::SeqCst) {
        return Err(InstallFail::Cancelled);
    }

    let mut last_error = String::new();
    // 最多 3 轮：每轮都从 .part 的当前长度接着下，所以"重试"就是"续传"
    for attempt in 1..=3u32 {
        if cancel.load(Ordering::SeqCst) {
            return Err(InstallFail::Cancelled);
        }
        let have = std::fs::metadata(&part_path).map(|m| m.len()).unwrap_or(0);
        match download_attempt(component, &url, &final_path, &part_path, have, job, cancel) {
            Attempt::Done => return Ok(final_path),
            Attempt::Cancelled => return Err(InstallFail::Cancelled),
            Attempt::RangeRejected => {
                let _ = std::fs::remove_file(&part_path);
                continue;
            }
            Attempt::Failed(msg) => {
                last_error = msg;
                let kept = std::fs::metadata(&part_path).map(|m| m.len()).unwrap_or(0);
                if attempt < 3 {
                    job_set(
                        job,
                        None,
                        Some(&format!("第 {attempt} 次下载中断（{last_error}），已保留 {kept} 字节，准备续传")),
                    );
                    std::thread::sleep(Duration::from_millis(800 * attempt as u64));
                } else {
                    job_set(job, None, Some(&format!("第 {attempt} 次下载失败（{last_error}），已保留 {kept} 字节")));
                }
            }
        }
    }

    Err(InstallFail::Failed(format!(
        "组件下载失败：{last_error}\n\
         下载地址：{url}\n\
         已保留断点文件：{}（下次点「安装」会接着下）\n\
         如果这台机器不能访问外网，也可以手工把 {file_name} 放到 {} 后再点安装。",
        part_path.display(),
        cache_dir.display()
    )))
}

fn download_attempt(
    component: &str,
    url: &str,
    final_path: &Path,
    part_path: &Path,
    have_in: u64,
    job: &JobArc,
    cancel: &AtomicBool,
) -> Attempt {
    if cancel.load(Ordering::SeqCst) {
        return Attempt::Cancelled;
    }
    let mut have = have_in;

    // 单个请求的整体超时给得很宽（见 DOWNLOAD_TIMEOUT_SEC）：54 MB 慢网要好几分钟
    let client = crate::http::client_with_timeout_ua(DOWNLOAD_TIMEOUT_SEC as i64, Some(DOWNLOAD_UA));
    let mut req = client
        .get(url)
        /* ⚠ **必须显式要 identity**：本仓库给 reqwest 开了 gzip/brotli，它在请求头里没有
         * `Accept-Encoding` 时会自动补一个 `gzip` 并透明解压（`ai.rs` 那条注释里有同样的
         * 追查：tower-http 的 `decompression/service.rs` 判的是 `Entry::Vacant`）。
         *
         * 这对"下载一个文件"是**错的**，有两个后果：
         *   ① **断点续传会拼出坏文件** —— `Range: bytes=<已下载>-` 的偏移指的是**压缩流**的
         *      偏移，而落盘的是解压后的字节，两者不是一套坐标；
         *   ② 进度条会失去总量 —— reqwest 解压时会把 `Content-Length` 抹掉
         *      （它不知道解压后多长），于是 `content_length()` 变 None、界面只能显示"未知大小"。
         * C# 那边其实从不发这个头（.NET 的 `HttpClientHandler.AutomaticDecompression` 默认是
         * `DecompressionMethods.None`），所以发 `identity` 才是**与 C# 一致**的行为，
         * 不是额外加限制。 */
        .header("Accept-Encoding", "identity");
    if have > 0 {
        req = req.header("Range", format!("bytes={have}-"));
    }
    let resp = match req.send() {
        Ok(r) => r,
        Err(e) => return Attempt::Failed(e.to_string()),
    };
    let status = resp.status().as_u16();

    if status == 416 {
        // 服务端说这个范围不合法：多半是 .part 比真实文件还大（换过包/写坏了）
        job_set(job, None, Some("服务端拒绝了续传范围（416），删掉半成品重新下载"));
        return Attempt::RangeRejected;
    }
    if !(200..300).contains(&status) {
        let reason = resp.status().canonical_reason().unwrap_or("");
        return Attempt::Failed(format!("下载失败：HTTP {status} {reason}"));
    }

    let resumed = status == 206 && have > 0;
    if !resumed && have > 0 {
        // 服务端忽略了 Range（返回 200 全量）：必须从头写，绝不能追加
        job_set(
            job,
            None,
            Some(&format!("服务端不支持断点续传（返回 200 全量），已丢弃已下载的 {have} 字节重新开始")),
        );
        have = 0;
    }

    let total: i64 = match resp.content_length() {
        // 206 的 Content-Length 是"这一段"的长度，要加上已经落盘的部分才是总长
        Some(len) if status == 206 => len as i64 + have as i64,
        Some(len) => len as i64,
        None => -1,
    };

    let file = std::fs::OpenOptions::new()
        .write(true)
        .create(true)
        .append(resumed)
        .truncate(!resumed)
        .open(part_path);
    let mut file = match file {
        Ok(f) => f,
        Err(e) => return Attempt::Failed(format!("写断点文件失败：{e}")),
    };

    let mut src = resp;
    let mut buf = vec![0u8; 1 << 17]; // 128 KB
    let mut done = have;
    let mut last_pct = -1i64;
    loop {
        if cancel.load(Ordering::SeqCst) {
            let _ = file.sync_all();
            return Attempt::Cancelled;
        }
        let n = match src.read(&mut buf) {
            Ok(0) => break,
            Ok(n) => n,
            Err(e) => {
                let _ = file.sync_all();
                return Attempt::Failed(e.to_string());
            }
        };
        if let Err(e) = file.write_all(&buf[..n]) {
            return Attempt::Failed(format!("写断点文件失败：{e}"));
        }
        done += n as u64;
        // 下载占 0~90%（余下的百分比留给校验与解压，与 C# 同一处换算：这里 0~90，
        // 到作业进度上再 ×9/10 → 0~81）
        let pct: i64 = if total > 0 { done as i64 * 90 / total } else { 0 };
        if pct != last_pct {
            last_pct = pct;
            let total_mb = if total > 0 { (total / 1_048_576).to_string() } else { "?".to_string() };
            let note = if resumed { "（续传）" } else { "" };
            job_set(
                job,
                Some((pct * 9 / 10) as i32),
                Some(&format!("下载 {component}：{}/{} MB{}", done / 1_048_576, total_mb, note)),
            );
        }
    }
    // Flush(true) 的等价物：续传的凭据必须真的落到盘上，否则断电后 .part 的长度不可信
    if let Err(e) = file.sync_all() {
        return Attempt::Failed(format!("写断点文件失败：{e}"));
    }
    if let Err(e) = file.flush() {
        return Attempt::Failed(format!("写断点文件失败：{e}"));
    }
    drop(file);

    if total > 0 && done as i64 != total {
        return Attempt::Failed(format!(
            "下载不完整：期望 {total} 字节，实际 {done} 字节（已保留断点，下次会接着下）"
        ));
    }

    // 落定：`std::fs::rename` 在 Windows 上走 MOVEFILE_REPLACE_EXISTING，等价于 C# 的
    // `File.Move(overwrite: true)`；顺带把 .part 清掉（用例断言下载完成后 .part 不存在）
    match std::fs::rename(part_path, final_path) {
        Ok(()) => Attempt::Done,
        Err(e) => Attempt::Failed(format!("落定组件包失败（{}）：{e}", final_path.display())),
    }
}

/// 校验组件包完整性。有同名 `.sha256` 旁文件时以旁文件为准，这样换自建包不必改代码。
fn expected_sha256(payload_path: &Path, built_in: &str) -> String {
    let mut side = payload_path.as_os_str().to_os_string();
    side.push(".sha256");
    let side = PathBuf::from(side);
    if side.is_file() {
        if let Ok(text) = std::fs::read_to_string(&side) {
            // 兼容 "hash" 与 "hash  filename" 两种写法
            let first = text
                .split(|c: char| c == ' ' || c == '\t' || c == '\r' || c == '\n')
                .find(|s| !s.is_empty())
                .unwrap_or("");
            if first.len() == 64 {
                return first.to_ascii_uppercase();
            }
        }
        // 旁文件坏了就退回内置摘要
    }
    built_in.to_string()
}

/// 校验失败就返回 Err（消息里带上期望值与实际值，便于用户判断是哪种坏）。
fn verify_payload(payload_path: &Path, built_in: &str, job: &JobArc) -> Result<(), InstallFail> {
    let want = expected_sha256(payload_path, built_in);
    let bytes = std::fs::metadata(payload_path).map(|m| m.len()).unwrap_or(0);
    job_set(job, Some(8), Some(&format!("校验组件包完整性（{} MB）…", bytes / 1024 / 1024)));
    let actual = match crate::pack::sha256_file(payload_path) {
        Ok(h) => h.to_ascii_uppercase(),
        Err(e) => return Err(InstallFail::Failed(format!("读取组件包失败：{e}"))),
    };
    if !crate::pack::sha256_eq(&actual, &want) {
        return Err(InstallFail::Failed(format!(
            "组件包校验失败，可能没有下载完整或已损坏。\n\
             文件：{}\n\
             期望 SHA-256：{want}\n\
             实际 SHA-256：{actual}\n\
             请删除该文件后重新下载。",
            payload_path.display()
        )));
    }
    Ok(())
}

/// 把「组件包还没下载」这件事准备好：先下载（带断点续传），再交给安装。
/// 下载完成前不会碰组件目录，所以中途失败不会留下半装状态。
fn ensure_payload(component: &str, file_name: &str, job: &JobArc, cancel: &AtomicBool) -> Result<PathBuf, InstallFail> {
    if let Some(p) = find_payload(file_name) {
        return Ok(p);
    }
    job_set(job, Some(0), Some("开始下载组件包…"));
    download(component, file_name, &cache_dir(), job, cancel)
}

/* ══════════════════════════ 安装实现 ══════════════════════════ */

fn replace_dir(staging: &Path, dest: &Path) -> Result<(), InstallFail> {
    if dest.exists() {
        std::fs::remove_dir_all(dest).map_err(|e| InstallFail::Failed(format!("删除旧组件目录失败：{e}")))?;
    }
    std::fs::rename(staging, dest).map_err(|e| InstallFail::Failed(format!("替换为已安装版本失败：{e}")))
}

fn install_python(job: &JobArc, cancel: &AtomicBool) -> Result<(), InstallFail> {
    job_set(job, Some(5), Some("查找组件包…"));
    let zip = ensure_payload("python", PYTHON_PAYLOAD_NAME, job, cancel)?;

    verify_payload(&zip, PYTHON_PAYLOAD_SHA256, job)?;

    job_set(job, Some(60), Some("解压 CPython…"));
    let staging = staging_of(&python_dir());
    if staging.exists() {
        let _ = std::fs::remove_dir_all(&staging);
    }
    std::fs::create_dir_all(&staging).map_err(|e| InstallFail::Failed(format!("建暂存目录失败：{e}")))?;

    // ⚠ 解包**只用** pack::unzip_to：它自带路径穿越防护（`..\..\Windows\System32\x.dll`
    // 或绝对路径条目一律整包拒绝），不要在这里另写一套解压。
    let bytes = std::fs::read(&zip).map_err(|e| InstallFail::Failed(format!("读取组件包失败：{e}")))?;
    crate::pack::unzip_to(&bytes, &staging)?;

    // 引擎门面：从应用目录拷进组件目录，保证 Python 侧能找到 mfmath.py
    let facade_src = app_dir().join("python").join("mfmath.py");
    if !facade_src.is_file() {
        return Err(InstallFail::Failed("应用目录缺少 python\\mfmath.py（控制台无法调用引擎）".into()));
    }
    std::fs::copy(&facade_src, staging.join("mfmath.py"))
        .map_err(|e| InstallFail::Failed(format!("拷贝 mfmath.py 失败：{e}")))?;

    if !staging.join("python.exe").is_file() {
        return Err(InstallFail::Failed("解压后没有 python.exe，组件包可能不完整".into()));
    }

    job_set(job, Some(80), Some("替换为已安装版本…"));
    replace_dir(&staging, &python_dir())?;

    let mb = dir_size(&python_dir()) / 1024 / 1024;
    {
        let mut j = guard(job);
        j.percent = 100;
        j.state = "done".into();
        j.message = format!("CPython {PYTHON_VERSION} 已安装（{mb} MB）");
    }
    Ok(())
}

/// 装 MinGW A 档工具链，并把它变成"能调用引擎"的完整环境：
///   ① 解压工具链
///   ② 拷入门面头文件 mfmath.hpp / mfmath_autorun.hpp
///   ③ 现场生成 mf_mathematics.dll 的导入库（.def + dlltool）
/// ③ 是关键：用户代码 `#include "mfmath.hpp"` 后正常链接即可，
/// 计算全部落在引擎 DLL 里，和 Python 侧走的是同一个 C ABI。
fn install_cpp(job: &JobArc, cancel: &AtomicBool) -> Result<(), InstallFail> {
    job_set(job, Some(3), Some("查找组件包…"));
    let zip = ensure_payload("mingw", CPP_PAYLOAD_NAME, job, cancel)?;

    verify_payload(&zip, CPP_PAYLOAD_SHA256, job)?;

    job_set(job, Some(20), Some("解压 MinGW 工具链…"));
    let staging = staging_of(&cpp_dir());
    if staging.exists() {
        let _ = std::fs::remove_dir_all(&staging);
    }
    std::fs::create_dir_all(&staging).map_err(|e| InstallFail::Failed(format!("建暂存目录失败：{e}")))?;

    let bytes = std::fs::read(&zip).map_err(|e| InstallFail::Failed(format!("读取组件包失败：{e}")))?;
    crate::pack::unzip_to(&bytes, &staging)?;
    flatten_single_root(&staging);

    if !staging.join("bin").join("g++.exe").is_file() {
        return Err(InstallFail::Failed("解压后没有 bin\\g++.exe，组件包可能不完整或布局不对".into()));
    }

    job_set(job, Some(40), Some("拷入门面头文件…"));
    let inc_dir = staging.join("include");
    std::fs::create_dir_all(&inc_dir).map_err(|e| InstallFail::Failed(format!("建 include 目录失败：{e}")))?;
    for header in ["mfmath.hpp", "mfmath_autorun.hpp"] {
        let src = app_dir().join("cpp").join(header);
        if !src.is_file() {
            return Err(InstallFail::Failed(format!("应用目录缺少 cpp\\{header}（控制台无法调用引擎）")));
        }
        std::fs::copy(&src, inc_dir.join(header))
            .map_err(|e| InstallFail::Failed(format!("拷贝 {header} 失败：{e}")))?;
    }

    job_set(job, Some(65), Some("生成引擎导入库…"));
    let lib_dir = staging.join("lib");
    std::fs::create_dir_all(&lib_dir).map_err(|e| InstallFail::Failed(format!("建 lib 目录失败：{e}")))?;
    let def_path = lib_dir.join("mf_mathematics.def");
    // ASCII 写出（与 C# 的 `new ASCIIEncoding()` 一致：.def 是给 dlltool 的纯 ASCII 文本）
    std::fs::write(&def_path, CPP_DEF_TEXT.as_bytes())
        .map_err(|e| InstallFail::Failed(format!("写 .def 失败：{e}")))?;
    let import_lib = lib_dir.join("libmf_mathematics.a");
    if import_lib.exists() {
        let _ = std::fs::remove_file(&import_lib);
    }

    let dlltool = staging.join("bin").join("dlltool.exe");
    if !dlltool.is_file() {
        return Err(InstallFail::Failed("组件包里没有 bin\\dlltool.exe，无法生成导入库".into()));
    }
    let args = vec![
        "-d".to_string(),
        def_path.to_string_lossy().to_string(),
        "-l".to_string(),
        import_lib.to_string_lossy().to_string(),
        "-k".to_string(),
    ];
    let tool_out = run_tool(&dlltool, &args, &lib_dir, COMPILE_TIMEOUT_SEC);
    if !import_lib.is_file() {
        return Err(InstallFail::Failed(format!(
            "dlltool 没能生成 libmf_mathematics.a：{}",
            tool_out
        )));
    }

    job_set(job, Some(90), Some("替换为已安装版本…"));
    replace_dir(&staging, &cpp_dir())?;

    let mb = dir_size(&cpp_dir()) / 1024 / 1024;
    {
        let mut j = guard(job);
        j.percent = 100;
        j.state = "done".into();
        j.message = format!("MinGW {CPP_VERSION} 已安装（{mb} MB），C++ 已出现在语言列表里");
    }
    Ok(())
}

/// 组件包若整体套了一层目录（mingw64/…），提到根上，省得处处要拼前缀。
fn flatten_single_root(dir: &Path) {
    if dir.join("bin").join("g++.exe").is_file() {
        return;
    }
    let Ok(rd) = std::fs::read_dir(dir) else { return };
    let mut subs: Vec<PathBuf> = Vec::new();
    let mut files = 0usize;
    for e in rd.flatten() {
        let p = e.path();
        if p.is_dir() {
            subs.push(p);
        } else {
            files += 1;
        }
    }
    if subs.len() != 1 || files != 0 {
        return;
    }
    let inner = subs.remove(0);
    if !inner.join("bin").join("g++.exe").is_file() {
        return;
    }
    if let Ok(rd) = std::fs::read_dir(&inner) {
        for e in rd.flatten() {
            let from = e.path();
            let Some(name) = from.file_name() else { continue };
            let _ = std::fs::rename(&from, dir.join(name));
        }
    }
    let _ = std::fs::remove_dir_all(&inner);
}

/* ══════════════════════════ 子进程 ══════════════════════════ */

/// 输出缓冲（一个子进程一份，读线程往里追加）
#[derive(Default, Clone)]
struct Capture {
    out: String,
    err: String,
    /// 只有 stdout 会被标记截断（与 C# `Poll` 里 `truncated = run.Out.Length > Max` 一致）
    truncated: bool,
}

/// 到上限就丢（`Poll` 里会提示截断）；上限判定与 C# `Append` 同一条件。
fn append_line(cap: &mut Capture, line: &str, is_out: bool) {
    let over = {
        let slot = if is_out { &mut cap.out } else { &mut cap.err };
        if slot.len() > MAX_OUTPUT_BYTES {
            return;
        }
        slot.push_str(line);
        slot.push('\n');
        slot.len() > MAX_OUTPUT_BYTES
    };
    if over && is_out {
        cap.truncated = true;
    }
}

/// 常驻读线程：按行读，行尾的 `\n` / `\r\n` 去掉（与 .NET 的 `OutputDataReceived` 同形）。
///
/// 用 `read_until` + 有损 UTF-8 解码，而不是 `BufRead::lines()`：后者遇到非法 UTF-8
/// 会直接返回 `Err` 并终止读取，用户程序里一个坏字节就会吞掉后面所有输出。
/// C# 的 `StandardOutputEncoding = UTF8` 是**有损**解码，行为与这里一致。
fn spawn_reader<R, F>(mut r: R, is_out: bool, mut sink: F) -> std::thread::JoinHandle<()>
where
    R: BufRead + Send + 'static,
    F: FnMut(&str, bool) + Send + 'static,
{
    std::thread::spawn(move || {
        let mut buf: Vec<u8> = Vec::with_capacity(4096);
        loop {
            buf.clear();
            match r.read_until(b'\n', &mut buf) {
                Ok(0) => break,
                Ok(_) => {}
                Err(_) => break,
            }
            while matches!(buf.last(), Some(b'\n') | Some(b'\r')) {
                buf.pop();
            }
            let line = String::from_utf8_lossy(&buf).into_owned();
            sink(&line, is_out);
        }
    })
}

/// 杀掉整个进程树。
///
/// C# 用的是 `Process.Kill(entireProcessTree: true)`；std 的 `Child::kill()` 只杀直接子进程，
/// 所以这里调 `taskkill /T /F`（Windows 自带），调用方再补一次 `child.kill()` 兜底。
///
/// ⚠ 返回 `false` 表示**进程树没被结束**（极简镜像没有 taskkill、权限不足、或 pid 已经没了）——
/// 那时调用方只能杀掉直接子进程，**孙进程可能残留**。这是真实的能力边界，别把它当成"杀干净了"：
/// 所以这里失败要写进 app.log（诊断包里能看到），而不是无声无息。
/// （没有改 `Stop`/`StopAll` 的返回形状：那是前端契约，为一个罕见降级去动它不划算。）
fn kill_tree(pid: u32) -> bool {
    let pid_s = pid.to_string();
    let ok = Command::new("taskkill")
        .args(["/PID", &pid_s, "/T", "/F"])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .creation_flags(CREATE_NO_WINDOW)
        .status()
        .map(|s| s.success())
        .unwrap_or(false);
    if !ok {
        crate::logging::warn(&format!(
            "结束进程树失败（taskkill 不可用或权限不足）：pid={pid}。已退回只结束直接子进程，孙进程可能残留。"
        ));
    }
    ok
}

/// 同步跑一个工具并回收它的输出（安装阶段用，量很小）。
/// 返回值与 C# `RunTool` 一致：`(stdout + stderr).Trim()`。
fn run_tool(exe: &Path, args: &[String], work_dir: &Path, timeout_sec: u64) -> String {
    let mut cmd = Command::new(exe);
    cmd.args(args)
        .current_dir(work_dir)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .creation_flags(CREATE_NO_WINDOW);
    let mut child = match cmd.spawn() {
        Ok(c) => c,
        Err(e) => return format!("无法启动 {}：{e}", exe.display()),
    };
    let sink: Arc<Mutex<Capture>> = Arc::new(Mutex::new(Capture::default()));
    let t_out = child.stdout.take().map(|s| {
        let sink = sink.clone();
        spawn_reader(std::io::BufReader::new(s), true, move |line, is_out| {
            if let Ok(mut c) = sink.lock() {
                append_line(&mut c, line, is_out);
            }
        })
    });
    let t_err = child.stderr.take().map(|s| {
        let sink = sink.clone();
        spawn_reader(std::io::BufReader::new(s), false, move |line, is_out| {
            if let Ok(mut c) = sink.lock() {
                append_line(&mut c, line, is_out);
            }
        })
    });

    let deadline = Instant::now() + Duration::from_secs(timeout_sec);
    loop {
        match child.try_wait() {
            Ok(Some(_)) => break,
            Ok(None) => {
                if Instant::now() >= deadline {
                    // C# 的 `WaitForExit(ms)` 超时后**不杀进程**（RunTool 没杀）；这里也不杀，
                    // 只把已经收到的输出带回去 —— 调用方靠"导入库在不在"判断成败。
                    break;
                }
                std::thread::sleep(Duration::from_millis(15));
            }
            Err(_) => break,
        }
    }
    if let Some(t) = t_out {
        let _ = t.join();
    }
    if let Some(t) = t_err {
        let _ = t.join();
    }
    let cap = guard(&sink).clone();
    format!("{}{}", cap.out, cap.err).trim().to_string()
}

/* ══════════════════════════ 运行 ══════════════════════════ */
//
// 「跑用户代码」这一段的边界，逐项与 C# 对齐（**都是有意保留的原行为**，不是漏做）：
//   · **超时**：Python / C++ 程序 60 s，C++ 编译 120 s。到点杀**整棵进程树**。
//   · **并发上限：没有**。C# 每个 `Start` 直接起一个线程 + 一个进程，不排队、不拒绝。
//     这里照搬。真实的并发压力来自用户连点「运行」，界面自己的 `running` 标志挡住了大部分；
//     宿主侧没有闸门这件事与 C# 一致 —— 若要收紧，应两边一起定，否则两个宿主行为分叉。
//   · **stdin**：只在非空时才接管道，写完立刻关闭（= 给子进程 EOF），避免子进程卡在 input()。
//   · **输出上限**：stdout / stderr 各 256 KB，超了丢行并在 `Poll` 里回报 `truncated`。
//   · **进程退出与清理**：等两个读线程把管道读完再收工；`Stop`/`StopAll` 用 pid 调
//     `taskkill /T /F`；宿主退出的最后一道保险是前端调的 `StopAll`。
//   · **取消语义**：`Stop` 是真的杀进程（不像 jobs.rs 那样"只能停止等待"——因为这边有
//     进程边界可用）；而**安装**作业的取消只做到"下载循环里检查标记"，解压阶段打不断，
//     所以界面文案是"已取消安装"而不是"已停止"，与本项目一贯纪律一致。
//   · **临时目录**：每次运行一个 `%LOCALAPPDATA%\MFMath\console\run<n>\`；进程内只清一次
//     （上一次会话留下的），所以本次会话里报错给出的 `run<n>\main.py` 路径一直有效。

struct RunState {
    language: String,
    /// queued | compiling | running | done（C++ 比 Python 多一个「编译」阶段）
    stage: String,
    /// queued | running | done
    ///
    /// queued → running → done：`Poll` 必须能区分"还没起来"和"已结束"，
    /// 否则客户端第一次轮询就以为跑完了（C# 实测踩过）。
    state: String,
    exit_code: Option<i32>,
    timed_out: bool,
    compile_ms: Option<i64>,
    started: Instant,
    /// 当前子进程 pid（None = 没有在跑的子进程）。
    /// `Stop`/`StopAll` 只认它，等价于 C# 的 `run.Proc != null`。
    pid: Option<u32>,
    dir: PathBuf,
    cap: Capture,
}

type RunArc = Arc<Mutex<RunState>>;

static RUNS: OnceLock<Mutex<HashMap<String, RunArc>>> = OnceLock::new();

fn runs() -> &'static Mutex<HashMap<String, RunArc>> {
    RUNS.get_or_init(|| Mutex::new(HashMap::new()))
}

fn run_of(id: &str) -> Option<RunArc> {
    guard(runs()).get(id).cloned()
}

/// 把一次控制台运行的状态推给界面（topic = `console.run`）
fn push_run(id: &str, run: &RunArc, evt: &str) {
    let payload = {
        let r = guard(run);
        json!({
            "runId": id,
            "language": r.language,
            "event": evt,
            "stage": r.stage,
            "state": r.state,
            "exitCode": r.exit_code,
            "elapsedMs": r.started.elapsed().as_millis() as i64,
            "timedOut": r.timed_out,
        })
        .to_string()
    };
    crate::push::send("console.run", &payload);
}

static SCRATCH_CLEANED: OnceLock<()> = OnceLock::new();

/// 清掉上一次会话留下的控制台临时工程目录。
///
/// 为什么放在宿主里做，而不是交给卸载程序：临时目录在 `%LOCALAPPDATA%` 下，
/// 是**用户级**路径；管理员模式安装的卸载程序可能运行在另一个管理员账号下，
/// 去删 `{localappdata}` 会删错人（Inno 编译时的 `UsedUserAreasWarning` 就是这件事）。
/// 宿主自己清最准：它一定运行在真正使用它的那个用户下。
///
/// 只清一次（每个进程），所以本次会话里报错信息中给出的 `run<n>\main.py` 路径
/// 在会话期间一直有效。
fn clean_scratch_once() {
    SCRATCH_CLEANED.get_or_init(|| {
        let root = scratch_root();
        if root.exists() {
            // 有别的实例在用就跳过，不因为清理失败影响运行
            let _ = std::fs::remove_dir_all(&root);
        }
    });
}

/// 开始运行一段代码，返回 runId。`language`：`"python"` | `"cpp"`
pub fn start(language: &str, code: &str, stdin: &str) -> String {
    let id = format!("run{}", SEQ.fetch_add(1, Ordering::Relaxed));
    let run: RunArc = Arc::new(Mutex::new(RunState {
        // C# 是 `language ?? "python"`（空串保持空串，最终按"非 cpp 即 python"分支），
        // 这里同样原样保留，分支判断在 run_thread 里做
        language: language.to_string(),
        stage: "queued".into(),
        state: "queued".into(),
        exit_code: None,
        timed_out: false,
        compile_ms: None,
        started: Instant::now(),
        pid: None,
        dir: PathBuf::new(),
        cap: Capture::default(),
    }));
    guard(runs()).insert(id.clone(), run.clone());

    let (code, stdin, id2) = (code.to_string(), stdin.to_string(), id.clone());
    let _ = std::thread::Builder::new()
        .name(format!("console-{id}"))
        .spawn(move || run_thread(id2, run, code, stdin));
    id
}

fn run_thread(id: String, run: RunArc, code: String, stdin: String) {
    clean_scratch_once();
    let outcome = (|| -> Result<(), String> {
        let scratch = scratch_root();
        std::fs::create_dir_all(&scratch).map_err(|e| e.to_string())?;
        let work = scratch.join(&id);
        if work.exists() {
            std::fs::remove_dir_all(&work).map_err(|e| e.to_string())?;
        }
        std::fs::create_dir_all(&work).map_err(|e| e.to_string())?;
        guard(&run).dir = work.clone();

        let language = guard(&run).language.clone();
        if language == "cpp" {
            run_cpp(&id, &run, &code, &stdin, &work)
        } else {
            run_python(&id, &run, &code, &stdin, &work)
        }
    })();

    if let Err(msg) = outcome {
        let mut st = guard(&run);
        append_line(&mut st.cap, &format!("[宿主错误] {msg}"), false);
        st.exit_code = Some(-2);
    }
    {
        let mut st = guard(&run);
        st.state = "done".into();
        st.stage = "done".into();
    }
    // 结束即推：界面不用再靠自己轮询才知道跑完了
    push_run(&id, &run, "done");
}

fn set_stage(id: &str, run: &RunArc, stage: &str) {
    {
        let mut st = guard(run);
        st.stage = stage.to_string();
    }
    push_run(id, run, "stage");
}

fn run_python(id: &str, run: &RunArc, code: &str, stdin: &str, work: &Path) -> Result<(), String> {
    let py = python_dir().join("python.exe");
    if !py.is_file() {
        let mut st = guard(run);
        st.cap.err.push_str("CPython 组件未安装：请先在控制台里点「安装 Python 组件」。\n");
        st.exit_code = Some(-1);
        return Ok(());
    }
    let file = work.join("main.py");
    // UTF-8 **无 BOM**（C# 是 `new UTF8Encoding(false)`）
    std::fs::write(&file, code.as_bytes()).map_err(|e| e.to_string())?;

    // 引导脚本：解决"嵌入版 Python 处于 isolated 模式"这个坑。
    //
    // 嵌入式 CPython 带一个 python313._pth，等于强制在隔离模式下运行：
    //   · 环境变量 PYTHONPATH 被**完全忽略**（所以下面设了也白设）
    //   · 脚本所在目录不会进 sys.path[0]
    // 后果是用户不能 import 自己刚写的模块、也 import 不到 mfmath（除非它在
    // 组件目录里靠搜索路径撞上）。用一个显式引导文件把这些路径补回来，
    // 比去改组件里的 _pth 更稳（组件是官方发行的，改它会在升级时被覆盖）。
    let runner = work.join("_run.py");
    let bootstrap = [
        "import os, sys",
        "_d = os.path.dirname(os.path.abspath(__file__))",
        "for _p in (os.environ.get('MF_ENGINE_DIR') or '', sys.prefix, _d):",
        "    if _p and _p not in sys.path:",
        "        sys.path.insert(0, _p)",
        "# 以 __main__ 方式执行用户代码：traceback 里的文件名保持 main.py，行号可直接对上",
        "_f = os.path.join(_d, 'main.py')",
        "with open(_f, encoding='utf-8') as _h:",
        "    _src = _h.read()",
        "exec(compile(_src, 'main.py', 'exec'), {'__name__': '__main__', '__file__': _f})",
    ]
    .join("\n");
    std::fs::write(&runner, bootstrap.as_bytes()).map_err(|e| e.to_string())?;

    // 让 Python 侧 ① 输出一律 UTF-8（中文不乱码）② 能找到引擎 DLL
    let env = vec![
        ("PYTHONIOENCODING".to_string(), "utf-8".to_string()),
        ("PYTHONUTF8".to_string(), "1".to_string()),
        ("MF_ENGINE_DIR".to_string(), app_dir().to_string_lossy().to_string()),
        (
            "PYTHONPATH".to_string(),
            format!("{};{}", python_dir().display(), app_dir().display()),
        ),
    ];
    set_stage(id, run, "running");
    let args = vec!["-X".to_string(), "utf8".to_string(), runner.to_string_lossy().to_string()];
    let code = exec_child(run, &py, &args, work, stdin, &env, DEFAULT_TIMEOUT_SEC)?;
    guard(run).exit_code = Some(code);
    Ok(())
}

/// C++：先编译再运行。编译用的工具链、门面头文件、引擎导入库都来自 C++ 组件。
/// 编译器输出原样进 stderr（用户要靠它定位自己代码的问题），
/// 编译失败就**不运行**，退出码沿用编译器的。
fn run_cpp(id: &str, run: &RunArc, code: &str, stdin: &str, work: &Path) -> Result<(), String> {
    let gpp = cpp_dir().join("bin").join("g++.exe");
    if !gpp.is_file() {
        let mut st = guard(run);
        st.cap.err.push_str("C++ 组件（MinGW A 档）未安装：请先在控制台里点「安装 C++ 组件」。\n");
        st.exit_code = Some(-1);
        return Ok(());
    }
    let inc_dir = cpp_dir().join("include");
    let lib_dir = cpp_dir().join("lib");
    for need in [
        inc_dir.join("mfmath.hpp"),
        inc_dir.join("mfmath_autorun.hpp"),
        lib_dir.join("libmf_mathematics.a"),
    ] {
        if !need.is_file() {
            let mut st = guard(run);
            st.cap
                .err
                .push_str(&format!("C++ 组件不完整，缺少 {}：请重新安装 C++ 组件。\n", need.display()));
            st.exit_code = Some(-1);
            return Ok(());
        }
    }

    std::fs::write(work.join("main.cpp"), code.as_bytes()).map_err(|e| e.to_string())?;

    let args = vec![
        "-std=c++17".to_string(),
        "-O2".to_string(),
        "-static-libgcc".to_string(),
        "-static-libstdc++".to_string(),
        format!("-I{}", inc_dir.display()),
        // 强制注入：让 stdout 边写边落管道，未捕获异常打断时前面的输出不会丢
        "-include".to_string(),
        inc_dir.join("mfmath_autorun.hpp").to_string_lossy().to_string(),
        "main.cpp".to_string(),
        format!("-L{}", lib_dir.display()),
        "-lmf_mathematics".to_string(),
        "-o".to_string(),
        "main.exe".to_string(),
    ];

    // C++ 多一个「编译」阶段：界面靠这条 push 立刻把"编译中…"显示出来
    set_stage(id, run, "compiling");
    let t0 = Instant::now();
    let cc = exec_child(run, &gpp, &args, work, "", &[], COMPILE_TIMEOUT_SEC)?;
    let compile_ms = t0.elapsed().as_millis() as i64;
    {
        let mut st = guard(run);
        st.compile_ms = Some(compile_ms);
    }
    if cc != 0 {
        let timed_out = guard(run).timed_out;
        let head = if timed_out {
            format!("编译超时（超过 {COMPILE_TIMEOUT_SEC} 秒已被终止）。\n")
        } else {
            format!("编译失败（编译器退出码 {cc}）：\n")
        };
        let mut st = guard(run);
        st.cap.err.insert_str(0, &head);
        st.exit_code = Some(cc);
        return Ok(());
    }

    let exe = work.join("main.exe");
    if !exe.is_file() {
        let mut st = guard(run);
        st.cap.err.push_str("编译器报告成功，但没有产出 main.exe。\n");
        st.exit_code = Some(-3);
        return Ok(());
    }

    set_stage(id, run, "running");
    // 引擎 DLL 和它的依赖都在应用目录，放进 PATH 让 main.exe 找得到
    let old_path = std::env::var("PATH").unwrap_or_default();
    let env = vec![("PATH".to_string(), format!("{};{old_path}", app_dir().display()))];
    let code2 = exec_child(run, &exe, &[], work, stdin, &env, DEFAULT_TIMEOUT_SEC)?;
    {
        let mut st = guard(run);
        st.exit_code = Some(code2);
    }

    if code2 < 0 && !guard(run).timed_out {
        let msg = format!(
            "[宿主] 程序异常终止（退出码 {code2}，0x{:08X}）。\
             未捕获的 C++ 异常会让标准库直接 std::terminate 终止进程、不打任何说明，\
             把可能抛异常的调用（mfm::call / mfm::num / mfm::text）包进 try/catch 才能看见原因。",
            code2 as u32
        );
        let mut st = guard(run);
        append_line(&mut st.cap, &msg, false);
    }
    Ok(())
}

/// 跑一个子进程并回收输出。编译和运行共用一份逻辑：
/// 都接管道、都限时、都能被 `Stop` 杀。
#[allow(clippy::too_many_arguments)]
fn exec_child(
    run: &RunArc,
    exe: &Path,
    args: &[String],
    work: &Path,
    stdin: &str,
    env: &[(String, String)],
    timeout_sec: u64,
) -> Result<i32, String> {
    let mut cmd = Command::new(exe);
    cmd.args(args)
        .current_dir(work)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        // C# 只在有 stdin 时才重定向；没有 stdin 时它继承宿主句柄（GUI 宿主下那是个无效
        // 句柄）。这里明确给 NUL：既不会让子进程阻塞在 input()，也不会拿到无效句柄。
        .stdin(if stdin.is_empty() { Stdio::null() } else { Stdio::piped() })
        .creation_flags(CREATE_NO_WINDOW);
    for (k, v) in env {
        cmd.env(k, v);
    }

    let mut child = cmd.spawn().map_err(|e| format!("无法启动 {}：{e}", exe.display()))?;
    let pid = child.id();
    {
        let mut st = guard(run);
        st.pid = Some(pid);
        st.state = "running".into();
    }

    // 先把两个读线程挂上，再写 stdin：大块 stdin 也不会和输出互锁
    let t_out = child.stdout.take().map(|s| {
        let cap = run.clone();
        spawn_reader(std::io::BufReader::new(s), true, move |line, is_out| {
            if let Ok(mut st) = cap.lock() {
                append_line(&mut st.cap, line, is_out);
            }
        })
    });
    let t_err = child.stderr.take().map(|s| {
        let cap = run.clone();
        spawn_reader(std::io::BufReader::new(s), false, move |line, is_out| {
            if let Ok(mut st) = cap.lock() {
                append_line(&mut st.cap, line, is_out);
            }
        })
    });

    if !stdin.is_empty() {
        if let Some(mut si) = child.stdin.take() {
            // 进程可能已退出：写失败不是错误
            let _ = si.write_all(stdin.as_bytes());
            let _ = si.flush();
            drop(si); // 关掉 stdin = 给子进程 EOF（C# 是 StandardInput.Close()）
        }
    }

    let deadline = Instant::now() + Duration::from_secs(timeout_sec);
    let mut status_code: Option<i32> = None;
    let mut timed_out = false;
    loop {
        match child.try_wait() {
            Ok(Some(st)) => {
                status_code = st.code();
                break;
            }
            Ok(None) => {
                if Instant::now() >= deadline {
                    timed_out = true;
                    kill_tree(pid);
                    // taskkill 也可能失败（权限/极简镜像），至少杀掉直接子进程
                    let _ = child.kill();
                    let _ = child.wait();
                    break;
                }
                // C# 的 WaitForExit(ms) 是在进程句柄上阻塞等待；std 没有这个 API，
                // 所以每 15 ms 轮询一次。对 60/120 秒的预算而言这点开销可以忽略。
                std::thread::sleep(Duration::from_millis(15));
            }
            Err(_) => break,
        }
    }

    // 等读线程把管道余量读完再收工。
    // ⚠ 这里比 C# **更完整**：`Process.WaitForExit(int)` 不等异步输出回调结束
    //（.NET 的已知行为，只有无参 `WaitForExit()` 才等），所以 C# 偶发会漏掉最后几行。
    // 进程已退出 → 管道必然 EOF → join 一定返回，不会挂。
    if let Some(t) = t_out {
        let _ = t.join();
    }
    if let Some(t) = t_err {
        let _ = t.join();
    }

    {
        let mut st = guard(run);
        st.pid = None;
        if timed_out {
            st.timed_out = true;
        }
    }
    // 超时后 C# 取 `HasExited ? ExitCode : -1`；杀完通常都已退出，取不到就给 -1
    Ok(status_code.unwrap_or(-1))
}

/// 增量取回输出与状态（JSON）。
pub fn poll(run_id: &str) -> String {
    let Some(run) = run_of(run_id) else {
        return json!({ "state": "unknown", "running": false, "message": "没有这个运行" }).to_string();
    };
    let r = guard(&run);
    let done = r.state == "done";
    json!({
        "state": r.state,
        "stage": r.stage,
        "running": !done,
        // 与 C# 一致：跑完才给 exitCode，没跑完给 null
        "exitCode": if done { json!(r.exit_code) } else { Value::Null },
        "timedOut": r.timed_out,
        "elapsedMs": r.started.elapsed().as_millis() as i64,
        "compileMs": r.compile_ms,
        "stdout": r.cap.out,
        "stderr": r.cap.err,
        "truncated": r.cap.truncated,
    })
    .to_string()
}

/// 终止运行（连同子进程树）。
pub fn stop(run_id: &str) -> String {
    let Some(run) = run_of(run_id) else {
        return json!({ "stopped": false }).to_string();
    };
    let pid = guard(&run).pid;
    match pid {
        Some(pid) => {
            kill_tree(pid);
            json!({ "stopped": true }).to_string()
        }
        None => json!({ "stopped": false }).to_string(),
    }
}

/// 应用退出前清场：把还活着的子进程杀掉，别留孤儿进程。
pub fn stop_all() -> String {
    let all: Vec<RunArc> = guard(runs()).values().cloned().collect();
    let mut n = 0;
    for r in all {
        if let Some(pid) = guard(&r).pid {
            kill_tree(pid);
            n += 1;
        }
    }
    json!({ "killed": n }).to_string()
}

/* ══════════════════════════ 与 C# 的有意差异（逐条） ══════════════════════════
 *
 * ① **Rust 侧不引入 tokio/async**：C# 用 `Thread` + `CancellationTokenSource`，
 *    这里用 `std::thread` + `Arc<AtomicBool>`。取消语义一字不差：起跑前与下载循环里
 *    检查标记；**解压阶段不响应取消**（C# 也没响应）。所以取消可能表现为"作业最终还是
 *    success"，或者被取消时停在下载中途。界面文案仍是"已取消安装（已下载的部分保留着，
 *    下次接着下）"—— 与本项目一贯的"停止等待，不假装杀干净"纪律一致（见 jobs.rs 模块注释）。
 *
 * ② **超时等待是轮询**（15 ms 一次 `try_wait`）。C# 是 `WaitForExit(ms)` 阻塞在进程句柄上。
 *    语义相同（都限时、超时都杀进程树），只是 std 没有带超时的 wait。
 *
 * ③ **下载的整体超时是 30 分钟**，而不是 C# 的 `Timeout.InfiniteTimeSpan`。
 *    C# 靠 `ConnectTimeout=20s` + 无限读超时；reqwest 的 blocking 客户端在这一层
 *    没有"只限连接"的旋钮，照抄"无限"会让一个半死的连接把作业永远停在 running
 *    （取消能救，但界面会一直显示在装）。30 分钟对 54 MB 的慢网足够宽。
 *
 * ④ **子进程没有 stdin 时给 NUL**，而不是继承宿主句柄（C# 的行为）。GUI 宿主下
 *    继承到的是无效句柄；给 NUL 是确定的 EOF，也不会让子进程卡在 input()。
 *
 * ⑤ **退出前等读线程收尾**。C# 的 `WaitForExit(int)` 不等异步输出回调，
 *    偶发会漏掉最后几行；这里 join 读线程，输出只会多不会少。
 *
 * ⑥ **`__MF_COMPONENT_BASE` 与 `MF_COMPONENT_BASE` 都认**（前者优先）。
 *    `__MF_COMPONENT_BASE` 是本 Rust 宿主 `sys.rs` 已经在用的名字，`MF_COMPONENT_BASE`
 *    是 C# 的名字。两个都认 = 换宿主不用改环境变量，是超集不是分歧。
 *
 * ⑦ **下载源没有加"必须 https / 不能本机"的闸门**（与 C# 一样只 trim）。理由见
 *    `set_download_base` 的文档注释：它只决定"从哪里拉包"，包要过 SHA-256 才进解压流程；
 *    且本机用例正是用 127.0.0.1 的镜像验续传，加白名单会把那条用例打死。
 *
 * ⑧ **没有把下载源持久化到设置文件**（与 C# 一致：`_baseUrl` 是进程内静态量）。
 *    `SetDownloadBase` 是会话级的"临时换镜像"，重启回到默认/环境变量。
 *
 * ⑨ **进程树用 `taskkill /T /F`** 而不是 Win32 Job Object。C# 的
 *    `Kill(entireProcessTree: true)` 也是走进程遍历，语义一致；用 taskkill 不需要
 *    给 `windows` crate 加 `Win32_System_JobObjects` 特性（那会牵动一次全量重编译）。
 *    失败时调用方还有 `Child::kill()` 兜底（杀直接子进程）。
 *
 * ⑩ **`Install` / `Start` 返回裸 id 字符串**（不是 JSON）—— 这一点**不是**差异，
 *    是照抄 C#：前端 `String(c.Install(name))` 与用例都按裸字符串用。
 *
 * ⑪ 组件目录用的是 `logging::data_dir()`（`%LOCALAPPDATA%` 环境变量），而 C# 用的是
 *    Known Folder API。两者在本机同值；Rust 宿主全程（`sys.rs`/`logging.rs`）都用前者，
 *    端到端用例也是按 `process.env.LOCALAPPDATA` 拼路径去查盘的，所以这一致性反而是需要的。
 */
