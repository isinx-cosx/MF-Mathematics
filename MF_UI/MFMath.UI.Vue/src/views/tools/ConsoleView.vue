<!--
  ConsoleView.vue — 控制台（/tools/console）

  定位：给**普通用户**写小程序/试算用的控制台，两门语言：
    · Python —— 走嵌入式 CPython（可选组件），通过 mfmath 调 C++ 引擎
    · C++    —— 走 MinGW A 档（可选组件），直接链接引擎 DLL

  两条硬约定（见项目设计）：
    1. **计算仍由 C++ 引擎完成**：Python 侧只有 mfmath（ctypes 封装），C++ 侧只有导入库，
       界面自己不算任何数学。
    2. **C++ 默认隐藏**：组件没装好之前，语言下拉里不出现 C++，装上后自动出现。
-->
<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from "vue";
import { useRoute } from "vue-router";
import {
  isConsoleHosted, components, installComponent, installStatus, cancelInstall, setDownloadBase,
  consoleStart, consolePoll, consoleStop,
} from "../../lib/console/bridge.js";
// 取引擎函数表（list_functions）作为补全候选
import { engineCall } from "../../lib/bridge.js";
import { initPush, onPush, isPushHosted } from "../../lib/push.js";
import { getPage, setPage } from "../../lib/workspace/store.js";
import CodeEditor from "../../components/console/CodeEditor.vue";

const hosted = isConsoleHosted();
const route = useRoute();
const comps = ref(null);
const lang = ref("python");
const code = ref("");
// 引擎函数名候选：控制台的核心用法就是调引擎那 400 多个函数，用户不可能背下来。
// 引擎的 list_functions 早就有，之前一直没被调用过 —— C++ 模式更是一个候选都没有
// （@codemirror/lang-cpp 的 languageData 里根本没有 autocomplete）。
const fnNames = ref([]);
const CPP_API = ["mfm::num", "mfm::text", "mfm::call", "mfm::call_raw",
                 "mfm::exists", "mfm::functions", "mfm::Error", "mfm::Json"];
const candidates = computed(() =>
  lang.value === "cpp" ? [...CPP_API, ...fnNames.value] : fnNames.value);
const stdin = ref("");
const out = ref("");
const err = ref("");
const running = ref(false);
const exitCode = ref(null);
const elapsedMs = ref(0);
const truncated = ref(false);
const status = ref(hosted ? "就绪" : "浏览器预览：无宿主桥，控制台不可用");
const installJob = ref(null);
const installPct = ref(0);
const installMsg = ref("");

let runId = null;
let pollTimer = null;
let offPush = null;

/** 语言选项：C++ 只在组件**装好且可用**之后出现（默认隐藏）。
 *  用 ready 而不是 installed：工具链解压到一半、或缺导入库/门面头文件时，
 *  让 C++ 出现在下拉里只会让用户点了报错。 */
const languages = computed(() => {
  const list = [{ value: "python", label: "Python" }];
  if (comps.value?.cpp?.ready) list.push({ value: "cpp", label: "C++" });
  return list;
});

const pythonReady = computed(() => !!comps.value?.python?.installed);
const pythonPayload = computed(() => !!comps.value?.python?.payloadAvailable);
const cppReady = computed(() => !!comps.value?.cpp?.ready);
/** C++ 组件状态文案：装了一半（缺导入库/门面头文件）要说清楚，别让用户以为能用 */
const cppStatusText = computed(() => {
  const c = comps.value?.cpp;
  if (!c) return "";
  if (c.ready) return "已安装（" + Math.round((c.bytes || 0) / 1048576) + " MB），语言里已出现 C++";
  if (c.installed) return c.warning || "已安装但不完整，请重新安装";
  return payloadText(c);
});

/**
 * 未安装时的说明：要下多大、从哪来、上次是不是下到一半。
 * 「可选组件」如果只写一句"未安装"，用户根本不知道点下去会发生什么（要下 54 MB？）。
 */
function payloadText(c) {
  const mb = Math.round((c.payloadBytes || 0) / 1048576);
  if (c.payloadAvailable) return "未安装（组件包已在本地，约 " + mb + " MB，点安装即可）";
  if (c.payloadPartial) return "未安装（上次只下到 " + mb + " MB，点安装会接着下）";
  return "未安装（点安装会从官网下载约 " + Math.round((c.expectBytes || 0) / 1048576) + " MB）";
}

