<template>
  <Teleport to="body">
    <div
      v-if="visible && source"
      ref="floatRef"
      class="chat-citation-float"
      data-test="citation-float"
      role="tooltip"
      :style="floatStyle"
      @mouseenter="emit('enter')"
      @mouseleave="emit('leave')"
    >
      <!-- 顶部元信息 (复刻 WeKnora chat-citation-float__title) -->
      <div class="chat-citation-float__header flex items-center justify-between gap-2 pb-2 mb-2 border-b border-[var(--border-subtle,rgba(0,0,0,0.06))]">
        <div class="flex items-center gap-1.5 min-w-0 flex-1">
          <span class="chat-citation-float__index shrink-0 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold bg-[var(--color-primary-light,rgba(16,185,129,0.1))] text-[var(--color-primary,#10b981)]">
            [{{ source.index }}]
          </span>
          <span class="chat-citation-float__title font-semibold text-xs text-[var(--text-primary)] truncate" :title="displayName">
            {{ displayName }}
          </span>
        </div>
        <span v-if="pageLabel" class="chat-citation-float__page text-[10px] px-1.5 py-0.5 rounded font-mono text-[var(--text-muted)] bg-[var(--bg-secondary)] shrink-0" data-test="citation-float-page">
          {{ pageLabel }}
        </span>
      </div>

      <!-- 切片正文 (复刻 WeKnora chat-citation-float__body，最大高度 200px 优雅滚动) -->
      <div class="chat-citation-float__body max-h-[190px] overflow-y-auto text-[12px] leading-relaxed text-[var(--text-secondary)] pr-1 scrollbar-thin select-text" data-test="citation-float-text">
        {{ source.text || '无正文摘要' }}
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { Source } from '@/types/models'
import { clampFloatPosition, type CitationAnchor } from '@/composables/useChatCitationPopover'

const props = defineProps<{
  visible: boolean
  source: Source | null
  anchor: CitationAnchor | null
}>()

const emit = defineEmits<{
  (e: 'enter'): void
  (e: 'leave'): void
}>()

const floatRef = ref<HTMLElement | null>(null)
const pos = ref<{ left: number; top: number } | null>(null)

const DEFAULT_SIZE = { width: 320, height: 140 }

const displayName = computed(() => {
  const s = props.source
  if (!s) return ''
  return s.source || s.document_id || '未知来源'
})

const pageLabel = computed(() => {
  const p = props.source?.page
  if (p == null || p === '') return ''
  return `P${p}`
})

function measureSize(): { width: number; height: number } {
  const rect = floatRef.value?.getBoundingClientRect()
  const width = rect && rect.width > 0 ? rect.width : DEFAULT_SIZE.width
  const height = rect && rect.height > 0 ? rect.height : DEFAULT_SIZE.height
  return { width, height }
}

function updatePosition(): void {
  if (!props.anchor) {
    pos.value = null
    return
  }
  const viewport = {
    width: typeof window !== 'undefined' ? window.innerWidth : 1200,
    height: typeof window !== 'undefined' ? window.innerHeight : 800,
  }
  pos.value = clampFloatPosition(props.anchor, measureSize(), viewport)
}

const floatStyle = computed(() => {
  if (!pos.value) {
    if (!props.anchor) return { visibility: 'hidden' as const }
    return {
      left: `${props.anchor.x}px`,
      top: `${props.anchor.y + props.anchor.height + 8}px`,
      visibility: 'hidden' as const,
    }
  }
  return {
    left: `${pos.value.left}px`,
    top: `${pos.value.top}px`,
    visibility: 'visible' as const,
  }
})

watch(
  () => [props.visible, props.anchor] as const,
  async ([vis]) => {
    if (!vis) {
      pos.value = null
      return
    }
    await nextTick()
    updatePosition()
    await nextTick()
    updatePosition()
  },
  { immediate: true, deep: true },
)

defineExpose({ updatePosition, floatRef })
</script>

<style scoped>
/* 参照 WeKnora chat-citations.less 浮层规范 */
.chat-citation-float {
  position: fixed;
  z-index: 9999;
  width: 320px;
  max-width: calc(100vw - 24px);
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--bg-primary, #ffffff);
  border: 1px solid var(--border-default, #e5e7eb);
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.12), 0 8px 10px -6px rgba(0, 0, 0, 0.08);
  pointer-events: auto;
  animation: floatFadeIn 0.15s ease-out;
}

.dark .chat-citation-float {
  background: #18181b;
  border-color: #27272a;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.5);
}

@keyframes floatFadeIn {
  from {
    opacity: 0;
    transform: scale(0.97) translateY(-3px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.scrollbar-thin::-webkit-scrollbar {
  width: 3px;
}
.scrollbar-thin::-webkit-scrollbar-thumb {
  background: var(--border-default, #e5e7eb);
  border-radius: 999px;
}
</style>
