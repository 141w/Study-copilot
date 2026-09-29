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
          testTimeout: 20000,
          include: ['tests/**/*.{test,spec}.{js,ts}'],
          setupFiles: ['./tests/setup.js'],
          // 钉住时区：F4 会话时间分组（ChatHistoryPanel）按「本地时区」分桶，
          // 测试里 setSystemTime 用的是 +08:00 偏移。不钉 TZ 则结果取决于
          // 跑测试的机器——开发机 CST 全绿，GitHub Runner（UTC）必红。
          env: { TZ: 'Asia/Shanghai' },
        },
      },
      {
        resolve: { alias },
        test: {
          name: 'bot',
          environment: 'node',
          globals: true,
          testTimeout: 300000,
          include: ['src/bot/**/*.test.ts'],
          setupFiles: ['./tests/setup.js'],
        },
      },
    ],
  },
})
