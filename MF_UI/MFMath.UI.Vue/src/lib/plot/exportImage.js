/**
 * plot/exportImage.js — 把画布导出成 PNG 文件
 *
 * v1 有这个功能（i18n 键 `menu.export = "导出图片"`，绘图工作区里用 matplotlib
 * `savefig(dpi=200)`），v2.0 一直没有——绘图结果只能看，不能存。
 * （注意注释里别写 `plot/星号/workspace.py` 这种路径：`星号/` 会把块注释提前闭合。）
 *
 * 三个必须处理的细节：
 *   ① **放大像素**：画布是按 CSS 像素画的，直接 toDataURL 出来在高分屏/论文里偏糊；
 *      这里按 devicePixelRatio（至少 2x）重画到离屏画布再导出。
 *      ⚠ 说清楚这是什么：它是把**已渲染的位图放大**（`drawImage` 到 2 倍尺寸），
 *      不是"按 2 倍分辨率重新渲染一遍"——所以像素数是 2×，细节不是。
 *      要真提升细节得让绘图代码按 2 倍画布重绘（采样点也随之加密），那是另一件事。
 *   ② **背景不能透明**：canvas 的透明区在图片查看器里是黑的，粘进文档也难看。
 *      先铺一层不透明底色（取画布自身的背景色，取不到就白）再画。
 *   ③ **文件名要能认**：用"页面名 + 时间戳"，例如 `plot-2d-20261002-1930.png`。
 *
 * 自动化钩子：`window.__mfExportTo` 非空时**跳过保存对话框**直接写到该路径，
 * 供测试与命令行使用（与宿主 SaveBinaryFile 的 path 参数同一条约定）。
 */
import { saveBinaryFile } from "../bridge.js";

const FILTER = "PNG 图片 (*.png)|*.png|所有文件 (*.*)|*.*";

/** 导出目标覆盖（自动化用）：非空则跳过对话框 */
export function setExportTarget(path) {
  try {
    if (path) window.__mfExportTo = String(path);
    else delete window.__mfExportTo;
  } catch { /* 忽略 */ }
}

function exportTarget() {
  try { return String(window.__mfExportTo || ""); } catch { return ""; }
}

/** 页面名 → 安全的文件名前缀（/plot/2d → plot-2d） */
export function nameFromRoute(routePath, fallback = "plot") {
  const s = String(routePath || "").replace(/^\/+/, "").replace(/[^\w-]+/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
  return s || fallback;
}

function stamp(d = new Date()) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

/**
 * 把画布重绘到离屏画布（放大 + 不透明底），返回 dataURL。
 * @param {HTMLCanvasElement} canvas
 * @param {{scale?:number}} opts
 */
export function canvasToDataUrl(canvas, { scale = 0 } = {}) {
  if (!canvas || !canvas.width || !canvas.height) {
    return { ok: false, error: "画布还没准备好（宽高为 0）" };
  }
  const dpr = Math.max(1, Math.min(3, Number(window.devicePixelRatio) || 1));
  const k = scale > 0 ? scale : Math.max(2, dpr);      // 至少 2x，保证放大后不糊
  const out = document.createElement("canvas");
  out.width = Math.round(canvas.width * k);
  out.height = Math.round(canvas.height * k);
  const ctx = out.getContext("2d");
  if (!ctx) return { ok: false, error: "无法创建导出画布（浏览器拒绝 2D 上下文）" };

  // 不透明底色：优先用画布自己的背景色（深色主题下就是深色），取不到用白
  let bg = "#ffffff";
  try {
    const c = getComputedStyle(canvas).backgroundColor || "";
    const m = /rgba?\(([^)]+)\)/.exec(c);
    if (m) {
      const v = m[1].split(",").map((x) => parseFloat(x));
      const alpha = v.length >= 4 ? v[3] : 1;
      if (alpha > 0) {
        bg = v.length >= 4
          ? `rgba(${v[0]}, ${v[1]}, ${v[2]}, ${alpha})`
          : `rgb(${v[0]}, ${v[1]}, ${v[2]})`;
      }
    }
  } catch { /* 取不到就用白 */ }
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, out.width, out.height);

  ctx.imageSmoothingEnabled = true;
  if ("imageSmoothingQuality" in ctx) ctx.imageSmoothingQuality = "high";
  ctx.drawImage(canvas, 0, 0, out.width, out.height);

  let url = "";
  try { url = out.toDataURL("image/png"); } catch (e) {
    // 画布被跨源内容污染时浏览器会拒绝（本应用不会，但别让它变成一句"导出失败"）
    return { ok: false, error: "画布内容无法导出：" + (e?.message || e) };
  }
  return { ok: true, url, width: out.width, height: out.height };
}

/**
 * 导出画布到 PNG 文件。
 * @returns {{ok:boolean, path?:string, bytes?:number, width?:number, height?:number,
 *            canceled?:boolean, error?:string}}
 */
export function exportCanvas(canvas, { routePath = "", defaultName = "", note = "" } = {}) {
  const r = canvasToDataUrl(canvas);
  if (!r.ok) return r;
  const base = defaultName || `${nameFromRoute(routePath)}-${stamp()}.png`;
  const res = saveBinaryFile({
    title: note ? `导出图片 — ${note}` : "导出图片",
    defaultName: base,
    filter: FILTER,
    base64: r.url,
    path: exportTarget(),      // 自动化时非空 → 跳过对话框
  });
  if (!res || res.ok !== true) {
    return { ok: false, canceled: !!res?.canceled, error: res?.error || "保存失败" };
  }
  return { ok: true, path: res.path, bytes: res.bytes, width: r.width, height: r.height };
}
