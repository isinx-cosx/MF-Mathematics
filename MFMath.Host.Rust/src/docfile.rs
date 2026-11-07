//! docfile.rs — 工作区文档的 zip 容器读写。
//!
//! 容器形状（.mfws，将来课件复用同一套）：
//!
//! ```text
//! xxx.mfws
//! ├── document.json     内容与信封，deflate
//! └── assets/…          图片/音视频，原样存储（媒体本就压过，再 deflate 白费 CPU）
//! ```
//!
//! 三条与安全相关的硬约束，都在这里执行：
//!
//! 1. **先看中央目录再解**：条目数、各自声明大小、总解压量都要先校验，
//!    防止「声明 1 KB、实际 4 GB」这类 zip 炸弹；
//! 2. **条目名白名单**：只允许 `[A-Za-z0-9._/-]`，禁 `..`、禁绝对路径、禁反斜杠，
//!    防止解压时穿越到容器外；
//! 3. **上限写死**：单件 64 MiB、总计 256 MiB、条目 512、document.json 4 MiB。
//!
//! 另外兼容旧格式：早先的工作区是**纯 JSON**（`.mfws.json`，没有 zip 外壳）。
//! 打开时按首字节判断，纯 JSON 直接原样返回，前端只需认一种返回形状。

use std::io::{Read, Write};
use std::path::{Path, PathBuf};

use serde_json::json;

use crate::winbridge::pick_target;

/// 容器里正文的文件名（固定，不随扩展名变）
const DOC_ENTRY: &str = "document.json";
/// 资产目录前缀
const ASSET_PREFIX: &str = "assets/";

/// 条目数上限（防炸弹的一环，也防"一个目录被整包塞进来"）
const MAX_ENTRIES: usize = 512;
/// 单个资产上限
const MAX_ASSET_BYTES: u64 = 64 * 1024 * 1024;
/// 资产总计上限
const MAX_TOTAL_ASSET_BYTES: u64 = 256 * 1024 * 1024;
/// 正文上限（与前端 4 MiB 一致）
const MAX_DOC_BYTES: u64 = 4 * 1024 * 1024;

/// 已知媒体后缀：这些原样存储，不再 deflate。
fn is_media(name: &str) -> bool {
    let lower = name.to_ascii_lowercase();
    const EXT: [&str; 12] = [
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg",
        ".mp4", ".webm", ".mp3", ".wav", ".m4a",
    ];
    EXT.iter().any(|e| lower.ends_with(e))
}

/// 条目名是否安全。只允许相对路径、白名单字符、无 `..` 段。
fn safe_entry_name(name: &str) -> bool {
    if name.is_empty() || name.len() > 200 {
        return false;
    }
    if name.starts_with('/') || name.contains('\\') || name.contains(':') {
        return false;
    }
    if !name
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-' | '/'))
    {
        return false;
    }
    // 任何一段是 `..` 就拒绝
    name.split('/').all(|seg| !seg.is_empty() && seg != "." && seg != "..")
}

/// 保存文档。
///
/// `document` 是正文 JSON 文本；`assets` 是 `[{"name","base64"}]` 的 JSON 文本，
/// 工作区用不上（传空数组即可），课件放图片/音视频时用。
///
/// 返回 `{ok,path,bytes}` / `{canceled:true}` / `{ok:false,error}`。
pub fn save_doc_file(
    title: &str,
    default_name: &str,
    filter: &str,
    document: &str,
    assets: &str,
    path: &str,
) -> String {
    if document.is_empty() {
        return json!({ "ok": false, "error": "工作区内容为空，未保存" }).to_string();
    }
    if document.len() as u64 > MAX_DOC_BYTES {
        return json!({
            "ok": false,
            "error": format!(
                "工作区内容 {} KiB，超过上限 {} KiB，请减少计算块或控制台代码",
                document.len() / 1024,
                MAX_DOC_BYTES / 1024
            )
        })
        .to_string();
    }

    // 先把资产解析并校验完，再弹对话框 —— 免得用户选完路径才发现内容不合法
    let items = match decode_assets(assets) {
        Ok(v) => v,
        Err(e) => return json!({ "ok": false, "error": e }).to_string(),
    };

    let target = match pick_target(title, default_name, filter, path, true) {
        Ok(Some(p)) => p,
        Ok(None) => return json!({ "canceled": true }).to_string(),
        Err(e) => return json!({ "ok": false, "error": e }).to_string(),
    };
    if let Some(dir) = Path::new(&target).parent() {
        if !dir.as_os_str().is_empty() {
            let _ = std::fs::create_dir_all(dir);
        }
    }

    match write_container(&target, document, &items) {
        Ok(bytes) => json!({ "ok": true, "path": target, "bytes": bytes }).to_string(),
        Err(e) => json!({ "ok": false, "error": e }).to_string(),
    }
}

