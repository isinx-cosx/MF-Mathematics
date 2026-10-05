/**
 * WebView2 宿主对象的最小类型声明。
 *
 * 为什么需要它：`window.chrome` 不属于 lib.dom（那是浏览器标准里没有的东西），
 * 不声明就永远是 `any` 或直接报 TS2339「Property 'chrome' does not exist」——
 * 补上之后，桥的调用点至少能拿到参数/返回值的类型，而不是全靠记忆。
 *
 * ⚠ 这里只声明**实际用到**的形状，不追求完整。宿主侧的 C# 实现在 MFMath.Host/*.cs
 * （每个 bridge 一个 hostObjects 命名空间：mf / ai / con / search / account / update / sys / win）。
 * 同步对象（hostObjects.sync.*）的方法都是**阻塞**的：在渲染进程主线程上直接调用，
 * 所以耗时操作必须走异步/推送，别在这些方法里等网络。
 */

/**
 * 宿主命名空间：一个装着 C# 方法的动态对象。
 *
 * 这里用显式 `any` 是有意的 —— 桥的对面是 C# 的 COM/IDispatch 对象，参数与返回值
 * 只有运行时才知道（例如 `mf.Dispatch(name, json)` 返回一段 JSON 字符串）。
 * 在这一层做精确类型只会变成一堆无意义的断言，所以边界上放开、**出了边界再收严**。
 */
export type HostNamespace = Record<string, (...args: any[]) => any>

export interface WebView2HostObjects {
  /** 同步对象：调用即阻塞渲染进程 */
  sync?: Record<string, HostNamespace>
  /** 异步对象：返回 Promise */
  async?: Record<string, HostNamespace>
}

export interface WebView2 {
  hostObjects?: WebView2HostObjects
  /** 宿主 → 渲染进程 的消息入口 */
  addEventListener?: (type: string, listener: (ev: { data?: unknown }) => void) => void
  removeEventListener?: (type: string, listener: (ev: { data?: unknown }) => void) => void
  /** 渲染进程 → 宿主 */
  postMessage?: (message: unknown) => void
}

declare global {
  interface Window {
    chrome?: { webview?: WebView2 }
  }
}

export {}
