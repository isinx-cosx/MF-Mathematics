<script setup>
/**
 * App — 壳组件（对应旧版 index.html + app.js）
 * 侧边栏导航 / 顶栏 / 内容区(router-view) / 状态栏
 */
import { ref, computed, onMounted, onBeforeUnmount, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NAV_GROUPS, findNav } from "./router/registry.js";
import TourOverlay from "./components/tutorial/TourOverlay.vue";
import WelcomeDialog from "./components/tutorial/WelcomeDialog.vue";
import MathKeypad from "./components/math/MathKeypad.vue";
import HistoryDialog from "./components/history/HistoryDialog.vue";
import AiPanel from "./components/ai/AiPanel.vue";
import { initSearch, initSearchHook } from "./lib/search/bridge.js";
import { initTutorials, isFirstLaunch, markLaunched } from "./lib/tutorial/store.js";
import { start as startTour } from "./lib/tutorial/tour.js";
import { initPush } from "./lib/push.js";
import { initWorkspace } from "./lib/workspace/store.js";
import { installShortcuts } from "./lib/keyboard/shortcuts.js";
import { initPrefs } from "./lib/settings/prefs.js";
import { initSettingsIoHook } from "./lib/settings/io.js";
import { initTourSanitizerHook } from "./lib/tutorial/targets.js";
import { initPlotMathHook } from "./lib/plot/plotMath.js";
import { initAi, initAiHook } from "./lib/ai/bridge.js";
import { accountInfo, initAccount, initAccountHook } from "./lib/account/bridge.js";
import { aiRequest } from "./lib/ai/bridge.js";
import { updateState, initUpdate, initUpdateHook, refreshUpdateInfo } from "./lib/update/bridge.js";
import {
  THEME_LIST, SHAPE_LIST, DENSITY_LIST, FONT_LIST,
  themeLabel, currentAppearance, applyAppearance, watchSystemTheme,
  bridgeReady, bridgeVersion, isHosted,
  themeBackgroundColor,     // onMounted 里要把窗口底色同步成当前主题色（漏了它会整段中断）
  windowControlsAvailable, winMinimize, winToggleMaximize, winClose,
  winIsMaximized, winStartDrag, winSetChromeBackground,
} from "./lib/bridge.js";

const route = useRoute();
const router = useRouter();

/* ── 教程系统：首次启动欢迎窗 + 引导遮罩（TourOverlay 常驻挂载，自己判断是否显示）── */
initTutorials();
const showWelcome = ref(false);

/** 从欢迎窗/教程页启动引导：关掉欢迎窗并回到首页，让遮罩有界面可高亮 */
function onStartTour() {
  showWelcome.value = false;
  if (startTour("quick-start")) router.replace("/");
}
function openTutorial() { router.replace("/tutorial"); }

/* ── 数学键盘面板 ──
 * v1 是"左下角按钮切换、默认隐藏"，且**基础运算页整页隐藏键盘入口**
 * （那一页自带计算器键盘）。这两条都保留：显隐记忆到 localStorage，
 * 基础运算路由下不显示（避免两套键盘叠在一起）。 */
const keypadVisible = ref(false);
const KEYPAD_HEIGHT = 236;
const keypadAllowed = computed(() => route.path !== "/calc/basic");
function toggleKeypad() {
  keypadVisible.value = !keypadVisible.value;
  try { localStorage.setItem("mf_kb_visible", keypadVisible.value ? "1" : "0"); } catch { /* 忽略 */ }
}

/* ── 侧边栏收放（localStorage 记忆）── */
const sidebarCollapsed = ref(false);
function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
  try { localStorage.setItem("mf_sidebar", sidebarCollapsed.value ? "1" : "0"); } catch { /* 忽略 */ }
}

/* ── 分组手风琴（localStorage 记忆）── */
const groupCollapsed = ref({});
function toggleGroup(g) {
  groupCollapsed.value[g] = !groupCollapsed.value[g];
  try { localStorage.setItem("mf_nav_" + g, groupCollapsed.value[g] ? "1" : "0"); } catch { /* 忽略 */ }
}

