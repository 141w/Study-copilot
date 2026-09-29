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

/**
 * F2 · ParseTimeline 四态与计数（fix(phase2-audit): F2）
 * 原实现把 root 计入「n/m 阶段完成」，成功时显示 6/6 误导；
 * 取消/跳过无「未执行（上游失败）」文案；阶段中文名与规格不一致。
 */
describe('ParseTimeline F2 视觉规格', () => {
  beforeEach(() => vi.clearAllMocks())

  async function mountOpen(data) {
    api.get.mockResolvedValue({ data })
    const w = mount(ParseTimeline, {
      props: { docId: 'dx' },
      global: { stubs: { 'el-icon': true } }
    })
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    await w.find('[data-test="parse-timeline"] button').trigger('click')
    await w.vm.$nextTick()
    return w
  }

  it('顶部计数只统计 stage，不含 root', async () => {
    const w = await mountOpen(sample)
    // stage: parse=done, chunk=failed, embed=cancelled → 1/3
    // 原实现把 root 算进去会显示 2/4
    expect(w.text()).toContain('1/3')
    expect(w.text()).not.toContain('2/4')
  })

  it('阶段中文名映射符合规格，不出现英文枚举名', async () => {
    const w = await mountOpen({
      spans: [
        { id: '1', kind: 'stage', name: 'parse', status: 'done', started_at: '2026-09-28T00:00:00', ended_at: '2026-09-28T00:00:01', detail: null, error: null, attempt: 1 },
        { id: '2', kind: 'stage', name: 'profile', status: 'done', started_at: '2026-09-28T00:00:01', ended_at: '2026-09-28T00:00:02', detail: null, error: null, attempt: 1 },
        { id: '3', kind: 'stage', name: 'chunk', status: 'done', started_at: '2026-09-28T00:00:02', ended_at: '2026-09-28T00:00:03', detail: null, error: null, attempt: 1 },
        { id: '4', kind: 'stage', name: 'embed', status: 'done', started_at: '2026-09-28T00:00:03', ended_at: '2026-09-28T00:00:04', detail: null, error: null, attempt: 1 },
        { id: '5', kind: 'stage', name: 'index', status: 'done', started_at: '2026-09-28T00:00:04', ended_at: '2026-09-28T00:00:05', detail: null, error: null, attempt: 1 },
        { id: '6', kind: 'stage', name: 'finalize', status: 'done', started_at: '2026-09-28T00:00:05', ended_at: '2026-09-28T00:00:06', detail: null, error: null, attempt: 1 }
      ]
    })
    const text = w.text()
    expect(text).toContain('文本解析')
    expect(text).toContain('文档画像')
    expect(text).toContain('分块')
    expect(text).toContain('向量化')
    expect(text).toContain('索引写入')
    expect(text).toContain('完成入库')
    // 不得出现英文枚举名（作为阶段标题）
    expect(text).not.toMatch(/\bparse\b/)
    expect(text).not.toMatch(/\bfinalize\b/)
  })

  it('取消态文案为「未执行（上游失败）」，带虚线视觉', async () => {
    const w = await mountOpen(sample)
    const cancelled = w.find('[data-test="span-embed"]')
    expect(cancelled.exists()).toBe(true)
    expect(cancelled.text()).toContain('未执行（上游失败）')
    expect(cancelled.attributes('data-status')).toBe('cancelled')
  })

  it('失败态展开错误原因', async () => {
    const w = await mountOpen(sample)
    const failed = w.find('[data-test="span-chunk"]')
    expect(failed.text()).toContain('内容不足')
    expect(failed.attributes('data-status')).toBe('failed')
  })

  it('默认只渲染最近 attempt', async () => {
    const w = await mountOpen({
      spans: [
        { id: 'r1', kind: 'root', name: 'process', status: 'failed', started_at: null, ended_at: null, attempt: 1 },
        { id: 'a1', kind: 'stage', name: 'parse', status: 'failed', started_at: '2026-09-28T00:00:00', ended_at: '2026-09-28T00:00:01', detail: null, error: '旧错误', attempt: 1 },
        { id: 'r2', kind: 'root', name: 'process', status: 'done', started_at: null, ended_at: null, attempt: 2 },
        { id: 'b1', kind: 'stage', name: 'parse', status: 'done', started_at: '2026-09-29T00:00:00', ended_at: '2026-09-29T00:00:01', detail: 'ok', error: null, attempt: 2 }
      ]
    })
    // 只应出现 attempt=2 的记录
    expect(w.find('[data-test="span-parse"]').attributes('data-status')).toBe('done')
    expect(w.text()).not.toContain('旧错误')
    expect(w.text()).not.toContain('attempt 1')
  })
})
