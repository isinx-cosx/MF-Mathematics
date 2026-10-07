# 文档地图

> **本文只回答一个问题：我想知道某件事，该读哪一份？**
>
> 这份地图同时是**文档建设进度的唯一台账**：`✅` 是已经写好的，`🚧` 是本文档计划里已定名、
> 尚未动笔的。**不要给 `🚧` 的条目写链接** —— 死链比缺文档更糟。

**最后核对**：2026-10-07 · 计划档位：**标准（35 份）** · 已落地 5 份

---

## 0. 先分清两类文档

这个仓库里的文档有两种**寿命**，混在一起看会误判：

| 类别 | 会不会过期 | 有哪些 | 怎么读 |
| --- | --- | --- | --- |
| **手册（handbook）** | 慢 —— 只在架构/契约真的改了才动 | 就是本文地图里的 6 层 | 可以当"现状说明"信 |
| **状态类** | 快 —— 每天甚至每小时都在变 | [docs/PROJECT-BOARD.md](PROJECT-BOARD.md)、[docs/OPEN-ITEMS.md](OPEN-ITEMS.md)、[MF_UI/BUGS.md](../MF_UI/BUGS.md)、[docs/STATUS-and-ROADMAP.md](STATUS-and-ROADMAP.md) | 必须看**时间戳**；过一天就要重新核 |

**判据**：一段话如果"明天可能就不成立"，它属于状态类，**不要写进手册**；
写进手册的必须是"改了就是设计变更"的东西。这条界线就是本仓库"结论必须带时间戳"的落地方式。

---

## 1. 六层结构

```
层1  README          入口：是什么 + 3 分钟导览 + 本地图
层5  设计理念         为什么这么做（读代码前先读它，否则会把设计当缺陷）
层4  链接层           前端 ↔ 宿主 的契约（层2/层3 都要引用它）
层2  引擎             C++ 计算层
层3  前端             Vue 壳 + React 绘图组
层6  全面介绍软件      用户向：能做什么、不能做什么、怎么排障
```

**为什么这个顺序**：层5 定口径 → 层4 定契约 → 层2/层3 是契约两侧的实现 →
层6 最后写（它要引用前面全部）。**按这个顺序写，不会出现"写完发现口径变了"。**

---

## 2. 按问题查（先看这张）

| 我想知道 | 读 |
| --- | --- |
| 这是什么软件、能做什么 | [README.md](../README.md)（→ 层6 写完后迁往 `docs/manual/README.md`） |
| 怎么构建 / 怎么跑起来 | [README.md](../README.md) 的「快速开始」；宿主侧以 [ACCEPTANCE.md](../MFMath.Host.Rust/docs/ACCEPTANCE.md) 为准 |
| 为什么前端一行数学都不算 | [DESIGN.md](DESIGN.md) §2 ① |
| 为什么"算不出来"是真的算不出来 | [DESIGN.md](DESIGN.md) §2 ②、`docs/engine/BOUNDARIES.md`🚧 |
| 引擎有哪些函数、怎么调 | `docs/engine/README.md`🚧、`docs/engine/CONTRACT.md`🚧 |
| 某个 action 的参数键名是什么 | `docs/engine/MODULES.md`🚧；**权威源是** [`engine-signatures.json`](../MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json)（424 个 action） |
| 前端怎么把界面接到引擎 | `docs/ui/ENGINE-BINDING.md`🚧 |
| 绘图页是怎么组织的 | `docs/ui/PLOT.md`🚧 |
| 宿主对象有哪些方法 | `docs/link/OBJECTS.md`🚧；**权威源是**宿主启动日志（9 对象 / 84 方法） |
| 前端和宿主之间的接缝是什么 | `docs/link/README.md`🚧；现有最全的是 [LINK-LAYER.md](../MFMath.Host.Rust/docs/LINK-LAYER.md) |
| 凭据存在哪、安不安全 | `docs/link/CREDENTIALS.md`🚧 |
| 为什么 .NET 宿主被废弃 | [DECISIONS.md](DECISIONS.md) D-006 |
| 哪些功能明确不做 | [DESIGN-BOUNDARIES.md](DESIGN-BOUNDARIES.md) |
| 现在还有什么没做完 | [OPEN-ITEMS.md](OPEN-ITEMS.md)（功能）、[PROJECT-BOARD.md](PROJECT-BOARD.md)（进度与风险） |
| 现在有哪些确证的缺陷 | [MF_UI/BUGS.md](../MF_UI/BUGS.md) |
| 谁能改哪些文件、怎么提交 | [AGENTS.md](../AGENTS.md) |
| 怎么复现宿主验收 | [ACCEPTANCE.md](../MFMath.Host.Rust/docs/ACCEPTANCE.md) |
| 怎么打包 | [PACKAGING.md](../MFMath.Host.Rust/docs/PACKAGING.md) |

---

