/**
 * 控制台桥封装（JS 侧）
 *
 * 宿主对象：window.chrome.webview.hostObjects.sync.con（见 MFMath.Host/ConsoleBridge.cs）
 * 设计：组件是**可选下载**（CPython / MinGW），运行用"开始 + 轮询"，
 *       因为同步跨桥调用会把页面阻塞到返回，控制台可能跑几十秒。
 *
 * 无宿主（浏览器预览）时全部优雅降级：返回 null / 明确说明，界面显示提示而不是报错。
 */
"use strict";

function conObj() {
  try {
    return window.chrome?.webview?.hostObjects?.sync?.con ?? null;
  } catch {
    return null;
  }
}

export function isConsoleHosted() {
  return conObj() !== null;
}

function parse(text) {
  if (text == null) return null;
  if (typeof text === "object") return text;
  try {
    return JSON.parse(String(text));
  } catch {
    return null;
  }
}

/** 组件状态：{engineDir, python:{installed,version,path,bytes,payloadAvailable,warning}, cpp:{...}} */
export function components() {
  const c = conObj();
  if (!c) return null;
  try {
    return parse(c.Components());
  } catch (e) {
    return { error: String(e && e.message ? e.message : e) };
  }
}

/** 开始安装组件，返回 jobId（用 installStatus 轮询） */
export function installComponent(name) {
  const c = conObj();
  if (!c) return null;
  try {
    return String(c.Install(name));
  } catch (e) {
    return null;
  }
}

export function installStatus(jobId) {
  const c = conObj();
  if (!c) return null;
  try {
    return parse(c.InstallStatus(jobId));
  } catch {
    return null;
  }
}

/** 取消正在进行的安装/下载（已下载的部分会保留，下次接着下） */
export function cancelInstall(jobId) {
  const c = conObj();
  if (!c) return null;
  try {
    return parse(c.CancelInstall(jobId));
  } catch {
    return null;
  }
}

/**
 * 卸载一个可选组件：删掉它的安装目录，保留下载缓存（重装可省一次下载）。
 * 只接受 "python" / "cpp"，宿主侧会拒绝其它名字。
 * @returns {{ok:boolean, removed?:boolean, bytes?:number, error?:string}|null}
 */
export function uninstallComponent(name) {
  const c = conObj();
  if (!c) return null;
  try {
    return parse(c.Uninstall(name));
  } catch (e) {
    return { ok: false, error: String(e && e.message ? e.message : e) };
  }
}

/** 换组件下载源（企业内网镜像 / 本地测试）。传空字符串恢复成默认的官网地址。 */
export function setDownloadBase(url) {
  const c = conObj();
  if (!c) return null;
  try {
    return parse(c.SetDownloadBase(url ?? ""));
  } catch {
    return null;
  }
}

/** 开始运行：language = "python" | "cpp"，返回 runId */
export function consoleStart(language, code, stdin = "") {
  const c = conObj();
  if (!c) return null;
  try {
    return String(c.Start(language, code, stdin));
  } catch (e) {
    return null;
  }
}

/** 取回输出：{state:"queued|running|done", running, exitCode, timedOut, elapsedMs, stdout, stderr, truncated} */
export function consolePoll(runId) {
  const c = conObj();
  if (!c) return null;
  try {
    return parse(c.Poll(runId));
  } catch {
    return null;
  }
}

export function consoleStop(runId) {
  const c = conObj();
  if (!c) return null;
  try {
    return parse(c.Stop(runId));
  } catch {
    return null;
  }
}

/** 退出前清场（兜底；正常由宿主关窗时自己清） */
export function consoleStopAll() {
  const c = conObj();
  if (!c) return null;
  try {
    return parse(c.StopAll());
  } catch {
    return null;
  }
}
