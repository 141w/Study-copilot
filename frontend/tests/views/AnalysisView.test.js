import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AnalysisView from '@/views/AnalysisView.vue'
import { useQuizStore } from '@/stores/quiz'
import { useClassroomStore } from '@/stores/classroom'

vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({
    show: vi.fn(),
    error: vi.fn(),
    success: vi.fn(),
  }),
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useRouter: () => ({
      push: vi.fn(),
      replace: vi.fn(),
    }),
    useRoute: () => ({
      path: '/analysis',
      query: {},
    }),
  }
})

describe('AnalysisView Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  function createWrapper() {
    return mount(AnalysisView, {
      global: {
        stubs: {
          'el-tabs': {
            template: '<div class="el-tabs"><slot /></div>',
            props: ['modelValue']
          },
          'el-tab-pane': true,
          'el-icon': true,
          'el-button': {
            template: '<button :disabled="loading" @click="$emit(\'click\')"><slot /></button>',
            props: ['loading', 'type', 'size', 'plain']
          },
          SkeletonList: {
            template: '<div data-test="skeleton-list" :data-variant="variant"></div>',
            props: ['variant', 'count']
          }
        }
      }
    })
  }

  it('mounts successfully and renders header and refresh button', async () => {
    const wrapper = createWrapper()
    expect(wrapper.text()).toContain('学习分析')
    expect(wrapper.text()).toContain('刷新数据')
  })

  it('renders history items grouped by date correctly', async () => {
    const quizStore = useQuizStore()
    quizStore.quizResults = [
      {
        quiz_id: 'q1',
        question: '什么是注意力机制？',
        user_answer: 'A',
        correct_answer: 'A',
        is_correct: true,
        submitted_at: '2026-09-05 10:00:00'
      },
      {
        quiz_id: 'q2',
        question: 'Transformer 的输入是什么？',
        user_answer: 'B',
        correct_answer: 'C',
        is_correct: false,
        submitted_at: '2026-09-05 10:05:00'
      }
    ]

    const wrapper = createWrapper()
    expect(wrapper.text()).toContain('什么是注意力机制？')
    expect(wrapper.text()).toContain('Transformer 的输入是什么？')
    expect(wrapper.text()).toContain('2 道题')
    expect(wrapper.text()).toContain('正确率: 50%')
  })

  it('switches to stats tab and renders stats exclusively', async () => {
    const quizStore = useQuizStore()
    quizStore.knowledgeStats = {
      total_quizzes: 10,
      correct_count: 8,
      accuracy_rate: 80
    }
    quizStore.weakAreas = [
      {
        topic: '注意力机制',
        wrong_count: 2,
        total_count: 10,
        accuracy_rate: 80
      }
    ]

    const wrapper = createWrapper()
    // 切换到 stats Tab
    wrapper.vm.activeTab = 'stats'
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('整体掌握情况')
    expect(wrapper.text()).toContain('总做题数')
    expect(wrapper.text()).toContain('知识点掌握情况')
    expect(wrapper.text()).toContain('注意力机制')
    // 确保课堂学习内容没有混入
    expect(wrapper.text()).not.toContain('暂无课堂记录')
  })

  it('switches to classroom tab and renders classroom exclusively', async () => {
    const classroomStore = useClassroomStore()
    classroomStore.classrooms = [
      {
        course_id: 'c1',
        title: '深度学习课堂',
        url: 'https://classroom.example.com/c1',
        created_at: '2026-09-05T10:00:00Z'
      }
    ]

    const wrapper = createWrapper()
    wrapper.vm.activeTab = 'classroom'
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('深度学习课堂')
    expect(wrapper.text()).toContain('进入课堂')
    // 确保统计概览内容没有混入
    expect(wrapper.text()).not.toContain('整体掌握情况')
    expect(wrapper.text()).not.toContain('重新分析错题')
  })
})
