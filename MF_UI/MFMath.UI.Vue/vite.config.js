import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// MFMath 桌面端 WebView2 UI — Vue 3 + Vite
// - dev  : npm run dev          → http://127.0.0.1:5173（C# 宿主 Debug 模式指向此处，热更新）
// - build: npm run build        → dist/（宿主 Release 经虚拟主机加载 wwwroot 拷贝）
//
// 2026-10-06：绘图页（/plot/2d 与 /plot/polar）改用 React 实现，**嵌在 Vue 外壳里**。
// 两个框架共存是有意的：外壳（导航/顶栏/设置/教程/控制台…）仍在 Vue，只有绘图页是 React。
// 为此这里加三样东西：
//   ① @vitejs/plugin-react —— 转译 .tsx。版本必须配 vite 6：用 ^4.3.3
//      （最新的 v6 要求 vite ^8，装上去会 ERESOLVE 冲突）。
//   ② `@shared` 别名 —— React 侧源码里写的是 `@shared/plot/*`、`@shared/bridge.js`，
//      这里指到**本工程的 src/lib**。必须是同一份文件（同一个模块实例），
//      否则 plotMath 的注入钩子、引擎桥会各有一份，行为会漂移。
//   ③ server.fs.allow —— dev 下要允许读工程上一级（React 源码在 ../MFMath.UI.React）。
export default defineConfig({
  plugins: [
    // MathLive 提供 <math-field> 自定义元素：直接把数学排版渲染在输入框内。
    // 必须告诉 Vue 它是原生自定义元素，否则会被当成"未注册组件"而报警告/不渲染。
    vue({
      template: {
        compilerOptions: { isCustomElement: (tag) => tag === "math-field" },
      },
    }),
    react(),
    {
      name: "access-log",
      apply: "serve",
      configureServer(server) {
        server.middlewares.use((req, _res, next) => {
          console.log("[webview]", req.url);
          next();
        });
      },
    },
  ],
  resolve: {
    alias: {
      "@shared": fileURLToPath(new URL("./src/lib", import.meta.url)),
    },
  },
  // 相对路径，保证经虚拟主机/file 方式加载时资源可用
  base: "./",
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    // React 源码在工程外一层（../MFMath.UI.React/src），dev 要允许读
    fs: { allow: [fileURLToPath(new URL("..", import.meta.url))] },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    target: "chrome110",
  },
});
