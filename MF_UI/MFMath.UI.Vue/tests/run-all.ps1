# One-click regression: launch host with CDP port, run all verification scripts, summarize.
# Usage (Windows PowerShell 5.1 or PowerShell 7):
#   powershell -ExecutionPolicy Bypass -File run-all.ps1
# Prereq: Vue built (npm run build) and host built (dotnet build -c Release)
#
# unit-* 是纯 Node 单元测试（假桥，不需要宿主窗口）；cdp-* 需要上面那个宿主进程。
# Each test script prints a machine-readable line: RESULT|<name>|<pass>|<fail>
# (ASCII only, so the summary parses regardless of console encoding.)

$ErrorActionPreference = "Continue"
# v2.0：宿主就在同一棵树里的 ..\..\MFMath.Host（旧版这里指向 cppcshap 的宿主，已改）
$hostExe = (Resolve-Path (Join-Path $PSScriptRoot "..\..\MFMath.Host\bin\Release\net10.0-windows\MFMath.exe") -ErrorAction SilentlyContinue)
if (-not $hostExe) { $hostExe = "C:\Users\fsafsafsa\Desktop\MVS知识库\Multifunctional系列\Multifunctional-Mathematics-v2.0\MFMath.Host\bin\Release\net10.0-windows\MFMath.exe" }
$tests = @(
  "unit-result-model",
  "cdp-bridge-verify", "cdp-window-shell", "cdp-appearance", "cdp-input-notation", "cdp-font-load", "cdp-plot-verify", "cdp-plot-p3", "cdp-plot-p4",
  "cdp-plot-region", "cdp-plot-p5", "cdp-plot-final", "cdp-plot-asymptote",
  "cdp-plot-extrema", "cdp-plot-extrema-domain", "cdp-plot-3d", "cdp-plot-vector", "cdp-plot-fractal",
  "cdp-complex-modes", "cdp-plot-geometry", "cdp-plot-truth", "cdp-calc-workspace", "cdp-basic-calc",
  "cdp-diff-at-param", "cdp-fractal-orient", "cdp-fractal-clickzoom", "cdp-geometry-line", "cdp-geometry-aspect", "cdp-canvas-theme",
  "cdp-console", "cdp-modes-render",
  # 本轮新增：教程系统 + 数学键盘（18 篇教程目录/正文、引导走查的上一步与暂停、
  # 完成判定、126 键键盘、LaTeX 插入与占位符、搜索、无焦点时的明确提示）
  "cdp-tutorials-keypad",
  "audit-modes"
)

if (-not (Test-Path $hostExe)) {
  Write-Host "Host not found: $hostExe  (build Release first)" -ForegroundColor Red
  exit 1
}

$env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = "--remote-debugging-port=9222"
$proc = Start-Process -FilePath $hostExe -PassThru
Start-Sleep -Seconds 6

# NOTE (encoding): keep this block ASCII-only on purpose.
# Windows PowerShell 5.1 reads a .ps1 without a BOM as ANSI. A Chinese comment here gets
# mis-decoded, and the mangled bytes can swallow the *next* line -- which silently kills the
# assignment below ($rst becomes $null) and the reset never runs. That happened twice.
# Comments in Chinese are fine elsewhere in this file, just not immediately before code
# that must run.
# Appearance (palette / radius / density / font) lives in localStorage, and the WebView2 user
# data folder is reused across runs. Without this reset a dark palette from the previous run
# leaks into this one, while the plot suites count pixels expecting a light canvas -- the
# classic "passes alone, fails in the suite" false failure. Costs a few seconds.
$rst = Join-Path $PSScriptRoot "reset-appearance.mjs"
if ($rst -and (Test-Path $rst)) {
  $rout = & node $rst 2>&1 | Out-String
  Write-Host ("{0}" -f (($rout -split "`n" | Where-Object { $_ -match "OK|FAIL|RESULT" }) -join "`n")) -ForegroundColor DarkGray
}

$tp = 0
$tf = 0
foreach ($t in $tests) {
  $script = Join-Path $PSScriptRoot "$t.mjs"
  if (-not (Test-Path $script)) { Write-Host "missing script: $t" -ForegroundColor Yellow; continue }
  $out = & node $script 2>&1 | Out-String
  $m = [regex]::Match($out, "RESULT\|\S+\|(\d+)\|(\d+)")
  if ($m.Success) {
    $p = [int]$m.Groups[1].Value
    $f = [int]$m.Groups[2].Value
    $tp += $p; $tf += $f
    $mark = if ($f -eq 0) { "OK  " } else { "FAIL" }
    $color = if ($f -eq 0) { "Green" } else { "Red" }
    Write-Host ("{0} {1,-20} {2,3} pass / {3} fail" -f $mark, $t, $p, $f) -ForegroundColor $color
    if ($f -ne 0) {
      ($out -split "`n" | Where-Object { $_ -match "FAIL" }) | ForEach-Object { Write-Host "        $_" -ForegroundColor DarkYellow }
    }
  } else {
    Write-Host ("???? {0,-20} (no RESULT line, exit={1})" -f $t, $LASTEXITCODE) -ForegroundColor Yellow
  }
}

Write-Host ""
if ($tf -eq 0) {
  Write-Host "==== TOTAL: $tp pass / $tf fail ====" -ForegroundColor Green
} else {
  Write-Host "==== TOTAL: $tp pass / $tf fail ====" -ForegroundColor Red
}

if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
Remove-Item Env:\WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS -ErrorAction SilentlyContinue
exit $tf
