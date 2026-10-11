# 设置面板与工作区

> 本文回答设置面板与工作区：设置分组与项数、存储位置、导入导出的语义、工作区保存范围，以及外观偏好的存储方式。
>
> 与同层文档的分工：[README.md](README.md) 讲两个工程与构建链；[ARCHITECTURE.md](ARCHITECTURE.md) 讲 views/components/lib 分层与路由；[TOOLS.md](TOOLS.md) 讲控制台 / 函数工具箱 / 历史 / 搜索页；[AI.md](AI.md) 讲 `ai.json` 明文密钥的代价；[CHECKS.md](CHECKS.md) 讲构建闸门；宿主侧 `sys` 桥的方法契约见 [../link/FEATURES.md](../link/FEATURES.md)。

## 1. 分组与项数

设置目录在 `src/lib/settings/catalog.js`，共 9 组、57 项，全部 `status === "ready"`。

| 组 id | 组名 | 项数 | 面板组件 |
| --- | --- | --- | --- |
| `appearance` | 外观 | 6 | `AppearanceGroup.vue` |
| `calc` | 计算与绘图 | 2 | `CalcPlotGroup.vue` |
| `engine` | 引擎 | 6 | `EngineGroup.vue` |
| `components` | 组件 | 5 | `ComponentsGroup.vue` |
| `ai` | AI | 11 | `AiGroup.vue` |
| `search` | 搜索 | 8 | `SearchGroup.vue` |
| `account` | 账号 | 5 | `AccountGroup.vue` |
| `update` | 更新 | 7 | `UpdateGroup.vue` |
| `storage` | 存储与数据 | 7 | `StorageGroup.vue` |

验证命令：

```powershell
node -e "import('./MF_UI/MFMath.UI.Vue/src/lib/settings/catalog.js').then(m=>{const {GROUPS,ITEMS}=m;console.log('groups='+GROUPS.length+' items='+ITEMS.length);console.log(GROUPS.map(g=>g.id+'='+ITEMS.filter(i=>i.group===g.id).length).join(' '))})"
```

面板是容器而非一页：左侧分类导航 + 右侧内容，`GROUPS` 直接渲染，每行带完成度。顶部搜索做的是跳到具体某一项。深链 `/settings?group=<id>` 支持初始、挂载、query 变化三种进入方式。未落地的组由 `PlaceholderGroup.vue` 兜底，当前没有 `pending` 组。

## 2. 存储位置

桥面：前端 `lib/settings/bridge.js` 包一层 `window.chrome.webview.hostObjects.sync.sys`，宿主实现是 `MFMath.Host.Rust/src/sys.rs`。

| 方法 | 关键行为 |
| --- | --- |
| `Info` | `dataDir` / `settingsDir` / `appDir` / `hostVersion` / `componentBase` |
| `StoreList` | 只列 `.json`；目录不存在返回空数组；I/O 错误返回 `{"error":…}` |
| `StoreRead` | `{ok,exists}` / `{ok,exists,json}` / `{ok:false,corrupt,error}` |
| `StoreWrite` | 校验后写 `.tmp`、备份 `.bak`、原子替换 |
| `StoreDelete` | 删 `.json`，不删 `.bak` |
| `OpenPath` | 白名单：数据目录 / exe 目录 / 组件目录 |
| `ExportDiagnostics` | 写 `dataDir\diagnostics-<stamp>.txt` |

路径：`settingsDir = dataDir/settings`，`dataDir = %LOCALAPPDATA%\MFMath`。文件名只允许 `[a-z0-9_-]`、非空、≤40 字符。

各分组落盘：

