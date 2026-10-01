/**
 * check-examples.mjs — 教程示例"能不能正确跳转"的构建期检查
 *
 * 为什么需要它（真实缺陷，本文件就是为它写的）：
 * 教程示例里的 `mode` 是**计算分类**（"代数"、"数值分析"），`action` 才是具体操作
 * （"不定积分"、"辛普森积分"）。早先只按分类决定页面，于是「不定积分」被送到代数页；
 * 代数页没有这个模式 → 匹配失败 → 模式停在**该页默认值**（恰好是「解方程/组」）→
 * 用户点计算，引擎收到 `solve_sym(x*sin(x))` 而不是 `integrate(...)`，
 * 报出"方程含超越函数（x*sin(x)）"这种与操作完全无关的错误。
 *
 * 这项检查会：
 *   1. 对全部 52 个示例跑产品里同一套 resolveExample（操作名反查页面 → 兜底按分类）；
 *   2. 断言"解析成功"的示例，其操作在目标页面的模式表里**确实存在**；
 *   3. 对确实无处可去的示例，要求写进 KNOWN_UNAVAILABLE 并给理由 ——
 *      新增的错配会让检查失败，而不是静默退化。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const VUE = path.resolve(HERE, "..");
const imp = (rel) => import(pathToFileURL(path.join(VUE, rel)).href);

/**
 * 已知无处可去的操作/模式：每一条都必须写清理由。
 * 补上能力后请从这里删除（否则下面的"过时条目"检查会报错）。
 */
const KNOWN_UNAVAILABLE = {
  "行列式": "引擎没有行列式动作（只有 matrix_inverse / rank / matrix_multiply），补能力前无法加载",
  "AI 助手": "AI 助手尚未实现（方案 P3），示例暂时无法加载",
  "联网搜索": "在线搜索面板尚未实现（方案 P1）",
  "设置": "设置面板虽已存在，但示例指向的是配置项而非某个计算模式，需要专门的落点（暂未支持）",
  "数学键盘": "数学键盘是顶栏面板而不是页面，自动打开它需要特殊处理（暂未支持）",
};

const tutorials = JSON.parse(fs.readFileSync(path.join(VUE, "src/tutorials/tutorials.json"), "utf8")).tutorials;
const { getViewConfig } = await imp("src/lib/engine/viewConfigs.js");
const { resolveExample, ensureModeIndex, ALIASES } = await imp("src/lib/workspace/pendingInput.js");
await ensureModeIndex();

const problems = [];
const unresolved = new Map();   // 操作名 → 出现次数
let checked = 0;
let resolvedViaOperation = 0;
let resolvedViaCategory = 0;

for (const t of tutorials) {
  for (const e of t.examples) {
    checked++;
    const info = resolveExample(e);
    if (!info.ok) {
      // 没有操作时（绘图类示例）按模式名登记，便于看清到底是哪一类无处可去
      const key = e.operation || e.mode || "(无操作无模式)";
      unresolved.set(key, (unresolved.get(key) || 0) + 1);
      continue;
    }
    if (info.via === "operation") resolvedViaOperation++; else resolvedViaCategory++;

    // 解析到了页面，还要确认"操作"在那一页的模式表里真的存在 ——
    // 否则运行时仍会退化成"用默认模式计算"。
    if (info.mode) {
      const key = info.route.split("/").filter(Boolean).pop();
      const cfg = getViewConfig(key) || { modes: [] };
      if (!(cfg.modes || []).includes(info.mode)) {
        problems.push(`${t.id} #${e.index}「${e.label}」：解析到 ${info.route}，但那里没有模式「${info.mode}」`);
      }
    }
  }
}

// 别名表的每一项都要指向真实存在的模式，否则就是死映射
for (const [from, to] of Object.entries(ALIASES)) {
  const info = resolveExample({ mode: "", operation: to });
  if (!info.ok) problems.push(`别名「${from} → ${to}」指向的模式在任何页面都不存在`);
}

// 无处可去的示例：必须已登记
for (const [op, count] of unresolved) {
  if (!KNOWN_UNAVAILABLE[op]) {
    problems.push(`操作「${op}」的示例（${count} 条）无法定位到任何页面，且未登记在 KNOWN_UNAVAILABLE`);
  }
}
// 登记了却已经能解析 → 过时条目
for (const op of Object.keys(KNOWN_UNAVAILABLE)) {
  if (!unresolved.has(op)) problems.push(`KNOWN_UNAVAILABLE 里的「${op}」已经能解析了，属于过时条目，请删除`);
}

console.log("=".repeat(78));
console.log(`示例总数 ${checked}：按操作名反查定位 ${resolvedViaOperation} 条，按分类兜底 ${resolvedViaCategory} 条`);
console.log(`无法定位 ${[...unresolved.entries()].map(([k, v]) => `${k}(${v})`).join("、") || "0 条"}`);
console.log("=".repeat(78));

if (problems.length) {
  console.error("\n检查失败：");
  for (const p of problems) console.error("  ✗ " + p);
  process.exit(1);
}
console.log("\n检查通过：每个示例都会落到「它自己那一页」、且操作在该页确实存在");
