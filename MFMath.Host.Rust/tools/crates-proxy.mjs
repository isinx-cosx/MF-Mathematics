/**
 * crates-proxy.mjs — 本机开发用的 crates.io 明文代理（**只在开发机上用，不是产品的一部分**）
 *
 * 为什么存在：
 *   这台机器上 Schannel 在受限令牌下不可用（`AcquireCredentialsHandle failed:
 *   SEC_E_NO_CREDENTIALS`），于是 cargo / curl 这类走 Schannel 的客户端都取不了包，
 *   而 Node 自带 OpenSSL 可以。这个代理让 **Node 去 HTTPS 取**、cargo 只走 **明文 HTTP**，
 *   两端各自用能用的 TLS 栈，问题消失。
 *
 * 用法：
 *   node tools/crates-proxy.mjs                 # 默认 127.0.0.1:8432
 *   PORT=9000 node tools/crates-proxy.mjs
 *
 * 然后在 MFMath.Host.Rust/.cargo/config.toml 里（本文件已带一份）：
 *   [source.crates-io]
 *   replace-with = "local-http"
 *   [source.local-http]
 *   registry = "sparse+http://127.0.0.1:8432/index/"
 *
 * 路由：
 *   /index/config.json                      → index.crates.io 的 config.json，但把 dl 改写成指向本代理
 *   /index/<sparse index path>              → index.crates.io/<path>
 *   /crates/<name>/<version>/download       → static.crates.io 的 .crate 包
 *
 * 它只做转发与改写，不缓存（要缓存就直接给它加一层 Map 即可）。
 */
import http from "node:http";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";

const PORT = Number(process.env.PORT || 8432);
const HOST = "127.0.0.1";
const INDEX_UPSTREAM = "https://index.crates.io";
const STATIC_UPSTREAM = "https://static.crates.io/crates";

const self = `http://${HOST}:${PORT}`;

function log(...a) {
  const t = new Date().toTimeString().slice(0, 8);
  console.log(`[${t}]`, ...a);
}

/**
 * 取上游，**失败重试**。
 * 为什么要重试：上游偶尔会在长响应中途重置连接（tauri 那个 2 MB 的索引条目最容易），
 * 单次失败就让 cargo 整个报错，代价太大。
 */
async function fetchUpstream(url, attempts = 3) {
  let last;
  for (let i = 1; i <= attempts; i++) {
    try {
      const r = await fetch(url, { redirect: "follow" });
      if (r.ok || i === attempts) return r;
      last = `HTTP ${r.status}`;
    } catch (e) {
      last = e?.message || e;
    }
    await new Promise((r) => setTimeout(r, 300 * i));
  }
  throw new Error(`上游取不到 ${url}：${last}`);
}

/** 上游取回 → 直接写回给 cargo；只透传必要头 */
async function pipe(url, res, rewrite) {
  const upstream = await fetchUpstream(url);
  if (!upstream.ok) {
    res.writeHead(upstream.status, { "content-type": "text/plain" });
    res.end(`upstream ${upstream.status} for ${url}`);
    return;
  }
  const type = upstream.headers.get("content-type") || "application/octet-stream";
  if (rewrite) {
    const text = rewrite(await upstream.text());
    res.writeHead(200, { "content-type": type, "cache-control": "no-store" });
    res.end(text);
    return;
  }
  /* ⚠ 这里**必须**用 pipeline 而不是 `stream.pipe(res)`：
   * `.pipe()` 不转发错误，上游一旦中途重置就会冒出**未处理的 'error' 事件**，
   * 在 Node 上等于**直接杀进程** —— 用户看到的是 cargo 报
   * "Failure when receiving data from the peer (Connection was reset)"，
   * 而代理自己已经没了（2026-10-07 排查 `cargo build` 反复失败时找到的）。 */
  try {
    res.writeHead(200, { "content-type": type });
    await pipeline(Readable.fromWeb(upstream.body), res);
  } catch (e) {
    log("pipe 中断", url, e?.message || e);
    try { res.destroy(); } catch { /* 已经断了 */ }
  }
}

/* 进程级兜底：**任何**漏网的异步异常都不许把代理带走 ——
 * 代理一死，cargo 就会看到 "Connection was reset"，而错误信息里完全看不出是代理挂了。 */
process.on("uncaughtException", (e) => log("uncaughtException（继续运行）", e?.message || e));
process.on("unhandledRejection", (e) => log("unhandledRejection（继续运行）", e?.message || e));

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, self);
  const path = decodeURIComponent(url.pathname);
  try {
    // ① 稀疏索引的配置：把 dl 指回本代理，否则 cargo 又会去 static.crates.io 走 Schannel
    if (path === "/index/config.json") {
      log("config.json");
      await pipe(`${INDEX_UPSTREAM}/config.json`, res, (text) => {
        try {
          const cfg = JSON.parse(text);
          cfg.dl = `${self}/crates`;
          return JSON.stringify(cfg);
        } catch {
          return text; // 解析不了就原样透传（cargo 会自己报错，不静默）
        }
      });
      return;
    }
    // ② 稀疏索引条目：/index/se/rd/serde 之类
    if (path.startsWith("/index/")) {
      const rest = path.slice("/index/".length);
      log("index", rest);
      await pipe(`${INDEX_UPSTREAM}/${rest}`, res);
      return;
    }
    // ③ .crate 包下载：/crates/<name>/<version>/download
    if (path.startsWith("/crates/")) {
      const rest = path.slice("/crates/".length);
      log("crate", rest);
      await pipe(`${STATIC_UPSTREAM}/${rest}`, res);
      return;
    }
    res.writeHead(404, { "content-type": "text/plain" });
    res.end("not found: " + path);
  } catch (e) {
    log("ERROR", path, e?.message || e);
    try {
      res.writeHead(502, { "content-type": "text/plain" });
      res.end("proxy error: " + (e?.message || e));
    } catch { /* 头已发出 */ }
  }
});

server.listen(PORT, HOST, () => {
  log(`crates 代理已启动： ${self}/index/   （上游 ${INDEX_UPSTREAM} / ${STATIC_UPSTREAM}）`);
});
