# 联网与落盘功能（搜索 / 账号 / 更新 / 设置备份 / 控制台）

> 本文说明五个需要联网、落盘或运行外部程序的功能在 Rust 宿主侧的接口、错误分类、缓存、取消语义与边界。
> 契约与接缝见 [README.md](README.md)，宿主对象与方法清单见 [OBJECTS.md](OBJECTS.md)，异步与推送见 [JOBS-PUSH.md](JOBS-PUSH.md)，凭据边界见 [CREDENTIALS.md](CREDENTIALS.md)。
> 权威源是 `MFMath.Host.Rust/src/{search,console,account,site,update,sys}.rs` 与 `MF_UI/MFMath.UI.Vue/src/lib/settings/io.js`。

## 0. 总览

| 功能 | 宿主对象 | 慢活如何返回 | 落盘位置 | 凭据 |
| --- | --- | --- | --- | --- |
| 联网搜索 | `search` | `Start` 立即返回 `requestId`，结果走 push | `search_cache.json`、`settings/search.json` | Wolfram App ID = DPAPI 密文 |
| 用户系统 | `account` | 全部同步（网络调用带超时） | `settings/account.json` | token = DPAPI 密文 |
| 更新链 | `update` | 全部同步 | 无 | 无 |
| 设置 / 诊断 | `sys` | 全部同步 | `settings/<name>.json` | 诊断包排除凭据 |
| 设置备份 | 前端 `settings/io.js` | 同步（借 `sys` 与 `win`） | 用户选择的目标文件 | 凭据不进备份 |
| 控制台与组件 | `con` | `Install`/`Start` 立即返回 id，进度走 push + 轮询 | `components/`、`console/` | 无（组件包过 SHA-256） |

方法名注册在 `MFMath.Host.Rust/src/handlers.rs`，统一核对：

```powershell
Select-String -Path MFMath.Host.Rust/src/handlers.rs -Pattern "fn (con|search|account|update|sys)\("
```

## 1. 联网搜索（`search`）

方法：`Info` `Configure` `SetWolframKey` `ClearWolframKey` `Start` `Cancel` `CancelAll` `Busy` `OpenUrl` `CacheStats` `ClearCache` `SelfCheck`。

### 1.1 三个后端

| 引擎 | 请求形状 | 说明 |
| --- | --- | --- |
| `duckduckgo`（默认） | IA JSON + HTML 结果页，两路共享超时预算 | 免密钥；HTML 结构变化归 `parse` |
| `wolfram` | `GET /v1/result`（纯文本） | 需要 App ID；无 key 或 401/403/501 归 `config` |
| `custom` | SearXNG 形状 JSON（`/search?q=…&format=json`） | 基址必须 http/https 且不含 `?` `#` `@` |

端点覆盖只走环境变量 `MF_SEARCH_ENDPOINTS`（JSON，键大小写不敏感，进程内解析一次）。`custom` 基址校验是 `search::custom_url_ok`，请求走 `site::get_verbatim` 绕开 `normalize_base_url`，因为后者对坏值退回内置站点。三个后端都用浏览器 UA `http::BROWSER_UA`（`site::get_ua` 传入），不是共享客户端的默认 UA。

### 1.2 失败分类（六类）

| kind | 触发条件 | 界面提示 |
| --- | --- | --- |
| `config` | 缺 App ID、自定义端点非法、Wolfram 401/403/501 | 补配置或换引擎 |
| `network` | 连接失败、TLS 失败、连接中断 | 检查网络/代理 |
| `http` | 非 2xx（含 DDG 反爬 202/403、限流 429） | 稍后再试或换端点 |
| `parse` | 返回形状不符（改版或未开 `format=json`） | 改用自定义端点 |
| `timeout` | 超过设定秒数 | 调大超时或换引擎 |
| `aborted` | 用户按停止 | 已取消 |

`search` 把 `unauthorized`（401/403）与 `ratelimit`（429）并入 `http`（`search::kind_of`），`account` 则分开，两个对象词表不同。

