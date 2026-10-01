<script setup>
/**
 * TourOverlay — 引导式走查的遮罩层（替代 v1 的 overlay.py + walkthrough.py）
 *
 * 关键设计取舍，逐条对应 v1 的缺陷：
 *
 * 1. **遮罩不吞点击**（v1 的 overlay.py:91 设了 WA_TransparentForMouseEvents=False，
 *    于是"用户点击"其实是 _execute_action 用 hasattr(target,"click") 反射模拟的，
 *    而且 15 处 action:click 里绝大多数没写 action_value，压根不会执行）。
 *    这里遮罩整体 pointer-events:none，只有提示卡可点；用户**真的去点**那个按钮，
 *    由页面自身逻辑生效，引导只监听"点到了目标"就前进。
 *
 * 2. **挖洞用 box-shadow 扩散**，一个元素搞定：目标矩形上放一个 span，
 *    给它 `box-shadow: 0 0 0 9999px <遮罩色>` 就等于"除了这块以外全盖住"。
 *    比 v1 的 QPainterPath.subtracted 简单得多，圆角/椭圆（circle 形状）
 *    也只需 border-radius。颜色沿用 v1 的 #00000073(亮) / #0000008C(暗)，
 *    圆角 8px、内边距 8px 也对齐。
 *
 * 3. **缺目标不静默跳过**：v1 找不到控件就 `_current_step += 1; 递归`，
 *    用户什么都看不到，教程 05/11 因此"走完"并被标记已学。这里改为显示
 *    一张明确的提示卡：缺哪个界面、依赖什么、以及"跳过此步 / 结束引导"。
 *
 * 4. 补上 v1 没有的：上一步、暂停/继续、步骤进度条、以及"接着上次走"的入口
 *    （入口在教程目录/正文页，这里只负责走）。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import {
  tourState, currentTutorial, currentStep, stepCount, isLast, canPrev,
  currentTargetName, next, prev, togglePause, skip, finish, noteMissing,
} from "../../lib/tutorial/tour.js";
import { resolveTarget, sanitizeTourHtml } from "../../lib/tutorial/targets.js";

const route = useRoute();

const rect = ref(null);          // { x, y, w, h, circle }
const missingReason = ref("");
const tooltipEl = ref(null);
const tipPos = ref({ left: 0, top: 0 });

const step = computed(() => currentStep.value);
const total = computed(() => stepCount.value);
const stepNo = computed(() => tourState.index + 1);
const tutorial = computed(() => currentTutorial.value);
const tipHtml = computed(() => sanitizeTourHtml(step.value?.text || ""));
const dark = computed(() => document.documentElement.dataset.mode === "dark");

let raf = 0;
function scheduleLocate() {
  if (raf) return;
  raf = requestAnimationFrame(() => { raf = 0; locate(); });
}

function locate() {
  const s = step.value;
  if (!tourState.active || tourState.paused || !s) {
    rect.value = null;
    missingReason.value = "";
    return;
  }
  const info = resolveTarget(s.target);
  if (!info.available) {
    rect.value = null;
    missingReason.value = info.reason;
    noteMissing(tourState.index);
    return;
  }
  missingReason.value = "";
  const el = info.el;
  try { el.scrollIntoView({ block: "nearest", inline: "nearest" }); } catch { /* 老内核无此 API */ }
  const r = el.getBoundingClientRect();
  const pad = 8; // 对齐 v1 overlay.py 的 pad = 8
  rect.value = {
    x: r.left - pad,
    y: r.top - pad,
    w: r.width + pad * 2,
    h: r.height + pad * 2,
    circle: s.highlight === "circle",
  };
  nextTick(placeTooltip);
}

/** 四方位定位 + 边界夹取（对齐 v1 overlay.py:287-302 的 clamp(10, …)） */
function placeTooltip() {
  const r = rect.value;
  const tip = tooltipEl.value;
  if (!tip) return;
  const tw = tip.offsetWidth || 300;
  const th = tip.offsetHeight || 140;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  let left;
  let top;
  if (!r) {
    left = (vw - tw) / 2;
    top = vh * 0.35;
  } else {
    switch (step.value?.placement || "bottom") {
      case "top":
        left = r.x + r.w / 2 - tw / 2;
        top = r.y - th - 16;
        break;
      case "left":
        left = r.x - tw - 16;
        top = r.y + r.h / 2 - th / 2;
        break;
      case "right":
        left = r.x + r.w + 16;
        top = r.y + r.h / 2 - th / 2;
        break;
      default: // bottom
        left = r.x + r.w / 2 - tw / 2;
        top = r.y + r.h + 16;
    }
  }
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(v, hi));
  tipPos.value = {
    left: clamp(left, 10, Math.max(10, vw - tw - 10)),
    top: clamp(top, 10, Math.max(10, vh - th - 10)),
  };
}

