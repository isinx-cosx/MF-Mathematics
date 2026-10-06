/**
 * sync-engine.mjs —— 把引擎产物拷到宿主 exe 同目录（**C# 宿主靠 csproj 做的事，这里得自己做**）
 *
 * 为什么要它：`engine.rs` 按"宿主 exe 同目录"找 `mf_mathematics.dll`（与 C# 的
 * `AppContext.BaseDirectory` 同义）。C# 宿主的 csproj 用相对路径把 6 个 DLL 带进输出目录，
 * Rust 宿主此前**没有任何机制** —— 少了它就只会在启动自检里看到
 * 「引擎未加载：找不到数学引擎 …」，界面照常打开、但一次都算不了。
 *
 * 用法：
 *   node tools/sync-engine.mjs                      # → target/debug（默认）
 *   node tools/sync-engine.mjs --profile release    # → target/release
 *   node tools/sync-engine.mjs --dest "<某目录>"     # → 指定目录（例如工作区外的运行目录）
 *   node tools/sync-engine.mjs --exe "<宿主 exe>"   # → 该 exe 同目录
 *
 * 源目录可用 `MF_ENGINE_BIN` 覆盖，默认 `../MF_Mathematics/build/bin/Release`。
 */
import { copyFile, mkdir, stat } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

/** 引擎主 DLL 与 5 个运行时依赖（顺序与 `sys::ENGINE_DEPS` 一致） */
const DLLS = [
  "mf_mathematics.dll",
  "symengine-0.14.dll",
  "flint-24.dll",
  "gmp-10.dll",
  "mpfr-6.dll",
  "pthreadVC3.dll",
];

const here = dirname(fileURLToPath(import.meta.url));
const hostDir = resolve(here, "..");
const repoRoot = resolve(hostDir, "..");
const srcDir = process.env.MF_ENGINE_BIN
  ? resolve(process.env.MF_ENGINE_BIN)
  : join(repoRoot, "MF_Mathematics", "build", "bin", "Release");

function argOf(name) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : null;
}

let dest;
const exe = argOf("--exe");
if (exe) dest = dirname(resolve(exe));
else if (argOf("--dest")) dest = resolve(argOf("--dest"));
else dest = join(hostDir, "target", argOf("--profile") || "debug");

try {
  await stat(join(srcDir, DLLS[0]));
} catch {
  console.error(`[sync-engine] 找不到 ${join(srcDir, DLLS[0])}`);
  console.error(`[sync-engine] 先构建引擎：`);
  console.error(`  cmake -S "${join(repoRoot, "MF_Mathematics")}" -B "${join(repoRoot, "MF_Mathematics", "build")}" -A x64`);
  console.error(`  cmake --build "${join(repoRoot, "MF_Mathematics", "build")}" --config Release --target mf_mathematics`);
  process.exit(1);
}

await mkdir(dest, { recursive: true });
let bytes = 0;
for (const d of DLLS) {
  const from = join(srcDir, d);
  try {
    await copyFile(from, join(dest, d));
    bytes += (await stat(from)).size;
    console.log(`[sync-engine]   ${d}`);
  } catch (e) {
    console.error(`[sync-engine]   ${d} 失败：${e.message}`);
    process.exitCode = 1;
  }
}
console.log(`[sync-engine] ${srcDir}`);
console.log(`[sync-engine]   → ${dest}   (${DLLS.length} 个 DLL, ${(bytes / 1024 / 1024).toFixed(1)} MB)`);
