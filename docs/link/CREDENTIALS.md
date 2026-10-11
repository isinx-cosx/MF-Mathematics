# 凭据与隐私

> 本文说明三类凭据的落盘形式与页面可见范围、DPAPI 的规则与适用范围、AI 密钥的明文存储代价、导出与诊断的排除规则、日志的位置与内容。
> 桥面契约与方法清单见 [README.md](README.md) 与 [OBJECTS.md](OBJECTS.md)，宿主分工见 [HOSTS.md](HOSTS.md)。
> 权威源是 [`dpapi.rs`](../../MFMath.Host.Rust/src/dpapi.rs)、[`account.rs`](../../MFMath.Host.Rust/src/account.rs)、[`search.rs`](../../MFMath.Host.Rust/src/search.rs)、[`sys.rs`](../../MFMath.Host.Rust/src/sys.rs)、[`logging.rs`](../../MFMath.Host.Rust/src/logging.rs)；AI 密钥的读写位于页面 [`bridge.js`](../../MF_UI/MFMath.UI.Vue/src/lib/ai/bridge.js) 与 [`relay.ts`](../../MF_UI/MFMath.UI.Vue/src/lib/ai/relay.ts)。

## 1. 三类凭据的落盘形式

| 凭据 | 文件与字段 | 落盘形式 | 写入者 | 页面可读到 |
| --- | --- | --- | --- | --- |
| 登录 token | `%LOCALAPPDATA%\MFMath\settings\account.json` 的 `token_protected` | DPAPI 密文（base64） | `account.rs` 的 `store_token` | `loggedIn`、`tokenSource`（`dpapi` / `memory` / `none`） |
| Wolfram App ID | `search.json` 的 `wolfram_key_protected` | DPAPI 密文（base64） | `search.rs` 的 `set_wolfram_key` | `hasWolframKey`、`wolframKeySource` |
| AI API Key | `ai.json` 的 `apiKey` | 明文 | 页面 `bridge.js` 的 `aiSetKey`（经 `sys.StoreWrite`） | 明文本身，显示在设置面板的输入框 |

前两类的脱敏由断言守住：

- `account.rs` 的 `self_check` 断言 `info()` 的返回文本不含 `access_token`、不含 `tokenProtected`、不含 token 本体。
- `search.rs` 的 `info()` 只返回 `hasWolframKey` 与 `wolframKeySource`，不返回 App ID 与密文。

```powershell
Select-String -Path MFMath.Host.Rust/src/account.rs -Pattern "tokenProtected|access_token"
Select-String -Path MFMath.Host.Rust/src/search.rs  -Pattern "hasWolframKey|wolframKeySource"
```

设置文件的写入方：`ai`、`ai-chat`、`history`、`workspace`、`update` 由页面写，`account`、`search` 由宿主写。

```powershell
Get-ChildItem MF_UI -Recurse -Include *.js,*.ts,*.vue | Select-String -Pattern "StoreWrite\("
```

## 2. DPAPI 的规则与适用范围

`dpapi.rs` 是密钥保护的唯一实现，`protect` 返回 base64 的 DPAPI blob，`unprotect` 接受同一形式。规则如下。

| 规则 | 实现 | 后果 |
| --- | --- | --- |
| 只在当前用户下可解 | 不传 `CRYPTPROTECT_LOCAL_MACHINE` | 换 Windows 用户后密文解不开，密文不可跨用户搬运 |
| 加解密不弹界面 | 传 `CRYPTPROTECT_UI_FORBIDDEN` | 系统状态异常时返回失败，不阻塞调用方 |
| 失败不降级为明文 | 调用方在 `protect` 返回 `None` 时只把值留在内存 | 磁盘上不出现明文；本次运行可用，重启后需重填 |
| 不传 optional entropy | `CryptProtectData` / `CryptUnprotectData` 的 entropy 参数为 `None` | 同一用户下由同一实现写出的密文互相可解，两个宿主可共用一份设置文件 |
| 描述串不参与解密 | 常量 `DESCR` 只写入 blob 元数据 | 校验失败时按 `None` 处理，不做内容推断 |

失败路径的具体表现：`account.rs` 的 `store_token` 返回 `(false, warning)`，登录响应带 `warning` 字段并在 `lastErrorKind` 记为 `dpapi`；`search.rs` 的 `set_wolfram_key` 返回 `{"persisted": false, "warning": …}`。两条警告都写明值只保留在本次运行的内存里。

`account.Info()` 与 `search.Info()` 的 `dpapiAvailable` 字段不是读标志位，而是调用 `dpapi::selftest()` 做一次完整的 `protect` 加 `unprotect` 往返。

适用范围由调用点决定，`protect` / `unprotect` 共 6 处、`selftest` 共 3 处：