### 1.3 缓存

| 项 | 取值 |
| --- | --- |
| 文件 | `%LOCALAPPDATA%\MFMath\search_cache.json`（JSON 数组） |
| 键 | `<engine>|<规范化查询>`，规范化 = 折叠空白 + 转小写 |
| TTL | 从配置读，单位小时；`0` = 不过期；命中判定 `age > ttl` |
| 上限 | `CACHE_MAX_ENTRIES` = 200，写死不可配；超限按 `at` 淘汰最旧 |
| 空结果 / 坏文件 | 不写缓存 / 视为空缓存，均不阻断搜索 |
| `noCache:true` | 只跳过读，成功仍写 |
| 落盘 | 临时文件 + rename（原子） |

### 1.4 结果与解析

结果条数默认 8，钳在 1–20；查询词上限 500 字符，超长直接截断。DDG 扫描上限 `max*8+32`（不是结果上限），解析为手写扫描（`regex` crate 不支持旧实现的反引用）。摘要按下标配对；`href` 解实体后还原跳转，非 http(s) 丢弃。清洗顺序固定：去 `<script>`/`<style>` 整块 → 标签换空格 → 解实体 → 折叠空白；实体表是 HTML4 全集。

### 1.5 边界与取消

无翻页；无正文抓取（只用 snippet）；无去重/限流/退避（每个 `Start` 起新线程，唯一抑制是缓存命中）；不允许页面覆盖端点（只走 `MF_SEARCH_ENDPOINTS`）；`Info().endpoint` 文案写死，真实端点看 `Info().endpoints`。取消：`Cancel`/`CancelAll` 只置各自作业标记，在飞请求不强杀，响应回来后不采用，推 `search.error{kind:"aborted"}`。`SelfCheck` 的缓存项会 `cache_put("__selftest_a__", …)` 写回真实的 `search_cache.json` 且不检查 `cacheEnabled`。

```powershell
Select-String -Path MFMath.Host.Rust/src/search.rs,MFMath.Host.Rust/src/site.rs,MFMath.Host.Rust/src/http.rs -Pattern "CACHE_MAX_ENTRIES|MAX_QUERY_CHARS|MAX_JOBS|MF_SEARCH_ENDPOINTS|fn custom_url_ok|fn get_verbatim|BROWSER_UA"
```

## 2. 用户系统（`account`）

方法：`Info` `Configure` `ClearLocal` `Login` `LoginEx` `Logout` `RefreshProfile` `RefreshToken` `EnsureFresh` `Register` `SendCode` `VerifyCode` `ResendCode` `ChangePassword` `LoginHistory` `SiteVersion` `Busy` `CancelAll` `SelfCheck`。

### 2.1 端点与请求形状

| 方法 | 端点 | Content-Type | 认证 |
| --- | --- | --- | --- |
| `Login` / `LoginEx` | `POST /api/login` | form | 无 |
| `Logout` | `POST /api/logout` | form（空 body） | Bearer |
| `RefreshProfile` | `GET /api/me` | — | Bearer |
| `RefreshToken` | `POST /api/token/refresh` | form | Bearer |
| `Register` | `POST /api/register` | JSON | 无 |
| `SendCode` | `POST /api/send-code` | JSON | 无 |
| `VerifyCode` | `POST /api/verify-code` | form | 无 |
| `ResendCode` | `POST /api/resend-code` | form | 无 |
| `ChangePassword` | `POST /api/change-password` | form | Bearer |
| `LoginHistory` | `GET /api/login-history` | — | Bearer |
| `SiteVersion` | `GET /api/version` | — | 无 token |

`remember` 为真才加字段 `remember=1`，为假字段不出现；`Register` 原样转发页面 JSON；`ChangePassword` 返回固定 note 说明站点不立刻废止已登录会话。`SiteVersion` 返回只有 `latest/date/downloadUrl/hasUpdate/relation`，与 `update.Check`（另有 `current/sha256/size/…`）形状不同。

