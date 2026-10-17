import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { ALL_COLORS } from "@shared/plot/colors.js";
import { parseDefinition, registerUserFn } from "@shared/plot/userFn.js";
import MathField from "../components/MathField";
import type { MathFieldHandle } from "../components/MathField";
import "../styles/expr-list.css";

export type Expr = {
  id: number;
  /** 引擎语法（送引擎/采样用）。**不是**显示内容 —— 显示用 `latex`。 */
  text: string;
  /** 用户输入的原始 LaTeX。缺省（老载荷）时回退显示 `text`。
   *  为什么必须分开（BUGS.md B16）：`text` 是引擎规范化后的串（`5*x`、多余括号），
   *  拿它当 LaTeX 回填，切页回来用户就会看到"分数变成一堆星号"。 */
  latex?: string;
  color: string;
  visible: boolean;
  error?: string | null;
  /** 强调显示（画布把线加粗、区域填充更实）。
   *  原版 Vue（views/plot/PlotView.vue:95）由「当前选中行」产生它
   *  （`emphasis: row.id === activeId`）；本移植版的 PlotPage 只做透传
   *  （`emphasis: r.emphasis`），表达式列表这一侧还没有产生方。
   *  字段保留是因为画布侧 PlotCanvas 的 Curve.emphasis 仍在消费它
   *  （undefined 即普通线宽），且它是一个可选字段、不产生任何运行时行为。 */
  emphasis?: boolean;
};

type Props = {
  rows: Expr[];
  activeId: number | null;
  onRowsChange: (rows: Expr[]) => void;
  onActiveIdChange: (id: number) => void;
  onAdd: (index: number) => void;
  onRemove: (id: number) => void;
  onChange: () => void;
};

/**
 * ExpressionList — Desmos 式表达式列表（照抄 Vue 版 ExpressionList.vue 的模板与行为）。
 * 每行：[显示切换] [颜色圆点(点击改色)] [表达式输入] [删除]
 */
const SYMBOLS = [
  { label: "√", tip: "根号", latex: "\\sqrt{#0}" },
  { label: "x²", tip: "平方", latex: "^{2}" },
  { label: "xⁿ", tip: "幂", latex: "^{#0}" },
  { label: "a/b", tip: "分式", latex: "\\frac{#0}{#?}" },
  { label: "π", tip: "圆周率", latex: "\\pi" },
  { label: "e", tip: "自然对数底", latex: "e" },
  { label: "|x|", tip: "绝对值", latex: "\\left|#0\\right|" },
  { label: "sin", tip: "正弦", latex: "\\sin\\left(#0\\right)" },
  { label: "cos", tip: "余弦", latex: "\\cos\\left(#0\\right)" },
  { label: "tan", tip: "正切", latex: "\\tan\\left(#0\\right)" },
  { label: "ln", tip: "自然对数", latex: "\\ln\\left(#0\\right)" },
  { label: "lg", tip: "常用对数", latex: "\\lg\\left(#0\\right)" },
  { label: "eˣ", tip: "指数函数", latex: "e^{#0}" },
  { label: "≤", tip: "小于等于", latex: "\\le" },
  { label: "≥", tip: "大于等于", latex: "\\ge" },
  { label: "θ", tip: "极角 theta", latex: "\\theta" },
];

