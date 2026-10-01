<script setup>
/**
 * 设置 · 引擎分组
 *
 * 目的很实际：**出问题时让用户自助排查**，减少支持成本。
 * 展示：引擎版本、引擎目录（可打开）、依赖 DLL 是否齐全、已注册函数数、以及一个自检按钮。
 *
 * 自检做的是真事：走一遍 P/Invoke → 引擎 → 拿回结果 → 与预期比对，
 * 而不是只报"引擎正常"。任何一项不过，就把**实际返回值**显示出来，
 * 让人一眼看出是哪个函数、返回了什么（这比"自检失败"有用得多）。
 */
import { onMounted, ref } from "vue";
import { bridgeReady, bridgeVersion, isHosted, engineCall, functionExists } from "../../lib/bridge.js";
import { info, engineReport, openPath, isSettingsHosted } from "../../lib/settings/bridge.js";

const hostInfo = ref(info());
const report = ref(engineReport());
const fnCount = ref(null);
const fnError = ref("");
const testing = ref(false);
const results = ref([]);
const openMsg = ref("");

function totalBytes(files) {
  return files.reduce((n, f) => n + (f.bytes || 0), 0);
}
const depsOk = () => (report.value.files || []).every((f) => f.present);

onMounted(() => {
  if (!isHosted()) return;
  // 已注册函数数量：走引擎的 list_functions（这也是"引擎真的被调到了"的证据）
  const r = engineCall("list_functions", {});
  if (r && !r.isError && r.value && typeof r.value.count === "number") fnCount.value = r.value.count;
  else if (r && r.isError) fnError.value = String(r.value);
  else if (!r) fnError.value = "无引擎桥";
});

/** 冒烟自检：每条都比对真实返回值 */
async function selfTest() {
  testing.value = true;
  results.value = [];
  const cases = [
    {
      name: "expr_eval（数值）",
      run: () => engineCall("expr_eval", { expr: "x^2", x: 3 }),
      ok: (v) => Math.abs(Number(v) - 9) < 1e-9,
    },
    {
      name: "diff（符号求导）",
      run: () => engineCall("diff", { expr: "x^2", var: "x" }),
      ok: (v) => /2\s*\*?\s*x/.test(String(v)),
    },
    {
      name: "factor（因式分解）",
      run: () => engineCall("factor", { expr: "x^2-1" }),
      ok: (v) => /x\s*-\s*1/.test(String(v)) && /x\s*\+\s*1/.test(String(v)),
    },
    {
      name: "list_functions（函数表）",
      run: () => engineCall("list_functions", {}),
      ok: (v) => v && typeof v.count === "number" && v.count > 0,
    },
    {
      name: "function_exists（能力探测）",
      run: () => ({ __direct: functionExists("solve_sym") }),
      ok: (v) => v && v.__direct === true,
    },
  ];
  for (const c of cases) {
    let detail = "";
    let pass = false;
    try {
      const r = c.run();
      if (r === null) { detail = "无引擎桥（浏览器预览）"; }
      else if (r && r.isError) { detail = "引擎报错：" + r.value; }
      else {
        const v = r && Object.prototype.hasOwnProperty.call(r, "__direct") ? r : (r.value ?? r);
        pass = c.ok(v);
        detail = "返回：" + JSON.stringify(v);
      }
    } catch (e) {
      detail = "抛异常：" + (e?.message || e);
    }
    results.value.push({ name: c.name, pass, detail });
  }
  // 依赖 DLL 必须齐全：缺一个就会在运行时加载失败，报错很不直观
  const missing = (report.value.files || []).filter((f) => !f.present).map((f) => f.name);
  results.value.push({
    name: "运行时依赖 DLL 齐全",
    pass: missing.length === 0,
    detail: missing.length ? "缺失：" + missing.join(", ") : `全部就位（共 ${((totalBytes(report.value.files || [])) / 1048576).toFixed(1)} MB）`,
  });
  testing.value = false;
}

function openEngineDir() {
  const r = openPath(report.value.dir || "");
  openMsg.value = r?.ok ? "" : (r?.error || "打开失败");
}
function openDataDir() {
  const r = openPath(hostInfo.value.dataDir || "");
  openMsg.value = r?.ok ? "" : (r?.error || "打开失败");
}
</script>

