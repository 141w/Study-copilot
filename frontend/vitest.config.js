import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.js'],
    // 测试仅收集 tests/（src 下若有非本项目文件也不会被误捞进报告）
    include: ['tests/**/*.{test,spec}.{js,ts}'],
  },
})
