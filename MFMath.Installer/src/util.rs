//! 公用工具：路径、输出、哈希、宽字符串。

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};

/// 静默模式（`/S`）：抑制全部输出。
static SILENT: AtomicBool = AtomicBool::new(false);

pub fn set_silent(v: bool) {
    SILENT.store(v, Ordering::SeqCst);
}

pub fn is_silent() -> bool {
    SILENT.load(Ordering::SeqCst)
}

pub const PRODUCT_NAME: &str = "Multifunctional-Mathematics";
/// 安装目录名。与 v1 的 `MF-Mathematics` 区分开：v1 用的是
/// `%LOCALAPPDATA%\Programs\MF-Mathematics\`，两者互不干扰。
pub const INSTALL_DIR_NAME: &str = "Multifunctional-Mathematics";
pub const USER_DATA_DIR_NAME: &str = "MFMath";
pub const MAIN_EXE_NAME: &str = "Multifunctional-Mathematics.exe";
/// 构建产物名。安装时改名为 `MAIN_EXE_NAME`。
pub const BUILT_EXE_NAME: &str = "mfmath-host-rust.exe";
pub const UNINSTALL_EXE_NAME: &str = "uninstall.exe";
pub const MANIFEST_NAME: &str = "manifest.json";
pub const UNINSTALL_KEY: &str =
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Multifunctional-Mathematics";

/// 带刷新的输出。安装器是交互式程序，输出不能留在缓冲区里。
pub fn say(msg: &str) {
    if is_silent() {
        return;
    }
    println!("{msg}");
    use std::io::Write;
    let _ = std::io::stdout().flush();
}

pub fn warn(msg: &str) {
    if is_silent() {
        return;
    }
    eprintln!("{msg}");
}

pub fn local_app_data() -> PathBuf {
    std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

pub fn roaming_app_data() -> PathBuf {
    std::env::var_os("APPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

/// 默认安装目录：`%LOCALAPPDATA%\Programs\Multifunctional-Mathematics`。
pub fn default_install_dir() -> PathBuf {
    local_app_data().join("Programs").join(INSTALL_DIR_NAME)
}

/// 用户数据目录：`%LOCALAPPDATA%\MFMath`。卸载默认不动它。
pub fn user_data_dir() -> PathBuf {
    local_app_data().join(USER_DATA_DIR_NAME)
}

/// 开始菜单的 Programs 目录。
pub fn start_menu_dir() -> PathBuf {
    roaming_app_data()
        .join("Microsoft")
        .join("Windows")
        .join("Start Menu")
        .join("Programs")
}

pub fn desktop_dir() -> PathBuf {
    std::env::var_os("USERPROFILE")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
        .join("Desktop")
}

/// 本进程可执行文件的完整路径。
pub fn current_exe() -> anyhow::Result<PathBuf> {
    Ok(std::env::current_exe()?)
}

/// 文件 sha256，十六进制小写。
pub fn sha256_file(path: &Path) -> anyhow::Result<String> {
    use sha2::{Digest, Sha256};
    use std::io::Read;
    let mut f = std::fs::File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buf = [0u8; 64 * 1024];
    loop {
        let n = f.read(&mut buf)?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

/// 转成 NUL 结尾的宽字符串，供 Win32 API 使用。
pub fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

/// 目录占用字节数。
pub fn dir_size(dir: &Path) -> u64 {
    walkdir::WalkDir::new(dir)
        .into_iter()
        .filter_map(Result::ok)
        .filter(|e| e.file_type().is_file())
        .filter_map(|e| e.metadata().ok())
        .map(|m| m.len())
        .sum()
}

/// 递归删除目录。目录不存在时视为成功。
pub fn remove_dir_all(dir: &Path) -> anyhow::Result<()> {
    if !dir.exists() {
        return Ok(());
    }
    std::fs::remove_dir_all(dir)?;
    Ok(())
}
