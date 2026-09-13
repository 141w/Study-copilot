import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUsageStore } from '@/stores/usage'
import api from '@/services/api'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

describe('Usage Store', () => {
  let store: ReturnType<typeof useUsageStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useUsageStore()
    vi.clearAllMocks()
  })

  it('initializes with default values', () => {
    expect(store.dashboard).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.syncing).toBe(false)
    expect(store.days).toBe(30)
    expect(store.sourceFilter).toBe('all')
    expect(store.totals.total_tokens).toBe(0)
    expect(store.dailyTrend).toEqual([])
    expect(store.byModel).toEqual([])
  })

  it('fetches dashboard data and computes properties accurately', async () => {
    const mockData = {
      totals: {
        total_tokens: 35000,
        prompt_tokens: 10000,
        completion_tokens: 25000,
        chat_tokens: 5000,
        classroom_tokens: 30000,
        other_tokens: 0,
        requests: 12,
      },
      summary: {
        total_tokens: 35000,
        prompt_tokens: 10000,
        completion_tokens: 25000,
        chat_tokens: 5000,
        classroom_tokens: 30000,
        other_tokens: 0,
        requests: 12,
      },
      by_source: [
        { source: 'classroom', label: 'AI 互动课堂生成', tokens: 30000, requests: 10 },
        { source: 'chat', label: 'AI 问答与对话', tokens: 5000, requests: 2 },
      ],
      by_kind: [
        { kind: 'llm', label: '大语言模型 (Tokens)', tokens: 35000, quantity: 35000, unit: 'token', requests: 10 },
        { kind: 'image', label: '课件插图生成 (张)', tokens: 0, quantity: 2, unit: 'image', requests: 2 },
      ],
      by_model: [
        {
          model_name: 'step-3.7-flash',
          provider: 'stepfun',
          kind: 'llm',
          requests: 10,
          prompt_tokens: 8000,
          completion_tokens: 22000,
          total_tokens: 30000,
          quantity: 30000,
          unit: 'token',
        },
      ],
      by_day: [
        { date: '2026-09-12', total_tokens: 15000, chat_tokens: 5000, classroom_tokens: 10000, other_tokens: 0, requests: 5 },
        { date: '2026-09-13', total_tokens: 20000, chat_tokens: 0, classroom_tokens: 20000, other_tokens: 0, requests: 7 },
      ],
      recent_records: [
        {
          id: 'rec-1',
          created_at: '2026-09-13T12:00:00',
          source: 'classroom',
          source_label: 'AI 互动课堂生成',
          kind: 'llm',
          provider: 'stepfun',
          model_name: 'step-3.7-flash',
          prompt_tokens: 1000,
          completion_tokens: 2000,
          total_tokens: 3000,
          quantity: 3000,
          unit: 'token',
        },
      ],
    }

    vi.mocked(api.get).mockResolvedValueOnce({ data: mockData })

    await store.fetchDashboard(7, 'classroom')
    expect(api.get).toHaveBeenCalledWith('/usage/dashboard?days=7&source=classroom')
    expect(store.days).toBe(7)
    expect(store.sourceFilter).toBe('classroom')
    expect(store.totals.total_tokens).toBe(35000)
    expect(store.totals.classroom_tokens).toBe(30000)
    expect(store.totals.chat_tokens).toBe(5000)
    expect(store.dailyTrend).toHaveLength(2)
    expect(store.byModel).toHaveLength(1)
    expect(store.recentRecords).toHaveLength(1)
  })

  it('syncs classroom usage and re-fetches dashboard', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ data: { status: 'success', synced_count: 5, message: '成功同步 5 条' } })
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        totals: { total_tokens: 5000, prompt_tokens: 2000, completion_tokens: 3000, chat_tokens: 0, classroom_tokens: 5000, other_tokens: 0, requests: 5 },
        by_source: [],
        by_kind: [],
        by_model: [],
        by_day: [],
        recent_records: [],
      },
    })

    const res = await store.syncClassroom()
    expect(api.post).toHaveBeenCalledWith('/usage/sync')
    expect(api.get).toHaveBeenCalled()
    expect(res.synced_count).toBe(5)
  })
})
