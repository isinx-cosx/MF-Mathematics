// 一次性：把 ENGINE_MAP / ENGINE_VAR_SPECS 导出成可读文本
import fs from "node:fs";
import { ENGINE_MAP, ENGINE_VAR_SPECS } from "../src/lib/engine/engineMap.js";

const keys = Object.keys(ENGINE_MAP);
const lines = keys.map((k) => {
  const s = ENGINE_MAP[k];
  const args = (s.args || []).map((a) => `${a.key}:${a.type}${a.opt ? "?" : ""}`).join(", ");
  const vars = ENGINE_VAR_SPECS[k] ? "  <<VAR>> " + JSON.stringify(ENGINE_VAR_SPECS[k]) : "";
  return `${k}\t${s.fn}\t${args}${vars}`;
});
fs.writeFileSync(process.env.TEMP + "/engine_map.txt", lines.join("\n"), "utf8");
console.log("ENGINE_MAP 条目:", keys.length, "| 带 VAR_SPECS:", Object.keys(ENGINE_VAR_SPECS).length);

// 按引擎函数分组，看哪些函数已被接入、以什么键名
const byFn = new Map();
for (const k of keys) {
  const fn = ENGINE_MAP[k].fn;
  if (!byFn.has(fn)) byFn.set(fn, []);
  byFn.get(fn).push(k);
}
const dup = [...byFn.entries()].filter(([, v]) => v.length > 1);
console.log(`被多个模式共用的引擎函数: ${dup.length} 个`);
console.log("参数里出现 point 类型的模式：");
for (const k of keys) {
  if ((ENGINE_MAP[k].args || []).some((a) => a.type === "point")) console.log("  ", k, JSON.stringify(ENGINE_MAP[k].args));
}
