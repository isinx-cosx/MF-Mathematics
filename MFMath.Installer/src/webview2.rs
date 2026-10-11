//! WebView2 Runtime 的检测与安装。
//!
//! 宿主用 WebView2 承载界面。Windows 11 自带 Runtime；Windows 10 可能没有，
//! 缺失时程序起不来。安装器在释放载荷前先探测一次，缺失就运行内嵌的
//! Evergreen 引导程序（静默）。
//!
//! **探测必须读 32 位注册表视图**：Runtime 的安装信息登记在
//! `HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{产品码}`，
//! 而安装器是 64 位进程，直接读 `SOFTWARE\Microsoft\...` 会走 64 位视图、读不到。
//! 本机实测：只有 `WOW6432Node` 那处存在（`pv = 149.0.4022.80`）。

use std::path::Path;

use anyhow::{Context, Result};
use winreg::enums::{HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE};
use winreg::RegKey;

use crate::util;

/// Evergreen Runtime 的产品码。
const CLIENT_GUID: &str = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}";
/// 载荷里引导程序的文件名。
pub const BOOTSTRAPPER_ENTRY: &str = "MicrosoftEdgeWebview2Setup.exe";
/// 引导程序下载地址（微软官方短链）。
pub const BOOTSTRAPPER_URL: &str = "https://go.microsoft.com/fwlink/p/?LinkId=2124703";

/// 探测已安装的 Runtime 版本。未安装返回 `None`。
pub fn installed_version() -> Option<String> {
    let subkeys = [
        // 32 位视图。本机 Runtime 就登记在这里，必须显式写 WOW6432Node。
        (HKEY_LOCAL_MACHINE, format!(r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{CLIENT_GUID}")),
        // 64 位视图（部分安装方式会登记在这里）。
        (HKEY_LOCAL_MACHINE, format!(r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{CLIENT_GUID}")),
        // 每用户安装。
        (HKEY_CURRENT_USER, format!(r"Software\Microsoft\EdgeUpdate\Clients\{CLIENT_GUID}")),
    ];
    for (hive, path) in subkeys {
        let root = RegKey::predef(hive);
        if let Ok(key) = root.open_subkey(&path) {
            if let Ok(pv) = key.get_value::<String, _>("pv") {
                let pv = pv.trim().to_string();
                // 空串与 0.0.0.0 表示"登记了但没装"。
                if !pv.is_empty() && pv != "0.0.0.0" {
                    return Some(pv);
                }
            }
        }
    }
    None
}

/// 确保 Runtime 可用。缺失时运行引导程序；失败只报告，不阻断安装。
///
/// `bootstrapper` 是引导程序在本机的路径（安装器会先从载荷里抽到临时目录）。
pub fn ensure(bootstrapper: Option<&Path>) -> Result<()> {
    // 诊断钩子：强制走"缺失"分支，用于验证引导程序那条路。
    let assume_missing = std::env::var_os("MF_WEBVIEW2_ASSUME_MISSING").is_some();

    if !assume_missing {
        if let Some(v) = installed_version() {
            util::say(&format!("WebView2 Runtime 已安装（版本 {v}）。"));
            return Ok(());
        }
    } else {
        util::warn("按诊断开关 MF_WEBVIEW2_ASSUME_MISSING 强制走缺失分支。");
    }

    util::say("未检测到 WebView2 Runtime，尝试运行内嵌引导程序…");
    let Some(bootstrapper) = bootstrapper else {
        report_manual(bootstrapper);
        return Ok(());
    };
    if !bootstrapper.is_file() {
        util::warn(&format!("引导程序不在：{}", bootstrapper.display()));
        report_manual(None);
        return Ok(());
    }

    let status = std::process::Command::new(bootstrapper)
        .args(["/silent", "/install"])
        .status();

    match status {
        Ok(s) if s.success() => {
            match installed_version() {
                Some(v) => util::say(&format!("WebView2 Runtime 安装完成（版本 {v}）。")),
                // 引导程序返回成功但注册表还没刷新时不必惊慌：宿主启动时还会再探一次。
                None => util::warn(
                    "引导程序返回成功，但暂时读不到版本号；若程序起不来请手动安装 WebView2。",
                ),
            }
        }
        Ok(s) => {
            util::warn(&format!("引导程序退出码 {s}，WebView2 可能未安装成功。"));
            report_manual(Some(bootstrapper));
        }
        Err(e) => {
            util::warn(&format!("运行引导程序失败：{e}"));
            report_manual(Some(bootstrapper));
        }
    }
    Ok(())
}

/// 引导程序不可用或失败时的兜底说明。**不阻断安装**：安装本身是成功的。
fn report_manual(_bootstrapper: Option<&Path>) {
    util::warn(&format!(
        "  WebView2 缺失时程序无法启动。请手动安装微软的 Evergreen Runtime：\n  {BOOTSTRAPPER_URL}\n  安装过程会继续。"
    ));
}

/// 把引导程序从载荷抽到临时目录，返回其路径。载荷里没有时返回 `None`。
pub fn stage_bootstrapper(payload: &crate::payload::Payload) -> Result<Option<std::path::PathBuf>> {
    // 诊断钩子：允许指定外部引导程序，便于验证。
    if let Some(p) = std::env::var_os("MF_WEBVIEW2_BOOTSTRAPPER") {
        return Ok(Some(std::path::PathBuf::from(p)));
    }
    let dest = std::env::temp_dir().join(format!("mfmath-webview2-{}.exe", std::process::id()));
    match payload
        .extract_entry(BOOTSTRAPPER_ENTRY, &dest)
        .with_context(|| format!("从载荷抽取 {BOOTSTRAPPER_ENTRY} 失败"))?
    {
        true => Ok(Some(dest)),
        false => Ok(None),
    }
}
