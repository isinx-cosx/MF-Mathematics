/**
 * 控制台编辑器内核（CodeMirror 6）—— **按需加载**
 *
 * 设计要点：
 *
 * ① 惰性：这个模块**只能**动态 import。控制台不是首页，编辑器内核（state/view/
 *    commands/language/search/autocomplete）差不多 150 KB，没必要让每个用户都先下它。
 *    调用方见 CodeEditor.vue 的 `await import("../../lib/console/editor.js")`。
 *
 * ② 语言也惰性，而且**按语言分开**：Python 和 C++ 的语法包各是一个独立 chunk
 *    （见 LANGS），只有真的切到那门语言才下载。装了 MinGW 组件才有 C++，
 *    所以只写 Python 的用户永远不下载 C++ 语法包。
 *
 * ③ 配色直接引用本项目的外观变量（`var(--...)`）。CodeMirror 的 theme 接受任意
 *    CSS 值，所以主题色不用在 JS 里再抄一遍——10 套配色、浅深切换、跟随系统
 *    全部自动生效，而且切换是**即时**的（走 CSS 层叠，不用重建编辑器）。
 *    这一点很重要：如果在这里硬编码颜色，多主题功能一到控制台就断了。
 */

import { EditorState, Compartment } from "@codemirror/state";
import {
  EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter,
  drawSelection, dropCursor, rectangularSelection, crosshairCursor,
  highlightSpecialChars,
} from "@codemirror/view";
import {
  history, defaultKeymap, historyKeymap, indentMore, indentLess,
} from "@codemirror/commands";
import {
  syntaxHighlighting, HighlightStyle, bracketMatching, indentOnInput,
} from "@codemirror/language";
import { highlightSelectionMatches, searchKeymap } from "@codemirror/search";
import { autocompletion, closeBrackets, closeBracketsKeymap, completionKeymap } from "@codemirror/autocomplete";
import { tags as t } from "@lezer/highlight";

/** 每门语言一个独立 chunk：只有选到它才会被下载 */
const LANGS = {
  python: () => import("@codemirror/lang-python").then((m) => m.python()),
  cpp: () => import("@codemirror/lang-cpp").then((m) => m.cpp()),
};

/** 已加载过的语言扩展缓存（切回来不用再 import） */
const langCache = new Map();

/**
 * 引擎函数名补全源。
 *
 * 为什么需要：控制台的核心价值就是"调引擎那 400 多个函数"，而用户不可能背下这些名字
 * （原版 PyQt 也是把引擎函数名喂给 QCompleter 的）。C++ 模式尤其明显——
 * @codemirror/lang-cpp 的 languageData 里**根本没有** autocomplete，一个候选都没有。
 *
 * 用 EditorState.languageData 追加，而不是 autocompletion({override:...})：
 * 后者会把语言自带的候选（Python 内置名、snippet）一起顶掉，得不偿失。
 */
function engineCompletionSource(holder) {
  return (ctx) => {
    // holder.list 是可变的：函数表要过桥去取（list_functions），通常比编辑器晚到。
    // 所以这里**不能**在空的时候返回 null 把源整个注册掉——那样后到的候选永远进不来
    // （实测踩过：面板里只有 Python 内置名，一个引擎函数都没有）。
    if (!holder.list.length) return null;
    const word = ctx.matchBefore(/[\w:.>]*/);
    if (!word) return null;
    if (word.from === word.to && !ctx.explicit) return null;   // 空词要 Ctrl+Space 才弹
    return { from: word.from, options: holder.list, validFor: /^[\w:.>]*$/ };
  };
}

/** 把函数名数组转成 CodeMirror 的候选对象（字符串会让渲染抛 localeCompare 异常）。 */
function toCompletionOptions(names) {
    // boost 给高一点：空查询时 CodeMirror 按分数排序，Python 内置名会把 424 个引擎函数
  // 整个挤出可视的 100 条（实测就是这样）。控制台的重点是调引擎，所以让引擎名优先。
  return names.map((c) =>
    typeof c === "string" ? { label: c, type: "function", boost: 99 } : c);
}

async function loadLanguage(name) {
  if (!LANGS[name]) return [];
  if (langCache.has(name)) return langCache.get(name);
  const ext = await LANGS[name]();
  langCache.set(name, ext);
  return ext;
}

export function languageNames() {
  return Object.keys(LANGS);
}

/**
 * 主题：颜色全部取自项目的外观变量（theme.css）。
 *
 * 语法着色的分工（数学/编程代码都常见，刻意把关键字与函数名分开，
 * 免得一屏全是同一种颜色）：
 *   关键字 / 运算符 → 强调色    数字 / 常量 → 成功色
 *   字符串          → 暖色        注释       → 弱化色（不抢视线）
 *   函数名          → 强调色的亮版
 */
