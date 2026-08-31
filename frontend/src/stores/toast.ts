import { ElMessage } from 'element-plus'
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
    const method = toastType === 'error' ? 'error' :
                   toastType === 'warning' ? 'warning' :
                   toastType === 'success' ? 'success' : 'info'
    ElMessage({ message: msg, type: method, duration })
  }

  function hide(): void {
    ElMessage.closeAll()
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
    success,
    error,
    warning,
    info
  }
})
