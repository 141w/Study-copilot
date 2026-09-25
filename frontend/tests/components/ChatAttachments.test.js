import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatAttachments from '@/components/chat/ChatAttachments.vue'

const base = {
  id: 'att-1',
  filename: '讲义.pdf',
  file_type: 'document',
  status: 'ready',
  size: 1024,
}

describe('ChatAttachments', () => {
  it('renders nothing when list empty', () => {
    const wrapper = mount(ChatAttachments, {
      props: { attachments: [] },
    })
    expect(wrapper.find('[data-test="chat-attachments"]').exists()).toBe(false)
  })

  it('renders filename and two-phase status labels', () => {
    const wrapper = mount(ChatAttachments, {
      props: {
        attachments: [
          { ...base, id: 'a1', status: 'uploading', filename: 'up.png', file_type: 'image' },
          { ...base, id: 'a2', status: 'parsing', filename: 'p.pdf' },
          { ...base, id: 'a3', status: 'ready', filename: 'r.pdf' },
          { ...base, id: 'a4', status: 'error', filename: 'e.pdf' },
        ],
      },
    })
    const statuses = wrapper.findAll('[data-test="attachment-status"]').map((n) => n.text())
    expect(statuses).toContain('上传中')
    expect(statuses).toContain('解析中')
    expect(statuses).toContain('就绪')
    expect(statuses).toContain('失败')
    expect(wrapper.text()).toContain('up.png')
  })

  it('emits remove with attachment id', async () => {
    const wrapper = mount(ChatAttachments, {
      props: { attachments: [{ ...base }] },
    })
    await wrapper.find('[data-test="attachment-remove"]').trigger('click')
    expect(wrapper.emitted('remove')).toEqual([['att-1']])
  })

  it('marks data-status for upload-in-progress blocking contract', () => {
    const wrapper = mount(ChatAttachments, {
      props: {
        attachments: [{ ...base, id: 'up-1', status: 'uploading' }],
      },
    })
    const chip = wrapper.find('[data-test="attachment-up-1"]')
    expect(chip.attributes('data-status')).toBe('uploading')
  })
})
