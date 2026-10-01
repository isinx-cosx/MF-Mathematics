// 一次性分析：未接入模式 ↔ 已有 ENGINE_MAP 键 / 引擎函数 的候选匹配
// 归一化规则：去空白、统一全/半角括号、统一大小写、去掉尾部修饰
import { VIEW_CONFIGS } from "../src/lib/engine/viewConfigs.js";
import { ENGINE_MAP } from "../src/lib/engine/engineMap.js";

const norm = (s) => String(s)
  .replace(/\s+/g, "")
  .replace(/[（(]/g, "(").replace(/[）)]/g, ")")
  .replace(/[·・]/g, "")
  .toLowerCase();

const byNorm = new Map();
for (const k of Object.keys(ENGINE_MAP)) {
  const n = norm(k);
  if (!byNorm.has(n)) byNorm.set(n, []);
  byNorm.get(n).push(k);
}

const unmapped = [];
for (const [key, cfg] of Object.entries(VIEW_CONFIGS)) {
  for (const m of cfg.modes || []) {
    if (!Object.prototype.hasOwnProperty.call(ENGINE_MAP, m)) unmapped.push({ view: key, mode: m });
  }
}

console.log(`未接入 ${unmapped.length} 个；其中「仅名称写法不同、其实已有映射」的：\n`);
let exact = 0;
for (const u of unmapped) {
  const hit = byNorm.get(norm(u.mode));
  if (hit) { exact++; console.log(`  ${u.view.padEnd(18)} ${u.mode}  ==  ${hit.join(" / ")}`); }
}
console.log(`\n仅写法不同合计 ${exact} 个\n`);

console.log("包含关系的近似（名字里有一段相同）：");
for (const u of unmapped) {
  if (byNorm.get(norm(u.mode))) continue;
  const n = norm(u.mode);
  const near = Object.keys(ENGINE_MAP).filter((k) => {
    const kk = norm(k);
    return kk.includes(n) || n.includes(kk);
  });
  if (near.length) console.log(`  ${u.mode}  ~  ${near.join(" / ")}`);
}

console.log("其余未接入（需要在引擎里找函数或新写）：");
for (const u of unmapped) {
  if (byNorm.get(norm(u.mode))) continue;
  console.log(`  ${u.view.padEnd(18)} ${u.mode}`);
}
