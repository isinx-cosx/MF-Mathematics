//! 安装器的图形界面：选项页 → 进度页 → 完成页。
//!
//! 双击运行时 Windows 会给控制台子系统的 exe 分配一个黑框。安装器不该长那样，
//! 所以在这种情形下先 `FreeConsole` 丢掉黑框，再建自己的窗口。
//!
//! 从终端运行时保留文字输出（脚本与排障靠它），不建窗口。
//! 判断依据是 `GetConsoleProcessList` 的返回数：只有自己一个进程，说明黑框是
//! 双击时新建的；多于一个说明终端在共享它。
//!
//! 界面只用纯 Win32 控件，不引入 GUI 框架。
//!
//! 几个与 rc/Windows 版本相关的注意点写在各自位置：`w!` 宏在本项目的
//! `windows` 版本里不可用，控件类名统一用 `util::wide` 取指针。

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, AtomicIsize, Ordering};
use std::sync::Mutex;

use anyhow::Result;
use windows::core::PCWSTR;
use windows::Win32::Foundation::{HINSTANCE, HWND, LPARAM, LRESULT, WPARAM};
use windows::Win32::Graphics::Gdi::{
    CreateFontW, DeleteObject, GetStockObject, InvalidateRect, SetBkMode, SetTextColor,
    UpdateWindow, COLOR_WINDOW, DEFAULT_GUI_FONT, FONT_CHARSET, FONT_CLIP_PRECISION, FONT_QUALITY,
    FONT_OUTPUT_PRECISION, HBRUSH, HGDIOBJ, TRANSPARENT, WHITE_BRUSH,
};
use windows::Win32::System::Com::{
    CoCreateInstance, CoInitializeEx, CoTaskMemFree, CLSCTX_INPROC_SERVER,
    COINIT_APARTMENTTHREADED,
};
use windows::Win32::System::Console::{FreeConsole, GetConsoleProcessList, GetConsoleWindow};
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::Controls::{
    InitCommonControlsEx, IsDlgButtonChecked, INITCOMMONCONTROLSEX, ICC_PROGRESS_CLASS,
};
use windows::Win32::UI::Input::KeyboardAndMouse::{EnableWindow, SetFocus};
use windows::Win32::UI::Shell::{
    FileOpenDialog, IFileOpenDialog, FOS_FORCEFILESYSTEM, FOS_PICKFOLDERS, SIGDN_FILESYSPATH,
};
use windows::Win32::UI::WindowsAndMessaging::*;

use crate::util;

// ── 控件 ID ────────────────────────────────────────────────────────────────
const ID_ICON: usize = 1000;
const ID_TITLE: usize = 1001;
const ID_SUBTITLE: usize = 1002;
const ID_LABEL_PATH: usize = 1003;
const ID_PATH_EDIT: usize = 1004;
const ID_BROWSE: usize = 1005;
const ID_CHK_DESKTOP: usize = 1006;
const ID_CHK_RUN: usize = 1007;
const ID_CHK_PURGE: usize = 1008;
const ID_STEP: usize = 1009;
const ID_BTN_PRIMARY: usize = 1010;
const ID_BTN_CANCEL: usize = 1011;

// ── 消息与常量 ─────────────────────────────────────────────────────────────
const WM_APP_STEP: u32 = WM_APP + 1;
const WM_APP_DONE: u32 = WM_APP + 2;

const PBM_SETPOS: u32 = 0x0402;
const PBM_SETSTATE: u32 = 0x0410;
const PBST_NORMAL: usize = 0x0001;
const PBST_ERROR: usize = 0x0002;

const TIMER_PROGRESS: usize = 1;
const PROGRESS_CAP: isize = 90;

/// `SS_LEFT` 的值是 **0**（1 是 `SS_CENTER`）。
const SS_LEFT: u32 = 0x0000_0000;
const SS_ICON: u32 = 0x0000_0003;
const BS_DEFPUSHBUTTON: u32 = 0x0000_0001;
const BS_AUTOCHECKBOX: u32 = 0x0000_0003;
const ES_AUTOHSCROLL: u32 = 0x0000_0080;

/// 子线程要干的活。
pub enum Job {
    Install { default_dir: PathBuf, force: bool },
    Uninstall { dir: PathBuf },
}

