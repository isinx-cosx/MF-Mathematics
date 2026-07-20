; ═══════════════════════════════════════════════════════════════════════
;  MF-Mathematics 安装脚本 (Inno Setup 6)
;  深色 Banner + Light 主题 WizardForm + 简体中文
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
#define IconDir "C:\Users\fsafsafsa\Desktop\Multifunctional-Mathematics\assets"

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
OutputDir={#OutputDir}
OutputBaseFilename=Multifunctional-Mathematics-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog
SetupIconFile={#IconDir}\icon.ico
UninstallDisplayIcon={app}\_internal\assets\icon.ico
WizardImageFile={#BannerDir}\WizardImage.bmp
WizardSmallImageFile={#BannerDir}\WizardSmallImage.bmp
UninstallDisplayName={#AppName} {#AppVersion}

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式(&D)"; GroupDescription: "其他快捷方式:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Comment: "多功能数学计算与可视化"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon; Comment: "多功能数学计算与可视化"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "立即启动 {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\*.log"

[Code]
{ ═══════════════════════════════════════════════════════ }
{  MF-Mathematics 主题 — WizardForm 定制               }
{  Light 界面 (匹配 QSS light.qss 色值)                 }
{ ═══════════════════════════════════════════════════════ }

const
  CL_BG      = $fcfaf8;
  CL_SURFACE = $ffffff;
  CL_BORDER  = $f0e8e2;
  CL_TEXT    = $2a170f;
  CL_MUTED   = $695647;
  CL_BLUE    = $f6823b;

procedure InitializeWizard;
var
  i: Integer;
begin
  WizardForm.Color := CL_BG;
  WizardForm.Font.Name := 'Segoe UI';
  WizardForm.Font.Size := 9;
  WizardForm.Font.Color := CL_TEXT;

  WizardForm.InnerPage.Color := CL_BG;
  WizardForm.WelcomePage.Color := CL_BG;
  WizardForm.FinishedPage.Color := CL_BG;

  for i := 0 to WizardForm.ControlCount - 1 do
  begin
    if (WizardForm.Controls[i] is TNewButton) then
      with TNewButton(WizardForm.Controls[i]) do
      begin Font.Name := 'Segoe UI'; Font.Size := 9; end
    else if (WizardForm.Controls[i] is TNewStaticText) then
      with TNewStaticText(WizardForm.Controls[i]) do
      begin Font.Name := 'Segoe UI'; Font.Size := 9; end;
  end;

  with WizardForm.WelcomeLabel1 do
  begin Font.Name := 'Segoe UI'; Font.Size := 13;
    Font.Style := [fsBold]; Font.Color := CL_TEXT; AutoSize := True; end;
  WizardForm.WelcomeLabel2.Font.Name := 'Segoe UI';
  WizardForm.WelcomeLabel2.Font.Size := 9;
  WizardForm.WelcomeLabel2.Font.Color := CL_MUTED;

  with WizardForm.FinishedLabel do
  begin Font.Name := 'Segoe UI'; Font.Size := 13;
    Font.Style := [fsBold]; Font.Color := CL_TEXT; AutoSize := True; end;
  WizardForm.FinishedHeadingLabel.Font.Name := 'Segoe UI';
  WizardForm.FinishedHeadingLabel.Font.Size := 9;
  WizardForm.FinishedHeadingLabel.Font.Color := CL_MUTED;

  WizardForm.PageNameLabel.Font.Name := 'Segoe UI';
  WizardForm.PageNameLabel.Font.Size := 9;
  WizardForm.PageNameLabel.Font.Color := CL_MUTED;
  WizardForm.PageDescriptionLabel.Font.Name := 'Segoe UI';
  WizardForm.PageDescriptionLabel.Font.Size := 9;
  WizardForm.PageDescriptionLabel.Font.Color := CL_MUTED;

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
  WizardForm.LicenseMemo.Font.Name := 'Segoe UI';
  WizardForm.LicenseMemo.Font.Size := 9;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  WizardForm.BackButton.Font.Name := 'Segoe UI';
  WizardForm.BackButton.Font.Size := 9;
  WizardForm.CancelButton.Font.Name := 'Segoe UI';
  WizardForm.CancelButton.Font.Size := 9;
  WizardForm.NextButton.Font.Name := 'Segoe UI';
  WizardForm.NextButton.Font.Size := 9;
  WizardForm.NextButton.Font.Style := [fsBold];
end;
