<script setup>
/**
 * HistoryDialog — 计算历史（对应 v1 的 dialogs/history_dialog.py）
 *
 * v1 的历史只记表达式、点击"回退到该表达式"；这里把**结果摘要**也带上，
 * 因为用户回忆"我上次算的是哪一条"时，认的是结果而不是表达式。
 *
 * 三件事与 v1 不同（都是踩过的坑）：
 *   ① 跨会话保留，且落在 `%LOCALAPPDATA%\MFMath\settings\history.json`（宿主原子写），
 *      不写安装目录 —— v1 的工作区就写在安装目录里，重装即丢；
 *   ② 失败的计算也记（标红），因为"上次那条报错的是什么"同样是要回看的信息；
 *   ③ 回填走 pendingInput 的**已验证通路**（示例库同一条），不直接抓控件 setText
 *      —— v1 那种做法在模式匹配不上时会静默丢失语义。
 */
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useHistory, MAX } from "../../lib/history/store.js";
import { setPending } from "../../lib/workspace/pendingInput.js";

const emit = defineEmits(["close"]);
const router = useRouter();
const { entries, error, removeEntry, clearAll, listByRoute, searchEntries, reload } = useHistory();

const query = ref("");
const confirmClear = ref(false);

const filtered = computed(() => searchEntries(query.value, entries.value));

function fmtTime(ts) {
  const d = new Date(ts);
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** 点一条 → 回到它原来的页面并填入表达式。 */
function restore(e) {
  setPending({ expr: e.expr, mode: e.mode, operation: e.mode, label: e.expr });
  const route = e.route || "/calc/algebra";
  router.push(route);
  emit("close");
}

function doClear() {
  clearAll();
  confirmClear.value = false;
}

function onKeydown(ev) {
  if (ev.key === "Escape") { ev.preventDefault(); emit("close"); }
}
onMounted(() => { reload(); window.addEventListener("keydown", onKeydown); });
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));

// 基础运算页把自己那一页的历史单独清（它页面里也有个"清空"按钮，语义是"清我这页"）
const basicCount = computed(() => listByRoute("/calc/basic").length);
</script>

<template>
  <div class="dialog-overlay">
    <div class="dialog hist-dialog">
      <div class="dialog-header">
        <span>计算历史 — 共 {{ entries.length }} 条（最多保留 {{ MAX }} 条）</span>
        <button class="dialog-close" @click="emit('close')">✕</button>
      </div>

      <div class="dialog-body">
        <div class="hist-toolbar">
          <input
            v-model="query"
            class="hist-search"
            type="search"
            placeholder="搜索表达式 / 结果 / 模式"
            aria-label="搜索历史"
          >
          <span class="hist-count">{{ filtered.length }} / {{ entries.length }}</span>
        </div>

        <p v-if="error" class="hist-error">{{ error }}</p>

        <p v-if="!entries.length" class="hist-empty">
          还没有历史记录。在计算页算一次，就会出现在这里；关掉应用也不会丢。
        </p>
        <p v-else-if="!filtered.length" class="hist-empty">没有匹配「{{ query }}」的记录。</p>

        <ul v-else class="hist-list">
          <li v-for="e in filtered" :key="e.id" class="hist-row" :class="{ bad: !e.ok }">
            <button class="hist-main" :title="`回到 ${e.route} 并填入这条表达式`" @click="restore(e)">
              <span class="hist-time">{{ fmtTime(e.ts) }}</span>
              <span class="hist-mode">{{ e.mode || "—" }}</span>
              <span class="hist-expr">{{ e.expr || "（无表达式）" }}</span>
              <span class="hist-sum">{{ e.ok ? (e.summary || "（无结果摘要）") : ("失败：" + e.summary) }}</span>
            </button>
            <button class="hist-del" title="删除这一条" @click="removeEntry(e.id)">✕</button>
          </li>
        </ul>
      </div>

      <div class="dialog-footer">
        <span class="hist-foot-note">
          点击一条即可回到原页面并填入表达式{{ basicCount ? `（其中基础运算 ${basicCount} 条）` : "" }}
        </span>
        <button v-if="!confirmClear" class="btn btn-ghost" :disabled="!entries.length" @click="confirmClear = true">
          清空全部
        </button>
        <template v-else>
          <span class="hist-warn">确定清空 {{ entries.length }} 条？</span>
          <button class="btn btn-danger" @click="doClear">确定清空</button>
          <button class="btn btn-ghost" @click="confirmClear = false">取消</button>
        </template>
        <button class="btn btn-primary" @click="emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hist-dialog { width: min(760px, 92vw); max-height: 82vh; display: flex; flex-direction: column; }
.dialog-body { overflow: auto; }

.hist-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.hist-search {
  flex: 1; min-width: 0; padding: 6px 10px;
  border: 1px solid var(--border); border-radius: var(--r-sm);
  background: var(--surface-alt); color: var(--text); font: inherit;
}
.hist-search:focus { outline: none; border-color: var(--accent); }
.hist-count { font-size: 12px; color: var(--text-subtle); white-space: nowrap; }

.hist-error {
  margin: 0 0 8px; padding: 6px 10px; border-radius: var(--r-sm);
  background: var(--danger-soft, #fee2e2); color: var(--danger, #b91c1c); font-size: 12px;
}
.hist-empty { margin: 18px 0; color: var(--text-subtle); font-size: 13px; text-align: center; }

.hist-list { list-style: none; margin: 0; padding: 0; }
.hist-row { display: flex; align-items: stretch; gap: 6px; border-top: 1px solid var(--border); }
.hist-row:first-child { border-top: none; }
.hist-row:hover { background: var(--surface-alt); }

.hist-main {
  flex: 1; min-width: 0; display: grid; grid-template-columns: 84px 130px minmax(120px, 1fr) minmax(0, 1.2fr);
  gap: 10px; align-items: baseline; padding: 7px 8px; text-align: left;
  background: none; border: none; color: inherit; font: inherit; cursor: pointer;
}
.hist-time { font-size: 12px; color: var(--text-subtle); font-variant-numeric: tabular-nums; }
.hist-mode {
  font-size: 12px; color: var(--text-subtle); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.hist-expr {
  font-family: ui-monospace, Consolas, monospace; font-size: 13px; color: var(--text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.hist-sum {
  font-size: 12px; color: var(--text-subtle);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.hist-row.bad .hist-sum { color: var(--danger, #b91c1c); }

.hist-del {
  flex: none; width: 28px; background: none; border: none; color: var(--text-subtle);
  cursor: pointer; border-radius: var(--r-sm);
}
.hist-del:hover { color: var(--danger, #b91c1c); background: var(--surface); }

.dialog-footer { display: flex; align-items: center; gap: 8px; }
.hist-foot-note { flex: 1; font-size: 12px; color: var(--text-subtle); text-align: left; }
.hist-warn { font-size: 12px; color: var(--danger, #b91c1c); }
</style>
