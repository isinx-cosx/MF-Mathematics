//! 安装器的图形界面。
//!
//! 双击运行时，Windows 会为控制台子系统的 exe 分配一个黑框。安装器不该长那样，
//! 所以在这种情形下先 `FreeConsole` 丢掉黑框，再建自己的窗口。
//!
//! 从终端运行时保留文字输出（脚本与排障都靠它），不建窗口。
//! 判断依据是 `GetConsoleProcessList` 的返回数：只有自己一个进程，说明黑框是
//! 双击时新建的；多于一个说明终端在共享它。
//!
//! 界面只用纯 Win32 控件（STATIC / BUTTON / msctls_progress32），不引入 GUI 框架：
//! 安装器只需要一个进度条加几行字。
//!
//! 控件类名与文字都先转成宽字符串再取指针 —— 本项目的 `windows` 版本里
//! `w!` 宏不可用。

use std::sync::atomic::{AtomicBool, AtomicIsize, Ordering};
use std::sync::Mutex;

use anyhow::Result;
use windows::core::PCWSTR;
use windows::Win32::Foundation::{HINSTANCE, HWND, LPARAM, LRESULT, WPARAM};
use windows::Win32::Graphics::Gdi::{
    GetStockObject, InvalidateRect, SetBkMode, UpdateWindow, COLOR_WINDOW, DEFAULT_GUI_FONT,
    HBRUSH, TRANSPARENT, WHITE_BRUSH,
};
use windows::Win32::System::Console::{FreeConsole, GetConsoleProcessList, GetConsoleWindow};
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::Controls::{InitCommonControlsEx, INITCOMMONCONTROLSEX, ICC_PROGRESS_CLASS};
use windows::Win32::UI::Input::KeyboardAndMouse::{EnableWindow, SetFocus};
use windows::Win32::UI::WindowsAndMessaging::*;

use crate::util;

/// 自定义消息：子线程通过它把状态发回界面线程。
const WM_APP_STEP: u32 = WM_APP + 1;
const WM_APP_DONE: u32 = WM_APP + 2;

/// 进度条的控件消息（comctl32）。
const PBM_SETPOS: u32 = 0x0402;
const PBM_SETSTATE: u32 = 0x0410;
/// `PBST_NORMAL` / `PBST_ERROR`
const PBST_NORMAL: usize = 0x0001;
const PBST_ERROR: usize = 0x0002;
/// 推进进度的计时器。
const TIMER_PROGRESS: usize = 1;
/// 进度条在完成前的上限。装到 90% 等着，剩下的留给"收尾"，
/// 免得进度条先跑到 100 然后卡住不动。
const PROGRESS_CAP: isize = 90;
/// `SS_LEFT` —— 注意它的值是 **0**，不是 1（1 是 `SS_CENTER`）。
const SS_LEFT: u32 = 0x0000_0000;
/// `BS_DEFPUSHBUTTON`
const BS_DEFPUSHBUTTON: u32 = 0x0000_0001;

const ID_CLOSE: usize = 1001;

/// 控件句柄。窗口只有一个，用静态量传递最省事。
static STEP_LABEL: AtomicIsize = AtomicIsize::new(0);
static PROGRESS: AtomicIsize = AtomicIsize::new(0);
static CLOSE_BUTTON: AtomicIsize = AtomicIsize::new(0);
static WORKING: AtomicBool = AtomicBool::new(true);
/// 进度条当前位置（0–100）。由界面线程的计时器推进。
static PROGRESS_POS: AtomicIsize = AtomicIsize::new(0);
static JOB: Mutex<Option<Box<dyn FnOnce() -> Result<()> + Send>>> = Mutex::new(None);

fn hwnd_of(v: &AtomicIsize) -> HWND {
    HWND(v.load(Ordering::SeqCst) as *mut std::ffi::c_void)
}

fn set_text(hwnd: HWND, text: &str) {
    let wide = util::wide(text);
    unsafe {
        let _ = SetWindowTextW(hwnd, PCWSTR(wide.as_ptr()));
    }
}

/// 当前进程是否独占了控制台（即黑框是双击时新建的）。
pub fn console_is_ours_alone() -> bool {
    unsafe {
        if GetConsoleWindow().0.is_null() {
            // 根本没有控制台窗口：当作需要自建界面。
            return true;
        }
        let mut pids = [0u32; 4];
        let n = GetConsoleProcessList(&mut pids);
        n <= 1
    }
}

/// 收起控制台黑框。
pub fn detach_console() {
    unsafe {
        let _ = FreeConsole();
    }
}

/// 把一行状态文字发到界面线程。
fn post_step(text: String) {
    let hwnd = hwnd_of(&STEP_LABEL);
    if hwnd.0.is_null() {
        return;
    }
    let raw = Box::into_raw(Box::new(text));
    unsafe {
        let _ = PostMessageW(Some(hwnd), WM_APP_STEP, WPARAM(0), LPARAM(raw as isize));
    }
}

