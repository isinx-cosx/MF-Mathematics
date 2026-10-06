import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

/**
 * 绘图页面（React 版）构建配置。
 *
 * 关键点：计算与绘图逻辑不重写，直接从 Vue 工程复用 `MFMath.UI.Vue/src/lib`：
 *   - `lib/plot/*.js`  采样、坐标映射、表达式解析、网格配色 —— **纯 JS，零 Vue 依赖**
 *   - `lib/bridge.js`  WebView2 引擎桥（hostObjects.sync.mf.Dispatch）—— 同样零依赖
 * 这样 React 版与 Vue 版共用同一份逻辑，不会出现两套算法漂移。
 */
const sharedSrc = fileURLToPath(new URL("../MFMath.UI.Vue/src/lib", import.meta.url));
const uiRoot = fileURLToPath(new URL("..", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@shared": sharedSrc },
  },
  server: {
    fs: { allow: [uiRoot] },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
