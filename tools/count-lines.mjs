/**
 * tools/count-lines.mjs — 统计 MM2.0 的代码行数（无依赖，直接 `node tools/count-lines.mjs`）
 *
 * 三条原则，避免"数字好看但没意义"：
 *
 * 1. **生成物与第三方一律不计**：`node_modules`、`dist`、`build`、`bin`、`obj`、`.vs`、`__pycache__`…
 *    这些目录会被**单独列出来**（文件数 + 体积），所以"被排除了什么"是看得见的，
 *    而不是藏在总数里让人猜。
 *
 * 2. **区分"代码行 / 注释行 / 空行"**：注释识别是**启发式**（行注释前缀 + `/* *​/` 与 `<!-- -->` 块），
 *    各语言规则不同（例如 Python 的三引号文档串会算成代码、Markdown 全是散文）。
 *    所以表格里给的是"约"，代码行 = 总行 − 空行 − 注释行。
 *
 * 3. **分区统计**：光看总数没意义。这里同时按"区域"（数学库 / C++ 宿主 / Python / 前端 / 文档…）
 *    分组，因为 MM2.0 是 C# + Vue + C++ + Python 的混合体，各块规模差别很大。
 *
 * 用法：node tools/count-lines.mjs [--json]
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const AS_JSON = process.argv.includes("--json");

/** 生成物 / 第三方 / 编辑器缓存：不参与统计，但会单独汇报 */
const SKIP_DIRS = new Set([
  ".git", "node_modules", "dist", "build", "bin", "obj", ".vs", ".vscode", ".idea",
  "__pycache__", ".venv", "venv", "packages", "TestResults", "coverage",
  ".pytest_cache", "publish", "out", "target", "artifacts", ".dsh", "tmp", "temp",
]);

const LANG_BY_EXT = {
  ".cs": "C#",
  ".vue": "Vue 单文件组件",
  ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
  ".ts": "TypeScript", ".tsx": "TSX", ".jsx": "JSX",
  ".cpp": "C++", ".cc": "C++", ".cxx": "C++",
  ".h": "C/C++ 头", ".hpp": "C/C++ 头", ".hxx": "C/C++ 头",
  ".py": "Python",
  ".ps1": "PowerShell", ".psm1": "PowerShell",
  ".sh": "Shell", ".bash": "Shell",
  ".xaml": "XAML",
  ".csproj": "MSBuild", ".sln": "MSBuild", ".props": "MSBuild", ".targets": "MSBuild",
  ".json": "JSON（数据/配置）",
  ".md": "Markdown（文档）",
  ".html": "HTML", ".css": "CSS", ".scss": "CSS",
  ".yml": "YAML", ".yaml": "YAML",
  ".sql": "SQL",
  ".tex": "LaTeX",
  ".txt": "纯文本",
};

/** 行注释前缀（按语言）。注释识别是启发式：够用，但不假装精确。 */
const LINE_COMMENT = {
  "C#": ["//"], "Vue 单文件组件": ["//"], "JavaScript": ["//"], "TypeScript": ["//"],
  "TSX": ["//"], "JSX": ["//"], "C++": ["//"], "C/C++ 头": ["//"],
  "Python": ["#"], "PowerShell": ["#"], "Shell": ["#"], "YAML": ["#"],
  "SQL": ["--"], "HTML": ["<!--"], "XAML": ["<!--"],
};
/** 块注释（可跨行）。顺序有意义：先匹配更长的开标记。 */
const BLOCK_COMMENT = {
  "C#": [["/*", "*/"]], "Vue 单文件组件": [["/*", "*/"], ["<!--", "-->"]],
  "JavaScript": [["/*", "*/"]], "TypeScript": [["/*", "*/"]], "TSX": [["/*", "*/"]], "JSX": [["/*", "*/"]],
  "C++": [["/*", "*/"]], "C/C++ 头": [["/*", "*/"]], "CSS": [["/*", "*/"]],
  "HTML": [["<!--", "-->"]], "XAML": [["<!--", "-->"]],
  "PowerShell": [["<#", "#>"]],
  // Python 的三引号文档串：整段算注释（近似 —— 赋给变量的多行字符串会被误判成注释，
  // 但 MM2.0 里没有这种写法，值得换来"文档串不再虚增代码行"）
  "Python": [["\"\"\"", "\"\"\""], ["'''", "'''"]],
};

