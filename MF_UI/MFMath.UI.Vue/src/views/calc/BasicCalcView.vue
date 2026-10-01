<script setup>
/**
 * BasicCalcView — 基础运算（计算器）
 *
 * 旧版是个空壳：30 个键，按 `=` 只弹"计算功能待接入引擎"。
 * 这一版**真的算**——所有求值都经 C++ 引擎（expr_eval），界面只负责拼表达式：
 *
 *   按键 → 显示串（课本写法：× ÷ − √ π）→ prepare_expr 规范化成引擎语法
 *        → expr_eval 求值 → 显示结果
 *
 * 顺带把"引擎理解为 …"显示出来：`2×(3+4)` 会被规范化成 `2*(3+4)`，
 * 用户能立刻看出自己写的式子被理解成了什么（这也是引擎侧隐式乘法规范的可见收益）。
 */
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from "vue";
import { prepareExpr } from "../../lib/plot/prepare.js";
import { engineCall, isHosted } from "../../lib/bridge.js";
import { fmtNum } from "../../lib/engine/resultFormat.js";

/* ── 键盘布局（沿用旧版 30 键、5 列，值用课本写法）── */
const KEYS = [
  { t: "C", c: "ctrl" }, { t: "⌫", c: "ctrl" }, { t: "(", c: "paren" }, { t: ")", c: "paren" }, { t: "÷", c: "op" },
  { t: "7", c: "num" }, { t: "8", c: "num" }, { t: "9", c: "num" }, { t: "×", c: "op" }, { t: "x²", c: "func" },
  { t: "4", c: "num" }, { t: "5", c: "num" }, { t: "6", c: "num" }, { t: "−", c: "op" }, { t: "√", c: "func" },
  { t: "1", c: "num" }, { t: "2", c: "num" }, { t: "3", c: "num" }, { t: "+", c: "op" }, { t: "n!", c: "func" },
  { t: "0", c: "num" }, { t: ".", c: "num" }, { t: "±", c: "func" }, { t: "=", c: "eq" }, { t: "1/x", c: "func" },
  { t: "π", c: "const" }, { t: "e", c: "const" }, { t: "xʸ", c: "func" }, { t: "log", c: "func" }, { t: "ln", c: "func" },
];

const display = ref("");      // 课本写法（用户看到的）＝原版的 _expr
/**
 * 大号行显示的内容 ＝ 原版的 _current（**当前操作数**）。
 * 原版的规则（calculator.py:156-184）：
 *   · 打数字/小数点/括号 → 累加当前操作数
 *   · 按运算符          → 清空并把运算符显示在大号行
 *   · 按函数（√ n! xʸ 等）→ 清空并把函数名显示在大号行
 *   · 按 =             → 显示结果
 * 之前这一行直接绑 result，而 result 只在求值时写 → 按 7+8 全程显示 0（真 bug）。
 */
const current = ref("0");
const evaluated = ref(false);  // 求值后表达式行追加 " ="（原版 :235）
// 原版用"把 _current 清成空串"来表达"下一个数字要新起一个操作数"；
// 这里大号行在按运算符时要显示运算符本身，所以用标志位表达同一语义，
// 否则按 + 再按 8 会拼成 "+8"（实测踩过）。
let operandFresh = true;
const result = ref("0");      // 结果（数字，或错误信息）
const error = ref("");        // 引擎报错
const history = ref([]);      // 最近计算

const hosted = isHosted();
const preview = computed(() => (display.value.trim() ? prepareExpr(display.value) : null));
/** 引擎语法（规范化后的写法），用于"理解为"与求值 */
const engineExpr = computed(() => preview.value?.normalized || display.value);

const OP_LABELS = ["+", "−", "×", "÷"];
const FUNC_LABELS = ["x²", "xʸ", "√", "n!", "log", "ln", "π", "e"];

/** 按一个键 */
function press(label) {
  error.value = "";
  evaluated.value = false;
  if (label === "C") { display.value = ""; current.value = "0"; result.value = "0"; operandFresh = true; return; }
  if (label === "⌫") {
    display.value = display.value.slice(0, -1);
    current.value = current.value.length > 1 ? current.value.slice(0, -1) : "0";
    operandFresh = false;
    return;
  }
  if (label === "=") { evaluate(); return; }
  if (label === "±") {
    // 整体取反：有最外层括号就脱掉，否则套一层
    const s = display.value.trim();
    if (!s) return;
    display.value = /^-\((.*)\)$/.test(s) ? s.slice(2, -1) : `-(${s})`;
    return;
  }
  if (label === "1/x") {
    // 整个当前表达式取倒数
    const s = display.value.trim();
    if (!s) return;
    display.value = `1/(${s})`;
    return;
  }
  // 运算符：大号行显示运算符本身（原版行为），当前操作数归零
  if (OP_LABELS.includes(label)) {
    display.value += label;
    current.value = label;
    result.value = label;
    operandFresh = true;
    return;
  }
  // 函数：大号行显示函数名（原版行为）
  if (FUNC_LABELS.includes(label)) {
    const text = { "x²": "^2", "xʸ": "^", "√": "√(", "n!": "!", "log": "log10(", "ln": "ln(", "π": "π", "e": "e" }[label];
    display.value += text;
    current.value = label;
    result.value = label;
    operandFresh = true;
    return;
  }
  // 数字 / 小数点 / 括号：累加当前操作数
  display.value += label;
  current.value = operandFresh || current.value === "0" ? label : current.value + label;
  operandFresh = false;
  result.value = current.value;
}

/**
 * 补齐缺少的右括号。
 * 原版在按 = 时会自动补（calculator.py:226-227），而且 √、( 这些键本身只输入左括号，
 * 所以不补的话 `√(9` 直接报「缺少右括号 ')' (位置 6)」——用户按了 √ 再按 9 就得不到结果。
 */
