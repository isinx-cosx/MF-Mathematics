# 设置面板与工作区

> **本文只回答一个问题：设置面板与工作区：有哪几组设置、怎么存、怎么导入导出、工作区保存什么。**
>
> 与同层其它文档的分工：[README.md](README.md) 讲两个工程与构建链、[ARCHITECTURE.md](ARCHITECTURE.md) 讲 views/components/lib 分层与路由、[TOOLS.md](TOOLS.md) 讲控制台 / 函数工具箱 / 历史 / 搜索页（工作区三个页面里的控制台那一页在那边）、[AI.md](AI.md) 讲 `ai.json` 明文密钥的代价（备份为什么必须排除它）、[CHECKS.md](CHECKS.md) 讲构建闸门与用例纪律；宿主侧 `sys` 桥的逐方法契约在跨层文档 [../link/FEATURES.md](../link/FEATURES.md) §4。

---

## 1. 判据与产物

本文写于 **2026-10-07**，**没有运行宿主**（因此没有任何端到端实测），所以文中的事实只有三类来源：

| 来源 | 可信度 | 本文怎么标 |
| --- | --- | --- |
| 源码行 | 源码即契约；但注释可能是错的（见 §9） | `文件:行` |
| 可复跑命令 | 本机跑过，输出抄在下面 | 命令 + 输出 |
| 本机状态快照 | **不可当契约**（机器状态、可能是测试残留） | 明确标注"机器状态" |

复跑本文数字的命令（都在 `MF_UI/MFMath.UI.Vue` 下执行）：

```powershell
node -e "import('./src/lib/settings/catalog.js').then(m=>{const {GROUPS,ITEMS}=m;console.log('groups='+GROUPS.length+' items='+ITEMS.length);console.log(GROUPS.map(g=>g.id+'='+ITEMS.filter(i=>i.group===g.id).length).join(' '))})"
# groups=9 items=57
# appearance=6 calc=2 engine=6 components=5 ai=11 search=8 account=5 update=7 storage=7
```

```powershell
# 设置目录长什么样（**机器状态**，不是契约；这份是 2026-10-07 本机的样本）
Get-ChildItem (Join-Path $env:LOCALAPPDATA 'MFMath\settings') -File | Select-Object Name, Length
```

实测样本（当时目录里是这 8 个 stem）：`account` `ai` `ai-chat` `history` `prefs` `search` `update` `io-probe`，外加各自的 `.json.bak`。
其中 `io-probe.json.bak` 是 `tests/cdp-settings-io.mjs:185` 调 `StoreDelete` 之后的**残留** —— 它只删 `.json`、不删 `.bak`（`sys.rs:222-232`）；
**当时目录里没有 `workspace.json`**（该用例收尾会把用户的这份还原或删除，`tests/cdp-workspace.mjs:36-44,271-277`）。

---

## 2. 设置分几组、每组多少项

**9 组 / 57 项，全部 `status === "ready"`**（上面的命令；`catalog.js:17-27` 定义组、`:33-112` 定义项、`:114` 提供 `itemsOf`）。

| 组 id | 组名（`label`） | 项数 | 面板组件 | 该组的口径（`catalog.js` 的 `note`） |
| --- | --- | --- | --- | --- |
| `appearance` | 外观 | **6** | `components/settings/AppearanceGroup.vue` | 改了就生效，没有保存按钮 |
| `calc` | 计算与绘图 | **2** | `CalcPlotGroup.vue` | 改了就生效；非法范围退回自动并在行内说明 |
| `engine` | 引擎 | **6** | `EngineGroup.vue` | 出问题时用来自助排查 |
| `components` | 组件 | **5** | `ComponentsGroup.vue` | 可选下载的运行时 |
| `ai` | AI | **11** | `AiGroup.vue` | 密钥只存宿主（DPAPI）；流式输出走推送通道；默认只发表达式与结果 |
| `search` | 搜索 | **8** | `SearchGroup.vue` | 抓取与解析在宿主；App ID 只存宿主；缓存键含引擎 |
| `account` | 账号 | **5** | `AccountGroup.vue` | token 只存宿主；未登录 / 断网不影响计算 |
| `update` | 更新 | **7** | `UpdateGroup.vue` | 只提示 + 显示 sha256 + 把下载交给浏览器 |
| `storage` | 存储与数据 | **7** | `StorageGroup.vue` | 含导入 / 导出设置（凭据不进备份） |

> 各组 id 与项数由第 1 节的命令复跑得到；"组名"与"口径"照抄 `catalog.js:18-26` 的 `label`/`note`（**它是数据，不是注释**）。

**面板是一个容器，不是一页**（`views/settings/SettingsView.vue:2-15`）：

- 左侧分类导航 + 右侧内容，`GROUPS` 直接渲染，每行带 `x/y` 完成度（`SettingsView.vue:94-102`，`countOf()` 在 `:56-60`）；
- 顶部搜索做的是**跳到具体某一项**：命中后切组、滚到该行、高亮 1.8 秒（`SettingsView.vue:62-73`）；
  索引来自 `searchItems()`（`catalog.js:117-125`，按 `label` + `keywords` + `group` 分词全命中）；
