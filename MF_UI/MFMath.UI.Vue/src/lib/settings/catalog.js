/**
 * settings/catalog.js — 设置项目的目录（唯一真相源）
 *
 * 为什么把"有哪些设置项"单独抽成数据：设置面板是一个**容器**，分组会陆续填内容
 * （外观/引擎/组件现在就能做，搜索依赖 P1、AI 依赖 P3、更新依赖 P5）。
 * 有了这份目录：
 *   · 顶部搜索能按名字/关键词**跳到具体某一项**（而不是只筛分组）；
 *   · 每个分组的"完成了哪些、还缺哪些"一目了然，占位分组也能显示"将提供什么"；
 *   · 构建期脚本可以断言"catalog 里的项都在界面上有对应行"（避免又出现
 *     v1 那种"看起来有、实际没有"的静默缺口）。
 *
 * status 取值：
 *   "ready"   已有实现，做完即可用
 *   "partial" 部分可用（例如历史/工作区管理依赖 P1）
 *   "pending" 依赖其它缺口，本轮只显示占位与依赖说明
 */
export const GROUPS = [
  { id: "appearance", label: "外观", status: "ready", note: "改了就生效，没有保存按钮" },
  { id: "engine", label: "引擎", status: "ready", note: "出问题时用来自助排查" },
  { id: "components", label: "组件", status: "ready", note: "可选下载的运行时" },
  { id: "ai", label: "AI", status: "pending", depends: "方案 P3（AI 助手 + 推送通道）" },
  { id: "search", label: "搜索", status: "pending", depends: "方案 P1（在线搜索面板）" },
  { id: "update", label: "更新", status: "pending", depends: "方案 P5（站点 /api/version 需先补 sha256）" },
  { id: "storage", label: "存储与数据", status: "partial", depends: "历史/工作区管理依赖 P1" },
];

/**
 * 设置项目录。group 对应上面的分组 id；id 会渲染成 data-setting 属性，供搜索跳转定位。
 * keywords 用于模糊搜索（中英文都要给，用户可能敲任一种）。
 */