const skipReport = new Map(); // 目录名 → { files, bytes }
const byLang = new Map();     // 语言 → { files, total, blank, comment, code }
const byArea = new Map();     // 区域 → { files, code, data, docs, total }
const byKind = new Map();     // code | data | docs → { files, total, blank, comment, code }
const biggest = [];           // 最大的若干文件（含数据文件，便于识别"生成物混进来"）

function areaOf(rel) {
  const p = rel.split(path.sep);
  if (p[0] === "MF_Mathematics") return "MF_Mathematics";   // 语言构成由 labels 自动附上，别手写"C#"
  if (p[0] === "MFMath.Host") {
    if (p[1] === "cpp") return "MFMath.Host/cpp";
    if (p[1] === "python") return "MFMath.Host/python";
    if (p[1] === "tools") return "MFMath.Host/tools";
    return "MFMath.Host";
  }
  if (p[0] === "MF_UI") {
    if (p[2] === "src") return "MF_UI/src（前端源码）";
    if (p[2] === "tests") return "MF_UI/tests（CDP 自动化测试）";
    if (p[2] === "tools" || p[2] === "scripts") return "MF_UI（构建工具）";
    if (p[2] === "public") return "MF_UI/public（静态资源）";
    return "MF_UI（工程配置）";
  }
  if (p[0] === "docs") return "docs（文档与数据）";
  if (p[0] === "tools") return "tools（仓库脚本）";
  return p[0];
}

/**
 * 文件三级分类：手写源码 / 数据与锁文件 / 文档。
 * 为什么要分：JSON 里混着构建产物（引擎签名、压力测试数据、教程数据、lock 文件），
 * 把它们算进"代码行"会让数字虚高 —— 上一版统计里 24k 行 JSON 就占了很大一块。
 */
function kindOf(rel, lang) {
  const name = path.basename(rel).toLowerCase();
  if (name.endsWith("-lock.json") || name === "package-lock.json" || name.endsWith(".lock")) return "data";
  if (lang === "JSON（数据/配置）" || lang === "YAML") return "data";
  if (lang === "Markdown（文档）" || lang === "LaTeX" || lang === "纯文本") return "docs";
  return "code";
}

/**
 * 数一个文件的行：**只有真正带代码的行才算"代码行"**。
 *
 *   total = blank + comment + code
 *
 * 规则（按要求收紧）：
 *   · 空行 → blank；
 *   · 整行都是注释、或处在块注释/文档串内部 → comment；
 *   · 代码后面跟 `// 说明` → **算代码**（这一行确实有代码）；
 *   · 只有 `{` `}` `);` 这类结构符号的行 → 算代码（是真实语法，不是注释）。
 */
function countLines(text, lang) {
  const lines = text.split(/\r?\n/);
  if (lines.length && lines[lines.length - 1] === "") lines.pop();

  const blocks = BLOCK_COMMENT[lang] || [];
  const prefixes = LINE_COMMENT[lang] || [];
  let blank = 0;
  let comment = 0;
  let code = 0;
  let inBlock = null;

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { blank++; continue; }

    // ① 块注释/文档串内部
    if (inBlock) {
      comment++;
      if (line.includes(inBlock[1])) inBlock = null;
      continue;
    }

    // ② JSX/TSX 里注释常写成 {/* ... */}：剥掉前导 { 再判断，否则会被当成代码
    const probe = line.startsWith("{") ? line.slice(1).trimStart() : line;

    // ③ 块注释开头
    let opened = false;
    for (const [open, close] of blocks) {
      if (!probe.startsWith(open)) continue;
      comment++;
      // 同一行就闭合 → 不进入块状态；否则记住块标记
      if (!probe.slice(open.length).includes(close)) inBlock = [open, close];
      opened = true;
      break;
    }
    if (opened) continue;

    // ④ 行注释
    if (prefixes.some((p) => line.startsWith(p))) { comment++; continue; }

    code++;
  }
  return { total: lines.length, blank, comment, code };
}

