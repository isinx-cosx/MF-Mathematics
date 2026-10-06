//! hostobject.rs —— **一个通用 COM 宿主对象**，10 个桥共用
//!
//! `AddHostObjectToScript` 要的是一个 `VARIANT(VT_DISPATCH)`，也就是货真价实的 `IDispatch`。
//! 这里手写 7 个 vtable 槽位（IUnknown 3 + IDispatch 4），行为完全可预测。
//!
//! 前端的调用形状保持不变：
//! ```js
//! window.chrome.webview.hostObjects.sync.mf.Dispatch("expr_eval", "{…}")
//! ```
//!
//! ## 为什么还要一份 ITypeInfo（本文件 2026-10-06 的第二个版本）
//!
//! 第一版没有类型信息（`GetTypeInfo` 返回 E_NOTIMPL），实测结果是：
//! ```
//! {"hasSync":true,"hasMf":true}  {"t":"string","err":"mf.Dispatch is not a function"}
//! ```
//! `mf` 可见说明 `GetIDsOfNames` 是通的，但读 `mf.Dispatch` 拿到的是**字符串**：
//! WebView2 的宿主对象代理要靠 `ITypeInfo` 才知道成员是"方法"还是"属性"；没有类型信息时
//! 它按属性处理（发 `DISPATCH_PROPERTYGET`、无参），我们的处理函数返回了"缺少函数名"的错误
//! JSON，于是 `mf.Dispatch` 成了字符串。
//!
//! 所以现在：`GetTypeInfoCount` 返回 1，`GetTypeInfo` 返回一份由 `CreateDispTypeInfo`
//! 从**方法表**造出的 `ITypeInfo`（方法名、参数名与类型、返回类型都在表里）。
//! **只补类型信息，调度仍走本文件的 Invoke** —— 上一版把 `CreateStdDispatch` 也一起换上，
//! 结果宿主直接起不起来（窗口在 `event_loop.run()` 才显示，所以表现为"打不开"），已回退。
//!
//! 生命周期：对象与类型信息都故意 `Box::leak` —— 宿主进程活着，它们就该活着。

// edition 2024 的 `unsafe_op_in_unsafe_fn`：本文件里每个 `unsafe fn` 的函数体**本身就是**
// 不安全操作（裸指针解引用、`VARIANT` 的 union 字段访问、COM 调用），一共 37 处。
// 逐处在函数体里套一层 `unsafe { }` 不会让审阅更容易 —— 它只是把"这个函数整体不安全"
// 这件事重复 37 遍，并给 7 个 vtable 槽位的实现各多套一层缩进（那 7 个函数是全文件最不能
// 改出细枝末节的地方）。所以这里**显式关掉这一条 lint**，而不是假装每处都单独审过。
// 想恢复逐条检查时删掉这一行即可，警告会原样回来。
#![allow(unsafe_op_in_unsafe_fn)]

use std::ffi::c_void;
use std::mem::ManuallyDrop;
use std::sync::atomic::{AtomicU32, Ordering};

use webview2_com::Microsoft::Web::WebView2::Win32::ICoreWebView2;
use windows::core::{BSTR, GUID, HRESULT, Interface, PCWSTR, PWSTR};
use windows::Win32::Foundation::VARIANT_BOOL;
use windows::Win32::System::Com::{
    DISPATCH_METHOD, DISPATCH_PROPERTYGET, DISPATCH_PROPERTYPUT, DISPATCH_PROPERTYPUTREF, DISPPARAMS, EXCEPINFO,
    IDispatch, ITypeInfo, CC_STDCALL,
};
use windows::Win32::System::Ole::{CreateDispTypeInfo, INTERFACEDATA, METHODDATA, PARAMDATA};
use windows::Win32::System::Variant::{VARIANT, VT_BOOL, VT_BSTR, VT_DISPATCH, VT_EMPTY, VT_I4, VT_R8};

