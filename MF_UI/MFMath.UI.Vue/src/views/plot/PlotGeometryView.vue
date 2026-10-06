<script setup>
/**
 * PlotGeometryView — 自由几何（对齐 Python plot/arbitrary/geometry_canvas）
 * 10 工具 + 吸附 + 撤销/重做 + 图形列表（点击选中、隐藏、删除）
 * 坐标系与 2D 绘图一致（复用 cartesian.js）
 */
import { ref, computed } from "vue";
import { useRoute } from "vue-router";
import GeometryCanvas from "../../components/plot/GeometryCanvas.vue";
import { exportCanvas } from "../../lib/plot/exportImage.js";

const route = useRoute();

/**
 * 导出当前几何画布为 PNG（2x、不透明底）。
 * canvasRef 在下面才声明：函数体是用户点按钮时才执行的，那时 setup 早已跑完，不存在 TDZ。
 */
function exportImage() {
  const r = exportCanvas(canvasRef.value?.canvasEl?.(), { routePath: route.path, note: "自由几何" });
  statusText.value = r.ok
    ? `已导出图片：${r.path}（${r.width}×${r.height}）`
    : (r.canceled ? "已取消导出" : `导出失败：${r.error}`);
}

const TOOLS = [
  { id: "select", label: "选择", hint: "点击图形选中，拖拽移动" },
  { id: "pan", label: "平移", hint: "按住左键拖拽平移视图" },
  { id: "point", label: "点", hint: "点击画布创建点" },
  { id: "segment", label: "线段", hint: "点击起点，再点击终点" },
  { id: "circle", label: "圆", hint: "点击圆心，再点击确定半径" },
  { id: "vector", label: "向量", hint: "点击起点，再点击终点" },
  { id: "line", label: "直线", hint: "点击两点确定无限直线" },
  { id: "ellipse", label: "椭圆", hint: "中心 → 水平半轴 → 垂直半轴" },
  { id: "rect", label: "矩形", hint: "点击对角两点" },
  { id: "polygon", label: "多边形", hint: "依次点击顶点，双击/右键闭合" },
];

const tool = ref("select");
const shapes = ref([]);
const selectedId = ref(null);
const snap = ref(true);
const statusText = ref("就绪");
const canvasRef = ref(null);

let nextId = 1;
const undoStack = ref([]);
const redoStack = ref([]);

const currentTool = computed(() => TOOLS.find((t) => t.id === tool.value) || TOOLS[0]);

/** 按类型生成默认标签（点用 A/B/C…，其余用中文名 + 序号） */
function makeLabel(type, id) {
  if (type === "point") return String.fromCharCode(64 + ((id - 1) % 26) + 1);
  const names = { segment: "线段", circle: "圆", vector: "v", line: "直线", ellipse: "椭圆", rect: "矩形", polygon: "多边形" };
  return `${names[type] || "图形"}${id}`;
}

function snapshot() {
  undoStack.value = [...undoStack.value, JSON.stringify(shapes.value)].slice(-100);
  redoStack.value = [];
}

/**
 * 图形颜色 = 原版几何模块的固定色 #3498db：
 *   `arbitrary/shapes.py:54,76` 的默认色就是 #3498db，且 `geometry_canvas.py` 的 6 处
 *   create_shape 调用（894/953/962/973/982/990）**都不传 color** → 原版画布上所有图形同色。
 * 之前用 Desmos 循环色板，其中第 6 色是纯黑 #000000，在深色主题画布（#12161f）上几乎看不见。
 * 想恢复"每个图形不同色"的话，改这一处即可（并请一并去掉纯黑）。
 */
const SHAPE_COLOR = "#3498db";

function createShape({ type, data }) {
  snapshot();
  const id = nextId++;
  shapes.value = [...shapes.value, {
    id, type, data,
    color: SHAPE_COLOR,
    label: makeLabel(type, id),
    visible: true,
  }];
  selectedId.value = id;
  statusText.value = `已创建 ${makeLabel(type, id)}`;
}

function moveShape({ id, dx, dy }) {
  shapes.value = shapes.value.map((s) => {
    if (s.id !== id) return s;
    const d = JSON.parse(JSON.stringify(s.data));
    const t = s.type;
    if (t === "point") { d[0] += dx; d[1] += dy; }
    else if (t === "segment" || t === "vector" || t === "line" || t === "rect") {
      d[0][0] += dx; d[0][1] += dy; d[1][0] += dx; d[1][1] += dy;
    } else if (t === "circle" || t === "ellipse") { d[0][0] += dx; d[0][1] += dy; }
    else if (t === "polygon") for (const p of d) { p[0] += dx; p[1] += dy; }
    return { ...s, data: d };
  });
}

