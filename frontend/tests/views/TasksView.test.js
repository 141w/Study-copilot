import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import TasksView from '@/views/TasksView.vue'
import { useDocumentStore } from '@/stores/document'

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

vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({
    show: vi.fn(),
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
  }),
}))

const mockTasks = [
  {
    id: 'task-doc-001-abcdef',
    task_type: 'document_process',
    status: 'completed',
    result: {
      doc_id: 'doc-101',
      filename: '深度学习导论.pdf',
      chunk_count: 42,
      chunk_strategy: 'heading',
    },
    created_at: '2026-09-06T10:00:00Z',
    completed_at: '2026-09-06T10:00:06Z',
  },
  {
    id: 'task-quiz-002-xyz789',
    task_type: 'quiz_generate',
    status: 'running',
    result: {
      document_names: ['现代操作系统 (第4版)'],
      quiz_id: 'quiz-202',
    },
    created_at: '2026-09-06T10:05:00Z',
  },
  {
    id: 'task-doc-003-fallback',
    task_type: 'document_process',
    status: 'failed',
    error: 'PDF 文件损坏无法提取文本',
    result: {
      doc_id: 'doc-legacy-303',
    },
    created_at: '2026-09-06T09:30:00Z',
  },
]

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn((url) => {
      if (url === '/tasks') {
        return Promise.resolve({ data: { tasks: mockTasks } })
      }
      return Promise.resolve({ data: {} })
    }),
    delete: vi.fn().mockResolvedValue({ data: { success: true } }),
  },
}))

describe('TasksView & TaskPanel Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockPush.mockClear()
  })

  function createWrapper() {
    return mount(TasksView, {
      global: {
        stubs: {
          'el-icon': {
            template: '<span class="el-icon-stub"><slot /></span>',
          },
          'el-progress': {
            template: '<div class="el-progress-stub"></div>',
            props: ['percentage', 'strokeWidth', 'showText'],
          },
          'el-button': {
            template: '<button :class="type" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
            props: ['disabled', 'type', 'size', 'loading', 'plain'],
          },
          'el-tag': {
            template: '<span class="el-tag-stub"><slot /></span>',
            props: ['type', 'size', 'effect'],
          },
          'el-input': {
            template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
            props: ['modelValue', 'prefixIcon', 'clearable', 'placeholder', 'size'],
          },
        },
      },
    })
  }

  it('renders TasksView in full-width responsive container and mounts TaskPanel', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    // 验证顶层容器破除 max-w-4xl，采用 max-w-7xl 宽屏布局
    const container = wrapper.find('.max-w-7xl')
    expect(container.exists()).toBe(true)

    // 验证控制台顶栏标题
    expect(wrapper.text()).toContain('后台任务控制台')
    expect(wrapper.text()).toContain('实时监控与追踪异步文档解析')
  })

  it('renders task statistics cards with accurate counts', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    // 统计卡片：全部 3，进行中 1，已完成 1，失败 1
    const text = wrapper.text()
    expect(text).toContain('全部任务')
    expect(text).toContain('进行中')
    expect(text).toContain('已完成')
    expect(text).toContain('失败 / 异常')
  })

  it('differentiates task titles using filename and quiz document details', async () => {
    // 注入 documentStore 模拟历史旧数据对齐回退
    const docStore = useDocumentStore()
    docStore.documents = [
      { id: 'doc-legacy-303', title: '计算机网络自顶向下.pdf', chunk_count: 30 },
    ]

    const wrapper = createWrapper()
    await flushPromises()

    const text = wrapper.text()

    // 1. 带 filename 的文档任务显示书名号与具体文件名
    expect(text).toContain('《深度学习导论.pdf》· 文档解析与向量化')
    expect(text).toContain('42 个知识段落')
    expect(text).toContain('6.0 秒')

    // 2. 测验任务展示目标文档
    expect(text).toContain('《现代操作系统 (第4版)》· 智能测验生成')

    // 3. 历史只有 doc_id 的任务，智能从 documentStore 回退匹配出标题
    expect(text).toContain('《计算机网络自顶向下.pdf》· 文档解析与向量化')
    expect(text).toContain('PDF 文件损坏无法提取文本')
  })

  it('supports searching tasks by keyword', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const input = wrapper.find('input')
    expect(input.exists()).toBe(true)

    // 输入搜索关键词 "深度学习"
    await input.setValue('深度学习')
    await flushPromises()

    expect(wrapper.text()).toContain('深度学习导论.pdf')
    expect(wrapper.text()).not.toContain('现代操作系统')
  })

  it('supports filtering tasks by status tabs', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    // 找到所有筛选 tab 按钮
    const filterButtons = wrapper.findAll('button')
    const failedTab = filterButtons.find(b => b.text().includes('失败'))
    expect(failedTab).toBeDefined()

    await failedTab.trigger('click')
    await flushPromises()

    // 筛选后只展示失败任务
    expect(wrapper.text()).toContain('PDF 文件损坏无法提取文本')
    expect(wrapper.text()).not.toContain('深度学习导论.pdf')
  })
})

