// fake-search-server.mjs — 本地假搜索端点（DuckDuckGo 结果页 / IA / Wolfram / SearXNG）
//
// 为什么要有它：搜索的三条后端全是**外部站点的 HTML/JSON 形状**，而这类形状最容易随对方
// 改版而碎。端到端用例需要能按需触发"正常 / 500 / 超时 / 改版 / 空结果"这些情况 —— 真站点
// 上做不到，而且不该拿真站点跑测试。
//
// 场景由查询词触发：
//   含「500」   → 500 + JSON 错误体
//   含「慢速」  → 延迟 3 秒再回（测超时与取消）
//   含「空」    → 结构合法但没有任何结果块（测"没有找到结果"这个状态）
//   含「改版」  → 返回一坨没有结果块的短 HTML（测 parse 分类）
//   默认        → DDG：3 条结果 + 摘要；SearXNG：2 条结果；Wolfram：一段纯文本答案
//
// 给测试用的端点：GET /__requests（**记录请求**，含是否带 appid）、POST /__reset、GET /__health
import http from "node:http";

const PORT = Number(process.env.FAKE_SEARCH_PORT || 8792);
const requests = [];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** 一坨长度够长、但没有结果块的 HTML（用来区分"空结果"与"形状变了"） */
function emptyPage() {
  return "<html><body><div class=\"no-results\">没有找到结果</div>"
    + "<!-- " + "padding ".repeat(400) + " --></body></html>";
}

function ddgHtml(q) {
  if (q.includes("空") || q.includes("改版")) {
    return q.includes("改版") ? "<html><body>nope</body></html>" : emptyPage();
  }
  const items = [
    ["黎曼猜想 - 维基百科", "https://zh.wikipedia.org/wiki/黎曼猜想", "黎曼猜想是关于 ζ 函数非平凡零点实部都为 1/2 的猜想。"],
    ["素数定理", "https://example.org/prime", "π(x) ~ x / ln x，可由 ζ(s) 的解析性质推出。"],
    ["零点分布", "https://example.org/zeros", "前 10^13 个非平凡零点都满足 Re(s)=1/2。"],
  ];
  let html = "<html><body>";
  for (const [t, u, s] of items) {
    // 刻意做成 DDG 的真实形状：包一层跳转链接 + 结果块里带 <b>
    html += `<a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=${encodeURIComponent(u)}&rut=abc">${t}</a>`;
    html += `<a class="result__snippet" href="${u}">${s.replace("1/2", "<b>1/2</b>")}</a>`;
  }
  // 混一条坏协议链接：解析器必须把它丢掉
  html += "<a class=\"result__a\" href=\"javascript:alert(1)\">坏链接</a>";
  return html + "</body></html>";
}

function ddgIa(q) {
  return JSON.stringify({
    AbstractText: q.includes("空") || q.includes("改版") ? "" : `<b>${q}</b> 的摘要：${q} 是数学里的一个概念。`,
    Heading: q,
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://127.0.0.1:${PORT}`);

  if (url.pathname === "/__requests") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify(requests));
    return;
  }
  if (url.pathname === "/__reset") {
    requests.length = 0;
    res.writeHead(200, { "content-type": "application/json" });
    res.end('{"ok":true}');
    return;
  }
  if (url.pathname === "/__health") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end('{"ok":true}');
    return;
  }

  const q = url.searchParams.get("q") || url.searchParams.get("i") || "";
  const appid = url.searchParams.get("appid") || "";
  requests.push({
    at: Date.now(),
    path: url.pathname,
    query: q,
    hasAppid: appid.length > 6,
    appidTail: appid ? appid.slice(-4) : "",
    raw: url.pathname + url.search,
  });

  if (q.includes("500")) {
    res.writeHead(500, { "content-type": "application/json" });
    res.end('{"error":"fake search 故意返回 500"}');
    return;
  }
  if (q.includes("慢速")) await sleep(3000);

  if (url.pathname.startsWith("/ddg/ia")) {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(ddgIa(q));
    return;
  }
  if (url.pathname.startsWith("/ddg/html")) {
    res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
    res.end(ddgHtml(q));
    return;
  }
  if (url.pathname.startsWith("/wolfram")) {
    if (!appid) { res.writeHead(403, { "content-type": "text/plain" }); res.end("Invalid appid"); return; }
    res.writeHead(200, { "content-type": "text/plain; charset=utf-8" });
    res.end(`Wolfram 简答：${q} → 结果是 42`);
    return;
  }
  if (url.pathname.startsWith("/searxng/search")) {
    if (url.searchParams.get("format") !== "json") {
      res.writeHead(200, { "content-type": "text/html" });
      res.end("<html><body>这是 HTML，不是 JSON</body></html>");
      return;
    }
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({
      results: q.includes("空") ? [] : [
        { title: "自建实例结果甲", url: "https://self.example/a", content: "内容甲", engine: "searxng" },
        { title: "自建实例结果乙", url: "https://self.example/b", content: "内容乙", engine: "searxng" },
      ],
    }));
    return;
  }

  res.writeHead(404, { "content-type": "application/json" });
  res.end('{"error":"unknown fake endpoint"}');
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`[fake-search] listening on http://127.0.0.1:${PORT}`);
});
