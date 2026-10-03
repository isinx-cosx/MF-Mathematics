<script setup>
/**
 * CalcView — 通用计算工作区（对应旧版 renderCalcWorkspace + Python BaseWorkspace/BaseCalcBlock）
 *  · 计算块：表达式输入 + 模式下拉 + 计算结果 + 删除（可增删，多块独立）
 *  · 计算流程：模式 → 引擎映射（324 项）→ 自动构造参数 → 引擎调用 → 结果对话框
 *  · 多参数模式（19 项 VAR_SPECS）先弹出参数输入框，用户可自定义 a/b/n 等
 *  · 未映射的模式明确提示"引擎未提供该模式的接口"（不静默）
 */
import { ref, computed, watch, onMounted, onBeforeUnmount } from "vue";
import MathField from "../../components/math/MathField.vue";
import { useRoute } from "vue-router";
import MultiVarDialog from "../../components/calc/MultiVarDialog.vue";
import ResultDialog from "../../components/calc/ResultDialog.vue";
import { getViewConfig } from "../../lib/engine/viewConfigs.js";
import { ENGINE_MAP, ENGINE_VAR_SPECS } from "../../lib/engine/engineMap.js";
import { buildEngineArgs, buildEngineArgsFromValues, toEngineExpr, hasEngineMode, needsVarDialog } from "../../lib/engine/calcArgs.js";
import { engineCall, isHosted, bridgeVersion } from "../../lib/bridge.js";
// 「查看步骤」：把这道题交给 AI 逐步调引擎讲解（分步显示的渲染层在 AiPanel/StepViewer）
import { requestAiTurn } from "../../lib/ai/bridge.js";
import { takePending, pickMode } from "../../lib/workspace/pendingInput.js";
import { getPage, setPage } from "../../lib/workspace/store.js";
import { registerUndoable } from "../../lib/keyboard/shortcuts.js";
import { briefValue } from "../../lib/engine/resultModel.js";
import { record } from "../../lib/history/store.js";

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
  // blocked：示例带来的操作没能在本页匹配上时的拦截原因。非空则**不允许计算** ——
  // 否则会带着该页默认模式（第一个模式）去算，算出来用户看不懂，还会误判成"功能出错"。
  return { id: nextId++, expr: "", mode: modes.value[0] || "", error: "", computing: false, lastResult: null, blocked: "" };
}

watch(config, () => {
  blocks.value = [makeBlock()];
  statusText.value = `${config.value.title} · ${modes.value.length} 个模式` +
    (hosted ? ` · ${bridgeVersion()}` : " · 浏览器预览（无引擎）");
  // 示例库 / 教程正文送来的表达式（跨路由携带）。取一次即清空，避免下次进来被
  // 旧示例反复覆盖。v1 在这里只做 setText 且 mode 匹配不到就静默忽略，这里明说。
  const pending = takePending();
  if (pending) { applyPending(pending); return; }
  // 工作区：没有示例要加载时，用保存过的这一页内容还原（示例优先——它是用户
  // 刚刚主动点的动作，不该被上次保存的旧内容顶掉）
  restoreFromWorkspace();
}, { immediate: true });

/** 用工作区里保存的这一页内容还原计算块（没有就用默认的一个空块） */
function restoreFromWorkspace() {
  const saved = getPage(route.path);
  if (!saved || saved.kind !== "calc" || !Array.isArray(saved.blocks) || !saved.blocks.length) return;
  blocks.value = saved.blocks.map((b) => {
    const blank = makeBlock();
    return {
      ...blank,
      expr: String(b.expr || ""),
      mode: modes.value.includes(b.mode) ? b.mode : (modes.value[0] || ""),
      blocked: "",
      error: "",
    };
  });
  statusText.value = `${config.value.title}：已从工作区还原 ${blocks.value.length} 个计算块`;
}

/** 采集本页要存进工作区的内容（只存"用户写的东西"，不存结果与临时错误） */
function capturePage() {
  return {
    kind: "calc",
    blocks: blocks.value.map((b) => ({ expr: b.expr || "", mode: b.mode || "" })),
  };
}

// 挂载完成前不回写 store：那期间 blocks 还是默认值，写回会把刚还原的内容盖掉
let syncWorkspace = false;

