/**
 * ai/tools.ts — 给 AI 的工具：**直接调用 C++ 引擎**
 *
 * 这是"AI 不当计算源"那条原则的落地方式：模型不能自己心算，它只能**调引擎**。
 * 于是每一步推导里的数值都是引擎算出来的事实，而不是模型的措辞。
 *
 * 五个刻意的决定：
 *
 * ① **只暴露两个工具**（不是 424 个）。424 个动作全写成 tool schema 会撑爆上下文、也降低选择准确率；
 *    所以给「查」与「调」两个：`engine_find` 找函数，`engine_call` 调函数。
 * ② **只走 engineCall**（宿主 `mf.Dispatch`）。绝不碰 `win` / `sys` / `con` 那些桥 ——
 *    工具一旦能碰它们，模型就能写文件、跑进程，那是权限提升，不是计算。
 * ③ **参数按动作表校验**（`ENGINE_MAP` 的 args 就是引擎的入参说明）：
 *    缺必填、写错参数名，都直接回给模型一句"缺什么/多了什么"，让它自己改，而不是让引擎报个看不懂的错。
 * ④ **函数名必须在表里**。表外的名字一律拒绝（顺便把最接近的几个候选回过去，方便模型自我纠正）。
 * ⑤ 结果**截断**后再回给模型（引擎能吐很大的矩阵/数组），但界面显示仍用完整值。
 */

import { ENGINE_MAP } from "../engine/engineMap.js";
import { engineCall } from "../bridge.js";
import type { ToolSchema } from "./types.ts";

/** 一个引擎函数（由 ENGINE_MAP 反推：多个中文模式可能指向同一个 fn） */
export interface EngineFn {
  fn: string;
  module: string;
  modes: string[];
  args: { key: string; type: string; opt: boolean }[];
}

/** 调用记录（界面拿它渲染"这一步做了什么"，也是测试的断言对象） */
export interface ToolCallRecord {
  name: string;
  fn?: string;
  args?: Record<string, unknown>;
  ok: boolean;
  /** 回给模型的内容（已截断） */
  content: string;
  /** 界面显示用的摘要（完整值不截断） */
  summary: string;
  ms: number;
}

/* ── 目录（从 ENGINE_MAP 反推）────────────────────────────────────────── */

const CATALOG: EngineFn[] = (() => {
  const byFn = new Map<string, EngineFn>();
  for (const [mode, spec] of Object.entries(ENGINE_MAP as Record<string, any>)) {
    const fn = String(spec?.fn || "").trim();
    if (!fn) continue;
    let cur = byFn.get(fn);
    if (!cur) {
      cur = { fn, module: String(spec?.module || ""), modes: [], args: [] };
      byFn.set(fn, cur);
    }
    cur.modes.push(mode);
    for (const a of (spec?.args || []) as { key: string; type: string; opt?: boolean }[]) {
      const key = String(a?.key || "");
      if (!key) continue;
      const seen = cur.args.find((x) => x.key === key);
      if (!seen) cur.args.push({ key, type: String(a?.type || "string"), opt: !!a?.opt });
      // 同一个 fn 在不同模式下对同一参数的要求可能不同：**从严**（任一处必填就算必填）
      else if (!a?.opt) seen.opt = false;
    }
  }
  return [...byFn.values()].sort((a, b) => a.fn.localeCompare(b.fn));
})();

export const ENGINE_FN_COUNT = CATALOG.length;

const BY_NAME = new Map(CATALOG.map((e) => [e.fn.toLowerCase(), e]));

export function listEngineModules(): { module: string; fns: number }[] {
  const m = new Map<string, number>();
  for (const e of CATALOG) m.set(e.module || "(未分组)", (m.get(e.module || "(未分组)") || 0) + 1);
  return [...m.entries()].map(([module, fns]) => ({ module, fns })).sort((a, b) => a.module.localeCompare(b.module));
}

