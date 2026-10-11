//! 打包：把载荷目录压成归档，追加到安装器副本尾部，产出单文件安装器。

use std::io::Write;
use std::path::Path;

use anyhow::{bail, Context, Result};
use zip::write::SimpleFileOptions;
use zip::CompressionMethod;

use crate::payload::{self, Meta};
use crate::util;

/// 产出单文件安装器。
pub fn run(payload_dir: &Path, out: &Path, version: &str) -> Result<()> {
    if !payload_dir.is_dir() {
        bail!("载荷目录不存在：{}", payload_dir.display());
    }
    let installer = util::current_exe()?;
    let archive = build_archive(payload_dir, version)?;
    payload::build_self_extracting(&installer, &archive, out)?;

    let mb = |n: u64| n as f64 / 1024.0 / 1024.0;
    util::say(&format!(
        "载荷目录：{}（未压缩 {:.2} MB）",
        payload_dir.display(),
        mb(util::dir_size(payload_dir))
    ));
    util::say(&format!("压缩后：{:.2} MB", mb(archive.len() as u64)));
    util::say(&format!("产出：{}", out.display()));
    Ok(())
}

/// 把载荷目录打成 zip（条目路径全部是相对根目录的前斜杠形式）。
fn build_archive(payload_dir: &Path, version: &str) -> Result<Vec<u8>> {
    let meta = Meta {
        product: util::PRODUCT_NAME.to_string(),
        version: version.to_string(),
    };
    let options = SimpleFileOptions::default().compression_method(CompressionMethod::Deflated);

    let mut cursor = std::io::Cursor::new(Vec::new());
    {
        let mut zw = zip::ZipWriter::new(&mut cursor);

        zw.start_file(payload::META_ENTRY, options)?;
        zw.write_all(serde_json::to_string_pretty(&meta)?.as_bytes())?;

        for entry in walkdir::WalkDir::new(payload_dir)
            .into_iter()
            .filter_map(Result::ok)
        {
            if !entry.file_type().is_file() {
                continue;
            }
            let path = entry.path();
            let name = path.file_name().and_then(|s| s.to_str()).unwrap_or("");
            // 清单由安装时生成，目录里若有旧的不要带进包。
            if name == util::MANIFEST_NAME || name == payload::META_ENTRY {
                continue;
            }
            let rel = path
                .strip_prefix(payload_dir)
                .with_context(|| format!("路径不在载荷目录内：{}", path.display()))?
                .to_string_lossy()
                .replace('\\', "/");
            zw.start_file(rel, options)?;
            zw.write_all(&std::fs::read(path)?)?;
        }
        zw.finish().context("收尾归档失败")?;
    }
    Ok(cursor.into_inner())
}
