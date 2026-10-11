# 排障手册

> 本文回答：出了问题怎么排查。按症状分节。
> 产品说明见 [README.md](README.md)，常见问题见 [FAQ.md](FAQ.md)，功能全表见 [FEATURES.md](FEATURES.md)。

## 1. 任何症状先做这四件事

| 步骤 | 做什么 | 判据 |
| --- | --- | --- |
| 1 | 看日志目录有没有内容 | `%LOCALAPPDATA%\MFMath\logs` |
| 2 | 确认页面 URL | `https://mfmath.local/index.html` |
| 3 | 确认引擎在不在 | `app.log` 里搜「引擎自检」，应有 `list_functions.count = 424` |
| 4 | 确认宿主对象 | `app.log` 里应有 9 行「宿主对象 X 已注册」，没有 `ai` |

一条命令看日志：

```powershell
$logs = Join-Path $env:LOCALAPPDATA 'MFMath\logs'
Get-ChildItem $logs | Sort-Object LastWriteTime -Descending | Select-Object -First 8 Name,Length,LastWriteTime
Select-String -Path "$logs\app.log" -Pattern '宿主对象|引擎自检'
```

## 2. 界面无响应或卡住

先分四种形态：

| 形态 | 判据 | 归类 |
| --- | --- | --- |
| 按钮点了没动静，其余能动 | `app.log` 有 `[前端] 未捕获异常` | 前端异常 |
| 提示「未检测到引擎桥」 | 结果对话框写「（计算功能待接入引擎）」 | 不在宿主里运行 |
| 白屏 + 系统标「未响应」 | 同步调用占住主线程 | 重活走了同步通道 |
| 窗口起不来 | 有 `crash-*.log` | 见数据目录占用 |

### 前端异常

异常不会丢：未捕获异常、未处理 Promise、Vue 组件异常都经 `diag` 写进 `app.log`，前缀 `[前端]`。
复现一次卡住的点击，再看日志：

```powershell
Select-String -Path (Join-Path $env:LOCALAPPDATA 'MFMath\logs\app.log') -Pattern '\[前端\]' | Select-Object -Last 20
```

### 引擎在算

同步引擎调用会占住界面线程。重的活走后台任务通道，分界线由 `asyncPolicy.js` 决定。「取消」只能
停止等待并丢弃结果，引擎没有取消钩子，工作线程会把它算完，所以界面文案是「已取消等待」。

已知会慢的算法（持续同调、12×12 以上符号矩阵等）见 [../HANG-OPTIMIZATION.md](../HANG-OPTIMIZATION.md)。
大规模病态输入现在会快速报错并给出上限说明，看到「超出可计算范围」就是这一层，不是坏了。

### 数据目录占用

宿主在建窗口前用锁文件检查实例。启动报「WebView2 数据目录正被另一个实例占用」说明真的有两个
实例，结束掉锁文件里记录的 pid。走到建窗口才报 `0x800700AA`，可能是上次异常退出残留的
`msedgewebview2.exe` 子进程。若换全新目录仍报同一个码，属宿主侧问题，留档 `crash-*.log` 与
`app.log` 排查。

## 3. 结果为空或「未实现」

「未实现」本身可能是正确答案：非初等函数的不定积分返回 `{"isError":false,"value":"未实现"}`，
这是设计选择，不是缺陷。四种引擎返回要分清：

| 返回 | 含义 |
| --- | --- |
| `isError:false` 且值为「未实现」 | 如实拒绝，设计选择 |
| `isError:true` 且「未找到函数」 | action 名不存在，或注册表为空 |
| `isError:true` 且「超出可计算范围」 | 上限拒绝，防卡死 |
| `isError:true` 且「缺少必填参数」 | 参数没给全 |

不起宿主直接问引擎：

```powershell
$p = "MF_Mathematics\build\bin\Release\probe_call.exe"
& $p list_functions '{}'
& $p integrate '{"expr":"x**x","var":"x"}'
```

如果所有 action 都返回「未找到函数」，是注册表整个为空，成因在链接期漏了 `/WHOLEARCHIVE`。
守门断言是 `count` 为 424。

## 4. 公式显示不对

分三种现象：

| 现象 | 原因 |
| --- | --- |
| 公式渲染成方框 | 字体文件没加载到，或 `wwwroot` 是旧的 |
| 显示成 `\frac{a}{b}` 纯文本 | KaTeX 渲染失败后主动退回纯文本 |
| 整个界面像旧版 | `npm run build` 之后没有重新同步 `wwwroot` |

`npm run build` 末尾会裁剪字体，只保留 `.woff2`。字体判据在真宿主里跑 `cdp-font-load.mjs`。

## 5. 组件安装

控制台的 Python 与 C++ 组件是可选下载。界面上「未安装（组件包已在本地，约 N MB，点安装即可）」
表示包已在本机缓存，安装不会再联网；「未安装（点安装会从官网下载约 N MB）」表示需要下载。

两个组件包在站点侧尚未上传，所以「点安装 → 下载 → 装好」这条路径没有成功记录。下载失败的错误
信息里带下载地址与断点文件名。断点续传存 `<包名>.part`，校验失败保留 `.part` 不删。

手工兜底：把 `<包名>.zip` 放进 `%LOCALAPPDATA%\MFMath\components\cache\`，再点安装，宿主跳过
下载直接校验。

## 6. 登录与更新

| 问题 | 说明 |
| --- | --- |
| 什么时候清登录态 | 401 或 403；404、429、5xx、网络、超时都不清 |
| 登录后掉线 | 站点侧续期端点可能未部署，或站点不给到期时间导致静默续期不触发 |
| 站点版本比本机旧 | 是正确判定，不提示下载，避免把 v2 用户引去下 v1 安装包 |
| 更新不下载安装包 | 设计如此，只提示并把下载页交给系统浏览器 |

账号、更新、搜索全都报 `aborted` 是取消闩锁：点过一次取消后，全局取消标记被置位，只有改一次
账号设置或发起一次搜索才复位。

## 7. 日志与诊断包

| 项 | 位置与内容 |
| --- | --- |
| 常规日志 | `%LOCALAPPDATA%\MFMath\logs\app.log`，单文件上限 2 MB，轮转成 `app.1.log` |
| 崩溃日志 | `crash-<时间戳>.log`，含异常与 `app.log` 尾部 200 行，只留最近 20 个 |
| 诊断包 | 设置 → 存储与数据 → 「导出诊断包」，含环境、引擎清单、设置内容与日志尾部 |

崩溃与前端异常只写本地，不联网上报。诊断包跳过凭据（`ai`、`account`、`search` 三个设置文件）。

日志目录是空的，按顺序查：exe 是否跑在工作区内（工作区内进程写不了 `%LOCALAPPDATA%`）、
`LOCALAPPDATA` 是否被重定向、宿主是否根本没启动。