| 分组 | 存储位置 |
| --- | --- |
| 外观 | `localStorage`：`mf_theme` / `mf_shape` / `mf_density` / `mf_font` / `mf_theme_follow`；界面语言 `mf.lang` |
| 计算与绘图 | `settings\prefs.json`（`decimals` + 四项绘图范围） |
| 引擎 | 不写设置文件，读 `Info`/`EngineReport` + 引擎自检 |
| 组件 | 不写设置文件，状态来自 `con` 桥 |
| AI | `settings\ai.json`（`apiKey` 明文）+ `settings\ai-chat.json`（会话） |
| 搜索 | `settings\search.json`（宿主写） |
| 账号 | `settings\account.json`（宿主写） |
| 更新 | `settings\update.json` |
| 存储与数据 | 本组不写设置文件 |

同一目录还有 `history.json`（不属任何分组，但进备份）。

无宿主时降级：只读信息返回 `{browser:true,…}`，读写降级到 `localStorage` 的 `mf_set_` 前缀。

## 3. 导入 / 导出

实现全在 `lib/settings/io.js`，包格式 `settings-bundle`，`version: 1`。

### 3.1 包内容

| 字段 | 内容 |
| --- | --- |
| `files` | `StoreList` 报出的每个设置文件，整份排除 `ai` / `account` / `search` |
| `prefs` | `localStorage` 里所有 `mf_` 前缀的键 |
| `excluded` | 排除名单 `["ai","account","search"]` |
| `stripped` | 字段级剥离记录 |
| `skippedCorrupt` | 读不出或解析失败的文件名清单，仅在遇到坏文件时出现 |

`prefs` 的范围比外观偏好宽，还包括教程进度 `mf_tut_progress`、界面语言 `mf.lang`、`mf_kb_visible` / `mf_sidebar` / `mf_nav_*`。

凭据两道防线：整份排除 `CREDENTIAL_FILES`，字段级剥离 `SECRET_FIELD`（正则 `/(protected|password|passwd|secret|token|api[-_]?key)/i`）。`StoreList` 返回非数组时中止导出。

导出到文件走 `win.SaveTextFile`，文件名 `mfmath-settings-<YYYY-MM-DD>.json`；`path` 非空跳过对话框。

### 3.2 导入语义

| 性质 | 实现 |
| --- | --- |
| 不清现有凭据 | `applyBundle` 只写包里存在的文件，三个凭据文件永远不写，字段再剥一遍 |
| 坏包整包拒绝 | `app` / `kind` / `version` 任一不符，写第一个文件之前 return |
| 偏好只写 `mf_` 前缀 | 其余记进 `skipped` |
| 生效需重启 | `needsRestart: true` 写死 |

元数据校验通过后，单个文件写失败不中断整包，其余照写，失败记进 `skipped`。「不部分写入」精确指元数据不合格的包不写任何文件。

## 4. 工作区

「工作区」是正在计算 / 绘制 / 编写的内容。三条原则：每页只声明自己的载荷形状、store 不解释内容；最近工作区落 `%LOCALAPPDATA%\MFMath\settings\workspace.json`、「另存为」走宿主文件对话框；载入失败必须说出来。

### 4.1 保存范围

| 保存 | 不保存 |
| --- | --- |
| 各页的输入：计算块（表达式 + 模式）、绘图表达式 / 视野 / 参数、控制台的语言 + 代码 + 标准输入 | 结果：曲线采样、交点、极值、向量场数据、分形像素、运行输出 |
| 页面身份：`route.path` 作为键、`kind` 认领 | 撤销/重做栈、错误文本、临时状态 |

### 4.2 按 `route.path` 分页

| 位置 | 行为 |
| --- | --- |
| `pages` | `ref({})`，键是 `route.path`（不带 `#`） |
| `snapshot(route)` | `{version: 1, savedAt, route, pages}` |
| `applySnapshot(obj)` | 校验 `version`，`pages` 必须是对象，只接受 `/` 开头的键 |
| `summary()` | pages 数、routes 列表、blocks 数、curves 数 |

### 4.3 六个绘图页的载荷

`/plot/*` 有 7 条路由、6 个页面组件。各页 `kind` 与载荷字段：

