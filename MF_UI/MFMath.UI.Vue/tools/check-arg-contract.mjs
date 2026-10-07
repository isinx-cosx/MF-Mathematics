#!/usr/bin/env node
/**
 * check-arg-contract.mjs —— **UI 的参数键 ↔ 引擎实际读的键** 对账（BUGS.md B1 那一类）
 *
 * 为什么需要它（本轮审计出来的缺口）：
 *   `tools/engine-signatures.mjs` 只对账「引擎源码 ↔ engine-signatures.json」——
 *   **完全没有把 UI 算进去**，而 UI 的 `ENGINE_MAP` 才决定"往引擎发哪些键"。
 *   B1 正是从这个缝里过去的：引擎读 `interval`，UI 发 `a`/`b`，两边**各自都"无漂移"**，
 *   而用户填的区间**永远不生效**（恒定 [0,1]），静默算错。
 *
 * 判据（只认会坏事的那个方向）：
 *   UI 为某模式声明了参数键 K ⇒ 必须**有证据**说明引擎真的读 K：
 *     ① 刮取器看到 `get_xxx(args,"K")`（engine-signatures.mjs 的 scrape），或
 *     ② 在下面的 HELPER_READ 白名单里 —— 即"经 helper / lambda / args[...] 读，刮取器看不到"。
 *   两者都不是 ⇒ **失败**：这个键很可能是"填了不生效"。
 *
 * 另一方向（引擎按必填读、UI 没声明）只**警告**：绝大多数是**多分支互斥**的假阳性
 *   （例：`variance` 的 required=[expr,pmf_data]，实际是 data / pmf_data / expr+range 三选一，
 *   见 probability_api.cpp:237-249）。严格判定会产出成片假失败，而"吵闹的守卫比没有守卫更糟"。
 *
 * ── 白名单是怎么来的（不是猜的）────────────────────────────────────────────
 * 2026-10-07 对全部 78 个"刮取器看不到"的键逐个做了**差分探针**（删掉它 / 改成别的值，
 * 用 probe_call.exe 真调引擎，看结果变不变），结论分两类：
 *   · **删掉即报「对象缺少键: X」/「缺少必填参数 X」/「X 必须为 [a,b]」** ⇒ 铁证；
 *   · 删掉无变化但**改值结果就变** ⇒ 引擎读了（`get_interval` 之类 helper 有默认值，
 *     所以"删除"看不出差别 —— 已单独验证：`darboux_sum("x^2")` 省略 interval 与传 [0,1]
 *     结果逐字相同，而传 [0,2] 下和从 0.285 变 2.28）。
 * 结论：**78 个全是刮取器盲区，不是缺陷** —— 415 个模式 / 934 个声明键的契约是干净的。
 * 每一条都保留了它当时的判据（见下面的字符串）。
 */
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { scrape } from "./engine-signatures.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PROJECT = path.resolve(HERE, "..");
/* ⚠ 动态 import 必须给 file:// URL：Windows 绝对路径（`C:\...`）会被当成协议 `c:` 拒绝。 */
const { ENGINE_MAP } = await import(pathToFileURL(path.join(PROJECT, "src", "lib", "engine", "engineMap.js")).href);

/**
 * "刮取器看不见、但引擎确实读"的键：`fn → { key: 判据 }`。
 * 逐条按 fn 写而不是给全局键名白名单 —— 否则将来某个新模式用 `interval` 就能蒙混过去，
 * 而那正是本闸门要防的事。
 */
