import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// MFMath 桌面端 WebView2 UI — Vue 3 + Vite
// - dev  : npm run dev          → http://127.0.0.1:5173（C# 宿主 Debug 模式指向此处，热更新）
// - build: npm run build        → dist/（C# 宿主 Release 经虚拟主机加载 wwwroot 拷贝）
export default defineConfig({
  plugins: [
    // MathLive 提供 <math-field> 自定义元素：直接把数学排版渲染在输入框内。
    // 必须告诉 Vue 它是原生自定义元素，否则会被当成"未注册组件"而报警告/不渲染。
    vue({
      template: {
        compilerOptions: { isCustomElement: (tag) => tag === "math-field" },
      },
    }),
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
  // 相对路径，保证经虚拟主机/file 方式加载时资源可用
  base: "./",
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    target: "chrome110",
  },
});
