<script setup>
/**
 * MathField — 用 MathLive 的 <math-field> 做**就地排版**的数学输入框。
 *
 * 与旧实现的关键区别：旧版是普通文本框 + 下方一行 LaTeX 预览；
 * 这里数学**直接显示在输入框里**——输入 \frac 就当场变成分数，
 * 光标位置、括号配对、上下标都由 MathLive 处理。
 *
 * 数据流（单向为主，避免打断输入）：
 *   MathLive 的 value 是 LaTeX
 *        ↓ 引擎 to_engine_expr 规范化
 *   引擎语法（= v-model 的值，供绘图/求值使用）
 * 只有**外部**改值时（切预设、新增行）才回写 LaTeX 到字段，
 * 用户输入过程中绝不回写，否则光标会跳。
 *
 * 外观上刻意做成"干净的一格"：
 *   · 关掉 MathLive 自带的右下角两个角标按钮（软键盘 / 菜单）——
 *     桌面端不需要软键盘，菜单按钮也只是噪声；右键菜单本身仍然可用。
 *   · 高度不写死：MathLive 内部 .ML__container 是 min-height:auto !important，
 *     分数、根式、上下标由内容决定高度，整格跟着长高，不会被裁掉。
 *     （之前写死 height:30px/34px，内容比框高，分数会压到下一行。）
 *   · 字号 = 数学排版尺寸：MathLive 的 .ML__latex 是 font-size:1em，
 *     继承宿主的 font-size，所以 13px 的输入框里 LaTeX 自然看不清，
 *     这里统一成 22px（界面基准字号 13px 的 1.7 倍）。
 *     嫌大/嫌小只改下面 font-size 与 min-height 两行即可，别在调用处再写一遍。
 */
import { onMounted, onBeforeUnmount, ref, watch } from "vue";
import "mathlive";
import { toEngineExpr } from "../../lib/plot/prepare.js";
import { createFieldHandle } from "../../lib/math/activeField.js";

const props = defineProps({
  modelValue: { type: String, default: "" },   // 引擎语法
  placeholder: { type: String, default: "" },
});
const emit = defineEmits(["update:modelValue", "change", "focus", "blur", "enter"]);

const el = ref(null);
const editing = ref(false);       // 用户正在输入：此时不回写 LaTeX
const lastEmitted = ref(null);    // 记住自己发出的值，避免回环
let field = null;                 // 数学键盘的"最后聚焦输入框"登记句柄

function latexFromEngine(text) {
  // 引擎语法 → 可让 MathLive 正确显示的 LaTeX。
  // 引擎语法本身几乎都能被 LaTeX 解析器接受（^ 幂、/ 分数、括号、
  // 函数名如 sin 会被 MathLive 识别成 \sin），所以直接回填即可。
  return text || "";
}

onMounted(() => {
  const mf = el.value;
  if (!mf) return;
  mf.value = latexFromEngine(props.modelValue);
  if (props.placeholder) mf.setAttribute("aria-label", props.placeholder);
  // 桌面端不弹软键盘。模板里已有 math-virtual-keyboard-policy="manual"，
  // 这里再设一次属性是为了兼容老版本 MathLive 只认 property 的情况。
  try { mf.mathVirtualKeyboardPolicy = "manual"; } catch { /* 老版本无此属性，忽略 */ }

  const onInput = () => {
    const latex = mf.value ?? "";
    emit("change", latex);
    // LaTeX → 引擎语法（引擎侧规范化，含 \frac/\sqrt/全角/π 等）
    const eng = toEngineExpr(latex);
    lastEmitted.value = eng;
    emit("update:modelValue", eng);
  };
  mf.addEventListener("input", onInput);
  // 登记为"最后聚焦的数学输入框"，供数学键盘插入符号用（见 lib/math/activeField.js）。
  // v1 靠 QApplication.focusWidget() 实时取焦点，点键盘时焦点已跑掉，只能靠
  // 按钮 NoFocus 兜住；这里改成记住最后一次聚焦的字段，更稳。
  field = createFieldHandle({
    kind: "mathfield",
    insertLatex: (latex, options) => insertLatex(latex, options),
    focus: () => el.value?.focus(),
  });
  // 三种入口都登记：focusin / focus / pointerdown。
  // 只挂 focusin 不够 —— 实测 MathLive 的元素在程序化 focus() 时不触发它，
  // 而真实鼠标点击会先走 pointerdown，所以三者合起来才覆盖全。
  const markActive = () => { editing.value = true; emit("focus"); field?.activate(); };
  mf.addEventListener("focusin", markActive);
  mf.addEventListener("focus", markActive);
  mf.addEventListener("pointerdown", markActive);
  mf.addEventListener("focusout", () => { editing.value = false; emit("blur"); });
  mf.addEventListener("keydown", (e) => {
    if (e.key === "Enter") emit("enter", e);
  });
  cleanup = () => mf.removeEventListener("input", onInput);
});
let cleanup = null;
onBeforeUnmount(() => { if (cleanup) cleanup(); field?.deactivate(); });

