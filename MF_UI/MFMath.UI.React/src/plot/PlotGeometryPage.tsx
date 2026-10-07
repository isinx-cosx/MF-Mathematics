import { useMemo, useRef, useState } from "react";
import GeometryCanvas from "./GeometryCanvas";
import type { GeometryApi, Shape, ShapeDataMap, ShapeDraft, ShapeType } from "./GeometryCanvas";
import { exportCanvas } from "@shared/plot/exportImage.js";
import { loadPlotPage, usePlotWorkspace, boolOr, strOr } from "../lib/plotWorkspace";
import "../styles/plot-geometry.css";

/**
 * PlotGeometryPage — 自由几何（对照 Vue 版 views/plot/PlotGeometryView.vue 逐行移植）
 * 10 工具 + 吸附 + 撤销/重做 + 图形列表（点击选中、隐藏、删除）
 * 坐标系与 2D 绘图一致（复用 cartesian.js）
 *
 * DOM 契约与 Vue 版逐字一致（cdp-plot-geometry 依赖）：`.tool-btn`（10 个，文字固定）、
 * `.chk input`（吸附）、`.mini-btn`（撤销/重做/取消/清空）、`.shape-row`（`.shape-label`/`.shape-sum`/
 * `.shape-btn`/`.shape-btn.del`，隐藏时加 `.hidden`）、`.status`、`.vc-btn[title="重置视图"]`。
 */

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

/**
 * 图形颜色 = 原版几何模块的固定色 #3498db：原版 6 处 create_shape 都不传 color，
 * 画布上所有图形同色。用 Desmos 循环色板时第 6 色是纯黑，在深色主题上几乎看不见。
 */
const SHAPE_COLOR = "#3498db";

/** 按类型生成默认标签（点用 A/B/C…，其余用中文名 + 序号） */
function makeLabel(type: ShapeType, id: number): string {
  if (type === "point") return String.fromCharCode(64 + ((id - 1) % 26) + 1);
  const names: Record<string, string> = {
    segment: "线段", circle: "圆", vector: "v", line: "直线",
    ellipse: "椭圆", rect: "矩形", polygon: "多边形",
  };
  return `${names[type] || "图形"}${id}`;
}

/** 图形摘要（列表展示） */
function shapeSummary(s: Shape): string {
  switch (s.type) {
    case "point": return `(${s.data[0].toFixed(2)}, ${s.data[1].toFixed(2)})`;
    case "segment":
    case "vector":
    case "line":
    case "rect":
      return `(${s.data[0][0].toFixed(1)}, ${s.data[0][1].toFixed(1)}) → (${s.data[1][0].toFixed(1)}, ${s.data[1][1].toFixed(1)})`;
    case "circle": return `圆心 (${s.data[0][0].toFixed(1)}, ${s.data[0][1].toFixed(1)}) r=${Math.abs(s.data[1]).toFixed(2)}`;
    case "ellipse": return `${Math.abs(s.data[1]).toFixed(2)} × ${Math.abs(s.data[2]).toFixed(2)}`;
    case "polygon": return `${s.data.length} 个顶点`;
    default: return "";
  }
}

