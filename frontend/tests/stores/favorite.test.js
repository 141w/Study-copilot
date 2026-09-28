import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
  cancelAll: vi.fn(),
}))

import { setActivePinia, createPinia } from 'pinia'
import { useFavoriteStore } from '@/stores/favorite'
import api from '@/services/api'

describe('P0-B favorite store', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useFavoriteStore()
    vi.clearAllMocks()
  })

  it('fetchFavorites 加载列表', async () => {
    api.get.mockResolvedValue({
      data: [{ id: 'f1', resource_type: 'document', resource_id: 'd1' }]
    })
    await store.fetchFavorites()
    expect(store.isFavorite('document', 'd1')).toBe(true)
    expect(store.loaded).toBe(true)
  })

  it('toggle 添加收藏', async () => {
    api.post.mockResolvedValue({
      data: { id: 'f2', resource_type: 'note', resource_id: 'n1' }
    })
    const now = await store.toggle('note', 'n1')
    expect(now).toBe(true)
    expect(store.isFavorite('note', 'n1')).toBe(true)
  })

  it('toggle 取消收藏', async () => {
    store.items = [{ id: 'f3', resource_type: 'document', resource_id: 'd9' }]
    api.delete.mockResolvedValue({ data: { success: true } })
    const now = await store.toggle('document', 'd9')
    expect(now).toBe(false)
    expect(store.isFavorite('document', 'd9')).toBe(false)
  })

  it('接口失败时状态不变', async () => {
    store.items = [{ id: 'f4', resource_type: 'note', resource_id: 'n2' }]
    api.delete.mockRejectedValue(new Error('x'))
    const now = await store.toggle('note', 'n2')
    expect(now).toBe(true)
    expect(store.isFavorite('note', 'n2')).toBe(true)
  })
})
