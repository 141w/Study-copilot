import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ClassroomPlayerView from '@/views/ClassroomPlayerView.vue'
import { useClassroomStore } from '@/stores/classroom'

const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { id: 'course-cls-101' }
  }),
  useRouter: () => ({
    push: mockPush,
  }),
}))

const mockClassroomData = {
  id: 'course-cls-101',
  stage: {
    name: 'Vue3 响应式原理深度微课',
    description: '深入理解 Proxy 与 Reflect',
    generatedAgentConfigs: [
      { id: 'teacher', name: '苏老师', role: '主讲导师', color: '#3B82F6' },
      { id: 'curious', name: '求知同学', role: '探索学员', color: '#F59E0B' },
      { id: 'thinker', name: '学霸', role: '深度思考者', color: '#10B981' },
    ]
  },
  scenes: [
    {
      id: 'sc-1',
      title: '导论：响应式系统演进',
      type: 'slide',
      content: {
        canvas: {
          theme: { backgroundColor: '#0F172A', fontColor: '#FFFFFF' },
          elements: [
            { id: 'el-1', type: 'text', content: 'Vue3 响应式原理深度微课', fontSize: 28, left: 60, top: 60, width: 800, height: 60 },
            { id: 'el-2', type: 'shape', text: '【学习目标】深入掌握 Proxy 机制', fill: '#1E293B', left: 60, top: 150, width: 800, height: 100 }
          ]
        }
      },
      actions: [
        { id: 'act-1', type: 'speech', agentId: 'teacher', text: '欢迎来到本节微课，今天我们学习响应式原理。' },
        { id: 'act-2', type: 'speech', agentId: 'curious', text: '请问老师，Proxy 和 defineProperty 相比优势在哪里？' }
      ]
    },
    {
      id: 'sc-2',
      title: '随堂测验：Proxy 基础',
      type: 'quiz',
      quiz: {
        question: 'Vue 3 为何使用 Proxy 替代 Object.defineProperty？',
        type: 'single_choice',
        options: [
          '无法拦截属性的新增与删除',
          '代码量更小',
          '完全废弃了 JavaScript 对象',
          '不需要浏览器支持'
        ],
        answer: '无法拦截属性的新增与删除',
        explanation: 'Object.defineProperty 无法原生感知新增和删除属性，需要借助 $set API。'
      },
      actions: [
        { id: 'act-q1', type: 'speech', agentId: 'teacher', text: '请根据前面的讲解完成这道测验题。' }
      ]
    }
  ]
}

