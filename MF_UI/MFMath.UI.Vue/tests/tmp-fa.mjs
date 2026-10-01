import { VIEW_CONFIGS } from "../src/lib/engine/viewConfigs.js";
import { ENGINE_MAP } from "../src/lib/engine/engineMap.js";
const c = VIEW_CONFIGS["functional-analysis"];
for (const m of c.modes) {
  const s = ENGINE_MAP[m];
  console.log(`${m}\t${s ? s.fn + "(" + (s.args||[]).map(a=>a.key).join(",") + ")" : "(未接入)"}`);
}