async function doCancelInstall() {
  if (!installJob.value) return;
  cancelInstall(installJob.value);
  installMsg.value = "正在取消…";
}
const stage = ref("");        // queued | compiling | running | done
const compileMs = ref(null);  // C++ 专有：编译耗时

const SAMPLES = {
  python: [
    {
      name: "调引擎：求导 / 求值",
      code: [
        "import mfmath",
        "",
        "# 引擎算，Python 只负责组织与打印",
        "print('x^2 在 x=3 处 =', mfmath.call('expr_eval', expr='x^2', x=3))",
        "print('d/dx (x e^x) =', mfmath.call('diff', expr='xe^x', var='x'))",
        "print('lim (1+1/x)^x (x→∞) =', mfmath.call('limit', expr='(1+1/x)^x', var='x', point='oo'))",
      ].join("\n"),
    },
    {
      name: "循环 + 用引擎批量求值",
      code: [
        "import mfmath",
        "",
        "# 例：把 f(x)=x^2-4 的零点扫出来（每一步都问引擎要值）",
        "def f(x):",
        "    return mfmath.call('expr_eval', expr='x^2-4', x=x)",
        "",
        "prev = None",
        "for i in range(-40, 41):",
        "    x = i / 10",
        "    y = f(x)",
        "    if prev is not None and y * prev[1] < 0:",
        "        print('符号变化在 [%.1f, %.1f] 之间 → 有根' % (prev[0], x))",
        "    prev = (x, y)",
      ].join("\n"),
    },
    {
      name: "函数 + 条件 + 错误处理",
      code: [
        "import mfmath",
        "",
        "def safe(fn, **kw):",
        "    \"\"\"引擎报错时给出可读提示，而不是让整段脚本崩掉\"\"\"",
        "    try:",
        "        return mfmath.call(fn, **kw)",
        "    except mfmath.EngineError as e:",
        "        return '引擎拒绝：' + str(e)",
        "",
        "print(safe('factor_sym', expr='x^2-1'))",
        "print(safe('diff', expr='sin(', var='x'))",
      ].join("\n"),
    },
  ],
  cpp: [
    {
      name: "调引擎：求值 / 求导 / 极限",
      code: [
        '#include "mfmath.hpp"',
        '#include <iostream>',
        '',
        '// 计算全部落在引擎 DLL 里，这里只负责组织参数与打印（和 Python 侧同一个 C ABI）',
        'int main() {',
        '    std::cout << "x^2 在 x=3 处 = "',
        '              << mfm::num("expr_eval", {{"expr", "x^2"}, {"x", 3}}) << "\\n";',
        '    std::cout << "d/dx (x e^x) = "',
        '              << mfm::text("diff", {{"expr", "xe^x"}, {"var", "x"}}) << "\\n";',
        '    std::cout << "lim (1+1/x)^x (x→∞) = "',
        '              << mfm::text("limit", {{"expr", "(1+1/x)^x"}, {"var", "x"}, {"point", "oo"}})',
        '              << "\\n";',
        '    return 0;',
        '}',
      ].join('\n'),
    },
    {
      name: "循环 + 用引擎逐点求值",
      code: [
        '#include "mfmath.hpp"',
        '#include <iostream>',
        '',
        '// 扫 f(x)=x^2-4 的零点：每一步都问引擎要值，绝不在 C++ 里自己实现数学',
        'int main() {',
        '    double prevX = 0, prevY = 0;',
        '    bool has = false;',
        '    for (int i = -40; i <= 40; ++i) {',
        '        double x = i / 10.0;',
        '        double y = mfm::num("expr_eval", {{"expr", "x^2-4"}, {"x", x}});',
        '        if (has && prevY * y < 0)',
        '            std::cout << "符号变化在 [" << prevX << ", " << x << "] 之间 → 有根\\n";',
        '        prevX = x; prevY = y; has = true;',
        '    }',
        '    return 0;',
        '}',
      ].join('\n'),
    },
    {
      name: "错误处理：引擎报错必须看得见",
      code: [
        '#include "mfmath.hpp"',
        '#include <iostream>',
        '',
        '// 引擎报错会抛 mfm::Error。不接住的话标准库直接 std::terminate，',
        '// 只留一句 terminate，看不到原因。',
        'int main() {',
        '    try {',
        '        std::cout << mfm::text("diff", {{"expr", "sin("}, {"var", "x"}}) << "\\n";',
        '    } catch (const mfm::Error& e) {',
        '        std::cout << "引擎拒绝：" << e.what() << "\\n";',
        '    }',
        '',
        '    // 想自己判错、不要异常的用 call_raw',
        '    mfm::Json raw = mfm::call_raw("expr_eval", {{"expr", "x^^2"}, {"x", 1}});',
        '    std::cout << "isError = " << (raw["isError"].as_bool() ? "true" : "false")',
        '              << "，说明：" << raw["value"].dump() << "\\n";',
        '    return 0;',
        '}',
      ].join('\n'),
    },
  ],
};

