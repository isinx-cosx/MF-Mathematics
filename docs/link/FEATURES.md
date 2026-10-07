# 链接层承载的功能（搜索 / 账号 / 更新 / 备份 / 控制台）

> **本文只回答一个问题：那几个"要联网、要落盘、要跑外部程序"的功能，各自怎么落在这条缝上。**
>
> 契约与接缝见 [README.md](README.md)；方法清单见 [OBJECTS.md](OBJECTS.md)；
> 异步与推送见 [JOBS-PUSH.md](JOBS-PUSH.md)；凭据边界见 [CREDENTIALS.md](CREDENTIALS.md)。
>
> **本文接替 4 份旧的 `.NET` 侧文档**（它们写的是已废弃的实现）：
> `docs/ONLINE-SEARCH.md`、`docs/ACCOUNT.md`、`docs/UPDATE-CHAIN.md`、`docs/SETTINGS-BACKUP.md`。
> 退役理由与顺序见 [PROJECT-BOARD.md](../PROJECT-BOARD.md) §3 **R7**。

**核对时间**：2026-10-07 · **权威源**：`MFMath.Host.Rust/src/{search,console,account,site,update,sys}.rs`（行号按实测文件）

---

## 0. 一张表看全

| 功能 | 宿主对象 | 慢活怎么回 | 落盘在哪 | 凭据 |
| --- | --- | --- | --- | --- |
| 联网搜索 | `search`（12） | `Start` 立即回 `requestId`，结果走 **push** | `search_cache.json`（缓存）、`settings/search.json`（配置） | Wolfram App ID = **DPAPI 密文** |
| 用户系统 | `account`（19） | 全部同步（网络调用有超时） | `settings/account.json` | token = **DPAPI 密文** |
| 更新链 | `update`（6） | 全部同步 | `settings/update.json` | 无 |
| 设置 / 备份 / 诊断 | `sys`（8） | 全部同步 | `settings/<name>.json` | 备份与诊断**都排除**凭据 |
| 控制台 + 组件 | `con`（10） | `Install`/`Start` 立即回 id，进度走 **push + 轮询** | `components/`、`console/` | 无（组件包过 **SHA-256**） |

---

## 1. 联网搜索（`search`）

### 1.1 三个后端

| 引擎 | 形状 | 备注 |
| --- | --- | --- |
| `duckduckgo`（**默认**） | IA JSON + HTML 两路，**共享一份超时预算** | 无需密钥；HTML 结构变了会 `parse` 失败 |
| `wolfram` | `GET /v1/result`（纯文本） | 需要 App ID；无 key 或 401/403/501 一律归 `config` |
| `custom` | SearXNG 形状的 JSON（`/search?q=…&format=json`） | 基址**刻意比旧实现更严**：必须 http/https，且**不许含 `?` `#` `@`** |

> 📌 **`custom` 走的是 `site::get_verbatim`，刻意绕开 `normalize_base_url`** ——
> 因为后者对坏值会"退回内置站点"，那等于**把用户的查询词发到我们自己的服务器**。
> 这是隐私闸门，不是洁癖（`search.rs:1367-1369`）。

### 1.2 失败分类（六类）

| kind | 什么时候 | 界面给的下一步 |
| --- | --- | --- |
| `config` | 没填 App ID / 自定义端点非法 / Wolfram 说 App ID 无效（401/403）或没理解查询（501） | 去设置里补，或换引擎 |
| `network` | 连不上、TLS 失败、连接中断 | 检查网络/代理，或换引擎 |
| `http` | 端点非 2xx（含 DDG 反爬的 202/403、限流 429） | 稍后再试，或改用自定义端点 |
| `parse` | 返回形状不是我们要的（改版、或自定义端点没开 `format=json`） | 改用自定义端点 |
| `timeout` | 超过设定秒数 | 调大超时，或换引擎 |
| `aborted` | 用户按了停止 | 已取消 |

