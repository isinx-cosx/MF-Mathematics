import { createElement, useEffect, useRef, useState } from "react";
import type { HTMLAttributes, ReactNode, Ref } from "react";
/* 与 Vue 版**共用同一份样式**（同一套视觉，改一处两边生效）。
 * 路径相对本文件：src/components → 上两级是 MFMath.UI.React，再上一级才是 MF_UI。 */
import "../../../MFMath.UI.Vue/src/styles/select-box.css";

export type SelectOption = {
  value: string;
  label: ReactNode;
  /** 展开到隐藏原生 <option> 的 data-* 上（用例靠 option.dataset.* 判断状态时用） */
  data?: Record<string, string>;
};

type Props = {
  value: string;
  options: SelectOption[];
  /** 选中回调（只给值，不给事件 —— 调用方拿到的是"选了什么"） */
  onChange: (value: string) => void;
  /** 隐藏原生 select 的类名（兼容既有选择器，如 `input lang`） */
  nativeClass?: string;
  /** 额外落到隐藏原生 select 上的属性（如 data-search="engine"） */
  nativeAttrs?: Record<string, string>;
  ariaLabel?: string;
  placeholder?: string;
  disabled?: boolean;
  handleRef?: Ref<HTMLSelectElement>;
} & Omit<HTMLAttributes<HTMLButtonElement>, "onChange" | "value">;

/**
 * SelectBox（React 版）—— 自绘下拉，替换原生 `<select>` 的系统弹层。
 *
 * 与 Vue 版行为一致（见 `MFMath.UI.Vue/src/components/ui/SelectBox.vue` 的文件头）：
 * 弹层自己画（主题/字体预设都能跟上），但**保留一个隐藏的原生 `<select>`** 作为数据源与
 * 既有用例的抓手 —— 那些用例是 `querySelector('.xxx')` 取 option、设 value 再派发 change。
 *
 * 传给组件的其余属性（如 `data-tour`）落在**看得见的触发区**上：教程引导要高亮的是它，
 * 而不是 1px 的隐藏 select。
 */
export default function SelectBox({
  value, options, onChange, nativeClass = "input", nativeAttrs, ariaLabel, placeholder = "请选择",
  disabled = false, handleRef, ...rest
}: Props) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const wrapRef = useRef<HTMLSpanElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const nativeRef = useRef<HTMLSelectElement | null>(null);
  const listRef = useRef<HTMLUListElement | null>(null);

  const currentIndex = options.findIndex((o) => o.value === value);
  const current = currentIndex >= 0 ? options[currentIndex] : null;

  const openList = () => {
    if (disabled) return;
    setOpen(true);
    setActiveIndex(currentIndex >= 0 ? currentIndex : 0);
  };
  const closeList = (focusBack = false) => {
    setOpen(false);
    setActiveIndex(-1);
    if (focusBack) triggerRef.current?.focus();
  };
  const toggle = () => (open ? closeList(true) : openList());

  const pick = (v: string) => {
    if (v !== value) onChange(v);
    // 让隐藏的 select 跟上（有些旧逻辑直接读它）
    const sel = nativeRef.current;
    if (sel && sel.value !== v) sel.value = v;
    closeList(true);
    triggerRef.current?.focus();
  };

  const move = (delta: number) => {
    const n = options.length;
    if (!n) return;
    const from = activeIndex < 0 ? Math.max(currentIndex, 0) : activeIndex;
    setActiveIndex((from + delta + n) % n);
  };

  /* 当前项滚进可视区 */
  useEffect(() => {
    if (!open) return;
    const el = listRef.current?.querySelector(".sb-opt.is-active");
    if (el && typeof (el as HTMLElement).scrollIntoView === "function") {
      (el as HTMLElement).scrollIntoView({ block: "nearest" });
    }
  }, [open, activeIndex]);

  /* 点外部 / Esc 收起 */
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) closeList();
    };
    document.addEventListener("pointerdown", onDown, true);
    return () => document.removeEventListener("pointerdown", onDown, true);
  }, [open]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;
    const k = e.key;
    if (!open) {
      if (k === "Enter" || k === " " || k === "ArrowDown" || k === "ArrowUp") { e.preventDefault(); openList(); }
      return;
    }
    if (k === "Escape" || k === "Tab") { e.preventDefault(); closeList(true); return; }
    if (k === "Enter" || k === " ") {
      e.preventDefault();
      const o = options[activeIndex];
      if (o) pick(o.value);
      return;
    }
    if (k === "ArrowDown") { e.preventDefault(); move(1); return; }
    if (k === "ArrowUp") { e.preventDefault(); move(-1); return; }
    if (k === "Home") { e.preventDefault(); setActiveIndex(0); return; }
    if (k === "End") { e.preventDefault(); setActiveIndex(options.length - 1); }
  };

  return createElement(
    "span",
    { ref: wrapRef as unknown as Ref<HTMLSpanElement>, className: "sb" + (open ? " is-open" : "") + (disabled ? " is-disabled" : ""), onKeyDown },
    createElement(
      "button",
      {
        ref: triggerRef, type: "button", className: "sb-trigger", disabled,
        role: "combobox", "aria-haspopup": "listbox", "aria-expanded": open ? "true" : "false",
        "aria-label": ariaLabel || undefined, onClick: toggle,
        ...rest,
      },
      createElement("span", { className: "sb-label" }, current ? current.label : placeholder),
      createElement("svg", { className: "sb-caret", viewBox: "0 0 12 12", "aria-hidden": "true" },
        createElement("path", {
          d: "M2.5 4.5 6 8l3.5-3.5", fill: "none", stroke: "currentColor",
          strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round",
        })),
    ),
    open && createElement(
      "ul",
      { ref: listRef, className: "sb-list", role: "listbox", "aria-label": ariaLabel || undefined },
      ...options.map((o, i) =>
        createElement(
          "li",
          {
            key: o.value,
            className: "sb-opt" + (i === activeIndex ? " is-active" : "") + (o.value === value ? " is-selected" : ""),
            role: "option",
            "aria-selected": o.value === value ? "true" : "false",
            onMouseEnter: () => setActiveIndex(i),
            onClick: () => pick(o.value),
          },
          createElement("span", { className: "sb-opt-label" }, o.label),
          o.value === value && createElement("svg", { className: "sb-check", viewBox: "0 0 12 12", "aria-hidden": "true" },
            createElement("path", {
              d: "M2 6.5 4.5 9 10 3.5", fill: "none", stroke: "currentColor",
              strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round",
            })),
        )),
    ),
    /* 隐藏原生 select：数据真相 + 既有用例的抓手 */
    createElement(
      "select",
      {
        ref: handleRef ? (el: HTMLSelectElement | null) => { nativeRef.current = el; (handleRef as (v: HTMLSelectElement | null) => void)(el); } : nativeRef,
        className: "sr-select " + nativeClass,
        tabIndex: -1,
        "aria-hidden": "true",
        value,
        disabled,
        onChange: () => { const v = nativeRef.current?.value ?? ""; if (v !== value) onChange(v); },
        ...(nativeAttrs || {}),
      },
      ...options.map((o) => createElement("option", { key: o.value, value: o.value, ...(o.data || {}) }, o.label as ReactNode)),
    ),
  );
}
