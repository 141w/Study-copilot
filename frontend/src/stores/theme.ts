import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type Theme = 'light' | 'dark' | 'system'

/**
 * 模块级强引用持久保存 MediaQueryList，
 * 彻底防止被 V8 / WebKit GC 垃圾回收导致 change 监听静默失效（Chromium Issue 889370）。
 */
let persistentMql: MediaQueryList | null = null

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<Theme>((typeof localStorage !== 'undefined' && localStorage.getItem('theme') as Theme) || 'system')
  const isDark = ref(false)
  const systemTheme = ref<'light' | 'dark'>(getSystemTheme())

  // Detect system preference
  function getSystemTheme(): 'light' | 'dark' {
    if (typeof window === 'undefined' || !window.matchMedia) {
      return 'light'
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }

  // Apply theme to document & sync colorScheme
  function applyTheme(value: Theme, sysPref?: 'light' | 'dark') {
    const currentSys = sysPref ?? getSystemTheme()
    systemTheme.value = currentSys
    const resolved = value === 'system' ? currentSys : value
    isDark.value = resolved === 'dark'

    if (typeof document !== 'undefined') {
      if (resolved === 'dark') {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
      // 同步系统原生控件与滚动条色调
      document.documentElement.style.colorScheme = resolved
    }
  }

  // Set theme & persist to localStorage
  function setTheme(value: Theme) {
    theme.value = value
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('theme', value)
    }
    applyTheme(value)
  }

  const isSystem = computed(() => theme.value === 'system')
  const resolvedTheme = computed<'light' | 'dark'>(() => (isDark.value ? 'dark' : 'light'))

  const themeLabel = computed<string>(() => {
    if (theme.value === 'system') {
      return `跟随系统 (${systemTheme.value === 'dark' ? '暗色' : '亮色'})`
    }
    return theme.value === 'dark' ? '暗色模式' : '亮色模式'
  })

  // 三态循环：亮色 -> 暗色 -> 跟随系统 -> 亮色
  const nextTheme = computed<Theme>(() => {
    if (theme.value === 'light') return 'dark'
    if (theme.value === 'dark') return 'system'
    return 'light'
  })

  // Toggle between light, dark, and system
  function toggleTheme() {
    setTheme(nextTheme.value)
  }

  // Listen for system theme changes with robust reference
  function initSystemThemeListener() {
    if (typeof window === 'undefined' || !window.matchMedia) return
    if (!persistentMql) {
      persistentMql = window.matchMedia('(prefers-color-scheme: dark)')
    }

    const handler = (e: MediaQueryListEvent | MediaQueryList) => {
      const newSysTheme = e.matches ? 'dark' : 'light'
      systemTheme.value = newSysTheme
      if (theme.value === 'system') {
        applyTheme('system', newSysTheme)
      }
    }

    if (persistentMql.addEventListener) {
      persistentMql.addEventListener('change', handler)
    } else if ('addListener' in persistentMql) {
      persistentMql.addListener(handler)
    }
  }

  // Initialize
  initSystemThemeListener()
  applyTheme(theme.value)

  return {
    theme,
    isDark,
    systemTheme,
    isSystem,
    resolvedTheme,
    themeLabel,
    nextTheme,
    setTheme,
    toggleTheme,
    applyTheme,
    getSystemTheme
  }
})
