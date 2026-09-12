import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import NoteViewer from '@/components/NoteViewer.vue'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/documents', component: { template: '<div/>' } },
    ],
  })
}

const stubs = {
  'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
  'el-icon': true,
}

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
        plugins: [makeRouter()],
        stubs,
      },
    })

    expect(wrapper.text()).toContain('死锁笔记')
    expect(wrapper.text()).toContain('操作系统')
    expect(wrapper.find('.note-md').html()).toContain('<h2')
    expect(wrapper.find('.note-md').text()).toContain('死锁是并发问题')
    const btns = wrapper.findAll('button')
    const editBtn = btns.find(b => b.text().includes('编辑'))
    expect(editBtn).toBeTruthy()
    await editBtn.trigger('click')
    expect(wrapper.emitted('edit')).toBeTruthy()
  })

  it('converts [来源N] to clickable badge and strips note-sources meta', async () => {
    setActivePinia(createPinia())
    const router = makeRouter()
    const pushSpy = vi.spyOn(router, 'push')
    const wrapper = mount(NoteViewer, {
      props: {
        note: {
          id: 'n2',
          title: '带来源',
          content:
            '结论[来源1]。\n\n<!--note-sources:[{"index":1,"document_id":"doc-1","page":"3","source":"os.pdf","snippet":"死锁条件"}]-->',
          tags: [],
          course_space_id: null,
          note_type: 'markdown',
          is_pinned: false,
          created_at: '2026-09-12T00:00:00',
          updated_at: '2026-09-12T00:00:00',
        },
      },
      global: {
        plugins: [router],
        stubs,
      },
    })
    const html = wrapper.find('.note-md').html()
    expect(html).toContain('note-source-badge')
    expect(html).not.toContain('note-sources:')
    const badge = wrapper.find('.note-source-badge')
    expect(badge.attributes('data-index')).toBe('1')
    await badge.trigger('click')
    expect(pushSpy).toHaveBeenCalled()
    const arg = pushSpy.mock.calls[0][0]
    expect(arg.path).toBe('/documents')
    expect(arg.query.doc).toBe('doc-1')
    expect(arg.query.page).toBe('3')
  })
})


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

  it('converts [来源N] to clickable badge and strips note-sources meta', async () => {
    setActivePinia(createPinia())
    const push = vi.fn()
    const wrapper = mount(NoteViewer, {
      props: {
        note: {
          id: 'n2',
          title: '带来源',
          content:
            '结论[来源1]。\n\n<!--note-sources:[{"index":1,"document_id":"doc-1","page":"3","source":"os.pdf","snippet":"死锁条件"}]-->',
          tags: [],
          course_space_id: null,
          note_type: 'markdown',
          is_pinned: false,
          created_at: '2026-09-12T00:00:00',
          updated_at: '2026-09-12T00:00:00',
        },
      },
      global: {
        mocks: { $router: { push } },
        plugins: [],
        stubs: {
          'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'el-icon': true,
        },
      },
    })
    // useRouter needs real router; spy via component internals if mocked poorly
    const html = wrapper.find('.note-md').html()
    expect(html).toContain('note-source-badge')
    expect(html).not.toContain('note-sources:')
    const badge = wrapper.find('.note-source-badge')
    expect(badge.attributes('data-index')).toBe('1')
  })
})