/** 找函数：按函数名 / 模块名 / 中文模式名匹配（中文模式名对国内模型很好用） */
export function findEngineFns(query: string, limit = 12): EngineFn[] {
  const q = String(query || "").trim().toLowerCase();
  if (!q) return [];
  const scored: { e: EngineFn; score: number }[] = [];
  for (const e of CATALOG) {
    let score = 0;
    const fn = e.fn.toLowerCase();
    if (fn === q) score = 100;
    else if (fn.startsWith(q)) score = 80;
    else if (fn.includes(q)) score = 60;
    if (e.module.toLowerCase().includes(q)) score = Math.max(score, 40);
    if (e.modes.some((m) => m.toLowerCase() === q)) score = Math.max(score, 90);
    else if (e.modes.some((m) => m.toLowerCase().includes(q))) score = Math.max(score, 50);
    if (score > 0) scored.push({ e, score });
  }
  return scored.sort((a, b) => b.score - a.score || a.e.fn.localeCompare(b.e.fn)).slice(0, limit).map((s) => s.e);
}

/** 给模型看的签名：`solve_quadratic(expr: string, var?: string) — 模块 algebra · 模式 解一元二次` */
export function signature(e: EngineFn): string {
  const args = e.args.map((a) => `${a.key}: ${a.type}${a.opt ? "?" : ""}`).join(", ");
  const modes = e.modes.slice(0, 3).join(" / ") + (e.modes.length > 3 ? " …" : "");
  return `${e.fn}(${args})${e.module ? ` — 模块 ${e.module}` : ""}${modes ? ` · 模式 ${modes}` : ""}`;
}

/* ── 参数校验 ─────────────────────────────────────────────────────────── */

export function validateArgs(e: EngineFn, args: Record<string, unknown>):
  { ok: true } | { ok: false; error: string } {
  // 动作表里没有 args（`args: []`）的函数：引擎自己会判断，这里不拦
  if (e.args.length === 0) return { ok: true };

  const known = new Set(e.args.map((a) => a.key));
  const given = Object.keys(args || {});
  const missing = e.args.filter((a) => !a.opt && !(a.key in (args || {}))).map((a) => a.key);
  const unknown = given.filter((k) => !known.has(k));
  // 参数名写错是最常见的一类：把正确名字直接摆出来，模型下一轮就能改对
  if (missing.length || unknown.length) {
    const parts: string[] = [];
    if (missing.length) parts.push(`缺少必填参数 ${missing.join(", ")}`);
    if (unknown.length) parts.push(`不认识的参数 ${unknown.join(", ")}`);
    return { ok: false, error: `${parts.join("；")}。本函数的参数是：${signature(e)}` };
  }
  return { ok: true };
}

/* ── 工具定义 ─────────────────────────────────────────────────────────── */

/**
 * 形状用**内部扁平形**（`{name, description, parameters}`）—— 与 `types.ts` 的 `ToolSchema` 一致，
 * 线上格式由 client.ts 的 `toWireTool` 转换（那里才是 OpenAI 的 `{type:"function", function:{…}}`）。
 *
 * 描述里最重要的那句是"不要自己算"：模型天然倾向于心算，
 * 而这一层的全部意义就是让计算发生在引擎里。
 */