const HELPER_READ = {
  analytic_continuation_zeta: { "s": "删掉即报「对象缺少键: s」" },
  bayes_theorem: { "events": "删掉即报「对象缺少键: events」", "P": "删掉即报「对象缺少键: P」" },
  betti_numbers: { "complex": "helper 读（改值结果变）" },
  calc_is_continuous: { "point": "删掉即报「缺少必填参数 point」" },
  caratheodory_measurable: { "E": "删掉即报「E 必须为 [a,b]」" },
  cauchy_integral_formula: { "a": "删掉即报「对象缺少键: a」" },
  cohomology_group: { "space": "helper 读（改值结果变）" },
  conditional_expectation: { "X": "helper 读（改值结果变）", "Omega": "helper 读（改值结果变）" },
  conditional_probability: { "P": "删掉即报「对象缺少键: P」" },
  contour_integral: { "gamma": "删掉即报「gamma 必须为 circle(center, r)」" },
  darboux_sum: { "interval": "get_interval(args,a,b)，默认 [0,1]；实测 [0,2] 下和 0.285→2.28" },
  euler_characteristic: { "space": "helper 读（改值结果变）" },
  exp_complex: { "z": "删掉即报「对象缺少键: z」" },
  extreme_value: { "interval": "get_interval；实测 [0,1] max=1 → [0,2] max=4" },
  fubini_theorem: { "range": "helper 读（改值结果变）" },
  functional_equation_zeta: { "s": "删掉即报「对象缺少键: s」" },
  fundamental_theorem: { "interval": "get_interval（real_analysis_api.cpp:174；改值结果变）" },
  homology_group: { "space": "helper 读（改值结果变）" },
  improper_integral: { "a": "helper 读（改值结果变）", "b": "helper 读（改值结果变）" },
  integral_mean_value: { "interval": "get_interval；实测 [0,1] 均值 0.333 → [0,2] 1.333" },
  integrate: { "a": "定积分分支 args.has(\"a\")（calculus_api.cpp:93）", "b": "同上，与 a 成对出现才走定积分" },
  integrate_double: { "xa": "重积分 x 边界（helper 读；删/改结果都变）", "xb": "同上", "ya": "重积分 y 边界", "yb": "同上" },
  integrate_triple: { "xa": "三重积分 x 边界（helper 读）", "xb": "同上", "ya": "y 边界", "yb": "同上", "za": "z 边界", "zb": "同上" },
  intermediate_value: { "interval": "get_interval；实测 [0,2] ξ=0 → [1,4] ξ=null" },
  is_holomorphic: { "z": "删掉即报「对象缺少键: z」" },
  is_independent: { "P": "删掉即报「对象缺少键: P」" },
  laurent_series: { "z0": "删掉即报「对象缺少键: z0」" },
  lebesgue_measure: { "E": "删掉即报「E 必须为 [a,b] 或集合名」" },
  limit: { "point": "删掉即报「缺少必填参数 point」" },
  log_complex: { "z": "删掉即报「对象缺少键: z」" },
  meas_expectation: { "X": "helper 读（改值结果变）" },
  mobius_transform: { "z": "删掉即报「对象缺少键: z」", "a": "删掉即报「对象缺少键: a」", "b": "删掉即报「对象缺少键: b」", "c": "删掉即报「对象缺少键: c」", "d": "删掉即报「对象缺少键: d」" },
  outer_measure: { "E": "删掉即报「E 必须为 [a,b]」" },
  product_measure: { "mu": "删掉即报「对象缺少键: mu」", "nu": "删掉即报「对象缺少键: nu」", "A": "删掉即报「A/B 必须为 [a,b]」", "B": "同上" },
  recurrence_sequence: { "initial": "删掉即报「对象缺少键: initial」" },
  residue: { "z0": "删掉即报「对象缺少键: z0」" },
  residue_theorem: { "singularities": "删掉即报「对象缺少键: singularities」" },
  riemann_integrable: { "interval": "get_interval（real_analysis_api.cpp:170）" },
  series_sum: { "b": "helper 读（改值结果变）" },
  simplicial_complex: { "simplices": "删掉即报「对象缺少键: simplices」" },
  singularity_classify: { "z0": "删掉即报「对象缺少键: z0」" },
  solve_inequality_system: { "ineqs": "删掉即报「对象缺少键: ineqs」" },
  space_completeness_check: { "sequence": "删掉即报「对象缺少键: sequence」" },
  sqrt_complex: { "z": "删掉即报「对象缺少键: z」" },
  termwise_integration: { "interval": "get_interval（real_analysis_api.cpp:263；改值结果变）" },
  total_probability: { "events": "删掉即报「对象缺少键: events」", "P": "删掉即报「对象缺少键: P」" },
  uniform_boundedness: { "operators": "删掉即报「对象缺少键: operators」", "test_points": "helper 读（改值结果变）" },
  uniform_continuity: { "interval": "get_interval（real_analysis_api.cpp:210）" },
  uniform_convergence: { "interval": "get_interval（同族）" },
  weak_convergence: { "sequence": "删掉即报「对象缺少键: sequence」" },
  weierstrass_m_test: { "interval": "get_interval（real_analysis_api.cpp:254）" },
  zeros_and_poles: { "center": "helper 读（改值结果变）" },
  zeta_series: { "s": "删掉即报「对象缺少键: s」" },
};

