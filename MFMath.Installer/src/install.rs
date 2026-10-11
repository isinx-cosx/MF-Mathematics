//! 安装：释放载荷、主程序改名、建快捷方式、写清单与卸载信息。

use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};

use crate::payload::{self, Payload};use crate::util;
use crate::{registry, shortcut};

pub struct Options {
    pub dir: PathBuf,
    /// 目标目录里已有本产品以外的文件时，是否仍然继续。
    pub force: bool,
}

/// 本机当前的本地时间，`YYYY-MM-DDTHH:MM:SS`。
fn now_local() -> String {
    let st = unsafe { windows::Win32::System::SystemInformation::GetLocalTime() };
    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}",
        st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond
    )
}

/// 结束正在运行的主程序。未运行时静默返回。
fn stop_running_main() {
    let _ = std::process::Command::new("taskkill")
        .args(["/IM", util::MAIN_EXE_NAME, "/F"])
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status();
    // 给系统一点时间释放文件句柄。
    std::thread::sleep(std::time::Duration::from_millis(400));
}

pub fn run(opts: &Options) -> Result<()> {
    let me = util::current_exe()?;
    let payload = Payload::locate(&me)?;
    let meta = payload.meta().context("读取载荷元信息失败")?;

    if let Some(old) = registry::installed_version() {
        if old != meta.version {
            util::say(&format!(
                "检测到已安装版本 {old}，将升级到 {}。",
                meta.version
            ));
        } else {
            util::say(&format!("已安装同版本 {}，将重新安装。", meta.version));
        }
    }

    let dir = opts.dir.clone();
    util::say(&format!("安装目标：{}", dir.display()));

    // 覆盖安装前先结束正在运行的主程序，否则它的文件删不掉。
    stop_running_main();
    prepare_target(&dir, opts.force)?;
    std::fs::create_dir_all(&dir)
        .with_context(|| format!("创建安装目录失败：{}", dir.display()))?;

    let written = payload
        .extract_into(&dir)
        .context("释放载荷失败")?;
    util::say(&format!("已释放 {written} 个文件。"));

    let main_exe = rename_main(&dir)?;
    let uninstall_exe = install_uninstaller(&dir, &me)?;

    // 图标优先用载荷里的 icon.ico；没有就用主程序自带的图标（传 None）。
    let icon = {
        let p = dir.join("icon.ico");
        if p.is_file() {
            Some(p)
        } else {
            None
        }
    };

    util::say("创建快捷方式…");
    for lnk in [shortcut::start_menu_lnk(), shortcut::desktop_lnk()] {
        if let Err(e) = shortcut::create(
            &lnk,
            &main_exe,
            &dir,
            util::PRODUCT_NAME,
            icon.as_deref(),
        ) {
            // 快捷方式失败不影响程序可用，如实报告但不中断。
            util::warn(&format!("  快捷方式未创建（{}）：{e}", lnk.display()));
        } else {
            util::say(&format!("  {}", lnk.display()));
        }
    }

    let installed_at = now_local();
    // 清单只登记本产品释放的文件；归档里叫 BUILT_EXE_NAME 的那条在安装时已改名。
    let mut owned: Vec<String> = payload
        .entry_names()
        .context("读取载荷文件清单失败")?
        .into_iter()
        .map(|n| {
            if n == util::BUILT_EXE_NAME {
                util::MAIN_EXE_NAME.to_string()
            } else {
                n
            }
        })
        .collect();
    owned.push(util::UNINSTALL_EXE_NAME.to_string());
    let manifest = payload::build_manifest(&dir, &meta, &installed_at, &owned)
        .context("生成安装清单失败")?;
    let manifest_path = dir.join(util::MANIFEST_NAME);
    std::fs::write(&manifest_path, serde_json::to_vec_pretty(&manifest)?)
        .with_context(|| format!("写入清单失败：{}", manifest_path.display()))?;

    let size_kb = util::dir_size(&dir) / 1024;
    // 卸载信息写不进只影响「已安装的应用」里的列表项，程序本身照常可用，
    // 因此按非致命处理：报告出来，继续走完安装。
    let mut note = String::new();
    match registry::write_uninstall_key(&dir, &meta.version, size_kb) {
        Ok(()) => util::say("已写入卸载信息。"),
        Err(e) => {
            note = format!("{e:#}") ;
            util::warn(&format!(
                "  卸载信息未写入（不影响运行，但「设置 → 应用」里不会出现本产品）：{note}"
            ));
        }
    }

    util::say("");
    util::say(&format!(
        "{} {} 安装完成。",
        util::PRODUCT_NAME, meta.version
    ));
    util::say(&format!("安装目录：{}", dir.display()));
    util::say(&format!("主程序：{}", main_exe.display()));
    util::say(&format!("卸载程序：{}", uninstall_exe.display()));
    util::say(&format!("清单记录了 {} 个文件。", manifest.files.len()));
    if !note.is_empty() {
        util::warn("有一步未完成，见上面的警告。");
    }
    Ok(())
}