use crate::handlers::{self, Arg, Ret};

// ── HRESULT 常量（就地定义，避免到处猜导入路径）──────────────────────────────
const S_OK: HRESULT = HRESULT(0);
const E_NOINTERFACE: HRESULT = HRESULT(0x8000_4002u32 as i32);
const E_INVALIDARG: HRESULT = HRESULT(0x8007_0057u32 as i32);
const E_FAIL: HRESULT = HRESULT(0x8000_4005u32 as i32);
const DISP_E_UNKNOWNNAME: HRESULT = HRESULT(0x8002_0006u32 as i32);
const DISP_E_MEMBERNOTFOUND: HRESULT = HRESULT(0x8002_0003u32 as i32);
const DISP_E_TYPEMISMATCH: HRESULT = HRESULT(0x8002_0005u32 as i32);

const IID_IUNKNOWN: u128 = 0x0000_0000_0000_0000_C000_0000_0000_0046;
const IID_IDISPATCH: u128 = 0x0002_0400_0000_0000_C000_0000_0000_0046;
/// `IProvideClassInfo`（{B196B283-BAB4-101A-B69C-00AA00341D07}）：
/// 同步代理是不是从这里取类型信息，是这个 spike 现在要回答的问题。
const IID_IPROVIDECLASSINFO: u128 = 0xB196_B283_BAB4_101A_B69C_00AA_0034_1D07;

/// 调用追踪（设 `MF_TRACE_DISPATCH=1` 时写 `<exe_dir>\dispatch-trace.log`）。
/// 为什么需要它：S2 的现象（同步代理把成员当属性）可以有多种原因，
/// 唯一可靠的办法是看 WebView2 **实际**问了什么 —— 追 QI 的 IID 与每个 IDispatch 调用。
fn trace(line: &str) {
    if std::env::var_os("MF_TRACE_DISPATCH").is_none() {
        return;
    }
    use std::io::Write;
    let dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()))
        .unwrap_or_else(|| std::path::PathBuf::from("."));
    if let Ok(mut f) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(dir.join("dispatch-trace.log"))
    {
        let _ = writeln!(f, "{line}");
    }
}

fn guid_str(g: &GUID) -> String {
    format!(
        "{{{:08X}-{:04X}-{:04X}-{:02X}{:02X}-{:02X}{:02X}{:02X}{:02X}{:02X}{:02X}}}",
        g.data1, g.data2, g.data3,
        g.data4[0], g.data4[1], g.data4[2], g.data4[3], g.data4[4], g.data4[5], g.data4[6], g.data4[7]
    )
}

/// 返回值类型（目前只用到这三种，用到再加，不预留）
#[derive(Clone, Copy, PartialEq)]
pub enum RetKind {
    Str,
    Bool,
    Empty,
}

/// 一个方法的声明：名字 + 参数名（当前一律 VT_BSTR）+ 返回类型
pub struct MethodSpec {
    pub name: &'static str,
    pub params: &'static [&'static str],
    pub ret: RetKind,
}

#[repr(C)]
struct Vtbl {
    query_interface: unsafe extern "system" fn(*mut c_void, *const GUID, *mut *mut c_void) -> HRESULT,
    add_ref: unsafe extern "system" fn(*mut c_void) -> u32,
    release: unsafe extern "system" fn(*mut c_void) -> u32,
    get_type_info_count: unsafe extern "system" fn(*mut c_void, *mut u32) -> HRESULT,
    get_type_info: unsafe extern "system" fn(*mut c_void, u32, u32, *mut *mut c_void) -> HRESULT,
    get_ids_of_names: unsafe extern "system" fn(
        *mut c_void,
        *const GUID,
        *const *const u16,
        u32,
        u32,
        *mut i32,
    ) -> HRESULT,
    invoke: unsafe extern "system" fn(
        *mut c_void,
        i32,
        *const GUID,
        u32,
        u16,
        *const DISPPARAMS,
        *mut VARIANT,
        *mut EXCEPINFO,
        *mut u32,
    ) -> HRESULT,
}

