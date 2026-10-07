// fake-ai-server.mjs — 本地假 AI 端点（OpenAI 兼容 /chat/completions）
//
// 为什么要有它：
//   · 端到端测试不能依赖真模型：**不要钱、不要 key、可复现**，而且异常路径
//     （断开、500、坏 JSON、没有 [DONE]）在真实端点上根本没法按需触发；
//   · 它跑在**真实 TCP + 真实 SSE** 上 —— 页面那一段 fetch/流读取、分帧、超时、取消、
//     错误分类全都真的执行一遍，不是被 mock 掉的。
//
// ⚠ CORS：页面（origin `https://mfmath.local`）现在**自己发请求**，所以这里必须像
//   真实端点那样把跨源头给全，并处理 OPTIONS 预检。否则浏览器会在预检阶段就拦下，
//   测试看到的会是"network 错误"而不是我们想验的场景。
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

/**
 * 跨源头。**每个响应**（含 4xx/5xx 与流式端点）都要带，否则浏览器读不到状态行与正文，
 * 测试会把"HTTP 401"看成"network 错误"。
 *
 * ⚠ `Access-Control-Allow-Headers` 不能只写 `*`：按 CORS 规范，
 * `Authorization` 属于 non-wildcard request-header name，通配符**不覆盖它**。
 * 所以这里除了 `*` 还把常见头点名列出 —— 不点名的话带密钥的预检会被浏览器拒掉。
 */
const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "Authorization, Content-Type, Accept, *",
  "access-control-allow-methods": "*",
  "access-control-max-age": "600",
};
const cors = (extra = {}) => ({ ...CORS, ...extra });

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
  // 工具调用系列（见下面的 toolChunk / TOOL_SCENARIOS）
  if (has("工具循环")) return "tool_loop";
  if (has("工具坏函数")) return "tool_badfn";
  if (has("工具错参数")) return "tool_badargs";
  if (has("工具越权")) return "tool_privilege";
  if (has("工具算")) return "tool_calc";
  // 「分步讲解」也是一种要引擎算的请求（计算页的「查看步骤」发的就是它）——
  // 让它也走工具场景，这样"分步"这条路在测试里同样能拿到引擎步骤
  if (has("分步")) return "tool_calc";
  return "normal";
}

/* ── 工具调用：假端点也要像真端点那样"先要工具、拿到结果再回答" ───────────
 *
 * 判据是**请求里有没有 role:"tool" 的消息**（无状态、可重复）：
 *   没有 → 发一个 tool_call（要引擎算）
 *   有   → 用引擎返回的内容收尾（并把那段内容原样回显，方便断言"引擎的值确实到了模型手里"）
 */
function toolChunk(index, name, argsJson, { id = "call_1" } = {}) {
  // 参数刻意切成碎片：真实端点也是这么流的，拼不回来就白测了
  const mid = Math.max(1, Math.floor(argsJson.length / 2));
  return [
    wrap({ tool_calls: [{ index, id, type: "function", function: { name, arguments: "" } }] }),
    wrap({ tool_calls: [{ index, function: { arguments: argsJson.slice(0, mid) } }] }),
    wrap({ tool_calls: [{ index, function: { arguments: argsJson.slice(mid) } }] }),
  ];
}

/** 各场景要发起的工具调用（fn / args 由场景决定，故意包含坏例子） */
const TOOL_SCENARIOS = {
  tool_calc: { name: "engine_call", args: { fn: "solve_quadratic", args: { expr: "x^2-4", var: "x" } }, claim: "答案应该是 99" },
  tool_badfn: { name: "engine_call", args: { fn: "definitely_not_an_engine_function", args: {} }, claim: "我用了一个不存在的函数" },
  tool_badargs: { name: "engine_call", args: { fn: "solve_quadratic", args: { exprr: "x^2-4" } }, claim: "参数名写错了" },
  // 越权：想调"写文件"这种非引擎工具，以及把引擎工具当成万能入口
  tool_privilege: { name: "engine_call", args: { fn: "SaveTextFile", args: { path: "C:/evil.txt", text: "x" } }, claim: "我想写文件" },
  tool_loop: { name: "engine_call", args: { fn: "gcd", args: { a: 12, b: 18 } }, claim: "一直算下去" },
};

