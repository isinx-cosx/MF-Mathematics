# One-click regression: launch host with CDP port, run all verification scripts, summarize.
# Usage (Windows PowerShell 5.1 or PowerShell 7):
#   powershell -ExecutionPolicy Bypass -File run-all.ps1
#   powershell -ExecutionPolicy Bypass -File run-all.ps1 -NoLaunch      # attach to a host you started
# Prereq: Vue built (npm run build) and host built (dotnet build -c Release)
#
# ⚠ This file MUST keep its UTF-8 BOM. Windows PowerShell 5.1 reads a .ps1 without a BOM as
#   ANSI; every Chinese comment then gets mis-decoded, and the mangled bytes can swallow the
#   next line -- which broke this script's own $tests array ("Missing expression after ','")
#   until the BOM was added. That is the third time this encoding bit us.
#
# unit-* 是纯 Node 单元测试（假桥，不需要宿主窗口）；cdp-* 需要上面那个宿主进程。
# Each test script prints a machine-readable line: RESULT|<name>|<pass>|<fail>
# (ASCII only, so the summary parses regardless of console encoding.)

param([switch]$NoLaunch)

$ErrorActionPreference = "Continue"
# v2.0：宿主在 v2.0 根下，是 MF_UI 的**兄弟目录**，所以从 tests/ 数上去是**三层**：
#   tests → MFMath.UI.Vue → MF_UI → Multifunctional-Mathematics-v2.0
# ⚠ 这里原来写的是两层（`..\..\`），**永远解析不到**，于是靠下面那条写死的本机绝对路径兜住 ——
#   换台机器就直接 "Host not found"（BUGS.md B8）。是"真跑一次"才把它暴露出来的。
# 路径优先级：环境变量 MF_HOST_EXE → 三层相对路径；都拿不到就给一句能照着做的提示。
$hostExe = $env:MF_HOST_EXE
if (-not $hostExe) {
  $cand = Join-Path $PSScriptRoot "..\..\..\MFMath.Host\bin\Release\net10.0-windows\MFMath.exe"
  if (Test-Path $cand) { $hostExe = (Resolve-Path $cand).Path }
}
if (-not $hostExe) {
  Write-Host "Host not found: 期望 <v2.0>\MFMath.Host\bin\Release\net10.0-windows\MFMath.exe" -ForegroundColor Red
  Write-Host "  先构建它：dotnet build -c Release <v2.0>\MFMath.Host" -ForegroundColor Red
  Write-Host "  或用环境变量指定：`$env:MF_HOST_EXE = '<...>\MFMath.exe'" -ForegroundColor Red
  exit 1
}
$tests = @(
  "unit-result-model",
  # 协议层的离线单测：SSE 分帧（含"任意字节切分一致"），不需要宿主。TS 层搬过来之后
  # 这类纯逻辑第一次可以脱离窗口测 —— 这也是把协议放进 TS 的直接收益。
  "unit-sse",
  # markdown 解析（同样是纯逻辑）：重点在"递归不会把自己卡死"与"注入面为零"
  "unit-markdown",
  # 计算历史的**写盘去抖 vs 重新加载**竞态：250ms 的窗口界面上几乎点不出来，但会静默丢数据
  # （record 后 reload ⇒ 新条目永久消失；clearAll 后 reload ⇒ 清空的条目复活）。
  # 用假桥（内存 KV）把那个窗口稳定复现 —— 不需要宿主窗口。
  "unit-history-store",
  # ⚠ 曾漏登记：本用例一直在磁盘上却从未被执行（BUGS.md B7）。它是唯一按**几何判据**
  #   验证绘图的用例（曲线是否经过已知坐标点、视口内是否连续），与只数像素的其它
  #   绘图用例互补 —— 漏掉它等于绘图准确性没有回归。放在绘图组里，不放到最后。
  "cdp-plot-accuracy",
  "cdp-bridge-verify", "cdp-window-shell", "cdp-appearance", "cdp-input-notation", "cdp-font-load", "cdp-plot-verify", "cdp-plot-p3", "cdp-plot-p4",
  "cdp-plot-region", "cdp-plot-p5", "cdp-plot-final", "cdp-plot-asymptote",
  "cdp-plot-extrema", "cdp-plot-extrema-domain", "cdp-plot-3d", "cdp-plot-vector", "cdp-plot-fractal",
  "cdp-complex-modes", "cdp-plot-geometry", "cdp-plot-truth", "cdp-calc-workspace", "cdp-basic-calc",
  # B14 的往返验证：cdp-workspace 只碰 /plot/2d，3D/复平面/向量场/几何/分形这 5 页的
  # 工作区载荷是**新设计**的（Vue 版时代没接过），只过了类型检查 —— 这个用例补那一块。
  # ⚠ 它对"别人同时驱动同一个页面"极敏感（并行会话会互相踩），失败时先看它的 INTERFERENCE 提示。
  "cdp-plot-workspace",
  "cdp-diff-at-param", "cdp-fractal-orient", "cdp-fractal-clickzoom", "cdp-geometry-line", "cdp-geometry-aspect", "cdp-canvas-theme",
  "cdp-console", "cdp-modes-render",
  # 本轮新增：教程系统 + 数学键盘（18 篇教程目录/正文、引导走查的上一步与暂停、
  # 完成判定、126 键键盘、LaTeX 插入与占位符、搜索、无焦点时的明确提示）
  "cdp-tutorials-keypad",
  # 本轮新增：设置面板（入口、7 个分组、外观即时生效、引擎自检、组件状态、
  # 数据目录与诊断包、占位分组不隐藏、搜索能跳到未实现项）
  "cdp-settings",
  # 本轮新增：设置备份（导出/导入）。重点是「凭据不进备份、导入也不清凭据」。
  "cdp-settings-io",
  # 本轮新增：解方程端到端（三角方程给通解、部分解带说明、根式方程拒绝文案准确、
  # 二次方程的解集显示无回归）—— 修的是引擎断言，这里证明用户看得到
  "cdp-engine-solve",
  # 本轮新增：计算历史 + 顶栏「搜索」占位（算一次能在历史里看到、能搜、能点回填、
  # 真要落盘、清空要确认；搜索按钮打开的是说明面板而不是死按钮）
  "cdp-history-search",
  # 本轮新增：控制台的科学计算包（sympy/numpy/scipy 在组件 Python 里能 import 且能算，
  # 门面 mfmath 仍能调引擎）。组件未安装时本项 SKIP，不算失败。
  "cdp-console-sci",
  # 本轮新增：推送通道（宿主 → 页面）——往返信封、控制台运行结束、组件安装进度、
  # 设置里的通道自检行。它是 AI 流式输出与更新进度的共同前置。
  "cdp-push",
  # 本轮新增：工作区保存 / 载入（三个页面的内容采集、落盘、刷新后还原、坏输入不静默；
  # 跑完会把用户原有的工作区文件还原回去）
  "cdp-workspace",
  # 本轮新增：导出图片（六个绘图页都有入口、写出真 PNG、2 倍分辨率、背景不透明、
  # 写不进去时给失败原因）。走 window.__mfExportTo 钩子跳过模态保存对话框。
  "cdp-export-image",
  # 本轮新增：全局快捷键（F1 / Ctrl+Z / Ctrl+Y）+ 两个设置项（数值精度、绘图默认范围）。
  # 这条用例会断言"全程没有弹过任何窗口"。
  "cdp-shortcuts-prefs",
  # 本轮新增：表达式归一化的语义不变性（界面不许改算符/常量语义，否则同一个输入
  # 在不同页面会画出不同函数）
  "cdp-expr-normalize",
  # 本轮新增：AI 助手（宿主 AiBridge + 右侧抽屉面板 + 流式输出）。
  # 它自带一个本地假端点（tests/fake-ai-server.mjs）：不联网、不要真 key，
  # 覆盖配置 / 密钥不外泄 / 流式 / 停止 / 七类异常 / 隐私开关 /「AI 不得当计算源」。
  # 用例跑完会把密钥与 AI 配置还原（不污染用户环境）。
  "cdp-ai",
  # 本轮新增：联网搜索（宿主 SearchBridge + 三个后端 + 缓存；页面 /tools/search）。
  # 自带假搜索端点（tests/fake-search-server.mjs），场景由查询词触发（500/慢速/空/改版）。
  # ⚠ 宿主必须带 MF_SEARCH_ENDPOINTS 启动指向假端点 —— 端点覆盖走环境变量是有意的：
  #   页面能改端点就等于能把 Wolfram App ID 发到任意地址。run-all 下面会设置它。
  "cdp-search",
  # 本轮新增：用户系统（宿主 AccountBridge ↔ 站点 /api/* 契约 ↔ /account 页面）。
  # 自带假账号服务器（tests/fake-account-server.mjs，**照站点契约实现**），不需要真站点。
  # 最要紧的一段是"离线承诺"：断网后仍显示上次资料（标未校验）、**本地计算照常出结果**、仍能退出。
  # 用例结束会把站点地址还原成生产域名，不会把软件留在指向本地假服务器的状态。
  "cdp-account",
  # 本轮新增：更新链（宿主 UpdateBridge + 设置→更新 + 顶栏提示）。
  # 复用 cdp-account 的假账号服务器（/api/version 的夹具可用 /__setversion 调）。
  # 重点是「站点版本比本机旧时**不**提示更新」—— 站点现在报 1.2.0，若按"版本不同即新版"，
  # v2 用户会被引去下载 v1 安装包（那是降级）。
  "cdp-update",
  "audit-modes",
  # ⚠ 必须放最后：这条用例会**走遍每个视图并逐个模式点一次计算**，因此会顺带把
  # 控制台编辑器内核加载进来、在绘图页留下点与采样。放在前面会让后面那些
  # "编辑器内核还没加载""画布是干净的"之类的断言集体失败（实测踩过：把三条用例
  # 单独跑在干净宿主上分别是 46/0、9/0、66/0，混在同一会话里就成了 43/3、?/3、63/3）。
  "cdp-engine-coverage"
)

