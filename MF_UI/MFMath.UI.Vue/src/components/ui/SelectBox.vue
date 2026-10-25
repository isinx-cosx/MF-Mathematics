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

/* 组件根是 <span>，但调用方写的 data-tour 之类应当落在**看得见的触发区**上，
 * 否则教程引导会高亮到一个 1px 的隐藏 select。所以关掉自动继承、手动 v-bind 到 trigger。 */
defineOptions({ inheritAttrs: false });

const props = defineProps({
  modelValue: { type: String, default: "" },
  /** [{ value, label, data? }] —— `data` 会展开到隐藏原生 `<option>` 的 data-* 上
   *  （计算页的模式下拉靠 `option.dataset.mapped` / `dataset.varDialog` 判断"接没接引擎"） */
  options: { type: Array, default: () => [] },
  /** 隐藏原生 select 的类名（调用方靠它兼容既有用例/选择器） */
  nativeClass: { type: String, default: "input" },
  /** 额外落到**隐藏原生 select** 上的属性（如 `data-search="engine"`：用例按属性找它） */
  nativeAttrs: { type: Object, default: () => ({}) },
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
      v-bind="$attrs"
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

    <!-- 隐藏的原生 select：数据真相 + 兼容既有用例（见文件头 ① ） -->
    <select
      ref="nativeSel"
      class="sr-select"
      :class="nativeClass"
      tabindex="-1"
      aria-hidden="true"
      :value="modelValue"
      :disabled="disabled"
      v-bind="nativeAttrs"
      @change="onNativeChange"
    >
      <option
        v-for="o in options"
        :key="o.value"
        :value="o.value"
        v-bind="o.data || {}"
      >{{ o.label }}</option>
    </select>
  </span>
</template>

<style src="../../styles/select-box.css"></style>

