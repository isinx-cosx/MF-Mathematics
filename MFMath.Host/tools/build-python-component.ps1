# build-python-component.ps1 — 生成"带 sympy / numpy / scipy"的控制台 CPython 组件包
#
# ⚠️ 本文件必须保存为 **UTF-8 with BOM**：Windows PowerShell 5.1 会把无 BOM 的 .ps1
#    按 ANSI(GBK) 解码，中文注释被拆错字节后连行尾一起吞掉，报一堆"Unexpected token"。
#    编辑后请确认前三个字节是 EF BB BF（用编辑器"以 UTF-8 BOM 保存"，或本仓库的
#    `powershell -Command "$t = Get-Content .\build-python-component.ps1 -Raw -Encoding UTF8;
#     Set-Content .\build-python-component.ps1 $t -Encoding utf8"`）。
#
# 背景：控制台的 CPython 组件用的是官方 **embeddable** 包（python-3.13.15-embed-amd64.zip，
# 约 10.5 MB），它**不含 pip、不含 site-packages**，所以用户在控制台里
# `import sympy` 会失败；而 v1 的控制台是进程内 Python（numpy/sympy/scipy 都带在安装包里），
# 也就是说 v2 的控制台在这一点上是**降级**的。本脚本把三个科学计算包装进同一个组件包。
#
# 为什么不用改宿主代码：ConsoleBridge 的 ExpectedSha256() 规定"与被校验文件同名的
# .sha256 旁文件优先于代码里写死的摘要"（ConsoleBridge.cs:227-243），
# 所以自建包只要放在缓存目录并附上 .sha256 就能被安装流程接受。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File build-python-component.ps1            # 只构建，输出到临时目录
#   powershell -ExecutionPolicy Bypass -File build-python-component.ps1 -Install   # 构建并装进本机组件缓存
#
# 站点侧（让所有用户都能拿到新包）：
#   1. 把生成的 python-3.13.15-embed-amd64.zip 上传到 https://mf-vis-science.cn/download/component/python
#   2. 更新 MFMath.Host/ConsoleBridge.cs 里的两个常量：
#        PythonPayloadSha256   ← 本脚本打印的 sha256（大写十六进制）
#        PythonPayloadBytes    ← 本脚本打印的字节数（界面用它告诉用户"要下多大"）
#   **在站点换包之前不要改这两个常量**：改了但没有新包，新用户会下到旧包、校验失败。
#
# 版本说明：CPython 版本必须与 ConsoleBridge.cs 的 PythonVersion 一致（当前 3.13.15），
# 轮子也必须是 cp313 的（脚本用 pip 的 --python-version 3.13 交叉下载，不需要本机装 3.13）。

param(
    [string]$EmbedZip,                       # 官方 embed 包；默认自动在组件缓存里找
    [string]$WheelsDir,                      # 轮子目录；默认自动下载到临时目录
    [string]$OutDir,                         # 输出目录；默认 %TEMP%\mf-python-component\out
    [string[]]$Packages = @("sympy", "numpy", "scipy"),
    [switch]$Install                         # 构建后放进 %LOCALAPPDATA%\MFMath\components\cache
)

$ErrorActionPreference = "Stop"

$Work        = Join-Path $env:TEMP "mf-python-component"
$ComponentsRoot = Join-Path $env:LOCALAPPDATA "MFMath\components"
$CacheDir    = Join-Path $ComponentsRoot "cache"
$PayloadName = "python-3.13.15-embed-amd64.zip"
$PyVersion   = "3.13"

if (-not $EmbedZip) {
    # 注意 @() 必须包住整条管道：只写 `$cand = @(a,b) | Where-Object …` 时，
    # 命中一个的话 $cand 会被拆成**字符串**，$cand[0] 就取到第一个字符（'C'）。
    $cand = @(
        @(
            (Join-Path $CacheDir $PayloadName),
            (Join-Path $ComponentsRoot $PayloadName)
        ) | Where-Object { Test-Path $_ }
    )
    if ($cand.Count -eq 0) {
        throw "找不到官方 embed 包（$PayloadName）。请先在应用里安装一次 CPython 组件，或用 -EmbedZip 指定路径。"
    }
    $EmbedZip = $cand[0]
}
if (-not $WheelsDir) { $WheelsDir = Join-Path $Work "wheels" }
if (-not $OutDir)    { $OutDir    = Join-Path $Work "out" }

Write-Host "── 参数 ──"
Write-Host "  embed 包 : $EmbedZip"
Write-Host "  轮子目录 : $WheelsDir"
Write-Host "  输出目录 : $OutDir"
Write-Host "  包       : $($Packages -join ', ')"

