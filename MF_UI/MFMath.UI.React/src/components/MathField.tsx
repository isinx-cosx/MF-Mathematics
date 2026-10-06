import { createElement, useEffect, useImperativeHandle, useRef } from "react";
import type { Ref } from "react";
import "mathlive";
import { toEngineExpr } from "@shared/plot/prepare.js";
import { createFieldHandle } from "../lib/activeField";
import "../styles/math-field.css";

export type MathFieldHandle = {
  focus: () => void;
  insertLatex: (latex: string, opts?: unknown) => void;
};

type Props = {
  /** 引擎语法（与 Vue 版 v-model 的值一致） */
  value: string;
  placeholder?: string;
  dataTour?: string;
  /** LaTeX 变化（MathLive 的值） */
  onChange?: (latex: string) => void;
  /** 引擎语法变化（经 to_engine_expr 规范化） */
  onValueChange?: (engine: string) => void;
  onFocus?: () => void;
  onBlur?: () => void;
  onEnter?: () => void;
  handleRef?: Ref<MathFieldHandle>;
};

/**
 * MathField — MathLive 的 <math-field> 就地数学输入框（照抄 Vue 版 MathField.vue）。
 * 类名沿用 `expr-input mathfield`，样式来自同一份抽出的 CSS，外观与 Vue 版一致。
 */
export default function MathField({
  value, placeholder = "", dataTour, onChange, onValueChange, onFocus, onBlur, onEnter, handleRef,
}: Props) {
  const elRef = useRef<HTMLElement | null>(null);
  const editing = useRef(false);
  const lastEmitted = useRef<string | null>(null);
  const cbs = useRef({ onChange, onValueChange, onFocus, onBlur, onEnter });
  cbs.current = { onChange, onValueChange, onFocus, onBlur, onEnter };

  useImperativeHandle(handleRef, () => ({
    focus: () => elRef.current?.focus(),
    insertLatex: (latex: string, opts?: unknown) => {
      const mf = elRef.current as unknown as { focus(): void; insert?(l: string, o?: unknown): void; value?: string };
      if (!mf) return;
      mf.focus();
      if (typeof mf.insert === "function") {
        mf.insert(latex, opts ?? { selectionMode: "placeholder" });
        cbs.current.onValueChange?.(toEngineExpr(mf.value ?? ""));
      }
    },
  }), []);

  useEffect(() => {
    const mf = elRef.current as unknown as {
      value: string; addEventListener(t: string, f: (e: Event) => void): void;
      removeEventListener(t: string, f: (e: Event) => void): void;
      setAttribute(k: string, v: string): void; mathVirtualKeyboardPolicy?: string;
    } | null;
    if (!mf) return;

    mf.value = value || "";
    if (placeholder) mf.setAttribute("aria-label", placeholder);
    try { mf.mathVirtualKeyboardPolicy = "manual"; } catch { /* 老版本无此属性 */ }

    const onInput = () => {
      const latex = mf.value ?? "";
      cbs.current.onChange?.(latex);
      const eng = toEngineExpr(latex);
      lastEmitted.current = eng;
      cbs.current.onValueChange?.(eng);
    };
    const markActive = () => { editing.current = true; cbs.current.onFocus?.(); field?.activate(); };
    const onFocusOut = () => { editing.current = false; cbs.current.onBlur?.(); };
    const onKeyDown = (e: Event) => {
      if ((e as KeyboardEvent).key === "Enter") cbs.current.onEnter?.();
    };

    /* 登记为"最后聚焦的数学输入框"，供数学键盘插入符号用。
     * 三种入口都登记：只挂 focusin 不够 —— MathLive 元素在程序化 focus() 时不触发它。 */
    const field = createFieldHandle({
      kind: "mathfield",
      insertLatex: (latex: string, opts?: unknown) => {
        const m = elRef.current as unknown as { focus(): void; insert?(l: string, o?: unknown): void; value?: string };
        if (!m) return;
        m.focus();
        if (typeof m.insert === "function") {
          m.insert(latex, opts ?? { selectionMode: "placeholder" });
          cbs.current.onValueChange?.(toEngineExpr(m.value ?? ""));
        }
      },
      focus: () => elRef.current?.focus(),
    });

    mf.addEventListener("input", onInput);
    mf.addEventListener("focusin", markActive);
    mf.addEventListener("focus", markActive);
    mf.addEventListener("pointerdown", markActive);
    mf.addEventListener("focusout", onFocusOut);
    mf.addEventListener("keydown", onKeyDown);
    return () => {
      mf.removeEventListener("input", onInput);
      mf.removeEventListener("focusin", markActive);
      mf.removeEventListener("focus", markActive);
      mf.removeEventListener("pointerdown", markActive);
      mf.removeEventListener("focusout", onFocusOut);
      mf.removeEventListener("keydown", onKeyDown);
      field.deactivate();
    };
    // 只在挂载时绑定：值与回调都通过 ref 读，避免反复解绑重绑打断输入
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* 外部改值才回写（用户输入过程中 editing=true，跳过以免光标跳动） */
  useEffect(() => {
    const mf = elRef.current as unknown as { value?: string } | null;
    if (!mf) return;
    if (editing.current) return;
    if (value === lastEmitted.current) return;
    if ((mf.value ?? "") === (value ?? "")) return;
    mf.value = value || "";
  }, [value]);

  return createElement("math-field", {
    ref: elRef as unknown as Ref<HTMLElement>,
    className: "expr-input mathfield",
    "math-virtual-keyboard-policy": "manual",
    ...(dataTour ? { "data-tour": dataTour } : {}),
  });
}
