<template>
  <nav
    v-if="sections.length"
    class="pr-nav"
    aria-label="消息定位"
    data-test="proximity-sidebar"
  >
    <div
      class="pr-stack"
      @mouseenter="pointerInside = true"
      @mouseleave="onStackLeave"
    >
      <button
        v-for="s in sections"
        :key="s.id"
        type="button"
        class="pr-chip"
        :class="{
          'pr-chip--active': s.id === activeId,
          [`pr-chip--${kindOf(s)}`]: true,
        }"
        :aria-current="s.id === activeId ? 'location' : undefined"
        :aria-label="`跳到 ${s.label}`"
        :data-test="`proximity-tick-${s.id}`"
        :data-active="s.id === activeId ? 'true' : 'false'"
        @mouseenter="onChipEnter(s.id)"
        @focus="onChipEnter(s.id)"
        @blur="hoverId = null"
        @click="selectSection(s.id)"
      >
        <span class="pr-chip__bar" />
      </button>
    </div>

    <!-- 悬停预览：浮在胶囊左侧，跟随 chip 垂直位置 -->
    <Transition
      enter-active-class="transition duration-120 ease-out"
      enter-from-class="opacity-0 translate-x-1"
      enter-to-class="opacity-100 translate-x-0"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="hovered"
        class="pr-preview"
        :style="{ top: `${hoverTop}px` }"
        data-test="proximity-preview"
      >
        <span class="pr-preview__role">{{ roleLabel(hovered) }}</span>
        <span class="pr-preview__text">{{ excerpt(hovered) }}</span>
      </div>
    </Transition>
  </nav>
</template>

<script lang="ts">
export type ProximityKind = 'title' | 'subtitle' | 'section' | 'body'
export type ProximitySection = {
  id: string
  label: string
  kind?: ProximityKind
  level?: 1 | 2 | 3 | 4 | 5 | 6
  /** 可选：悬停预览正文摘要（未传则用 label） */
  preview?: string
  /** 可选：角色名（我 / Copilot / 研讨） */
  role?: string
}
</script>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    sections: ProximitySection[]
    activeOffset?: number
  }>(),
  { activeOffset: 0.35 }
)

const emit = defineEmits<{ (e: 'navigate', id: string): void }>()

const activeId = ref<string | undefined>(props.sections[0]?.id)
const hoverId = ref<string | null>(null)
const pointerInside = ref(false)
const hoverTop = ref(0)
let scrollRaf = 0
let scrollParents: EventTarget[] = []

const hovered = computed(() => {
  if (!hoverId.value) return null
  return props.sections.find((s) => s.id === hoverId.value) || null
})

function kindOf(s: ProximitySection): ProximityKind {
  if (s.kind) return s.kind
  if (s.level === 1) return 'title'
  if (s.level === 2) return 'subtitle'
  if (s.level === 3) return 'section'
  return 'body'
}

function roleLabel(s: ProximitySection): string {
  if (s.role) return s.role
  if (s.kind === 'title') return '研讨'
  if (s.kind === 'section') return '我'
  return 'Copilot'
}

function excerpt(s: ProximitySection): string {
  const raw = s.preview || s.label
  return raw.length > 80 ? `${raw.slice(0, 80)}…` : raw
}

function onChipEnter(id: string): void {
  hoverId.value = id
  const el = document.querySelector(`[data-test="proximity-tick-${id}"]`)
  if (!el) return
  const nav = el.closest('.pr-nav') as HTMLElement | null
  if (!nav) return
  const chipRect = el.getBoundingClientRect()
  const navRect = nav.getBoundingClientRect()
  // 预览浮层垂直中心对齐 chip
  hoverTop.value = chipRect.top + chipRect.height / 2 - navRect.top
}

function onStackLeave(): void {
  pointerInside.value = false
  hoverId.value = null
}

function getScrollParent(el: HTMLElement): EventTarget {
  let parent: HTMLElement | null = el.parentElement
  while (parent) {
    const { overflowY } = window.getComputedStyle(parent)
    if (/(auto|scroll|overlay)/.test(overflowY)) return parent
    parent = parent.parentElement
  }
  return window
}

function selectSection(id: string): void {
  const el = document.getElementById(id)
  activeId.value = id
  hoverId.value = null
  emit('navigate', id)
  if (!el) return
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
}

