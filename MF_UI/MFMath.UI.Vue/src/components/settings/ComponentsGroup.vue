<script setup>
/**
 * 设置 · 组件分组
 *
 * 复用宿主 `con` 桥已有的能力（`ConsoleBridge`）：语言运行时是**可选下载**的，
 * 断点续传 + SHA-256 校验 + 解压 + 进度回调都已经在那边实现好了，这里只是把
 * 状态与按钮搬进设置面板（v1 里这些只在控制台内部可见，用户在设置里找不到）。
 *
 * 进度获取：宿主目前只有"开始 + 轮询"（`Install` 返回 jobId，再 `InstallStatus` 轮询）。
 * 方案里的推送通道做完后，这里可以改成推式，届时只是替换获取方式，界面不变。
 */
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  components, installComponent, installStatus, cancelInstall, setDownloadBase,
  uninstallComponent, isConsoleHosted,
} from "../../lib/console/bridge.js";
import { openPath } from "../../lib/settings/bridge.js";

const state = ref(null);
const job = ref(null);        // { id, name, pct, message, state }
const baseInput = ref("");
const msg = ref("");
let timer = 0;

const KINDS = [
  { id: "python", label: "CPython 组件", desc: "控制台里跑 Python 代码的运行时（引擎调用经 mfmath.py → 同一个 C++ DLL）" },
  { id: "cpp", label: "MinGW 组件", desc: "控制台里编译运行 C++ 的编译器（g++）" },
];

function refresh() {
  const c = components();
  state.value = c;
  if (!baseInput.value && c && c.engineDir) {
    // 下载源由宿主决定（默认站点 + __MF_COMPONENT_BASE 覆盖），这里只回显
    baseInput.value = "";
  }
}

const root = computed(() => state.value?.componentsRoot || "");
const entryOf = (id) => state.value?.[id] || null;

function pctOf(st) {
  if (!st) return 0;
  if (typeof st.percent === "number") return st.percent;
  if (st.total > 0 && st.done >= 0) return Math.min(100, Math.round((st.done / st.total) * 100));
  return 0;
}

function poll() {
  if (!job.value) return;
  const st = installStatus(job.value.id);
  if (!st) return;
  job.value = { ...job.value, pct: pctOf(st), message: st.message || "", state: st.state || "" };
  if (["done", "error"].includes(job.value.state)) {
    const finished = job.value;
    job.value = null;
    refresh();
    msg.value = finished.state === "done" ? `「${finished.name}」安装完成` : `「${finished.name}」安装失败：${finished.message}`;
  }
}

onMounted(() => {
  refresh();
  timer = setInterval(poll, 400);
});
onBeforeUnmount(() => clearInterval(timer));

function install(kind) {
  const id = installComponent(kind.id);
  if (!id) { msg.value = "无宿主：组件安装只在 MFMath.exe 里可用"; return; }
  job.value = { id, name: kind.label, pct: 0, message: "开始…", state: "running" };
  msg.value = "";
}
function cancel() {
  if (job.value) { cancelInstall(job.value.id); msg.value = "已请求取消（已下载的部分保留，下次接着下）"; }
}
function uninstall(kind) {
  const r = uninstallComponent(kind.id);
  if (!r) { msg.value = "无宿主：卸载只在 MFMath.exe 里可用"; return; }
  if (r.ok) {
    refresh();
    msg.value = r.removed ? `已卸载「${kind.label}」，释放 ${((r.bytes || 0) / 1048576).toFixed(1)} MB` : "该组件本来就没安装";
  } else {
    msg.value = `卸载失败：${r.error}（若控制台里正在运行，请先停止）`;
  }
}
function saveBase() {
  const r = setDownloadBase(baseInput.value || "");
  msg.value = r ? "下载源已更新（空值表示恢复默认站点）" : "无宿主：无法修改下载源";
}
function openComponents() {
  const r = openPath(root.value);
  msg.value = r?.ok ? "" : (r?.error || "打开失败");
}