# ── 1. 轮子 ────────────────────────────────────────────────────────────────
New-Item -ItemType Directory -Path $WheelsDir -Force | Out-Null
$missing = $Packages | Where-Object {
    -not (Get-ChildItem -Path $WheelsDir -Filter "$_*.whl" -ErrorAction SilentlyContinue)
}
if ($missing.Count -gt 0) {
    Write-Host "`n── 下载轮子（交叉下载 cp313/win_amd64，不需要本机装 3.13）──"
    & python -m pip download --only-binary=:all: --python-version $PyVersion `
        --platform win_amd64 --implementation cp --dest $WheelsDir @Packages
    if ($LASTEXITCODE -ne 0) { throw "pip download 失败" }
}

# ── 2. 解压 embed 包 → 解压轮子 → 开放 site-packages ─────────────────────
$Staging = Join-Path $Work "staging"
if (Test-Path $Staging) { Remove-Item $Staging -Recurse -Force }
New-Item -ItemType Directory -Path $Staging -Force | Out-Null
Write-Host "`n── 解压 embed 包 ──"
Expand-Archive -LiteralPath $EmbedZip -DestinationPath $Staging -Force

$SitePackages = Join-Path $Staging "Lib\site-packages"
New-Item -ItemType Directory -Path $SitePackages -Force | Out-Null

Write-Host "── 解压轮子到 Lib\site-packages ──"
# 轮子就是 zip，但 Expand-Archive 只认 .zip 后缀（对 .whl 直接报"不支持的格式"），
# 所以这里用 .NET 的 ZipFile —— 顺便也比 Expand-Archive 快很多。
Add-Type -AssemblyName System.IO.Compression.FileSystem
foreach ($whl in (Get-ChildItem -Path $WheelsDir -Filter "*.whl")) {
    $tmp = Join-Path $Work ("whl-" + $whl.BaseName)
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    [System.IO.Compression.ZipFile]::ExtractToDirectory($whl.FullName, $tmp)
    Copy-Item -Path (Join-Path $tmp '*') -Destination $SitePackages -Recurse -Force
    Remove-Item $tmp -Recurse -Force
    Write-Host ("  {0}" -f $whl.Name)
}

# _pth：官方 embed 默认只有 "python313.zip" 与 "."，且 `import site` 是注释掉的。
# 不放开这一行，site-packages 不会被加进 sys.path（.pth 文件也不处理）。
$PthBase = "python" + $PyVersion.Replace(".", "")
$Pth = Join-Path $Staging "$PthBase._pth"
@("$PthBase.zip", ".", "Lib\site-packages", "import site") |
    Set-Content -LiteralPath $Pth -Encoding ascii
Write-Host "`n── $PthBase._pth ──"
Get-Content $Pth | ForEach-Object { "  $_" }

# ── 3. 冒烟测试：先证明这套 Python 真能 import 三个包，再打包 ──────────────
Write-Host "`n── 冒烟测试（用打包前的这份 Python 跑）──"
$probe = "import {0}; print('ok', {1})" -f `
    ($Packages -join ", "), (($Packages | ForEach-Object { "$_.__version__" }) -join ", ")
& (Join-Path $Staging "python.exe") -c $probe
if ($LASTEXITCODE -ne 0) { throw "冒烟测试失败：组件包里 import 不成功" }

# 清掉刚才跑出来的字节码，别把 __pycache__ 打进包
Get-ChildItem -Path $Staging -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force
Get-ChildItem -Path $Staging -Recurse -File -Include "*.pyc" -ErrorAction SilentlyContinue |
    Remove-Item -Force

# ── 4. 打包（文件名必须与原包一致：FindPayload 按名字找）──────────────────
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$OutZip = Join-Path $OutDir $PayloadName
if (Test-Path $OutZip) { Remove-Item $OutZip -Force }
Write-Host "`n── 打包 ──"
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $Staging, $OutZip, [System.IO.Compression.CompressionLevel]::Optimal, $false)

$hash  = (Get-FileHash -LiteralPath $OutZip -Algorithm SHA256).Hash
$bytes = (Get-Item -LiteralPath $OutZip).Length
$installSize = (Get-ChildItem -Path $Staging -Recurse -File | Measure-Object Length -Sum).Sum

Write-Host ""
Write-Host "── 结果 ──"
Write-Host ("  包名      : {0}" -f $PayloadName)
Write-Host ("  路径      : {0}" -f $OutZip)
Write-Host ("  下载大小  : {0:N1} MB（{1} 字节）" -f ($bytes / 1MB), $bytes)
Write-Host ("  安装后    : {0:N1} MB" -f ($installSize / 1MB))
Write-Host ("  sha256    : {0}" -f $hash)

# ── 5. 可选：装进本机组件缓存 ──────────────────────────────────────────────
if ($Install) {
    New-Item -ItemType Directory -Path $CacheDir -Force | Out-Null
    $target = Join-Path $CacheDir $PayloadName
    $backup = Join-Path $CacheDir ($PayloadName + ".official")
    if ((Test-Path $target) -and -not (Test-Path $backup)) {
        Copy-Item $target $backup -Force
        Write-Host ("`n  已备份原包 → {0}" -f $backup)
    }
    Copy-Item $OutZip $target -Force
    Set-Content -LiteralPath ($target + ".sha256") -Value $hash -Encoding ascii
    Write-Host ("  已装入缓存: {0}" -f $target)
    Write-Host ("  已写旁文件: {0}.sha256" -f $target)
    Write-Host ""
    Write-Host "  下一步：在应用里「设置 → 组件 → CPython」先卸载再安装，即可生效。"
}
