; ═══════════════════════════════════════════════════════════════════════
;  MF-Mathematics 安装脚本 (Inno Setup 6)
;  自定义 MF-Mathematics Light 主题界面 + 简体中文
;  生成: Multifunctional-Mathematics-v1.0-setup.exe
; ═══════════════════════════════════════════════════════════════════════

#define AppName "MF-Mathematics"
#define AppVersion "1.0"
#define AppPublisher "MF-Vis-Science"
#define AppURL "https://github.com/MF-Mathematics"
#define AppExeName "Multifunctional-Mathematics-v1.0.exe"
#define SourceDir "C:\Users\fsafsafsa\Desktop\Multifunctional-Mathematics\dist\Multifunctional-Mathematics-v1.0"
#define OutputDir "C:\Users\fsafsafsa\Desktop\Multifunctional-Mathematics\dist\installer"
#define BannerDir "C:\Users\fsafsafsa\Desktop\Multifunctional-Mathematics\assets\installer"

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
; 输出
OutputDir={#OutputDir}
OutputBaseFilename=Multifunctional-Mathematics-v1.0-setup
; 压缩
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; 安装权限
PrivilegesRequiredOverridesAllowed=dialog
; 图标
SetupIconFile=C:\Users\fsafsafsa\Desktop\Multifunctional-Mathematics\assets\icon.ico
UninstallDisplayIcon={app}\_internal\assets\icon.ico
; 自定义向导图片
WizardImageFile={#BannerDir}\WizardImage.bmp
WizardSmallImageFile={#BannerDir}\WizardSmallImage.bmp
; 卸载信息
UninstallDisplayName={#AppName} {#AppVersion}

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式(&D)"; GroupDescription: "其他快捷方式:"

[Files]
; 主程序及所有依赖
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; \
  Comment: "多功能数学计算与可视化"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; \
  Tasks: desktopicon; Comment: "多功能数学计算与可视化"

[Run]
Filename: "{app}\{#AppExeName}"; \
  Description: "立即启动 {#AppName}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\*.log"

[Code]
{ ═══════════════════════════════════════════════════════════════ }
{  MF-Mathematics Light 主题 — WizardForm 定制                  }
{  配色: #f8fafc 背景 / #3b82f6 强调 / #e2e8f0 边框           }
{ ═══════════════════════════════════════════════════════════════ }

const
  COLOR_BG       = $fcfaf8;  { #f8fafc (BGR) }
  COLOR_SURFACE  = $ffffff;   { #ffffff }
  COLOR_BORDER   = $f0e8e2;   { #e2e8f0 }
  COLOR_PRIMARY  = $f6823b;   { #3b82f6 }
  COLOR_PRIMARY_DARK = $eb6525; { #2563eb }
  COLOR_TEXT     = $2a170f;   { #0f172a }
  COLOR_TEXT_MUTED = $695647; { #475569 }

procedure InitializeWizard;
var
  i: Integer;
begin
  WizardForm.Color := COLOR_BG;
  WizardForm.Font.Color := COLOR_TEXT;
  WizardForm.Font.Name := 'Segoe UI';
  WizardForm.Font.Size := 9;

  { ── 主面板 (欢迎/完成页) ── }
  WizardForm.WelcomePage.Color := COLOR_BG;
  WizardForm.FinishedPage.Color := COLOR_BG;

  { ── 内页面板 ── }
  WizardForm.InnerPage.Color := COLOR_BG;

  { ── 所有子控件样式 ── }
  for i := 0 to WizardForm.ControlCount - 1 do
  begin
    { 按钮 (Bevel 或 NewButton) }
    if (WizardForm.Controls[i] is TNewButton) then
    begin
      with TNewButton(WizardForm.Controls[i]) do
      begin
        Font.Name := 'Segoe UI';
        Font.Size := 9;
        Font.Color := COLOR_TEXT;
      end;
    end
    else if (WizardForm.Controls[i] is TNewStaticText) then
    begin
      with TNewStaticText(WizardForm.Controls[i]) do
      begin
        Font.Name := 'Segoe UI';
        Font.Size := 9;
        { 欢迎/完成页标题用主文字色 }
        if (Parent = WizardForm.WelcomePage) or
           (Parent = WizardForm.FinishedPage) then
          Font.Color := COLOR_TEXT;
      end;
    end;
  end;

  { ── 欢迎页标题 ── }
  WizardForm.WelcomeLabel1.Font.Name := 'Segoe UI';
  WizardForm.WelcomeLabel1.Font.Size := 13;
  WizardForm.WelcomeLabel1.Font.Style := [fsBold];
  WizardForm.WelcomeLabel1.Font.Color := COLOR_TEXT;
  WizardForm.WelcomeLabel1.AutoSize := True;

  WizardForm.WelcomeLabel2.Font.Name := 'Segoe UI';
  WizardForm.WelcomeLabel2.Font.Size := 9;
  WizardForm.WelcomeLabel2.Font.Color := COLOR_TEXT_MUTED;

  { ── 完成页标题 ── }
  WizardForm.FinishedLabel.Font.Name := 'Segoe UI';
  WizardForm.FinishedLabel.Font.Size := 13;
  WizardForm.FinishedLabel.Font.Style := [fsBold];
  WizardForm.FinishedLabel.Font.Color := COLOR_TEXT;
  WizardForm.FinishedLabel.AutoSize := True;

  WizardForm.FinishedHeadingLabel.Font.Name := 'Segoe UI';
  WizardForm.FinishedHeadingLabel.Font.Size := 9;
  WizardForm.FinishedHeadingLabel.Font.Color := COLOR_TEXT_MUTED;

  { ── 页标题/描述 ── }
  WizardForm.PageNameLabel.Font.Name := 'Segoe UI';
  WizardForm.PageNameLabel.Font.Size := 9;
  WizardForm.PageNameLabel.Font.Color := COLOR_TEXT_MUTED;

  WizardForm.PageDescriptionLabel.Font.Name := 'Segoe UI';
  WizardForm.PageDescriptionLabel.Font.Size := 9;
  WizardForm.PageDescriptionLabel.Font.Color := COLOR_TEXT_MUTED;

  { ── 目录选择 / 组选择页面 ── }
  WizardForm.DirEdit.Font.Name := 'Segoe UI';
  WizardForm.DirEdit.Font.Size := 9;
  WizardForm.DirBrowseButton.Font.Name := 'Segoe UI';
  WizardForm.DirBrowseButton.Font.Size := 9;

  WizardForm.GroupEdit.Font.Name := 'Segoe UI';
  WizardForm.GroupEdit.Font.Size := 9;
  WizardForm.GroupBrowseButton.Font.Name := 'Segoe UI';
  WizardForm.GroupBrowseButton.Font.Size := 9;

  WizardForm.ReadyMemo.Font.Name := 'Segoe UI';
  WizardForm.ReadyMemo.Font.Size := 9;

  { ── 许可页 ── }
  WizardForm.LicenseMemo.Font.Name := 'Segoe UI';
  WizardForm.LicenseMemo.Font.Size := 9;
end;

{ ── 按钮色彩 — 每页切换时重新应用 ── }
procedure CurPageChanged(CurPageID: Integer);
begin
  WizardForm.BackButton.Font.Name := 'Segoe UI';
  WizardForm.BackButton.Font.Size := 9;

  WizardForm.NextButton.Font.Name := 'Segoe UI';
  WizardForm.NextButton.Font.Size := 9;
  WizardForm.NextButton.Font.Style := [fsBold];
  WizardForm.NextButton.Font.Color := COLOR_SURFACE;

  WizardForm.CancelButton.Font.Name := 'Segoe UI';
  WizardForm.CancelButton.Font.Size := 9;

  { 安装进行中 }
end;

{ ── 安装更新文本颜色 ── }
procedure CurInstallProgressChanged(CurProgress, MaxProgress: Integer);
begin
  { 保持进度条风格 }
end;