/* ── 外观（配色 / 圆角阴影 / 疏密 / 字体 四组独立预设）──
 *
 * 旧版是一个「◐ 主题」按钮点一下就循环到下一套配色，只有 4 套且看不出差别。
 * 现在改成弹层：配色是一网格**实时预览卡**——卡片自己挂 data-theme，
 * 于是卡片内用的是那套主题的真实 CSS 变量渲染，改配色时预览永远跟着变，
 * 而不是一张会过期的截图。圆角/疏密/字体各一行分段按钮，可只换其中一项。 */
const appearance = ref(currentAppearance());
const showAppearance = ref(false);

function pickAppearance(patch) {
  applyAppearance(patch);
  appearance.value = currentAppearance();
}

/** 关弹层的两种方式：点外面、按 Esc。
 *  刻意**不用**点遮罩关闭——本项目其它对话框已经因为"点周围就关"改过一轮。 */
function onDocPointerDown(e) {
  if (!showAppearance.value) return;
  if (!e.target?.closest?.(".appearance-anchor")) showAppearance.value = false;
}
function onDocKey(e) {
  if (e.key === "Escape") showAppearance.value = false;
}

watch(showAppearance, (open) => {
  if (open) {
    document.addEventListener("pointerdown", onDocPointerDown, true);
    document.addEventListener("keydown", onDocKey);
  } else {
    document.removeEventListener("pointerdown", onDocPointerDown, true);
    document.removeEventListener("keydown", onDocKey);
  }
});

// 跟随系统：系统深浅色一变就换到同一风格的深浅版本
const unwatchSystem = watchSystemTheme();
let uninstallShortcuts = null;   // onMounted 里安装的全局快捷键，卸载时收尾
onBeforeUnmount(() => {
  unwatchSystem?.();
  uninstallShortcuts?.();
  document.removeEventListener("pointerdown", onDocPointerDown, true);
  document.removeEventListener("keydown", onDocKey);
  // resize 是 onMounted 里挂的（用快捷键/系统菜单最大化时同步按钮图标）。
  // 之前漏了摘除：根组件常驻，生产上影响很小，但 HMR 下每热更一次就多一个。
  window.removeEventListener("resize", syncMaximized);
});

/* ── 窗口外壳：顶栏本身就是标题栏 ──
 *
 * WPF 侧已不再画标题栏（否则顶部会出现两套最小化/最大化/关闭，
 * 且 WPF 那条不跟随主题）。现在：
 *   · 顶栏空白处按下 → 交给宿主 StartDrag（走系统消息，支持 Aero Snap）
 *   · 双击顶栏 → 最大化/还原
 *   · 右侧三个按钮 → 最小化 / 最大化(还原) / 关闭
 * 浏览器里没有宿主，按钮直接不显示。
 */
const canControlWindow = ref(false);
const isMaximized = ref(false);

function syncMaximized() {
  isMaximized.value = winIsMaximized();
}

function onTopbarMouseDown(e) {
  // 只处理左键、且不落在按钮/输入/链接上——否则点按钮会变成拖窗口
  if (e.button !== 0) return;
  const t = e.target;
  if (t && t.closest && t.closest("button, a, input, textarea, .math-field, math-field, select")) return;
  winStartDrag();
}

function onTopbarDoubleClick(e) {
  const t = e.target;
  if (t && t.closest && t.closest("button, a, input, textarea, .math-field, math-field, select")) return;
  winToggleMaximize();
  setTimeout(syncMaximized, 120);
}

function onWinMinimize() { winMinimize(); }
function onWinMaximize() { winToggleMaximize(); setTimeout(syncMaximized, 120); }
function onWinClose() { winClose(); }

/* ── 顶栏标题（跟随路由 meta）── */
const current = computed(() => findNav(route.path));
const modeTitle = computed(() => (current.value ? current.value.item.name : (route.meta?.title || "首页")));
const modeDesc = computed(() => (current.value ? "· " + current.value.group.title : (route.meta?.desc || "")));

