// build.rs —— Tauri 的构建脚本，外加**把宿主运行需要的东西放到 exe 同目录**。
//
// 三件事：
//   1. 读 tauri.conf.json、生成上下文（`tauri::generate_context!` 依赖它）、在 Windows 上
//      写入应用的资源与清单。**没有它 Tauri 编译不过**。
//   2. **引擎产物**（`mf_mathematics.dll` + 5 个运行时依赖）→ exe 同目录。
//      `src/engine.rs` 按"宿主 exe 同目录"找它（与 C# 的 `AppContext.BaseDirectory` 同义）；
//      C# 宿主靠 csproj 的相对路径把 6 个 DLL 带进输出目录，Rust 这边**原来没有任何机制** ——
//      少了它界面照常打开、启动自检却会写「引擎未加载：找不到数学引擎…」，一次都算不了。
//   3. **前端产物**（`MF_UI/MFMath.UI.Vue/dist`）→ `<exe 同目录>/wwwroot`。
//      有它才走 `https://mfmath.local/`（与 C# 宿主同一份、47 个 CDP 用例的取页正则也认这个）；
//      没有就退回 Tauri 内嵌资产，页面变成 `http://tauri.localhost/`，用例会当场找不到页面。
//
// 两条原则：
//   · **缺了就只警告，不让构建失败** —— 干净机器上可能还没构建引擎/前端，
//     这时 `cargo build` 仍应给出一个能编译、能起窗口（但算不了数）的宿主；
//   · **只在新的时候拷** —— 22 MB 的 DLL 每次构建都拷一遍太浪费。
//
// 图标：用 Tauri 的标准布局 `icons/icon.ico`（tauri-build 的默认查找路径）。
// 该文件是从项目 v1 的 `Multifunctional-Mathematics/assets/icon.ico` **原样复制**过来的，
// 逐字节相同、不做任何加工；换品牌图标时替换这一个文件即可。

use std::path::{Path, PathBuf};
use std::time::SystemTime;

/// 引擎主 DLL 与 5 个运行时依赖（顺序与 `src/sys.rs` 的 `ENGINE_DEPS` 一致）
const ENGINE_DLLS: [&str; 6] = [
    "mf_mathematics.dll",
    "symengine-0.14.dll",
    "flint-24.dll",
    "gmp-10.dll",
    "mpfr-6.dll",
    "pthreadVC3.dll",
];

fn main() {
    let default_icon = Path::new("icons/icon.ico");
    if !default_icon.exists() {
        println!(
            "cargo:warning=缺少 {}（tauri-build 在 Windows 上必须有 .ico），请从 assets/icon.ico 复制一份",
            default_icon.display()
        );
    }

    sync_runtime_assets();

    tauri_build::build()
}

/// exe 所在目录 = `OUT_DIR` 往上三级
/// （`<target>/<profile>/build/<pkg>-<hash>/out` → `<target>/<profile>`）
fn profile_dir() -> Option<PathBuf> {
    let out = std::env::var_os("OUT_DIR")?;
    Path::new(&out).ancestors().nth(3).map(|p| p.to_path_buf())
}

fn mtime(p: &Path) -> Option<SystemTime> {
    std::fs::metadata(p).and_then(|m| m.modified()).ok()
}

/// 目标比源新（或源不存在时间戳）就不重复拷
fn needs_copy(src: &Path, dst: &Path) -> bool {
    match (mtime(src), mtime(dst)) {
        (Some(s), Some(d)) => s > d,
        (Some(_), None) => true,
        _ => false,
    }
}

fn copy_if_newer(src: &Path, dst: &Path) -> std::io::Result<()> {
    if !needs_copy(src, dst) {
        return Ok(());
    }
    std::fs::copy(src, dst)?;
    Ok(())
}

