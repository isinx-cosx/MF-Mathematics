import { useEffect, useRef, useState } from "react";
import "../styles/param-slider.css";

type Props = {
  name: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onValueChange: (v: number) => void;
  onConfigChange: (cfg: { min: number; max: number; step: number }) => void;
};

/** 动画速度（每秒变化量，按范围自适应） */
const SPEEDS = [0.25, 0.5, 1];

/**
 * ParamSlider — 参数滑块（照抄 Vue 版 ParamSlider.vue 的模板与行为）。
 * 拖动实时重绘；数值框可精确输入；齿轮展开设置；播放按钮自动往返动画。
 */
export default function ParamSlider({ name, value, min, max, step, onValueChange, onConfigChange }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [speedIdx, setSpeedIdx] = useState(1);

  const rafId = useRef(0);
  const lastTs = useRef(0);
  const dir = useRef(1);
  /* 动画回调里要读最新的 value/min/max，走 ref 以免每帧重建 rAF 循环 */
  const live = useRef({ value, min, max, speedIdx, onValueChange });
  live.current = { value, min, max, speedIdx, onValueChange };

  const display = (() => {
    const v = value;
    if (!isFinite(v)) return "—";
    const a = Math.abs(v);
    if (a !== 0 && (a < 1e-4 || a >= 1e5)) return v.toExponential(2);
    return String(Math.round(v * 1e6) / 1e6);
  })();

  const sliderValue = Math.min(Math.max(value, min), max);

  function stopAnim() {
    setPlaying(false);
    if (rafId.current) cancelAnimationFrame(rafId.current);
    rafId.current = 0;
  }

  /** 播放/暂停自动动画：值在 [min,max] 间往返 */
  function togglePlay() {
    if (playing) { stopAnim(); return; }
    setPlaying(true);
    lastTs.current = 0;
    const tick = (ts: number) => {
      const L = live.current;
      const span = Math.max(1e-9, L.max - L.min);
      const perSecond = span * SPEEDS[L.speedIdx] * 0.35; // 每秒走过的区间比例
      if (!lastTs.current) lastTs.current = ts;
      const dt = Math.min(0.1, (ts - lastTs.current) / 1000);
      lastTs.current = ts;
      let v = L.value + dir.current * perSecond * dt;
      if (v > L.max) { v = L.max; dir.current = -1; }
      if (v < L.min) { v = L.min; dir.current = 1; }
      L.onValueChange(v);
      rafId.current = requestAnimationFrame(tick);
    };
    rafId.current = requestAnimationFrame(tick);
  }

  useEffect(() => stopAnim, []);

  return (
    <div className="param-block" data-tour="plot_workspace.sliders">
      <div className="param-row">
        <span className="param-name">{name}</span>
        <input
          className="param-slider"
          type="range"
          min={min}
          max={max}
          step={step}
          value={sliderValue}
          onChange={(e) => onValueChange(Number(e.target.value))}
        />
        {editing ? (
          <input
            className="param-val-input"
            value={draft}
            autoFocus
            onChange={(e) => setDraft(e.target.value)}
            onBlur={() => {
              const v = Number(draft);
              if (isFinite(v)) onValueChange(v);
              setEditing(false);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                const v = Number(draft);
                if (isFinite(v)) onValueChange(v);
                setEditing(false);
              }
              if (e.key === "Escape") setEditing(false);
            }}
          />
        ) : (
          <button className="param-val" onClick={() => { setDraft(display); setEditing(true); }}>
            {display}
          </button>
        )}
        <button className="icon-btn" title={playing ? "暂停动画" : "播放动画"} onClick={togglePlay}>
          {playing ? "❚❚" : "▶"}
        </button>
        <button className="icon-btn" title="滑块设置" onClick={() => setShowSettings((s) => !s)}>⚙</button>
      </div>

      {/* 滑块设置（对齐 Desmos：最小值 / 最大值 / 步长 / 动画速度） */}
      {showSettings && (
        <div className="param-settings">
          <label>
            最小
            <input className="set-input" type="number" value={min}
                   onChange={(e) => onConfigChange({ min: Number(e.target.value), max, step })} />
          </label>
          <label>
            最大
            <input className="set-input" type="number" value={max}
                   onChange={(e) => onConfigChange({ min, max: Number(e.target.value), step })} />
          </label>
          <label>
            步长
            <input className="set-input" type="number" min={0} value={step}
                   onChange={(e) => onConfigChange({ min, max, step: Math.abs(Number(e.target.value)) || 0.1 })} />
          </label>
          <label className="speed-row">
            速度
            <button className="speed-btn" onClick={() => setSpeedIdx((i) => (i + 1) % SPEEDS.length)}>
              {SPEEDS[speedIdx]}×
            </button>
          </label>
        </div>
      )}
    </div>
  );
}
