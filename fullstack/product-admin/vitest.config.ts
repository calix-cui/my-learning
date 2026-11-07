import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vitest/config'

// 只测不含 DOM 的纯逻辑模块（src/api 下的请求封装），因此不引 jsdom、不需要浏览器环境。
// 组件/页面级测试留给 Playwright，见 ADR-0002 的取舍。
export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    include: ['src/**/*.test.ts'],
    environment: 'node',
    reporters: ['default'],
  },
})
