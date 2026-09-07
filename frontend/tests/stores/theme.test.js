import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useThemeStore } from '@/stores/theme'

describe('Theme Store', () => {
  let mediaChangeHandler = null
  let matchesDark = false

  beforeEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove('dark')
    document.documentElement.style.colorScheme = ''
    matchesDark = false
    mediaChangeHandler = null

    // Mock window.matchMedia
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: matchesDark,
      media: query,
      onchange: null,
      addListener: vi.fn((fn) => { mediaChangeHandler = fn }),
      removeListener: vi.fn(),
      addEventListener: vi.fn((event, fn) => {
        if (event === 'change') mediaChangeHandler = fn
      }),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))

    setActivePinia(createPinia())
  })

  it('initializes with system theme by default and adapts to system preference', () => {
    matchesDark = true
    const store = useThemeStore()

    expect(store.theme).toBe('system')
    expect(store.isSystem).toBe(true)
    expect(store.isDark).toBe(true)
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(document.documentElement.style.colorScheme).toBe('dark')
  })

  it('explicitly sets theme to light and persists to localStorage', () => {
    const store = useThemeStore()
    store.setTheme('light')

    expect(store.theme).toBe('light')
    expect(store.isSystem).toBe(false)
    expect(store.isDark).toBe(false)
    expect(localStorage.getItem('theme')).toBe('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(document.documentElement.style.colorScheme).toBe('light')
  })

  it('explicitly sets theme to dark and persists to localStorage', () => {
    const store = useThemeStore()
    store.setTheme('dark')

    expect(store.theme).toBe('dark')
    expect(store.isSystem).toBe(false)
    expect(store.isDark).toBe(true)
    expect(localStorage.getItem('theme')).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(document.documentElement.style.colorScheme).toBe('dark')
  })

  it('cycles through 3-state toggle: light -> dark -> system -> light', () => {
    const store = useThemeStore()
    store.setTheme('light')
    expect(store.theme).toBe('light')

    // 1st toggle: light -> dark
    store.toggleTheme()
    expect(store.theme).toBe('dark')
    expect(localStorage.getItem('theme')).toBe('dark')

    // 2nd toggle: dark -> system
    store.toggleTheme()
    expect(store.theme).toBe('system')
    expect(store.isSystem).toBe(true)
    expect(localStorage.getItem('theme')).toBe('system')

    // 3rd toggle: system -> light
    store.toggleTheme()
    expect(store.theme).toBe('light')
    expect(localStorage.getItem('theme')).toBe('light')
  })

  it('reacts dynamically to system preference change when theme is system', () => {
    const store = useThemeStore()
    store.setTheme('system')
    expect(store.isDark).toBe(false)

    // Simulate system switching to dark mode
    if (mediaChangeHandler) {
      mediaChangeHandler({ matches: true })
    }

    expect(store.systemTheme).toBe('dark')
    expect(store.isDark).toBe(true)
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(document.documentElement.style.colorScheme).toBe('dark')

    // Simulate system switching back to light mode
    if (mediaChangeHandler) {
      mediaChangeHandler({ matches: false })
    }

    expect(store.systemTheme).toBe('light')
    expect(store.isDark).toBe(false)
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(document.documentElement.style.colorScheme).toBe('light')
  })

  it('ignores system preference change when theme is fixed to dark or light', () => {
    const store = useThemeStore()
    store.setTheme('light')

    // System switches to dark, but user fixed theme to light
    if (mediaChangeHandler) {
      mediaChangeHandler({ matches: true })
    }

    expect(store.theme).toBe('light')
    expect(store.isDark).toBe(false)
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })
})
