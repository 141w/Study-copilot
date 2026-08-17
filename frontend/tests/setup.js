import { createPinia, setActivePinia } from 'pinia'
import { beforeEach } from 'vitest'

// Create a fresh Pinia instance before each test
beforeEach(() => {
  setActivePinia(createPinia())
})

// Mock localStorage
const localStorageMock = (() => {
  let store = {}
  return {
    getItem: vi.fn((key) => store[key] || null),
    setItem: vi.fn((key, value) => { store[key] = value }),
    removeItem: vi.fn((key) => { delete store[key] }),
    clear: vi.fn(() => { store = {} }),
  }
})()

Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock })

// Mock window.location for router redirects
Object.defineProperty(window, 'location', {
  value: {
    href: '/',
    assign: vi.fn(),
    replace: vi.fn(),
    reload: vi.fn(),
  },
  writable: true,
})
