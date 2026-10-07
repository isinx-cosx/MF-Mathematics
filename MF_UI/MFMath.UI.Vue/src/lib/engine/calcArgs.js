/**
 * 引擎参数构造（移植自旧版 MFMath.UI/js/calcblock.js，并按类型补全）
 *
 * 两条路径：
 *  ① 自动映射：用 ENGINE_MAP[mode].args 的签名 + ENGINE_VAR_SPECS 的默认值
 *  ② 多参数弹窗：用户逐项填写 VAR_SPECS 字段后
 *
 * ⚠ 2026-09 修正（原实现把结构化参数当字符串/数字塞，导致一类静默失败）：
 *   旧代码对非 string 参数一律 `a.type === 'double' ? 0 : 1`，于是
 *     · point        → 1     （引擎 get_point 要求 [x,y]）
 *     · matrix       → 1     （get_matrix 要求 [[…]]）
 *     · double_array → 1     （方差/插值/检验这类模式全部打不开）
 *     · 可选参数缺省时被塞成 1，而不是"省略、让引擎用自己的默认"
 *   现在按声明的类型真解析，并且输入框支持用 `;` 分段一次给多个参数：
 *     "(1,2);(3,4)"     → p1=[1,2], p2=[3,4]
 *     "1,2,3"           → data=[1,2,3]
 *     "[[1,2],[3,4]]"   → matrix
 *     "x^2-4; -2; 2"    → expr="x^2-4"，再补 a=-2, b=2
 *     "x>1; x<3"        → string_array ["x>1","x<3"]
 *   不分号的老写法行为不变（只有一个表达式时走 VAR_SPECS/引擎默认）。
 */
"use strict";

import { ENGINE_MAP, ENGINE_VAR_SPECS } from "./engineMap.js";

/**
 * 表达式语法归一化。
 *
 * 曾经这里是"旧版 UI 的 ^ 幂写法 → 引擎的 **"的替换。2026-09 统一为 **使用 `^`**：
 * 引擎（math_input.h 的归一化）现在把 `**` 也归一到 `^`，界面不再做任何算符替换，
 * 语法归一化只发生在引擎里一处（避免"界面换一种、引擎换一种"的两套写法）。
 */
export function toEngineExpr(s) {
  return String(s == null ? "" : s);
}

/**
 * 跳过不映射到引擎参数的字段（变量/表达式类，用输入框或默认值提供）。
 * 「（输入框）」是显式约定：该字段就是输入框的占位，值已经在弹窗第一个格子里预填。
 *
 * ⚠ 这里**不能**用宽松的 `includes("函数")`：字段表里还有「第二个函数」「未知函数」
 * 这类**真的要喂给引擎**的字段（内积空间的 g、一阶 ODE 的 yvar），一并跳过会让它们
 * 静默取默认值——用户填了也不生效。判断只认显式约定与明确属于"主表达式"的措辞。
 */
export function isSkippedField(label) {
  const s = String(label ?? "");
  return s.includes("（输入框）") || s.includes("(输入框)")
      || s === "变量" || s.includes("表达式") || s.includes("被积")
      || s.includes("通项");
}

/** 结构化参数类型：必须真解析成数组/点，不能当字符串 */
export const STRUCTURED = new Set([
  "point", "vec", "vector", "matrix", "matrix_list", "point_cloud", "prob_table",
  "double_array", "int_array", "string_array", "double_list", "int_list", "pair_list", "complex_obj",
  "ll_matrix", "ll_array", "ll_list",
]);

/** 按深度 0 的分号/换行切段：括号里的分号不算分隔；只去掉末尾空段，位置保持稳定 */
export function splitSegments(text) {
  const s = String(text ?? "");
  const parts = [];
  let depth = 0, cur = "";
  for (const c of s) {
    if ("([{".includes(c)) depth++;
    else if (")]}".includes(c)) depth = Math.max(0, depth - 1);
    if ((c === ";" || c === "\n") && depth === 0) { parts.push(cur); cur = ""; continue; }
    cur += c;
  }
  parts.push(cur);
  const out = parts.map((x) => x.trim());
  if (out.length > 1 && out[out.length - 1] === "") out.pop();
  return out;
}

