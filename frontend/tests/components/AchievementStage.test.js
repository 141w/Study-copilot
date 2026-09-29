import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import AchievementStage from '@/components/profile/AchievementStage.vue'
import AchievementWallDropdown from '@/components/profile/AchievementWallDropdown.vue'
import { ACHIEVEMENT_CATALOG, getAchievement } from '@/components/profile/achievementCatalog'
import {
  buildDefaultContext,
  computeStreakDays,
  evaluateUnlocks,
  meetsRule,
  visibleAchievements
} from '@/components/profile/achievementUnlock'

const sampleSticker = {
  id: 'sample',
  label: '示例',
  img: 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7',
  x: 10,
  y: 20,
  rot: 0
}

describe('AchievementStage', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('默认无贴纸且无文案占位', () => {
    const wrapper = mount(AchievementStage)
    expect(wrapper.find('[data-test="achievement-stage"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="achievement-empty"]').exists()).toBe(false)
    expect(wrapper.text().trim()).toBe('')
  })

  it('传入 stickers 时渲染贴纸图片', () => {
    const wrapper = mount(AchievementStage, {
      props: { stickers: [sampleSticker] }
    })
    const el = wrapper.find('[data-test="sticker-sample"]')
    expect(el.exists()).toBe(true)
    expect(el.find('img').attributes('src')).toContain('data:image')
  })

  it('拖拽后写入 localStorage 落点', async () => {
    const wrapper = mount(AchievementStage, {
      props: { stickers: [sampleSticker] },
      attachTo: document.body
    })
    const stage = wrapper.find('[data-test="achievement-stage"]')
    Object.defineProperty(stage.element, 'getBoundingClientRect', {
      value: () => ({ left: 0, top: 0, width: 1000, height: 400, right: 1000, bottom: 400 })
    })
    const stickerEl = wrapper.find('[data-test="sticker-sample"]').element
    stickerEl.setPointerCapture = vi.fn()
    stickerEl.releasePointerCapture = vi.fn()
    stickerEl.dispatchEvent(new PointerEvent('pointerdown', { pointerId: 1, bubbles: true }))
    stickerEl.dispatchEvent(
      new PointerEvent('pointermove', { pointerId: 1, clientX: 500, clientY: 100, bubbles: true })
    )
    stickerEl.dispatchEvent(new PointerEvent('pointerup', { pointerId: 1, bubbles: true }))
    await flushPromises()
    await nextTick()
    const layout = JSON.parse(localStorage.getItem('study_copilot_achievement_layout'))
    expect(layout.sample.x).toBeCloseTo(50, 1)
    // 拖拽不应触发 remove
    expect(wrapper.emitted('remove')).toBeFalsy()
    wrapper.unmount()
  })

  it('轻点贴纸触发 remove（点击移除）', async () => {
    const wrapper = mount(AchievementStage, {
      props: { stickers: [sampleSticker] },
      attachTo: document.body
    })
    const stickerEl = wrapper.find('[data-test="sticker-sample"]').element
    stickerEl.setPointerCapture = vi.fn()
    stickerEl.releasePointerCapture = vi.fn()
    stickerEl.dispatchEvent(new PointerEvent('pointerdown', { pointerId: 1, bubbles: true }))
    stickerEl.dispatchEvent(new PointerEvent('pointerup', { pointerId: 1, bubbles: true }))
    await nextTick()
    expect(wrapper.emitted('remove')?.[0]).toEqual(['sample'])
    wrapper.unmount()
  })

  it('从成就墙拖放 drop 时按落点坐标 emit', async () => {
    const wrapper = mount(AchievementStage, {
      props: { stickers: [], dropTarget: true },
      attachTo: document.body
    })
    const stage = wrapper.find('[data-test="achievement-stage"]')
    Object.defineProperty(stage.element, 'getBoundingClientRect', {
      value: () => ({ left: 0, top: 0, width: 1000, height: 400, right: 1000, bottom: 400 })
    })
    const dt = {
      getData: (k) => (k === 'text/achievement-id' ? 'first-document' : ''),
      effectAllowed: 'copy',
      dropEffect: 'copy'
    }
    const over = new Event('dragover', { bubbles: true, cancelable: true })
    Object.defineProperty(over, 'dataTransfer', { value: dt })
    stage.element.dispatchEvent(over)
    const drop = new Event('drop', { bubbles: true, cancelable: true })
    Object.defineProperty(drop, 'dataTransfer', { value: dt })
    Object.defineProperty(drop, 'clientX', { value: 250 })
    Object.defineProperty(drop, 'clientY', { value: 80 })
    stage.element.dispatchEvent(drop)
    await nextTick()
    const payload = wrapper.emitted('drop')?.[0]?.[0]
    expect(payload.id).toBe('first-document')
    expect(payload.x).toBeCloseTo(25, 1)
    expect(payload.y).toBeCloseTo(20, 1)
    wrapper.unmount()
  })
})