export const AI_TOOLS: ToolSchema[] = [
  {
    name: "engine_find",
    description:
      `查找可用的引擎函数（本地 C++ 数学引擎，共 ${ENGINE_FN_COUNT} 个函数）。` +
      "用函数名、模块名或中文模式名都可以查。传空 query 会列出所有模块与函数数量。" +
      "需要计算时先用它确认函数名与参数，再用 engine_call 调用。",
    parameters: {
      type: "object",
      properties: {
        query: { type: "string", description: "搜索词：函数名（如 solve_quadratic）、模块（calculus）或中文模式名（解一元二次）。空字符串 = 列出模块" },
        module: { type: "string", description: "可选：限定模块，如 algebra / calculus / linear_algebra" },
      },
      required: ["query"],
    },
  },
  {
    name: "engine_call",
    description:
      "调用本地 C++ 引擎做一次真实计算，返回引擎的结果。" +
      "**所有数值计算、化简、求解、求导、积分等都必须通过它完成，不要自己心算或推断数值**——" +
      "你负责讲思路与措辞，计算交给引擎。参数写错或缺少必填项时，会返回具体缺什么，按提示改正后再调。",
    parameters: {
      type: "object",
      properties: {
        fn: { type: "string", description: "引擎函数名，必须是 engine_find 查到的名字" },
        args: { type: "object", description: "该函数的参数对象，键名与 engine_find 给出的一致" },
      },
      required: ["fn", "args"],
    },
  },
];

export const TOOL_NAMES = new Set(AI_TOOLS.map((t) => t.name));

/* ── 执行 ─────────────────────────────────────────────────────────────── */

const MAX_CONTENT = 3000;   // 回给模型的上限（界面仍显示完整值）
const MAX_SUMMARY = 600;

function clip(s: string, max: number): string {
  return s.length <= max ? s : s.slice(0, max) + `…（已截断，共 ${s.length} 字符）`;
}

/**
 * 执行一次工具调用。
 *
 * @param allowResults 「发送引擎结果」隐私开关。关着时**拒绝**工具调用并说明原因 ——
 *   工具的结果要回传给模型，那就是"把引擎结果发出去"，不能绕过用户的选择。
 */