/// 打开文档。兼容旧的纯 JSON 工作区，返回形状一致。
///
/// 返回 `{ok,path,document,assetRoot,assets:[{name,bytes}]}` / `{canceled:true}` / `{ok:false,error}`。
pub fn open_doc_file(title: &str, filter: &str, path: &str) -> String {
    let target = match pick_target(title, "", filter, path, false) {
        Ok(Some(p)) => p,
        Ok(None) => return json!({ "canceled": true }).to_string(),
        Err(e) => return json!({ "ok": false, "error": e }).to_string(),
    };
    let p = Path::new(&target);
    if !p.is_file() {
        return json!({ "ok": false, "error": format!("文件不存在：{target}") }).to_string();
    }
    // 上限按"文件本身"先拦一道（解压后还有更细的校验）
    if let Ok(md) = std::fs::metadata(p) {
        if md.len() > MAX_TOTAL_ASSET_BYTES + MAX_DOC_BYTES {
            return json!({
                "ok": false,
                "error": format!("文件过大（{} MB），拒绝打开", md.len() / 1024 / 1024)
            })
            .to_string();
        }
    }

    match read_container(p) {
        Ok((document, assets, asset_root)) => json!({
            "ok": true,
            "path": target,
            "document": document,
            "assetRoot": asset_root,
            "assets": assets,
        })
        .to_string(),
        Err(e) => json!({ "ok": false, "error": e }).to_string(),
    }
}

/* ── 内部实现 ───────────────────────────────────────────────────────── */

struct Asset {
    name: String,
    bytes: Vec<u8>,
}

/// 解析 `[{"name","base64"}]`，逐条校验名字与大小。
fn decode_assets(text: &str) -> Result<Vec<Asset>, String> {
    let t = text.trim();
    if t.is_empty() || t == "[]" {
        return Ok(Vec::new());
    }
    let arr: serde_json::Value =
        serde_json::from_str(t).map_err(|e| format!("资产清单不是合法 JSON：{e}"))?;
    let list = arr.as_array().ok_or("资产清单必须是数组")?;
    if list.len() + 2 > MAX_ENTRIES {
        return Err(format!("资产数量 {} 超过上限 {}", list.len(), MAX_ENTRIES - 2));
    }
    let mut out = Vec::with_capacity(list.len());
    let mut total: u64 = 0;
    for (i, item) in list.iter().enumerate() {
        let raw_name = item.get("name").and_then(|v| v.as_str()).unwrap_or("");
        let name = raw_name.trim_start_matches('/').to_string();
        if !safe_entry_name(&name) {
            return Err(format!("第 {} 个资产的名字不合法：{raw_name}", i + 1));
        }
        let b64 = item.get("base64").and_then(|v| v.as_str()).unwrap_or("");
        let bytes = super::winbridge::base64_decode(b64)
            .map_err(|e| format!("第 {} 个资产解码失败：{e}", i + 1))?;
        let n = bytes.len() as u64;
        if n > MAX_ASSET_BYTES {
            return Err(format!(
                "资产「{name}」{} MB，超过单件上限 {} MB",
                n / 1024 / 1024,
                MAX_ASSET_BYTES / 1024 / 1024
            ));
        }
        total = total.saturating_add(n);
        if total > MAX_TOTAL_ASSET_BYTES {
            return Err(format!(
                "资产合计 {} MB，超过上限 {} MB",
                total / 1024 / 1024,
                MAX_TOTAL_ASSET_BYTES / 1024 / 1024
            ));
        }
        out.push(Asset { name, bytes });
    }
    Ok(out)
}

