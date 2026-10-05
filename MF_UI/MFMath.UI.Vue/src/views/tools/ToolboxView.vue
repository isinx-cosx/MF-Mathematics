<script setup>
/**
 * ToolboxView — 函数工具箱：把**全部 424 个引擎 action** 列出来并可直接调用。
 *
 * 为什么要有这一页
 *   "计算页 / 绘图页"那一套是按**界面模式**组织的（lib/engine/engineMap.js，
 *   371 个 action）。剩下 38 个引擎早就算得出来，但界面上**没有任何入口** ——
 *   例如 matrix_multiply（矩阵乘法）、simplify_sym、taylor_series、
 *   cauchy_riemann / is_harmonic 那一批复分析判定。
 *   本页以 `lib/ai/engine-signatures.json` 为唯一数据源：它由引擎 handler 生成、
 *   与注册表逐字一致（424/424），含每个 action 的 params / required / optional。
 *   所以这里是**表驱动**的：引擎将来新增 action 会自动出现在列表里，
 *   不会再出现"引擎有、界面没有"的倒挂。
 *
 * 与 AI 工具表的关系
 *   AI 那边（lib/ai/tools.ts）用的是同一张表 —— 两边一致，不会各说各话。
 *
 * 数据流：表单 → args（跳过空的可选项）→ engineCall → 引擎信封 {isError,value} 原样展示。
 * 数值一律来自引擎，本页不做任何自己的计算。
 */
import { computed, ref } from "vue";
import SIGNATURES from "../../lib/ai/engine-signatures.json";
import { engineCall, isHosted } from "../../lib/bridge.js";
import { ENGINE_MAP } from "../../lib/engine/engineMap.js";
import { EXTRA_MAP } from "../../lib/engine/engineMapExtra.js";

const hosted = ref(isHosted());

/** 界面模式表已经覆盖到的 action —— 不在里面的就是"此前没有任何入口" */
const MAPPED = (() => {
  const s = new Set();
  for (const spec of Object.values(ENGINE_MAP || {})) if (spec && spec.fn) s.add(String(spec.fn));
  for (const spec of Object.values(EXTRA_MAP || {})) if (spec && spec.fn) s.add(String(spec.fn));
  return s;
})();

/** 由签名表的 file 反推模块名：algebra/algebra_api.cpp → algebra */
function moduleOf(file) {
  const top = String(file || "").split("/")[0].trim();
  if (!top) return "(未分组)";
  const stem = top.replace(/_api\.cpp$/, "");
  return /\.cpp$/i.test(stem) || !stem ? "(未分组)" : stem;
}

const CATALOG = Object.entries(SIGNATURES)
  .map(([fn, s]) => {
    const optional = new Set(s.optional || []);
    return {
      fn,
      module: moduleOf(s.file),
      params: Object.keys(s.params || {}).map((k) => ({
        key: k,
        type: String(s.params[k] || "string").replace(/^\?/, ""),
        required: !optional.has(k),
      })),
      // 是否出现在**界面模式表**（ENGINE_MAP ∪ EXTRA_MAP）里。
      // 不在里面 ≠ 完全没有入口（绘图/基础运算等页面会直接调几个，如 expr_eval*），
      // 所以文案只说"不在模式表" —— 不夸大成"绝对没有入口"。
      inModeTable: MAPPED.has(fn),
    };
  })
  .sort((a, b) => a.fn.localeCompare(b.fn));

/** 数值型参数：引擎按数字收（int 也在这里 —— 传字符串会被引擎的类型检查拒掉） */
const NUMERIC = new Set(["number", "int", "integer", "float", "double", "real"]);
/** 结构型参数：引擎按 JSON 值收（例如 matrix_multiply 要的是 [[1,2],[3,4]] 而不是它的字符串） */
const STRUCT = /^(matrix|array|object|list|vector|tuple|sets|data|pmf_data)$/i;

/** 给输入框一个能直接照抄的示例，省得用户猜格式 */
function placeholderOf(type) {
  if (NUMERIC.has(type)) return "数字";
  if (/^matrix$/i.test(type)) return "[[1,2],[3,4]]（JSON 数组）";
  if (STRUCT.test(type)) return "JSON，如 [1,2,3]";
  return "字符串（如 x^2+1）";
}

const MODULES = [...new Set(CATALOG.map((c) => c.module))].sort();

const query = ref("");
const onlyMissing = ref(false);
const picked = ref("");
const values = ref({});
const result = ref(null);
const lastMs = ref(0);

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase();
  return CATALOG.filter((c) => {
    if (onlyMissing.value && c.inModeTable) return false;
    if (!q) return true;
    if (c.fn.toLowerCase().includes(q)) return true;
    if (c.module.toLowerCase().includes(q)) return true;
    return c.params.some((p) => p.key.toLowerCase().includes(q));
  });
});

