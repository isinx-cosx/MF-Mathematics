/**
 * knownNames.js — "引擎/界面都当常量或函数看"的名字表。
 *
 * 为什么单独一个文件：`plotMath.js` 与 `userFn.js` 都要用它，而
 * `plotMath.js` 又要 import `userFn.js`（定义分支要用 parseDefinition）。
 * 把这张表放在第三方文件里，两边都从这儿取，依赖就是**单向**的，
 * 不用依赖"ESM 循环引用在这里恰好安全"这种运气。
 */
"use strict";

/** 已知常量与函数名（不视作参数，也不允许被用户重定义） */
export const KNOWN = new Set([
  "pi", "e", "tau", "inf", "nan", "true", "false",
  "sin", "cos", "tan", "csc", "sec", "cot",
  "asin", "acos", "atan", "acsc", "asec", "acot",
  "sinh", "cosh", "tanh", "asinh", "acosh", "atanh",
  "sqrt", "cbrt", "abs", "exp", "log", "ln", "log2", "log10",
  "floor", "ceil", "round", "sign", "max", "min", "mod", "pow",
  "factorial", "gamma", "erf",
  // Desmos 常用简写
  "arcsin", "arccos", "arctan",
]);

/** 这个名字是不是内置的常量/函数 */
export function isKnownName(name) {
  return KNOWN.has(String(name));
}