### 2.2 脱敏边界

`Info()` 暴露 `baseUrl timeoutSec remember autoRefresh loggedIn username email balance hasAiService role isActive sessionExpiresAt sessionExpiresInSec profileVerified profileCheckedAt offline dpapiAvailable tokenSource busy lastError lastErrorKind configPath`，不含 `tokenProtected`、`access_token` 与 token 本体。`Configure` 只改 `baseUrl` `timeoutSec` `remember` `autoRefresh` 四个字段。

### 2.3 清登录态的条件

`clear_token()` 的调用点是 `ClearLocal`、`Logout`、`RefreshProfile`/`RefreshToken` 收到 `unauthorized`。`unauthorized` = 401 或 403（`site::finish`），因此 401 或 403 才清登录态，404/429/5xx/网络/超时不清。登录失败不清已有登录态；`Logout` 不清 `username/email/balance`（登出后 `loggedIn=false` 但 `username` 仍在），要抹掉需调 `ClearLocal`。

### 2.4 到期与静默续期

到期时刻优先响应 `expires_in`，拿不到才解 JWT `exp`（不校验签名），都没有则为 0。「记住我 = 30 天」是站点侧给出，宿主无此常量。`EnsureFresh(thresholdSec)` 缺参默认 300：`autoRefresh=false` 或无 token → false；无到期时间 → false；离到期超过阈值 → true；否则尝试续期。「未登录」与「续期失败」都返回 false；站点既不给 `expires_in` 也不是 JWT 时静默续期永不触发。

### 2.5 离线与降级

不需网络：`Info`（自检断言 < 50 ms）、`Configure`、`ClearLocal`、`Busy`、`CancelAll`、`SelfCheck`。

| 场景 | 行为 |
| --- | --- |
| 取资料失败 | 保留缓存 `username/email/balance`，置 `profileVerified=false` + `offline=true` |
| 登录成功但 `/api/me` 失败 | 不回滚登录，只标未校验 |
| `Logout` 服务器不通 | 照样清本地，`serverNote` 说明 token 有效期内仍可用 |
| DPAPI 不可用 | token 只留内存，登录成功并带 `warning`，不写明文 |

`timeoutSec` 夹取是「< 5 → 20，> 120 → 120」。`Busy` 只反映登录，注册/续期/取资料/改密都不置位。

### 2.6 `token_version`

宿主侧零实现，全仓库 Rust 源码无 `token_version` 符号，它是站点侧会话版本号。定位：`Select-String -Path MFMath.Host.Rust/src/*.rs -Pattern "token_version"`（期望无输出）。

## 3. 更新链（`update`）

方法：`Info` `Check` `OpenDownloadPage` `PreviewDownloadUrl` `CancelAll` `SelfCheck`。

### 3.1 边界

| 做 | 不做 |
| --- | --- |
| 查站点版本、与本机比较 | 自动下载安装包 |
| 显示 `sha256`、大小、版本差异 | 自动运行安装包 |
| 把下载页交给系统浏览器（http/https） | 自行实现下载器或静默安装 |

`Info().policy` 原样把该取舍带给界面；自动执行安装包等于装一条「下载并运行可执行文件」的通路。

### 3.2 `sha256` 只显示，不校验

`parse_version_body` 只透传站点给的 `sha256`；没给就返回 `null` 并附 `sha256_reason`（或默认文案）。`pack::sha256_eq` 的调用点只有组件包解压前校验与两处自检，更新链没有校验路径，与「不提供下载」自洽。定位：`Select-String -Path MFMath.Host.Rust/src/*.rs -Pattern "sha256_eq"`。

### 3.3 版本比较

`compare_versions` 逐段比数字（`1.10.0 > 1.9.9`），带 `-` 后缀的预发布小于同号正式版。`update.rs` 的注释记录站点 `/api/version` 可能报告 `1.2.0`（v1 的版本），应用版本来自 `CARGO_PKG_VERSION`（值为 2.0.0），按「关系」判定：