fn sync_runtime_assets() {
    let Some(profile) = profile_dir() else {
        println!("cargo:warning=取不到 exe 输出目录（OUT_DIR 结构变了？），跳过引擎/UI 同步");
        return;
    };
    // 一次解析成 owned 值：下面三处同步都用它，别再 Option 化（否则 clone/unwrap 很容易搬错）
    let root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_default();

    /* ── 引擎 DLL ───────────────────────────────────────────────────────── */
    let engine_src = std::env::var_os("MF_ENGINE_BIN")
        .map(PathBuf::from)
        .unwrap_or_else(|| root.join("MF_Mathematics/build/bin/Release"));
    if engine_src.join(ENGINE_DLLS[0]).is_file() {
        let mut copied = 0;
        for dll in ENGINE_DLLS {
            match copy_if_newer(&engine_src.join(dll), &profile.join(dll)) {
                Ok(()) => copied += 1,
                Err(e) => println!("cargo:warning=拷贝 {dll} 失败：{e}"),
            }
        }
        if copied > 0 {
            println!("cargo:warning=引擎产物已同步到 {}（{copied} 个文件）", profile.display());
        }
    } else {
        println!(
            "cargo:warning=找不到引擎产物 {}（先 cmake 构建，或设 MF_ENGINE_BIN）—— 宿主能起来但算不了数",
            engine_src.join(ENGINE_DLLS[0]).display()
        );
    }
    println!("cargo:rerun-if-env-changed=MF_ENGINE_BIN");
    println!("cargo:rerun-if-changed={}", engine_src.display());

    /* ── 前端 wwwroot ───────────────────────────────────────────────────── */
    let dist = root.join("MF_UI/MFMath.UI.Vue/dist");
    if dist.join("index.html").is_file() {
        let wwwroot = profile.join("wwwroot");
        if let Err(e) = copy_tree(&dist, &wwwroot, "前端（wwwroot）") {
            println!("cargo:warning=同步 wwwroot 失败：{e}");
        }
    } else {
        println!(
            "cargo:warning=找不到前端产物 {}（先 npm run build）—— 页面会退回内嵌资产、URL 变成 tauri.localhost",
            dist.display()
        );
    }
    println!("cargo:rerun-if-changed={}", dist.display());

    /* ── 控制台门面（python/ 与 cpp/）──────────────────────────────────────
     * 组件安装时要把它们拷进组件目录（见 `src/con.rs`）：
     *   · Python 侧靠 `mfmath.py`（ctypes → mf_mathematics.dll）；
     *   · C++ 侧靠 `mfmath.hpp` + `mfmath_autorun.hpp`（`#include` 起引擎）。
     * 少了它们，控制台能起、组件却装不上（报"应用目录缺少 python\mfmath.py"）。
     *
     * ⚠ 来源是 **C# 宿主项目目录**：这三个文件在仓库里只有那一份，两个宿主共用，
     * 它们本身就是"用户代码怎么调到引擎"的对外契约 —— 要改就两边一起想。
     */
    for (src_rel, dst_rel) in [("MFMath.Host/python", "python"), ("MFMath.Host/cpp", "cpp")] {
        let src = root.join(src_rel);
        if src.is_dir() {
            if let Err(e) = copy_tree(&src, &profile.join(dst_rel), &format!("控制台门面（{dst_rel}/）")) {
                println!("cargo:warning=同步 {dst_rel}/ 失败：{e}");
            }
        } else {
            println!(
                "cargo:warning=找不到控制台门面 {}（控制台能起，但组件安装会失败）",
                src.display()
            );
        }
        println!("cargo:rerun-if-changed={}", src.display());
    }
}

/// 把 dist 整棵树镜像到 wwwroot（删掉目标里多出来的文件，避免旧版本残留）
fn copy_tree(src: &Path, dst: &Path, label: &str) -> std::io::Result<()> {
    let mut copied = 0usize;
    let mut stack = vec![(src.to_path_buf(), dst.to_path_buf())];
    while let Some((s, d)) = stack.pop() {
        std::fs::create_dir_all(&d)?;
        for entry in std::fs::read_dir(&s)? {
            let entry = entry?;
            let name = entry.file_name();
            let (sp, dp) = (entry.path(), d.join(&name));
            if entry.file_type()?.is_dir() {
                stack.push((sp, dp));
            } else {
                if needs_copy(&sp, &dp) {
                    std::fs::copy(&sp, &dp)?;
                    copied += 1;
                }
            }
        }
    }
    if copied > 0 {
        println!("cargo:warning={label} 已同步（{copied} 个文件）");
    }
    Ok(())
}
