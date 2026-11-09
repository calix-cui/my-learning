import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

// 默认 node 环境跑纯逻辑（api / stores / theme），快且不需要 DOM。
// 组件测试在文件顶部写 `// @vitest-environment happy-dom` 单独切换，setup.ts 补浏览器 API 缺口。
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    include: ['src/**/*.test.ts'],
    environment: 'node',
    setupFiles: ['./src/test/setup.ts'],
    reporters: ['default'],
    coverage: {
      provider: 'v8',
      // 只统计会被组件/测试真正引用到的源码，配置文件与入口不计
      include: ['src/**/*.{ts,vue}'],
      exclude: ['src/**/*.test.ts', 'src/test/**', 'src/main.ts', 'src/vite-env.d.ts'],
      reporter: ['text', 'html'],
      reportsDirectory: 'coverage',
      // 不设门槛：前端组件覆盖率靠 E2E 兜底，硬性阈值会逼着写无意义的断言（见 ADR-0002）
      thresholds: undefined,
    },
  },
})
