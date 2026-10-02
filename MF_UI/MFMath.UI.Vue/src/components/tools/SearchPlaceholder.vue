<script setup>
/**
 * SearchPlaceholder — 顶栏「搜索」的占位面板
 *
 * 背景：这个按钮此前**点了没有任何反应**（没有 @click）。修法有两种——把按钮摘掉，
 * 或者把"现在没有、将来会是什么样"讲清楚。选后者：在线搜索是 v1 就有的功能
 * （v1 的 MF_Online + dialogs/search_panel.py，支持 DuckDuckGo / Wolfram Alpha / 自定义端点），
 * 用户会来找它；摆一个说明面板比让按钮死着好，也比假装有搜索好。
 *
 * 这里**不做假搜索框**：装一个搜不出东西的输入框，比明说"还没接入"更糟。
 */
import { useRouter } from "vue-router";

const emit = defineEmits(["close"]);
const router = useRouter();

const PLANNED = [
  ["搜索源", "DuckDuckGo（免密钥）、Wolfram Alpha（自备 App ID）、自定义端点（如 SearXNG）"],
  ["结果处理", "结果里识别出的数学表达式可一键送进计算页 / 绘图页（走已有的 pendingInput 通路）"],
  ["本地缓存", "命中过的查询缓存到 %LOCALAPPDATA%\\MFMath（可设 TTL、可清空），断网时仍能回看"],
  ["超时与隐私", "可设超时秒数；面板上明确写出「查询会发往哪个站点」"],
];

function goSettings() {
  router.push({ path: "/settings", query: { group: "search" } });
  emit("close");
}
function goHelp() {
  router.push("/tutorial");
  emit("close");
}
</script>

<template>
  <div class="dialog-overlay">
    <div class="dialog sp-dialog">
      <div class="dialog-header">
        <span>在线搜索 — 尚未接入</span>
        <button class="dialog-close" @click="emit('close')">✕</button>
      </div>

      <div class="dialog-body">
        <p class="sp-lead">
          这个入口对应的在线搜索面板<strong>还没有实现</strong>，所以这里先说明它将来是什么样，
          而不是给你一个点了没反应的按钮（这是之前的状态）或一个搜不出东西的假搜索框。
        </p>

        <table class="sp-table">
          <tbody>
            <tr v-for="[k, v] in PLANNED" :key="k">
              <th>{{ k }}</th>
              <td>{{ v }}</td>
            </tr>
          </tbody>
        </table>

        <p class="sp-plan">
          对应计划：<code>docs/MIGRATION-GAPS.md</code> §2.3（第三批）。
          依赖项只有 Wolfram 的 App ID 需要你自备，其余不需要等任何决策。
        </p>
        <p class="sp-plan">
          现在能用的替代：<strong>使用教程</strong>里有 18 篇分步讲解与 52 个可直接加载的示例任务；
          设置面板里的搜索框可以按名字定位到具体设置项（含尚未实现的项）。
        </p>
      </div>

      <div class="dialog-footer">
        <button class="btn btn-ghost" @click="goSettings">看设置里的搜索项</button>
        <button class="btn btn-ghost" @click="goHelp">打开教程与示例库</button>
        <button class="btn btn-primary" @click="emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sp-dialog { width: min(620px, 92vw); }
.sp-lead { margin: 0 0 12px; font-size: 13px; line-height: 1.7; color: var(--text); }
.sp-table { width: 100%; border-collapse: collapse; margin-bottom: 12px; }
.sp-table th {
  width: 92px; text-align: left; vertical-align: top; padding: 6px 10px 6px 0;
  font-size: 12px; font-weight: 600; color: var(--text-subtle); white-space: nowrap;
}
.sp-table td {
  padding: 6px 0; font-size: 13px; color: var(--text); border-bottom: 1px solid var(--border);
}
.sp-table tr:last-child td { border-bottom: none; }
.sp-plan { margin: 8px 0 0; font-size: 12px; line-height: 1.7; color: var(--text-subtle); }
.sp-plan code { font-family: ui-monospace, Consolas, monospace; }
</style>