/* ── 撤销 / 重做（Ctrl+Z / Ctrl+Y，v1 编辑菜单里那两个）──
 *
 * 只记"用户写的东西"：表达式与模式。结果、错误、屏蔽原因都不进历史 ——
 * 撤销一次却把错误信息翻出来，比不撤销更让人困惑。
 * 上限 50 步，够用且不会把内存吃满。
 *
 * ⚠ 两个栈必须是**响应式**的（ref，不是普通数组）：
 * 第一版写成 `const undoStack = []` + `computed(() => undoStack.length > 0)`，
 * 而普通数组的 .length 不产生依赖 → computed 求值一次就永远缓存 false，
 * 于是按钮一直禁用、Ctrl+Z 也拿不到"可撤销对象"（`active()` 看的就是 canUndo）。
 * 实测症状：改了两处、栈里其实有东西，但 canUndo 一直是 false，快捷键和按钮全哑。
 */
const HISTORY_MAX = 50;
const undoStack = ref([]);
const redoStack = ref([]);
const canUndo = computed(() => undoStack.value.length > 0);
const canRedo = computed(() => redoStack.value.length > 0);
let applyingHistory = false;

function historySnapshot() {
  return blocks.value.map((b) => ({ expr: b.expr || "", mode: b.mode || "" }));
}
function sameAsCurrent(snap) {
  const cur = historySnapshot();
  return snap.length === cur.length
    && snap.every((s, i) => s.expr === cur[i].expr && s.mode === cur[i].mode);
}
function pushHistory(prev) {
  if (sameAsCurrent(prev)) return;
  undoStack.value.push(prev);
  if (undoStack.value.length > HISTORY_MAX) undoStack.value.shift();
  redoStack.value = [];
}
function applyHistory(snap) {
  applyingHistory = true;
  blocks.value = snap.map((s) => {
    const blank = makeBlock();
    return {
      ...blank,
      expr: s.expr,
      mode: modes.value.includes(s.mode) ? s.mode : (modes.value[0] || ""),
      blocked: "",
      error: "",
    };
  });
  // 下一个 tick 再解锁：watch(blocks) 是异步触发的，早解锁会把这次改动记成"用户操作"
  Promise.resolve().then(() => { applyingHistory = false; });
}
function undo() {
  if (!undoStack.value.length) return false;
  const prev = undoStack.value.pop();
  redoStack.value.push(historySnapshot());
  applyHistory(prev);
  statusText.value = `已撤销（可再撤销 ${undoStack.value.length} 步）`;
  return true;
}
function redo() {
  if (!redoStack.value.length) return false;
  const next = redoStack.value.pop();
  undoStack.value.push(historySnapshot());
  applyHistory(next);
  statusText.value = `已重做（可再撤销 ${undoStack.value.length} 步）`;
  return true;
}

onMounted(() => {
  syncWorkspace = true;
  // 基线在挂载时就定下来，而不是等"第一次改动"再顺手记：
  // 否则用户进来只改了一处时栈里空空如也，Ctrl+Z 什么都不会发生（第一版就是这样，
  // 因为 lastSnap 只在下一次回调里才有值）。
  lastSnap = historySnapshot();
});
let lastSnap = null;
watch(blocks, () => {
  if (syncWorkspace) setPage(route.path, capturePage());
  const cur = historySnapshot();
  if (!applyingHistory && lastSnap) pushHistory(lastSnap);
  lastSnap = cur;
}, { deep: true });

// 换页（同一个组件被不同计算页复用）＝换工作台：历史必须清空，
// 否则在新页面上撤销会把**上一页**的计算块搬过来。
watch(config, () => {
  undoStack.value = [];
  redoStack.value = [];
  lastSnap = historySnapshot();
});

// 注册给全局快捷键：本页在栈顶期间 Ctrl+Z/Ctrl+Y 作用在这里
let unregisterUndo = null;
onMounted(() => {
  unregisterUndo = registerUndoable({
    name: "计算页",
    undo, redo,
    canUndo: () => canUndo.value,
    canRedo: () => canRedo.value,
  });
});
onBeforeUnmount(() => { if (unregisterUndo) unregisterUndo(); });

/** 把送来的表达式与操作填进第一个计算块 */
function applyPending(p) {
  const b = blocks.value[0];
  if (!b) return;
  if (p.expr) b.expr = p.expr;
  // 优先用调用方已解析好的目标模式（示例库会先反查"这个操作属于哪个页面"，
  // 见 lib/workspace/pendingInput.js 的 resolveExample）。
  const wanted = (p.mode && modes.value.includes(p.mode)) ? p.mode : pickMode(p.operation, modes.value);
  if (p.operation && !wanted) {
    // 关键修复：早先这里只改状态栏文字，模式仍留在默认值上，用户一点「计算」
    // 就用错了动作（积分示例因此跑成 solve_sym，报"方程含超越函数"）。
    // 现在把该块**拦住**，并说明要用户先选操作。
    const msg = `示例要的操作「${p.operation}」在本页没有对应模式。表达式已填入，请先手动选择操作再计算。`;
    patchBlock(b.id, { blocked: msg, error: msg });
    statusText.value = msg;
    return;
  }
  if (wanted) {
    patchBlock(b.id, { mode: wanted, blocked: "", error: "" });
  }
  statusText.value = `已加载示例：${p.label || p.expr}`;
}

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
  // 被示例拦住的块：先让用户选对操作，不要用默认模式算出一个不相干的结果
  if (block.blocked) { patchBlock(block.id, { error: block.blocked }); return; }
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
  // 记历史：成功与失败都记（"上次那条报错的是什么"同样是要回看的信息）。
  // 摘要用 briefValue，历史面板里认的是结果而不是表达式本身。
  record({
    route: route.path,
    mode,
    expr,
    summary: result.isError ? String(result.value ?? "") : briefValue(result.value),
    ok: !result.isError,
  });
}

