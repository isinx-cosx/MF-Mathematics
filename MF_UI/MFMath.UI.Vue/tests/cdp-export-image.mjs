// 导出图片端到端验证（真实宿主窗口里跑）
//
// v1 有「导出图片」（菜单里那一项，绘图工作区用 matplotlib savefig(dpi=200)），
// v2.0 之前没有：绘图结果只能看，不能存。这条测试要证明：
//   ① 六个绘图页面**都有**导出入口，点了真的会写文件（不是死按钮）；
//   ② 写出来的是**真 PNG**，且比屏幕上的画布大（按 2x 重绘，不是原尺寸糊图）；
//   ③ 背景不透明（透明背景粘进文档/看图器里是黑的，等于没导出）；
//   ④ 写不进去时**说出来**（比如路径不存在），不是静默什么都不发生。
//
// 「保存对话框」是模态的、自动化点不了，所以走 `window.__mfExportTo` 这个
// 自动化钩子（与宿主 SaveBinaryFile 的 path 参数同一条约定，见 lib/plot/exportImage.js）。
//
// 用法: node cdp-export-image.mjs   （宿主需带 --remote-debugging-port=9222 启动）
import { existsSync, readFileSync, rmSync } from "node:fs";
import { inflateSync } from "node:zlib";
import { join } from "node:path";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage() {
  for (let i = 0; i < 30; i++) {
    try {
      const list = await (await fetch("http://127.0.0.1:9222/json/list")).json();
      const p = list.find((t) => t.type === "page" && /mfmath\.local|index\.html/.test(t.url || ""));
      if (p) return p.webSocketDebuggerUrl;
    } catch { /* 等宿主 */ }
    await sleep(1000);
  }
  return null;
}
const wsUrl = await findPage();
if (!wsUrl) { console.error("未找到宿主页面"); process.exit(1); }
const ws = new WebSocket(wsUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0;
const send = (method, params, timeoutMs = 30000) => new Promise((resolve) => {
  const mid = ++id;
  const h = (ev) => {
    const d = JSON.parse(ev.data);
    if (d.id === mid) { clearTimeout(timer); ws.removeEventListener("message", h); resolve(d); }
  };
  const timer = setTimeout(() => {
    ws.removeEventListener("message", h);
    resolve({ timeout: true, result: { result: { value: "[超时]" } } });
  }, timeoutMs);
  ws.addEventListener("message", h);
  ws.send(JSON.stringify({ id: mid, method, params }));
});
const evalJs = async (expr) => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return "[异常] " + (r.result.exceptionDetails.text || "");
  return r.result?.result?.value;
};

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};
const goto = async (hash) => { await evalJs(`location.hash = ${JSON.stringify(hash)}; true`); await sleep(1500); };

/** 读 PNG 的 IHDR：宽高在固定偏移上（字节序大端） */
function pngSize(buf) {
  const magic = buf.subarray(0, 8).toString("hex");
  if (magic !== "89504e470d0a1a0a") return null;
  return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
}

/**
 * 取导出图**左上角那个像素**的 RGBA（用来验证"背景不透明"）。
 *
 * 为什么要解 PNG 而不是看 IHDR 的 colorType：canvas 的 toDataURL 一律输出
 * 带 alpha 通道的 PNG（colorType=6），哪怕每个像素的 alpha 都是 255 ——
 * 看 colorType 会把"像素不透明"误判成失败（第一版就是这么写的）。
 * 所以这里把 IDAT 解压出来看真实像素：第一行第一个像素的 alpha 与滤波方式无关
 * （左邻与上邻都视为 0），不需要完整实现 PNG 滤波器。
 */
function firstPixelAlpha(buf) {
  let off = 8;
  const idat = [];
  let colorType = 0;
  while (off + 8 <= buf.length) {
    const len = buf.readUInt32BE(off);
    const type = buf.subarray(off + 4, off + 8).toString("ascii");
    if (type === "IHDR") colorType = buf[off + 8 + 9];
    if (type === "IDAT") idat.push(buf.subarray(off + 8, off + 8 + len));
    off += 12 + len;
    if (type === "IEND") break;
  }
  if (!idat.length) return { ok: false, error: "没有 IDAT" };
  let raw = null;
  try { raw = inflateSync(Buffer.concat(idat)); } catch (e) {
    return { ok: false, error: "IDAT 解压失败：" + (e?.message || e) };
  }
  const channels = colorType === 6 ? 4 : (colorType === 2 ? 3 : 1);
  // raw[0] 是第一行的滤波类型，之后是像素
  const px = raw.subarray(1, 1 + channels);
  const alpha = channels === 4 ? px[3] : 255;   // 无 alpha 通道本身就是不透明
  return { ok: true, alpha, r: px[0], g: px[1], b: px[2], colorType, channels };
}

const tmpRoot = process.env.TEMP || ".";
const PAGES = [
  { route: "/plot/2d", name: "2D 函数绘图", btn: '.view-controls button[title*="导出图片"]' },
  { route: "/plot/3d", name: "3D 曲面", btn: '.view-controls button[title*="导出图片"]' },
  { route: "/plot/vector", name: "向量场", btn: '.view-controls button[title*="导出图片"]' },
  { route: "/plot/geometry", name: "自由几何", btn: '.view-controls button[title*="导出图片"]' },
  { route: "/plot/fractal", name: "分形", btn: '.view-controls button[title*="导出图片"]' },
  { route: "/plot/complex", name: "复平面", btn: ".btn" },   // 复平面是自己那一栏里的按钮
];