- 深链 `/settings?group=<id>` 支持三种进入方式（初始、挂载、query 变化），只读 `onMounted` 会"点了没反应"（`SettingsView.vue:43-49`）；
- 未落地的组由 `PlaceholderGroup.vue` 兜底（`SettingsView.vue:126`），**当前没有 `pending` 组**（命令输出 `nonReady=0`）。

### 2.1 目录与界面之间有两处不一致

用命令比对"catalog 里的 id"与"渲染出来的 `data-setting`"，命中两处（第 9 节记债）：

| 现象 | 出处 |
| --- | --- |
| `components.python` / `components.cpp` 没有字面 `data-setting`，是**动态拼**的 —— 不是缺口 | `ComponentsGroup.vue:152` `:data-setting="'components.' + k.id"` |
| `appearance.language` 这一行**在界面上有、在 catalog 里没有** | `AppearanceGroup.vue:50` ↔ `catalog.js:33-40`（该组只有 mode/theme/shape/density/font/reset 六项） |

第二处的后果是可复跑的：`searchItems("语言")` 返回 `[]`（同一命令换成 `m.searchItems('语言')`），
所以**界面语言切换在设置搜索里搜不到**（`cdp-settings.mjs:103-105` 只断言那一行存在，没断言它能被搜到）。

---

## 3. 设置怎么落盘

### 3.1 桥面：前端只认 `hostObjects.sync.sys`

前端 `lib/settings/bridge.js` 把 `window.chrome.webview.hostObjects.sync.sys` 包了一层（`bridge.js:12-18`），
宿主侧现役实现是 **`MFMath.Host.Rust/src/sys.rs`**（`handlers.rs:259-273` 分发；`main.rs:90-93` 声明签名）。

| 方法 | 关键行为 | 出处 |
| --- | --- | --- |
| `Info` | `dataDir` / `settingsDir` / `appDir` / `hostVersion` / `componentBase` | `sys.rs:77-91` |
| `StoreList` | 只列 `.json`（stem 去掉扩展名）；目录不存在=空数组；**其它 I/O 错误返回 `{"error":…}`，不是数组** | `sys.rs:120-153` |
| `StoreRead` | `{ok:true,exists:false}` / `{ok:true,exists:true,json}` / `{ok:false,corrupt:true,error}`（**解析失败保留原文件**） | `sys.rs:157-174` |
| `StoreWrite` | 先校验 name、非空、body 是合法 JSON → 写 `.tmp` → 旧文件复制成 `.bak`（失败不阻断）→ `rename` 原子替换 | `sys.rs:189-220` |
| `StoreDelete` | 删 `<name>.json`；不存在也 `{ok:true}`；**不删 `.bak`** | `sys.rs:222-232`，残留后果见 [CREDENTIALS.md](../link/CREDENTIALS.md) §2.3 |
| `OpenPath` | 白名单 = 数据目录 / exe 目录 / 组件目录三个根 | `sys.rs:58-72, 237-256` |
| `ExportDiagnostics` | 写 `dataDir\diagnostics-<stamp>.txt` | `sys.rs:260-319` |

**路径**：`settingsDir = dataDir/settings`（`sys.rs:31-36`），`dataDir = %LOCALAPPDATA%\MFMath`（`logging.rs:29-36`）。
文件名只允许 `[a-z0-9_-]`、非空、≤40 字符（`sys.rs:50-55`）—— 这是防 `../` 跳出目录的那道闸门。

前端封装：`storeRead/storeWrite/storeDelete/storeList` 直通（`bridge.js:70-121`）；
`loadSettings(name, defaults)` 合并默认值，损坏时回默认值并把原因带出来、**不覆盖原文件**（`bridge.js:132-144`）；
`saveSettings(name, value, version=1)` 自动补 `version` 字段（`bridge.js:147-149`）。

### 3.2 每个分组落到哪

| 分组 | 落在哪 | 写入方 | 出处 |
| --- | --- | --- | --- |
| 外观 | `localStorage`：`mf_theme` / `mf_shape` / `mf_density` / `mf_font` / `mf_theme_follow`；界面语言 `mf.lang` | 前端 | `lib/bridge.js:353-369`、`lib/i18n/index.js:34,52` |
| 计算与绘图 | `settings\prefs.json`（`decimals` + 四项绘图范围） | 前端 `saveSettings("prefs")` | `lib/settings/prefs.js:23-30,53,70` |
| 引擎 | **不写设置文件**（读 `Info`/`EngineReport` + 真调引擎自检） | — | `lib/settings/bridge.js:46-68`、`EngineGroup.vue:13-15` |
| 组件 | **不写设置文件**；状态来自 `con` 桥；下载源只在宿主进程内的 `Mutex` 里，重启回环境变量 / 内置默认 | 宿主 | `console.rs:150-167,181-186`、`lib/console/bridge.js:93-97` |
| AI | `settings\ai.json`（`apiKey` **明文**）+ `settings\ai-chat.json`（会话记录） | 前端 | `lib/ai/bridge.js:8,53,133,466,475` |
| 搜索 | `settings\search.json`（Wolfram App ID 密文等），宿主经 `sys::store_write` 写 | 宿主 | `search.rs:108,230,241-242` |
| 账号 | `settings\account.json`（token 密文） | 宿主 | `account.rs:79,92,255` |
| 更新 | `settings\update.json`（`autoCheck` / `intervalDays` / `lastCheckAt`） | 前端 | `lib/update/bridge.js:44-45,59-76` |
| 存储与数据 | 本组自己不写设置文件：它列出 / 打开 / 清理别的文件，并承载工作区与导入导出 | — | `StorageGroup.vue:109-138,147-279` |

