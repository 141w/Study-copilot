import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatInput from '@/components/chat/ChatInput.vue'

describe('ChatInput', () => {
  it('正确渲染输入卡片、快捷键提示与占位符', () => {
    const wrapper = mount(ChatInput, {
      props: {
        placeholder: '输入问题，按 Enter 发送...'
      },
      global: {
        stubs: {
          'el-icon': true,
        }
      }
    })

    expect(wrapper.find('textarea').exists()).toBe(true)
    expect(wrapper.find('textarea').attributes('placeholder')).toBe('输入问题，按 Enter 发送...')
    expect(wrapper.text()).toContain('Enter 发送')
  })

  it('输入内容后点击发送按钮触发 send 事件并清空输入', async () => {
    const wrapper = mount(ChatInput, {
      global: {
        stubs: {
          'el-icon': true,
        }
      }
    })

    const textarea = wrapper.find('textarea')
    await textarea.setValue('什么是深度学习？')

    const sendBtn = wrapper.find('button[aria-label="发送消息"]')
    expect(sendBtn.attributes('disabled')).toBeUndefined()

    await sendBtn.trigger('click')
    expect(wrapper.emitted('send')).toBeTruthy()
    expect(wrapper.emitted('send')?.[0]).toEqual(['什么是深度学习？'])
    expect(wrapper.find('textarea').element.value).toBe('')
  })

  it('按 Enter 触发发送，而 Shift+Enter 不触发发送', async () => {
    const wrapper = mount(ChatInput, {
      global: {
        stubs: {
          'el-icon': true,
        }
      }
    })

    const textarea = wrapper.find('textarea')
    await textarea.setValue('第一行内容')

    // Shift + Enter 换行
    await textarea.trigger('keydown', { key: 'Enter', shiftKey: true })
    expect(wrapper.emitted('send')).toBeFalsy()

    // 纯 Enter 发送
    await textarea.trigger('keydown', { key: 'Enter', shiftKey: false })
    expect(wrapper.emitted('send')).toBeTruthy()
    expect(wrapper.emitted('send')?.[0]).toEqual(['第一行内容'])
  })

  it('中文输入法 composition 期间按 Enter 不触发发送', async () => {
    const wrapper = mount(ChatInput, {
      global: {
        stubs: {
          'el-icon': true,
        }
      }
    })

    const textarea = wrapper.find('textarea')
    await textarea.setValue('ceshi')

    await textarea.trigger('keydown', { key: 'Enter', isComposing: true })
    expect(wrapper.emitted('send')).toBeFalsy()
  })

  it('loading 状态下渲染停止生成按钮并触发 stop 事件', async () => {
    const wrapper = mount(ChatInput, {
      props: {
        loading: true
      },
      global: {
        stubs: {
          'el-icon': true,
        }
      }
    })

    const stopBtn = wrapper.find('button[aria-label="停止生成"]')
    expect(stopBtn.exists()).toBe(true)
    expect(stopBtn.text()).toContain('停止生成')

    await stopBtn.trigger('click')
    expect(wrapper.emitted('stop')).toBeTruthy()
  })
})