/** 文本 → 数字数组（容忍 [] () 逗号 空格 与中文逗号） */
function numberList(text) {
  const t = String(text ?? "").replace(/[\[\](){}]/g, " ").replace(/[，、]/g, " ");
  const out = [];
  for (const p of t.split(/[\s,]+/)) {
    if (p === "") continue;
    const v = Number(p);
    if (Number.isFinite(v)) out.push(v);
  }
  return out;
}

/** 文本 → 矩阵（"[[1,2],[3,4]]" / "1,2; 3,4" / "1,2,3,4" 都接受） */
function matrixOf(text) {
  const s = String(text ?? "").trim();
  if (s.startsWith("[[")) {
    try {
      const v = JSON.parse(s.replace(/，/g, ","));
      if (Array.isArray(v) && v.length && v.every(Array.isArray)) return v.map((r) => r.map(Number));
    } catch { /* 落到下面的宽松解析 */ }
  }
  const rows = s.split(/[;\n]/).map((r) => numberList(r)).filter((r) => r.length);
  if (rows.length > 1) return rows;
  const flat = numberList(s);
  return flat.length ? [flat] : [];
}

/** 文本 → 矩阵数组（[[[…]],…]；只给一个矩阵时包成单元素数组） */
function matrixListOf(text) {
  const s = String(text ?? "").trim();
  if (s.startsWith("[[[")) {
    try {
      const v = JSON.parse(s.replace(/，/g, ","));
      if (Array.isArray(v) && v.every((m) => Array.isArray(m) && m.every(Array.isArray)))
        return v.map((m) => m.map((r) => r.map(Number)));
    } catch { /* 落到单矩阵处理 */ }
  }
  const m = matrixOf(s);
  return m.length ? [m] : [];
}

/**
 * 文本 → 概率表对象：`"A_and_B=0.2; B=0.5"` → `{A_and_B:0.2, B:0.5}`。
 * 条件概率/全概率/贝叶斯要的是"带具体键名的对象"，前端没法从纯数值输入拼出来，
 * 所以给一个最直白的 `键=值; 键=值` 写法。
 */
function complexObjOf(text) {
  const s = String(text ?? "").trim();
  if (s.startsWith("{")) { try { return JSON.parse(s); } catch { return {}; } }
  const out = {};
  for (const seg of s.split(/[|;]\s*/)) {
    const i = seg.indexOf(":");
    if (i <= 0) continue;
    const dim = seg.slice(0, i).trim();
    const sims = seg.slice(i + 1).split(/,\s*/).filter((x) => x !== "");
    if (sims.length) out[dim] = [sims.map((v) => Math.trunc(Number(v) || 0))];
  }
  return out;
}

function probTableOf(text) {
  const out = {};
  for (const seg of String(text ?? "").split(/[;,]\s*/)) {
    const i = seg.indexOf("=");
    if (i <= 0) continue;
    const k = seg.slice(0, i).trim();
    const v = Number(seg.slice(i + 1).trim());
    if (k) out[k] = Number.isFinite(v) ? v : 0;
  }
  return out;
}

/** 文本 → 点 [x,y]（写成分组的 (1,2) 时取第一组） */
function pointOf(text) {
  const g = String(text ?? "").match(/[(（[][^)）\]]*[)）\]]/);
  const flat = numberList(g ? g[0] : text);
  return flat.slice(0, 2);
}

/**
 * 按类型把文本转成引擎要的 JSON 值。
 * 解析不出来时**原样返回文本**：让引擎抛出它自己的参数错误（对话框里能看到中文原因）。
 * 在这里静默塞 0/1 才是真正难查的失败。
 */