/// 界面状态。只在界面线程读写。
struct State {
    job: Job,
    desktop: bool,
    run_after: bool,
    purge: bool,
}

static STATE: Mutex<Option<State>> = Mutex::new(None);
static WORKING: AtomicBool = AtomicBool::new(false);
static PROGRESS_POS: AtomicIsize = AtomicIsize::new(0);

/// 当前在哪一页。主按钮的含义随页变化，必须明确记录：
/// 选项页是「安装/卸载」，完成页是「关闭」。
/// （曾经用 `WORKING` 兼职表示页面，结果完成页点「关闭」又触发了一次安装。）
const PAGE_OPTIONS: isize = 0;
const PAGE_WORKING: isize = 1;
const PAGE_DONE: isize = 2;
static PAGE: AtomicIsize = AtomicIsize::new(PAGE_OPTIONS);

static ICON_CTL: AtomicIsize = AtomicIsize::new(0);
static TITLE_CTL: AtomicIsize = AtomicIsize::new(0);
static SUBTITLE_CTL: AtomicIsize = AtomicIsize::new(0);
static LABEL_PATH_CTL: AtomicIsize = AtomicIsize::new(0);
static EDIT_CTL: AtomicIsize = AtomicIsize::new(0);
static BROWSE_CTL: AtomicIsize = AtomicIsize::new(0);
static CHK_DESKTOP_CTL: AtomicIsize = AtomicIsize::new(0);
static CHK_RUN_CTL: AtomicIsize = AtomicIsize::new(0);
static CHK_PURGE_CTL: AtomicIsize = AtomicIsize::new(0);
static STEP_CTL: AtomicIsize = AtomicIsize::new(0);
static PROGRESS_CTL: AtomicIsize = AtomicIsize::new(0);
static PRIMARY_CTL: AtomicIsize = AtomicIsize::new(0);
static CANCEL_CTL: AtomicIsize = AtomicIsize::new(0);

static BOLD_FONT: AtomicIsize = AtomicIsize::new(0);
static SUBTITLE_COLOR: AtomicIsize = AtomicIsize::new(0);

fn h(ctl: &AtomicIsize) -> HWND {
    HWND(ctl.load(Ordering::SeqCst) as *mut std::ffi::c_void)
}

fn set_text(hwnd: HWND, text: &str) {
    let wide = util::wide(text);
    unsafe {
        let _ = SetWindowTextW(hwnd, PCWSTR(wide.as_ptr()));
    }
}

fn get_text(hwnd: HWND) -> String {
    unsafe {
        let len = GetWindowTextLengthW(hwnd);
        if len <= 0 {
            return String::new();
        }
        let mut buf = vec![0u16; len as usize + 1];
        let n = GetWindowTextW(hwnd, &mut buf);
        String::from_utf16_lossy(&buf[..n as usize])
    }
}

fn show(ctl: &AtomicIsize, visible: bool) {
    unsafe {
        let _ = ShowWindow(h(ctl), if visible { SW_SHOW } else { SW_HIDE });
    }
}

/// 切页：选项页与进度/完成页互斥。
fn show_options_page(show_it: bool) {
    for c in [
        &LABEL_PATH_CTL,
        &EDIT_CTL,
        &BROWSE_CTL,
        &CHK_DESKTOP_CTL,
        &CHK_RUN_CTL,
        &CHK_PURGE_CTL,
    ] {
        show(c, show_it);
    }
    show(&STEP_CTL, !show_it);
    show(&PROGRESS_CTL, !show_it);
}

/// 当前进程是否独占了控制台（即黑框是双击时新建的）。
pub fn console_is_ours_alone() -> bool {
    unsafe {
        if GetConsoleWindow().0.is_null() {
            return true;
        }
        let mut pids = [0u32; 4];
        GetConsoleProcessList(&mut pids) <= 1
    }
}

/// 收起控制台黑框。
pub fn detach_console() {
    unsafe {
        let _ = FreeConsole();
    }
}

