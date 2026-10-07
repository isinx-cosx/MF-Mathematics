# 凭据边界：什么加密、什么明文、为什么

> **本文只回答一个问题：用户的密钥与登录态存在哪、什么形式、谁能读到。**
>
> 契约见 [README.md](README.md)；方法清单见 [OBJECTS.md](OBJECTS.md)；
> 决策背景见 [DECISIONS.md](../DECISIONS.md) D-004。

**核对时间**：2026-10-07
**权威源**：`MFMath.Host.Rust/src/dpapi.rs`、`account.rs`、`search.rs`、`logging.rs`；前端 `src/lib/ai/relay.ts`、`src/lib/settings/io.js`

---

## 0. 一句话

**同一份设置目录里，两种截然不同的待遇：**

| 数据 | 形式 | 谁写的 | 页面能看见什么 |
| --- | --- | --- | --- |
| 账号 token | **DPAPI 密文**（base64 blob） | 宿主 `account.rs:188` | 只有 `hasToken` 这类布尔 |
| 搜索 Wolfram App ID | **DPAPI 密文** | 宿主 `search.rs:1693` | 只有 `hasWolframKey` 布尔 |
| **AI 的 API Key** | **明文** | **页面**（经 `sys.StoreWrite`） | **明文本身** |

最后一行是刻意的例外，不是遗漏 —— 见 §2。**它也是这套边界里唯一"降级"过的地方。**

---

## 1. DPAPI 的三条纪律（`dpapi.rs` 文件头，一条不少）

`dpapi.rs` 是密钥保护的**唯一实现**。三条纪律：

| # | 纪律 | 为什么 |
| --- | --- | --- |
| ① | **只在当前用户下可解**（**不传** `CRYPTPROTECT_LOCAL_MACHINE`） | 换用户就解不开，密文不能跨用户搬运 |
| ② | **禁止弹 UI**（`CRYPTPROTECT_UI_FORBIDDEN`） | 加解密不能因为系统状态弹窗；**失败就如实报告失败** |
| ③ | **失败绝不降级成明文落盘** | 调用方在 `protect` 返回 `None` 时**只把密钥留在内存里**，并明确告诉用户"本次会话有效、重启后需要重填" |

另外两条**格式约束**（同样不是随便选的）：

- **不传 optional entropy**（C# 传的是 `IntPtr.Zero`）—— 熵一变，同机同用户的密文就**互相解不开**，
  而"两个宿主共用同一份设置文件"正是迁移期的主要用法；
- 密文是 **base64 的 DPAPI blob**（不是 hex、不是裸字节）—— `ai.json` 里历史上的
  `apiKeyProtected` 字段存的就是它。

**验证手段**：`selftest.rs:39-48` 有一条 DPAPI 往返探针（`--selftest-common`，期望 **10/0**），
`account.Info()` 里还会报 `dpapiAvailable`（`account.rs:248`）。

> ⚠ **注意 `Info()` 每次调用都真的做一次 DPAPI 往返**：它里面的 `dpapi::selftest()`
> 不是读标志位，而是**真的 protect + unprotect 一次探针串**（`dpapi.rs:129-135`）。
> 所以 `account` 自检的 ⑥ 项断言"`Info()` < 50 ms"（`account.rs:869-884`）**同时也在量 DPAPI 的开销**。

> ⚠ **`dpapi.rs` 的文件头已经过时**：`dpapi.rs:1` 把"AI 的 API Key"列为 DPAPI 的三类用户之一，
> `dpapi.rs:18` 还写"`ai.json` 里 `apiKeyProtected` 存的就是它"。**AI 的密钥已经不走 DPAPI 了**
> （改成明文，见 §2；旧字段由前端主动删除，`lib/ai/bridge.js:275-293`）。
> 实测确认当前调用点只有两处：`account.rs:183/188`、`search.rs:1598/1693`
> （外加 `selftest.rs` 与 `account.rs:887` 的自检）。
> 这是 [PROJECT-BOARD.md](../PROJECT-BOARD.md) §3 R7 那一类问题的一个新实例，**已登记给 A 面**。

---

