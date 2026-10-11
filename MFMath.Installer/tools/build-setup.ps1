# 收集载荷并产出单文件安装包。
#
#   .\MFMath.Installer\tools\build-setup.ps1
#
# 前置：宿主已构建（MFMath.Host.Rust\target\release\ 下有 mfmath-host-rust.exe 与 wwwroot）。
# 产出：MFMath.Installer\target\release\Multifunctional-Mathematics_<版本>_x64-setup.exe
#
# 说明：本脚本只做"收集 + 打包"，不触发 cargo/cmake 构建。要出完整安装包，
# 先按 README 的三步构建把宿主编出来，再跑本脚本。

[CmdletBinding()]
param(
    [string]$Version = '2.0.0',
    [string]$Target = 'release'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$hostDir = Join-Path $root 'MFMath.Host.Rust'
$relDir = Join-Path $hostDir "target\$Target"
$stage = Join-Path $root '.tmp-build\payload-src'
$outDir = Join-Path $root 'MFMath.Installer\target\release'
$setup = Join-Path $outDir "Multifunctional-Mathematics_${Version}_x64-setup.exe"
$installer = Join-Path $root 'MFMath.Installer\target\release\mfmath-installer.exe'

Write-Host "仓库根：$root"

# ── 前置检查 ────────────────────────────────────────────────────────────────
if (-not (Test-Path $installer)) {
    throw "安装器未构建：$installer`n先跑：cd MFMath.Host.Rust; cargo build --release --offline --manifest-path ..\MFMath.Installer\Cargo.toml"
}
$mainExe = Join-Path $relDir 'mfmath-host-rust.exe'
if (-not (Test-Path $mainExe)) {
    throw "宿主未构建：$mainExe`n先按 README 的三步构建编译宿主。"
}
$wwwroot = Join-Path $relDir 'wwwroot'
if (-not (Test-Path $wwwroot)) {
    throw "前端产物未同步：$wwwroot`n先跑：node MFMath.Host.Rust/tools/sync-wwwroot.mjs"
}

# ── 收集载荷 ────────────────────────────────────────────────────────────────
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

Copy-Item $mainExe $stage
$dlls = @(
    'mf_mathematics.dll', 'symengine-0.14.dll', 'flint-24.dll',
    'gmp-10.dll', 'mpfr-6.dll', 'pthreadVC3.dll'
)
foreach ($d in $dlls) {
    $p = Join-Path $relDir $d
    if (-not (Test-Path $p)) { throw "缺少引擎依赖：$p" }
    Copy-Item $p $stage
}
Copy-Item $wwwroot (Join-Path $stage 'wwwroot') -Recurse

# 控制台门面：优先取 Rust 宿主目录下的 console/（build.rs 会把它们同步到产物目录）
$facadeSrc = Join-Path $hostDir 'console'
$facadeFrom = if (Test-Path (Join-Path $relDir 'python\mfmath.py')) { $relDir } else { $facadeSrc }
foreach ($sub in 'python', 'cpp') {
    $from = Join-Path $facadeFrom $sub
    if (-not (Test-Path $from)) { throw "缺少控制台门面：$from" }
    Copy-Item $from (Join-Path $stage $sub) -Recurse
}

$icon = Join-Path $hostDir 'icons\icon.ico'
if (Test-Path $icon) { Copy-Item $icon $stage }

$files = Get-ChildItem $stage -Recurse -File
$sizeMb = ($files | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("载荷：{0} 个文件，{1:N2} MB" -f $files.Count, $sizeMb)

# ── 打包 ────────────────────────────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
if (Test-Path $setup) { Remove-Item $setup -Force }

& $installer --pack $stage $setup --version $Version
if ($LASTEXITCODE -ne 0) { throw "打包失败，退出码 $LASTEXITCODE" }

$setupMb = (Get-Item $setup).Length / 1MB
Write-Host ("`n安装包：{0}" -f $setup)
Write-Host ("体积：{0:N2} MB（压缩率 {1:P0}）" -f $setupMb, (1 - $setupMb / $sizeMb))
