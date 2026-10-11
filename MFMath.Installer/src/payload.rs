//! 载荷：从自身尾部取出内嵌归档，或读取旁置归档；解压并生成清单。

use std::io::{Read, Seek, Write};
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
            "找不到载荷。\n\
             这是安装器的编译产物，本身不含载荷，只有 --pack 产出的单文件安装包才能直接安装。\n\
             要产出安装包：.\\MFMath.Installer\\tools\\build-setup.ps1\n\
             （安装器在同目录查找的旁置归档是 payload.zip，位置：{}）",
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

    /// 归档里的文件条目（相对路径，已校验安全），不含元信息条目。
    pub fn entry_names(&self) -> Result<Vec<String>> {
        let mut zip = zip::ZipArchive::new(self.reader()?)?;
        let mut names = Vec::new();
        for i in 0..zip.len() {
            let entry = zip.by_index(i)?;
            if entry.is_dir() {
                continue;
            }
            let raw = entry.name().to_string();
            if raw == META_ENTRY || raw == crate::webview2::BOOTSTRAPPER_ENTRY {
                continue;
            }
            names.push(safe_relative_path(&raw)?.to_string_lossy().replace('\\', "/"));
        }
        Ok(names)
    }

    /// 把归档里的**单个**条目释放到指定文件。条目不存在时返回 `Ok(false)`。
    ///
    /// 用于那些不该进安装目录的附属程序（例如 WebView2 引导程序）。
    pub fn extract_entry(&self, name: &str, dest: &Path) -> Result<bool> {
        let mut zip = zip::ZipArchive::new(self.reader()?)?;
        let mut entry = match zip.by_name(name) {
            Ok(e) => e,
            Err(_) => return Ok(false),
        };
        if let Some(parent) = dest.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let mut f = std::fs::File::create(dest)?;
        std::io::copy(&mut entry, &mut f)?;
        Ok(true)
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
            if raw == META_ENTRY || raw == crate::webview2::BOOTSTRAPPER_ENTRY {
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

/// 在缓冲里查找**最后一处**尾部标记，返回 `(载荷起点, 载荷长度)`。
///
/// 不能只看文件末尾：Authenticode 签名会把证书表追加到文件末尾，正好落在
/// 标记之后。从后往前扫可以穿过证书表找到标记，签名与未签名两种情况都能用。
fn find_trailer(data: &[u8]) -> Option<(usize, u64)> {
    let magic_len = MAGIC.len();
    let len_bytes = LEN_BYTES as usize;
    if data.len() < magic_len + len_bytes {
        return None;
    }
    let mut idx = data.len() - magic_len;
    loop {
        if &data[idx..idx + magic_len] == MAGIC {
            let len_start = idx.checked_sub(len_bytes)?;
            let len = u64::from_le_bytes(data[len_start..idx].try_into().ok()?);
            if len > 0 {
                if let Some(start) = len_start.checked_sub(len as usize) {
                    return Some((start, len));
                }
            }
        }
        if idx == 0 {
            return None;
        }
        idx -= 1;
    }
}

/// 读自身的内嵌载荷。没有标记时返回 `None`。
fn read_embedded(exe: &Path) -> Result<Option<Vec<u8>>> {
    let data = std::fs::read(exe)?;
    match find_trailer(&data) {
        Some((start, len)) => Ok(Some(data[start..start + len as usize].to_vec())),
        None => Ok(None),
    }
}

/// 把归档追加到安装器副本的尾部，产出单文件安装器。
pub fn build_self_extracting(installer: &Path, archive: &[u8], out: &Path) -> Result<()> {
    let mut data = std::fs::read(installer)?;
    // 若安装器自身已带载荷（重复打包），先把旧的载荷与标记截掉。
    if let Some((start, _)) = find_trailer(&data) {
        data.truncate(start);
    }
    data.extend_from_slice(archive);
    data.extend_from_slice(&(archive.len() as u64).to_le_bytes());
    data.extend_from_slice(MAGIC);
    let mut f = std::fs::File::create(out)?;
    f.write_all(&data)?;
    f.sync_all()?;
    Ok(())
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
///
/// `owned` 只列出**本产品释放的文件**（归档条目名 + 安装时新增的文件）。
/// 不能扫描整个目录：`--dir` 可以指向任何位置，那里可能有本产品以外的文件
/// （v1 就装在 `%LOCALAPPDATA%\Programs\MF-Mathematics\`，含主程序与卸载器），
/// 把它们写进清单会导致卸载时被一并删除。
pub fn build_manifest(
    dir: &Path,
    meta: &Meta,
    installed_at: &str,
    owned: &[String],
) -> Result<Manifest> {
    let mut files = Vec::new();
    for rel in owned {
        let path = dir.join(rel.replace('/', "\\"));
        if !path.is_file() {
            continue;
        }
        files.push(ManifestFile {
            path: rel.clone(),
            bytes: std::fs::metadata(&path)?.len(),
            sha256: util::sha256_file(&path)?,
        });
    }
    files.sort_by(|a, b| a.path.cmp(&b.path));
    files.dedup_by(|a, b| a.path == b.path);
    Ok(Manifest {
        product: meta.product.clone(),
        version: meta.version.clone(),
        installed_at: installed_at.to_string(),
        install_dir: dir.to_string_lossy().to_string(),
        main_exe: util::MAIN_EXE_NAME.to_string(),
        files,
    })
}