const baseTheme = EditorView.theme({
  "&": {
    color: "var(--text)",
    backgroundColor: "var(--surface-alt)",
    fontSize: "12.5px",
    height: "100%",
  },
  ".cm-scroller": {
    fontFamily: "var(--font-mono)",
    lineHeight: "1.6",
    overflow: "auto",
  },
  ".cm-content": { caretColor: "var(--accent)", padding: "8px 0" },
  ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--accent)", borderLeftWidth: "2px" },
  "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection": {
    backgroundColor: "var(--accent-soft)",
  },
  ".cm-activeLine": { backgroundColor: "transparent" },
  ".cm-gutters": {
    backgroundColor: "var(--surface-alt)",
    color: "var(--text-subtle)",
    border: "none",
    borderRight: "1px solid var(--border)",
  },
  ".cm-activeLineGutter": { backgroundColor: "var(--surface)", color: "var(--text-muted)" },
  ".cm-lineNumbers .cm-gutterElement": { padding: "0 8px 0 10px" },
  ".cm-matchingBracket, &.cm-focused .cm-matchingBracket": {
    backgroundColor: "var(--accent-soft)",
    outline: "1px solid var(--accent)",
    color: "inherit",
  },
  ".cm-nonmatchingBracket": { color: "var(--danger)" },
  ".cm-selectionMatch": { backgroundColor: "var(--accent-soft)" },
  ".cm-panels": { backgroundColor: "var(--surface)", color: "var(--text)", border: "none" },
  ".cm-panels.cm-panels-top": { borderBottom: "1px solid var(--border)" },
  ".cm-textfield": {
    background: "var(--surface-alt)", color: "var(--text)",
    border: "1px solid var(--border)", borderRadius: "var(--r-sm)", padding: "2px 6px",
  },
  ".cm-tooltip": {
    background: "var(--surface)", color: "var(--text)",
    border: "1px solid var(--border)", borderRadius: "var(--r-md)",
    boxShadow: "var(--shadow-2)",
  },
  ".cm-tooltip-autocomplete > ul > li[aria-selected]": {
    background: "var(--accent-soft)", color: "var(--accent)",
  },
});

const highlight = HighlightStyle.define([
  { tag: t.comment, color: "var(--text-subtle)", fontStyle: "italic" },
  { tag: [t.keyword, t.operatorKeyword, t.modifier], color: "var(--accent)", fontWeight: "600" },
  { tag: [t.string, t.special(t.string)], color: "var(--success)" },
  { tag: [t.number, t.bool, t.null, t.atom], color: "var(--danger)" },
  { tag: [t.function(t.variableName), t.function(t.propertyName)], color: "var(--accent-hover)" },
  { tag: [t.typeName, t.className, t.namespace], color: "var(--success)", fontWeight: "600" },
  { tag: [t.definition(t.variableName), t.definition(t.propertyName)], color: "var(--text)" },
  { tag: [t.variableName, t.propertyName], color: "var(--text-muted)" },
  { tag: [t.operator, t.punctuation, t.bracket], color: "var(--text-subtle)" },
  { tag: t.meta, color: "var(--text-subtle)" },
  { tag: t.invalid, color: "var(--danger)", textDecoration: "underline wavy" },
]);

/** Tab 缩进：选中多行时整块缩进，光标处插入空格（和原来的 textarea 手感一致） */
const tabKeymap = [
  {
    key: "Tab",
    run: (view) => {
      if (view.state.selection.ranges.some((r) => !r.empty)) return indentMore(view);
      view.dispatch(view.state.replaceSelection("    "));
      return true;
    },
    shift: indentLess,
  },
];

/**
 * 创建编辑器。
 *
 * @returns {{view: EditorView, setDoc(s:string):void, getDoc():string,
 *            setLanguage(name:string):Promise<void>, focus():void, destroy():void}}
 */
export async function createEditor({ parent, doc = "", language = "python", onRun = null, onChange = null, candidates = [] }) {
  const langCompartment = new Compartment();
  const initialLang = await loadLanguage(language);
  // 引擎函数名补全：函数表由 ConsoleView 过桥取，通常比编辑器晚到，
  // 所以这里用一个可变 holder 始终注册，后到的候选随时生效（见 setCandidates）。
  const holder = { list: toCompletionOptions(candidates) };
  const completionExt = EditorState.languageData.of(() => [
    { autocomplete: engineCompletionSource(holder) },
  ]);

  const view = new EditorView({
    parent,
    state: EditorState.create({
      doc,
      extensions: [
        lineNumbers(),
        highlightSpecialChars(),
        history(),
        drawSelection(),
        dropCursor(),
        EditorState.allowMultipleSelections.of(true),
        indentOnInput(),
        bracketMatching(),
        closeBrackets(),
        autocompletion(),
        completionExt,
        rectangularSelection(),
        crosshairCursor(),
        highlightActiveLine(),
        highlightActiveLineGutter(),
        highlightSelectionMatches(),
        EditorView.lineWrapping,
        syntaxHighlighting(highlight),
        baseTheme,
        keymap.of([
          // Ctrl/Cmd+Enter 运行：写代码的人习惯这个，不用去够按钮
          { key: "Mod-Enter", run: () => { onRun?.(); return true; } },
          ...closeBracketsKeymap,
          ...defaultKeymap,
          ...searchKeymap,
          ...historyKeymap,
          ...completionKeymap,
          ...tabKeymap,
        ]),
        langCompartment.of(initialLang),
        EditorView.updateListener.of((u) => {
          if (u.docChanged) onChange?.(u.state.doc.toString());
        }),
      ],
    }),
  });

  return {
    view,
    getDoc: () => view.state.doc.toString(),
    /** 更新补全候选（函数表取回后调用） */
    setCandidates(names) { holder.list = toCompletionOptions(names || []); },
    setDoc(text) {
      const cur = view.state.doc.toString();
      if (cur === text) return;                      // 避免和 v-model 互相触发
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text } });
    },
    async setLanguage(name) {
      const ext = await loadLanguage(name);
      view.dispatch({ effects: langCompartment.reconfigure(ext) });
    },
    focus: () => view.focus(),
    destroy: () => view.destroy(),
  };
}
