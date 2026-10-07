//! winbridge.rs —— 窗口与文件对话框桥（JS 侧 `hostObjects.sync.win`）
//! 对照 C# `MFMath.Host/WindowBridge.cs` 逐条实现。
//!
//! **为什么文件对话框放在宿主**：页面里既不能弹系统对话框，也不能写任意路径。
//! 工作区"另存为 / 从文件打开"、导出设置、导出图片都要走这里。
//!
//! **为什么这两个方法是同步返回、不用投递**（C# 注释里的判断，照搬）：
//! 它们要拿到用户的即时选择（确定/取消），投递式调用只能返回"已投递"。对话框是模态的，
//! 阻塞的只是这一次 JS 调用，不会像 ToggleMaximize 那样和 WebView 的 resize 回调互等。
//!
//! **自动化钩子**：`path` 非空时**跳过对话框**直接读写该路径 —— 只给测试脚本与命令行场景用。

use std::path::Path;
use std::sync::OnceLock;

use serde_json::json;
use windows::core::PCWSTR;
use windows::Win32::Foundation::HWND;
use windows::Win32::UI::Controls::Dialogs::{
    GetOpenFileNameW, GetSaveFileNameW, OFN_EXPLORER, OFN_FILEMUSTEXIST, OFN_NOCHANGEDIR,
    OFN_OVERWRITEPROMPT, OPENFILENAMEW,
};
use windows::Win32::UI::Input::KeyboardAndMouse::ReleaseCapture;
use windows::Win32::UI::WindowsAndMessaging::{
    IsZoomed, PostMessageW, SendMessageW, ShowWindow, SW_MAXIMIZE, SW_MINIMIZE, SW_RESTORE,
    WM_CLOSE, WM_NCLBUTTONDOWN,
};

/// 主窗口句柄（run() 建好窗口后塞进来；其余模块只读）
static HWND_RAW: OnceLock<isize> = OnceLock::new();

pub fn set_hwnd(h: isize) {
    let _ = HWND_RAW.set(h);
}

fn hwnd() -> Option<HWND> {
    HWND_RAW
        .get()
        .map(|h| HWND(*h as *mut core::ffi::c_void))
}

/// 无边框窗口默认是**直角且没有投影**（去掉系统标题栏会丢掉 DWM 的边框渲染），
/// 于是窗口看起来像一块贴死的方块，跟 UI 内的圆角面板不搭。用 DWM 属性补回：
///   · DWMWA_WINDOW_CORNER_PREFERENCE = ROUND → Windows 11 的原生圆角
///   · DWMWA_NCRENDERING_POLICY = ENABLED     → 让 DWM 重新绘制投影
///   · DWMWA_BORDER_COLOR = DWMWA_COLOR_NONE  → **别画那 1px 外框**
///
/// ⚠ 第三条是必须的、不是可选的美化：一旦打开非客户区渲染，DWM 会在窗口外沿补画
/// 一圈 1px 边框（+投影）。对 WPF（C# 宿主）那是有边框窗口的边框回来了；但对 tao 这种
/// "样式里根本没有 WS_CAPTION/WS_THICKFRAME"的窗口，那一圈就是**凭空多出来的一个空窗框**
/// —— 用户看到的"程序周围一圈 WinForm 窗口"就是它。
///
/// ⚠⚠ **只在窗口无边框（`decorations(false)`）时才调用它。** 有系统标题栏时 Windows
/// 自己会画圆角与投影，什么都不用补，这时再打开非客户区渲染反而会多画一圈。
#[allow(dead_code)]
pub fn apply_dwm_chrome(hwnd_raw: isize) {
    use windows::Win32::Graphics::Dwm::{
        DwmSetWindowAttribute, DWMWA_BORDER_COLOR, DWMWA_COLOR_NONE, DWMWA_NCRENDERING_POLICY,
        DWMWA_WINDOW_CORNER_PREFERENCE,
    };
    let h = HWND(hwnd_raw as *mut core::ffi::c_void);
    // SAFETY: 三个属性都只读我们传入的定长值；失败（旧系统）直接忽略
    unsafe {
        let round: i32 = 2; // DWMWCP_ROUND
        let _ = DwmSetWindowAttribute(
            h,
            DWMWA_WINDOW_CORNER_PREFERENCE,
            &round as *const i32 as *const core::ffi::c_void,
            std::mem::size_of::<i32>() as u32,
        );
        /* ⚠⚠ 这里必须是 **2**。`DWMNCRENDERINGPOLICY` 的枚举是：
         *     0 = DWMNCRP_USEWINDOWSTYLE / 1 = DWMNCRP_DISABLED / 2 = DWMNCRP_ENABLED
         * 2026-10-07 修的 bug：这一行原先写的是 `1`（注释却写着 ENABLED），于是我们实际
         * 把 DWM 的**非客户区渲染关掉了** —— DWM 一关，Windows 就退回**经典（未主题化）
         * 窗口边框**，在无边框窗口上表现为"凭空多出一个 WinForm 味的老式窗框"。
         * 因为 tao 把客户区铺满整个窗口，那圈框只在**底部与两侧**露出来，
         * 用户的原话是"为什么底部会有一个 WinForm 的窗口"。
         * 对照：C# 宿主 `MainWindow.xaml.cs:15, 100-101` 传的就是 `DWMNCRP_ENABLED = 2`。 */
        let nc: i32 = 2; // DWMNCRP_ENABLED（**不是 1**，1 是 DISABLED）
        let _ = DwmSetWindowAttribute(
            h,
            DWMWA_NCRENDERING_POLICY,
            &nc as *const i32 as *const core::ffi::c_void,
            std::mem::size_of::<i32>() as u32,
        );
        // 0xFFFFFFFE = DWMWA_COLOR_NONE："不画边框"，只留圆角与投影
        let no_border: u32 = DWMWA_COLOR_NONE;
        let _ = DwmSetWindowAttribute(
            h,
            DWMWA_BORDER_COLOR,
            &no_border as *const u32 as *const core::ffi::c_void,
            std::mem::size_of::<u32>() as u32,
        );
    }
}

