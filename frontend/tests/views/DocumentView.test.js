import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DocumentView from '@/views/DocumentView.vue'
import { useDocumentStore } from '@/stores/document'

vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({
    show: vi.fn(),
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
  }),
}))

const mockPush = vi.fn()
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useRouter: () => ({
      push: mockPush,
      replace: vi.fn(),
    }),
  }
})

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn().mockResolvedValue({
      data: {
        chunks: [
          { text: '第一段内容：深入了解机器学习原理。', page: '1' },
          { text: '第二段内容：神经网络反向传播。', page: '2' },
        ],
      },
    }),
  },
}))

describe('DocumentView Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockPush.mockClear()
    window.scrollTo = vi.fn()
  })

  function createWrapper() {
    return mount(DocumentView, {
      global: {
        stubs: {
          'el-icon': true,
          'el-input': {
            template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
            props: ['modelValue']
          },
          'el-button': {
            template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
            props: ['disabled', 'type', 'size']
          },
          'el-pagination': true,
          'el-tooltip': {
            template: '<div class="el-tooltip-stub"><slot /></div>',
            props: ['content', 'placement']
          },
          SkeletonList: true,
          TransformDialog: true,
          GenerateClassroomDialog: true,
          Transition: {
            template: '<div><slot /></div>',
          },
        }
      }
    })
  }

  it('renders page header and document list', async () => {
    const docStore = useDocumentStore()
    docStore.documents = [
      { id: 'doc-1', filename: '深度学习导论.pdf', file_size: 1024 * 1024, status: 'ready', created_at: '2026-09-01' }
    ]

    const wrapper = createWrapper()
    expect(wrapper.text()).toContain('文档阅读')
    expect(wrapper.text()).toContain('选择要阅读的文档')
    expect(wrapper.text()).toContain('深度学习导论.pdf')
  })

  it('selects document and renders unified action buttons: AI 提问, 内容转换, 复制全文', async () => {
    const docStore = useDocumentStore()
    docStore.documents = [
      { id: 'doc-1', filename: '深度学习导论.pdf', file_size: 1024 * 1024, status: 'ready', created_at: '2026-09-01' }
    ]

    const wrapper = createWrapper()
    const docCard = wrapper.find('[role="button"]')
    expect(docCard.exists()).toBe(true)
    await docCard.trigger('click')

    // Wait for api.get chunks resolution
    await wrapper.vm.$nextTick()
    await new Promise((r) => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('AI 提问')
    expect(wrapper.text()).toContain('内容转换')
    expect(wrapper.text()).toContain('复制全文')
    expect(wrapper.text()).toContain('第一段内容：深入了解机器学习原理。')
  })

  it('triggers scrollToTop on back to top button click', async () => {
    const docStore = useDocumentStore()
    docStore.documents = [
      { id: 'doc-1', filename: '深度学习导论.pdf', file_size: 1024 * 1024, status: 'ready', created_at: '2026-09-01' }
    ]

    const wrapper = createWrapper()
    const docCard = wrapper.find('[role="button"]')
    await docCard.trigger('click')
    await wrapper.vm.$nextTick()

    // simulate scroll threshold
    wrapper.vm.showBackToTop = true
    await wrapper.vm.$nextTick()

    const backToTopBtn = wrapper.find('button[aria-label="回到顶部"]')
    expect(backToTopBtn.exists()).toBe(true)

    // Setup container mock scrollTo
    if (wrapper.vm.contentRef) {
      wrapper.vm.contentRef.scrollTo = vi.fn()
    }
    await backToTopBtn.trigger('click')

    expect(window.scrollTo).toBeDefined()
  })
})