/// 让 `util::say` 的输出改道到窗口。
fn install_sink() {
    util::set_sink(|line| post_step(line.to_string()));
}

unsafe extern "system" fn wndproc(hwnd: HWND, msg: u32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    match msg {
        WM_CREATE => {
            create_controls(hwnd);
            start_worker(hwnd);
            LRESULT(0)
        }
        WM_TIMER => {
            // 推进进度条。不追求精确百分比（释放 115 个文件很快，真正耗时的是
            // 解压与哈希），只要让用户看到"在动"且不会提前跑满。
            if wp.0 == TIMER_PROGRESS && WORKING.load(Ordering::SeqCst) {
                let cur = PROGRESS_POS.load(Ordering::SeqCst);
                if cur < PROGRESS_CAP {
                    let next = (cur + 2).min(PROGRESS_CAP);
                    PROGRESS_POS.store(next, Ordering::SeqCst);
                    let pb = hwnd_of(&PROGRESS);
                    unsafe {
                        SendMessageW(pb, PBM_SETPOS, Some(WPARAM(next as usize)), Some(LPARAM(0)));
                    }
                }
            }
            LRESULT(0)
        }
        WM_APP_STEP => {
            // 收回子线程送来的字符串。
            let text = Box::from_raw(lp.0 as *mut String);
            set_text(hwnd_of(&STEP_LABEL), &text);
            LRESULT(0)
        }
        WM_APP_DONE => {
            let text = Box::from_raw(lp.0 as *mut String);
            let ok = wp.0 == 0;
            WORKING.store(false, Ordering::SeqCst);

            let pb = hwnd_of(&PROGRESS);
            let btn = hwnd_of(&CLOSE_BUTTON);
            let label = hwnd_of(&STEP_LABEL);
            unsafe {
                // 停掉计时器并定格在终态。
                let _ = KillTimer(Some(hwnd), TIMER_PROGRESS);
                SendMessageW(pb, PBM_SETPOS, Some(WPARAM(100)), Some(LPARAM(0)));
                SendMessageW(
                    pb,
                    PBM_SETSTATE,
                    Some(WPARAM(if ok { PBST_NORMAL } else { PBST_ERROR })),
                    Some(LPARAM(0)),
                );
                let _ = InvalidateRect(Some(pb), None, true);
                let _ = UpdateWindow(pb);
                set_text(label, &text);
                let _ = EnableWindow(btn, true);
                set_text(btn, if ok { "关闭" } else { "关闭（失败）" });
                let _ = SetFocus(Some(btn));
            }
            LRESULT(0)
        }
        WM_CTLCOLORSTATIC => {
            // STATIC 默认用灰色对话框背景，会在白底窗口上留一条灰带。
            // 让文字透明、背景用窗口的白色。
            let hdc = windows::Win32::Graphics::Gdi::HDC(wp.0 as *mut std::ffi::c_void);
            unsafe {
                SetBkMode(hdc, TRANSPARENT);
                LRESULT(GetStockObject(WHITE_BRUSH).0 as isize)
            }
        }
        WM_COMMAND => {
            if (wp.0 & 0xffff) == ID_CLOSE {
                let _ = unsafe { DestroyWindow(hwnd) };
            }
            LRESULT(0)
        }
        WM_CLOSE => {
            // 干活期间不允许关窗，否则会留下半装状态。
            if !WORKING.load(Ordering::SeqCst) {
                let _ = unsafe { DestroyWindow(hwnd) };
            }
            LRESULT(0)
        }
        WM_DESTROY => {
            unsafe { PostQuitMessage(0) };
            LRESULT(0)
        }
        _ => unsafe { DefWindowProcW(hwnd, msg, wp, lp) },
    }
}