/// 让 `util::say` 的输出改道到窗口的步骤行。
fn install_sink() {
    util::set_sink(|line| {
        let step = h(&STEP_CTL);
        if step.0.is_null() {
            return;
        }
        let raw = Box::into_raw(Box::new(line.to_string()));
        unsafe {
            let _ = PostMessageW(Some(step), WM_APP_STEP, WPARAM(0), LPARAM(raw as isize));
        }
    });
}

/// 弹系统文件夹选择框。
fn pick_folder(owner: HWND) -> Option<String> {
    unsafe {
        let _ = CoInitializeEx(None, COINIT_APARTMENTTHREADED);
        let dialog: IFileOpenDialog =
            CoCreateInstance(&FileOpenDialog, None, CLSCTX_INPROC_SERVER).ok()?;
        if let Ok(opts) = dialog.GetOptions() {
            let _ = dialog.SetOptions(opts | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM);
        }
        let title = util::wide("选择安装位置");
        let _ = dialog.SetTitle(PCWSTR(title.as_ptr()));
        if dialog.Show(Some(owner)).is_err() {
            return None;
        }
        let item = dialog.GetResult().ok()?;
        let pw = item.GetDisplayName(SIGDN_FILESYSPATH).ok()?;
        let s = pw.to_string().ok();
        CoTaskMemFree(Some(pw.0 as *const std::ffi::c_void));
        s
    }
}

unsafe extern "system" fn wndproc(hwnd: HWND, msg: u32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    match msg {
        WM_CREATE => {
            create_controls(hwnd);
            LRESULT(0)
        }
        WM_TIMER => {
            // 推进进度条。释放 115 个文件很快，真正耗时的是解压与逐文件哈希，
            // 所以不追求精确百分比，只要"在动"且不会提前跑满。
            if wp.0 == TIMER_PROGRESS && WORKING.load(Ordering::SeqCst) {
                let cur = PROGRESS_POS.load(Ordering::SeqCst);
                if cur < PROGRESS_CAP {
                    let next = (cur + 2).min(PROGRESS_CAP);
                    PROGRESS_POS.store(next, Ordering::SeqCst);
                    let pb = h(&PROGRESS_CTL);
                    SendMessageW(pb, PBM_SETPOS, Some(WPARAM(next as usize)), Some(LPARAM(0)));
                }
            }
            LRESULT(0)
        }
        WM_APP_STEP => {
            let text = Box::from_raw(lp.0 as *mut String);
            set_text(h(&STEP_CTL), &text);
            LRESULT(0)
        }
        WM_APP_DONE => {
            let text = Box::from_raw(lp.0 as *mut String);
            let ok = wp.0 == 0;
            WORKING.store(false, Ordering::SeqCst);
            PAGE.store(PAGE_DONE, Ordering::SeqCst);
            unsafe {
                let _ = KillTimer(Some(hwnd), TIMER_PROGRESS);
                let pb = h(&PROGRESS_CTL);
                SendMessageW(pb, PBM_SETPOS, Some(WPARAM(100)), Some(LPARAM(0)));
                SendMessageW(
                    pb,
                    PBM_SETSTATE,
                    Some(WPARAM(if ok { PBST_NORMAL } else { PBST_ERROR })),
                    Some(LPARAM(0)),
                );
                let _ = InvalidateRect(Some(pb), None, true);
                let _ = UpdateWindow(pb);

                set_text(h(&STEP_CTL), &text);
                // 完成页：主按钮变成"关闭"，取消按钮收起来。
                set_text(h(&PRIMARY_CTL), "关闭");
                let _ = EnableWindow(h(&PRIMARY_CTL), true);
                show(&CANCEL_CTL, false);
                let _ = SetFocus(Some(h(&PRIMARY_CTL)));
            }
            LRESULT(0)
        }
        WM_CTLCOLORSTATIC => {
            // STATIC 默认用灰色对话框背景，会在白底窗口上留灰带；
            // 副标题另外用灰色文字区分层级。
            let hdc = windows::Win32::Graphics::Gdi::HDC(wp.0 as *mut std::ffi::c_void);
            let ctl = HWND(lp.0 as *mut std::ffi::c_void);
            unsafe {
                SetBkMode(hdc, TRANSPARENT);
                let gray = SUBTITLE_COLOR.load(Ordering::SeqCst) as u32;
                if ctl == h(&SUBTITLE_CTL) {
                    SetTextColor(hdc, windows::Win32::Foundation::COLORREF(gray));
                }
                LRESULT(GetStockObject(WHITE_BRUSH).0 as isize)
            }
        }
        WM_COMMAND => {
            let id = wp.0 & 0xffff;
            match id {
                ID_BROWSE => {
                    if let Some(p) = pick_folder(hwnd) {
                        set_text(h(&EDIT_CTL), &p);
                    }
                }
                ID_BTN_PRIMARY => {
                    match PAGE.load(Ordering::SeqCst) {
                        // 完成页：关窗。
                        PAGE_DONE => {
                            let _ = DestroyWindow(hwnd);
                        }
                        // 选项页：开始干活。
                        PAGE_OPTIONS => begin_work(hwnd),
                        // 干活期间按钮是灰的，正常点不到。
                        _ => {}
                    }
                }
                ID_BTN_CANCEL => {
                    let _ = DestroyWindow(hwnd);
                }
                _ => {}
            }
            LRESULT(0)
        }
        WM_CLOSE => {
            // 干活期间不允许关窗，否则会留下半装状态。
            if !WORKING.load(Ordering::SeqCst) {
                let _ = DestroyWindow(hwnd);
            }
            LRESULT(0)
        }
        WM_DESTROY => {
            let bold = BOLD_FONT.load(Ordering::SeqCst);
            if bold != 0 {
                let _ = DeleteObject(HGDIOBJ(bold as *mut std::ffi::c_void));
            }
            PostQuitMessage(0);
            LRESULT(0)
        }
        _ => DefWindowProcW(hwnd, msg, wp, lp),
    }
}

