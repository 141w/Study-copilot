import { getCurrentInstance, onBeforeUnmount, ref, type Ref } from 'vue'
import type { Source } from '@/types/models'

/** 角标锚点矩形（getBoundingClientRect 的可序列化子集） */
export interface CitationAnchor {
  x: number
  y: number
  width: number
  height: number
}

export interface UseChatCitationPopoverOptions {
  /** 解析 index → Source 的数据源 */
  sources: Ref<Source[] | undefined> | (() => Source[] | undefined)
  /** 入场防抖（ms），默认 80 */
  delayIn?: number
  /** 离场防抖（ms），默认 120 */
  delayOut?: number
}

/** 浮层定位：优先在角标下方左对齐，越界时翻转/夹紧到视口内 */
export function clampFloatPosition(
  anchor: CitationAnchor,
  floatSize: { width: number; height: number },
  viewport: { width: number; height: number },
  gap = 8,
  margin = 8,
): { left: number; top: number } {
  let left = anchor.x
  let top = anchor.y + anchor.height + gap

  // 下方放不下且上方能放下 → 翻转到上方
  const overflowBottom = top + floatSize.height > viewport.height - margin
  const spaceAbove = anchor.y - gap - floatSize.height
  if (overflowBottom && spaceAbove >= margin) {
    top = spaceAbove
  }

  const maxLeft = Math.max(margin, viewport.width - floatSize.width - margin)
  const maxTop = Math.max(margin, viewport.height - floatSize.height - margin)
  left = Math.min(Math.max(margin, left), maxLeft)
  top = Math.min(Math.max(margin, top), maxTop)
  return { left, top }
}

/**
 * 引用角标 hover 浮层状态机。
 * - 入场 80ms 防抖 / 离场 120ms 防抖（可配）
 * - 移入浮层取消离场计时，移出浮层重新计时
 */
export function useChatCitationPopover(opts: UseChatCitationPopoverOptions) {
  const visible = ref(false)
  const activeSource = ref<Source | null>(null)
  const anchor = ref<CitationAnchor | null>(null)

  const delayIn = opts.delayIn ?? 80
  const delayOut = opts.delayOut ?? 120

  let inTimer: ReturnType<typeof setTimeout> | null = null
  let outTimer: ReturnType<typeof setTimeout> | null = null

  function cancelTimers(): void {
    if (inTimer != null) {
      clearTimeout(inTimer)
      inTimer = null
    }
    if (outTimer != null) {
      clearTimeout(outTimer)
      outTimer = null
    }
  }

  function resolveSources(): Source[] {
    const list = typeof opts.sources === 'function' ? opts.sources() : opts.sources.value
    return Array.isArray(list) ? list : []
  }

  function findSource(index: number): Source | null {
    return resolveSources().find((s) => s != null && s.index === index) ?? null
  }

  function scheduleShow(index: number, rect: CitationAnchor): void {
    cancelTimers()
    inTimer = setTimeout(() => {
      inTimer = null
      const src = findSource(index)
      if (!src) return
      activeSource.value = src
      anchor.value = {
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
      }
      visible.value = true
    }, delayIn)
  }

  function scheduleHide(): void {
    cancelTimers()
    outTimer = setTimeout(() => {
      outTimer = null
      visible.value = false
      activeSource.value = null
      anchor.value = null
    }, delayOut)
  }

  function rectOf(el: Element): CitationAnchor {
    const r = el.getBoundingClientRect()
    return { x: r.left, y: r.top, width: r.width, height: r.height }
  }

  /** 内容容器 mouseover：命中 .source-badge 则调度显示 */
  function onContentMouseOver(e: Event): void {
    const target = e.target as HTMLElement | null
    const badge = target?.closest?.('.source-badge') as HTMLElement | null
    if (!badge) return
    const idx = Number(badge.getAttribute('data-index'))
    if (!Number.isFinite(idx)) return
    scheduleShow(idx, rectOf(badge))
  }

  /** 内容容器 mouseout：离开角标则调度隐藏 */
  function onContentMouseOut(e: Event): void {
    const target = e.target as HTMLElement | null
    const badge = target?.closest?.('.source-badge') as HTMLElement | null
    if (!badge) return
    scheduleHide()
  }

  /** 浮层自身 enter：取消离场隐藏 */
  function onFloatEnter(): void {
    cancelTimers()
  }

  /** 浮层自身 leave：重新走离场防抖 */
  function onFloatLeave(): void {
    scheduleHide()
  }

  function close(): void {
    cancelTimers()
    visible.value = false
    activeSource.value = null
    anchor.value = null
  }

  // 仅在组件 setup 内注册卸载钩子（纯函数单测里直接调用时不挂生命周期）
  if (getCurrentInstance()) {
    onBeforeUnmount(() => {
      cancelTimers()
    })
  }

  return {
    visible,
    activeSource,
    anchor,
    onContentMouseOver,
    onContentMouseOut,
    onFloatEnter,
    onFloatLeave,
    scheduleShow,
    scheduleHide,
    close,
  }
}