/* ── 状态栏 ── */
const statusText = ref("就绪");
const engineBadge = ref("");
const hosted = ref(false);

onMounted(() => {
  hosted.value = isHosted();
  // 推送通道（宿主 → 页面）：挂一次监听，之后组件面板/控制台/将来的 AI 流式输出
  // 都能被动收到宿主主动发的消息，不必再靠轮询。无宿主时是 no-op。
  initPush();
  // 工作区：挂上 window.__mfWorkspace 诊断钩子（保存/载入/另存为都从这里可见）
  initWorkspace();
  // 计算与绘图偏好：载入并挂 window.__mfPrefs 钩子（精度与绘图范围）
  initPrefs();
  // 教程富文本清洗是安全边界：挂 window.__mfSanitize 供端到端断言清洗确实生效
  initTourSanitizerHook();
  // 绘图表达式归一化：挂 window.__mfToEngineExpr，便于断言"界面不改算符语义"
  initPlotMathHook();
  // AI 助手：订阅 ai.* 推送话题（流式增量、usage、notice、done/error）并读回脱敏配置。
  // 必须在 initPush 之后：推送监听是它唯一的输入来源。
  initAi();
  initAiHook();
  // 联网搜索：订阅 search.done / search.error，并挂 __mfSearch 钩子（同样要在 initPush 之后）
  initSearch();
  initSearchHook();
  // 账号：订阅 account.changed，挂 __mfAccount 钩子（同样在 initPush 之后）
  initAccount();
  initAccountHook();
  // 更新链：读本机版本与上次检查结果；**自动检查默认关**（启动不偷偷联网）
  initUpdate();
  initUpdateHook();
  // 设置备份（导入/导出）：挂 __mfSettingsIo 钩子（用例与排障要用；界面按钮走文件对话框）
  initSettingsIoHook();
  // 全局快捷键：F1 帮助、Ctrl+Z/Y 撤销重做（谁有"上一步"谁注册，见 lib/keyboard/shortcuts.js）
  // 卸载放在 onBeforeUnmount 里由 uninstallShortcuts 收尾
  uninstallShortcuts = installShortcuts(router);

  // 窗口外壳：桌面壳里才有窗口控制；并把窗口底色同步成当前主题色
  canControlWindow.value = windowControlsAvailable();
  syncMaximized();
  winSetChromeBackground(themeBackgroundColor());
  // 用户用快捷键/系统菜单最大化时也要同步按钮图标
  window.addEventListener("resize", syncMaximized);
  // 恢复侧栏 / 分组记忆
  try {
    sidebarCollapsed.value = localStorage.getItem("mf_sidebar") === "1";
    for (const g of NAV_GROUPS) {
      if (localStorage.getItem("mf_nav_" + g.id) === "1") groupCollapsed.value[g.id] = true;
    }
    keypadVisible.value = localStorage.getItem("mf_kb_visible") === "1";
  } catch { /* 忽略 */ }

  // 首次启动的欢迎窗：v1 的语义是"弹过一次就永久置真"（点跳过也算），保持一致。
  // markLaunched() 在 v1 里是 if 之外无条件调用的，所以 launch_count 才会一直涨；
  // 这里同样无条件记一次，便于将来做"新版本再弹一次"。
  if (isFirstLaunch.value) showWelcome.value = true;
  markLaunched();

  if (hosted.value) {
    statusText.value = "引擎已连接（WebView2 桥）";
    engineBadge.value = bridgeReady() ? bridgeVersion() : "桥未就绪";
  } else {
    statusText.value = "浏览器预览模式 — 计算功能待接入引擎";
    engineBadge.value = "浏览器（无引擎桥）";
  }
});

function about() { alert("MF-Mathematics\nMF-Vis-Science · Open Studio"); }
/* 设置自本轮起是真实页面（之前是 alert("设置（待实现）")）。
   侧栏底部的「外观」快捷入口保留：一个改外观，一个进完整设置，两者不冲突。 */
function settings() { router.replace("/settings"); }

