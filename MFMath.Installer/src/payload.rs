//! 载荷：从自身尾部取出内嵌归档，或读取旁置归档；解压并生成清单。

use std::io::{Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};

use crate::util;

/// `ZipArchive` 要求可读**且**可定位，用这个别名把两种来源统一起来。
trait ReadSeek: Read + Seek {}
impl<T: Read + Seek> ReadSeek for T {}

/// 尾部标记，长度固定 16 字节。改这个值等于换载荷格式，新旧安装器互不兼容。
pub const MAGIC: &[u8; 16] = b"MFMATH-INSTALLER";
/// 尾部长度的字节数（u64 小端）。
const LEN_BYTES: u64 = 8;
/// 尾部总长 = 长度字段 + 标记。
pub const TRAILER_LEN: u64 = LEN_BYTES + MAGIC.len() as u64;

/// 归档内记录载荷元信息的文件名。安装时不会被释放到安装目录。
pub const META_ENTRY: &str = "payload-meta.json";

/// 载荷元信息，打包时写入归档，安装时读取。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Meta {
    pub product: String,
    pub version: String,
}

/// 载荷来源。
pub enum Payload {
    /// 内嵌在自身尾部。
    Embedded(Vec<u8>),
    /// 与本程序同目录的旁置归档。
    Sidecar(PathBuf),
}

impl Payload {
    /// 定位载荷：先找自身尾部标记，再找同目录的 `payload.zip`。
    pub fn locate(exe: &Path) -> Result<Self> {
        if let Some(bytes) = read_embedded(exe)? {
            return Ok(Payload::Embedded(bytes));
        }
        let sidecar = exe
            .parent()
            .unwrap_or_else(|| Path::new("."))
            .join("payload.zip");
        if sidecar.is_file() {
            return Ok(Payload::Sidecar(sidecar));
        }
        bail!(
            "找不到载荷。安装器尾部没有内嵌归档，同目录也没有 payload.zip（查找位置：{}）",
            sidecar.display()
        )
    }

    /// 打开为可读可定位的流。
    fn reader(&self) -> Result<Box<dyn ReadSeek + '_>> {
        Ok(match self {
            Payload::Embedded(bytes) => Box::new(std::io::Cursor::new(bytes.as_slice())),
            Payload::Sidecar(path) => Box::new(std::fs::File::open(path)?),
        })
    }

    /// 读取归档里的元信息。
    pub fn meta(&self) -> Result<Meta> {
        let mut zip = zip::ZipArchive::new(self.reader()?)?;
        let mut entry = zip
            .by_name(META_ENTRY)
            .with_context(|| format!("载荷缺少 {META_ENTRY}"))?;
        let mut text = String::new();
        entry.read_to_string(&mut text)?;
        Ok(serde_json::from_str(&text)?)
    }

    /// 把归档释放到目标目录。返回写入的文件数。
    ///
    /// 归档内的路径全部相对于安装目录；带 `..`、绝对路径或盘符的条目一律拒绝。
    pub fn extract_into(&self, dest: &Path) -> Result<usize> {
        std::fs::create_dir_all(dest)?;
        let mut zip = zip::ZipArchive::new(self.reader()?)?;
        let mut written = 0usize;
        for i in 0..zip.len() {
            let mut entry = zip.by_index(i)?;
            let raw = entry.name().to_string();
            if raw == META_ENTRY {
                continue;
            }
            let rel = safe_relative_path(&raw)
                .with_context(|| format!("归档条目路径不安全，已拒绝：{raw}"))?;
            let out = dest.join(&rel);
            if entry.is_dir() {
                std::fs::create_dir_all(&out)?;
                continue;
            }
            if let Some(parent) = out.parent() {
                std::fs::create_dir_all(parent)?;
            }
            let mut f = std::fs::File::create(&out)?;
            std::io::copy(&mut entry, &mut f)?;
            written += 1;
        }
        Ok(written)
    }
}

/// 校验归档条目路径，返回可安全拼接的相对路径。
fn safe_relative_path(raw: &str) -> Result<PathBuf> {
    let normalized = raw.replace('\\', "/");
    if normalized.starts_with('/') {
        bail!("绝对路径");
    }
    let mut out = PathBuf::new();
    for part in normalized.split('/') {
        match part {
            "" | "." => continue,
            ".." => bail!("包含上级引用"),
            // 盘符形式（C:）与 NTFS 备用数据流（name:stream）
            p if p.contains(':') => bail!("包含冒号"),
            p => out.push(p),
        }
    }
    if out.as_os_str().is_empty() {
        bail!("空路径");
    }
    Ok(out)
}

