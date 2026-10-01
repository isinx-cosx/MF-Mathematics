using System.Runtime.InteropServices;
using System.Text.Json;

namespace MFMath.Host;

/// <summary>供 JS 调用的桥对象（通过 AddHostObjectToScript 注册为 window 下的 "mf"）。
///
/// 两类接口：
///  1) 通用透传 Dispatch(name, argsJson) —— 可调引擎任意已注册函数；
///     引擎新增函数无需改 C# 即可用。
///  2) 符号能力类型化方法 —— 由 C# 构造参数 JSON，避免 JS 侧手拼字符串出转义错误。
/// </summary>
[ComVisible(true)]
public class MathBridge
{
    /// <summary>JS 调用：window.chrome.webview.hostObjects.sync.mf.dispatch(name, argsJson)</summary>
    public string Dispatch(string name, string argsJson)
    {
        try
        {
            return NativeEngine.Call(name, argsJson);
        }
        catch (Exception e)
        {
            return JsonSerializer.Serialize(new { isError = true, value = e.Message });
        }
    }

    /// <summary>桥自检：返回 true 表示桥已就绪</summary>
    public bool Ready() => true;

    /// <summary>引擎版本信息</summary>
    public string Version() => "mf_mathematics (C++ 引擎) via MFMath.Host";

    /// <summary>引擎是否注册了指定函数（用于 UI 判断能力是否存在/降级）</summary>
    public bool FunctionExists(string name)
    {
        try
        {
            return NativeEngine.Exists(name);
        }
        catch
        {
            return false;
        }
    }

    // ── 符号能力（类型化封装：内部构造 JSON，返回引擎的 {isError,value} JSON）──────

    /// <summary>精确解（含自由参数），如 x^2-a → ["-sqrt(a)","sqrt(a)"]</summary>
    public string SolveSymbolic(string expr, string var = "x")
        => Dispatch("solve_sym", JsonSerializer.Serialize(new { expr, var }));

    /// <summary>符号判别式 Δ=b²-4ac（系数保留表达式，不数值化）</summary>
    public string DiscriminantSymbolic(string expr, string var = "x")
        => Dispatch("discriminant_sym", JsonSerializer.Serialize(new { expr, var }));

    /// <summary>符号因式分解（保留精确根）</summary>
    public string FactorSymbolic(string expr, string var = "x")
        => Dispatch("factor_sym", JsonSerializer.Serialize(new { expr, var }));

    /// <summary>表达式等价判定（两式之差恒为 0？）</summary>
    public string CompareExpr(string a, string b)
        => Dispatch("compare_expr", JsonSerializer.Serialize(new { a, b }));

    /// <summary>精确化简</summary>
    public string SimplifySymbolic(string expr)
        => Dispatch("simplify_sym", JsonSerializer.Serialize(new { expr }));

    /// <summary>含参极值 + 参数分类讨论（符号驻点 + 参数分支）</summary>
    public string ExtremaSymbolic(string expr, string var = "x")
        => Dispatch("extrema_sym", JsonSerializer.Serialize(new { expr, var }));

    /// <summary>表达式的自由符号列表（判断是否含参数）</summary>
    public string FreeSymbols(string expr)
        => Dispatch("free_symbols_of", JsonSerializer.Serialize(new { expr }));

    /// <summary>求导（支持自由参数）</summary>
    public string Differentiate(string expr, string var = "x")
        => Dispatch("diff", JsonSerializer.Serialize(new { expr, var }));
}
