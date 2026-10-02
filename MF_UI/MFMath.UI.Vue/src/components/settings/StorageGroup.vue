<script setup>
/**
 * 设置 · 存储与数据分组
 *
 * 这一组的价值是"出事时能自助"：数据在哪、有哪些设置文件、教程进度怎么重置、
 * 一键导出诊断包。危险操作（重置进度、清理）都要**二次确认**，
 * 且宿主侧写文件是原子替换、解析失败保留原文件（见 SettingsBridge.cs）。
 *
 * 依赖说明：历史记录与工作区管理依赖 P1（`StoreBridge`），导入/导出设置依赖文件对话框，
 * 这三项在界面上以"待实现"列出，不隐藏（让用户知道功能存在但还没做）。
 */
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { info, storeList, openPath, exportDiagnostics, isSettingsHosted } from "../../lib/settings/bridge.js";
import { progress, resetAllProgress, storageError } from "../../lib/tutorial/store.js";
import { useHistory } from "../../lib/history/store.js";
import { useWorkspace } from "../../lib/workspace/store.js";

const hostInfo = ref(info());
const files = ref([]);
const msg = ref("");
const confirmingReset = ref(false);
const confirmingHistory = ref(false);
const confirmingWs = ref(false);
const diagPath = ref("");

/* 历史记录：条数与清空放这儿，用户不必跑到顶栏去清 */
const { entries: historyEntries, clearAll: clearHistoryAll, reload: reloadHistory } = useHistory();

