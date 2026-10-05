<script setup>
/**
 * WelcomeDialog — 首次启动的欢迎窗（替代 v1 `MF_Tutorial/welcome_dialog.py`）
 *
 * 卡片文案**照抄 v1 的 `_WELCOME_CARDS`**（保留产品既有措辞），只改一处：
 * 第 4 张卡的"帮助文档中还有 30+ 示例任务"是写死的——实际示例有 52 条
 * （已清点），这里改成按真实数量计算，避免文案与内容对不上。
 *
 * 触发语义与 v1 一致：`welcomeSeen` 为假时弹一次；点"跳过"也算已弹过。
 * 另：v1 唯一的"重置"方式是删除进度文件，这里在设置里留了重置入口（见 store.resetAllProgress）。
 */
import { computed, ref } from "vue";
import { TUTORIALS } from "../../lib/tutorial/store.js";

const emit = defineEmits(["close", "start-tour"]);

const exampleCount = computed(() => TUTORIALS.reduce((n, t) => n + t.examples.length, 0));

const cards = computed(() => [
  {
    icon: "🧮",
    title: "欢迎使用 MF-Mathematics",
    description: "一款强大而优雅的数学工具，集成了<br><b>符号计算 · 函数绘图 · AI 助手</b><br>三大核心能力，覆盖 12 个数学分支。",
    features: [
      "📐 代数 · 微积分 · 线性代数 · 概率统计",
      "📊 2D/3D 绘图 · 复数着色 · 向量场 · 几何做图",
      "🤖 AI 步骤推导 · 会调引擎算的数学问答",
    ],
  },
  {
    icon: "⚡",
    title: "快速上手",
    description: "只需 3 步完成你的第一次数学计算：",
    features: [
      "① 在输入框中输入表达式，如 x² + 2x + 1",
      "② 在下拉菜单选择操作类型（化简/求导/积分…）",
      "③ 点击「计算」，查看结果和 AI 生成的推导步骤",
    ],
  },
  {
    icon: "🎨",
    title: "不只是计算",
    description: "MF-Mathematics 还能做更多：",
    features: [
      "📈 绘制精美函数图像，支持隐函数和参数方程",
      "🔍 联网搜索数学知识（DuckDuckGo + WolframAlpha）",
      "⌨️ 数学键盘，快速输入各种符号",
      "🌓 亮色/暗色主题自由切换",
    ],
  },
  {
    icon: "🚀",
    title: "准备好了吗？",
    description: "接下来，我们为你准备了一个<br><b>2 分钟的交互式引导</b>，<br>带你快速熟悉软件的核心操作。",
    features: [
      "💡 引导过程会高亮每个按钮和输入区域",
      "📖 随时从侧栏「帮助 → 使用教程」打开完整帮助文档",
      `🧪 教程里共有 ${exampleCount.value} 个示例任务等你探索`,
    ],
  },
]);

const index = ref(0);
const last = computed(() => index.value >= cards.value.length - 1);
const card = computed(() => cards.value[index.value]);

function next() {
  if (last.value) { emit("start-tour"); emit("close"); return; }
  index.value += 1;
}
function prev() { if (index.value > 0) index.value -= 1; }
</script>

<template>
  <div class="welcome-mask">
    <div class="welcome" role="dialog" aria-label="欢迎">
      <div class="w-icon">{{ card.icon }}</div>
      <h2 class="w-title">{{ card.title }}</h2>
      <p class="w-desc" v-html="card.description" />
      <ul class="w-feats">
        <li v-for="(f, i) in card.features" :key="i">{{ f }}</li>
      </ul>

      <div class="w-dots">
        <button v-for="(c, i) in cards" :key="i" class="w-dot" :class="{ on: i === index }"
                :title="c.title" @click="index = i" />
      </div>

      <div class="w-actions">
        <button class="wbtn ghost" @click="emit('close')">跳过</button>
        <span class="spacer" />
        <button class="wbtn" :disabled="index === 0" @click="prev">上一步</button>
        <button class="wbtn primary" @click="next">{{ last ? "开始引导 🚀" : "下一步" }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.welcome-mask {
  position: fixed; inset: 0; z-index: 4200;
  display: flex; align-items: center; justify-content: center;
  background: rgba(15, 23, 42, 0.42);
}
.welcome {
  width: 540px; max-width: calc(100vw - 40px);
  padding: 26px 28px 18px;
  border-radius: var(--r-md, 12px);
  background: var(--surface); color: var(--text);
  border: 1px solid var(--border);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.3);
}
.w-icon { font-size: 40px; line-height: 1; }
.w-title { margin: 10px 0 8px; font-size: 19px; }
.w-desc { margin: 0 0 14px; font-size: 13px; line-height: 1.75; color: var(--text-subtle, #475569); }
.w-feats { margin: 0 0 18px; padding-left: 18px; font-size: 13px; line-height: 1.9; }
.w-dots { display: flex; gap: 6px; justify-content: center; margin-bottom: 14px; }
.w-dot {
  width: 8px; height: 8px; padding: 0; border-radius: 4px; cursor: pointer;
  border: 1px solid var(--border); background: var(--surface-alt);
}
.w-dot.on { background: var(--accent, #3b82f6); border-color: var(--accent, #3b82f6); }
.w-actions { display: flex; align-items: center; gap: 8px; }
.spacer { flex: 1; }
.wbtn {
  font: inherit; font-size: 13px; padding: 6px 14px; cursor: pointer;
  border: 1px solid var(--border); border-radius: var(--r-sm, 6px);
  background: var(--surface-alt); color: var(--text);
}
.wbtn:disabled { opacity: .45; cursor: default; }
.wbtn.ghost { background: transparent; }
.wbtn.primary { background: var(--accent, #3b82f6); border-color: var(--accent, #3b82f6); color: #fff; }
</style>
