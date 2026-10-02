// fake-ai-server.mjs — 本地假 AI 端点（OpenAI 兼容 /chat/completions）
//
// 为什么要有它：
//   · 端到端测试不能依赖真模型：**不要钱、不要 key、可复现**，而且异常路径
//     （断开、500、坏 JSON、没有 [DONE]）在真实端点上根本没法按需触发；
//   · 它跑在**真实 TCP + 真实 SSE** 上 —— 宿主里那段分帧、超时、取消、错误分类
//     全都真的执行一遍，不是被 mock 掉的。
//
// 场景由**最后一条 user 消息的内容**触发（类似 MVS Agent 的 scripts/fake-server.ts）：
//   含「断开」   → 吐两个字后粗暴掐断连接（验证 network / 吐了一半）
//   含「慢速」   → 每 300ms 一个字（验证"停止"与流式渲染）
//   含「挂起」   → 吐一个字后永不结束（验证超时）
//   含「500」    → 500 + JSON 错误体
//   含「401」    → 401（验证"密钥错"这一类）
//   含「坏JSON」 → 中间塞一条不是 JSON 的 data（验证 bad_sse_data 降级）
//   含「无usage」→ 正常结束但不发 usage 尾包（验证 missing_usage 降级）
//   含「无DONE」 → 不发 [DONE] 也不给 finish_reason（验证 truncated_stream 降级）
//   含「思考」   → 先发 reasoning_content 再发正文（验证 DeepSeek 式思维链）
//   含「公式」   → 正文里带回 $...$ 与 $$...$$（验证公式渲染路径）
//   默认         → 逐字吐一段话，带 finish_reason=stop 与 usage 尾包，最后 [DONE]
//
// 额外端点（给测试用，不在真实端点里）：
//   GET  /__requests  → 收到过的请求（**含原始 body**，隐私断言就靠它：
//                       比如"关掉历史开关后，第二个请求体里不该有第一轮的回复"）
//   POST /__reset     → 清空记录
//   GET  /__health    → {"ok":true}
import http from "node:http";

const PORT = Number(process.env.FAKE_AI_PORT || 8791);
const requests = [];

const chunk = (obj) => `data: ${JSON.stringify(obj)}\n\n`;
const wrap = (delta, finish = null) => chunk({
  id: "chatcmpl-fake", object: "chat.completion.chunk", created: Math.floor(Date.now() / 1000),
  model: "fake-model", choices: [{ index: 0, delta, finish_reason: finish }],
});

function pickScenario(text) {
  const has = (s) => text.includes(s);
  if (has("断开")) return "cut";
  if (has("慢速")) return "slow";
  if (has("挂起")) return "hang";
  if (has("500")) return "http500";
  if (has("401")) return "http401";
  if (has("坏JSON")) return "badjson";
  if (has("无usage")) return "nousage";
  if (has("无DONE")) return "nodone";
  if (has("思考")) return "reasoning";
  if (has("公式")) return "math";
  if (has("markdown")) return "markdown";
  return "normal";
}

/** markdown 全家桶 + 故意混进 HTML：用来断言"渲染了，但没有注入面" */
const MARKDOWN_SAMPLE = [
  "# 标题一",
  "",
  "**粗体** 与 *斜体* 与 `行内代码` 与 ~~删除~~。",
  "",
  "- 无序甲",
  "- 无序乙",
  "",
  "1. 有序甲",
  "2. 有序乙",
  "",
  "| 量 | 值 |",
  "| --- | ---: |",
  "| $x$ | 1 |",
  "| y | 2 |",
  "",
  "```python",
  "print('$这个不该被当公式$')",
  "```",
  "",
  "> 引用一行",
  "",
  "行内公式 $x^2+1$；占位符 $...$ 应当原样显示。",
  "",
  "安全链接 [示例](https://example.com/a) 与危险链接 [坏](javascript:alert(1))。",
  "",
  "<img src=x onerror=alert(1)> 与 <script>alert(2)</script> 都应当只是文本。",
].join("\n");

/** 让一段文字逐字发出去，可指定间隔 */
async function streamText(res, text, gapMs) {
  for (const ch of text) {
    res.write(wrap({ content: ch }));
    if (gapMs > 0) await new Promise((r) => setTimeout(r, gapMs));
  }
}