#[repr(C)]
struct HostObject {
    vtbl: *const Vtbl,
    refs: AtomicU32,
    object: &'static str,
    spec: &'static [MethodSpec],
    type_info: ITypeInfo,
}

static VTBL: Vtbl = Vtbl {
    query_interface: qi,
    add_ref: add_ref,
    release: release,
    get_type_info_count: type_info_count,
    get_type_info: type_info,
    get_ids_of_names: ids_of_names,
    invoke: invoke,
};

// ── IProvideClassInfo（同步代理是否从这里取类型信息，就靠这一版验证）──────────
//
// 为什么怀疑它：异步命名空间（hostObjects.mf，不带 .sync）认得我们的 ITypeInfo ——
// 探针里它给出了 `function () { [native code] }`；而同步命名空间把成员一律当属性取值。
// 两者取类型信息的来源可能不同：一个走 IDispatch::GetTypeInfo，另一个可能走
// IProvideClassInfo::GetClassInfo。这是最便宜的一个假设，先验它。

#[repr(C)]
struct PciVtbl {
    query_interface: unsafe extern "system" fn(*mut c_void, *const GUID, *mut *mut c_void) -> HRESULT,
    add_ref: unsafe extern "system" fn(*mut c_void) -> u32,
    release: unsafe extern "system" fn(*mut c_void) -> u32,
    get_class_info: unsafe extern "system" fn(*mut c_void, *mut *mut c_void) -> HRESULT,
}

#[repr(C)]
struct ProvideClassInfo {
    vtbl: *const PciVtbl,
    host: *const HostObject,
}

static PCI_VTBL: PciVtbl = PciVtbl {
    query_interface: pci_qi,
    add_ref: pci_add_ref,
    release: pci_release,
    get_class_info: pci_get_class_info,
};

unsafe extern "system" fn pci_qi(this: *mut c_void, riid: *const GUID, out: *mut *mut c_void) -> HRESULT {
    if riid.is_null() || out.is_null() {
        return E_INVALIDARG;
    }
    let want = *riid;
    if want == GUID::from_u128(IID_IUNKNOWN) || want == GUID::from_u128(IID_IPROVIDECLASSINFO) {
        *out = this;
        S_OK
    } else {
        *out = std::ptr::null_mut();
        E_NOINTERFACE
    }
}

unsafe extern "system" fn pci_add_ref(_this: *mut c_void) -> u32 {
    2
}
unsafe extern "system" fn pci_release(_this: *mut c_void) -> u32 {
    1
}

unsafe extern "system" fn pci_get_class_info(this: *mut c_void, out: *mut *mut c_void) -> HRESULT {
    if out.is_null() || this.is_null() {
        return E_INVALIDARG;
    }
    let p = &*(this as *const ProvideClassInfo);
    let host = &*p.host;
    trace("IProvideClassInfo::GetClassInfo -> ITypeInfo");
    let ti = host.type_info.clone(); // clone = AddRef
    *out = Interface::as_raw(&ti) as *mut c_void;
    std::mem::forget(ti); // 所有权交给调用方
    S_OK
}

/// 常驻宽字符串指针（`PARAMDATA`/`METHODDATA` 的名字必须一直活着）
fn wname(s: &str) -> PWSTR {
    let v: Vec<u16> = s.encode_utf16().chain(std::iter::once(0)).collect();
    PWSTR(Box::leak(v.into_boxed_slice()).as_mut_ptr())
}

fn vt_of(k: RetKind) -> windows::Win32::System::Variant::VARENUM {
    match k {
        RetKind::Str => VT_BSTR,
        RetKind::Bool => VT_BOOL,
        RetKind::Empty => VT_EMPTY,
    }
}

