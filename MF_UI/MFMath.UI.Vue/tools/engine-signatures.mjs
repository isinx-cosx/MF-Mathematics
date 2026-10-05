#!/usr/bin/env node
/**
 * engine-signatures.mjs —— 从引擎源码重建 `src/lib/ai/engine-signatures.json`，并**对账**。
 *
 * 为什么需要它：
 *   `engine-signatures.json`（424 条）是引擎函数签名的**副本** —— 函数工具箱与 AI 的工具表
 *   都以它为唯一数据源。但引擎那边才是真相，而这份副本**没有任何机制保证跟着更新**：
 *   引擎新增一个 action、或给某个 action 加一个参数，这里不会变，于是
 *   "工具箱里少一个函数""AI 调引擎时少了必填参数"这类问题会**静默发生**。
 *
 * 数据从哪来：
 *   引擎的 `list_functions` 只返回**函数名**（没有参数信息），所以这份表当年是
 *   **从 C++ 源码里刮出来的**（`file` 字段就是痕迹）。本脚本沿用同一来源，但规则写死在这里、
 *   可重复、可对账 —— 于是它同时是"生成器"和"漂移检查"。
 *
 * 用法：
 *   node tools/engine-signatures.mjs --check     # 对账；有漂移则 exit 1（进 npm run check）
 *   node tools/engine-signatures.mjs --write     # 重新生成（引擎改动后跑一次）
 *   node tools/engine-signatures.mjs --check --verbose   # 打印全部差异
 *
 * ⚠ 判据只覆盖**会坏事的部分**：函数集合、参数名、必填/可选。
 *   参数**类型**不参与判定 —— 因为现有表里已有一批降级值（`?` / `?bound` / `?get_sig` …，
 *   当年刮取失败留下的），拿它当基线只会产生上百条假差异。类型差异单独作为提示打印。
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PROJECT = path.resolve(HERE, "..");
const ENGINE = path.resolve(PROJECT, "..", "..", "MF_Mathematics");
const SIG_FILE = path.join(PROJECT, "src", "lib", "ai", "engine-signatures.json");

const argv = process.argv.slice(2);
const WRITE = argv.includes("--write");
const VERBOSE = argv.includes("--verbose");

/* ── 类型映射：getter → 表里的类型名（未知一律 "?"，与既有约定一致）── */
const TYPE_OF = {
  int: "int", int_bounded: "int", int_opt: "int", int_opt_bounded: "int",
  double: "number", double_opt: "number",
  bool: "bool", bool_opt: "bool",
  string: "string", string_opt: "string",
  keyword: "keyword", keyword_opt: "keyword",
  string_or_number: "string|number", equation: "equation", equation_opt: "equation",
  int_array: "int[]", int_list: "int[]",
  double_array: "number[]", double_list: "number[]",
  ll_array: "array", ll_list: "array",
  interval: "array", range: "array", vec: "array", vec_opt: "array",
  vector: "array", point: "array", point_cloud: "array", pair_list: "array", args: "array",
  matrix: "matrix", ll_matrix: "matrix", matrix_symbolic: "matrix",
};

function apiFiles() {
  const out = [];
  (function walk(d) {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      if (e.name === "build" || e.name === "tests") continue;
      const p = path.join(d, e.name);
      if (e.isDirectory()) walk(p);
      else if (e.name.endsWith("_api.cpp") || e.name === "api.cpp") out.push(p);
    }
  })(ENGINE);
  return out.sort();
}

