//! 卸载信息：写在 HKCU 下，出现在「设置 → 应用 → 已安装的应用」里。

use std::path::Path;

use anyhow::{Context, Result};
use winreg::enums::HKEY_CURRENT_USER;
use winreg::RegKey;

use crate::util;

/// 写入卸载项。`size_kb` 是安装目录占用的 KB 数。
pub fn write_uninstall_key(install_dir: &Path, version: &str, size_kb: u64) -> Result<()> {
    let uninstall_exe = install_dir.join(util::UNINSTALL_EXE_NAME);
    let main_exe = install_dir.join(util::MAIN_EXE_NAME);

    let hkcu = RegKey::predef(HKEY_CURRENT_USER);
    let (key, _) = hkcu
        .create_subkey(util::UNINSTALL_KEY)
        .context("创建卸载注册表项失败")?;

    let set = |name: &str, value: String| -> Result<()> {
        key.set_value(name, &value)
            .with_context(|| format!("写入注册表值 {name} 失败"))?;
        Ok(())
    };

    set("DisplayName", util::PRODUCT_NAME.to_string())?;
    set("DisplayVersion", version.to_string())?;
    set("InstallLocation", install_dir.to_string_lossy().to_string())?;
    set(
        "UninstallString",
        format!("\"{}\" /uninstall", uninstall_exe.display()),
    )?;
    set(
        "QuietUninstallString",
        format!("\"{}\" /uninstall /S", uninstall_exe.display()),
    )?;
    set("DisplayIcon", main_exe.to_string_lossy().to_string())?;
    key.set_value("EstimatedSize", &(size_kb.min(u32::MAX as u64) as u32))
        .context("写入 EstimatedSize 失败")?;
    key.set_value("NoModify", &1u32).context("写入 NoModify 失败")?;
    key.set_value("NoRepair", &1u32).context("写入 NoRepair 失败")?;
    Ok(())
}

/// 删除卸载项。不存在视为成功。
pub fn remove_uninstall_key() -> Result<()> {
    let hkcu = RegKey::predef(HKEY_CURRENT_USER);
    match hkcu.delete_subkey_all(util::UNINSTALL_KEY) {
        Ok(()) => Ok(()),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(e) => Err(anyhow::Error::from(e).context("删除卸载注册表项失败")),
    }
}

/// 读取已登记的版本号，用于识别「已安装」状态。
pub fn installed_version() -> Option<String> {
    let hkcu = RegKey::predef(HKEY_CURRENT_USER);
    let key = hkcu.open_subkey(util::UNINSTALL_KEY).ok()?;
    key.get_value::<String, _>("DisplayVersion").ok()
}
