//! engine.rs —— 对 `mf_mathematics.dll` 的 FFI 封装
//!
//! 引擎只有**两个** C ABI 导出（见 `MF_Mathematics/api.cpp`），所以这层很薄：
//!
//! ```c
//! bool function_exists(const char* name);
//! int  math_call(const char* name, const char* args_json, char* out, int out_size);
//! // math_call 返回写入的字节数（不含 '\0'）；缓冲不足或参数非法返回 -1
//! ```
//!
//! 与 C# 宿主 `NativeEngine.cs` 的契约逐字一致，包括**分级缓冲**：
//! 常规调用 4 MB 够用，而复网格那种整块数据（600×600 的 re/im 约 12 MB JSON）
//! 会被顶掉，于是逐级扩容重试 —— 而不是给所有调用一律开 64 MB 白占内存。

use std::ffi::{c_char, c_int, CString};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

use windows::core::{PCSTR, PCWSTR};
use windows::Win32::Foundation::HMODULE;
use windows::Win32::System::LibraryLoader::{GetProcAddress, LoadLibraryW};

/// 与 C# 侧相同的三级缓冲
const BUF_SIZES: [usize; 3] = [4 * 1024 * 1024, 16 * 1024 * 1024, 64 * 1024 * 1024];

type FnExists = unsafe extern "C" fn(*const c_char) -> bool;
type FnCall = unsafe extern "C" fn(*const c_char, *const c_char, *mut c_char, c_int) -> c_int;

static ENGINE: OnceLock<Result<Engine, String>> = OnceLock::new();

pub struct Engine {
    // 句柄故意不 Free：宿主进程活着，引擎就该活着（与 C# 的 DllImport 语义一致）
    _module: HMODULE,
    exists: FnExists,
    call: FnCall,
}

// SAFETY: 句柄与两个函数指针在进程生命周期内都不变，且不做任何可变共享 ——
// 所有调用都发生在同一个线程（WebView2 宿主对象的 Invoke 在 UI 线程上）。
unsafe impl Send for Engine {}
unsafe impl Sync for Engine {}

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

impl Engine {
    /// 从宿主 exe 同目录加载引擎（与 C# 的 AppContext.BaseDirectory 同义）
    pub fn load(dir: &Path) -> Result<Self, String> {
        let dll: PathBuf = dir.join("mf_mathematics.dll");
        if !dll.is_file() {
            return Err(format!(
                "找不到数学引擎：{}（应与宿主 exe 同目录；CS 版的同一句话见 NativeEngine.LoadFailure）",
                dll.display()
            ));
        }
        let path_w = wide(&dll.to_string_lossy());
        let module = unsafe { LoadLibraryW(PCWSTR(path_w.as_ptr())) }
            .map_err(|e| format!("无法加载 {}：{}", dll.display(), e))?;

        // SAFETY: 两个符号名来自 api.cpp 的 extern "C" 声明，签名见文件头
        let exists: FnExists = unsafe {
            let p = GetProcAddress(module, PCSTR(b"function_exists\0".as_ptr()));
            match p {
                Some(f) => std::mem::transmute(f),
                None => return Err("mf_mathematics.dll 里找不到 function_exists（导出被裁剪？）".into()),
            }
        };
        let call: FnCall = unsafe {
            let p = GetProcAddress(module, PCSTR(b"math_call\0".as_ptr()));
            match p {
                Some(f) => std::mem::transmute(f),
                None => return Err("mf_mathematics.dll 里找不到 math_call（导出被裁剪？）".into()),
            }
        };
        Ok(Self { _module: module, exists, call })
    }

    /// 进程级单例：第一次调用时按 `dir` 加载
    pub fn shared(dir: &Path) -> Result<&'static Engine, String> {
        let slot = ENGINE.get_or_init(|| Engine::load(dir));
        match slot {
            Ok(e) => Ok(e),
            Err(msg) => Err(msg.clone()),
        }
    }

    pub fn exists(&self, name: &str) -> bool {
        let Ok(c) = CString::new(name) else { return false };
        // SAFETY: 引擎只读该 C 串
        unsafe { (self.exists)(c.as_ptr()) }
    }

    /// 调用一个已注册 action；返回引擎的 JSON 信封 `{isError,value}`
    pub fn call_json(&self, name: &str, args_json: &str) -> Result<String, String> {
        let name_c = CString::new(name).map_err(|_| "函数名含 NUL".to_string())?;
        let args_c = CString::new(args_json).map_err(|_| "参数 JSON 含 NUL".to_string())?;

        for size in BUF_SIZES {
            let mut buf: Vec<u8> = vec![0; size];
            // SAFETY: 缓冲区按 size 分配；引擎保证写入不超过 size（不足则返回 -1）
            let n = unsafe {
                (self.call)(
                    name_c.as_ptr(),
                    args_c.as_ptr(),
                    buf.as_mut_ptr() as *mut c_char,
                    size as c_int,
                )
            };
            if n < 0 {
                continue; // 缓冲不够（或参数非法）→ 换更大的
            }
            let n = n as usize;
            let bytes = &buf[..n.min(size)];
            // 引擎写的是 UTF-8（C# 侧同样按 UTF-8 读）
            return Ok(String::from_utf8_lossy(bytes).into_owned());
        }
        Err(format!(
            "math_call({name}) 在 {} MB 缓冲下仍失败",
            BUF_SIZES[BUF_SIZES.len() - 1] / (1024 * 1024)
        ))
    }
}
