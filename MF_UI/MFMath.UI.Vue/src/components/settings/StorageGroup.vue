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
import { info, storeList, openPath, exportDiagnostics, isSettingsHosted } from "../../lib/settings/bridge.js";
import { progress, resetAllProgress, storageError } from "../../lib/tutorial/store.js";

const hostInfo = ref(info());
const files = ref([]);
const msg = ref("");
const confirmingReset = ref(false);
const diagPath = ref("");

onMounted(() => {
  files.value = storeList();
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
      <div class="s-label"><label>历史记录</label><p class="s-hint">条数 / 清空 / 导出</p></div>
      <div class="s-ctl"><span class="pending-tag">待实现 · 依赖 P1（历史与设置存储桥）</span></div>
    </div>
    <div class="s-row" data-setting="storage.workspace">
      <div class="s-label"><label>工作区</label><p class="s-hint">保存 / 恢复 / 清空</p></div>
      <div class="s-ctl"><span class="pending-tag">待实现 · 依赖 P1（同上，v1 的实现在安装目录里且字段残缺）</span></div>
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
