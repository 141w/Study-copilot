import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PersonaManageDialog from '@/components/chat/PersonaManageDialog.vue'
import api from '@/services/api'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn()
  }
}))

describe('PersonaManageDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    api.get.mockResolvedValue({
      data: {
        personas: [
          { role: 'teacher', name: '苏老师', avatar: 'User', is_custom: false, system_message: '讲师人设' },
          { id: 'custom-1', role: 'custom_socrates', name: '苏格拉底', avatar: 'Brain', is_custom: true, system_message: '反问启发' }
        ]
      }
    })
  })

  it('打开时拉取角色并在列表中渲染官方角色和自定义角色', async () => {
    const wrapper = mount(PersonaManageDialog, {
      props: {
        modelValue: true
      },
      global: {
        stubs: {
          'el-dialog': {
            template: '<div><h2>{{ title }}</h2><slot /><slot name="footer" /></div>',
            props: ['modelValue', 'title']
          },
          'el-button': {
            template: '<button @click="$emit(\'click\')"><slot /></button>',
            emits: ['click']
          },
          'el-icon': { template: '<span><slot /></span>' },
          'el-tooltip': { template: '<div><slot /></div>' },
          'el-popconfirm': { template: '<div><slot name="reference" /></div>' },
          'el-input': { template: '<input />' }
        }
      }
    })

    // 等待拉取数据并渲染
    await vi.waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/chat/personas')
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('全部角色库')
    expect(wrapper.text()).toContain('苏老师')
    expect(wrapper.text()).toContain('苏格拉底')
    expect(wrapper.text()).toContain('官方内置角色')
    expect(wrapper.text()).toContain('我的自定义角色')
  })

  it('点击新建角色切换到编辑表单', async () => {
    const wrapper = mount(PersonaManageDialog, {
      props: {
        modelValue: true
      },
      global: {
        stubs: {
          'el-dialog': {
            template: '<div><h2>{{ title }}</h2><slot /><slot name="footer" /></div>',
            props: ['modelValue', 'title']
          },
          'el-button': {
            template: '<button @click="$emit(\'click\')"><slot /></button>',
            emits: ['click']
          },
          'el-icon': { template: '<span><slot /></span>' },
          'el-tooltip': { template: '<div><slot /></div>' },
          'el-popconfirm': { template: '<div><slot name="reference" /></div>' },
          'el-input': { template: '<input />' }
        }
      }
    })

    const buttons = wrapper.findAll('button')
    // 找到包含 "新建角色" 的按钮并点击
    const createBtn = buttons.find(b => b.text().includes('新建角色'))
    expect(createBtn).toBeDefined()
    await createBtn?.trigger('click')

    expect(wrapper.text()).toContain('角色名称')
    expect(wrapper.text()).toContain('人设提示词')
    expect(wrapper.text()).toContain('快捷灵感')
    expect(wrapper.text()).toContain('角色矢量图标')
  })

  it('表单中提供角色矢量图标并可通过快捷灵感切换图标', async () => {
    const wrapper = mount(PersonaManageDialog, {
      props: {
        modelValue: true
      },
      global: {
        stubs: {
          'el-dialog': {
            template: '<div><h2>{{ title }}</h2><slot /><slot name="footer" /></div>',
            props: ['modelValue', 'title']
          },
          'el-button': {
            template: '<button @click="$emit(\'click\')"><slot /></button>',
            emits: ['click']
          },
          'el-icon': { template: '<span><slot /></span>' },
          'el-tooltip': { template: '<div><slot /></div>' },
          'el-popconfirm': { template: '<div><slot name="reference" /></div>' },
          'el-input': { template: '<input />' }
        }
      }
    })

    const buttons = wrapper.findAll('button')
    const createBtn = buttons.find(b => b.text().includes('新建角色'))
    await createBtn?.trigger('click')

    // 快捷灵感按钮中不含 Emoji
    const tplBtn = wrapper.findAll('button').find(b => b.text().includes('苏格拉底反问'))
    expect(tplBtn).toBeDefined()
    expect(tplBtn?.text()).not.toContain('🏛️')

    await tplBtn?.trigger('click')
    expect(wrapper.vm.formData.avatar).toBe('Brain')
    expect(wrapper.text()).toContain('哲思')
  })
})