export function executeTool(name: string, args: Record<string, unknown>, allowResults: boolean): ToolCallRecord {
  const t0 = Date.now();
  const done = (rec: Omit<ToolCallRecord, "ms">): ToolCallRecord => ({ ...rec, ms: Date.now() - t0 });

  if (!TOOL_NAMES.has(name)) {
    const content = `{"ok":false,"error":"没有这个工具：${name}。可用工具只有 engine_find 与 engine_call。"}`;
    return done({ name, ok: false, content, summary: content });
  }

  if (name === "engine_find") {
    const query = String((args as any)?.query ?? "");
    const module = String((args as any)?.module ?? "");
    if (!query && !module) {
      const mods = listEngineModules();
      const content = JSON.stringify({ modules: mods, total: ENGINE_FN_COUNT });
      return done({ name, ok: true, content: clip(content, MAX_CONTENT), summary: `${mods.length} 个模块 / ${ENGINE_FN_COUNT} 个函数` });
    }
    let hits = findEngineFns(query || module, 40);
    if (module) hits = hits.filter((e) => e.module.toLowerCase().includes(module.toLowerCase()));
    if (!hits.length) {
      const content = `{"ok":false,"error":"没有匹配的函数。先不带参数调用 engine_find 看模块列表，或换关键词。"}`;
      return done({ name, ok: false, content, summary: "没有匹配的函数" });
    }
    const lines = hits.slice(0, 12).map(signature);
    const content = clip(JSON.stringify({ ok: true, count: hits.length, hint: "用 engine_call 调用，参数键名见签名", functions: lines }), MAX_CONTENT);
    return done({ name, ok: true, content, summary: `${hits.length} 个匹配：${hits.slice(0, 3).map((h) => h.fn).join(", ")}${hits.length > 3 ? " …" : ""}` });
  }

  // ── engine_call ──
  const fn = String((args as any)?.fn ?? "").trim();
  const callArgs = ((args as any)?.args ?? {}) as Record<string, unknown>;

  if (!fn) {
    const content = `{"ok":false,"error":"缺少 fn。"}`;
    return done({ name, fn: "", ok: false, content, summary: "缺少 fn" });
  }
  // ④ 函数名必须在引擎表里；表外一律拒绝（顺手给候选，别让模型瞎试）
  const entry = BY_NAME.get(fn.toLowerCase());
  if (!entry) {
    const near = findEngineFns(fn, 5).map((e) => e.fn);
    const content = JSON.stringify({
      ok: false,
      error: `引擎里没有 ${fn} 这个函数。`,
      candidates: near,
      hint: near.length ? "用上面最接近的名字重试；也可用 engine_find 查。" : "先用 engine_find 查函数名。",
    });
    return done({ name, fn, ok: false, content: clip(content, MAX_CONTENT), summary: `没有函数 ${fn}` });
  }
  if (typeof callArgs !== "object" || callArgs === null || Array.isArray(callArgs)) {
    const content = `{"ok":false,"error":"args 必须是一个对象，例如 {\\"expr\\":\\"x^2-4\\"}"}`;
    return done({ name, fn: entry.fn, ok: false, content, summary: "args 不是对象" });
  }
  // 只允许 JSON 能表达的值：防止把函数/循环引用塞进桥调用
  let safeArgs: Record<string, unknown>;
  try {
    safeArgs = JSON.parse(JSON.stringify(callArgs));
  } catch {
    const content = `{"ok":false,"error":"args 必须是可序列化的普通值（字符串/数字/布尔/数组/对象）"}`;
    return done({ name, fn: entry.fn, ok: false, content, summary: "args 不可序列化" });
  }

  const v = validateArgs(entry, safeArgs);
  if (!v.ok) {
    const content = JSON.stringify({ ok: false, error: v.error });
    return done({ name, fn: entry.fn, args: safeArgs, ok: false, content, summary: v.error });
  }

  // 隐私闸门：工具结果要回传给模型，等于"把引擎结果发出去"
  if (!allowResults) {
    const content = JSON.stringify({
      ok: false,
      error: "用户关闭了「发送引擎结果」，而工具调用的结果必须回传给模型 —— 所以现在不能调用引擎。",
      hint: "请告诉用户：要用工具计算，需要在 AI 设置里打开「发送引擎结果」。不要自己估算数值。",
    });
    return done({ name, fn: entry.fn, args: safeArgs, ok: false, content, summary: "被隐私开关拦住（未开启「发送引擎结果」）" });
  }

  const res = engineCall(entry.fn, safeArgs);
  if (res === null) {
    const content = `{"ok":false,"error":"没有连上本地引擎（可能不在 MFMath.exe 里运行）"}`;
    return done({ name, fn: entry.fn, args: safeArgs, ok: false, content, summary: "没有连上引擎" });
  }

  const isError = !!(res as any).isError;
  const value = (res as any).value;
  const valueJson = typeof value === "string" ? value : JSON.stringify(value);
  const content = clip(JSON.stringify({
    ok: !isError,
    fn: entry.fn,
    ...(isError ? { error: valueJson } : { value: valueJson }),
  }), MAX_CONTENT);

  return done({
    name,
    fn: entry.fn,
    args: safeArgs,
    ok: !isError,
    content,
    summary: clip(`${entry.fn}(${JSON.stringify(safeArgs)}) → ${valueJson}`, MAX_SUMMARY),
  });
}

/** 测试/排障钩子：把工具能力暴露给断言（含"只能调引擎"这条边界） */
export function initAiToolsHook() {
  try {
    (window as any).__mfAiTools = {
      catalogSize: () => ENGINE_FN_COUNT,
      modules: listEngineModules,
      find: findEngineFns,
      signature,
      validate: (fn: string, args: Record<string, unknown>) => {
        const e = BY_NAME.get(String(fn).toLowerCase());
        if (!e) return { ok: false, error: "没有这个函数" };
        return validateArgs(e, args);
      },
      tools: () => AI_TOOLS,
      execute: executeTool,
      nameOf: (fn: string) => BY_NAME.get(String(fn).toLowerCase())?.fn ?? "",
    };
  } catch { /* 忽略 */ }
}
