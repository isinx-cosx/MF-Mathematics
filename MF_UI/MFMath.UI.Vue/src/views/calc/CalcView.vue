<script setup>
/**
 * CalcView — 通用计算工作区（对应旧版 renderCalcWorkspace + Python BaseWorkspace/BaseCalcBlock）
 *  · 计算块：表达式输入 + 模式下拉 + 计算结果 + 删除（可增删，多块独立）
 *  · 计算流程：模式 → 引擎映射（324 项）→ 自动构造参数 → 引擎调用 → 结果对话框
 *  · 多参数模式（19 项 VAR_SPECS）先弹出参数输入框，用户可自定义 a/b/n 等
 *  · 未映射的模式明确提示"引擎未提供该模式的接口"（不静默）
 */
import { ref, computed, watch } from "vue";
import MathField from "../../components/math/MathField.vue";
import { useRoute } from "vue-router";
import MultiVarDialog from "../../components/calc/MultiVarDialog.vue";
import ResultDialog from "../../components/calc/ResultDialog.vue";
import { getViewConfig } from "../../lib/engine/viewConfigs.js";
import { ENGINE_MAP, ENGINE_VAR_SPECS } from "../../lib/engine/engineMap.js";
import { buildEngineArgs, buildEngineArgsFromValues, toEngineExpr, hasEngineMode, needsVarDialog } from "../../lib/engine/calcArgs.js";
import { engineCall, isHosted, bridgeVersion } from "../../lib/bridge.js";

const route = useRoute();
const hosted = isHosted();

/** 当前视图配置：按路由末段取（/calc/algebra → algebra） */
const configKey = computed(() => String(route.path).split("/").filter(Boolean).pop() || "");
const config = computed(() => getViewConfig(configKey.value) || { title: route.meta?.title || "计算", desc: "", modes: [], single: false });
const modes = computed(() => config.value.modes || []);
const single = computed(() => config.value.single === true);

/* ── 计算块 ── */
let nextId = 1;
const blocks = ref([]);
const statusText = ref("");

function makeBlock() {
  return { id: nextId++, expr: "", mode: modes.value[0] || "", error: "", computing: false, lastResult: null };
}

watch(config, () => {
  blocks.value = [makeBlock()];
  statusText.value = `${config.value.title} · ${modes.value.length} 个模式` +
    (hosted ? ` · ${bridgeVersion()}` : " · 浏览器预览（无引擎）");
}, { immediate: true });

function addBlock() {
  if (single.value) return;
  blocks.value = [...blocks.value, makeBlock()];
}
function removeBlock(id) {
  if (blocks.value.length <= 1) return;
  blocks.value = blocks.value.filter((b) => b.id !== id);
}
function patchBlock(id, patch) {
  blocks.value = blocks.value.map((b) => (b.id === id ? { ...b, ...patch } : b));
}

/* ── 弹窗状态 ── */
const varDialog = ref(null);     // {mode, fields, firstValue, blockId}
const resultDialog = ref(null);  // {mode, expr, result, rawJson}

/** 模式未映射的提示 */
function unmappedHint(mode) {
  return hasEngineMode(mode)
    ? ""
    : `模式「${mode}」暂无引擎映射（引擎未提供该接口）`;
}

/* ── 计算 ── */
/**
 * 该模式是否真的需要输入框里的东西。
 * 像「三角恒等式」「测度性质」「共形映射（只选区域）」这类模式引擎不收表达式，
 * 旧代码一刀切要求输入非空 —— 结果是这些模式永远点不动，只提示"请输入表达式"。
 */
function modeNeedsInput(mode) {
  const spec = ENGINE_MAP[mode];
  if (!spec) return true;                       // 未映射时仍要求输入，提示更具体
  const args = spec.args || [];
  if (!args.length) return false;               // 无参模式：直接可算
  // 只有"靠输入框提供值的必填参数"才要求输入；其它走弹窗字段/默认值
  return args.some((a) => !a.opt);
}

function calc(block) {
  const expr = String(block.expr || "").trim();
  const mode = block.mode;
  if (!expr && modeNeedsInput(mode)) { patchBlock(block.id, { error: "请输入表达式" }); return; }
  patchBlock(block.id, { error: "", computing: true });

  const spec = ENGINE_MAP[mode];

  if (!spec) {
    patchBlock(block.id, { computing: false, error: unmappedHint(mode) });
    return;
  }

  // 多参数模式：先收集参数（用户可改 a/b/n 等）
  if (needsVarDialog(mode)) {
    patchBlock(block.id, { computing: false });
    varDialog.value = {
      mode,
      fields: ENGINE_VAR_SPECS[mode],
      firstValue: expr,
      blockId: block.id,
      expr,
    };
    return;
  }

  finish(block, mode, expr, engineCall(spec.fn, buildEngineArgs(mode, expr)));
}

/** 弹窗确认：用收集的值构造参数并计算 */
function onVarConfirm(values) {
  const dlg = varDialog.value;
  if (!dlg) return;
  varDialog.value = null;
  const block = blocks.value.find((b) => b.id === dlg.blockId);
  const spec = ENGINE_MAP[dlg.mode];
  const args = buildEngineArgsFromValues(spec, dlg.fields, values);
  if (block) {
    patchBlock(block.id, { computing: true });
    finish(block, dlg.mode, dlg.expr, engineCall(spec.fn, args));
  }
}

