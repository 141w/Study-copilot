import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOpenMAICStore } from '@/stores/openmaic'
import api from '@/services/api'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

describe('OpenMAIC Store', () => {
  let store: ReturnType<typeof useOpenMAICStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useOpenMAICStore()
    vi.clearAllMocks()
  })

  it('fetchClassrooms loads and caches classrooms', async () => {
    const mockClassrooms = [
      { course_id: 'c-1', title: '线性代数课堂', url: 'https://open.maic.chat/c/1', created_at: '2026-09-05' },
    ]
    ;(api.get as any).mockResolvedValueOnce({ data: { classrooms: mockClassrooms } })

    await store.fetchClassrooms()
    expect(store.classrooms).toHaveLength(1)
    expect(store.classrooms[0].title).toBe('线性代数课堂')
    expect(api.get).toHaveBeenCalledWith('/integrations/openmaic/classrooms')

    // 第二次调用因缓存跳过
    await store.fetchClassrooms()
    expect(api.get).toHaveBeenCalledTimes(1)

    // force = true 强制刷新
    ;(api.get as any).mockResolvedValueOnce({ data: { classrooms: mockClassrooms } })
    await store.fetchClassrooms(true)
    expect(api.get).toHaveBeenCalledTimes(2)
  })

  it('getClassroom retrieves a specific classroom by course_id', async () => {
    store.classrooms = [
      { course_id: 'c-100', title: '微积分', url: 'https://open.maic.chat/c/100', created_at: '2026-09-05' },
    ]
    const found = store.getClassroom('c-100')
    expect(found?.title).toBe('微积分')
    expect(store.getClassroom('non-existent')).toBeUndefined()
  })

  it('pollJobStatus tracks job progress and auto-refreshes when done', async () => {
    const mockStatusRunning = {
      job_id: 'job-1',
      status: 'running',
      step: 'generating_scenes',
      progress: 0.5,
      message: '生成中',
      scenes_generated: 2,
      total_scenes: 4,
      done: false,
    }
    ;(api.get as any).mockResolvedValueOnce({ data: mockStatusRunning })

    const status1 = await store.pollJobStatus('job-1')
    expect(status1.done).toBe(false)
    expect(store.activeJobs['job-1']?.step).toBe('generating_scenes')

    const mockStatusDone = {
      job_id: 'job-1',
      status: 'succeeded',
      step: 'completed',
      progress: 1.0,
      message: '完成',
      scenes_generated: 4,
      total_scenes: 4,
      done: true,
      result: { url: 'https://open.maic.chat/c/job-1' },
    }
    ;(api.get as any)
      .mockResolvedValueOnce({ data: mockStatusDone }) // for poll status
      .mockResolvedValueOnce({ data: { classrooms: [{ course_id: 'c-new', title: '新课', url: '...', created_at: '...' }] } }) // for auto-refresh classrooms

    const status2 = await store.pollJobStatus('job-1')
    expect(status2.done).toBe(true)
    expect(store.activeJobs['job-1']?.status).toBe('succeeded')
    // 验证任务完成后已触发课堂列表刷新
    expect(store.classrooms).toHaveLength(1)
  })
})