| `relation` | 界面 |
| --- | --- |
| `newer` | 顶栏徽标 + 差异 + 下载入口（只有这种提示更新） |
| `same` | 已是最新版本 |
| `older` | 站点版本比本机旧 + 原因，不提示下载 |

### 3.4 下载地址闸门

`PreviewDownloadUrl` 与 `OpenDownloadPage` 共用 `resolve_download_url`：空拒绝；带协议过 `shellopen::is_allowed`（只放行 http/https）；不带协议过 `looks_relative_safe`（拒绝空、带协议、`//` 开头、含空白、`\`、`..`、`:`）后拼到 `baseUrl`。成功键名不同：`PreviewDownloadUrl` → `{ok,url}`（只算不开），`OpenDownloadPage` → `{ok,opened}`（调 `ShellExecuteW`）。

### 3.5 取消

`update.CancelAll` = `site::cancel_all()`，语义是「新请求不再发起」，在飞请求不强杀，带全局闩锁副作用（见 6.2）。宿主侧无自动下载或执行安装包的入口，地址解析是内部函数，不是桥面方法。

## 4. 设置 / 备份 / 诊断

### 4.1 设置存储（`sys`）

方法：`Info` `EngineReport` `StoreList` `StoreRead` `StoreWrite` `StoreDelete` `OpenPath` `ExportDiagnostics`。存到 `%LOCALAPPDATA%\MFMath\settings\<name>.json`，`<name>` 匹配 `[a-z0-9_-]`、非空、不超过 40 字符（`sys::valid_name`）。

| 方法 | 返回形状 |
| --- | --- |
| `StoreList` | 裸数组 `[{name,bytes,mtime}]`，只列 `.json`；目录不存在视为空数组；其它 I/O 错误返回 `{"error":…}` |
| `StoreRead` | `{ok:true,exists:false}` / `{ok:true,exists:true,json}` / `{ok:false,corrupt:true,error}`（解析失败保留原文件） |
| `StoreWrite` | 校验 name、非空 body、合法 JSON；写 `.tmp` → 旧文件复制 `.bak`（失败不阻断）→ 原子 rename |
| `StoreDelete` | 删 `<name>.json`；不存在也 `{ok:true}`；不删 `.bak` |

走 `sys` 的数据：`account.json`、`search.json`（宿主侧）与 `ai.json`（调用方是前端）。

### 4.2 设置备份（前端 `settings/io.js`）

备份在 Rust 侧无对应对象，实现在 `MF_UI/MFMath.UI.Vue/src/lib/settings/io.js`。包格式 `{app,kind,version,exportedAt,appVersion,files,prefs,excluded,stripped}`。

| 进备份 | 不进备份 |
| --- | --- |
| 设置文件（历史、工作区、会话、教程进度、更新偏好等） | `ai.json`（API Key）、`account.json`（token 密文）、`search.json`（App ID 密文） |
| `localStorage` 中 `mf_` 前缀的键 | 凭据文件的字段 |
| 包元数据与 `excluded`/`stripped` | — |

整份排除记入 `excluded`；其余文件字段级剥离（字段名命中 `protected/password/secret/token/api-key` 正则即不写，记入 `stripped`）。导入只写包里存在的文件，凭据文件永远不写；`app/kind/version` 任一不对就整包拒绝且发生在写第一个文件之前。设置与外观偏好在启动时读取，导入后需重启生效。

### 4.3 诊断包（`sys::export_diagnostics`）

写到 `%LOCALAPPDATA%\MFMath\diagnostics-<时间戳>.txt`，含宿主与环境、引擎产物清单、设置文件列表、除凭据外的设置文件原文、`app.log` 尾部 200 行、最新崩溃记录全文。跳过名单是 `CREDENTIAL_STEMS = ["ai","account","search"]` 外加「文件名含 `secret`」兜底。

### 4.4 `OpenPath` 约束

白名单是数据目录、exe 目录、组件目录三个根；目录用 `explorer.exe <path>`，文件用 `explorer.exe /select,<path>`。实现是小写化字符串前缀比较，未补分隔符、未 `canonicalize`，同前缀兄弟目录会通过检查。

## 5. 控制台与可选组件（`con`）

方法：`Components` `SetDownloadBase` `Install` `Uninstall` `CancelInstall` `InstallStatus` `Start` `Poll` `Stop` `StopAll`。

### 5.1 语言与组件清单

语言只有 `python` 与 `cpp`，非 `cpp` 一律按 Python 处理。清单是编译进代码的常量，无远程清单：`PYTHON_VERSION = 3.13.15`（包 11,009,825 字节）、`CPP_VERSION = 16.1.0`（包 54,084,880 字节），期望 SHA-256 与字节数也是内置常量，可在包旁放同名 `.sha256` 旁文件覆盖。安装/卸载用 `cpp`，下载路径是 `{base}/download/component/mingw`。

### 5.2 安装 / 卸载 / 取消

安装：找包（先缓存再 exe 目录）→ 下载 → SHA-256 校验 → 解压到 `.staging`（`pack::unzip_to` 带路径穿越防护）→ 补门面文件 → 校验关键可执行文件 → 替换目录。C++ 额外做 `flatten_single_root`、拷头文件、用 `.def` + `dlltool` 生成导入库（导出 `function_exists`/`math_call`）。安装作业初值必须是 `running`；未知组件名也返回 `jobId`，失败延后到 `state="error"`。卸载只认 `python`/`cpp`，成功返回删前体积，失败返回系统错误原文，不删 `cache/`。取消只在检查点生效（请求前、下载循环每轮、写盘每 1 MiB 块），校验/解压/dlltool/替换目录不响应；取消用 `state="error"` 承载，无独立 `cancelled` 状态。`CancelInstall` 返回键是 `canceled`（单 L），「id 不存在」与「标记没设上」同为 `{canceled:false}`。失败/取消清理 `.staging`、保留 `.part`。无「同组件只允许一个安装作业」的并发闸门（后果未验证）。

### 5.3 下载与断点续传

进度存 `<包名>.part`，带 `Range: bytes=<have>-`；`200`（忽略 Range）丢弃已下字节从头写；`416` 删 `.part` 重来；最多 3 轮。`Accept-Encoding: identity` 是断点续传正确性的前提。单请求超时 1800 秒，校验失败保留 `.part`。进度百分比非单调：下载阶段上限 81，随后校验把 percent 置为 8。下载源无 https/host 白名单（包要过 SHA-256，且本机端到端用例用 `http://127.0.0.1:<port>` 验续传）。

