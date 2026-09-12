import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import NoteViewer from '@/components/NoteViewer.vue'

describe('NoteViewer', () => {
  it('renders markdown headings and tags, emits edit', async () => {
    setActivePinia(createPinia())
    const wrapper = mount(NoteViewer, {
      props: {
        note: {
          id: 'n1',
          title: '死锁笔记',
          content: '## 概念\n\n**死锁**是并发问题。\n\n- 条件一\n- 条件二',
          tags: ['操作系统', '死锁'],
          course_space_id: null,
          note_type: 'markdown',
          is_pinned: false,
          created_at: '2026-09-12T00:00:00',
          updated_at: '2026-09-12T00:00:00',
        },
        courseName: '操作系统',
      },
      global: {
        stubs: {
          'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'el-icon': true,
        },
      },
    })

    expect(wrapper.text()).toContain('死锁笔记')
    expect(wrapper.text()).toContain('操作系统')
    // rendered markdown: heading text present, raw ## should not be needed
    expect(wrapper.find('.note-md').html()).toContain('<h2')
    expect(wrapper.find('.note-md').text()).toContain('死锁是并发问题')
    const btns = wrapper.findAll('button')
    const editBtn = btns.find(b => b.text().includes('编辑'))
    expect(editBtn).toBeTruthy()
    await editBtn.trigger('click')
    expect(wrapper.emitted('edit')).toBeTruthy()
  })
})
