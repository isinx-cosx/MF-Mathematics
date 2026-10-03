/**
 * targets.js — 引导步骤的目标定位 + "尚未实现"的显式清单
 *
 * 定位方式与 v1 的等价关系：
 *   v1（Qt）：`Step.target` 是字符串语义 ID → 「注册名→QWidget 引用」字典
 *            → 找不到就按 `objectName` 递归搜主窗口 → 还找不到就
 *            **静默递归跳过该步**（walkthrough.py:118-123）。
 *   v2（Vue）：`Step.target` 同名 → `[data-tour="<name>"]` → `getBoundingClientRect()`。
 *            **找不到时绝不静默跳过**：返回 { available:false, reason } 由界面明说。
 *
 * 为什么要 PENDING 清单：v1 的 66 个步骤里有 34 个目标控件根本不存在
 * （22 个名字全库无 setObjectName），最严重的是教程 05 与 11 **每一步都失效**——
 * 遮罩一闪即消失，而教程还被标记成"已完成"。重做时若继续"找不到就跳过"，
 * 这个缺陷会原样复活。所以这里把"暂不可用"变成**显式数据**：
 *   · 运行期：resolveTarget() 明确告诉界面"缺哪个界面、依赖什么"；
 *   · 构建期：tools/check-tour-targets.mjs 断言每个 target 要么在源码里真有
 *     data-tour，要么在本清单里写明理由——两者都不占就构建失败。
 * 等到 AI / 搜索 / 设置等模块做出来（P1–P3），同一批步骤会自动变为可用，
 * 那时把对应条目从 PENDING 删掉即可（同时校验脚本会提醒删除过时条目）。
 */

/**
 * 尚未实现的界面：name → 缺什么、依赖哪个阶段。做完后请从这里删除。
 *
 * ⚠️ 本轮踩到的坑（值得写下来）：AI 与搜索的 5 个目标曾长期留在这里，
 * 理由是"尚未实现" —— 而界面其实早就做好了，只是**钩子的名字不一样**
 * （教程用 v1 的语义 ID `ai_dialog.input`，面板挂的是 `data-ai="input"`）。
 * 两边名字对不上时 `check-ui.mjs` 查不出来：教程引用了它 ✓、PENDING 有理由 ✓，
 * 两条检查都满足，于是引导一直指不到东西，理由还是一句假话。
 * 现在的规矩：**新界面落地时，同一步骤里既补 `data-tour`、也删 PENDING 条目**；
 * 沿用 v1 的语义 ID 而不是自造名字（这样教程与 YAML 原件都不用改）。
 */
export const PENDING = {
  // 真的还没做：v1 每个计算块上有"AI 加速"按钮，v2 没有（不是接线问题）
  "calc_block.ai_accel_button": "AI 加速按钮尚未实现（v1 有这个入口，v2 未做；见 docs/OPEN-ITEMS.md §4）",
};

/**
 * 目标"在别的页面"或"要满足前置条件才出现"时的提示。
 *
 * 为什么需要它：引导不会自动跳页（v1 也没有），于是教程里"设置 → AI 配置"
 * 这类步骤在计算页上必然找不到目标 —— 若不区分，界面就会误报"该界面尚未实现"，
 * 而其实它已经做好了，只是不在当前页。这类**误报**和 v1 的静默跳过一样有害：
 * 用户会以为功能缺失。
 *
 * route：目标所在页面（与当前路由不同时，界面给出"前往该界面"按钮）
 * note ：需要用户先做什么（例如先打开数学键盘、先算一次让结果对话框出现）
 */
export const TARGET_HINTS = {
  "settings_dialog.appearance_tab": { route: "/settings", note: "该设置在设置面板的「外观」分组里" },
  "settings_dialog.ai_tab": { route: "/settings", note: "AI 的开关、接口与密钥在设置面板的「AI」分组里" },
  "math_keyboard.panel": { note: "先点顶栏的「⌨ 键盘」把面板打开" },
  "math_keyboard.titlebar": { note: "先点顶栏的「⌨ 键盘」把面板打开" },
  "result_dialog.steps_button": { note: "先在本页点一次「计算结果」，结果对话框打开后才有这个按钮" },
  // 分步显示：由「查看步骤」打开（计算页的结果对话框，或 AI 面板里那条回答上的按钮）
  "step_viewer.content": { note: "先点结果对话框或 AI 回答里的「查看步骤」；步骤来自 AI 调引擎的记录" },
  "plot_workspace.sliders": { note: "表达式里要含参数（例如 sin(a*x)）才会出现参数滑块" },
  // AI 面板是抽屉：里面的目标要先把它打开才存在（v-if="open"）
  "ai_dialog.input": { note: "先点顶栏的「AI」把助手抽屉打开" },
  "ai_dialog.send_button": { note: "先点顶栏的「AI」把助手抽屉打开" },
  "ai_dialog.context_label": { note: "先点顶栏的「AI」把助手抽屉打开" },
  "main_window.ai_settings": { route: "/settings", note: "AI 的开关、接口与密钥在设置面板的「AI」分组里（面板未就绪时这里也能进）" },
  "calc_block.ai_accel_button": { note: "AI 加速尚未实现（v1 有这个入口，v2 未做）" },
  // 搜索是独立页面（/tools/search）
  "search_panel.input": { route: "/tools/search", note: "搜索在「工具 → 搜索」这一页" },
  "search_panel.results": { route: "/tools/search", note: "搜索在「工具 → 搜索」这一页；有结果后才会出现结果列表" },
  "toolbar.ai_button": { note: "AI 助手在顶栏的「AI」按钮里（非模态抽屉）" },
};