const ExpressionList = forwardRef<{ focusRow: (id: number) => void }, Props>(function ExpressionList(
  { rows, activeId, onRowsChange, onActiveIdChange, onAdd, onRemove, onChange },
  ref
) {
  /**
   * 本地影子副本：连续快速修改多行时，若每次都以 props 为基准构造新数组，
   * 会因为 props 更新是异步的而互相覆盖（第一次的修改被第二次用旧 props 冲掉）。
   */
  const [local, setLocal] = useState<Expr[]>(() => rows.map((r) => ({ ...r })));
  /* ⚠ 光有影子副本还不够：**同一个 tick 内改多行**时，三次 update 会读到同一份旧
   * `local`（闭包快照），于是最后一次覆盖前两次 —— 表现是"一次性写入多行表达式，
   * 只有最后一行生效"（粘贴/载入多行、以及端到端用例批量设表达式都会中招）。
   * 所以再拿一个 ref 记住**最新**数组，update 从它出发。 */
  const localRef = useRef<Expr[]>(local);
  localRef.current = local;
  useEffect(() => {
    setLocal(rows);
    localRef.current = rows;
  }, [rows]);

  const [paletteFor, setPaletteFor] = useState<number | null>(null);
  const [focusedId, setFocusedId] = useState<number | null>(null);
  const fieldRefs = useRef<Record<number, MathFieldHandle | null>>({});

  useImperativeHandle(ref, () => ({
    focusRow: (id: number) => fieldRefs.current[id]?.focus(),
  }), []);

  function update(id: number, patch: Partial<Expr>) {
    const next = localRef.current.map((r) => (r.id === id ? { ...r, ...patch } : r));
    localRef.current = next;   // 立刻生效：同一 tick 里的后续修改能看见它
    setLocal(next);
    onRowsChange(next);
    onChange();
  }

  /** 把符号插入当前行光标处：交给 MathLive，排版会就地生效（#0 决定光标落点）。 */
  function insertSymbol(sym: { latex: string }) {
    const id = focusedId ?? (local[0] && local[0].id);
    const field = id != null ? fieldRefs.current[id] : null;
    if (field && typeof field.insertLatex === "function") field.insertLatex(sym.latex);
  }

  return (
    <div className="expr-list">
      {/* 符号面板：点一下插入，省去手打 √ π ≤ 这些难输入的符号 */}
      <div className="symbol-bar">
        {SYMBOLS.map((s) => (
          <button key={s.label} className="symbol-btn" title={s.tip} onClick={() => insertSymbol(s)}>
            {s.label}
          </button>
        ))}
      </div>

      {local.map((row, i) => (
        <div
          key={row.id}
          className={
            "expr-row" + (row.id === activeId ? " active" : "") + (!row.visible ? " hidden" : "")
          }
          onClick={() => onActiveIdChange(row.id)}
        >
          {/* 行号 */}
          <span className="row-no">{i + 1}</span>

          {/* 显示切换（点击圆点式图标，同 Desmos） */}
          <button
            className="vis-btn"
            title={row.visible ? "隐藏" : "显示"}
            onClick={(e) => { e.stopPropagation(); update(row.id, { visible: !row.visible }); }}
          >
            <span className={"vis-ring" + (!row.visible ? " off" : "")} />
          </button>

          {/* 颜色圆点（点击改色） */}
          <button
            className="color-dot"
            style={{ background: row.color }}
            title="颜色"
            onClick={(e) => {
              e.stopPropagation();
              setPaletteFor(paletteFor === row.id ? null : row.id);
            }}
          />
          {paletteFor === row.id && (
            <div className="palette" onClick={(e) => e.stopPropagation()}>
              {ALL_COLORS.map((c: string) => (
                <button
                  key={c}
                  className={"palette-swatch" + (c === row.color ? " picked" : "")}
                  style={{ background: c }}
                  onClick={(e) => {
                    e.stopPropagation();
                    update(row.id, { color: c });
                    setPaletteFor(null);
                  }}
                />
              ))}
            </div>
          )}

          {/* 表达式输入：MathLive 就地排版。
              data-tour 只标在第一行：教程里"函数输入框"指的是用户要输入的那一格。 */}
          <MathField
            handleRef={(el) => { fieldRefs.current[row.id] = el; }}
            value={row.text}
            latex={row.latex}
            dataTour={i === 0 ? "plot_workspace.function_input" : undefined}
            placeholder="输入表达式，如 y=x^2 或 cosx"
            onValueChange={(v) => update(row.id, { text: v })}
            /* 原始 LaTeX 单独存一份：`text` 是引擎规范化结果，回填它会让用户
             * 切页回来看到 `5*x`、多余括号（BUGS.md B16）。
             * ⚠ 这里的顺序很关键：MathField 的 onInput 是**先**调 onChange(latex)、
             * **后**调 toEngineExpr(latex)。定义行必须在那一刻就登记函数名，
             * 否则引擎已经把它写成 `f*(x)` 了（`prepare.js` 的修复靠这张表）。 */
            onChange={(l) => {
              const d = parseDefinition(l);
              if (d && !d.error) registerUserFn(d.name);
              update(row.id, { latex: l });
              onChange();
            }}
            onFocus={() => setFocusedId(row.id)}
            onEnter={() => onAdd(i)}
          />

          {/* 删除（行 >1 时可用） */}
          {local.length > 1 && (
            <button className="del-btn" title="删除" onClick={(e) => { e.stopPropagation(); onRemove(row.id); }}>
              ✕
            </button>
          )}

          {/* 行内错误提示（对齐 Desmos：解析不了就明确提示） */}
          {row.error && <div className="expr-error">{row.error}</div>}
        </div>
      ))}

      <button className="add-row" data-tour="plot_workspace.add_function" onClick={() => onAdd(local.length - 1)}>
        ＋ 添加表达式
      </button>
    </div>
  );
});

export default ExpressionList;