同一目录里还有一份不属任何分组、但会进备份的文件：`history.json`（`lib/history/store.js:18,68`，上限 200 条见 `:21`）。

### 3.3 无宿主时降级

`npm run dev` 的浏览器预览没有 `sys`：只读信息返回 `{browser:true,…}` 并显示"浏览器预览：无宿主"（`bridge.js:46-68`），
读写**降级到 `localStorage` 的 `mf_set_` 前缀**（`bridge.js:10,87-121`），且 `storeWrite` 在降级路径上**同样先校验 JSON**（`bridge.js:104`）—— 与宿主"坏 JSON 不落盘"一致。判据函数是 `isSettingsHosted()`（`bridge.js:20-22`）。

---

## 4. 导入 / 导出（换机迁移）

实现全在 `lib/settings/io.js`；文件名约定 `settings-bundle`，`version: 1`（`io.js:26-28`）。

### 4.1 包里有什么

```jsonc
{ "app":"MF-Mathematics", "kind":"settings-bundle", "version":1,
  "exportedAt":"…", "appVersion":"2.0.0",
  "files": { "history": {…}, "ai-chat": {…}, "prefs": {…}, "update": {…} },
  "prefs": { "mf_theme": "dark", "mf_tut_progress": "…", "mf.lang": "en-US" },
  "excluded": ["ai","account","search"], "stripped": ["someFile.apiKey"] }
```

包元数据里还有一个 `skippedCorrupt`（读不出 / 解析失败的文件名清单），只在真的遇到坏文件时才出现（`io.js:116`）。

| 字段 | 内容 | 出处 |
| --- | --- | --- |
| `files` | `StoreList` 报出来的每个设置文件；**整份排除** `ai` / `account` / `search`；读不出或解析失败的记进 `skippedCorrupt` 并**跳过** | `io.js:82-102,116` |
| `prefs` | `localStorage` 里**所有 `mf_` 前缀**的键（`collectPrefs()`） | `io.js:56-65` |
| `stripped` | 字段级剥离记录（见下） | `io.js:122-131` |
| 元数据 | `app`/`kind`/`version`/`exportedAt`/`appVersion`/`excluded` | `io.js:104-118` |

> ⚠ **`prefs` 的范围比"外观偏好"宽。** 除外观五项外，还包括教程进度 `mf_tut_progress`
> （`lib/tutorial/store.js:24`）、界面语言 `mf.lang`、以及 `mf_kb_visible` / `mf_sidebar` / `mf_nav_*`
> （`App.vue:61,68,75`）。[../link/FEATURES.md](../link/FEATURES.md) §4.2 只列了外观五项 —— 已记为文档债（§9 第 10 条）。

**凭据的两道防线，都是可见的**：

1. **整份排除**：`CREDENTIAL_FILES = ["ai","account","search"]`（`io.js:31`），排除名单原样写进包的 `excluded`（`io.js:114`）；
2. **字段级剥离**：其余文件递归剥掉字段名命中 `/(protected|password|passwd|secret|token|api[-_]?key)/i` 的字段（`io.js:34,122-131`），
   剥掉了哪些**记进 `stripped`**（同一个命令可复跑：`cdp-settings-io.mjs:80-82` 断言 `io-probe.apiKeyProtected` 在 `stripped` 里）。

`buildBundle()` 还有一处**如实失败**：`StoreList` 返回的不是数组（即 `{"error":…}` 分支）时**中止导出**并报原因，
不再把"0 个设置文件"当成导出成功（`io.js:73-81`）。读不出 / 损坏的文件也不再静默跳过（`io.js:92-100`）。

**导出到文件**：`exportToFile(path)` → `win.SaveTextFile(标题, "mfmath-settings-<YYYY-MM-DD>.json", 过滤器, 内容, path)`（`io.js:180-193`）；
`path` 非空则**跳过原生对话框**（宿主自带的自动化钩子），用例正是靠它跑完整链路（`cdp-settings-io.mjs:104-109`）。

### 4.2 导入的两条性质（都有断言守着）

| 性质 | 实现 | 断言 |
| --- | --- | --- |
| **不清现有凭据** | `applyBundle` 只写包里存在的文件；三个凭据文件**永远不写**（再查一遍，并记进 `skipped`）；每个文件的字段**再剥一遍** | `io.js:152-160`；`cdp-settings-io.mjs:150-163`（"ai.json 内容未被改动"） |
| **坏包整包拒绝、不部分写入** | `app` / `kind` / `version` 任一不对**在写第一个文件之前**就 return；版本比程序新则要求先更新 | `io.js:141-147`；`cdp-settings-io.mjs:139-148`（"被拒绝的导入没有改动任何文件"） |

**一条需要说清的细节（不是"部分写入"）**：通过元数据校验之后，**单个文件写失败不会中断整包**——
其余文件照写、失败的记进 `skipped`（`io.js:158-159`）。所以"不部分写入"精确地说是
"**元数据不合格的包不写任何文件**"，而不是"任何失败都全有全无"。

偏好写入还有一条闸门：**只写 `mf_` 前缀的键**，其余记进 `skipped`（`io.js:162-167`）。
界面侧有二次确认（`data-io="confirm"`）且提示"导入会覆盖同名的设置文件"（`StorageGroup.vue:262-270`）。

