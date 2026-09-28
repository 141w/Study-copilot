import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn() }
}))

import { setActivePinia, createPinia } from 'pinia'
import ChatHistoryPanel from '@/components/chat/ChatHistoryPanel.vue'
import { useChatStore } from '@/stores/chat'

function isoDaysAgo(days, hour = 12) {
  const d = new Date()
  d.setDate(d.getDate() - days)
  d.setHours(hour, 0, 0, 0)
  return d.toISOString()
}

describe('ChatHistoryPanel 时间分组与筛选（P0-C）', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useChatStore()
    store.sessions = [
      { session_id: 's1', title: '今天的对话', created_at: isoDaysAgo(0) },
      { session_id: 's2', title: '昨天的对话', created_at: isoDaysAgo(1) },
      { session_id: 's3', title: '更早的对话', created_at: isoDaysAgo(20) },
    ]
  })

  function mountPanel() {
    return mount(ChatHistoryPanel, {
      props: { visible: true },
      global: {
        stubs: {
          'el-icon': true,
          Teleport: true
        }
      }
    })
  }

  it('按今天/昨天/更早分组渲染', async () => {
    const wrapper = mountPanel()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="session-group-today"]').text()).toContain('今天')
    expect(wrapper.find('[data-test="session-group-yesterday"]').text()).toContain('昨天')
    expect(wrapper.find('[data-test="session-group-older"]').text()).toContain('更早')
    expect(wrapper.text()).toContain('今天的对话')
    expect(wrapper.text()).toContain('昨天的对话')
    expect(wrapper.text()).toContain('更早的对话')
  })

  it('点时间筛选只显示对应分组', async () => {
    const wrapper = mountPanel()
    await wrapper.vm.$nextTick()
    await wrapper.find('[data-test="time-filter-today"]').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('今天的对话')
    expect(wrapper.text()).not.toContain('昨天的对话')
    expect(wrapper.find('[data-test="session-group-yesterday"]').exists()).toBe(false)
  })

  it('内联重命名：点编辑后出现输入框', async () => {
    const wrapper = mountPanel()
    await wrapper.vm.$nextTick()
    await wrapper.find('[aria-label="重命名对话"]').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('input').exists()).toBe(true)
  })
})
