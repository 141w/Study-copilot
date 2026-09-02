import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, vi } from 'vitest'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import { createApp } from 'vue'

// setup 同时服务两类测试：
//  - tests/**（jsdom）：完整 SPA mock
//  - src/bot/**（node，纯函数引擎）：window 不存在，DOM 相关 mock 全部跳过
const isDom = typeof window !== 'undefined'

if (isDom) {
  // Register Element Plus globally so tests can resolve el-* components
  const app = createApp({ template: '<div />' })
  app.use(ElementPlus, { locale: zhCn })
}

// Mock axios（bot 测试不用 api，mock 无害且对两类环境安全）
vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
    interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
  },
}))

if (isDom) {
  // Mock localStorage
  const store = {}
  Object.defineProperty(globalThis, 'localStorage', {
    value: {
      getItem: vi.fn((k) => store[k] || null),
      setItem: vi.fn((k, v) => { store[k] = v }),
      removeItem: vi.fn((k) => { delete store[k] }),
      clear: vi.fn(() => { Object.keys(store).forEach(k => delete store[k]) }),
    },
  })

  Object.defineProperty(window, 'location', {
    value: { href: '/', assign: vi.fn(), replace: vi.fn(), reload: vi.fn() },
    writable: true,
  })

  beforeEach(() => {
    setActivePinia(createPinia())
  })
}