> ⚠ **`search` 把 `unauthorized`(401/403) 与 `ratelimit`(429) 都并进 `http`**，
> 而 [`account`](#2-用户系统account) 把它们分开。**两个对象的 kind 词表不一样** ——
> 写"链接层统一的失败词表"是错的。

### 1.3 缓存

| 项 | 事实 |
| --- | --- |
| 文件 | `%LOCALAPPDATA%\MFMath\search_cache.json`（JSON 数组） |
| 键 | `<engine>|<规范化查询>`（规范化 = 折叠空白 + 转小写）。**v1 的缺陷就是键里没有引擎** |
| TTL | 从配置读，单位小时，**0 = 不过期**；判定是 `age > ttl`（严格大于） |
| 上限 | **200 条，写死不可配**；超了按 `at` 淘汰最旧 |
| 空结果 | **不写缓存**（下次还会重试） |
| `noCache:true` | **只跳过读，成功仍会写** |
| 坏文件 | 视为空缓存，**绝不阻断搜索** |
| 落盘 | 临时文件 + rename（原子） |

### 1.4 结果与限流

- 结果条数默认 **8**，钳在 1–20；DDG 的**扫描**上限是 `max*8+32`（扫描上限 ≠ 结果上限）；
- 解析是**手写扫描**而不是正则（`regex` crate 不支持旧实现那条反引用）；摘要**按下标与标题配对**，不按邻近；`href` 解实体后还原跳转，非 http(s) 一律丢（`javascript:` / `data:` 丢弃）；
- 文本清洗的顺序是**有意的**：先去 `<script>`/`<style>` 整块 → 把标签换成空格 → **再**解实体 → 折叠空白。反了会把 `&lt;b&gt;` 当标签删掉。实体表是 HTML4 全集；
- **限流 / 去重 / 并发闸门：都没做。** 每个 `Start` = 一个新线程 + 一串新请求，唯一抑制是缓存命中。

### 1.5 有意不做（代码里没有，且注释写了理由）

1. **不做翻页**（没有 page/offset 参数，只有一页）；
2. **不做网页正文抓取**（只用引擎给的 snippet，绝不二次请求结果页）；
3. **不做请求去重 / 限流 / 退避**；
4. **不允许页面覆盖端点** —— 理由是"页面能改端点 = 能把 App ID 发到任意地址"；
   端点只能用环境变量 **`MF_SEARCH_ENDPOINTS`** 覆盖（JSON，键大小写不敏感，**进程内只解析一次**）；
5. **设置面板的"发往哪里"文案是写死的**（`search.rs:1556-1560`）—— 即使运维把端点指到内网镜像，
   面板仍显示内置域名。**真实生效端点看 `Info().endpoints`**。这是**有意**的：否则端到端用例里
   "隐私行写明发往哪里"那条断言就失去意义。

### 1.6 取消的语义

`Cancel` / `CancelAll` **只置标记**：阻塞式客户端没有中断句柄，**已在飞的请求不会被强杀**，
响应回来后被丢弃，推 `search.error{kind:"aborted"}`。**措辞别写"中止请求"。**

### 1.7 两个必须知道的坑

- **`SelfCheck()` 不是只读的**：它的第 ④ 项会 `cache_put("__selftest_a__", …)`，而 `cache_put`
  会把整表**写回真实的 `search_cache.json`**，且**不检查 `cacheEnabled`**。
  也就是说**关掉缓存也会被写进一条假条目**。
- **模块注释与实际相反**：`search.rs:1093-1094` 说"请求头是共享客户端那份，
  不是搜索专用的浏览器 UA"，**实际三个后端全部显式用浏览器 UA**（否则 DDG 反爬 403）。
  **不要照抄那条注释。**（已登记，见 §7）

### 1.8 三个"静默"行为（调用方会踩）

| 行为 | 事实 |
| --- | --- |
| **非法引擎名被静默改回** | `Configure({engine:"google"})` 返回 `{ok:true,changed:1}`，但 `normalize()` 把非法引擎**静默改回 `duckduckgo`** —— **返回值说改了，实际改成了别的** |
| **超长查询被静默截断** | 上限 500 字符，超了**直接截断，不报错、不提示**（注释只说"超长查询对端也是白费"） |
| **`Configure` 只认类型对得上的字段** | 一个都没给 → `{ok:true,changed:0}`；它保存的是**整份配置**，所以不会把已有 App ID 弄丢 |

> 附带两条返回形状：`Info()` 与 `CacheStats()` **都没有 `ok` 字段**
> （前端靠 `"engine" in info` 判断），见 §6.1。

---

## 2. 用户系统（`account`）

### 2.1 端点与请求形状

| 方法 | 端点 | Content-Type | 认证 |
| --- | --- | --- | --- |
| `Login` / `LoginEx` | `POST /api/login` | **form** | 无 |
| `Logout` | `POST /api/logout` | form（空 body） | Bearer |
| `RefreshProfile` | `GET /api/me` | — | Bearer |
| `RefreshToken` | `POST /api/token/refresh` | form | Bearer |
| `Register` | `POST /api/register` | **JSON** | 无 |
| `SendCode` | `POST /api/send-code` | **JSON** | 无 |
| `VerifyCode` | `POST /api/verify-code` | form | 无 |
| `ResendCode` | `POST /api/resend-code` | form | 无 |
| `ChangePassword` | `POST /api/change-password` | form | Bearer |
| `LoginHistory` | `GET /api/login-history` | — | Bearer |
| `SiteVersion` | `GET /api/version` | — | **无 token** |

**形状细节**：`remember` 为真才**加**字段 `remember=1`，为假时**整个字段不出现**（不是 `=0`）；
`Register` 把页面传来的 JSON **原样转发**（宿主不做字段过滤）；
改密成功后返回固定 note，**如实说明"站点行为是已登录会话不会立刻失效"**，不谎称已踢下线。

> ⚠ **`SiteVersion` 与 `update.Check` 的形状不同**：前者**没有** `current`/`sha256`/`size`/
> `sha256Reason`/`note`/`changelogUrl`。写成"同一个返回"就错了。

### 2.2 脱敏边界

`Info()` 暴露：`baseUrl` `timeoutSec` `remember` `autoRefresh` `loggedIn` `username` `email`
`balance` `hasAiService` `role` `isActive` `sessionExpiresAt` `sessionExpiresInSec`
`profileVerified` `profileCheckedAt` `offline` `dpapiAvailable` `tokenSource`
`busy` `lastError` `lastErrorKind` `configPath`。

**没有** `tokenProtected`、**没有** `access_token`、**没有** token 本体。
`Configure` **只能改 4 个字段**（`baseUrl`/`timeoutSec`/`remember`/`autoRefresh`）——
页面**无法**注入 `tokenProtected`/`username`。

自检第 ⑤ 项钉住这条：断言 `Info()` 文本里**不含** `access_token`、**不含** `tokenProtected`、
**不含** token 本体三个字符串。**三处端到端断言**同时守着：脱敏视图、落盘文件（**应该**是密文）、页面 DOM 搜不到 `eyJ…`。

> ⚠ 这条断言查的是**字符串包含**，而 `Info()` 里有服务端原文 `lastError` ——
> 若站点在 detail 里恰好回了 `access_token` 字样，自检会**误报**。属自检脆弱性，不是泄漏。

### 2.3 ⚠ 什么时候会清掉登录态（**修正一条流传的说法**）

`clear_token()` 只有 4 个调用点：`ClearLocal`、`Logout`、`RefreshProfile` 与 `RefreshToken`
收到 `kind == "unauthorized"`。

而 **`unauthorized` = 401 **或** 403**（`site.rs:178`）。所以准确表述是：

> **401 或 403 才清登录态**；404 / 429 / 5xx / 网络 / 超时**都不清**。

`docs/OPEN-ITEMS.md:44` 写的"只有 401 才清登录态"**与代码不符**（403 同样会把用户登出）。

另有两条容易误判的：
- **登录失败不会清掉已有登录态**；
- **`Logout` 不会清 `username`/`email`/`balance`** —— 登出后 `loggedIn=false` 但 `username` 还是上一个人。
  要真正抹掉得调 **`ClearLocal`**。**这是共享机器上的隐私残留**，两者语义不同，文档必须显式区分。

### 2.4 记住我与静默续期

- 到期时刻：优先响应里的 `expires_in`；拿不到才解 JWT 的 `exp`（**不校验签名，这是故意的**）；
  两者都没有 → `session_expires_at = 0`；
- "记住我 = 30 天"是**站点侧**给的，宿主自己**没有**任何"30 天"常量；
- `EnsureFresh(thresholdSec)`：前端固定传 **300**，宿主缺参默认也是 **300**。语义：
  `autoRefresh=false` 或没 token → `false`；拿不到到期时间 → `false`；离到期超过阈值 → `true`；否则尝试续期；
- ⚠ **"未登录"与"续期失败"都返回 `false`，调用方无法区分**；
- ⚠ **站点若既不给 `expires_in` 也不是 JWT，静默续期永不触发**（静默不发生，不是报错）。

### 2.5 离线与降级（四条纪律的第一条）

**不需要网络**：`Info`（自检断言它 **< 50 ms**，且它**只读内存/本地缓存**）、`Configure`、
`ClearLocal`、`Busy`、`CancelAll`、`SelfCheck`。
**未登录、不登录、断网、站点挂了 —— 本地全部计算功能照常可用。**

| 场景 | 降级行为 |
| --- | --- |
| 取资料失败 | 保留上次缓存的 `username/email/balance`，只置 `profileVerified=false` + `offline=true`（界面标"未校验"） |
| 登录成功但 `/api/me` 失败 | **不回滚登录**（token 有效就是有效），只标未校验 |
| `Logout` 时服务器不通 | **照样清本地**（否则断网退不出去），返回 `serverNote` 说明该 token 有效期内仍可用 |
| DPAPI 不可用 | token **只留进程内存**，登录仍成功，返回值带 `warning`；**绝不写明文** |

其它纪律：**不合并失败**（八类 kind 分开，服务端原话原样显示）；
**站点地址是安全边界**（只接受 http/https，带 `?`/`#`/`@` 一律退回默认站点 —— 这个值决定 token 发往哪里）。

**两个小坑**：`timeoutSec` 的夹取是"**跳过 5**"而不是"夹到 5"（配 3 秒 → **变成 20 秒并落盘**）；
`Busy` **只反映登录这一件事**（注册、续期、取资料、改密都不会让它变 true），且**前端不调它**。

### 2.6 本站无关的一件事：`token_version`

**宿主侧零实现**（全仓库 Rust 源码一处都没有，只有文档提到它）。它是**站点侧的会话版本号**。
**不要把它写成宿主行为** —— 只能写"站点侧特性、宿主无关"。
`docs/OPEN-ITEMS.md` / `docs/STATUS-and-ROADMAP.md` 里的相关说法属 R7 债。

---

## 3. 更新链（`update`）

### 3.1 三条边界

| 做 | **不做** |
| --- | --- |
| 查站点版本、与本机比较 | ❌ 自动下载安装包 |
| 显示 `sha256` / 大小 / 版本差异 | ❌ 自动运行安装包 |
| 把下载页交给**系统浏览器**（http/https） | ❌ 自己实现下载器或静默安装 |

**理由**（`update.rs:4-5`）：自动执行安装包等于给自己装一条"下载并运行可执行文件"的通路。
**少一个通路少一片攻击面**，而用户点一下浏览器的代价极小 —— 而且他能在浏览器里看清下载的是什么。
`Info().policy` 会把这句话原样带给界面。

### 3.2 ⚠ `sha256` **只显示，不校验**

这一点必须写准，否则会被读成"已校验"：

- `parse_version_body` 只是把站点给的 `sha256` **透传给界面显示**；
- 站点没给就返回 `null` **并附上原因**（`sha256_reason` 或默认"站点没有提供校验值"）——
  **绝不给空串**让界面显示成"已校验"；
- 全仓库 `pack::sha256_eq` 的调用点只有：**组件**安装包解压前的整包校验、以及两处自检。
  **更新链一处都没有** —— 与"不提供下载"是自洽的：**没有下载物，就没有可比对的对象**。

### 3.3 版本比较：比的是**关系**，不是"不同"

站点 `/api/version` 现在报的是 **1.2.0**（v1 的版本），而应用声明 **2.0.0**。
按"版本不同就算有新版"，v2 用户会被提示升级到 1.2.0 —— **那是降级**。所以：

| `relation` | 界面 | 说明 |
| --- | --- | --- |
| `newer` | 顶栏徽标 + 差异 + 下载入口 | **只有这一种**才叫"有更新" |
| `same` | 「已是最新版本」 | — |
| `older` | 「站点上的版本（1.2.0）比本机旧」+ 原因 | **不提示下载** |

比较是**逐段比数字**（`1.10.0 > 1.9.9` —— 字符串比较会搞错这个）；带 `-` 后缀的预发布
**小于**同号正式版。两类样例都在自检里。

> 📌 **发布 v2.0 的动作项**：要把站点 `src/lib/constants.ts` 的 `VERSION` 改成 `2.0.0`，
> 否则本机会一直显示"站点上的版本比本机旧"。**这是站点数据，不是代码缺陷** ——
> 但忘了它，用户就不会收到任何更新提示。

### 3.4 下载地址的唯一闸门

`PreviewDownloadUrl` 与 `OpenDownloadPage` **共用同一条解析**：

- 空 → 拒；
- **带协议**（`^[A-Za-z][A-Za-z0-9+.\-]*:`）→ 过 `shellopen::is_allowed`（**只放行 http/https**）；
- **不带协议** → 过 `looks_relative_safe` 后拼到当前 `baseUrl`。
  该检查拒绝：空、带协议、`//` 开头、含空白、含 `\`、含 `..`、含 `:`。

> 这个函数**独立成函数就是为了能被自检单测** —— 起因是拼接逻辑曾把
> `javascript:alert(1)` 拼成一个合法的 http URL，让协议闸门形同虚设。

**两者成功时的键名不同**：`PreviewDownloadUrl` → `{ok,url}`（**只算不开**）；
`OpenDownloadPage` → `{ok,opened}`（真的调 `ShellExecuteW`）。

### 3.5 取消与"没有入口"

- `update.CancelAll` = `site::cancel_all()`：**语义是"新的请求不再发起"，已在飞的那一个不会被强杀**
  （阻塞客户端没有中断句柄）。而且它有一个**闩锁**副作用，见 §6.3；
- **没有任何自动下载 / 执行安装包的入口**：`UPDATE_SPEC` 只有 6 个方法，
  地址解析是**内部函数、不是宿主对象方法**。宿主侧唯一"执行外部程序"的原语是
  `shellopen::open`，被 http/https 闸门锁死。
  ⚠ `docs/UPDATE-CHAIN.md:48` 把 `ResolveDownloadUrl` 列成桥面方法 —— 那是旧 `.NET` 桥面，**页面调不到它**。

### 3.6 仍未做（**与"永不做"要分开写**）

- **未做**：更新回滚、增量更新、静默安装；站点侧仍是"一个安装包一个地址"，没有通道（beta）与历史版本列表。
- **永不做**：自动下载 / 自动执行安装包（§3.1）。**别把这两类混成一句"以后会做"。**

---

## 4. 设置 / 备份 / 诊断（`sys`）

### 4.1 存储契约

存到 `%LOCALAPPDATA%\MFMath\settings\<name>.json`，`<name>` 必须匹配 `[a-z0-9_-]`、非空、≤40 字符。

| 方法 | 返回形状（**注意不一致**） |
| --- | --- |
| `StoreList` | **裸 JSON 数组** `[{name,bytes,mtime}]`，只列 `.json`；目录不存在视为空数组；**其它 I/O 错误返回对象 `{"error":…}`** —— 前端正是按"**不是数组**"识别错误 |
| `StoreRead` | `{ok:true,exists:false}` / `{ok:true,exists:true,json:"原文"}` / `{ok:false,corrupt:true,error}`（解析失败**保留原文件不动**） |
| `StoreWrite` | 先校验 name、非空 body、**body 必须是合法 JSON**；写 `.tmp` → 原文件复制成 `.bak`（**备份失败不阻断写入**）→ **原子 rename 替换** |
| `StoreDelete` | 删 `<name>.json`；不存在也返回 `{ok:true}`。**不删 `.bak`**（见 [CREDENTIALS.md](CREDENTIALS.md) §2.3） |

> **为什么要这么绕**：v1 直接 `open(path,"w")`，**写一半崩掉下次必然 JSONDecodeError**。
> 所以现在是"先备份 + 临时文件 + 原子替换"。

**哪些数据走它**：`account.json`、`search.json`（宿主侧）；**`ai.json`（调用方是前端）**。
**Rust 侧没有 `ai.rs`** —— AI 不是宿主对象，前端判定"AI 是否就绪"的依据就是 `sys` 对象在不在。

### 4.2 设置备份：包里有什么

| 进备份 | **不进备份** |
| --- | --- |
| 设置文件：历史、工作区、会话记录、教程进度、更新偏好（`settings\*.json`） | **`ai.json`**（AI 的 API Key，**明文**） |
| 外观偏好：`localStorage` 里 `mf_` 前缀的键（主题/形状/密度/字体/跟随系统） | **`account.json`**（登录 token 密文） |
| 包元数据：`app`/`kind`/`version`/`exportedAt`/`appVersion`/`excluded`/`stripped` | **`search.json`**（Wolfram App ID 密文） |

**两道防线，都是可见的**（写进包里，不是悄悄处理）：① 整份排除并记进 `excluded`；
② 对其余文件再做**字段级剥离**（字段名命中 `protected / password / secret / token / apikey`
就不写，剥掉的记进 `stripped`）。

**为什么密钥干脆不带**：DPAPI 密文换台机器也解不开，搬过去只是一串没用的字节，
却会让人误以为"密钥跟着走了"。**换机时密钥应当在新机器上重新填一次。**

### 4.3 导入的两条性质（都有断言守着）

1. **不会清掉你现在的凭据**：导入只写包里存在的文件，而那三个凭据文件**永远不写** ——
   即便有人手改备份把 `ai.json` 塞进去，也会被跳过并报告（`skipped`）；
2. **坏包一律拒绝，且不部分写入**：`app`/`kind`/`version` 任一不对就**整包拒绝**并给可读原因
   （"这不是 MF-Mathematics 的设置备份"、"备份来自更新的版本（v99）；请先更新软件再导入"）。
   **拒绝发生在写第一个文件之前**，所以磁盘状态不变。

**生效时机**：设置文件与外观偏好都在**启动时**读取，所以界面如实说"**重启后全部生效**"，
不假装即时生效。

### 4.4 诊断包

写到 `%LOCALAPPDATA%\MFMath\diagnostics-yyyyMMdd-HHmmss.txt`，分段包含：
宿主与环境、引擎产物清单、设置文件列表、**除凭据外的设置文件原文**、
`app.log` 尾部 200 行、**最新一份崩溃记录全文**。

**跳过凭据的名单**：`["ai","account","search"]`，**外加**"文件名含 `secret`"的兜底。

> 📌 **这里记着一个真实的坑**：宿主原先**只按"文件名含 `secret`"跳**，
> 而这三个文件**一个都不含 `secret`** —— 等于没跳，会把 API Key、登录态、Wolfram App ID
> 整份打进诊断包。**"规则写对了"和"规则真的命中"是两件事。**

**边界**：不做云同步（备份是本地文件，用户自己保管）；不做增量/合并（导入是"覆盖同名文件"，
先确认再执行）。

### 4.5 `OpenPath` 的约束（以及一处不够严的地方）

白名单 = 数据目录 / exe 目录 / 组件目录三个根；目录用 `explorer.exe <path>`，
文件用 `explorer.exe /select,<path>`；不存在则报错（**不会"创建式打开"**）。

⚠ 实现是**小写化的字符串前缀**，**没补路径分隔符**、也没 `canonicalize`。
因此**同前缀的兄弟目录必然通过**检查。实际危害有限（`explorer.exe` 只打开或选中，不执行目标），
但与"只允许打开白名单内的路径"的注释**不完全相符**。**已登记**（见 §7）。

---

## 5. 控制台与可选组件（`con`）

### 5.1 语言与组件来源

- **语言只有两种**：`python` 与 `cpp`；**非 `cpp` 一律当 Python**（含空串、拼错的名字 —— 这是照旧行为保留的）；
- **组件清单是编译进代码的常量，没有远程清单**：`python 3.13.15`（包 **11,009,825** 字节）。
  `mingw 16.1.0`（包 **54,084,880** 字节）。期望 SHA-256 与字节数也是内置常量。
  ⇒ **服务端换包必须发新宿主**（除非在包旁边放一个同名 `.sha256` 旁文件，以旁文件为准）；
- ⚠ **下载路径里的组件名与安装用的名字不同**：安装/卸载用 `cpp`，
  但下载路径是 `{base}/download/component/**mingw**`。两个名字都要交代。

### 5.2 安装 / 卸载 / 取消

- **安装**：找包（先缓存，再 exe 目录）→ 没有就下载 → **SHA-256 校验** → 解压到 `.staging`
  （自带路径穿越防护，**任何一条不安全就整包失败**）→ 补门面文件 → 校验关键可执行文件存在 → **替换目录**；
  - C++ 额外做三件：`flatten_single_root`、拷贝头文件、**现场生成导入库**
    （写 `.def` 导出 `function_exists` / `math_call` 两个符号 → 跑 `dlltool` → 校验 `.a` 存在）；
  - ⚠ 安装作业的**初始状态必须是 `"running"`**：注释记着，用 `"queued"` 初值会让**第一次轮询就以为装完**
    （`console.rs:372-379`）；
  - ⚠ **未知组件名也照样返回一个 `jobId`**，失败延后到 `state="error"`；
- **卸载**：只认 `python`/`cpp`；成功返回**删前体积**；删失败（例如控制台正有进程在用）返回系统错误原文；
  **不删 `cache/`** —— 重装能省一次下载；
- ⚠ **取消不打断解压阶段**：只在少数检查点生效（请求前、下载循环每轮、写盘每 1 MiB 块之间），
  **校验 / 解压 / dlltool / 替换目录完全不响应取消**；
  而且**取消是用 `state="error"` 承载的**（文案"已取消安装（已下载的部分保留着，下次接着下）"）。
  **没有独立的 `cancelled` 状态**；注释也承认"取消可能表现为作业最终还是 success"；
- ⚠ `CancelInstall` 的返回键是 **`canceled`（单 L）**，且"**id 不存在**"与"**标记没设上**"返回**同一个值**；
- **失败/取消的清理**：删 `.staging`，**保留 `.part`**（那是续传凭据）；
- **没有并发保护**：没有"同一组件只允许一个安装作业"的闸门（实际后果**未证实**）。
- **下载基址**：初始值取环境变量 **`__MF_COMPONENT_BASE` 优先，其次 `MF_COMPONENT_BASE`**；
  运行时由 `SetDownloadBase` 覆盖，**会话级、不落盘**。

### 5.3 下载与断点续传

- 进度存 `<包名>.part`，带 `Range: bytes=<have>-`；
  **`200`（服务端忽略 Range）→ 丢弃已下字节、从头写**；`416` → 删 `.part` 重来；最多 **3 轮**；
- **`Accept-Encoding: identity` 是断点续传正确性的前提，不是可选优化** ——
  否则透明解压会让 Range 偏移与落盘字节不是同一套坐标，拼出坏文件；
- 单请求整体超时 **1800 s**（Rust 侧新增的上限）；
- 校验失败**保留 `.part`**，不进解压；
- ⚠ **进度百分比非单调**：下载阶段上限 81，但随后校验把 percent **置为 8** ——
  用户会看到进度条**从 ~81% 跳回 8%**。是遗留还是有意，**代码没说**。
- **下载源故意没有 https/host 白名单**：理由是包要过 SHA-256 才进解压，
  且本机端到端用例正是用 `http://127.0.0.1:<port>` 验断点续传，加白名单会打死那条用例。
  **别把它写成"安全漏洞"。**

### 5.4 运行（`Start` / `Poll` / `Stop`）

- 状态机：`state: queued → running → done`；`stage: queued → [compiling] → running → done`；
  **`exitCode` 在 `done` 之前是 `null`**；
- 工作目录 `%LOCALAPPDATA%\MFMath\console\run<N>`（`console\` 只在本进程**第一次运行**时清一次）；
- Python：写 `main.py` + 引导脚本（显式 `sys.path.insert`，绕开嵌入式 CPython 的隔离模式），
  子进程超时 **60 s**；
- C++：编译参数含 `-include mfmath_autorun.hpp`（**强制**，让 stdout 边写边落管道），
  编译超时 **120 s**、运行超时 **60 s**；编译失败**不运行**；
- 退出码约定：组件未装 `-1`、宿主侧错误 `-2`（stderr 前缀 `[宿主错误] `）、缺 exe `-3`；
- **输出各上限 256 KiB**，按行读 + **有损 UTF-8**（一个坏字节不会吞掉后续输出）；
- ⚠ **`Poll` 每次返回的是完整累积缓冲，不是增量** —— 注释里那个"增量取回"描述的是**调用方式**，
  **不是数据形状**。写成"返回增量输出"会误导实现方去做拼接；
- **`Stop` 会真杀进程树**（`taskkill /PID <pid> /T /F`）—— 这与搜索/账号的"停止等待"**不是一回事**。
  但 `taskkill` 失败时**孙进程可能残留**，代码只记进日志、**不改返回形状**；
- **没有并发上限、没有队列、不拒绝**（有意保留旧行为）。

### 5.5 两个必须知道的坑

- **组件完整性判据不一致** → **"下拉里能选 C++，一跑就报缺件"**：
  `cpp.ready`（决定 C++ 是否出现在语言下拉）只检查 `lib\libmf_mathematics.a` + `include\mfmath.hpp`，
  而实际运行要求**三件**（还要 `include\mfmath_autorun.hpp`）。
  **只缺 `mfmath_autorun.hpp` 时，下拉里有 C++、点了却报"组件不完整"**。
- **两张内存表只增不减**：`RUNS` 与安装 `JOBS` **从不删除条目**，
  所以每个 `Start` 都把整个 `RunState`（可能含 ≤512 KiB 输出）**永久留在宿主内存里**。
  对比：搜索桥那边有 `MAX_JOBS=64` 的淘汰。**两个对象策略不一致。**

### 5.6 推送与轮询的分工（两个主题的"能带什么"）

| 主题 | 载荷 | 消费者 |
| --- | --- | --- |
| `component.install` | `{kind, jobId, state, percent, message}` —— 由进度观察线程每 **200 ms** 采样，**只在值变化时**推 | **设置页**的组件组；⚠ **控制台页不订阅它**，它用 400 ms 轮询 `InstallStatus` |
| `console.run` | `{runId, language, event, stage, state, exitCode, elapsedMs, timedOut}` —— `event` 实际只有 **`"stage"`** 与 **`"done"`** | 控制台页 |

两条必须知道的：

- **`console.run` 里不含 `stdout`/`stderr`** —— 页面收到推送只是"叫你去看"，**数据必须 `Poll` 取**；
- **没有 `queued` 的首次推送** —— 第一条通常是 `stage="running"`（Python）或 `"compiling"`（C++）。

前端把推送当"叫你去看"，收到就 tick 一次，轮询（有推送 500 ms、无推送 200 ms）作兜底。

### 5.7 三个容易写错的实现细节

| 细节 | 事实 |
| --- | --- |
| `-include mfmath_autorun.hpp` | C++ 编译参数里是**强制**的 —— 作用不只是引头文件，而是**让 stdout 边写边落管道**（否则输出要等程序结束才拿得到） |
| `PYTHONPATH` | **设了但没用**：嵌入式 CPython 的 `.pth` 强制隔离模式会**完全忽略**它（同一段注释自己写了"设了也白设"）。真正起作用的是引导脚本里显式 `sys.path.insert`。**别写"靠 PYTHONPATH 找到引擎"** |
| 临时目录 | `console\` 只在本进程**第一次运行**时清一次，不是启动时清 —— 理由是**卸载程序可能运行在别的管理员账号下**，启动就删会删错人的目录 |

**另一条与"停止"有关的**：`Stop` 用 `taskkill /T /F` 杀**整棵进程树**；但 `taskkill` 失败时
**孙进程可能残留**，代码只把这个事实写进日志、**不改返回形状**（`{stopped:true}` 仍会返回）。

---

## 6. 跨这五个功能的共同约定与陷阱

### 6.1 返回形状的例外（**别写"一律 JSON"**）

| 方法 | 返回 |
| --- | --- |
| `con.Install` / `con.Start` | **裸 id 字符串**（`"job3"` / `"run4"`） |
| `search.Busy` | **裸布尔** |
| `mf.Ready` / `mf.FunctionExists` / `account.EnsureFresh` / `account.Busy` / `search.Busy` | **真布尔** |
| `StoreList` | **裸 JSON 数组**（错误时才是对象） |
| `search.CacheStats` / `con.SetDownloadBase` / `con.Poll` / `con.Stop` / `con.StopAll` / `con.CancelInstall` | **没有 `ok` 字段**（同一对象内不一致，调用方要逐方法处理） |

### 6.2 `SelfCheck()` 的 `ok` **恒为 true**

真正的总判据是 **`ok_all`**。判 `ok` 会**永远通过**。`account`、`search`、`update` 三个对象都是这个形状。

> ⚠ 附带两处过时标签：`account` 自检实际产出 **7** 项，而 `docs/ACCOUNT.md` 与
> `tests/cdp-account.mjs` 都写"6 项" —— 用例只断言 `ok_all:true`、**不数个数**，
> 所以**标签错了但一直是绿的**。

### 6.3 ⚠ 取消有三种语义，而且有一个"闩锁"

| 场景 | 语义 |
| --- | --- |
| job 通道 `CancelJob` | **停止等待 + 丢弃结果**（引擎会把这一步算完） |
| `search.Cancel` / `account.CancelAll` / `update.CancelAll` | **不再发起新请求**；已在飞的不强杀 |
| `con.Stop` | **真杀进程树**（`taskkill /T /F`） |

**闩锁**：`site::cancel_all()` 置一个**全局**取消标记；**只有两处会复位它** ——
`account.Configure` 与 `search.Start`。其它任何成功调用**都不会解锁**。后果：

> 用户（或脚本）点过一次取消之后，**`account`/`update`/`search` 的后续网络调用会一路返回
> `{"ok":false,"kind":"aborted"}`**，直到他改一次账号设置。

（前端目前**从不调** `account.CancelAll`，所以这条路径一般由用例或外部脚本触发。）

### 6.4 失败词表**不是全局统一**的

| 对象 | kind 取值 |
| --- | --- |
| `account` | `unauthorized` `ratelimit` `http` `timeout` `aborted` `network` + `config` `parse`（**8** 类） |
| `search` | `config` `network` `http` `parse` `timeout` `aborted`（**6** 类，`unauthorized`/`ratelimit` **并进 `http`**） |
| `update` | 走 `site` 层词表（**没有 `parse`/`config` 之说**，失败原样带 `kind`+`error`） |

`docs/ACCOUNT.md:96` 列的七类**漏了 `http`**（500/404/502 都会产出它）。

---

## 7. 本文核对出的"文档与现实不符"（都已登记）

写这份文档时逐条对照过源码，**下面这些是旧文档/注释与代码不符的地方**，
清单与处置归 [PROJECT-BOARD.md](../PROJECT-BOARD.md) §3 **R7**：

| # | 位置 | 问题 |
| --- | --- | --- |
| 1 | `docs/OPEN-ITEMS.md:44` | "只有 401 才清登录态" → **403 也会**（§2.3） |
| 2 | `docs/STATUS-and-ROADMAP.md:29`、`docs/OPEN-ITEMS.md:40-52` | 把 `token_version` 写成软件侧相关行为 → **宿主零实现**（§2.6） |
| 3 | `docs/ACCOUNT.md:96` | 失败分类漏了 `http`（§6.4） |
| 4 | `docs/ACCOUNT.md:106`、`tests/cdp-account.mjs:225` | "自检 6 项" → 实际 **7** 项（§6.2） |
| 5 | `docs/ACCOUNT.md:127-128` | 把"校验 sha256"归入"未做" → 设计上是**永不做**（§3.6） |
| 6 | `docs/UPDATE-CHAIN.md:48` | 把 `ResolveDownloadUrl` 写成桥面方法 → **内部函数**（§3.5） |
| 7 | `docs/UPDATE-CHAIN.md:28` | 版本比较写在 `UpdateBridge.CompareVersions` → Rust 在 `update::compare_versions` |
| 8 | `MFMath.Host.Rust/src/search.rs:1093-1094` | 注释说"不用浏览器 UA"，**代码用的就是**（§1.7） |
| 9 | `MFMath.Host.Rust/src/console.rs:9,26,1514`、`handlers.rs:104` | 说 `Poll` 是"增量取回" → **全量快照**（§5.4） |
| 10 | `MFMath.Host.Rust/src/account.rs:10-11` | 说续期失败"只标记需重新登录" → 401/403 时**直接清登录态**（§2.3） |
| 11 | `MFMath.Host.Rust/src/dpapi.rs:1,18` | 仍把 AI 的 API Key 列为 DPAPI 用户 → 已是**明文**（[CREDENTIALS.md](CREDENTIALS.md) §1） |

另有两条**代码行为本身**值得单独跟进（不是文档问题）：
**`con` 的 `cpp.ready` 判据少一件文件**（§5.5）、**两张内存表只增不减**（§5.5）。
