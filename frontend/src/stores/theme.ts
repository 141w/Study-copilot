import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type Theme = 'light' | 'dark' | 'system'

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<Theme>((localStorage.getItem('theme') as Theme) || 'system')
  const isDark = ref(false)

  // Detect system preference
  function getSystemTheme(): 'light' | 'dark' {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }

  // Apply theme to document
  function applyTheme(value: Theme) {
    const resolved = value === 'system' ? getSystemTheme() : value
    isDark.value = resolved === 'dark'

    if (resolved === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }

  // Set theme
  function setTheme(value: Theme) {
    theme.value = value
    localStorage.setItem('theme', value)
    applyTheme(value)
  }

  // Toggle between light and dark
  function toggleTheme() {
    const next = isDark.value ? 'light' : 'dark'
    setTheme(next)
  }

  // Listen for system theme changes
  if (typeof window !== 'undefined') {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    mediaQuery.addEventListener('change', () => {
      if (theme.value === 'system') {
        applyTheme('system')
      }
    })
  }

  // Initialize
  applyTheme(theme.value)

  return {
    theme,
    isDark,
    setTheme,
    toggleTheme
  }
})
