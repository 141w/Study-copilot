import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ChunkEditDialog from '@/components/ChunkEditDialog.vue'
import ChunkRevisionList from '@/components/ChunkRevisionList.vue'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
  },
}))

import api from '@/services/api'

const dialogStubs = {
  'el-dialog': {
    template: '<div><slot /><slot name="footer" /></div>',
    props: ['modelValue', 'title', 'width', 'destroyOnClose'],
    emits: ['update:modelValue', 'closed', 'opened'],
  },
  'el-input': {
    template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
    props: ['modelValue', 'type', 'rows', 'maxlength', 'placeholder'],
  },
  'el-button': {
    template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
    props: ['disabled', 'type', 'size', 'loading'],
    emits: ['click'],
  },
  'el-icon': true,
  Loading: true,
  CircleCheckFilled: true,
  CircleCloseFilled: true,
}

function mountEdit(props = {}) {
  return mount(ChunkEditDialog, {
    props: {
      visible: true,
      docId: 'doc-1',
      chunk: { id: 'chunk-1', content: '原文', contentRevision: 0 },
      ...props,
    },
    global: { stubs: dialogStubs },
  })
}

describe('ChunkEditDialog — 索引状态三态', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('保存后 index_status=processing 显示处理中', async () => {
    api.put.mockResolvedValue({
      data: { content: '改后', content_revision: 1, index_status: 'processing' },
    })
    const wrapper = mountEdit()
    await wrapper.find('[data-test="save-chunk"]').trigger('click')
    await flushPromises()

    expect(api.put).toHaveBeenCalledWith('/documents/doc-1/chunks/chunk-1', {
      content: '原文',
      expected_revision: 0,
    })
    expect(wrapper.find('[data-test="status-processing"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('索引处理中')
  })

  it('保存后 index_status=ready 显示就绪', async () => {
    api.put.mockResolvedValue({
      data: { content: '改后', content_revision: 1, index_status: 'ready' },
    })
    const wrapper = mountEdit()
    await wrapper.find('[data-test="save-chunk"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="status-ready"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('索引已就绪')
  })

  it('保存后 index_status=failed 显示失败并提供重试', async () => {
    api.put.mockResolvedValue({
      data: { content: '改后', content_revision: 1, index_status: 'failed', error: 'embed boom' },
    })
    const wrapper = mountEdit()
    await wrapper.find('[data-test="save-chunk"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="status-failed"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('索引失败')
    expect(wrapper.find('[data-test="retry-index"]').exists()).toBe(true)

    // 重试 → ready
    api.put.mockResolvedValue({
      data: { content: '改后', content_revision: 1, index_status: 'ready' },
    })
    await wrapper.find('[data-test="retry-index"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-test="status-ready"]').exists()).toBe(true)
  })

  it('409 版本冲突显示冲突提示', async () => {
    api.put.mockRejectedValue({
      response: { status: 409, data: { detail: '版本冲突：期望 revision=0，当前为 2' } },
    })
    const wrapper = mountEdit()
    await wrapper.find('[data-test="save-chunk"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="edit-conflict"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('版本冲突')
  })
})

describe('ChunkRevisionList — 版本列表', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('渲染版本列表并支持一键回滚', async () => {
    api.get.mockResolvedValue({
      data: [
        { id: 'r2', revision: 2, content: 'V0 再次', edited_at: '2026-09-26 12:00:00' },
        { id: 'r1', revision: 1, content: 'V1 版本', edited_at: '2026-09-26 11:00:00' },
        { id: 'r0', revision: 0, content: 'V0 原始', edited_at: '2026-09-26 10:00:00' },
      ],
    })
    api.post.mockResolvedValue({
      data: { content: 'V0 原始', content_revision: 3, index_status: 'ready' },
    })

    const wrapper = mount(ChunkRevisionList, {
      props: { visible: true, docId: 'doc-1', chunkId: 'chunk-1' },
      global: { stubs: dialogStubs },
    })
    await flushPromises()

    expect(api.get).toHaveBeenCalledWith('/documents/doc-1/chunks/chunk-1/revisions')
    const items = wrapper.findAll('[data-test="revision-item"]')
    expect(items.length).toBe(3)
    expect(wrapper.text()).toContain('revision 0')
    expect(wrapper.text()).toContain('V0 原始')

    await wrapper.find('[data-test="revert-btn"]').trigger('click')
    await flushPromises()
    expect(api.post).toHaveBeenCalledWith('/documents/doc-1/chunks/chunk-1/revert', {
      revision: 2,
    })
    expect(wrapper.emitted('reverted')?.[0]?.[0]).toMatchObject({
      content: 'V0 原始',
      contentRevision: 3,
      indexStatus: 'ready',
    })
  })

  it('无历史版本时显示空态', async () => {
    api.get.mockResolvedValue({ data: [] })
    const wrapper = mount(ChunkRevisionList, {
      props: { visible: true, docId: 'doc-1', chunkId: 'chunk-1' },
      global: { stubs: dialogStubs },
    })
    await flushPromises()
    expect(wrapper.find('[data-test="revision-empty"]').exists()).toBe(true)
  })
})