```powershell
(Select-String -Path MFMath.Host.Rust/src/*.rs -Pattern "dpapi::(protect|unprotect)").Count   # 期望 6
Select-String -Path MFMath.Host.Rust/src/*.rs -Pattern "dpapi::(protect|unprotect)"
(Select-String -Path MFMath.Host.Rust/src/*.rs -Pattern "dpapi::selftest").Count              # 期望 3
```

调用点是 `account.rs` 的 `resolve_token` 与 `store_token`、`search.rs` 的 `resolve_key` 与 `set_wolfram_key`、[`selftest.rs`](../../MFMath.Host.Rust/src/selftest.rs) 的往返探针。AI 密钥不在其中。

清除路径覆盖对象相同：`account.clear_local` 清空内存 token 与 `token_protected`；`search.clear_wolfram_key` 清空内存 App ID 与密文。

## 3. AI 密钥：明文存储与代价

AI 请求由页面直接发往用户配置的端点，密钥由 `ai.json` 的 `apiKey` 字段提供，不经过宿主，也不经过 DPAPI。

读取与写入路径：

- `refreshAiConfig` 从 `ai.json` 取 `apiKey`，置 `hasKey`、`keySource`、`keyPersisted`；若只剩旧版 `apiKeyProtected` 密文则置 `hasKey = false`、`legacyProtectedKey = true`，并给出在设置里重填一次的提示。
- `refreshAiConfig` 构造页面状态时删除 `apiKey` 与 `apiKeyProtected` 两个字段，密钥另行交给运输层。
- `aiSetKey` 写入明文 `apiKey` 并删除 `apiKeyProtected`；`aiClearKey` 删除两者。

```powershell
Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/ai/bridge.js -Pattern "next.apiKey = k|delete next.apiKeyProtected|legacyProtectedKey"
```

代价与对应事实：

| 代价 | 事实 |
| --- | --- |
| 密钥以明文落盘 | 能读到 `ai.json`、能拿到文件备份或磁盘镜像的人可直接取用 |
| 密钥常驻页面内存 | `relay.ts` 以模块级 `creds` 持有密钥，每次请求用它组 `Authorization: Bearer`，会话期间一直存在 |
| 旧版密文无法解出 | 页面侧没有 DPAPI 可调，`hasKey` 为 `false`，界面如实提示重填，不显示为已配置 |
| 端点由用户填写的地址决定 | 闸门在 `relay.ts`：`isUsableBaseUrl` 只接受 http/https 绝对地址；`joinBasePath` 要求路径以单个 `/` 开头、不含空白与控制字符、拼接结果与 `baseUrl` 同源，否则抛 `RelayError('config')`，不做退回内置站点的规范化 |
| 服务商兼容性未逐一验证 | 设置面板提供 DeepSeek、OpenAI、Ollama 三个预设；可用性由"测试连接"实测，它发一条 `max_tokens` 为 1 的请求；企业代理与按域白名单的服务商未做验证 |

```powershell
Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/ai/relay.ts -Pattern "isUsableBaseUrl|joinBasePath|RelayError\('config'"
```

## 4. 导出与诊断的排除规则

两处实现按同一份文件清单排除凭据，清单之外的设置文件按字段名再剥一遍。

| 位置 | 规则 | 记录 |
| --- | --- | --- |
| 页面备份导出（`io.js` 的 `buildBundle`） | `CREDENTIAL_FILES` 为 `["ai","account","search"]`，整份排除 | 包内 `excluded` 列出被排除的文件名 |
| 页面备份导出（同上） | `SECRET_FIELD` 为正则 `(protected\|password\|passwd\|secret\|token\|api[-_]?key)`，命中键名即剥离 | 包内 `stripped` 列出被剥离的字段名 |
| 页面备份导入（`applyBundle`） | 跳过 `CREDENTIAL_FILES` 中的文件，不覆盖本机现存的密钥 | 被跳过的名字进入返回值 `skipped` |
| 宿主诊断包（`sys.rs` 的 `export_diagnostics`） | `CREDENTIAL_STEMS` 为 `["ai","account","search"]`，按文件名主干排除；另有文件名含 `secret` 的兜底条件 | 被排除的文件不进包 |

```powershell
Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/settings/io.js -Pattern "CREDENTIAL_FILES =|SECRET_FIELD ="
Select-String -Path MFMath.Host.Rust/src/sys.rs -Pattern "CREDENTIAL_STEMS"
```

诊断包的收集范围是 `settings` 目录下所有以 `.json` 结尾的文件（`account.json`、`search.json`、`ai.json` 除外），加上宿主与环境信息、引擎产物清单、设置文件清单、`app.log` 尾部和最近一个崩溃文件的全文。设置文件清单只含文件名、字节数与修改时间。