export const ITEMS = [
  // ── 外观（现在就能做：复用既有 10 套配色 + 四维外观）──
  { id: "appearance.mode", group: "appearance", label: "主题模式", keywords: "亮 暗 跟随系统 theme mode light dark system", status: "ready" },
  { id: "appearance.theme", group: "appearance", label: "配色方案", keywords: "配色 主题 玻璃 极简 北欧 纸质 樱粉 霓虹 终端 palette theme", status: "ready" },
  { id: "appearance.shape", group: "appearance", label: "圆角与阴影", keywords: "形状 圆角 阴影 硬朗 圆润 shape radius shadow", status: "ready" },
  { id: "appearance.density", group: "appearance", label: "疏密", keywords: "紧凑 舒适 留白 density spacing", status: "ready" },
  { id: "appearance.font", group: "appearance", label: "界面字体", keywords: "字体 衬线 等宽 sans serif mono font", status: "ready" },
  { id: "appearance.reset", group: "appearance", label: "恢复默认外观", keywords: "重置 恢复默认 reset default", status: "ready" },

  // ── 引擎（现在就能做：只读展示 + 自检）──
  { id: "engine.version", group: "engine", label: "引擎版本", keywords: "版本 version 桥 bridge", status: "ready" },
  { id: "engine.path", group: "engine", label: "引擎目录", keywords: "路径 目录 path dir 打开 open", status: "ready" },
  { id: "engine.deps", group: "engine", label: "依赖 DLL 状态", keywords: "依赖 dll flint symengine gmp mpfr pthread 完整性", status: "ready" },
  { id: "engine.functions", group: "engine", label: "已注册函数数量", keywords: "函数 数量 action 424 list_functions", status: "ready" },
  { id: "engine.selftest", group: "engine", label: "引擎自检", keywords: "自检 冒烟 测试 selftest smoke 检查", status: "ready" },

  // ── 组件（现在就能做：复用 ConsoleBridge 已有的下载能力）──
  { id: "components.python", group: "components", label: "CPython 组件", keywords: "python cpython 组件 安装 卸载", status: "ready" },
  { id: "components.cpp", group: "components", label: "MinGW 组件", keywords: "mingw cpp g++ 编译器 组件 安装 卸载", status: "ready" },
  { id: "components.dir", group: "components", label: "组件目录", keywords: "组件目录 路径 components dir", status: "ready" },
  { id: "components.source", group: "components", label: "下载源", keywords: "下载源 镜像 地址 url base mirror", status: "ready" },
  { id: "components.cleanup", group: "components", label: "清理未使用组件", keywords: "清理 删除 未使用 cache cleanup", status: "ready" },

  // ── AI（占位：字段名已按 v1 的 MF_AI/config.yaml 对齐，等 P3 填）──
  { id: "ai.enabled", group: "ai", label: "启用 AI", keywords: "启用 开关 禁用 enable disable", status: "pending" },
  { id: "ai.provider", group: "ai", label: "Provider", keywords: "provider 提供商 deepseek openai ollama", status: "pending" },
  { id: "ai.baseUrl", group: "ai", label: "API Base", keywords: "base url 端点 endpoint 地址", status: "pending" },
  { id: "ai.apiKey", group: "ai", label: "API Key", keywords: "密钥 key token dpapi 加密", status: "pending" },
  { id: "ai.model", group: "ai", label: "默认模型", keywords: "模型 model deepseek-chat reasoner v4-pro", status: "pending" },
  { id: "ai.modelMap", group: "ai", label: "角色映射", keywords: "角色 model_map chat sonnet opus haiku fable mythos reasoner", status: "pending" },
  { id: "ai.modelParams", group: "ai", label: "模型参数", keywords: "max_tokens temperature 参数 覆盖", status: "pending" },
  { id: "ai.context", group: "ai", label: "上下文长度", keywords: "上下文 context length 长度", status: "pending" },
  { id: "ai.localModel", group: "ai", label: "本地模型", keywords: "本地 local ollama 路径 auto_detect", status: "pending" },
  { id: "ai.test", group: "ai", label: "测试连接", keywords: "测试 连接 test connection 连通性", status: "pending" },
  { id: "ai.cache", group: "ai", label: "缓存管理", keywords: "缓存 cache 条数 清空 ai_cache", status: "pending" },
  { id: "ai.privacy", group: "ai", label: "隐私说明", keywords: "隐私 说明 privacy 发送", status: "pending" },

  // ── 搜索（占位：依赖 P1）──
  { id: "search.engine", group: "search", label: "搜索引擎", keywords: "引擎 duckduckgo wolfram custom searxng", status: "pending" },
  { id: "search.wolframKey", group: "search", label: "Wolfram App ID", keywords: "wolfram appid 密钥 key", status: "pending" },
  { id: "search.customUrl", group: "search", label: "自定义端点", keywords: "自定义 端点 searxng url", status: "pending" },
  { id: "search.timeout", group: "search", label: "超时", keywords: "超时 timeout 秒", status: "pending" },
  { id: "search.cache", group: "search", label: "缓存管理", keywords: "缓存 cache ttl 清空", status: "pending" },
  { id: "search.privacy", group: "search", label: "隐私说明", keywords: "隐私 说明 privacy 查询", status: "pending" },

  // ── 更新（占位：依赖 P5）──
  { id: "update.version", group: "update", label: "当前版本", keywords: "版本 version 当前", status: "pending" },
  { id: "update.channel", group: "update", label: "更新通道", keywords: "通道 channel stable beta", status: "pending" },
  { id: "update.mode", group: "update", label: "自动检查", keywords: "自动 检查 下载 安装 auto update", status: "pending" },
  { id: "update.interval", group: "update", label: "检查间隔", keywords: "间隔 频率 每天 每周 interval", status: "pending" },
  { id: "update.check", group: "update", label: "手动检查", keywords: "手动 立即检查 check now", status: "pending" },
  { id: "update.source", group: "update", label: "更新源", keywords: "更新源 地址 url source", status: "pending" },

  // ── 存储与数据（部分可用）──
  { id: "storage.dir", group: "storage", label: "数据目录", keywords: "数据目录 路径 datadir localappdata 打开", status: "ready" },
  { id: "storage.tutorial", group: "storage", label: "教程进度", keywords: "教程 进度 重置 tutorial progress", status: "ready" },
  { id: "storage.settings", group: "storage", label: "设置文件", keywords: "设置 文件 列表 大小 settings json", status: "ready" },
  { id: "storage.diagnostics", group: "storage", label: "导出诊断包", keywords: "诊断 导出 日志 diagnostics support", status: "ready" },
  { id: "storage.history", group: "storage", label: "历史记录", keywords: "历史 记录 清空 导出 history", status: "pending" },
  { id: "storage.workspace", group: "storage", label: "工作区", keywords: "工作区 workspace 清空", status: "pending" },
  { id: "storage.io", group: "storage", label: "导入 / 导出设置", keywords: "导入 导出 备份 迁移 import export", status: "pending" },
];

export const itemsOf = (groupId) => ITEMS.filter((i) => i.group === groupId);

/** 模糊搜索：命中 label 或 keywords（空格分词，全部命中才算） */
export function searchItems(query) {
  const q = String(query || "").trim().toLowerCase();
  if (!q) return [];
  const terms = q.split(/\s+/).filter(Boolean);
  return ITEMS.filter((it) => {
    const hay = (it.label + " " + it.keywords + " " + it.group).toLowerCase();
    return terms.every((t) => hay.includes(t));
  });
}

export const groupById = (id) => GROUPS.find((g) => g.id === id) || null;