/* ── 顶栏「历史」与「搜索」──
 * 这两个按钮此前**都点了没反应**（没有 @click）：历史功能只在基础运算页里有个
 * 8 条的内存列表，在线搜索则完全没有。现在：
 *   · 历史 → 打开真实的历史面板（lib/history/store.js，跨会话落 %LOCALAPPDATA%）；
 *   · 搜索 → 打开占位说明面板，讲清它将来是什么、依赖什么（比一个死按钮诚实，
 *            也比摆一个搜不出东西的假搜索框好）。 */
const showHistory = ref(false);
// 搜索自本轮起是**真实页面**（/tools/search）：结果是内容，值得有路由，
// 教程示例「联网搜索」也能直接落过去。所以这里不再有 showSearch 浮层状态。
function openHistory() { showHistory.value = true; }
function openSearch() { router.push("/tools/search"); }

/* ── 顶栏「AI」──
 * 非模态右侧抽屉（不是模态对话框：用户常要一边看结果一边问）。
 * 不可用时也**照旧能打开** —— 面板里会说清"为什么不能用、去哪里开"，
 * 比给一个点不动的按钮诚实（沿用搜索占位面板的那条判断）。 */
const showAi = ref(false);
function openAi() { showAi.value = true; }

/* 别处发起的"分步讲解"（计算页结果对话框的「查看步骤」）：把抽屉打开，
   面板自己会取走请求并自动发送。用户点那个按钮就是想看步骤，不该再让他点一次发送。 */
watch(aiRequest, (req) => { if (req) showAi.value = true; });

/* ── 账号（顶栏登录态）───────────────────────────────────────────────────
 * 这里只放"这个名字 + 一个入口"，不做拦截：未登录、断网、站点挂了，
 * 顶栏只是少显示一个用户名，任何计算功能都不受影响（见 docs/ACCOUNT.md 的离线承诺）。 */
const accountLabel = computed(() => {
  if (accountInfo.value.loggedIn && accountInfo.value.username) return accountInfo.value.username;
  return "登录";
});
const accountTitle = computed(() => {
  const i = accountInfo.value;
  if (!i.loggedIn) return "登录 / 注册（可选，不影响任何计算功能）";
  const extra = i.offline ? " · 当前离线，显示的是缓存资料" : "";
  return `${i.username} · 额度 ${i.balance}${extra}`;
});
function openAccount() { router.push("/account"); }

/* ── 更新提示（只提示，不自动下载）────────────────────────────────────────
 * 站点版本比本机旧时**不显示这个徽标** —— 否则用户会被引去下载更旧的安装包。
 * 点击只是跳到「设置 → 更新」，那一页才显示校验值与下载入口。 */
const updateAvailable = computed(() => updateState.value.result?.hasUpdate === true);
const updateTitle = computed(() => {
  const r = updateState.value.result;
  return r ? `站点上有更新的版本：${r.latest}（点开看校验值与下载入口）` : "";
});
function openUpdateSettings() {
  refreshUpdateInfo();
  router.push({ path: "/settings", query: { group: "update" } });
}
</script>