function updateActiveSection(): void {
  if (!props.sections.length) return
  const anchorY = window.innerHeight * props.activeOffset
  let next = props.sections[0].id
  let shortest = Number.POSITIVE_INFINITY
  for (const s of props.sections) {
    const el = document.getElementById(s.id)
    if (!el) continue
    const rect = el.getBoundingClientRect()
    const contains = rect.top <= anchorY && rect.bottom >= anchorY
    const distance = contains
      ? 0
      : Math.min(Math.abs(rect.top - anchorY), Math.abs(rect.bottom - anchorY))
    if (distance < shortest) {
      shortest = distance
      next = s.id
    }
  }
  activeId.value = next
}

function onScrollScheduled(): void {
  if (scrollRaf) return
  scrollRaf = requestAnimationFrame(() => {
    scrollRaf = 0
    updateActiveSection()
  })
}

function bindScroll(): void {
  unbindScroll()
  const parents = new Set<EventTarget>([window])
  for (const s of props.sections) {
    const el = document.getElementById(s.id)
    if (el) parents.add(getScrollParent(el))
  }
  scrollParents = [...parents]
  for (const p of scrollParents) {
    p.addEventListener('scroll', onScrollScheduled, { passive: true })
  }
  window.addEventListener('resize', onScrollScheduled)
  updateActiveSection()
}

function unbindScroll(): void {
  for (const p of scrollParents) {
    p.removeEventListener('scroll', onScrollScheduled)
  }
  window.removeEventListener('resize', onScrollScheduled)
  scrollParents = []
}

onMounted(bindScroll)
onBeforeUnmount(() => {
  unbindScroll()
  if (scrollRaf) cancelAnimationFrame(scrollRaf)
})
watch(
  () => props.sections.map((s) => s.id).join('|'),
  () => bindScroll()
)
</script>

<style scoped>
/*
 * 项目主题定位轨：右侧固定「胶囊条」索引
 * - 短圆角条（非 110px 细线），长度表达消息权重
 * - 激活 / 悬停加宽 + 主色，符合 monochrome 设计系统
 */
.pr-nav {
  position: absolute;
  top: 0;
  bottom: 0;
  right: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  pointer-events: none;
  overflow: visible;
}

.pr-stack {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  margin-right: 10px;
  max-height: calc(100% - 1.5rem);
  overflow: hidden;
  pointer-events: auto;
  padding: 4px 0;
}

.pr-chip {
  border: 0;
  background: transparent;
  padding: 0;
  margin: 0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  height: 10px;
  outline: none;
}

.pr-chip__bar {
  display: block;
  height: 4px;
  border-radius: 999px;
  background: var(--border-default);
  transition:
    width 0.18s ease,
    background 0.15s ease,
    opacity 0.15s ease;
}

/* 按消息角色/权重表达长度 */
.pr-chip--title .pr-chip__bar {
  width: 22px;
  background: color-mix(in srgb, var(--text-primary) 55%, transparent);
}

.pr-chip--subtitle .pr-chip__bar {
  width: 18px;
  background: color-mix(in srgb, var(--text-primary) 40%, transparent);
}

.pr-chip--section .pr-chip__bar {
  width: 14px;
  background: color-mix(in srgb, var(--text-muted) 55%, transparent);
}

.pr-chip--body .pr-chip__bar {
  width: 10px;
  background: color-mix(in srgb, var(--text-muted) 40%, transparent);
}

/* 悬停：贴近主题色，略加长 */
.pr-chip:hover .pr-chip__bar {
  width: 28px;
  background: var(--text-secondary);
}

/* 激活：主色实心 + 最长 */
.pr-chip--active .pr-chip__bar {
  width: 28px;
  background: var(--color-primary);
  opacity: 1;
}

.pr-chip--active:hover .pr-chip__bar {
  background: var(--color-primary);
}

.pr-chip:focus-visible .pr-chip__bar {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

/* 悬停预览浮层 */
.pr-preview {
  position: absolute;
  right: 42px;
  transform: translateY(-50%);
  width: min(16rem, 36vw);
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid var(--border-default);
  background: var(--surface-card);
  box-shadow: 0 6px 20px rgb(0 0 0 / 0.1);
  pointer-events: none;
  z-index: 40;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.pr-preview__role {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.02em;
}

.pr-preview__text {
  font-size: 12px;
  line-height: 1.45;
  color: var(--text-primary);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

@media (max-width: 900px) {
  .pr-nav {
    display: none;
  }
}
</style>
