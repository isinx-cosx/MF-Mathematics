<script setup>
/**
 * MathKeypad — 数学键盘面板（替代 v1 `MF_UI/math_keyboard.py`）
 *
 * 保留的部分：6 个分类的名称与顺序、126 个键面文字、面板默认隐藏、
 * 由左下角"键盘"按钮切换（按钮文字 `键盘` ↔ `▼ 收起`）、
 * 键位不可聚焦（`tabindex="-1"` + mousedown.prevent，否则点按钮会抢走输入焦点）。
 *
 * 修掉/新增的部分：
 *   · 插入 LaTeX 而非 Unicode（见 lib/math/keypadSymbols.js 的说明）；
 *   · 占位符改用 MathLive 的 `#0 / #?`，插入后光标就位，不再插出 `\frac{}{}`；
 *   · 矩阵模板补 `\end`；
 *   · 找不到插入目标时**明确提示**，不再静默忽略（v1 只在焦点是 QLineEdit 时生效）；
 *   · 新增：符号搜索（按键面/LaTeX/中文关键词）、最近使用、收藏；
 *   · 分类页签与面板显隐记忆到 localStorage（v1 每次回到"基础运算"）。
 */
import { computed, onMounted, ref, watch } from "vue";
import { CATEGORIES, ALL_KEYS, searchKeys, DEFAULT_RECENT } from "../../lib/math/keypadSymbols.js";
import { insertLatex, activeField } from "../../lib/math/activeField.js";
import KeyFace from "./KeyFace.vue";

const activeCat = ref("basic");
const query = ref("");
const view = ref("keys");          // keys | recent | fav
const recent = ref([]);
const fav = ref([]);
const hint = ref("");
let hintTimer = 0;

const K_TAB = "mf_kb_tab";
const K_RECENT = "mf_kb_recent";
const K_FAV = "mf_kb_fav";

function load() {
  try {
    const t = localStorage.getItem(K_TAB);
    if (t && CATEGORIES.some((c) => c.id === t)) activeCat.value = t;
    const r = JSON.parse(localStorage.getItem(K_RECENT) || "[]");
    if (Array.isArray(r)) recent.value = r.filter((x) => typeof x === "string").slice(0, 12);
    const f = JSON.parse(localStorage.getItem(K_FAV) || "[]");
    if (Array.isArray(f)) fav.value = f.filter((x) => typeof x === "string");
  } catch { /* 读不到就用默认值，不影响功能 */ }
}
function persist() {
  try {
    localStorage.setItem(K_TAB, activeCat.value);
    localStorage.setItem(K_RECENT, JSON.stringify(recent.value));
    localStorage.setItem(K_FAV, JSON.stringify(fav.value));
  } catch { /* 配额/隐私模式：界面功能不因此中断 */ }
}
onMounted(load);
watch([activeCat, recent, fav], persist, { deep: true });

const current = computed(() => CATEGORIES.find((c) => c.id === activeCat.value) || CATEGORIES[0]);
const results = computed(() => (query.value.trim() ? searchKeys(query.value) : []));
const recentKeys = computed(() => {
  const list = recent.value.length ? recent.value : DEFAULT_RECENT;
  return list
    .map((latex) => ALL_KEYS.find((k) => k.latex === latex))
    .filter(Boolean);
});
const favKeys = computed(() => fav.value.map((latex) => ALL_KEYS.find((k) => k.latex === latex)).filter(Boolean));

function flash(msg) {
  hint.value = msg;
  clearTimeout(hintTimer);
  hintTimer = setTimeout(() => { hint.value = ""; }, 2600);
}

/**
 * 键面渲染交给 KeyFace：模板类键的键面本身是 LaTeX（`\frac{▢}{▢}`、`\begin{pmatrix}`），
 * 必须排版后才能看；其余键面是 Unicode/函数名，保持纯文本。
 * （这里以前是 `faceOf(k) { return k.label }`，直接把 LaTeX 源码当文字画出来。）
 */