/// 由方法表造一份 ITypeInfo（WebView2 靠它区分"方法/属性"）
fn build_type_info(spec: &'static [MethodSpec]) -> windows::core::Result<ITypeInfo> {
    let mut methods: Vec<METHODDATA> = Vec::with_capacity(spec.len());
    for (i, m) in spec.iter().enumerate() {
        // 入参列表（返回值不在其中：由 vtReturn + 尾参负责）
        let params: &'static mut [PARAMDATA] = if m.params.is_empty() {
            &mut []
        } else {
            let v: Vec<PARAMDATA> = m
                .params
                .iter()
                .map(|p| PARAMDATA { szName: wname(p), vt: VT_BSTR })
                .collect();
            Box::leak(v.into_boxed_slice())
        };
        methods.push(METHODDATA {
            szName: wname(m.name),
            ppdata: if params.is_empty() { std::ptr::null_mut() } else { params.as_mut_ptr() },
            // dispid 必须与 GetIDsOfNames 给出的编号一致：下标 + 1
            dispid: i as i32 + 1,
            iMeth: i as u32,
            cc: CC_STDCALL,
            cArgs: m.params.len() as u32,
            wFlags: DISPATCH_METHOD.0,
            vtReturn: vt_of(m.ret),
        });
    }
    let methods: &'static mut [METHODDATA] = Box::leak(methods.into_boxed_slice());
    let iface: &'static mut INTERFACEDATA = Box::leak(Box::new(INTERFACEDATA {
        pmethdata: methods.as_mut_ptr(),
        cMembers: methods.len() as u32,
    }));

    let mut ti: Option<ITypeInfo> = None;
    unsafe { CreateDispTypeInfo(iface as *mut INTERFACEDATA, 0 /*LOCALE_NEUTRAL*/, &mut ti)? };
    ti.ok_or_else(|| windows::core::Error::from(E_FAIL))
}

/// 注册一个宿主对象（名字对前端可见，如 `mf`）
pub fn register(
    core: &ICoreWebView2,
    name: &str,
    spec: &'static [MethodSpec],
) -> windows::core::Result<()> {
    let type_info = build_type_info(spec)?;

    let obj: &'static HostObject = Box::leak(Box::new(HostObject {
        vtbl: &VTBL,
        refs: AtomicU32::new(1),
        object: Box::leak(name.to_string().into_boxed_str()),
        spec,
        type_info,
    }));

    let mut var = VARIANT::default();
    unsafe {
        {
            let body: &mut windows::Win32::System::Variant::VARIANT_0_0 =
                &mut *var.Anonymous.Anonymous;
            body.vt = VT_DISPATCH;
            body.Anonymous.pdispVal = ManuallyDrop::new(Some(IDispatch::from_raw(
                obj as *const HostObject as *mut c_void,
            )));
        }
        let name_w: Vec<u16> = name.encode_utf16().chain(std::iter::once(0)).collect();
        core.AddHostObjectToScript(PCWSTR(name_w.as_ptr()), &mut var)?;
    }
    // 不 VariantClear：对象由我们持有到进程结束
    Ok(())
}

// ── IUnknown ────────────────────────────────────────────────────────────────

unsafe extern "system" fn qi(this: *mut c_void, riid: *const GUID, out: *mut *mut c_void) -> HRESULT {
    if riid.is_null() || out.is_null() {
        return E_INVALIDARG;
    }
    let want = *riid;
    if want == GUID::from_u128(IID_IUNKNOWN) || want == GUID::from_u128(IID_IDISPATCH) {
        *out = this;
        add_ref(this);
        trace(&format!("QI {} -> S_OK", guid_str(&want)));
        S_OK
    } else if want == GUID::from_u128(IID_IPROVIDECLASSINFO) {
        // 现造一个（调用很少，泄漏无所谓）：这是同步代理是否用 IProvideClassInfo 的关键证据
        let o = &*(this as *const HostObject);
        let pci: &'static ProvideClassInfo = Box::leak(Box::new(ProvideClassInfo {
            vtbl: &PCI_VTBL,
            host: o as *const HostObject,
        }));
        *out = pci as *const ProvideClassInfo as *mut c_void;
        trace(&format!("QI {} -> S_OK（IProvideClassInfo）", guid_str(&want)));
        S_OK
    } else {
        *out = std::ptr::null_mut();
        trace(&format!("QI {} -> E_NOINTERFACE", guid_str(&want)));
        E_NOINTERFACE
    }
}