if (-not (Test-Path $hostExe)) {
  Write-Host "Host not found: $hostExe  (build Release first)" -ForegroundColor Red
  exit 1
}

$env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = "--remote-debugging-port=9222"
# Point the search backends at the local fake server for cdp-search. Endpoint overrides live in
# an environment variable (not in settings) on purpose: if the renderer could change the Wolfram
# endpoint, it could send the App ID anywhere. cdp-search refuses to run if this is not set.
# ⚠ The HOST reads this at startup, so it must be exported before the host starts.
$env:MF_SEARCH_ENDPOINTS = '{"ddgHtml":"http://127.0.0.1:8792/ddg/html","ddgIa":"http://127.0.0.1:8792/ddg/ia","wolfram":"http://127.0.0.1:8792/wolfram/result"}'

# -NoLaunch : attach to a host that is ALREADY running (started by you), instead of starting one.
# Why this exists: in some environments this script's own Start-Process cannot create a GUI
# process at all ("The operation was canceled by the user", i.e. ERROR_CANCELLED) while a
# shell-mediated launch (`cmd /c start "" "<exe>"`) works fine. Splitting "start the host" from
# "run the suites" keeps this script usable in both worlds -- and is handy when you want to run
# the suites against a host you are already debugging by hand.
# When attaching, YOU are responsible for having exported WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS
# and MF_SEARCH_ENDPOINTS before starting that host (see the two lines above).
$noLaunch = $NoLaunch -or ($env:MF_HOST_ALREADY_RUNNING -eq "1")

