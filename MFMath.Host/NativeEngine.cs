using System.Runtime.InteropServices;
using System.Text;

namespace MFMath.Host;

/// <summary>P/Invoke 层：调 mf_mathematics.dll 的 C ABI（api.cpp 的 math_call / function_exists）</summary>
internal static partial class NativeEngine
{
    [DllImport("mf_mathematics.dll", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)]
    private static extern bool function_exists([MarshalAs(UnmanagedType.LPUTF8Str)] string name);

    [DllImport("mf_mathematics.dll", CallingConvention = CallingConvention.Cdecl)]
    private static extern int math_call(
        [MarshalAs(UnmanagedType.LPUTF8Str)] string name,
        [MarshalAs(UnmanagedType.LPUTF8Str)] string argsJson,
        IntPtr outBuffer, int outSize);

    // 分级缓冲：常规调用 4 MB 够用；复网格这类整块数据（600×600 的 re/im 约 12 MB JSON）
    // 会被 4 MB 顶掉，所以逐级扩容重试——而不是给所有调用一律开 64 MB 白占内存。
    private static readonly int[] BufSizes = { 4 * 1024 * 1024, 16 * 1024 * 1024, 64 * 1024 * 1024 };

    /// <summary>引擎是否注册了指定函数</summary>
    public static bool Exists(string name) => function_exists(name);

    /// <summary>调用引擎任意函数，返回 {isError, value} JSON 字符串</summary>
    public static string Call(string name, string argsJson)
    {
        foreach (int size in BufSizes)
        {
            IntPtr buf = Marshal.AllocHGlobal(size);
            try
            {
                int n = math_call(name, argsJson, buf, size);
                if (n < 0) continue;                 // 缓冲不够：换更大的再试一次
                byte[] bytes = new byte[n];
                Marshal.Copy(buf, bytes, 0, n);
                return Encoding.UTF8.GetString(bytes);
            }
            finally
            {
                Marshal.FreeHGlobal(buf);
            }
        }
        return "{\"isError\":true,\"value\":\"引擎结果超过 64 MB 上限（请降低分辨率）\"}";
    }
}
