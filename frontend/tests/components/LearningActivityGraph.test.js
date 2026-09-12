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

  it('无数据时仍渲染满年灰底格（对齐原组件 emptyDays）', async () => {
    api.get.mockResolvedValue({
      data: { days: 365, total: 0, active_days: 0, contributions: [] },
    })

    const wrapper = mount(LearningActivityGraph, {
      props: { days: 365, cellSize: 11 },
      global: { stubs: { Teleport: true } },
    })
    await flushPromises()

    expect(wrapper.find('[data-test="learning-activity"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('0 contributions')
    // 每一格都是灰底 + 透明度 0 叠层
    const cells = wrapper.findAll('[data-test="activity-cell"]')
    expect(cells.length).toBeGreaterThanOrEqual(365)
    expect(cells[0].classes()).toContain('activity-cell')
  })

  it('有贡献时叠层透明度非 0，标题含总数', async () => {
    const contributions = Array.from({ length: 28 }, (_, i) => ({
      date: `2026-08-${String((i % 28) + 1).padStart(2, '0')}`,
      count: i === 27 ? 5 : 0,
      level: i === 27 ? 4 : 0,
    }))
    api.get.mockResolvedValue({
      data: { days: 28, total: 5, active_days: 1, contributions },
    })

    const wrapper = mount(LearningActivityGraph, {
      props: { days: 28, cellSize: 10, accent: '#39d353' },
      global: { stubs: { Teleport: true } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('5 contributions')
    const overlays = wrapper.findAll('[data-test="activity-level"]')
    expect(overlays.length).toBeGreaterThanOrEqual(28)
    const opacities = overlays.map(el => el.attributes('style') || '')
    expect(opacities.some(s => /opacity:\s*1(?:;|$)/.test(s))).toBe(true)
  })

  it('接口失败时静默用 emptyDays', async () => {
    api.get.mockRejectedValue(new Error('network'))
    const wrapper = mount(LearningActivityGraph, {
      props: { days: 30 },
      global: { stubs: { Teleport: true } },
    })
    await flushPromises()
    expect(wrapper.find('[data-test="learning-activity"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('0 contributions')
  })
})