function closeParens(s) {
  let depth = 0;
  for (const ch of s) {
    if (ch === "(") depth++;
    else if (ch === ")") depth = Math.max(0, depth - 1);
  }
  return s + ")".repeat(depth);
}

/** 求值：引擎语法 → expr_eval */
function evaluate() {
  const raw = closeParens(display.value.trim());
  if (!raw) return;
  if (raw !== display.value.trim()) display.value = raw;   // 补上的括号也要看得见
  const p = prepareExpr(raw);
  if (!p.ok) { error.value = p.error || "表达式无法解析"; result.value = "—"; current.value = "0"; return; }
  const expr = p.normalized;
  const r = engineCall("expr_eval", { expr, x: 0 });
  if (r === null) { error.value = "未连接引擎（请在 MFMath.exe 中运行）"; result.value = "—"; current.value = "0"; return; }
  if (r.isError) { error.value = String(r.value); result.value = "—"; current.value = "0"; return; }
  const v = r.value;
  const text = typeof v === "number" ? fmtNum(v) : String(v);
  result.value = text;
  current.value = text;          // 原版：= 之后大号行显示结果，_current 也设成结果
  operandFresh = true;
  evaluated.value = true;        // 表达式行追加 " ="
  error.value = "";
  history.value = [{ display: raw, expr, value: text }, ...history.value].slice(0, 8);
}

/** 键盘输入 */
function onKeydown(e) {
  const k = e.key;
  if (/^[0-9.]$/.test(k)) { press(k); e.preventDefault(); return; }
  if (["+", "-", "*", "/", "(", ")", "^", "!"].includes(k)) {
    press({ "-": "−", "*": "×", "/": "÷" }[k] ?? k);
    e.preventDefault();
    return;
  }
  if (k === "Enter" || k === "=") { evaluate(); e.preventDefault(); return; }
  if (k === "Backspace") { press("⌫"); e.preventDefault(); return; }
  if (k === "Delete" || k === "Escape") { press("C"); e.preventDefault(); return; }
}

onMounted(() => window.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));

function reuse(h) { display.value = h.display; result.value = h.value; current.value = h.value; evaluated.value = false; error.value = ""; }
const lcdRef = ref(null);
async function clearHistory() { history.value = []; await nextTick(); lcdRef.value?.focus?.(); }
</script>

<template>
  <div class="view-body">
    <div class="calc-wrap">
      <div class="ws-title">基础运算</div>
      <div class="ws-desc">计算器风格的基础数学运算 — 四则运算 · 乘方 · 开方 · 阶乘 · 三角函数 · 对数（全部经 C++ 引擎求值）</div>

      <div class="work-card">
        <div class="lcd" ref="lcdRef" tabindex="-1">
          <div class="lcd-expr">{{ display }}{{ evaluated ? " =" : "" }}</div>
          <!-- 大号行 ＝ 当前操作数（原版 _current），不是 last result -->
          <div class="lcd-result" :class="{ 'is-error': !!error }">{{ error ? "错误" : current || "0" }}</div>
        </div>

        <!-- 引擎把课本写法理解成了什么（隐式乘法/√/π 等规范化结果） -->
        <div class="calc-note">
          <template v-if="error">
            <span class="calc-err">{{ error }}</span>
          </template>
          <template v-else-if="display.trim() && engineExpr !== display.trim()">
            引擎理解为 <code>{{ engineExpr }}</code>
          </template>
          <template v-else-if="!hosted">
            浏览器预览模式：未连接引擎，无法求值
          </template>
          <template v-else>
            支持键盘输入：数字 · + − * / ( ) ^ ! · Enter 求值 · Backspace 退格 · Esc 清空
          </template>
        </div>

        <div class="keypad">
          <button
            v-for="k in KEYS"
            :key="k.t"
            class="key"
            :class="`key-${k.c}`"
            :data-key="k.t"
            @click="press(k.t)"
          >{{ k.t }}</button>
        </div>

        <div v-if="history.length" class="calc-history">
          <div class="calc-history-head">
            <span>最近计算</span>
            <button class="link-btn" @click="clearHistory">清空</button>
          </div>
          <button
            v-for="(h, i) in history"
            :key="i"
            class="calc-history-row"
            :title="`点击重新输入：${h.expr}`"
            @click="reuse(h)"
          >
            <span class="ch-expr">{{ h.display }}</span>
            <span class="ch-eq">=</span>
            <span class="ch-val">{{ h.value }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.calc-note {
  margin: -4px 2px 10px;
  font-size: 12px;
  color: var(--text-subtle);
  min-height: 18px;
}
.calc-note code {
  font-family: 'Cascadia Code', 'Consolas', monospace;
  color: var(--text-muted);
  background: var(--surface-alt);
  padding: 1px 5px;
  border-radius: 4px;
}
.calc-err { color: var(--danger); }
.lcd-result.is-error { font-size: 20px; color: var(--danger); }

.calc-history { margin-top: 12px; border-top: 1px solid var(--border); padding-top: 8px; }
.calc-history-head {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 11.5px; color: var(--text-subtle); margin-bottom: 4px;
}
.calc-history-row {
  display: flex; gap: 8px; align-items: baseline; width: 100%;
  background: none; border: none; cursor: pointer; text-align: left;
  padding: 4px 6px; border-radius: var(--r-sm);
  font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 13px;
  color: var(--text);
}
.calc-history-row:hover { background: var(--surface-alt); }
.ch-expr { color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ch-eq { color: var(--text-subtle); }
.ch-val { color: var(--accent); font-weight: 600; margin-left: auto; }
</style>