export function convertArg(type, raw) {
  const s = String(raw == null ? "" : raw).trim();
  switch (type) {
    case "double": return Number.isFinite(Number(s)) ? Number(s) : s;
    case "int": return Number.isFinite(Number(s)) ? Math.trunc(Number(s)) : s;
    case "bool": return s === "true" || s === "1" || s === "是";
    case "string_or_number": return /^-?\d+(\.\d+)?$/.test(s) ? Number(s) : toEngineExpr(s);
    case "point": return pointOf(s);
    case "vec": case "vector": return numberList(s);
    case "matrix": return matrixOf(s);
    case "matrix_list": return matrixListOf(s);
    case "point_cloud": return matrixOf(s);   // 点云就是 [[x,y],…]
    case "prob_table": return probTableOf(s);
    case "complex_obj": return complexObjOf(s);
    case "ll_matrix": return matrixOf(s);
    case "ll_array": case "ll_list": return numberList(s);
    // pair_list（[[a,b],…]，如「简单函数」的 sets）原先**没有分支**，直接落到
    // default: toEngineExpr → 变成字符串 → 引擎报「缺少数组参数 sets」。
    // 而用到 pair_list 的这两个模式都**没有参数弹窗**，于是 sets 根本填不进去，
    // 模式永远算不出来（实测：点计算只得到"缺少数组参数 sets"）。
    // 用与 matrix 同一套写法即可：`[[0,1],[1,2]]`。
    case "pair_list": return matrixOf(s);
    // sig（信号/序列数组，高斯模糊/低通滤波器/短时傅里叶变换/小波变换）
    // 同样原先没有分支 → 落到 default: toEngineExpr → 字符串 → 引擎报"缺少数组参数 signal"。
    case "sig": return numberList(s);
    case "double_array": case "double_list": return numberList(s);
    case "int_array": case "int_list": return numberList(s).map((v) => Math.trunc(v));
    case "string_array": return splitSegments(s);
    default: return toEngineExpr(s);
  }
}

/**
 * 必填参数拿不到值时的兜底值。
 *
 * ⚠ 这些值**在引擎眼里全都是合法值**（0 / [0,0] / [] / ""），所以引擎不会报错，
 * 而是拿它们老老实实算出一个结果。注释里曾写"仍交给引擎校验并报错"，**那是错的**：
 * 「某点导数」缺 point 时静默算成 f'(0)，用户以为算的是自己想的那个点（BUGS.md B4）。
 * 因此每次走到这里都要经 noteDefaulted() 记账，由调用点决定怎么告诉用户。
 */
function fallbackOf(type) {
  switch (type) {
    case "double": case "int": return 0;
    case "bool": return false;
    case "point": return [0, 0];
    default: return STRUCTURED.has(type) ? [] : "";
  }
}

/**
 * 记账：这次调用里有哪些**必填**参数是"替用户填的"。
 *
 * 为什么要这个通道：构造器返回的就是引擎参数对象本身，没有地方放"警告"。
 * 而"用了兜底"这件事必须能传出去 —— 否则用户看到的就是一个**看起来很正常的错结果**。
 * 收集器由调用点传入（可选参数，老调用点一行都不用改）。
 * @param {{defaulted?: Array<{key:string,type:string,value:unknown}>}|undefined} report
 * @param {{key:string,type:string}} a 参数声明
 */
function noteDefaulted(report, a) {
  if (!report || !Array.isArray(report.defaulted)) return;
  report.defaulted.push({ key: a.key, type: a.type, value: fallbackOf(a.type) });
}

/**
 * 选"输入框的第一段喂给哪个参数"。
 *
 * 这段规则原先在文件里**复制了 3 份**（其中两份逐字相同），于是任何一处改动都极易
 * 只落到一处 —— 这类漂移在本文件里已经出过事（BUGS.md B12）。现在只有这一处实现。
 *
 * 两种口径是**有意不同**的，不要合并：
 *   · `skipWholeString: true`（自动映射路径）：排除 `string_array`（整组条件）与
 *     `complex_obj`（整串复形），因为它们要的是"整串"而不是"第一段"；
 *     找不到就返回 undefined，把整串留给后面的整串分支处理。
 *     ⚠ 也**不能**退回 `args[0]`：唯一参数就是 string_array 时（「解不等式/组」），
 *     退回 args[0] 会把整串交给"只吃第一段"的逻辑，于是 `x>1; x<3` 只剩 x>1（BUGS.md B2③）。
 *   · `skipWholeString: false`（弹窗路径）：必填字符串 → 第一个必填 → 第一个声明的。
 *     弹窗第一格是输入框镜像，本来就该落到"那条表达式"上；首参是数字/矩阵的模式
 *     （等差数列、Lp 范数）也要能拿到它。
 *
 * @param {Array<{key:string,type:string,opt?:boolean}>} args 参数声明
 * @param {{skipWholeString?:boolean}} [opt]
 */
