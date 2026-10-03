<script setup>
/**
 * UpdateGroup.vue — 设置 → 更新
 *
 * 这一组只做三件事（本项目的既定取舍）：**查版本、如实显示差异、把下载交给浏览器**。
 * 软件不自动下载、更不执行安装包。
 *
 * 界面上刻意保留的两处"不好看但诚实"：
 *   · 站点没给校验值 → 显示"站点未提供校验值：<原因>"，不显示成"已校验"；
 *   · 站点版本比本机旧 → 不说"有新版"，而说"站点上的是 X（比本机旧）"并解释原因。
 */
import { computed, onMounted, ref, watch } from "vue";
import {
  updateInfo, updateState, updatePrefs, updateHosted,
  initUpdate, refreshUpdateInfo, loadUpdatePrefs, saveUpdatePrefs,
  checkUpdate, openDownloadPage, previewDownloadUrl, updateSelfCheck, hintFor,
} from "../../lib/update/bridge.js";

const selfCheck = ref(null);
const opened = ref("");
/** 将打开的地址：点之前就让用户看见，而不是点下去才知道会被送到哪儿 */
const previewUrl = ref("");

onMounted(() => {
  initUpdate();
  refreshUpdateInfo();
  loadUpdatePrefs();
  selfCheck.value = updateSelfCheck();
});

const r = computed(() => updateState.value.result);
const err = computed(() => updateState.value.error);