<template>
  <!--
    ⚠ 这里不能用 id="app"：index.html 里的挂载点已经是 <div id="app">，
    App.vue 的根再叫 #app 就会形成两层同 id 嵌套，而全局样式
    #app { display:flex } 会同时命中两层 —— 内层于是变成外层的 flex item，
    flex-grow 默认 0，宽度只按内容算，于是内容较窄的页面
    （首页、代数）右侧会空出一大块，内容够宽的绘图页反而看不出来。
    改用 class，并把「占满挂载点」的职责写在下面的 .app-shell 上。
  -->
  <div class="app-shell">
    <!-- ── 左侧导航（可收放）── -->
    <aside id="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-head" @mousedown="onTopbarMouseDown">
        <div class="logo">
          <span class="logo-badge">M</span>
          <span class="logo-text">MF-Mathematics</span>
        </div>
        <button class="nav-btn sidebar-toggle" :title="sidebarCollapsed ? '展开侧栏' : '收起侧栏'"
                @click="toggleSidebar">{{ sidebarCollapsed ? "»" : "«" }}</button>
      </div>

      <nav id="nav" data-tour="main_window.toolbar">
        <template v-for="g in NAV_GROUPS" :key="g.id">
          <p class="nav-group" :class="{ collapsed: groupCollapsed[g.id] }" @click="toggleGroup(g.id)"
             :data-tour="g.id === 'calc' ? 'toolbar.calc_button' : (g.id === 'plot' ? 'toolbar.plot_button' : undefined)">
            {{ g.title }} <span class="nav-arrow">▾</span>
          </p>
          <!-- 计算模式列表 = 旧版教程里说的「这里切换子模式」，故沿用 main_window.mode_selector -->
          <ul class="mode-list" :class="{ collapsed: groupCollapsed[g.id] }"
              :data-tour="g.id === 'calc' ? 'main_window.mode_selector' : undefined">
            <li v-for="it in g.items" :key="it.route"
                :class="{ active: current && current.item.route === it.route }"
                @click="$router.push(it.route)">{{ it.name }}</li>
          </ul>
        </template>
      </nav>

      <div class="sidebar-footer appearance-anchor">
        <!-- 外观选择器：点开弹层挑，而不是点一下循环到下一套。
             title 保留「切换主题」四个字：既有的 cdp-window-shell 套件按它定位按钮。 -->
        <button class="nav-btn" title="切换主题" data-icon="◐" data-tour="main_window.theme_toggle"
                :aria-expanded="showAppearance" @click="showAppearance = !showAppearance">
          <span>◐ 外观 · {{ themeLabel(appearance.theme) }}</span>
        </button>

        <div v-if="showAppearance" class="appearance-pop" role="dialog" aria-label="外观设置">
          <div class="ap-head">
            <span>外观</span>
            <button class="ap-close" title="关闭" @click="showAppearance = false">✕</button>
          </div>

          <p class="ap-label">配色</p>
          <div class="ap-themes">
            <button v-for="t in THEME_LIST" :key="t.id"
                    class="tp-card" :data-theme="t.id" :data-shape="appearance.shape"
                    :class="{ on: appearance.theme === t.id }"
                    :title="t.desc" @click="pickAppearance({ theme: t.id, followSystem: false })">
              <span class="tp-preview">
                <span class="tp-side"></span>
                <span class="tp-body">
                  <span class="tp-line"></span>
                  <span class="tp-line w70"></span>
                  <span class="tp-chip"></span>
                </span>
              </span>
              <span class="tp-name">{{ t.label }}</span>
              <span class="tp-mode">{{ t.mode === "dark" ? "深" : "浅" }}</span>
            </button>
          </div>

          <p class="ap-label">圆角与阴影</p>
          <div class="ap-row">
            <button v-for="s in SHAPE_LIST" :key="s.id" class="ap-seg"
                    :class="{ on: appearance.shape === s.id }" :title="s.desc"
                    @click="pickAppearance({ shape: s.id })">{{ s.label }}</button>
          </div>

          <p class="ap-label">疏密</p>
          <div class="ap-row">
            <button v-for="d in DENSITY_LIST" :key="d.id" class="ap-seg"
                    :class="{ on: appearance.density === d.id }" :title="d.desc"
                    @click="pickAppearance({ density: d.id })">{{ d.label }}</button>
          </div>

          <p class="ap-label">界面字体</p>
          <div class="ap-row">
            <button v-for="f in FONT_LIST" :key="f.id" class="ap-seg"
                    :class="{ on: appearance.font === f.id }" :title="f.desc"
                    @click="pickAppearance({ font: f.id })">{{ f.label }}</button>
          </div>

          <label class="ap-follow">
            <input type="checkbox" :checked="appearance.followSystem"
                   @change="pickAppearance({ followSystem: $event.target.checked })" />
            <span>跟随系统深浅色</span>
          </label>
          <p class="ap-hint">公式与代码始终等宽，不受界面字体影响。</p>
        </div>

        <button class="nav-btn" title="设置" data-icon="⚙" data-tour="toolbar.settings_button" @click="settings">
          <span>⚙ 设置</span>
        </button>
      </div>
    </aside>

    <!-- ── 右侧 ── -->
    <main id="main">
      <!-- 顶栏同时也是标题栏：空白处可拖动窗口、双击最大化 -->
      <header id="topbar" @mousedown="onTopbarMouseDown" @dblclick="onTopbarDoubleClick">
        <div class="topbar-title">
          <span id="modeTitle">{{ modeTitle }}</span>
          <span id="modeDesc">{{ modeDesc }}</span>
        </div>
        <div class="topbar-actions">
          <!-- 账号：未登录时显示「登录」，登录后显示用户名。**它不挡住任何功能** ——
               未登录、断网都只是这里少一个名字，计算全部在本地引擎里。 -->
          <!-- 有更新时出现（站点版本比本机旧时**不会**出现 —— 免得把用户引去下载更旧的包） -->
          <button v-if="updateAvailable" class="btn btn-ghost up-badge" data-update="badge"
                  :title="updateTitle" @click="openUpdateSettings">有新版本</button>
          <button class="btn btn-ghost" data-account="open" :title="accountTitle"
                  @click="openAccount">{{ accountLabel }}</button>
          <button class="btn btn-ghost" data-tour="toolbar.ai_button" data-ai="open"
                  title="AI 助手（解释与思路；计算仍由引擎完成）" @click="openAi">AI</button>
          <button class="btn btn-ghost" data-tour="toolbar.search_button" @click="openSearch">搜索</button>
          <button class="btn btn-ghost" data-tour="toolbar.history_button" @click="openHistory">历史</button>
          <button class="btn btn-ghost" data-tour="main_window.keyboard_button"
                  :title="keypadVisible ? '收起数学键盘' : '打开数学键盘'"
                  @click="toggleKeypad">{{ keypadVisible ? "▼ 收起" : "⌨ 键盘" }}</button>
          <button class="btn btn-ghost" data-tour="main_window.help_button" title="使用教程"
                  @click="openTutorial">帮助</button>
          <button class="btn btn-ghost" @click="about">关于</button>
          <!-- 窗口控制：只有桌面壳里才可用；浏览器里不显示（点了也没意义） -->
          <span v-if="canControlWindow" class="win-controls">
            <button class="win-btn" title="最小化" @click="onWinMinimize">─</button>
            <button class="win-btn" :title="isMaximized ? '还原' : '最大化'" @click="onWinMaximize">
              {{ isMaximized ? "❐" : "□" }}
            </button>
            <button class="win-btn win-close" title="关闭" @click="onWinClose">✕</button>
          </span>
        </div>
      </header>

      <!-- 内容区：路由视图（替代旧 iframe） -->
      <div class="view-host">
        <router-view />
      </div>

      <!-- 数学键盘面板：默认隐藏，由顶栏「⌨ 键盘」切换；基础运算页不显示 -->
      <MathKeypad v-if="keypadVisible && keypadAllowed" class="keypad-host"
                  :style="{ height: KEYPAD_HEIGHT + 'px' }" />

      <footer id="statusbar">
        <span id="statusText">{{ statusText }}</span>
        <span>{{ engineBadge }}</span>
      </footer>
    </main>

    <!-- 首次启动欢迎窗 + 引导遮罩 -->
    <WelcomeDialog v-if="showWelcome" @close="showWelcome = false" @start-tour="onStartTour" />
    <TourOverlay />

    <!-- 顶栏「历史」/「搜索」弹窗 + AI 抽屉 -->
    <HistoryDialog v-if="showHistory" @close="showHistory = false" />
    <AiPanel :open="showAi" @close="showAi = false" />
  </div>