/// 读界面上的选项，切到进度页，把活交给子线程。
fn begin_work(hwnd: HWND) {
    let (dir_text, desktop, run_after, purge, is_uninstall) = {
        let st = match STATE.lock() {
            Ok(g) => g,
            Err(_) => return,
        };
        let Some(s) = st.as_ref() else { return };
        let dir = match &s.job {
            Job::Install { .. } => get_text(h(&EDIT_CTL)),
            Job::Uninstall { dir } => dir.to_string_lossy().to_string(),
        };
        let desktop = unsafe { IsDlgButtonChecked(hwnd, ID_CHK_DESKTOP as i32) } == 1;
        let run_after = unsafe { IsDlgButtonChecked(hwnd, ID_CHK_RUN as i32) } == 1;
        let purge = unsafe { IsDlgButtonChecked(hwnd, ID_CHK_PURGE as i32) } == 1;
        let is_uninstall = matches!(s.job, Job::Uninstall { .. });
        (dir, desktop, run_after, purge, is_uninstall)
    };

    if dir_text.trim().is_empty() {
        let msg = util::wide("请先选择安装位置。");
        let cap = util::wide(util::PRODUCT_NAME);
        unsafe {
            MessageBoxW(
                Some(hwnd),
                PCWSTR(msg.as_ptr()),
                PCWSTR(cap.as_ptr()),
                MB_OK | MB_ICONWARNING,
            );
        }
        return;
    }

    // 记录选择，供子线程读取。
    if let Ok(mut g) = STATE.lock() {
        if let Some(s) = g.as_mut() {
            s.desktop = desktop;
            s.run_after = run_after;
            s.purge = purge;
            if let Job::Install { default_dir, .. } = &mut s.job {
                *default_dir = PathBuf::from(&dir_text);
            }
        }
    }

    WORKING.store(true, Ordering::SeqCst);
    PAGE.store(PAGE_WORKING, Ordering::SeqCst);
    PROGRESS_POS.store(0, Ordering::SeqCst);
    show_options_page(false);
    set_text(h(&STEP_CTL), if is_uninstall { "正在卸载…" } else { "正在安装…" });
    set_text(h(&PRIMARY_CTL), if is_uninstall { "卸载中…" } else { "安装中…" });
    unsafe {
        let _ = EnableWindow(h(&PRIMARY_CTL), false);
        let _ = EnableWindow(h(&CANCEL_CTL), false);
        SetTimer(Some(hwnd), TIMER_PROGRESS, 120, None);
    }

    // 取出待执行的活，交给子线程。
    let job = {
        let mut g = match STATE.lock() {
            Ok(g) => g,
            Err(_) => return,
        };
        let s = match g.as_mut() {
            Some(s) => s,
            None => return,
        };
        let desktop = s.desktop;
        let run_after = s.run_after;
        let purge = s.purge;
        match &s.job {
            Job::Install { default_dir, force } => {
                let opts = crate::install::Options {
                    dir: default_dir.clone(),
                    force: *force,
                    desktop_shortcut: desktop,
                    run_after,
                };
                Box::new(move || crate::install::run(&opts)) as Box<dyn FnOnce() -> Result<()> + Send>
            }
            Job::Uninstall { dir } => {
                let opts = crate::uninstall::Options {
                    dir: Some(dir.clone()),
                    purge,
                };
                Box::new(move || crate::uninstall::run(&opts))
            }
        }
    };

    let addr = hwnd.0 as isize;
    std::thread::spawn(move || {
        let hwnd = HWND(addr as *mut std::ffi::c_void);
        let (code, text) = match job() {
            Ok(()) => (0usize, "完成。".to_string()),
            Err(e) => (1usize, format!("{e:#}")),
        };
        let raw = Box::into_raw(Box::new(text));
        unsafe {
            let _ = PostMessageW(Some(hwnd), WM_APP_DONE, WPARAM(code), LPARAM(raw as isize));
        }
    });
}