function walk(dir, relBase = "") {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const abs = path.join(dir, entry.name);
    const rel = relBase ? path.join(relBase, entry.name) : entry.name;
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) {
        // 单独统计被排除的目录规模
        let files = 0;
        let bytes = 0;
        const stack = [abs];
        while (stack.length) {
          const d = stack.pop();
          for (const e of fs.readdirSync(d, { withFileTypes: true })) {
            const a = path.join(d, e.name);
            if (e.isDirectory()) stack.push(a);
            else { files++; try { bytes += fs.statSync(a).size; } catch { /* 并发删除 */ } }
          }
        }
        const key = rel;
        skipReport.set(key, { files, bytes });
        continue;
      }
      walk(abs, rel);
      continue;
    }
    if (!entry.isFile()) continue;

    const ext = path.extname(entry.name).toLowerCase();
    const lang = LANG_BY_EXT[ext];
    if (!lang) continue;

    let buf;
    try { buf = fs.readFileSync(abs); } catch { continue; }
    // 二进制（含 NUL）直接跳过，免得把图片/字体当文本数
    if (buf.subarray(0, 8192).includes(0)) continue;

    const stat = countLines(buf.toString("utf8"), lang);
    const kind = kindOf(rel, lang);

    const hit = byLang.get(lang) || { files: 0, total: 0, blank: 0, comment: 0, code: 0 };
    hit.files++; hit.total += stat.total; hit.blank += stat.blank; hit.comment += stat.comment; hit.code += stat.code;
    byLang.set(lang, hit);

    const kh = byKind.get(kind) || { files: 0, total: 0, blank: 0, comment: 0, code: 0 };
    kh.files++; kh.total += stat.total; kh.blank += stat.blank; kh.comment += stat.comment; kh.code += stat.code;
    byKind.set(kind, kh);

    const area = areaOf(rel);
    const ah = byArea.get(area) || { files: 0, code: 0, data: 0, docs: 0, total: 0 };
    ah.files++;
    ah.total += stat.total;
    if (kind === "code") ah.code += stat.code;
    else if (kind === "data") ah.data += stat.total;
    else ah.docs += stat.total;
    byArea.set(area, ah);

    biggest.push({ rel: rel.replace(/\\/g, "/"), lang, kind, total: stat.total, code: stat.code });
  }
}

walk(ROOT);

const langRows = [...byLang.entries()].sort((a, b) => b[1].code - a[1].code);
const areaRows = [...byArea.entries()].sort((a, b) => b[1].code - a[1].code);
const sum = langRows.reduce((acc, [, v]) => ({
  files: acc.files + v.files, total: acc.total + v.total, blank: acc.blank + v.blank,
  comment: acc.comment + v.comment, code: acc.code + v.code,
}), { files: 0, total: 0, blank: 0, comment: 0, code: 0 });

biggest.sort((a, b) => b.total - a.total);

if (AS_JSON) {
  console.log(JSON.stringify({ sum, byLang: langRows, byArea: areaRows, skipped: [...skipReport.entries()], biggest: biggest.slice(0, 20) }, null, 2));
  process.exit(0);
}

const n = (x) => x.toLocaleString("en-US");
const pad = (s, w) => String(s).padEnd(w, " ");

const codeSum = byKind.get("code") || { files: 0, total: 0, blank: 0, comment: 0, code: 0 };
const dataSum = byKind.get("data") || { files: 0, total: 0, blank: 0, comment: 0, code: 0 };
const docsSum = byKind.get("docs") || { files: 0, total: 0, blank: 0, comment: 0, code: 0 };

console.log(`MM2.0 代码行数统计 —— ${ROOT}`);
console.log(`（统计的是**当前工作区**的文件，包含未提交的改动）\n`);