/* ── 窗口操作 ───────────────────────────────────────────────────────── */

pub fn minimize() {
    if let Some(h) = hwnd() {
        // SAFETY: 句柄来自本进程的主窗口；ShowWindow 只读该句柄
        unsafe { let _ = ShowWindow(h, SW_MINIMIZE); }
    }
}

pub fn toggle_maximize() {
    let Some(h) = hwnd() else { return };
    // SAFETY: 同上
    unsafe {
        if IsZoomed(h).as_bool() {
            let _ = ShowWindow(h, SW_RESTORE);
        } else {
            let _ = ShowWindow(h, SW_MAXIMIZE);
        }
    }
}

pub fn is_maximized() -> bool {
    match hwnd() {
        // SAFETY: 同上
        Some(h) => unsafe { IsZoomed(h).as_bool() },
        None => false,
    }
}

pub fn close() {
    if let Some(h) = hwnd() {
        // SAFETY: 向自己的主窗口投递 WM_CLOSE（不跨进程）
        unsafe { let _ = PostMessageW(Some(h), WM_CLOSE, Default::default(), Default::default()); }
    }
}

/// 无边框窗口的标题栏拖拽：释放捕获后把"点在标题栏"的消息发给窗口，交给系统拖动
pub fn start_drag() {
    let Some(h) = hwnd() else { return };
    // SAFETY: 标准的"手动标题栏拖拽"配方（ReleaseCapture + WM_NCLBUTTONDOWN/HTCAPTION）
    unsafe {
        let _ = ReleaseCapture();
        SendMessageW(
            h,
            WM_NCLBUTTONDOWN,
            Some(windows::Win32::Foundation::WPARAM(2)), // HTCAPTION
            Some(windows::Win32::Foundation::LPARAM(0)),
        );
    }
}

/// 用 JS 当前主题色设置窗口背景。
/// 窗口背景只在"加载中/缩放/最大化动画"的瞬间可见，但那时露出的白色很扎眼，
/// 所以让 JS 在切换主题时回设一次。颜色串非法就保持原背景（与 C# 一致）。
pub fn set_chrome_background(color: &str) {
    let Some(h) = hwnd() else { return };
    let Some(rgb) = parse_hex_color(color) else { return };
    // SAFETY: 给窗口类换一支实心画刷并请求重绘；句柄与画刷都由本进程持有
    unsafe {
        use windows::Win32::Foundation::COLORREF;
        use windows::Win32::Graphics::Gdi::{CreateSolidBrush, InvalidateRect, HBRUSH};
        use windows::Win32::UI::WindowsAndMessaging::{SetClassLongPtrW, GCLP_HBRBACKGROUND};
        let brush: HBRUSH = CreateSolidBrush(COLORREF(rgb));
        SetClassLongPtrW(h, GCLP_HBRBACKGROUND, brush.0 as isize);
        let _ = InvalidateRect(Some(h), None, true);
    }
}

