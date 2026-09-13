import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ProximitySidebar from '@/components/chat/ProximitySidebar.vue'

const sections = [
  { id: 'msg-1', label: '我：什么是 Transformer？', kind: 'section' },
  { id: 'msg-2', label: 'Copilot：Transformer 是…', kind: 'body' },
  { id: 'msg-3', label: '研讨：纪要', kind: 'title' },
]

describe('ProximitySidebar (project-theme chips)', () => {
  it('renders one chip per section', () => {
    const wrapper = mount(ProximitySidebar, { props: { sections } })
    expect(wrapper.findAll('.pr-chip')).toHaveLength(3)
  })

  it('hides when no sections', () => {
    const wrapper = mount(ProximitySidebar, { props: { sections: [] } })
    expect(wrapper.findAll('.pr-chip')).toHaveLength(0)
  })

  it('emits navigate on click', async () => {
    const wrapper = mount(ProximitySidebar, { props: { sections } })
    await wrapper.findAll('.pr-chip')[1].trigger('click')
    expect(wrapper.emitted('navigate')?.[0]).toEqual(['msg-2'])
  })

  it('applies kind classes for length hierarchy', () => {
    const wrapper = mount(ProximitySidebar, { props: { sections } })
    expect(wrapper.findAll('.pr-chip--title')).toHaveLength(1)
    expect(wrapper.findAll('.pr-chip--section')).toHaveLength(1)
    expect(wrapper.findAll('.pr-chip--body')).toHaveLength(1)
  })

  it('shows hover preview on chip mouseenter', async () => {
    const wrapper = mount(ProximitySidebar, {
      props: {
        sections: [
          {
            id: 'msg-1',
            label: '我：问题',
            preview: '这是一段较长的预览文本用于悬停显示',
            role: '我',
            kind: 'section',
          },
          { id: 'msg-2', label: 'Copilot：回答', kind: 'body' },
        ],
      },
      attachTo: document.body,
    })
    expect(wrapper.find('[data-test="proximity-preview"]').exists()).toBe(false)
    await wrapper.findAll('.pr-chip')[0].trigger('mouseenter')
    const preview = wrapper.find('[data-test="proximity-preview"]')
    expect(preview.exists()).toBe(true)
    expect(preview.text()).toContain('我')
    expect(preview.text()).toContain('预览文本')
    await wrapper.find('.pr-stack').trigger('mouseleave')
    expect(wrapper.find('[data-test="proximity-preview"]').exists()).toBe(false)
    wrapper.unmount()
  })
})