/// 建窗口里的各个控件。
fn create_controls(hwnd: HWND) {
    let instance = unsafe { GetModuleHandleW(None) }.unwrap_or_default();
    let hinstance = HINSTANCE(instance.0);
    let font = unsafe { GetStockObject(DEFAULT_GUI_FONT) };

    // 控件类名与初始文字先做成局部宽字符串，保证在整个调用期间存活。
    let cls_static = util::wide("STATIC");
    let cls_button = util::wide("BUTTON");
    let cls_progress = util::wide("msctls_progress32");
    let txt_ready = util::wide("准备中…");
    let txt_working = util::wide("安装中…");
    let txt_empty = util::wide("");

    let label = unsafe {
        CreateWindowExW(
            WINDOW_EX_STYLE(0),
            PCWSTR(cls_static.as_ptr()),
            PCWSTR(txt_ready.as_ptr()),
            WS_CHILD | WS_VISIBLE | WINDOW_STYLE(SS_LEFT),
            20,
            20,
            420,
            44,
            Some(hwnd),
            None,
            Some(hinstance),
            None,
        )
    }
    .unwrap_or_default();

    let pb = unsafe {
        CreateWindowExW(
            WINDOW_EX_STYLE(0),
            PCWSTR(cls_progress.as_ptr()),
            PCWSTR(txt_empty.as_ptr()),
            WS_CHILD | WS_VISIBLE,
            20,
            74,
            420,
            20,
            Some(hwnd),
            None,
            Some(hinstance),
            None,
        )
    }
    .unwrap_or_default();

    let btn = unsafe {
        CreateWindowExW(
            WINDOW_EX_STYLE(0),
            PCWSTR(cls_button.as_ptr()),
            PCWSTR(txt_working.as_ptr()),
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | WINDOW_STYLE(BS_DEFPUSHBUTTON),
            340,
            110,
            100,
            30,
            Some(hwnd),
            None,
            Some(hinstance),
            None,
        )
    }
    .unwrap_or_default();

    // 按钮的控件 ID：用 SetWindowLongPtrW 设，比 CreateWindowExW 的菜单参数可靠。
    unsafe {
        SetWindowLongPtrW(btn, GWLP_ID, ID_CLOSE as isize);
        for h in [label, pb, btn] {
            SendMessageW(h, WM_SETFONT, Some(WPARAM(font.0 as usize)), Some(LPARAM(1)));
        }
        // 用计时器推进进度条（见 WM_TIMER）。不用跑马灯：停掉之后控件不重画，
        // 会停在动画中途的花纹上。
        SetTimer(Some(hwnd), TIMER_PROGRESS, 120, None);
        let _ = EnableWindow(btn, false);
    }

    STEP_LABEL.store(label.0 as isize, Ordering::SeqCst);
    PROGRESS.store(pb.0 as isize, Ordering::SeqCst);
    CLOSE_BUTTON.store(btn.0 as isize, Ordering::SeqCst);
}

/// 把实际工作放到子线程，界面线程只负责刷新。
fn start_worker(hwnd: HWND) {
    let job = JOB.lock().ok().and_then(|mut g| g.take());
    let hwnd_addr = hwnd.0 as isize;
    std::thread::spawn(move || {
        let hwnd = HWND(hwnd_addr as *mut std::ffi::c_void);
        let outcome = match job {
            Some(f) => f(),
            None => Err(anyhow::anyhow!("内部错误：没有待执行的任务")),
        };
        let (code, text) = match outcome {
            Ok(()) => (0usize, "完成。".to_string()),
            Err(e) => (1usize, format!("{e:#}")),
        };
        let raw = Box::into_raw(Box::new(text));
        unsafe {
            let _ = PostMessageW(Some(hwnd), WM_APP_DONE, WPARAM(code), LPARAM(raw as isize));
        }
    });
}

/// 建窗并跑消息循环。`job` 在子线程执行。
pub fn run(window_title: &str, job: impl FnOnce() -> Result<()> + Send + 'static) -> Result<()> {
    // 先让输出改道到窗口，再建窗，避免工作开始时日志还往黑框里写。
    install_sink();
    *JOB
        .lock()
        .map_err(|_| anyhow::anyhow!("任务槽被占用"))? = Some(Box::new(job));

    unsafe {
        let instance = GetModuleHandleW(None)?;
        let hinstance = HINSTANCE(instance.0);

        let mut icc = INITCOMMONCONTROLSEX {
            dwSize: std::mem::size_of::<INITCOMMONCONTROLSEX>() as u32,
            dwICC: ICC_PROGRESS_CLASS,
        };
        let _ = InitCommonControlsEx(&mut icc);

        let class_name = util::wide("MFMathInstallerWindow");
        let wc = WNDCLASSW {
            style: WNDCLASS_STYLES(0),
            lpfnWndProc: Some(wndproc),
            cbClsExtra: 0,
            cbWndExtra: 0,
            hInstance: hinstance,
            // 图标用 exe 里嵌的那一份（资源 ID 1，见 build.rs）。
            hIcon: LoadIconW(Some(hinstance), PCWSTR(1 as *const u16)).unwrap_or_default(),
            hCursor: LoadCursorW(None, IDC_ARROW).unwrap_or_default(),
            // 系统窗口背景色：+1 是 Win32 用 COLOR_* 当画刷的约定。
            hbrBackground: HBRUSH((COLOR_WINDOW.0 + 1) as *mut std::ffi::c_void),
            lpszMenuName: PCWSTR::null(),
            lpszClassName: PCWSTR(class_name.as_ptr()),
        };
        if RegisterClassW(&wc) == 0 {
            anyhow::bail!("注册窗口类失败");
        }

        let title = util::wide(window_title);
        // 固定大小：可关闭、可最小化，不给缩放。
        let style = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX;
        let hwnd = CreateWindowExW(
            WS_EX_DLGMODALFRAME,
            PCWSTR(class_name.as_ptr()),
            PCWSTR(title.as_ptr()),
            style,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            480,
            190,
            None,
            None,
            Some(hinstance),
            None,
        )?;

        let _ = ShowWindow(hwnd, SW_SHOW);
        let _ = UpdateWindow(hwnd);

        let mut msg = MSG::default();
        while GetMessageW(&mut msg, None, 0, 0).as_bool() {
            let _ = TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    }
    Ok(())
}