const current = computed(() => CATALOG.find((c) => c.fn === picked.value) || null);
const outsideCount = computed(() => CATALOG.filter((c) => !c.inModeTable).length);

function pick(fn) {
  picked.value = fn;
  result.value = null;
  const c = CATALOG.find((x) => x.fn === fn);
  const v = {};
  for (const p of c?.params || []) v[p.key] = "";
  values.value = v;
}

function call() {
  const c = current.value;
  if (!c) return;
  const args = {};
  for (const p of c.params) {
    const raw = String(values.value[p.key] ?? "").trim();
    if (raw === "") continue;                      // 空的可选项不发（引擎用自己的默认值）
    if (NUMERIC.has(p.type)) {
      args[p.key] = Number(raw);
    } else if (STRUCT.test(p.type)) {
      // 结构化参数要真值而不是它的字符串：matrix_multiply 传 "[[1,2]]" 会被引擎
      // 判成"缺少矩阵参数"（实测），传 [[1,2]] 才对。
      try { args[p.key] = JSON.parse(raw); } catch { args[p.key] = raw; }  // 解析失败就原样交出去，让引擎报准确原因
    } else {
      args[p.key] = raw;
    }
  }
  const t0 = performance.now();
  const res = engineCall(c.fn, args);
  lastMs.value = Math.round(performance.now() - t0);
  result.value = res === null
    ? { localError: "没有连上本地引擎（本页只在 MFMath.exe 里可用）" }
    : { isError: !!res.isError, value: res.value, args };
}

function reset() {
  result.value = null;
  for (const k of Object.keys(values.value)) values.value[k] = "";
}

/** 测试/排障钩子：CDP 里够不到模块作用域 */
try {
  window.__mfToolbox = {
    size: () => CATALOG.length,
    missing: () => CATALOG.filter((c) => !c.inModeTable).map((c) => c.fn),
    modules: () => MODULES,
    pick: (fn) => { pick(fn); return current.value?.fn ?? ""; },
    call: (fn, args) => { pick(fn); for (const [k, v] of Object.entries(args || {})) values.value[k] = String(v); call(); return result.value; },
  };
} catch { /* 忽略 */ }
</script>

<template>
  <div class="tb">
    <header class="tb-head">
      <div>
        <h2>函数工具箱</h2>
        <p class="tb-sub">
          引擎共有 <b>{{ CATALOG.length }}</b> 个可调用函数，本页全部列出。
          <span v-if="outsideCount">其中 <b>{{ outsideCount }}</b> 个不在界面模式表里（标了「不在模式表」）——
            这些正是最容易没有入口的，本页把它们一并列出并可直接调用。</span>
          <span v-else>界面模式已覆盖全部函数。</span>
        </p>
      </div>
      <p v-if="!hosted" class="tb-warn">浏览器预览：无引擎桥，本页只列出函数、不能调用。</p>
    </header>

    <div class="tb-bar">
      <input v-model="query" class="tb-input" data-toolbox="search" type="search"
             placeholder="按函数名 / 模块 / 参数名过滤，例如 matrix、taylor、expr" />
      <label class="tb-chk">
        <input v-model="onlyMissing" data-toolbox="missing" type="checkbox" />
        只看不在模式表里的（{{ outsideCount }}）
      </label>
      <span class="tb-count">{{ filtered.length }} / {{ CATALOG.length }}</span>
    </div>

    <div class="tb-body">
      <aside class="tb-list" data-toolbox="list">
        <button v-for="c in filtered" :key="c.fn" class="tb-item" :class="{ on: c.fn === picked }"
                :data-fn="c.fn" @click="pick(c.fn)">
          <span class="tb-fn">{{ c.fn }}</span>
          <span class="tb-mod">{{ c.module }}</span>
          <span v-if="!c.inModeTable" class="tb-badge">不在模式表</span>
        </button>
        <p v-if="!filtered.length" class="tb-empty">没有匹配的函数。</p>
      </aside>

      <section class="tb-call">
        <template v-if="current">
          <h3 class="tb-title">{{ current.fn }}</h3>
          <p class="tb-meta">模块 {{ current.module }} · {{ current.params.length }} 个参数
            <span v-if="!current.inModeTable"> · <b>不在界面模式表里</b></span>
          </p>

          <p v-if="!current.params.length" class="tb-hint">该函数没有参数，直接调用即可。</p>
          <div v-else class="tb-form">
            <label v-for="p in current.params" :key="p.key" class="tb-field">
              <span class="tb-label">
                {{ p.key }}
                <em v-if="p.required">必填</em><em v-else>可选</em>
                <small>{{ p.type }}</small>
              </span>
              <input v-model="values[p.key]" class="tb-inp" :data-arg="p.key"
                     :type="NUMERIC.has(p.type) ? 'number' : 'text'"
                     :placeholder="placeholderOf(p.type)" />
            </label>
          </div>

          <div class="tb-actions">
            <button class="btn btn-primary" data-toolbox="call" :disabled="!hosted" @click="call">调用引擎</button>
            <button class="btn btn-ghost" data-toolbox="reset" @click="reset">清空</button>
            <span v-if="result" class="tb-ms">{{ lastMs }} ms</span>
          </div>

          <div v-if="result" class="tb-result" :class="{ bad: result.isError || result.localError }" data-toolbox="result">
            <p class="tb-rhead">
              <template v-if="result.localError">{{ result.localError }}</template>
              <template v-else-if="result.isError">引擎返回错误（这是引擎自己的判定，本页不做解读）</template>
              <template v-else>结果</template>
            </p>
            <pre class="tb-pre">{{ result.localError ? "" : JSON.stringify(result.value, null, 2) }}</pre>
          </div>
        </template>
        <p v-else class="tb-empty">左侧选一个函数。</p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.tb { display: flex; flex-direction: column; height: 100%; min-height: 0; padding: 14px 16px; gap: 10px; }
