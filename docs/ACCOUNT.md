# 用户系统（软件 ↔ 服务器）

> 🚩 **已退役（2026-10-07）**：本文的实现表讲的是**已废弃的 .NET 宿主**（`MFMath.Host/*.cs`）。
> **现役 Rust 侧的对应内容见 [`docs/link/FEATURES.md`](link/FEATURES.md) §2** ——
> 含逐条核对后的端点表、脱敏边界，以及"**401 或 403** 才清登录态"这条更正。
>
> **本文暂不删除**：仓库里还有多处引用它（12 个文件 / 41 处，清单见
> [`docs/PROJECT-BOARD.md`](PROJECT-BOARD.md) §3 R8），等引用改完再删。
> **引用本文任何一处数字前，请先核对 `FEATURES.md`。**

> 落地于本轮。**服务器侧不需要新造接口** —— 站点早就有面向客户端的 Bearer token API；
> 本轮补的是它缺的那一块（长会话与续期），以及软件侧一整套客户端。

## 1. 先回答"服务器有没有向软件开放的端口"

有。生产站点 `https://mf-vis-science.cn`（Next.js，`src/app/api/*`）已经是一套
**面向桌面客户端**的接口，契约本身写着"桌面客户端兼容"：

| 端点 | 方法 | 入参 | 返回 |
| --- | --- | --- | --- |
| `/api/login` | POST | 表单 `username, password[, remember]` | `{access_token, token_type:"bearer", expires_in}` |
| `/api/token/refresh` | POST | 表单（可带 `remember`）+ Bearer | 同上（**本轮新增**） |
| `/api/me` | GET | Bearer | `{username, email, balance, has_ai_service, role, is_active}` |
| `/api/register` | POST | JSON `{username, email, password, code?}` | `{msg}` |
| `/api/send-code` | POST | JSON `{email}` | `{msg}` |
| `/api/verify-code` | POST | 表单 `username, code` | `{msg}` |
| `/api/resend-code` | POST | 表单 `username, email` | `{msg}` |
| `/api/change-password` | POST | 表单 `old_password, new_password` + Bearer | `{msg}` |
| `/api/login-history` | GET | Bearer | `{items:[…]}` |
| `/api/logout` | POST | Bearer | `{msg}`（把 jti 加入黑名单） |
| `/api/version` | GET | — | 信封 `{code:0, data:{latest, date, download_url}}` |

两条约定必须照做：

- **失败体是 `{detail: "…"}`**（站点注释里就写着"桌面端依赖 detail"）。所以界面上显示的是
  服务器的原话（"用户名或密码错误"、"登录尝试次数过多，请 15 分 0 秒后再试"），不是我们编的。
- **认证是 `Authorization: Bearer <jwt>`**（HS256，payload 带 `jti` 供黑名单使用）。
  站点早期的登录路径 `/login`（FastAPI 路径）已经 404，现行路径是 `/api/login`。

实测（只做无害 GET，没去猜密码以免触发登录锁定）：

```
GET https://mf-vis-science.cn/health        → 200 {"code":0,"data":{"status":"healthy","version":"1.2.0"}…}
GET https://mf-vis-science.cn/api/version   → 200 {"code":0,"data":{"latest":"1.2.0",…}}
GET https://mf-vis-science.cn/api/me        → 401 {"detail":"未认证"}       ← 契约在
GET https://mf-vis-science.cn/api/login     → 405（POST 路由存在）
GET https://mf-vis-science.cn/login         → 404（早期路径已下线）
```

## 2. 服务器侧补的那一块：会话

**缺口**：access_token 只有 30 分钟，**没有续期端点**。网站里点一下就好，
桌面软件却是"用着用着突然被登出"。本轮补两条，且**网站行为一字不改**：

1. `POST /api/token/refresh`（新）：用当前有效 token 换一枚新的。
   - **只认有效 token**：过期就必须重新登录 —— 续期不会变成"过期凭证复活"；
   - 登出把 jti 加入黑名单后，**续期也会被拒**（不能让登出被绕过）；
   - 续期**不写登录历史**（它不是一次新的登录，写进去只会污染"最近登录"）；
   - 有宽松的频率上限（120 次/小时/IP），只挡异常刷接口。
2. 登录/续期支持可选 `remember` → 换 30 天长 token（桌面端「记住我」）。
   网站登录框不传这个字段，行为与以前完全一致。

共用实现放在站点 `src/lib/session.ts`（策略一处：`wantsRemember` / `sessionMinutes` /
`expiresInSeconds`），登录与续期都调它。**为什么不引 refresh_token**：本项目会话是
JWT + jti 黑名单，加 refresh_token 要再引入"轮换 / 二次废止 / 存储"三件事，收益只是把
"长期 token"换成"长期 refresh + 短期 access"；桌面端的 token 由 DPAPI 加密落盘，
威胁模型与浏览器 localStorage 不同，所以选了简单可审计的那条路。

### 站点侧验证（本机、临时库、不碰生产/不碰真实 dev 库）

用真实 `mvs.db` 的 schema 只读拷出一份临时库、种一个测试用户，起 `next dev` 跑完整流程：