function onKey(k) {
  const ok = insertLatex(k.latex, { selectionMode: "placeholder" });
  if (!ok) {
    flash("先点一下要输入的输入框，再点符号");
    return;
  }
  recent.value = [k.latex, ...recent.value.filter((x) => x !== k.latex)].slice(0, 12);
}

function toggleFav(k, e) {
  e?.stopPropagation?.();
  fav.value = fav.value.includes(k.latex)
    ? fav.value.filter((x) => x !== k.latex)
    : [k.latex, ...fav.value];
}

defineExpose({ activeCat, query, view });
</script>

<template>
  <section class="keypad" data-tour="math_keyboard.panel" aria-label="数学键盘">
    <header class="kp-head" data-tour="math_keyboard.titlebar">
      <span class="kp-title">⌨ 数学键盘</span>

      <div class="kp-tabs" role="tablist">
        <button v-for="c in CATEGORIES" :key="c.id" class="kp-tab" role="tab"
                :class="{ on: activeCat === c.id && view === 'keys' }"
                :aria-selected="activeCat === c.id && view === 'keys'"
                @click="view = 'keys'; activeCat = c.id">{{ c.name }}</button>
      </div>

      <div class="kp-tools">
        <button class="kp-mini" :class="{ on: view === 'recent' }" title="最近使用" @click="view = view === 'recent' ? 'keys' : 'recent'">最近</button>
        <button class="kp-mini" :class="{ on: view === 'fav' }" title="收藏" @click="view = view === 'fav' ? 'keys' : 'fav'">★ 收藏</button>
        <input v-model="query" class="kp-search" type="search" placeholder="搜索符号（如 积分 / sqrt / alpha）" />
      </div>
    </header>

    <p v-if="hint" class="kp-hint">{{ hint }}</p>
    <p v-else-if="!activeField()" class="kp-hint quiet">
      未选中输入框 —— 点一下计算或绘图里的输入格，再点符号即可插入
    </p>

    <div class="kp-body">
      <!-- 搜索结果 -->
      <div v-if="query.trim()" class="kp-grid">
        <button v-for="k in results" :key="k.cat + k.latex" class="kp-key" tabindex="-1"
                :title="k.catName + ' · ' + k.latex" @mousedown.prevent @click="onKey(k)">
          <KeyFace class="k-face" :label="k.label" />
          <span class="k-star" :class="{ on: fav.includes(k.latex) }" @click="toggleFav(k, $event)">★</span>
        </button>
        <p v-if="!results.length" class="kp-empty">没有匹配的符号</p>
      </div>

      <!-- 最近使用 / 收藏 -->
      <div v-else-if="view === 'recent' || view === 'fav'" class="kp-grid">
        <button v-for="k in (view === 'fav' ? favKeys : recentKeys)" :key="view + k.latex" class="kp-key"
                tabindex="-1" :title="k.catName + ' · ' + k.latex" @mousedown.prevent @click="onKey(k)">
          <KeyFace class="k-face" :label="k.label" />
          <span class="k-star" :class="{ on: fav.includes(k.latex) }" @click="toggleFav(k, $event)">★</span>
        </button>
        <p v-if="!(view === 'fav' ? favKeys : recentKeys).length" class="kp-empty">
          {{ view === "fav" ? "还没有收藏。点键位右上角的 ★ 即可收藏。" : "还没有使用记录。" }}
        </p>
      </div>

      <!-- 分类键区 -->
      <div v-else class="kp-rows">
        <div v-for="(row, ri) in current.rows" :key="ri" class="kp-row">
          <button v-for="k in row" :key="String(k[0] ?? k)" class="kp-key" tabindex="-1"
                  :title="(typeof k === 'string' ? k : k[2] ? k[2] + ' · ' + k[1] : k[1])"
                  @mousedown.prevent @click="onKey(typeof k === 'string' ? { label: k, latex: k, catName: current.name } : { label: k[0], latex: k[1], catName: current.name })">
            <KeyFace class="k-face" :label="typeof k === 'string' ? k : k[0]" />
            <span class="k-star"
                  :class="{ on: fav.includes(typeof k === 'string' ? k : k[1]) }"
                  @click="toggleFav({ latex: typeof k === 'string' ? k : k[1] }, $event)">★</span>
          </button>
        </div>
        <p class="kp-note">
          共 {{ CATEGORIES.reduce((n, c) => n + c.rows.reduce((m, r) => m + r.length, 0), 0) }} 键 ·
          模板类键面按数学排版显示 · 插入的是 LaTeX
        </p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.keypad {
  border-top: 1px solid var(--border);
  background: var(--surface);
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
.kp-head {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 10px; flex-wrap: wrap;
  border-bottom: 1px solid var(--border);
  background: var(--surface-alt);
}
.kp-title { font-size: 12px; font-weight: 600; color: var(--text); white-space: nowrap; }
.kp-tabs { display: flex; gap: 4px; flex-wrap: wrap; }
.kp-tab {
  font: inherit; font-size: 12px; padding: 3px 9px; cursor: pointer;
  border: 1px solid var(--border); border-radius: 999px;
  background: var(--surface); color: var(--text-subtle, #475569);
}
.kp-tab.on { background: var(--accent); border-color: var(--accent); color: #fff; }
.kp-tools { margin-left: auto; display: flex; align-items: center; gap: 6px; }
.kp-mini {
  font: inherit; font-size: 12px; padding: 3px 8px; cursor: pointer;
  border: 1px solid var(--border); border-radius: var(--r-sm, 6px);
  background: var(--surface); color: var(--text-subtle, #475569);
}
.kp-mini.on { border-color: var(--accent); color: var(--accent); }
.kp-search {
  font: inherit; font-size: 12px; padding: 4px 8px; width: 210px;
  border: 1px solid var(--border); border-radius: var(--r-sm, 6px);
  background: var(--surface); color: var(--text);
}
.kp-hint {
  margin: 6px 10px 0; padding: 5px 9px; font-size: 12px; border-radius: 6px;
  background: color-mix(in srgb, #f59e0b 16%, transparent);
  border: 1px solid color-mix(in srgb, #f59e0b 42%, transparent);
}
.kp-hint.quiet {
  background: transparent; border-color: transparent;
  color: var(--text-subtle, #94a3b8); padding: 4px 10px;
}
.kp-body { padding: 8px 10px 10px; overflow: auto; }
.kp-rows { display: flex; flex-direction: column; gap: 6px; }
.kp-row { display: flex; gap: 6px; flex-wrap: wrap; }
.kp-grid { display: flex; gap: 6px; flex-wrap: wrap; }
.kp-key {
  position: relative;
  font: inherit; font-size: 13px; min-width: 40px; height: 30px; padding: 0 8px;
  cursor: pointer; border: 1px solid var(--border); border-radius: var(--r-sm, 6px);
  background: var(--surface-alt); color: var(--text);
  /* 键面可能是排版后的数学（分数/根式比文字高），居中并允许它在格内收缩 */
  display: inline-flex; align-items: center; justify-content: center;
}
.kp-key:hover { border-color: var(--accent); }
.kp-key:active { background: var(--accent-soft, #e0ecff); }
.k-face { pointer-events: none; }
/* KaTeX 默认按正文大小排版，在 30px 的键格里偏高；略缩小并压紧行高，保证分数/根式完整可见。
   这里直接选 .katex 而不依赖 class 落在哪一层，避免属性透传的细节影响布局。 */
.kp-key :deep(.katex) { font-size: 0.88em; line-height: 1; }
.k-star {
  position: absolute; top: -2px; right: 0; font-size: 10px; line-height: 1;
  color: transparent; cursor: pointer;
}
.kp-key:hover .k-star { color: var(--text-subtle, #cbd5e1); }
.k-star.on, .kp-key:hover .k-star.on { color: #f59e0b; }
.kp-note { margin: 8px 0 0; font-size: 11px; color: var(--text-subtle, #94a3b8); }
.kp-empty { margin: 6px 0; font-size: 12px; color: var(--text-subtle, #94a3b8); }
</style>
