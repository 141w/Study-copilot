import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import path from 'path'

const alias = { '@': path.resolve(__dirname, './src') }

/**
 * 双 project 拆分（vitest 4）：
 *  - spa：tests/ 下的组件/store 测试，jsdom 环境
 *  - bot：src/bot/ 下的纯函数引擎测试，node 环境（无 DOM，更快更准）
 * setup.js 内部按 window 存在与否自适应，两环境共用。
 */
export default defineConfig({
  plugins: [vue()],
  resolve: { alias },
  test: {
    projects: [
      {
        plugins: [vue()],
        resolve: { alias },
        test: {
          name: 'spa',
          environment: 'jsdom',
          globals: true,
          include: ['tests/**/*.{test,spec}.{js,ts}'],
          setupFiles: ['./tests/setup.js'],
        },
      },
      {
        resolve: { alias },
        test: {
          name: 'bot',
          environment: 'node',
          globals: true,
          include: ['src/bot/**/*.test.ts'],
          setupFiles: ['./tests/setup.js'],
        },
      },
    ],
  },
})
