//! 创建快捷方式：走 COM 的 `IShellLink` + `IPersistFile`。

use std::path::Path;

use anyhow::{Context, Result};
use windows::core::{Interface, PCWSTR};
use windows::Win32::Foundation::RPC_E_CHANGED_MODE;
use windows::Win32::System::Com::{
    CoCreateInstance, CoInitializeEx, IPersistFile, CLSCTX_INPROC_SERVER, COINIT_APARTMENTTHREADED,
};
use windows::Win32::UI::Shell::{IShellLinkW, ShellLink};

use crate::util;

/// 初始化 COM。重复初始化返回 `RPC_E_CHANGED_MODE` 时不视为错误。
fn init_com() -> Result<()> {
    let hr = unsafe { CoInitializeEx(None, COINIT_APARTMENTTHREADED) };
    if hr.is_ok() || hr == RPC_E_CHANGED_MODE {
        return Ok(());
    }
    Err(anyhow::anyhow!("COM 初始化失败：{hr:?}"))
}

/// 写一个 `.lnk`。
pub fn create(
    lnk: &Path,
    target: &Path,
    workdir: &Path,
    description: &str,
    icon: Option<&Path>,
) -> Result<()> {
    init_com()?;
    if let Some(parent) = lnk.parent() {
        std::fs::create_dir_all(parent)?;
    }

    let target_w = util::wide(&target.to_string_lossy());
    let workdir_w = util::wide(&workdir.to_string_lossy());
    let desc_w = util::wide(description);
    let lnk_w = util::wide(&lnk.to_string_lossy());

    unsafe {
        let link: IShellLinkW = CoCreateInstance(&ShellLink, None, CLSCTX_INPROC_SERVER)
            .context("创建 IShellLink 失败")?;
        link.SetPath(PCWSTR(target_w.as_ptr()))
            .context("设置快捷方式目标失败")?;
        link.SetWorkingDirectory(PCWSTR(workdir_w.as_ptr()))
            .context("设置工作目录失败")?;
        link.SetDescription(PCWSTR(desc_w.as_ptr()))
            .context("设置描述失败")?;
        if let Some(icon) = icon {
            let icon_w = util::wide(&icon.to_string_lossy());
            // 索引 0：取图标文件的第一帧。
            link.SetIconLocation(PCWSTR(icon_w.as_ptr()), 0)
                .context("设置图标失败")?;
        }
        let persist: IPersistFile = link.cast().context("取 IPersistFile 失败")?;
        persist
            .Save(PCWSTR(lnk_w.as_ptr()), true.into())
            .with_context(|| format!("写入快捷方式失败：{}", lnk.display()))?;
    }
    Ok(())
}

/// 删除快捷方式。不存在视为成功。
pub fn remove(lnk: &Path) -> Result<()> {
    if lnk.is_file() {
        std::fs::remove_file(lnk)
            .with_context(|| format!("删除快捷方式失败：{}", lnk.display()))?;
    }
    Ok(())
}

/// 开始菜单里的快捷方式路径。
pub fn start_menu_lnk() -> std::path::PathBuf {
    util::start_menu_dir().join(format!("{}.lnk", util::PRODUCT_NAME))
}

/// 桌面上的快捷方式路径。
pub fn desktop_lnk() -> std::path::PathBuf {
    util::desktop_dir().join(format!("{}.lnk", util::PRODUCT_NAME))
}
