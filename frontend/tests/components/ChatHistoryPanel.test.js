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

/**
 * F4 · 后端真实序列化格式（fix(phase2-audit): F4）
 *
 * 原测试用 toISOString()（带 Z）造数，恰好绕过 bug。后端输出的是
 * naive UTC 空格分隔串 `str(datetime)`，如 "2026-09-29 03:24:11.123"，
 * 前端 new Date() 按本地时区解释 → 偏 8 小时。
 */
describe('ChatHistoryPanel F4 时间解析与本地时区分组', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useChatStore()
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

  it('UTC 00:30（东八区 08:30）归入「今天」而非「昨天」', async () => {
    // 后端旧格式：naive UTC、空格分隔
    // 东八区当天 08:30 = UTC 前一日 16:30... 用「东八区今天 08:30」对应 UTC 昨天 16:30
    // 更直接：东八区今天 08:30 的 UTC 是 昨天 00:30... 不对。
    // 东八区 2026-09-29 08:30 = UTC 2026-09-29 00:30
    store.sessions = [
      {
        session_id: 's-utc-0030',
        title: '今晨会话',
        created_at: '2026-09-29 00:30:00.000'
      }
    ]
    // 冻结「现在」为东八区 2026-09-29 12:00，使上述时刻落在「今天」
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-29T12:00:00+08:00'))
    const wrapper = mountPanel()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="session-group-today"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('今晨会话')
    expect(wrapper.find('[data-test="session-group-yesterday"]').exists()).toBe(false)
    vi.useRealTimers()
  })

  it('UTC 17:00（东八区次日 01:00）归入「今天」', async () => {
    // 东八区 2026-09-30 01:00 = UTC 2026-09-29 17:00
    store.sessions = [
      {
        session_id: 's-utc-1700',
        title: '跨零点会话',
        created_at: '2026-09-29 17:00:00.000'
      }
    ]
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-30T12:00:00+08:00'))
    const wrapper = mountPanel()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="session-group-today"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('跨零点会话')
    vi.useRealTimers()
  })

  it('畸形输入不产生 Invalid Date 文案', async () => {
    store.sessions = [
      { session_id: 's-bad', title: '坏时间', created_at: '' },
      { session_id: 's-bad2', title: '坏时间2', created_at: 'not-a-date' },
      { session_id: 's-ok', title: '正常', created_at: '2026-09-29 00:30:00.000' }
    ]
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-29T12:00:00+08:00'))
    const wrapper = mountPanel()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).not.toContain('Invalid Date')
    expect(wrapper.text()).not.toContain('NaN')
    vi.useRealTimers()
  })

  it('parseTimestamp 工具解析后端空格格式与 ISO Z 格式', async () => {
    const { parseTimestamp } = await import('@/utils/parseTime')
    const a = parseTimestamp('2026-09-29 00:30:00.000')
    const b = parseTimestamp('2026-09-29T00:30:00.000Z')
    expect(a).toBeInstanceOf(Date)
    expect(Number.isFinite(a.getTime())).toBe(true)
    // 两种写法若都表示 UTC 同一时刻，毫秒应相等
    expect(a.getTime()).toBe(b.getTime())
    // 畸形返回 null 而非 Invalid Date
    expect(parseTimestamp('nope')).toBeNull()
    expect(parseTimestamp('')).toBeNull()
  })
})

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
