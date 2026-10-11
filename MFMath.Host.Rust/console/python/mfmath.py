# mfmath.py — 控制台里调用 C++ 引擎的唯一门面（纯 ctypes，不依赖任何第三方包）
#
# 设计约束（与项目一致）：**计算全部由 C++ 引擎完成**，这里只做参数封装与 JSON 编解码。
# 有了它，Python 侧写的就是：
#
#     import mfmath
#     print(mfmath.call("diff", expr="xe^x", var="x"))     # x*exp(x) + exp(x)
#     print(mfmath.call("expr_eval", expr="x^2", x=3))     # 9
#
# 引擎 DLL 的位置按顺序找：
#   ① MF_ENGINE_DIR 环境变量指向的目录（宿主启动 Python 时会设为应用目录）
#   ② 本文件所在目录
#   ③ 系统 PATH
import ctypes
import json
import os

_DLL_NAME = "mf_mathematics.dll"
_BUF_SIZE = 4 * 1024 * 1024          # 4 MB，与 C# 侧 MathBridge 一致
_here = os.path.dirname(os.path.abspath(__file__))


class EngineError(RuntimeError):
    """引擎返回的错误（{isError:true}）都会以这个异常抛出，便于 try/except 捕获。"""


def _search_paths():
    paths = []
    env = os.environ.get("MF_ENGINE_DIR")
    if env:
        paths.append(env)
    paths.append(_here)
    paths.append(os.getcwd())
    return paths


def _load():
    last = None
    for directory in _search_paths():
        candidate = os.path.join(directory, _DLL_NAME)
        if os.path.exists(candidate):
            try:
                return ctypes.CDLL(candidate)
            except OSError as exc:      # 依赖 DLL 缺失或架构不符
                last = exc
    try:                                 # 最后交给系统搜索 PATH
        return ctypes.CDLL(_DLL_NAME)
    except OSError as exc:
        last = exc
    raise ImportError(
        "找不到 %s（应放在应用目录，或让 MF_ENGINE_DIR 指向它）：%s" % (_DLL_NAME, last)
    )


_dll = _load()
_dll.function_exists.argtypes = [ctypes.c_char_p]
_dll.function_exists.restype = ctypes.c_bool
_dll.math_call.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
_dll.math_call.restype = ctypes.c_int


def exists(name):
    """引擎是否注册了这个函数（例如 exists("diff")）。"""
    if not isinstance(name, str):
        raise TypeError("函数名必须是字符串")
    return bool(_dll.function_exists(name.encode("utf-8")))


def call_raw(name, **args):
    """调用引擎并原样返回 {isError, value}，不抛异常（要自己判错时用）。"""
    payload = json.dumps(args, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    buf = ctypes.create_string_buffer(_BUF_SIZE)
    n = _dll.math_call(name.encode("utf-8"), payload, buf, _BUF_SIZE)
    if n < 0:
        return {"isError": True, "value": "引擎调用失败（输出超出缓冲或参数非法）"}
    text = buf.raw[:n].decode("utf-8", "replace")
    try:
        return json.loads(text)
    except ValueError:
        return {"isError": True, "value": "引擎返回的不是 JSON：" + text[:200]}


def call(name, **args):
    """调用引擎，返回 value；引擎报错则抛 EngineError。"""
    if not isinstance(name, str):
        raise TypeError("函数名必须是字符串")
    out = call_raw(name, **args)
    if out.get("isError"):
        raise EngineError(str(out.get("value")))
    return out.get("value")


def functions():
    """引擎注册的全部函数名（list_functions）。"""
    value = call("list_functions")
    if isinstance(value, dict):          # 不同版本可能包成对象
        for key in ("functions", "names", "items"):
            if key in value:
                return value[key]
    return value


def call_json(name, args_json):
    """参数已经是 JSON 字符串时用这个（少一层编码）。"""
    return call_raw(name, **json.loads(args_json))
