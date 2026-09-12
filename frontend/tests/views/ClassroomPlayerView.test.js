import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ClassroomPlayerView from '@/views/ClassroomPlayerView.vue'
import { useCourseStore } from '@/stores/course'
import { ElMessage } from 'element-plus'

const mockPush = vi.fn()
const mockBack = vi.fn()

let mockRoute = {
  path: '/courses/course-101/classroom',
  params: { id: 'course-101' },
}

vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
  useRouter: () => ({
    push: mockPush,
    back: mockBack,
  }),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: {
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
    },
  }
})

const defaultStubs = {
  'el-button': { template: '<button v-bind="$attrs"><slot /></button>' },
  'el-icon': { template: '<i><slot /></i>' },
  'el-popover': { template: '<div><slot name="reference" /><slot /></div>' },
  'el-dialog': { template: '<div class="el-dialog" v-if="$attrs.modelValue"><slot /></div>' },
  'el-radio-group': { template: '<div class="el-radio-group"><slot /></div>' },
  'el-radio-button': { template: '<button class="el-radio-button" v-bind="$attrs"><slot /></button>' },
  'el-slider': { template: '<div class="el-slider"></div>' },
  'el-switch': { template: '<input type="checkbox" class="el-switch" />' },
}

describe('ClassroomPlayerView (OpenMAIC Embedded Host)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockPush.mockClear()
    mockBack.mockClear()
    vi.clearAllMocks()

    mockRoute = {
      path: '/courses/course-101/classroom',
      params: { id: 'course-101' },
    }
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('从课程路由 /courses/:id/classroom 加载：解析 classroomId 并渲染 OpenMAIC iframe', async () => {
    const courseStore = useCourseStore()
    vi.spyOn(courseStore, 'fetchCourse').mockResolvedValue({
      id: 'course-101',
      name: '深度学习原理与实战',
      description: JSON.stringify({
        classroom_id: 'openmaic-stage-999',
        classroom_url: '/courses/course-101/classroom',
      }),
      user_id: 'u-1',
      color: '#409EFF',
      created_at: '',
      updated_at: '',
    })
    vi.spyOn(courseStore, 'fetchCourseDocuments').mockResolvedValue([
      { id: 'doc-1', filename: '深度学习.pdf', file_size: 1024 * 1024, user_id: 'u-1', file_path: '', status: 'ready', created_at: '', updated_at: '' },
      { id: 'doc-2', filename: '神经网络.docx', file_size: 512 * 1024, user_id: 'u-1', file_path: '', status: 'ready', created_at: '', updated_at: '' },
    ])

    const wrapper = mount(ClassroomPlayerView, {
      global: {
        stubs: defaultStubs,
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('深度学习原理与实战')
    expect(wrapper.text()).toContain('AI 互动微课')
    expect(wrapper.text()).toContain('2 份参考文档')

    const iframe = wrapper.find('iframe')
    expect(iframe.exists()).toBe(true)
    expect(iframe.attributes('src')).toBe('/classroom-engine/classroom/openmaic-stage-999?embedded=true&theme=light')
  })

  it('直接从 /classroom/:id 路由访问：将路由 ID 作为微课 ID 并渲染 iframe', async () => {
    mockRoute = {
      path: '/classroom/openmaic-direct-555',
      params: { id: 'openmaic-direct-555' },
    }

    const wrapper = mount(ClassroomPlayerView, {
      global: {
        stubs: defaultStubs,
      },
    })

    await flushPromises()

    const iframe = wrapper.find('iframe')
    expect(iframe.exists()).toBe(true)
    expect(iframe.attributes('src')).toBe('/classroom-engine/classroom/openmaic-direct-555?embedded=true&theme=light')
  })

  it('响应 postMessage OPENMAIC_READY 事件更新加载状态', async () => {
    const courseStore = useCourseStore()
    vi.spyOn(courseStore, 'fetchCourse').mockResolvedValue({
      id: 'course-101',
      name: '测试微课',
      description: JSON.stringify({ classroom_id: 'stage-1' }),
      user_id: 'u-1',
      color: '',
      created_at: '',
      updated_at: '',
    })
    vi.spyOn(courseStore, 'fetchCourseDocuments').mockResolvedValue([])

    const wrapper = mount(ClassroomPlayerView, {
      global: {
        stubs: defaultStubs,
      },
    })

    await flushPromises()

    // 初始加载遮罩存在
    expect(wrapper.text()).toContain('正在载入 OpenMAIC 画布与声学引擎')

    // 触发 OPENMAIC_READY 跨窗口消息
    window.dispatchEvent(new MessageEvent('message', {
      data: { type: 'OPENMAIC_READY', classroomId: 'stage-1' },
    }))

    await flushPromises()

    // 遮罩消除
    expect(wrapper.text()).not.toContain('正在载入 OpenMAIC 画布与声学引擎')
  })

  it('响应 postMessage OPENMAIC_EXIT 事件返回课程空间', async () => {
    const courseStore = useCourseStore()
    vi.spyOn(courseStore, 'fetchCourse').mockResolvedValue({
      id: 'course-101',
      name: '测试微课',
      description: JSON.stringify({ classroom_id: 'stage-exit-1' }),
      user_id: 'u-1',
      color: '',
      created_at: '',
      updated_at: '',
    })
    vi.spyOn(courseStore, 'fetchCourseDocuments').mockResolvedValue([])

    mount(ClassroomPlayerView, {
      global: {
        stubs: defaultStubs,
      },
    })

    await flushPromises()

    window.dispatchEvent(new MessageEvent('message', {
      data: { type: 'OPENMAIC_EXIT' },
    }))

    expect(mockPush).toHaveBeenCalledWith('/courses/course-101')
  })

  it('响应 postMessage OPENMAIC_QUIZ_COMPLETED 事件展示同步成功通知', async () => {
    const courseStore = useCourseStore()
    vi.spyOn(courseStore, 'fetchCourse').mockResolvedValue({
      id: 'course-101',
      name: '测试微课',
      description: JSON.stringify({ classroom_id: 'stage-quiz-1' }),
      user_id: 'u-1',
      color: '',
      created_at: '',
      updated_at: '',
    })
    vi.spyOn(courseStore, 'fetchCourseDocuments').mockResolvedValue([])

    mount(ClassroomPlayerView, {
      global: {
        stubs: defaultStubs,
      },
    })

    await flushPromises()

    window.dispatchEvent(new MessageEvent('message', {
      data: { type: 'OPENMAIC_QUIZ_COMPLETED', stageId: 'stage-quiz-1', results: [] },
    }))

    expect(ElMessage.success).toHaveBeenCalledWith(expect.stringContaining('随堂测验已完成'))
  })

  it('点击独立窗口演播按钮调用 window.open', async () => {
    const courseStore = useCourseStore()
    vi.spyOn(courseStore, 'fetchCourse').mockResolvedValue({
      id: 'course-101',
      name: '测试微课',
      description: JSON.stringify({ classroom_id: 'stage-pop-1' }),
      user_id: 'u-1',
      color: '',
      created_at: '',
      updated_at: '',
    })
    vi.spyOn(courseStore, 'fetchCourseDocuments').mockResolvedValue([])

    const windowOpenSpy = vi.spyOn(window, 'open').mockImplementation(() => null)

    const wrapper = mount(ClassroomPlayerView, {
      global: {
        stubs: defaultStubs,
      },
    })

    await flushPromises()

    const openBtn = wrapper.findAll('button').find(b => b.attributes('title') === '在独立窗口中演播')
    expect(openBtn).toBeDefined()
    await openBtn?.trigger('click')

    expect(windowOpenSpy).toHaveBeenCalledWith('/classroom-engine/classroom/stage-pop-1', '_blank')
  })

  it('课程未生成微课时渲染友好提示与返回按钮', async () => {
    const courseStore = useCourseStore()
    vi.spyOn(courseStore, 'fetchCourse').mockResolvedValue({
      id: 'course-101',
      name: '空白课程',
      description: '',
      user_id: 'u-1',
      color: '',
      created_at: '',
      updated_at: '',
    })
    vi.spyOn(courseStore, 'fetchCourseDocuments').mockResolvedValue([])

    const wrapper = mount(ClassroomPlayerView, {
      global: {
        stubs: defaultStubs,
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('未能载入互动微课')
    expect(wrapper.text()).toContain('当前课程尚未生成完整的 AI 互动微课')

    const backBtn = wrapper.findAll('button').find(b => b.text().includes('返回课程空间'))
    expect(backBtn).toBeDefined()
    await backBtn?.trigger('click')

    expect(mockPush).toHaveBeenCalledWith('/courses/course-101')
  })

  it('点击微课设置按钮唤起设置面板并显示参会人设与主模型状态', async () => {
    const courseStore = useCourseStore()
    vi.spyOn(courseStore, 'fetchCourse').mockResolvedValue({
      id: 'course-101',
      name: '微课设置测试',
      description: JSON.stringify({ classroom_id: 'stage-settings-1' }),
      user_id: 'u-1',
      color: '',
      created_at: '',
      updated_at: '',
    })
    vi.spyOn(courseStore, 'fetchCourseDocuments').mockResolvedValue([])

    const wrapper = mount(ClassroomPlayerView, {
      global: {
        stubs: defaultStubs,
      },
    })

    await flushPromises()

    const settingBtn = wrapper.findAll('button').find(b => b.attributes('title') === '微课设置')
    expect(settingBtn).toBeDefined()
    await settingBtn?.trigger('click')

    await flushPromises()

    expect(wrapper.text()).toContain('演播与语音控制')
    expect(wrapper.text()).toContain('主模型与讨论引擎')
    expect(wrapper.text()).toContain('已接入 · 无感直通')
    expect(wrapper.text()).toContain('微课参会人设')
    expect(wrapper.text()).toContain('苏老师')
    expect(wrapper.text()).toContain('学霸同学')
    expect(wrapper.text()).toContain('求知同学')
  })

  it('接收 OPENMAIC_READY 中的 config 同步更新主模型与倍速', async () => {
    const courseStore = useCourseStore()
    vi.spyOn(courseStore, 'fetchCourse').mockResolvedValue({
      id: 'course-101',
      name: '微课同步测试',
      description: JSON.stringify({ classroom_id: 'stage-sync-1' }),
      user_id: 'u-1',
      color: '',
      created_at: '',
      updated_at: '',
    })
    vi.spyOn(courseStore, 'fetchCourseDocuments').mockResolvedValue([])

    const wrapper = mount(ClassroomPlayerView, {
      global: {
        stubs: defaultStubs,
      },
    })

    await flushPromises()

    window.dispatchEvent(new MessageEvent('message', {
      data: {
        type: 'OPENMAIC_READY',
        classroomId: 'stage-sync-1',
        config: {
          speed: 1.5,
          volume: 0.8,
          muted: false,
          autoPlay: true,
          modelId: 'step-3.7-flash',
        },
      },
    }))

    await flushPromises()

    const settingBtn = wrapper.findAll('button').find(b => b.attributes('title') === '微课设置')
    await settingBtn?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('step-3.7-flash')
  })

  it('随堂测验完成时携带 results 并展示正确题数', async () => {
    const courseStore = useCourseStore()
    vi.spyOn(courseStore, 'fetchCourse').mockResolvedValue({
      id: 'course-101',
      name: '测验得分测试',
      description: JSON.stringify({ classroom_id: 'stage-score-1' }),
      user_id: 'u-1',
      color: '',
      created_at: '',
      updated_at: '',
    })
    vi.spyOn(courseStore, 'fetchCourseDocuments').mockResolvedValue([])

    mount(ClassroomPlayerView, {
      global: {
        stubs: defaultStubs,
      },
    })

    await flushPromises()

    window.dispatchEvent(new MessageEvent('message', {
      data: {
        type: 'OPENMAIC_QUIZ_COMPLETED',
        stageId: 'stage-score-1',
        results: [
          { questionId: 'q1', isCorrect: true },
          { questionId: 'q2', isCorrect: false },
          { questionId: 'q3', isCorrect: true },
        ],
      },
    }))

    expect(ElMessage.success).toHaveBeenCalledWith(expect.stringContaining('答对 2/3 题'))
  })
})