### 4.3 生效时机：如实说要重启

`applyBundle()` 的返回值里 `needsRestart: true` 是**写死的**，理由写在同处：
"设置文件与外观偏好都在启动时读取 → 如实说要重启（不假装即时生效）"（`io.js:169-175`）。
界面同样明说（`StorageGroup.vue:276`），用例也断言了它（`cdp-settings-io.mjs:134`）。

### 4.4 用例与界面钩子

| 东西 | 出处 |
| --- | --- |
| `window.__mfSettingsIo`（`build` / `apply` / `exportToFile` / `importFromFile` / `prefs` / `state` / `constants`） | `io.js:207-218`；`App.vue:197` 启动时挂 |
| 界面按钮 | `data-io="export"` / `"import"` / `"confirm"` / `"msg"` / `"scope"`（`StorageGroup.vue:263-277`） |
| 范围文案 | 必须含"不含密钥"与"重启后生效"两条（`cdp-settings-io.mjs:172-173`） |
| 存储组不许再出现"待实现"标签 | `cdp-settings.mjs:169-173`、`cdp-settings-io.mjs:170-171` |

### 4.5 诊断包与备份**不是同一件事**

诊断包（`ExportDiagnostics`）跳过 `["ai","account","search"]` 三份凭据文件，另有"文件名含 `secret`"的兜底（`sys.rs:278-297`；[../link/FEATURES.md](../link/FEATURES.md) §4.4 记着"原先只按 secret 跳，等于没跳"那个坑）。
**`ai-chat.json` 不在跳过名单里** —— 它会连同会话原文整份进诊断包（`sys.rs:290-304`）。这与"除凭据外的设置文件原文"的设计一致，但要知道**会话记录是你自己输入的内容**，发给支持前先看一眼。

---

## 5. 工作区

「工作区」= 你正在算 / 正在画 / 正在写的东西（`lib/workspace/store.js:5-6`）。三条原则写在 `store.js:8-13`：① 每页只声明自己的载荷形状、store 不解释内容；② 最近工作区落 `%LOCALAPPDATA%\MFMath\settings\workspace.json`、"另存为"走宿主文件对话框；③ 载入失败**必须说出来**。

### 5.1 保存什么、不保存什么

| 保存 | 不保存 |
| --- | --- |
| 各页的**输入**：计算块（表达式 + 模式）、绘图表达式 / 视野 / 参数、控制台的语言 + 代码 + 标准输入 | **结果**：曲线采样、交点、极值、向量场数据、分形像素、运行输出（都能重算） |
| 页面身份：`route.path` 作为键、`kind` 认领 | 撤销 / 重做栈、错误文本、临时状态（`PlotGeometryPage.tsx:93`、`Plot3DPage.tsx:88`） |

出处：`store.js:5-6,51`；各页 `capture*` 见 §5.3、§5.4。

### 5.2 按 `route.path` 分页

| 位置 | 行为 | 出处 |
| --- | --- | --- |
| `pages` | `ref({})`，键是 `route.path`（**不带 `#`**） | `store.js:25,34-42` |
| `snapshot(route)` | `{version: 1, savedAt, route, pages}` | `store.js:20,51` |
| `applySnapshot(obj)` | 校验 `version`（缺失 / 比程序新都拒绝）、`pages` 必须是对象；**只接受以 `/` 开头的键**；一条都没有则拒绝 | `store.js:58-79` |
| `summary()` | `pages` 数 + `routes` 列表 + `blocks` 数 + `curves` 数（`curves` 数的是 `expressions` 数组长度） | `store.js:82-100` |

`cdp-workspace.mjs:159-166` 与 `cdp-plot-workspace.mjs:103-121` 都明确用**不带 `#`** 的键
（后者注释里记着"第一版拿 `#/plot/2d` 当键，于是永远查不到"这个用例自身的坑）。

### 5.3 六个绘图页的载荷形状

`/plot/*` 有 **7 条路由**，但只有 **6 个 React 页面组件**（2D 与极坐标共用 `PlotPage`）：
路由表 `src/router/index.js:37-46`，路由→页面键 `REACT_PAGES` 在 `:68-76`，外壳按 `meta.reactPage` 动态加载
（`components/plot-react/ReactPlotView.vue:39-40`）；绘图组自身怎么组织见 [PLOT.md](PLOT.md)，本节只讲"每页存什么"。