/** "未使用"= 目录在、但组件不可用（缺关键文件），这时占用空间却用不上 */
const stale = computed(() => KINDS.filter((k) => {
  const e = entryOf(k.id);
  return e && !e.installed && (e.bytes || 0) > 0;
}));
function cleanup() {
  let freed = 0;
  for (const k of stale.value) {
    const r = uninstallComponent(k.id);
    if (r?.ok) freed += r.bytes || 0;
  }
  refresh();
  msg.value = `已清理 ${stale.value.length} 项，释放 ${(freed / 1048576).toFixed(1)} MB（下载缓存 cache/ 保留，重装时可省一次下载）`;
}
</script>

<template>
  <section>
    <p v-if="!isConsoleHosted()" class="s-warn">浏览器预览：组件状态读不到（需要宿主）。</p>

    <div v-for="k in KINDS" :key="k.id" class="s-row" :data-setting="'components.' + k.id">
      <div class="s-label">
        <label>{{ k.label }}</label>
        <p class="s-hint">{{ k.desc }}</p>
      </div>
      <div class="s-ctl">
        <template v-if="entryOf(k.id)">
          <span class="tag" :class="{ ok: entryOf(k.id).installed }">
            {{ entryOf(k.id).installed ? "已安装" : "未安装" }}
          </span>
          <span class="s-hint">
            <template v-if="entryOf(k.id).installed">
              {{ ((entryOf(k.id).bytes || 0) / 1048576).toFixed(1) }} MB
              <template v-if="entryOf(k.id).version"> · v{{ entryOf(k.id).version }}</template>
            </template>
            <template v-else>需要时再下载，主程序体积不受影响</template>
          </span>
          <button v-if="!entryOf(k.id).installed" class="s-btn" :disabled="!!job" @click="install(k)">安装</button>
          <button v-else class="s-btn danger" :disabled="!!job" @click="uninstall(k)">卸载</button>
          <p v-if="entryOf(k.id).warning" class="s-warn inline">{{ entryOf(k.id).warning }}</p>
        </template>
        <span v-else class="s-hint">读取中…</span>
      </div>
    </div>

    <div v-if="job" class="s-row">
      <div class="s-label"><label>正在安装 {{ job.name }}</label><p class="s-hint">{{ job.message }}</p></div>
      <div class="s-ctl">
        <span class="bar"><i :style="{ width: job.pct + '%' }" /></span>
        <span class="s-hint">{{ job.pct }}%</span>
        <button class="s-btn" @click="cancel">取消</button>
      </div>
    </div>

    <div class="s-row" data-setting="components.dir">
      <div class="s-label"><label>组件目录</label><p class="s-hint mono">{{ root || "—" }}</p></div>
      <div class="s-ctl"><button class="s-btn" :disabled="!root" @click="openComponents">打开目录</button></div>
    </div>

    <div class="s-row" data-setting="components.source">
      <div class="s-label">
        <label>下载源</label>
        <p class="s-hint">留空 = 默认站点；企业内网镜像在此填绝对地址</p>
      </div>
      <div class="s-ctl">
        <input v-model="baseInput" class="s-input wide" placeholder="https://…/download/component/" />
        <button class="s-btn" @click="saveBase">应用</button>
      </div>
    </div>

    <div class="s-row" data-setting="components.cleanup">
      <div class="s-label">
        <label>清理未使用组件</label>
        <p class="s-hint">
          {{ stale.length ? `发现 ${stale.length} 项"装了但不可用"的目录，可释放空间` : "没有可清理的内容" }}
        </p>
      </div>
      <div class="s-ctl"><button class="s-btn" :disabled="!stale.length" @click="cleanup">清理</button></div>
    </div>

    <p v-if="msg" class="s-warn">{{ msg }}</p>
  </section>
</template>

<style scoped>
.tag {
  font-size: 11.5px; padding: 2px 8px; border-radius: 999px;
  border: 1px solid var(--border); color: var(--text-subtle, #64748b);
}
.tag.ok { color: #10b981; border-color: color-mix(in srgb, #10b981 45%, var(--border)); }
.bar { display: inline-block; width: 160px; height: 6px; border-radius: 3px; background: var(--surface-alt); overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--accent, #3b82f6); transition: width .2s; }
.s-btn.danger { border-color: color-mix(in srgb, #ef4444 45%, var(--border)); color: #ef4444; }
.s-warn.inline { margin: 4px 0 0; padding: 4px 8px; }
</style>
