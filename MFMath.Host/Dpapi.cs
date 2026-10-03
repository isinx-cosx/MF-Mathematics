// Dpapi.cs — 密钥保护的唯一实现（AI 的 API Key 与搜索的 Wolfram App ID 共用）（Windows DPAPI，用户范围）
//
// 为什么自己 P/Invoke 而不是引 NuGet 的 System.Security.Cryptography.ProtectedData：
//   · 宿主的依赖清单是**刻意短**的（目前只有 WebView2 一个包），而 ProtectedData 在
//     .NET Core 之后被拆成了独立包；为了一个 20 行的调用拉一个新依赖不划算；
//   · crypt32 是 Windows 自带的，DllImport 直接可用，行为完全一致（同样的
//     CryptProtectData / CryptUnprotectData，同样的"当前用户"作用域）。
//
// 三条纪律：
//   ① **只在当前用户下可解**（不传 CRYPTPROTECT_LOCAL_MACHINE）：换个用户账户
//      复制走这个文件也解不开。这正是密钥文件该有的性质。
//   ② **禁止弹 UI**（CRYPTPROTECT_UI_FORBIDDEN）：加解密绝不能因为系统状态而弹窗，
//      这与"不弹窗口"的整体要求一致；失败就如实报告失败。
//   ③ **失败绝不降级成明文落盘** —— 调用方（AiBridge）在 Protect 失败时只把密钥留在
//      内存里并明确告诉用户"本次会话有效、重启后需要重填"，绝不写一份明文到磁盘。
using System;
using System.Runtime.InteropServices;
using System.Text;

namespace MFMath.Host;

internal static class Dpapi
{
    private const int CRYPTPROTECT_UI_FORBIDDEN = 0x1;

    [StructLayout(LayoutKind.Sequential)]
    private struct DATA_BLOB
    {
        public int cbData;
        public IntPtr pbData;
    }

    [DllImport("crypt32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool CryptProtectData(
        ref DATA_BLOB pDataIn, string? szDataDescr, IntPtr pOptionalEntropy,
        IntPtr pvReserved, IntPtr pPromptStruct, int dwFlags, out DATA_BLOB pDataOut);

    [DllImport("crypt32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool CryptUnprotectData(
        ref DATA_BLOB pDataIn, IntPtr ppszDataDescr, IntPtr pOptionalEntropy,
        IntPtr pvReserved, IntPtr pPromptStruct, int dwFlags, out DATA_BLOB pDataOut);

    [DllImport("kernel32.dll")]
    private static extern IntPtr LocalFree(IntPtr hMem);

    private static byte[] BlobBytes(DATA_BLOB blob)
    {
        var outBytes = new byte[blob.cbData];
        if (blob.cbData > 0) Marshal.Copy(blob.pbData, outBytes, 0, blob.cbData);
        return outBytes;
    }

    /// <summary>加密成 base64。失败返回 null（调用方绝不能因此改成明文存储）。</summary>
    public static string? Protect(string plain)
    {
        if (string.IsNullOrEmpty(plain)) return null;
        var input = Encoding.UTF8.GetBytes(plain);
        var inBlob = new DATA_BLOB { cbData = input.Length, pbData = Marshal.AllocHGlobal(input.Length) };
        DATA_BLOB outBlob = default;
        try
        {
            Marshal.Copy(input, 0, inBlob.pbData, input.Length);
            if (!CryptProtectData(ref inBlob, "MFMath secret", IntPtr.Zero, IntPtr.Zero, IntPtr.Zero,
                                  CRYPTPROTECT_UI_FORBIDDEN, out outBlob))
                return null;
            return Convert.ToBase64String(BlobBytes(outBlob));
        }
        catch
        {
            return null;
        }
        finally
        {
            if (inBlob.pbData != IntPtr.Zero)
            {
                // 明文缓冲区先擦再还
                for (int i = 0; i < input.Length; i++) Marshal.WriteByte(inBlob.pbData, i, 0);
                Marshal.FreeHGlobal(inBlob.pbData);
            }
            if (outBlob.pbData != IntPtr.Zero) LocalFree(outBlob.pbData);
        }
    }

    /// <summary>解密。失败返回 null（换了用户、文件被改、系统策略禁止都会走到这里）。</summary>
    public static string? Unprotect(string base64)
    {
        if (string.IsNullOrWhiteSpace(base64)) return null;
        byte[] cipher;
        try { cipher = Convert.FromBase64String(base64); }
        catch { return null; }

        var inBlob = new DATA_BLOB { cbData = cipher.Length, pbData = Marshal.AllocHGlobal(cipher.Length) };
        DATA_BLOB outBlob = default;
        try
        {
            Marshal.Copy(cipher, 0, inBlob.pbData, cipher.Length);
            if (!CryptUnprotectData(ref inBlob, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero,
                                    CRYPTPROTECT_UI_FORBIDDEN, out outBlob))
                return null;
            return Encoding.UTF8.GetString(BlobBytes(outBlob));
        }
        catch
        {
            return null;
        }
        finally
        {
            if (inBlob.pbData != IntPtr.Zero) Marshal.FreeHGlobal(inBlob.pbData);
            if (outBlob.pbData != IntPtr.Zero) LocalFree(outBlob.pbData);
        }
    }

    /// <summary>DPAPI 在这台机器上到底能不能用（设置面板要如实告诉用户密钥是怎么存的）</summary>
    public static bool SelfTest()
    {
        const string probe = "mfmath-dpapi-probe";
        var blob = Protect(probe);
        if (blob == null) return false;
        return Unprotect(blob) == probe;
    }
}
