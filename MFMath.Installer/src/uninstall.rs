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
pub fn respawn_from_temp(dir: &Path, purge: bool, silent: bool) -> Result<bool> {
    let temp = std::env::temp_dir();
    let copy = temp.join(format!("mfmath-uninstall-{}.exe", std::process::id()));
    let me = util::current_exe()?;
    if let Err(e) = std::fs::copy(&me, &copy) {
        util::warn(&format!(
            "无法把卸载器复制到临时目录（{e}），改为原地卸载；卸载器自身会留到退出后由收尾脚本清理。"
        ));
        return Ok(false);
    }
    // 参数必须原样转发：漏掉 --purge 会让临时副本保留用户数据，
    // 漏掉 --silent 会让静默卸载突然开始输出。
    let mut cmd = Command::new(&copy);
    cmd.arg("--uninstall")
        .arg("--from-temp")
        .arg("--dir")
        .arg(dir);
    if purge {
        cmd.arg("--purge");
    }
    if silent {
        cmd.arg("--silent");
    }
    match cmd.spawn() {
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

    // 只删本产品自己的文件。安装目录里可能有别的东西（例如旧版本的主程序），
    // 它们不属于本产品，一律不动。
    let mut owned = 0usize;
    match read_owned_files(&dir) {
        Ok(files) => {
            for rel in &files {
                let p = dir.join(rel.replace('/', "\\"));
                if p.starts_with(&dir) && std::fs::remove_file(&p).is_ok() {
                    owned += 1;
                }
            }
        }
        Err(e) => util::warn(&format!("读安装清单失败（{e}），无法按清单精确清理。")),
    }
    // 卸载器与清单本身也属本产品。
    let _ = std::fs::remove_file(dir.join(util::MANIFEST_NAME));
    let _ = std::fs::remove_file(dir.join(util::UNINSTALL_EXE_NAME));
    remove_empty_dirs(&dir);
    util::say(&format!("已删除本产品的 {owned} 个文件。"));

    // 目录里若还剩别的东西，保留目录并如实说明；只有空了才删目录。
    let left: Vec<String> = std::fs::read_dir(&dir)
        .map(|it| {
            it.filter_map(Result::ok)
                .map(|e| e.file_name().to_string_lossy().to_string())
                .collect()
        })
        .unwrap_or_default();
    let dir_now_empty = left.is_empty();
    if dir_now_empty {
        match std::fs::remove_dir_all(&dir) {
            Ok(()) => util::say(&format!("已删除安装目录：{}", dir.display())),
            Err(e) => util::warn(&format!(
                "安装目录未删除（{}）：{e}\n  余下部分由收尾脚本在退出后清理。",
                dir.display()
            )),
        }
    } else {
        util::say(&format!(
            "安装目录里还有 {} 项不属于本产品，予以保留：{}",
            left.len(),
            left.iter().take(6).cloned().collect::<Vec<_>>().join("、")
        ));
    }

    // 收尾：本进程退出后由脚本删除自身；只有目录该清空时才连目录一起删。
    match schedule_cleanup(&dir, dir_now_empty) {
        Ok(()) => util::say("已安排退出后清理（含卸载器自身）。"),
        Err(e) => util::warn(&format!("安排退出后清理失败：{e:#}")),
    }

    util::say("卸载完成。");
    Ok(())
}

/// 从安装清单里取出本产品登记的文件（相对路径）。
fn read_owned_files(dir: &Path) -> Result<Vec<String>> {
    let text = std::fs::read_to_string(dir.join(util::MANIFEST_NAME))?;
    let m: crate::payload::Manifest = serde_json::from_str(&text)?;
    Ok(m.files.into_iter().map(|f| f.path).collect())
}

/// 删掉目录里已经空了的子目录（只在下层，避免误删目标目录本身）。
fn remove_empty_dirs(dir: &Path) {
    for entry in walkdir::WalkDir::new(dir)
        .min_depth(1)
        .contents_first(true)
        .into_iter()
        .filter_map(Result::ok)
    {
        if entry.file_type().is_dir() {
            let _ = std::fs::remove_dir(entry.path());
        }
    }
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

/// 安排退出后清理：删掉卸载器自身；`remove_dir` 为真时连安装目录一起删。
///
/// 不用 `MoveFileEx(MOVEFILE_DELAY_UNTIL_REBOOT)`：那条路要写 HKLM 的
/// `PendingFileRenameOperations`，而本产品是每用户安装、不请求管理员权限，
/// 普通账户下它必然失败，临时副本会永远留在 `%TEMP%`。
///
/// 改为起一个隐藏的 `cmd`，等本进程退出后自行删除，不需要任何特权。
/// 命令写进临时 `.cmd` 文件再执行，避免把带引号的路径拼进 `cmd /c` 的转义问题；
/// 延迟用 `ping`，因为 `timeout` 在 stdin 被重定向时会直接失败。
fn schedule_cleanup(install_dir: &Path, remove_dir: bool) -> Result<()> {
    use std::os::windows::process::CommandExt;
    use std::process::Stdio;

    /// 不弹出控制台窗口。
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;

    let me = util::current_exe()?;
    let script_path =
        std::env::temp_dir().join(format!("mfmath-cleanup-{}.cmd", std::process::id()));
    let mut script = String::from("@echo off\r\nping -n 3 127.0.0.1 >nul\r\n");
    if remove_dir {
        // 目录里不该再有别的东西才走到这里；`rd` 对不存在的路径不报错。
        script.push_str(&format!("rd /s /q \"{}\"\r\n", install_dir.display()));
    }
    script.push_str(&format!("del /f /q \"{}\"\r\n", me.display()));
    script.push_str("del /f /q \"%~f0\"\r\n");

    std::fs::write(&script_path, script)
        .with_context(|| format!("写收尾脚本失败：{}", script_path.display()))?;

    Command::new("cmd")
        .arg("/c")
        .arg(&script_path)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .creation_flags(CREATE_NO_WINDOW)
        .spawn()
        .context("启动收尾脚本失败")?;
    Ok(())
}
