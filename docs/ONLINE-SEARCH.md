# 联网搜索（宿主侧 C#）

> 🚩 **已退役（2026-10-07）**：本文讲的是**已废弃的 .NET 宿主**实现（`SearchBridge.cs` 等）。
> **现役 Rust 侧的对应内容见 [`docs/link/FEATURES.md`](link/FEATURES.md) §1** ——
> 含三个后端、缓存键（键里必须含引擎）、六类失败分类与"有意不做"的完整清单。
>
> **本文暂不删除**：仓库里还有多处引用它（清单见
> [`docs/PROJECT-BOARD.md`](PROJECT-BOARD.md) §3 R8），等引用改完再删。
> **引用本文任何一处数字前，请先核对 `FEATURES.md`。**

> 落地于本轮。**抓取、解析、缓存、凭据全在宿主（C#）**；前端只是一个页面（`/tools/search`）。
> 三个后端：DuckDuckGo（免密钥）、Wolfram Alpha（自备 App ID）、自定义端点（SearXNG 兼容 JSON）。

## 1. 为什么放在宿主

与 AI 那条边界同源，三条理由：

| 理由 | 说明 |
| --- | --- |
| **凭据** | Wolfram 的 App ID 只在宿主（DPAPI 密文），页面只见 `hasWolframKey`。如果页面能改后端端点，它就能把 App ID 发到任意地址 —— 所以**端点覆盖走环境变量**（`MF_SEARCH_ENDPOINTS`），不从页面暴露 |
| **网络** | 页面跑在虚拟主机 `https://mfmath.local` 下，直连外部站点会撞 CORS；DDG 的结果页也不允许跨源读 |
| **一处实现** | 超时、取消、缓存、失败分类只写一遍；断网/被反爬/形状变了要能分开说 |

## 2. 结构

| 文件 | 职责 |
| --- | --- |
| `MFMath.Host/SearchBridge.cs` | 桥面：`Info/Configure/SetWolframKey/ClearWolframKey/Start/Cancel/CancelAll/Busy/OpenUrl/CacheStats/ClearCache/SelfCheck` |
| `MFMath.Host/SearchBackend.cs` | 三个后端 + 四个解析器 + 文本清洗 + 错误分类 |
| `MFMath.Host/SearchCache.cs` | 本地缓存（键含引擎、TTL、上限、原子落盘） |
| `MFMath.Host/SearchConfig.cs` | 配置与落盘（App ID 为 DPAPI 密文）；端点覆盖 |
| `src/lib/search/bridge.js` | 页面侧：发起查询、订阅 `search.done/error`、表达式提取 |
| `src/views/tools/SearchView.vue` | 搜索页（路由 `/tools/search`，读 `?q=` 直接开搜） |
| `src/components/settings/SearchGroup.vue` | 设置 → 搜索（引擎 / App ID / 自定义端点 / 超时 / 条数 / 缓存 / 隐私 / 自检） |

数据流：

```
页面 runSearch(q, engine) → 宿主 Start() 立即返回 {requestId}
  → 查缓存（键 = 引擎 + 规范化查询；命中则完全不出网）
  → SearchBackend 抓取（DDG：IA 摘要 + HTML 结果页；Wolfram：短答案；自定义：SearXNG JSON）
  → 解析成**纯文本**结果（去标签、解实体、截断）
  → PushHub: search.done{results, abstract, fromCache, elapsedMs} | search.error{kind, status, message}
```

## 3. 缓存：键里必须含引擎

如果缓存**只用查询词做键**，"用 A 引擎搜过 x"会让"用 B 引擎搜 x"直接命中 A 的结果 ——
换了引擎却不生效，而且看不出来。现在的做法是键里含引擎：

- **键 = 引擎 + 规范化查询**（去空白、折叠空格、小写）；
- **带 TTL**（默认 24 小时，0 = 不过期），过期当未命中；
- **有上限**（200 条，按时间淘汰最旧的）；
- 命中时界面显示「来自缓存 · 时间」，并提供「忽略缓存」强制重抓；
- **空结果不缓存**（下次还该再试一次）。

自检里有一条专门验它的样本：同引擎同查询命中、换引擎或换查询都不命中。

## 4. 失败分类（都能指导下一步，不是笼统一句"搜索失败"）

| kind | 什么时候 | 界面给的下一步 |
| --- | --- | --- |
| `config` | 没填 App ID / 没填自定义端点 / Wolfram 说 App ID 无效（401/403）或没理解查询（501） | 去设置里补，或换引擎 |
| `network` | 连不上、TLS 失败、连接中断 | 检查网络/代理，或换引擎 |
| `http` | 端点非 2xx（含 DDG 反爬的 202/403、限流 429） | 稍后再试，或改用自定义端点 |
| `parse` | 返回的形状不是我们要的（改版、或自定义端点没开 `format=json`） | 改用自定义端点 |
| `timeout` | 超过设定的秒数 | 调大超时，或换引擎 |
| `aborted` | 用户按了停止 | 已取消 |