/// 建所有控件。三页共用同一批句柄，靠显示/隐藏切换。
fn create_controls(hwnd: HWND) {
    let instance = unsafe { GetModuleHandleW(None) }.unwrap_or_default();
    let inst = HINSTANCE(instance.0);
    let normal = unsafe { GetStockObject(DEFAULT_GUI_FONT) };

    // 标题用加粗稍大的字体；中文用雅黑。
    let face = util::wide("Microsoft YaHei UI");
    let bold = unsafe {
        CreateFontW(
            -22,
            0,
            0,
            0,
            700,
            0,
            0,
            0,
            FONT_CHARSET(1), // DEFAULT_CHARSET
            FONT_OUTPUT_PRECISION(0),
            FONT_CLIP_PRECISION(0),
            FONT_QUALITY(0),
            0,
            PCWSTR(face.as_ptr()),
        )
    };
    BOLD_FONT.store(bold.0 as isize, Ordering::SeqCst);

    let cls_static = util::wide("STATIC");
    let cls_edit = util::wide("EDIT");
    let cls_button = util::wide("BUTTON");
    let cls_progress = util::wide("msctls_progress32");

    let mk = |class: &[u16],
              text: &str,
              style: u32,
              x: i32,
              y: i32,
              w: i32,
              hgt: i32,
              id: usize|
     -> HWND {
        let t = util::wide(text);
        let ctl = unsafe {
            CreateWindowExW(
                WINDOW_EX_STYLE(0),
                PCWSTR(class.as_ptr()),
                PCWSTR(t.as_ptr()),
                WS_CHILD | WS_VISIBLE | WINDOW_STYLE(style),
                x,
                y,
                w,
                hgt,
                Some(hwnd),
                None,
                Some(inst),
                None,
            )
        }
        .unwrap_or_default();
        if id != 0 {
            unsafe { SetWindowLongPtrW(ctl, GWLP_ID, id as isize) };
        }
        ctl
    };

    // ── 页眉（三页共用）────────────────────────────────────────────────
    let icon = mk(
        &cls_static,
        "",
        SS_ICON,
        20,
        18,
        32,
        32,
        ID_ICON,
    );
    unsafe {
        // 用 exe 里嵌的图标（资源 ID 1，见 build.rs）。
        let hicon = LoadIconW(Some(inst), PCWSTR(1 as *const u16)).unwrap_or_default();
        SendMessageW(icon, STM_SETICON, Some(WPARAM(hicon.0 as usize)), Some(LPARAM(0)));
    }

    let title = mk(
        &cls_static,
        util::PRODUCT_NAME,
        SS_LEFT,
        64,
        14,
        460,
        30,
        ID_TITLE,
    );
    let subtitle = mk(
        &cls_static,
        "多功能可视化科学计算工作台 · 离线优先",
        SS_LEFT,
        64,
        44,
        460,
        20,
        ID_SUBTITLE,
    );
    unsafe {
        SendMessageW(title, WM_SETFONT, Some(WPARAM(bold.0 as usize)), Some(LPARAM(1)));
        SendMessageW(subtitle, WM_SETFONT, Some(WPARAM(normal.0 as usize)), Some(LPARAM(1)));
    }

    // ── 选项页 ────────────────────────────────────────────────────────
    let label_path = mk(
        &cls_static,
        "安装位置",
        SS_LEFT,
        20,
        84,
        520,
        20,
        ID_LABEL_PATH,
    );
    // 路径输入框单独建：要 WS_EX_CLIENTEDGE 才有边框，否则看着不像输入框。
    let edit = {
        let t = util::wide("");
        let ctl = unsafe {
            CreateWindowExW(
                WS_EX_CLIENTEDGE,
                PCWSTR(cls_edit.as_ptr()),
                PCWSTR(t.as_ptr()),
                WS_CHILD | WS_VISIBLE | WINDOW_STYLE(ES_AUTOHSCROLL),
                20,
                106,
                430,
                26,
                Some(hwnd),
                None,
                Some(inst),
                None,
            )
        }
        .unwrap_or_default();
        unsafe { SetWindowLongPtrW(ctl, GWLP_ID, ID_PATH_EDIT as isize) };
        ctl
    };
    let browse = mk(&cls_button, "浏览…", 0, 458, 106, 82, 26, ID_BROWSE);
    let chk_desktop = mk(
        &cls_button,
        "创建桌面快捷方式",
        BS_AUTOCHECKBOX,
        20,
        150,
        300,
        22,
        ID_CHK_DESKTOP,
    );
    let chk_run = mk(
        &cls_button,
        "安装完成后运行",
        BS_AUTOCHECKBOX,
        20,
        178,
        300,
        22,
        ID_CHK_RUN,
    );
    let chk_purge = mk(
        &cls_button,
        "同时删除我的数据（设置、日志、组件缓存）",
        BS_AUTOCHECKBOX,
        20,
        150,
        480,
        22,
        ID_CHK_PURGE,
    );

    // ── 进度页 ────────────────────────────────────────────────────────
    let step = mk(&cls_static, "准备中…", SS_LEFT, 20, 110, 520, 44, ID_STEP);
    let progress = mk(&cls_progress, "", 0, 20, 168, 520, 20, 0);

    // ── 页脚按钮（三页共用）───────────────────────────────────────────
    let primary = mk(
        &cls_button,
        "安装",
        BS_DEFPUSHBUTTON,
        360,
        250,
        90,
        32,
        ID_BTN_PRIMARY,
    );
    let cancel = mk(&cls_button, "取消", 0, 458, 250, 82, 32, ID_BTN_CANCEL);

    unsafe {
        for c in [label_path, edit, browse, chk_desktop, chk_run, chk_purge, step, progress, cancel] {
            SendMessageW(c, WM_SETFONT, Some(WPARAM(normal.0 as usize)), Some(LPARAM(1)));
        }
        SendMessageW(primary, WM_SETFONT, Some(WPARAM(normal.0 as usize)), Some(LPARAM(1)));
    }

    // ── 存句柄 ────────────────────────────────────────────────────────
    ICON_CTL.store(icon.0 as isize, Ordering::SeqCst);
    TITLE_CTL.store(title.0 as isize, Ordering::SeqCst);
    SUBTITLE_CTL.store(subtitle.0 as isize, Ordering::SeqCst);
    LABEL_PATH_CTL.store(label_path.0 as isize, Ordering::SeqCst);
    EDIT_CTL.store(edit.0 as isize, Ordering::SeqCst);
    BROWSE_CTL.store(browse.0 as isize, Ordering::SeqCst);
    CHK_DESKTOP_CTL.store(chk_desktop.0 as isize, Ordering::SeqCst);
    CHK_RUN_CTL.store(chk_run.0 as isize, Ordering::SeqCst);
    CHK_PURGE_CTL.store(chk_purge.0 as isize, Ordering::SeqCst);
    STEP_CTL.store(step.0 as isize, Ordering::SeqCst);
    PROGRESS_CTL.store(progress.0 as isize, Ordering::SeqCst);
    PRIMARY_CTL.store(primary.0 as isize, Ordering::SeqCst);
    CANCEL_CTL.store(cancel.0 as isize, Ordering::SeqCst);

    // ── 按任务类型初始化选项页 ────────────────────────────────────────
    let (is_uninstall, initial_dir) = {
        let g = STATE.lock().ok();
        match g.as_ref().and_then(|g| g.as_ref()) {
            Some(s) => match &s.job {
                Job::Install { default_dir, .. } => (false, default_dir.to_string_lossy().to_string()),
                Job::Uninstall { dir } => (true, dir.to_string_lossy().to_string()),
            },
            None => (false, String::new()),
        }
    };

    if is_uninstall {
        set_text(h(&LABEL_PATH_CTL), "将卸载");
        set_text(h(&EDIT_CTL), &initial_dir);
        unsafe {
            // 卸载时路径只读，也不给"桌面快捷方式/完成后运行"这些安装选项。
            let _ = EnableWindow(h(&EDIT_CTL), false);
            let _ = EnableWindow(h(&BROWSE_CTL), false);
        }
        show(&CHK_DESKTOP_CTL, false);
        show(&CHK_RUN_CTL, false);
        show(&CHK_PURGE_CTL, true);
        set_text(h(&PRIMARY_CTL), "卸载");
    } else {
        set_text(h(&EDIT_CTL), &initial_dir);
        show(&CHK_PURGE_CTL, false);
        // 桌面快捷方式默认勾上，装完启动默认不勾。
        unsafe {
            SendMessageW(h(&CHK_DESKTOP_CTL), BM_SETCHECK, Some(WPARAM(1)), Some(LPARAM(0)));
        }
    }
    // 进度页的两件控件初始隐藏。
    show(&STEP_CTL, false);
    show(&PROGRESS_CTL, false);
    show(&BROWSE_CTL, !is_uninstall);
}

