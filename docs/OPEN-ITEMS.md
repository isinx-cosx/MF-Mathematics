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

**功能面已无缺口**（AI 加速按钮已落地）；**设置面板里没有「待实现」项**；
教程引导目标 **30/30 全部实现**（`PENDING` 已空）。
其余未完成项分三种性质：**外部依赖**（组件 zip 上传）、**等你拍板**、**明确不做/推迟**。另有 6 项等你拍板。

> **2026-10 后续核对（已按"修完就删"更新本文）**：本文件此前有三处已经过期，均已改正 ——
> ①「20 处已知失败基线」→ `cdp-engine-coverage` 的 `KNOWN_FAIL` **已为空**，实测 393/0；
> ②「AI 加速按钮 / step_viewer.content 仍在 PENDING」→ **PENDING 已是空对象**，教程目标 30/30；
> ③「v1 Python 清零」→ **已执行**（见 §4）。
> 留这段是因为它自己写着"修完不删就会变成没人信的摆设"—— 那次它真的过时了。

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

**要做的事**：在服务器上发布站点仓库的 `739c79f`（续期端点 + 记住我）、
`aeb3233`（`token_version` + 契约验证脚本）与**本轮**的 `/api/version` 补 sha256（站点侧提交见下）。
部署方式是 `git archive HEAD -o mvs-site.tar` → `scp` → 解包 → **`npm run build`** → `systemctl restart`
（⚠ 必须重跑 `next build`：`next start` 服务的是构建产物，只换源码不重建，新路由不会出现）。

**验证方式**：部署后再跑上面的探针，`/api/token/refresh` 应返回 `401 {"detail":"未认证"}`；
`/api/version` 的 `data` 里应出现 `sha256` 与 `size`。

**另一个环境发现（2026-10）**：在本机，**.NET 侧到生产站点的 TLS 建立失败**
（错误原文 `The SSL connection could not be established`），而 Node 侧（`fetch`）正常。
影响：账号登录 / 更新检查**对着线上会失败**（错误分类为 `network`，本地功能不受影响）。
怀疑与服务器 TLS 配置或本机 Schannel 有关，需要单独排查 —— 它不是本项目代码的问题，
但会让人误以为"账号功能坏了"。

---

## 2. 已定、但我还没做的

**（本轮清空）** —— 更新链与分步显示的渲染层都已落地：
- 更新链见 `docs/UPDATE-CHAIN.md`（端到端 `cdp-update.mjs` 37 / 0）；
- 分步显示的渲染层见 `docs/STEP-VIEW.md`（步骤 = AI 调引擎的记录；端到端在 `cdp-ai.mjs` ②d/②e/②f）。

现在没有任何"已定但未做"的功能项了。

---

## 3. ~~用户可见的接线问题：引导指不到 AI / 搜索~~（**本轮已修**）

修法：给 AI 面板与搜索页补上**与教程同名**的 `data-tour`（沿用 v1 的语义 ID，教程与 YAML 原件不用改），
并把 5 个条目从 `PENDING` 删掉、理由从"尚未实现"改成**真实前置条件**（"先点顶栏的「AI」把抽屉打开"、
"搜索在「工具 → 搜索」这一页"）。构建自检现在报 **31 个教程目标里 29 个已实现 / 2 个待实现**
（只剩真缺口：AI 加速按钮、分步显示），警告也清了。

端到端补了断言：`cdp-ai`（`ai_dialog.input` / `send_button` / `context_label` 能定位到可见控件）、
`cdp-search`（`search_panel.input` / `results`）。

**为什么静态检查当初没拦住**：`check-ui.mjs` 只查"目标要么在源码里真有 `data-tour`、要么在 PENDING 里写明理由"
与"PENDING 不留过时条目" —— 名字对不上时两条都满足。所以这次的教训写进了 `targets.js` 的注释：
**新界面落地时同一步骤里既补 `data-tour`、也删 PENDING 条目**。

| 教程里的 target | 当时的问题 | 现在 |
| --- | --- | --- |
| `ai_dialog.input` / `.send_button` / `.context_label` | 面板挂的是 `data-ai=*`，名字对不上 | 已补同名 `data-tour` |
| `search_panel.input` / `.results` | 页面挂的是 `data-search=*` | 已补同名 `data-tour` |
| `main_window.ai_settings` | 面板未就绪时才出现的"去设置"按钮 | 已挂上（静态检查覆盖；它只在 blocked 状态可见，故不做 CDP 断言） |
| `step_viewer.content` / `calc_block.ai_accel_button` | **真的没做** | 仍在 PENDING（理由已改成真实原因） |

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

**本轮之后，设置面板里已经没有任何 `pending` 项；教程引导只剩 1 个待实现目标。**

| 缺口 | 证据 / 出处 |
| --- | --- |
| **AI 加速按钮**（v1 每个计算块上有）| ~~未做~~ **已落地**；`calc_block.ai_accel_button` 已从 `PENDING` 删除，教程目标 30/30 |
| ~~设置 → 更新（6 项）~~ | 已落地（`docs/UPDATE-CHAIN.md`） |
| ~~导入 / 导出设置~~ | **已落地**（`docs/SETTINGS-BACKUP.md`）：凭据不进备份、导入也不清凭据 |
| ~~分步显示的渲染层~~ | **已落地**（`docs/STEP-VIEW.md`）：步骤 = AI 调引擎的记录，`step_viewer.content` 已从 PENDING 删除 |
| **控制台可选组件（sympy / numpy / scipy）** | 清单端点已修复（部署脚本漏打 `components/`，线上 `/api/components` 曾整块报错）；**两个 zip（python 11 MB / mingw 54 MB）尚未上传**，清单里如实标着 `available:false` |
| ~~**v1 Python 清零**~~ | **已执行**：删掉 v1 树的 Python 后端 **277 个 `.py`（2.1 MB）+ 8 个二进制（`.pyd` / `inner_product.dll`，9.5 MB）**。删除前已归档到 `Multifunctional系列\_archive\v1-python-backend-20261006-073851.zip`（2.7 MB）+ v1 自己的 git 历史。**保留** `MF_Mathematics/tests/accuracy/` 的 28 个 `.py`（2180 条准确性用例 —— 它是测试资产、可对任意引擎 DLL 运行，不是"让 v1 跑起来的后端"）。⚠ 那 8 个二进制**无法重建**（两棵树里都没有构建脚本），所以先归档再删 |
| ~~`cdp-engine-coverage` 的 20 处已知失败基线~~ | **已清零**：`KNOWN_FAIL` 现为空对象，实测 393/0（三类原因都查到了根因：`;` 后关键词被归一化拆坏 → 改为只归一化第一段且纯字母词跳过；"算完不弹结果" → 弹窗字段错位与 `modeNeedsInput` 自相矛盾；模式参数问题 → 按引擎签名覆盖 `EXTRA_MAP`）|
| 搜索：**翻页 / 网页正文抓取 / 请求去重限流** | `ONLINE-SEARCH.md` §8（有意不做，记为边界） |
| 历史：**导出为文件**；绘图页操作不入历史 | `MIGRATION-GAPS.md` §2.5（需要宿主文件对话框） |
| 工作区：**外观偏好不入工作区**（现在可以靠"导入/导出设置"整机迁移，但外观仍不进工作区文件） | `MIGRATION-GAPS.md` §2.6 |
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
