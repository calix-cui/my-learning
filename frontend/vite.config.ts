import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import vueDevtools from 'vite-plugin-vue-devtools'

// 开发服务器固定 5173，预览服务器固定 4173；两者均不占用后端 8000 端口。
export default defineConfig({
  // 只影响 `pnpm dev`：Vite DevTools 面板（组件树 / Pinia 状态 / 路由 / 性能）
  plugins: [vue(), vueDevtools()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // 同时监听 IPv4/IPv6 回环地址，保证 127.0.0.1 与 localhost 都能访问
    host: '::',
    port: 5173,
    strictPort: true,
    proxy: {
      // 开发期把 /api 转发到 FastAPI 后端，避免依赖浏览器跨域配置。
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: '::',
    port: 4173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // element-plus 单包体积较大，属于预期情况，放宽告警阈值
    chunkSizeWarningLimit: 1000,
    // 拆出框架与组件库，利用浏览器缓存并减小主包体积
    rollupOptions: {
      output: {
        manualChunks: {
          vue: ['vue', 'vue-router'],
          element: ['element-plus', '@element-plus/icons-vue'],
        },
      },
    },
  },
})
