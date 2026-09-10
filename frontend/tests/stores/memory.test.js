import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useMemoryStore } from '@/stores/memory'
import api from '@/services/api'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('Memory Store', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useMemoryStore()
    vi.clearAllMocks()
  })

  it('initializes with default values', () => {
    expect(store.items).toEqual([])
    expect(store.config.enabled).toBe(true)
    expect(store.activeItems).toEqual([])
    expect(store.pendingItems).toEqual([])
  })

  it('fetches memories and classifies resident and situational items', async () => {
    const mockItems = [
      { id: '1', kind: 'profile', status: 'active', key: 'grade', content: '大三' },
      { id: '2', kind: 'preference', status: 'active', key: 'lang', content: 'Python' },
      { id: '3', kind: 'fact', status: 'active', key: 'exam', content: '12月考试' },
      { id: '4', kind: 'profile', status: 'pending', key: 'major', content: '计算机科学' },
      { id: '5', kind: 'interest', status: 'active', key: 'ml', content: '机器学习' },
    ]
    api.get.mockResolvedValueOnce({
      data: {
        items: mockItems,
        config: { enabled: true, capacity: 200, has_resident_block: true, last_extracted_at: null },
      },
    })

    await store.fetchMemories()
    expect(store.items).toHaveLength(5)
    expect(store.activeItems).toHaveLength(4)
    expect(store.pendingItems).toHaveLength(1)
    expect(store.residentItems).toHaveLength(2)
    expect(store.situationalItems).toHaveLength(1)
    expect(store.interestItems).toHaveLength(1)
  })

  it('confirms a pending memory item', async () => {
    api.post.mockResolvedValueOnce({ data: { id: '4', status: 'active' } })
    api.get.mockResolvedValueOnce({
      data: {
        items: [{ id: '4', kind: 'profile', status: 'active', key: 'major', content: '计算机科学' }],
        config: { enabled: true, capacity: 200, has_resident_block: true, last_extracted_at: null },
      },
    })

    await store.confirmMemory('4')
    expect(api.post).toHaveBeenCalledWith('/memory/4/confirm')
    expect(api.get).toHaveBeenCalledWith('/memory')
  })

  it('updates configuration', async () => {
    api.put.mockResolvedValueOnce({ data: { enabled: false, capacity: 150 } })

    await store.updateConfig({ enabled: false })
    expect(api.put).toHaveBeenCalledWith('/memory/config', { enabled: false })
    expect(store.config.enabled).toBe(false)
  })

  it('deletes a memory item', async () => {
    store.items = [
      { id: '1', kind: 'profile', status: 'active', key: 'grade', content: '大三' },
      { id: '2', kind: 'fact', status: 'active', key: 'exam', content: '12月考试' },
    ]
    api.delete.mockResolvedValueOnce({ data: { message: 'ok' } })

    await store.deleteMemory('1')
    expect(api.delete).toHaveBeenCalledWith('/memory/1')
    expect(store.items).toHaveLength(1)
    expect(store.items[0].id).toBe('2')
  })
})
