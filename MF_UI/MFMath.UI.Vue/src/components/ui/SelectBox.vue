<script setup>
/**
 * SelectBox — 自绘下拉选择器（替换原生 `<select>` 的系统弹层）。
 *
 * 为什么不用原生 `<select>`：**弹层由操作系统绘制**，CSS 管不到它 ——
 * 深色主题下会弹出一个浅色的系统列表，圆角/阴影/字体全跟界面不一致，
 * 换「字体预设」时那一层也不会变。要"随样式变化"就只能自己画。
 *
 * 设计上的两个关键决定：
 *
 * ① **保留一个隐藏的原生 `<select>` 作为数据源**（`.sr-select`）。
 *    · 兼容：既有用例是
 *        `document.querySelector('.console-wrap .input.lang')` → 取 `option` 列表
 *        → 设 `.value = 'cpp'` 再派发 `change`
 *      只要这个 select 还在、类名还在、`option` 还在，那些断言就不用改一行。
 *    · 无障碍：**由自绘层承担**（combobox + listbox + 完整键盘操作）；
 *      隐藏 select 设 `aria-hidden`，避免读屏里出现两个控件。
 *    自绘层与它双向同步：点选 → 写回 select；外部改 select → 同步到自绘层。
 *
 * ② **颜色/字体全部走 CSS 变量**（--surface/--border/--accent/--font-ui …），
 *    所以切主题、切「字体预设」、玻璃拟态都会自动跟上 —— 这正是用户要的"随样式变化"。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  modelValue: { type: String, default: "" },
  /** [{ value, label }] */
  options: { type: Array, default: () => [] },
  /** 隐藏原生 select 的类名（调用方靠它兼容既有用例/选择器） */
  nativeClass: { type: String, default: "input" },
  ariaLabel: { type: String, default: "" },
  placeholder: { type: String, default: "请选择" },
  disabled: { type: Boolean, default: false },
});
const emit = defineEmits(["update:modelValue", "change"]);

const open = ref(false);
const activeIndex = ref(-1);
const wrap = ref(null);
const trigger = ref(null);
const nativeSel = ref(null);
const listEl = ref(null);

const currentIndex = computed(() => props.options.findIndex((o) => o.value === props.modelValue));
const currentLabel = computed(() => {
  const o = props.options[currentIndex.value];
  return o ? o.label : props.placeholder;
});

function openList() {
  if (props.disabled) return;
  open.value = true;
  activeIndex.value = currentIndex.value >= 0 ? currentIndex.value : 0;
  nextTick(() => {
    // 让当前项滚进可视区
    const el = listEl.value?.querySelector(".sb-opt.is-active");
    if (el && typeof el.scrollIntoView === "function") el.scrollIntoView({ block: "nearest" });
  });
}
function closeList(focusBack = false) {
  if (!open.value) return;
  open.value = false;
  activeIndex.value = -1;
  if (focusBack) trigger.value?.focus();
}
function toggle() { open.value ? closeList(true) : openList(); }

/** 选中：写回隐藏 select（**不**再派发 change —— 否则会和上面的 emit 重复触发一次） */
function pick(v) {
  if (v !== props.modelValue) {
    emit("update:modelValue", v);
    emit("change", v);
  }
  const sel = nativeSel.value;
  if (sel && sel.value !== v) sel.value = v;
  closeList(true);
  trigger.value?.focus();
}

function move(delta) {
  const n = props.options.length;
  if (!n) return;
  const from = activeIndex.value < 0 ? (currentIndex.value < 0 ? 0 : currentIndex.value) : activeIndex.value;
  activeIndex.value = (from + delta + n) % n;
  nextTick(() => {
    const el = listEl.value?.querySelector(".sb-opt.is-active");
    if (el && typeof el.scrollIntoView === "function") el.scrollIntoView({ block: "nearest" });
  });
}

function onKeydown(e) {
  if (props.disabled) return;
  const k = e.key;
  if (!open.value) {
    if (k === "Enter" || k === " " || k === "ArrowDown" || k === "ArrowUp") { e.preventDefault(); openList(); }
    return;
  }
  if (k === "Escape" || k === "Tab") { e.preventDefault(); closeList(true); return; }
  if (k === "Enter" || k === " ") {
    e.preventDefault();
    const o = props.options[activeIndex.value];
    if (o) pick(o.value);
    return;
  }
  if (k === "ArrowDown") { e.preventDefault(); move(1); return; }
  if (k === "ArrowUp") { e.preventDefault(); move(-1); return; }
  if (k === "Home") { e.preventDefault(); activeIndex.value = 0; return; }
  if (k === "End") { e.preventDefault(); activeIndex.value = props.options.length - 1; return; }
}

/** 原生 select 被外部改（含既有用例直接设 .value + change）时，同步到自绘层 */
function onNativeChange() {
  const v = nativeSel.value?.value ?? "";
  if (v !== props.modelValue) { emit("update:modelValue", v); emit("change", v); }
}

function onDocPointerDown(e) {
  if (!open.value) return;
  if (wrap.value && !wrap.value.contains(e.target)) closeList();
}
/** 窗口失焦（切到别的应用）时收起弹层 */
function onWinBlur() { closeList(); }

