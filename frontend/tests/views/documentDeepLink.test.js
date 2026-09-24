import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ChatMessageItem from '@/components/chat/ChatMessageItem.vue'
import DocumentView from '@/views/DocumentView.vue'

const mockPush = vi.fn()
/** 可变 route.query，便于兼容参数场景 */
const routeQuery = { doc: 'doc-42', page: '3', q: '梯度下降' }
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => ({
    path: '/documents',
    query: routeQuery,
  }),
}))

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: { chunks: [{ text: '梯度下降是一种优化算法', page: 3 }] } }),
  },
}))

import api from '@/services/api'
import { useDocumentStore } from '@/stores/document'
import { useToastStore } from '@/stores/toast'

describe('来源卡 → 文档深链（统一 ?doc=）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockPush.mockClear()
    vi.clearAllMocks()
    api.get.mockResolvedValue({ data: { chunks: [{ text: '梯度下降是一种优化算法', page: 3 }] } })
  })

  it('ChatMessageItem 打开原文使用 doc 而非 document_id', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        message: {
          id: 'm1',
          role: 'assistant',
          content: '答案 [来源1]',
          sources: [
            { index: 1, source: 'ml.pdf', page: '3', text: '梯度下降是一种优化算法', document_id: 'doc-42' },
          ],
          isStreaming: false,
          created_at: new Date().toISOString(),
        },
      },
      global: {
        stubs: {
          CopilotBotAvatar: true,
          TTSPlayer: true,
          'el-icon': true,
          'el-button': true,
        },
      },
    })
    await wrapper.vm.$nextTick()
    // 展开来源区
    await wrapper.find('[data-test="sources-toggle"]').trigger('click')
    await wrapper.vm.$nextTick()
    // 展开单卡正文以露出「打开原文」
    await wrapper.find('[data-test="source-card-toggle-1"]').trigger('click')
    await wrapper.vm.$nextTick()
    await wrapper.find('[data-test="source-card-open-doc"]').trigger('click')

    expect(mockPush).toHaveBeenCalled()
    const arg = mockPush.mock.calls[0][0]
    expect(arg.name).toBe('documents')
    expect(arg.query.doc).toBe('doc-42')
    expect(arg.query.document_id).toBeUndefined()
    expect(arg.query.page).toBe('3')
  })

  it('DocumentView 带 ?doc= 挂载后选中对应文档并加载切片', async () => {
    const documentStore = useDocumentStore()
    const toast = useToastStore()
    vi.spyOn(documentStore, 'fetchDocuments').mockImplementation(async () => {
      documentStore.documents = [
        { id: 'doc-42', filename: 'ml.pdf', status: 'ready', file_size: 10, chunk_count: 1 },
        { id: 'other', filename: 'x.pdf', status: 'ready', file_size: 1, chunk_count: 0 },
      ]
      return documentStore.documents
    })
    const errSpy = vi.spyOn(toast, 'error')

    const wrapper = mount(DocumentView, {
      global: {
        stubs: {
          TransformDialog: true,
          GenerateClassroomDialog: true,
          SkeletonList: true,
          'el-button': true,
          'el-icon': true,
          'el-pagination': true,
          RouterLink: true,
        },
      },
    })
    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(documentStore.fetchDocuments).toHaveBeenCalled()
    // 选中深链文档
    expect(wrapper.text()).toContain('ml.pdf')
    expect(api.get).toHaveBeenCalledWith('/documents/doc-42')
    expect(errSpy).not.toHaveBeenCalled()
  })

  it('DocumentView 找不到文档时 toast 提示，不静默', async () => {
    const documentStore = useDocumentStore()
    const toast = useToastStore()
    vi.spyOn(documentStore, 'fetchDocuments').mockImplementation(async () => {
      documentStore.documents = [
        { id: 'other', filename: 'x.pdf', status: 'ready', file_size: 1, chunk_count: 0 },
      ]
      return documentStore.documents
    })
    const errSpy = vi.spyOn(toast, 'error')

    mount(DocumentView, {
      global: {
        stubs: {
          TransformDialog: true,
          GenerateClassroomDialog: true,
          SkeletonList: true,
          'el-button': true,
          'el-icon': true,
          'el-pagination': true,
        },
      },
    })
    await flushPromises()
    expect(errSpy).toHaveBeenCalledWith('未找到对应文档')
  })

  it('DocumentView 兼容旧参数 document_id 深链', async () => {
    const documentStore = useDocumentStore()
    vi.spyOn(documentStore, 'fetchDocuments').mockImplementation(async () => {
      documentStore.documents = [
        { id: 'legacy-1', filename: 'legacy.pdf', status: 'ready', file_size: 2, chunk_count: 1 },
      ]
      return documentStore.documents
    })
    // 只给 document_id，不给 doc
    routeQuery.doc = undefined
    routeQuery.document_id = 'legacy-1'
    try {
      const wrapper = mount(DocumentView, {
        global: {
          stubs: {
            TransformDialog: true,
            GenerateClassroomDialog: true,
            SkeletonList: true,
            'el-button': true,
            'el-icon': true,
            'el-pagination': true,
          },
        },
      })
      await flushPromises()
      expect(wrapper.text()).toContain('legacy.pdf')
      expect(api.get).toHaveBeenCalledWith('/documents/legacy-1')
    } finally {
      routeQuery.doc = 'doc-42'
      delete routeQuery.document_id
    }
  })

  it('切片操作按钮文案为「基于本文出题」（与整文档出题一致）', async () => {
    const documentStore = useDocumentStore()
    vi.spyOn(documentStore, 'fetchDocuments').mockImplementation(async () => {
      documentStore.documents = [
        { id: 'doc-42', filename: 'ml.pdf', status: 'ready', file_size: 10, chunk_count: 1 },
      ]
      return documentStore.documents
    })

    const wrapper = mount(DocumentView, {
      global: {
        stubs: {
          TransformDialog: true,
          GenerateClassroomDialog: true,
          SkeletonList: true,
          'el-button': { template: '<button><slot /></button>' },
          'el-icon': true,
          'el-pagination': true,
        },
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('基于本文出题')
    expect(wrapper.text()).not.toContain('基于此段出题')
  })
})
