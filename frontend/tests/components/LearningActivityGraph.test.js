import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import LearningActivityGraph from '@/components/profile/LearningActivityGraph.vue'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
  },
}))

import api from '@/services/api'

describe('LearningActivityGraph', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('加载并渲染贡献图摘要与格子', async () => {
    const contributions = Array.from({ length: 28 }, (_, i) => ({
      date: `2026-08-${String((i % 28) + 1).padStart(2, '0')}`,
      count: i % 5,
      level: i % 5,
    }))
    api.get.mockResolvedValue({
      data: { days: 28, total: 42, active_days: 12, contributions },
    })

    const wrapper = mount(LearningActivityGraph, {
      props: { days: 28, cellSize: 10 },
      global: { stubs: { Teleport: true } },
    })
    await flushPromises()

    expect(api.get).toHaveBeenCalledWith('/analysis/activity', { params: { days: 28 } })
    expect(wrapper.text()).toContain('学习活动')
    expect(wrapper.text()).toContain('42 次学习行为')
    expect(wrapper.find('[data-test="learning-activity"]').exists()).toBe(true)
  })

  it('接口失败时静默为空图', async () => {
    api.get.mockRejectedValue(new Error('network'))
    const wrapper = mount(LearningActivityGraph, {
      props: { days: 30 },
      global: { stubs: { Teleport: true } },
    })
    await flushPromises()
    expect(wrapper.find('[data-test="learning-activity"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('0 次学习行为')
  })
})
