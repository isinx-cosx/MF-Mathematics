import { useEffect, useMemo, useRef, useState } from "react";
import {
  THEME_LIST, SHAPE_LIST, DENSITY_LIST, FONT_LIST,
  themeLabel, currentAppearance, applyAppearance, initTheme, watchSystemTheme,
  windowControlsAvailable, winMinimize, winToggleMaximize, winClose, winIsMaximized, winStartDrag,
} from "@shared/bridge.js";
import PlotPage from "./plot/PlotPage";
import { safe } from "./lib/hostSafe";
import "./styles/app.css";

/* 外观兜底：宿主对象未就绪时 currentAppearance() 可能抛错，退回默认值 */
const DEFAULT_APPEARANCE = {
  theme: "glass-light",
  shape: "glass",
  density: "cozy",
  font: "sans",
  followSystem: false,
} as { theme: string; shape: string; density: string; font: string; followSystem: boolean };

/**
 * 导航数据：**与 Vue 版 src/router/registry.js 逐字一致**（分组、名称、路由、顺序）。
 * registry.js 顶部 import 了 HomeView.vue，React 侧不能直接引用，故在此同步一份。
 * 后续应收口：把 NAV_GROUPS 抽到零依赖模块（如 lib/router/nav.js），两边共用。
 */
type NavItem = { name: string; route: string; grid?: "polar" };
type NavGroup = { id: string; title: string; items: NavItem[] };

const NAV_GROUPS: NavGroup[] = [
  {
    id: "calc",
    title: "计算模式",
    items: [
      { name: "基础运算", route: "/calc/basic" },
      { name: "代数计算", route: "/calc/algebra" },
      { name: "微积分", route: "/calc/calculus" },
      { name: "解析几何", route: "/calc/analytic-geometry" },
      { name: "数列", route: "/calc/sequences" },
      { name: "线性代数", route: "/calc/linear-algebra" },
      { name: "概率论与数理统计", route: "/calc/probability" },
      { name: "数值分析", route: "/calc/numerical" },
      { name: "数论", route: "/calc/number-theory" },
      { name: "实分析", route: "/calc/real-analysis" },
      { name: "泛函分析", route: "/calc/functional-analysis" },
      { name: "复分析", route: "/calc/complex-analysis" },
      { name: "代数拓扑", route: "/calc/algebraic-topology" },
      { name: "测度论", route: "/calc/measure-theory" },
      { name: "调和分析", route: "/calc/harmonic-analysis" },
    ],
  },
  {
    id: "plot",
    title: "绘图模式",
    items: [
      { name: "2D 函数绘图", route: "/plot/2d" },
      { name: "极坐标", route: "/plot/polar", grid: "polar" },
      { name: "3D 曲面", route: "/plot/3d" },
      { name: "复平面", route: "/plot/complex" },
      { name: "向量场", route: "/plot/vector" },
      { name: "自由几何", route: "/plot/geometry" },
      { name: "分形", route: "/plot/fractal" },
    ],
  },
  {
    id: "tools",
    title: "工具",
    items: [
      { name: "搜索", route: "/tools/search" },
      { name: "控制台", route: "/tools/console" },
      { name: "函数工具箱", route: "/tools/toolbox" },
    ],
  },
  {
    id: "help",
    title: "帮助",
    items: [
      { name: "使用教程", route: "/tutorial" },
      { name: "示例任务库", route: "/examples" },
    ],
  },
];

function findNav(route: string): { group: NavGroup; item: NavItem } | null {
  for (const g of NAV_GROUPS) for (const it of g.items) if (it.route === route) return { group: g, item: it };
  return null;
}

/** 已迁移到 React 的绘图路由（其余绘图页与计算页尚未迁移） */
const MIGRATED_PLOTS = new Set(["/plot/2d", "/plot/polar"]);