function finish(block, mode, expr, result) {
  patchBlock(block.id, { computing: false, lastResult: result });
  if (result === null) {
    patchBlock(block.id, { error: "未检测到引擎桥（请在 MFMath.exe 中运行）" });
    return;
  }
  resultDialog.value = {
    mode, expr, result,
    rawJson: JSON.stringify(result, null, 2),
  };
  statusText.value = result.isError
    ? `${mode}：计算失败`
    : `${mode}：计算完成（${specFnName(mode)}）`;
}

function specFnName(mode) {
  const s = ENGINE_MAP[mode];
  return s ? s.fn : "—";
}

function closeResult() { resultDialog.value = null; }

/** 查看步骤：由上层能力决定（当前给出明确提示，不伪造内容） */
function onSteps() {
  const d = resultDialog.value;
  closeResult();
  if (!d) return;
  statusText.value = `「步骤」需 AI 或符号推理服务：引擎已给出精确结果 ${specFnName(d.mode)}，步骤推导未接入`;
}

/* 该视图已映射/未映射模式统计（供状态栏与排查） */
const mappedCount = computed(() => modes.value.filter((m) => hasEngineMode(m)).length);
const varDialogCount = computed(() => modes.value.filter((m) => needsVarDialog(m)).length);
</script>

<template>
  <div class="view-body">
    <div class="ws-wrap">
      <div class="ws-title">{{ config.title }}</div>
      <div class="ws-desc">{{ config.desc }}</div>

      <div class="work-card">
        <div v-for="(b, i) in blocks" :key="b.id">
          <div v-if="i > 0" class="cb-sep" />
          <div class="calc-block">
            <div class="cb-row">
              <!-- 与绘图页同一套输入体验：数学就地排版（输入 \frac 当场成分数） -->
              <!--
                必须用 v-model（等价于 update:model-value 里**原地**写 b.expr），
                不能用 patchBlock(b.id, {expr}) —— patchBlock 用 {...b} 生成新对象，
                而同一行里 <select v-model="b.mode"> 的处理器闭包持有的是**旧对象**，
                会写进已被丢弃的孤儿对象，导致"先改表达式、再改模式"时模式被静默丢弃。
                MathField 暴露的正是 modelValue/update:modelValue，可直接 v-model。 -->
              <MathField
                v-model="b.expr"
                class="cb-input"
                placeholder="输入表达式，如 x^2+3*x-1"
                @enter="calc(b)"
              />
              <select v-model="b.mode" class="select cb-mode">
                <option
                  v-for="m in modes"
                  :key="m"
                  :value="m"
                  :data-mapped="hasEngineMode(m)"
                  :data-var-dialog="needsVarDialog(m)"
                >{{ m }}{{ hasEngineMode(m) ? "" : "（未接入引擎）" }}</option>
              </select>
              <button class="btn btn-primary cb-calc" :disabled="b.computing" @click="calc(b)">
                {{ b.computing ? "计算中…" : "计算结果" }}
              </button>
              <button
                v-if="!single"
                class="btn btn-danger cb-del"
                title="删除"
                @click="removeBlock(b.id)"
              >✕</button>
            </div>
            <div v-if="b.error" class="cb-error">{{ b.error }}</div>
            <div v-else-if="b.lastResult && !b.lastResult.isError" class="cb-ok">
              已计算（{{ specFnName(b.mode) }}）
            </div>
          </div>
        </div>
        <button v-if="!single" class="btn-add" @click="addBlock">＋ 添加计算</button>
      </div>

      <div class="ws-foot">
        <span>{{ statusText }}</span>
        <span class="ws-stat">
          已映射 {{ mappedCount }}/{{ modes.length }} 个模式
          <template v-if="varDialogCount">· 其中 {{ varDialogCount }} 个需输入参数</template>
        </span>
      </div>
    </div>

    <MultiVarDialog
      v-if="varDialog"
      :mode="varDialog.mode"
      :fields="varDialog.fields"
      :first-value="varDialog.firstValue"
      @confirm="onVarConfirm"
      @cancel="varDialog = null"
    />

    <ResultDialog
      v-if="resultDialog"
      :mode="resultDialog.mode"
      :expr="resultDialog.expr"
      :result="resultDialog.result"
      :raw-json="resultDialog.rawJson"
      @close="closeResult"
      @steps="onSteps"
    />
  </div>
</template>

<style scoped>
.ws-wrap { max-width: 860px; margin: 0 auto; }

/* 数学输入框：框体、字号、高度（自适应）全部由 MathField.vue 决定。
 * 这里只保证它能作为 flex 子项收缩，不会被后面的 select/按钮挤变形。
 * 曾经这里写 display:flex + align-items:center —— <math-field> 是宿主元素，
 * 被当成 flex 容器后会把 shadow DOM 里的 .ML__container / .ML__sr-only
 * 当作并排的 flex 项，排版会错位；MathLive 明确要求宿主是 block。 */
.cb-input {
  min-width: 0;
}
.ws-foot {
  display: flex; justify-content: space-between; gap: 12px;
  margin-top: 10px; font-size: 11.5px; color: var(--text-subtle);
}
.ws-stat { white-space: nowrap; }
.cb-ok { font-size: 11.5px; color: var(--success); margin-top: 4px; }
</style>