const toolMessages = (messages) => messages.filter((m) => m.role === "tool");

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
  // ── CORS 预检：必须在任何路由判断**之前**答掉 ─────────────────────────
  // （包括错误状态那条路：预检不过，后面 401/500 的场景就永远看不到）
  if (req.method === "OPTIONS") {
    res.writeHead(204, cors());
    res.end();
    return;
  }
  if (req.method === "GET" && req.url === "/__requests") {
    res.writeHead(200, cors({ "content-type": "application/json" }));
    res.end(JSON.stringify(requests));
    return;
  }
  if (req.method === "POST" && req.url === "/__reset") {
    requests.length = 0;
    res.writeHead(200, cors({ "content-type": "application/json" }));
    res.end('{"ok":true}');
    return;
  }
  if (req.method === "GET" && req.url === "/__health") {
    res.writeHead(200, cors({ "content-type": "application/json" }));
    res.end('{"ok":true}');
    return;
  }
  if (!req.url?.endsWith("/chat/completions")) {
    res.writeHead(404, cors({ "content-type": "application/json" }));
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
    //
    // `origin` 是"请求真的由**页面**发出"的判据：浏览器跨源 fetch 一定会带 Origin，
    // 而宿主侧 HttpClient（旧架构）不会 —— 测试据此断言链路已经换成页面直连。
    requests.push({
      at: Date.now(),
      model: body.model ?? "",
      stream: !!body.stream,
      messageCount: messages.length,
      roles: messages.map((m) => m.role),
      body,
      origin: String(req.headers.origin || ""),
      authPresent: auth.startsWith("Bearer ") && auth.length > 12,
      authTail: auth ? auth.slice(-4) : "",
      scenario: pickScenario(prompt),
    });

    const scenario = pickScenario(prompt);

    if (scenario === "http500" || scenario === "http401") {
      const status = scenario === "http500" ? 500 : 401;
      res.writeHead(status, cors({ "content-type": "application/json" }));
      res.end(JSON.stringify({ error: { message: "fake endpoint 故意返回 " + status, type: "fake_error" } }));
      return;
    }

    // 流式端点同样要带跨源头（浏览器读流之前先看预检/实际响应）
    res.writeHead(200, cors({
      "content-type": "text/event-stream",
      "cache-control": "no-cache",
      connection: "keep-alive",
    }));

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

      // ── 工具调用 ────────────────────────────────────────────────────
      case "tool_calc":
      case "tool_badfn":
      case "tool_badargs":
      case "tool_privilege":
      case "tool_loop": {
        const spec = TOOL_SCENARIOS[scenario];
        const seen = toolMessages(messages);

        if (scenario === "tool_loop") {
          // 故意永远要工具：用来验证"轮次上限"真的拦得住（不然会一直烧）
          for (const c of toolChunk(0, spec.name, JSON.stringify(spec.args), { id: `call_${seen.length + 1}` })) res.write(c);
          res.write(wrap({}, "tool_calls"));
          res.write(usageChunk());
          res.write("data: [DONE]\n\n");
          res.end();
          return;
        }

        if (seen.length === 0) {
          // 第一轮：先要一次工具
          for (const c of toolChunk(0, spec.name, JSON.stringify(spec.args))) res.write(c);
          res.write(wrap({}, "tool_calls"));
          res.write(usageChunk());
          res.write("data: [DONE]\n\n");
          res.end();
          return;
        }

        // 第二轮：把工具返回的内容**原样**回显（断言"引擎的值到了模型手里"就靠它），
        // 再故意加一句与引擎无关的错数字 —— 界面上必须看到引擎的值，而不是这句错的
        const toolContent = String(seen[seen.length - 1].content || "");
        await streamText(res, `我收到工具结果：${toolContent}\n\n${spec.claim}`, 0);
        res.write(wrap({}, "stop"));
        res.write(usageChunk());
        res.write("data: [DONE]\n\n");
        res.end();
        return;
      }

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