const server = http.createServer((req, res) => {
  if (req.method === "GET" && req.url === "/__requests") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify(requests));
    return;
  }
  if (req.method === "POST" && req.url === "/__reset") {
    requests.length = 0;
    res.writeHead(200, { "content-type": "application/json" });
    res.end('{"ok":true}');
    return;
  }
  if (req.method === "GET" && req.url === "/__health") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end('{"ok":true}');
    return;
  }
  if (!req.url?.endsWith("/chat/completions")) {
    res.writeHead(404, { "content-type": "application/json" });
    res.end('{"error":"only /chat/completions is implemented"}');
    return;
  }

  let raw = "";
  req.on("data", (p) => { raw += p; });
  req.on("end", async () => {
    let body = {};
    try { body = JSON.parse(raw || "{}"); } catch { /* 保留原文 */ }
    const messages = Array.isArray(body.messages) ? body.messages : [];
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    const prompt = String(lastUser?.content ?? "");
    const auth = String(req.headers.authorization || "");

    // 记录请求：**记 body 原文**，隐私断言要看"到底发出去了什么"。
    // 密钥只记"有没有 + 末四位"，绝不落全文（假端点也没必要持有它）。
    requests.push({
      at: Date.now(),
      model: body.model ?? "",
      stream: !!body.stream,
      messageCount: messages.length,
      roles: messages.map((m) => m.role),
      body,
      authPresent: auth.startsWith("Bearer ") && auth.length > 12,
      authTail: auth ? auth.slice(-4) : "",
      scenario: pickScenario(prompt),
    });

    const scenario = pickScenario(prompt);

    if (scenario === "http500" || scenario === "http401") {
      const status = scenario === "http500" ? 500 : 401;
      res.writeHead(status, { "content-type": "application/json" });
      res.end(JSON.stringify({ error: { message: "fake endpoint 故意返回 " + status, type: "fake_error" } }));
      return;
    }

    res.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-cache", connection: "keep-alive" });

    // 首包：role（真实端点也会先发一个只有 role 的 chunk）
    res.write(wrap({ role: "assistant", content: "" }));

    const usageChunk = () => chunk({
      id: "chatcmpl-fake", object: "chat.completion.chunk", created: Math.floor(Date.now() / 1000),
      model: "fake-model", choices: [],
      usage: { prompt_tokens: 42, completion_tokens: 7, total_tokens: 49 },
    });

    switch (scenario) {
      case "cut":
        res.write(wrap({ content: "好" }));
        res.write(wrap({ content: "的" }));
        // 粗暴掐断：不写 [DONE]、不写 finish_reason
        setTimeout(() => { try { res.socket?.destroy(); } catch { /* 忽略 */ } }, 20);
        return;

      case "slow":
        await streamText(res, "这是一段慢慢吐出来的文字，用来验证流式渲染与停止按钮。", 300);
        res.write(wrap({}, "stop"));
        res.write(usageChunk());
        res.write("data: [DONE]\n\n");
        res.end();
        return;

      case "hang":
        res.write(wrap({ content: "占" }));
        // 之后永不结束：由客户端的超时/取消来收尾（服务端保持连接挂着）
        return;

      case "badjson":
        res.write(wrap({ content: "前半" }));
        res.write("data: {这不是 JSON\n\n");
        res.write(wrap({ content: "后半" }));
        res.write(wrap({}, "stop"));
        res.write(usageChunk());
        res.write("data: [DONE]\n\n");
        res.end();
        return;

      case "nousage":
        await streamText(res, "这条回复没有 usage 尾包。", 0);
        res.write(wrap({}, "stop"));
        res.write("data: [DONE]\n\n");
        res.end();
        return;

      case "nodone":
        await streamText(res, "这条回复既没有 [DONE] 也没有 finish_reason。", 0);
        res.end();
        return;

      case "reasoning":
        for (const s of ["用户问的是", "一个数学问题，", "我应该先解释思路。"]) {
          res.write(chunk({
            id: "chatcmpl-fake", object: "chat.completion.chunk", created: Math.floor(Date.now() / 1000),
            model: "fake-model", choices: [{ index: 0, delta: { reasoning_content: s }, finish_reason: null }],
          }));
        }
        await streamText(res, "先看定义，再看它满足的条件。", 0);
        res.write(wrap({}, "stop"));
        res.write(usageChunk());
        res.write("data: [DONE]\n\n");
        res.end();
        return;

      case "math":
        await streamText(res, "由定义可得 $f'(x)=2x$，于是", 0);
        res.write(wrap({ content: "$$\\int_0^1 2x\\,dx = 1$$" }));
        await streamText(res, "这就是结果。", 0);
        res.write(wrap({}, "stop"));
        res.write(usageChunk());
        res.write("data: [DONE]\n\n");
        res.end();
        return;

      case "markdown":
        await streamText(res, MARKDOWN_SAMPLE, 0);
        res.write(wrap({}, "stop"));
        res.write(usageChunk());
        res.write("data: [DONE]\n\n");
        res.end();
        return;

      default: {
        // 默认回复里**带上收到的消息条数**：测试可以据此断言隐私开关是否生效
        // （关掉历史时第二个请求仍然只有 2~3 条消息，而不是整段对话）
        const text = `收到 ${messages.length} 条消息。1+1=3。`;
        await streamText(res, text, 0);
        res.write(wrap({}, "stop"));
        res.write(usageChunk());
        res.write("data: [DONE]\n\n");
        res.end();
      }
    }
  });
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`[fake-ai] listening on http://127.0.0.1:${PORT}/v1`);
});
