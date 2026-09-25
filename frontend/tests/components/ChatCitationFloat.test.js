import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatCitationFloat from '@/components/chat/ChatCitationFloat.vue'
import {
  clampFloatPosition,
  useChatCitationPopover,
} from '@/composables/useChatCitationPopover'

function mountFloat(props) {
  return mount(ChatCitationFloat, {
    props: {
      visible: true,
      source: {
        index: 1,
        source: 'rag_paper.pdf',
        page: '3',
        text: 'RAG 架构解析切片原文',
        document_id: 'd-1',
      },
      anchor: { x: 100, y: 200, width: 24, height: 16 },
      ...props,
    },
    attachTo: document.body,
  })
}

function getFloatEl() {
  return document.body.querySelector('[data-test="citation-float"]')
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ChatCitationFloat — 引用悬停浮层', () => {
  it('展示切片原文与页码，并标注来源名/序号', async () => {
    const wrapper = mountFloat()
    await wrapper.vm.$nextTick()

    const el = getFloatEl()
    expect(el).toBeTruthy()
    expect(el.getAttribute('data-test')).toBe('citation-float')
    expect(el.textContent).toContain('RAG 架构解析切片原文')
    expect(el.textContent).toContain('[1]')
    expect(el.textContent).toContain('rag_paper.pdf')
    expect(el.querySelector('[data-test="citation-float-page"]').textContent).toContain('P3')
    expect(el.querySelector('[data-test="citation-float-text"]').textContent).toContain(
      'RAG 架构解析切片原文',
    )
    wrapper.unmount()
  })

  it('visible=false 时不渲染浮层', async () => {
    const wrapper = mountFloat({ visible: false, source: null, anchor: null })
    await wrapper.vm.$nextTick()
    expect(getFloatEl()).toBeNull()
    wrapper.unmount()
  })

  it('无 page 时不渲染页码徽章', async () => {
    const wrapper = mountFloat({
      source: { index: 2, source: 'a.pdf', text: '无页码切片' },
    })
    await wrapper.vm.$nextTick()
    const el = getFloatEl()
    expect(el.querySelector('[data-test="citation-float-page"]')).toBeNull()
    expect(el.textContent).toContain('无页码切片')
    wrapper.unmount()
  })

  it('浮层 enter/leave 事件上抛（供 80ms/120ms 防抖接线）', async () => {
    const wrapper = mountFloat()
    await wrapper.vm.$nextTick()
    const el = getFloatEl()

    el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: false }))
    el.dispatchEvent(new MouseEvent('mouseleave', { bubbles: false }))
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('enter')).toBeTruthy()
    expect(wrapper.emitted('leave')).toBeTruthy()
    wrapper.unmount()
  })

  it('定位样式：优先锚点下方，视口夹紧后不出界', async () => {
    // jsdom 默认 innerWidth/Height = 1024 x 768
    const wrapper = mountFloat({
      anchor: { x: 100, y: 200, width: 24, height: 16 },
    })
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const el = getFloatEl()
    const style = el.style
    // 默认浮层 320x140，放在 y+height+8 = 224
    expect(parseFloat(style.left)).toBeGreaterThanOrEqual(8)
    expect(parseFloat(style.top)).toBeGreaterThanOrEqual(8)
    expect(parseFloat(style.left) + 320).toBeLessThanOrEqual(window.innerWidth + 1)
    expect(parseFloat(style.top) + 140).toBeLessThanOrEqual(window.innerHeight + 1)
    wrapper.unmount()
  })
})

describe('clampFloatPosition — 视口夹紧算法', () => {
  const vp = { width: 1000, height: 800 }
  const size = { width: 320, height: 140 }

  it('空间充足时放在角标下方、左对齐锚点', () => {
    const pos = clampFloatPosition(
      { x: 100, y: 200, width: 24, height: 16 },
      size,
      vp,
    )
    expect(pos.left).toBe(100)
    expect(pos.top).toBe(200 + 16 + 8)
  })

  it('右侧越界时向左夹紧到视口内', () => {
    const pos = clampFloatPosition(
      { x: 900, y: 100, width: 24, height: 16 },
      size,
      vp,
    )
    expect(pos.left).toBe(1000 - 320 - 8)
    expect(pos.top).toBe(100 + 16 + 8)
  })

  it('下方放不下且上方能放下时翻转到锚点上方', () => {
    const pos = clampFloatPosition(
      { x: 100, y: 700, width: 24, height: 16 },
      size,
      vp,
    )
    // 700+16+8+140 > 800-8 → 翻转
    expect(pos.top).toBe(700 - 8 - 140)
    expect(pos.left).toBe(100)
  })

  it('上下都放不下时夹紧在视口内（不越出底边）', () => {
    const pos = clampFloatPosition(
      { x: 50, y: 790, width: 24, height: 8 },
      { width: 320, height: 500 },
      vp,
    )
    expect(pos.top + 500).toBeLessThanOrEqual(800)
    expect(pos.top).toBeGreaterThanOrEqual(8)
  })
})

describe('useChatCitationPopover — 80ms 入 / 120ms 出 防抖', () => {
  it('hover 角标后延迟 80ms 显示，120ms 内移出则不显示', async () => {
    vi.useFakeTimers()
    try {
      const source = { index: 3, source: 'x.pdf', text: '切片', page: '1' }
      const pop = useChatCitationPopover({
        sources: () => [source],
        delayIn: 80,
        delayOut: 120,
      })

      // 80ms 内移出：不应显示
      pop.scheduleShow(3, { x: 1, y: 2, width: 3, height: 4 })
      vi.advanceTimersByTime(50)
      pop.scheduleHide()
      vi.advanceTimersByTime(200)
      expect(pop.visible.value).toBe(false)

      // 停留超过 80ms：显示
      pop.scheduleShow(3, { x: 1, y: 2, width: 3, height: 4 })
      vi.advanceTimersByTime(80)
      expect(pop.visible.value).toBe(true)
      expect(pop.activeSource.value?.index).toBe(3)
      expect(pop.anchor.value).toEqual({ x: 1, y: 2, width: 3, height: 4 })

      // 移出后 120ms 才隐藏
      pop.scheduleHide()
      vi.advanceTimersByTime(100)
      expect(pop.visible.value).toBe(true)
      vi.advanceTimersByTime(30)
      expect(pop.visible.value).toBe(false)

      // 浮层 enter 取消 hide
      pop.scheduleShow(3, { x: 1, y: 2, width: 3, height: 4 })
      vi.advanceTimersByTime(80)
      expect(pop.visible.value).toBe(true)
      pop.scheduleHide()
      pop.onFloatEnter()
      vi.advanceTimersByTime(500)
      expect(pop.visible.value).toBe(true)
    } finally {
      vi.useRealTimers()
    }
  })

  it('未知 index 不弹出', async () => {
    vi.useFakeTimers()
    try {
      const pop = useChatCitationPopover({ sources: () => [], delayIn: 80, delayOut: 120 })
      pop.scheduleShow(99, { x: 0, y: 0, width: 1, height: 1 })
      vi.advanceTimersByTime(120)
      expect(pop.visible.value).toBe(false)
      expect(pop.activeSource.value).toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })
})
