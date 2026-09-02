import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

describe('ConfirmDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('打开时渲染标题与消息', async () => {
    const wrapper = mount(ConfirmDialog, {
      props: {
        modelValue: true,
        title: '删除笔记',
        message: '确定要删除「测试」吗？'
      },
      global: {
        stubs: {
          'el-dialog': {
            template: '<div><h2>{{ title }}</h2><slot /><slot name="footer" /></div>',
            props: ['modelValue', 'title']
          },
          'el-button': {
            template: '<button data-test="btn" @click="$emit(\'click\')"><slot /></button>',
            emits: ['click']
          }
        }
      }
    })
    expect(wrapper.text()).toContain('删除笔记')
    expect(wrapper.text()).toContain('确定要删除「测试」吗？')
    expect(wrapper.text()).toContain('取消')
    expect(wrapper.text()).toContain('确认') // 默认 confirmText（footer 第二个按钮 slot）
  })

  it('点击确认按钮触发 confirm 事件', async () => {
    const wrapper = mount(ConfirmDialog, {
      props: {
        modelValue: true,
        title: 'T',
        message: 'M',
        confirmText: '删除'
      },
      global: {
        stubs: {
          'el-dialog': {
            template: '<div><slot /><slot name="footer" /></div>',
            props: ['modelValue']
          },
          'el-button': {
            template: '<button data-test="btn" @click="$emit(\'click\')"><slot /></button>',
            emits: ['click']
          }
        }
      }
    })
    const buttons = wrapper.findAll('[data-test="btn"]')
    // footer 里第二个按钮是确认
    await buttons[1].trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })

  it('取消按钮触发 update:modelValue(false)', async () => {
    const wrapper = mount(ConfirmDialog, {
      props: {
        modelValue: true,
        title: 'T',
        message: 'M'
      },
      global: {
        stubs: {
          'el-dialog': {
            template: '<div><slot /><slot name="footer" /></div>',
            props: ['modelValue']
          },
          'el-button': {
            template: '<button data-test="btn" @click="$emit(\'click\')"><slot /></button>',
            emits: ['click']
          }
        }
      }
    })
    const buttons = wrapper.findAll('[data-test="btn"]')
    await buttons[0].trigger('click')
    const events = wrapper.emitted('update:modelValue')
    expect(events).toBeTruthy()
    expect(events[0]).toEqual([false])
  })

  it('关闭事件由 el-dialog 的 update:model-value 转发', async () => {
    const wrapper = mount(ConfirmDialog, {
      props: { modelValue: true, title: 'T', message: 'M' },
      global: {
        stubs: {
          'el-dialog': {
            name: 'ElDialogStub',
            template: '<div data-test="dialog"><slot /><slot name="footer" /></div>',
            props: ['modelValue'],
            emits: ['update:modelValue']
          },
          'el-button': {
            template: '<button><slot /></button>'
          }
        }
      }
    })
    // 模拟 el-dialog 关闭（点遮罩/X 触发 update:model-value）
    const dialog = wrapper.findComponent('[data-test="dialog"]')
    await dialog.vm.$emit('update:modelValue', false)
    const events = wrapper.emitted('update:modelValue')
    expect(events).toBeTruthy()
    expect(events[0]).toEqual([false])
  })
})
