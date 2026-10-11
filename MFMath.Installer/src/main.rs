//! MF-Mathematics 安装器。
//!
//! 三种模式：
//!   · 安装（默认）—— 释放载荷、建快捷方式、写卸载信息；
//!   · 卸载（`/uninstall`）—— 反向操作，可选删除用户数据；
//!   · 打包（`--pack`）—— 把载荷目录封成单文件安装器，供发布使用。

mod install;
mod pack;
mod payload;
mod registry;
mod shortcut;
mod uninstall;
mod util;

use std::path::PathBuf;

use anyhow::{bail, Context, Result};

const HELP: &str = "\
Multifunctional-Mathematics 安装器

用法：
  mfmath-installer [选项]                 安装
  mfmath-installer /uninstall [选项]      卸载
  mfmath-installer --pack <载荷目录> <输出 exe> [--version <版本>]
                                          打包（发布用）

安装选项：
  /S                  静默安装，不输出
  /D=<路径>           指定安装目录（必须放在最后，路径不加引号）
  --dir <路径>        同上，写法更宽松
  /force              目标目录已有本产品以外的文件时，仍就地覆盖
                      （只覆盖同名文件；不加此项时安装器会拒绝）

卸载选项：
  /S                  静默卸载
  --purge             同时删除用户数据（%LOCALAPPDATA%\\MFMath）
  --dir <路径>        指定要卸载的目录

默认安装目录：%LOCALAPPDATA%\\Programs\\MF-Mathematics
";

struct Args {
    silent: bool,
    dir: Option<PathBuf>,
    uninstall: bool,
    purge: bool,
    force: bool,
    from_temp: bool,
    pack: Option<(PathBuf, PathBuf)>,
    version: Option<String>,
    help: bool,
}

fn parse() -> Result<Args> {
    let mut a = Args {
        silent: false,
        dir: None,
        uninstall: false,
        purge: false,
        force: false,
        from_temp: false,
        pack: None,
        version: None,
        help: false,
    };
    let argv: Vec<String> = std::env::args().skip(1).collect();
    let mut i = 0usize;
    while i < argv.len() {
        let arg = argv[i].clone();
        let lower = arg.to_ascii_lowercase();
        match lower.as_str() {
            "/s" | "--silent" | "-s" => a.silent = true,
            "/uninstall" | "--uninstall" => a.uninstall = true,
            "/purge" | "--purge" => a.purge = true,
            "/force" | "--force" => a.force = true,
            "--from-temp" => a.from_temp = true,
            "/?" | "-h" | "--help" => a.help = true,
            "--pack" => {
                let dir = argv
                    .get(i + 1)
                    .context("--pack 需要一个载荷目录参数")?
                    .clone();
                let out = argv
                    .get(i + 2)
                    .context("--pack 需要一个输出路径参数")?
                    .clone();
                a.pack = Some((PathBuf::from(dir), PathBuf::from(out)));
                i += 2;
            }
            "--version" => {
                a.version = Some(
                    argv.get(i + 1)
                        .context("--version 需要一个版本号参数")?
                        .clone(),
                );
                i += 1;
            }
            "--dir" => {
                a.dir = Some(PathBuf::from(
                    argv.get(i + 1).context("--dir 需要一个路径参数")?,
                ));
                i += 1;
            }
            other => {
                // NSIS 风格：/D=<路径>，通常是最后一个参数。
                if let Some(rest) = other.strip_prefix("/d=") {
                    a.dir = Some(PathBuf::from(rest));
                } else if other.starts_with('/') || other.starts_with('-') {
                    bail!("无法识别的参数：{arg}（用 --help 看用法）");
                }
            }
        }
        i += 1;
    }
    Ok(a)
}

fn main() {
    let args = match parse() {
        Ok(a) => a,
        Err(e) => {
            eprintln!("{e:#}");
            std::process::exit(2);
        }
    };
    if args.help {
        print!("{HELP}");
        return;
    }
    if args.silent {
        util::set_silent(true);
    }

    if let Err(e) = run(&args) {
        util::warn(&format!("失败：{e:#}"));
        // 双击运行时没有控制台，用户看不到 stderr，用消息框把原因显示出来。
        // 从命令行运行时控制台里已有输出，不再弹框（弹框会挂住脚本）。
        if !args.silent && !has_console() {
            show_error(&format!("{e:#}"));
        }
        std::process::exit(1);
    }
}

/// 当前进程是否连着控制台窗口。
fn has_console() -> bool {
    !unsafe { windows::Win32::System::Console::GetConsoleWindow() }
        .0
        .is_null()
}

fn run(args: &Args) -> Result<()> {
    if let Some((dir, out)) = &args.pack {
        let version = args.version.clone().unwrap_or_else(|| "2.0.0".to_string());
        return pack::run(dir, out, &version);
    }

    if args.uninstall {
        let dir = match &args.dir {
            Some(d) => d.clone(),
            None => util::current_exe()?
                .parent()
                .map(PathBuf::from)
                .context("无法确定安装目录")?,
        };
        if !args.from_temp {
            // 运行中的 exe 删不掉自己所在的目录，优先转到临时副本里执行；
            // 临时目录不可写时退回原地卸载。
            if uninstall::respawn_from_temp(&dir, args.purge, args.silent)? {
                return Ok(());
            }
        }
        return uninstall::run(&uninstall::Options {
            dir: Some(dir),
            purge: args.purge,
        });
    }

    install::run(&install::Options {
        dir: args.dir.clone().unwrap_or_else(util::default_install_dir),
        force: args.force,
    })
}

fn show_error(msg: &str) {
    use windows::core::PCWSTR;
    use windows::Win32::UI::WindowsAndMessaging::{MessageBoxW, MB_ICONERROR, MB_OK};
    let text = util::wide(msg);
    let caption = util::wide("Multifunctional-Mathematics 安装器");
    unsafe {
        MessageBoxW(
            None,
            PCWSTR(text.as_ptr()),
            PCWSTR(caption.as_ptr()),
            MB_OK | MB_ICONERROR,
        );
    }
}
