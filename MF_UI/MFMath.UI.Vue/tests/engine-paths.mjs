/**
 * engine-paths.mjs —— **树外路径的唯一解析处**（BUGS.md B8）
 *
 * 为什么需要它：引擎构建产物、引擎源码、以及 v1 的教程 YAML，**都不在这个仓库里**：
 *   · 引擎在 v2.0 的兄弟目录  `<v2.0>/MF_Mathematics`；
 *   · 教程源在**另一棵树**       `<v2.0>/../Multifunctional-Mathematics/MF_Tutorial/tutorials`。
 * 以前这些路径被逐个写死成 `C:/Users/fsafsafsa/Desktop/...`，后果有两个：
 *   ① 换台机器、换用户名、进 CI 时直接抛 ENOENT/EPERM，而且错误信息里看不出该改哪里；
 *   ② 其中两条指向 `Desktop/cppcshap/MF_Mathematics` —— 那是**完全另一棵树**，
 *      早就不是这份代码所跑的引擎了（正确的那份在 `<v2.0>/MF_Mathematics`）。
 *
 * 规矩（与项目里"不静默降级"的一贯做法一致）：
 *   **环境变量 → 相对本文件推导**；推导不出来就打印一句能照着做的提示并退出，
 *   不猜路径、不假装成功、也不要让它抛一个只有 errno 的异常。
 *
 * 可覆盖的环境变量：`MF_ENGINE_ROOT` / `MF_PROBE_EXE` / `MF_TUTORIAL_SRC`
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));   // <repo>/tests 或 <repo>/tools
const REPO = path.resolve(HERE, "..");                       // MFMath.UI.Vue
const V2 = path.resolve(REPO, "..", "..");                   // Multifunctional-Mathematics-v2.0

/** 引擎（源码 + 构建产物）根目录 */
export const ENGINE_ROOT = process.env.MF_ENGINE_ROOT
  || path.resolve(V2, "MF_Mathematics");

/** probe_call.exe —— audit-modes / probe-implicit 用它绕过宿主直接调引擎 */
export const PROBE = process.env.MF_PROBE_EXE
  || path.join(ENGINE_ROOT, "build", "bin", "Release",
       process.platform === "win32" ? "probe_call.exe" : "probe_call");

/** v1 教程 YAML 源目录（在另一棵树里，所以给两个候选） */
const TUTORIAL_CANDIDATES = [
  path.resolve(V2, "..", "Multifunctional-Mathematics", "MF_Tutorial", "tutorials"),
  path.resolve(V2, "MF_Tutorial", "tutorials"),
];
export const TUTORIAL_SRC = process.env.MF_TUTORIAL_SRC
  || TUTORIAL_CANDIDATES.find((p) => fs.existsSync(p))
  || TUTORIAL_CANDIDATES[0];

/**
 * 取一个**必需**的树外路径；不存在就说明怎么修，然后退出。
 * @param {string} p 路径
 * @param {string} what 人话描述（出现在错误里）
 * @param {string} envName 可覆盖它的环境变量名
 */
export function requirePath(p, what, envName) {
  if (fs.existsSync(p)) return p;
  console.error(
    `\n找不到${what}：\n  ${p}\n` +
    `它不在本仓库里。请把它指对，例如：\n` +
    `  $env:${envName} = "<正确的路径>"\n` +
    `然后再跑一次（当前环境变量 ${envName} = ${process.env[envName] || "(未设置)"}）。\n`
  );
  process.exit(2);
}
