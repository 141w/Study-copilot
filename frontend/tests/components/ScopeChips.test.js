import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ScopeChips from '@/components/chat/ScopeChips.vue'
import ChatInput from '@/components/chat/ChatInput.vue'

vi.mock('@/stores/document', () => ({
  useDocumentStore: () => ({ documents: [], readyDocuments: [], fetchDocuments: vi.fn().mockResolvedValue([]) }),
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

  it('候选浮层展开：支持点击候选项目触发 pick 事件并关闭浮层', async () => {
    const wrapper = mount(ScopeChips, {
      props: {
        chips: [],
        mentionOpen: true,
        candidates: [
          { key: 'course:1', kind: 'course', id: '1', label: '高等数学' },
          { key: 'doc:2', kind: 'doc', id: '2', label: '线性代数.pdf' },
        ],
      },
    })
    await flushPromises()
    const popup = wrapper.find('[data-test="mention-popup"]')
    expect(popup.exists()).toBe(true)

    const items = wrapper.findAll('[data-test="mention-item"]')
    expect(items.length).toBe(2)
    expect(items[0].text()).toContain('高等数学')
    expect(items[1].text()).toContain('线性代数.pdf')

    // 点击第二个候选（文档）
    await items[1].trigger('click')
    const pickEmitted = wrapper.emitted('pick')
    expect(pickEmitted).toBeTruthy()
    expect(pickEmitted[0][0]).toEqual({ key: 'doc:2', kind: 'doc', id: '2', label: '线性代数.pdf' })
    expect(wrapper.emitted('update:mentionOpen')?.[0][0]).toBe(false)
  })

  it('候选浮层通过键盘 Enter 选择当前高亮项', async () => {
    const wrapper = mount(ScopeChips, {
      props: {
        chips: [],
        mentionOpen: true,
        candidates: [
          { key: 'doc:1', kind: 'doc', id: '1', label: 'ml.pdf' },
        ],
      },
    })
    await flushPromises()
    const item = wrapper.find('[data-test="mention-item"]')
    await item.trigger('keydown.enter')
    expect(wrapper.emitted('pick')?.[0][0].id).toBe('1')
  })

  it('无匹配候选时展示空状态提示', async () => {
    const wrapper = mount(ScopeChips, {
      props: {
        chips: [{ key: 'doc:1', kind: 'doc', id: '1', label: 'ml.pdf' }],
        mentionOpen: true,
        candidates: [{ key: 'doc:1', kind: 'doc', id: '1', label: 'ml.pdf' }],
      },
    })
    await flushPromises()
    expect(wrapper.find('[data-test="mention-popup"]').text()).toContain('所有文档已在引用范围中')
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