**两个已修复的缺陷**（注释里都写了）：早期把 `OperationCanceledException` 直接当成"已取消"返回，
于是"慢速 + 短超时"被报成 aborted；去掉那个 catch 之后，`HttpClient` 抛的是
**`TaskCanceledException`**（OCE 的子类），又掉进泛型 catch 被归成 `parse`。现在显式 rethrow，
且这条 catch 必须排在泛型之前。

## 5. 安全

- **HTML 是不可信输入**：只抽文本（`StripTags` 去标签 + 解实体 + 折叠空白 + 截断），
  界面那边也只走插值。结果里的 `javascript:` / `data:` **链接一律丢弃**（自检有样本）。
- **结果链接不导航**：点「打开」走宿主 `OpenUrl`，**只放行 http/https**
  （`file:`、`ms-*:`、自定义协议全拒）—— 否则这就成了"用任意协议启动本机程序"的原语。
- **App ID 只写不读**：与 AI 密钥同一条规矩；面板上分开说"在不在"与"是不是明文落盘"。
- **查询发往哪里写在界面上**（`Info.endpoint`），隐私说明不是装饰。

## 6. 验证

| 用例 | 断言 | 结果 |
| --- | --- | --- |
| `cdp-search.mjs`（自带 `tests/fake-search-server.mjs`） | 页面与配置 · 三条后端（DDG 结果页 + IA 摘要 / Wolfram 需 App ID / SearXNG JSON）· 缓存命中不出网 + 忽略缓存 + **换引擎不误命中** · 异常分类（500→http、改版→parse、慢速+短超时→timeout、取消→aborted、空结果**不是错误**）· **App ID 不外泄**（脱敏视图/落盘密文/页面都读不到）且只发给配置的端点 · `OpenUrl` 协议闸门 · 结果里的表达式「算这个」送去计算页（由引擎算）· `?q=` 深链 · 自检五项 · 设置页分组 | **53 / 0** |
| `cdp-history-search.mjs`（更新） | 顶栏「搜索」现在跳到**真实页面**：有可用搜索框、引擎选择器、隐私行写明发往哪里；占位浮层已删除；侧栏「工具」里有入口 | 21 / 0 |
| `cdp-settings.mjs`（更新） | 搜索组已是真实设置（无待实现标记、写明发往哪里）；「占位必须说清依赖」这条覆盖挪到仍是占位的**更新**组 | 33 / 0 |
| 全套回归（18 个用例） | — | **561 / 0** |

**测试怎么跑**：宿主必须带 `MF_SEARCH_ENDPOINTS` 指向假端点（`run-all.ps1` 会设置）。
用例发现端点没指到本地时会**明确报错退出**，不会去连真的 DuckDuckGo —— 这也是"端点覆盖
只能由启动宿主的人设置"这条安全边界带来的副作用，是值得的。

## 7. 设计取舍

| 旧版行为（`MF_Online/` + `search_panel.py`） | 现在 | 为什么 |
| --- | --- | --- |
| 缓存键只用查询词 | **含引擎** | 换引擎不生效是"看起来能用、实际用错"的那类缺陷 |
| 没有 TTL | 有 TTL + 上限 + 清空 | 搜索结果的时效性强 |
| 结果面板是对话框 | **路由页面**（`/tools/search`） | 结果是内容：要来回看、要送进计算页、示例与教程需要落点 |
| 支持 DDG / Wolfram / 自定义三选一 | 同三个，但**失败分类可指导下一步** | 一句"搜索失败"没法让人决定下一步做什么 |

## 8. 已知边界

- **DDG 的结果页是 HTML**：官方没有稳定的免密钥 JSON 结果接口，所以这一路靠 HTML 结构。
  对方改版就会 `parse` 失败（界面会明说"形状变了"并建议改用自定义端点）。自检用内置样本
  盯住解析器，改版时至少能立刻看出是哪一层的问题。
- **自定义端点要求 SearXNG 形状的 JSON**（`/search?q=…&format=json`）。很多公共实例默认关掉了
  json 格式；自建实例要在 `settings.yml` 里打开 `search.formats`。
- **不做翻页**：只取前 N 条（默认 8，可在设置里调）。
- **不做"网页正文抓取"**：只显示搜索引擎给的标题/摘要/链接，不把结果页抓下来再解析 ——
  那会把"外部 HTML"的面积放大一个量级，收益却有限。
- **没有请求去重/限流**：同一查询连点会连发（缓存能挡住大部分，但 `noCache` 时不挡）。
