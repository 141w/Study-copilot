import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ScopeChips from '@/components/chat/ScopeChips.vue'
import ChatInput from '@/components/chat/ChatInput.vue'

vi.mock('@/stores/document', () => ({
  useDocumentStore: () => ({ documents: [], fetchDocuments: vi.fn().mockResolvedValue([]) }),
}))
vi.mock('@/stores/course', () => ({
  useCourseStore: () => ({ courses: [], fetchCourses: vi.fn().mockResolvedValue([]) }),
}))

describe('ScopeChips', () => {
  it('渲染胶囊并支持移除', async () => {
    const wrapper = mount(ScopeChips, {
      props: {
        chips: [{ key: 'doc:1', kind: 'doc', id: '1', label: 'ml.pdf' }],
        candidates: [],
      },
    })
    await flushPromises()
    expect(wrapper.find('[data-test="scope-chip-doc"]').exists()).toBe(true)
    await wrapper.find('[aria-label="移除 ml.pdf"]').trigger('click')
    expect(wrapper.emitted('remove')).toBeTruthy()
  })

  it('IME 组合态不误弹 @（由 ChatInput 守卫）', async () => {
    const wrapper = mount(ChatInput, {
      global: { stubs: { 'el-icon': true, 'el-dropdown': true, ScopeChips: true, ModelChip: true } },
      props: { scopeChips: [] },
    })
    const ta = wrapper.find('textarea')
    await ta.trigger('compositionstart')
    ta.element.value = '你好@'
    await ta.trigger('input')
    expect(wrapper.find('[data-test="mention-popup"]').exists()).toBe(false)
  })
})

describe('ChatInput 范围退格', () => {
  it('空文本按 Backspace 弹出最后一个胶囊', async () => {
    const wrapper = mount(ChatInput, {
      props: {
        scopeChips: [
          { key: 'doc:1', kind: 'doc', id: '1', label: 'a.pdf' },
          { key: 'doc:2', kind: 'doc', id: '2', label: 'b.pdf' },
        ],
      },
      global: {
        stubs: {
          'el-icon': true,
          'el-dropdown': true,
          'el-dropdown-menu': true,
          'el-dropdown-item': true,
        },
      },
    })
    await flushPromises()
    const ta = wrapper.find('textarea')
    await ta.trigger('keydown', { key: 'Backspace' })
    const ev = wrapper.emitted('remove-scope')
    expect(ev).toBeTruthy()
    expect(ev[0][0].id).toBe('2')
  })
})
