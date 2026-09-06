import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ProfileView from '@/views/ProfileView.vue'
import { useAuthStore } from '@/stores/auth'
import { useDocumentStore } from '@/stores/document'
import { useCourseStore } from '@/stores/course'
import { useNoteStore } from '@/stores/note'
import { useChatStore } from '@/stores/chat'
import { useQuizStore } from '@/stores/quiz'
import { useThemeStore } from '@/stores/theme'

vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({
    show: vi.fn(),
    error: vi.fn(),
    success: vi.fn(),
  }),
}))

vi.mock('@/components/CopilotBotAvatar.vue', () => ({
  default: {
    name: 'CopilotBotAvatar',
    template: '<div data-test="bot-avatar"></div>',
    props: ['size', 'mood', 'gaze']
  }
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
      path: '/profile',
      query: {},
    }),
  }
})

describe('ProfileView Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  function createWrapper() {
    const auth = useAuthStore()
    auth.user = {
      id: 'u1',
      username: 'AliceLearner',
      email: 'alice@example.com',
      created_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString()
    }

    const docStore = useDocumentStore()
    docStore.documents = [
      { id: 'd1', filename: 'ai_paper.pdf', file_size: 1048576, chunk_count: 12, status: 'ready', created_at: '' },
      { id: 'd2', filename: 'math_notes.docx', file_size: 2097152, chunk_count: 20, status: 'ready', created_at: '' }
    ]

    const courseStore = useCourseStore()
    courseStore.courses = [{ id: 'c1', name: '深度学习', created_at: '' }]

    const noteStore = useNoteStore()
    noteStore.notes = [{ id: 'n1', title: '注意力机制笔记', content: '...', tags: ['AI'], created_at: '', updated_at: '' }]

    const chatStore = useChatStore()
    chatStore.sessions = [
      { session_id: 's1', title: 'Transformer 研读', created_at: '', updated_at: '', message_count: 4 }
    ]

    const quizStore = useQuizStore()
    quizStore.knowledgeStats = {
      total_quizzes: 25,
      correct_count: 20,
      accuracy_rate: 80
    }

    return mount(ProfileView, {
      global: {
        stubs: {
          'router-link': {
            template: '<a><slot /></a>',
            props: ['to']
          },
          'el-tabs': {
            template: '<div><slot /></div>',
            props: ['modelValue']
          },
          'el-tab-pane': {
            template: '<div class="tab-pane"><slot /></div>',
            props: ['label', 'name']
          },
          'el-input': {
            template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
            props: ['modelValue', 'disabled']
          },
          'el-input-number': {
            template: '<input type="number" :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
            props: ['modelValue']
          },
          'el-radio-group': {
            template: '<div><slot /></div>',
            props: ['modelValue']
          },
          'el-radio-button': {
            template: '<button><slot /></button>',
            props: ['label']
          },
          'el-switch': {
            template: '<input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked); $emit(\'change\', $event.target.checked)" />',
            props: ['modelValue']
          },
          'el-button': {
            template: '<button @click="$emit(\'click\')"><slot /></button>'
          },
          'el-icon': true
        }
      }
    })
  }

  it('正确渲染个人名片信息与陪伴天数', () => {
    const wrapper = createWrapper()
    expect(wrapper.text()).toContain('AliceLearner')
    expect(wrapper.text()).toContain('alice@example.com')
    expect(wrapper.text()).toContain('陪伴学习第')
    expect(wrapper.text()).toContain('本地知识库')
  })

  it('正确计算并展示学习资产看板数据', () => {
    const wrapper = createWrapper()
    // 文档 2 篇
    expect(wrapper.text()).toContain('2')
    // 课程 1 个
    expect(wrapper.text()).toContain('1')
    // 做题 25 题，正确率 80%
    expect(wrapper.text()).toContain('25 题')
    expect(wrapper.text()).toContain('正确率 80%')
  })

  it('支持切换主题并触发 themeStore', async () => {
    const wrapper = createWrapper()
    const themeStore = useThemeStore()
    const spy = vi.spyOn(themeStore, 'setTheme')

    // 模拟点击暗色模式卡片
    const cards = wrapper.findAll('.cursor-pointer')
    // 找到包含 "暗色模式" 的元素
    const darkCard = cards.find(c => c.text().includes('暗色模式'))
    expect(darkCard).toBeTruthy()
    await darkCard?.trigger('click')

    expect(spy).toHaveBeenCalledWith('dark')
  })

  it('密码修改校验：两次密码不一致时报错', async () => {
    const wrapper = createWrapper()
    wrapper.vm.passwordForm.oldPassword = 'currentPassword'
    wrapper.vm.passwordForm.newPassword = 'password123'
    wrapper.vm.passwordForm.confirmPassword = 'mismatchedPassword'

    await wrapper.vm.handleChangePassword()
    expect(wrapper.vm.passwordError).toBe('两次输入的新密码不一致')
    expect(wrapper.vm.passwordChanged).toBe(false)
  })

  it('密码修改校验：新密码少于6位时报错', async () => {
    const wrapper = createWrapper()
    wrapper.vm.passwordForm.oldPassword = 'currentPassword'
    wrapper.vm.passwordForm.newPassword = '123'
    wrapper.vm.passwordForm.confirmPassword = '123'

    await wrapper.vm.handleChangePassword()
    expect(wrapper.vm.passwordError).toBe('新密码至少需要 6 位')
    expect(wrapper.vm.passwordChanged).toBe(false)
  })
})