describe('ClassroomPlayerView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockPush.mockClear()
    // 模拟 window.speechSynthesis
    window.speechSynthesis = {
      speak: vi.fn(),
      cancel: vi.fn(),
      pause: vi.fn(),
      resume: vi.fn(),
    }
  })

  it('正确加载并渲染微课标题与第一幕内容', async () => {
    const classroomStore = useClassroomStore()
    vi.spyOn(classroomStore, 'fetchClassroomDetail').mockResolvedValue(mockClassroomData)

    const wrapper = mount(ClassroomPlayerView, {
      global: {
        stubs: {
          'el-button': { template: '<button><slot /></button>' },
          'el-icon': { template: '<i><slot /></i>' },
          'el-drawer': { template: '<div><slot /></div>' }
        }
      }
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Vue3 响应式原理深度微课')
    expect(wrapper.text()).toContain('第 1 / 2 幕')
    expect(wrapper.text()).toContain('苏老师')
    expect(wrapper.text()).toContain('欢迎来到本节微课，今天我们学习响应式原理。')
    expect(wrapper.text()).toContain('【学习目标】深入掌握 Proxy 机制')
  })

  it('支持上一句/下一句动作切换与切幕', async () => {
    const classroomStore = useClassroomStore()
    vi.spyOn(classroomStore, 'fetchClassroomDetail').mockResolvedValue(mockClassroomData)

    const wrapper = mount(ClassroomPlayerView, {
      global: {
        stubs: {
          'el-button': { template: '<button><slot /></button>' },
          'el-icon': { template: '<i><slot /></i>' },
          'el-drawer': { template: '<div><slot /></div>' }
        }
      }
    })

    await flushPromises()

    // 初始处于 action 0 (苏老师)
    expect(wrapper.text()).toContain('苏老师')

    // 找到包含 下一句/下一幕 标题的按钮并触发
    const buttons = wrapper.findAll('button')
    const nextBtn = buttons.find(b => b.attributes('title') === '下一句/下一幕')
    expect(nextBtn).toBeDefined()
    await nextBtn.trigger('click')

    // 切换到 action 1 (求知同学)
    expect(wrapper.text()).toContain('求知同学')
    expect(wrapper.text()).toContain('请问老师，Proxy 和 defineProperty 相比优势在哪里？')

    // 再次点击进入下一幕 (Quiz)
    await nextBtn.trigger('click')
    expect(wrapper.text()).toContain('随堂挑战')
    expect(wrapper.text()).toContain('Vue 3 为何使用 Proxy 替代 Object.defineProperty？')
  })

  it('测验场景支持答题、即时正误反馈与解析展开', async () => {
    const classroomStore = useClassroomStore()
    vi.spyOn(classroomStore, 'fetchClassroomDetail').mockResolvedValue(mockClassroomData)

    const wrapper = mount(ClassroomPlayerView, {
      global: {
        stubs: {
          'el-button': { template: '<button><slot /></button>' },
          'el-icon': { template: '<i><slot /></i>' },
          'el-drawer': { template: '<div><slot /></div>' }
        }
      }
    })

    await flushPromises()

    // 跳转到第二幕 (Quiz)
    const sidebarItems = wrapper.findAll('aside .cursor-pointer')
    if (sidebarItems.length > 1) {
      await sidebarItems[1].trigger('click')
    }

    expect(wrapper.text()).toContain('Vue 3 为何使用 Proxy 替代 Object.defineProperty？')

    // 查找选项按钮并点击正确选项
    const optBtns = wrapper.findAll('main button').filter(b => b.text().includes('无法拦截属性的新增与删除'))
    expect(optBtns.length).toBeGreaterThan(0)
    await optBtns[0].trigger('click')

    // 验证反馈结果
    expect(wrapper.text()).toContain('✓ 回答正确！')
    expect(wrapper.text()).toContain('Object.defineProperty 无法原生感知新增和删除属性')
  })

  it('加载失败时渲染错误提示与重试按钮', async () => {
    const classroomStore = useClassroomStore()
    vi.spyOn(classroomStore, 'fetchClassroomDetail').mockRejectedValue(new Error('网络连接超时'))

    const wrapper = mount(ClassroomPlayerView, {
      global: {
        stubs: {
          'el-button': { template: '<button><slot /></button>' },
          'el-icon': { template: '<i><slot /></i>' },
          'el-drawer': { template: '<div><slot /></div>' }
        }
      }
    })

    await flushPromises()

    expect(wrapper.text()).toContain('课件未找到或已被移除')
    expect(wrapper.text()).toContain('网络连接超时')
  })

  it('支持播放倍速循环切换与语音静音切换', async () => {
    const classroomStore = useClassroomStore()
    vi.spyOn(classroomStore, 'fetchClassroomDetail').mockResolvedValue(mockClassroomData)

    const wrapper = mount(ClassroomPlayerView, {
      global: {
        stubs: {
          'el-button': { template: '<button><slot /></button>' },
          'el-icon': { template: '<i><slot /></i>' },
          'el-drawer': { template: '<div><slot /></div>' }
        }
      }
    })

    await flushPromises()

    // 默认倍速为 1x
    expect(wrapper.text()).toContain('1x')

    // 找到倍速按钮并点击切换
    const buttons = wrapper.findAll('button')
    const rateBtn = buttons.find(b => b.attributes('title') === '点击切换播放倍速')
    expect(rateBtn).toBeDefined()
    await rateBtn.trigger('click')
    expect(wrapper.text()).toContain('1.25x')

    // 语音开关
    const audioBtn = buttons.find(b => b.attributes('title')?.includes('语音朗读'))
    expect(audioBtn).toBeDefined()
    expect(wrapper.text()).toContain('语音开启')
    await audioBtn.trigger('click')
    expect(wrapper.text()).toContain('已静音')
  })

  it('验证舞台与台词控制台解耦布局及主题变量应用', async () => {
    const classroomStore = useClassroomStore()
    vi.spyOn(classroomStore, 'fetchClassroomDetail').mockResolvedValue(mockClassroomData)

    const wrapper = mount(ClassroomPlayerView, {
      global: {
        stubs: {
          'el-button': { template: '<button><slot /></button>' },
          'el-icon': { template: '<i><slot /></i>' },
          'el-drawer': { template: '<div><slot /></div>' }
        }
      }
    })

    await flushPromises()

    // 验证根节点应用项目主题变量
    expect(wrapper.classes()).toContain('bg-[var(--bg-primary)]')
    expect(wrapper.classes()).toContain('text-[var(--text-primary)]')

    // 验证视觉演播区 16:9 画布存在
    const stageCanvas = wrapper.find('.aspect-video')
    expect(stageCanvas.exists()).toBe(true)

    // 验证画布内部已解耦，不再包含绝对定位的台词卡
    const subtitleDockInside = stageCanvas.find('.absolute.bottom-2\\.5')
    expect(subtitleDockInside.exists()).toBe(false)

    // 验证台词正文存在且在独立控制台内
    expect(wrapper.text()).toContain('欢迎来到本节微课，今天我们学习响应式原理。')
  })

  it('支持章节目录抽屉切换展开与折叠', async () => {
    const classroomStore = useClassroomStore()
    vi.spyOn(classroomStore, 'fetchClassroomDetail').mockResolvedValue(mockClassroomData)

    const wrapper = mount(ClassroomPlayerView, {
      global: {
        stubs: {
          'el-button': { template: '<button><slot /></button>' },
          'el-icon': { template: '<i><slot /></i>' },
          'el-drawer': { template: '<div><slot /></div>' }
        }
      }
    })

    await flushPromises()

    const aside = wrapper.find('aside')
    expect(aside.exists()).toBe(true)
    // 默认折叠以保持视口开阔无拥挤
    expect(aside.attributes('style')).toContain('display: none')

    // 触发目录按钮展开
    const dirBtn = wrapper.findAll('button').find(b => b.attributes('title') === '章节目录')
    expect(dirBtn).toBeDefined()
    await dirBtn.trigger('click')
    await flushPromises()

    // 验证展开
    expect(aside.attributes('style') || '').not.toContain('display: none')
  })
})