### 5.4 运行（`Start` / `Poll` / `Stop`）

状态机 `state: queued → running → done`，`stage: queued → [compiling] → running → done`，`exitCode` 在 `done` 前是 `null`。工作目录 `%LOCALAPPDATA%\MFMath\console\run<N>`，`console\` 只在进程第一次运行时清一次。Python 写 `main.py` + 引导脚本（显式 `sys.path.insert` 绕开嵌入 CPython 隔离模式），子进程超时 60 秒；C++ 编译参数含 `-include mfmath_autorun.hpp`（强制，让 stdout 边写边落管道），编译超时 120 秒、运行 60 秒，编译失败不运行。退出码：组件未装 `-1`、宿主错误 `-2`（stderr 前缀 `[宿主错误] `）、缺 exe `-3`。输出各上限 256 KiB（`MAX_OUTPUT_BYTES`），按行读 + 有损 UTF-8。`Poll` 返回完整累积缓冲，不是增量。`Stop` 真杀进程树（`taskkill /PID <pid> /T /F`），失败时孙进程可能残留，仅记日志不改返回形状。无并发上限、无队列、不拒绝。

### 5.5 完整性判据与内存表

`cpp.ready` 只检查 `lib\libmf_mathematics.a` + `include\mfmath.hpp`，实际运行还要求 `include\mfmath_autorun.hpp`；只缺该文件时下拉有 C++、运行却报「组件不完整」。`RUNS` 与安装 `JOBS` 两张内存表只增不减，每个 `Start` 的 `RunState`（可能含至多 512 KiB 输出）永久留在内存；对比 `search` 有 `MAX_JOBS=64` 淘汰。

```powershell
Select-String -Path MFMath.Host.Rust/src/console.rs -Pattern "PYTHON_VERSION|CPP_VERSION|PYTHON_PAYLOAD_BYTES|CPP_PAYLOAD_BYTES|DOWNLOAD_TIMEOUT_SEC|MAX_OUTPUT_BYTES"
```

### 5.6 推送与轮询

| 主题 | 载荷 | 消费者 |
| --- | --- | --- |
| `component.install` | `{kind, jobId, state, percent, message}`，观察线程每 200 ms 采样，值变才推 | 设置页组件组；控制台页不订阅，用 400 ms 轮询 `InstallStatus` |
| `console.run` | `{runId, language, event, stage, state, exitCode, elapsedMs, timedOut}`，`event` 只有 `stage` 与 `done` | 控制台页 |

`console.run` 不含 `stdout/stderr`，收到推送仍需 `Poll` 取数据；无 `queued` 首条推送。

## 6. 跨功能约定

### 6.1 返回形状与自检

| 方法 | 返回 |
| --- | --- |
| `con.Install` / `con.Start` | 裸 id 字符串 |
| `search.Busy` / `account.Busy` / `account.EnsureFresh` / `mf.Ready` / `mf.FunctionExists` | 裸布尔 |
| `sys.StoreList` | 裸 JSON 数组（出错时才是对象） |
| `search.CacheStats` / `con.SetDownloadBase` / `con.Poll` / `con.Stop` / `con.StopAll` / `con.CancelInstall` | 无 `ok` 字段 |

`SelfCheck()` 的 `ok` 恒为 true，总判据是 `ok_all`；判 `ok` 会恒真。`account`、`search`、`update` 三个对象都是这个形状。

### 6.2 取消的三种语义与全局闩锁

| 场景 | 语义 |
| --- | --- |
| job 通道 `CancelJob` | 停止等待 + 丢弃结果（引擎把这步算完） |
| `search.Cancel` / `account.CancelAll` / `update.CancelAll` | 不再发起新请求；在飞的不强杀 |
| `con.Stop` | 真杀进程树（`taskkill /T /F`） |

`account.CancelAll` 与 `update.CancelAll` 都调用 `site::cancel_all()` 置全局标记；复位只有 `account.configure` 与 `search.start` 两处（都调 `site::arm()`）。全局标记置位期间，`account`、`update`、`search` 经 `site` 发起的网络调用持续返回 `{"ok":false,"kind":"aborted"}`，直到改一次账号设置或发起一次搜索。

```powershell
Select-String -Path MFMath.Host.Rust/src/site.rs,MFMath.Host.Rust/src/account.rs,MFMath.Host.Rust/src/search.rs -Pattern "fn cancel_all|fn arm"
Select-String -Path MFMath.Host.Rust/src/site.rs -Pattern "unauthorized|ratelimit|fn finish|fn classify"
```

### 6.3 失败词表不是全局统一

| 对象 | kind 取值 |
| --- | --- |
| `account` | `unauthorized` `ratelimit` `http` `timeout` `aborted` `network` + `config` `parse`（八类） |
| `search` | `config` `network` `http` `parse` `timeout` `aborted`（六类，`unauthorized`/`ratelimit` 并入 `http`） |
| `update` | 站点层 `unauthorized`/`ratelimit`/`http`/`timeout`/`aborted`/`network` + 版本体 `parse` |
