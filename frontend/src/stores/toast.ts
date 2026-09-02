// 子路径导入：避免 'element-plus' 根入口 re-export 全量组件（曾致 vendor chunk 945KB）
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import 'element-plus/es/components/message/style/css'
import { defineStore } from 'pinia'

type ToastType = 'info' | 'success' | 'warning' | 'error'

export const useToastStore = defineStore('toast', () => {
  function show(msg: string, toastType: ToastType = 'info', duration = 3000): void {
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
    show,
    hide,
    success,
    error,
    warning,
    info
  }
})