export default function App() {
  const [route, setRoute] = useState(() => window.location.hash.replace(/^#/, "") || "/plot/2d");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [groupCollapsed, setGroupCollapsed] = useState<Record<string, boolean>>({});
  const [showAppearance, setShowAppearance] = useState(false);
  /* ⚠ 一律用 safe() 包住：宿主对象（chrome.webview.hostObjects.sync.*）在首帧可能还没挂上，
   * 访问不存在的成员会抛 0x80070057，直接让整页渲染失败（白屏、且日志无痕）。 */
  const [appearance, setAppearance] = useState(() => safe(() => currentAppearance(), DEFAULT_APPEARANCE));
  const [keypadVisible, setKeypadVisible] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);
  // 这两项也**不在首帧取**：放到挂载后的 effect 里
  const [canControlWindow, setCanControlWindow] = useState(false);
  const [statusText, setStatusText] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);

  /* 主题与外观：与 Vue 版同一套 bridge API；宿主未就绪时全部兜底 */
  useEffect(() => {
    safe(() => initTheme(), undefined);
    setCanControlWindow(safe(() => windowControlsAvailable(), false));
    setIsMaximized(safe(() => winIsMaximized(), false));
    const off = safe(() => watchSystemTheme?.(), undefined);
    const onApp = () => setAppearance(safe(() => currentAppearance(), DEFAULT_APPEARANCE));
    window.addEventListener("mf-appearance", onApp);
    return () => {
      if (typeof off === "function") (off as () => void)();
      window.removeEventListener("mf-appearance", onApp);
    };
  }, []);

  useEffect(() => {
    const onHash = () => setRoute(window.location.hash.replace(/^#/, "") || "/plot/2d");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const current = findNav(route);
  const modeTitle = current?.item.name ?? "";
  const modeDesc = current?.group.title ?? "";

  const navigate = (r: string) => { window.location.hash = r; };

  const engineBadge = "mf_mathematics (C++ 引擎) via MFMath.Host";

  return (
    <div className="app-shell" ref={rootRef}>
      {/* ── 左侧导航（可收放）── */}
      <aside id="sidebar" className={sidebarCollapsed ? "collapsed" : ""}>
        <div className="sidebar-head" onMouseDown={() => { if (canControlWindow) safe(() => winStartDrag(), undefined); }}>
          <div className="logo">
            <span className="logo-badge">M</span>
            <span className="logo-text">MF-Mathematics</span>
          </div>
          <button
            className="nav-btn sidebar-toggle"
            title={sidebarCollapsed ? "展开侧栏" : "收起侧栏"}
            onClick={() => setSidebarCollapsed((v) => !v)}
          >{sidebarCollapsed ? "»" : "«"}</button>
        </div>

        <nav id="nav" data-tour="main_window.toolbar">
          {NAV_GROUPS.map((g) => (
            <div key={g.id}>
              <p
                className={"nav-group" + (groupCollapsed[g.id] ? " collapsed" : "")}
                onClick={() => setGroupCollapsed((s) => ({ ...s, [g.id]: !s[g.id] }))}
                data-tour={g.id === "calc" ? "toolbar.calc_button" : (g.id === "plot" ? "toolbar.plot_button" : undefined)}
              >
                {g.title} <span className="nav-arrow">▾</span>
              </p>
              <ul
                className={"mode-list" + (groupCollapsed[g.id] ? " collapsed" : "")}
                data-tour={g.id === "calc" ? "main_window.mode_selector" : undefined}
              >
                {g.items.map((it) => (
                  <li key={it.route} className={route === it.route ? "active" : ""} onClick={() => navigate(it.route)}>
                    {it.name}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <div className="sidebar-footer appearance-anchor">
          <button
            className="nav-btn"
            title="切换主题"
            data-icon="◐"
            data-tour="main_window.theme_toggle"
            aria-expanded={showAppearance}
            onClick={() => setShowAppearance((v) => !v)}
          >
            <span>◐ 外观 · {safe(() => themeLabel(appearance.theme), appearance.theme)}</span>
          </button>

          {showAppearance && (
            <div className="appearance-pop" role="dialog" aria-label="外观设置">
              <div className="ap-head">
                <span>外观</span>
                <button className="ap-close" title="关闭" onClick={() => setShowAppearance(false)}>✕</button>
              </div>

              <p className="ap-label">配色</p>
              <div className="ap-themes">
                {THEME_LIST.map((t: { id: string; label: string; mode: string; desc: string }) => (
                  <button
                    key={t.id}
                    className={"tp-card" + (appearance.theme === t.id ? " on" : "")}
                    data-theme={t.id}
                    data-shape={appearance.shape}
                    title={t.desc}
                    onClick={() => safe(() => applyAppearance({ theme: t.id, followSystem: false }), undefined)}
                  >
                    <span className="tp-preview">
                      <span className="tp-side" />
                      <span className="tp-body">
                        <span className="tp-line" />
                        <span className="tp-line w70" />
                        <span className="tp-chip" />
                      </span>
                    </span>
                    <span className="tp-name">{t.label}</span>
                    <span className="tp-mode">{t.mode === "dark" ? "深" : "浅"}</span>
                  </button>
                ))}
              </div>

              <p className="ap-label">圆角与阴影</p>
              <div className="ap-row">
                {SHAPE_LIST.map((s: { id: string; label: string; desc: string }) => (
                  <button key={s.id} className={"ap-seg" + (appearance.shape === s.id ? " on" : "")}
                          title={s.desc} onClick={() => safe(() => applyAppearance({ shape: s.id }), undefined)}>{s.label}</button>
                ))}
              </div>

              <p className="ap-label">疏密</p>
              <div className="ap-row">
                {DENSITY_LIST.map((d: { id: string; label: string; desc: string }) => (
                  <button key={d.id} className={"ap-seg" + (appearance.density === d.id ? " on" : "")}
                          title={d.desc} onClick={() => safe(() => applyAppearance({ density: d.id }), undefined)}>{d.label}</button>
                ))}
              </div>

              <p className="ap-label">界面字体</p>
              <div className="ap-row">
                {FONT_LIST.map((f: { id: string; label: string; desc: string }) => (
                  <button key={f.id} className={"ap-seg" + (appearance.font === f.id ? " on" : "")}
                          title={f.desc} onClick={() => safe(() => applyAppearance({ font: f.id }), undefined)}>{f.label}</button>
                ))}
              </div>

              <label className="ap-follow">
                <input type="checkbox" checked={!!appearance.followSystem}
                       onChange={(e) => safe(() => applyAppearance({ followSystem: e.target.checked }), undefined)} />
                <span>跟随系统深浅色</span>
              </label>
              <p className="ap-hint">公式与代码始终等宽，不受界面字体影响。</p>
            </div>
          )}

          <button className="nav-btn" title="设置" data-icon="⚙" data-tour="toolbar.settings_button">
            <span>⚙ 设置</span>
          </button>
        </div>
      </aside>

      {/* ── 右侧 ── */}
      <main id="main">
        <header
          id="topbar"
          onMouseDown={() => { if (canControlWindow) safe(() => winStartDrag(), undefined); }}
          onDoubleClick={() => { if (canControlWindow) safe(() => winToggleMaximize(), undefined); }}
        >
          <div className="topbar-title">
            <span id="modeTitle">{modeTitle}</span>
            <span id="modeDesc">{modeDesc}</span>
          </div>
          <div className="topbar-actions">
            <button className="btn btn-ghost" data-account="open" title="账号">登录</button>
            <button className="btn btn-ghost" data-tour="toolbar.ai_button" data-ai="open"
                    title="AI 助手（解释与思路；计算仍由引擎完成）">AI</button>
            <button className="btn btn-ghost" data-tour="toolbar.search_button">搜索</button>
            <button className="btn btn-ghost" data-tour="toolbar.history_button">历史</button>
            <button
              className="btn btn-ghost"
              data-tour="main_window.keyboard_button"
              title={keypadVisible ? "收起数学键盘" : "打开数学键盘"}
              onClick={() => setKeypadVisible((v) => !v)}
            >
              {keypadVisible ? "▼ 收起" : "⌨ 键盘"}
            </button>
            <button className="btn btn-ghost" data-tour="main_window.help_button" title="使用教程">帮助</button>
            <button className="btn btn-ghost">关于</button>
            {canControlWindow && (
              <span className="win-controls">
                <button className="win-btn" title="最小化" onClick={() => safe(() => winMinimize(), undefined)}>─</button>
                <button
                  className="win-btn"
                  title={isMaximized ? "还原" : "最大化"}
                  onClick={() => { safe(() => winToggleMaximize(), undefined); setIsMaximized(safe(() => winIsMaximized(), false)); }}
                >
                  {isMaximized ? "❐" : "□"}
                </button>
                <button className="win-btn win-close" title="关闭" onClick={() => safe(() => winClose(), undefined)}>✕</button>
              </span>
            )}
          </div>
        </header>

        {/* 内容区 */}
        <div className="view-host">
          {route === "/plot/2d" && <PlotPage gridMode="rect" onStatusText={setStatusText} />}
          {route === "/plot/polar" && <PlotPage gridMode="polar" onStatusText={setStatusText} />}
          {!MIGRATED_PLOTS.has(route) && (
            <div className="todo-page">
              <h2>{modeTitle}</h2>
              <p>这个页面还没迁移到 React。已迁移的绘图页面：2D 函数绘图、极坐标。</p>
            </div>
          )}
        </div>

        {/* 待办：数学键盘面板（MathKeypad）尚未移植；顶栏按钮已按原样保留 */}
        <footer id="statusbar">
          <span id="statusText">{statusText}</span>
          <span>{engineBadge}</span>
        </footer>
      </main>
    </div>
  );
}