if ($noLaunch) {
  $ok = $false
  try { $ok = @((Invoke-RestMethod "http://127.0.0.1:9222/json/list" -TimeoutSec 4)).Count -gt 0 } catch { $ok = $false }
  if (-not $ok) {
    Write-Host "-NoLaunch 给了，但 127.0.0.1:9222 上没有可达的 CDP 端点。" -ForegroundColor Red
    Write-Host "  请先自己起宿主（注意先设好上面两个环境变量），例如：" -ForegroundColor Red
    Write-Host "    cmd /c start `"`" `"$hostExe`"" -ForegroundColor Red
    exit 1
  }
  Write-Host "== 附着到已在运行的宿主（-NoLaunch）==" -ForegroundColor DarkGray
  $proc = $null
} else {
  # NOTE (ASCII on purpose, see the encoding note below): a leftover WebView2 from the
  # previous run keeps the CDP port 9222 bound. The freshly started host then cannot bind
  # it, while CDP silently attaches to the STALE host -- which never saw the env vars set
  # above. Symptom seen in practice: cdp-search reports "host endpoints are the fake ones"
  # even though this script sets MF_SEARCH_ENDPOINTS, i.e. a false failure that looks like
  # a product bug. Clear the leftovers and wait for the port before launching.
  Get-Process msedgewebview2 -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  $portDeadline = (Get-Date).AddSeconds(10)
  while ((Get-Date) -lt $portDeadline) {
    $busy = Get-NetTCPConnection -LocalPort 9222 -State Listen -ErrorAction SilentlyContinue
    if (-not $busy) { break }
    Start-Sleep -Milliseconds 250
  }
  $proc = Start-Process -FilePath $hostExe -PassThru
  Start-Sleep -Seconds 6
}

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
$tskip = 0
foreach ($t in $tests) {
  $script = Join-Path $PSScriptRoot "$t.mjs"
  if (-not (Test-Path $script)) { Write-Host "missing script: $t" -ForegroundColor Yellow; continue }

  $out = & node $script 2>&1 | Out-String
  $m = [regex]::Match($out, "RESULT\|\S+\|(\d+)\|(\d+)")
  # SKIP：用例自己说了"这次没测"（例：cdp-console-sci 的 CPython 组件未安装）。
  # 它打印的是 RESULT|…|0|0，若照旧按 fail=0 处理就会显示成 OK —— 一个**什么都没测**的用例
  # 看起来像通过，正是纪律①（不编造结果）要防的。所以单独成一行、单独计数。
  if ($out -match "\[SKIP\]") {
    $tskip++
    Write-Host ("SKIP {0,-20} {1}" -f $t, (($out -split "`n" | Where-Object { $_ -match "\[SKIP\]" } | Select-Object -First 1) -replace '^\s+', '')) -ForegroundColor DarkGray
  } elseif ($m.Success) {
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
$skipNote = if ($tskip -gt 0) { " ($tskip skipped)" } else { "" }
if ($tf -eq 0) {
  Write-Host "==== TOTAL: $tp pass / $tf fail$skipNote ====" -ForegroundColor Green
} else {
  Write-Host "==== TOTAL: $tp pass / $tf fail$skipNote ====" -ForegroundColor Red
}

# Only stop the host if THIS script started it ($proc is $null under -NoLaunch -- never kill
# a host the caller is running on purpose).
if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
Remove-Item Env:\WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS -ErrorAction SilentlyContinue
Remove-Item Env:\MF_SEARCH_ENDPOINTS -ErrorAction SilentlyContinue
exit $tf