</template>

<style scoped>
/* 外壳占满挂载点 #app（后者是 display:flex 的 row 容器）：
   flex:1 让它横向吃满剩余空间，min-width:0 防止内部超宽内容把它撑大。 */
.app-shell {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: row;
}

.view-host {
  flex: 1;
  overflow: auto;
  background: var(--bg);
}

/* 数学键盘面板：#main 是 overflow:hidden 的纵向 flex，所以这里 flex:none 定高，
   内部自己滚动（.kp-body 有 overflow:auto）。 */
.keypad-host {
  flex: none;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

/* 顶栏是标题栏：拖动手感交给系统（StartDrag 走 WM_NCLBUTTONDOWN），
   这里只需避免文字被选中、并保持默认箭头光标。 */
.up-badge { color: var(--accent, #5a82f0); border-color: var(--accent, #5a82f0); }
#topbar { user-select: none; }
.sidebar-head { user-select: none; }

/* ═══════════════ 外观选择弹层 ═══════════════
   用 position:fixed 而不是 absolute：外层 #sidebar 是 overflow:hidden，
   absolute 会被裁掉；fixed 以视口为参照，能正常浮在内容区上面。 */
.appearance-pop {
  position: fixed;
  left: calc(var(--pane-gap) + 2px);
  bottom: calc(var(--pane-gap) + 56px);
  width: 302px;
  max-height: calc(100vh - 90px);
  overflow-y: auto;
  z-index: 900;
  padding: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-3);
  text-align: left;
}
.ap-head {
  display: flex; align-items: center; justify-content: space-between;
  font-weight: 700; font-size: 13px; margin-bottom: 10px;
}
.ap-close {
  width: 22px; height: 22px; padding: 0;
  border: none; border-radius: var(--r-sm);
  background: transparent; color: var(--text-muted);
}
.ap-close:hover { background: var(--danger-soft); color: var(--danger); }
.ap-label {
  font-size: 11.5px; color: var(--text-subtle);
  margin: 10px 0 6px; font-weight: 600;
}

/* ── 配色网格：每张卡自带 data-theme，于是卡里用的是那套主题的真实变量 ──
   预览不是截图，改配色时预览自动跟着变，永远不会与实际不一致。 */
.ap-themes { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.tp-card {
  position: relative;
  display: flex; flex-direction: column; gap: 3px;
  padding: 5px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  cursor: pointer;
  transition: transform .12s, box-shadow .12s;
}
.tp-card:hover { transform: translateY(-1px); box-shadow: var(--shadow-2); }
.tp-card.on { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }
.tp-preview {
  display: flex; height: 34px; overflow: hidden;
  border-radius: calc(var(--r-sm) - 1px);
  border: 1px solid var(--border);
  background: var(--bg);
}
.tp-side { width: 11px; background: var(--surface-alt); border-right: 1px solid var(--border); }
.tp-body {
  flex: 1; padding: 5px 5px 0 5px;
  display: flex; flex-direction: column; gap: 3px;
  background: var(--surface);
}
.tp-line { height: 3px; border-radius: 2px; background: var(--text-subtle); opacity: .55; }
.tp-line.w70 { width: 70%; }
.tp-chip { width: 26px; height: 6px; border-radius: 3px; background: var(--grad); margin-top: 1px; }
.tp-name {
  font-size: 10.5px; color: var(--text); font-weight: 600;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.tp-mode {
  position: absolute; top: 4px; right: 4px;
  font-size: 9px; line-height: 1;
  padding: 2px 3px; border-radius: 3px;
  background: var(--accent-soft); color: var(--accent);
}

/* ── 分段按钮（圆角 / 疏密 / 字体）── */
.ap-row { display: flex; gap: 5px; }
.ap-seg {
  flex: 1; height: 26px; padding: 0 4px;
  font-size: 11.5px; font-weight: 600;
  background: var(--surface-alt); color: var(--text-muted);
  border: 1px solid var(--border); border-radius: var(--r-sm);
  transition: all .12s;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.ap-seg:hover { color: var(--text); border-color: var(--accent); }
.ap-seg.on { background: var(--accent-soft); color: var(--accent); border-color: var(--accent); }

.ap-follow {
  display: flex; align-items: center; gap: 7px;
  margin-top: 12px; font-size: 12px; color: var(--text-muted); cursor: pointer;
}
.ap-follow input { accent-color: var(--accent); cursor: pointer; }
.ap-hint { font-size: 10.5px; color: var(--text-subtle); margin-top: 6px; line-height: 1.5; }
</style>
