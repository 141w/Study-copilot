import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, vi } from 'vitest'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import { createApp } from 'vue'

// Register Element Plus globally so tests can resolve el-* components
const app = createApp({ template: '<div />' })
app.use(ElementPlus, { locale: zhCn })

// Mock axios
vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
    interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
  },
}))

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
