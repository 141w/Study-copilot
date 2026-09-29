import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
  cancelAll: vi.fn(),
}))

import ParseTimeline from '@/components/ParseTimeline.vue'
import api from '@/services/api'

const sample = {
  spans: [
    { id: 'r', kind: 'root', name: 'process', status: 'done', started_at: null, ended_at: null },
    { id: '1', kind: 'stage', name: 'parse', status: 'done', started_at: '2026-09-28T00:00:00', ended_at: '2026-09-28T00:00:01', detail: '3 pages', error: null, attempt: 1 },
    { id: '2', kind: 'stage', name: 'chunk', status: 'failed', started_at: '2026-09-28T00:00:01', ended_at: '2026-09-28T00:00:02', detail: null, error: '内容不足', attempt: 1 },
    { id: '3', kind: 'stage', name: 'embed', status: 'cancelled', started_at: null, ended_at: null, detail: null, error: null, attempt: 1 }
  ]
}

describe('ParseTimeline（阶段三）', () => {
  beforeEach(() => vi.clearAllMocks())

  it('展开后渲染阶段状态', async () => {
    api.get.mockResolvedValue({ data: sample })
    const w = mount(ParseTimeline, {
      props: { docId: 'd1' },
      global: { stubs: { 'el-icon': true } }
    })
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    await w.find('[data-test="parse-timeline"] button').trigger('click')
    await w.vm.$nextTick()
    expect(w.find('[data-test="span-parse"]').attributes('data-status')).toBe('done')
    expect(w.find('[data-test="span-chunk"]').attributes('data-status')).toBe('failed')
    expect(w.find('[data-test="span-embed"]').attributes('data-status')).toBe('cancelled')
    expect(w.text()).toContain('内容不足')
    expect(w.text()).toContain('2/4 阶段完成')  // root+3 stage，done=2
  })

  it('旧文档无 span 时降级提示', async () => {
    api.get.mockResolvedValue({ data: { spans: [] } })
    const w = mount(ParseTimeline, {
      props: { docId: 'd2' },
      global: { stubs: { 'el-icon': true } }
    })
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    await w.find('button').trigger('click')
    await w.vm.$nextTick()
    expect(w.text()).toContain('旧文档暂无阶段记录')
  })
})