/** 从源码刮出 { fn: {file, params, required, optional} } */
function scrape() {
  const result = {};
  for (const file of apiFiles()) {
    const text = fs.readFileSync(file, "utf8");
    const rel = path.relative(ENGINE, file).split(path.sep).join("/");
    // 按 register_function( 切块：每块到下一处注册或文件末尾
    const marks = [...text.matchAll(/register_function\s*\(\s*"([^"]+)"/g)];
    for (let i = 0; i < marks.length; i++) {
      const name = marks[i][1];
      const body = text.slice(marks[i].index, i + 1 < marks.length ? marks[i + 1].index : text.length);
      const params = {};
      const required = [];
      const optional = [];
      // 取这个 handler 的**顶层参数名**（`[](const Value& args) {` → "args"），
      // 只认对这个名字的读取。
      // ⚠ 为什么必须这么严：引擎里常有"读嵌套子对象"的写法 ——
      //     const Value& pm = args["pmf_data"];  get_double_array(pm, "values")
      //   以及"合成一个临时对象喂给辅助函数"的写法 ——
      //     Value op_args = …;  get_matrix(op_args, "A")
      //   这两种都不是顶层参数。第一版放宽成"任意标识符"，于是把 values/probs/A
      //   误判成顶层参数、报了 9 条假漂移。
      const lam = body.match(/\[\s*\]\s*\(\s*const\s+Value\s*&\s*([A-Za-z_][A-Za-z_0-9]*)/);
      const argsVar = lam ? lam[1] : "args";
      const readRe = new RegExp(
        `\\bget_([a-z_0-9]+?)\\s*\\(\\s*${argsVar}\\s*,\\s*"([^"]+)"`, "g");
      for (const m of body.matchAll(readRe)) {
        const [, getter, key] = m;
        // ⚠ 可选判定必须用 includes 而不是 endsWith：引擎里还有
        // `get_int_opt_bounded` 这类**以 _bounded 结尾**的可选读取函数，
        // 只判后缀会把它们当成必填，于是产出几十条假漂移。
        const isOpt = getter.includes("_opt");
        const base = isOpt ? getter.replace(/_opt.*$/, "") : getter;
        if (!(key in params)) params[key] = TYPE_OF[base] ?? TYPE_OF[getter] ?? "?";
        (isOpt ? optional : required).push(key);
      }
      const entry = {
        file: rel,
        optional: [...new Set(optional)].sort(),
        params: Object.fromEntries(Object.entries(params).sort(([a], [b]) => a.localeCompare(b))),
        required: [...new Set(required)].sort(),
        signature: "",
      };
      // 同名重复注册时保留第一次（与运行时注册表一致：后注册会覆盖，但源码里极少见）
      if (!(name in result)) result[name] = entry;
    }
  }
  return Object.fromEntries(Object.entries(result).sort(([a], [b]) => a.localeCompare(b)));
}

const fresh = scrape();

if (WRITE) {
  fs.writeFileSync(SIG_FILE, JSON.stringify(fresh, null, 1) + "\n", "utf8");
  console.log(`✓ 已重建 ${Object.keys(fresh).length} 条 → src/lib/ai/engine-signatures.json`);
  process.exit(0);
}

/* ── 对账 ── */
const old = JSON.parse(fs.readFileSync(SIG_FILE, "utf8"));
const oldNames = new Set(Object.keys(old));
const newNames = new Set(Object.keys(fresh));
const problems = [];
const notes = [];

for (const n of newNames) if (!oldNames.has(n)) problems.push(`函数缺失：源码里有 ${n}，表里没有（${fresh[n].file}）`);
for (const n of oldNames) if (!newNames.has(n)) problems.push(`多余条目：表里有 ${n}，源码里已找不到`);

/* ── 对账 ──
 * ⚠ 判据是**单向**的，这是本工具最重要的一条设计决定（前两版都栽在这里）：
 *   源码里"能看出来的参数"只是**下界** —— 引擎里大量参数是用 `args["k"]`、
 *   或域内辅助函数（`get_complex_or_space(args)`）读取的，刮取器看不到。
 *   所以"表里有、源码里没看出"**不能**判为漂移（否则会产出上百条假差异，
 *   而吵闹的守卫比没有守卫更糟 —— 它会变成没人信的摆设）。
 *
 *   因此**失败**只针对这三个方向：
 *     ① 函数集合不一致（源码 register_function ↔ 表的键，两侧都可靠）；
 *     ② 源码**明确读取了**的某个参数名，表里没有 → 工具箱/AI 根本没法提供它；
 *     ③ 源码按**必填**读取（非 _opt），表里却写成可选 → 用户会漏填、引擎报缺参数。
 *   其余（表里多出来的参数、类型差异、表里必填但源码只见 _opt）一律只作提示。 */
const same = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);
const sameSet = (a, b) => same([...a].sort(), [...b].sort());

const names = { miss: [], extra: [] };
for (const n of newNames) if (!oldNames.has(n)) names.miss.push(n);
for (const n of oldNames) if (!newNames.has(n)) names.extra.push(n);

const hard = [];
const soft = [];

for (const n of [...newNames].filter((x) => oldNames.has(x))) {
  const o = old[n], f = fresh[n];
  const tableParams = new Set([...(o.required || []), ...(o.optional || [])]);
  const tableRequired = new Set(o.required || []);
  const tableOptional = new Set(o.optional || []);

  // ② 源码读了、表里没有
  for (const k of [...f.required, ...f.optional]) {
    if (!tableParams.has(k)) hard.push(`${n}: 源码读取参数「${k}」，但表里没这一项（工具箱/AI 无法提供）`);
  }
  // ③ 源码按必填读、表里写成可选
  for (const k of f.required) {
    if (tableOptional.has(k) && !tableRequired.has(k)) {
      hard.push(`${n}: 「${k}」源码里是必填，表里却当成可选（用户会漏填）`);
    }
  }
  // 提示：表里必填、源码只见 _opt；表里多出来的参数；类型差异
  for (const k of f.optional) {
    if (tableRequired.has(k)) soft.push(`${n}: 「${k}」表里必填，源码里按可选读取`);
  }
  for (const k of tableParams) {
    if (!(k in f.params)) soft.push(`${n}: 表里的「${k}」未能在源码里刮到（可能用了 args[...] 或域内辅助，正常）`);
  }
  for (const k of Object.keys(f.params)) {
    const t = (o.params || {})[k];
    if (t !== undefined && t !== f.params[k] && t !== "?") soft.push(`${n}: 「${k}」类型 表=${t} 源码=${f.params[k]}`);
  }
}

console.log(`引擎签名对账：源码 register_function ${newNames.size} 条 / 表 ${oldNames.size} 条`);

if (names.miss.length) for (const n of names.miss) hard.push(`函数缺失：源码注册了 ${n}，表里没有（${fresh[n].file}）`);
if (names.extra.length) for (const n of names.extra) hard.push(`多余条目：表里有 ${n}，源码中找不到 register_function`);

console.log(`提示（不判定失败）${soft.length} 处` + (VERBOSE ? "" : "，--verbose 看全部"));
if (VERBOSE) for (const s of soft) console.log("  · " + s);

if (hard.length) {
  console.error(`\n签名漂移 ${hard.length} 处：`);
  for (const p of (VERBOSE ? hard : hard.slice(0, 20))) console.error("  ✗ " + p);
  if (!VERBOSE && hard.length > 20) console.error(`  …另有 ${hard.length - 20} 处（--verbose 看全部）`);
  console.error("\n若是引擎新增/改名导致，跑 node tools/engine-signatures.mjs --write 重建；"
    + "重建后请人工核对被覆盖的部分（刮取器看不全用 args[...] / 域内辅助读取的参数）。");
  process.exit(1);
}
console.log("✓ 无漂移：函数集合一致，且源码读取的每个参数都在表里、必填/可选不矛盾");
