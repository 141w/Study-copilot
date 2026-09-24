import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ChunkPreviewDialog from '@/components/ChunkPreviewDialog.vue'

vi.mock('@/services/api', () => ({
  default: { post: vi.fn() },
}))

import api from '@/services/api'

describe('ChunkPreviewDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('运行预览后渲染策略链、拒绝原因与块卡片', async () => {
    api.post.mockResolvedValue({
      data: {
        selected_strategy: 'hierarchical',
        chain: ['hierarchical', 'semantic', 'fixed'],
        rejected: [{ strategy: 'semantic', reason: 'skipped in preview (would call embedder)' }],
        fallback_used: false,
        profile: {
          total_chars: 1200,
          total_lines: 40,
          md_heading_total: 4,
          dominant_heading_level: 2,
        },
        chunks: [
          { seq: 1, content: '第一块正文', page: 1, context_header: '# 章' },
          { seq: 2, content: '第二块正文', page: 1, context_header: '' },
        ],
        stats: { count: 2, avg_chars: 5, min: 5, max: 5 },
      },
    })

    const wrapper = mount(ChunkPreviewDialog, {
      props: { visible: true, initialText: '# 章\n\n内容' },
      global: { stubs: { 'el-dialog': { template: '<div><slot /></div>' }, 'el-select': true, 'el-option': true, 'el-input': true, 'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>', emits: ['click'] } } },
    })
    await flushPromises()

    // initialText 自动预览
    expect(api.post).toHaveBeenCalledWith('/documents/preview-chunking', expect.objectContaining({ strategy: 'auto' }))
    expect(wrapper.text()).toContain('hierarchical')
    expect(wrapper.text()).toContain('would call embedder')
    expect(wrapper.findAll('[data-test="preview-chunk"]').length).toBe(2)
    expect(wrapper.text()).toContain('第一块正文')
  })

  it('空文本不请求接口并提示', async () => {
    const wrapper = mount(ChunkPreviewDialog, {
      props: { visible: true, initialText: '' },
      global: { stubs: { 'el-dialog': { template: '<div><slot /></div>' }, 'el-select': true, 'el-option': true, 'el-input': true, 'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>', emits: ['click'] } } },
    })
    await flushPromises()
    const btns = wrapper.findAll('button')
    await btns[btns.length - 1].trigger('click')
    await flushPromises()
    expect(api.post).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('请先粘贴文本')
  })
})
