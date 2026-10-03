# 未完成清单（Open items）

> **本文只回答一个问题：现在还有什么没实现。**
> 按"卡在谁那里"分类，每条都带证据与出处；修完一项就删一项。
>
> 与另外两份文档的分工：
> - `docs/STATUS-and-ROADMAP.md` —— 全局状态、路线图、风险台账、待你拍板的项；
> - `docs/MIGRATION-GAPS.md` —— 与 v1 的逐项差距（迁移视角）；
> - **本文** —— 可直接当待办清单用的"未完成"汇总（含验证方式，便于复查后划掉）。

**最后核对：2026-10（本轮）**。事实分两类：**实测**（本文写明了命令或探针输出）与
**引自既有文档**（标了出处）。改动前请以实测为准。

---

## 0. 一句话摘要

功能面**缺 4 处**（AI 加速按钮、更新链、分步显示的渲染层、导入/导出设置）；
其余未完成项分三种性质：**已定但我没做**（更新链）、**外部依赖**（站点部署、组件换包）、
**明确不做/推迟**（不欠债）。另有 6 项等你拍板，以及一条**用户可见的接线问题**（引导指不到 AI/搜索）。

---

## 1. ⚠ 卡在部署（最要紧，实测）

站点侧改动**已提交但未部署**，所以账号功能对着线上是半成品：

```text
POST https://mf-vis-science.cn/api/token/refresh  →  404   ← 本轮新增端点，线上没有
GET  https://mf-vis-science.cn/api/me             →  401   ← 老契约在（对照）
GET  https://mf-vis-science.cn/api/version        →  200
```

**影响**：软件里的「记住我」30 天长会话与静默续期**在线上不生效**；`token_version`
（改密即全端下线）同样未生效。

**降级行为是有意的**（所以不算坏掉）：`expires_in` 缺失时改解 JWT 的 `exp`；续期撞 404
只报错、**不会把用户登出**（只有 401 才清登录态）。

**要做的事**：在服务器上发布站点仓库的 `739c79f`（续期端点 + 记住我）与
`aeb3233`（`token_version` + 契约验证脚本）。

**验证方式**：部署后再跑上面的探针，`/api/token/refresh` 应返回 `401 {"detail":"未认证"}`。

---

## 2. 已定、但我还没做的

| 项 | 状态 | 说明 |
| --- | --- | --- |
| **更新链**（提示有新版本 + 打开下载页 + 显示 sha256，**不自动执行安装包**） | 未做 | 你已定形态。前置：站点 `/api/version` 需先补 sha256 清单（要真实安装包才能算，站点 `DOWNLOAD_FILE_PATH` 指向 `dist/Multifunctional-Mathematics-Setup.exe`） |
| **分步显示的渲染层** | 未做 | 语义已定（AI 只能通过 `engine_call` 拿数值，每一步都是引擎算出来的事实）、**地基已落地**（工具调用）；剩下的是把工具记录渲染成"步骤"而不是"工具块" |

---

## 3. 用户可见的接线问题：引导指不到 AI / 搜索（本轮实测发现）

教程步骤引用的目标名，与界面实际挂的钩子**不是一回事**：

| 教程里的 target | 实际钩子（已核对源码） | 后果 |
| --- | --- | --- |
| `ai_dialog.input` | `data-ai="input"` | 3 个步骤高亮不到任何控件 |
| `ai_dialog.send_button` | `data-ai="send"`（停止时是 `data-ai="stop"`） | 同上 |
| `ai_dialog.context_label` | `data-ai="outgoing"`（"将发送什么"那条） | 同上 |
| `search_panel.input` | `data-search="input"` | 2 个步骤同上 |
| `search_panel.results` | `data-search="results"` | 同上 |
| `step_viewer.content` | —— | 分步显示确实没做（见 §2） |

（AI 面板实际钩子共 18 个：panel / status / close / blocked / settings-link / msgs / input /
send / stop / clear / test / outgoing / stream / notices / error / usage / reasoning / tools-live；
搜索页 17 个。补 `data-tour` 时可直接复用这些名字，避免再造一套。）

更糟的是 `src/lib/tutorial/targets.js` 的 `PENDING` 里理由**已经变成假话**：
"AI 助手尚未实现（方案 P3）""在线搜索面板尚未实现"。用户点引导会看到一句错的说明。

**为什么构建自检没拦住**：`tools/check-ui.mjs` 查两个方向（目标要么在源码里真有 `data-tour`、
要么在 `PENDING` 里写明理由；`PENDING` 不留过时条目）—— 这两条它都满足，
"名字对不上"不属于它检查的范畴。

**修法（小）**：给 AI 面板/搜索页补上与教程一致的 `data-tour`（或改教程里的名字），
然后从 `PENDING` 删掉那 5 条。`toolbar.ai_button` 是存在的 ✓，所以入口那条步骤能用。

---

## 4. 功能缺口（有出处，可直接查）

