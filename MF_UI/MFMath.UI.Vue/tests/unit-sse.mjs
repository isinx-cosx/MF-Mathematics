// unit-sse.mjs — SSE 分帧的离线单元测试（**不需要宿主、不需要网络**）
//
// 这是把协议层放进 TS 换来的最大好处：分帧是纯函数，用 Node 直接跑就行。
// 换成宿主侧 C# 实现时，同样的保证只能靠端到端用例（起窗口、连假端点）来验，
// 而"任意字节切分"这种性质在端到端里几乎不可能稳定复现。
//
// 被测对象：src/lib/ai/sse.ts（移植自 MVS Agent 的 src/model/sse.ts）
// 样本：tests/fixtures/*.sse（同样取自 MVS Agent 的录制样本）
//
// 用法: node tests/unit-sse.mjs
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseSSE } from "../src/lib/ai/sse.ts";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FX = path.join(HERE, "fixtures");

let pass = 0, fail = 0;
const check = (label, ok, detail = "") => {
  ok ? pass++ : fail++;
  console.log(`  ${ok ? "[OK]" : "[FAIL]"} ${label}${detail ? "   " + detail : ""}`);
};

const loadFixture = (name) => readFileSync(path.join(FX, name), "utf8");

async function* fromChunks(chunks) {
  for (const c of chunks) yield c;
}

/** 把 UTF-8 文本按固定字节数切开再解析，模拟真实网络分片 */
async function parseWithChunkSize(text, chunkSize) {
  const bytes = new TextEncoder().encode(text);
  const chunks = [];
  for (let i = 0; i < bytes.length; i += chunkSize) chunks.push(bytes.slice(i, i + chunkSize));

  const events = [];
  for await (const ev of parseSSE(fromChunks(chunks))) events.push(ev);
  return events;
}

console.log("=== 基本形状 ===");
{
  const ev = await parseWithChunkSize("data: hello\n\ndata: world\n\n", 4096);
  check("两个最简单的事件", JSON.stringify(ev) === JSON.stringify([
    { event: "", data: "hello" }, { event: "", data: "world" }]), JSON.stringify(ev));
}

console.log("=== 核心：整份样本在任意字节切分下结果完全一致 ===");
for (const fx of ["text-basic.sse", "reasoning-deepseek.sse", "tool-calls.sse", "no-usage.sse"]) {
  const text = loadFixture(fx);
  const baseline = await parseWithChunkSize(text, text.length);
  let ok = baseline.length > 0;
  let detail = `${baseline.length} 个事件`;
  for (const size of [1, 2, 3, 5, 17, 64, 333]) {
    const sliced = await parseWithChunkSize(text, size);
    if (JSON.stringify(sliced) !== JSON.stringify(baseline)) {
      ok = false;
      detail = `chunkSize=${size} 时结果不一致（${sliced.length}/${baseline.length} 个事件）`;
      break;
    }
  }
  check(`${fx} 在 1/2/3/5/17/64/333 字节切分下一致`, ok, detail);
}

console.log("=== 规范细节 ===");
{
  const text = loadFixture("text-basic.sse");
  const ev = await parseWithChunkSize(text, text.length);
  check("text-basic 有 6 个事件且以 [DONE] 收尾",
    ev.length === 6 && ev.at(-1)?.data === "[DONE]", `${ev.length} 个，末尾=${JSON.stringify(ev.at(-1)?.data)}`);
}
{
  // chunkSize=1 会把每个 \r 与 \n 拆到不同 chunk，专门打这条路径
  const ev = await parseWithChunkSize("data: a\r\n\r\ndata: b\r\n\r\n", 1);
  check("CRLF 归一化（含被切散的 \\r | \\n）",
    JSON.stringify(ev) === JSON.stringify([{ event: "", data: "a" }, { event: "", data: "b" }]), JSON.stringify(ev));
}
{
  const ev = await parseWithChunkSize("data: line1\ndata: line2\n\n", 4096);
  check("多行 data 用 \\n 连接", ev.length === 1 && ev[0].data === "line1\nline2", JSON.stringify(ev));
}
{
  const ev = await parseWithChunkSize(": keep-alive\nevent: ping\ndata: {}\n\n", 4096);
  check("注释行跳过、event 字段保留",
    ev.length === 1 && ev[0].event === "ping" && ev[0].data === "{}", JSON.stringify(ev));
}
{
  const ev = await parseWithChunkSize("data:no-space\n\ndata:  two-spaces\n\n", 4096);
  check("冒号后只去掉一个空格",
    JSON.stringify(ev) === JSON.stringify([{ event: "", data: "no-space" }, { event: "", data: " two-spaces" }]),
    JSON.stringify(ev));
}
{
  const ev = await parseWithChunkSize("data: tail", 3);
  check("末尾没有空行收尾的事件也会发出", ev.length === 1 && ev[0].data === "tail", JSON.stringify(ev));
}
{
  const text = `data: ${JSON.stringify({ t: "中文😀混合" })}\n\n`;
  let ok = true;
  let detail = "";
  for (const size of [1, 2, 3, 5]) {
    const ev = await parseWithChunkSize(text, size);
    if (ev.length !== 1 || JSON.parse(ev[0].data).t !== "中文😀混合") {
      ok = false;
      detail = `chunkSize=${size} 时多字节字符被切坏`;
      break;
    }
  }
  check("多字节 UTF-8 字符跨 chunk 不被切坏", ok, detail);
}
{
  const ev = await parseWithChunkSize("\n\n: x\n\n\n\n", 4096);
  check("纯空行与纯注释不产生事件", ev.length === 0, JSON.stringify(ev));
}

console.log(`RESULT|unit-sse|${pass}|${fail}`);
process.exit(fail === 0 ? 0 : 1);