/** 引擎按必填读、但 UI 确实不声明 —— 已核为**多分支互斥**的假阳性，仅提示 */
const KNOWN_MULTI_BRANCH = {
  series_sum: ["expr"],
  variance: ["expr"],
  contour_integral: ["func"],
  prob_expectation: ["expr"],
};

const eng = scrape();
const hard = [];
const soft = [];
let checkedKeys = 0;

for (const [mode, spec] of Object.entries(ENGINE_MAP)) {
  const fn = spec.fn;
  const e = eng[fn];
  if (!e) { hard.push(`${mode}：fn=${fn} 在引擎源码里找不到 register_function`); continue; }
  const engRead = new Set([...(e.required || []), ...(e.optional || [])]);
  const declared = new Set();
  for (const a of spec.args || []) {
    declared.add(a.key);
    checkedKeys++;
    if (engRead.has(a.key)) continue;                 // ① 刮取器直接看到
    if (HELPER_READ[fn] && HELPER_READ[fn][a.key]) continue;  // ② 白名单（带判据）
    hard.push(`${mode}（fn=${fn}）：UI 声明了参数「${a.key}」，但引擎源码里看不到读它 `
      + `—— 很可能是"填了不生效"（B1 类）。引擎实际读：${[...engRead].join(", ") || "(刮不到)"}`);
  }
  for (const k of e.required) {
    if (declared.has(k)) continue;
    if ((KNOWN_MULTI_BRANCH[fn] || []).includes(k)) continue;
    soft.push(`${mode}（fn=${fn}）：引擎按必填读「${k}」，UI 未声明（可能是多分支：请回源码确认）`);
  }
}

console.log(`参数契约对账：${Object.keys(ENGINE_MAP).length} 个模式 / 检查 ${checkedKeys} 个声明键`);
console.log(`  引擎 register_function ${Object.keys(eng).length} 个；白名单（helper 读，带判据）`
  + `${Object.values(HELPER_READ).reduce((n, o) => n + Object.keys(o).length, 0)} 条`);

if (soft.length) {
  console.log(`\n提示 ${soft.length} 处（不判定失败）：`);
  for (const s of soft.slice(0, 8)) console.log("  · " + s);
  if (soft.length > 8) console.log(`  …另有 ${soft.length - 8} 处`);
}

if (hard.length) {
  console.error(`\n✗ 参数契约不符 ${hard.length} 处：`);
  for (const h of hard) console.error("  ✗ " + h);
  console.error("\n怎么修：要么把 UI 的键名改成引擎实际读的那个（B1 就是这么修的），"
    + "要么确认引擎确实经 helper / args[...] 读它后，加进本文件的 HELPER_READ **并写明判据**"
    + "（拿不出判据就别加 —— 白名单只会越长越没人信）。");
  process.exit(1);
}
console.log("✓ 参数契约一致：UI 声明的每个键都有证据说明引擎会读它");
