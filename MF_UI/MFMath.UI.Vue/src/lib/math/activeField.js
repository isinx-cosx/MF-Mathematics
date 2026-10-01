/**
 * activeField.js — "符号往哪儿插"的唯一判据
 *
 * v1 的做法是 `QApplication.focusWidget()`：**只看当前的全局焦点**。
 * 于是有三个真实问题（都能在 v1 里复现）：
 *   ① 点键盘按钮时焦点已经跑到按钮上了 —— v1 只能靠 `setFocusPolicy(NoFocus)`
 *      这个隐式约束兜住，任何人后来给按钮加个可聚焦属性就会静默失效；
 *   ② 只支持 `QLineEdit`：AI 输入框、控制台这些 `QTextEdit` 一律无效；
 *   ③ 找不到目标时**静默忽略**，用户不知道是键盘坏了还是自己点错了。
 *
 * 这里改成"记住最后聚焦过的输入框"（last-focused），于是：
 *   · 点键盘、点搜索框、点分类页签都不会丢掉插入目标；
 *   · 仍然保留 v1 的 NoFocus 约束（键位 tabindex="-1" + mousedown.prevent），
 *     因为那条约束本身是对的 —— 只是不再作为唯一保障；
 *   · 没有可用目标时返回 false，由界面明确提示。
 */
import { ref } from "vue";

const active = ref(null); // { id, kind, insertLatex(latex, opts), focus() }

let seq = 0;

/** 组件挂载时登记一个可插入目标；返回注销函数 */
export function createFieldHandle({ kind = "mathfield", insertLatex, focus }) {
  const id = `field-${++seq}`;
  const handle = {
    id,
    kind,
    insertLatex: (latex, opts) => insertLatex(latex, opts),
    focus: () => focus?.(),
  };
  return {
    handle,
    activate: () => { active.value = handle; },
    deactivate: () => { if (active.value?.id === id) active.value = null; },
  };
}

/** 兜底：没登记过字段时，看当前 DOM 焦点本身是不是可插入的 <math-field>。
 *
 * 为什么需要它：实测发现 MathLive 的元素在**程序化聚焦**（el.focus()）时不会
 * 触发我们挂在宿主上的 focusin（真实鼠标点击会触发）。只靠"最后聚焦"这一条，
 * 就会出现"焦点明明在输入框里、键盘却说没选中输入框"的错判。
 * 两条一起用：登记句柄优先（它能正确回写 Vue 状态），DOM 焦点兜底。 */
function domActiveTarget() {
  const el = typeof document === "undefined" ? null : document.activeElement;
  if (!el) return null;
  if (el.tagName === "MATH-FIELD") {
    return {
      id: "dom-active",
      kind: "mathfield",
      insertLatex: (latex, opts) => el.insert(latex, opts || { selectionMode: "placeholder" }),
      focus: () => el.focus(),
    };
  }
  return null;
}

/** 当前可插入目标（登记句柄 → DOM 焦点兜底） */
export function currentTarget() {
  return active.value || domActiveTarget();
}

/** 兼容既有调用名：返回当前可插入目标（可能来自兜底） */
export const activeField = () => currentTarget();

/** 插入 LaTeX；返回是否真的插入了（false = 界面应提示"先点一下输入框"） */
export function insertLatex(latex, opts) {
  const f = currentTarget();
  if (!f) return false;
  try {
    f.insertLatex(latex, opts);
    return true;
  } catch {
    return false;
  }
}

/** 纯文本目标的兜底（AI 对话输入框这类将来会用到，先留着不假装已支持） */
export function insertPlainText(text) {
  const el = document.activeElement;
  if (!el || !(el.tagName === "INPUT" || el.tagName === "TEXTAREA")) return false;
  const start = el.selectionStart ?? el.value.length;
  const end = el.selectionEnd ?? start;
  el.value = el.value.slice(0, start) + text + el.value.slice(end);
  const pos = start + text.length;
  try { el.setSelectionRange(pos, pos); } catch { /* 某些类型不支持，忽略 */ }
  el.dispatchEvent(new Event("input", { bubbles: true }));
  return true;
}
