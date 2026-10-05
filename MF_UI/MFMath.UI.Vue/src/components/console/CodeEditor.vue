<script setup>
/**
 * CodeEditor — 控制台代码编辑框（CodeMirror 6，**惰性加载**）
 *
 * 为什么要换掉原来的 <textarea>：
 *   · 写代码没有行号、没有语法着色、没有括号配对，几十行的脚本读起来很累；
 *   · Tab / 撤销 / 查找这些最基本的编辑行为都没有；
 *   · 出错时引擎给的是 `main.cpp:5:13: error:`，用户得自己数行。
 *
 * 为什么惰性加载：控制台不是首页，编辑器内核 + 语法包有 150~250 KB。
 * 进控制台才 import，切到 C++ 才下载 C++ 语法包（见 lib/console/editor.js）。
 *
 * 为什么保留 textarea 回退：桌面端 chunk 从本地磁盘加载，正常不会失败；
 * 但万一 chunk 缺失，整个控制台就彻底不能写代码了——代价太大。
 * 所以 import 失败就退成普通 textarea：功能少一点，但**写得进去、跑得起来**。
 */
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from "vue";

const props = defineProps({
  modelValue: { type: String, default: "" },
  language: { type: String, default: "python" },
  placeholder: { type: String, default: "" },
  /** 引擎函数名候选（补全用）；空数组表示不做补全 */
  candidates: { type: Array, default: () => [] },
  /** 载入失败时是否允许退成 textarea */
  allowFallback: { type: Boolean, default: true },
});
const emit = defineEmits(["update:modelValue", "run"]);

const host = ref(null);
const loading = ref(true);
const ready = ref(false);
const fallback = ref(false);
const errorText = ref("");

let handle = null;
/** 语言切换期间可能有多次请求，只认最后一次（否则快速连点会用到旧语法） */
let langSeq = 0;
/**
 * 语言切换必须**串行**。setLanguage 内部是 `await loadLanguage(name)`（动态 import
 * 语言包，几十~几百毫秒）之后才 `dispatch(reconfigure)` —— 两次调用并发时，谁后
 * dispatch 谁说了算，于是先发出的慢请求会盖掉后发出的快请求，最终语法与下拉框不符。
 * 只用序号判断**挡不住**这一点：等 await 回来时 reconfigure 早已执行完。
 * 这里改成一条 Promise 链：同一时刻只有一个在跑，且排队期间被取代的请求直接跳过
 * （连语言包都不必再 import）。
 */
let langChain = Promise.resolve();
/** 组件是否已卸载：boot() 是异步的，期间可能已经 unmount */
let disposed = false;

/** 回退分支的双向绑定：直接走同一份 modelValue，避免两份状态 */
const fallbackText = computed({
  get: () => props.modelValue,
  set: (v) => emit("update:modelValue", v),
});

async function boot() {
  // 只动态 import：静态 import 会把编辑器打进主包，把懒加载的意义抵消掉
  let mod = null;
  try {
    mod = await import("../../lib/console/editor.js");
  } catch (e) {
    if (!props.allowFallback) throw e;
    fallback.value = true;
    loading.value = false;
    errorText.value = "编辑器内核加载失败，已退回到纯文本编辑框：" + String(e?.message || e);
    return;
  }
  if (disposed) return;                 // 动态 import 期间已卸载：不必再建
  await nextTick();
  if (disposed) return;
  try {
    const created = await mod.createEditor({
      parent: host.value,
      doc: props.modelValue,
      language: props.language,
      candidates: props.candidates,
      onRun: () => emit("run"),
      onChange: (text) => emit("update:modelValue", text),
    });
    if (disposed) {
      // 创建期间卸载了：onBeforeUnmount 当时看到的 handle 还是 null，不会替我们销毁。
      // 不在这里 destroy 的话，EditorView 会挂在已脱离文档的宿主上，连同它自己的
      // 监听与 MutationObserver 一起泄漏，且永远无人回收。
      created.destroy();
      return;
    }
    handle = created;
    // 给自动化测试与调试用：测试要能拿到 EditorView 才能设置/读取内容。
    // 挂成 DOM 属性而不是全局变量，够用又不污染 window。
    host.value.__mfEditor = handle;
    ready.value = true;
  } catch (e) {
    if (!props.allowFallback) throw e;
    fallback.value = true;
    errorText.value = "编辑器初始化失败，已退回到纯文本编辑框：" + String(e?.message || e);
  } finally {
    loading.value = false;
  }
}

onMounted(boot);

onBeforeUnmount(() => {
  disposed = true;
  if (handle) handle.destroy();
  handle = null;
});

// 外部改内容（载入示例、清空、切换示例下拉）→ 推进编辑器
watch(() => props.modelValue, (v) => {
  if (handle && handle.getDoc() !== v) handle.setDoc(v);
});

// 补全候选后到（要过桥取函数表）→ 推到编辑器里
watch(() => props.candidates, (v) => { handle?.setCandidates?.(v); });

// 切语言 → 换语法扩展（只下载那门语言的包）
watch(() => props.language, (lang) => {
  const seq = ++langSeq;
  langChain = langChain
    .then(async () => {
      // 顺序判断必须放在 await **之前**：等到 setLanguage 返回时 reconfigure
      // 早就 dispatch 完了，那时再判已经晚了（旧写法就是这个毛病）。
      if (seq !== langSeq) return;   // 排队期间已被更新的切换取代 → 本次作废
      if (!handle) return;
      await handle.setLanguage(lang);
    })
    .catch(() => { /* 某一门语言包加载失败不该毒化整条链、也不该卡住后续切换 */ });
});

defineExpose({ focus: () => handle?.focus() });
</script>

<template>
  <div class="editor-wrap">
    <!-- 根节点带 .editor：既有的样式与测试按这个类名找编辑区 -->
    <div ref="host" class="editor"></div>

    <textarea v-if="fallback" v-model="fallbackText" class="editor-ta mono"
              :placeholder="placeholder" spellcheck="false"
              @keydown.ctrl.enter.prevent="emit('run')"></textarea>

    <div v-if="loading" class="editor-loading">正在加载编辑器…</div>
    <div v-else-if="fallback" class="editor-warn">{{ errorText }}</div>
  </div>
</template>

<style scoped>
.editor-wrap { position: relative; flex: 1; min-height: 0; display: flex; flex-direction: column; }
.editor {
  flex: 1;
  /* 与右栏输出区高度大致相当，切语言/载入示例时行数变化不会让整体跳动 */
  min-height: 380px;
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  background: var(--surface-alt);
  overflow: hidden;
}
.editor:focus-within { border-color: var(--accent); }
/* CodeMirror 挂进来后由它自己撑满，这里只负责外框 */
.editor :deep(.cm-editor) { height: 100%; }
.editor :deep(.cm-editor.cm-focused) { outline: none; }
.editor :deep(.cm-content) { font-family: var(--font-mono); }

.editor-ta {
  width: 100%; min-height: 320px; padding: 8px 10px; margin-top: 6px;
  border: 1px solid var(--border); border-radius: var(--r-sm);
  background: var(--surface-alt); color: var(--text);
  font-size: 12.5px; line-height: 1.6;
  outline: none; resize: vertical;
}
.editor-ta:focus { border-color: var(--accent); }

.editor-loading {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-subtle); font-size: 12.5px;
  background: var(--surface-alt);
  border-radius: var(--r-sm);
}
.editor-warn {
  margin-top: 6px; font-size: 11.5px; color: var(--danger);
  background: var(--danger-soft); border-radius: var(--r-sm); padding: 6px 8px;
}
</style>