| 缺口 | 证据 / 出处 |
| --- | --- |
| **AI 加速按钮**（v1 每个计算块上有） | `calc_block.ai_accel_button` 目标不存在；v2 未做 |
| **设置 → 更新**（6 项） | `src/lib/settings/catalog.js`：`update.*` 全为 `pending`，组 `depends: 方案 P5` |
| **导入 / 导出设置** | `catalog.js` 的 `storage.io` 仍为 `pending` |
| **控制台可选组件（sympy / numpy / scipy）** | 本地已重建组件包；**站点尚未换包** → 用户下载到的仍是旧的（`MIGRATION-GAPS.md` §0.1） |
| **v1 Python 清零** | **305 个文件 / 61,534 行**未处理；且 `.pyd` 删除前必须先给 5 个算法补返回值（否则静默失效）—— `STATUS-and-ROADMAP.md` 风险台账 |
| **`cdp-engine-coverage` 的 20 处已知失败基线** | 三类：`;` 后关键词被当表达式（7 处）、算完不弹结果（9 处）、模式自身参数/期望问题（4 处）；`FRONTEND-FIXES.md` §4 明确"建议单独立项" |
| 搜索：**翻页 / 网页正文抓取 / 请求去重限流** | `ONLINE-SEARCH.md` §8（有意不做，记为边界） |
| 历史：**导出为文件**；绘图页操作不入历史 | `MIGRATION-GAPS.md` §2.5（需要宿主文件对话框） |
| 工作区：**外观偏好不入工作区**；跨机器迁移整套设置 | `MIGRATION-GAPS.md` §2.6 |
| 绘图：复制到剪贴板、导出 SVG/PDF | `MIGRATION-GAPS.md` §2.7（不在范围） |
| AI：token 估算自校准、首字节超时与重试退避 | `AI-ASSISTANT.md` §8 |

**另有**：`docs/HANG-OPTIMIZATION.md` §4 是一份独立的"已知仍未优化"清单
（持续同调 O(n³)、符号矩阵 >12×12、`roots_in_disc` 密集求值、`expand((x+1)^10000000)`），
本文不重复，改动那部分时以该文为准。

---

## 5. 明确"不做 / 推迟"（不是欠债）

- 不重建后端（用户系统 / 组件清单 / 版本检测全部复用站点端点）；
- 不重写下载能力（复用 `ComponentDownload.cs`）；
- 不复用已废弃的 HTTP 层（`math_http_service.py` 与 `{code,data.result,msg}` 客户端）；
- 不移植 `MF_AI/agent.py`（含 Python `eval()`）、`strategy.recommend` 等死代码；
- 不照抄 v1 的引导层与外层壳；
- **推迟**：更新回滚、AI 多模态、教程录制回放、离线文档全文搜索。

出处：`STATUS-and-ROADMAP.md` §5「明确不做 / 推迟」。

---

## 6. 等你拍板（6 项，仍未答）

| # | 问题 | 为什么需要你 |
| --- | --- | --- |
| 1 | 控制台的 **Python 语言支持**是否保留 | 它是给用户写程序的可选运行时组件，不是我们的实现代码；影响"只用 C++/C#/JS·TS"这条边界怎么认定 |
| 2 | 是否允许 **Node 作为构建工具** | 打包/手册/截图需要一个脚本层；纯 C# 可行但更慢 |
| 3 | **Inno Setup `.iss` / CMake `CMakeLists.txt`** 是否算例外 | 它们是第三方工具的声明式配置；要求严格可改 WiX/MSIX |
| 4 | 是否给 **AI / 云功能加登录门禁** | 需站点按 `balance` 扣减，后端目前没有这个语义 |
| 5 | **配额制**（免费 5 次步骤 / 3 次加速）是否保留 | 保留则云服务要能对账（现状是纯本地计数 + 有 API Key 就绕过） |
| 6 | 站点仓库那批**不是我改的未提交内容**（当时 65 项，品牌 SVG 等）是否保留 | `STATUS-and-ROADMAP.md` §3.4 第 6 条 |

§3.5 里第 4 项（AI 分步语义）本轮已由你决定并落地，见 §2。

---

## 7. 建议顺序

1. **部署站点**（§1）—— 否则账号那条在线上是半成品；
2. **修引导接线**（§3）—— 小、用户可见、顺带删掉 `PENDING` 里的假话；
3. **更新链**（§2）—— 你已定形态；
4. 其余按 §6 的答复推进。

---

## 8. 怎么复查这份清单

```powershell
$V2 = "…\Multifunctional-Mathematics-v2.0"
# ① 前端自检（引导目标、示例覆盖、键盘、教程）—— §3、§4 的接线类
npm run check:ui --prefix "$V2\MF_UI\MFMath.UI.Vue"
# ② 站点契约与端点（本机临时库，不碰生产）—— §1
node "$SITE\scripts\verify-client-api.mjs"
# ③ 生产是否已部署（无害探针，别拿真账号猜密码：5 次失败会锁 15 分钟）
#    POST https://mf-vis-science.cn/api/token/refresh   → 期望 401（未部署时是 404）
# ④ 全套端到端（19 个用例）
powershell -File "$V2\MF_UI\MFMath.UI.Vue\tests\run-all.ps1"
```

**维护规矩**：这份清单跟 `PENDING` / `KNOWN_UNAVAILABLE` 一样的纪律 ——
**修完就删**。留着不删，它就会变成一份没人信的摆设（v1 的 34/66 步失效就是这么来的）。