function undo() {
  if (!undoStack.value.length) { statusText.value = "无可撤销"; return; }
  redoStack.value = [...redoStack.value, JSON.stringify(shapes.value)];
  const prev = JSON.parse(undoStack.value[undoStack.value.length - 1]);
  undoStack.value = undoStack.value.slice(0, -1);
  shapes.value = prev;
  selectedId.value = null;
  statusText.value = "已撤销";
}

function redo() {
  if (!redoStack.value.length) { statusText.value = "无可重做"; return; }
  undoStack.value = [...undoStack.value, JSON.stringify(shapes.value)];
  const next = JSON.parse(redoStack.value[redoStack.value.length - 1]);
  redoStack.value = redoStack.value.slice(0, -1);
  shapes.value = next;
  statusText.value = "已重做";
}

function removeShape(id) {
  snapshot();
  shapes.value = shapes.value.filter((s) => s.id !== id);
  if (selectedId.value === id) selectedId.value = null;
  statusText.value = "已删除";
}

function toggleVisible(id) {
  shapes.value = shapes.value.map((s) => (s.id === id ? { ...s, visible: !s.visible } : s));
}

function clearAll() {
  if (!shapes.value.length) return;
  snapshot();
  shapes.value = [];
  selectedId.value = null;
  statusText.value = "已清空";
}

function cancelConstruction() {
  canvasRef.value?.cancelConstruction?.();
  statusText.value = "已取消构造";
}

function resetView() {
  canvasRef.value?.resetView?.();
}

/** 图形摘要（列表展示） */
function shapeSummary(s) {
  const d = s.data;
  switch (s.type) {
    case "point": return `(${d[0].toFixed(2)}, ${d[1].toFixed(2)})`;
    case "segment":
    case "vector":
    case "line":
    case "rect":
      return `(${d[0][0].toFixed(1)}, ${d[0][1].toFixed(1)}) → (${d[1][0].toFixed(1)}, ${d[1][1].toFixed(1)})`;
    case "circle": return `圆心 (${d[0][0].toFixed(1)}, ${d[0][1].toFixed(1)}) r=${Math.abs(d[1]).toFixed(2)}`;
    case "ellipse": return `${Math.abs(d[1]).toFixed(2)} × ${Math.abs(d[2]).toFixed(2)}`;
    case "polygon": return `${d.length} 个顶点`;
    default: return "";
  }
}
</script>

<template>
  <div class="geo-layout">
    <aside class="geo-side">
      <div class="field">
        <label>工具</label>
        <div class="tools">
          <button
            v-for="t in TOOLS"
            :key="t.id"
            class="tool-btn"
            :class="{ active: tool === t.id }"
            :title="t.hint"
            @click="tool = t.id"
          >{{ t.label }}</button>
        </div>
        <div class="hint">{{ currentTool.hint }}</div>
      </div>

      <div class="field opts">
        <label class="chk"><input v-model="snap" type="checkbox" /> 吸附（端点/中点/圆心 + 网格）</label>
      </div>

      <div class="field row-actions">
        <button class="mini-btn" title="撤销" @click="undo">撤销</button>
        <button class="mini-btn" title="重做" @click="redo">重做</button>
        <button class="mini-btn" title="取消当前构造" @click="cancelConstruction">取消</button>
        <button class="mini-btn danger" title="清空全部" @click="clearAll">清空</button>
      </div>

      <div class="field">
        <label>图形（{{ shapes.length }}）</label>
        <div v-if="!shapes.length" class="empty">用左侧工具在画布上作图</div>
        <div
          v-for="s in shapes"
          :key="s.id"
          class="shape-row"
          :class="{ active: s.id === selectedId, hidden: !s.visible }"
          @click="selectedId = s.id"
        >
          <span class="shape-dot" :style="{ background: s.color }" />
          <span class="shape-main">
            <span class="shape-label">{{ s.label }}</span>
            <span class="shape-sum">{{ shapeSummary(s) }}</span>
          </span>
          <button class="shape-btn" :title="s.visible ? '隐藏' : '显示'" @click.stop="toggleVisible(s.id)">
            {{ s.visible ? "◉" : "○" }}
          </button>
          <button class="shape-btn del" title="删除" @click.stop="removeShape(s.id)">✕</button>
        </div>
      </div>

      <div class="status">{{ statusText }}</div>
    </aside>

    <div class="geo-main">
      <GeometryCanvas
        ref="canvasRef"
        data-tour="geometry_canvas"
        :shapes="shapes"
        :tool="tool"
        :selected-id="selectedId"
        :snap="snap"
        @create="createShape"
        @select="(id) => (selectedId = id)"
        @move="moveShape"
        @cursor="() => {}"
      />
      <div class="view-controls">
        <button class="vc-btn" title="重置视图" @click="resetView">⟲</button>
        <button class="vc-btn" title="导出图片（PNG，2 倍像素）" @click="exportImage">⤓</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 两列都必须能压缩、行高必须受容器约束（与 PlotView.vue 同款问题）：
 * 写死 `320px 1fr` 时窗口一窄画布列就被算成 0px，整幅图"消失"。 */
