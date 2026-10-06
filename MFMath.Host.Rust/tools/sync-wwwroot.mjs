/**
 * sync-wwwroot.mjs —— 把前端构建产物拷成宿主的 `wwwroot`（**两个宿主共用同一份**）
 *
 * 为什么需要它：
 *   Tauri 的 `frontendDist` 会把界面**嵌进 exe**，于是页面 URL 变成 `http://tauri.localhost/`，
 *   而 47 个 CDP 用例、C# 宿主、以及"改了前端只要重拷 dist"这条工作流全都以
 *   `https://mfmath.local/` 为准（C# `MainWindow.xaml.cs:187-192` 就是这么做的）。
 *   所以 Rust 宿主也读**磁盘上的** wwwroot：改了界面 `npm run build` + 本脚本即可，
 *   不必重编 Rust（那是几分钟 vs 几秒的区别）。
 *
 * 用法：
 *   node tools/sync-wwwroot.mjs                      # → target/debug/wwwroot
 *   node tools/sync-wwwroot.mjs --profile release    # → target/release/wwwroot
 *   node tools/sync-wwwroot.mjs --dest "D:\somewhere\wwwroot"
 *   node tools/sync-wwwroot.mjs --exe "path\to\exe"  # 拷到该 exe 同目录的 wwwroot
 */
import { cp, mkdir, rm, stat } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const hostDir = resolve(here, "..");
const repoRoot = resolve(hostDir, "..");
const distDir = join(repoRoot, "MF_UI", "MFMath.UI.Vue", "dist");

function argOf(name) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : null;
}

let dest;
const exe = argOf("--exe");
if (exe) {
  dest = join(dirname(resolve(exe)), "wwwroot");
} else if (argOf("--dest")) {
  dest = resolve(argOf("--dest"));
} else {
  dest = join(hostDir, "target", argOf("--profile") || "debug", "wwwroot");
}

// 源必须在：没有 dist 就先跑 npm run build（别让宿主静默退回内嵌资产）
try {
  await stat(join(distDir, "index.html"));
} catch {
  console.error(`[sync-wwwroot] 找不到 ${join(distDir, "index.html")}`);
  console.error(`[sync-wwwroot] 先构建前端： npm run build --prefix "${join(repoRoot, "MF_UI", "MFMath.UI.Vue")}"`);
  process.exit(1);
}

/* ── 护栏：目标看起来是"exe 目录"就拒绝 ─────────────────────────────────────
 * 下面第 50 行会**先删掉整个目标目录**再拷。而 `--dest` 的语义是"wwwroot 目录本身"，
 * 与 `sync-engine.mjs --dest`（"exe 所在的目录"）**不是一回事** ——
 * 把同一个目录传给两个脚本，第二个就会把前一个刚拷进去的引擎 DLL（乃至宿主 exe）一起删光。
 * 这个坑我自己踩过一次（冒烟测试里就是这么写的），代价是整份部署目录被清空。
 * 所以：目标里只要看得到宿主 exe，就明确拒绝并告诉用户该指到哪儿。 */
for (const exeName of ["mfmath-host-rust.exe", "MFMath.exe"]) {
  try {
    await stat(join(dest, exeName));
    console.error(`[sync-wwwroot] 拒绝：${dest} 里放着 ${exeName}，看起来是**宿主 exe 目录**。`);
    console.error(`[sync-wwwroot] 本脚本的 --dest 是「wwwroot 目录本身」，而且会先清空它 ——`);
    console.error(`[sync-wwwroot] 指错地方会把引擎 DLL 和宿主 exe 一起删掉。请改成：`);
    console.error(`[sync-wwwroot]   node tools/sync-wwwroot.mjs --exe "<exe 的完整路径>"`);
    console.error(`[sync-wwwroot] 或明确指到子目录： --dest "<exe 目录>\\wwwroot"`);
    process.exit(1);
  } catch { /* 没有 exe 就正常继续 */ }
}

await rm(dest, { recursive: true, force: true });
await mkdir(dirname(dest), { recursive: true });
await cp(distDir, dest, { recursive: true });

let files = 0;
let bytes = 0;
const walk = async (dir) => {
  const { readdir } = await import("node:fs/promises");
  for (const e of await readdir(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) await walk(p);
    else {
      files += 1;
      bytes += (await stat(p)).size;
    }
  }
};
await walk(dest);

console.log(`[sync-wwwroot] ${distDir}`);
console.log(`[sync-wwwroot]   → ${dest}   (${files} 个文件, ${(bytes / 1024 / 1024).toFixed(2)} MB)`);
console.log(`[sync-wwwroot] 宿主会把它映射成 https://mfmath.local/index.html`);