| 路由 | 页面键 | 组件 | `kind` | 载荷字段 | 出处 |
| --- | --- | --- | --- | --- | --- |
| `/plot/2d` | `2d` | `plot/PlotPage.tsx` | `plot` | `expressions[{text,color,visible}]`、`view{x0,x1,y0,y1}`、`gridMode`、`showGrid`、`params` | `PlotPage.tsx:159-166` |
| `/plot/polar` | `polar` | 同上（`gridMode:"polar"`） | `plot` | 同上 | `PlotPage.tsx:75-79,111-112,163` |
| `/plot/3d` | `3d` | `plot/Plot3DPage.tsx` | `plot3d` | `exprInput`、`view{yaw,pitch,zoom}`、`showSurface`、`showWireframe`、`gridN`、`domain`、`params` | `Plot3DPage.tsx:89-98` |
| `/plot/complex` | `complex` | `plot/PlotComplexPage.tsx` | `plot-complex` | `funcExpr`、`mode`（**下标**，越界即归 0）、`xMin/xMax/yMin/yMax`、`resolution` | `PlotComplexPage.tsx:117-141` |
| `/plot/vector` | `vector` | `plot/PlotVectorPage.tsx` | `plot-vector` | `dxInput`、`dyInput`、`view{x0,y0,x1,y1}`、`density`、`normalize`、`colorByMagnitude`、`showGrid`、`arrowScale`、`params` | `PlotVectorPage.tsx:91-102` |
| `/plot/geometry` | `geometry` | `plot/PlotGeometryPage.tsx` | `plot-geometry` | `shapes[{id,type,data}]`、`tool`、`snap` | `PlotGeometryPage.tsx:94-99` |
| `/plot/fractal` | `fractal` | `plot/PlotFractalPage.tsx` | `plot-fractal` | `view{xmin,xmax,ymin,ymax}`、`maxIter`、`scheme`、`smooth`、`maxSide` | `PlotFractalPage.tsx:115-122` |

六个绘图页共有的三条规矩（`MFMath.UI.React/src/lib/plotWorkspace.ts`）：

1. **首帧不回写** —— `usePlotWorkspace` 用 `useRef(true)` 吞掉第一次 effect，
   否则"刚打开一页"就被标脏（`plotWorkspace.ts:51-72`）；
2. **形状不符就当没有** —— `loadPlotPage` 要求 `kind` 对上，否则返回 `null`（`plotWorkspace.ts:32-38`）；
3. **每个字段都要过类型守卫** —— `numOr` / `boolOr` / `strOr` / `numsOr` / `isViewLike`
   （`plotWorkspace.ts:74-101`），因为工作区文件是**用户可手改的**：坏值逐项丢掉，
   典型处理是分形视野必须 `xmin<xmax && ymin<ymax`（`PlotFractalPage.tsx:97-105`）、
   3D 的 `zoom<=0` 退回默认（`Plot3DPage.tsx:75-82`）、几何图形 `id` 必须有限且 `data` 是数组
   （`PlotGeometryPage.tsx:71-79`，还原后还要把 `nextIdRef` 推到下一个空 id，`:88-91`）。

⚠ 2D / 极坐标必须由外壳**传 `routePath`**，否则连"存到哪个键"都没有：`ReactPlotView.vue:69-75`
（B14 修的就是这一条，此前这两页只传了 `gridMode`）。

### 5.4 谁在还原、谁在回写

| 页面 | 还原时机 | 回写时机 | 出处 |
| --- | --- | --- | --- |
| `/calc/*`（14 个学科视图共用 `CalcView`） | 挂载时 `restoreFromWorkspace()`：要求 `kind === "calc"` 且 `blocks` 非空；模式不在本页模式表里就落回第一个 | `watch(blocks, …, {deep:true})`，且 `syncWorkspace` 在 `onMounted` 才置真 | `CalcView.vue:56-84,155-168` |
| `/plot/*`（6 个 React 页） | `useState` **惰性初值**（首帧就带还原值，从根上排除"默认值盖掉还原内容"） | `usePlotWorkspace(route, deps, capture)` 的 effect | `PlotPage.tsx:90-92`、`plotWorkspace.ts:59-72` |
| `/tools/console` | `onMounted` 读 `getPage`：要求 `kind === "console"` 且 `code` 非空，否则回到示例 | `watch([lang, code, stdin], …, {deep:true})` | `ConsoleView.vue:339-350,375-379` |
| 其它页面 | 不参与 | — | grep `setPage(`/`getPage(` 的全部命中：`CalcView.vue:64,164`、`ConsoleView.vue:342,378`、`PlotView.vue:35,701`（冻结资产）、`MFMath.UI.React/src/lib/plotWorkspace.ts:22,34,43`、`lib/ai/bridge.js:540` |

两条容易踩的交互：

- **工作区还原的优先级高于"新页面的默认范围"**：`cdp-shortcuts-prefs.mjs:246-252` 必须先 `clearAll()`，
  否则前一个用例写进 `/plot/2d` 的视野会把"绘图默认范围"这条断言顶掉 —— 那是**正确的产品行为**
  （还原用户上次的视野），`BUGS.md` §0.3 也把这条记为"用例的顺序脆弱性，不是功能坏了"。
- **示例加载优先于工作区还原**：`CalcView.vue:56-59`（示例是用户刚点的动作，不该被旧内容顶掉）。
- 冻结资产 `src/views/plot/PlotView.vue`（Vue 版）**不在构建图里**（`router/index.js:29-36`），
  它的 `capturePlot()`（`:661-670`）只作为"2D / 极坐标载荷逐字一致"的参照物。

**第五个消费方是 AI 面板**：`currentContext(route)` 从工作区载荷里取"当前工作现场"（`lib/ai/bridge.js:538-558`），
只有隐私开关打开、且该字段非空时才写进发给模型的消息（`bridge.js:568-573`）。
⚠ 它读的是 `p.blocks[].result`（`bridge.js:548`），而**工作区从来只存 `expr`/`mode`、不存结果**
（`CalcView.vue:80-84`）—— 于是"引擎结果"这一项在计算页恒为"没有"（面板也如实这样显示，`AiPanel.vue:147-149`），
`sendResult` 开关在计算页实际不起作用。**未运行时验证**，验法见 §8 第 7 条。