/// 安装前的目标目录检查与清理。
///
/// 安装目录里可能有**本产品以外**的东西 —— 实测本机的
/// `%LOCALAPPDATA%\Programs\MF-Mathematics\` 里就装着 v1（132 MB 的主程序加
/// 它自己的卸载器）。因此这里绝不无条件清空目录：
///
/// * 目录不存在或为空 —— 直接安装；
/// * 目录里有我们自己的 `manifest.json` —— 按旧清单只删我们登记过的文件，属覆盖升级；
/// * 其余情况 —— 默认**拒绝**，列出看到的内容，让用户换目录或显式 `--force`；
///   即使 `--force`，也只覆盖同名文件，不动其它文件。
fn prepare_target(dir: &Path, force: bool) -> Result<()> {
    if !dir.is_dir() {
        return Ok(());
    }
    let entries: Vec<std::fs::DirEntry> = std::fs::read_dir(dir)
        .with_context(|| format!("读取目标目录失败：{}", dir.display()))?
        .filter_map(Result::ok)
        .collect();
    if entries.is_empty() {
        return Ok(());
    }

    let manifest_path = dir.join(util::MANIFEST_NAME);
    if manifest_path.is_file() {
        match read_manifest(&manifest_path) {
            Ok(old) => {
                util::say(&format!(
                    "检测到既有安装（版本 {}），按清单清理旧文件。",
                    old.version
                ));
                for f in &old.files {
                    let target = dir.join(f.path.replace('/', "\\"));
                    // 只删清单登记过、且确实在目标目录内的文件。
                    if target.starts_with(dir) {
                        let _ = std::fs::remove_file(&target);
                    }
                }
                remove_empty_dirs(dir);
                return Ok(());
            }
            Err(e) => {
                if !force {
                    bail!(
                        "目标目录里有本产品的清单，但读不出来：{e}\n\
                         不敢据此清理。请换一个 --dir，或加 --force 就地覆盖。"
                    );
                }
                util::warn(&format!("既有清单无法读取（{e}），按 --force 继续。"));
                return Ok(());
            }
        }
    }

    let mut names: Vec<String> = entries
        .iter()
        .map(|e| e.file_name().to_string_lossy().to_string())
        .collect();
    names.sort();
    let total = names.len();
    let shown = names.iter().take(8).cloned().collect::<Vec<_>>().join("、");
    let suffix = if total > 8 {
        format!("（共 {total} 项）")
    } else {
        String::new()
    };

    if !force {
        bail!(
            "目标目录已有内容，且不是本产品安装的：\n  {}\n  {}{}\n\
             安装器不删除不认识的文​​件。请改用其它 --dir，\
             或加 --force 在本目录就地覆盖（原有文件保持不动）。",
            dir.display(),
            shown,
            suffix
        );
    }
    util::warn(&format!(
        "目标目录已有内容（{shown}{suffix}），按 --force 就地覆盖；原有文件保持不动。"
    ));
    Ok(())
}

fn read_manifest(path: &Path) -> Result<payload::Manifest> {
    let text = std::fs::read_to_string(path)?;
    Ok(serde_json::from_str(&text)?)
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

/// 把构建产物名改成面向用户的主程序名。
fn rename_main(dir: &Path) -> Result<PathBuf> {
    let main = dir.join(util::MAIN_EXE_NAME);
    let built = dir.join(util::BUILT_EXE_NAME);
    if built.is_file() {
        if main.is_file() {
            std::fs::remove_file(&main)?;
        }
        std::fs::rename(&built, &main)
            .with_context(|| format!("主程序改名失败：{}", built.display()))?;
    }
    if !main.is_file() {
        anyhow::bail!(
            "载荷里找不到主程序（既没有 {} 也没有 {}）",
            util::BUILT_EXE_NAME,
            util::MAIN_EXE_NAME
        );
    }
    Ok(main)
}

/// 把自身复制一份到安装目录，充当卸载器。
fn install_uninstaller(dir: &Path, me: &Path) -> Result<PathBuf> {
    let dst = dir.join(util::UNINSTALL_EXE_NAME);
    if me == dst {
        return Ok(dst);
    }
    std::fs::copy(me, &dst)
        .with_context(|| format!("写卸载程序失败：{}", dst.display()))?;
    Ok(dst)
}
