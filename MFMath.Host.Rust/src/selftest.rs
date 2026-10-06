//! selftest.rs —— 共享件（DPAPI / sha256 / zip / HTTP 环境）的**无头自检**
//!
//! 为什么要单独一个自检：这些是 `search`/`account`/`update`/`ai`/`con` 的地基，
//! 而它们各自的端到端用例都要起假服务器、都要走一遍完整业务；地基坏了却只有一个
//! 远端的现象（"登录失败""更新检查失败"），很难一眼看出是哪一层。
//! 这里用 `--selftest-common` 把它钉死，**不需要 WebView2**（受限环境里也能跑）。
//!
//! 其中最要紧的一条是 **DPAPI 的跨实现互操作**：
//! 迁移期 C# 宿主与 Rust 宿主**共用同一份设置文件**，C# 写的 `ai.json` 里的密文，
//! Rust 必须解得开、反之亦然。本自检把这条做成可外部验证的形状 ——
//!   · 它打印 `BLOB|<base64>`，外部脚本（PowerShell 的 CryptUnprotectData）解它并比对；
//!   · 它接受 `--unprotect <base64>`，解开外部产出的密文并比对。
//! 两边都过，才说明"同一台机器、同一个用户下的密文互通"。

use std::path::PathBuf;

use crate::{dpapi, http, pack};

/// 打印一行结果并累计成败（与 `--selftest-jobs` 的格式一致，便于脚本抓 `RESULT|`）
fn line(ok: bool, name: &str, detail: &str, pass: &mut u32, fail: &mut u32) {
    if ok {
        *pass += 1
    } else {
        *fail += 1
    }
    println!("{} {:<34} {}", if ok { "[PASS]" } else { "[FAIL]" }, name, detail);
}

pub fn run(external_blob: Option<&str>) -> ! {
    let mut pass = 0u32;
    let mut fail = 0u32;

    println!("── DPAPI ──");
    let rt = dpapi::selftest();
    line(rt, "加密→解密往返", "protect/unprotect", &mut pass, &mut fail);

    // 给外部验证用的密文（PowerShell 侧用 CryptUnprotectData 解它应得到 probe 串）
    const PROBE: &str = "mfmath-dpapi-probe";
    match dpapi::protect(PROBE) {
        Some(blob) => {
            line(true, "产出可外验的密文", &format!("BLOB 长度 {}", blob.len()), &mut pass, &mut fail);
            println!("BLOB|{blob}");
        }
        None => line(false, "产出可外验的密文", "protect 返回 None", &mut pass, &mut fail),
    }

    if let Some(b64) = external_blob {
        match dpapi::unprotect(b64) {
            Some(v) if v == PROBE => line(true, "解开外部（C#/PS）产出的密文", "内容一致", &mut pass, &mut fail),
            Some(v) => line(
                false,
                "解开外部（C#/PS）产出的密文",
                &format!("解开了但内容不符（长度 {}）", v.len()),
                &mut pass,
                &mut fail,
            ),
            None => line(false, "解开外部（C#/PS）产出的密文", "解不开（熵/用户/格式不一致？）", &mut pass, &mut fail),
        }
    }

    println!("\n── sha256 ──");
    // 公开测试向量：sha256("abc")
    let want = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
    let got = pack::sha256_bytes(b"abc");
    line(got == want, "sha256(\"abc\") 对齐标准向量", &got, &mut pass, &mut fail);
    line(
        pack::sha256_eq(want, &want.to_uppercase()),
        "大小写不敏感比较（站点可能给大写）",
        "",
        &mut pass,
        &mut fail,
    );

    println!("\n── zip ──");
    let root = crate::logging::data_dir().join("selftest-tmp");
    let _ = std::fs::remove_dir_all(&root);
    let src = root.join("src");
    let dst = root.join("dst");
    let mk = || -> std::io::Result<()> {
        std::fs::create_dir_all(src.join("sub"))?;
        std::fs::write(src.join("a.txt"), b"hello")?;
        std::fs::write(src.join("sub/b.bin"), [0u8, 1, 2, 255])?;
        Ok(())
    };
    match mk().and_then(|_| pack::zip_dir(&src).map_err(std::io::Error::other)) {
        Ok(bytes) => {
            let n = pack::unzip_to(&bytes, &dst).unwrap_or(0);
            let a = std::fs::read(dst.join("a.txt")).unwrap_or_default();
            let b = std::fs::read(dst.join("sub/b.bin")).unwrap_or_default();
            line(
                n == 2 && a == b"hello" && b == [0u8, 1, 2, 255],
                "打包→解包往返（含子目录与二进制）",
                &format!("{n} 个文件, 共 {} 字节", bytes.len()),
                &mut pass,
                &mut fail,
            );
        }
        Err(e) => line(false, "打包→解包往返（含子目录与二进制）", &e.to_string(), &mut pass, &mut fail),
    }
    // 恶意条目：必须在**落盘之前**被整包拒绝
    let mut evil = Vec::new();
    {
        use std::io::Write;
        let mut zw = zip::ZipWriter::new(std::io::Cursor::new(&mut evil));
        let opts: zip::write::FileOptions<'_, ()> = zip::write::FileOptions::default();
        if zw.start_file("../evil.txt", opts).is_ok() {
            let _ = zw.write_all(b"pwned");
        }
        let _ = zw.finish();
    }
    let evil_dst = root.join("evil");
    let rejected = pack::unzip_to(&evil, &evil_dst).is_err();
    let untouched = !evil_dst.join("evil.txt").exists() && !root.join("evil.txt").exists();
    line(
        rejected && untouched,
        "拒绝路径穿越（../evil.txt）",
        if rejected { "已拒绝" } else { "**没拒绝**" },
        &mut pass,
        &mut fail,
    );

    println!("\n── HTTP 环境 ──");
    let proxy = http::describe_system_proxy();
    line(!proxy.is_empty(), "读到系统代理设置", &proxy, &mut pass, &mut fail);
    line(
        http::origin_of("https://example.com/a/b?q=1") == "https://example.com",
        "origin_of 不泄漏路径与查询串",
        &http::origin_of("https://example.com/a/b?q=1"),
        &mut pass,
        &mut fail,
    );
    line(
        http::is_loopback("http://127.0.0.1:1234/x") && !http::is_loopback("https://example.com"),
        "回环判定",
        "",
        &mut pass,
        &mut fail,
    );
    // 真正发一次请求：只打回环，且**失败不算错**（沙箱可能拦出站，见 http.rs 文件头）
    http::ensure_crypto();
    match http::client(5).get("http://127.0.0.1:9/").send() {
        Ok(_) => line(true, "HTTP 客户端可用（回环）", "连上了", &mut pass, &mut fail),
        Err(e) => {
            // 连接被拒也是"客户端工作正常"的证据：说明请求真的发出去了
            let ok = e.is_connect() || e.is_timeout() || e.is_request();
            line(ok, "HTTP 客户端可用（回环）", &format!("（预期内的失败类型）{e}"), &mut pass, &mut fail)
        }
    }

    let _ = std::fs::remove_dir_all(&root);
    let _: PathBuf = root;
    println!("\nRESULT|selftest-common|{pass}|{fail}");
    std::process::exit(if fail == 0 { 0 } else { 1 });
}