.geo-layout {
  display: grid;
  grid-template-columns: minmax(0, 320px) minmax(160px, 1fr);
  grid-template-rows: minmax(0, 1fr);
  height: 100%;
  min-height: 520px;
}
@media (max-width: 760px) {
  .geo-layout { grid-template-columns: minmax(0, 1fr); grid-template-rows: auto minmax(220px, 1fr); min-height: 320px; }
  .geo-side { max-height: 34vh; border-right: none; border-bottom: 1px solid var(--border); }
}
.geo-side {
  display: flex; flex-direction: column; gap: 12px;
  padding: 12px; border-right: 1px solid var(--border);
  background: var(--surface-alt); overflow-y: auto;
  min-width: 0; min-height: 0;
}
.field { display: flex; flex-direction: column; gap: 5px; }
.field > label { font-size: 11.5px; color: var(--text-muted); }
.tools { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; }
.tool-btn {
  height: 28px; border: 1px solid var(--border); border-radius: 7px;
  background: var(--surface); color: var(--text-muted); font-size: 12px; cursor: pointer;
  transition: all .12s;
}
.tool-btn:hover { border-color: var(--accent); color: var(--accent); }
.tool-btn.active { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); font-weight: 700; }
.hint { font-size: 11.5px; color: var(--text-subtle); min-height: 15px; }
.opts { gap: 6px; }
.chk { display: flex; align-items: center; gap: 5px; font-size: 12px; color: var(--text); }
.row-actions { flex-direction: row; gap: 4px; flex-wrap: wrap; }
.mini-btn {
  padding: 3px 9px; border: 1px solid var(--border); border-radius: 6px;
  background: var(--surface); color: var(--text-muted); font-size: 11.5px; cursor: pointer;
}
.mini-btn:hover { border-color: var(--accent); color: var(--accent); }
.mini-btn.danger:hover { border-color: var(--danger); color: var(--danger); }
.empty { font-size: 11.5px; color: var(--text-subtle); padding: 4px 2px; }
.shape-row {
  display: grid; grid-template-columns: 12px 1fr auto auto;
  align-items: center; gap: 5px;
  padding: 3px 4px; border-radius: 6px; cursor: pointer;
  border: 1px solid transparent;
}
.shape-row:hover { background: var(--surface); }
.shape-row.active { border-color: var(--accent); background: var(--accent-soft); }
.shape-row.hidden { opacity: .5; }
.shape-dot { width: 10px; height: 10px; border-radius: 50%; }
.shape-main { display: flex; flex-direction: column; min-width: 0; }
.shape-label { font-size: 12px; color: var(--text); }
.shape-sum {
  font-size: 10.5px; color: var(--text-subtle);
  font-family: 'Cascadia Code', Consolas, monospace;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.shape-btn {
  border: none; background: none; color: var(--text-subtle);
  font-size: 11px; cursor: pointer; padding: 0 3px;
}
.shape-btn.del:hover { color: var(--danger); }
.status { margin-top: auto; font-size: 11.5px; color: var(--text-subtle); }
.geo-main { position: relative; min-width: 0; min-height: 0; }
.view-controls { position: absolute; top: 12px; right: 12px; }
.vc-btn {
  width: 32px; height: 32px; border: 1px solid var(--border); border-radius: 8px;
  background: var(--glass); backdrop-filter: blur(8px); color: var(--text);
  font-size: 15px; cursor: pointer;
}
.vc-btn:hover { background: var(--surface); border-color: var(--accent); color: var(--accent); }
</style>