/// 读自身尾部的内嵌载荷。没有标记时返回 `None`。
fn read_embedded(exe: &Path) -> Result<Option<Vec<u8>>> {
    let mut f = std::fs::File::open(exe)?;
    let total = f.metadata()?.len();
    if total <= TRAILER_LEN {
        return Ok(None);
    }
    f.seek(SeekFrom::End(-(TRAILER_LEN as i64)))?;
    let mut trailer = [0u8; TRAILER_LEN as usize];
    f.read_exact(&mut trailer)?;
    let (len_part, magic_part) = trailer.split_at(LEN_BYTES as usize);
    if magic_part != MAGIC {
        return Ok(None);
    }
    let payload_len = u64::from_le_bytes(len_part.try_into().unwrap());
    if payload_len == 0 || payload_len + TRAILER_LEN > total {
        bail!("自身尾部的载荷长度不可信（声明 {payload_len} 字节，文件共 {total} 字节）");
    }
    let offset = total - TRAILER_LEN - payload_len;
    f.seek(SeekFrom::Start(offset))?;
    let mut buf = vec![0u8; payload_len as usize];
    f.read_exact(&mut buf)?;
    Ok(Some(buf))
}

/// 把归档追加到安装器副本的尾部，产出单文件安装器。
pub fn build_self_extracting(installer: &Path, archive: &[u8], out: &Path) -> Result<()> {
    let mut data = std::fs::read(installer)?;
    // 若安装器自身已带载荷（重复打包），先截掉旧的尾部与归档。
    if let Some(existing) = embedded_len(&data)? {
        data.truncate(data.len() - (existing + TRAILER_LEN) as usize);
    }
    data.extend_from_slice(archive);
    data.extend_from_slice(&(archive.len() as u64).to_le_bytes());
    data.extend_from_slice(MAGIC);
    let mut f = std::fs::File::create(out)?;
    f.write_all(&data)?;
    f.sync_all()?;
    Ok(())
}

/// 从字节缓冲里读内嵌载荷长度。
fn embedded_len(data: &[u8]) -> Result<Option<u64>> {
    if (data.len() as u64) <= TRAILER_LEN {
        return Ok(None);
    }
    let tail = &data[data.len() - TRAILER_LEN as usize..];
    let (len_part, magic_part) = tail.split_at(LEN_BYTES as usize);
    if magic_part != MAGIC {
        return Ok(None);
    }
    Ok(Some(u64::from_le_bytes(len_part.try_into().unwrap())))
}

/// 安装清单，写入安装目录，供更新链与自检使用。
#[derive(Debug, Serialize, Deserialize)]
pub struct Manifest {
    pub product: String,
    pub version: String,
    pub installed_at: String,
    pub install_dir: String,
    pub main_exe: String,
    pub files: Vec<ManifestFile>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ManifestFile {
    pub path: String,
    pub bytes: u64,
    pub sha256: String,
}

/// 扫描安装目录生成清单。
pub fn build_manifest(dir: &Path, meta: &Meta, installed_at: &str) -> Result<Manifest> {
    let mut files = Vec::new();
    for entry in walkdir::WalkDir::new(dir).into_iter().filter_map(Result::ok) {
        if !entry.file_type().is_file() {
            continue;
        }
        let path = entry.path();
        let name = path.file_name().and_then(|s| s.to_str()).unwrap_or("");
        // 卸载器与清单本身不进清单：它们随安装而变化。
        if name == util::UNINSTALL_EXE_NAME || name == util::MANIFEST_NAME {
            continue;
        }
        let rel = path
            .strip_prefix(dir)
            .unwrap_or(path)
            .to_string_lossy()
            .replace('\\', "/");
        files.push(ManifestFile {
            path: rel,
            bytes: entry.metadata()?.len(),
            sha256: util::sha256_file(path)?,
        });
    }
    files.sort_by(|a, b| a.path.cmp(&b.path));
    Ok(Manifest {
        product: meta.product.clone(),
        version: meta.version.clone(),
        installed_at: installed_at.to_string(),
        install_dir: dir.to_string_lossy().to_string(),
        main_exe: util::MAIN_EXE_NAME.to_string(),
        files,
    })
}
