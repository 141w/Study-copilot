import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ModelChip from '@/components/chat/ModelChip.vue'

const mockFetchLLMConfig = vi.fn()
const mockPush = vi.fn()

vi.mock('@/stores/config', () => ({
  useConfigStore: () => ({
    fetchLLMConfig: mockFetchLLMConfig,
  }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}))

describe('ModelChip', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('未配置模型时：下拉列表为空，触发按钮显示“未配置模型”，且绝无预设或默认模型', async () => {
    mockFetchLLMConfig.mockResolvedValueOnce({
      id: '',
      model_name: '',
      has_api_key: false,
    })

    const wrapper = mount(ModelChip, {
      attachTo: document.body,
    })
    await flushPromises()

    const trigger = wrapper.find('.model-selector-trigger')
    expect(trigger.exists()).toBe(true)
    expect(trigger.classes()).toContain('is-empty')
    expect(wrapper.find('.model-selector-name').text()).toBe('未配置模型')
    expect(wrapper.find('.model-selector-ctx').exists()).toBe(false)

    // 点击打开下拉弹层
    await trigger.trigger('click')
    await flushPromises()

    const dropdown = document.body.querySelector('.model-selector-dropdown')
    expect(dropdown).toBeTruthy()

    // 绝不包含任何预设模型 (DeepSeek, GPT-4o, 通义千问等)
    const textContent = dropdown?.textContent || ''
    expect(textContent).not.toContain('DeepSeek')
    expect(textContent).not.toContain('GPT-4o')
    expect(textContent).not.toContain('通义千问')
    expect(textContent).not.toContain('默认主模型')

    // 应展示未配置提示
    expect(textContent).toContain('未检测到已配置的模型')

    wrapper.unmount()
  })

  it('配置了真实模型时：正确加载并显示真实模型与上下文窗口，绝无默认预设污染', async () => {
    mockFetchLLMConfig.mockResolvedValueOnce({
      id: 'cfg-uuid-123',
      model_name: 'step-3.7-flash',
      context_window: 262144,
      has_api_key: true,
    })

    const wrapper = mount(ModelChip, {
      attachTo: document.body,
    })
    await flushPromises()

    const trigger = wrapper.find('.model-selector-trigger')
    expect(trigger.classes()).not.toContain('is-empty')
    expect(wrapper.find('.model-selector-name').text()).toBe('step-3.7-flash')
    expect(wrapper.find('.model-selector-ctx').text()).toBe('256K')

    // 打开下拉菜单
    await trigger.trigger('click')
    await flushPromises()

    const dropdown = document.body.querySelector('.model-selector-dropdown')
    expect(dropdown).toBeTruthy()

    const options = dropdown?.querySelectorAll('.model-option')
    expect(options?.length).toBe(1)
    expect(options?.[0].textContent).toContain('step-3.7-flash')
    expect(options?.[0].textContent).toContain('256K')

    // 点击模型选项触发 select 事件
    const optionEl = dropdown?.querySelector('.model-option')
    if (optionEl) {
      optionEl.click()
    }
    await flushPromises()

    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')?.[0]).toEqual(['step-3.7-flash'])

    wrapper.unmount()
  })
})
