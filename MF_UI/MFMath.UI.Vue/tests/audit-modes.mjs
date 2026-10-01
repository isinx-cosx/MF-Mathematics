// 引擎模式审计：**不经过界面**，对每个模式的参数构造结果直接调引擎（每模式一个独立进程）
//
// 为什么要有它：
//   ① CDP 界面测试跑一个模式要 2 秒，还共用宿主进程 —— 某个模式把宿主搞崩，
//      后面全部模式都测不了（第一版就卡在这里）。
//   ② 这里用 probe_call.exe 每模式一个进程：崩溃/死循环只会影响那一行，能精确定位。
//   ③ 参数构造用的是界面的同一份代码（calcArgs.buildEngineArgs /
//      buildEngineArgsFromValues），所以查出来的问题就是界面上的问题。
//
// 用法: node audit-modes.mjs [视图key]
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { VIEW_CONFIGS } from "../src/lib/engine/viewConfigs.js";
import { ENGINE_MAP, ENGINE_VAR_SPECS } from "../src/lib/engine/engineMap.js";
import { buildEngineArgs, buildEngineArgsFromValues, needsVarDialog } from "../src/lib/engine/calcArgs.js";

const PROBE = "C:/Users/fsafsafsa/Desktop/cppcshap/MF_Mathematics/build/bin/Release/probe_call.exe";
const only = process.argv[2] || "";
const tmp = path.join(os.tmpdir(), "audit-args.json");

/* 与 cdp-engine-coverage / cdp-modes-render 共用的样本：`;` 分段顺序 = args 声明顺序。
   放在 fixtures/ 里而不是各自抄一份，避免"一边改了样本、另一边没改"造成的假结论。 */
import { VIEW_SAMPLE } from "./fixtures/view-samples.mjs";
import { MODE_SAMPLE } from "./fixtures/mode-samples.mjs";

/** 复现界面里的参数构造（有 VAR_SPECS 的模式走弹窗那条路径） */
function argsFor(mode, sample) {
  const spec = ENGINE_MAP[mode];
  if (!spec) return null;
  if (needsVarDialog(mode)) {
    const fields = ENGINE_VAR_SPECS[mode];
    const values = fields.map((f, i) => (i === 0 ? sample : f[1]));
    return buildEngineArgsFromValues(spec, fields, values);
  }
  return buildEngineArgs(mode, sample);
}

function callEngine(fn, args) {
  fs.writeFileSync(tmp, JSON.stringify(args), "utf8");
  try {
    const out = execFileSync(PROBE, [fn, `@${tmp}`], { encoding: "utf8", timeout: 15000 });
    return { out: out.trim() };
  } catch (e) {
    if (e.signal === "SIGTERM" || (e.error && e.error.code === "ETIMEDOUT"))
      return { timeout: true, out: String(e.stdout || "").trim() };
    return { crash: true, code: e.status, out: String(e.stdout || "").trim() };
  }
}

const rows = [];
for (const [view, cfg] of Object.entries(VIEW_CONFIGS)) {
  if (only && view !== only) continue;
  for (const mode of cfg.modes || []) {
    const spec = ENGINE_MAP[mode];
    if (!spec) { rows.push({ view, mode, kind: "未接入" }); continue; }
    const sample = Object.prototype.hasOwnProperty.call(MODE_SAMPLE, mode)
      ? MODE_SAMPLE[mode]
      : (VIEW_SAMPLE[view] ?? "");
    const args = argsFor(mode, sample);
    const r = callEngine(spec.fn, args);
    if (r.crash) rows.push({ view, mode, kind: "崩溃", fn: spec.fn, code: r.code, args });
    else if (r.timeout) rows.push({ view, mode, kind: "超时", fn: spec.fn, args });
    else {
      let parsed = null;
      try { parsed = JSON.parse(r.out); } catch { /* 非 JSON */ }
      if (!parsed) rows.push({ view, mode, kind: "输出异常", fn: spec.fn, out: r.out.slice(0, 120), args });
      else if (parsed.isError) rows.push({ view, mode, kind: "错误", fn: spec.fn, msg: String(parsed.value).slice(0, 150), args });
      else rows.push({ view, mode, kind: "OK", fn: spec.fn });
    }
  }
}

const by = (k) => rows.filter((r) => r.kind === k);
const show = (list, label) => {
  if (!list.length) return;
  console.log(`\n── ${label}（${list.length}）──`);
  for (const r of list) {
    const extra = r.msg ? `  ${r.msg}` : r.code ? `  exit=${r.code}` : r.out ? `  ${r.out}` : "";
    console.log(`  ${r.view.padEnd(18)} ${r.mode}${r.fn ? " [" + r.fn + "]" : ""}${extra}`);
  }
};
console.log(`模式总数 ${rows.length}：OK ${by("OK").length}，错误 ${by("错误").length}，崩溃 ${by("崩溃").length}，超时 ${by("超时").length}，未接入 ${by("未接入").length}，输出异常 ${by("输出异常").length}`);
show(by("崩溃"), "崩溃（引擎把进程搞挂了）");
show(by("超时"), "超时（15 秒没返回）");
show(by("未接入"), "未接入引擎");
show(by("错误"), "引擎报错");
show(by("输出异常"), "输出不是 JSON");

// 供 run-all.ps1 解析：通过数=除"未接入/崩溃/超时/输出异常"之外的模式数
const passed = rows.filter((r) => r.kind === "OK").length;
const failed = rows.length - passed;
console.log(`RESULT|audit-modes|${passed}|${failed}`);
const dump = path.join(os.tmpdir(), "audit-args-fail.json");
fs.writeFileSync(dump, JSON.stringify(rows.filter((r) => r.kind !== "OK"), null, 1), "utf8");
console.log(`\n明细: ${dump}`);