/* 工作区：保存 / 载入 / 另存为 / 从文件打开 / 清空 */
const route = useRoute();
const router = useRouter();
const wsApi = useWorkspace();
const ws = computed(() => wsApi.summary());
function wsSaveApp() {
  const r = wsApi.saveToApp(route.path);
  msg.value = r.ok
    ? `工作区已保存（${ws.value.pages} 个页面：${ws.value.routes.join("、") || "—"}）`
    : `保存失败：${r.error}`;
  refreshFiles();
}
function wsLoadApp() {
  const r = wsApi.loadFromApp();
  if (!r.ok) { msg.value = `载入失败：${r.error}`; return; }
  msg.value = `已载入 ${r.pages} 个页面${r.route ? "，正在跳回 " + r.route : ""}；页面内容会在切换到该页时还原`;
  if (r.route) router.push(r.route);
}
function wsSaveFile() {
  const r = wsApi.saveToFile(route.path);
  if (r.canceled) { msg.value = "已取消另存为"; return; }
  msg.value = r.ok ? `已另存为：${r.path}` : `另存为失败：${r.error}`;
}
function wsLoadFile() {
  const r = wsApi.loadFromFile();
  if (r.canceled) { msg.value = "已取消打开"; return; }
  if (!r.ok) { msg.value = `打开失败：${r.error}`; return; }
  msg.value = `已从文件载入 ${r.pages} 个页面${r.route ? "，正在跳回 " + r.route : ""}`;
  if (r.route) router.push(r.route);
}
function wsClear() {
  wsApi.clearAll();
  confirmingWs.value = false;
  msg.value = "工作区已清空（下次保存会覆盖磁盘上的那份）";
}
function fmtTime(ts) {
  const d = new Date(ts);
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

function doClearHistory() {
  clearHistoryAll();
  confirmingHistory.value = false;
  refreshFiles();
  msg.value = "历史记录已清空";
}

onMounted(() => {
  files.value = storeList();
  reloadHistory();
});

const bytes = computed(() => files.value.reduce((n, f) => n + (f.bytes || 0), 0));

function openData() {
  const r = openPath(hostInfo.value.dataDir || "");
  msg.value = r?.ok ? "" : (r?.error || "打开失败");
}
function doReset() {
  resetAllProgress();
  confirmingReset.value = false;
  msg.value = "教程进度已重置（已学标记与引导步数都清空了）";
}
function doExport() {
  const r = exportDiagnostics();
  if (!r?.ok) { msg.value = r?.error || "导出失败"; return; }
  diagPath.value = r.path;
  msg.value = "诊断包已导出";
}
function openDiag() {
  const r = openPath(diagPath.value);
  msg.value = r?.ok ? "" : (r?.error || "打开失败");
}
function refreshFiles() {
  files.value = storeList();
  msg.value = `已刷新：${files.value.length} 个设置文件`;
}
</script>

<template>
  <section>
    <p v-if="!isSettingsHosted()" class="s-warn">
      浏览器预览模式：设置读写降级到 localStorage（不落文件），导出诊断包不可用。
    </p>

    <div class="s-row" data-setting="storage.dir">
      <div class="s-label">
        <label>数据目录</label>
        <p class="s-hint mono">{{ hostInfo.dataDir }}</p>
      </div>
      <div class="s-ctl">
        <button class="s-btn" :disabled="!isSettingsHosted()" @click="openData">打开目录</button>
      </div>
    </div>

    <div class="s-row" data-setting="storage.tutorial">
      <div class="s-label">
        <label>教程进度</label>
        <p class="s-hint">
          已学 {{ progress.done }} / {{ progress.total }} 篇 · {{ progress.percent }}%
          <span v-if="storageError">（注意：{{ storageError }}）</span>
        </p>
      </div>
      <div class="s-ctl">
        <template v-if="!confirmingReset">
          <button class="s-btn danger" @click="confirmingReset = true">重置进度</button>
        </template>
        <template v-else>
          <span class="s-hint">确定重置？</span>
          <button class="s-btn danger" @click="doReset">确定</button>
          <button class="s-btn" @click="confirmingReset = false">取消</button>
        </template>
      </div>
    </div>

    <div class="s-row col" data-setting="storage.settings">
      <div class="s-label">
        <label>设置文件</label>
        <p class="s-hint">
          {{ files.length }} 个 · 共 {{ (bytes / 1024).toFixed(1) }} KB
          <span v-if="!isSettingsHosted()">（浏览器预览时从 localStorage 读取）</span>
        </p>
      </div>
      <div class="s-ctl wrap">
        <table class="file-table">
          <tbody>
            <tr v-for="f in files" :key="f.name">
              <td class="mono">{{ f.name }}.json</td>
              <td class="num">{{ (f.bytes / 1024).toFixed(1) }} KB</td>
              <td class="num">{{ f.mtime }}</td>
            </tr>
            <tr v-if="!files.length"><td colspan="3" class="s-hint">还没有任何设置文件（改一次设置就会生成）</td></tr>
          </tbody>
        </table>
        <button class="s-btn" @click="refreshFiles">刷新</button>
      </div>
    </div>

    <div class="s-row" data-setting="storage.diagnostics">
      <div class="s-label">
        <label>导出诊断包</label>
        <p class="s-hint">版本、路径、引擎产物清单、设置内容（**不含密钥文件**），发给支持时用</p>
      </div>
      <div class="s-ctl">
        <button class="s-btn primary" :disabled="!isSettingsHosted()" @click="doExport">导出</button>
        <button v-if="diagPath" class="s-btn" @click="openDiag">打开所在目录</button>
      </div>
    </div>

    <div class="s-row" data-setting="storage.history">
      <div class="s-label">
        <label>历史记录</label>
        <p class="s-hint">
          当前 {{ historyEntries.length }} 条（最多保留 200 条），存在数据目录的
          <code>settings\history.json</code>，顶层「历史」按钮里可以逐条回看与回填
        </p>
      </div>
      <div class="s-ctl">
        <template v-if="!confirmingHistory">
          <button class="s-btn danger" :disabled="!historyEntries.length" @click="confirmingHistory = true">清空</button>
        </template>
        <template v-else>
          <span class="s-hint">确定清空 {{ historyEntries.length }} 条？</span>
          <button class="s-btn danger" @click="doClearHistory">确定</button>
          <button class="s-btn" @click="confirmingHistory = false">取消</button>
        </template>
      </div>
    </div>
    <div class="s-row" data-setting="storage.workspace">
      <div class="s-label">
        <label>工作区</label>
        <p class="s-hint">
          计算块 / 绘图表达式与视野 / 控制台代码，全部可存可还原。
          当前 <b>{{ ws.pages }}</b> 个页面（{{ ws.blocks }} 个计算块、{{ ws.curves }} 条曲线）<template
            v-if="ws.savedAt">，上次保存 {{ fmtTime(ws.savedAt) }}</template><template
            v-if="ws.dirty"> · <b>有未保存的改动</b></template>
        </p>
        <p v-if="ws.savedPath" class="s-hint">上次另存为：<code>{{ ws.savedPath }}</code></p>
      </div>
      <div class="s-ctl wrap">
        <button class="s-btn primary" @click="wsSaveApp">保存</button>
        <button class="s-btn" @click="wsLoadApp">载入</button>
        <button class="s-btn" :disabled="!isSettingsHosted()" @click="wsSaveFile">另存为文件…</button>
        <button class="s-btn" :disabled="!isSettingsHosted()" @click="wsLoadFile">从文件打开…</button>
        <template v-if="!confirmingWs">
          <button class="s-btn danger" :disabled="!ws.pages" @click="confirmingWs = true">清空</button>
        </template>
        <template v-else>
          <span class="s-hint">确定清空？</span>
          <button class="s-btn danger" @click="wsClear">确定</button>
          <button class="s-btn" @click="confirmingWs = false">取消</button>
        </template>
      </div>
    </div>
    <div class="s-row" data-setting="storage.io">
      <div class="s-label"><label>导入 / 导出设置</label><p class="s-hint">换机迁移用</p></div>
      <div class="s-ctl"><span class="pending-tag">待实现 · 需要文件对话框（宿主侧）</span></div>
    </div>

    <p v-if="msg" class="s-warn">{{ msg }}</p>
  </section>
</template>

<style scoped>
.file-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 6px; }
.file-table td { padding: 3px 8px 3px 0; border-bottom: 1px solid var(--border); }
.file-table .num { text-align: right; color: var(--text-subtle, #64748b); white-space: nowrap; }
.pending-tag {
  font-size: 11.5px; padding: 2px 8px; border-radius: 999px;
  border: 1px dashed var(--border); color: var(--text-subtle, #94a3b8);
}
.s-btn.danger { border-color: color-mix(in srgb, #ef4444 45%, var(--border)); color: #ef4444; }
</style>
