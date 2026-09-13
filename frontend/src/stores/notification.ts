import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import api from '@/services/api'
import { useToastStore } from '@/stores/toast'
import { useAuthStore } from '@/stores/auth'

export interface AppNotification {
  id: string
  task_id: string
  task_type: string
  status: string
  level: 'success' | 'error' | 'info' | string
  icon: string
  title: string
  body: string
  link: string
  read: boolean
  created_at?: string | null
  completed_at?: string | null
}

const POLL_MS = 15_000

export const useNotificationStore = defineStore('notification', () => {
  const items = ref<AppNotification[]>([])
  const unread = ref(0)
  const loading = ref(false)
  const open = ref(false)
  let timer: ReturnType<typeof setInterval> | null = null
  let lastSignature = ''

  const hasUnread = computed(() => unread.value > 0)

  function signatureOf(list: AppNotification[]): string {
    return list.map((n) => `${n.id}:${n.read ? 1 : 0}`).join('|')
  }

  async function fetchNotifications(silent = true): Promise<void> {
    const auth = useAuthStore()
    if (!auth.isAuthenticated) return
    if (!silent) loading.value = true
    try {
      const { data } = await api.get('/notifications', { params: { limit: 20 } })
      const list: AppNotification[] = data?.notifications || []
      items.value = list
      unread.value = Number(data?.unread || 0)
      const sig = signatureOf(list)
      // 新完成任务：首次出现且未读 → toast 提醒
      if (lastSignature && sig !== lastSignature) {
        const toast = useToastStore()
        const fresh = list.filter((n) => !n.read).slice(0, 2)
        for (const n of fresh) {
          if (!lastSignature.includes(n.id)) {
            const msg = n.title + (n.body ? `：${n.body}` : '')
            if (n.level === 'error') toast.error(msg)
            else toast.success(msg)
          }
        }
      }
      lastSignature = sig
    } catch {
      // 静默失败，避免轮询噪音
    } finally {
      loading.value = false
    }
  }

  async function markRead(id: string): Promise<void> {
    const target = items.value.find((n) => n.id === id)
    if (!target || target.read) return
    try {
      await api.post(`/notifications/${id}/read`)
      target.read = true
      unread.value = Math.max(0, unread.value - 1)
    } catch {
      /* ignore */
    }
  }

  async function markAllRead(): Promise<void> {
    try {
      await api.post('/notifications/read-all')
      items.value.forEach((n) => {
        n.read = true
      })
      unread.value = 0
    } catch {
      /* ignore */
    }
  }

  function startPolling(): void {
    stopPolling()
    void fetchNotifications(true)
    timer = setInterval(() => {
      void fetchNotifications(true)
    }, POLL_MS)
  }

  function stopPolling(): void {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  function reset(): void {
    stopPolling()
    items.value = []
    unread.value = 0
    lastSignature = ''
    open.value = false
  }

  return {
    items,
    unread,
    loading,
    open,
    hasUnread,
    fetchNotifications,
    markRead,
    markAllRead,
    startPolling,
    stopPolling,
    reset,
  }
})
