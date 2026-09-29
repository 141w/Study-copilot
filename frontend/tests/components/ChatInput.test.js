import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ChatInput from '@/components/chat/ChatInput.vue'

// ModelChip 内部用 useRouter 跳转「模型配置」，未注入会产生 injection 告警
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

// 发送/停止已统一为 el-button circle 图标圆钮，需要真实解析 EP 组件
// （tests/setup.js 的注册挂在被丢弃的 app 实例上，对 VTU 自建 app 无效，
//   故在此按文件显式装插件）。el-icon 仍打桩，避免依赖图标包样式。
const GLOBAL = { plugins: [ElementPlus], stubs: { 'el-icon': true } }

function mountInput(props = {}) {
  return mount(ChatInput, { props, global: GLOBAL })
}

describe('ChatInput', () => {
  it('正确渲染输入卡片与占位符', () => {
    const wrapper = mountInput({ placeholder: '输入您的问题...' })

    expect(wrapper.find('textarea').exists()).toBe(true)
    expect(wrapper.find('textarea').attributes('placeholder')).toBe('输入您的问题...')
  })

  it('输入内容后点击发送按钮触发 send 事件并清空输入', async () => {
    const wrapper = mountInput()

    const textarea = wrapper.find('textarea')
    await textarea.setValue('什么是深度学习？')

    const sendBtn = wrapper.find('button[aria-label="发送消息"]')
    expect(sendBtn.exists()).toBe(true)
    expect(sendBtn.attributes('disabled')).toBeUndefined()

    await sendBtn.trigger('click')
    expect(wrapper.emitted('send')).toBeTruthy()
    expect(wrapper.emitted('send')?.[0]).toEqual(['什么是深度学习？'])
    expect(wrapper.find('textarea').element.value).toBe('')
  })

  it('按 Enter 触发发送，而 Shift+Enter 不触发发送', async () => {
    const wrapper = mountInput()

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
    const wrapper = mountInput()

    const textarea = wrapper.find('textarea')
    await textarea.setValue('ceshi')

    await textarea.trigger('keydown', { key: 'Enter', isComposing: true })
    expect(wrapper.emitted('send')).toBeFalsy()
  })

  it('发送键为 el-button circle 主色圆钮，前景由 EP 反色令牌提供（暗色下不致白底白图标）', async () => {
    const wrapper = mountInput()

    const textarea = wrapper.find('textarea')
    await textarea.setValue('暗色模式检查')

    const sendBtn = wrapper.find('button[aria-label="发送消息"]')
    expect(sendBtn.exists()).toBe(true)
    const cls = sendBtn.classes().join(' ')

    // 皮肤来自 EP：primary 实心 + 正圆
    expect(cls).toContain('el-button')
    expect(cls).toContain('el-button--primary')
    expect(cls).toContain('is-circle')
    // 不得硬编码 text-white——暗色主色为白，白底白图标会看不见；
    // 反色前景由 --el-color-white → var(--text-inverse) 令牌映射自动反转
    expect(cls).not.toMatch(/(?:^|\s)text-white(?:\s|$)/)
    // 不再残留手写的 Tailwind 尺寸/圆角/配色
    expect(cls).not.toMatch(/w-8|h-8|rounded-lg/)
    expect(cls).not.toContain('bg-[var(--color-primary)]')
  })

  it('loading 状态下渲染停止生成按钮并触发 stop 事件', async () => {
    const wrapper = mountInput({ loading: true })

    const stopBtn = wrapper.find('button[aria-label="停止生成"]')
    expect(stopBtn.exists()).toBe(true)
    // 与发送键同一套 circle 皮肤，语义色走 danger 而非硬编码 rose
    const cls = stopBtn.classes().join(' ')
    expect(cls).toContain('is-circle')
    expect(cls).toContain('el-button--danger')
    expect(cls).not.toMatch(/rose/)
    // 停止回答只保留 SVG 图标，移除文字
    expect(stopBtn.find('svg').exists()).toBe(true)
    expect(stopBtn.text().trim()).toBe('')

    await stopBtn.trigger('click')
    expect(wrapper.emitted('stop')).toBeTruthy()
  })

  it('发送按钮在无内容时禁用', async () => {
    const wrapper = mountInput()
    const sendBtn = wrapper.find('button[aria-label="发送消息"]')
    expect(sendBtn.classes()).toContain('is-disabled')
    await sendBtn.trigger('click')
    expect(wrapper.emitted('send')).toBeFalsy()
  })
})