## 2. AI 为什么是明文（唯一的一次降级）

**2026-10-07，项目所有者决定**：AI 整体搬到 TS 页面直连（[DECISIONS.md](../DECISIONS.md) D-004）。
于是 `ai.json` 的 `apiKey` **没有任何加密**。

### 2.1 代价（五条，都是真的）

1. **密钥明文落盘**：换用户、拷贝文件、看备份都能直接读到；
2. **密钥常驻页面内存**：每次请求都要用它拼 `Authorization`，所以**会话期间一直在渲染进程里**
   —— 不只是录入那一瞬；
3. **旧版的 DPAPI 密文解不开了**：老用户 `apiKeyProtected` 里的密文，页面侧**没有 DPAPI 可调**。
   现在的处理是**如实提示"请在设置里重填一次"**，并且 `hasKey=false`（**不假装还有密钥**）；
4. **"中继路径闸门"这条安全属性消失**：以前宿主只接受相对路径、绝对地址一律拒
   （防止密钥被发到任意地址）。现在端点由用户配的 `baseUrl` 决定 —— 闸门转移到 §2.2；
5. **只实测过 DeepSeek 与 GitHub**：**不能**说"所有服务商都能直连"（企业代理、按域白名单的服务商仍可能不行）。

### 2.2 换地方但仍然生效的两条闸门

**闸门一：绝不做"地址不认识就退回内置站点"的规范化。**
这是原先宿主侧特意绕开 `site.rs` 的理由，换到 TS 后由 `relay.ts` 的
`isUsableBaseUrl` / `joinBasePath` 承担：

- 只接受 **http/https 绝对地址**；
- 路径必须以**单个 `/`** 开头；
- 拼接结果必须与 `baseUrl` **同源**；
- 否则报 `config` 错。

`ai.SelfCheck()` 里**有一项专门验它**（含"错误信息里不出现内置站点域名"）。

**闸门二：导出 / 诊断**整份**剥掉**密钥字段。**三处实现，逻辑一致**：

| 位置 | 做法 |
| --- | --- |
| `settings/io.js`（前端导出备份） | `CREDENTIAL_FILES = ["ai","account","search"]` **整份排除**，并把名字写进包里的 `excluded` |
| `settings/io.js`（前端） | `SECRET_FIELD` 正则再命中 `apiKey` 等字段名 —— **双保险** |
| `sys.rs:282`、`292-297`（宿主导出诊断包） | `CREDENTIAL_STEMS = ["ai","account","search"]`，**外加**"文件名含 `secret`"的兜底 |

> 📌 **这里的注释记着一个真实的坑**（`sys.rs:278-281`）：宿主原先**只按"文件名含 `secret`"跳**，
> 而 `ai.json` / `account.json` / `search.json` **一个都不含 `secret`** —— 等于没跳，
> 会把 API Key、登录态、Wolfram App ID 整份打进诊断包。
> **"过滤规则写对了"和"过滤规则真的命中"是两件事** —— 与 [DESIGN.md](../DESIGN.md) §2 ③ 同一族教训。

否则备份包会把明文密钥带出去。

### 2.3 ⚠ 一处**没被这两道闸门覆盖**的残留：`.bak` 里可能有明文密钥

`StoreWrite` 的落盘流程是"**先备份、再临时文件、再原子替换**"（`sys.rs:208-219`）：
覆盖前把原文件复制成 `<name>.json.bak`。起因是 v1 直接 `open(path,"w")`，
**写一半崩掉下次必然 JSONDecodeError**。

但 **`StoreDelete` 只删 `<name>.json`，不删 `.bak`**（`sys.rs:222-232`），
全仓库也没有任何清理 `.bak` 的逻辑。于是：

| 事实 | 后果 |
| --- | --- |
| `ai.json` 的 `.bak` 里是**明文 `apiKey`** | 磁盘上留下一份明文 |
| `StoreList` 只列 `.json`（`sys.rs:126-128`） | 界面上**看不到**它 |
| 诊断包只收 `.json`（`sys.rs:287`） | 导出时**也不会**带上它 |