## 3. 六层 × 35 份：建设台账

### 层 1 · README（2 份）

| 文件 | 状态 | 回答什么 |
| --- | --- | --- |
| [README.md](../README.md) | ✅ | 这是什么 + 导览 + 文档地图入口 |
| 本文（`docs/README.md`） | ✅ | 文档地图与建设进度 |

### 层 5 · 设计理念（3 份）

| 文件 | 状态 | 回答什么 |
| --- | --- | --- |
| [DESIGN.md](DESIGN.md) | ✅ | 六条设计理念：每条一句话 + 代码里的对应机制 + 违反它会发生什么 |
| [DECISIONS.md](DECISIONS.md) | ✅ | 决策记录（ADR）：每条含背景 / 决定 / **代价** / 现状 / 出处 |
| [DESIGN-BOUNDARIES.md](DESIGN-BOUNDARIES.md) | ✅ | 明确不做、推迟、能力边界 —— 并写明**推翻它的门槛** |

### 层 4 · 链接层（6 份）

> 这 6 份都是**新文件**，但其中 2 份还兼着"替存量"的作用 —— 别把两笔账混在一句话里
> （我在本文件的初稿里就混过一次）：
> - `FEATURES.md` 写完后**退役 4 份存量文档**（[ONLINE-SEARCH.md](ONLINE-SEARCH.md)、
>   [ACCOUNT.md](ACCOUNT.md)、[UPDATE-CHAIN.md](UPDATE-CHAIN.md)、[SETTINGS-BACKUP.md](SETTINGS-BACKUP.md)）——
>   它们讲的是**已废弃的 .NET 实现**，即 R7 债；
> - `HOSTS.md` 接替 [LINK-LAYER.md](../MFMath.Host.Rust/docs/LINK-LAYER.md) §9 的"两宿主并存"前提。
>
> 所以这一层的账是：**新增 6 份、退役 4 份、净 +2**。

| 文件 | 状态 | 回答什么 | 权威源 |
| --- | --- | --- | --- |
| `docs/link/README.md` | 🚧 | 接缝是 `AddHostObjectToScript`（**不是 invoke**）、三条契约、为什么同步是硬需求 | LINK-LAYER §1 |
| `docs/link/OBJECTS.md` | 🚧 | 9 个宿主对象 × 84 个方法的权威表 | 宿主启动日志 + ACCEPTANCE §2 |
| `docs/link/JOBS-PUSH.md` | 🚧 | 异步 job 通道 + 下行推送信封 `{topic,seq,ts,payload}` | `jobs.rs` / `push.rs` |
| `docs/link/CREDENTIALS.md` | 🚧 | DPAPI 只存宿主 vs AI 明文 `ai.json`；两个宿主不通用 | LINK-LAYER §8/§9 |
| `docs/link/FEATURES.md` | 🚧 **接替 4 份存量** | 搜索 / 账号 / 更新 / 设置备份 / 控制台组件（**偿还 R7 债**：那 4 份现存文档写的是已废弃的 .NET 实现） | [ONLINE-SEARCH.md](ONLINE-SEARCH.md) 等 4 份 |
| `docs/link/HOSTS.md` | 🚧 **接替 LINK-LAYER §9** | 宿主谱系：.NET 已废弃 → Rust 现役、切换与退役条件 | LINK-LAYER §9 |

### 层 2 · 引擎（9 份）

| 文件 | 状态 | 回答什么 | 权威源 |
| --- | --- | --- | --- |
| `docs/engine/README.md` | 🚧 | 两个构建目标、C ABI 恰好两个导出、`/WHOLEARCHIVE` 守门、构建与测试入口 | `CMakeLists.txt`、`api.cpp` |
| `docs/engine/CONTRACT.md` | 🚧 | args JSON 形状、**键名契约**、必填参数拒绝计算、"未实现"的返回形状 | `api_helpers.h`、BUGS.md B1/B2/B4 |
| `docs/engine/MODULES.md` | 🚧 | 12 个学科模块逐个：文件/行数/action/能力/边界（**由签名表生成，不手抄**） | `engine-signatures.json`（424） |
| `docs/engine/SYMBOLIC.md` | 🚧 | 符号层：SymEngine/RCP 边界、化简/求导/积分/极限、pretty 与 LaTeX | `symbolic_util.h` 等 |
| `docs/engine/NUMERIC.md` | 🚧 | 数值层：`special_numeric`/`complex_numeric`、容差与精度策略 | 同名头文件 |
| `docs/engine/INPUT.md` | 🚧 | 输入层：`math_input`/`parser_lib` 的归一化与解析（含 `;` 双语义那个坑） | 同名头文件、BUGS.md B2 |
| `docs/engine/PLOT.md` | 🚧 | 采样与视口契约、分形迭代上限 | `plot_api.cpp`、`fractal_api.cpp` |
| `docs/engine/BOUNDARIES.md` | 🚧 | 如实的能力边界 + `NOT_EXPOSED` 口径 | check-ui.mjs 的守卫 |
| `docs/engine/TESTS.md` | 🚧 | 19 个可执行目标 / 16 个 CTest 用例 + 2180 条准确性用例；怎么加一条 | `CMakeLists.txt`、`probe_call` |

