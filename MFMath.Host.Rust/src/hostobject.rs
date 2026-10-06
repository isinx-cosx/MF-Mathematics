//! hostobject.rs —— **一个通用 COM 宿主对象**，10 个桥共用
//!
//! 为什么手写 vtable 而不用 `#[implement]`：
//!   `AddHostObjectToScript` 要的是一个 `VARIANT(VT_DISPATCH)`，也就是一个货真价实的
//!   `IDispatch`。手写 vtable 只有 7 个槽位（IUnknown 3 + IDispatch 4），全部逻辑都在
//!   这个文件里，行为完全可预测 —— 不依赖宏对 IDispatch 这种"泛型接口"的支持程度。
//!
//! 前端的调用形状保持不变：
//! ```js
//! window.chrome.webview.hostObjects.sync.mf.Dispatch("expr_eval", "{…}")
//! ```
//! 名字解析走 `GetIDsOfNames`（dispid = 方法名在 `methods` 里的下标 + 1），
//! 调用走 `Invoke`，返回值按 `Ret` 装成 `VARIANT`。
//!
//! ⚠ 已知缺口（实测，见 2026-10-06 的 spike 记录）：
//!   这一版**没有类型信息**（`GetTypeInfo` 如实返回 E_NOTIMPL），于是 WebView2 的宿主对象
//!   代理把成员一律当"属性"：读 `mf.Dispatch` 会发一次 `PROPERTYGET`（无参），拿到我们
//!   返回的错误 JSON 字符串，所以 `typeof mf.Dispatch === "string"`，调用时报
//!   "mf.Dispatch is not a function"。修法是给 `GetTypeInfo` 真返回一个 `ITypeInfo`
//!   （可由 `CreateDispTypeInfo` 从方法表造出），而不是换成 `CreateStdDispatch` 整套
//!   —— 后者实测会让宿主起不来。
//!
//! 生命周期：对象故意 `Box::leak` —— 宿主进程活着，宿主对象就该活着；
//! 这也省掉了"WebView2 何时释放我们"这个没法验证的问题。

use std::ffi::c_void;
use std::mem::ManuallyDrop;
use std::sync::atomic::{AtomicU32, Ordering};

use webview2_com::Microsoft::Web::WebView2::Win32::ICoreWebView2;
use windows::core::{BSTR, GUID, HRESULT, Interface, PCWSTR};
use windows::Win32::Foundation::VARIANT_BOOL;
use windows::Win32::System::Com::{IDispatch, DISPPARAMS, EXCEPINFO};
use windows::Win32::System::Variant::{VARIANT, VT_BOOL, VT_BSTR, VT_DISPATCH, VT_EMPTY, VT_I4, VT_R8};

use crate::handlers::{self, Arg, Ret};

// ── HRESULT 常量（就地定义，避免到处猜导入路径）──────────────────────────────
const S_OK: HRESULT = HRESULT(0);
const E_NOTIMPL: HRESULT = HRESULT(0x8000_4001u32 as i32);
const E_NOINTERFACE: HRESULT = HRESULT(0x8000_4002u32 as i32);
const E_INVALIDARG: HRESULT = HRESULT(0x8007_0057u32 as i32);
const DISP_E_UNKNOWNNAME: HRESULT = HRESULT(0x8002_0006u32 as i32);
const DISP_E_MEMBERNOTFOUND: HRESULT = HRESULT(0x8002_0003u32 as i32);
const DISP_E_TYPEMISMATCH: HRESULT = HRESULT(0x8002_0005u32 as i32);

const IID_IUNKNOWN: u128 = 0x0000_0000_0000_0000_C000_0000_0000_0046;
const IID_IDISPATCH: u128 = 0x0002_0400_0000_0000_C000_0000_0000_0046;

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
    methods: &'static [&'static str],
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

/// 注册一个宿主对象（名字对前端可见，如 `mf`）
pub fn register(
    core: &ICoreWebView2,
    name: &str,
    methods: &'static [&'static str],
) -> windows::core::Result<()> {
    let obj: &'static HostObject = Box::leak(Box::new(HostObject {
        vtbl: &VTBL,
        refs: AtomicU32::new(1),
        object: Box::leak(name.to_string().into_boxed_str()),
        methods,
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
        S_OK
    } else {
        *out = std::ptr::null_mut();
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

unsafe extern "system" fn type_info_count(_this: *mut c_void, out: *mut u32) -> HRESULT {
    if out.is_null() {
        return E_INVALIDARG;
    }
    *out = 0; // 暂不提供类型信息（这正是 mf.Dispatch 被当成属性的原因，见文件头）
    S_OK
}

unsafe extern "system" fn type_info(
    _this: *mut c_void,
    _itinfo: u32,
    _lcid: u32,
    out: *mut *mut c_void,
) -> HRESULT {
    if !out.is_null() {
        *out = std::ptr::null_mut();
    }
    // 若将来 WebView2 需要枚举成员，这里才需要真做一个 ITypeInfo；
    // 先如实返回"不支持"，不要在返回值上撒谎。
    E_NOTIMPL
}

unsafe extern "system" fn ids_of_names(
    this: *mut c_void,
    _riid: *const GUID,
    names: *const *const u16,
    count: u32,
    _lcid: u32,
    dispids: *mut i32,
) -> HRESULT {
    if names.is_null() || dispids.is_null() {
        return E_INVALIDARG;
    }
    let o = &*(this as *const HostObject);
    for i in 0..count as usize {
        let name_ptr = *names.add(i);
        let name = wide_to_string(name_ptr);
        let found = o
            .methods
            .iter()
            .position(|m| m.eq_ignore_ascii_case(&name))
            .map(|p| p as i32 + 1)
            .unwrap_or(-1); // DISPID_UNKNOWN
        *dispids.add(i) = found;
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
    _flags: u16,
    params: *const DISPPARAMS,
    result: *mut VARIANT,
    _excep: *mut EXCEPINFO,
    arg_err: *mut u32,
) -> HRESULT {
    let o = &*(this as *const HostObject);
    if dispid <= 0 || dispid as usize > o.methods.len() {
        return DISP_E_MEMBERNOTFOUND;
    }
    let method = o.methods[dispid as usize - 1];

    // DISPPARAMS.rgvarg 是**倒序**的（最后一个实参在 [0]）
    let mut args: Vec<Arg> = Vec::new();
    if !params.is_null() {
        let p = &*params;
        let n = p.cArgs as usize;
        for i in 0..n {
            let v = &*p.rgvarg.add(i);
            match variant_to_arg(v) {
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