function pickTextArg(args, opt = {}) {
  const list = Array.isArray(args) ? args : [];
  const reqString = list.find((a) => !a.opt && a.type === "string");
  if (reqString) return reqString;
  if (opt.skipWholeString) {
    return list.find((a) => !a.opt && a.type !== "string_array")
        || list.find((a) => a.type !== "string_array" && a.type !== "complex_obj")
        || list.find((a) => a.type !== "string_array");
  }
  return list.find((a) => !a.opt) || list[0];
}

/**
 * 自动映射构造参数
 * @param {string} mode 中文模式名
 * @param {string} expr 用户输入的表达式（可用 `;` 分段附带结构化参数）
 * @param {{defaulted?: Array<object>}} [report] 可选收集器：调用点传入后即可知道
 *        哪几个**必填**参数是兜底填的（见 noteDefaulted / BUGS.md B4）
 * @returns {object|null} 引擎参数对象；模式未映射时返回 null
 */
export function buildEngineArgs(mode, expr, report) {
  const spec = ENGINE_MAP[mode];
  if (!spec) return null;
  const fields = ENGINE_VAR_SPECS[mode] || [];
  const segments = splitSegments(expr);
  const args = {};
  const missingRequired = [];
  const eat = (a, text) => (a.type === "string" ? toEngineExpr(text) : convertArg(a.type, text));
  let seg = 0;

  // ① 第一段永远是"那条表达式"：给第一个必填的字符串参数
  //    （不能按声明顺序给 —— 傅里叶系数这类模式的必填项是 n:int 在前、f:string 在后，
  //      那样会把用户写的表达式当项号。）
  //    选法与口径说明见 pickTextArg（原来这里是一段复制出来的 find 链）。
  const textArg = pickTextArg(spec.args, { skipWholeString: true });
  // 必须按类型转换：textArg 现在可能是数字/矩阵/点等（旧写法一律 toEngineExpr，
  // 结果把 "5" 当字符串塞给 int 参数 → "参数 n 类型错误"。string_array 交给下面的分支整组处理）
  /* ⚠ prob_table 是"整串就是一张表"的类型：`;` 在它里面是**表项分隔符**，不是参数分隔符。
   * 不特殊处理的话，条件概率/独立性/全概率/贝叶斯自带的那串
   * "A_and_B=0.2; B=0.5" 会在这里被切成两段，表只剩前半张（BUGS.md B2①）——
   * 而 buildEngineArgs 的 ④ 还会把剩下的半张喂给下一个参数，于是 A 变成 "B=0.5"。
   * 所以对 prob_table 一律"整串 join 回去"（与下面 string_array 的处理同一个思路）。 */
  if (textArg && segments.length) {
    if (textArg.type === "prob_table") {
      args[textArg.key] = convertArg("prob_table", segments.join(";"));
      seg = segments.length;
    } else {
      args[textArg.key] = eat(textArg, segments[seg++]);
    }
  }

  // ② 不等式组这类：剩下的段整组当字符串数组
  for (const a of spec.args) {
    if (a.type !== "string_array" || a.key in args) continue;
    args[a.key] = convertArg("string_array", segments.slice(seg).join(";"));
    seg = segments.length;
  }

  // ③ 其余必填参数按声明顺序吃段
  for (const a of spec.args) {
    if (a.opt || a.key in args) continue;
    if (seg < segments.length) { args[a.key] = eat(a, segments[seg++]); continue; }
    missingRequired.push(a);
  }

  // ④ 还有剩余的段 → 补给可选参数（"x^2-4; -2; 2"）
  for (const a of spec.args) {
    if (!a.opt || a.key in args) continue;
    if (seg >= segments.length) break;
    args[a.key] = eat(a, segments[seg++]);
  }

  // ⑤ 仍缺的必填参数 → VAR_SPECS 字段（跳掉表达式类字段），再不行按类型兜底
  let fi = 0;
  const skipField = () => { while (fi < fields.length && isSkippedField(fields[fi][0])) fi++; };
  const takeField = () => { skipField(); return fi < fields.length ? fields[fi++][1] : null; };
  for (const a of missingRequired) {
    const v = takeField();
    if (v === null) {
      // 必填却拿不到值：兜底 + **记账**（引擎不会报错，但结果已不是用户要的，见 B4）
      noteDefaulted(report, a);
      args[a.key] = fallbackOf(a.type);
    } else {
      args[a.key] = eat(a, v);
    }
  }

  // ⑥ 其余可选参数 → VAR_SPECS 字段；没有就**整个键省略**，让引擎用自己的默认值
  for (const a of spec.args) {
    if (a.key in args) continue;
    const v = takeField();
    if (v !== null) args[a.key] = eat(a, v);
  }
  return args;
}

