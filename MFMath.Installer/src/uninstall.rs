//! 卸载：结束主程序、删快捷方式与注册表项、删安装目录；可选删用户数据。
//!
//! 运行中的 exe 无法删除自己所在的目录，所以卸载分两段：
//! 先把自身复制到临时目录并以 `--from-temp` 重启，再由临时副本执行实际删除。

use std::path::{Path, PathBuf};
use std::process::Command;

use anyhow::{Context, Result};

use crate::util;
use crate::{registry, shortcut};

pub struct Options {
    /// 要卸载的目录。未指定时取当前可执行文件所在目录。
    pub dir: Option<PathBuf>,
    /// 同时删除用户数据目录。
    pub purge: bool,
}

/// 从临时目录重新启动自己，然后退出。
///
/// 返回 `Ok(true)` 表示已转交临时副本（调用方应结束进程）；
/// 返回 `Ok(false)` 表示复制或启动失败，调用方应退回**原地卸载**。
pub fn respawn_from_temp(dir: &Path) -> Result<bool> {
    let temp = std::env::temp_dir();
    let copy = temp.join(format!("mfmath-uninstall-{}.exe", std::process::id()));
    let me = util::current_exe()?;
    if let Err(e) = std::fs::copy(&me, &copy) {
        util::warn(&format!(
            "无法把卸载器复制到临时目录（{e}），改为原地卸载；卸载器自身会留到下次重启后清理。"
        ));
        return Ok(false);
    }
    match Command::new(&copy)
        .arg("--uninstall")
        .arg("--from-temp")
        .arg("--dir")
        .arg(dir)
        .spawn()
    {
        Ok(_) => Ok(true),
        Err(e) => {
            util::warn(&format!("启动临时卸载进程失败（{e}），改为原地卸载。"));
            Ok(false)
        }
    }
}

/// 执行卸载。此函数在临时目录的副本里运行。
pub fn run(opts: &Options) -> Result<()> {
    let dir = match &opts.dir {
        Some(d) => d.clone(),
        None => util::current_exe()?
            .parent()
            .map(Path::to_path_buf)
            .context("无法确定安装目录")?,
    };

    util::say(&format!("卸载：{}", util::PRODUCT_NAME));
    util::say(&format!("安装目录：{}", dir.display()));

    stop_running_main();

    for lnk in [shortcut::start_menu_lnk(), shortcut::desktop_lnk()] {
        match shortcut::remove(&lnk) {
            Ok(()) => util::say(&format!("已删除快捷方式：{}", lnk.display())),
            Err(e) => util::warn(&format!("快捷方式未删除（{}）：{e}", lnk.display())),
        }
    }

    match registry::remove_uninstall_key() {
        Ok(()) => util::say("已删除卸载注册表项。"),
        Err(e) => util::warn(&format!("注册表项未删除：{e}")),
    }

    if opts.purge {
        let data = util::user_data_dir();
        match util::remove_dir_all(&data) {
            Ok(()) => util::say(&format!("已删除用户数据：{}", data.display())),
            Err(e) => util::warn(&format!("用户数据未删除（{}）：{e}", data.display())),
        }
    } else {
        util::say(&format!(
            "保留用户数据：{}（设置、日志、组件缓存）",
            util::user_data_dir().display()
        ));
    }

    match util::remove_dir_all(&dir) {
        Ok(()) => util::say(&format!("已删除安装目录：{}", dir.display())),
        Err(e) => {
            // 原地卸载时，正在运行的这个 exe 自己删不掉，属预期情况。
            util::warn(&format!(
                "安装目录未完全删除（{}）：{e}\n  正运行中的卸载器会留到下次重启后清理。",
                dir.display()
            ));
        }
    }

    // 自删除要写 HKLM 的 PendingFileRenameOperations；受限环境下会失败，
    // 但那不影响本次卸载的结果，按非致命处理。
    if let Err(e) = schedule_self_delete() {
        util::warn(&format!("登记自删除失败（不影响卸载结果）：{e:#}"));
    }

    util::say("卸载完成。");
    Ok(())
}

/// 结束正在运行的主程序，否则它的文件删不掉。
fn stop_running_main() {
    let _ = Command::new("taskkill")
        .args(["/IM", util::MAIN_EXE_NAME, "/F"])
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status();
    std::thread::sleep(std::time::Duration::from_millis(400));
}

/// 把临时目录里的自己排进「下次重启时删除」队列。
fn schedule_self_delete() -> Result<()> {
    use windows::core::PCWSTR;
    use windows::Win32::Storage::FileSystem::{MoveFileExW, MOVEFILE_DELAY_UNTIL_REBOOT};

    let me = util::current_exe()?;
    let me_w = util::wide(&me.to_string_lossy());
    unsafe {
        MoveFileExW(
            PCWSTR(me_w.as_ptr()),
            PCWSTR::null(),
            MOVEFILE_DELAY_UNTIL_REBOOT,
        )
        .context("登记自删除失败")?;
    }
    Ok(())
}