function loadSample(index = 0) {
  const list = SAMPLES[lang.value] || [];
  if (list[index]) code.value = list[index].code;
}

async function refreshComponents() {
  if (!hosted) return;
  comps.value = components();
  if (!pythonReady.value) status.value = "还没安装 Python 组件（点右侧「安装」）";
  else status.value = "组件就绪";
}

async function doInstall(which) {
  if (!hosted) return;
  installJob.value = installComponent(which);
  installMsg.value = "开始安装…";
  installPct.value = 0;
  const tick = setInterval(async () => {
    const s = installStatus(installJob.value);
    if (s) {
      installPct.value = s.percent || 0;
      installMsg.value = s.message || "";
      if (s.state !== "running") {
        clearInterval(tick);
        installJob.value = null;
        await refreshComponents();
        if (s.state === "error") status.value = "安装失败：" + (s.message || "");
        else { status.value = s.message || "安装完成"; if (!languages.value.some((l) => l.value === lang.value)) lang.value = "python"; }
      }
    }
  }, 400);
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

async function run() {
  if (!hosted || running.value) return;
  if (!code.value.trim()) { status.value = "先写点代码吧"; return; }
  if (lang.value === "python" && !pythonReady.value) { status.value = "需要先安装 Python 组件"; return; }
  if (lang.value === "cpp" && !cppReady.value) { status.value = "需要先安装 C++ 组件"; return; }
  out.value = ""; err.value = ""; exitCode.value = null; elapsedMs.value = 0; truncated.value = false;
  compileMs.value = null; stage.value = "queued";
  runId = consoleStart(lang.value, code.value, stdin.value);
  if (!runId) { status.value = "启动失败：桥不可用"; return; }
  running.value = true;
  status.value = "运行中…";
  stopPolling();
  // 推送负责"及时"：宿主在阶段变化（编译/运行）与结束时会主动推 console.run，
  // 收到就立刻拉一次权威状态。轮询退成 500ms 兜底 —— 推送丢一条也不会卡住界面。
  pollTimer = setInterval(tick, isPushHosted() ? 500 : 200);
}

/** 拉一次权威状态（Poll）。推送只是"叫你去看"，数据永远来自这里。 */
function tick() {
  const s = consolePoll(runId);
  if (!s) return;
  out.value = s.stdout || "";
  err.value = s.stderr || "";
  elapsedMs.value = s.elapsedMs || 0;
  truncated.value = !!s.truncated;
  stage.value = s.stage || "";
  // C++ 的编译耗时单独显示：总耗时里混着编译会让人以为程序跑得慢
  if (typeof s.compileMs === "number") compileMs.value = s.compileMs;
  if (!s.running) {
    stopPolling();
    running.value = false;
    exitCode.value = s.exitCode;
    status.value = s.timedOut
      ? "超时已终止"
      : (s.exitCode === 0 ? "运行结束" : (stage.value === "compiling" || compileMs.value !== null ? "编译失败" : "运行结束（有错误）"));
  } else if (s.stage === "compiling") {
    status.value = "正在编译…";
  } else if (s.stage === "running") {
    status.value = "运行中…";
  }
}

function clearOutput() {
  out.value = ""; err.value = ""; exitCode.value = null; elapsedMs.value = 0;
  compileMs.value = null; truncated.value = false; status.value = "已清空输出";
}

/** 重置：清输出 + 回到示例代码（原版有个「重置」按钮，Vue 侧一直没有入口） */
function resetAll() {
  clearOutput();
  loadSample(0);
  status.value = "已重置（代码回到示例）";
}

function stop() {
  if (!runId) return;
  consoleStop(runId);
  stopPolling();
  running.value = false;
  status.value = "已手动终止";
}

// Tab 缩进与 Ctrl+Enter 运行现在由编辑器内核负责（见 components/console/CodeEditor.vue）：
// CodeMirror 的 keymap 比在 textarea 上手工搬光标可靠得多（撤销栈、多光标都能正确处理）。

onMounted(async () => {
  await refreshComponents();
  // 工作区还原优先：存过的代码/语言就用它，否则才回到示例
  const saved = getPage(route.path);
  if (saved && saved.kind === "console" && typeof saved.code === "string" && saved.code.trim()) {
    lang.value = ["python", "cpp"].includes(saved.lang) ? saved.lang : "python";
    code.value = saved.code;
    if (typeof saved.stdin === "string") stdin.value = saved.stdin;
    status.value = "已从工作区还原";
  } else {
    loadSample(0);
  }
  syncWorkspace = true;
  // 推送：宿主在编译/运行阶段切换与结束时主动通知，收到就立刻 tick 一次
  initPush();
  offPush = onPush("console.run", (env) => {
    const p = env?.payload;
    if (!p || p.runId !== runId) return;      // 只关心本次运行
    if (p.stage === "compiling") status.value = "正在编译…";
    else if (p.stage === "running") status.value = "运行中…";
    tick();
  });
  // 函数表只在进页面时取一次（引擎函数是固定的）
  if (hosted) {
    const r = engineCall("list_functions", {});
    const v = r && !r.isError ? r.value : null;
    const list = Array.isArray(v) ? v : (v && Array.isArray(v.functions) ? v.functions : []);
    fnNames.value = list.map((s) => String(s));
  }
});
onBeforeUnmount(() => {
  stopPolling();
  if (offPush) offPush();
});

/* 工作区：控制台存的是"语言 + 代码 + 标准输入"，不存运行结果 */
let syncWorkspace = false;
watch([lang, code, stdin], () => {
  if (syncWorkspace) setPage(route.path, { kind: "console", lang: lang.value, code: code.value, stdin: stdin.value });
}, { deep: true });
</script>

<template>
  <div class="console-wrap">
    <div class="ws-title">控制台</div>
    <div class="ws-desc">
      在应用里直接写小程序试算：Python 与 C++ 都能调同一套 C++ 引擎（<code class="mono">mfmath</code>）。
      语言运行时是可选的独立组件，不需要时不下载，主程序体积不受影响。
    </div>

    <div class="layout">
      <!-- 左：编辑区 -->
      <div class="pane">
        <div class="bar">
          <select v-model="lang" class="input lang" @change="loadSample(0)">
            <option v-for="l in languages" :key="l.value" :value="l.value">{{ l.label }}</option>
          </select>
          <select class="input sample" @change="loadSample($event.target.selectedIndex)">
            <option v-for="(s, i) in (SAMPLES[lang] || [])" :key="i">{{ s.name }}</option>
          </select>
          <span class="spacer"></span>
          <button v-if="!running" class="btn btn-primary" :disabled="!hosted" @click="run">运行 ▷</button>
          <button v-else class="btn btn-danger" @click="stop">终止 ■</button>
          <button class="btn btn-ghost" title="只清空下面的输出" @click="clearOutput">清空输出</button>
          <button class="btn btn-ghost" title="清空输出并回到示例代码" @click="resetAll">重置</button>
        </div>

        <!-- 代码编辑区：CodeMirror 6（进控制台才加载，语法包按语言再单独加载）
             Ctrl/Cmd+Enter 由编辑器内核转发成 run 事件 -->
        <CodeEditor v-model="code" :language="lang" :candidates="candidates" @run="run"
                    placeholder="在这里写代码（Ctrl+Enter 运行，Ctrl+Space 补全引擎函数）" />

        <!-- 会话态说明：宿主每次运行都起新进程，这一点必须让用户知道，
             否则他会以为"上次算出的 a 这次还能用"（原版 PyQt 是同进程持久命名空间） -->
        <p class="hint">
          每次「运行」都是新进程：变量不跨次保留（上一次算出的 a 这一次用不了）。
          要接着算就把整段写成一次运行的代码。Ctrl+Space 可按引擎函数名补全。
        </p>
        <div class="row">
          <label class="lbl">标准输入（可选）</label>
          <input v-model="stdin" class="input mono stdin" placeholder="每行一个输入，运行时会喂给程序" />
        </div>
      </div>

      <!-- 右：输出 + 组件 -->
      <div class="pane">
        <div class="bar">
          <span class="badge" :class="{ ok: exitCode === 0, bad: exitCode !== null && exitCode !== 0 }">
            {{ exitCode === null ? "未运行" : "退出码 " + exitCode }}
          </span>
          <span class="meta">{{ elapsedMs }} ms</span>
          <!-- C++ 多一个编译阶段：单独列出来，免得用户以为程序跑得慢 -->
          <span v-if="compileMs !== null" class="meta">编译 {{ compileMs }} ms</span>
          <span v-if="truncated" class="meta warn">输出已截断</span>
          <span class="spacer"></span>
          <span class="meta">{{ status }}</span>
        </div>

        <div class="io">
          <div class="io-title">输出</div>
          <pre class="out mono">{{ out || "（还没有输出）" }}</pre>
        </div>
        <div class="io" v-if="err">
          <div class="io-title bad">错误</div>
          <pre class="out mono err">{{ err }}</pre>
        </div>

        <div class="comps">
          <div class="io-title">组件</div>
          <div class="comp-row">
            <span>Python {{ comps?.python?.version || "" }}</span>
            <span class="meta">{{ comps?.python?.installed ? "已安装（" + Math.round((comps.python.bytes || 0) / 1048576) + " MB）" : payloadText(comps?.python || {}) }}</span>
            <button class="btn btn-ghost" :disabled="!hosted || installJob !== null || comps?.python?.installed" @click="doInstall('python')">
              {{ comps?.python?.installed ? "已装" : "安装" }}
            </button>
          </div>
          <div class="comp-row">
            <span>C++（MinGW A 档）{{ comps?.cpp?.version || "" }}</span>
            <span class="meta">{{ cppStatusText }}</span>
            <button class="btn btn-ghost" :disabled="!hosted || installJob !== null || comps?.cpp?.ready" @click="doInstall('cpp')">
              {{ comps?.cpp?.ready ? "已装" : "安装" }}
            </button>
          </div>
          <!-- 安装中：进度 + 取消。下载 54 MB 可能要几分钟，没有取消按钮等于把用户锁住；
               取消后已下载的部分会保留（.part），下次点安装接着下。 -->
          <div v-if="installJob" class="progress">
            <div class="progress-bar" :style="{ width: installPct + '%' }"></div>
            <span class="progress-txt">{{ installPct }}% {{ installMsg }}</span>
            <button class="btn btn-ghost progress-cancel" @click="doCancelInstall">取消</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.console-wrap { padding: 4px 2px 12px; }
.layout { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 1100px) { .layout { grid-template-columns: 1fr; } }
.pane { display: flex; flex-direction: column; gap: 8px; }
.bar { display: flex; align-items: center; gap: 8px; }
.spacer { flex: 1; }
.input.lang, .input.sample { width: auto; padding: 6px 8px; }
/* 编辑区的外框样式归 components/console/CodeEditor.vue 管：它要同时伺候
   CodeMirror 与 textarea 回退两条路，而 `.editor` 是那个组件的内部节点，
   本组件的 scoped 样式够不到它（父组件的 scope id 只加在子组件根节点上）。 */
.row { display: flex; align-items: center; gap: 8px; }
.hint { font-size: 11px; color: var(--text-subtle); line-height: 1.6; margin: 2px 0 6px; }
.lbl { font-size: 12.5px; color: var(--text-muted); white-space: nowrap; }
.stdin { flex: 1; height: 30px; }
.badge { font-size: 12px; padding: 2px 8px; border-radius: 999px; background: var(--surface-alt); color: var(--text-muted); }
.badge.ok { background: #dcfce7; color: #166534; }
.badge.bad { background: var(--danger-soft); color: var(--danger); }
.meta { font-size: 12px; color: var(--text-subtle); }
.meta.warn { color: var(--danger); }
.io { display: flex; flex-direction: column; gap: 4px; }
.io-title { font-size: 12.5px; font-weight: 600; color: var(--text-muted); }
.io-title.bad { color: var(--danger); }
.out {
  margin: 0; min-height: 120px; max-height: 320px; overflow: auto;
  padding: 10px 12px; font-size: 12.5px; line-height: 1.55;
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-md);
  white-space: pre-wrap; word-break: break-word;
}
.out.err { color: var(--danger); }
.comps { display: flex; flex-direction: column; gap: 6px; margin-top: 4px; }
.comp-row { display: flex; align-items: center; gap: 10px; font-size: 12.5px; }
.comp-row .meta { flex: 1; }
.progress { position: relative; height: 20px; background: var(--surface-alt); border-radius: var(--r-sm); overflow: hidden; }
.progress-bar { height: 100%; background: var(--grad); transition: width .2s; }
.progress-txt { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 11.5px; color: var(--text); }
/* 取消按钮浮在进度条右端：进度条本身只有 20px 高，按钮要压住它才点得到 */
.progress-cancel {
  position: absolute; right: 2px; top: 1px; height: 18px;
  padding: 0 8px; font-size: 11px; z-index: 2;
}
</style>
