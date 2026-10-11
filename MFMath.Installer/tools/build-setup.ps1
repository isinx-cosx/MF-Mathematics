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
    [string]$Target = 'release',
    # 签名（可选）。不传证书参数时不签名。
    [string]$CertThumbprint = '',
    [string]$PfxPath = '',
    [string]$PfxPassword = '',
    [string]$TimestampUrl = 'http://timestamp.digicert.com'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$hostDir = Join-Path $root 'MFMath.Host.Rust'
$relDir = Join-Path $hostDir "target\$Target"
$stage = Join-Path $root '.tmp-build\payload-src'
$outDir = Join-Path $root 'MFMath.Installer\target\release'
$setup = Join-Path $outDir "Multifunctional-Mathematics_${Version}_x64-setup.exe"
$installer = Join-Path $root 'MFMath.Installer\target\release\mfmath-installer.exe'

$doSign = ($CertThumbprint -ne '') -or ($PfxPath -ne '')

# 找 signtool（Windows SDK 里，不在 PATH 上）
function Get-SignTool {
    $onPath = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    $roots = @(
        "${env:ProgramFiles(x86)}\Windows Kits\10\bin",
        "$env:ProgramFiles\Windows Kits\10\bin"
    )
    foreach ($r in $roots) {
        if (-not (Test-Path $r)) { continue }
        $hit = Get-ChildItem $r -Filter 'signtool.exe' -Recurse -ErrorAction SilentlyContinue |
               Where-Object { $_.FullName -match '\\x64\\' } |
               Sort-Object FullName -Descending | Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}

# 给一个文件做 Authenticode 签名（SHA-256 + 时间戳）
function Invoke-Sign([string]$File) {
    if ($CertThumbprint -ne '') {
        & $script:signTool sign /sha1 $CertThumbprint /fd sha256 /tr $TimestampUrl /td sha256 $File
    } else {
        & $script:signTool sign /f $PfxPath /p $PfxPassword /fd sha256 /tr $TimestampUrl /td sha256 $File
    }
    if ($LASTEXITCODE -ne 0) { throw "签名失败（退出码 $LASTEXITCODE）：$File" }
    Write-Host "已签名：$(Split-Path $File -Leaf)"
}

$signTool = $null
if ($doSign) {
    $signTool = Get-SignTool
    if (-not $signTool) {
        throw "找不到 signtool.exe。装一个 Windows SDK（含 Signing Tools），或把它加到 PATH。"
    }
    Write-Host "signtool：$signTool"
}

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

# WebView2 引导程序（约 1.8 MB）：Windows 11 自带 Runtime，Windows 10 可能没有，
# 缺失时由安装器静默运行它。缓存到 .tmp-build，避免每次重新下载。
$cache = Join-Path $root '.tmp-build\webview2'
$bootstrapper = Join-Path $cache 'MicrosoftEdgeWebview2Setup.exe'
$bootstrapperUrl = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703'
if (-not (Test-Path $bootstrapper)) {
    New-Item -ItemType Directory -Force -Path $cache | Out-Null
    Write-Host "下载 WebView2 引导程序…"
    try {
        Invoke-WebRequest -Uri $bootstrapperUrl -OutFile $bootstrapper -TimeoutSec 120
    } catch {
        Write-Warning "引导程序下载失败：$_`n  本次产出的安装包不含它；Win10 无 Runtime 的机器需手动安装 WebView2。"
    }
}
if (Test-Path $bootstrapper) {
    Copy-Item $bootstrapper $stage
    Write-Host ("引导程序：{0:N2} MB" -f ((Get-Item $bootstrapper).Length / 1MB))
} else {
    Write-Warning "安装包将不含 WebView2 引导程序。"
}

$files = Get-ChildItem $stage -Recurse -File
$sizeMb = ($files | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("载荷：{0} 个文件，{1:N2} MB" -f $files.Count, $sizeMb)

# 签名要装在包里的主程序：签名后主程序名由安装器改，但文件内容不变，
# 所以在这里签一次，装完就是已签名的。
# 注意 WebView2 引导程序是微软的二进制，不要签（签了反而破坏它的签名）。
if ($doSign) {
    Invoke-Sign (Join-Path $stage 'mfmath-host-rust.exe')
}

# ── 打包 ────────────────────────────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
if (Test-Path $setup) { Remove-Item $setup -Force }

& $installer --pack $stage $setup --version $Version
if ($LASTEXITCODE -ne 0) { throw "打包失败，退出码 $LASTEXITCODE" }

# 给成品安装包签名。安装器的载荷标记在文件中部，签名追加的证书表落在它之后，
# 安装器用"从后往前扫描标记"的方式定位载荷，因此签名后仍可正常安装。
if ($doSign) {
    Invoke-Sign $setup
}

$setupMb = (Get-Item $setup).Length / 1MB
Write-Host ("`n安装包：{0}" -f $setup)
Write-Host ("体积：{0:N2} MB（压缩率 {1:P0}）" -f $setupMb, (1 - $setupMb / $sizeMb))
if ($doSign) {
    & $signTool verify /pa /v $setup | Select-String 'Successfully verified|Issued to|SHA1 hash'
}