| 路由 | `kind` | 载荷字段 |
| --- | --- | --- |
| `/plot/2d` | `plot` | `expressions`、`view`、`gridMode`、`showGrid`、`params` |
| `/plot/polar` | `plot` | 同上 |
| `/plot/3d` | `plot3d` | `exprInput`、`view{yaw,pitch,zoom}`、`showSurface`、`showWireframe`、`gridN`、`domain`、`params` |
| `/plot/complex` | `plot-complex` | `funcExpr`、`mode`、`xMin/xMax/yMin/yMax`、`resolution` |
| `/plot/vector` | `plot-vector` | `dxInput`、`dyInput`、`view`、`density`、`normalize`、`colorByMagnitude`、`showGrid`、`arrowScale`、`params` |
| `/plot/geometry` | `plot-geometry` | `shapes`、`tool`、`snap` |
| `/plot/fractal` | `plot-fractal` | `view{xmin,xmax,ymin,ymax}`、`maxIter`、`scheme`、`smooth`、`maxSide` |

绘图页共有三条规矩：首帧不回写、形状不符当作没有、每个字段过类型守卫。

### 4.4 还原与回写

| 页面 | 还原时机 | 回写时机 |
| --- | --- | --- |
| `/calc/*` | 挂载时 `restoreFromWorkspace()`，要求 `kind === "calc"` 且 `blocks` 非空 | `watch(blocks, …, {deep:true})`，挂载后才解锁 |
| `/plot/*` | `useState` 惰性初值 | `usePlotWorkspace` 的 effect |
| `/tools/console` | `onMounted` 读 `getPage` | `watch([lang, code, stdin])` |

示例加载优先于工作区还原；工作区还原优先于新页面默认范围。

第五个消费方是 AI 面板：`currentContext(route)` 从工作区载荷取当前现场，只有隐私开关打开且字段非空才写进消息。它读 `p.blocks[].result`，而工作区只存 `expr`/`mode` 不存结果，因此引擎结果这一项在计算页恒为空。

### 4.5 落盘与校验

| 动作 | 路径 |
| --- | --- |
| 保存 | `saveToApp(route)` → `storeWrite("workspace", snapshot(route))` |
| 载入 | `loadFromApp()` → `storeRead("workspace")` → `applySnapshot` |
| 另存为 | `saveTextFile({defaultName:"workspace.mfws.json", …})` |
| 从文件打开 | `openTextFile` → `JSON.parse` → `applySnapshot` |

「载入」不是自动发生：`loadFromApp()` 只有一个调用点，即设置面板的「载入」按钮。刷新或重启后内存里的 `pages` 是空的，必须显式点一次。

坏输入不静默：版本比程序新拒绝、文件非 JSON 拒绝、缺 `pages` 拒绝、全非法键拒绝、磁盘文件损坏报错保留原文件、未保存过提示。

## 5. 外观偏好的存储方式

外观是 `localStorage` 的 `mf_*` 键，工作区文件没有它的字段，整机迁移由导入/导出设置承担。

| 理由 | 证据 |
| --- | --- |
| 外观不落设置目录 | `lib/bridge.js` 写 `localStorage` |
| 工作区 schema 无其位置 | `snapshot()` 只有 `{version, savedAt, route, pages}` |
| 迁移由备份解决 | `collectPrefs()` 收所有 `mf_` 前缀键，导入写回 `localStorage` |

界面语言 `mf.lang` 也在这一层，不进工作区但随备份走。

## 6. 验证命令

```powershell
# 设置目录样本（机器状态，非契约）
Get-ChildItem (Join-Path $env:LOCALAPPDATA 'MFMath\settings') -File | Select-Object Name, Length
```

端到端用例：`cdp-settings.mjs`、`cdp-settings-io.mjs`、`cdp-workspace.mjs`、`cdp-shortcuts-prefs.mjs`、`cdp-plot-workspace.mjs`，均需宿主，由 `tests/run-all.ps1` 统一登记。