/**
 * 用多参数弹窗收集的值构造参数
 *
 * 规则（与弹窗交互对齐）：
 *   ① 输入框内容（values[0]，也就是弹窗第一个格子预填的值）喂给
 *      **第一个必填参数**；若没有必填参数，则喂给第一个声明的参数。
 *      旧实现只认"第一个必填字符串"，于是首参是数字/矩阵的模式（等差数列、Lp范数、
 *      拉格朗日插值…）拿不到输入框里的值。
 *   ② 其余字段按顺序填剩下的参数：先必填，后可选；跳过「（输入框）」占位字段。
 * @param {object} spec ENGINE_MAP[mode]
 * @param {Array<[string,string]>} fields VAR_SPECS 的字段定义
 * @param {string[]} values 用户填写的值（与 fields 一一对应）
 * @param {{defaulted?: Array<object>}} [report] 可选收集器，同 buildEngineArgs（见 BUGS.md B4）
 */
export function buildEngineArgsFromValues(spec, fields, values, report) {
  const args = {};
  // 弹窗第一个格子就是输入框的内容，里面同样可以用 `;` 分段带参数：
  //   "x^3; x; 2" + 弹窗默认 → 不必逐个手填
  const boxText = String((values && values[0]) ?? "");
  const segments = splitSegments(boxText);
  /* ⚠ 判空要看**去掉空白后的字符串**，不能靠 segments：
   * splitSegments("") 返回的是**空数组**，于是 `segments.length === 1 && segments[0] === ""`
   * 恒为 false —— 输入框明明空着却被判成"有输入"。后果是走"有输入框"的分支但没有段可吃，
   * 字段队列从一个本不该被消费的位置开始，整体错位一格（乘积测度实测：
   * mu 吃了 nu 的格子 → 引擎报"值不是数字"）。 */
  const boxEmpty = boxText.trim() === "";
  // 输入框为空时（例如"只靠弹窗填参数"的模式）跳过它，直接吃弹窗字段
  const rest = fields
    .map((f, i) => ({ label: f[0], value: values[i] }))
    .filter((f, i) => i > 0 && !isSkippedField(f.label));
  let ui = 0, seg = 0;
  /* 输入框整串被当成**一张概率表**吃掉时置真。为什么需要它：下面的 ui 是"弹窗字段要跳过
   * 几格"（段已经填掉几个参数）。而概率表是把所有段 join 成一张表用的，**没有**填掉
   * 若干个参数，所以此时 ui 必须是 0，否则字段队列会整体错位（BUGS.md B2①）。 */
  let tableTookAll = false;
  const conv = (a, v) => (a.type === "string" ? toEngineExpr(String(v)) : convertArg(a.type, v));

  if (!boxEmpty) {
    // ① 第一段给第一个必填字符串参数（"那条表达式"），其次给第一个必填参数
    const textArg = pickTextArg(spec.args);
    if (textArg) {
      if (textArg.type === "prob_table") {
        // 整串就是一张表：`;` 是表项分隔符（同 buildEngineArgs 里那段说明）
        args[textArg.key] = conv(textArg, segments.join(";"));
        seg = segments.length;
        tableTookAll = true;
      } else {
        args[textArg.key] = conv(textArg, segments[seg++]);
      }
    }
    // ② 剩下的段：**先必填、后可选**，按声明顺序（与 buildEngineArgs 同一规则）。
    //    旧写法按声明顺序一把梭，遇到"可选参数声明在前"的模式（RK4 的 h）会把
    //    第一段参数喂给可选参数，必填参数反而落空。
    for (const pass of [false, true]) {
      for (const a of spec.args) {
        if (!!a.opt !== pass || a.key in args) continue;
        if (seg >= segments.length) break;
        args[a.key] = conv(a, segments[seg++]);
      }
    }
  }

  // 段已经填过若干参数 → 对应的弹窗字段也要跳过，否则同一参数被"段"和"字段"各填一次
  // （交换律验证就是这样把运算符填成了 b 的值）
  ui = tableTookAll ? 0 : Math.max(0, seg - 1);
  /* 输入框为空时，先处理**第 0 格**（输入框的镜像）。
   *
   * 它对应的参数（textArg，与 ① 的选法一致）此时拿不到"段"，但**这一格自己是有值的**：
   * 多数模式是空串，而有的模式默认值是有意义的 —— 乘积测度的第 0 格默认就是 "lebesgue"。
   * 早先这里直接把这个参数**整个跳过**，于是 mu 根本没传给引擎，
   * product_measure 读不到 mu → as_double 抛「值不是数字」（cdp-engine-coverage 实测）。
   * 现在用这一格自己的值填；为空时才走 fallbackOf（引擎仍会如实报"缺少必填参数 X"）。 */
  {
    const textArg = pickTextArg(spec.args);
    const f0 = fields[0];
    // 注意：**不能**因为第 0 格带"（输入框）"就跳过它 —— isSkippedField 说"它是输入框的镜像、
    // 不进字段队列"是对的，但**空输入框**时这一格的默认值正是该参数该取的值
    // （乘积测度第 0 格默认 "lebesgue"；其它模式是 ""，于是走 fallback，引擎照样如实报错）。
    if (boxEmpty && textArg && f0 && values.length) {
      const v = values[0];
      if (String(v ?? "") === "") {
        // 必填（textArg 非可选）却连这一格的默认值都是空 → 兜底并记账
        if (!textArg.opt) noteDefaulted(report, textArg);
        args[textArg.key] = fallbackOf(textArg.type);
      } else {
        args[textArg.key] = conv(textArg, v);
      }
    }
  }
  // ③ 其余必填参数（弹窗字段优先，其次兜底）
  for (const a of spec.args) {
    if (a.opt || a.key in args) continue;
    if (ui < rest.length) {
      args[a.key] = conv(a, rest[ui++].value);
    } else {
      noteDefaulted(report, a);          // 必填却没有格子可填 → 记账（见 B4）
      args[a.key] = fallbackOf(a.type);
    }
  }
  // ④ 可选参数（剩余字段；没有就省略 → 用引擎默认）
  for (const a of spec.args) {
    if (!a.opt || a.key in args) continue;
    if (ui < rest.length) args[a.key] = conv(a, rest[ui++].value);
  }
  return args;
}

/* hasEngineMode 只在 engineMap.js 里实现**一处**，这里原样再导出（既有调用点无需改动）。
 * 从前这里又实现了一遍逐字相同的判断，两份各改一半就会分叉（BUGS.md B12）。 */
export { hasEngineMode } from "./engineMap.js";

/** 模式是否需要多参数弹窗 */
export function needsVarDialog(mode) {
  return Object.prototype.hasOwnProperty.call(ENGINE_VAR_SPECS, mode);
}

export { ENGINE_MAP, ENGINE_VAR_SPECS };