for (const p of PAGES) {
  const out = join(tmpRoot, `mf-export-${p.route.replace(/\W+/g, "-").replace(/^-|-$/g, "")}.png`);
  try { rmSync(out, { force: true }); } catch { /* 忽略 */ }
  console.log(`=== ${p.name}（${p.route}）===`);
  await goto(p.route);
  // 关键：**点之前**就要把自动化目标设好，否则会弹模态保存对话框
  // （对话框会把 WebView 的 UI 线程占住，后面所有 evaluate 全部超时——实测踩过）。
  await evalJs(`window.__mfExportTo = ${JSON.stringify(out)}; true`);
  // 复平面要先输入函数才会画；其它页面进来就有内容
  if (p.route === "/plot/complex") {
    await evalJs(`(() => {
      const f = document.querySelector('math-field, input');
      if (f) { f.value = "z^2"; f.dispatchEvent(new Event("input", { bubbles: true })); }
      const b = [...document.querySelectorAll('button')].find((x) => (x.textContent || "").trim() === "重绘");
      if (b) b.click();
      return true;
    })()`);
    await sleep(2500);
  }
  const canvasSize = await evalJs(`(() => {
    const c = document.querySelector('canvas');
    return c ? { w: c.width, h: c.height } : null;
  })()`);
  check("画布已有内容（宽高不为 0）", !!canvasSize && canvasSize.w > 0 && canvasSize.h > 0,
    canvasSize ? `${canvasSize.w}×${canvasSize.h}` : "没有 canvas");

  // 找不到按钮就是"这个页面没有导出入口"，属于真失败
  const clicked = await evalJs(`(() => {
    const sel = ${JSON.stringify(p.btn)};
    const list = [...document.querySelectorAll(sel)];
    const b = list.find((x) => /导出图片/.test(x.getAttribute('title') || '') || /导出图片/.test(x.textContent || ''));
    if (!b) return 'no-button';
    b.click();
    return 'clicked';
  })()`);
  check("页面上有「导出图片」按钮且能点", clicked === "clicked", String(clicked));
  await sleep(1200);

  const exists = existsSync(out);
  check("点了就真的写出文件", exists, out);
  if (!exists) { continue; }
  const buf = readFileSync(out);
  const size = pngSize(buf);
  check("是合法 PNG（魔数 + IHDR 可解析）", !!size, size ? `${size.w}×${size.h}，${(buf.length / 1024).toFixed(0)} KB` : buf.subarray(0, 8).toString("hex"));
  check("导出尺寸是屏幕画布的 2 倍（不是原尺寸糊图）",
    !!size && canvasSize && size.w >= canvasSize.w * 2 - 2 && size.h >= canvasSize.h * 2 - 2,
    size && canvasSize ? `${size.w}×${size.h} vs 画布 ${canvasSize.w}×${canvasSize.h}` : "—");
  // 背景不透明：看**像素**而不是 PNG 的颜色类型（canvas 一律输出 RGBA）
  const px = firstPixelAlpha(buf);
  check("背景不透明（左上角像素 alpha = 255，不是透明底）",
    px.ok === true && px.alpha === 255,
    px.ok ? `rgba(${px.r}, ${px.g}, ${px.b}, ${px.alpha})，colorType=${px.colorType}` : String(px.error));
  const status = await evalJs(`(document.querySelector('.status, .side-status') || {}).textContent || ''`);
  check("界面上说明了导出到哪里（不是静默）", /已导出图片/.test(String(status)), String(status).trim().slice(0, 70));
  try { rmSync(out, { force: true }); } catch { /* 忽略 */ }
  await evalJs(`delete window.__mfExportTo; true`);   // 每页清一次，避免钩子泄漏到下一页
}

console.log("=== 写不进去时必须说出来 ===");
await goto("/plot/2d");
const badPath = "Z:\\definitely-not-here\\x.png";
await evalJs(`window.__mfExportTo = ${JSON.stringify(badPath)}; true`);
await evalJs(`(() => {
  const b = [...document.querySelectorAll('.view-controls button')].find((x) => /导出图片/.test(x.getAttribute('title') || ''));
  if (b) b.click();
  return true;
})()`);
await sleep(1200);
const badStatus = await evalJs(`(document.querySelector('.side-status') || {}).textContent || ''`);
check("路径写不进去时给出失败原因（不静默）", /导出失败/.test(String(badStatus)), String(badStatus).trim().slice(0, 90));
check("失败时没有留下半个文件", !existsSync(badPath));

// 收尾：清掉自动化钩子，别影响用户后续点击（否则会绕过保存对话框）
await evalJs(`delete window.__mfExportTo; true`);
const cleared = await evalJs(`typeof window.__mfExportTo === "undefined"`);
check("测试结束后已清掉自动化钩子", cleared === true);

console.log(`RESULT|cdp-export-image|${pass}|${fail}`);
try { ws.close(); } catch { /* 忽略 */ }
process.exit(fail === 0 ? 0 : 1);