```powershell
Select-String -Path MFMath.Host.Rust/src/sys.rs -Pattern "logging::tail|ends_with\(.\.json.\)"
```

两项不在上述规则覆盖范围内，按现状记录：

| 项 | 现状 | 验证方法 |
| --- | --- | --- |
| `<name>.json.bak` | `store_write` 在覆盖前把旧文件复制为 `<name>.json.bak`；`store_delete` 只删除 `<name>.json`。全仓库没有清理 `.bak` 的代码，因此写入过 AI 密钥的机器上可能留下含明文 `apiKey` 的 `ai.json.bak`。`store_list` 与诊断包都只收 `.json`，界面上看不到该文件 | 运行 `Select-String -Path MFMath.Host.Rust/src/*.rs -Pattern "\.bak"`，命中只有 `store_write` 的复制处；再在设置面板保存一次密钥并清除，检查 `%LOCALAPPDATA%\MFMath\settings` 下是否仍有 `ai.json.bak` |
| `ai-chat.json` | 会话记录由 `bridge.js` 以 `CHAT_STORE = "ai-chat"` 写入，内容为最终消息文本，不在 `CREDENTIAL_FILES` 名单内，因此会进入页面导出的备份包 | 对照 `CHAT_STORE` 与 `CREDENTIAL_FILES` 两个常量，或导出一次备份后检查包内 `files` 的键名 |

```powershell
Select-String -Path MFMath.Host.Rust/src/sys.rs -Pattern "json.bak|fn store_delete"
Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/ai/bridge.js -Pattern "const CHAT_STORE|StoreWrite\(CHAT_STORE"
```

## 5. 日志的位置与内容

| 项 | 事实 |
| --- | --- |
| 根目录 | `%LOCALAPPDATA%\MFMath`（`logging::data_dir`），设置文件在其 `settings` 子目录 |
| 日志目录 | `%LOCALAPPDATA%\MFMath\logs`（`logging::dir`） |
| 常规日志 | `app.log`，单文件上限 2 MB，超过后整体改名为 `app.1.log`，只保留一代 |
| 崩溃日志 | `crash-<yyyyMMdd-HHmmss>.log`：时间、来源、版本、系统、程序目录、日志目录、异常文本与 backtrace、`app.log` 尾部 200 行；只保留最近 20 个 |
| 尾部读取上限 | 读日志尾部时最多读 256 KB |
| 前端异常 | 未捕获异常、未处理的 Promise 异常与 Vue 组件异常经 `diag.Front` 写入同一个 `app.log`，前缀为 `[前端]`；每个会话上限 50 条，按文本去重 |
| 字段脱敏 | 日志写入不做键名或值的过滤，写入内容是异常文本、截断后的栈与页面路由 |
| 上报 | `logging.rs` 不发起任何网络调用；日志内容只在本机，仅在用户主动导出诊断包时写入数据目录下的 `diagnostics-<yyyyMMdd-HHmmss>.txt` |

```powershell
Select-String -Path MFMath.Host.Rust/src/logging.rs -Pattern "const (MAX_BYTES|KEEP_CRASH_FILES|CRASH_TAIL_LINES|TAIL_CHUNK)"
Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/diagnostics/errors.js -Pattern "MAX_PER_SESSION"
Select-String -Path MFMath.Host.Rust/src/logging.rs -Pattern "http|reqwest|TcpStream"   # 期望无输出
```

## 6. 复查清单

```powershell
# DPAPI 调用点数量与分布：期望 6 处，位于 account.rs / search.rs / selftest.rs
Select-String -Path MFMath.Host.Rust/src/*.rs -Pattern "dpapi::(protect|unprotect)"

# AI 密钥的读写路径：应为明文写入 apiKey，并删除 apiKeyProtected
Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/ai/bridge.js -Pattern "apiKey"

# 备份与诊断的排除名单：两侧都应覆盖 ai / account / search
Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/settings/io.js -Pattern "CREDENTIAL_FILES|SECRET_FIELD"
Select-String -Path MFMath.Host.Rust/src/sys.rs -Pattern "CREDENTIAL_STEMS|secret"

# 日志上限、崩溃文件保留数与前端异常上限
Select-String -Path MFMath.Host.Rust/src/logging.rs -Pattern "MAX_BYTES|KEEP_CRASH_FILES|CRASH_TAIL_LINES"
Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/diagnostics/errors.js -Pattern "MAX_PER_SESSION"
```

DPAPI 的往返可由宿主自检直接验证：`--selftest-common` 覆盖 `selftest.rs` 中的探针，`account.SelfCheck()` 与 `search.SelfCheck()` 各自报告 `dpapiAvailable`。