unsafe extern "system" fn add_ref(this: *mut c_void) -> u32 {
    let o = &*(this as *const HostObject);
    o.refs.fetch_add(1, Ordering::SeqCst) + 1
}

unsafe extern "system" fn release(this: *mut c_void) -> u32 {
    let o = &*(this as *const HostObject);
    // 故意不真释放：见文件头"生命周期"
    o.refs.fetch_sub(1, Ordering::SeqCst).saturating_sub(1)
}

// ── IDispatch ───────────────────────────────────────────────────────────────

unsafe extern "system" fn type_info_count(this: *mut c_void, out: *mut u32) -> HRESULT {
    if out.is_null() || this.is_null() {
        return E_INVALIDARG;
    }
    *out = 1; // 有类型信息：这是 WebView2 区分"方法/属性"的依据
    S_OK
}

unsafe extern "system" fn type_info(
    this: *mut c_void,
    itinfo: u32,
    _lcid: u32,
    out: *mut *mut c_void,
) -> HRESULT {
    if out.is_null() || this.is_null() {
        return E_INVALIDARG;
    }
    let o = &*(this as *const HostObject);
    if itinfo != 0 {
        *out = std::ptr::null_mut();
        return E_INVALIDARG;
    }
    // 交出一份**已 AddRef** 的引用（clone 就是 AddRef；forget 把所有权让给调用方）
    let ti = o.type_info.clone();
    *out = Interface::as_raw(&ti) as *mut c_void;
    std::mem::forget(ti);
    S_OK
}

unsafe extern "system" fn ids_of_names(
    this: *mut c_void,
    _riid: *const GUID,
    names: *const *const u16,
    count: u32,
    _lcid: u32,
    dispids: *mut i32,
) -> HRESULT {
    if names.is_null() || dispids.is_null() || this.is_null() {
        return E_INVALIDARG;
    }
    let o = &*(this as *const HostObject);
    for i in 0..count as usize {
        let name = wide_to_string(*names.add(i));
        let found = o
            .spec
            .iter()
            .position(|m| m.name.eq_ignore_ascii_case(&name))
            .map(|p| p as i32 + 1) // 与 build_type_info 的 dispid 一致
            .unwrap_or(-1); // DISPID_UNKNOWN
        *dispids.add(i) = found;
        trace(&format!("GetIDsOfNames \"{name}\" -> dispid {found}"));
        if found < 0 {
            return DISP_E_UNKNOWNNAME;
        }
    }
    S_OK
}