<template>
  <section>
    <p v-if="!isSettingsHosted()" class="s-warn">
      浏览器预览模式：读不到宿主信息（引擎目录、依赖清单）。在 MFMath.exe 里运行才完整。
    </p>

    <div class="s-row" data-setting="engine.version">
      <div class="s-label"><label>引擎版本</label><p class="s-hint">经 WebView2 桥读取</p></div>
      <div class="s-ctl mono">{{ bridgeReady() ? bridgeVersion() : "桥未就绪" }}</div>
    </div>

    <div class="s-row" data-setting="engine.path">
      <div class="s-label"><label>引擎目录</label><p class="s-hint">{{ hostInfo.appDir || "—" }}</p></div>
      <div class="s-ctl">
        <button class="s-btn" :disabled="!isSettingsHosted()" @click="openEngineDir">打开目录</button>
        <button class="s-btn" :disabled="!isSettingsHosted()" @click="openDataDir">打开数据目录</button>
      </div>
    </div>

    <div class="s-row" data-setting="engine.deps">
      <div class="s-label">
        <label>依赖 DLL 状态</label>
        <p class="s-hint">
          共 {{ (report.files || []).length }} 个 ·
          {{ depsOk() ? "全部就位" : "有缺失（缺一个就会加载失败）" }}
        </p>
      </div>
      <div class="s-ctl">
        <table class="dep-table">
          <tbody>
            <tr v-for="f in report.files" :key="f.name">
              <td class="dep-ok" :class="{ bad: !f.present }">{{ f.present ? "✓" : "✕" }}</td>
              <td class="mono">{{ f.name }}</td>
              <td class="dep-size">{{ f.present ? (f.bytes / 1048576).toFixed(2) + " MB" : "缺失" }}</td>
              <td class="dep-time">{{ f.mtime || "" }}</td>
            </tr>
            <tr v-if="!(report.files || []).length">
              <td colspan="4" class="s-hint">（浏览器预览：无宿主，无法列举）</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="s-row" data-setting="engine.functions">
      <div class="s-label"><label>已注册函数数量</label><p class="s-hint">来自引擎的 list_functions</p></div>
      <div class="s-ctl">
        <b v-if="fnCount !== null" class="mono">{{ fnCount }}</b>
        <span v-else class="s-hint">{{ fnError || "读取中…" }}</span>
      </div>
    </div>

    <div class="s-row" data-setting="engine.selftest">
      <div class="s-label">
        <label>引擎自检</label>
        <p class="s-hint">走一遍桥 → 引擎 → 比对返回值；失败会显示实际返回内容</p>
      </div>
      <div class="s-ctl">
        <button class="s-btn primary" :disabled="testing || !isHosted()" @click="selfTest">
          {{ testing ? "自检中…" : "开始自检" }}
        </button>
      </div>
    </div>

    <div v-if="results.length" class="s-result">
      <p v-for="(r, i) in results" :key="i" class="s-item" :class="{ bad: !r.pass }">
        <span class="s-mark">{{ r.pass ? "✓" : "✕" }}</span>
        <span class="s-name">{{ r.name }}</span>
        <span class="s-detail mono">{{ r.detail }}</span>
      </p>
      <p class="s-hint" style="margin-top:6px">
        合计 {{ results.filter(r => r.pass).length }} / {{ results.length }} 项通过。
        若依赖 DLL 缺失，请重新运行安装包或从引擎目录补齐。
      </p>
    </div>

    <p v-if="openMsg" class="s-warn">{{ openMsg }}</p>
  </section>
</template>

<style scoped>
.dep-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.dep-table td { padding: 3px 8px 3px 0; border-bottom: 1px solid var(--border); }
.dep-ok { color: #10b981; width: 18px; }
.dep-ok.bad { color: #ef4444; }
.dep-size { color: var(--text-subtle, #64748b); text-align: right; white-space: nowrap; }
.dep-time { color: var(--text-subtle, #94a3b8); white-space: nowrap; padding-left: 10px; }
.s-result { margin-top: 10px; border-top: 1px dashed var(--border); padding-top: 8px; }
.s-item { display: flex; gap: 8px; align-items: baseline; margin: 4px 0; font-size: 12.5px; }
.s-mark { color: #10b981; }
.s-item.bad .s-mark { color: #ef4444; }
.s-name { min-width: 190px; }
.s-detail { color: var(--text-subtle, #64748b); word-break: break-all; }
</style>
