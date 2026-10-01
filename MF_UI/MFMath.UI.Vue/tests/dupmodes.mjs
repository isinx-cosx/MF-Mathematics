import { VIEW_CONFIGS } from "../src/lib/engine/viewConfigs.js";
const seen = new Map();
for (const [k, c] of Object.entries(VIEW_CONFIGS)) {
  for (const m of c.modes || []) {
    if (!seen.has(m)) seen.set(m, []);
    seen.get(m).push(k);
  }
}
const dup = [...seen.entries()].filter(([, v]) => v.length > 1);
console.log("跨视图重名模式:", dup.length);
for (const [m, v] of dup) console.log(`  ${m}  →  ${v.join(" / ")}`);