unsafe extern "system" fn invoke(
    this: *mut c_void,
    dispid: i32,
    _riid: *const GUID,
    _lcid: u32,
    flags: u16,
    params: *const DISPPARAMS,
    result: *mut VARIANT,
    _excep: *mut EXCEPINFO,
    arg_err: *mut u32,
) -> HRESULT {
    if this.is_null() {
        return E_INVALIDARG;
    }
    let o = &*(this as *const HostObject);
    if dispid <= 0 || dispid as usize > o.spec.len() {
        return DISP_E_MEMBERNOTFOUND;
    }
    let method = o.spec[dispid as usize - 1].name;

    // ── invoke kind 必须校验（这是本 spike 的真正 bug）────────────────────────
    // 我们暴露的成员**全是方法**。按 COM 惯例，拿 PROPERTYGET 去读一个方法成员，
    // 实现方应当返回 DISP_E_MEMBERNOTFOUND，调用方据此判定"这是方法"。
    //
    // 实测（dispatch-trace.log，2026-10-06）：WebView2 的**同步**代理在读成员时发的就是
    // `flags=0x0002`(PROPERTYGET)。我们原先照单全收、把方法当属性算了一遍并返回 S_OK，
    // 于是 `mf.Dispatch` 变成了一个字符串、`mf.Ready` 变成了 `true`，前端 `mf.Ready()` 就炸。
    // 异步命名空间不用这条路（它从 ITypeInfo 枚举成员），所以那边一直是函数。
    let wants_method = flags & DISPATCH_METHOD.0 != 0;
    let wants_prop = flags
        & (DISPATCH_PROPERTYGET.0 | DISPATCH_PROPERTYPUT.0 | DISPATCH_PROPERTYPUTREF.0)
        != 0;
    if !wants_method && wants_prop {
        trace(&format!(
            "Invoke dispid={dispid} method={method} flags=0x{flags:04X} -> DISP_E_MEMBERNOTFOUND（方法是方法，不是属性）"
        ));
        return DISP_E_MEMBERNOTFOUND;
    }

    // DISPPARAMS.rgvarg 是**倒序**的（最后一个实参在 [0]）
    let mut args: Vec<Arg> = Vec::new();
    if !params.is_null() {
        let p = &*params;
        for i in 0..p.cArgs as usize {
            match variant_to_arg(&*p.rgvarg.add(i)) {
                Some(a) => args.push(a),
                None => {
                    if !arg_err.is_null() {
                        *arg_err = i as u32;
                    }
                    return DISP_E_TYPEMISMATCH;
                }
            }
        }
        args.reverse();
    }

    let ret = handlers::call(o.object, method, &args);
    trace(&format!(
        "Invoke dispid={dispid} method={method} flags=0x{flags:04X} cArgs={} -> 执行",
        args.len()
    ));
    if !result.is_null() {
        write_result(result, ret);
    }
    S_OK
}

// ── VARIANT 编解码 ──────────────────────────────────────────────────────────

unsafe fn variant_to_arg(v: &VARIANT) -> Option<Arg> {
    let body = &*v.Anonymous.Anonymous;
    match body.vt {
        VT_BSTR => {
            let b: &ManuallyDrop<BSTR> = &body.Anonymous.bstrVal;
            Some(Arg::Str(b.to_string()))
        }
        VT_I4 => Some(Arg::Num(body.Anonymous.lVal as f64)),
        VT_R8 => Some(Arg::Num(body.Anonymous.dblVal)),
        VT_BOOL => Some(Arg::Bool(body.Anonymous.boolVal.0 != 0)),
        VT_EMPTY => Some(Arg::None),
        _ => None,
    }
}

unsafe fn write_result(p: *mut VARIANT, r: Ret) {
    let body: &mut windows::Win32::System::Variant::VARIANT_0_0 = &mut *(*p).Anonymous.Anonymous;
    match r {
        Ret::Str(s) => {
            body.vt = VT_BSTR;
            body.Anonymous.bstrVal = ManuallyDrop::new(BSTR::from(&s));
        }
        Ret::Bool(b) => {
            body.vt = VT_BOOL;
            // VARIANT_BOOL 是 i16 的新类型：TRUE = -1，FALSE = 0
            body.Anonymous.boolVal = VARIANT_BOOL(if b { -1 } else { 0 });
        }
        Ret::Empty => {
            body.vt = VT_EMPTY;
        }
    }
}

fn wide_to_string(p: *const u16) -> String {
    if p.is_null() {
        return String::new();
    }
    let mut len = 0usize;
    unsafe {
        while *p.add(len) != 0 {
            len += 1;
        }
        String::from_utf16_lossy(std::slice::from_raw_parts(p, len))
    }
}