fn write_container(target: &str, document: &str, assets: &[Asset]) -> Result<u64, String> {
    use zip::write::SimpleFileOptions;
    use zip::CompressionMethod;

    let file = std::fs::File::create(target).map_err(|e| format!("创建文件失败：{e}"))?;
    let mut zip = zip::ZipWriter::new(file);

    let doc_opts = SimpleFileOptions::default()
        .compression_method(CompressionMethod::Deflated)
        .unix_permissions(0o644);
    zip.start_file(DOC_ENTRY, doc_opts)
        .map_err(|e| format!("写入正文失败：{e}"))?;
    zip.write_all(document.as_bytes())
        .map_err(|e| format!("写入正文失败：{e}"))?;

    for a in assets {
        let method = if is_media(&a.name) {
            CompressionMethod::Stored
        } else {
            CompressionMethod::Deflated
        };
        let opts = SimpleFileOptions::default()
            .compression_method(method)
            .unix_permissions(0o644);
        let entry = format!("{ASSET_PREFIX}{}", a.name.trim_start_matches(ASSET_PREFIX));
        zip.start_file(entry, opts)
            .map_err(|e| format!("写入资产失败：{e}"))?;
        zip.write_all(&a.bytes)
            .map_err(|e| format!("写入资产失败：{e}"))?;
    }

    zip.finish().map_err(|e| format!("收尾失败：{e}"))?;
    std::fs::metadata(target)
        .map(|m| m.len())
        .map_err(|e| format!("读取文件大小失败：{e}"))
}