/** 用户真的点到了目标元素 → 前进一步（替代 v1 的反射式模拟点击） */
function onDocClick(e) {
  if (!tourState.active || tourState.paused) return;
  const name = currentTargetName.value;
  if (!name) return;
  const hit = e.target?.closest?.(`[data-tour="${name.replace(/["\\]/g, "\\$&")}"]`);
  if (hit) next();
}

function onDocKey(e) {
  if (!tourState.active) return;
  if (e.key === "Escape") { tourState.paused ? null : togglePause(); }
  else if (e.key === "ArrowRight" && !e.altKey && !e.ctrlKey) next();
  else if (e.key === "ArrowLeft" && !e.altKey && !e.ctrlKey) prev();
}

onMounted(() => {
  window.addEventListener("resize", scheduleLocate);
  window.addEventListener("scroll", scheduleLocate, true);
  document.addEventListener("click", onDocClick, true);
  document.addEventListener("keydown", onDocKey);
  scheduleLocate();
});
onBeforeUnmount(() => {
  window.removeEventListener("resize", scheduleLocate);
  window.removeEventListener("scroll", scheduleLocate, true);
  document.removeEventListener("click", onDocClick, true);
  document.removeEventListener("keydown", onDocKey);
  if (raf) cancelAnimationFrame(raf);
});

// 步骤、路由、暂停态变化都要重新定位
watch(() => [tourState.index, tourState.paused, tourState.active, route.path], () => nextTick(scheduleLocate));
</script>

<template>
  <div v-if="tourState.active" class="tour" :class="{ paused: tourState.paused }" role="dialog" aria-label="引导式走查">
    <!-- 挖洞：box-shadow 扩散盖住除目标以外的全部区域 -->
    <span v-if="rect" class="tour-hole" :class="{ circle: rect.circle }"
          :style="{ left: rect.x + 'px', top: rect.y + 'px', width: rect.w + 'px', height: rect.h + 'px',
                    boxShadow: '0 0 0 9999px ' + (dark ? 'rgba(0,0,0,0.549)' : 'rgba(0,0,0,0.451)') }" />
    <!-- 无目标时整屏压暗，避免"什么都没发生"的错觉 -->
    <span v-else class="tour-veil" />
    <!-- 目标上的脉冲光圈（与挖洞分开，才能独立动画） -->
    <span v-if="rect" class="tour-ring" :class="{ circle: rect.circle }"
          :style="{ left: rect.x + 'px', top: rect.y + 'px', width: rect.w + 'px', height: rect.h + 'px' }" />

    <div ref="tooltipEl" class="tour-tip" :style="{ left: tipPos.left + 'px', top: tipPos.top + 'px' }">
      <div class="tip-head">
        <span class="tip-title">{{ tutorial?.title || "引导" }}</span>
        <span class="tip-count">{{ stepNo }} / {{ total }}</span>
      </div>
      <div class="tip-bar"><i :style="{ width: (total ? (stepNo / total) * 100 : 0) + '%' }" /></div>

      <p v-if="tourState.paused" class="tip-paused">已暂停。点「继续」接着走，或结束本次引导。</p>

      <template v-else>
        <p v-if="missingReason" class="tip-missing">
          <b>这一步的目标界面还没做</b>，不是你的操作问题。<br>
          <span class="tip-reason">{{ missingReason }}</span>
        </p>
        <div v-else class="tip-text" v-html="tipHtml" />
        <p v-if="step?.actionType === 'type' && step?.actionValue" class="tip-hint">
          该步可自动填入：<code>{{ step.actionValue }}</code>
        </p>
        <p v-else-if="step?.actionType === 'click'" class="tip-hint">点一下高亮的按钮继续。</p>
      </template>

      <div class="tip-actions">
        <button class="tbtn ghost" title="结束本次引导（不会标记为已学）" @click="skip">结束引导</button>
        <span class="spacer" />
        <button class="tbtn" :disabled="!canPrev || tourState.paused" @click="prev">上一步</button>
        <button class="tbtn" @click="togglePause">{{ tourState.paused ? "继续" : "暂停" }}</button>
        <button v-if="missingReason" class="tbtn" @click="next">跳过此步</button>
        <button class="tbtn primary" @click="isLast ? finish() : next()">
          {{ isLast ? "完成" : "下一步" }}
        </button>
      </div>
      <p class="tip-foot">Esc 暂停 · ←/→ 上一步/下一步</p>
    </div>
  </div>
