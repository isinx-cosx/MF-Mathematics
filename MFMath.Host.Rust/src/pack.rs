//! pack.rs —— 校验与解包（`con` 的组件下载、`update` 的 sha256 都用它）
//!
//! 两件事，都是"下下来必须能验、能安全解开"的那一类：
//!   · `sha256_*`：组件包与安装包的完整性；
//!   · `unzip_*`：组件包（zip）解包到目标目录 —— **自带路径穿越防护**。
//!
//! ⚠ 解包是最容易出安全问题的一步：zip 里的条目名可以写成 `..\..\Windows\System32\x.dll`
//! 或绝对路径。这里逐个条目校验"解出来的绝对路径必须仍在目标目录内"，否则整包拒绝，
//! 与 C# `ComponentDownload` 的取舍一致（宁可拒绝，不要半解）。

use std::io::{Cursor, Read, Write};
use std::path::{Component, Path, PathBuf};

use sha2::{Digest, Sha256};

/// `sha256(文件)` → 小写十六进制
pub fn sha256_file(path: &Path) -> std::io::Result<String> {
    let mut f = std::fs::File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buf = vec![0u8; 1 << 20];
    loop {
        let n = f.read(&mut buf)?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    Ok(hex(&hasher.finalize()))
}

/// `sha256(bytes)` → 小写十六进制
pub fn sha256_bytes(data: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data);
    hex(&hasher.finalize())
}

fn hex(d: &[u8]) -> String {
    let mut s = String::with_capacity(d.len() * 2);
    for b in d {
        s.push_str(&format!("{b:02x}"));
    }
    s
}

/// 大小写不敏感地比较两个 sha256（站点给的可能是大写）
pub fn sha256_eq(a: &str, b: &str) -> bool {
    a.trim().eq_ignore_ascii_case(b.trim())
}

/// 目标路径是否安全地落在 `root` 之内（防 `..` 与绝对路径穿越）
fn safe_join(root: &Path, name: &str) -> Option<PathBuf> {
    let name_path = Path::new(name);
    // 绝对路径、盘符、父目录引用一律拒绝
    if name_path.is_absolute() {
        return None;
    }
    let mut out = root.to_path_buf();
    for c in name_path.components() {
        match c {
            Component::Normal(seg) => out.push(seg),
            Component::CurDir => {}
            // ParentDir / RootDir / Prefix 全部拒绝
            _ => return None,
        }
    }
    Some(out)
}

/// 把一个内存里的 zip 解到 `dest`（目录不存在会建）。
/// 返回解出的文件数；**任何一条不安全就整包失败**，不做部分解包。
pub fn unzip_to(zip_bytes: &[u8], dest: &Path) -> Result<usize, String> {
    let reader = zip::ZipArchive::new(Cursor::new(zip_bytes)).map_err(|e| format!("zip 打开失败：{e}"))?;
    // 先把条目名全部过一遍校验，确认没有穿越再落盘（避免解一半才发现）
    let mut planned: Vec<(String, bool)> = Vec::with_capacity(reader.len());
    for i in 0..reader.len() {
        let name = reader
            .name_for_index(i)
            .ok_or_else(|| format!("zip 第 {i} 个条目没有名字"))?
            .to_string();
        let is_dir = name.ends_with('/') || name.ends_with('\\');
        if safe_join(dest, name.trim_end_matches(['/', '\\'])).is_none() {
            return Err(format!("zip 条目路径不安全，拒绝整包：{name}"));
        }
        planned.push((name, is_dir));
    }

    std::fs::create_dir_all(dest).map_err(|e| format!("建目录失败：{e}"))?;
    let mut reader = zip::ZipArchive::new(Cursor::new(zip_bytes)).map_err(|e| format!("zip 打开失败：{e}"))?;
    let mut files = 0usize;
    for i in 0..reader.len() {
        let (name, is_dir) = planned[i].clone();
        let clean = name.trim_end_matches(['/', '\\']).to_string();
        let Some(target) = safe_join(dest, &clean) else {
            return Err(format!("zip 条目路径不安全：{name}"));
        };
        if is_dir {
            std::fs::create_dir_all(&target).map_err(|e| format!("建目录失败：{e}"))?;
            continue;
        }
        if let Some(parent) = target.parent() {
            std::fs::create_dir_all(parent).map_err(|e| format!("建目录失败：{e}"))?;
        }
        let mut entry = reader.by_index(i).map_err(|e| format!("读条目失败：{e}"))?;
        let mut out = std::fs::File::create(&target).map_err(|e| format!("写文件失败：{e}"))?;
        std::io::copy(&mut entry, &mut out).map_err(|e| format!("写文件失败：{e}"))?;
        files += 1;
    }
    Ok(files)
}

/// 把一个目录打成 zip（**只给自检/诊断用** —— 产品里没有"打包"的需求）
pub fn zip_dir(src: &Path) -> Result<Vec<u8>, String> {
    let mut buf = Vec::new();
    {
        let mut zw = zip::ZipWriter::new(Cursor::new(&mut buf));
        let opts: zip::write::FileOptions<'_, ()> =
            zip::write::FileOptions::default().compression_method(zip::CompressionMethod::Deflated);
        let mut stack = vec![src.to_path_buf()];
        while let Some(dir) = stack.pop() {
            let entries = std::fs::read_dir(&dir).map_err(|e| format!("读目录失败：{e}"))?;
            for e in entries {
                let e = e.map_err(|x| format!("读目录失败：{x}"))?;
                let p = e.path();
                if p.is_dir() {
                    stack.push(p);
                    continue;
                }
                let rel = p
                    .strip_prefix(src)
                    .map_err(|_| "路径不在源目录内".to_string())?
                    .to_string_lossy()
                    .replace('\\', "/");
                zw.start_file(rel, opts).map_err(|e| format!("写 zip 失败：{e}"))?;
                let data = std::fs::read(&p).map_err(|e| format!("读文件失败：{e}"))?;
                zw.write_all(&data).map_err(|e| format!("写 zip 失败：{e}"))?;
            }
        }
        zw.finish().map_err(|e| format!("收尾 zip 失败：{e}"))?;
    }
    Ok(buf)
}
