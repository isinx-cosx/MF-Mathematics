/**
 * keyboard/shortcuts.js — 全局快捷键（v1 的编辑菜单 / 帮助菜单里那几个）
 *
 * v1 有：F1 打开帮助文档、Ctrl+Z 撤销、Ctrl+Y 重做（`main_window.py` 的 QShortcut 与 Edit 菜单）。
 * v2.0 之前只有局部快捷键（对话框 Esc/Enter、编辑器 Ctrl+Enter、引导 ←/→），全局一个都没有。
 *
 * 三条设计约束：
 *   ① **不弹任何窗口**。F1 是"跳到教程页"（本来就是一个路由），撤销/重做是就地改状态；
 *      这里不出现 alert / confirm / 自定义模态。
 *   ② **不抢输入框里的键**。焦点在 <input> / <textarea> / [contenteditable] / MathLive 的
 *      <math-field> / CodeMirror 编辑器里时，Ctrl+Z 必须留给它们自己的撤销栈
 *      （MathLive 与 CodeMirror 都有），否则用户会发现"我打字撤销不了，反而把整块还原了"。
 *      F1 例外：任何地方按 F1 都打开帮助。
 *   ③ **可撤销的东西由页面自己注册**。谁有"上一步"谁调 registerUndoable()，
 *      最后注册的（也就是当前页面的）优先；页面卸载时注销。没有注册者时按键**不做任何事**
 *      （不提示、不弹窗）——避免出现"按了没反应"却不知道是没实现还是没内容可撤。
 */

const undoables = [];

/**
 * 注册一个可撤销对象（页面级）。
 * @param {{undo:Function, redo:Function, canUndo?:Function, canRedo?:Function, name?:string}} p
 * @returns 注销函数
 */
export function registerUndoable(p) {
  if (!p || typeof p.undo !== "function" || typeof p.redo !== "function") return () => {};
  const entry = {
    name: p.name || "页面",
    undo: p.undo,
    redo: p.redo,
    canUndo: typeof p.canUndo === "function" ? p.canUndo : () => true,
    canRedo: typeof p.canRedo === "function" ? p.canRedo : () => true,
  };
  undoables.push(entry);
  return () => {
    const i = undoables.indexOf(entry);
    if (i >= 0) undoables.splice(i, 1);
  };
}

/** 当前生效的可撤销对象（最后注册且"现在能做点什么"的那个） */
function active(op) {
  for (let i = undoables.length - 1; i >= 0; i--) {
    const e = undoables[i];
    try {
      if (op === "undo" ? e.canUndo() : e.canRedo()) return e;
    } catch { /* 单个注册者出错不该拖垮快捷键 */ }
  }
  return null;
}

/** 焦点是否在"该由它自己处理按键"的可编辑区域里 */
export function inEditableContext(el) {
  let n = el;
  while (n && n !== document.body) {
    const tag = (n.tagName || "").toUpperCase();
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "MATH-FIELD" || tag === "SELECT") return true;
    if (n.isContentEditable) return true;
    const cls = String(n.className || "");
    if (typeof cls === "string" && (cls.includes("cm-editor") || cls.includes("cm-content"))) return true;
    n = n.parentElement;
  }
  return false;
}

/**
 * 安装全局监听。router 用于 F1 跳教程页。
 * @returns 卸载函数
 */
export function installShortcuts(router) {
  function onKeydown(e) {
    const key = String(e.key || "");

    // F1：帮助（任何上下文都生效，且只跳路由、不开窗口）
    if (key === "F1") {
      e.preventDefault();
      if (router) router.push("/tutorial");
      return;
    }

    const mod = e.ctrlKey || e.metaKey;
    if (!mod) return;

    // 输入框里的 Ctrl+Z / Ctrl+Y 交给它们自己
    if (inEditableContext(e.target)) return;

    const k = key.toLowerCase();
    const isUndo = k === "z" && !e.shiftKey;
    const isRedo = (k === "y") || (k === "z" && e.shiftKey);
    if (!isUndo && !isRedo) return;

    const e2 = active(isUndo ? "undo" : "redo");
    if (!e2) return;                       // 没有可撤销的东西：不拦截、不提示
    e.preventDefault();
    try {
      if (isUndo) e2.undo(); else e2.redo();
    } catch (err) {
      // 出错只记到控制台：快捷键不该弹窗打断用户
      console.error("[shortcuts] " + e2.name + (isUndo ? " 撤销" : " 重做") + "失败：", err);
    }
  }

  window.addEventListener("keydown", onKeydown, true);   // 捕获阶段：先于页面自己的处理
  // 诊断/测试钩子：CDP 里够不到模块作用域，而"现在有没有可撤销的东西"正是最需要能看见的
  try { window.__mfShortcuts = { state: shortcutState, undoables }; } catch { /* 忽略 */ }
  return () => window.removeEventListener("keydown", onKeydown, true);
}

/** 诊断/测试用：当前有没有可撤销对象、能不能撤销 */
export function shortcutState() {
  return { registered: undoables.length, canUndo: !!active("undo"), canRedo: !!active("redo") };
}