// 外部改值才回写（用户输入过程中 editing=true，跳过以免光标跳动）
watch(
  () => props.modelValue,
  (v) => {
    const mf = el.value;
    if (!mf) return;
    if (editing.value) return;
    if (v === lastEmitted.value) return;
    if ((mf.value ?? "") === (v ?? "")) return;
    mf.value = latexFromEngine(v);
  }
);

/** 供符号面板调用：把 LaTeX 插到光标处，可带 #0 占位。 */
function insertLatex(latex, options) {
  const mf = el.value;
  if (!mf) return;
  mf.focus();
  if (typeof mf.insert === "function") {
    mf.insert(latex, options || { selectionMode: "placeholder" });
    emit("update:modelValue", toEngineExpr(mf.value ?? ""));
  }
}
function focus() { el.value?.focus(); }
defineExpose({ focus, insertLatex });
</script>

<template>
  <!-- 类名沿用 expr-input：调用处与既有测试无需改动。
       math-virtual-keyboard-policy=manual：桌面端不弹软键盘。 -->
  <math-field
    ref="el"
    class="expr-input mathfield"
    math-virtual-keyboard-policy="manual"
  />
</template>

<style>
/* ── 输入框外观的**唯一出处** ──────────────────────────────────────────
 * 这里故意不写 scoped：几何、字号、以及 shadow DOM 里的角标按钮都必须
 * 作用在 <math-field> 元素本身。选择器用 `math-field.mathfield`（0,1,1），
 * 压过宿主页里的单类规则（.input 0,1,0、.mono 0,1,0）——
 * 但压不过 `[data-v-x]` 的两类选择器，所以各调用处不再自己写
 * height / padding / font-size（见 ExpressionList、CalcView）。
 */
math-field.mathfield {
  display: block;              /* 覆盖 MathLive 的 :host{display:block}，也避免被写成 flex */
  width: 100%;
  min-width: 0;                /* 作为 flex/grid 子项时允许收缩，不撑破行 */
  max-width: 100%;
  /* ↓ 高度自适应：只给下界，不给 height */
  height: auto;
  min-height: 60px;
  box-sizing: border-box;
  /* 上下留一点内边距，并让行盒在框内垂直居中（align-content 作用于块容器，
   * Chromium 123+ 支持；不支持时只是回落到顶对齐，不影响排版）。
   * 横向：内部 .ML__container 自带 4px，叠加 8px = 12px，与 .input 的 12px 对齐。 */
  padding: 7px 8px;
  align-content: center;
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  background: var(--surface-alt);
  color: var(--text);
  font-size: 22px;             /* 数学排版尺寸，直接决定 LaTeX 看得清不清 */
  font-family: 'Cambria Math', 'Latin Modern Math', Georgia, serif;
  outline: none;
  transition: border-color .12s, background .12s, box-shadow .12s;
  /* MathLive 的配色跟随主题 */
  --hue: 216;
  --caret-color: var(--accent);
  --selection-background-color: var(--accent-soft);
  --contains-highlight-background-color: transparent;
  --smart-fence-color: var(--accent);
  --highlight-text: var(--accent);
  --placeholder-color: var(--text-subtle);
}
math-field.mathfield:focus,
math-field.mathfield:focus-within {
  border-color: var(--accent);
  background: var(--surface);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
/* 去掉右下角自带的两个角标按钮：软键盘 + 菜单。
 * 这是 MathLive 官方文档给的隐藏方式（math-field::part(menu-toggle)）；
 * !important 只是保证不被内部 .ML__menu-toggle 的 display 压回来。 */
math-field.mathfield::part(virtual-keyboard-toggle),
math-field.mathfield::part(menu-toggle) {
  display: none !important;
}
/* 占位提示走 shadow DOM 里的 [part=placeholder] */
math-field.mathfield::part(placeholder) {
  color: var(--text-subtle);
  opacity: 1;
}
</style>