### 5.5 落盘、另存为、读回来的校验

| 动作 | 走哪条路 | 出处 |
| --- | --- | --- |
| 保存 | `saveToApp(route)` → `storeWrite("workspace", snapshot(route))` → `settings\workspace.json`（宿主原子写） | `store.js:21,108-119` |
| 载入 | `loadFromApp()` → `storeRead("workspace")` → `applySnapshot`；损坏时**保留原文件**并说明 | `store.js:121-137` |
| 另存为文件 | `saveTextFile({defaultName:"workspace.mfws.json", filter: FILE_FILTER, path})`；`path` 非空跳过对话框 | `store.js:22,146-166` |
| 从文件打开 | `openTextFile({filter, path})` → `JSON.parse` → `applySnapshot` | `store.js:168-184` |
| 测试钩子 | `window.__mfWorkspace`（`summary` / `pages` / `save*` / `load*` / `clearAll` / `setPage` / `applySnapshot` / `VERSION`） | `store.js:211-225`，`App.vue:176` 启动时挂 |

**「载入」不是自动发生的。** `loadFromApp()` 在整个仓库里只有一个调用点 —— 设置面板那一行的「载入」按钮
（`StorageGroup.vue:73-78`）；`hasAppWorkspace()` 目前是**零引用导出**（全仓库 grep 只有 `store.js:139` 定义与 `:200` 导出）。
所以刷新或重启之后内存里的 `pages` 是空的，必须显式点一次「载入」——
`cdp-workspace.mjs:181-209` 就是这么验的（先断言"刷新后内存是空的"，再点按钮、再断言跳回与还原）。

### 5.6 坏输入不静默

| 输入 | 结果 | 断言 |
| --- | --- | --- |
| 版本比程序新（`version: 99`） | 拒绝："工作区版本 99 比当前程序（1）新，请先更新应用" | `store.js:62`；`cdp-workspace.mjs:256-259` |
| 文件不是 JSON | 拒绝并指出是文件坏了，带路径 | `store.js:176-179`；`cdp-workspace.mjs:261-264` |
| 缺 `pages` | 拒绝："缺少 pages 字段" | `store.js:63-65`；`cdp-workspace.mjs:266-268` |
| `pages` 里全是非法键 | 拒绝："工作区里没有任何页面内容" | `store.js:71-72` |
| 磁盘上的 `workspace.json` 损坏 | 报"已损坏（保留原文件）"，不写、不覆盖 | `store.js:123-127`；`sys.rs:165-173` |
| 还没有保存过 | "还没有保存过工作区" | `store.js:128` |

### 5.7 B14：React 绘图组完全没接工作区（已修）