const sizeText = computed(() => {
  const n = Number(r.value?.size);
  if (!Number.isFinite(n) || n <= 0) return "";
  return n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.round(n / 1024)} KB`;
});

const relationText = computed(() => {
  if (!r.value) return "";
  switch (r.value.relation) {
    case "newer": return `站点上有更新的版本：${r.value.latest}`;
    case "same": return "已是最新版本";
    case "older": return `站点上的版本（${r.value.latest}）比本机旧`;
    default: return "";
  }
});

const shaText = computed(() => {
  if (!r.value) return "";
  return r.value.sha256 ? r.value.sha256 : `站点未提供校验值：${r.value.sha256Reason || "原因未知"}`;
});

function doCheck() {
  const res = checkUpdate();
  selfCheck.value = updateSelfCheck();
  return res;
}

// 结果出来就先把"将打开的地址"算给用户看（宿主只算不打开；不合法就显示拒绝）
watch(r, () => {
  const url = r.value?.downloadUrl;
  const res = url ? previewDownloadUrl(url) : null;
  previewUrl.value = res?.ok ? res.url : "";
}, { immediate: true });

function doOpen() {
  const url = r.value?.downloadUrl || "/download";
  const res = openDownloadPage(url);
  opened.value = res?.ok ? `已在浏览器里打开：${res.opened}` : (res?.error || "打开失败");
  setTimeout(() => { if (opened.value) opened.value = ""; }, 4000);
}
</script>

<template>
  <div class="ug">
    <p v-if="!updateHosted" class="warn" data-setting="update.version">
      浏览器预览里没有宿主桥：更新检查由宿主发请求（也由宿主把下载页交给浏览器），这里只能看。
    </p>

    <!-- ① 当前版本 -->
    <section class="row" data-setting="update.version">
      <div class="lab">
        <span>当前版本</span>
        <small>来自程序集版本（csproj 显式声明）</small>
      </div>
      <div class="ctl col">
        <p class="state" data-update="current">MF-Mathematics <b>{{ updateInfo.appVersion || "未知" }}</b></p>
        <p class="hint">
          本软件**不会自动下载或运行安装包**：它只查版本、把校验值显示给你，下载与安装都在浏览器里由你决定。
          少一条"下载并运行可执行文件"的通路。
        </p>
      </div>
    </section>

    <!-- ② 更新通道 -->
    <section class="row" data-setting="update.channel">
      <div class="lab">
        <span>更新通道</span>
        <small>站点目前只提供一条通道</small>
      </div>
      <div class="ctl col">
        <p class="state" data-update="channel">stable（站点只提供这一条；没有 beta 通道）</p>
      </div>
    </section>

    <!-- ③ 更新源 -->
    <section class="row" data-setting="update.source">
      <div class="lab">
        <span>更新源</span>
        <small>与账号用的是同一个站点地址（一处真相，不设第二个地址框）</small>
      </div>
      <div class="ctl col">
        <p class="state mono" data-update="source">{{ updateInfo.baseUrl || "—" }}</p>
        <p class="hint">要改就去「设置 → 账号」改站点地址；这里刻意不重复一个输入框，免得两处不一致。</p>
      </div>
    </section>

    <!-- ④ 自动检查 -->
    <section class="row" data-setting="update.mode">
      <div class="lab">
        <span>自动检查</span>
        <small>默认**关**：启动就联网是替你做决定（也会暴露 IP 与使用时间）</small>
      </div>
      <div class="ctl col">
        <label class="sw">
          <input type="checkbox" data-update-set="autoCheck" :checked="updatePrefs.autoCheck"
                 @change="saveUpdatePrefs({ autoCheck: $event.target.checked })" />
          <span>启动时检查新版本（超过下面的间隔才真的查）</span>
        </label>
        <p class="hint" data-update="last-check">
          上次检查：{{ updatePrefs.lastCheckAt ? new Date(updatePrefs.lastCheckAt).toLocaleString() : "从未" }}
        </p>
      </div>
    </section>

    <!-- ⑤ 检查间隔 -->
    <section class="row" data-setting="update.interval">
      <div class="lab">
        <span>检查间隔</span>
        <small>只影响"自动检查"</small>
      </div>
      <div class="ctl col">
        <label class="inline">
          每
          <input class="inp num" type="number" min="1" max="90" data-update-set="intervalDays"
                 :value="updatePrefs.intervalDays"
                 @change="saveUpdatePrefs({ intervalDays: Number($event.target.value) })" />
          天
        </label>
      </div>
    </section>

    <!-- ⑥ 手动检查 -->
    <section class="row" data-setting="update.check">
      <div class="lab">
        <span>手动检查</span>
        <small>立刻查一次（不改变"自动检查"的设置）</small>
      </div>
      <div class="ctl col">
        <button class="btn btn-primary" data-update="check" :disabled="updateState.checking" @click="doCheck">
          {{ updateState.checking ? "检查中…" : "立即检查" }}
        </button>

        <p v-if="err" class="err" data-update="error">
          {{ err.message }}
          <span class="hint"> —— {{ hintFor(err.kind) }}</span>
        </p>

        <template v-if="r">
          <p class="state" data-update="result">
            {{ relationText }}
            <span class="mono">（本机 {{ r.current }} · 站点 {{ r.latest }}<span v-if="r.date"> · {{ r.date }}</span>）</span>
          </p>
          <p class="hint">{{ r.note }}</p>
          <p class="hint" data-update="sha">
            SHA-256：<span class="mono">{{ shaText }}</span><span v-if="sizeText"> · 大小 {{ sizeText }}</span>
          </p>
          <p class="hint" data-update="target">
            将打开：<span class="mono">{{ previewUrl || "（下载地址不合法，已被拒绝）" }}</span>
          </p>
          <div class="inline">
            <button class="btn" data-update="download" @click="doOpen">在浏览器里打开下载页</button>
            <span v-if="opened" class="hint" data-update="opened">{{ opened }}</span>
          </div>
        </template>
      </div>
    </section>

    <!-- ⑦ 自检 -->
    <section class="row" data-setting="update.selftest">
      <div class="lab">
        <span>自检</span>
        <small>版本比较 / 关系判定 / 缺校验值 / 协议闸门 —— **不联网**</small>
      </div>
      <div class="ctl col">
        <button class="btn" data-update="selfcheck" @click="selfCheck = updateSelfCheck()">重新自检</button>
        <ul class="checks" data-update="selfcheck-list">
          <li v-for="(c, i) in (selfCheck?.checks || [])" :key="i" :class="{ bad: !c.ok }">
            <span class="dot">{{ c.ok ? "✔" : "✗" }}</span>
            <span class="ck-name">{{ c.name }}</span>
            <span class="ck-detail">{{ c.detail }}</span>
          </li>
        </ul>
      </div>
    </section>
  </div>
</template>

<style scoped>
.ug { display: flex; flex-direction: column; gap: 2px; }
.row { display: flex; gap: 16px; padding: 12px 4px; border-bottom: 1px solid var(--border); align-items: flex-start; }
.lab { width: 190px; flex: none; display: flex; flex-direction: column; gap: 3px; }
.lab span { font-size: 13.5px; }
.lab small { color: var(--muted); font-size: 11.5px; line-height: 1.5; }
.ctl { flex: 1; min-width: 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ctl.col { flex-direction: column; align-items: stretch; gap: 7px; }
.inline { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.inp {
  background: var(--bg); color: var(--text); border: 1px solid var(--border);
  border-radius: 6px; padding: 5px 7px; font-size: 12.5px;
}
.inp.num { max-width: 88px; }
.mono { font-family: ui-monospace, Consolas, monospace; font-size: 11.5px; word-break: break-all; }
.sw { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--muted); }
.state { margin: 0; font-size: 12.5px; }
.hint { margin: 0; font-size: 11.5px; line-height: 1.7; color: var(--muted); }
.err { margin: 0; font-size: 12.5px; color: var(--danger, #d05a5a); }
.warn { color: var(--warn, #c77); font-size: 12.5px; }
.checks { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.checks li { display: flex; gap: 6px; font-size: 11.5px; color: var(--muted); }
.checks li.bad { color: var(--danger, #d05a5a); }
.ck-name { color: var(--text); flex: none; }
.ck-detail { overflow: hidden; text-overflow: ellipsis; }
</style>