### 层 3 · 前端（9 份）

| 文件 | 状态 | 回答什么 | 权威源 |
| --- | --- | --- | --- |
| `docs/ui/README.md` | 🚧 | 两个工程（Vue 壳 + React 绘图组）、`@shared` 共享面、构建链、48 CDP + 3 unit | `package.json`、`tests/` |
| `docs/ui/ARCHITECTURE.md` | 🚧 | 分层（views/components/lib）、路由与导航表、i18n、样式 | `src/router/`、`src/lib/router/nav.js` |
| `docs/ui/ENGINE-BINDING.md` | 🚧 | `ENGINE_MAP`/`engineMapExtra`/`calcArgs`/`viewConfigs`/`asyncPolicy` + 可达性守门 | 同名源码、check-ui.mjs |
| `docs/ui/PLOT.md` | 🚧 | React 6 页 + 共享 plot lib；**Vue 绘图组是冻结的回退资产** | `MFMath.UI.React/src/plot/`、BUGS.md B9 |
| `docs/ui/AI.md` | 🚧 | 页面直连、SSE、步骤视图、`ai.json` 明文密钥的代价 | `src/lib/ai/`（8 文件 2,372 行） |
| `docs/ui/TOOLS.md` | 🚧 | 控制台（CPython/MinGW 组件）/ 函数工具箱（424）/ 历史 / 搜索页 | `views/tools/`、`components/console/` |
| `docs/ui/SETTINGS-WORKSPACE.md` | 🚧 | 设置目录、导入导出、工作区（含 B14 那 6 页载荷形状） | `lib/settings/`、`lib/workspace/` |
| `docs/ui/TUTORIAL-KEYPAD.md` | 🚧 | 教程系统（18 篇 / 30 targets / `PENDING` 纪律）+ 126 键键盘 | `lib/tutorial/`、`tools/check-ui.mjs` |
| `docs/ui/CHECKS.md` | 🚧 | 四道构建闸门 + "守卫必须验证过会失败"的规矩 | `npm run check` 的四个脚本 |

### 层 6 · 全面介绍软件（6 份，用户向）

| 文件 | 状态 | 回答什么 |
| --- | --- | --- |
| `docs/manual/README.md` | 🚧 | 为谁做、能做什么、**不能做什么** |
| `docs/manual/FEATURES.md` | 🚧 | 功能全表：14 学科视图（415 模式）、6 类绘图、工具、AI、学习、系统 |
| `docs/manual/WORKFLOWS.md` | 🚧 | 典型用法：算题、画图、AI 步骤、控制台、导出与工作区 |
| `docs/manual/INSTALL.md` | 🚧 **受限** | 安装与构建。⚠ **阻塞**：Rust 宿主"安装 → 启动"真机验证未走完（见 PACKAGING.md），在此之前只写现状与验法，不写"照着做就能跑" |
| `docs/manual/TROUBLESHOOTING.md` | 🚧 | 卡死、字体/KaTeX、组件下载、账号/更新、日志与诊断包 |
| `docs/manual/FAQ.md` | 🚧 | 常见问题（为什么算不出来、离线承诺、为什么不上报崩溃、许可证） |

---

## 4. 写文档的规矩（与 [AGENTS.md](../AGENTS.md) §5 同一套）

1. **一份文档只回答一个问题** —— 标题就是那个问题，开头写明"本文只回答…"，并列出与兄弟文档的分工。
2. **能生成的绝不手抄。** 数字（action 数、方法数、用例数）必须能由命令复跑出来。
   手抄一遍，就是下一个 `BUGS.md` §0.2（那份"全绿"表格被后续提交推翻）。
3. **结论带时间戳与产物。** 写成"**2026-10-07 在 <产物> 上实测**"，不写"应该没问题"。
4. **失败要分类**：产品缺陷 / 用例自身判据错 / 环境没准备好 —— 三种不能混着写。
5. **修完就删。** 手册里写"待补"的条目，补完就把标记删掉；状态类文档里的条目，
   修完就删条目本身。留着不删，它就会变成没人信的摆设。
6. **不确定就不写。** 没验证过的路径，写明"未验证 + 怎么验"，**不要**替它背书。

---

## 5. 这份台账怎么维护

- **加一份文档**：先在本文件 §3 对应层里登记"文件 + 回答什么 + 权威源"，**再**动笔；
- **写完了**：把 🚧 改成 ✅ 并加上链接 —— 一次提交只做这一件事；
- **档位变更**：改本文 §3 的表格，并在提交信息里写明理由。
