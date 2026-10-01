<script setup>
/**
 * HomeView — 首页 / 引擎自检
 * 显示 WebView2 桥状态，并提供一个最小表达式试算（expr_eval）验证 C#→C++ 链路
 */
import { ref, onMounted } from "vue";
import { isHosted, bridgeReady, bridgeVersion, engineCall } from "../lib/bridge.js";

const hosted = ref(false);
const ready = ref(false);
const version = ref("");
const checks = ref([]);

const expr = ref("x^2 + 2*x + 1");
const xVal = ref("3");
const running = ref(false);
const result = ref(null);   // {isError, value}

function runChecks() {
  hosted.value = isHosted();
  ready.value = bridgeReady();
  version.value = bridgeVersion();
  checks.value = [];
  // 直接实调引擎函数（function_exists 是 C ABI 顶层，不可经 dispatch 调用）
  const probes = [
    ["expr_eval", { expr: "x^2", x: 3 }, "expr_eval(x², x=3)"],
    ["expr_eval_batch", { expr: "x^2", xs: [0, 1, 2, 3] }, "expr_eval_batch(x²)"],
    ["simpson_rule", { f: "sin(x)", a: 0, b: 1, n: 100 }, "simpson_rule(∫sin, 0..1)"],
  ];
  for (const [fn, args, label] of probes) {
    const r = engineCall(fn, args);
    const ok = !!(r && !r.isError);
    checks.value.push({
      fn: label, ok,
      detail: r && !r.isError ? String(r.value) : (r ? "错误: " + r.value : "未连接引擎"),
    });
  }
}

function runCalc() {
  running.value = true;
  result.value = null;
  try {
    const r = engineCall("expr_eval", { expr: expr.value.trim(), x: Number(xVal.value) });
    result.value = r;
  } catch (e) {
    result.value = { isError: true, value: String(e) };
  } finally {
    running.value = false;
  }
}

onMounted(runChecks);
</script>

<template>
  <div class="view-body">
    <div class="ws-title">MF-Mathematics · Vue 版</div>
    <div class="ws-desc">多功能可视化科学计算 — 计算经 mf_mathematics.dll（C++），链接经 C# MathBridge / WebView2</div>

    <div class="view-box">
      <!-- 引擎状态卡 -->
      <div class="card" style="margin-bottom:14px">
        <div class="ws-title" style="font-size:15px">引擎状态</div>
        <div class="form-row" style="margin-top:8px">
          <span id="hf-hosted" class="badge" :class="hosted ? 'ok' : 'no'">{{ hosted ? "WebView2 桥：已连接" : "浏览器预览：无引擎桥" }}</span>
          <span id="hf-ready" class="badge" :class="ready ? 'ok' : 'no'">{{ ready ? "Ready()：正常" : "Ready()：不可用" }}</span>
          <span id="hf-version" class="mono" style="color:var(--text-muted)">{{ version }}</span>
        </div>
        <table v-if="checks.length" class="check-table" id="hf-checks">
          <tr v-for="c in checks" :key="c.fn">
            <td class="mono">{{ c.fn }}</td>
            <td><span class="badge" :class="c.ok ? 'ok' : 'no'">{{ c.ok ? "正常" : "失败" }}</span></td>
            <td class="mono" style="color:var(--text-muted);padding-left:10px;font-size:12px">{{ c.detail }}</td>
          </tr>
        </table>
        <button class="btn btn-ghost" style="margin-top:8px" @click="runChecks">重新检测</button>
      </div>

      <!-- 最小表达式试算 -->
      <div class="card">
        <div class="ws-title" style="font-size:15px">表达式试算（expr_eval）</div>
        <div class="form-row" style="margin-top:8px">
          <input v-model="expr" class="input mono" style="flex:1" placeholder="表达式，如 x^2 + 2*x + 1" />
          <label>x =</label>
          <input v-model="xVal" class="input mono" style="width:80px" />
          <button class="btn btn-primary" :disabled="running || !hosted" @click="runCalc">
            {{ running ? "计算中…" : "计算" }}
          </button>
        </div>
        <div v-if="result" class="result-card" :style="result.isError ? 'border-color:var(--danger)' : ''">
          <div v-if="result.isError" style="color:var(--danger)">错误：{{ result.value }}</div>
          <div v-else class="answer">= {{ result.value }}</div>
        </div>
        <div v-if="!hosted" class="hint">在浏览器中预览：点击「计算」会返回待接入提示。请用 MFMath.exe（Release/Debug）验证引擎链路。</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.badge {
  display: inline-block; padding: 2px 10px; border-radius: 999px;
  font-size: 12px; font-weight: 600;
}
.badge.ok { background: var(--success); color: #fff; }
.badge.no { background: var(--danger-soft); color: var(--danger); }
.check-table { border-collapse: collapse; margin-top: 8px; }
.check-table td { padding: 3px 12px 3px 0; }
.hint { margin-top: 10px; font-size: 12px; color: var(--text-subtle); }
</style>
