<template>
  <Teleport to="body">
    <div
      v-if="visible && source"
      ref="floatRef"
      class="citation-float"
      data-test="citation-float"
      role="tooltip"
      :style="floatStyle"
      @mouseenter="emit('enter')"
      @mouseleave="emit('leave')"
    >
      <div class="citation-float__meta">
        <span class="citation-float__index" data-test="citation-float-index">[{{ source.index }}]</span>
        <span class="citation-float__name" :title="displayName">{{ displayName }}</span>
        <span v-if="pageLabel" class="citation-float__page" data-test="citation-float-page">{{ pageLabel }}</span>
      </div>
      <p class="citation-float__text" data-test="citation-float-text">
        {{ source.text || '无正文摘要' }}
      </p>
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
    // 尚未测量完成时先放到锚点下方，避免闪到 (0,0)
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
    // 布局完成后再夹紧一次（首次测量可能拿不到真实高度）
    await nextTick()
    updatePosition()
  },
  { immediate: true, deep: true },
)

defineExpose({ updatePosition, floatRef })
</script>

<!--
  样式说明：与来源卡同语言——无边框、同色系卡片，Teleport 到 body 后
  不受消息容器 overflow 裁剪。令牌取自 variables.css。
-->
<style scoped>
.citation-float {
  position: fixed;
  z-index: 4000;
  width: 320px;
  max-width: calc(100vw - 16px);
  max-height: 220px;
  overflow-y: auto;
  padding: 0.625rem 0.75rem;
  border-radius: var(--radius-xl);
  background: var(--bg-primary);
  border: 1px solid var(--border-default);
  box-shadow: 0 8px 24px color-mix(in srgb, var(--text-primary) 12%, transparent);
  pointer-events: auto;
}
.dark .citation-float {
  background: #111113;
  border-color: rgba(255, 255, 255, 0.1);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
}

.citation-float__meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
  margin-bottom: 0.375rem;
}
.citation-float__index {
  flex-shrink: 0;
  min-width: 20px;
  height: 20px;
  padding: 0 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--surface-card);
  color: var(--text-primary);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  font-weight: 600;
}
.citation-float__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
}
.citation-float__page {
  flex-shrink: 0;
  padding: 2px 6px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-xs);
  background: var(--surface-card);
  color: var(--text-muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  line-height: 1;
}
.citation-float__text {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.65;
  color: var(--text-secondary);
  overflow-wrap: break-word;
  white-space: pre-wrap;
}
.dark .citation-float__text {
  color: #d4d4d8;
}
</style>
