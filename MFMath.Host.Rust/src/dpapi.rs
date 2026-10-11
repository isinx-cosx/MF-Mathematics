//! dpapi.rs —— 密钥保护的**唯一实现**（AI 的 API Key、搜索的 Wolfram App ID、账号 token 共用）
//!
//! 对照 已移除的 C# 宿主的 Dpapi.cs 逐条实现。**必须逐字兼容**：迁移期两个宿主共用同一份
//! 设置文件（`%LOCALAPPDATA%\MFMath\settings`），C# 写的 `ai.json` 要能被 Rust 解开、
//! 反之亦然 —— 所以下面每一处细节都不是随便选的。
//!
//! 三条纪律（C# 注释里的原话，一条不少）：
//!   ① **只在当前用户下可解**（不传 `CRYPTPROTECT_LOCAL_MACHINE`）；
//!   ② **禁止弹 UI**（`CRYPTPROTECT_UI_FORBIDDEN`）：加解密不能因为系统状态弹窗，
//!      失败就如实报告失败；
//!   ③ **失败绝不降级成明文落盘** —— 调用方在 `protect` 返回 None 时只把密钥留在内存里，
//!      并明确告诉用户"本次会话有效、重启后需要重填"。
//!
//! ⚠ **不传 optional entropy**（C# 传的是 `IntPtr.Zero`）。熵一变，同机同用户的密文就
//! 互相解不开 —— 而"两个宿主共用设置文件"正是迁移期的主要用法。
//!
//! ⚠ 密文是 **base64 的 DPAPI blob**（不是 hex、不是裸字节）：`ai.json` 里
//! `apiKeyProtected` 字段存的就是它。

use base64::engine::general_purpose::STANDARD as B64;
use base64::Engine;
use windows::core::PCWSTR;
use windows::Win32::Foundation::{HLOCAL, LocalFree};
use windows::Win32::Security::Cryptography::{
    CRYPT_INTEGER_BLOB, CRYPTPROTECT_UI_FORBIDDEN, CryptProtectData, CryptUnprotectData,
};

/// 描述串：只是 blob 里的元数据，**不参与解密**；与 C# 保持一致便于排查
const DESCR: &str = "MFMath secret";

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

fn blob_of(data: &[u8]) -> CRYPT_INTEGER_BLOB {
    CRYPT_INTEGER_BLOB { cbData: data.len() as u32, pbData: data.as_ptr() as *mut u8 }
}

/// 把 API 写回来的 blob 拷成 Vec（随后由调用方 LocalFree）
unsafe fn take_out(b: &CRYPT_INTEGER_BLOB) -> Vec<u8> {
    if b.pbData.is_null() || b.cbData == 0 {
        return Vec::new();
    }
    // SAFETY: API 保证 pbData 指向 cbData 字节的 LocalAlloc 内存
    unsafe { std::slice::from_raw_parts(b.pbData, b.cbData as usize).to_vec() }
}

unsafe fn free_out(b: &CRYPT_INTEGER_BLOB) {
    if !b.pbData.is_null() {
        // SAFETY: 这块内存由 CryptProtectData/CryptUnprotectData 用 LocalAlloc 分配
        unsafe {
            let _ = LocalFree(Some(HLOCAL(b.pbData as *mut core::ffi::c_void)));
        }
    }
}

/// 加密成 base64。失败返回 None（**调用方绝不能因此改成明文存储**）。
pub fn protect(plain: &str) -> Option<String> {
    if plain.is_empty() {
        return None;
    }
    let descr = wide(DESCR);
    let mut input = plain.as_bytes().to_vec();
    let data_in = blob_of(&input);
    let mut data_out = CRYPT_INTEGER_BLOB::default();

    // SAFETY: 入参是两个本函数栈上的 blob；entropy/reserved/prompt 都是 None（与 C# 一致）
    let r = unsafe {
        CryptProtectData(
            &data_in,
            PCWSTR(descr.as_ptr()),
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            &mut data_out,
        )
    };
    let out = match r {
        // SAFETY: 调用成功时 data_out 已填好
        Ok(()) => Some(B64.encode(unsafe { take_out(&data_out) })),
        Err(_) => None,
    };
    // SAFETY: 释放 API 分配的输出；明文缓冲先擦再丢（与 C# 的 finally 一致）
    unsafe {
        free_out(&data_out);
    }
    input.iter_mut().for_each(|b| *b = 0);
    out
}

/// 解密。失败返回 None（换了用户、文件被改、系统策略禁止都会走到这里）。
pub fn unprotect(b64: &str) -> Option<String> {
    let cipher = B64.decode(b64.trim()).ok()?;
    if cipher.is_empty() {
        return None;
    }
    let data_in = blob_of(&cipher);
    let mut data_out = CRYPT_INTEGER_BLOB::default();

    // SAFETY: 同上；`ppszDataDescr` 传 None（我们不要那个描述串）
    let r = unsafe {
        CryptUnprotectData(
            &data_in,
            None,
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            &mut data_out,
        )
    };
    let mut bytes = match r {
        // SAFETY: 调用成功时 data_out 已填好
        Ok(()) => unsafe { take_out(&data_out) },
        Err(_) => Vec::new(),
    };
    // SAFETY: 释放 API 分配的输出
    unsafe {
        free_out(&data_out);
    }
    let text = String::from_utf8(bytes.clone()).ok();
    // 明文缓冲擦掉再返回（String 自己那份没法擦，但至少不留第二份）
    bytes.iter_mut().for_each(|b| *b = 0);
    text
}

/// DPAPI 在这台机器上到底能不能用（设置面板要如实告诉用户密钥是怎么存的）
pub fn selftest() -> bool {
    const PROBE: &str = "mfmath-dpapi-probe";
    match protect(PROBE) {
        Some(blob) => unprotect(&blob).as_deref() == Some(PROBE),
        None => false,
    }
}