| 项 | 内容 | 出处 |
| --- | --- | --- |
| 现象 | 工作区对绘图页**全部失效**；`cdp-workspace` 的失败清单里一条 `/plot/*` 都没有（因为连键都没写） | [MF_UI/BUGS.md](../../MF_UI/BUGS.md) §B14 的"现象"与"证据" |
| 根因 | 绘图组整组迁 React 时只搬了渲染层与算法（`@shared/plot/*`），没搬"与外壳的契约"（同一成因还有 B13 的 `emphasis`、B15 的导出反馈） | [MF_UI/BUGS.md](../../MF_UI/BUGS.md) §B14"根因" |
| 修法 | 新增 `lib/plotWorkspace.ts` + 给 **6 个绘图页全部接上**；`ReactPlotView.vue` 给 2D / 极坐标补传 `routePath` | [MF_UI/BUGS.md](../../MF_UI/BUGS.md) §0.3 表 B14 行 |
| 实测 | `cdp-workspace` **21/4 → 25/0**、`cdp-shortcuts-prefs` **22/1 → 23/0**（2026-10-07，第二轮） | [MF_UI/BUGS.md](../../MF_UI/BUGS.md) §0.3 表 B14 行 |
| 补测与跑绿状态 | `tests/cdp-plot-workspace.mjs` 专补 3D / 复平面 / 向量场 / 几何 / 分形这 5 页的**往返**（改控件→载荷变、离开再回→控件还原），已登记进 `run-all.ps1:50-53`；⚠ 但 [PROJECT-BOARD.md](../PROJECT-BOARD.md#L139) 写明它"在**独占窗口里跑绿之前**仍算'代码就绪、未验证'" | `tests/cdp-plot-workspace.mjs:1-17,137-189` |

### 5.8 `pendingInput.js` 不是工作区的一部分

`lib/workspace/pendingInput.js` 干的是另一件事：把示例库里的表达式 + 操作名**跨路由**交给计算 / 绘图视图
（`pendingInput.js:14-27`，取一次即清空），并把模式 / 操作名映射到目标路由与真实模式名
（`MODE_ROUTES:30-63`、`NOT_ROUTABLE:73-75`、`ALIASES:99-107`、`resolveExample:161-174`）。
它是**模块内的一个 `ref`**，不进 `snapshot()` 的 `pages`，所以**不落盘、不随工作区迁移**；它自己的坑（"AI 助手尚未实现"那句假话、旧操作名错位）记在文件注释里（`:65-75,92-98`）。

---

## 6. 外观偏好为什么不进工作区文件

结论：**外观是 `localStorage` 的 `mf_*` 键，工作区文件里没有放它的字段；整机迁移由"导入 / 导出设置"承担。**

| 理由 | 证据 |
| --- | --- |
| 外观本来就不落设置目录 | `lib/bridge.js:353-369` 写的是 localStorage；读取与生效在模块初始化（`bridge.js:408-411` 与 `currentAppearance`） |
| 工作区 schema 里没有它的位置 | `snapshot()` 只有 `{version, savedAt, route, pages}`（`store.js:51`）；要加就得动 `VERSION` 并写迁移（`store.js:20` 注释"将来好写迁移"） |
| 迁移问题已经被备份解决 | `collectPrefs()` 收**所有** `mf_` 前缀键（`io.js:56-65`），导入时写回 localStorage（`io.js:162-167`），并如实要求重启（`io.js:174`） |
| 它被登记成"缺口"而非缺陷 | [OPEN-ITEMS.md](../OPEN-ITEMS.md#L124)："工作区：**外观偏好不入工作区**（现在可以靠'导入/导出设置'整机迁移，但外观仍不进工作区文件）"，处置出处写的是 `MIGRATION-GAPS.md` §2.6 —— 那份属已登记的 R7 旧债（讲的是已废弃的 .NET 实现，见 [AGENTS.md](../../AGENTS.md) §2） |

顺带一条同类事实：**界面语言 `mf.lang` 也在这一层**（`lib/i18n/index.js:29-52`），
所以它同样不进工作区、但会随备份走。

---

## 7. 本文核对出的一处疑点（**未在运行时验证**）

**从设置面板点「保存」时，写进工作区的 `route` 是 `/settings`（设置页自己），不是用户当时在编辑的页面。**

| 环节 | 代码 | 说明 |
| --- | --- | --- |
| 取路由 | `StorageGroup.vue:62-67` | `const route = useRoute()` 取到的是**设置页**的路由，随后 `wsApi.saveToApp(route.path)` |
| 记录 | `store.js:51,108-118` | `snapshot(route)` 把它写成工作区的 `route` 字段 |
| 使用 | `StorageGroup.vue:73-78` | 载入后 `if (r.route) router.push(r.route)` → 跳回 `/settings`（用户已经在那儿） |

同样的问题在「另存为文件…」（`StorageGroup.vue:80`，传的也是 `route.path`）。

**用例没有覆盖到这条**：`cdp-workspace.mjs:169` 是直接调
`window.__mfWorkspace.saveToApp("/calc/algebra")`（绕开按钮），
之后 `:200-209` 点「载入」并断言"载入后跳回保存时的页面"能过，靠的正是那次直接调用写进去的 `route`。

**状态**：只有源码证据，**没有跑宿主**（本文 §1）。**怎么验**：起宿主后
① 在 `/calc/algebra` 改一个计算块 → ② `/settings?group=storage` 点「保存」→
③ 读 `%LOCALAPPDATA%\MFMath\settings\workspace.json` 的 `route` 字段，看是否为 `"/settings"` →
④ 点「载入」，看是否跳回 `/settings`。若两条都成立，这是一处**产品缺陷**（修法应回填"最后一个有载荷的页面路由"），
按纪律登记进 [MF_UI/BUGS.md](../../MF_UI/BUGS.md)；**本文不改那份文件**。

---

## 8. 未证实（附怎么验）

| # | 未证实的事 | 为什么没证 | 怎么验 |
| --- | --- | --- | --- |
| 1 | 本文全部"行为"结论 | 本文**没跑宿主**，只有源码 + 一次 `catalog.js` 导入 | 按 [AGENTS.md](../../AGENTS.md) §4 附着已有宿主后跑 `tests/run-all.ps1 -NoLaunch`；本主题相关的四条：`cdp-settings`、`cdp-settings-io`、`cdp-workspace`、`cdp-shortcuts-prefs`（`run-all.ps1:61,63,78,84`），补测 `cdp-plot-workspace`（`:53`） |
| 2 | `cdp-plot-workspace` 现在是否绿 | 未跑；[PROJECT-BOARD.md](../PROJECT-BOARD.md#L139) 明确"独占窗口里跑绿之前仍算未验证" | 独占时间窗内 `node tests/cdp-plot-workspace.mjs`；它连不上 CDP 时会退出码 2 且**不打印 RESULT 行**（`:23-33,197-203`），不要把它读成通过 |
| 3 | 导入后"必须重启"是否真的不重启就不生效 | `needsRestart: true` 是**代码声明**（`io.js:174`），我没有实测 | 导入一个含 `mf_theme` 的包 → 不刷新页面直接看 `document.documentElement.dataset.theme`；再刷新对比 |
| 4 | 界面语言行在设置搜索里搜不到（影响面） | 索引层已证（`searchItems("语言") === []`），但没在界面上敲字 | `/settings` 顶部搜索敲"语言"，看结果列表是否为空 |
| 5 | `StorageGroup.vue` 模板里的 `**不含密钥**` 是否字面显示 | Vue 模板不解析 markdown，但没截图确认 | `/settings?group=storage` 看"导出诊断包"与"导入 / 导出设置"两行的说明文字（`StorageGroup.vue:203,259`） |
| 6 | 本机设置目录快照 | 那是**机器状态**（含测试残留 `io-probe.json.bak`） | 见 §1 的 `Get-ChildItem` 命令 |
| 7 | AI 的 `sendResult` 开关在计算页是否真的无效 | 只有源码证据（§5.4 末段）：工作区不存 `result`，`currentContext` 却读它 | 打开 AI 面板，看"将发送的内容"里"引擎结果"一项是否恒为灰（`AiPanel.vue:147-149`）；或跑 `tests/cdp-ai.mjs` 看隐私开关一节的期望 |

---

## 9. 已知的文档债

| # | 文件:行 | 它说 | 代码做 | 影响 |
| --- | --- | --- | --- | --- |
| 1 | `src/lib/settings/catalog.js:5` | "9 组 / **60 项**，全部 status === ready" | 9 组 / **57 项**（§1 命令） | 读数偏大 3，会让人以为丢了 3 项 |
| 2 | `src/lib/settings/catalog.js:62-65` | AI "与 v1 的 12 项相比**收敛成 10 项**" | 实际 **11** 项（§2 表） | 同上 |
| 3 | `src/lib/settings/catalog.js:22` | AI 的 `note`："密钥只存宿主（**DPAPI**）" | `ai.json` 里的 `apiKey` 是**明文**（`lib/ai/bridge.js:8,53,133`；`cdp-settings.mjs:197` 也按"明文"断言） | **安全口径错误**，且它还是界面上显示给用户的说明 |
| 4 | `src/lib/settings/catalog.js:23` | 搜索"抓取与解析在宿主（**C#**）" | 现役宿主是 **Rust**（`search.rs:108,230` 经 `sys::store_write`）；C# 宿主已废弃（[AGENTS.md](../../AGENTS.md) §2） | 指向已废弃实现的 R7 类债；同句还出现在 `router/index.js:49` |
| 5 | `src/lib/settings/bridge.js:4` | "宿主侧是 `MFMath.Host/SettingsBridge.cs`" | 现役是 `MFMath.Host.Rust/src/sys.rs`（`handlers.rs:259-273`、`main.rs:90-93`） | 同上；`StorageGroup.vue:7` 也写"见 SettingsBridge.cs" |
| 6 | `src/components/settings/StorageGroup.vue:9-11` | "历史记录与工作区管理依赖 P1…这三项在界面上以'待实现'列出" | 三项都已落地且组件里没有 `pending-tag`（`StorageGroup.vue:211-279`；`cdp-settings.mjs:169-173` 断言标签数为 0） | 注释与代码相反 |
| 7 | `src/lib/settings/catalog.js:8` | "构建期脚本可以断言 catalog 里的项都在界面上有对应行" | **没有这个脚本**：全仓库引用 `settings/catalog.js` 的只有 `SettingsView.vue:19` 与 `router/index.js:62` 的注释；反向反例是 `AppearanceGroup.vue:50` 的 `appearance.language` 不在 catalog 里（→ `searchItems("语言")` 为空，§2.1） | 承诺的闸门不存在，缺口已经发生 |
| 8 | `tests/cdp-settings.mjs:5` | 头注释"**7 个分组**都在导航里" | 同文件 `:76` 断言 9 组，实测 `counts === 9` | 用例文档自相矛盾；`run-all.ps1:59` 的注释也还写着"7 个分组" |
| 9 | [FEATURES.md](../link/FEATURES.md) §4.2 | 把"**教程进度**"列进"设置文件（`settings\*.json`）" | 教程进度在 `localStorage` 的 `mf_tut_progress`（`lib/tutorial/store.js:24,49,75`），因此进的是包的 `prefs` 而不是 `files` | 读的人会去 `settings\` 里找它 |
| 10 | [FEATURES.md](../link/FEATURES.md) §4.2 | "外观偏好：`localStorage` 里 `mf_` 前缀的键（主题/形状/密度/字体/跟随系统）" | `collectPrefs()` 收**所有** `mf_` 前缀键，还包括 `mf.lang`、`mf_tut_progress`、`mf_kb_visible`、`mf_sidebar`、`mf_nav_*`（`io.js:56-65`、`App.vue:61,68,75`） | 范围被写窄了 |
| 11 | [MF_UI/BUGS.md](../../MF_UI/BUGS.md) 附 A 第 2 条 | "B14 里那 5 个页面的工作区接线，**没有任何测试覆盖**" | `tests/cdp-plot-workspace.mjs` 就是专补这一块的，且已登记进 `run-all.ps1:50-53` | 至少有一处未更新；这条与 [PROJECT-BOARD.md](../PROJECT-BOARD.md#L139)（"跑绿之前算未验证"）并存，容易读成"已有覆盖=已验证" |
| 12 | `src/components/settings/StorageGroup.vue:203,259` | 模板文本里写 `**不含密钥文件**` / `**不含密钥**` | Vue 模板不解析 markdown，用户看到的可能是字面星号 | 用户可见文案；未截图确认（§8 第 5 条） |

> 第 3 / 4 / 5 / 6 条都属于"注释与旧文档指向已废弃的 .NET 实现或已过期的状态"，与 [PROJECT-BOARD.md](../PROJECT-BOARD.md) §3 R7 是同一族；
> 本文只登记，不改任何文件（`catalog.js`、`bridge.js`、`StorageGroup.vue`、`BUGS.md`、`FEATURES.md` 都不属本份文档的管辖范围）。
