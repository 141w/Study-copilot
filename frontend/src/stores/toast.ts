import { defineStore } from 'pinia'
import { ref } from 'vue'

interface Toast {
  id: number
  message: string
  type: 'info' | 'success' | 'warning' | 'error'
  visible: boolean
}

export const useToastStore = defineStore('toast', () => {
  const toasts = ref<Toast[]>([])
  let idCounter = 0

  function show(msg: string, toastType: Toast['type'] = 'info', duration = 3000): void {
    const id = ++idCounter
    toasts.value.push({ id, message: msg, type: toastType, visible: true })

    // Enforce max 3 visible toasts — remove oldest if over limit
    if (toasts.value.length > 3) {
      toasts.value.splice(0, toasts.value.length - 3)
    }

    setTimeout(() => {
      remove(id)
    }, duration)
  }

  function remove(id: number): void {
    const idx = toasts.value.findIndex(t => t.id === id)
    if (idx !== -1) {
      toasts.value[idx].visible = false
      // Wait for leave animation then splice out
      setTimeout(() => {
        const i = toasts.value.findIndex(t => t.id === id)
        if (i !== -1) toasts.value.splice(i, 1)
      }, 300)
    }
  }

  function hide(): void {
    // Hide all toasts
    toasts.value.forEach(t => { t.visible = false })
    setTimeout(() => {
      toasts.value = []
    }, 300)
  }

  function success(msg: string, duration?: number): void {
    show(msg, 'success', duration)
  }

  function error(msg: string, duration?: number): void {
    show(msg, 'error', duration)
  }

  function warning(msg: string, duration?: number): void {
    show(msg, 'warning', duration)
  }

  function info(msg: string, duration?: number): void {
    show(msg, 'info', duration)
  }

  return {
    toasts,
    show,
    hide,
    remove,
    success,
    error,
    warning,
    info
  }
})