describe('AchievementWallDropdown 仅展示已解锁', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('未解锁成就绝不进入下拉', async () => {
    const unlocked = visibleAchievements([])
    expect(unlocked).toEqual([])
    const wrapper = mount(AchievementWallDropdown, {
      props: { modelValue: true, achievements: unlocked },
      slots: { trigger: `<button data-test="trigger-btn">成就墙</button>` },
      attachTo: document.body
    })
    await nextTick()
    expect(wrapper.find('[data-test="achievement-wall-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-test^="wall-item-"]').exists()).toBe(false)
    // 目录里有成就，但 UI 不可见
    expect(ACHIEVEMENT_CATALOG.length).toBeGreaterThan(0)
    for (const a of ACHIEVEMENT_CATALOG) {
      expect(wrapper.find(`[data-test="wall-item-${a.id}"]`).exists()).toBe(false)
    }
    wrapper.unmount()
  })

  it('仅渲染已解锁条目并可点选上墙', async () => {
    const unlocked = visibleAchievements(['first-document'])
    expect(unlocked).toHaveLength(1)
    const wrapper = mount(AchievementWallDropdown, {
      props: { modelValue: true, achievements: unlocked },
      slots: { trigger: `<button data-test="trigger-btn">成就墙</button>` },
      attachTo: document.body
    })
    await nextTick()
    expect(wrapper.find('[data-test="wall-item-first-document"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="wall-item-first-ask"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('将贴纸拖拽到上方区域')
    await wrapper.find('[data-test="wall-item-first-document"]').trigger('click')
    expect(wrapper.emitted('select')?.[0]).toEqual(['first-document'])
    wrapper.unmount()
  })
})

describe('成就触发条件', () => {
  it('目录 18 枚且规则完备', () => {
    expect(ACHIEVEMENT_CATALOG).toHaveLength(18)
    for (const a of ACHIEVEMENT_CATALOG) {
      expect(a.rule).toBeTruthy()
      expect(a.image).toBeTruthy()
      expect(a.unlockRule).toBeTruthy()
    }
  })

  it('document_count / quiz_perfect / streak 规则求值', () => {
    expect(meetsRule({ type: 'document_count', gte: 1 }, buildDefaultContext({ documentCount: 0 }))).toBe(false)
    expect(meetsRule({ type: 'document_count', gte: 1 }, buildDefaultContext({ documentCount: 1 }))).toBe(true)
    expect(meetsRule({ type: 'quiz_perfect' }, buildDefaultContext({ quizPerfect: true }))).toBe(true)
    expect(meetsRule({ type: 'streak_days', gte: 7 }, buildDefaultContext({ streakDays: 6 }))).toBe(false)
    expect(meetsRule({ type: 'streak_days', gte: 7 }, buildDefaultContext({ streakDays: 7 }))).toBe(true)
  })

  it('computeStreakDays 连续统计', () => {
    const days = ['2026-09-10', '2026-09-11', '2026-09-12']
    expect(computeStreakDays(days, new Date('2026-09-12T12:00:00Z'))).toBe(3)
    expect(computeStreakDays(days, new Date('2026-09-13T12:00:00Z'))).toBe(3)
    expect(computeStreakDays(['2026-09-01'], new Date('2026-09-12T12:00:00Z'))).toBe(0)
  })

  it('evaluateUnlocks 只返回新解锁 id', () => {
    const ctx = buildDefaultContext({ documentCount: 30, chatSessionCount: 1 })
    const fresh = evaluateUnlocks(ctx, [])
    expect(fresh).toContain('first-document')
    expect(fresh).toContain('first-ask')
    expect(fresh).toContain('knowledge-librarian')
    const again = evaluateUnlocks(ctx, fresh)
    expect(again).toEqual([])
    expect(getAchievement('first-document')?.rule).toEqual({ type: 'document_count', gte: 1 })
  })
})