export default function PlotGeometryPage({ routePath = "#/plot/geometry" }: { routePath?: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const apiRef = useRef<GeometryApi | null>(null);

  /* 工作区还原（BUGS.md B14）：这一页在 Vue 版时代也没接过工作区，属于补齐。
   * 形状来自 JSON（用户可手改），所以要**逐项最小校验**：id 必须是数字、type 是字符串、
   * data 是数组 —— 不合格的整条丢掉（宁少画一个，也不要一个半坏的图形把画布带崩）。 */
  const saved = loadPlotPage(routePath, "plot-geometry");
  const restoredShapes = (() => {
    const raw = saved?.shapes;
    if (!Array.isArray(raw)) return [] as Shape[];
    return raw.filter((s) => {
      if (!s || typeof s !== "object") return false;
      const o = s as Record<string, unknown>;
      return Number.isFinite(o.id) && typeof o.type === "string" && Array.isArray(o.data);
    }) as Shape[];
  })();

  const [tool, setTool] = useState(() => strOr(saved?.tool, "select"));
  const [shapes, setShapes] = useState<Shape[]>(restoredShapes);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [snap, setSnap] = useState(() => boolOr(saved?.snap, true));
  const [statusText, setStatusText] = useState(() => (restoredShapes.length ? `已从工作区还原 ${restoredShapes.length} 个图形` : "就绪"));
  const [undoStack, setUndoStack] = useState<string[]>([]);
  const [redoStack, setRedoStack] = useState<string[]>([]);
  /* ⚠ 还原之后必须把 nextIdRef 推到**下一个空 id** —— 否则新画的图形会与还原出来的某个撞 id：
   * 撞 id 时两条记录共享同一份状态（改动互相影响、删一条会删掉两条）。
   * Vue 版 PlotView 就是在同一个坑上踩过一次，注释里写得很清楚，所以这里刻意显式处理。 */
  const nextIdRef = useRef(restoredShapes.reduce((m, s) => Math.max(m, Number(s.id) || 0), 0) + 1);

  /* 变更即回写工作区；撤销/重做栈是过程状态，不存。 */
  usePlotWorkspace(routePath, [shapes, tool, snap], () => ({
    kind: "plot-geometry",
    shapes,
    tool,
    snap,
  }));

  const currentTool = useMemo(() => TOOLS.find((t) => t.id === tool) || TOOLS[0], [tool]);

  /** 快照进撤销栈（上限 100），并清空重做栈 */
  const snapshot = () => {
    setUndoStack((prev) => [...prev, JSON.stringify(shapes)].slice(-100));
    setRedoStack([]);
  };

  /* 草稿（type + 对应形状的 data）由画布抛出，这里补上 id/颜色/标签。
   * 直接展开整份草稿：type 与 data 的对应关系原样保留，不需要断言。 */
  const createShape = (draft: ShapeDraft) => {
    snapshot();
    const id = nextIdRef.current++;
    setShapes((prev) => [...prev, {
      id, ...draft, color: SHAPE_COLOR, label: makeLabel(draft.type, id), visible: true,
    }]);
    setSelectedId(id);
    setStatusText(`已创建 ${makeLabel(draft.type, id)}`);
  };

  const moveShape = ({ id, dx, dy }: { id: number; dx: number; dy: number }) => {
    setShapes((prev) => prev.map((s) => {
      if (s.id !== id) return s;
      /* 平移：按类型分别重建一份新的数据数组（等价于原来的 JSON 深拷贝 —— 同样不原地
       * 改 state 里已有的数组，数值逐位相同）。每个分支里 s.data 都是收窄后的真实形状，
       * 所以 d[0] / d[0][0] 都是数字，原来的 `as never` 不再需要。 */
      switch (s.type) {
        case "point": {
          const d: ShapeDataMap["point"] = [s.data[0] + dx, s.data[1] + dy];
          return { ...s, data: d };
        }
        case "segment":
        case "vector":
        case "line":
        case "rect": {
          const d: ShapeDataMap["segment"] = [
            [s.data[0][0] + dx, s.data[0][1] + dy], [s.data[1][0] + dx, s.data[1][1] + dy],
          ];
          return { ...s, data: d };
        }
        case "circle": {
          const d: ShapeDataMap["circle"] = [[s.data[0][0] + dx, s.data[0][1] + dy], s.data[1]];
          return { ...s, data: d };
        }
        case "ellipse": {
          const d: ShapeDataMap["ellipse"] = [[s.data[0][0] + dx, s.data[0][1] + dy], s.data[1], s.data[2]];
          return { ...s, data: d };
        }
        case "polygon": {
          const d: ShapeDataMap["polygon"] = s.data.map(([x, y]) => [x + dx, y + dy]);
          return { ...s, data: d };
        }
      }
    }));
  };

  const undo = () => {
    if (!undoStack.length) { setStatusText("无可撤销"); return; }
    setRedoStack((prev) => [...prev, JSON.stringify(shapes)]);
    const prev = JSON.parse(undoStack[undoStack.length - 1]) as Shape[];
    setUndoStack((s) => s.slice(0, -1));
    setShapes(prev);
    setSelectedId(null);
    setStatusText("已撤销");
  };

  const redo = () => {
    if (!redoStack.length) { setStatusText("无可重做"); return; }
    setUndoStack((prev) => [...prev, JSON.stringify(shapes)]);
    const next = JSON.parse(redoStack[redoStack.length - 1]) as Shape[];
    setRedoStack((s) => s.slice(0, -1));
    setShapes(next);
    setStatusText("已重做");
  };

  const removeShape = (id: number) => {
    snapshot();
    setShapes((prev) => prev.filter((s) => s.id !== id));
    if (selectedId === id) setSelectedId(null);
    setStatusText("已删除");
  };

  const toggleVisible = (id: number) => {
    setShapes((prev) => prev.map((s) => (s.id === id ? { ...s, visible: !s.visible } : s)));
  };

  const clearAll = () => {
    if (!shapes.length) return;
    snapshot();
    setShapes([]);
    setSelectedId(null);
    setStatusText("已清空");
  };

  const cancelConstruction = () => {
    apiRef.current?.cancelConstruction();
    setStatusText("已取消构造");
  };

  const resetView = () => apiRef.current?.resetView();

  /** 导出当前几何画布为 PNG（2x、不透明底） */
  const exportImage = () => {
    const r = exportCanvas(canvasRef.current, { routePath, note: "自由几何" });
    setStatusText(r.ok
      ? `已导出图片：${r.path}（${r.width}×${r.height}）`
      : (r.canceled ? "已取消导出" : `导出失败：${r.error}`));
  };

  return (
    <div className="geo-layout">
      <aside className="geo-side">
        <div className="field">
          <label>工具</label>
          <div className="tools">
            {TOOLS.map((t) => (
              <button key={t.id} className={"tool-btn" + (tool === t.id ? " active" : "")}
                      title={t.hint} onClick={() => setTool(t.id)}>{t.label}</button>
            ))}
          </div>
          <div className="hint">{currentTool.hint}</div>
        </div>

        <div className="field opts">
          <label className="chk">
            <input type="checkbox" checked={snap} onChange={(e) => setSnap(e.target.checked)} /> 吸附（端点/中点/圆心 + 网格）
          </label>
        </div>

        <div className="field row-actions">
          <button className="mini-btn" title="撤销" onClick={undo}>撤销</button>
          <button className="mini-btn" title="重做" onClick={redo}>重做</button>
          <button className="mini-btn" title="取消当前构造" onClick={cancelConstruction}>取消</button>
          <button className="mini-btn danger" title="清空全部" onClick={clearAll}>清空</button>
        </div>

        <div className="field">
          <label>图形（{shapes.length}）</label>
          {!shapes.length && <div className="empty">用左侧工具在画布上作图</div>}
          {shapes.map((s) => (
            <div key={s.id}
                 className={"shape-row" + (s.id === selectedId ? " active" : "") + (!s.visible ? " hidden" : "")}
                 onClick={() => setSelectedId(s.id)}>
              <span className="shape-dot" style={{ background: s.color }} />
              <span className="shape-main">
                <span className="shape-label">{s.label}</span>
                <span className="shape-sum">{shapeSummary(s)}</span>
              </span>
              <button className="shape-btn" title={s.visible ? "隐藏" : "显示"}
                      onClick={(e) => { e.stopPropagation(); toggleVisible(s.id); }}>
                {s.visible ? "◉" : "○"}
              </button>
              <button className="shape-btn del" title="删除"
                      onClick={(e) => { e.stopPropagation(); removeShape(s.id); }}>✕</button>
            </div>
          ))}
        </div>

        <div className="status">{statusText}</div>
      </aside>

      <div className="geo-main">
        <GeometryCanvas
          canvasRef={canvasRef}
          apiRef={apiRef}
          shapes={shapes}
          tool={tool}
          selectedId={selectedId}
          snap={snap}
          onCreate={createShape}
          onSelect={setSelectedId}
          onMove={moveShape}
        />
        <div className="view-controls">
          <button className="vc-btn" title="重置视图" onClick={resetView}>⟲</button>
          <button className="vc-btn" title="导出图片（PNG，2 倍像素）" onClick={exportImage}>⤓</button>
        </div>
      </div>
    </div>
  );
}
