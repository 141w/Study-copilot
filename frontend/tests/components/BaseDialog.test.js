import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import BaseDialog from '@/components/common/BaseDialog.vue'

describe('BaseDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  function createWrapper(props = {}, slots = {}) {
    return mount(BaseDialog, {
      props: { visible: true, title: 'Dialog', ...props },
      slots,
      global: {
        stubs: {
          Teleport: { template: '<slot />' },
        },
      },
    })
  }

  it('renders title', () => {
    const wrapper = createWrapper({ title: 'Test Dialog' })
    expect(wrapper.text()).toContain('Test Dialog')
  })

  it('does not render when not visible', () => {
    const wrapper = mount(BaseDialog, {
      props: { visible: false },
      global: { stubs: { Teleport: { template: '<slot />' } } },
    })
    expect(wrapper.find('[class*=fixed]').exists()).toBe(false)
  })

  it('emits close on button click', async () => {
    const wrapper = createWrapper()
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('update:visible')).toBeTruthy()
    expect(wrapper.emitted('update:visible')[0]).toEqual([false])
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('renders default slot', () => {
    const wrapper = createWrapper({}, { default: '<p class="slot-content">Hello</p>' })
    expect(wrapper.find('.slot-content').text()).toBe('Hello')
  })

  it('renders header slot', () => {
    const wrapper = createWrapper({}, { header: '<span class="hdr">Custom Header</span>' })
    expect(wrapper.find('.hdr').text()).toBe('Custom Header')
  })

  it('renders footer slot', () => {
    const wrapper = createWrapper({}, { footer: '<button class="ok-btn">OK</button>' })
    expect(wrapper.find('.ok-btn').text()).toBe('OK')
  })

  it('has correct default props', () => {
    const wrapper = createWrapper()
    expect(wrapper.props('closeOnBackdrop')).toBe(true)
    expect(wrapper.props('size')).toBe('md')
  })
})