**所以这不是泄漏到外部，是"删了以后磁盘上还留着"** —— 对共享机器上的用户是有意义的差别：
他以为"清掉本地登录态 / 删除 AI 配置"就干净了，实际 `ai.json.bak` 还在。
**准确的说法**：`StoreDelete` ≠ 抹除；要真正抹掉得手工删 `<name>.json.bak`。

> 这条属**待修**（不是待澄清）：要么删除时一并清 `.bak`，要么在界面上说明。
> 归属 B 面（`sys` 是宿主对象，但触发它的是前端设置面板）—— 已登记，
> 见 [PROJECT-BOARD.md](../PROJECT-BOARD.md) §3 R7 的同类清单。

### 2.3 一条仍然成立的自检：`account` 的信息不泄漏

`account.rs:855` 附近有一条断言：`account.Info()` 的返回文本里**不得包含 `tokenProtected`**
（即密文字段本身）。也就是说"给页面看的视图"经过一次**显式检查**，不是靠自觉。

---

## 3. 两个宿主之间的可移植性

| 数据 | 能否跟着用户走 | 原因 |
| --- | --- | --- |
| `search.json`（含 Wolfram App ID）、`account.json`（token）、`update.json`、窗口 / 工作区 / 历史 | ✅ **能** | 字段同名、格式相同；Rust 侧还给每个字段加了 PascalCase `alias`，对齐 C# 的 `PropertyNameCaseInsensitive` |
| **`ai.json` 的密钥** | ❌ **不能** | C# 写的是 `apiKeyProtected`（DPAPI 密文），Rust/TS 侧读的是 `apiKey`（明文）—— **两种形式互不通用** |

**结论**：从 C# 宿主演进过来的用户，**只有 AI 这一项要重填密钥**，其余配置不用动。
这是架构变更的直接后果，**不是 bug**（[HOSTS.md](HOSTS.md) §3）。

---

## 4. 日志与崩溃：本地、不上报

| 项 | 事实 |
| --- | --- |
| 目录 | `%LOCALAPPDATA%\MFMath\logs`（**一定可写**） |
| 常规日志 | `app.log`，单文件上限 **2 MB**，轮转成 `app.1.log` |
| 崩溃日志 | `crash-*.log`：环境 + 异常 + **`app.log` 尾部 200 行** —— 单文件即可复盘；**只留最近 20 个** |
| 与旧宿主的关系 | **共用同一个 `app.log`**，所以两边的时间线对得上；"导出诊断包"要能把日志尾部一起带走 |
| **上报** | **不联网上报**（[DECISIONS.md](../DECISIONS.md) D-008）。只有用户主动"导出诊断包"才会交出去 |

> 设计意图写在 [DESIGN.md](../DESIGN.md) §2 ⑤：数学工具的用户不该因为一次崩溃被上传任何东西。

---

## 5. 这段边界怎么复查

```powershell
# ① DPAPI 往返（无头，不起窗口）：期望 10/0
& $run\mfmath-host-rust.exe --selftest-common

# ② 当前只有两处 DPAPI 调用点（AI 不该在列表里）
Select-String -Path MFMath.Host.Rust\src\*.rs -Pattern 'dpapi::(protect|unprotect)'

# ③ 导出/诊断是否剥掉密钥字段
Select-String -Path MF_UI\MFMath.UI.Vue\src\lib\settings\io.js -Pattern 'CREDENTIAL_FILES|SECRET_FIELD'
```

**判据**：② 应该只有 `account.rs`、`search.rs`、`selftest.rs` 三处。**出现 `ai.rs` 就说明有回退。**

---

## 6. 如果哪天要回退 AI（回退点在哪）

回退点很清晰：宿主侧恢复 `ai` 对象（revert 删它的那一笔），前端把 `relay.ts` 换回"经 `ai.Begin` 转发字节"，
密钥回到 DPAPI 密文。

> ⚠ **但要先回答一个问题**：那时用户的密钥**已经明文存在 `ai.json` 里了** ——
> 回退时要么重新加密一次（读明文 → DPAPI → 写回），要么**承认"已经明文过"**。
> 这个选择不能靠技术默认，得由所有者拍板。