/// 读容器。返回 `(document, 资产清单, 资产解压目录)`。
fn read_container(p: &Path) -> Result<(String, serde_json::Value, String), String> {
    // 先看是不是纯 JSON（旧格式）。zip 以 `PK\x03\x04` 开头，JSON 以 `{` 开头。
    let mut head = [0u8; 4];
    {
        let mut f = std::fs::File::open(p).map_err(|e| format!("打开失败：{e}"))?;
        let n = f.read(&mut head).map_err(|e| format!("读取失败：{e}"))?;
        if n >= 2 && head[0] == b'{' {
            drop(f);
            let text = std::fs::read_to_string(p).map_err(|e| format!("读取失败：{e}"))?;
            if text.len() as u64 > MAX_DOC_TOTAL_FOR_JSON {
                return Err("旧格式工作区超过 4 MiB，拒绝打开".to_string());
            }
            return Ok((text, json!([]), String::new()));
        }
    }
    if head != [0x50, 0x4B, 0x03, 0x04] {
        return Err("不是工作区文件（既不是 zip 容器，也不是旧版 JSON）".to_string());
    }

    let file = std::fs::File::open(p).map_err(|e| format!("打开失败：{e}"))?;
    let mut zip = zip::ZipArchive::new(file).map_err(|e| format!("不是合法的 zip 容器：{e}"))?;

    // ① 先做整体校验：条目数、名字合法性、声明大小之和
    let count = zip.len();
    if count > MAX_ENTRIES {
        return Err(format!("容器内有 {count} 个条目，超过上限 {MAX_ENTRIES}"));
    }
    let mut declared_total: u64 = 0;
    let mut has_doc = false;
    for i in 0..count {
        let f = zip
            .by_index_raw(i)
            .map_err(|e| format!("读取容器目录失败：{e}"))?;
        let name = f.name().to_string();
        let size = f.size();
        if name == DOC_ENTRY {
            has_doc = true;
            if size > MAX_DOC_BYTES {
                return Err(format!("正文声明 {} MB，超过上限 4 MB", size / 1024 / 1024));
            }
            continue;
        }
        let rel = name.strip_prefix(ASSET_PREFIX).unwrap_or("");
        if rel.is_empty() || !safe_entry_name(rel) {
            return Err(format!("容器里有不安全的条目名：{name}"));
        }
        if size > MAX_ASSET_BYTES {
            return Err(format!(
                "资产「{rel}」声明 {} MB，超过单件上限 {} MB",
                size / 1024 / 1024,
                MAX_ASSET_BYTES / 1024 / 1024
            ));
        }
        declared_total = declared_total.saturating_add(size);
        if declared_total > MAX_TOTAL_ASSET_BYTES {
            return Err(format!(
                "资产合计超过上限 {} MB，拒绝打开",
                MAX_TOTAL_ASSET_BYTES / 1024 / 1024
            ));
        }
    }
    if !has_doc {
        return Err(format!("容器里没有 {DOC_ENTRY}，不是本应用的文档"));
    }

    // ② 读正文
    let document = {
        let mut f = zip
            .by_name(DOC_ENTRY)
            .map_err(|e| format!("读取正文失败：{e}"))?;
        let mut buf = String::new();
        f.read_to_string(&mut buf)
            .map_err(|e| format!("正文不是合法 UTF-8：{e}"))?;
        buf
    };
    if !document.trim_start().starts_with('{') {
        return Err("正文不是 JSON 对象".to_string());
    }

    // ③ 有资产才解压到临时目录（工作区通常没有资产，不创建任何目录）
    let mut assets = Vec::new();
    let mut asset_root = String::new();
    if declared_total > 0 {
        let root = doc_temp_dir()?;
        std::fs::create_dir_all(&root).map_err(|e| format!("建临时目录失败：{e}"))?;
        for i in 0..zip.len() {
            let mut f = zip
                .by_index(i)
                .map_err(|e| format!("读取资产失败：{e}"))?;
            let name = f.name().to_string();
            let Some(rel) = name.strip_prefix(ASSET_PREFIX) else {
                continue;
            };
            if rel.is_empty() || !safe_entry_name(rel) {
                continue;
            }
            let dest = root.join(rel.replace('/', std::path::MAIN_SEPARATOR_STR));
            if let Some(dir) = dest.parent() {
                std::fs::create_dir_all(dir).map_err(|e| format!("建目录失败：{e}"))?;
            }
            let mut out = std::fs::File::create(&dest).map_err(|e| format!("写资产失败：{e}"))?;
            let mut written: u64 = 0;
            let mut chunk = [0u8; 64 * 1024];
            loop {
                let n = f.read(&mut chunk).map_err(|e| format!("解压失败：{e}"))?;
                if n == 0 {
                    break;
                }
                written += n as u64;
                // 声明与实际不符（zip 炸弹）就中止
                if written > MAX_ASSET_BYTES {
                    let _ = std::fs::remove_file(&dest);
                    return Err(format!("资产「{rel}」实际大小超过上限，已中止"));
                }
                out.write_all(&chunk[..n])
                    .map_err(|e| format!("写资产失败：{e}"))?;
            }
            assets.push(json!({ "name": rel, "bytes": written }));
        }
        asset_root = root.to_string_lossy().to_string();
    }

    Ok((document, json!(assets), asset_root))
}

/// 旧格式（纯 JSON）正文的上限。用常量避免和资产上限混用。
const MAX_DOC_TOTAL_FOR_JSON: u64 = MAX_DOC_BYTES;

/// 每次打开文档给一个独立目录，进程退出后由系统清理。
fn doc_temp_dir() -> Result<PathBuf, String> {
    use std::sync::atomic::{AtomicU32, Ordering};
    static SEQ: AtomicU32 = AtomicU32::new(0);
    let n = SEQ.fetch_add(1, Ordering::Relaxed);
    let mut dir = std::env::temp_dir();
    dir.push(format!("mfmath-doc-{}-{n}", std::process::id()));
    Ok(dir)
}
