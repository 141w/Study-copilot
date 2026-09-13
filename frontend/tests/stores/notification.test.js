import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '@/services/api'
import { useNotificationStore } from '@/stores/notification'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({ success: vi.fn(), error: vi.fn(), show: vi.fn() }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ isAuthenticated: true }),
}))

describe('notification store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetches notifications and unread count', async () => {
    api.get.mockResolvedValue({
      data: {
        notifications: [
          {
            id: 't1',
            task_id: 't1',
            task_type: 'document_process',
            status: 'completed',
            level: 'success',
            icon: 'success',
            title: '文档解析完成',
            body: '《讲义.pdf》已可检索',
            link: '/documents?document_id=doc-1',
            read: false,
          },
        ],
        unread: 1,
      },
    })
    const store = useNotificationStore()
    await store.fetchNotifications()
    expect(store.unread).toBe(1)
    expect(store.items[0].link).toContain('/documents')
    expect(store.hasUnread).toBe(true)
  })

  it('marks one as read locally after API', async () => {
    const store = useNotificationStore()
    store.items = [
      {
        id: 't1',
        task_id: 't1',
        task_type: 'document_process',
        status: 'completed',
        level: 'success',
        icon: 'success',
        title: 'x',
        body: 'y',
        link: '/tasks',
        read: false,
      },
    ]
    store.unread = 1
    api.post.mockResolvedValue({ data: { ok: true, unread: 0 } })
    await store.markRead('t1')
    expect(api.post).toHaveBeenCalledWith('/notifications/t1/read')
    expect(store.items[0].read).toBe(true)
    expect(store.unread).toBe(0)
  })
})