console.log("══ 主口径：实际代码行（纯注释行、空行都不算）═══════════════════════════════════");
console.log(`  手写源码      ${pad(n(codeSum.files) + " 文件", 12)} 实际代码 ${pad(n(codeSum.code), 9)} 行`);
console.log(`                （其中纯注释 ${n(codeSum.comment)} 行、空行 ${n(codeSum.blank)} 行，均不计入）`);
console.log(`  数据/锁文件    ${pad(n(dataSum.files) + " 文件", 12)} ${pad(n(dataSum.total), 9)} 行（JSON/YAML，不是源码）`);
console.log(`  文档          ${pad(n(docsSum.files) + " 文件", 12)} ${pad(n(docsSum.total), 9)} 行（Markdown/纯文本）`);
console.log(`  ─────────────────────────────────────────────────────────────────────────`);
console.log(`  合计文件 ${n(sum.files)} 个 / 全部行数 ${n(sum.total)} 行`);

console.log("\n── 按语言（代码行 = 真正带代码的行）────────────────────────────────────────────");
console.log(`  ${pad("语言", 18)} ${pad("文件", 7)} ${pad("代码行", 10)} ${pad("纯注释", 9)} ${pad("空行", 8)} ${pad("总行", 10)}`);
for (const [lang, v] of langRows) {
  console.log(`  ${pad(lang, 18)} ${pad(n(v.files), 7)} ${pad(n(v.code), 10)} ${pad(n(v.comment), 9)} ${pad(n(v.blank), 8)} ${pad(n(v.total), 10)}`);
}
console.log("  " + "─".repeat(74));
console.log(`  ${pad("合计", 18)} ${pad(n(sum.files), 7)} ${pad(n(sum.code), 10)} ${pad(n(sum.comment), 9)} ${pad(n(sum.blank), 8)} ${pad(n(sum.total), 10)}`);

console.log("\n── 按区域（代码行只数手写源码；数据/文档单列，不混进去）─────────────────────────");
console.log(`  ${pad("区域", 26)} ${pad("文件", 7)} ${pad("代码行", 10)} ${pad("数据行", 10)} ${pad("文档行", 10)}`);
for (const [area, v] of areaRows) {
  console.log(`  ${pad(area, 26)} ${pad(n(v.files), 7)} ${pad(n(v.code), 10)} ${pad(n(v.data), 10)} ${pad(n(v.docs), 10)}`);
}

console.log("\n── 被排除的目录（生成物/第三方，完全不计）─────────────────────────────────────");
for (const [dir, v] of [...skipReport.entries()].sort((a, b) => b[1].bytes - a[1].bytes)) {
  console.log(`  ${pad(dir.replace(/\\/g, "/"), 40)} ${pad(n(v.files) + " 文件", 12)} ${(v.bytes / 1048576).toFixed(1)} MB`);
}

console.log("\n── 行数最多的 12 个文件（用来识别「生成物混进来」）─────────────────────────────");
for (const b of biggest.slice(0, 12)) {
  console.log(`  ${pad(n(b.total), 8)} 行  ${pad(b.kind, 6)} ${pad(b.lang, 16)} ${b.rel}`);
}

console.log(`
说明：
  · **主口径**：只有真正带代码的行才计数 —— 整行注释、块注释/文档串内部的行、空行都不算。
    代码后面跟一句 \`// 说明\` 仍算代码（这一行确实有代码）；只有 \`{\` \`}\` \`);\` 的结构行也算代码。
  · 注释识别是启发式：C#/C++/JS/TS/Vue 用 \`//\` + 块注释，Python 用 \`#\` + 三引号文档串，
    PowerShell 用 \`#\` + \`<# #>\`，JSX 的 \`{/* */}\` 也算注释。个别边界写法可能判错。
  · JSON/YAML 与 Markdown 单列为"数据/文档"，不进入代码行 —— 它们里面也可能含构建产物
    （引擎签名、压力测试数据、教程数据），已在上面按行数列出最大文件，便于你核对。
  · Vue 单文件组件的模板/脚本/样式合并计入"Vue 单文件组件"一类。`);