export function hintFor(name) {
  return TARGET_HINTS[name] || null;
}

/** 界面里确实注册了 data-tour 的名字（与源码一致，供文档与校验脚本对照） */
export const REGISTERED = [
  "main_window.toolbar",
  "main_window.mode_selector",
  "main_window.theme_toggle",
  "main_window.help_button",
  "main_window.keyboard_button",
  "toolbar.calc_button",
  "toolbar.plot_button",
  "toolbar.search_button",
  "toolbar.history_button",
  "toolbar.settings_button",
  "settings_dialog.appearance_tab",
  "settings_dialog.ai_tab",
  "calc_block.input",
  "calc_block.calc_button",
  "calc_block.action_dropdown",
  "result_dialog.steps_button",
  "plot_workspace.function_input",
  "plot_workspace.add_function",
  "plot_workspace.sliders",
  "plot_canvas",
  "geometry_canvas",
  "math_keyboard.panel",
  "math_keyboard.titlebar",
  "tutorial.catalog",
  // 本轮补上的 6 个（教程用 v1 的语义 ID，界面挂的就是这些名字）
  "toolbar.ai_button",
  "ai_dialog.input",
  "ai_dialog.send_button",
  "ai_dialog.context_label",
  "main_window.ai_settings",
  "search_panel.input",
  "search_panel.results",
  // 本轮补上：分步显示的渲染层（StepViewer，由「查看步骤」打开）
  "step_viewer.content",
];

const DASH = "\u2014";

/** 引导高亮用的定位结果。available=false 时界面必须显示 reason，不得跳过。 */
export function resolveTarget(name) {
  if (!name) return { name, available: false, reason: "该步骤没有写 target", el: null };
  const el = findTargetEl(name);
  if (el) return { name, available: true, reason: "", el };
  const pending = PENDING[name];
  return {
    name,
    available: false,
    el: null,
    reason: pending || `界面里找不到 data-tour="${name}"（既未注册，也不在待实现清单里）`,
  };
}

export function findTargetEl(name) {
  if (typeof document === "undefined") return null;
  try {
    const esc = window.CSS && CSS.escape ? CSS.escape(name) : name.replace(/["\\]/g, "\\$&");
    const el = document.querySelector(`[data-tour="${esc}"]`);
    if (!el) return null;
    // 被 v-if 隐藏的元素不算可用：v1 就有"高亮到隐藏控件上"的问题
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return null;
    return el;
  } catch {
    return null;
  }
}

export function isPending(name) {
  return Object.prototype.hasOwnProperty.call(PENDING, name);
}

/** 供界面文案：把 target 名显示成人能读的样子 */
export function describeTarget(name) {
  if (isPending(name)) return PENDING[name];
  return name || `（未指定${DASH}无法定位）`;
}

/**
 * 只放行安全标签的 HTML 清洗。
 * v1 是 QLabel.setText 直接吃 YAML 里的富文本——在桌面 Qt 里尚可，
 * 但教程 YAML 是**外部可编辑文件**，搬到 WebView 里就是真实注入面，必须过一遍。
 *
 * ⚠ 递归写法，不能写成"遍历快照"：
 * 旧实现是 `for (const child of Array.from(node.childNodes))`，遇到非白名单标签就
 * `child.replaceWith(...child.childNodes)` 把子节点**提升**到父级再 `continue`。
 * 但快照里没有这些被提升的节点，它们于是**既不会被剥属性、也不会被递归**——
 * `<p><img src=x onerror=...></p>` 里的 P 被拆壳后，IMG 带着 onerror 原样留下，
 * 而它最终经 `v-html` 渲染（TourOverlay / HelpArticleView）。实测确认过这条绕过。
 * 现在改成对每个节点自身处理，并在拆壳后**对提升上来的节点继续清洗**；标签白名单
 * 里没有 P/DIV/A/IMG，所以外壳一律拆掉、属性一律剥掉、子树一律清到干净。
 */
const ALLOWED_TAGS = new Set(["B", "I", "EM", "STRONG", "BR", "CODE", "SPAN", "U", "SMALL", "SUP", "SUB"]);

function cleanNode(node) {
  if (node.nodeType === 8) { node.remove(); return; }          // 注释
  if (node.nodeType !== 1) return;                             // 文本节点保留
  if (!ALLOWED_TAGS.has(node.tagName)) {                       // 不允许的标签：拆掉外壳留内容
    const promoted = Array.from(node.childNodes);
    node.replaceWith(...promoted);
    for (const p of promoted) cleanNode(p);                    // ← 关键：提升上来的也要清
    return;
  }
  for (const attr of Array.from(node.attributes)) node.removeAttribute(attr.name);
  for (const child of Array.from(node.childNodes)) cleanNode(child);
}

export function sanitizeTourHtml(html) {
  if (typeof document === "undefined") return String(html ?? "");
  const tpl = document.createElement("template");
  tpl.innerHTML = String(html ?? "");
  for (const child of Array.from(tpl.content.childNodes)) cleanNode(child);
  return tpl.innerHTML;
}

/**
 * 测试/排障钩子 `window.__mfSanitize`。
 * 清洗是**安全边界**，最需要能被端到端断言（CDP 里够不到模块作用域），
 * 所以在这里显式暴露；App 启动时调用一次。
 */
export function initTourSanitizerHook() {
  try {
    window.__mfSanitize = sanitizeTourHtml;
    window.__mfTourHtmlAllowedTags = Array.from(ALLOWED_TAGS);
  } catch { /* 忽略 */ }
}
