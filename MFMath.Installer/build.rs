//! 给安装器嵌 Windows 资源：程序图标 + 版本信息。
//!
//! 没有这个 build 脚本时，`mfmath-installer.exe` 不带资源段，编译出来是**通用 exe 图标**，
//! 于是 `--pack` 产出的成品安装包在资源管理器里也没有品牌图标。
//!
//! 资源文件在这里生成而不是写成静态 `app.rc`，有两个原因：
//!   · 版本号从 `CARGO_PKG_VERSION` 取，不会和 `Cargo.toml` 漂移；
//!   · 图标用绝对路径，rc.exe 不受工作目录影响。
//!
//! `VERSIONINFO` 里没有 `#include <windows.h>`：所需常量改用字面值写，
//! 这样 rc.exe 不需要 Windows SDK 的头文件搜索路径。

use std::io::Write;

/// 与 winver.h 中等价的值（省掉 `#include <windows.h>`）。
const VS_FFI_FILEFLAGSMASK: u32 = 0x3f;
const VOS_NT_WINDOWS32: u32 = 0x0004_0004;
const VFT_APP: u32 = 0x1;
const VFT2_UNKNOWN: u32 = 0x0;

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=icons/icon.ico");

    let version = std::env::var("CARGO_PKG_VERSION").unwrap_or_else(|_| "0.0.0".into());
    let mut parts = version.split('.').map(|s| s.parse::<u16>().unwrap_or(0));
    let (major, minor, patch) = (
        parts.next().unwrap_or(0),
        parts.next().unwrap_or(0),
        parts.next().unwrap_or(0),
    );

    let crate_dir = std::path::PathBuf::from(
        std::env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR"),
    );
    // 图标路径必须是**双反斜杠**的 Windows 形式：.rc 里 `\` 是转义符，
    // 单个反斜杠与正斜杠 rc.exe 都不接受（实测：单反斜杠 exit=1、正斜杠 exit=1、
    // 双反斜杠 exit=0）。中文路径本身没问题，不必改成 ASCII。
    let icon = crate_dir
        .join("icons")
        .join("icon.ico")
        .to_string_lossy()
        .replace('\\', "\\\\");

    let out_dir = std::path::PathBuf::from(std::env::var("OUT_DIR").expect("OUT_DIR"));
    let rc_path = out_dir.join("installer.rc");
    let manifest_path = out_dir.join("installer.manifest");

    // 应用程序清单。没有它，Windows 会加载 comctl32 v5，进度条与按钮都是老式外观
    // （进度条会画成一段一段的方块）。清单里同时声明：
    //   · comctl32 v6 —— 新版控件外观；
    //   · asInvoker —— 不请求管理员权限（每用户安装）；
    //   · 系统级 DPI 感知 —— 高 DPI 下由系统整体缩放，固定像素布局不会错位。
    let manifest = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <assemblyIdentity type="win32" name="Multifunctional-Mathematics.Installer" version="1.0.0.0" processorArchitecture="*"/>
  <dependency>
    <dependentAssembly>
      <assemblyIdentity type="win32" name="Microsoft.Windows.Common-Controls" version="6.0.0.0" processorArchitecture="*" publicKeyToken="6595b64144ccf1df" language="*"/>
    </dependentAssembly>
  </dependency>
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level="asInvoker" uiAccess="false"/>
      </requestedPrivileges>
    </security>
  </trustInfo>
  <application xmlns="urn:schemas-microsoft-com:asm.v3">
    <windowsSettings>
      <dpiAware xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings">true</dpiAware>
    </windowsSettings>
  </application>
</assembly>
"#;
    std::fs::write(&manifest_path, manifest).expect("写清单");
    // 清单路径同样要用双反斜杠。
    let manifest_rc = manifest_path.to_string_lossy().replace('\\', "\\\\");

    let rc = format!(
        r#"// 由 build.rs 生成，请勿手工编辑
// 下面的 #pragma 不能删：文件是 UTF-8，而 rc.exe 默认按本地 ANSI 码页读，
// 不声明码页的话中文（例如 FileDescription）会变成乱码导致编译失败。
#pragma code_page(65001)
1 ICON "{icon}"

// 应用程序清单：RT_MANIFEST(=24)，EXE 用 ID 1。
1 24 "{manifest}"

// 资源 ID 必须写字面 1：`VS_VERSION_INFO` 是 windows.h 里的宏（值为 1），
// 本文件刻意不包含头文件，若直接写那个名字会被当成字符串名而不是 ID，
// Windows 按 ID 1 查版本资源就查不到，表现为"版本信息全空"。
1 VERSIONINFO
FILEVERSION     {major},{minor},{patch},0
PRODUCTVERSION  {major},{minor},{patch},0
FILEFLAGSMASK   {mask}L
FILEFLAGS       0x0L
FILEOS          {os}L
FILETYPE        {ftype}L
FILESUBTYPE     {fsubtype}L
BEGIN
    BLOCK "StringFileInfo"
    BEGIN
        BLOCK "080404B0"
        BEGIN
            VALUE "CompanyName",      "Multifunctional-Mathematics"
            VALUE "FileDescription",  "Multifunctional-Mathematics 安装器"
            VALUE "FileVersion",      "{version}"
            VALUE "InternalName",     "mfmath-installer"
            VALUE "OriginalFilename", "mfmath-installer.exe"
            VALUE "ProductName",      "Multifunctional-Mathematics"
            VALUE "ProductVersion",   "{version}"
            VALUE "LegalCopyright",   ""
        END
    END
    BLOCK "VarFileInfo"
    BEGIN
        VALUE "Translation", 0x804, 1200
    END
END
"#,
        icon = icon,
        manifest = manifest_rc,
        major = major,
        minor = minor,
        patch = patch,
        mask = VS_FFI_FILEFLAGSMASK,
        os = VOS_NT_WINDOWS32,
        ftype = VFT_APP,
        fsubtype = VFT2_UNKNOWN,
        version = version,
    );

    let mut f = std::fs::File::create(&rc_path).expect("创建 .rc");
    f.write_all(rc.as_bytes()).expect("写 .rc");
    drop(f);

    // NONE：不给 rc.exe 额外的头文件搜索路径（上面的 .rc 不依赖任何头文件）。
    // 结果必须检查：静默失败会导致产出的 exe 又没有图标，而编译照样"成功"。
    match embed_resource::compile(&rc_path, embed_resource::NONE) {
        embed_resource::CompilationResult::Ok | embed_resource::CompilationResult::NotWindows => {}
        embed_resource::CompilationResult::NotAttempted(why) => {
            panic!("没能编译 Windows 资源（找不到 rc.exe？）：{why}")
        }
        embed_resource::CompilationResult::Failed(why) => {
            panic!("编译 Windows 资源失败：{why}")
        }
    }
}
