; ═══════════════════════════════════════════════════════════════════════
;  MF-Mathematics 安装脚本 (Inno Setup 6)
;  生成: Multifunctional-Mathematics-v1.0-setup.exe
; ═══════════════════════════════════════════════════════════════════════

#define AppName "MF-Mathematics"
#define AppVersion "1.0"
#define AppPublisher "MF-Vis-Science"
#define AppURL "https://github.com/MF-Mathematics"
#define AppExeName "Multifunctional-Mathematics-v1.0.exe"
#define SourceDir "C:\Users\fsafsafsa\Desktop\Multifunctional-Mathematics\dist\Multifunctional-Mathematics-v1.0"
#define OutputDir "C:\Users\fsafsafsa\Desktop\Multifunctional-Mathematics\dist\installer"

[Setup]
AppId={{B8F4A3D2-7E61-4C5A-9D2B-1F3E8A5C6D7E}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; 输出设置
OutputDir={#OutputDir}
OutputBaseFilename=Multifunctional-Mathematics-v1.0-setup
; 压缩与外观
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; 安装权限（用户可选）
PrivilegesRequiredOverridesAllowed=dialog
; 图标
SetupIconFile=C:\Users\fsafsafsa\Desktop\Multifunctional-Mathematics\assets\icon.ico
UninstallDisplayIcon={app}\_internal\assets\icon.ico
; 卸载信息
UninstallDisplayName={#AppName} {#AppVersion}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; 主程序及所有依赖（_internal 目录）
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; 开始菜单快捷方式
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
; 卸载快捷方式
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
; 桌面快捷方式（可选）
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; 安装完成后可选择立即运行
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
// InitializeSetup: 安装前置检查
function InitializeSetup: Boolean;
begin
  Result := True;
end;

[UninstallDelete]
; 清理可能残留的配置文件（如用户选择保留则不删）
Type: files; Name: "{app}\*.log"