</template>

<style scoped>
/* 整层不接收鼠标事件，只让提示卡可点：用户要能真的点到下面那个按钮 */
.tour { position: fixed; inset: 0; z-index: 4000; pointer-events: none; }
.tour.paused .tour-ring { animation: none; }
.tour-veil {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.451);
}
[data-mode="dark"] .tour-veil { background: rgba(0, 0, 0, 0.549); }
.tour-hole {
  position: fixed; border-radius: 8px; pointer-events: none;
}
.tour-hole.circle { border-radius: 50%; }
.tour-ring {
  position: fixed; pointer-events: none;
  border: 2.5px solid var(--accent, #3b82f6);
  border-radius: 8px;
  animation: tour-pulse 1.2s ease-in-out infinite;
}
.tour-ring.circle { border-radius: 50%; }
@keyframes tour-pulse {
  0%, 100% { box-shadow: 0 0 0 12px rgba(59, 130, 246, 0.24); }
  50%      { box-shadow: 0 0 0 16px rgba(59, 130, 246, 0.18); }
}
/* 尊重系统的"减少动态效果"：v1 没有这个考虑 */
@media (prefers-reduced-motion: reduce) {
  .tour-ring { animation: none; box-shadow: 0 0 0 12px rgba(59, 130, 246, 0.24); }
}

.tour-tip {
  position: fixed;
  pointer-events: auto;
  width: max-content;
  min-width: 220px;
  max-width: 340px;
  padding: 12px 14px 10px;
  border-radius: 10px;
  background: var(--surface, #fff);
  color: var(--text, #1e293b);
  border: 1px solid var(--border, #d1d5db);
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.22);
}
.tip-head { display: flex; align-items: baseline; gap: 8px; }
.tip-title { font-weight: 600; font-size: 13px; }
.tip-count { margin-left: auto; font-size: 11px; color: var(--text-subtle, #94a3b8); }
.tip-bar { height: 3px; border-radius: 2px; background: var(--surface-alt, #eef2f7); margin: 8px 0 10px; overflow: hidden; }
.tip-bar i { display: block; height: 100%; background: var(--accent, #3b82f6); transition: width .18s; }
.tip-text { font-size: 13px; line-height: 1.7; }
.tip-text :deep(b), .tip-text :deep(strong) { font-weight: 600; }
.tip-missing {
  font-size: 12.5px; line-height: 1.6; margin: 0 0 6px;
  padding: 8px 10px; border-radius: 8px;
  background: color-mix(in srgb, #f59e0b 14%, transparent);
  border: 1px solid color-mix(in srgb, #f59e0b 40%, transparent);
}
.tip-reason { color: var(--text-subtle, #64748b); }
.tip-hint { font-size: 12px; color: var(--text-subtle, #64748b); margin: 8px 0 0; }
.tip-paused { font-size: 13px; margin: 0; }
.tip-actions { display: flex; align-items: center; gap: 6px; margin-top: 12px; }
.spacer { flex: 1; }
.tbtn {
  font: inherit; font-size: 12px; padding: 5px 10px; cursor: pointer;
  border-radius: var(--r-sm, 6px); border: 1px solid var(--border, #d1d5db);
  background: var(--surface-alt, #f8fafc); color: var(--text, #1e293b);
}
.tbtn:hover:not(:disabled) { border-color: var(--accent, #3b82f6); }
.tbtn:disabled { opacity: .45; cursor: default; }
.tbtn.primary { background: var(--accent, #3b82f6); border-color: var(--accent, #3b82f6); color: #fff; }
.tbtn.ghost { background: transparent; }
.tip-foot { margin: 8px 0 0; font-size: 11px; color: var(--text-subtle, #94a3b8); }
</style>
