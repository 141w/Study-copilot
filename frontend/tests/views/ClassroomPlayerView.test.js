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

  it('支持播放倍速循环切换与语音静音切换（设置下拉）', async () => {
    const classroomStore = useClassroomStore()
    vi.spyOn(classroomStore, 'fetchClassroomDetail').mockResolvedValue(mockClassroomData)

    const wrapper = mount(ClassroomPlayerView, {
      global: {
        stubs: {
          'el-button': { template: '<button><slot /></button>' },
          'el-icon': { template: '<i><slot /></i>' },
          'el-drawer': { template: '<div><slot /></div>' },
          'el-dropdown': {
            template: `<div class="el-dropdown-stub">
              <slot />
              <div class="dropdown-menu-stub"><slot name="dropdown" /></div>
            </div>`,
            emits: ['command'],
            provide() {
              return {
                dropdownEmit: (cmd) => this.$emit('command', cmd),
              }
            },
          },
          'el-dropdown-menu': { template: '<div><slot /></div>' },
          'el-dropdown-item': {
            props: { command: { type: [String, Number, Object], default: '' } },
            inject: ['dropdownEmit'],
            template: `<button type="button" class="el-dropdown-item" @click="dropdownEmit(command)"><slot /></button>`,
          },
        }
      }
    })

    await flushPromises()

    // 设置下拉中展示当前倍速与语音状态（1 在模板中渲染为 1x）
    const items = wrapper.findAll('.el-dropdown-item')
    expect(items.length).toBeGreaterThanOrEqual(3)
    expect(items[0].text()).toMatch(/倍速 · 1(\.0)?x/)
    expect(items[1].text()).toContain('已开启')

    await items[0].trigger('click')
    expect(wrapper.findAll('.el-dropdown-item')[0].text()).toContain('1.25x')

    await wrapper.findAll('.el-dropdown-item')[1].trigger('click')
    expect(wrapper.findAll('.el-dropdown-item')[1].text()).toContain('已静音')
  })

  it('画布使用 flex 槽位约束（无 100vh 魔法数）', async () => {
    const classroomStore = useClassroomStore()
    vi.spyOn(classroomStore, 'fetchClassroomDetail').mockResolvedValue(mockClassroomData)

    const wrapper = mount(ClassroomPlayerView, {
      global: {
        stubs: {
          'el-button': { template: '<button><slot /></button>' },
          'el-icon': { template: '<i><slot /></i>' },
          'el-drawer': { template: '<div><slot /></div>' },
        }
      }
    })
    await flushPromises()

    const slot = wrapper.find('.stage-slot')
    expect(slot.exists()).toBe(true)
    expect(slot.classes()).toContain('flex-1')
    expect(slot.classes()).toContain('min-h-0')

    const frame = wrapper.find('.stage-frame')
    expect(frame.exists()).toBe(true)
    expect(frame.classes()).toContain('aspect-video')
    expect(frame.classes()).toContain('max-h-full')
    expect(frame.classes()).toContain('w-full')
    // 不再依赖 calc(100vh - 240px)
    expect(frame.attributes('style') || '').not.toContain('100vh')
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

  it('台词默认两行可点击展开/收起', async () => {
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

    const dialogue = wrapper.find('p.line-clamp-2')
    expect(dialogue.exists()).toBe(true)
    expect(dialogue.text()).toContain('欢迎来到本节微课')

    await dialogue.trigger('click')
    expect(wrapper.find('p.line-clamp-2').exists()).toBe(false)

    await wrapper.findAll('p').find(p => p.text().includes('欢迎来到本节微课'))?.trigger('click')
    expect(wrapper.find('p.line-clamp-2').exists()).toBe(true)
  })

  it('支持章节目录：桌面默认展开，可切换折叠', async () => {
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
    // 桌面端（jsdom 默认 1024px）默认打开
    expect(aside.attributes('style') || '').not.toContain('display: none')

    const dirBtn = wrapper.findAll('button').find(b => b.attributes('title') === '章节目录')
    expect(dirBtn).toBeDefined()
    await dirBtn.trigger('click')
    await flushPromises()
    expect(aside.attributes('style')).toContain('display: none')

    await dirBtn.trigger('click')
    await flushPromises()
    expect(aside.attributes('style') || '').not.toContain('display: none')
  })

  it('验证侧边栏桌面端自适应平铺与移动端遮罩交互（彻底消除遮挡）', async () => {
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

    const dirBtn = wrapper.findAll('button').find(b => b.attributes('title') === '章节目录')
    expect(dirBtn).toBeDefined()

    const aside = wrapper.find('aside')
    expect(aside.exists()).toBe(true)

    // 验证 aside 具有桌面端自适应平铺样式（相对定位非绝对覆盖）
    expect(aside.classes()).toContain('lg:relative')
    expect(aside.classes()).toContain('lg:inset-auto')

    // 验证 main 具有 flex-1 与 min-w-0 自适应缩放属性
    const main = wrapper.find('main')
    expect(main.classes()).toContain('min-w-0')
    expect(main.classes()).toContain('flex-1')

    // 验证画布槽位使用 flex 约束
    expect(wrapper.find('.stage-slot').classes()).toContain('min-h-0')

    // 确保目录打开后可点遮罩收起（移动端路径）
    if ((aside.attributes('style') || '').includes('display: none')) {
      await dirBtn.trigger('click')
      await flushPromises()
    }
    const backdrop = wrapper.find('.lg\\:hidden.fixed.inset-0')
    expect(backdrop.exists()).toBe(true)
    await backdrop.trigger('click')
    await flushPromises()
    expect(aside.attributes('style')).toContain('display: none')
  })

  it('播放控制使用 el-button 主/次按钮态', async () => {
    const classroomStore = useClassroomStore()
    vi.spyOn(classroomStore, 'fetchClassroomDetail').mockResolvedValue(mockClassroomData)

    const wrapper = mount(ClassroomPlayerView, {
      global: {
        stubs: {
          'el-button': {
            template: '<button :data-type="type"><slot /></button>',
            props: ['type', 'size', 'disabled', 'title', 'circle', 'text', 'plain'],
          },
          'el-icon': { template: '<i><slot /></i>' },
          'el-drawer': { template: '<div><slot /></div>' }
        }
      }
    })
    await flushPromises()

    // 初始「播放」为 primary（el-button :type 映射到 data-type 避免与原生 type 冲突）
    const playBtn = wrapper.findAll('button').find(b => b.text().trim() === '播放')
    expect(playBtn).toBeDefined()
    expect(playBtn.attributes('data-type')).toBe('primary')

    await playBtn.trigger('click')
    await flushPromises()
    const pauseBtn = wrapper.findAll('button').find(b => b.text().trim() === '暂停')
    expect(pauseBtn).toBeDefined()
    expect(pauseBtn.attributes('data-type')).toBe('default')
  })

  it('讲解幕无课件主题时跟随亮暗令牌，浅填充卡片用深色字', async () => {
    const classroomStore = useClassroomStore()
    const data = JSON.parse(JSON.stringify(mockClassroomData))
    delete data.scenes[0].content.canvas.theme
    data.scenes[0].content.canvas.elements.push({
      id: 'el-light',
      type: 'shape',
      text: '浅色卡片正文',
      fill: '#F1F5F9',
      left: 60,
      top: 280,
      width: 400,
      height: 80,
    })
    vi.spyOn(classroomStore, 'fetchClassroomDetail').mockResolvedValue(data)

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

    const frame = wrapper.find('.stage-frame')
    expect(frame.classes()).toContain('stage-default-theme')
    expect(frame.attributes('style') || '').not.toContain('#0F172A')

    const lightCard = wrapper.findAll('.stage-frame .rounded-xl').find(s => s.text().includes('浅色卡片正文'))
    expect(lightCard).toBeDefined()
    expect(lightCard.attributes('style')).toContain('rgb(241, 245, 249)')
    expect(lightCard.find('div').attributes('style')).toContain('rgb(17, 24, 39)')
  })
})