/// `#rrggbb` / `rrggbb` → COLORREF（0x00BBGGRR），非法返回 None
fn parse_hex_color(s: &str) -> Option<u32> {
    let t = s.trim().trim_start_matches('#');
    if t.len() != 6 || !t.chars().all(|c| c.is_ascii_hexdigit()) {
        return None;
    }
    let r = u32::from_str_radix(&t[0..2], 16).ok()?;
    let g = u32::from_str_radix(&t[2..4], 16).ok()?;
    let b = u32::from_str_radix(&t[4..6], 16).ok()?;
    Some((b << 16) | (g << 8) | r)
}

/* ── 文件对话框（文本 / 二进制）────────────────────────────────────── */

/// 保存文本到用户选定的文件。返回 `{ok,path,bytes}` / `{canceled:true}` / `{ok:false,error}`
pub fn save_text_file(title: &str, default_name: &str, filter: &str, content: &str, path: &str) -> String {
    let target = match pick_target(title, default_name, filter, path, true) {
        Ok(Some(p)) => p,
        Ok(None) => return json!({ "canceled": true }).to_string(),
        Err(e) => return json!({ "ok": false, "error": e }).to_string(),
    };
    if let Some(dir) = Path::new(&target).parent() {
        if !dir.as_os_str().is_empty() {
            let _ = std::fs::create_dir_all(dir);
        }
    }
    // 不带 BOM：JSON 消费方（包括本应用自己）按 UTF-8 读，BOM 只会带来麻烦
    match std::fs::write(&target, content.as_bytes()) {
        Ok(()) => {
            let bytes = std::fs::metadata(&target).map(|m| m.len()).unwrap_or(0);
            json!({ "ok": true, "path": target, "bytes": bytes }).to_string()
        }
        Err(e) => json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}

/// 从用户选定的文件读文本。返回 `{ok,path,content}` / `{canceled:true}` / `{ok:false,error}`
pub fn open_text_file(title: &str, filter: &str, path: &str) -> String {
    let target = match pick_target(title, "", filter, path, false) {
        Ok(Some(p)) => p,
        Ok(None) => return json!({ "canceled": true }).to_string(),
        Err(e) => return json!({ "ok": false, "error": e }).to_string(),
    };
    let p = Path::new(&target);
    if !p.is_file() {
        return json!({ "ok": false, "error": format!("文件不存在：{target}") }).to_string();
    }
    match std::fs::metadata(p) {
        Ok(md) if md.len() > 64 * 1024 * 1024 => {
            return json!({ "ok": false, "error": format!("文件过大（>64 MB），拒绝读取：{target}") }).to_string();
        }
        _ => {}
    }
    match std::fs::read_to_string(p) {
        Ok(text) => json!({ "ok": true, "path": target, "content": text }).to_string(),
        Err(e) => json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}

/// 保存**二进制**内容（导出图片走这条：页面把 canvas 转成 dataURL 传进来）。
/// 上限 64 MB：正常 2x 位图也就 3-5 MB，超过说明调用方传错了东西。
pub fn save_binary_file(
    title: &str, default_name: &str, filter: &str, base64: &str, path: &str,
) -> String {
    let mut data = base64.trim();
    // 允许直接把 dataURL 传进来
    if data.len() > 5 && data[..5].eq_ignore_ascii_case("data:") {
        if let Some(comma) = data.find(',') {
            data = &data[comma + 1..];
        }
    }
    if data.is_empty() {
        return json!({ "ok": false, "error": "内容为空" }).to_string();
    }
    let bytes = match base64_decode(data) {
        Ok(b) => b,
        Err(e) => return json!({ "ok": false, "error": e }).to_string(),
    };
    if bytes.len() > 64 * 1024 * 1024 {
        return json!({ "ok": false, "error": "内容过大（>64 MB）" }).to_string();
    }
    let target = match pick_target(title, default_name, filter, path, true) {
        Ok(Some(p)) => p,
        Ok(None) => return json!({ "canceled": true }).to_string(),
        Err(e) => return json!({ "ok": false, "error": e }).to_string(),
    };
    if let Some(dir) = Path::new(&target).parent() {
        if !dir.as_os_str().is_empty() {
            let _ = std::fs::create_dir_all(dir);
        }
    }
    match std::fs::write(&target, &bytes) {
        Ok(()) => json!({ "ok": true, "path": target, "bytes": bytes.len() }).to_string(),
        Err(e) => json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}

/// 决定目标路径：给了 `path` 就直接用（自动化钩子）；否则弹系统对话框。
/// `Ok(None)` = 用户取消。
fn pick_target(
    title: &str, default_name: &str, filter: &str, path: &str, save: bool,
) -> Result<Option<String>, String> {
    if !path.trim().is_empty() {
        return Ok(Some(path.trim().to_string()));
    }
    dialog(title, default_name, filter, save)
}

/// Win32 通用文件对话框（comdlg32）。C# 用 SaveFileDialog/OpenFileDialog，底层是同一套。
fn dialog(title: &str, default_name: &str, filter: &str, save: bool) -> Result<Option<String>, String> {
    const MAX_PATH_W: usize = 1024;
    let mut buf: Vec<u16> = vec![0; MAX_PATH_W];

    // 默认文件名
    let name: Vec<u16> = if default_name.trim().is_empty() {
        if save { "workspace.mfws.json" } else { "" }
    } else {
        default_name.trim()
    }
    .encode_utf16()
    .collect();
    for (i, c) in name.iter().enumerate().take(MAX_PATH_W - 1) {
        buf[i] = *c;
    }

    // 过滤器："JSON 文件 (*.json)|*.json|所有文件 (*.*)|*.*" → 以 \0 分隔 + 双 \0 结尾
    let flt_src = if filter.trim().is_empty() { "所有文件 (*.*)|*.*" } else { filter.trim() };
    let mut flt: Vec<u16> = flt_src
        .split('|')
        .flat_map(|part| part.encode_utf16().chain(std::iter::once(0)))
        .collect();
    flt.push(0);

    let t: Vec<u16> = if title.trim().is_empty() {
        if save { "保存".to_string() } else { "打开".to_string() }
    } else {
        title.trim().to_string()
    }
    .encode_utf16()
    .chain(std::iter::once(0))
    .collect();

    let mut ofn = OPENFILENAMEW {
        lStructSize: std::mem::size_of::<OPENFILENAMEW>() as u32,
        hwndOwner: hwnd().unwrap_or_default(),
        lpstrFilter: PCWSTR(flt.as_ptr()),
        nFilterIndex: 1,
        lpstrFile: windows::core::PWSTR(buf.as_mut_ptr()),
        nMaxFile: MAX_PATH_W as u32,
        lpstrTitle: PCWSTR(t.as_ptr()),
        Flags: OFN_EXPLORER | OFN_NOCHANGEDIR
            | if save { OFN_OVERWRITEPROMPT } else { OFN_FILEMUSTEXIST },
        ..Default::default()
    };

    // SAFETY: 所有指针都指向本函数栈上的、活得比调用久的缓冲区；结构体按 Win32 布局手填
    let ok = unsafe {
        if save {
            GetSaveFileNameW(&mut ofn).as_bool()
        } else {
            GetOpenFileNameW(&mut ofn).as_bool()
        }
    };
    if !ok {
        return Ok(None); // 取消（或失败）——C# 的 ShowDialog != true 同一分支
    }
    let end = buf.iter().position(|&c| c == 0).unwrap_or(0);
    if end == 0 {
        return Ok(None);
    }
    Ok(Some(String::from_utf16_lossy(&buf[..end])))
}

/// 标准 base64 解码（忽略空白；拒绝非法字符与错误填充）。
/// 手写而不引 crate：这一段只有二十来行，换来的是宿主依赖表不再增加。
fn base64_decode(s: &str) -> Result<Vec<u8>, String> {
    fn val(c: u8) -> Option<u8> {
        match c {
            b'A'..=b'Z' => Some(c - b'A'),
            b'a'..=b'z' => Some(c - b'a' + 26),
            b'0'..=b'9' => Some(c - b'0' + 52),
            b'+' => Some(62),
            b'/' => Some(63),
            _ => None,
        }
    }
    let mut out = Vec::with_capacity(s.len() / 4 * 3);
    let mut acc = 0u32;
    let mut nbits = 0u32;
    let mut pad = 0usize;
    for &c in s.as_bytes() {
        if c.is_ascii_whitespace() {
            continue;
        }
        if c == b'=' {
            pad += 1;
            continue;
        }
        if pad > 0 {
            return Err("base64 填充位置非法".into());
        }
        let Some(v) = val(c) else {
            return Err(format!("base64 含非法字符：{}", c as char));
        };
        acc = (acc << 6) | v as u32;
        nbits += 6;
        if nbits >= 8 {
            nbits -= 8;
            out.push(((acc >> nbits) & 0xFF) as u8);
        }
    }
    if pad > 2 {
        return Err("base64 填充过多".into());
    }
    Ok(out)
}