.tb-head h2 { margin: 0 0 4px; font-size: 16px; }
.tb-sub { margin: 0; font-size: 12px; color: var(--text-dim, #8a8f98); }
.tb-warn { margin: 6px 0 0; font-size: 12px; color: #b45309; }
.tb-bar { display: flex; align-items: center; gap: 10px; }
.tb-input { flex: 1 1 auto; min-width: 0; padding: 7px 10px; border-radius: 8px;
  border: 1px solid var(--border, #d8dbe0); background: var(--bg-elev, #fff); color: var(--text, #222); }
.tb-chk { font-size: 12px; color: var(--text-dim, #8a8f98); white-space: nowrap; display: flex; gap: 5px; align-items: center; }
.tb-count { font-size: 12px; color: var(--text-dim, #8a8f98); white-space: nowrap; }
.tb-body { flex: 1 1 auto; min-height: 0; display: grid; grid-template-columns: minmax(220px, 300px) 1fr; gap: 12px; }
.tb-list { overflow: auto; border: 1px solid var(--border, #d8dbe0); border-radius: 10px; padding: 6px; }
.tb-item { display: flex; align-items: center; gap: 6px; width: 100%; text-align: left; padding: 5px 7px;
  border: 0; border-radius: 7px; background: transparent; color: var(--text, #222); cursor: pointer; font-size: 12.5px; }
.tb-item:hover { background: var(--bg-hover, rgba(0,0,0,.05)); }
.tb-item.on { background: var(--accent-soft, rgba(90,130,240,.14)); }
.tb-fn { font-family: ui-monospace, Consolas, monospace; }
.tb-mod { margin-left: auto; font-size: 11px; color: var(--text-dim, #8a8f98); }
.tb-badge { font-size: 10.5px; padding: 0 5px; border-radius: 6px; color: #b45309; background: rgba(180,83,9,.12); }
.tb-call { overflow: auto; border: 1px solid var(--border, #d8dbe0); border-radius: 10px; padding: 12px; }
.tb-title { margin: 0; font-family: ui-monospace, Consolas, monospace; font-size: 14px; }
.tb-meta { margin: 4px 0 10px; font-size: 12px; color: var(--text-dim, #8a8f98); }
.tb-hint { font-size: 12px; color: var(--text-dim, #8a8f98); }
.tb-form { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; }
.tb-field { display: flex; flex-direction: column; gap: 3px; }
.tb-label { font-size: 11.5px; color: var(--text-dim, #8a8f98); display: flex; align-items: center; gap: 5px; }
.tb-label em { font-style: normal; font-size: 10.5px; color: var(--accent, #5a82f0); }
.tb-label small { margin-left: auto; opacity: .75; }
.tb-inp { padding: 6px 8px; border-radius: 7px; border: 1px solid var(--border, #d8dbe0);
  background: var(--bg-elev, #fff); color: var(--text, #222); font-size: 12.5px; }
.tb-actions { display: flex; align-items: center; gap: 8px; margin-top: 12px; }
.tb-ms { font-size: 11.5px; color: var(--text-dim, #8a8f98); }
.tb-result { margin-top: 12px; border-top: 1px solid var(--border, #d8dbe0); padding-top: 10px; }
.tb-rhead { margin: 0 0 6px; font-size: 12px; color: var(--text-dim, #8a8f98); }
.tb-result.bad .tb-rhead { color: #b45309; }
.tb-pre { margin: 0; max-height: 46vh; overflow: auto; padding: 9px; border-radius: 8px;
  background: var(--bg-code, rgba(0,0,0,.05)); font-size: 12px; white-space: pre-wrap; word-break: break-word; }
.tb-empty { font-size: 12.5px; color: var(--text-dim, #8a8f98); }
</style>