/// 建窗并跑消息循环。
pub fn run(job: Job) -> Result<()> {
    install_sink();
    // 标题随任务类型变化：卸载时不该还写"安装程序"。
    let is_uninstall = matches!(job, Job::Uninstall { .. });
    *STATE
        .lock()
        .map_err(|_| anyhow::anyhow!("界面状态被占用"))? = Some(State {
        job,
        desktop: true,
        run_after: false,
        purge: false,
    });

    unsafe {
        let instance = GetModuleHandleW(None)?;
        let inst = HINSTANCE(instance.0);

        let mut icc = INITCOMMONCONTROLSEX {
            dwSize: std::mem::size_of::<INITCOMMONCONTROLSEX>() as u32,
            dwICC: ICC_PROGRESS_CLASS,
        };
        let _ = InitCommonControlsEx(&mut icc);

        // 副标题的灰色：RGB(0x6b,0x6b,0x6b)，注意 COLORREF 是 0x00BBGGRR。
        SUBTITLE_COLOR.store(0x006b_6b6b, Ordering::SeqCst);

        let class_name = util::wide("MFMathInstallerWindow");
        let wc = WNDCLASSW {
            style: WNDCLASS_STYLES(0),
            lpfnWndProc: Some(wndproc),
            cbClsExtra: 0,
            cbWndExtra: 0,
            hInstance: inst,
            hIcon: LoadIconW(Some(inst), PCWSTR(1 as *const u16)).unwrap_or_default(),
            hCursor: LoadCursorW(None, IDC_ARROW).unwrap_or_default(),
            hbrBackground: HBRUSH((COLOR_WINDOW.0 + 1) as *mut std::ffi::c_void),
            lpszMenuName: PCWSTR::null(),
            lpszClassName: PCWSTR(class_name.as_ptr()),
        };
        if RegisterClassW(&wc) == 0 {
            anyhow::bail!("注册窗口类失败");
        }

        let what = if is_uninstall { "卸载程序" } else { "安装程序" };
        let caption = util::wide(&format!("{} {what}", util::PRODUCT_NAME));
        let hwnd = CreateWindowExW(
            WS_EX_DLGMODALFRAME,
            PCWSTR(class_name.as_ptr()),
            PCWSTR(caption.as_ptr()),
            WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            580,
            340,
            None,
            None,
            Some(inst),
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