```
① 短会话登录 expires_in=1800（与网站一致，行为未变）
② /api/me 返回本人与公开字段
③ 静默续期成功、换了一枚新 token、新 token 可用
④ remember=1 → expires_in=2592000（30 天），续期时也生效
⑤ 登出 → /api/me 401；**登出后的 token 续期也 401**（黑名单不可绕过）
⑥ 失败路径仍是 {detail:"…"}
RESULT|site-api|16|0
```

## 3. 软件侧结构

| 文件 | 职责 |
| --- | --- |
| `MFMath.Host/AccountApi.cs` | 站点契约的客户端：三个动词、`{detail}` 解析、JWT `exp` 解析、资料/历史归一化 |
| `MFMath.Host/AccountConfig.cs` | 配置与会话落盘（token 为 DPAPI 密文）；站点地址闸门 |
| `MFMath.Host/AccountBridge.cs` | 桥面：`Info/Configure/LoginEx/Logout/RefreshProfile/RefreshToken/EnsureFresh/Register/SendCode/VerifyCode/ResendCode/ChangePassword/LoginHistory/SiteVersion/ClearLocal/SelfCheck` |
| `src/lib/account/bridge.js` | 页面侧状态、失败分类→"下一步怎么办"、推送订阅 |
| `src/views/account/AccountView.vue` | 账号页（`/account`）：登录 / 注册 / 我的账号 / 改密 / 登录记录 |
| `src/components/settings/AccountGroup.vue` | 设置 → 账号：站点地址、会话策略、本机凭据、离线承诺、自检 |
| `src/App.vue` | 顶栏登录态（未登录显示「登录」，登录后显示用户名） |

## 4. 四条纪律

1. **离线优先，绝不阻塞**（最重要的一条）
   `Info()` 只读本地状态（自检里断言它 < 50 ms，不碰网络）；所有网络调用异步 + 超时；
   断网时界面显示**上次登录缓存的资料**并明确标注「未校验」，不假装是刚取到的。
   **未登录、不登录、断网、站点挂了 —— 本地全部计算功能照常可用**（端到端用例真的把
   假服务器杀掉，然后在计算页按 7 + 8 = 得出 15）。
2. **token 只在宿主**：DPAPI 密文落盘，页面只见 `loggedIn/username/balance`。
   端到端断言三处都读不到：脱敏视图、页面 DOM、落盘文件。
3. **不合并失败**：`unauthorized / ratelimit / network / timeout / aborted / parse / config`
   分开，服务器原话原样显示，界面只补一句"下一步怎么办"。
4. **站点地址是安全边界**：只接受 http/https，拒绝查询串、片段、`user@host` ——
   这个值决定 token 被发往哪里，能塞 `https://evil@host` 就麻烦了。

## 5. 验证

| 用例 | 内容 | 结果 |
| --- | --- | --- |
| 站点契约（本机临时库） | 见 §2 的六组 | **16 / 0** |
| `cdp-account.mjs`（自带 `tests/fake-account-server.mjs`，**按站点契约实现**） | 15 组断言：契约（登录/续期/me/登出/注册/验证码/改密/登录记录/站点版本）· 长会话与短会话 · **token 三处都读不到** · **服务端单方面作废 → 401 被认真处理并清掉登录态** · 未登录时的受保护操作给明确提示 · 失败分类（含 429 限流原话、超时、断网）· 自检六项 · **离线承诺**（断网后仍显示缓存资料并标未校验、本地计算照常出 15、仍能退出登录）· 收尾还原生产地址 | **52 / 0** |
| 全套回归（19 个用例） | — | 见 STATUS |

## 6. 设计取舍

| 旧版行为（`MF_User/`，login_dialog.py 33 KB） | 现在 | 为什么 |
| --- | --- | --- |
| `/login`（FastAPI 老路径） | `/api/login`（Next 路径） | 老路径已 404；契约仍是 OAuth2 form + bearer，兼容面没丢 |
| token 存在 `users.json`（明文） | DPAPI 密文（`account.json`） | 明文 token 等于明文密码 |
| 30 分钟过期就重新登录 | 「记住我」30 天 + 临期静默续期 | 桌面软件不该每半小时踢一次 |
| 登录对话框（模态） | **路由页面** `/account` + 顶栏登录态 | 账号要能边看边操作；且不弹模态窗 |
| 未登录时功能受限 | **未登录/断网不影响任何计算** | 计算全在本地引擎里，账号只是身份与额度 |

## 7. 已知边界

- **改密码不会立刻作废已发出的 token**（站点实现如此）。界面如实说明：要立刻踢掉需在站点登出。
  这是站点的既有行为，我没改它 —— 改它属于"会话策略变更"，应该单独决策。
- **AI 服务状态只显示不做限制**：账号页显示站点侧的 `has_ai_service` 与额度，
  但桌面端 AI 助手仍用用户自己填的接口与密钥（两者互不影响）。要不要让 AI 走站点额度
  是产品决策，不是这一轮能替他定的。
- **没有做"未登录也能用云同步/云历史"**：本轮只打通身份，没有引入任何"数据放服务器"的行为。
- **站点版本只读**：`/api/version` 能取到 `latest/date/download_url`，但更新链（校验 sha256、
  下载安装包、原子替换）仍是 P5，未做。
