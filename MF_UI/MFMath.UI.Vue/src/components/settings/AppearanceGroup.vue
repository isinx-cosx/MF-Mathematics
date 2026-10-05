<script setup>
/**
 * 设置 · 外观分组
 *
 * 复用既有的四维外观系统（配色 10 套 + 形状 / 疏密 / 字体），本组件只提供**入口**。
 * 与 v1 的差别：v1 是"点一下按钮循环到下一套配色"，看不出差别也回不去；
 * 这里是网格预览卡 —— 每张卡自带 data-theme，卡内用的是那套主题的真实 CSS 变量，
 * 所以预览永远与实际一致（不是截图，不会过期）。
 *
 * 交互约定（按设置面板的设计要求）：**改了就生效，没有"保存"按钮**，
 * 只提供"恢复默认"。
 */
import { ref, computed } from "vue";
import {
  THEME_LIST, SHAPE_LIST, DENSITY_LIST, FONT_LIST,
  currentAppearance, applyAppearance,
} from "../../lib/bridge.js";
// 界面语言（i18n）的入口就放在"外观"这一组：它和主题/字体一样属于"界面长什么样"，
// 而且这里本来就有分段控件的样式可复用。切换立即生效、并记住选择（见 lib/i18n/index.js）。
import { LOCALES, locale, setLocale, t } from "../../lib/i18n/index.js";

const ap = ref(currentAppearance());

function patch(p) {
  applyAppearance(p);
  ap.value = currentAppearance();
}

const mode = computed(() => (ap.value.followSystem ? "system" : (THEME_LIST.find((t) => t.id === ap.value.theme)?.mode || "light")));

/** 主题模式三选一：亮 / 暗 / 跟随系统。
 *  "亮/暗"要落到**同一配色家族**的对应深浅版本（例如从"液态玻璃·浅"切到"液态玻璃·深"），
 *  而不是跳到一个不相干的主题——否则用户只想换深浅，配色却被换掉了。 */
function pickMode(next) {
  if (next === "system") { patch({ followSystem: true }); return; }
  const cur = THEME_LIST.find((t) => t.id === ap.value.theme);
  const sib = THEME_LIST.find((t) => t.family === cur?.family && t.mode === next)
    || THEME_LIST.find((t) => t.mode === next);
  patch({ theme: sib ? sib.id : ap.value.theme, followSystem: false });
}

/** 恢复默认：四个维度的默认值与 lib/bridge.js 里的 DEFAULT_* 一致 */
function resetAll() {
  patch({ theme: "glass-light", shape: "glass", density: "cozy", font: "sans", followSystem: false });
}
</script>

<template>
  <section>
    <div class="s-row" data-setting="appearance.language">
      <div class="s-label">
        <label>{{ t('界面语言') }}</label>
        <p class="s-hint">{{ t('语言只影响界面文字，计算与结果表示方式不变。') }}</p>
      </div>
      <div class="s-ctl seg">
        <button v-for="l in LOCALES" :key="l.id" :class="{ on: locale === l.id }"
                @click="setLocale(l.id)">{{ l.label }}</button>
      </div>
    </div>

    <div class="s-row" data-setting="appearance.mode">
      <div class="s-label">
        <label>主题模式</label>
        <p class="s-hint">亮 / 暗会切到**同一配色家族**的深浅版本，不会换掉你选的配色</p>
      </div>
      <div class="s-ctl seg">
        <button :class="{ on: mode === 'light' }" @click="pickMode('light')">☀ 亮</button>
        <button :class="{ on: mode === 'dark' }" @click="pickMode('dark')">🌙 暗</button>
        <button :class="{ on: mode === 'system' }" @click="pickMode('system')">🖥 跟随系统</button>
      </div>
    </div>

    <div class="s-row col" data-setting="appearance.theme">
      <div class="s-label"><label>配色方案</label><p class="s-hint">共 {{ THEME_LIST.length }} 套，卡片内就是该主题的真实变量</p></div>
      <div class="theme-grid">
        <button v-for="t in THEME_LIST" :key="t.id" class="theme-card"
                :data-theme="t.id" :data-shape="ap.shape"
                :class="{ on: ap.theme === t.id }" :title="t.desc"
                @click="patch({ theme: t.id, followSystem: false })">
          <span class="tc-preview">
            <span class="tc-side" />
            <span class="tc-body">
              <span class="tc-line" />
              <span class="tc-line w70" />
              <span class="tc-chip" />
            </span>
          </span>
          <span class="tc-meta">
            <span class="tc-name">{{ t.label }}</span>
            <span class="tc-mode">{{ t.mode === "dark" ? "深" : "浅" }}</span>
          </span>
        </button>
      </div>
    </div>

    <div class="s-row" data-setting="appearance.shape">
      <div class="s-label"><label>圆角与阴影</label></div>
      <div class="s-ctl seg">
        <button v-for="s in SHAPE_LIST" :key="s.id" :class="{ on: ap.shape === s.id }"
                :title="s.desc" @click="patch({ shape: s.id })">{{ s.label }}</button>
      </div>
    </div>

    <div class="s-row" data-setting="appearance.density">
      <div class="s-label"><label>疏密</label></div>
      <div class="s-ctl seg">
        <button v-for="d in DENSITY_LIST" :key="d.id" :class="{ on: ap.density === d.id }"
                :title="d.desc" @click="patch({ density: d.id })">{{ d.label }}</button>
      </div>
    </div>

    <div class="s-row" data-setting="appearance.font">
      <div class="s-label"><label>界面字体</label><p class="s-hint">公式与代码始终等宽，不受此项影响</p></div>
      <div class="s-ctl seg">
        <button v-for="f in FONT_LIST" :key="f.id" :class="{ on: ap.font === f.id }"
                :title="f.desc" @click="patch({ font: f.id })">{{ f.label }}</button>
      </div>
    </div>

    <div class="s-row" data-setting="appearance.reset">
      <div class="s-label"><label>恢复默认外观</label><p class="s-hint">回到液态玻璃·浅 + 玻璃感 + 舒适 + 默认字体</p></div>
      <div class="s-ctl"><button class="s-btn" @click="resetAll">恢复默认</button></div>
    </div>
  </section>
</template>

<style scoped>
.theme-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; width: 100%; }
.theme-card {
  display: flex; flex-direction: column; gap: 6px; padding: 8px;
  border: 1px solid var(--border); border-radius: var(--r-sm, 8px);
  background: var(--surface); cursor: pointer; font: inherit; text-align: left;
}
.theme-card.on { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }
/* 预览块：卡内自带 data-theme，所以这些变量取的是**该主题**的值 */
.tc-preview { display: flex; height: 44px; border-radius: 6px; overflow: hidden; border: 1px solid var(--border); }
.tc-side { width: 26%; background: var(--surface-alt, #eef2f7); }
.tc-body { flex: 1; padding: 6px; display: flex; flex-direction: column; gap: 4px; background: var(--bg, #fff); }
.tc-line { height: 4px; border-radius: 2px; background: var(--text-subtle, #cbd5e1); opacity: .5; }
.tc-line.w70 { width: 70%; }
.tc-chip { margin-top: auto; width: 40%; height: 8px; border-radius: 4px; background: var(--accent, #3b82f6); }
.tc-meta { display: flex; align-items: baseline; gap: 6px; }
.tc-name { font-size: 12px; }
.tc-mode { margin-left: auto; font-size: 11px; color: var(--text-subtle, #94a3b8); }
</style>