function specFnName(mode) {
  const s = ENGINE_MAP[mode];
  return s ? s.fn : "—";
}

function closeResult() { resultDialog.value = null; }

/**
 * 查看步骤 —— 现在真的做事了（本轮接上"AI 调引擎"这条线）。
 *
 * 为什么不是从引擎直接拿步骤：引擎信封里**没有 steps 字段**（已核对 api.cpp 与全部 *_api.cpp），
 * 自己编步骤就等于伪造推导。所以正确做法是：把这道题交给 AI，让它逐步调引擎，
 * 每一步的数值都由引擎给出（工具调用），面板再把那些调用按步骤排开。
 *
 * 用户的动作是"查看步骤"，那就别让他再点一次发送：这条请求会预填进面板并自动发出，
 * 收尾后面板自动弹出步骤视图。
 */
function onSteps() {
  const d = resultDialog.value;
  closeResult();
  if (!d) return;
  const expr = String(d.expr || d.input || "").trim();
  const lines = [
    "请**分步**讲解下面这道题，每一步都要用 engine_call 让本地引擎算出数值（不要自己心算）：",
    expr ? `题目：${expr}` : "",
    `当前模式：${d.mode || ""}${specFnName(d.mode) ? `（引擎函数 ${specFnName(d.mode)}）` : ""}`,
    "已知引擎给出的结果：见上下文；请把推导拆成可核对的步骤，每步标明用了哪个引擎函数与它的返回。",
  ].filter(Boolean);
  const r = requestAiTurn(lines.join("\n"), { autoSteps: true });
  if (r.ok) {
    statusText.value = "已请 AI 分步讲解（会调用 AI 服务；每一步的数值仍由本地引擎算出）";
  } else {
    statusText.value = `无法发起分步讲解：${r.error}`;
  }
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
                data-tour="calc_block.input"
                placeholder="输入表达式，如 x^2+3*x-1"
                @enter="calc(b)"
              />
              <select v-model="b.mode" class="select cb-mode" data-tour="calc_block.action_dropdown"
                      @change="patchBlock(b.id, { blocked: '', error: '' })">
                <option
                  v-for="m in modes"
                  :key="m"
                  :value="m"
                  :data-mapped="hasEngineMode(m)"
                  :data-var-dialog="needsVarDialog(m)"
                >{{ m }}{{ hasEngineMode(m) ? "" : "（未接入引擎）" }}</option>
              </select>
              <button class="btn btn-primary cb-calc" data-tour="calc_block.calc_button"
                      :disabled="b.computing" @click="calc(b)">
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
        <div class="cb-tools">
          <button v-if="!single" class="btn-add" @click="addBlock">＋ 添加计算</button>
          <button class="btn-add cb-undo" title="撤销（Ctrl+Z）" :disabled="!canUndo" @click="undo">↶ 撤销</button>
          <button class="btn-add cb-redo" title="重做（Ctrl+Y）" :disabled="!canRedo" @click="redo">↷ 重做</button>
        </div>
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

/* 底部一行按钮：添加计算（宽的）+ 撤销/重做（窄的）。
 * .btn-add 本身是"整条虚线栏"（width:100%、height:46px），放进 flex 行里要压高度，
 * 否则三个按钮会各占一整行。 */
.cb-tools { display: flex; gap: 8px; align-items: stretch; }
.cb-tools .btn-add { margin-top: 8px; height: 38px; }
.cb-tools .btn-add:first-child { flex: 1; }
.cb-tools .cb-undo,
.cb-tools .cb-redo { flex: none; width: auto; padding: 0 14px; }
.cb-tools .cb-undo:disabled,
.cb-tools .cb-redo:disabled { opacity: .45; cursor: default; }
.cb-tools .cb-undo:disabled:hover,
.cb-tools .cb-redo:disabled:hover {
  color: var(--text-subtle); border-color: var(--border-strong, var(--border)); background: transparent;
}
</style>