watch(() => props.modelValue, (v) => {
  // 外部把值改成一个列表里没有的值时，别让自绘层停在旧标签上
  if (v && props.options.every((o) => o.value !== v)) closeList();
});

onMounted(() => {
  document.addEventListener("pointerdown", onDocPointerDown, true);
  window.addEventListener("blur", onWinBlur);
});
onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onDocPointerDown, true);
  window.removeEventListener("blur", onWinBlur);
});
</script>

<template>
  <span ref="wrap" class="sb" :class="{ 'is-open': open, 'is-disabled': disabled }" @keydown="onKeydown">
    <!-- 自绘触发区（视觉上就是"那个下拉框"） -->
    <button
      ref="trigger"
      type="button"
      class="sb-trigger"
      :disabled="disabled"
      role="combobox"
      aria-haspopup="listbox"
      :aria-expanded="open ? 'true' : 'false'"
      :aria-label="ariaLabel || undefined"
      @click="toggle"
    >
      <span class="sb-label">{{ currentLabel }}</span>
      <svg class="sb-caret" viewBox="0 0 12 12" aria-hidden="true">
        <path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.6"
              stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>

    <!-- 自绘弹层 -->
    <ul v-if="open" ref="listEl" class="sb-list" role="listbox" :aria-label="ariaLabel || undefined">
      <li
        v-for="(o, i) in options"
        :key="o.value"
        class="sb-opt"
        :class="{ 'is-active': i === activeIndex, 'is-selected': o.value === modelValue }"
        role="option"
        :aria-selected="o.value === modelValue ? 'true' : 'false'"
        @mouseenter="activeIndex = i"
        @click="pick(o.value)"
      >
        <span class="sb-opt-label">{{ o.label }}</span>
        <svg v-if="o.value === modelValue" class="sb-check" viewBox="0 0 12 12" aria-hidden="true">
          <path d="M2 6.5 4.5 9 10 3.5" fill="none" stroke="currentColor" stroke-width="1.8"
                stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </li>
    </ul>

    <!-- 隐藏的原生 select：数据真相 + 无障碍 + 兼容既有用例（见文件头 ① ） -->
    <select
      ref="nativeSel"
      class="sr-select"
      :class="nativeClass"
      tabindex="-1"
      aria-hidden="true"
      :value="modelValue"
      :disabled="disabled"
      @change="onNativeChange"
    >
      <option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
    </select>
  </span>
</template>

<style>
/* 非 scoped：颜色/字体一律用主题变量，切主题、切字体预设自动生效 */
.sb { position: relative; display: inline-flex; align-items: center; flex: 0 0 auto; }

/* 触发区：与「虚影」输入框同一套观感（淡底 + 极淡内描边），聚焦出主题色光环 */
.sb-trigger {
  display: inline-flex; align-items: center; gap: 8px;
  height: var(--input-h, 30px); padding: 0 10px 0 12px;
  border: 1px solid transparent; border-radius: var(--r-sm);
  background: var(--surface-alt); color: var(--text);
  box-shadow: inset 0 0 0 1px rgba(127, 127, 127, .18);
  font-family: var(--font-ui); font-size: 13px; font-weight: 500;
  cursor: pointer; white-space: nowrap;
  transition: background .12s, box-shadow .12s, color .12s;
}
.sb-trigger:hover { box-shadow: inset 0 0 0 1px rgba(127, 127, 127, .30); }
.sb-trigger:focus-visible,
.sb.is-open .sb-trigger {
  outline: none; background: var(--surface);
  box-shadow: inset 0 0 0 1px rgba(127, 127, 127, .24), 0 0 0 3px var(--accent-soft);
}
.sb-label { max-width: 160px; overflow: hidden; text-overflow: ellipsis; }
.sb-caret { width: 12px; height: 12px; flex: 0 0 auto; color: var(--text-subtle); transition: transform .15s; }
.sb.is-open .sb-caret { transform: rotate(180deg); }
.sb.is-disabled .sb-trigger { opacity: .55; cursor: not-allowed; }

/* 弹层：跟随主题的表面/描边/阴影/圆角；深色主题下不会再弹出浅色系统列表 */
.sb-list {
  position: absolute; z-index: 60; top: calc(100% + 4px); left: 0;
  min-width: max(100%, 132px); max-width: 320px; max-height: 264px; overflow: auto;
  margin: 0; padding: 4px; list-style: none;
  background: var(--surface); color: var(--text);
  border: 1px solid var(--border); border-radius: var(--r-md, 10px);
  box-shadow: var(--shadow-2, 0 10px 30px rgba(0, 0, 0, .18));
  font-family: var(--font-ui); font-size: 13px;
}
.sb-opt {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 8px; border-radius: var(--r-sm);
  cursor: pointer; white-space: nowrap;
}
.sb-opt.is-active { background: var(--accent-soft); color: var(--text); }
.sb-opt.is-selected { font-weight: 600; }
.sb-opt-label { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.sb-check { width: 12px; height: 12px; color: var(--accent); flex: 0 0 auto; }

/* 隐藏原生 select：仍可被脚本读写、仍参与无障碍树，但不占视觉位置 */
.sr-select {
  position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0;
  overflow: hidden; clip: rect(0 0 0 0); clip-path: inset(50%);
  border: 0; opacity: 0; pointer-events: none;
}
</style>
