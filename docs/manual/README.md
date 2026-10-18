# MF-Mathematics v2.0 产品说明

> 本文回答：这是什么软件、给谁用、能做什么、不能做什么。
> 功能全表见 [FEATURES.md](FEATURES.md)，操作步骤见 [WORKFLOWS.md](WORKFLOWS.md)，
> 构建与安装见 [INSTALL.md](INSTALL.md)，出问题见 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)，零散问题见 [FAQ.md](FAQ.md)。

## 1. 这是什么

MF-Mathematics 是一个 Windows 桌面数学工作台。它把计算、绘图、工具和教程放在同一个程序里，
本地完成绝大部分工作，断网后核心功能照常。

软件由三层组成：

| 层 | 作用 |
| --- | --- |
| C++ 计算引擎 | 承担全部数学计算，界面和 AI 都不自行算数 |
| Rust 宿主 | 负责程序窗口、文件读写、联网与组件下载 |
| Vue 界面 | 负责展示与操作，内部嵌一个 React 绘图组 |

平台与运行环境：

| 项 | 取值 |
| --- | --- |
| 操作系统 | Windows 10 / 11（64 位） |
| 运行时 | WebView2（Windows 11 自带，Windows 10 需安装） |
| 许可证 | 暂未提供，保留所有权利 |

计算结果的来源只有引擎一个。引擎注册了 424 个可调用函数，界面、控制台与 AI 助手都通过同一个
入口调用它们。

## 2. 给谁用

| 你是 | 先读什么 |
| --- | --- |
| 想拿它算题、画图、看步骤 | 本文，然后是 [WORKFLOWS.md](WORKFLOWS.md) 与 [FEATURES.md](FEATURES.md) |
| 想判断它到底能干什么 | 本文与 [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) |
| 想构建或安装 | [INSTALL.md](INSTALL.md) |

软件面向需要数学计算与可视化的人：学生、教师、需要快速验证计算的人。它不替人完成需要独立
判断的任务，算不出来的地方会如实说明。

## 3. 能做什么

| 分区 | 内容 |
| --- | --- |
| 学科计算 | 1 个基础运算页加 14 个学科视图，共 393 个模式 |
| 绘图 | 7 个绘图入口，覆盖函数、曲面、复平面、向量场、几何与分形 |
| 工具 | 联网搜索、控制台、函数工具箱 |
| AI | 助手对话与分步讲解，数值由引擎给出 |
| 学习 | 18 篇交互教程、示例任务库、数学键盘 |
| 系统 | 设置面板、工作区保存、图片导出、账号、更新检查、深浅色主题 |

### 学科计算

左侧「计算模式」共 15 项：基础运算加 14 个学科视图（代数、微积分、解析几何、数列、线性代数、
概率论与数理统计、数值分析、数论、实分析、泛函分析、复分析、代数拓扑、测度论、调和分析）。
每个学科视图按学科组织一批计算模式，模式列表与数量见 [FEATURES.md](FEATURES.md)。

### 离线范围

断网后本地计算、绘图、教程、控制台照常使用。只有联网搜索、账号与 AI 助手需要网络。更新检查
默认关闭，不会在启动时联网。

## 4. 不能做什么

| 类别 | 内容 |
| --- | --- |
| 能力边界 | 非初等函数的不定积分返回「未实现」，部分不定式极限与复变不定积分同理 |
| 明确不做 | 搜索不翻页、不抓网页正文；绘图不导出 SVG/PDF；更新不自动下载或执行安装包 |
| 推迟 | 更新回滚、AI 多模态、历史导出为文件等 |
| 尚未验证 | 安装包在其它 Windows 版本与高 DPI 缩放下的表现、部分绘图页的工作区往返 |

能力边界的完整清单与推翻条件见 [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md)。

需要单独说明的是安装包：安装器已经自带（`MFMath.Installer/`），一条命令
`.\MFMath.Installer\tools\build-setup.ps1` 出包，产出的 `Multifunctional-Mathematics_<版本>_x64-setup.exe`
约 18 MB，「安装 → 启动 → 卸载」已在 Windows 11 本机上跑通。安装包**没有数字签名**，首次运行会弹
SmartScreen，点「更多信息 → 仍要运行」即可。未验证的是其它 Windows 版本与高 DPI 缩放下的表现。
详见 [INSTALL.md](INSTALL.md) 的「安装包」一节。

## 5. 数据与隐私

| 项 | 内容 |
| --- | --- |
| 数据目录 | `%LOCALAPPDATA%\MFMath`，设置文件在 `settings` 子目录 |
| 日志 | 只写本地 `logs` 目录，不上传 |
| 崩溃 | 只写本地，不联网上报 |
| 凭据 | 登录 token 与搜索 App ID 用系统加密存储；AI 的 API Key 以明文存在 `settings\ai.json` |

诊断与备份都会排除凭据。详情见 [../link/CREDENTIALS.md](../link/CREDENTIALS.md)。

## 6. 数字复核

本文提到的数字都由命令得出，随代码变化。在仓库根目录执行：

```powershell
# 引擎注册函数数，应为 424
& MF_Mathematics\build\bin\Release\probe_call.exe list_functions '{}'

# 学科视图数与模式数，应为 14 个视图 / 393 条模式 / 391 个不同名字
node --input-type=module -e "const m=await import('./MF_UI/MFMath.UI.Vue/src/lib/engine/viewConfigs.js');const ks=Object.keys(m.VIEW_CONFIGS);let t=0;for(const k of ks)t+=m.VIEW_CONFIGS[k].modes.length;const a=ks.flatMap(k=>m.VIEW_CONFIGS[k].modes);console.log(ks.length,t,new Set(a).size)"

# 导航项数，应为 27
node --input-type=module -e "const m=await import('./MF_UI/MFMath.UI.Vue/src/lib/router/nav.js');let n=0;for(const g of m.NAV_GROUPS)n+=g.items.length;console.log(n)"
```

引擎产物 `probe_call.exe` 由三步构建的第一步产出，仓库不含编译产物。
