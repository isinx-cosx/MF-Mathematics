/**
 * activeField — "最后聚焦的数学输入框"登记处（React 版）
 *
 * 数学键盘要把符号插到**用户最后点过的那个输入框**里。浏览器/桌面壳在点键盘按钮时
 * 焦点已经离开输入框，所以不能实时取焦点，只能在输入框获得焦点时登记下来。
 * 逻辑与 Vue 版 lib/math/activeField.js 一致，只是把 Vue 的 ref 换成订阅表。
 */
type Handle = {
  id: number;
  kind: string;
  insertLatex: (latex: string, opts?: unknown) => void;
  focus: () => void;
};

let nextId = 1;
let current: Handle | null = null;
const listeners = new Set<(h: Handle | null) => void>();

function notify() {
  for (const l of listeners) l(current);
}

export function createFieldHandle(init: Omit<Handle, "id" | "activate" | "deactivate"> & {
  kind: string;
  insertLatex: (latex: string, opts?: unknown) => void;
  focus: () => void;
}) {
  const handle: Handle = { id: nextId++, ...init };
  return {
    activate() { current = handle; notify(); },
    deactivate() { if (current === handle) { current = null; notify(); } },
    handle,
  };
}

/** 供 React 组件订阅"当前活动输入框"（用于高亮等 UI 需要） */
export function subscribeActiveField(cb: (h: Handle | null) => void) {
  listeners.add(cb);
  cb(current);
  return () => { listeners.delete(cb); };
}

export function activeField(): Handle | null {
  return current;
}

/** 把 LaTeX 插入当前活动输入框；没有活动输入框时返回 false（调用方给提示） */
export function insertLatex(latex: string, opts?: unknown): boolean {
  if (!current) return false;
  current.insertLatex(latex, opts);
  return true;
}

export function focusActiveField() {
  current?.focus();
}
